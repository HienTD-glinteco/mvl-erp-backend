"""Tests for import_work_schedule management command."""

from datetime import time
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.hrm.models import WorkSchedule


class ImportWorkScheduleCommandTest(TestCase):
    """Test cases for import_work_schedule management command"""

    def setUp(self):
        """Clear work schedules before each test"""
        WorkSchedule.objects.all().delete()

    def test_import_single_weekday_with_all_sessions(self):
        """Test importing a single weekday with all time sessions"""
        out = StringIO()
        call_command(
            "import_work_schedule",
            "--weekdays",
            "2",
            "--morning",
            "08:00-12:00",
            "--noon",
            "12:00-13:30",
            "--afternoon",
            "13:30-17:30",
            "--allowed-late",
            5,
            "--note",
            "Standard work schedule",
            stdout=out,
        )

        self.assertEqual(WorkSchedule.objects.count(), 1)
        schedule = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.MONDAY)
        self.assertEqual(schedule.morning_start_time, time(8, 0))
        self.assertEqual(schedule.morning_end_time, time(12, 0))
        self.assertEqual(schedule.noon_start_time, time(12, 0))
        self.assertEqual(schedule.noon_end_time, time(13, 30))
        self.assertEqual(schedule.afternoon_start_time, time(13, 30))
        self.assertEqual(schedule.afternoon_end_time, time(17, 30))
        self.assertEqual(schedule.allowed_late_minutes, 5)
        self.assertEqual(schedule.note, "Standard work schedule")
        self.assertIn("Created work schedule for", out.getvalue())

    def test_import_multiple_weekdays(self):
        """Test importing multiple weekdays at once"""
        out = StringIO()
        call_command(
            "import_work_schedule",
            "--weekdays",
            "3,4,5",
            "--morning",
            "08:00-12:00",
            "--noon",
            "12:00-13:30",
            "--afternoon",
            "13:30-17:30",
            "--allowed-late",
            5,
            stdout=out,
        )

        self.assertEqual(WorkSchedule.objects.count(), 3)

        # Check each weekday
        for weekday_value, weekday_name in [
            (WorkSchedule.Weekday.TUESDAY, "tuesday"),
            (WorkSchedule.Weekday.WEDNESDAY, "wednesday"),
            (WorkSchedule.Weekday.THURSDAY, "thursday"),
        ]:
            schedule = WorkSchedule.objects.get(weekday=weekday_value)
            self.assertEqual(schedule.morning_start_time, time(8, 0))
            self.assertEqual(schedule.morning_end_time, time(12, 0))
            self.assertEqual(schedule.allowed_late_minutes, 5)
            self.assertIn("Created work schedule for", out.getvalue())

    def test_import_weekend_with_empty_times(self):
        """Test importing weekend with empty time sessions"""
        out = StringIO()
        call_command(
            "import_work_schedule",
            "--weekdays",
            "7,8",
            "--morning",
            "",
            "--noon",
            "",
            "--afternoon",
            "",
            "--note",
            "Weekend - no work",
            stdout=out,
        )

        self.assertEqual(WorkSchedule.objects.count(), 2)

        # Check saturday
        saturday = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.SATURDAY)
        self.assertIsNone(saturday.morning_start_time)
        self.assertIsNone(saturday.morning_end_time)
        self.assertIsNone(saturday.noon_start_time)
        self.assertIsNone(saturday.noon_end_time)
        self.assertIsNone(saturday.afternoon_start_time)
        self.assertIsNone(saturday.afternoon_end_time)
        self.assertEqual(saturday.note, "Weekend - no work")

    def test_import_with_dash_only_means_null(self):
        """Test that '-' alone means null times"""
        out = StringIO()
        call_command(
            "import_work_schedule",
            "--weekdays",
            "8",
            "--morning",
            "-",
            "--noon",
            "-",
            "--afternoon",
            "-",
            stdout=out,
        )

        self.assertEqual(WorkSchedule.objects.count(), 1)
        sunday = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.SUNDAY)
        self.assertIsNone(sunday.morning_start_time)
        self.assertIsNone(sunday.afternoon_end_time)

    def test_update_existing_schedule(self):
        """Test updating an existing work schedule"""
        # Create initial schedule
        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(9, 0),
            morning_end_time=time(13, 0),
            noon_start_time=time(13, 0),
            noon_end_time=time(14, 0),
            afternoon_start_time=time(14, 0),
            afternoon_end_time=time(18, 0),
            allowed_late_minutes=10,
            note="Old schedule",
        )

        out = StringIO()
        call_command(
            "import_work_schedule",
            "--weekdays",
            "2",
            "--morning",
            "08:00-12:00",
            "--noon",
            "12:00-13:30",
            "--afternoon",
            "13:30-17:30",
            "--allowed-late",
            5,
            "--note",
            "Updated schedule",
            stdout=out,
        )

        # Should still have only 1 schedule (updated, not created new)
        self.assertEqual(WorkSchedule.objects.count(), 1)
        schedule = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.MONDAY)
        self.assertEqual(schedule.morning_start_time, time(8, 0))
        self.assertEqual(schedule.allowed_late_minutes, 5)
        self.assertEqual(schedule.note, "Updated schedule")
        self.assertIn("Updated work schedule for", out.getvalue())

    def test_invalid_weekday_number(self):
        """Test error when invalid weekday number is provided"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "9",
                "--morning",
                "08:00-12:00",
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

        self.assertIn("Invalid weekday number: 9", str(context.exception))

    def test_invalid_weekday_format(self):
        """Test error when weekday format is invalid"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "abc",
                "--morning",
                "08:00-12:00",
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

        self.assertIn("Invalid weekdays format", str(context.exception))

    def test_invalid_time_format(self):
        """Test error when time format is invalid"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "2",
                "--morning",
                "08:00:12:00",  # Invalid format
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

        self.assertIn("Invalid morning time format", str(context.exception))

    def test_missing_start_time(self):
        """Test error when only end time is provided"""
        # Note: When argparse catches invalid input, it raises SystemExit instead of CommandError
        with self.assertRaises((CommandError, SystemExit)):
            call_command(
                "import_work_schedule",
                "--weekdays",
                "2",
                "--morning",
                "-12:00",  # Missing start time (argparse will catch this)
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

    def test_missing_end_time(self):
        """Test error when only start time is provided"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "2",
                "--morning",
                "08:00-",  # Missing end time
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

        self.assertIn("Both start and end times must be provided", str(context.exception))

    def test_validation_error_for_weekday_missing_times(self):
        """Test validation error when weekday schedule is missing required times"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "2",  # Monday requires all times
                "--morning",
                "08:00-12:00",
                # Missing noon and afternoon
            )

        self.assertIn("Validation error", str(context.exception))

    def test_validation_error_for_invalid_time_sequence(self):
        """Test validation error when times are not in sequence"""
        with self.assertRaises(CommandError) as context:
            call_command(
                "import_work_schedule",
                "--weekdays",
                "2",
                "--morning",
                "08:00-15:00",  # Ends after noon starts
                "--noon",
                "12:00-13:30",
                "--afternoon",
                "13:30-17:30",
            )

        self.assertIn("Validation error", str(context.exception))

    def test_without_note_sets_null(self):
        """Test that omitting note sets it to null"""
        call_command(
            "import_work_schedule",
            "--weekdays",
            "7",
            "--morning",
            "",
            "--noon",
            "",
            "--afternoon",
            "",
        )

        saturday = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.SATURDAY)
        self.assertIsNone(saturday.note)

    def test_without_allowed_late_sets_null(self):
        """Test that omitting allowed-late sets it to null"""
        call_command(
            "import_work_schedule",
            "--weekdays",
            "7",
            "--morning",
            "",
            "--noon",
            "",
            "--afternoon",
            "",
        )

        saturday = WorkSchedule.objects.get(weekday=WorkSchedule.Weekday.SATURDAY)
        self.assertIsNone(saturday.allowed_late_minutes)
