from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.core.models import Permission, Role
from apps.core.models.role import DataScopeLevel


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""

    class Meta:
        model = Permission
        fields = ["id", "code", "name", "description", "module", "submodule", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoleBranchScopeSerializer(serializers.Serializer):
    """Serializer for branch scope display"""

    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class RoleBlockScopeSerializer(serializers.Serializer):
    """Serializer for block scope display"""

    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class RoleDepartmentScopeSerializer(serializers.Serializer):
    """Serializer for department scope display"""

    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


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

    # Data scope fields
    data_scope_level_display = serializers.CharField(source="get_data_scope_level_display", read_only=True)
    branch_scopes = serializers.SerializerMethodField()
    block_scopes = serializers.SerializerMethodField()
    department_scopes = serializers.SerializerMethodField()

    # Write-only fields for scope assignments
    branch_scope_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    block_scope_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    department_scope_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Role
        fields = [
            "id",
            "code",
            "name",
            "description",
            "is_system_role",
            "is_default_role",
            "created_by",
            "permission_ids",
            "permissions_detail",
            # Data scope fields
            "data_scope_level",
            "data_scope_level_display",
            "branch_scopes",
            "block_scopes",
            "department_scopes",
            "branch_scope_ids",
            "block_scope_ids",
            "department_scope_ids",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "is_system_role", "created_by", "created_at", "updated_at"]

    def get_branch_scopes(self, obj):
        """Get branch scopes for the role"""
        from apps.hrm.models import Branch

        branches = Branch.objects.filter(role_scopes__role=obj).values("id", "code", "name")
        return RoleBranchScopeSerializer(branches, many=True).data

    def get_block_scopes(self, obj):
        """Get block scopes for the role"""
        from apps.hrm.models import Block

        blocks = Block.objects.filter(role_scopes__role=obj).values("id", "code", "name")
        return RoleBlockScopeSerializer(blocks, many=True).data

    def get_department_scopes(self, obj):
        """Get department scopes for the role"""
        from apps.hrm.models import Department

        departments = Department.objects.filter(role_scopes__role=obj).values("id", "code", "name")
        return RoleDepartmentScopeSerializer(departments, many=True).data

    def validate(self, attrs):
        """Custom validation for Role"""
        # Check if at least one permission is selected
        if "permissions" in attrs and not attrs["permissions"]:
            raise serializers.ValidationError({"permission_ids": _("At least one permission must be selected")})

        # Validate data scope configuration
        self._validate_data_scope_config(attrs)

        return attrs

    def _validate_data_scope_config(self, attrs):
        """Validate data scope level and assigned scopes are consistent"""
        data_scope_level = attrs.get("data_scope_level") or (
            self.instance.data_scope_level if self.instance else DataScopeLevel.ROOT
        )
        branch_scope_ids = attrs.get("branch_scope_ids")
        block_scope_ids = attrs.get("block_scope_ids")
        department_scope_ids = attrs.get("department_scope_ids")

        # Define which scopes are allowed for each level
        allowed_scopes = {
            DataScopeLevel.ROOT: {"branch": False, "block": False, "department": False},
            DataScopeLevel.BRANCH: {"branch": True, "block": False, "department": False},
            DataScopeLevel.BLOCK: {"branch": False, "block": True, "department": False},
            DataScopeLevel.DEPARTMENT: {"branch": False, "block": False, "department": True},
        }

        config = allowed_scopes.get(data_scope_level, {})

        # ROOT level should not have any scopes
        if data_scope_level == DataScopeLevel.ROOT:
            if branch_scope_ids or block_scope_ids or department_scope_ids:
                raise serializers.ValidationError(
                    {"data_scope_level": _("ROOT level should not have any scope assignments.")}
                )
            return

        # Validate scopes for non-ROOT levels
        if branch_scope_ids and not config.get("branch"):
            raise serializers.ValidationError(
                {
                    "branch_scope_ids": _("Cannot assign branch scopes for %(level)s-level role.")
                    % {"level": data_scope_level}
                }
            )
        if block_scope_ids and not config.get("block"):
            raise serializers.ValidationError(
                {
                    "block_scope_ids": _("Cannot assign block scopes for %(level)s-level role.")
                    % {"level": data_scope_level}
                }
            )
        if department_scope_ids and not config.get("department"):
            raise serializers.ValidationError(
                {
                    "department_scope_ids": _("Cannot assign department scopes for %(level)s-level role.")
                    % {"level": data_scope_level}
                }
            )

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

    def validate_branch_scope_ids(self, value):
        """Validate branch IDs exist"""
        if value:
            from apps.hrm.models import Branch

            valid_ids = set(Branch.objects.filter(id__in=value).values_list("id", flat=True))
            invalid_ids = set(value) - valid_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    _("Invalid branch IDs: %(ids)s") % {"ids": ", ".join(map(str, invalid_ids))}
                )
        return value

    def validate_block_scope_ids(self, value):
        """Validate block IDs exist"""
        if value:
            from apps.hrm.models import Block

            valid_ids = set(Block.objects.filter(id__in=value).values_list("id", flat=True))
            invalid_ids = set(value) - valid_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    _("Invalid block IDs: %(ids)s") % {"ids": ", ".join(map(str, invalid_ids))}
                )
        return value

    def validate_department_scope_ids(self, value):
        """Validate department IDs exist"""
        if value:
            from apps.hrm.models import Department

            valid_ids = set(Department.objects.filter(id__in=value).values_list("id", flat=True))
            invalid_ids = set(value) - valid_ids
            if invalid_ids:
                raise serializers.ValidationError(
                    _("Invalid department IDs: %(ids)s") % {"ids": ", ".join(map(str, invalid_ids))}
                )
        return value

    def create(self, validated_data):
        """Create a new role"""
        # Extract scope IDs before create
        branch_scope_ids = validated_data.pop("branch_scope_ids", None)
        block_scope_ids = validated_data.pop("block_scope_ids", None)
        department_scope_ids = validated_data.pop("department_scope_ids", None)

        validated_data["is_system_role"] = False
        instance = super().create(validated_data)

        # Create scope assignments
        self._update_scopes(instance, branch_scope_ids, block_scope_ids, department_scope_ids)

        return instance

    def update(self, instance, validated_data):
        """Update role - system roles can only update permissions, not other fields"""
        # Extract scope IDs before update
        branch_scope_ids = validated_data.pop("branch_scope_ids", None)
        block_scope_ids = validated_data.pop("block_scope_ids", None)
        department_scope_ids = validated_data.pop("department_scope_ids", None)

        if instance.is_system_role:
            # For system roles, only allow updating permissions
            allowed_fields = {"permissions"}
            provided_fields = set(validated_data.keys())

            # Check if any non-permission fields are being updated
            non_allowed_fields = provided_fields - allowed_fields
            if non_allowed_fields:
                raise serializers.ValidationError(_("System roles can only update permissions, not other fields"))

        instance = super().update(instance, validated_data)

        # Update scope assignments
        self._update_scopes(instance, branch_scope_ids, block_scope_ids, department_scope_ids)

        return instance

    def _update_scopes(self, instance, branch_ids, block_ids, dept_ids):
        """Update role scope assignments"""
        from apps.hrm.models import RoleBlockScope, RoleBranchScope, RoleDepartmentScope

        # Update branch scopes
        if branch_ids is not None:
            RoleBranchScope.objects.filter(role=instance).delete()
            for branch_id in branch_ids:
                RoleBranchScope.objects.create(role=instance, branch_id=branch_id)

        # Update block scopes
        if block_ids is not None:
            RoleBlockScope.objects.filter(role=instance).delete()
            for block_id in block_ids:
                RoleBlockScope.objects.create(role=instance, block_id=block_id)

        # Update department scopes
        if dept_ids is not None:
            RoleDepartmentScope.objects.filter(role=instance).delete()
            for dept_id in dept_ids:
                RoleDepartmentScope.objects.create(role=instance, department_id=dept_id)
