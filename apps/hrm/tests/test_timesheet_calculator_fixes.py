import pytest
from datetime import datetime, time, date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from django.utils import timezone
from apps.hrm.services.timesheet_calculator import TimesheetCalculator
from apps.hrm.constants import TimesheetStatus, TimesheetReason, TimesheetDayType
from apps.hrm.models.holiday import CompensatoryWorkday
from apps.hrm.models.work_schedule import WorkSchedule

@pytest.mark.django_db
class TestTimesheetCalculatorRepro:

    def setup_method(self):
        self.mock_entry = MagicMock()
        self.mock_entry.pk = 1
        self.mock_entry.employee_id = 1
        # Default mock values
        self.mock_entry.morning_hours = Decimal("0.00")
        self.mock_entry.afternoon_hours = Decimal("0.00")
        self.mock_entry.overtime_hours = Decimal("0.00")
        self.mock_entry.working_days = Decimal("0.00")
        self.mock_entry.count_for_payroll = True

    def test_stuck_in_absent_bug(self):
        """
        Reproduce Issue 1: If status is already ABSENT, calculator aborts and doesn't update to ON_TIME.
        """
        self.mock_entry.date = date(2023, 10, 23) # A Monday
        self.mock_entry.start_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(8, 0, 0)))
        self.mock_entry.end_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(17, 30, 0)))
        self.mock_entry.status = TimesheetStatus.ABSENT
        self.mock_entry.absent_reason = None

        with patch('apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday') as mock_get_schedule:
            mock_schedule = MagicMock()
            mock_schedule.morning_start_time = time(8, 0)
            mock_schedule.morning_end_time = time(12, 0)
            mock_schedule.afternoon_start_time = time(13, 30)
            mock_schedule.afternoon_end_time = time(17, 30)
            mock_schedule.allowed_late_minutes = 5
            mock_get_schedule.return_value = mock_schedule

            with patch('apps.hrm.models.holiday.Holiday.objects.filter') as mock_holiday, \
                 patch('apps.hrm.models.holiday.CompensatoryWorkday.objects.filter') as mock_comp, \
                 patch('apps.hrm.models.proposal.Proposal.objects.filter') as mock_proposal:

                mock_holiday.return_value.exists.return_value = False
                mock_comp.return_value.first.return_value = None

                mock_qs = MagicMock()
                mock_proposal.return_value = mock_qs
                mock_qs.filter.return_value = mock_qs
                mock_qs.__iter__.return_value = []

                calculator = TimesheetCalculator(self.mock_entry)
                calculator.compute_status()

                # Should update status to ON_TIME
                assert self.mock_entry.status == TimesheetStatus.ON_TIME, f"Status stuck in {self.mock_entry.status}"

    def test_compensatory_logic_error(self):
        """
        Reproduce Issue 2: Compensatory Afternoon shift grabs Morning start from fallback schedule.
        """
        self.mock_entry.date = date(2023, 10, 22) # A Sunday
        self.mock_entry.start_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(13, 30, 0)))
        self.mock_entry.end_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(17, 30, 0)))
        self.mock_entry.status = None

        mock_comp_day = MagicMock()
        mock_comp_day.session = CompensatoryWorkday.Session.AFTERNOON

        # Fallback schedule has Morning 8:00 and Afternoon 13:30
        mock_schedule = MagicMock()
        mock_schedule.morning_start_time = time(8, 0)
        mock_schedule.afternoon_start_time = time(13, 30)
        mock_schedule.allowed_late_minutes = 5

        with patch('apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday') as mock_get_schedule:
            def side_effect(weekday):
                if weekday == 8:
                    return None
                return mock_schedule

            mock_get_schedule.side_effect = side_effect

            with patch('apps.hrm.models.holiday.Holiday.objects.filter') as mock_holiday, \
                 patch('apps.hrm.models.holiday.CompensatoryWorkday.objects.filter') as mock_comp_query, \
                 patch('apps.hrm.models.proposal.Proposal.objects.filter') as mock_proposal:

                mock_holiday.return_value.exists.return_value = False
                mock_comp_query.return_value.first.return_value = mock_comp_day

                mock_qs = MagicMock()
                mock_proposal.return_value = mock_qs
                mock_qs.filter.return_value = mock_qs
                mock_qs.__iter__.return_value = []

                calculator = TimesheetCalculator(self.mock_entry)
                calculator.compute_status()

                # With fix, it should pick 13:30 (Afternoon) from fallback -> ON_TIME
                assert self.mock_entry.status == TimesheetStatus.ON_TIME, f"Status is {self.mock_entry.status} (likely picked Morning start time 8:00)"

    def test_timezone_crash_check(self):
        """
        Reproduce Issue 3: Verify strict timezone handling.
        """
        self.mock_entry.date = date(2023, 10, 23)
        self.mock_entry.start_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(8, 0)))
        self.mock_entry.end_time = timezone.make_aware(datetime.combine(self.mock_entry.date, time(17, 0)))

        mock_schedule = MagicMock()
        mock_schedule.morning_start_time = time(8, 0)
        mock_schedule.morning_end_time = time(12, 0)
        mock_schedule.afternoon_start_time = time(13, 0)
        mock_schedule.afternoon_end_time = time(17, 0)
        mock_schedule.allowed_late_minutes = 5 # Fix for TypeError

        with patch('apps.hrm.services.timesheet_calculator.get_work_schedule_by_weekday') as mock_get_schedule:
            mock_get_schedule.return_value = mock_schedule

            with patch('apps.hrm.models.holiday.Holiday.objects.filter') as mock_holiday, \
                 patch('apps.hrm.models.holiday.CompensatoryWorkday.objects.filter') as mock_comp, \
                 patch('apps.hrm.models.proposal.Proposal.objects.filter') as mock_proposal:

                mock_holiday.return_value.exists.return_value = False
                mock_comp.return_value.first.return_value = None

                mock_qs = MagicMock()
                mock_proposal.return_value = mock_qs
                mock_qs.filter.return_value = mock_qs
                mock_qs.__iter__.return_value = []

                calculator = TimesheetCalculator(self.mock_entry)
                # Just verify no crash
                calculator.compute_status()
                assert True
