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


####

# Group by: Project Organization report


class AttendanceProjectOrgReportDepartmentSerializer(BaseTypeNameSerializer):
    count = serializers.IntegerField()


class AttendanceProjectOrgReportBlockSerializer(BaseTypeNameSerializer):
    count = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportDepartmentSerializer(many=True)


class AttendanceProjectOrgReportBranchSerializer(BaseTypeNameSerializer):
    count = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportBlockSerializer(many=True)


class AttendanceProjectOrgReportAggregrationSerializer(serializers.Serializer):
    total = serializers.IntegerField(default=0)
    children = AttendanceProjectOrgReportBranchSerializer(many=True)


class AttendanceProjectOrgReportParameterSerializer(AttendanceReportBaseParameterSerializer):
    project = serializers.IntegerField(required=False)
