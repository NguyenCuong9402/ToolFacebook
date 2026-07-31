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
    action_type = forms.ChoiceField(
        choices=[("hide", "Ẩn"), ("delete", "Xóa")],
        required=True,
        label="Hành động",
        initial="hide",
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
    actions = ["clean_facebook_comments"]
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

    def clean_facebook_comments(self, request, queryset):
        service = CleanFacebook()
        processed_total = 0
        saved_total = 0
        errors = []

        user_token_id = request.POST.get("user_token")
        action_type = request.POST.get("action_type", "hide")
        user_token = None
        if user_token_id:
            user_token = UserToken.objects.filter(pk=user_token_id).first()

        for post in queryset:
            try:
                result = service.run_for_page(
                    page=post.page,
                    action=action_type,
                    user_token=user_token,
                    posts=[post],
                )
                processed_total += result["processed_count"]
                saved_total += result["saved_count"]
            except Exception as exc:  # pragma: no cover - admin safety net
                errors.append(f"{post.post_fb_id}: {exc}")

        if errors:
            self.message_user(
                request,
                f"Một số bài viết xử lý lỗi: {'; '.join(errors)}",
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Đã quét và xử lý {processed_total} comment spam. Đã lưu {saved_total} comment vào DB.",
                level=messages.SUCCESS,
            )

    clean_facebook_comments.short_description = "Quét và xử lý comment spam trên Facebook"


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
    change_list_template = "admin/spamword_import.html"

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
            path("import-from-file/", self.admin_site.admin_view(self.import_from_file), name="app_spamword_import_from_file"),
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
                    obj, created = SpamWord.objects.get_or_create(key=keyword)
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