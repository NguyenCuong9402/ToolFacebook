from django.db import models


class UserToken(models.Model):
    user_name = models.CharField(
        max_length=255,
        help_text="Tên người dùng Facebook."
    )
    access_token = models.TextField(
        help_text="User Access Token của Facebook."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "User Token"
        verbose_name_plural = "User Token"

    def __str__(self):
        return self.user_name
        
class Page(models.Model):
    page_fb_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID của Fanpage trên Facebook."
    )

    title = models.CharField(
        max_length=255,
        help_text="Tên Fanpage."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "Fanpage"
        verbose_name_plural = "Fanpage"

    def __str__(self):
        return self.title

class PageToken(models.Model):
    user_token = models.ForeignKey(
        UserToken,
        on_delete=models.CASCADE,
        related_name="page_tokens",
        help_text="User Token sở hữu Page Token này."
    )

    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="tokens",
        help_text="Fanpage sử dụng Page Token này."
    )

    access_token = models.TextField(
        help_text="Page Access Token của Facebook."
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Thời điểm hết hạn của Page Token. Để trống nếu token không có thời hạn hoặc không xác định."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "Page Token"
        verbose_name_plural = "Page Token"

    def __str__(self):
        return f"{self.id}"





class Post(models.Model):
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name="posts",
        help_text="Fanpage chứa bài viết."
    )

    post_fb_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID bài viết trên Facebook."
    )

    title = models.CharField(
        max_length=255,
        help_text="Nội dung hoặc tiêu đề bài viết."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "Bài viết"
        verbose_name_plural = "Bài viết"

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="Bài viết chứa bình luận."
    )

    comment_fb_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="ID bình luận trên Facebook."
    )

    title = models.TextField(
        help_text="Nội dung bình luận."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "Bình luận"
        verbose_name_plural = "Bình luận"

    def __str__(self):
        return self.comment_fb_id


class SpamWord(models.Model):
    key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Từ khóa hoặc cụm từ cần lọc."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Thời điểm tạo bản ghi."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Thời điểm cập nhật gần nhất."
    )

    class Meta:
        verbose_name = "Từ khóa spam"
        verbose_name_plural = "Từ khóa spam"
        ordering = ("key",)

    def __str__(self):
        return self.key