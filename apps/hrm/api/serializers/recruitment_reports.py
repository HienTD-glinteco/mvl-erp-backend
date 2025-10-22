from rest_framework import serializers

from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    ReferralCostReport,
    StaffGrowthReport,
)


class StaffGrowthReportSerializer(serializers.ModelSerializer):
    """Serializer for StaffGrowthReport model."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)

    class Meta:
        model = StaffGrowthReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "num_introductions",
            "num_returns",
            "num_new_hires",
            "num_transfers",
            "num_resignations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecruitmentSourceReportSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentSourceReport model."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    source_name = serializers.CharField(source="recruitment_source.name", read_only=True)

    class Meta:
        model = RecruitmentSourceReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "recruitment_source",
            "source_name",
            "org_unit_name",
            "org_unit_type",
            "num_hires",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecruitmentChannelReportSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentChannelReport model."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    channel_name = serializers.CharField(source="recruitment_channel.name", read_only=True)

    class Meta:
        model = RecruitmentChannelReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "recruitment_channel",
            "channel_name",
            "org_unit_name",
            "org_unit_type",
            "num_hires",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RecruitmentCostReportSerializer(serializers.ModelSerializer):
    """Serializer for RecruitmentCostReport model."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    source_name = serializers.CharField(source="recruitment_source.name", read_only=True, allow_null=True)
    channel_name = serializers.CharField(source="recruitment_channel.name", read_only=True, allow_null=True)

    class Meta:
        model = RecruitmentCostReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "recruitment_source",
            "source_name",
            "recruitment_channel",
            "channel_name",
            "total_cost",
            "num_hires",
            "avg_cost_per_hire",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class HiredCandidateReportSerializer(serializers.ModelSerializer):
    """Serializer for HiredCandidateReport model."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    employee_name = serializers.CharField(source="employee.fullname", read_only=True, allow_null=True)
    employee_code = serializers.CharField(source="employee.code", read_only=True, allow_null=True)

    class Meta:
        model = HiredCandidateReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "source_type",
            "employee",
            "employee_name",
            "employee_code",
            "num_candidates_hired",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ReferralCostReportSerializer(serializers.ModelSerializer):
    """Serializer for ReferralCostReport model."""

    department_name = serializers.CharField(source="department.name", read_only=True)
    employee_name = serializers.CharField(source="employee.fullname", read_only=True, allow_null=True)
    employee_code = serializers.CharField(source="employee.code", read_only=True, allow_null=True)

    class Meta:
        model = ReferralCostReport
        fields = [
            "id",
            "report_date",
            "period_type",
            "department",
            "department_name",
            "employee",
            "employee_name",
            "employee_code",
            "total_referral_cost",
            "num_referrals",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
