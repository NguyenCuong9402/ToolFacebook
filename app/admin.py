import re

from django.contrib import admin
from django.db import transaction
from django.shortcuts import redirect
from django.urls import path


from django.contrib import admin

from .models import (
    UserToken,
    PageToken,
    Page,
    Post,
    Comment,
    SpamWord,
)


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


@admin.register(PageToken)
class PageTokenAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "page_fb_id",
        "user_token",
        "expires_at",
        "created_at",
    )
    search_fields = (
        "page_fb_id",
        "user_token__user_name",
    )
    list_filter = (
        "expires_at",
        "created_at",
    )
    autocomplete_fields = ("user_token",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "page_fb_id",
        "page_token",
        "created_at",
    )
    search_fields = (
        "title",
        "page_fb_id",
    )
    autocomplete_fields = ("page_token",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")


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
        "created_at",
    )
    search_fields = (
        "comment_fb_id",
        "title",
        "post__title",
        "post__post_fb_id",
    )
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