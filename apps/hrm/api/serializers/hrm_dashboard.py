"""Serializers for HCNS dashboard metrics."""

from rest_framework import serializers


class HRMDashboardRealtimeSerializer(serializers.Serializer):
    """Serializer for HRM dashboard realtime KPIs."""

    proposals_pending = serializers.DictField(
        child=serializers.IntegerField(),
        help_text="Pending proposal counts grouped by proposal_type",
    )
    attendance_other_pending = serializers.IntegerField(
        help_text="Number of attendance records (type=other) pending approval"
    )
    timesheet_complaints_pending = serializers.IntegerField(
        help_text="Number of pending timesheet entry complaint proposals"
    )
    penalty_tickets_unpaid = serializers.IntegerField(help_text="Number of penalty tickets that are still unpaid")
