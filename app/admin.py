import re

from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import path

from .models import (
    UserToken,
    PageToken,
    Page,
    Post,
    Comment,
    SpamWord,
)
from .services.clean_facebook import CleanFacebook


@admin.register(UserToken)
class UserTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_name",
        "created_at",
        "updated_at",
    )
    search_fields = ("user_name",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    actions = ["clean_facebook_comments"]

    list_display = (
        "id",
        "title",
        "page_fb_id",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "title",
        "page_fb_id",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    def clean_facebook_comments(self, request, queryset):
        service = CleanFacebook()
        processed_total = 0
        saved_total = 0
        errors = []

        for page in queryset:
            try:
                result = service.run_for_page(page=page, action="hide")
                processed_total += result["processed_count"]
                saved_total += result["saved_count"]
            except Exception as exc:  # pragma: no cover - admin safety net
                errors.append(f"{page.title}: {exc}")

        if errors:
            self.message_user(
                request,
                f"Một số trang xử lý lỗi: {'; '.join(errors)}",
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Đã quét và xử lý {processed_total} comment spam. Đã lưu {saved_total} comment vào DB.",
                level=messages.SUCCESS,
            )

    clean_facebook_comments.short_description = "Quét và xử lý comment spam trên Facebook"


@admin.register(PageToken)
class PageTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "page",
        "user_token",
        "expires_at",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "page__title",
        "page__page_fb_id",
        "user_token__user_name",
    )

    list_filter = (
        "expires_at",
        "created_at",
    )

    autocomplete_fields = (
        "page",
        "user_token",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "post_fb_id",
        "page",
        "created_at",
    )
    search_fields = (
        "title",
        "post_fb_id",
        "page__title",
        "page__page_fb_id",
    )
    autocomplete_fields = ("page",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "comment_fb_id",
        "post",
        "status",
        "created_at",
    )
    search_fields = (
        "comment_fb_id",
        "title",
        "post__title",
        "post__post_fb_id",
    )
    list_filter = ("status",)
    autocomplete_fields = ("post",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(SpamWord)
class SpamWordAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "key",
        "created_at",
    )
    search_fields = ("key",)
    ordering = ("key",)
    readonly_fields = ("created_at", "updated_at")