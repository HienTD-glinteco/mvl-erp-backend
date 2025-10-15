from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class SimpleUserSerializer(serializers.ModelSerializer):
    """Simple serializer for basic user information"""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
        ]
