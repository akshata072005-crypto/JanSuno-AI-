from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from PIL import Image

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


def _safe_json(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
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


def analyze_image(image_path: str, complaint_text: str = "", category_hint: str | None = None) -> dict:
    """Inspect an uploaded civic image and return a structured summary when possible."""
    if not image_path:
        return {
            "visible_issue": "No image provided",
            "category": category_hint or "Other",
            "visible_damage": "No visual inspection was possible.",
            "severity_estimate": 4,
            "confidence_score": 0.0,
            "mode": "fallback",
        }

    client = get_gemini_client()
    if client is None:
        fallback_category = category_hint or "Other"
        return {
            "visible_issue": complaint_text[:120] if complaint_text else "Civic issue image uploaded for review.",
            "category": fallback_category if fallback_category in ALLOWED_CATEGORIES else "Other",
            "visible_damage": "Image captured and stored successfully; further damage details require manual review.",
            "severity_estimate": 5,
            "confidence_score": 0.0,
            "mode": "fallback",
        }

    try:
        input_image = Image.open(image_path)
        prompt = (
            "Analyze this civic issue image. Return only valid JSON with keys: visible_issue, category, "
            "visible_damage, severity_estimate, confidence_score. Use only one of these categories: "
            "Road Damage, Garbage / Sanitation, Water Leakage, Drainage, Electricity / Streetlights, Public Safety, Other. "
            "Do not claim exact location or hidden damage. Keep confidence between 0 and 1."
            f"Complaint context: {complaint_text or 'No additional text provided'}"
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[prompt, input_image],
        )

        raw_text = getattr(response, "text", None)
        if not raw_text:
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                if content is not None:
                    for part in getattr(content, "parts", []) or []:
                        if hasattr(part, "text"):
                            raw_text = part.text
                            break
                if raw_text:
                    break

        payload = _safe_json(raw_text or "")
        if payload:
            category = str(payload.get("category") or category_hint or "Other")
            if category not in ALLOWED_CATEGORIES:
                category = category_hint or "Other"
            return {
                "visible_issue": payload.get("visible_issue") or "Civic issue detected in image.",
                "category": category,
                "visible_damage": payload.get("visible_damage") or "Visual damage visible in the image.",
                "severity_estimate": int(payload.get("severity_estimate", 5)),
                "confidence_score": float(payload.get("confidence_score", 0.0)),
                "mode": "ai",
            }
    except Exception:
        pass

    fallback_category = category_hint or "Other"
    return {
        "visible_issue": complaint_text[:120] if complaint_text else "Civic issue image uploaded for review.",
        "category": fallback_category if fallback_category in ALLOWED_CATEGORIES else "Other",
        "visible_damage": "Image captured and stored successfully; a detailed damage assessment requires manual review.",
        "severity_estimate": 5,
        "confidence_score": 0.0,
        "mode": "fallback",
    }
