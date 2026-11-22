from __future__ import annotations


DEFAULT_DEPARTMENTS = {
    "Road Damage": "Public Works Department",
    "Garbage / Sanitation": "Municipal Sanitation Department",
    "Water Leakage": "Water Supply Department",
    "Drainage": "Storm Water & Drainage Department",
    "Electricity / Streetlights": "Electrical Maintenance Department",
    "Public Safety": "Public Safety & Local Police Coordination",
    "Other": "Civic Administration Office",
}


ACTION_MAP = {
    "Road Damage": "Inspect the damaged road surface, place temporary warning barriers if needed, and schedule pothole repair or resurfacing.",
    "Garbage / Sanitation": "Dispatch sanitation teams, remove waste, inspect illegal dumping points, and clean affected areas immediately.",
    "Water Leakage": "Isolate the leaking line, check for pressure loss and contamination risk, and arrange repair by the water utility team.",
    "Drainage": "Unblock drains and culverts, assess stormwater flow, and clear debris before the next rainfall event.",
    "Electricity / Streetlights": "Inspect the streetlight or wiring issue, restore power safely, and replace damaged fixtures where required.",
    "Public Safety": "Assess nearby risks, increase surveillance or patrol presence if needed, and coordinate with local safety authorities.",
    "Other": "Coordinate with the municipal help desk, inspect the site, and escalate to the correct civic department when needed.",
}


FOLLOW_UP_MAP = {
    "Road Damage": "Verify repair quality after work completion and monitor whether the location continues to pose traffic or pedestrian risk.",
    "Garbage / Sanitation": "Check for repeated dumping and ensure the area remains clean over the next few days.",
    "Water Leakage": "Inspect nearby utility lines and confirm that supply quality and pipe integrity remain stable.",
    "Drainage": "Review whether rainfall water is draining correctly and confirm no new blockage has formed.",
    "Electricity / Streetlights": "Test the renovated light fixture and ensure the area remains safe for pedestrians and vehicles.",
    "Public Safety": "Update resident safety advisories and monitor whether additional risk mitigation is required.",
    "Other": "Review whether the issue belongs to another department and document the final service handoff.",
}


SAFETY_PRECAUTIONS = {
    "Road Damage": "Avoid sudden traffic movement near the location, mark the area with visible barriers, and keep pedestrians away from unstable patches.",
    "Garbage / Sanitation": "Use protective gear while handling waste and avoid contact with unknown or hazardous material.",
    "Water Leakage": "Avoid water contact near electrical lines and restrict access until the leak is isolated and inspected.",
    "Drainage": "Keep children away from open drains or flood-prone areas and inspect standing water for health risks.",
    "Electricity / Streetlights": "Do not touch exposed wires, and ensure the site is temporarily secured before repair.",
    "Public Safety": "Share visible warnings, avoid isolated routes, and alert local authorities when immediate risk is found.",
    "Other": "Stay alert to nearby hazards and do not enter unsafe or unstable structures.",
}


def recommend_action(category: str, issue_type: str = "", department: str | None = None, location: str = "") -> dict:
    normalized_category = category or "Other"
    normalized_category = normalized_category.strip()
    if normalized_category not in ACTION_MAP:
        normalized_category = "Other"

    dept = department or DEFAULT_DEPARTMENTS.get(normalized_category, "Civic Administration Office")
    action = ACTION_MAP.get(normalized_category, ACTION_MAP["Other"])
    follow_up = FOLLOW_UP_MAP.get(normalized_category, FOLLOW_UP_MAP["Other"])
    safety = SAFETY_PRECAUTIONS.get(normalized_category, SAFETY_PRECAUTIONS["Other"])

    if location:
        action = f"{action} Location focus: {location}."

    return {
        "responsible_department": dept,
        "recommended_action": action,
        "follow_up_action": follow_up,
        "safety_precautions": safety,
    }
