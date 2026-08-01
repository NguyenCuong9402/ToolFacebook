import logging
import re
import time
import unicodedata

import requests

from ..models import Comment, PageToken, SpamWord, UserToken

logger = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    """Access token không còn hợp lệ."""


_INVISIBLE_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
_SEPARATOR_BETWEEN_LETTERS_RE = re.compile(
    r"(?<=[^\W\d_])[\s\.\-_,*]+(?=[^\W\d_])",
    re.UNICODE,
)


def strip_diacritics(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    value = _INVISIBLE_CHARS_RE.sub("", text)
    value = _SEPARATOR_BETWEEN_LETTERS_RE.sub("", value)
    value = strip_diacritics(value)
    value = value.lower()
    return re.sub(r"\s+", " ", value).strip()


def normalize_post_fb_id(post_fb_id: str, page_fb_id: str) -> str:
    if not post_fb_id:
        return ""

    normalized = str(post_fb_id).strip()
    if not page_fb_id:
        return normalized

    page_id_str = str(page_fb_id).strip()
    if not page_id_str:
        return normalized

    if normalized.startswith(f"{page_id_str}_") or normalized.startswith(page_id_str):
        return normalized

    if "_" in normalized:
        return normalized

    return f"{page_id_str}_{normalized}"


def is_transient_error(err: dict) -> bool:
    err_code = err.get("code")
    if err_code in (4, 17, 32, 613):
        return True
    if err_code == 1 and "reduce the amount of data" in err.get("message", "").lower():
        return True
    return False


def graph_get_with_retry(url: str, params: dict | None, max_retries: int = 5) -> dict:
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            res = requests.get(url, params=params, timeout=30)
            data = res.json()
            err = data.get("error", {})
            err_code = err.get("code")
            if res.status_code == 200 and "error" not in data:
                return data
            if err_code == 190:
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                logger.warning("[RATE LIMIT] Thử lại sau %ss (lần %s/%s)", delay, attempt, max_retries)
                time.sleep(delay)
                delay *= 2
                continue
            return data
        except TokenExpiredError:
            raise
        except Exception as exc:  # pragma: no cover - defensive path
            if attempt < max_retries:
                logger.warning("[RETRY] Lỗi kết nối: %s", exc)
                time.sleep(delay)
                delay *= 2
                continue
            return {"error": {"message": str(exc)}}
    return {"error": {"message": "max retries exceeded"}}


def get_page_access_token(user_token: str, page_id: str, version: str = "v20.0") -> str:
    if user_token:
        return user_token
    return page_id


def delete_comment(comment_id: str, access_token: str, version: str = "v20.0", max_retries: int = 5) -> bool:
    url = f"https://graph.facebook.com/{version}/{comment_id}"
    params = {"access_token": access_token}
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.delete(url, params=params, timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get("success") is True:
                return True
            err = data.get("error", {})
            if err.get("code") == 190:
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            return False
        except TokenExpiredError:
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            return False
    return False


def hide_comment(comment_id: str, access_token: str, version: str = "v20.0", max_retries: int = 5) -> bool:
    url = f"https://graph.facebook.com/{version}/{comment_id}"
    params = {"access_token": access_token, "is_hidden": "true"}
    delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, params=params, timeout=30)
            data = response.json()
            if response.status_code == 200 and data.get("success") is True:
                return True
            err = data.get("error", {})
            if err.get("code") == 190:
                raise TokenExpiredError(err.get("message", "Access token không hợp lệ"))
            if is_transient_error(err) and attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            return False
        except TokenExpiredError:
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(delay)
                delay *= 2
                continue
            return False
    return False


def get_sub_comments(comment_id: str, access_token: str, version: str = "v20.0") -> list:
    url = f"https://graph.facebook.com/{version}/{comment_id}/comments"
    params = {
        "access_token": access_token,
        "fields": "id,message,from,created_time",
        "limit": 100,
    }
    sub_comments = []
    while url:
        res = graph_get_with_retry(url, params)
        if "data" in res:
            sub_comments.extend(res["data"])
        else:
            logger.warning("[WARNING] Không lấy được sub-comment của %s", comment_id)
        url = res.get("paging", {}).get("next")
        params = None
    return sub_comments


def fetch_all_post_comments(post_id: str, access_token: str, version: str = "v20.0", limit: int = 2000) -> list:
    url = f"https://graph.facebook.com/{version}/{post_id}/comments"
    params = {
        "access_token": access_token,
        "fields": "id,message,from,created_time,comment_count",
        "order": "chronological",
        "limit": limit,
    }

    all_comments = []
    while url:
        data = graph_get_with_retry(url, params if params else None)
        if "data" in data:
            items = data["data"]
            for comment in items:
                all_comments.append(comment)
                if comment.get("comment_count", 1) > 0:
                    replies = get_sub_comments(comment["id"], access_token, version)
                    all_comments.extend(replies)
            url = data.get("paging", {}).get("next")
            params = None
        else:
            logger.error("[ERROR] Lỗi khi lấy comment bài viết %s: %s", post_id, data.get("error", data))
            break

    logger.info("[FETCH] Post %s: tổng số comment đã lấy từ Facebook = %s", post_id, len(all_comments))
    return all_comments


class CleanFacebook:
    def __init__(self, version: str = "v20.0"):
        self.version = version

    def _load_keywords(self, keywords: list[str] | None = None) -> list[str]:
        if keywords:
            return [str(item).strip() for item in keywords if str(item).strip()]
        return [str(item).strip() for item in SpamWord.objects.values_list("key", flat=True) if str(item).strip()]

    def _get_runtime_context(self, post_obj, user_token_obj=None):
        user_token = user_token_obj.access_token if user_token_obj else None
        page_token_obj = PageToken.objects.filter(page=post_obj.page).order_by("-created_at").first()
        page_access_token = None
        if page_token_obj and page_token_obj.access_token:
            page_access_token = page_token_obj.access_token
        elif user_token:
            page_access_token = user_token
        return {
            "user_token": user_token,
            "page_access_token": page_access_token or user_token or "",
            "page_id": post_obj.page.page_fb_id,
            "page_token_obj": page_token_obj,
        }

    def _should_process(self, comment: dict, keywords: list[str]) -> bool:
        if not isinstance(comment, dict):
            return False
        message = comment.get("message") or ""
        normalized_message = normalize_text(message)
        if not normalized_message:
            return False
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_message:
                return True
        return False

    def scan_and_delete_spam(self, post_obj, action_type: str = "hide", user_token_obj=None):
        context = self._get_runtime_context(post_obj, user_token_obj)
        page_access_token = get_page_access_token(context["user_token"], context["page_id"], self.version)
        if context.get("page_access_token"):
            page_access_token = context["page_access_token"]
        post_id_for_api = normalize_post_fb_id(post_obj.post_fb_id, context["page_id"])
        keyword_list = self._load_keywords()
        comments = fetch_all_post_comments(post_id_for_api, page_access_token, self.version, limit=1000)
        matched_comments = []

        for comment in comments:
            if not self._should_process(comment, keyword_list):
                continue
            comment_id = comment.get("id")
            if not comment_id:
                continue
            matched_comments.append(comment)
            comment_record, _ = Comment.objects.get_or_create(
                comment_fb_id=comment_id,
                defaults={
                    "post": post_obj,
                    "title": comment.get("message") or "",
                    "body": comment,
                    "status": None,
                },
            )
            if comment_record.post_id != post_obj.id:
                comment_record.post = post_obj
            comment_record.title = comment.get("message") or ""
            comment_record.body = comment
            comment_record.save()

            if action_type == "delete":
                success = delete_comment(comment_id, page_access_token, self.version)
            else:
                success = hide_comment(comment_id, page_access_token, self.version)
            if success:
                comment_record.status = action_type
                comment_record.save()

        return {
            "post_id": post_obj.id,
            "post_fb_id": post_obj.post_fb_id,
            "processed_count": len(matched_comments),
        }

    def run_for_posts(self, posts, action_type: str = "hide", user_token_obj=None):
        results = []
        for post_obj in posts:
            results.append(self.scan_and_delete_spam(post_obj, action_type=action_type, user_token_obj=user_token_obj))
        return results
