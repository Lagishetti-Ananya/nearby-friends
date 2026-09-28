"""Straight-line geographic distance using the Haversine formula (miles)."""

from __future__ import annotations

import math

EARTH_RADIUS_MILES = 3958.8
EARTH_RADIUS_KM = 6371.0


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in miles between two WGS84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MILES * c


def within_radius(lat1: float, lon1: float, lat2: float, lon2: float, radius_miles: float) -> bool:
    return haversine_miles(lat1, lon1, lat2, lon2) <= radius_miles
