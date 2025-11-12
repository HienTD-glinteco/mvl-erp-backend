from datetime import date

from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.hrm.models.employee import Employee
from apps.hrm.models.employee_work_history import EmployeeWorkHistory


class SimplifiedWorkHistorySerializer(serializers.ModelSerializer):
    """Simplified serializer for work history in seniority report.
    
    Only includes essential fields: name, date, detail, from_date, to_date.
    Ordered by creation time (ascending).
    """
    
    class Meta:
        model = EmployeeWorkHistory
        fields = ["name", "date", "detail", "from_date", "to_date"]
        read_only_fields = ["name", "date", "detail", "from_date", "to_date"]


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

    def _get_calculation_scope(self, work_histories, employee_start_date=None):
        """Determine which work history periods to include in calculation.

        Simplified logic focusing only on 2 event types:
        1. "Return to Work" events
        2. "Change Status" events with status=Resigned
        
        IMPORTANT: Always includes current employment period in the calculation
        
        Logic:
        I. If no "Return to Work" events exist:
           - Only include current employment period (from employee start_date to now)
           
        II. If at least one "Return to Work" with retain_seniority=False exists:
            - Find most recent retain_seniority=False "Return to Work"
            - Ignore all events before that cutoff
            - After cutoff: include "Change Status" (Resigned) events
            - Add current employment period (from employee start_date to now)
            
        III. If "Return to Work" events exist but none with retain_seniority=False:
             - Include all "Change Status" (Resigned) events
             - Add current employment period (from employee start_date to now)
        
        Finally, sort periods by start_date
        
        Args:
            work_histories (list): List of EmployeeWorkHistory objects
            employee_start_date: Employee's start_date for current period

        Returns:
            tuple: (periods_to_include, sorted_all_histories)
        """
        if not work_histories:
            return [], []

        # Sort by date (ascending for easier processing)
        sorted_histories = sorted(
            work_histories, 
            key=lambda x: x.date if x.date else date.min
        )

        periods = []
        
        # Find all "Return to Work" events
        return_to_work_events = [
            event for event in sorted_histories
            if hasattr(event, 'name') and event.name == "Return to Work"
        ]
        
        # Find most recent "Return to Work" with retain_seniority=False
        cutoff_date = None
        if return_to_work_events:
            for event in reversed(return_to_work_events):
                if hasattr(event, 'retain_seniority') and event.retain_seniority is False:
                    cutoff_date = event.date
                    break
        
        # Determine which events to consider based on cutoff
        if not return_to_work_events:
            # Case I: No "Return to Work" events - will add synthetic current period later
            relevant_events = []
        elif cutoff_date is not None:
            # Case II: Has retain_seniority=False - only consider events after cutoff
            relevant_events = [
                event for event in sorted_histories
                if event.date and event.date >= cutoff_date
            ]
        else:
            # Case III: Has "Return to Work" but no retain_seniority=False - consider all events
            relevant_events = sorted_histories
        
        # Extract periods from "Change Status" events with status=Resigned
        resignation_events = [
            event for event in relevant_events
            if (hasattr(event, 'name') and event.name == "Change Status" and
                hasattr(event, 'status') and event.status == "Resigned" and
                hasattr(event, 'previous_data') and event.previous_data)
        ]
        
        # Add periods from resignation events
        for event in resignation_events:
            prev_data = event.previous_data
            start_date = prev_data.get('start_date')
            end_date = prev_data.get('end_date') or prev_data.get('resignation_start_date')
            
            if start_date:
                period = {
                    'event': event,
                    'from_date': start_date,
                    'to_date': end_date,
                    'is_synthetic': False,
                }
                periods.append(period)
        
        # ALWAYS add current employment period for seniority calculation
        # Current period always starts from employee start_date to now
        if employee_start_date:
            current_period = {
                'event': None,  # Synthetic period
                'from_date': employee_start_date,
                'to_date': None,  # Current - no end date
                'is_synthetic': True,
            }
            periods.append(current_period)
        
        return periods, sorted_histories

    @extend_schema_field(serializers.IntegerField)
    def get_seniority(self, obj):
        """Calculate employee seniority according to QTNV 5.5.7.

        Business Logic:
        1. Focus on "Return to Work" and "Change Status" (Resigned) events
        2. Always include current employment period in calculation
        3. Sum all relevant periods

        Returns:
            int: Total seniority in days
        """
        work_histories = getattr(obj, "cached_work_histories", [])
        employee_start_date = getattr(obj, "start_date", None)

        if not work_histories:
            # Fallback: calculate from employee start_date
            if employee_start_date:
                return (date.today() - employee_start_date).days
            return 0

        # Get periods to calculate (reuse helper method)
        # Pass employee_start_date so current period is always included
        periods_to_calculate, __ = self._get_calculation_scope(work_histories, employee_start_date)

        # Calculate total days
        total_days = 0
        for period_data in periods_to_calculate:
            from_date = period_data.get('from_date')
            to_date = period_data.get('to_date')
            
            if not from_date:
                continue

            # Parse dates if they're strings
            if isinstance(from_date, str):
                from dateutil.parser import parse
                from_date = parse(from_date).date()
            
            if to_date:
                if isinstance(to_date, str):
                    from dateutil.parser import parse
                    to_date = parse(to_date).date()
                end_date = to_date
            else:
                end_date = date.today()

            # Calculate days for this period
            period_days = (end_date - from_date).days
            if period_days > 0:
                total_days += period_days

        return total_days

    @extend_schema_field(serializers.CharField)
    def get_seniority_text(self, obj):
        """Get human-readable seniority text.

        Returns:
            str: Formatted string like "2 years 1 month 0 day" or "1 year 0 month 20 days"
        """
        total_days = self.get_seniority(obj)
        
        if total_days <= 0:
            return "0 year 0 month 0 day"

        # Calculate years, months, days
        years, months, days = self._days_to_ymd_tuple(total_days)

        # Build parts with proper pluralization
        parts = []
        
        # Years
        if years == 1:
            parts.append(f"{years} year")
        else:
            parts.append(f"{years} years")
        
        # Months
        if months == 1:
            parts.append(f"{months} month")
        else:
            parts.append(f"{months} months")
        
        # Days
        if days == 1:
            parts.append(f"{days} day")
        else:
            parts.append(f"{days} days")
        
        return " ".join(parts)

    @extend_schema_field(SimplifiedWorkHistorySerializer(many=True))
    def get_work_history(self, obj):
        """Get work history periods that are included in seniority calculation.

        IMPORTANT: Returns the SAME periods used in seniority calculation
        to maintain consistency between displayed history and calculated seniority.

        Business Logic:
        - Only show periods from resignation events + current period
        - Current period always starts from employee start_date
        - Ordered by from_date (ascending)

        Returns:
            list: Serialized work history ordered by from_date
        """
        work_histories = getattr(obj, "cached_work_histories", [])
        employee_start_date = getattr(obj, "start_date", None)

        # Get periods to display (SAME as calculation scope)
        # Pass employee_start_date so current period is always included
        periods_to_display, __ = self._get_calculation_scope(work_histories, employee_start_date)

        # Build serialized entries from period data
        serialized_histories = []
        
        for period_data in periods_to_display:
            event = period_data.get('event')
            from_date = period_data.get('from_date')
            to_date = period_data.get('to_date')
            is_synthetic = period_data.get('is_synthetic', False)
            
            # Create entry for this period
            if is_synthetic:
                # Synthetic current period
                entry = {
                    "name": "Change Status",
                    "date": from_date,
                    "detail": _("Current employment period"),
                    "from_date": from_date,
                    "to_date": to_date,
                }
            else:
                # Real event from work history
                entry = {
                    "name": event.name if event and hasattr(event, 'name') else "Change Status",
                    "date": event.date if event and hasattr(event, 'date') else from_date,
                    "detail": event.detail if event and hasattr(event, 'detail') else "",
                    "from_date": from_date,
                    "to_date": to_date,
                }
            serialized_histories.append(entry)
        
        # Sort by from_date (ascending) for display
        serialized_histories.sort(key=lambda x: x['from_date'] if x['from_date'] else date.min)

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
