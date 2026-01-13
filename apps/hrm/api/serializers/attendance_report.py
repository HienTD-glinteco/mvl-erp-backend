from rest_framework import serializers

from apps.hrm.models import Block
from apps.realestate.api.serializers import ProjectSerializer
from libs.drf.serializers import BaseTypeNameSerializer


# Common
class AttendanceReportBaseParameterSerializer(serializers.Serializer):
    attendance_date = serializers.DateField(required=False)
    branch = serializers.IntegerField(required=False)
    block = serializers.IntegerField(required=False)
    department = serializers.IntegerField(required=False)

    def get_filters(self):
        validated_data = self.validated_data
        filters = {}
        if validated_data.get("attendance_date"):
            filters["report_date"] = validated_data.get("attendance_date")
        if validated_data.get("branch"):
            filters["branch_id"] = validated_data.get("branch")
        if validated_data.get("block"):
            filters["block_id"] = validated_data.get("block")
        if validated_data.get("department"):
            filters["department_id"] = validated_data.get("department")
        return filters


# Group by: By method report


class AttendanceMethodBreakdownReportSerializer(serializers.Serializer):
    device = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    wifi = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    geolocation = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    other = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)


class AttendanceMethodItemReportSerializer(serializers.Serializer):
    total_employee = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    not_attendance = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    has_attendance = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    method_breakdown = AttendanceMethodBreakdownReportSerializer()


class AttendanceMethodReportSerializer(serializers.Serializer):
    absolute = AttendanceMethodItemReportSerializer()
    percentage = AttendanceMethodItemReportSerializer()


class AttendanceMethodReportParameterSerializer(AttendanceReportBaseParameterSerializer):
    pass


####

# Group by: Project report


class AttendanceProjectReportItemSerializer(serializers.Serializer):
    project = ProjectSerializer()
    count = serializers.IntegerField(default=0)


class AttendanceProjectReportAggregrationSerializer(serializers.Serializer):
    projects = AttendanceProjectReportItemSerializer(many=True)
    total = serializers.IntegerField(default=0)


class AttendanceProjectReportParameterSerializer(AttendanceReportBaseParameterSerializer):
    block_type = serializers.ChoiceField(choices=Block.BlockType.choices, required=False)

    def get_filters(self):
        filters = super().get_filters()
        if self.validated_data.get("block_type"):
            filters["block__block_type"] = self.validated_data.get("block_type")
        return filters


####

# Group by: Project Organization report


class AttendanceProjectOrgReportDepartmentSerializer(BaseTypeNameSerializer):
    id = serializers.IntegerField()
    count = serializers.IntegerField()


class AttendanceProjectOrgReportBlockSerializer(BaseTypeNameSerializer):
    id = serializers.IntegerField()
    count = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportDepartmentSerializer(many=True)


class AttendanceProjectOrgReportBranchSerializer(BaseTypeNameSerializer):
    id = serializers.IntegerField()
    count = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportBlockSerializer(many=True)


class AttendanceProjectOrgReportAggregrationSerializer(serializers.Serializer):
    total = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportBranchSerializer(many=True)


class AttendanceProjectOrgReportParameterSerializer(AttendanceReportBaseParameterSerializer):
    project = serializers.IntegerField(required=False)

    def get_filters(self):
        filters = super().get_filters()
        if self.validated_data.get("project"):
            filters["project_id"] = self.validated_data.get("project")
        return filters
