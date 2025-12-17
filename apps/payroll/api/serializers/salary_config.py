from rest_framework import serializers

from apps.payroll.models import SalaryConfig


class SocialInsuranceSerializer(serializers.Serializer):
    """Serializer for social insurance configuration"""

    employee_rate = serializers.FloatField()
    employer_rate = serializers.FloatField()
    salary_ceiling = serializers.IntegerField()


class InsuranceContributionsSerializer(serializers.Serializer):
    """Serializer for all insurance contributions configuration"""

    social_insurance = SocialInsuranceSerializer()
    health_insurance = SocialInsuranceSerializer()
    unemployment_insurance = SocialInsuranceSerializer()
    union_fee = SocialInsuranceSerializer()
    accident_occupational_insurance = SocialInsuranceSerializer()


class ProgressiveTaxLevelSerializer(serializers.Serializer):
    """Serializer for a single progressive tax level"""

    up_to = serializers.IntegerField(allow_null=True)
    rate = serializers.FloatField()


class PersonalIncomeTaxSerializer(serializers.Serializer):
    """Serializer for personal income tax configuration"""

    standard_deduction = serializers.IntegerField()
    dependent_deduction = serializers.IntegerField()
    progressive_levels = ProgressiveTaxLevelSerializer(many=True)


class KpiTierSerializer(serializers.Serializer):
    """Serializer for a single KPI tier"""

    code = serializers.CharField()
    percentage = serializers.FloatField()
    description = serializers.CharField()


class KpiSalarySerializer(serializers.Serializer):
    """Serializer for KPI salary configuration"""

    apply_on = serializers.CharField()
    tiers = KpiTierSerializer(many=True)


class BusinessCommissionCriteriaSerializer(serializers.Serializer):
    """Serializer for business commission criteria"""

    name = serializers.CharField()
    min = serializers.IntegerField()


class BusinessCommissionTierSerializer(serializers.Serializer):
    """Serializer for business commission tier"""

    code = serializers.CharField()
    amount = serializers.IntegerField()
    criteria = BusinessCommissionCriteriaSerializer(many=True)


class BusinessProgressiveSalarySerializer(serializers.Serializer):
    """Serializer for business progressive salary configuration"""

    apply_on = serializers.CharField()
    tiers = BusinessCommissionTierSerializer(many=True)


class SalaryConfigSchemaSerializer(serializers.Serializer):
    """Complete salary configuration schema serializer.

    This serializer validates the entire config JSON structure.
    """

    insurance_contributions = InsuranceContributionsSerializer()
    personal_income_tax = PersonalIncomeTaxSerializer()
    kpi_salary = KpiSalarySerializer()
    business_progressive_salary = BusinessProgressiveSalarySerializer()


class SalaryConfigSerializer(serializers.ModelSerializer):
    """Serializer for SalaryConfig model.

    This serializer includes validation of the config JSON field
    using the SalaryConfigSchemaSerializer.
    """

    config = SalaryConfigSchemaSerializer()

    class Meta:
        model = SalaryConfig
        fields = ["id", "version", "config", "updated_at", "created_at"]
        read_only_fields = ["id", "version", "updated_at", "created_at"]

    def validate_config(self, value):
        """Validate config structure using nested serializers."""
        serializer = SalaryConfigSchemaSerializer(data=value)
        serializer.is_valid(raise_exception=True)
        return value
