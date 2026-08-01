import os
import re

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db import transaction
from django.shortcuts import redirect, render
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


class ImportSpamWordsForm(forms.Form):
    import_file = forms.FileField(required=True, label="Chọn file .txt")


class CleanFacebookActionForm(ActionForm):
    user_token = forms.ModelChoiceField(
        queryset=UserToken.objects.all().order_by("-created_at"),
        required=False,
        label="User Token",
        empty_label="Tự động chọn",
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


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
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
    actions = ["hide_facebook_comments", "delete_facebook_comments"]
    action_form = CleanFacebookActionForm

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

    def _resolve_user_token(self, request):
        token_id = request.POST.get("user_token")
        if not token_id:
            return None
        return UserToken.objects.filter(pk=token_id).first()

    def hide_facebook_comments(self, request, queryset):
        user_token = self._resolve_user_token(request)
        results = CleanFacebook().run_for_posts(queryset, action_type="hide", user_token_obj=user_token)
        processed_count = sum(item.get("processed_count", 0) for item in results)
        self.message_user(
            request,
            f"Đã ẩn {processed_count} comment spam trên {queryset.count()} bài viết.",
            level=messages.SUCCESS,
        )

    hide_facebook_comments.short_description = "Ẩn comment spam trên Facebook"

    def delete_facebook_comments(self, request, queryset):
        user_token = self._resolve_user_token(request)
        results = CleanFacebook().run_for_posts(queryset, action_type="delete", user_token_obj=user_token)
        processed_count = sum(item.get("processed_count", 0) for item in results)
        self.message_user(
            request,
            f"Đã xóa {processed_count} comment spam trên {queryset.count()} bài viết.",
            level=messages.SUCCESS,
        )

    delete_facebook_comments.short_description = "Xóa comment spam trên Facebook"


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
    change_list_template = "admin/app/spamword/change_list.html"

    list_display = (
        "id",
        "key",
        "created_at",
    )
    search_fields = ("key",)
    ordering = ("key",)
    readonly_fields = ("created_at", "updated_at")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-from-file/",
                self.admin_site.admin_view(self.import_from_file),
                name="spamword_import_from_file",
            ),
        ]
        return custom_urls + urls

    def import_from_file(self, request):
        if request.method == "POST":
            form = ImportSpamWordsForm(request.POST, request.FILES)
            if form.is_valid():
                file_obj = request.FILES["import_file"]
                content = file_obj.read().decode("utf-8", errors="ignore")
                imported_count = 0
                skipped_count = 0

                for raw_line in content.splitlines():
                    keyword = raw_line.strip()
                    if not keyword:
                        continue
                    _, created = SpamWord.objects.get_or_create(key=keyword)
                    if created:
                        imported_count += 1
                    else:
                        skipped_count += 1

                self.message_user(
                    request,
                    f"Đã import {imported_count} từ khóa mới. Bỏ qua {skipped_count} từ khóa đã tồn tại.",
                    level=messages.SUCCESS,
                )
                return redirect("admin:app_spamword_changelist")
        else:
            form = ImportSpamWordsForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "title": "Import từ khóa spam từ file .txt",
        }
        return render(request, "admin/spamword_import.html", context)


from django.contrib import admin

from django_celery_beat.models import (
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    ClockedSchedule,
    SolarSchedule,
)

from django_celery_results.models import TaskResult, GroupResult


# Celery Beat
for model in [
    PeriodicTask,
    IntervalSchedule,
    CrontabSchedule,
    ClockedSchedule,
    SolarSchedule,
]:
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass


# Celery Result
for model in [
    TaskResult,
    GroupResult,
]:
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass