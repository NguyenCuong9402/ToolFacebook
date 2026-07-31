import uuid

from django.contrib.contenttypes.models import ContentType


def get_content_type(content_type):
    """
    Return ContentType instance from str model name or pk.
    """
    if isinstance(content_type, str):
        try:
            return ContentType.objects.get(model=content_type.lower())
        except ContentType.DoesNotExist:
            return None
    elif isinstance(content_type, int):
        try:
            return ContentType.objects.get(pk=content_type)
        except ContentType.DoesNotExist:
            return None
    return None


def generate_uuid():
    return str(uuid.uuid4())

