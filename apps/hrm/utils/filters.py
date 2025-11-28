"""DRF FilterBackends for data scope and leadership filtering."""

from decimal import Decimal, InvalidOperation

from django.db.models import F, FloatField, Value
from django.db.models.functions import ACos, Cos, Greatest, Least, Radians, Sin
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
    """Filter backend that orders geolocations by distance from a given point.

    Uses Haversine formula for distance calculations at database level.

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

    # Earth's mean radius in meters (more accurate than 6371000)
    EARTH_RADIUS_M = 6371008.8

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

        # Use Haversine formula at database level for distance calculation
        # distance = R * acos(sin(lat1) * sin(lat2) + cos(lat1) * cos(lat2) * cos(lon2 - lon1))
        # where R is Earth's radius in meters
        #
        # Clamp the inner expression to [-1, 1] to prevent floating-point precision errors
        # that can occur when two points are very close or identical
        haversine_inner = (
            Sin(Radians(F("latitude"))) * Sin(Radians(float(user_lat)))
            + Cos(Radians(F("latitude"))) * Cos(Radians(float(user_lat))) * Cos(Radians(F("longitude")) - Radians(float(user_lon)))
        )

        # Clamp to valid ACos domain [-1, 1] using Least(Greatest(x, -1), 1)
        clamped_inner = Least(Greatest(haversine_inner, Value(-1.0)), Value(1.0))

        queryset = queryset.annotate(
            distance=self.EARTH_RADIUS_M * ACos(clamped_inner, output_field=FloatField())
        )

        # Apply ordering
        if ordering.startswith("-distance"):
            return queryset.order_by("-distance")
        else:
            return queryset.order_by("distance")
