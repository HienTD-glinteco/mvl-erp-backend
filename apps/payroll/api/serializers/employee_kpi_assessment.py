from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import Employee
from apps.payroll.api.serializers.common_nested import (
    DepartmentNestedSerializer,
    EmployeeWithDetailsNestedSerializer,
    KPIAssessmentPeriodNestedSerializer,
)
from apps.payroll.models import EmployeeKPIAssessment, EmployeeKPIItem


class EmployeeKPIItemScoreSerializer(serializers.Serializer):
    """Serializer for updating KPI item scores in batch."""

    item_id = serializers.IntegerField(help_text="ID of the KPI item to update")
    score = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Score value (must not exceed component_total_score)",
    )

    def validate(self, data):
        """Validate that score doesn't exceed component_total_score."""
        item_id = data.get("item_id")
        score = data.get("score")

        # Get assessment from context
        assessment = self.context.get("assessment")
        if not assessment:
            return data

        # Check if item exists and belongs to this assessment
        try:
            item = assessment.items.get(id=item_id)
        except EmployeeKPIItem.DoesNotExist:
            raise serializers.ValidationError({"item_id": f"Item with ID {item_id} not found in this assessment"})

        # Validate score doesn't exceed component_total_score
        if score > item.component_total_score:
            raise serializers.ValidationError(
                {"score": f"Score {score} cannot exceed component total score {item.component_total_score}"}
            )

        return data


class EmployeeSelfAssessmentUpdateRequestSerializer(serializers.Serializer):
    """Request serializer for employee self-assessment batch update.

    Example request:
    {
        "plan_tasks": "Complete Q4 targets",
        "extra_tasks": "Handle urgent requests",
        "proposal": "Improve workflow automation",
        "items": [
            {"item_id": 1, "score": "65.00"},
            {"item_id": 2, "score": "28.50"},
            {"item_id": 3, "score": "90.00"}
        ]
    }

    The 'items' field is a list of objects where each object contains:
    - item_id: ID of the KPI item to update
    - score: Employee's score for that item
    """

    plan_tasks = serializers.CharField(required=False, allow_blank=True, help_text="Planned tasks for the period")
    extra_tasks = serializers.CharField(required=False, allow_blank=True, help_text="Extra tasks handled")
    proposal = serializers.CharField(required=False, allow_blank=True, help_text="Employee's proposals")
    items = serializers.ListField(
        child=EmployeeKPIItemScoreSerializer(),
        required=False,
        help_text="List of item updates with item_id and score",
    )

    def validate(self, data):
        """Validate assessment is not finalized and manager hasn't graded."""
        assessment = self.context.get("assessment")
        if not assessment:
            return data

        # Check if finalized
        if assessment.finalized:
            from django.utils.translation import gettext as _

            raise serializers.ValidationError(_("Cannot update finalized assessment"))

        # Check if manager has already graded
        if assessment.grade_manager is not None:
            from django.utils.translation import gettext as _

            raise serializers.ValidationError(_("Cannot update assessment that has been assessed by manager"))

        return data

    def update_items(self, assessment, validated_data):
        """Update item scores from validated data."""
        items_data = validated_data.get("items", [])

        for item_data in items_data:
            item_id = item_data["item_id"]
            score = item_data["score"]

            try:
                item = assessment.items.get(id=item_id)
                item.employee_score = score
                item.save()
            except EmployeeKPIItem.DoesNotExist:
                continue

        return assessment


class ManagerAssessmentUpdateRequestSerializer(serializers.Serializer):
    """Request serializer for manager assessment batch update.

    Example request:
    {
        "manager_assessment": "Good performance overall",
        "grade": "A",
        "items": [
            {"item_id": 1, "score": "65.00"},
            {"item_id": 2, "score": "28.50"},
            {"item_id": 3, "score": "90.00"}
        ]
    }

    The 'items' field is a list of objects where each object contains:
    - item_id: ID of the KPI item to update
    - score: Manager's score for that item
    """

    manager_assessment = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Manager's assessment comments and feedback",
    )
    grade = serializers.CharField(
        required=True,
        max_length=10,
        help_text="Manager's grade override for the assessment",
    )
    items = serializers.ListField(
        child=EmployeeKPIItemScoreSerializer(),
        required=False,
        help_text="List of item updates with item_id and score",
    )

    def validate(self, data):
        """Validate assessment is not finalized."""
        assessment = self.context.get("assessment")
        if not assessment:
            return data

        # Check if finalized
        if assessment.finalized:
            from django.utils.translation import gettext as _

            raise serializers.ValidationError(_("Cannot update finalized assessment"))

        return data

    def update_items(self, assessment, validated_data):
        """Update item scores from validated data."""
        items_data = validated_data.get("items", [])

        for item_data in items_data:
            item_id = item_data["item_id"]
            score = item_data["score"]

            try:
                item = assessment.items.get(id=item_id)
                item.manager_score = score
                item.save()
            except EmployeeKPIItem.DoesNotExist:
                continue

        return assessment


