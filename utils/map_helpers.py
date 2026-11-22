from __future__ import annotations

from html import escape
from statistics import mean
from typing import Any, Mapping, Sequence

import folium

from utils.location import normalize_coordinates


def incidents_with_coordinates(
    incidents: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return incident records that have a valid latitude and longitude."""
    located_incidents = []
    for incident in incidents:
        latitude, longitude = normalize_coordinates(
            incident.get("latitude"),
            incident.get("longitude"),
        )
        if latitude is None or longitude is None:
            continue

        located_incident = dict(incident)
        located_incident["latitude"] = latitude
        located_incident["longitude"] = longitude
        located_incidents.append(located_incident)
    return located_incidents


def build_incident_map(
    incidents: Sequence[Mapping[str, Any]],
    selected_incident_id: str | None = None,
) -> tuple[folium.Map | None, int]:
    """Build markers only for incidents with valid citizen-provided coordinates."""
    located_incidents = incidents_with_coordinates(incidents)

    if not located_incidents:
        return None, 0

    selected_incident = next(
        (
            incident
            for incident in located_incidents
            if incident.get("incident_id") == selected_incident_id
        ),
        None,
    )
    center_latitude = (
        selected_incident["latitude"]
        if selected_incident
        else mean(incident["latitude"] for incident in located_incidents)
    )
    center_longitude = (
        selected_incident["longitude"]
        if selected_incident
        else mean(incident["longitude"] for incident in located_incidents)
    )

    civic_map = folium.Map(
        location=[center_latitude, center_longitude],
        zoom_start=16 if selected_incident else 12,
    )

    for incident in located_incidents:
        latitude = incident["latitude"]
        longitude = incident["longitude"]
        priority = str(incident.get("priority_level") or "Low")
        marker_color = {
            "Critical": "darkred",
            "High": "red",
            "Medium": "orange",
            "Low": "green",
        }.get(priority, "green")
        issue_type = (
            incident.get("issue_type")
            or incident.get("category")
            or incident.get("title")
            or "Unknown"
        )

        popup_html = f"""
        <div style="font-family:Arial; min-width:180px;">
            <b>Incident ID:</b> {escape(str(incident.get("incident_id") or "N/A"))}<br>
            <b>Issue type:</b> {escape(str(issue_type))}<br>
            <b>Location:</b> {escape(str(incident.get("location") or "Unknown"))}<br>
            <b>Priority:</b> {escape(priority)} ({escape(str(incident.get("priority_score") or "N/A"))})<br>
            <b>Priority source:</b> {escape(str(incident.get("manual_priority_level") or "Rule-based suggestion"))}<br>
            <b>Why:</b> {escape(str(incident.get("priority_reason") or "No explanation recorded"))}<br>
            <b>Report count:</b> {escape(str(incident.get("report_count") or 0))}<br>
            <b>Status:</b> {escape(str(incident.get("status") or "Reported"))}
        </div>
        """
        folium.Marker(
            location=[latitude, longitude],
            popup=folium.Popup(
                popup_html,
                max_width=300,
                show=incident.get("incident_id") == selected_incident_id,
            ),
            icon=folium.Icon(color=marker_color, icon="info-sign"),
        ).add_to(civic_map)

    return civic_map, len(located_incidents)
