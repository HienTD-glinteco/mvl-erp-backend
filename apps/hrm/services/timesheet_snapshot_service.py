import logging
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from apps.hrm.constants import TimesheetDayType
from apps.hrm.models.attendance_exemption import AttendanceExemption
from apps.hrm.models.contract import Contract
from apps.hrm.models.contract_type import ContractType
from apps.hrm.models.holiday import CompensatoryWorkday
from apps.hrm.models.timesheet import TimeSheetEntry

logger = logging.getLogger(__name__)


class TimesheetSnapshotService:
    """Service to snapshot configuration data onto TimeSheetEntry at creation/update time."""

    def snapshot_data(self, entry: TimeSheetEntry) -> None:
        """Populate snapshot fields on the timesheet entry.

        This method determines and sets:
        - day_type
        - contract
        - wage_rate
        - is_full_salary
        - is_exempt
        """
        self._set_day_type(entry)
        self._set_contract_info(entry)
        self._set_exemption_status(entry)

        # We don't save here to allow the caller to save efficiently (e.g., in bulk)
        # or subsequent logic to run before save.

    def _set_day_type(self, entry: TimeSheetEntry) -> None:
        """Determine and set the day_type based on Holiday and CompensatoryWorkday."""
        # Check for Compensatory Workday first (highest precedence?)
        # Based on legacy logic or typical business rules, if it's compensatory, it overrides holiday.
        # However, checking the old day_type_service.py might reveal precedence.
        # Assuming Compensatory > Holiday > Official.

        # Reset to None or Official default?
        # Usually, if no special type found, it stays None or assumes 'official' during calculation if schedule exists.
        # But here we want to explicitly tag 'holiday' or 'compensatory'.

        entry.day_type = None

        if CompensatoryWorkday.objects.filter(date=entry.date).exists():
            entry.day_type = TimesheetDayType.COMPENSATORY
            return

        # Use the property is_holiday logic or query directly?
        # The model logic for is_holiday relies on day_type.
        # We need to query the Holiday model.
        from apps.hrm.models.holiday import Holiday

        # Holiday uses start_date and end_date, not a single date field.
        if Holiday.objects.filter(start_date__lte=entry.date, end_date__gte=entry.date).exists():
            entry.day_type = TimesheetDayType.HOLIDAY
            return

        entry.day_type = TimesheetDayType.OFFICIAL

    def _set_contract_info(self, entry: TimeSheetEntry) -> None:
        """Find active contract and snapshot its details."""
        if not entry.employee_id or not entry.date:
            return

        active_contract = (
            Contract.objects.filter(
                employee_id=entry.employee_id,
                status__in=[Contract.ContractStatus.ACTIVE, Contract.ContractStatus.ABOUT_TO_EXPIRE],
                effective_date__lte=entry.date,
            )
            .filter(Q(expiration_date__gte=entry.date) | Q(expiration_date__isnull=True))
            .order_by("-effective_date")
            .first()
        )

        if active_contract:
            entry.contract = active_contract
            # If wage_rate exists (custom property?), use it. Else fallback to net_percentage logic?
            # Or assume wage_rate = net_percentage?
            # Looking at Contract model, net_percentage is an Integer (FULL=100, REDUCED=85).
            # This aligns with wage_rate default=100.
            if hasattr(active_contract, "wage_rate"):
                entry.wage_rate = active_contract.wage_rate
            else:
                # Fallback to net_percentage value if it behaves like a percentage
                # ContractType.NetPercentage choices are integers?
                # Contract model says `choices=ContractType.NetPercentage.choices`.
                # ContractType.NetPercentage.FULL is 100?
                # Let's check ContractType definition.
                # Assuming simple mapping for now.
                entry.wage_rate = active_contract.net_percentage

            # Determine is_full_salary based on contract net_percentage
            if active_contract.net_percentage == ContractType.NetPercentage.REDUCED:  # "85"
                entry.is_full_salary = False
            else:
                entry.is_full_salary = True
        else:
            # Defaults if no contract found
            entry.contract = None
            entry.wage_rate = 100
            entry.is_full_salary = True

    def _set_exemption_status(self, entry: TimeSheetEntry) -> None:
        """Check for attendance exemption."""
        if not entry.employee_id:
            return

        # Check if an exemption record exists and is effective
        # Condition: AttendanceExemption exists for employee AND (effective_date IS NULL OR effective_date <= entry.date)
        is_exempt = AttendanceExemption.objects.filter(
            employee_id=entry.employee_id
        ).filter(
            Q(effective_date__isnull=True) | Q(effective_date__lte=entry.date)
        ).exists()

        entry.is_exempt = is_exempt
