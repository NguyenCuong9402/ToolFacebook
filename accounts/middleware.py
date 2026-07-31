from django.conf import settings
from django.contrib.auth import login, get_user_model
from django.middleware.csrf import rotate_token, CsrfViewMiddleware
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.csrf import csrf_exempt

UserModel = get_user_model()


class DebugAutoLoginMiddleware(MiddlewareMixin):
    """
    Middleware that automatically logs in a specified user when DEBUG=True.
    This should only be used in development environments.

    Add to MIDDLEWARE in settings.py:
    'path.to.DebugAutoLoginMiddleware'

    Required settings:
    DEBUG_AUTO_LOGIN_EMAIL = 'admin@fpt.com'  # Email to auto-login as
    """

    def __init__(self, get_response=None):
        super().__init__(get_response)

        # Validate settings when middleware is initialized
        if settings.DEBUG and hasattr(settings, 'DEBUG_AUTO_LOGIN_EMAIL'):
            if not isinstance(settings.DEBUG_AUTO_LOGIN_EMAIL, str):
                print('DEBUG_AUTO_LOGIN_EMAIL must be a string')
                return

    def process_request(self, request):
        if not settings.DEBUG:
            return None

        # Skip if already authenticated
        if request.user.is_authenticated:
            return None

        # Skip if DEBUG_AUTO_LOGIN_EMAIL is not set
        if not hasattr(settings, 'DEBUG_AUTO_LOGIN_EMAIL') or settings.DEBUG_AUTO_LOGIN_EMAIL is None:
            return None

        # Get the user to auto-login as
        debug_email = settings.DEBUG_AUTO_LOGIN_EMAIL
        user, _created = UserModel.objects.get_or_create(
            email=debug_email,
            defaults={
                'username': debug_email.split('@')[0],
                'password': '76b8niU2t2^I',
            }
        )

        # Perform the login
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        login(request, user)
        # Rotate the CSRF token to ensure it matches the new session
        rotate_token(request)

    def process_view(self, request, callback, callback_args, callback_kwargs):
        """Handle CSRF exemption for views if needed"""
        if settings.DEBUG and getattr(settings, 'DEBUG_DISABLE_CSRF', False):
            # Wrap the view in csrf_exempt if CSRF is disabled
            return csrf_exempt(callback)(request, *callback_args, **callback_kwargs)
        return None


class CustomCsrfMiddleware(CsrfViewMiddleware, MiddlewareMixin):
    """
    Custom CSRF middleware that exempts specific paths or conditions.
    Useful for development and testing with DRF's BrowsableAPIRenderer.
    """

    def process_view(self, request, callback, callback_args, callback_kwargs):
        # Example of path-based exemption
        if request.path.startswith('/api/'):
            return None

        # Example of view-based exemption
        if getattr(callback, 'csrf_exempt', False):
            return None

        # Example of specific HTTP method exemption
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return None

        # For all other cases, apply normal CSRF validation
        return super().process_view(request, callback, callback_args, callback_kwargs)
