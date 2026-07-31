from __future__ import annotations

from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from app.models import Comment, Page, PageToken, Post, SpamWord, UserToken
from app.quet import (
    MIN_FUZZY_KEYWORD_LEN,
    TokenExpiredError,
    build_match_variants,
    delete_comment,
    fetch_all_post_comments,
    get_page_access_token,
    hide_comment,
    text_contains_keyword,
)


class CleanFacebook:
    """Service orchestrator để quét và xử lý comment spam trên Facebook."""

    def __init__(self, version: str = "v20.0"):
        self.version = version

    def get_page_token(self, page: Page, user_token: Optional[UserToken] = None) -> PageToken:
        if not page:
            raise ValueError("Page không hợp lệ")

        source_token = user_token
        if source_token is None:
            source_token = UserToken.objects.order_by("-created_at").first()

        if source_token is None:
            raise ValueError("Chưa có UserToken nào để tạo PageToken")

        existing = (
            PageToken.objects.filter(page=page, user_token=source_token)
            .order_by("-created_at")
            .first()
        )

        if existing and existing.access_token:
            try:
                get_page_access_token(existing.access_token, page.page_fb_id, self.version)
                return existing
            except TokenExpiredError:
                existing.access_token = ""
                existing.expires_at = timezone.now()
                existing.save(update_fields=["access_token", "expires_at"])

        page_access_token = get_page_access_token(
            source_token.access_token,
            page.page_fb_id,
            self.version,
        )

        return PageToken.objects.create(
            user_token=source_token,
            page=page,
            access_token=page_access_token,
            expires_at=None,
        )

    def _load_keywords(self, keywords: Optional[Iterable[str]] = None) -> list[str]:
        if keywords is not None:
            return [kw for kw in keywords if kw and str(kw).strip()]
        return list(SpamWord.objects.order_by("key").values_list("key", flat=True))

    def _match_keywords(self, raw_message: str, author_name: str, keywords: list[str]) -> list[str]:
        normalized_keywords = [(kw, build_match_variants(kw)) for kw in keywords if kw and str(kw).strip()]
        if not normalized_keywords:
            return []

        message_variants = build_match_variants(raw_message or "")
        author_variants = build_match_variants(author_name or "")

        matched = [
            original_kw
            for original_kw, kw_variants in normalized_keywords
            if text_contains_keyword(message_variants, kw_variants)
            or text_contains_keyword(author_variants, kw_variants)
        ]
        return matched

    def _has_strong_signal(self, matched_keywords: list[str]) -> bool:
        return any(len(build_match_variants(kw)["base"]) >= MIN_FUZZY_KEYWORD_LEN for kw in matched_keywords)

    @transaction.atomic
    def scan_and_delete_spam(
        self,
        post: Post | str,
        page_token: PageToken | str,
        keywords: Optional[Iterable[str]] = None,
        action: str = "hide",
    ) -> dict:
        if action not in {"delete", "hide"}:
            raise ValueError("Hành động không hợp lệ. Chỉ hỗ trợ delete hoặc hide")

        if isinstance(post, str):
            post_obj = Post.objects.filter(post_fb_id=post).first()
            if post_obj is None:
                raise ValueError(f"Không tìm thấy bài viết trong DB với post_fb_id={post}")
        else:
            post_obj = post

        if isinstance(page_token, PageToken):
            access_token = page_token.access_token
        else:
            access_token = page_token

        keyword_list = self._load_keywords(keywords)
        comments = fetch_all_post_comments(post_obj.post_fb_id, access_token, self.version)
        processed_count = 0
        saved_count = 0
        action_fn = hide_comment if action == "hide" else delete_comment
        action_label = "ẩn" if action == "hide" else "xóa"

        for item in comments:
            comment_id = item.get("id")
            if not comment_id:
                continue

            raw_message = item.get("message", "") or ""
            author_name = item.get("from", {}).get("name") or ""
            matched_keywords = self._match_keywords(raw_message, author_name, keyword_list)
            if not matched_keywords:
                continue

            if not self._has_strong_signal(matched_keywords):
                continue

            if action_fn(comment_id, access_token, self.version):
                processed_count += 1
                Comment.objects.update_or_create(
                    comment_fb_id=comment_id,
                    defaults={
                        "post": post_obj,
                        "title": raw_message or author_name or comment_id,
                        "status": action,
                    },
                )
                saved_count += 1

        return {
            "processed_count": processed_count,
            "saved_count": saved_count,
            "action": action,
            "action_label": action_label,
            "post": post_obj,
        }

    @transaction.atomic
    def run_for_page(
        self,
        page: Page,
        action: str = "hide",
        user_token: Optional[UserToken] = None,
        keywords: Optional[Iterable[str]] = None,
        posts: Optional[Iterable[Post]] = None,
    ) -> dict:
        if action not in {"delete", "hide"}:
            raise ValueError("Hành động không hợp lệ. Chỉ hỗ trợ delete hoặc hide")

        page_token = self.get_page_token(page, user_token=user_token)
        keyword_list = self._load_keywords(keywords)

        processed_total = 0
        saved_total = 0
        results = []
        posts_to_process = list(posts or page.posts.all())

        for post in posts_to_process:
            try:
                result = self.scan_and_delete_spam(
                    post=post,
                    page_token=page_token,
                    keywords=keyword_list,
                    action=action,
                )
            except TokenExpiredError:
                raise
            except Exception as exc:  # pragma: no cover - safety net for runtime errors
                results.append({"post_id": post.post_fb_id, "error": str(exc)})
                continue

            processed_total += result["processed_count"]
            saved_total += result["saved_count"]
            results.append(result)

        return {
            "page": page,
            "page_token": page_token,
            "processed_count": processed_total,
            "saved_count": saved_total,
            "results": results,
            "action": action,
            "message": f"Đã xử lý {processed_total} comment và lưu {saved_total} comment vào DB",
        }
