from datetime import date

from dateutil.relativedelta import relativedelta
from rest_framework import serializers

from apps.hrm.models.employee import Employee

from .employee_work_history import EmployeeWorkHistorySerializer


class EmployeeSenioritySerializer(serializers.ModelSerializer):
    """Serializer for Employee Seniority Report.

    Includes calculated seniority field and work history periods
    that are included in the seniority calculation.

    Business Logic:
    - Seniority is calculated based on employment periods in work history
    - If employee has retain_seniority=False event, only count from most recent such event onwards
    - Otherwise, count all employment periods
    - Display format: "YEARS-MONTHS-DAYS" (e.g., "5-3-15")
    """

    seniority = serializers.SerializerMethodField()
    work_history = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = [
            "id",
            "code",
            "fullname",
            "branch",
            "block",
            "department",
            "seniority",
            "work_history",
        ]

    def _get_calculation_scope(self, work_histories):
        """Determine which work history periods to include in calculation.

        This method is used by BOTH:
        - get_seniority() for calculation
        - get_work_history() for display

        This ensures consistency between displayed history and calculated seniority.

        Args:
            work_histories (list): List of EmployeeWorkHistory objects

        Returns:
            tuple: (periods_to_include, sorted_all_histories)
        """
        if not work_histories:
            return [], []

        # Sort by from_date
        sorted_histories = sorted(
            work_histories, key=lambda x: x.from_date if x.from_date else date.min
        )

        # Find most recent non-continuous period
        last_non_retain_index = None
        for i, wh in enumerate(sorted_histories):
            if hasattr(wh, "retain_seniority") and wh.retain_seniority is False:
                last_non_retain_index = i

        # Determine scope
        if last_non_retain_index is not None:
            # Only include from most recent non-continuous period onwards
            periods = sorted_histories[last_non_retain_index:]
        else:
            # Include all periods
            periods = sorted_histories

        return periods, sorted_histories

    def get_seniority(self, obj):
        """Calculate employee seniority according to QTNV 5.5.7.

        Business Logic:
        1. If employee has retain_seniority=False event:
           Calculate from the most recent such event onwards
        2. Otherwise:
           Calculate from all employment periods

        Returns:
            str: Seniority in format "YEARS-MONTHS-DAYS" (e.g., "5-3-15")
        """
        work_histories = getattr(obj, "cached_work_histories", [])

        if not work_histories:
            # Fallback: calculate from employee start_date
            if hasattr(obj, "start_date") and obj.start_date:
                return self._calculate_period(obj.start_date, date.today())
            return "0-0-0"

        # Get periods to calculate (reuse helper method)
        periods_to_calculate, _ = self._get_calculation_scope(work_histories)

        # Calculate total days
        total_days = 0
        for period in periods_to_calculate:
            if not period.from_date:
                continue

            # Use to_date or current date as end date
            end_date = period.to_date if period.to_date else date.today()

            # Calculate days for this period
            period_days = (end_date - period.from_date).days
            total_days += period_days

        # Convert to Year-Month-Day format
        return self._format_days_to_ymd(total_days)

    def get_work_history(self, obj):
        """Get work history periods that are included in seniority calculation.

        IMPORTANT: Returns the SAME periods used in seniority calculation
        to maintain consistency between displayed history and calculated seniority.

        Business Logic (BR-4):
        - If employee has retain_seniority=False event:
          Show only periods from the most recent such event onwards
        - Otherwise:
          Show all periods
        - Display in reverse chronological order (most recent first)

        Returns:
            list: Serialized work history in reverse chronological order
        """
        work_histories = getattr(obj, "cached_work_histories", [])

        # Get periods to display (SAME as calculation scope)
        periods_to_display, _ = self._get_calculation_scope(work_histories)

        # Return in reverse chronological order (most recent first)
        periods_to_display_reversed = list(reversed(periods_to_display))

        return EmployeeWorkHistorySerializer(periods_to_display_reversed, many=True).data

    def _format_days_to_ymd(self, total_days):
        """Convert total days to Year-Month-Day format.

        Args:
            total_days (int): Total number of days

        Returns:
            str: Formatted string "YEARS-MONTHS-DAYS"
        """
        if total_days <= 0:
            return "0-0-0"

        # Calculate years (365 days per year)
        years = total_days // 365
        remaining_days = total_days % 365

        # Calculate months (30 days per month - approximation)
        months = remaining_days // 30
        days = remaining_days % 30

        return f"{years}-{months}-{days}"

    def _calculate_period(self, start_date, end_date):
        """Calculate period using relativedelta for higher precision.

        Args:
            start_date (date): Start date
            end_date (date): End date

        Returns:
            str: Formatted string "YEARS-MONTHS-DAYS"
        """
        delta = relativedelta(end_date, start_date)
        return f"{delta.years}-{delta.months}-{delta.days}"
