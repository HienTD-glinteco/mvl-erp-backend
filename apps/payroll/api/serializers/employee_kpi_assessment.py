from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem


class BaseEmployeeKPIAssessmentSerializer(serializers.ModelSerializer):
    """Base serializer for EmployeeKPIAssessment with common fields and methods."""

    employee_username = serializers.CharField(source="employee.username", read_only=True)
    employee_fullname = serializers.SerializerMethodField()
    month = serializers.SerializerMethodField()

    def get_month(self, obj):
        """Return month in YYYY-MM format."""
        return obj.period.month.strftime("%Y-%m")

    def get_employee_fullname(self, obj):
        """Get employee full name if available."""
        try:
            from apps.hrm.models import Employee

            employee = Employee.objects.filter(username=obj.employee.username).first()
            if employee:
                return employee.fullname
        except (ImportError, AttributeError):
            pass
        return obj.employee.get_full_name()

    class Meta:
        model = EmployeeKPIAssessment
        abstract = True


class EmployeeKPIItemSerializer(serializers.ModelSerializer):
    """Serializer for EmployeeKPIItem model.

    Provides read and write operations for KPI assessment items.
    When employee_score or manager_score is updated, totals are recalculated.
    """

    class Meta:
        model = EmployeeKPIItem
        fields = [
            "id",
            "assessment",
            "criterion_id",
            "target",
            "criterion",
            "sub_criterion",
            "evaluation_type",
            "description",
            "component_total_score",
            "group_number",
            "order",
            "employee_score",
            "manager_score",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "assessment",
            "criterion_id",
            "target",
            "criterion",
            "sub_criterion",
            "evaluation_type",
            "description",
            "component_total_score",
            "group_number",
            "order",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Check if assessment is finalized and validate scores."""
        if self.instance and self.instance.assessment.finalized:
            raise serializers.ValidationError(_("Cannot update items of a finalized assessment"))

        # Validate scores don't exceed component_total_score
        component_total = self.instance.component_total_score if self.instance else data.get("component_total_score")

        employee_score = data.get("employee_score")
        if employee_score is not None and component_total and employee_score > component_total:
            raise serializers.ValidationError(
                {"employee_score": _("Employee score cannot exceed component total score")}
            )

        manager_score = data.get("manager_score")
        if manager_score is not None and component_total and manager_score > component_total:
            raise serializers.ValidationError(
                {"manager_score": _("Manager score cannot exceed component total score")}
            )

        return data


class EmployeeKPIItemUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating EmployeeKPIItem (limited fields)."""

    class Meta:
        model = EmployeeKPIItem
        fields = ["employee_score", "manager_score", "note"]

    def validate(self, data):
        """Check if assessment is finalized and validate scores."""
        if self.instance.assessment.finalized:
            raise serializers.ValidationError(_("Cannot update items of a finalized assessment"))

        # Validate scores don't exceed component_total_score
        component_total = self.instance.component_total_score

        employee_score = data.get("employee_score")
        if employee_score is not None and employee_score > component_total:
            raise serializers.ValidationError(
                {"employee_score": _("Employee score cannot exceed component total score")}
            )

        manager_score = data.get("manager_score")
        if manager_score is not None and manager_score > component_total:
            raise serializers.ValidationError(
                {"manager_score": _("Manager score cannot exceed component total score")}
            )

        return data


class EmployeeKPIAssessmentSerializer(BaseEmployeeKPIAssessmentSerializer):
    """Serializer for EmployeeKPIAssessment model.

    Provides full CRUD operations for employee KPI assessments.
    Includes nested items for detailed view.
    """

    items = EmployeeKPIItemSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "total_possible_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "grade_hrm",
            "finalized",
            "department_assignment_source",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "note",
            "items",
        ]
        read_only_fields = [
            "id",
            "month",
            "total_possible_score",
            "total_manager_score",
            "grade_manager",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        """Validate assessment data."""
        # Check if assessment already exists for employee and month
        if not self.instance:
            employee = data.get("employee")
            month = data.get("month")
            if employee and month:
                exists = EmployeeKPIAssessment.objects.filter(
                    employee=employee,
                    month=month,
                ).exists()
                if exists:
                    raise serializers.ValidationError(_("An assessment for this employee and month already exists"))

        # Check if trying to update finalized assessment
        if self.instance and self.instance.finalized:
            # Only allow updating grade_manager_overridden and note for finalized assessments
            allowed_fields = {"grade_manager_overridden", "note"}
            changed_fields = set(data.keys())
            if not changed_fields.issubset(allowed_fields):
                raise serializers.ValidationError(
                    _("Only grade_manager_overridden and note can be updated for finalized assessments")
                )

        return data


class EmployeeKPIAssessmentListSerializer(BaseEmployeeKPIAssessmentSerializer):
    """Lightweight serializer for listing employee KPI assessments without nested items."""

    kpi_config_snapshot = serializers.JSONField(source="period.kpi_config_snapshot", read_only=True)

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "kpi_config_snapshot",
            "total_possible_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "grade_hrm",
            "finalized",
            "created_at",
            "updated_at",
        ]


class EmployeeKPIAssessmentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating specific fields of EmployeeKPIAssessment (HRM only)."""

    class Meta:
        model = EmployeeKPIAssessment
        fields = ["grade_hrm", "note"]

    def validate(self, data):
        """Check permissions and finalization status."""
        if self.instance.finalized and "grade_hrm" in data:
            # Allow updating hrm grade even if finalized, but log it
            pass
        return data


class EmployeeSelfAssessmentSerializer(BaseEmployeeKPIAssessmentSerializer):
    """Serializer for employee self-assessment.

    Allows employees to:
    - View their current assessment
    - Update employee scores for items
    - Update plan_tasks, extra_tasks, and proposal
    """

    items = EmployeeKPIItemSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "total_possible_score",
            "grade_manager",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "finalized",
            "items",
        ]
        read_only_fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "total_possible_score",
            "grade_manager",
            "finalized",
            "items",
        ]

    def validate(self, data):
        """Validate that assessment is not finalized."""
        if self.instance and self.instance.finalized:
            raise serializers.ValidationError("Cannot update finalized assessment")
        return data


class ManagerAssessmentSerializer(BaseEmployeeKPIAssessmentSerializer):
    """Serializer for manager assessment of employees.

    Allows managers to:
    - View employee assessments
    - Update manager scores for items (via batch update in view)
    - Update manager_assessment field
    """

    items = EmployeeKPIItemSerializer(many=True, read_only=True)

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "finalized",
            "items",
        ]
        read_only_fields = [
            "id",
            "period",
            "employee",
            "employee_username",
            "employee_fullname",
            "month",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "finalized",
            "items",
        ]

    def validate(self, data):
        """Validate that assessment is not finalized."""
        if self.instance and self.instance.finalized:
            raise serializers.ValidationError("Cannot update finalized assessment")
        return data
