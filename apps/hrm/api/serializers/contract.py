"""Serializers for Contract model."""

from datetime import date

from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.files.api.serializers import FileSerializer
from apps.files.api.serializers.mixins import FileConfirmSerializerMixin
from apps.hrm.models import Contract, ContractType, Employee
from apps.hrm.utils.contract_code import generate_contract_number
from libs.drf.serializers import ColoredValueSerializer, FieldFilteringSerializerMixin


class ContractEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references."""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname", "email"]
        read_only_fields = ["id", "code", "fullname", "email"]


class ContractTypeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested contract type references."""

    class Meta:
        model = ContractType
        fields = ["id", "code", "name", "symbol"]
        read_only_fields = ["id", "code", "name", "symbol"]


class ContractListSerializer(serializers.ModelSerializer):
    """Serializer for Contract list view with flattened employee and contract type data."""

    # Flattened employee fields
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    employee_code = serializers.CharField(source="employee.code", read_only=True)
    employee_fullname = serializers.CharField(source="employee.fullname", read_only=True)

    # Flattened contract type fields
    contract_type_id = serializers.IntegerField(source="contract_type.id", read_only=True)
    contract_type_code = serializers.CharField(source="contract_type.code", read_only=True)
    contract_type_name = serializers.CharField(source="contract_type.name", read_only=True)

    # Color representation for status
    colored_status = ColoredValueSerializer(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "code",
            "contract_number",
            "employee_id",
            "employee_code",
            "employee_fullname",
            "contract_type_id",
            "contract_type_code",
            "contract_type_name",
            "sign_date",
            "effective_date",
            "expiration_date",
            "status",
            "colored_status",
            "base_salary",
            "created_at",
        ]
        read_only_fields = fields


class ContractDetailSerializer(serializers.ModelSerializer):
    """Serializer for Contract detail view with full information."""

    # Nested serializers for full object representation
    employee = ContractEmployeeNestedSerializer(read_only=True)
    contract_type = ContractTypeNestedSerializer(read_only=True)
    attachment = FileSerializer(read_only=True)

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
        read_only_fields = fields


class ContractCUDSerializer(FileConfirmSerializerMixin, serializers.ModelSerializer):
    """Serializer for Contract create/update/delete operations.

    This serializer provides:
    - Validation: Only allows edit/delete when status is DRAFT
    - Date validation: Ensures proper date logic
    - Create logic: Generates contract_number and copies snapshot data from ContractType
    - Update logic: Recalculates status if dates change
    """

    file_confirm_fields = ["attachment"]

    # Nested read-only serializers for response
    employee = ContractEmployeeNestedSerializer(read_only=True)
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
        queryset=ContractType.objects.all(),
        source="contract_type",
        write_only=True,
        required=True,
        help_text="ID of the contract type",
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
        """
        instance = self.instance

        # Check if instance exists and validate status for update/delete
        if instance and instance.status != Contract.ContractStatus.DRAFT:
            raise serializers.ValidationError({"status": _("Only contracts with DRAFT status can be edited.")})

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

    def _calculate_status(self, effective_date, expiration_date):
        """Calculate contract status based on dates.

        Args:
            effective_date: Contract effective date.
            expiration_date: Contract expiration date (can be None).

        Returns:
            Contract.ContractStatus: Calculated status.
        """
        today = date.today()

        if effective_date > today:
            return Contract.ContractStatus.NOT_EFFECTIVE

        if expiration_date is None:
            # Indefinite contract - always active after effective date
            return Contract.ContractStatus.ACTIVE

        if expiration_date < today:
            return Contract.ContractStatus.EXPIRED

        # Calculate days until expiration
        days_until_expiration = (expiration_date - today).days

        if days_until_expiration <= 30:
            return Contract.ContractStatus.ABOUT_TO_EXPIRE

        return Contract.ContractStatus.ACTIVE

    def _expire_previous_contracts(self, employee):
        """Mark previous active contracts as expired.

        Args:
            employee: Employee instance whose contracts should be expired.
        """
        Contract.objects.filter(
            employee=employee,
            status__in=[
                Contract.ContractStatus.ACTIVE,
                Contract.ContractStatus.ABOUT_TO_EXPIRE,
            ],
        ).update(status=Contract.ContractStatus.EXPIRED)

    def create(self, validated_data):
        """Create Contract with generated contract_number and snapshot data.

        Args:
            validated_data: Validated data dict.

        Returns:
            Contract: Created contract instance.
        """
        # Copy snapshot data from contract type
        self._copy_snapshot_from_contract_type(validated_data)

        # Create instance first (without contract_number)
        # We need the instance to generate contract_number
        instance = Contract(**validated_data)

        # Generate contract_number
        instance.contract_number = generate_contract_number(instance)

        # Save the instance
        instance.save()

        # Expire previous active contracts for the employee
        self._expire_previous_contracts(instance.employee)

        return instance

    def update(self, instance, validated_data):
        """Update Contract and recalculate status if dates change.

        Args:
            instance: Existing Contract instance.
            validated_data: Validated data dict.

        Returns:
            Contract: Updated contract instance.
        """
        # Check if dates are being updated
        effective_date = validated_data.get("effective_date", instance.effective_date)
        expiration_date = validated_data.get("expiration_date", instance.expiration_date)

        # If status is not explicitly provided and dates changed, recalculate status
        if "status" not in validated_data:
            dates_changed = (
                validated_data.get("effective_date") is not None or validated_data.get("expiration_date") is not None
            )
            if dates_changed:
                new_status = self._calculate_status(effective_date, expiration_date)
                validated_data["status"] = new_status

        return super().update(instance, validated_data)


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
