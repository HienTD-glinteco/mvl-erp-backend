from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.payroll.models import DepartmentKPIAssessment


class DepartmentKPIAssessmentSerializer(serializers.ModelSerializer):
    """Serializer for DepartmentKPIAssessment model.

    Provides full CRUD operations for department KPI assessments.
    """

    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    month = serializers.DateField(source="period.month", read_only=True)
    kpi_config_snapshot = serializers.JSONField(source="period.kpi_config_snapshot", read_only=True)

    class Meta:
        model = DepartmentKPIAssessment
        fields = [
            "id",
            "period",
            "department",
            "department_name",
            "department_code",
            "month",
            "kpi_config_snapshot",
            "grade",
            "default_grade",
            "assigned_by",
            "assigned_at",
            "finalized",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "note",
        ]
        read_only_fields = [
            "id",
            "month",
            "kpi_config_snapshot",
            "default_grade",
            "assigned_by",
            "assigned_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

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

    department_name = serializers.CharField(source="department.name", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    month = serializers.DateField(source="period.month", read_only=True)
    # kpi_config_snapshot = serializers.JSONField(source="period.kpi_config_snapshot", read_only=True)

    class Meta:
        model = DepartmentKPIAssessment
        fields = [
            "id",
            "period_id",
            "department",
            "department_name",
            "department_code",
            "month",
            # "kpi_config_snapshot",
            "grade",
            "finalized",
            "created_at",
            "updated_at",
        ]


class DepartmentKPIAssessmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specific fields of DepartmentKPIAssessment."""

    class Meta:
        model = DepartmentKPIAssessment
        fields = ["grade", "note"]

    def validate_grade(self, value):
        """Validate grade is one of A/B/C/D."""
        if value and value not in ["A", "B", "C", "D"]:
            raise serializers.ValidationError(_("Grade must be one of: A, B, C, D"))
        return value
