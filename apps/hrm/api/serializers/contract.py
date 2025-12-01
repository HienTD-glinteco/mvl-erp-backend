"""Serializers for Contract model."""

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.api.serializers.common_nested import ContractTypeNestedSerializer, EmployeeNestedSerializer
from apps.hrm.models import Contract, ContractType, Employee
from libs.drf.serializers import ColoredValueSerializer, FieldFilteringSerializerMixin


# Nested serializer for parent_contract (used in appendix responses)
class ParentContractNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for parent contract reference."""

    class Meta:
        model = Contract
        fields = ["id", "code", "contract_number"]
        read_only_fields = fields


class ContractListSerializer(serializers.ModelSerializer):
    """Serializer for Contract list view."""

    # Nested serializers for employee and contract type
    employee = EmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)

    # Color representation for status
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "code",
            "contract_number",
            "employee",
            "contract_type",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status",
            "colored_status",
            "base_salary",
            "created_at",
        ]
        read_only_fields = fields


class ContractSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for Contract detail, create, and update operations.

    This serializer provides:
    - Validation: Only allows edit/delete when status is DRAFT
    - Date validation: Ensures proper date logic
    - Create logic: Copies snapshot data from ContractType
    - Validation: Contract type must have category='contract'
    - Status is read-only, calculated automatically by the model
    """

    file_confirm_fields = ["attachment"]

    # Nested read-only serializers for response
    employee = EmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)
    attachment = FileSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
        required=True,
        help_text="ID of the employee for this contract",
    )

    contract_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ContractType.objects.filter(category=ContractType.Category.CONTRACT),
        source="contract_type",
        write_only=True,
        required=True,
        help_text="ID of the contract type (must be category='contract')",
    )

    # Color representation for status
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "code",
            "contract_number",
            "employee",
            "employee_id",
            "contract_type",
            "contract_type_id",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status",
            "colored_status",
            "base_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "net_percentage",
            "tax_calculation_method",
            "has_social_insurance",
            "working_conditions",
            "rights_and_obligations",
            "terms",
            "note",
            "attachment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "contract_number",
            "employee",
            "contract_type",
            "status",
            "colored_status",
            "attachment",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate contract data.

        Ensures that:
        - sign_date <= effective_date
        - effective_date <= expiration_date (if expiration_date is set)
        - Only DRAFT contracts can be edited
        - Contract type must have category='contract'
        """
        instance = self.instance

        # Check if instance exists and validate status for update/delete
        if instance is not None and instance.pk is not None and instance.status != Contract.ContractStatus.DRAFT:
            raise serializers.ValidationError({"status": _("Only contracts with DRAFT status can be edited.")})

        # Validate contract type category
        contract_type = attrs.get("contract_type", getattr(instance, "contract_type", None) if instance else None)
        if contract_type and contract_type.category != ContractType.Category.CONTRACT:
            raise serializers.ValidationError(
                {"contract_type_id": _("Contract type must have category 'contract'.")}
            )

        # Get dates from attrs or fallback to instance values
        sign_date = attrs.get("sign_date", getattr(instance, "sign_date", None))
        effective_date = attrs.get("effective_date", getattr(instance, "effective_date", None))
        expiration_date = attrs.get("expiration_date", getattr(instance, "expiration_date", None))

        # Validate date logic
        if sign_date and effective_date and sign_date > effective_date:
            raise serializers.ValidationError({"sign_date": _("Sign date must be on or before effective date.")})

        if effective_date and expiration_date and effective_date > expiration_date:
            raise serializers.ValidationError(
                {"expiration_date": _("Expiration date must be on or after effective date.")}
            )

        return attrs

    def _copy_snapshot_from_contract_type(self, validated_data):
        """Copy snapshot data from ContractType to Contract.

        Args:
            validated_data: Validated data dict to update with snapshot values.
        """
        contract_type = validated_data.get("contract_type")
        if not contract_type:
            return

        # Fields to copy from contract_type if not provided
        snapshot_fields = [
            "base_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "net_percentage",
            "tax_calculation_method",
            "has_social_insurance",
            "working_conditions",
            "rights_and_obligations",
            "terms",
        ]

        for field in snapshot_fields:
            if field not in validated_data:
                validated_data[field] = getattr(contract_type, field)

    def create(self, validated_data):
        """Create Contract with snapshot data from ContractType.

        Args:
            validated_data: Validated data dict.

        Returns:
            Contract: Created contract instance.
        """
        # Copy snapshot data from contract type
        self._copy_snapshot_from_contract_type(validated_data)

        # Create and save instance - model.save() handles status calculation and expiring previous contracts
        return super().create(validated_data)


class ContractExportSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Contract XLSX export."""

    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_fullname = serializers.CharField(source="employee.fullname", read_only=True)
    contract_type_code = serializers.CharField(source="contract_type.code", read_only=True)
    contract_type_name = serializers.CharField(source="contract_type.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Contract
        fields = [
            "code",
            "contract_number",
            "employee_code",
            "employee_fullname",
            "contract_type_code",
            "contract_type_name",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status_display",
            "base_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            "has_social_insurance",
            "note",
            "created_at",
        ]
