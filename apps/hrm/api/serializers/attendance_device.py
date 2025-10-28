from django.utils.translation import gettext as _
from rest_framework import serializers

from apps.hrm.models import AttendanceDevice
from apps.hrm.services import AttendanceDeviceService
from libs import FieldFilteringSerializerMixin


class AttendanceDeviceSerializer(FieldFilteringSerializerMixin, serializers.ModelSerializer):
    """Serializer for AttendanceDevice model.

    Provides serialization and validation for attendance device management.
    On create/update, validates device connection and updates device information.
    """

    class Meta:
        model = AttendanceDevice
        fields = [
            "id",
            "name",
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "serial_number",
            "registration_number",
            "is_connected",
            "realtime_enabled",
            "realtime_disabled_at",
            "polling_synced_at",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
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

        # Get existing values if updating
        if self.instance:
            ip_address = ip_address or self.instance.ip_address
            port = port or self.instance.port
            password = password or self.instance.password

        # Create temporary device object for connection testing
        temp_device = AttendanceDevice(
            ip_address=ip_address,
            port=port,
            password=password,
        )

        # Test connection and get device info
        service = AttendanceDeviceService(temp_device)
        is_connected, message = service.test_connection()

        if not is_connected:
            # Device not ready, just set is_connected to False
            attrs["is_connected"] = False
        else:
            # If connection successful, get device details
            try:
                with service:
                    if service._zk_connection:
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
                # If we can't get details, just mark as connected since test passed
                attrs["is_connected"] = True

        return attrs
