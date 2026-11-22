from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable

from utils.location import haversine_meters, normalize_coordinates

CATEGORY_ALIASES = {
    "road damage": "Road Damage",
    "pothole": "Road Damage",
    "road": "Road Damage",
    "garbage": "Garbage / Sanitation",
    "sanitation": "Garbage / Sanitation",
    "waste": "Garbage / Sanitation",
    "water leakage": "Water Leakage",
    "leak": "Water Leakage",
    "drainage": "Drainage",
    "blocked drain": "Drainage",
    "streetlight": "Electricity / Streetlights",
    "electricity": "Electricity / Streetlights",
    "power": "Electricity / Streetlights",
    "public safety": "Public Safety",
    "safety": "Public Safety",
    "other": "Other",
}


def _normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(str(value).lower().replace("-", " ").split())


def _canonical_category(category: str) -> str:
    if not category:
        return "Other"
    text = _normalize_text(category)
    if text in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[text]
    for key, mapped in CATEGORY_ALIASES.items():
        if key in text:
            return mapped
    return category.strip()


def description_similarity(desc_a: str, desc_b: str) -> float:
    if not desc_a or not desc_b:
        return 0.0
    left = _normalize_text(desc_a)
    right = _normalize_text(desc_b)
    if left == right:
        return 1.0
    return round(SequenceMatcher(None, left, right).ratio(), 3)


def find_duplicate_incident(
    issue_category: str,
    description: str,
    latitude: float | None,
    longitude: float | None,
    incidents: Iterable[dict],
) -> dict | None:
    """Return a matching incident dictionary if duplicate detection threshold is met."""
    normalized_category = _canonical_category(issue_category)
    candidate = None
    best_score = 0.0

    for incident in incidents:
        incident_category = _canonical_category(str(incident.get("category") or ""))
        if incident_category != normalized_category:
            if normalized_category not in {"Other", "Public Safety"}:
                continue

        description_score = description_similarity(description, str(incident.get("description") or ""))
        location_score = 0.0

        incident_lat, incident_lon = normalize_coordinates(incident.get("latitude"), incident.get("longitude"))
        current_lat, current_lon = normalize_coordinates(latitude, longitude)
        if current_lat is not None and current_lon is not None and incident_lat is not None and incident_lon is not None:
            distance_m = haversine_meters(current_lat, current_lon, incident_lat, incident_lon)
            if distance_m <= 100:
                location_score = 0.4

        if description_score >= 0.55 or location_score > 0:
            combined_score = description_score * 0.7 + location_score
            if combined_score > best_score:
                best_score = combined_score
                candidate = incident

    if candidate is not None and best_score >= 0.55:
        return candidate
    return None


def _title_similarity(title_a: str, title_b: str) -> float:
    if not title_a or not title_b:
        return 0.0
    return round(
        SequenceMatcher(None, _normalize_text(title_a), _normalize_text(title_b)).ratio(),
        3,
    )


def find_possible_duplicate_complaint(
    title: str,
    description: str,
    category: str,
    location: str,
    latitude: float | None,
    longitude: float | None,
    existing_complaints: Iterable[dict],
    maximum_distance_meters: float = 200,
) -> dict | None:
    """Find a conservative possible match; never merge or link records automatically."""
    normalized_category = _canonical_category(category)
    normalized_location = _normalize_text(location)
    current_lat, current_lon = normalize_coordinates(latitude, longitude)
    best_candidate = None
    best_score = 0.0

    for existing in existing_complaints:
        if not existing.get("incident_id"):
            continue
        if _canonical_category(str(existing.get("category") or "")) != normalized_category:
            continue

        title_score = _title_similarity(title, str(existing.get("title") or ""))
        description_score = description_similarity(
            description,
            str(existing.get("description") or ""),
        )
        text_score = 0.4 * title_score + 0.6 * description_score

        existing_lat, existing_lon = normalize_coordinates(
            existing.get("latitude"),
            existing.get("longitude"),
        )
        distance_meters = None
        same_location_text = (
            normalized_location
            and normalized_location == _normalize_text(str(existing.get("location") or ""))
        )

        if (
            current_lat is not None
            and current_lon is not None
            and existing_lat is not None
            and existing_lon is not None
        ):
            distance_meters = haversine_meters(
                current_lat,
                current_lon,
                existing_lat,
                existing_lon,
            )
            nearby = distance_meters <= maximum_distance_meters
        else:
            nearby = bool(same_location_text)

        # Require both title and description evidence as well as a nearby location.
        if not nearby or title_score < 0.25 or description_score < 0.30 or text_score < 0.48:
            continue

        score = text_score + (0.1 if distance_meters is not None else 0)
        if score > best_score:
            best_score = score
            best_candidate = dict(existing)
            best_candidate["title_similarity"] = title_score
            best_candidate["description_similarity"] = description_score
            best_candidate["text_similarity"] = round(text_score, 3)
            best_candidate["distance_meters"] = (
                round(distance_meters, 1)
                if distance_meters is not None
                else None
            )

    return best_candidate
