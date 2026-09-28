"""Geohash encoding and neighbor cells for geographic candidate pruning.

Production nearby lookup must not Haversine against every user on Earth.
Flow: location -> geohash cell + neighbors -> candidate user IDs -> exact Haversine -> radius filter.

Precision vs cell size (approx):
  4 ~ 39 km x 20 km  (covers a 10-mile radius with neighbors)
  5 ~ 4.9 km x 4.9 km (covers ~5 miles with neighbors)
  6 ~ 1.2 km x 0.6 km (covers ~1 mile with neighbors)
"""

from __future__ import annotations

from typing import Iterable

_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"
_BASE32_MAP = {c: i for i, c in enumerate(_BASE32)}

# Neighbor lookup tables (standard geohash neighborhood).
_NEIGHBORS = {
    "right": {"even": "bc01fg45238967deuvhjyznpkmstqrwx", "odd": "p0r21436x8zb9dcf5h7kjnmqesgutwvy"},
    "left": {"even": "238967debc01fg45kmstqrwxuvhjyznp", "odd": "14365h7k9dcfesgujnmqp0r2twvyx8zb"},
    "top": {"even": "p0r21436x8zb9dcf5h7kjnmqesgutwvy", "odd": "bc01fg45238967deuvhjyznpkmstqrwx"},
    "bottom": {"even": "14365h7k9dcfesgujnmqp0r2twvyx8zb", "odd": "238967debc01fg45kmstqrwxuvhjyznp"},
}
_BORDERS = {
    "right": {"even": "bcfguvyz", "odd": "prxz"},
    "left": {"even": "0145hjnp", "odd": "028b"},
    "top": {"even": "prxz", "odd": "bcfguvyz"},
    "bottom": {"even": "028b", "odd": "0145hjnp"},
}


def encode(latitude: float, longitude: float, precision: int = 5) -> str:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("latitude/longitude out of range")
    if precision < 1:
        raise ValueError("precision must be >= 1")
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    geohash = []
    bit = 0
    ch = 0
    even = True
    while len(geohash) < precision:
        if even:
            mid = (lon_range[0] + lon_range[1]) / 2
            if longitude >= mid:
                ch = (ch << 1) + 1
                lon_range[0] = mid
            else:
                ch = (ch << 1) + 0
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if latitude >= mid:
                ch = (ch << 1) + 1
                lat_range[0] = mid
            else:
                ch = (ch << 1) + 0
                lat_range[1] = mid
        even = not even
        bit += 1
        if bit == 5:
            geohash.append(_BASE32[ch])
            bit = 0
            ch = 0
    return "".join(geohash)


def decode_bbox(geohash: str) -> tuple[float, float, float, float]:
    """Return (lat_min, lat_max, lon_min, lon_max)."""
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    even = True
    for char in geohash:
        if char not in _BASE32_MAP:
            raise ValueError(f"invalid geohash character: {char}")
        cd = _BASE32_MAP[char]
        for mask in (16, 8, 4, 2, 1):
            if even:
                mid = (lon_range[0] + lon_range[1]) / 2
                if cd & mask:
                    lon_range[0] = mid
                else:
                    lon_range[1] = mid
            else:
                mid = (lat_range[0] + lat_range[1]) / 2
                if cd & mask:
                    lat_range[0] = mid
                else:
                    lat_range[1] = mid
            even = not even
    return lat_range[0], lat_range[1], lon_range[0], lon_range[1]


def decode(geohash: str) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = decode_bbox(geohash)
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2


def _adjacent(geohash: str, direction: str) -> str:
    geohash = geohash.lower()
    last = geohash[-1]
    parent = geohash[:-1]
    typ = "odd" if len(geohash) % 2 else "even"
    if last in _BORDERS[direction][typ] and parent:
        parent = _adjacent(parent, direction)
    if not parent and last in _BORDERS[direction][typ]:
        return geohash  # polar/dateline edge: stay put
    neighbor_index = _NEIGHBORS[direction][typ].index(last)
    return parent + _BASE32[neighbor_index]


def neighbors(geohash: str) -> list[str]:
    """Eight neighboring cells plus the center cell (unique, order stable)."""
    g = geohash.lower()
    top = _adjacent(g, "top")
    bottom = _adjacent(g, "bottom")
    cells = [
        g,
        _adjacent(g, "right"),
        _adjacent(g, "left"),
        top,
        bottom,
        _adjacent(top, "right"),
        _adjacent(top, "left"),
        _adjacent(bottom, "right"),
        _adjacent(bottom, "left"),
    ]
    seen: list[str] = []
    for cell in cells:
        if cell not in seen:
            seen.append(cell)
    return seen


def precision_for_radius_miles(radius_miles: float) -> int:
    """Choose a cell size so center+neighbors cover the configured radius."""
    if radius_miles <= 1.5:
        return 6
    if radius_miles <= 6:
        return 5
    return 4


def candidate_cells(latitude: float, longitude: float, radius_miles: float) -> list[str]:
    precision = precision_for_radius_miles(radius_miles)
    center = encode(latitude, longitude, precision)
    return neighbors(center)


def in_candidate_cells(geohash: str, cells: Iterable[str]) -> bool:
    """True if the stored geohash shares a prefix with any candidate cell.

    Stored hashes may use a fixed precision (5). Candidate cells vary with radius.
    We match if either is a prefix of the other.
    """
    g = geohash.lower()
    for cell in cells:
        c = cell.lower()
        if g.startswith(c) or c.startswith(g):
            return True
    return False
