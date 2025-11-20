import calendar
from datetime import date
from decimal import Decimal
from typing import Any, Dict, cast

from django.db import models
from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from apps.hrm.constants import STANDARD_WORKING_HOURS_PER_DAY, TimesheetReason
from apps.hrm.models.timesheet import TimeSheetEntry
from libs.decimals import DECIMAL_ZERO, quantize_decimal
from libs.models.base_model_mixin import BaseReportModel
from libs.models.fields import SafeTextField

# Values returned by compute_aggregates: Decimal for numeric fields, int for ids,
# date for report_date and str for month_key.
AggregateValue = Decimal | int | date | str


class EmployeeMonthlyTimesheet(BaseReportModel):
    """Flat monthly timesheet summary for an employee.

    The model is intended to be refreshed from daily rows via
    `compute_aggregates` and `refresh_for_employee_month`.
    """

    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="monthly_timesheets",
        verbose_name=_("Employee"),
    )

    # Report date is the first day of the month for which this row summarizes data.
    report_date = models.DateField(verbose_name=_("Report date"))
    # Month key in YYYYMM format to ease reporting and indexing
    month_key = models.CharField(max_length=6, verbose_name=_("Month key"))

    # Working day counts (use Decimal to allow partial days)
    probation_working_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Probation working days")
    )
    official_working_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Official working days")
    )
    total_working_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Total working days")
    )

    # Hour aggregates
    official_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Official hours")
    )
    overtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        verbose_name=_("Overtime hours"),
        help_text=_("TODO: Check logic after SRS is updated"),
    )
    total_worked_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        verbose_name=_("Total worked hours"),
        help_text=_("Sum of official_hours and overtime_hours"),
    )

    # Leave counts (days) - use decimal to allow partial days
    paid_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Paid leave days")
    )
    unpaid_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Unpaid leave days")
    )
    maternity_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Maternity leave days")
    )
    public_holiday_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Public holiday days")
    )
    unexcused_absence_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Unexcused absence days")
    )

    # Leave balances
    carried_over_leave = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=DECIMAL_ZERO,
        verbose_name=_(
            "Carried over leave from last year. Only applied for January. After that, this field must be set to 0."
        ),
    )
    opening_balance_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Opening balance leave days")
    )
    consumed_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Consumed leave days")
    )
    remaining_leave_days = models.DecimalField(
        max_digits=8, decimal_places=2, default=DECIMAL_ZERO, verbose_name=_("Remaining leave days")
    )

    note = SafeTextField(blank=True, verbose_name=_("Note"))

    class Meta:
        db_table = "hrm_employee_monthly_timesheet"
        verbose_name = _("Employee monthly timesheet")
        verbose_name_plural = _("Employee monthly timesheets")
        constraints = [
            models.UniqueConstraint(fields=["employee", "month_key"], name="uniq_employee_month_key"),
        ]
        indexes = [
            models.Index(fields=["employee", "month_key"], name="idx_employee_month_key"),
            models.Index(fields=["report_date"], name="idx_monthly_report_date"),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"EmployeeMonthlyTimesheet {self.employee_id} {self.month_key}"

    @classmethod
    def compute_aggregates(
        cls, employee_id: int, year: int, month: int, fields: list[str] | None = None
    ) -> Dict[str, AggregateValue]:
        """Compute aggregates from TimeSheetEntry for given employee/month.

        Returns a dict with keys matching model fields (except PK) and raw
        Decimal/int values (not quantized strings).
        """

        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        qs = TimeSheetEntry.objects.filter(employee_id=employee_id, date__range=(first_day, last_day))

        aggregates_expr = {
            # Hour aggregates - calculate from base fields
            # Use temp keys to avoid conflict with field names
            "_official_hours": Coalesce(
                Sum(F("morning_hours") + F("afternoon_hours")), Value(DECIMAL_ZERO, output_field=DecimalField())
            ),
            "_overtime_hours": Coalesce(Sum(F("overtime_hours")), Value(DECIMAL_ZERO, output_field=DecimalField())),
            "_total_worked_hours": Coalesce(
                Sum(F("morning_hours") + F("afternoon_hours") + F("overtime_hours")),
                Value(DECIMAL_ZERO, output_field=DecimalField()),
            ),
            # Working days - calculate from hours divided by 8
            "_probation_working_days": Coalesce(
                Sum(F("morning_hours") + F("afternoon_hours"), filter=Q(is_full_salary=False))
                / Value(STANDARD_WORKING_HOURS_PER_DAY),
                Value(DECIMAL_ZERO, output_field=DecimalField()),
            ),
            "_official_working_days": Coalesce(
                Sum(F("morning_hours") + F("afternoon_hours"), filter=Q(is_full_salary=True))
                / Value(STANDARD_WORKING_HOURS_PER_DAY),
                Value(DECIMAL_ZERO, output_field=DecimalField()),
            ),
            "_total_working_days": Coalesce(
                Sum(F("morning_hours") + F("afternoon_hours")) / Value(STANDARD_WORKING_HOURS_PER_DAY),
                Value(DECIMAL_ZERO, output_field=DecimalField()),
            ),
            # Leaves day
            "paid_leave_days": Coalesce(
                Count("date", filter=Q(absent_reason=TimesheetReason.PAID_LEAVE), distinct=True), Value(0)
            ),
            "unpaid_leave_days": Coalesce(
                Count("date", filter=Q(absent_reason=TimesheetReason.UNPAID_LEAVE), distinct=True), Value(0)
            ),
            "public_holiday_days": Coalesce(
                Count("date", filter=Q(absent_reason=TimesheetReason.PUBLIC_HOLIDAY), distinct=True), Value(0)
            ),
            "maternity_leave_days": Coalesce(
                Count("date", filter=Q(absent_reason=TimesheetReason.MATERNITY_LEAVE), distinct=True), Value(0)
            ),
            "unexcused_absence_days": Coalesce(
                Count("date", filter=Q(absent_reason=TimesheetReason.UNEXCUSED_ABSENCE), distinct=True), Value(0)
            ),
        }

        if fields:
            # Map field names to temp keys for filtering
            field_mapping = {
                "official_hours": "_official_hours",
                "overtime_hours": "_overtime_hours",
                "total_worked_hours": "_total_worked_hours",
                "probation_working_days": "_probation_working_days",
                "official_working_days": "_official_working_days",
                "total_working_days": "_total_working_days",
            }
            temp_fields = [field_mapping.get(f, f) for f in fields]
            aggregates_expr = {field: expr for field, expr in aggregates_expr.items() if field in temp_fields}

        raw_aggs: dict[str, Any] = qs.aggregate(**aggregates_expr) if aggregates_expr else {}

        # Rename temp keys back to original field names
        aggregates: Dict[str, AggregateValue] = {}
        for field, value in raw_aggs.items():
            if field.startswith("_"):
                # Remove the underscore prefix
                clean_field = field[1:]
                aggregates[clean_field] = quantize_decimal(value)
            else:
                aggregates[field] = quantize_decimal(value)

        # report_date is the first day of the month; month_key is YYYYMM
        report_date = first_day
        month_key = f"{year:04d}{month:02d}"

        result = {"employee_id": employee_id, "report_date": report_date, "month_key": month_key, **aggregates}

        return result

    @classmethod
    def refresh_for_employee_month(
        cls, employee_id: int, year: int, month: int, fields: list[str] | None = None
    ) -> "EmployeeMonthlyTimesheet":
        """Create or update the monthly timesheet row for employee/year/month.

        Uses `compute_aggregates` to obtain the aggregate values and writes them
        into the `EmployeeMonthlyTimesheet` table inside a transaction.
        """
        aggregates = cls.compute_aggregates(employee_id, year, month, fields)

        report_date = aggregates["report_date"]

        obj, __ = cls.objects.get_or_create(employee_id=employee_id, report_date=report_date)

        if fields:
            aggregates = {field: value for field, value in aggregates.items() if field in fields}

        # Handle leave balance calculations
        if "paid_leave_days" in aggregates:
            consumed_leave_days: Decimal = quantize_decimal(cast(Decimal, aggregates["paid_leave_days"]))
            aggregates["consumed_leave_days"] = consumed_leave_days
            delta = quantize_decimal(obj.carried_over_leave + obj.opening_balance_leave_days - consumed_leave_days)
            aggregates["remaining_leave_days"] = max(delta, DECIMAL_ZERO)

        # Apply aggregates to object fields
        for field, value in aggregates.items():
            setattr(obj, field, value)

        obj.need_refresh = False

        obj.save()

        return obj
