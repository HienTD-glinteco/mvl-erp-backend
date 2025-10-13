from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.models import Role, User


class EmployeeRoleListSerializer(serializers.ModelSerializer):
    """Serializer for listing employees with their roles and organizational information"""

    employee_code = serializers.CharField(source="username", read_only=True)
    employee_name = serializers.CharField(source="get_full_name", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    branch_name = serializers.SerializerMethodField()
    block_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    position_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "employee_code",
            "employee_name",
            "branch_name",
            "block_name",
            "department_name",
            "position_name",
            "role",
            "role_name",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_branch_name(self, obj):
        """Get branch name from primary organization position"""
        primary_org = obj.organization_positions.filter(is_primary=True, is_active=True).first()
        if primary_org:
            return primary_org.department.block.branch.name
        return ""

    @extend_schema_field(serializers.CharField())
    def get_block_name(self, obj):
        """Get block name from primary organization position"""
        primary_org = obj.organization_positions.filter(is_primary=True, is_active=True).first()
        if primary_org:
            return primary_org.department.block.name
        return ""

    @extend_schema_field(serializers.CharField())
    def get_department_name(self, obj):
        """Get department name from primary organization position"""
        primary_org = obj.organization_positions.filter(is_primary=True, is_active=True).first()
        if primary_org:
            return primary_org.department.name
        return ""

    @extend_schema_field(serializers.CharField())
    def get_position_name(self, obj):
        """Get position name from primary organization position"""
        primary_org = obj.organization_positions.filter(is_primary=True, is_active=True).first()
        if primary_org:
            return primary_org.position.name
        return ""


class BulkUpdateRoleSerializer(serializers.Serializer):
    """Serializer for bulk updating employee roles"""

    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=25,
        help_text=_("List of employee IDs to update (maximum 25)"),
    )
    new_role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=True,
        help_text=_("New role to assign to selected employees"),
    )

    def validate_employee_ids(self, value):
        """Validate that all employee IDs exist"""
        if len(value) > 25:
            raise serializers.ValidationError(_("Cannot update more than 25 employees at once."))

        existing_count = User.objects.filter(id__in=value).count()
        if existing_count != len(value):
            raise serializers.ValidationError(_("One or more employee IDs are invalid."))

        return value

    def validate(self, attrs):
        """Additional validation"""
        if not attrs.get("employee_ids"):
            raise serializers.ValidationError({"employee_ids": _("Please select at least one employee.")})

        if not attrs.get("new_role_id"):
            raise serializers.ValidationError({"new_role_id": _("Please select a new role.")})

        return attrs
