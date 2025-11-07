from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.api.serializers.administrative_unit import AdministrativeUnitSerializer
from apps.core.api.serializers.province import ProvinceSerializer
from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, Position

User = get_user_model()


class BranchSerializer(serializers.ModelSerializer):
    """Serializer for Branch model - used for create/update operations"""

    province_id = serializers.PrimaryKeyRelatedField(
        source="province",
        queryset=Province.objects.all(),
        required=True,
        write_only=True,
    )
    province = ProvinceSerializer(read_only=True)
    administrative_unit_id = serializers.PrimaryKeyRelatedField(
        source="administrative_unit",
        queryset=AdministrativeUnit.objects.all(),
        required=True,
        write_only=True,
    )
    administrative_unit = AdministrativeUnitSerializer(read_only=True)

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "address",
            "phone",
            "email",
            "province_id",
            "administrative_unit_id",
            "province",
            "administrative_unit",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "province",
            "administrative_unit",
            "is_active",
            "created_at",
            "updated_at",
        ]


class BlockSerializer(serializers.ModelSerializer):
    """Serializer for Block model"""

    branch_id = serializers.PrimaryKeyRelatedField(
        source="branch",
        queryset=Branch.objects.all(),
        required=True,
        write_only=True,
    )
    branch = BranchSerializer(read_only=True)
    block_type_display = serializers.CharField(source="get_block_type_display", read_only=True)

    class Meta:
        model = Block
        fields = [
            "id",
            "name",
            "code",
            "block_type",
            "block_type_display",
            "branch_id",
            "branch",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "created_at",
            "updated_at",
            "branch",
            "block_type_display",
            "is_active",
        ]


class OrganizationDepartmentNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested department references"""

    class Meta:
        model = Department
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department model"""

    branch = BranchSerializer(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), source="branch", write_only=True, required=True
    )
    block = BlockSerializer(read_only=True)
    block_id = serializers.PrimaryKeyRelatedField(
        queryset=Block.objects.all(), source="block", write_only=True, required=True
    )
    parent_department = OrganizationDepartmentNestedSerializer(read_only=True)
    parent_department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source="parent_department", write_only=True, required=False, allow_null=True
    )
    management_department = OrganizationDepartmentNestedSerializer(read_only=True)
    management_department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="management_department",
        write_only=True,
        required=False,
        allow_null=True,
    )
    function_display = serializers.CharField(source="get_function_display", read_only=True)
    full_hierarchy = serializers.CharField(read_only=True)
    available_function_choices = serializers.SerializerMethodField()
    available_management_departments = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "branch",
            "branch_id",
            "block",
            "block_id",
            "parent_department",
            "parent_department_id",
            "management_department",
            "management_department_id",
            "function",
            "function_display",
            "available_function_choices",
            "is_main_department",
            "available_management_departments",
            "full_hierarchy",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "created_at",
            "updated_at",
            "branch",
            "block",
            "parent_department",
            "management_department",
            "function_display",
            "full_hierarchy",
            "available_function_choices",
            "available_management_departments",
            "is_active",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_available_function_choices(self, obj):
        """Get available function choices based on block type"""
        if obj.block:
            return Department.get_function_choices_for_block_type(obj.block.block_type)
        return []

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_available_management_departments(self, obj):
        """Get available management departments with same function"""
        if obj.function and obj.block:
            departments = (
                Department.objects.filter(block=obj.block, function=obj.function, is_active=True)
                .exclude(id=obj.id)
                .select_related("block__branch")
            )

            return [
                {
                    "id": str(dept.id),
                    "name": dept.name,
                    "code": dept.code,
                    "full_path": f"{dept.block.branch.name}/{dept.block.name}/{dept.name}",
                }
                for dept in departments
            ]
        return []

    def validate(self, attrs):  # noqa: C901
        """
        Delegate validation to model's clean() method to avoid duplication.
        This ensures consistent validation across all entry points.
        """
        # Create a temporary instance to run validation
        if self.instance:
            # Update operation - use existing instance
            instance = self.instance
            for key, value in attrs.items():
                setattr(instance, key, value)
        else:
            # Create operation - create temporary instance
            instance = Department(**attrs)

        # Auto-set branch from block if not provided (model does this in save())
        if instance.block and not instance.branch:
            instance.branch = instance.block.branch

        # Auto-set function based on block type if needed (model does this in save())
        # Only auto-set if function was NOT explicitly provided by the user
        if instance.block and "function" not in attrs:
            # For business blocks, function must be business
            if instance.block.block_type == Block.BlockType.BUSINESS:
                instance.function = Department.DepartmentFunction.BUSINESS
            # For support blocks, if function is the model default (BUSINESS), set to HR_ADMIN
            elif instance.block.block_type == Block.BlockType.SUPPORT:
                if instance.function == Department.DepartmentFunction.BUSINESS:
                    instance.function = Department.DepartmentFunction.HR_ADMIN

        # Run model validation (calls our custom clean() method)
        # We use clean() directly instead of full_clean() because:
        # - DRF already validates required fields
        # - Code is auto-generated in save(), so it's not available yet
        # - Unique constraints are handled by DRF
        try:
            instance.clean()
        except ValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            # Map model field names to serializer field names (e.g., management_department -> management_department_id)
            error_dict = {}
            for field_name, errors in e.message_dict.items():
                # Map model field names to serializer write-only field names
                if field_name == "parent_department":
                    field_name = "parent_department_id"
                elif field_name == "management_department":
                    field_name = "management_department_id"
                error_dict[field_name] = errors
            raise serializers.ValidationError(error_dict)

        return attrs


class PositionSerializer(serializers.ModelSerializer):
    """Serializer for Position model"""

    data_scope_display = serializers.CharField(source="get_data_scope_display", read_only=True)

    class Meta:
        model = Position
        fields = [
            "id",
            "name",
            "code",
            "data_scope",
            "data_scope_display",
            "is_leadership",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "data_scope_display", "is_active", "created_at", "updated_at"]



