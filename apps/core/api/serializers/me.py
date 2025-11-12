from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.core.models import Permission, Role

User = get_user_model()


class RoleSummarySerializer(serializers.ModelSerializer):
    """Simplified serializer for role information in user profile"""

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system_role"]
        read_only_fields = ["id", "code", "name", "description", "is_system_role"]


class EmployeeSummarySerializer(serializers.Serializer):
    """Serializer for employee information in user profile"""

    id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    fullname = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    phone = serializers.CharField(read_only=True)
    avatar = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    position = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    start_date = serializers.DateField(read_only=True)

    def get_avatar(self, obj):
        """Get avatar information"""
        if obj.avatar:
            from apps.files.api.serializers import FileSerializer

            return FileSerializer(obj.avatar).data
        return None

    def get_department(self, obj):
        """Get department name"""
        if obj.department:
            return {"id": obj.department.id, "name": obj.department.name, "code": obj.department.code}
        return None

    def get_position(self, obj):
        """Get position name"""
        if obj.position:
            return {"id": obj.position.id, "name": obj.position.name, "code": obj.position.code}
        return None


class MeSerializer(serializers.ModelSerializer):
    """Serializer for authenticated user's profile"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role = RoleSummarySerializer(read_only=True)
    employee = serializers.SerializerMethodField()
    links = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_staff",
            "date_joined",
            "role",
            "employee",
            "links",
        ]
        read_only_fields = [
            "id",
            "username",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_staff",
            "date_joined",
            "role",
            "employee",
            "links",
        ]

    def get_employee(self, obj):
        """Get employee information if exists"""
        if hasattr(obj, "employee") and obj.employee:
            return EmployeeSummarySerializer(obj.employee).data
        return None

    def get_links(self, obj):
        """Get resource links"""
        request = self.context.get("request")
        links = {"self": "/api/me"}

        if hasattr(obj, "employee") and obj.employee:
            employee_id = obj.employee.id
            links["employee"] = f"/api/hrm/employees/{employee_id}"

        return links


class PermissionDetailSerializer(serializers.ModelSerializer):
    """Serializer for permission details"""

    class Meta:
        model = Permission
        fields = ["id", "code", "description", "created_at"]
        read_only_fields = ["id", "code", "description", "created_at"]


class MePermissionsSerializer(serializers.Serializer):
    """Serializer for user permissions response"""

    user_id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    role = RoleSummarySerializer(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    permissions = PermissionDetailSerializer(many=True, read_only=True)
    meta = serializers.DictField(read_only=True)
    links = serializers.DictField(read_only=True)
