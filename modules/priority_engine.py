from __future__ import annotations

import re
from typing import Any


CATEGORY_POINTS = {
    "Road Damage": 14,
    "Garbage / Sanitation": 8,
    "Water Leakage": 14,
    "Drainage": 15,
    "Electricity / Streetlights": 14,
    "Public Safety": 20,
    "Other": 8,
}

BASE_SEVERITY = {
    "Road Damage": 5,
    "Garbage / Sanitation": 3,
    "Water Leakage": 5,
    "Drainage": 5,
    "Electricity / Streetlights": 5,
    "Public Safety": 7,
    "Other": 3,
}

CRITICAL_KEYWORDS = {
    "fire",
    "collapse",
    "electrocution",
    "electric shock",
    "exposed live wire",
    "gas leak",
    "trapped",
    "severe flooding",
    "person injured",
}

HIGH_RISK_KEYWORDS = {
    "accident",
    "injury",
    "injured",
    "danger",
    "dangerous",
    "open manhole",
    "open drain",
    "flood",
    "contaminated",
    "children at risk",
    "school",
    "hospital",
}

ISSUE_KEYWORDS = {
    "blocked",
    "broken",
    "leaking",
    "overflow",
    "pothole",
    "dark",
    "cracked",
    "damaged",
}

PRIORITY_LEVELS = ("Critical", "High", "Medium", "Low")


def _contains_phrase(text: str, phrase: str) -> bool:
    if " " in phrase:
        return phrase in text
    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def calculate_priority(
    category: str,
    title: str,
    description: str,
    report_count: int,
) -> dict[str, Any]:
    """Calculate a transparent, deterministic severity and priority suggestion."""
    normalized_category = category if category in CATEGORY_POINTS else "Other"
    text = " ".join((str(title or ""), str(description or ""))).casefold()

    critical_matches = sorted(
        keyword for keyword in CRITICAL_KEYWORDS if _contains_phrase(text, keyword)
    )
    high_risk_matches = sorted(
        keyword for keyword in HIGH_RISK_KEYWORDS if _contains_phrase(text, keyword)
    )
    issue_matches = sorted(
        keyword for keyword in ISSUE_KEYWORDS if _contains_phrase(text, keyword)
    )

    severity = BASE_SEVERITY[normalized_category]
    keyword_points = 0
    safety_points = 0
    reasons = [f"{normalized_category} category"]

    if issue_matches:
        severity += 1
        keyword_points = 10
        reasons.append(f"issue keywords: {', '.join(issue_matches[:3])}")
    if high_risk_matches:
        severity += 2
        keyword_points = max(keyword_points, 20)
        safety_points = 25
        reasons.append(f"public-safety indicators: {', '.join(high_risk_matches[:3])}")
    if critical_matches:
        severity += 3
        keyword_points = 25
        safety_points = 35
        reasons.append(f"urgent hazards: {', '.join(critical_matches[:3])}")

    try:
        linked_reports = max(0, int(report_count))
    except (TypeError, ValueError):
        linked_reports = 1
    report_points = min(max(0, (linked_reports - 1) * 5), 20)
    if report_points:
        reasons.append(f"{linked_reports} linked complaints")

    category_points = CATEGORY_POINTS[normalized_category]
    priority_score = min(
        100,
        category_points + keyword_points + safety_points + report_points,
    )

    if priority_score >= 80:
        priority_level = "Critical"
    elif priority_score >= 60:
        priority_level = "High"
    elif priority_score >= 35:
        priority_level = "Medium"
    else:
        priority_level = "Low"

    if not issue_matches and not high_risk_matches and not critical_matches:
        reasons.append("no elevated-risk keywords found")

    return {
        "severity": min(10, severity),
        "priority_score": priority_score,
        "priority_level": priority_level,
        "priority_reason": "; ".join(reasons) + ".",
        "category_points": category_points,
        "keyword_points": keyword_points,
        "safety_points": safety_points,
        "report_count_points": report_points,
    }
