from rest_framework import serializers

from apps.hrm.models import Employee


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for Employee model"""

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "name",
            "user_id",
        ]
        read_only_fields = ["id"]
