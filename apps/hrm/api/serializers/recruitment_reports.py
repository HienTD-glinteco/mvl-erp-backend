from rest_framework import serializers

from apps.hrm.models import (
    HiredCandidateReport,
    RecruitmentChannelReport,
    RecruitmentCostReport,
    RecruitmentSourceReport,
    StaffGrowthReport,
)


class StaffGrowthReportSerializer(serializers.ModelSerializer):
    """Serializer for aggregated StaffGrowthReport data (read-only)."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    # Date fields may vary from individual records as reports aggregate by week/month
    start_date = serializers.DateField(source="report_date", read_only=True)
    end_date = serializers.DateField(source="report_date", read_only=True)

    class Meta:
        model = StaffGrowthReport
        fields = [
            "id",
            "start_date",
            "end_date",
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
        ]
        read_only_fields = fields


class RecruitmentSourceReportSerializer(serializers.ModelSerializer):
    """Serializer for aggregated RecruitmentSourceReport data (read-only)."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    source_name = serializers.CharField(source="recruitment_source.name", read_only=True)
    start_date = serializers.DateField(source="report_date", read_only=True)
    end_date = serializers.DateField(source="report_date", read_only=True)

    class Meta:
        model = RecruitmentSourceReport
        fields = [
            "id",
            "start_date",
            "end_date",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "recruitment_source",
            "source_name",
            "num_hires",
        ]
        read_only_fields = fields


class RecruitmentChannelReportSerializer(serializers.ModelSerializer):
    """Serializer for aggregated RecruitmentChannelReport data (read-only)."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    channel_name = serializers.CharField(source="recruitment_channel.name", read_only=True)
    start_date = serializers.DateField(source="report_date", read_only=True)
    end_date = serializers.DateField(source="report_date", read_only=True)

    class Meta:
        model = RecruitmentChannelReport
        fields = [
            "id",
            "start_date",
            "end_date",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "recruitment_channel",
            "channel_name",
            "num_hires",
        ]
        read_only_fields = fields


class RecruitmentCostReportSerializer(serializers.ModelSerializer):
    """Serializer for aggregated RecruitmentCostReport data (read-only)."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    start_date = serializers.DateField(source="report_date", read_only=True)
    end_date = serializers.DateField(source="report_date", read_only=True)

    class Meta:
        model = RecruitmentCostReport
        fields = [
            "id",
            "start_date",
            "end_date",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "source_type",
            "source_type_display",
            "total_cost",
            "num_hires",
            "avg_cost_per_hire",
        ]
        read_only_fields = fields


class HiredCandidateReportSerializer(serializers.ModelSerializer):
    """Serializer for aggregated HiredCandidateReport data (read-only)."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, allow_null=True)
    block_name = serializers.CharField(source="block.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.name", read_only=True, allow_null=True)
    employee_name = serializers.CharField(source="employee.fullname", read_only=True, allow_null=True)
    employee_code = serializers.CharField(source="employee.code", read_only=True, allow_null=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    start_date = serializers.DateField(source="report_date", read_only=True)
    end_date = serializers.DateField(source="report_date", read_only=True)

    class Meta:
        model = HiredCandidateReport
        fields = [
            "id",
            "start_date",
            "end_date",
            "branch",
            "branch_name",
            "block",
            "block_name",
            "department",
            "department_name",
            "source_type",
            "source_type_display",
            "employee",
            "employee_name",
            "employee_code",
            "num_candidates_hired",
        ]
        read_only_fields = fields
