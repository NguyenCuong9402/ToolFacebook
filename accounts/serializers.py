from rest_framework import serializers

from accounts.models import User


class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_staff",
        ]
        read_only_fields = ["id", "email"]
