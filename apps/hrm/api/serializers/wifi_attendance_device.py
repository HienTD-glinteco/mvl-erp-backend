from rest_framework import serializers

from apps.hrm.api.serializers.common_nested import BlockNestedSerializer, BranchNestedSerializer
from apps.hrm.models import WifiAttendanceDevice


class WifiAttendanceDeviceSerializer(serializers.ModelSerializer):
    """Serializer for WifiAttendanceDevice model"""

    # Nested serializers for read operations
    branch = BranchNestedSerializer(read_only=True)
    block = BlockNestedSerializer(read_only=True)

    # Write-only fields for create/update operations
    branch_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    block_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = WifiAttendanceDevice
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


class WifiAttendanceDeviceExportSerializer(serializers.ModelSerializer):
    """Serializer for exporting WifiAttendanceDevice data to Excel"""

    branch__name = serializers.CharField(source="branch.name", default="")
    block__name = serializers.CharField(source="block.name", default="")

    class Meta:
        model = WifiAttendanceDevice
        fields = [
            "code",
            "name",
            "branch__name",
            "block__name",
            "bssid",
            "state",
            "notes",
            "created_at",
            "updated_at",
        ]
