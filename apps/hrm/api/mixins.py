"""
API Mixins for HRM module.

Contains mixins for data scope validation and other cross-cutting concerns.
"""

from django.utils.translation import gettext as _
from rest_framework.exceptions import PermissionDenied

from apps.hrm.utils.role_data_scope import collect_role_allowed_units


class DataScopeCreateValidationMixin:
    """
    Mixin to validate create operations against user's data scope.

    Must be used with ViewSets that have `data_scope_config` attribute.

    Usage:
        class EmployeeViewSet(DataScopeCreateValidationMixin, BaseModelViewSet):
            data_scope_config = {
                "branch_field": "branch",
                "block_field": "block",
                "department_field": "department",
            }
    """

    def perform_create(self, serializer):
        """Validate new object is within user's allowed scope before saving"""
        user = self.request.user

        # Superusers bypass validation
        if user.is_superuser:
            return super().perform_create(serializer)

        allowed = collect_role_allowed_units(user)

        # ROOT scope allows creating anywhere
        if allowed.has_all:
            return super().perform_create(serializer)

        # Get config
        config = getattr(self, "data_scope_config", {})

        # Validate the object being created
        validated_data = serializer.validated_data

        if not self._validate_create_scope(validated_data, allowed, config):
            raise PermissionDenied(_("You cannot create objects outside your assigned organizational scope."))

        return super().perform_create(serializer)

    def _validate_create_scope(self, validated_data, allowed, config):
        """
        Validate that the object being created is within user's scope.

        Returns:
            bool: True if creation is allowed
        """
        branch_field = config.get("branch_field", "branch")
        block_field = config.get("block_field", "block")
        department_field = config.get("department_field", "department")

        # Get values from validated data
        branch = self._get_nested_value(validated_data, branch_field)
        block = self._get_nested_value(validated_data, block_field)
        department = self._get_nested_value(validated_data, department_field)

        # Get IDs
        branch_id = branch.id if branch else None
        block_id = block.id if block else None
        department_id = department.id if department else None

        # Check against allowed units using helper methods
        if self._is_branch_allowed(allowed, branch_id, block_id, department_id):
            return True
        if self._is_block_allowed(allowed, block_id, department_id):
            return True
        if self._is_department_allowed(allowed, department_id):
            return True

        return False

    def _is_branch_allowed(self, allowed, branch_id, block_id, department_id):
        """Check if any of the provided IDs fall within allowed branches"""
        if not allowed.branches:
            return False

        if branch_id and branch_id in allowed.branches:
            return True

        from apps.hrm.models import Block, Department

        if block_id:
            try:
                block = Block.objects.get(id=block_id)
                if block.branch_id in allowed.branches:
                    return True
            except Block.DoesNotExist:
                pass

        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                if dept.branch_id in allowed.branches:
                    return True
            except Department.DoesNotExist:
                pass

        return False

    def _is_block_allowed(self, allowed, block_id, department_id):
        """Check if any of the provided IDs fall within allowed blocks"""
        if not allowed.blocks:
            return False

        if block_id and block_id in allowed.blocks:
            return True

        from apps.hrm.models import Department

        if department_id:
            try:
                dept = Department.objects.get(id=department_id)
                if dept.block_id in allowed.blocks:
                    return True
            except Department.DoesNotExist:
                pass

        return False

    def _is_department_allowed(self, allowed, department_id):
        """Check if department is in allowed departments"""
        if not allowed.departments:
            return False
        return department_id and department_id in allowed.departments

    def _get_nested_value(self, data, field_path):
        """Get value from nested dict/object using field path"""
        parts = field_path.split("__")
        value = data
        for part in parts:
            if value is None:
                return None
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)
        return value
