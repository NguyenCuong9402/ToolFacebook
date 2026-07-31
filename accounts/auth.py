from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework.authentication import SessionAuthentication

from codebase.extensions import logger


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    DRF Session Authentication without CSRF validation.
    Only use this in development/testing environments.
    """

    def enforce_csrf(self, request):
        return
