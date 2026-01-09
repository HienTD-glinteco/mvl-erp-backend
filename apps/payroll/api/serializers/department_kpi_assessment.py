from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Department
from apps.payroll.api.serializers.common_nested import (
    BlockNestedSerializer,
    BranchNestedSerializer,
    DepartmentNestedSerializer,
    EmployeeNestedSerializer,
    KPIAssessmentPeriodNestedSerializer,
)
from apps.payroll.models import DepartmentKPIAssessment


class DepartmentKPIAssessmentSerializer(serializers.ModelSerializer):
    """Serializer for DepartmentKPIAssessment model.

    Provides full CRUD operations for department KPI assessments.
    """

    block = BlockNestedSerializer(source="department.block", read_only=True)
    branch = BranchNestedSerializer(source="department.branch", read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
    )
    leader = EmployeeNestedSerializer(source="department.leader", read_only=True)
    period_detail = KPIAssessmentPeriodNestedSerializer(source="period", read_only=True)
    kpi_config_snapshot = serializers.JSONField(source="period.kpi_config_snapshot", read_only=True)

    class Meta:
        model = DepartmentKPIAssessment
        fields = [
            "id",
            "period",
            "period_detail",
            "block",
            "branch",
            "department",
            "department_id",
            "leader",
            "kpi_config_snapshot",
            "grade",
            "default_grade",
            "assigned_by",
            "assigned_at",
            "finalized",
            "note",
            "grade_distribution",
            "manager_grade_distribution",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "block",
            "branch",
            "kpi_config_snapshot",
            "default_grade",
            "assigned_by",
            "assigned_at",
            "grade_distribution",
            "manager_grade_distribution",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """Ensure grade_distribution has default structure if empty."""
        data = super().to_representation(instance)
        if not data.get("grade_distribution"):
            data["grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        if not data.get("manager_grade_distribution"):
            data["manager_grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        return data

    def validate(self, data):
        """Validate department assessment data."""
        # Check if assessment already exists for department and period
        if not self.instance:
            department = data.get("department")
            period = data.get("period")
            if department and period:
                exists = DepartmentKPIAssessment.objects.filter(
                    department=department,
                    period=period,
                ).exists()
                if exists:
                    raise serializers.ValidationError(_("An assessment for this department and period already exists"))

        # Validate grade is one of A/B/C/D
        grade = data.get("grade")
        if grade and grade not in ["A", "B", "C", "D"]:
            raise serializers.ValidationError(_("Grade must be one of: A, B, C, D"))

        # Check if trying to update finalized assessment
        if self.instance and self.instance.finalized:
            allowed_fields = {"grade", "note"}
            changed_fields = set(data.keys())
            if not changed_fields.issubset(allowed_fields):
                raise serializers.ValidationError(_("Only grade and note can be updated for finalized assessments"))

        return data


class DepartmentKPIAssessmentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing department KPI assessments."""

    block = BlockNestedSerializer(source="department.block", read_only=True)
    branch = BranchNestedSerializer(source="department.branch", read_only=True)
    department = DepartmentNestedSerializer(read_only=True)
    leader = EmployeeNestedSerializer(source="department.leader", read_only=True)
    period = KPIAssessmentPeriodNestedSerializer(read_only=True)
    is_valid_unit_control = serializers.BooleanField(read_only=True)
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DepartmentKPIAssessment
        fields = [
            "id",
            "period",
            "block",
            "branch",
            "department",
            "leader",
            "grade",
            "grade_distribution",
            "manager_grade_distribution",
            "note",
            "finalized",
            "is_valid_unit_control",
            "employee_count",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance):
        """Ensure grade_distribution has default structure if empty."""
        data = super().to_representation(instance)
        if not data.get("grade_distribution"):
            data["grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        if not data.get("manager_grade_distribution"):
            data["manager_grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        return data


class DepartmentKPIAssessmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specific fields of DepartmentKPIAssessment."""

    class Meta:
        model = DepartmentKPIAssessment
        fields = ["grade", "note", "grade_distribution", "manager_grade_distribution"]
        read_only_fields = ["grade_distribution", "manager_grade_distribution"]

    def validate_grade(self, value):
        """Validate grade is one of A/B/C/D."""
        if value and value not in ["A", "B", "C", "D"]:
            raise serializers.ValidationError(_("Grade must be one of: A, B, C, D"))
        return value

    def to_representation(self, instance):
        """Ensure grade_distribution has default structure if empty."""
        data = super().to_representation(instance)
        if not data.get("grade_distribution"):
            data["grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        if not data.get("manager_grade_distribution"):
            data["manager_grade_distribution"] = {"A": 0, "B": 0, "C": 0, "D": 0}
        return data

    def update(self, instance, validated_data):
        """Update department assessment and sync leader's grade_hrm."""
        from apps.payroll.models import EmployeeKPIAssessment

        grade = validated_data.get("grade")

        # Update department assessment
        instance = super().update(instance, validated_data)

        # If grade changed and department has a leader, update leader's employee assessment
        if grade and instance.department.leader:
            EmployeeKPIAssessment.objects.filter(
                employee=instance.department.leader,
                period=instance.period,
            ).update(grade_hrm=grade)

        return instance
