"""DRF FilterBackends for data scope and leadership filtering."""

from rest_framework.filters import BaseFilterBackend

from .data_scope import filter_by_leadership, filter_queryset_by_data_scope


class DataScopeFilterBackend(BaseFilterBackend):
    """
    Filter backend that applies position-based data scope filtering.

    Usage in ViewSet:
        class MyViewSet(viewsets.ModelViewSet):
            filter_backends = [DataScopeFilterBackend, ...]
            data_scope_org_field = "department"  # or "employee__department", etc.

    The org_field should point to the organizational unit field in the model.
    """

    def filter_queryset(self, request, queryset, view):
        """Apply data scope filtering based on user's positions"""
        if not request.user or not request.user.is_authenticated:
            return queryset.none()

        # Get org_field from view configuration
        org_field = getattr(view, "data_scope_org_field", "department")

        return filter_queryset_by_data_scope(queryset, request.user, org_field)


class LeadershipFilterBackend(BaseFilterBackend):
    """
    Filter backend that filters by leadership positions.

    This should be applied AFTER DataScopeFilterBackend.

    Usage in ViewSet:
        class MyViewSet(viewsets.ModelViewSet):
            filter_backends = [DataScopeFilterBackend, LeadershipFilterBackend, ...]

    The filter is activated by query parameter:
        ?leadership=1 or ?leadership=true
    """

    def filter_queryset(self, request, queryset, view):
        """Apply leadership filtering based on query parameter"""
        leadership_param = request.query_params.get("leadership", "").lower()

        if leadership_param in ("1", "true", "yes"):
            return filter_by_leadership(queryset, leadership_only=True)

        return queryset
