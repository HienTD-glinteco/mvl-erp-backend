from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.api.serializers.administrative_unit import AdministrativeUnitSerializer
from apps.core.api.serializers.province import ProvinceSerializer
from apps.core.models import AdministrativeUnit, Province
from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position


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

    branch_name = serializers.CharField(source="branch.name", read_only=True)
    block_type_display = serializers.CharField(source="get_block_type_display", read_only=True)

    class Meta:
        model = Block
        fields = [
            "id",
            "name",
            "code",
            "block_type",
            "block_type_display",
            "branch",
            "branch_name",
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
            "branch_name",
            "block_type_display",
            "is_active",
        ]


class DepartmentNestedSerializer(serializers.ModelSerializer):
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
    parent_department = DepartmentNestedSerializer(read_only=True)
    parent_department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), source="parent_department", write_only=True, required=False, allow_null=True
    )
    management_department = DepartmentNestedSerializer(read_only=True)
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

    def validate_parent_department_id(self, value):
        """Validate parent department is in the same block"""
        if value and self.instance:
            if value.block != self.instance.block:
                raise serializers.ValidationError(
                    _("Parent department must be in the same block as the child department.")
                )
        elif value and "block" in self.initial_data:
            # For creation - use block_id from initial_data
            try:
                block_id = self.initial_data.get("block_id") or self.initial_data.get("block")
                block = Block.objects.get(id=block_id)
                if value.block != block:
                    raise serializers.ValidationError(
                        _("Parent department must be in the same block as the child department.")
                    )
            except Block.DoesNotExist:
                pass
        return value

    def validate_management_department_id(self, value):
        """Validate management department constraints"""
        if value:
            # Check for self-reference
            if self.instance and value.id == self.instance.id:
                raise serializers.ValidationError(_("Department cannot manage itself."))

            block_id = (
                self.initial_data.get("block_id") or self.initial_data.get("block")
                if not self.instance
                else self.instance.block.id
            )
            function = self.initial_data.get("function") if not self.instance else self.instance.function

            try:
                block = Block.objects.get(id=block_id)
                if value.block != block:
                    raise serializers.ValidationError(_("Management department must be in the same block."))
                if function and value.function != function:
                    raise serializers.ValidationError(_("Management department must have the same function."))
            except Block.DoesNotExist:
                pass
        return value

    def validate(self, attrs):
        """Custom validation for Department"""
        # Auto-set or validate function based on block type
        if "block" in attrs:
            block = attrs["block"]
            provided_function = attrs.get("function")

            if block.block_type == Block.BlockType.BUSINESS:
                # If function provided and not BUSINESS -> error; else default to BUSINESS
                if provided_function is not None and provided_function != Department.DepartmentFunction.BUSINESS:
                    raise serializers.ValidationError(
                        {"function": _("Business block can only have business function.")}
                    )
                if provided_function is None:
                    attrs["function"] = Department.DepartmentFunction.BUSINESS
            elif block.block_type == Block.BlockType.SUPPORT:
                # If provided BUSINESS for support -> error; else default to HR_ADMIN if missing
                if provided_function == Department.DepartmentFunction.BUSINESS:
                    raise serializers.ValidationError({"function": _("Support block cannot have business function.")})
                if provided_function is None:
                    attrs["function"] = Department.DepartmentFunction.HR_ADMIN

        # Validate function choice based on block type (final guard)
        if "block" in attrs and "function" in attrs:
            block = attrs["block"]
            function = attrs["function"]
            allowed = [c[0] for c in Department.get_function_choices_for_block_type(block.block_type)]
            if function not in allowed:
                raise serializers.ValidationError(
                    {
                        "function": _("This function is not compatible with block type %(block_type)s.")
                        % {"block_type": block.get_block_type_display()}
                    }
                )

        return attrs


class PositionSerializer(serializers.ModelSerializer):
    """Serializer for Position model"""

    class Meta:
        model = Position
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "is_active", "created_at", "updated_at"]


class OrganizationChartSerializer(serializers.ModelSerializer):
    """Serializer for OrganizationChart model"""

    employee_name = serializers.CharField(source="employee.get_full_name", read_only=True)
    employee_username = serializers.CharField(source="employee.username", read_only=True)
    position_name = serializers.CharField(source="position.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    department_hierarchy = serializers.CharField(source="department.full_hierarchy", read_only=True)

    class Meta:
        model = OrganizationChart
        fields = [
            "id",
            "employee",
            "employee_name",
            "employee_username",
            "position",
            "position_name",
            "department",
            "department_name",
            "department_hierarchy",
            "start_date",
            "end_date",
            "is_primary",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "employee_name",
            "employee_username",
            "position_name",
            "department_name",
            "department_hierarchy",
            "is_active",
        ]

    def validate(self, attrs):
        """Custom validation for organization chart"""
        # Ensure end_date is after start_date
        if attrs.get("end_date") and attrs.get("start_date"):
            if attrs["end_date"] <= attrs["start_date"]:
                raise serializers.ValidationError(_("End date must be after start date."))

        return attrs


class OrganizationChartDetailSerializer(OrganizationChartSerializer):
    """Detailed serializer for OrganizationChart with nested objects"""

    employee = serializers.SerializerMethodField()
    position = PositionSerializer(read_only=True)
    department = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField())
    def get_employee(self, obj):
        """Get employee basic info"""
        return {
            "id": obj.employee.id,
            "username": obj.employee.username,
            "full_name": obj.employee.get_full_name(),
            "email": obj.employee.email,
        }

    @extend_schema_field(serializers.DictField())
    def get_department(self, obj):
        """Get department with block info"""
        return {
            "id": obj.department.id,
            "name": obj.department.name,
            "code": obj.department.code,
            "full_hierarchy": obj.department.full_hierarchy,
            "block": {
                "id": obj.department.block.id,
                "name": obj.department.block.name,
                "code": obj.department.block.code,
                "block_type": obj.department.block.block_type,
                "branch": {
                    "id": obj.department.block.branch.id,
                    "name": obj.department.block.branch.name,
                    "code": obj.department.block.branch.code,
                },
            },
        }
