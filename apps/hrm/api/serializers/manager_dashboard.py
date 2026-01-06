"""Serializers for Manager dashboard metrics."""

from rest_framework import serializers


class ManagerDashboardItemQueryParamsSerializer(serializers.Serializer):
    """Serializer for query params in manager dashboard items."""

    status = serializers.CharField(required=False, help_text="Status filter")
    finalized = serializers.CharField(required=False, help_text="Finalized filter")


class ManagerDashboardItemSerializer(serializers.Serializer):
    """Serializer for a single manager dashboard statistic item."""

    key = serializers.CharField(help_text="Unique identifier for the item")
    label = serializers.CharField(help_text="Display label for the item")
    count = serializers.IntegerField(help_text="Count value for the statistic")
    path = serializers.CharField(help_text="API path for navigation")
    query_params = ManagerDashboardItemQueryParamsSerializer(help_text="Query parameters for filtering")


class ManagerDashboardRealtimeSerializer(serializers.Serializer):
    """Serializer for Manager dashboard realtime KPIs.

    Response structure optimized for frontend navigation:
    - Each item includes path and query_params for direct navigation
    - proposals_to_verify: Number of proposals the manager needs to verify
    - kpi_assessments_pending: Number of KPI assessments pending manager review
    """

    proposals_to_verify = ManagerDashboardItemSerializer(help_text="Proposals pending verification by this manager")
    kpi_assessments_pending = ManagerDashboardItemSerializer(help_text="KPI assessments pending manager review")
