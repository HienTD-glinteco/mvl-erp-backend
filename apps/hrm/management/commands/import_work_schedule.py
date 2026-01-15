import json

from django.core.management.base import BaseCommand, CommandError

from apps.hrm.models import WorkSchedule


class Command(BaseCommand):
    help = "Import work schedule data from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            type=str,
            help="Path to the JSON file containing work schedule data",
        )

    def handle(self, *args, **options):
        json_path = options["json_path"]

        # Read JSON file
        try:
            with open(json_path, encoding="utf-8") as f:
                schedules = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {json_path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON file: {e}")

        created_count = 0
        updated_count = 0

        for schedule_data in schedules:
            weekday = schedule_data.get("weekday")
            if weekday is None:
                self.stderr.write(self.style.WARNING(f"Skipping entry without weekday: {schedule_data}"))
                continue

            work_schedule, created = WorkSchedule.objects.update_or_create(
                weekday=weekday,
                defaults={
                    "morning_start_time": schedule_data.get("morning_start_time"),
                    "morning_end_time": schedule_data.get("morning_end_time"),
                    "noon_start_time": schedule_data.get("noon_start_time"),
                    "noon_end_time": schedule_data.get("noon_end_time"),
                    "afternoon_start_time": schedule_data.get("afternoon_start_time"),
                    "afternoon_end_time": schedule_data.get("afternoon_end_time"),
                    "allowed_late_minutes": schedule_data.get("allowed_late_minutes"),
                    "is_morning_required": schedule_data.get("is_morning_required", True),
                    "is_afternoon_required": schedule_data.get("is_afternoon_required", True),
                    "note": schedule_data.get("note"),
                },
            )

            weekday_name = schedule_data.get("weekday_name", work_schedule.get_weekday_display())
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created work schedule for {weekday_name}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"Updated work schedule for {weekday_name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully imported work schedules. Created: {created_count}, Updated: {updated_count}"
            )
        )
