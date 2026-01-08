from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import BlockNestedSerializer, BranchNestedSerializer
from apps.hrm.models import AttendanceWifiDevice
from libs.drf.serializers.mixins import FieldFilteringSerializerMixin


class AttendanceWifiDeviceSerializer(serializers.ModelSerializer):
    """Serializer for AttendanceWifiDevice model"""

    # Nested serializers for read operations
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)

    # Write-only fields for create/update operations
    branch_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    block_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = AttendanceWifiDevice
        fields = [
            "id",
            "code",
            "name",
            "branch",
            "branch_id",
            "block",
            "block_id",
            "bssid",
            "state",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "created_at",
            "updated_at",
        ]

    def validate_bssid(self, value):
        """Validate BSSID format (MAC address format: XX:XX:XX:XX:XX:XX)"""
        import re

        # Check if BSSID matches MAC address format
        mac_pattern = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
        if not mac_pattern.match(value):
            raise serializers.ValidationError("BSSID must be in MAC address format (XX:XX:XX:XX:XX:XX)")

        # Normalize to uppercase with colons
        normalized_bssid = value.upper().replace("-", ":")
        return normalized_bssid


class AttendanceWifiDeviceExportSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for exporting AttendanceWifiDevice data to Excel with template"""

    branch_name = serializers.CharField(source="branch.name", default="", label=_("Branch"))
    block_name = serializers.CharField(source="block.name", default="", label=_("Block"))
    state = serializers.CharField(source="get_state_display", label=_("State"))

    default_fields = [
        "code",
        "name",
        "branch_name",
        "block_name",
        "bssid",
        "state",
        "notes",
    ]

    class Meta:
        model = AttendanceWifiDevice
        fields = [
            "code",
            "name",
            "branch_name",
            "block_name",
            "bssid",
            "state",
            "notes",
        ]
