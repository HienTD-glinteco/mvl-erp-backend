from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.hrm.models import WorkSchedule


class Command(BaseCommand):
    help = "Import work schedule data for specified weekdays"

    def add_arguments(self, parser):
        parser.add_argument(
            "--weekdays",
            type=str,
            required=True,
            help="Comma-separated list of weekday numbers (2=Monday, 3=Tuesday, ..., 8=Sunday)",
        )
        parser.add_argument(
            "--morning",
            type=str,
            default="",
            help="Morning session time range in format 'HH:MM-HH:MM' (e.g., '08:00-12:00')",
        )
        parser.add_argument(
            "--noon",
            type=str,
            default="",
            help="Noon session time range in format 'HH:MM-HH:MM' (e.g., '12:00-13:30')",
        )
        parser.add_argument(
            "--afternoon",
            type=str,
            default="",
            help="Afternoon session time range in format 'HH:MM-HH:MM' (e.g., '13:30-17:30')",
        )
        parser.add_argument(
            "--allowed-late",
            type=int,
            default=None,
            help="Allowed late minutes",
        )
        parser.add_argument(
            "--note",
            type=str,
            default="",
            help="Note for the work schedule",
        )

    def handle(self, *args, **options):
        weekdays_str = options["weekdays"]
        morning = options["morning"]
        noon = options["noon"]
        afternoon = options["afternoon"]
        allowed_late = options["allowed_late"]
        note = options["note"]

        # Parse weekdays
        try:
            weekday_numbers = [int(w.strip()) for w in weekdays_str.split(",")]
        except ValueError:
            raise CommandError("Invalid weekdays format. Must be comma-separated numbers (2-8).")

        # Validate weekday numbers
        for num in weekday_numbers:
            if num not in range(2, 9):  # 2-8 inclusive
                raise CommandError("Invalid weekday number: {}. Must be between 2 and 8.".format(num))

        # Parse time ranges
        morning_start, morning_end = self._parse_time_range(morning, "morning")
        noon_start, noon_end = self._parse_time_range(noon, "noon")
        afternoon_start, afternoon_end = self._parse_time_range(afternoon, "afternoon")

        # Import work schedules for each weekday
        created_count = 0
        updated_count = 0

        for weekday in weekday_numbers:
            work_schedule, created = WorkSchedule.objects.get_or_create(weekday=weekday)

            work_schedule.morning_start_time = morning_start
            work_schedule.morning_end_time = morning_end
            work_schedule.noon_start_time = noon_start
            work_schedule.noon_end_time = noon_end
            work_schedule.afternoon_start_time = afternoon_start
            work_schedule.afternoon_end_time = afternoon_end
            work_schedule.allowed_late_minutes = allowed_late
            work_schedule.note = note if note else None

            try:
                work_schedule.full_clean()
                work_schedule.save()

                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Created work schedule for %(weekday)s" % {"weekday": work_schedule.get_weekday_display()}
                        )
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            "Updated work schedule for %(weekday)s" % {"weekday": work_schedule.get_weekday_display()}
                        )
                    )
            except ValidationError as e:
                raise CommandError(
                    "Validation error for %(weekday)s: %(error)s"
                    % {"weekday": work_schedule.get_weekday_display(), "error": e}
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported work schedules. Created: %(created)s, Updated: %(updated)s"
                % {"created": created_count, "updated": updated_count}
            )
        )

    def _parse_time_range(self, time_range_str, session_name):
        """Parse time range string into start and end time strings.

        Args:
            time_range_str: String in format "HH:MM-HH:MM" or empty
            session_name: Name of the session (for error messages)

        Returns:
            Tuple of (start_time_str, end_time_str) or (None, None)

        Raises:
            CommandError: If time range format is invalid
        """
        if not time_range_str or time_range_str.strip() == "" or time_range_str.strip() == "-":
            return None, None

        parts = time_range_str.split("-")
        if len(parts) != 2:
            raise CommandError(
                "Invalid %(session)s time format: %(value)s. Expected 'HH:MM-HH:MM'."
                % {"session": session_name, "value": time_range_str}
            )

        start_str = parts[0].strip()
        end_str = parts[1].strip()

        # Both start and end must be provided
        if not start_str or not end_str:
            raise CommandError(
                "Both start and end times must be provided for %(session)s session: %(value)s"
                % {"session": session_name, "value": time_range_str}
            )

        return start_str, end_str
