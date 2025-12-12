import json

from apps.hrm.models import AttendanceDevice

FIXTURE_PATH = "apps/hrm/fixtures/attendance_devices.json"


def run_import(fixture_path: str = FIXTURE_PATH):
    with open(fixture_path) as f:
        device_infos = json.load(f)

    devices = []
    for device_info in device_infos:
        AttendanceDevice.objects.create(**device_info)

    for device in devices:
        print(f"test device: {device.id} - {device.name}")
        try:
            device.check_and_update_connection()
        except Exception as ex:
            print(f"ex: {ex}")

        print("\n=====\n")
