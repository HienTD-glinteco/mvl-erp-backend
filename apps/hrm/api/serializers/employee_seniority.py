from datetime import date

from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
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
    - Display format: total days as integer, text as human-readable string
    """

    seniority = serializers.SerializerMethodField(
        help_text="Total seniority in days (integer)"
    )
    seniority_text = serializers.SerializerMethodField(
        help_text="Human-readable seniority text (e.g., '5 year(s) 3 month(s), 15 day(s)')"
    )
    work_history = serializers.SerializerMethodField(
        help_text="List of work history periods included in seniority calculation"
    )

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
            "seniority_text",
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
        sorted_histories = sorted(work_histories, key=lambda x: x.from_date if x.from_date else date.min)

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

    @extend_schema_field(serializers.IntegerField)
    def get_seniority(self, obj):
        """Calculate employee seniority according to QTNV 5.5.7.

        Business Logic:
        1. If employee has retain_seniority=False event:
           Calculate from the most recent such event onwards
        2. Otherwise:
           Calculate from all employment periods

        Returns:
            int: Total seniority in days
        """
        work_histories = getattr(obj, "cached_work_histories", [])

        if not work_histories:
            # Fallback: calculate from employee start_date
            if hasattr(obj, "start_date") and obj.start_date:
                return (date.today() - obj.start_date).days
            return 0

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

        return total_days

    @extend_schema_field(serializers.CharField)
    def get_seniority_text(self, obj):
        """Get human-readable seniority text.

        Returns:
            str: Formatted string like "5 year(s) 3 month(s), 15 day(s)"
        """
        total_days = self.get_seniority(obj)
        
        if total_days <= 0:
            return _("0 year(s) 0 month(s), 0 day(s)")

        # Calculate years, months, days
        years, months, days = self._days_to_ymd_tuple(total_days)

        return _("{year} year(s) {month} month(s), {day} day(s)").format(
            year=years, month=months, day=days
        )

    @extend_schema_field(EmployeeWorkHistorySerializer(many=True))
    def get_work_history(self, obj):
        """Get work history periods that are included in seniority calculation.

        IMPORTANT: Returns the SAME periods used in seniority calculation
        to maintain consistency between displayed history and calculated seniority.

        Business Logic (BR-4):
        - If employee has retain_seniority=False event:
          Show only periods from the most recent such event onwards
        - Otherwise:
          Show all periods
        - If no work history exists for current status, add a synthetic entry
          from start_date to now
        - Display in reverse chronological order (most recent first)

        Returns:
            list: Serialized work history in reverse chronological order
        """
        work_histories = getattr(obj, "cached_work_histories", [])

        # Get periods to display (SAME as calculation scope)
        periods_to_display, _ = self._get_calculation_scope(work_histories)

        # Check if we need to add current employment period
        # If no work history exists OR if latest work history doesn't represent current status
        needs_current_period = False
        
        if not periods_to_display:
            # No work history at all - need to add current period
            needs_current_period = True
        else:
            # Check if the most recent period (by from_date) covers current time
            latest_period = max(periods_to_display, key=lambda x: x.from_date if x.from_date else date.min)
            # If latest period has a to_date (meaning it ended), we need current period
            if latest_period.to_date is not None:
                needs_current_period = True

        # Serialize existing periods
        serialized_histories = []
        
        if needs_current_period and hasattr(obj, "start_date") and obj.start_date:
            # Add synthetic current employment period
            # We'll create a dict that matches the serializer structure
            current_period = {
                "id": None,
                "date": obj.start_date,
                "name": "Change Status",
                "name_display": "Change Status",
                "detail": _("Current employment period"),
                "employee": {
                    "id": obj.id,
                    "code": obj.code,
                    "fullname": obj.fullname,
                },
                "branch": {
                    "id": obj.branch.id,
                    "name": obj.branch.name,
                    "code": obj.branch.code,
                } if obj.branch else None,
                "block": {
                    "id": obj.block.id,
                    "name": obj.block.name,
                    "code": obj.block.code,
                } if obj.block else None,
                "department": {
                    "id": obj.department.id,
                    "name": obj.department.name,
                    "code": obj.department.code,
                } if obj.department else None,
                "position": {
                    "id": obj.position.id,
                    "name": obj.position.name,
                } if obj.position else None,
                "from_date": obj.start_date,
                "to_date": None,
                "retain_seniority": True,
                "created_at": None,
                "updated_at": None,
            }
            serialized_histories.append(current_period)

        # Add existing periods
        if periods_to_display:
            # Return in reverse chronological order (most recent first)
            periods_to_display_reversed = list(reversed(periods_to_display))
            existing_serialized = EmployeeWorkHistorySerializer(
                periods_to_display_reversed, many=True
            ).data
            serialized_histories.extend(existing_serialized)

        return serialized_histories

    def _days_to_ymd_tuple(self, total_days):
        """Convert total days to (years, months, days) tuple.

        Args:
            total_days (int): Total number of days

        Returns:
            tuple: (years, months, days)
        """
        if total_days <= 0:
            return (0, 0, 0)

        # Calculate years (365 days per year)
        years = total_days // 365
        remaining_days = total_days % 365

        # Calculate months (30 days per month - approximation)
        months = remaining_days // 30
        days = remaining_days % 30

        return (years, months, days)
