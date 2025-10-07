from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.models import Permission, Role


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""

    class Meta:
        model = Permission
        fields = ["id", "code", "description", "module", "submodule", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model"""

    created_by = serializers.CharField(source="created_by_display", read_only=True)
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        source="permissions",
        write_only=True,
    )
    permissions_detail = PermissionSerializer(source="permissions", many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_system_role",
            "created_by",
            "permission_ids",
            "permissions_detail",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "is_system_role", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        """Custom validation for Role"""
        # Check if at least one permission is selected
        if "permissions" in attrs and not attrs["permissions"]:
            raise serializers.ValidationError({"permission_ids": _("At least one permission must be selected")})

        return attrs

    def validate_name(self, value):
        """Validate role name uniqueness"""
        instance = self.instance
        if instance:
            # Update case: check if name is changed and not duplicate
            if Role.objects.exclude(pk=instance.pk).filter(name=value).exists():
                raise serializers.ValidationError(_("Role name already exists"))
        else:
            # Create case: check if name already exists
            if Role.objects.filter(name=value).exists():
                raise serializers.ValidationError(_("Role name already exists"))
        return value

    def create(self, validated_data):
        """Create a new role with auto-generated code"""
        # Auto-generate code VTxxx
        last_role = Role.objects.order_by("-code").first()
        if last_role and last_role.code.startswith("VT"):
            try:
                last_number = int(last_role.code[2:])
                new_number = last_number + 1
            except ValueError:
                new_number = 3
        else:
            new_number = 3

        validated_data["code"] = f"VT{new_number:03d}"
        validated_data["is_system_role"] = False

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update role - system roles can only update permissions, not other fields"""
        if instance.is_system_role:
            # For system roles, only allow updating permissions
            allowed_fields = {"permissions"}
            provided_fields = set(validated_data.keys())

            # Check if any non-permission fields are being updated
            non_allowed_fields = provided_fields - allowed_fields
            if non_allowed_fields:
                raise serializers.ValidationError(_("System roles can only update permissions, not other fields"))

        return super().update(instance, validated_data)
