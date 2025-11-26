"""DRF FilterBackends for data scope and leadership filtering."""

from decimal import Decimal, InvalidOperation

from django.db.models import Case, DecimalField, ExpressionWrapper, F, FloatField, Func, Value, When
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


class DistanceOrderingFilterBackend(BaseFilterBackend):
    """
    Filter backend that orders geolocations by distance from a given point.

    Usage in ViewSet:
        class MyViewSet(viewsets.ModelViewSet):
            filter_backends = [DistanceOrderingFilterBackend, ...]

    Query parameters:
        - user_latitude: Latitude of user's current location
        - user_longitude: Longitude of user's current location
        - ordering: Use 'distance' or '-distance' to sort by distance

    Example:
        ?user_latitude=10.7769&user_longitude=106.7009&ordering=distance
    """

    def filter_queryset(self, request, queryset, view):
        """Order queryset by distance from user's location if coordinates are provided."""
        user_lat_str = request.query_params.get("user_latitude")
        user_lon_str = request.query_params.get("user_longitude")
        ordering = request.query_params.get("ordering", "")

        # Only apply distance ordering if coordinates are provided and distance ordering is requested
        if not (user_lat_str and user_lon_str and "distance" in ordering):
            return queryset

        try:
            user_lat = Decimal(user_lat_str)
            user_lon = Decimal(user_lon_str)

            # Validate coordinates range
            if not (-90 <= user_lat <= 90 and -180 <= user_lon <= 180):
                return queryset

        except (InvalidOperation, ValueError):
            return queryset

        # Calculate distance using Haversine formula in SQL
        # Convert to radians
        lat1 = ExpressionWrapper(
            Value(float(user_lat)) * Value(3.141592653589793) / Value(180), output_field=FloatField()
        )
        lon1 = ExpressionWrapper(
            Value(float(user_lon)) * Value(3.141592653589793) / Value(180), output_field=FloatField()
        )
        lat2 = ExpressionWrapper(F("latitude") * Value(3.141592653589793) / Value(180), output_field=FloatField())
        lon2 = ExpressionWrapper(F("longitude") * Value(3.141592653589793) / Value(180), output_field=FloatField())

        # Calculate differences
        dlat = ExpressionWrapper(lat2 - lat1, output_field=FloatField())
        dlon = ExpressionWrapper(lon2 - lon1, output_field=FloatField())

        # Haversine formula using SQL functions
        a = ExpressionWrapper(
            Func(dlat / Value(2), function="SIN") ** Value(2)
            + Func(lat1, function="COS")
            * Func(lat2, function="COS")
            * (Func(dlon / Value(2), function="SIN") ** Value(2)),
            output_field=FloatField(),
        )

        # Calculate distance in meters (Earth radius = 6371000 meters)
        distance = ExpressionWrapper(
            Value(6371000) * Value(2) * Func(Func(a, function="SQRT"), function="ASIN"), output_field=FloatField()
        )

        # Annotate queryset with distance
        queryset = queryset.annotate(distance=distance)

        # Apply ordering
        if ordering.startswith("-distance"):
            return queryset.order_by("-distance")
        else:
            return queryset.order_by("distance")

        return queryset
