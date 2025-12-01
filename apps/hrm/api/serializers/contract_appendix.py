"""Serializers for Contract Appendix (using Contract model with category='appendix')."""

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import ContractTypeNestedSerializer, EmployeeNestedSerializer
from apps.hrm.api.serializers.contract import ParentContractNestedSerializer
from apps.hrm.models import Contract, ContractType, Employee
from libs.drf.serializers import ColoredValueSerializer, FieldFilteringSerializerMixin


class ContractAppendixListSerializer(serializers.ModelSerializer):
    """Serializer for Contract Appendix list view."""

    # Nested serializers for employee, contract type, and parent contract
    employee = EmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)
    parent_contract = ParentContractNestedSerializer(read_only=True)

    # Color representation for status
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "code",
            "contract_number",
            "parent_contract",
            "employee",
            "contract_type",
            "sign_date",
            "effective_date",
            "status",
            "colored_status",
            "created_at",
        ]
        read_only_fields = fields


class ContractAppendixSerializer(serializers.ModelSerializer):
    """Serializer for Contract Appendix detail, create, and update operations.

    This serializer provides:
    - Validation: Only allows edit/delete when status is DRAFT
    - Date validation: Ensures proper date logic
    - Validation: Contract type must have category='appendix'
    - Validation: parent_contract is required
    - Status is read-only, calculated automatically by the model
    """

    # Nested read-only serializers for response
    employee = EmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)
    parent_contract = ParentContractNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
        required=True,
        help_text="ID of the employee for this appendix",
    )

    contract_type_id = serializers.PrimaryKeyRelatedField(
        queryset=ContractType.objects.filter(category=ContractType.Category.APPENDIX),
        source="contract_type",
        write_only=True,
        required=True,
        help_text="ID of the contract type (must be category='appendix')",
    )

    parent_contract_id = serializers.PrimaryKeyRelatedField(
        queryset=Contract.objects.filter(contract_type__category=ContractType.Category.CONTRACT),
        source="parent_contract",
        write_only=True,
        required=True,
        help_text="ID of the parent contract",
    )

    # Color representation for status
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "code",
            "contract_number",
            "parent_contract",
            "parent_contract_id",
            "employee",
            "employee_id",
            "contract_type",
            "contract_type_id",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status",
            "colored_status",
            "content",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "contract_number",
            "parent_contract",
            "employee",
            "contract_type",
            "status",
            "colored_status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate contract appendix data.

        Ensures that:
        - sign_date <= effective_date
        - effective_date <= expiration_date (if expiration_date is set)
        - Only DRAFT appendices can be edited
        - Contract type must have category='appendix'
        - parent_contract is required
        """
        instance = self.instance

        # Check if instance exists and validate status for update/delete
        if instance is not None and instance.pk is not None and instance.status != Contract.ContractStatus.DRAFT:
            raise serializers.ValidationError({"status": _("Only appendices with DRAFT status can be edited.")})

        # Validate contract type category
        contract_type = attrs.get("contract_type", getattr(instance, "contract_type", None) if instance else None)
        if contract_type and contract_type.category != ContractType.Category.APPENDIX:
            raise serializers.ValidationError(
                {"contract_type_id": _("Contract type must have category 'appendix'.")}
            )

        # Validate parent_contract is provided
        parent_contract = attrs.get("parent_contract", getattr(instance, "parent_contract", None) if instance else None)
        if not parent_contract and instance is None:
            raise serializers.ValidationError(
                {"parent_contract_id": _("Parent contract is required for appendices.")}
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


class ContractAppendixExportSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for Contract Appendix XLSX export."""

    parent_contract_code = serializers.CharField(source="parent_contract.code", read_only=True)
    parent_contract_number = serializers.CharField(source="parent_contract.contract_number", read_only=True)
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_fullname = serializers.CharField(source="employee.fullname", read_only=True)
    contract_type_name = serializers.CharField(source="contract_type.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Contract
        fields = [
            "code",
            "contract_number",
            "parent_contract_code",
            "parent_contract_number",
            "employee_code",
            "employee_fullname",
            "contract_type_name",
            "sign_date",
            "effective_date",
            "status_display",
            "content",
            "note",
            "created_at",
        ]

