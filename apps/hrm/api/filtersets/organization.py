import django_filters

from apps.hrm.models import Block, Branch, Department, Position


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
    is_active = django_filters.BooleanFilter()

    class Meta:
        model = Position
        fields = ["name", "code", "is_active"]



