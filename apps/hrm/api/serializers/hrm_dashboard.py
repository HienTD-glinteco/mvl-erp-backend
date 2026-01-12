"""Serializers for HRM dashboard metrics."""

from rest_framework import serializers


class DashboardItemQueryParamsSerializer(serializers.Serializer):
    """Serializer for query params in dashboard items."""

    proposal_status__in = serializers.CharField(required=False, help_text="Proposal status filter")
    approve_status = serializers.CharField(required=False, help_text="Approval status filter")
    is_pending = serializers.CharField(required=False, help_text="Pending status filter")
    status = serializers.CharField(required=False, help_text="Status filter")


class DashboardItemSerializer(serializers.Serializer):
    """Serializer for a single dashboard statistic item."""

    key = serializers.CharField(help_text="Unique identifier for the item")
    label = serializers.CharField(help_text="Display label for the item")
    count = serializers.IntegerField(help_text="Count value for the statistic")
    path = serializers.CharField(help_text="API path for navigation")
    query_params = DashboardItemQueryParamsSerializer(help_text="Query parameters for filtering")


class ProposalsPendingItemSerializer(serializers.Serializer):
    """Serializer for proposals pending section."""

    key = serializers.CharField(help_text="Fixed key: proposals_pending")
    label = serializers.CharField(help_text="Display label for proposals section")
    items = DashboardItemSerializer(many=True, help_text="List of pending proposal items by type")


class HRMDashboardRealtimeSerializer(serializers.Serializer):
    """Serializer for HRM dashboard realtime KPIs.

    Response structure optimized for frontend navigation:
    - Each item includes path and query_params for direct navigation
    - proposals_pending is grouped separately with nested items by type
    """

    proposals_pending = ProposalsPendingItemSerializer(
        help_text="Pending proposals grouped by type with navigation info"
    )
    attendance_other_pending = DashboardItemSerializer(help_text="Manual attendance records pending approval")
    timesheet_complaints_pending = DashboardItemSerializer(help_text="Timesheet entry complaints pending approval")
    penalty_tickets_unpaid = DashboardItemSerializer(help_text="Penalty tickets that are still unpaid")
