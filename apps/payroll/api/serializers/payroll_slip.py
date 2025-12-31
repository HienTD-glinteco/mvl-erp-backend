"""Serializers for PayrollSlip model."""

from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import EmployeeNestedSerializer
from apps.payroll.models import PayrollSlip
from libs import ColoredValueSerializer

from .common_nested import SalaryPeriodNestedSerializer


class PayrollSlipSerializer(serializers.ModelSerializer):
    """Serializer for PayrollSlip with all calculation fields.

    Used for both list and detail views to provide complete payroll information.
    """

    employee = EmployeeNestedSerializer(read_only=True)
    salary_period = SalaryPeriodNestedSerializer(read_only=True)
    colored_status = ColoredValueSerializer(source="get_colored_status", read_only=True)

    class Meta:
        model = PayrollSlip
        fields = [
            # Basic info
            "id",
            "code",
            "salary_period",
            "employee",
            "employee_code",
            "employee_name",
            "department_name",
            "position_name",
            "employment_status",
            "has_unpaid_penalty",
            "unpaid_penalty_count",
            # Contract info
            "contract_id",
            "base_salary",
            "kpi_salary",
            "lunch_allowance",
            "phone_allowance",
            "other_allowance",
            # KPI
            "kpi_grade",
            "kpi_percentage",
            "kpi_bonus",
            # Sales
            "sales_revenue",
            "sales_transaction_count",
            "business_grade",
            "business_progressive_salary",
            # Working days
            "standard_working_days",
            "total_working_days",
            "official_working_days",
            "probation_working_days",
            # Overtime
            "tc1_overtime_hours",
            "tc2_overtime_hours",
            "tc3_overtime_hours",
            "total_overtime_hours",
            "hourly_rate",
            "overtime_pay",
            "total_position_income",
            "actual_working_days_income",
            "taxable_overtime_salary",
            "overtime_progress_allowance",
            "non_taxable_overtime_salary",
            # Travel expenses
            "taxable_travel_expense",
            "non_taxable_travel_expense",
            "total_travel_expense",
            # Income
            "gross_income",
            "taxable_income_base",
            # Insurance (employee)
            "social_insurance_base",
            "employee_social_insurance",
            "employee_health_insurance",
            "employee_unemployment_insurance",
            "employee_union_fee",
            # Insurance (employer)
            "employer_social_insurance",
            "employer_health_insurance",
            "employer_unemployment_insurance",
            "employer_union_fee",
            "employer_accident_insurance",
            # Tax
            "personal_deduction",
            "dependent_count",
            "dependent_deduction",
            "taxable_income",
            "personal_income_tax",
            # Vouchers
            "back_pay_amount",
            "recovery_amount",
            # Final
            "net_salary",
            # Status
            "status",
            "colored_status",
            "status_note",
            "need_resend_email",
            "email_sent_at",
            "delivered_at",
            "delivered_by",
            # Audit
            "calculation_log",
            "calculated_at",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = fields

    def get_colored_status(self, obj):
        """Get colored status value."""
        return obj.get_colored_value("status")


class PayrollSlipHoldSerializer(serializers.Serializer):
    """Serializer for holding a payroll slip."""

    reason = serializers.CharField(required=True, max_length=500, help_text="Reason for holding the payroll slip")


class PayrollSlipStatusUpdateSerializer(serializers.Serializer):
    """Serializer for status update responses."""

    id = serializers.IntegerField()
    status = serializers.CharField()
    status_note = serializers.CharField()
