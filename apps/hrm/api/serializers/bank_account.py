from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.hrm.models import Bank, BankAccount, Employee


class BankAccountBankNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested bank references"""

    class Meta:
        model = Bank
        fields = ["id", "name", "code"]
        read_only_fields = ["id", "name", "code"]


class BankAccountEmployeeNestedSerializer(serializers.ModelSerializer):
    """Simplified serializer for nested employee references"""

    class Meta:
        model = Employee
        fields = ["id", "code", "fullname"]
        read_only_fields = ["id", "code", "fullname"]


class BankAccountSerializer(serializers.ModelSerializer):
    """Serializer for BankAccount model with CRUD operations"""

    # Nested read-only serializers for full object representation
    bank = BankAccountBankNestedSerializer(read_only=True)
    employee = BankAccountEmployeeNestedSerializer(read_only=True)

    # Write-only fields for POST/PUT/PATCH operations
    bank_id = serializers.PrimaryKeyRelatedField(
        queryset=Bank.objects.all(),
        source="bank",
        write_only=True,
        required=True,
    )
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
        required=True,
    )

    class Meta:
        model = BankAccount
        fields = [
            "id",
            "employee",
            "employee_id",
            "bank",
            "bank_id",
            "account_number",
            "account_name",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "bank",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        """Validate bank account data by delegating to model's clean() method"""
        # Create a temporary instance with the provided data for validation
        instance = self.instance or BankAccount()

        # Apply attrs to the instance
        for attr, value in attrs.items():
            setattr(instance, attr, value)

        # Call model's clean() method to perform business logic validation
        try:
            instance.clean()
        except DjangoValidationError as e:
            # Convert Django ValidationError to DRF ValidationError
            if hasattr(e, "message_dict"):
                raise serializers.ValidationError(e.message_dict)
            else:
                raise serializers.ValidationError({"non_field_errors": e.messages})

        return attrs