class BaseEmployeeKPIAssessmentSerializer(serializers.ModelSerializer):
    """Base serializer for EmployeeKPIAssessment with common fields and methods."""

    employee = EmployeeWithDetailsNestedSerializer(read_only=True)
    period = KPIAssessmentPeriodNestedSerializer(read_only=True)
    department_snapshot = DepartmentNestedSerializer(read_only=True)
    colored_status = serializers.ReadOnlyField()

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
    employee_id = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.all(),
        source="employee",
        write_only=True,
    )

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "employee_id",
            "department_snapshot",
            "status",
            "colored_status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
            "finalized",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "note",
            "items",
        ]
        read_only_fields = [
            "id",
            "department_snapshot",
            "status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "manager_assessment_date",
            "hrm_assessed",
            "hrm_assessment_date",
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

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "department_snapshot",
            "status",
            "colored_status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
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
            "department_snapshot",
            "status",
            "colored_status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
            "finalized",
            "items",
        ]
        read_only_fields = [
            "id",
            "period",
            "employee",
            "department_snapshot",
            "status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "manager_assessment",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
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
    - Update grade_manager_overridden field
    """

    items = EmployeeKPIItemSerializer(many=True, read_only=True)
    grade = serializers.CharField(
        source="grade_manager_overridden",
        required=False,
        allow_blank=True,
        max_length=10,
        help_text="Manager's grade override",
    )

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "id",
            "period",
            "employee",
            "department_snapshot",
            "status",
            "colored_status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "grade",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
            "finalized",
            "items",
        ]
        read_only_fields = [
            "id",
            "period",
            "employee",
            "department_snapshot",
            "status",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment_date",
            "grade_hrm",
            "hrm_assessed",
            "hrm_assessment_date",
            "finalized",
            "items",
        ]

    def validate(self, data):
        """Validate that assessment is not finalized."""
        if self.instance and self.instance.finalized:
            raise serializers.ValidationError("Cannot update finalized assessment")
        return data

    def update(self, instance, validated_data):
        """Handle grade mapping from request serializer."""
        request = self.context.get("request")
        if request and "grade" in request.data:
            validated_data["grade_manager_overridden"] = request.data["grade"]
        return super().update(instance, validated_data)


class EmployeeKPIAssessmentExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting EmployeeKPIAssessment data to Excel."""

    period__month = serializers.SerializerMethodField()
    employee__code = serializers.CharField(source="employee.code", read_only=True)
    employee__fullname = serializers.CharField(source="employee.fullname", read_only=True)
    employee__branch__name = serializers.CharField(source="employee.branch.name", read_only=True)
    employee__block__name = serializers.CharField(source="employee.block.name", read_only=True)
    employee__department__name = serializers.CharField(source="employee.department.name", read_only=True)
    employee__position__name = serializers.CharField(source="employee.position.name", read_only=True)

    class Meta:
        model = EmployeeKPIAssessment
        fields = [
            "period__month",
            "employee__code",
            "employee__fullname",
            "employee__branch__name",
            "employee__block__name",
            "employee__department__name",
            "employee__position__name",
            "total_possible_score",
            "total_employee_score",
            "total_manager_score",
            "grade_manager",
            "grade_manager_overridden",
            "grade_hrm",
            "plan_tasks",
            "extra_tasks",
            "proposal",
            "manager_assessment",
            "finalized",
        ]

    def get_period__month(self, obj):
        """Return period month in readable format."""
        if obj.period and obj.period.month:
            return obj.period.month.strftime("%m/%Y")
        return ""
