from __future__ import annotations

from pathlib import Path
from typing import Any

from database.db import (
    get_incident_by_id,
    get_incident_priority_inputs,
    insert_complaint,
    insert_incident,
    refresh_incident_report_count,
    update_incident_coordinates_if_missing,
    update_suggested_priority,
)
from modules.action_recommender import recommend_action
from modules.priority_engine import calculate_priority
from utils.helpers import save_image_bytes


def save_confirmed_complaint(
    complaint: dict[str, Any],
    selected_location: dict[str, Any],
    uploads_dir: Path,
    duplicate_incident_id: str | None = None,
) -> dict[str, Any]:
    """Save a citizen-confirmed location and optional citizen-confirmed duplicate link."""
    location = complaint["location"]
    latitude = float(selected_location["latitude"])
    longitude = float(selected_location["longitude"])
    category = complaint["category"]

    image_path = ""
    image_bytes = complaint.get("image_bytes")
    if image_bytes:
        image_path = save_image_bytes(
            image_bytes,
            complaint["image_name"],
            uploads_dir,
        )

    recommendation = recommend_action(
        category=category,
        issue_type=category,
        location=location,
    )

    if duplicate_incident_id:
        incident = get_incident_by_id(duplicate_incident_id)
        if incident is None:
            raise ValueError("The selected existing incident could not be found.")
        if incident.get("status") == "Resolved":
            raise ValueError(
                "The selected incident is already resolved. Submit this as a new incident instead."
            )
        incident_id = duplicate_incident_id
        group_note = f"Your complaint was linked to incident {incident_id} after your confirmation."
        update_incident_coordinates_if_missing(incident_id, latitude, longitude)
    else:
        initial_priority = calculate_priority(
            category=category,
            title=complaint["title"],
            description=complaint["description"],
            report_count=1,
        )
        incident_id = insert_incident(
            {
                "title": complaint["title"],
                "issue_type": category,
                "category": category,
                "description": complaint["description"],
                "location": location,
                "latitude": latitude,
                "longitude": longitude,
                "severity": initial_priority["severity"],
                "impact_score": initial_priority["priority_score"],
                "report_count": 1,
                "priority_score": initial_priority["priority_score"],
                "priority_level": initial_priority["priority_level"],
                "suggested_priority_score": initial_priority["priority_score"],
                "suggested_priority_level": initial_priority["priority_level"],
                "priority_reason": initial_priority["priority_reason"],
                "priority_override": 0,
                "department": recommendation["responsible_department"],
                "recommended_action": recommendation["recommended_action"],
            }
        )
        group_note = "A new civic incident was created."

    insert_complaint(
        {
            "citizen_name": complaint.get("citizen_name") or "Anonymous",
            "title": complaint["title"],
            "description": complaint["description"],
            "category": category,
            "image_path": image_path,
            "location": location,
            "latitude": latitude,
            "longitude": longitude,
            "incident_id": incident_id,
        }
    )

    report_count = refresh_incident_report_count(incident_id)
    priority_inputs = get_incident_priority_inputs(incident_id) or {}
    priority = calculate_priority(
        category=priority_inputs.get("category") or category,
        title=" ".join(
            value
            for value in (
                priority_inputs.get("title"),
                priority_inputs.get("complaint_titles"),
            )
            if value
        ),
        description=priority_inputs.get("complaint_descriptions") or "",
        report_count=report_count,
    )
    update_suggested_priority(
        incident_id=incident_id,
        priority_score=priority["priority_score"],
        priority_level=priority["priority_level"],
        priority_reason=priority["priority_reason"],
    )

    return {
        "incident_id": incident_id,
        "incident": get_incident_by_id(incident_id),
        "category": category,
        "severity": priority["severity"],
        "priority": priority,
        "group_note": group_note,
    }
