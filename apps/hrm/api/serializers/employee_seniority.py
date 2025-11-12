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

    def _get_calculation_scope(self, work_histories):
        """Determine which work history periods to include in calculation.

        This method builds employment periods by following the chain of work history events.
        
        Logic based on example from comment:
        1. Sort by date (descending - most recent first)
        2. Start from most recent event
        3. Current period: from most recent event.date to now (if no to_date)
        4. If current event has retain_seniority=True, look for previous periods
        5. Find previous periods from previous_data of resignation events
        6. Continue chain until hit retain_seniority=False or end of history
        
        Args:
            work_histories (list): List of EmployeeWorkHistory objects

        Returns:
            tuple: (periods_to_include, sorted_all_histories)
        """
        if not work_histories:
            return [], []

        # Sort by date (descending - most recent first)
        sorted_histories = sorted(
            work_histories, 
            key=lambda x: x.date if x.date else date.min,
            reverse=True
        )

        periods = []
        
        # Start with most recent event
        if not sorted_histories:
            return periods, sorted_histories
            
        most_recent = sorted_histories[0]
        
        # Current period (most recent event)
        current_period = {
            'event': most_recent,
            'from_date': most_recent.date,
            'to_date': None,  # Current period has no end date
        }
        periods.append(current_period)
        
        # Check if we should include previous periods
        # Only if most_recent has retain_seniority=True
        if not (hasattr(most_recent, 'retain_seniority') and most_recent.retain_seniority is True):
            # Don't include previous periods
            return periods, sorted_histories
        
        # Find the chain of previous periods
        # We need to find resignation events and extract period info from previous_data
        for i in range(1, len(sorted_histories)):
            event = sorted_histories[i]
            
            # Check if this is a resignation/status change that has previous employment data
            if hasattr(event, 'previous_data') and event.previous_data:
                prev_data = event.previous_data
                
                # Extract period dates from previous_data
                start_date = prev_data.get('start_date')
                end_date = prev_data.get('end_date') or prev_data.get('resignation_start_date')
                
                if start_date:
                    # Found a previous employment period
                    period = {
                        'event': event,
                        'from_date': start_date,
                        'to_date': end_date,
                    }
                    periods.append(period)
                    
                    # Check if we should continue (look for the event that started this period)
                    # Find the "Return to Work" or "Change Status" event with this start_date
                    start_event = None
                    for j in range(i + 1, len(sorted_histories)):
                        check_event = sorted_histories[j]
                        if check_event.date == start_date:
                            start_event = check_event
                            break
                    
                    # If the start event has retain_seniority=False or None, stop
                    if start_event:
                        if hasattr(start_event, 'retain_seniority'):
                            if start_event.retain_seniority is False or start_event.retain_seniority is None:
                                break
                        else:
                            break
                    else:
                        # No start event found, stop
                        break

        return periods, sorted_histories

    @extend_schema_field(serializers.IntegerField)
    def get_seniority(self, obj):
        """Calculate employee seniority according to QTNV 5.5.7.

        Business Logic:
        1. Follow the chain of work history events from most recent backwards
        2. Include periods where retain_seniority=True
        3. Stop at retain_seniority=False or None

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
        periods_to_calculate, __ = self._get_calculation_scope(work_histories)

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
        - Follow the chain from most recent event backwards
        - Include periods where retain_seniority=True
        - If no work history exists, add synthetic current period
        - Display ordered by from_date (ascending)

        Returns:
            list: Serialized work history ordered by from_date
        """
        work_histories = getattr(obj, "cached_work_histories", [])

        # Get periods to display (SAME as calculation scope)
        periods_to_display, __ = self._get_calculation_scope(work_histories)

        # Serialize periods
        serialized_histories = []
        
        if not periods_to_display:
            # No work history at all - add synthetic current period
            if hasattr(obj, "start_date") and obj.start_date:
                current_period = {
                    "name": "Change Status",
                    "date": obj.start_date,
                    "detail": _("Current employment period"),
                    "from_date": obj.start_date,
                    "to_date": None,
                }
                serialized_histories.append(current_period)
        else:
            # Build serialized entries from period data
            for period_data in periods_to_display:
                event = period_data.get('event')
                from_date = period_data.get('from_date')
                to_date = period_data.get('to_date')
                
                # Create entry for this period
                entry = {
                    "name": event.name if hasattr(event, 'name') else "Change Status",
                    "date": event.date if hasattr(event, 'date') else from_date,
                    "detail": event.detail if hasattr(event, 'detail') else "",
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
