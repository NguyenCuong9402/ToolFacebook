from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from loguru import logger

from common.mixins import StructuredLoggingMixin

UserModel = get_user_model()


class EmailBackend(StructuredLoggingMixin, ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username and "email" in kwargs:
            username = kwargs.get("email")
        if not username:
            messages.warning(request, "Email is required.")
            return
        try:
            user = UserModel.objects.get(
                Q(username__iexact=username.lower()) | Q(email__iexact=username.lower())
            )
        except UserModel.DoesNotExist:
            UserModel().set_password(password)
            self.log_warning(f"Authentication failed for: {username}")
            if request:
                messages.warning(request, "Invalid credentials.")
            return None
        except UserModel.MultipleObjectsReturned:
            self.log_error(f"Multiple users found with email {username}")
            return None

        if not self.user_can_authenticate(user):
            messages.warning(request, "You are not allowed to authenticate.")
            return

        if user.check_password(password):
            return user

        if request:
            messages.warning(request, "Invalid credentials.")
        return None
