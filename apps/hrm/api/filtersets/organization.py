import django_filters

from apps.hrm.models import Block, Branch, Department, OrganizationChart, Position


class BranchFilterSet(django_filters.FilterSet):
    """FilterSet for Branch model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Branch
        fields = ["name", "code", "is_active"]


class BlockFilterSet(django_filters.FilterSet):
    """FilterSet for Block model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    block_type = django_filters.ChoiceFilter(choices=Block.BlockType.choices)
    branch = django_filters.ModelChoiceFilter(queryset=Branch.objects.all())
    branch_code = django_filters.CharFilter(field_name="branch__code", lookup_expr="icontains")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Block
        fields = ["name", "code", "block_type", "branch", "branch_code", "is_active"]


class DepartmentFilterSet(django_filters.FilterSet):
    """FilterSet for Department model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    block = django_filters.ModelChoiceFilter(queryset=Block.objects.all())
    block_code = django_filters.CharFilter(field_name="block__code", lookup_expr="icontains")
    block_type = django_filters.ChoiceFilter(field_name="block__block_type", choices=Block.BlockType.choices)
    branch = django_filters.ModelChoiceFilter(field_name="block__branch", queryset=Branch.objects.all())
    branch_code = django_filters.CharFilter(field_name="block__branch__code", lookup_expr="icontains")
    parent_department = django_filters.ModelChoiceFilter(queryset=Department.objects.all())
    has_parent = django_filters.BooleanFilter(field_name="parent_department", lookup_expr="isnull", exclude=True)
    function = django_filters.ChoiceFilter(choices=Department.DepartmentFunction.choices)
    is_main_department = django_filters.BooleanFilter()
    management_department = django_filters.ModelChoiceFilter(queryset=Department.objects.all())
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Department
        fields = [
            "name",
            "code",
            "block",
            "block_code",
            "block_type",
            "branch",
            "branch_code",
            "parent_department",
            "has_parent",
            "function",
            "is_main_department",
            "management_department",
            "is_active",
        ]


class PositionFilterSet(django_filters.FilterSet):
    """FilterSet for Position model"""

    name = django_filters.CharFilter(lookup_expr="icontains")
    code = django_filters.CharFilter(lookup_expr="icontains")
    level = django_filters.ChoiceFilter(choices=Position.PositionLevel.choices)
    level_gte = django_filters.NumberFilter(field_name="level", lookup_expr="gte")
    level_lte = django_filters.NumberFilter(field_name="level", lookup_expr="lte")
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Position
        fields = ["name", "code", "level", "level_gte", "level_lte", "is_active"]


class OrganizationChartFilterSet(django_filters.FilterSet):
    """FilterSet for OrganizationChart model"""

    employee = django_filters.UUIDFilter()
    employee_username = django_filters.CharFilter(field_name="employee__username", lookup_expr="icontains")
    position = django_filters.ModelChoiceFilter(queryset=Position.objects.all())
    position_level = django_filters.ChoiceFilter(field_name="position__level", choices=Position.PositionLevel.choices)
    department = django_filters.ModelChoiceFilter(queryset=Department.objects.all())
    department_code = django_filters.CharFilter(field_name="department__code", lookup_expr="icontains")
    block = django_filters.ModelChoiceFilter(field_name="department__block", queryset=Block.objects.all())
    block_code = django_filters.CharFilter(field_name="department__block__code", lookup_expr="icontains")
    block_type = django_filters.ChoiceFilter(
        field_name="department__block__block_type", choices=Block.BlockType.choices
    )
    branch = django_filters.ModelChoiceFilter(field_name="department__block__branch", queryset=Branch.objects.all())
    branch_code = django_filters.CharFilter(field_name="department__block__branch__code", lookup_expr="icontains")
    start_date = django_filters.DateFilter()
    start_date_gte = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_lte = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")
    end_date = django_filters.DateFilter()
    end_date_gte = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date_lte = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")
    is_current = django_filters.BooleanFilter(field_name="end_date", lookup_expr="isnull")
    is_primary = django_filters.BooleanFilter()
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = OrganizationChart
        fields = [
            "employee",
            "employee_username",
            "position",
            "position_level",
            "department",
            "department_code",
            "block",
            "block_code",
            "block_type",
            "branch",
            "branch_code",
            "start_date",
            "start_date_gte",
            "start_date_lte",
            "end_date",
            "end_date_gte",
            "end_date_lte",
            "is_current",
            "is_primary",
            "is_active",
        ]
