from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv

load_dotenv()

ALLOWED_CATEGORIES = [
    "Road Damage",
    "Garbage / Sanitation",
    "Water Leakage",
    "Drainage",
    "Electricity / Streetlights",
    "Public Safety",
    "Other",
]


def _fallback_classification(text: str, category_hint: str | None = None) -> dict:
    lowered = (text or "").lower()
    category = category_hint or "Other"

    if "pothole" in lowered or "road" in lowered or "crack" in lowered:
        category = "Road Damage"
    elif "garbage" in lowered or "trash" in lowered or "dump" in lowered or "sanitation" in lowered:
        category = "Garbage / Sanitation"
    elif "water" in lowered or "leak" in lowered or "pipe" in lowered:
        category = "Water Leakage"
    elif "drain" in lowered or "clog" in lowered or "stagnant" in lowered:
        category = "Drainage"
    elif "streetlight" in lowered or "light" in lowered or "electric" in lowered:
        category = "Electricity / Streetlights"
    elif "safety" in lowered or "danger" in lowered or "accident" in lowered:
        category = "Public Safety"

    if category not in ALLOWED_CATEGORIES:
        category = "Other"

    severity = 6
    if any(word in lowered for word in ["severe", "danger", "burst", "flood", "collapse", "fire"]):
        severity = 9
    elif any(word in lowered for word in ["major", "big", "broken", "overflow", "dark"]):
        severity = 7

    dept = {
        "Road Damage": "Public Works Department",
        "Garbage / Sanitation": "Municipal Sanitation Department",
        "Water Leakage": "Water Supply Department",
        "Drainage": "Storm Water & Drainage Department",
        "Electricity / Streetlights": "Electrical Maintenance Department",
        "Public Safety": "Public Safety & Local Police Coordination",
        "Other": "Civic Administration Office",
    }.get(category, "Civic Administration Office")

    summary = (text or "Civic issue reported by citizen").strip()
    if len(summary) > 180:
        summary = summary[:177] + "..."

    return {
        "issue_type": category,
        "category": category,
        "severity": severity,
        "responsible_department": dept,
        "summary": summary,
        "safety_concern": "Site should be monitored for public risk until civic staff inspect it.",
        "recommended_action": "Inspect the site quickly and coordinate with the responsible department for repair or cleanup.",
        "mode": "fallback",
    }


def _extract_json_object(raw_text: str) -> dict | None:
    if not raw_text:
        return None

    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        return None
    return None


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception:
        return None


def analyze_complaint_text(text: str, category_hint: str | None = None) -> dict:
    """Analyze a complaint description using Gemini when available, otherwise use local fallback logic."""
    if not text or not text.strip():
        return _fallback_classification("Citizen complaint description is missing.", category_hint)

    client = get_gemini_client()
    if client is None:
        return _fallback_classification(text, category_hint)

    prompt = (
        "You are a civic complaint analyst. Return only valid JSON with keys: "
        "issue_type, category, severity, responsible_department, summary, safety_concern, recommended_action. "
        "The category must be exactly one of: Road Damage, Garbage / Sanitation, Water Leakage, Drainage, "
        "Electricity / Streetlights, Public Safety, Other. "
        "Do not invent location information. Keep the summary concise and practical."
        f"Complaint text: {text}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        raw_text = getattr(response, "text", None)
        if not raw_text:
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                if content is not None:
                    parts = getattr(content, "parts", []) or []
                    for part in parts:
                        if hasattr(part, "text"):
                            raw_text = part.text
                            break
                    if raw_text:
                        break

        data = _extract_json_object(raw_text or "")
        if data:
            category = str(data.get("category", category_hint or "Other")).strip()
            if category not in ALLOWED_CATEGORIES:
                category = category_hint or "Other"
            data["category"] = category
            data["issue_type"] = str(data.get("issue_type") or category)
            data["severe"] = data.get("severity")
            data["severity"] = int(data.get("severity", 6))
            data["responsible_department"] = data.get("responsible_department") or "Civic Administration Office"
            data["summary"] = data.get("summary") or text
            data["safety_concern"] = data.get("safety_concern") or "Monitor the site for public risk."
            data["recommended_action"] = data.get("recommended_action") or "Inspect the issue and coordinate with the relevant civic team."
            data["mode"] = "ai"
            return data
    except Exception:
        pass

    return _fallback_classification(text, category_hint)
