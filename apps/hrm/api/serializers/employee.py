from rest_framework import serializers

from apps.hrm.models import Employee
from libs import FieldFilteringSerializerMixin


class EmployeeSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Employee model"""

    default_fields = [
        "id",
        "code",
        "name",
        "user_id",
    ]

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "name",
            "user_id",
        ]
        read_only_fields = ["id"]
