"""Geolocation utilities for attendance tracking.

This module provides utilities for calculating distances between geographic coordinates
using the Haversine formula.
"""

import math
from decimal import Decimal


def haversine_distance(lat1: Decimal, lon1: Decimal, lat2: Decimal, lon2: Decimal) -> float:
    """Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula to calculate the distance between two points
    on the Earth's surface given their latitude and longitude coordinates.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance between the two points in meters

    Example:
        >>> haversine_distance(Decimal('10.7769'), Decimal('106.7009'), 
        ...                    Decimal('10.7800'), Decimal('106.7050'))
        450.23  # approximately 450 meters
    """
    # Earth's radius in meters
    EARTH_RADIUS_M = 6371000

    # Convert decimal degrees to radians
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    # Distance in meters
    distance = EARTH_RADIUS_M * c

    return distance


def is_within_radius(
    user_lat: Decimal, user_lon: Decimal, center_lat: Decimal, center_lon: Decimal, radius_m: int
) -> bool:
    """Check if a user's location is within a specified radius of a center point.

    Args:
        user_lat: User's latitude in degrees
        user_lon: User's longitude in degrees
        center_lat: Center point latitude in degrees
        center_lon: Center point longitude in degrees
        radius_m: Radius in meters

    Returns:
        True if the user's location is within the radius, False otherwise

    Example:
        >>> is_within_radius(Decimal('10.7769'), Decimal('106.7009'),
        ...                  Decimal('10.7770'), Decimal('106.7010'), 100)
        True
    """
    distance = haversine_distance(user_lat, user_lon, center_lat, center_lon)
    return distance <= radius_m
