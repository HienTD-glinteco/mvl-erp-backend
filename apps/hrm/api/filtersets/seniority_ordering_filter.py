from datetime import date

from rest_framework.filters import OrderingFilter


class SeniorityOrderingFilter(OrderingFilter):
    """Custom ordering filter for calculated seniority field.

    Sorts in Python memory after prefetch optimization.
    Supports ordering by:
    - seniority_days: Ascending order (least senior first)
    - -seniority_days: Descending order (most senior first)
    - code: Employee code
    - fullname: Employee full name
    """

    # Define ordering fields to prevent ImproperlyConfigured error
    ordering_fields = ["seniority_days", "code", "fullname"]

    def get_valid_fields(self, queryset, view, context=None):
        """Return valid fields for ordering."""
        if context is None:
            context = {}
        valid_fields = super().get_valid_fields(queryset, view, context)
        # Add seniority_days as a valid field
        valid_fields = list(valid_fields) if valid_fields else []
        if ("seniority_days", "seniority_days") not in valid_fields:
            valid_fields.append(("seniority_days", "seniority_days"))
        return valid_fields

    def filter_queryset(self, request, queryset, view):
        """Filter queryset with custom ordering."""
        ordering = self.get_ordering(request, queryset, view)

        if ordering and ("seniority_days" in ordering or "-seniority_days" in ordering):
            return self._sort_by_seniority(queryset, ordering)

        return super().filter_queryset(request, queryset, view)

    def _sort_by_seniority(self, queryset, ordering):
        """Sort queryset by calculated seniority in memory."""
        employees = list(queryset)  # Fetch all with prefetch

        # Calculate seniority for each
        for emp in employees:
            emp._calculated_seniority_days = self._calculate_seniority_days(emp)

        # Sort
        reverse = "-seniority_days" in ordering
        employees.sort(key=lambda emp: emp._calculated_seniority_days, reverse=reverse)

        return employees

    def _calculate_seniority_days(self, employee):
        """Calculate total seniority in days.

        Uses same logic as serializer to ensure consistency.

        Args:
            employee: Employee object with cached_work_histories attribute

        Returns:
            int: Total seniority in days
        """
        work_histories = getattr(employee, "cached_work_histories", [])

        if not work_histories:
            if hasattr(employee, "start_date") and employee.start_date:
                return (date.today() - employee.start_date).days
            return 0

        sorted_histories = sorted(work_histories, key=lambda x: x.from_date if x.from_date else date.min)

        # Find most recent non-continuous period
        last_non_retain_index = None
        for i, wh in enumerate(sorted_histories):
            if hasattr(wh, "retain_seniority") and wh.retain_seniority is False:
                last_non_retain_index = i

        if last_non_retain_index is not None:
            periods_to_calculate = sorted_histories[last_non_retain_index:]
        else:
            periods_to_calculate = sorted_histories

        # Calculate total days
        total_days = 0
        for period in periods_to_calculate:
            if not period.from_date:
                continue

            end_date = period.to_date if period.to_date else date.today()
            period_days = (end_date - period.from_date).days
            total_days += period_days

        return total_days
