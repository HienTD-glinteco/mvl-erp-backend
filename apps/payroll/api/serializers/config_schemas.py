from rest_framework import serializers


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


class ProgressiveTaxLevelSerializer(serializers.Serializer):
    """Serializer for a single progressive tax level"""

    up_to = serializers.IntegerField(allow_null=True)
    rate = serializers.FloatField()


class PersonalIncomeTaxSerializer(serializers.Serializer):
    """Serializer for personal income tax configuration"""

    standard_deduction = serializers.IntegerField()
    dependent_deduction = serializers.IntegerField()
    progressive_levels = ProgressiveTaxLevelSerializer(many=True)


class KpiGradesSerializer(serializers.Serializer):
    """Serializer for KPI grade multipliers"""

    A = serializers.FloatField()
    B = serializers.FloatField()
    C = serializers.FloatField()
    D = serializers.FloatField()


class KpiSalarySerializer(serializers.Serializer):
    """Serializer for KPI salary configuration"""

    grades = KpiGradesSerializer()


class BusinessLevelsSerializer(serializers.Serializer):
    """Serializer for business progressive salary levels"""

    M0 = serializers.CharField()
    M1 = serializers.IntegerField()
    M2 = serializers.IntegerField()
    M3 = serializers.IntegerField()
    M4 = serializers.IntegerField()


class BusinessProgressiveSalarySerializer(serializers.Serializer):
    """Serializer for business progressive salary configuration"""

    levels = BusinessLevelsSerializer()


class SalaryConfigSchemaSerializer(serializers.Serializer):
    """Complete salary configuration schema serializer.

    This serializer validates the entire config JSON structure.
    """

    insurance_contributions = InsuranceContributionsSerializer()
    personal_income_tax = PersonalIncomeTaxSerializer()
    kpi_salary = KpiSalarySerializer()
    business_progressive_salary = BusinessProgressiveSalarySerializer()
