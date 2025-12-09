from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.models import Permission, Role
from apps.files.api.serializers import FileSerializer

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

    def get_avatar(self, obj) -> FileSerializer:
        """Get avatar information"""
        if obj.avatar:
            return FileSerializer(obj.avatar).data
        return None  # type: ignore

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


class MeLinksSerializer(serializers.Serializer):
    """Serializer for links in user profile response"""

    self = serializers.CharField(read_only=True, help_text="Link to the current resource")
    employee = serializers.CharField(
        required=False,
        allow_null=True,
        read_only=True,
        help_text="Link to employee detail endpoint if user has employee record",
    )


class MeSerializer(serializers.ModelSerializer):
    """Serializer for authenticated user's profile"""

    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role = RoleSummarySerializer(read_only=True)
    employee = EmployeeSummarySerializer(allow_null=True, read_only=True)
    links = serializers.SerializerMethodField()

    @extend_schema_field(MeLinksSerializer)
    def get_links(self, obj):
        """Get resource links"""
        request = self.context.get("request")
        links = {"self": "/api/me"}

        if hasattr(obj, "employee") and obj.employee:
            employee_id = obj.employee.id
            links["employee"] = f"/api/hrm/employees/{employee_id}"

        return links

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
