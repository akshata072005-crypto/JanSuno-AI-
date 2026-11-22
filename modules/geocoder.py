from __future__ import annotations

import json
import os
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from database.db import cache_geocoding_results, get_cached_geocoding_results
from dotenv import load_dotenv
from utils.location import normalize_coordinates

load_dotenv()

NOMINATIM_URL = os.getenv(
    "JAN_SUNO_GEOCODER_URL",
    "https://nominatim.openstreetmap.org/search",
)
USER_AGENT = "JanSunoAI/1.0 (civic complaint mapping prototype)"
REQUEST_INTERVAL_SECONDS = 1.0
REQUEST_TIMEOUT_SECONDS = 10

_request_lock = threading.RLock()
_last_request_time = 0.0


def build_address_query(
    address: str,
    city: str = "",
    district: str = "",
    state: str = "",
    country: str = "",
) -> str:
    """Build one geocoding query from the entered address and optional context."""
    parts = [address.strip(), city.strip(), district.strip(), state.strip(), country.strip()]
    return ", ".join(part for part in parts if part)


def _normalize_result(result: dict[str, Any]) -> dict[str, Any] | None:
    latitude, longitude = normalize_coordinates(result.get("lat"), result.get("lon"))
    if latitude is None or longitude is None:
        return None

    return {
        "display_name": str(result.get("display_name") or "Matched location"),
        "latitude": latitude,
        "longitude": longitude,
        "address": result.get("address") or {},
    }


def _request_nominatim(query: str) -> list[dict[str, Any]]:
    global _last_request_time

    params = urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 5,
        }
    )
    request = Request(
        f"{NOMINATIM_URL}?{params}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    # Serialize requests across app sessions to stay within the public service limit.
    with _request_lock:
        remaining_wait = REQUEST_INTERVAL_SECONDS - (time.monotonic() - _last_request_time)
        if remaining_wait > 0:
            time.sleep(remaining_wait)
        _last_request_time = time.monotonic()

        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 429:
                raise GeocodingError(
                    "OpenStreetMap's geocoding service is rate-limiting requests. "
                    "Please wait a moment and try again."
                ) from error
            raise GeocodingError(
                f"OpenStreetMap geocoding failed with HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise GeocodingError(
                "Could not reach OpenStreetMap geocoding. Check your internet connection and try again."
            ) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise GeocodingError(
                "OpenStreetMap returned an unreadable response. Please try again."
            ) from error

    if not isinstance(payload, list):
        raise GeocodingError("OpenStreetMap returned an unexpected response.")

    results = []
    for item in payload:
        if isinstance(item, dict):
            normalized = _normalize_result(item)
            if normalized is not None:
                results.append(normalized)
    return results


class GeocodingError(Exception):
    """Raised when Nominatim cannot be reached or returns an invalid response."""


def geocode_address(query: str) -> list[dict[str, Any]]:
    """Return cached or newly geocoded address matches from OpenStreetMap Nominatim."""
    normalized_query = " ".join(query.casefold().split())
    if not normalized_query:
        raise ValueError("Enter an address before searching.")

    cached_results = get_cached_geocoding_results(normalized_query)
    if cached_results is not None:
        return cached_results

    # Recheck after taking the lock to avoid duplicate calls from concurrent sessions.
    with _request_lock:
        cached_results = get_cached_geocoding_results(normalized_query)
        if cached_results is not None:
            return cached_results
        results = _request_nominatim(query)
        cache_geocoding_results(normalized_query, results)
        return results
