import uuid

from django.contrib.contenttypes.models import ContentType

from app.models import SpamWord


def import_spam_words(keywords: list[str]) -> dict:
    """
    Import danh sách từ khóa spam.

    Args:
        keywords: Danh sách từ khóa.

    Returns:
        Thống kê kết quả import.
    """

    created_count = 0
    existed_count = 0

    for keyword in keywords:
        keyword = keyword.strip()

        if not keyword:
            continue

        _, created = SpamWord.objects.get_or_create(
            key=keyword
        )

        if created:
            created_count += 1
        else:
            existed_count += 1

    return {
        "created": created_count,
        "existed": existed_count,
        "total": created_count + existed_count,
    }

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

