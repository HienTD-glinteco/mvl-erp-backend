from datetime import time

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.hrm.models import WorkSchedule


class WorkScheduleModelTest(TestCase):
    """Test cases for WorkSchedule model"""

    def test_create_work_schedule_with_all_fields(self):
        """Test creating a work schedule with all fields"""
        work_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
            allowed_late_minutes=5,
            note="Standard work schedule",
        )

        self.assertEqual(work_schedule.weekday, WorkSchedule.Weekday.MONDAY)
        self.assertEqual(work_schedule.morning_start_time, time(8, 0))
        self.assertEqual(work_schedule.morning_end_time, time(12, 0))
        self.assertEqual(work_schedule.noon_start_time, time(12, 0))
        self.assertEqual(work_schedule.noon_end_time, time(13, 30))
        self.assertEqual(work_schedule.afternoon_start_time, time(13, 30))
        self.assertEqual(work_schedule.afternoon_end_time, time(17, 30))
        self.assertEqual(work_schedule.allowed_late_minutes, 5)
        self.assertEqual(work_schedule.note, "Standard work schedule")
        # Check string representation exists (locale-dependent)
        self.assertTrue(len(str(work_schedule)) > 0)
        # Check properties
        self.assertEqual(work_schedule.morning_time, "08:00 - 12:00")
        self.assertEqual(work_schedule.noon_time, "12:00 - 13:30")
        self.assertEqual(work_schedule.afternoon_time, "13:30 - 17:30")

    def test_create_weekend_schedule_with_null_times(self):
        """Test creating a weekend schedule with null time fields"""
        work_schedule = WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.SATURDAY,
            morning_start_time=None,
            morning_end_time=None,
            noon_start_time=None,
            noon_end_time=None,
            afternoon_start_time=None,
            afternoon_end_time=None,
            allowed_late_minutes=None,
            note="Weekend - no work",
        )

        self.assertEqual(work_schedule.weekday, WorkSchedule.Weekday.SATURDAY)
        self.assertIsNone(work_schedule.morning_start_time)
        self.assertIsNone(work_schedule.morning_end_time)
        self.assertIsNone(work_schedule.noon_start_time)
        self.assertIsNone(work_schedule.noon_end_time)
        self.assertIsNone(work_schedule.afternoon_start_time)
        self.assertIsNone(work_schedule.afternoon_end_time)
        # Check properties return None when times are null
        self.assertIsNone(work_schedule.morning_time)
        self.assertIsNone(work_schedule.noon_time)
        self.assertIsNone(work_schedule.afternoon_time)

    def test_weekday_unique_constraint(self):
        """Test weekday uniqueness constraint"""
        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )

        # Try to create another schedule for the same weekday
        with self.assertRaises(Exception):  # IntegrityError
            WorkSchedule.objects.create(
                weekday=WorkSchedule.Weekday.MONDAY,
                morning_start_time=time(9, 0),
                morning_end_time=time(13, 0),
                noon_start_time=time(13, 0),
                noon_end_time=time(14, 0),
                afternoon_start_time=time(14, 0),
                afternoon_end_time=time(18, 0),
            )

    def test_clean_invalid_weekday(self):
        """Test validation of invalid weekday"""
        work_schedule = WorkSchedule(weekday=999)

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        self.assertIn("weekday", context.exception.message_dict)

    def test_clean_weekday_monday_requires_all_times(self):
        """Test that Monday requires all working time fields"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            # Missing noon and afternoon times
        )

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        self.assertIn("weekday", context.exception.message_dict)
        error_message = str(context.exception.message_dict["weekday"][0])
        self.assertIn("all working time fields must be provided", error_message)

    def test_clean_weekday_friday_requires_all_times(self):
        """Test that Friday requires all working time fields"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.FRIDAY,
            morning_start_time=time(8, 0),
            # Missing other times
        )

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        self.assertIn("weekday", context.exception.message_dict)

    def test_clean_weekend_allows_null_times(self):
        """Test that weekend schedules can have null times"""
        work_schedule = WorkSchedule(weekday=WorkSchedule.Weekday.SATURDAY)

        # Should not raise validation error
        work_schedule.full_clean()
        work_schedule.save()

        self.assertIsNone(work_schedule.morning_start_time)

    def test_clean_time_sequence_valid(self):
        """Test valid time sequence (non-decreasing)"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),  # Same as morning_end_time (valid)
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),  # Same as noon_end_time (valid)
            afternoon_end_time=time(17, 30),
        )

        # Should not raise validation error
        work_schedule.full_clean()
        work_schedule.save()

        self.assertEqual(work_schedule.weekday, WorkSchedule.Weekday.MONDAY)

    def test_clean_time_sequence_invalid_morning_to_noon(self):
        """Test invalid time sequence from morning to noon"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(13, 0),  # Later than noon_start_time
            noon_start_time=time(12, 0),  # Earlier than morning_end_time (invalid)
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        # Should have error on noon_start_time field
        self.assertIn("noon_start_time", context.exception.message_dict)

    def test_clean_time_sequence_invalid_noon_to_afternoon(self):
        """Test invalid time sequence from noon to afternoon"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.TUESDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(15, 0),  # Later than afternoon_start_time
            afternoon_start_time=time(13, 30),  # Earlier than noon_end_time (invalid)
            afternoon_end_time=time(17, 30),
        )

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        # Should have error on afternoon_start_time field
        self.assertIn("afternoon_start_time", context.exception.message_dict)

    def test_clean_time_sequence_invalid_within_session(self):
        """Test invalid time sequence within the same session"""
        work_schedule = WorkSchedule(
            weekday=WorkSchedule.Weekday.WEDNESDAY,
            morning_start_time=time(12, 0),  # Later than morning_end_time
            morning_end_time=time(8, 0),  # Earlier than morning_start_time (invalid)
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )

        with self.assertRaises(ValidationError) as context:
            work_schedule.full_clean()

        # Should have error on morning_end_time field
        self.assertIn("morning_end_time", context.exception.message_dict)

    def test_ordering(self):
        """Test default ordering by weekday"""
        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.FRIDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )
        WorkSchedule.objects.create(
            weekday=WorkSchedule.Weekday.MONDAY,
            morning_start_time=time(8, 0),
            morning_end_time=time(12, 0),
            noon_start_time=time(12, 0),
            noon_end_time=time(13, 30),
            afternoon_start_time=time(13, 30),
            afternoon_end_time=time(17, 30),
        )

        schedules = list(WorkSchedule.objects.all())

        # Should be ordered by weekday (2=Monday comes before 6=Friday)
        self.assertEqual(schedules[0].weekday, WorkSchedule.Weekday.MONDAY)
        self.assertEqual(schedules[1].weekday, WorkSchedule.Weekday.FRIDAY)
