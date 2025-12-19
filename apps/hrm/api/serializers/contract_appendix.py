"""Serializers for Contract Appendix (using Contract model with category='appendix')."""

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import ContractTypeNestedSerializer, EmployeeNestedSerializer
from apps.hrm.api.serializers.contract import ParentContractNestedSerializer
from apps.hrm.models import Contract, ContractType
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
    - Auto-set: contract_type and employee are derived from parent_contract
    - Validation: parent_contract is required
    - Status is read-only, calculated automatically by the model
    """

    # Nested read-only serializers for response
    employee = EmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)
    parent_contract = ParentContractNestedSerializer(read_only=True)

    # Write-only field for POST/PUT/PATCH operations
    # Note: employee and contract_type are auto-derived from parent_contract
    parent_contract_id = serializers.PrimaryKeyRelatedField(
        queryset=Contract.objects.filter(contract_type__category=ContractType.Category.CONTRACT),
        source="parent_contract",
        write_only=True,
        required=True,
        help_text="ID of the parent contract (employee and contract_type are derived from this)",
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
            "contract_type",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status",
            "colored_status",
            "base_salary",
            "kpi_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
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
        - parent_contract is required and must be in valid status
        """
        instance = self.instance

        # Check if instance exists and validate status for update/delete
        if instance is not None and instance.pk is not None and instance.status != Contract.ContractStatus.DRAFT:
            raise serializers.ValidationError({"status": _("Only appendices with DRAFT status can be edited.")})

        # Validate parent_contract is provided and in valid status
        parent_contract = attrs.get(
            "parent_contract", getattr(instance, "parent_contract", None) if instance else None
        )
        if not parent_contract and instance is None:
            raise serializers.ValidationError({"parent_contract_id": _("Parent contract is required for appendices.")})

        # Validate parent contract status (must be ACTIVE or ABOUT_TO_EXPIRE)
        if parent_contract and parent_contract.status not in [
            Contract.ContractStatus.ACTIVE,
            Contract.ContractStatus.ABOUT_TO_EXPIRE,
        ]:
            raise serializers.ValidationError(
                {"parent_contract_id": _("Parent contract must be in ACTIVE or ABOUT_TO_EXPIRE status.")}
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

        # Validate effective date against parent contract
        if effective_date and parent_contract and parent_contract.effective_date:
            if effective_date < parent_contract.effective_date:
                raise serializers.ValidationError(
                    {
                        "effective_date": _(
                            "Appendix effective date must be on or after parent contract effective date."
                        )
                    }
                )

        if expiration_date and parent_contract and parent_contract.expiration_date:
            if expiration_date > parent_contract.expiration_date:
                raise serializers.ValidationError(
                    {
                        "expiration_date": _(
                            "Appendix expiration date must be on or before parent contract expiration date."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        """Create Contract Appendix with auto-derived employee and contract_type.

        Args:
            validated_data: Validated data dict.

        Returns:
            Contract: Created appendix instance.
        """
        parent_contract = validated_data.get("parent_contract")

        # Auto-set employee from parent contract
        validated_data["employee"] = parent_contract.employee

        # Auto-set contract_type_id to the appendix type (uses cached value)
        try:
            validated_data["contract_type_id"] = ContractType.get_appendix_type_id()
        except ValueError as e:
            raise serializers.ValidationError({"contract_type": str(e)})

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update Contract Appendix.

        If parent_contract is changed, update employee accordingly.

        Args:
            instance: Existing Contract instance.
            validated_data: Validated data dict.

        Returns:
            Contract: Updated appendix instance.
        """
        parent_contract = validated_data.get("parent_contract")

        # If parent_contract is changed, update employee
        if parent_contract and parent_contract != instance.parent_contract:
            validated_data["employee"] = parent_contract.employee

        return super().update(instance, validated_data)


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
