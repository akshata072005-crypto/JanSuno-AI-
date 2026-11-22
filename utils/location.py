import math
from typing import Optional, Tuple


def normalize_coordinates(latitude: Optional[float], longitude: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    """Validate and normalize user-provided coordinates."""
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return None, None

    if not math.isfinite(lat) or not math.isfinite(lon):
        return None, None

    if lat < -90 or lat > 90 or lon < -180 or lon > 180:
        return None, None

    return lat, lon


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the distance in meters between two coordinate pairs."""
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c
