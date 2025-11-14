from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.devices.zk import ZKDeviceService
from apps.hrm.models import AttendanceDevice, Block
from libs import FieldFilteringSerializerMixin

from .organization import BlockSerializer


class AttendanceDeviceSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AttendanceDevice model.

    Provides serialization and validation for attendance device management.
    On create/update, validates device connection and updates device information.
    """

    # Expose nested block data for reads, and accept block id for writes.
    block = BlockSerializer(read_only=True)
    block_id = serializers.PrimaryKeyRelatedField(
        queryset=Block.objects.all(), source="block", write_only=True, required=False
    )

    class Meta:
        model = AttendanceDevice
        fields = [
            "id",
            "code",
            "name",
            "block_id",
            "block",
            "ip_address",
            "port",
            "password",
            "serial_number",
            "registration_number",
            "is_enabled",
            "is_connected",
            "realtime_enabled",
            "realtime_disabled_at",
            "polling_synced_at",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "serial_number",
            "is_connected",
            "realtime_enabled",
            "realtime_disabled_at",
            "polling_synced_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "password": {"required": True},
        }

    def validate(self, attrs):
        """Validate device connection on create/update.

        Tests connection to the device and retrieves serial and registration numbers.
        Updates the is_connected status and device information.
        """
        # Only test connection if network details are being set/changed
        ip_address = attrs.get("ip_address")
        port = attrs.get("port")
        password = attrs.get("password")
        is_enabled = attrs.get("is_enabled")

        self.ensure_unique_device(ip_address, port)

        # Get existing values if updating
        if self.instance:
            ip_address = ip_address or self.instance.ip_address
            port = port or self.instance.port
            password = password or self.instance.password

        if is_enabled:
            self.fetch_device_info(ip_address, port, password, attrs)
        else:
            attrs["is_connected"] = False

        return attrs

    def ensure_unique_device(self, ip_address: str | None = None, port: str | None = None):
        if not ip_address or not port:
            return

        qs = AttendanceDevice.objects.filter(ip_address=ip_address, port=port)
        if self.instance and self.instance.id:
            qs = qs.exclude(id=self.instance.id)

        if qs.exists():
            raise serializers.ValidationError(
                _("A device with IP {ip} and port {port} already exists.".format(ip=ip_address, port=port))
            )

    def fetch_device_info(self, ip_address, port, password, attrs: dict):
        # Test connection and get device info
        service = ZKDeviceService(
            ip_address=ip_address,
            port=port,
            password=password,
        )
        is_connected, __ = service.test_connection()

        if not is_connected:
            attrs["is_connected"] = False
        else:
            # If connection successful, get device details
            try:
                with service:
                    if not service._zk_connection:
                        raise Exception("No zk connection set")

                    # Get serial number and registration number from device
                    serial = service._zk_connection.get_serialnumber()
                    if serial:
                        attrs["serial_number"] = serial

                    # Get device name/registration as registration_number
                    device_name = service._zk_connection.get_device_name()
                    if device_name:
                        attrs["registration_number"] = device_name

                    # Mark as connected
                    attrs["is_connected"] = True
            except Exception:
                attrs["is_connected"] = False
