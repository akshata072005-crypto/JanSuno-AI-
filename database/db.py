from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.helpers import get_now_iso
from modules.priority_engine import calculate_priority

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "jansuno.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    schema_path = BASE_DIR / "database" / "schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text(encoding="utf-8"))
    incident_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(incidents)").fetchall()
    }
    new_columns = {
        "suggested_priority_score": "REAL",
        "suggested_priority_level": "TEXT",
        "priority_reason": "TEXT",
        "manual_priority_level": "TEXT",
        "priority_override": "INTEGER NOT NULL DEFAULT 0",
        "resolved_at": "TEXT",
    }
    for column_name, column_type in new_columns.items():
        if column_name not in incident_columns:
            conn.execute(
                f"ALTER TABLE incidents ADD COLUMN {column_name} {column_type}"
            )
    conn.execute(
        """
        UPDATE incidents
        SET suggested_priority_score = COALESCE(suggested_priority_score, priority_score),
            suggested_priority_level = COALESCE(suggested_priority_level, priority_level),
            priority_reason = COALESCE(
                priority_reason,
                'Existing priority retained; awaiting rule-based recalculation.'
            )
        """
    )
    conn.execute(
        """
        UPDATE incidents
        SET report_count = (
            SELECT COUNT(*) FROM complaints
            WHERE complaints.incident_id = incidents.incident_id
        )
        """
    )
    legacy_priorities = conn.execute(
        """
        SELECT incidents.incident_id, incidents.category, incidents.title,
               incidents.manual_priority_level, incidents.priority_override,
               COUNT(complaints.complaint_id) AS linked_count,
               GROUP_CONCAT(complaints.title, ' ') AS complaint_titles,
               GROUP_CONCAT(complaints.description, ' ') AS complaint_descriptions
        FROM incidents
        LEFT JOIN complaints ON complaints.incident_id = incidents.incident_id
        WHERE incidents.priority_reason =
              'Existing priority retained; awaiting rule-based recalculation.'
        GROUP BY incidents.incident_id
        """
    ).fetchall()
    for row in legacy_priorities:
        priority = calculate_priority(
            category=row["category"] or "Other",
            title=" ".join(
                value for value in (row["title"], row["complaint_titles"]) if value
            ),
            description=row["complaint_descriptions"] or "",
            report_count=row["linked_count"],
        )
        effective_level = (
            row["manual_priority_level"]
            if row["priority_override"] and row["manual_priority_level"]
            else priority["priority_level"]
        )
        conn.execute(
            """
            UPDATE incidents
            SET severity = ?,
                impact_score = ?,
                priority_score = ?,
                priority_level = ?,
                suggested_priority_score = ?,
                suggested_priority_level = ?,
                priority_reason = ?
            WHERE incident_id = ?
            """,
            (
                priority["severity"],
                priority["priority_score"],
                priority["priority_score"],
                effective_level,
                priority["priority_score"],
                priority["priority_level"],
                priority["priority_reason"],
                row["incident_id"],
            ),
        )
    conn.commit()
    conn.close()


def get_cached_geocoding_results(query: str) -> Optional[List[Dict[str, Any]]]:
    conn = get_connection()
    row = conn.execute(
        "SELECT results_json FROM geocode_cache WHERE query = ?",
        (query,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return json.loads(row["results_json"])


def cache_geocoding_results(query: str, results: List[Dict[str, Any]]) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO geocode_cache (query, results_json, cached_at)
        VALUES (?, ?, ?)
        ON CONFLICT(query) DO UPDATE SET
            results_json = excluded.results_json,
            cached_at = excluded.cached_at
        """,
        (query, json.dumps(results), get_now_iso()),
    )
    conn.commit()
    conn.close()


def generate_record_id(prefix: str, table_name: str, column_name: str) -> str:
    conn = get_connection()
    query = (
        f"SELECT MAX(CAST(SUBSTR({column_name}, {len(prefix) + 1}) AS INTEGER)) AS highest "
        f"FROM {table_name} WHERE {column_name} LIKE '{prefix}%';"
    )
    row = conn.execute(query).fetchone()
    conn.close()
    highest = int(row["highest"] or 0) if row and row["highest"] is not None else 0
    return f"{prefix}{highest + 1:03d}"


def get_incident_by_id(incident_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT incidents.*,
               (SELECT COUNT(*) FROM complaints
                WHERE complaints.incident_id = incidents.incident_id) AS actual_report_count
        FROM incidents
        WHERE incident_id = ?
        """,
        (incident_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    incident = dict(row)
    incident["report_count"] = incident.pop("actual_report_count")
    return incident


def get_incidents_for_duplicate_check() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT incident_id, title, category, description, latitude, longitude, report_count, priority_score FROM incidents ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_duplicate_complaint_candidates() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT complaints.complaint_id, complaints.title, complaints.description,
               complaints.category, complaints.location, complaints.latitude,
               complaints.longitude, incidents.incident_id,
               incidents.title AS incident_title, incidents.issue_type,
               incidents.priority_score, incidents.priority_level, incidents.status,
               incidents.department, incidents.recommended_action,
               incidents.priority_reason,
               (SELECT COUNT(*) FROM complaints AS linked
                WHERE linked.incident_id = incidents.incident_id) AS report_count
        FROM complaints
        JOIN incidents ON incidents.incident_id = complaints.incident_id
        WHERE incidents.status IS NULL OR incidents.status != 'Resolved'
        ORDER BY complaints.created_at DESC
        """
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_incident_priority_inputs(incident_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT incidents.category, incidents.title,
               COUNT(complaints.complaint_id) AS linked_count,
               GROUP_CONCAT(complaints.title, ' ') AS complaint_titles,
               GROUP_CONCAT(complaints.description, ' ') AS complaint_descriptions
        FROM incidents
        LEFT JOIN complaints ON complaints.incident_id = incidents.incident_id
        WHERE incidents.incident_id = ?
        GROUP BY incidents.incident_id
        """,
        (incident_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def list_incidents() -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT incidents.*,
               (SELECT COUNT(*) FROM complaints
                WHERE complaints.incident_id = incidents.incident_id) AS actual_report_count
        FROM incidents
        ORDER BY incidents.created_at DESC
        """
    ).fetchall()
    conn.close()
    incidents = []
    for row in rows:
        incident = dict(row)
        incident["report_count"] = incident.pop("actual_report_count")
        incidents.append(incident)
    return incidents


def insert_incident(data: Dict[str, Any]) -> str:
    incident_id = data.get("incident_id") or generate_record_id("INC-", "incidents", "incident_id")
    timestamp = get_now_iso()
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO incidents (
            incident_id, title, issue_type, category, description, location, latitude, longitude,
            severity, impact_score, report_count, priority_score, priority_level, department,
            recommended_action, status, created_at, updated_at, suggested_priority_score,
            suggested_priority_level, priority_reason, manual_priority_level, priority_override,
            resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            data.get("title"),
            data.get("issue_type"),
            data.get("category"),
            data.get("description"),
            data.get("location"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("severity"),
            data.get("impact_score"),
            data.get("report_count") or 1,
            data.get("priority_score"),
            data.get("priority_level"),
            data.get("department"),
            data.get("recommended_action"),
            data.get("status") or "Reported",
            timestamp,
            timestamp,
            data.get("suggested_priority_score", data.get("priority_score")),
            data.get("suggested_priority_level", data.get("priority_level")),
            data.get("priority_reason"),
            data.get("manual_priority_level"),
            data.get("priority_override", 0),
            data.get("resolved_at"),
        ),
    )
    conn.commit()
    conn.close()
    return incident_id


def insert_complaint(data: Dict[str, Any]) -> str:
    complaint_id = data.get("complaint_id") or generate_record_id("CMP-", "complaints", "complaint_id")
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO complaints (
            complaint_id, citizen_name, title, description, category, image_path, location,
            latitude, longitude, incident_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            complaint_id,
            data.get("citizen_name"),
            data.get("title"),
            data.get("description"),
            data.get("category"),
            data.get("image_path"),
            data.get("location"),
            data.get("latitude"),
            data.get("longitude"),
            data.get("incident_id"),
            get_now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return complaint_id


def update_incident_status(incident_id: str, new_status: str) -> None:
    allowed_statuses = {"Reported", "Under Review", "Assigned", "In Progress", "Resolved"}
    if new_status not in allowed_statuses:
        raise ValueError(f"Unsupported incident status: {new_status}")

    timestamp = get_now_iso()
    conn = get_connection()
    conn.execute(
        """
        UPDATE incidents
        SET status = ?,
            updated_at = ?,
            resolved_at = CASE
                WHEN ? = 'Resolved' THEN COALESCE(resolved_at, ?)
                ELSE NULL
            END
        WHERE incident_id = ?
        """,
        (new_status, timestamp, new_status, timestamp, incident_id),
    )
    conn.commit()
    conn.close()


def refresh_incident_report_count(incident_id: str) -> int:
    conn = get_connection()
    report_count = conn.execute(
        "SELECT COUNT(*) AS count FROM complaints WHERE incident_id = ?",
        (incident_id,),
    ).fetchone()["count"]
    conn.execute(
        "UPDATE incidents SET report_count = ?, updated_at = ? WHERE incident_id = ?",
        (report_count, get_now_iso(), incident_id),
    )
    conn.commit()
    conn.close()
    return report_count


def update_incident_coordinates_if_missing(
    incident_id: str,
    latitude: float,
    longitude: float,
) -> None:
    """Use a newly confirmed report location when a grouped incident has none."""
    conn = get_connection()
    conn.execute(
        """
        UPDATE incidents
        SET latitude = ?, longitude = ?, updated_at = ?
        WHERE incident_id = ? AND (latitude IS NULL OR longitude IS NULL)
        """,
        (latitude, longitude, get_now_iso(), incident_id),
    )
    conn.commit()
    conn.close()


def update_suggested_priority(
    incident_id: str,
    priority_score: float,
    priority_level: str,
    priority_reason: str,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE incidents
        SET suggested_priority_score = ?,
            suggested_priority_level = ?,
            priority_reason = ?,
            priority_score = ?,
            priority_level = CASE
                WHEN priority_override = 1 THEN manual_priority_level
                ELSE ?
            END,
            updated_at = ?
        WHERE incident_id = ?
        """,
        (
            priority_score,
            priority_level,
            priority_reason,
            priority_score,
            priority_level,
            get_now_iso(),
            incident_id,
        ),
    )
    conn.commit()
    conn.close()


def set_manual_priority_override(
    incident_id: str,
    manual_priority_level: Optional[str],
) -> None:
    allowed_priorities = {"Critical", "High", "Medium", "Low"}
    if manual_priority_level is not None and manual_priority_level not in allowed_priorities:
        raise ValueError(f"Unsupported priority level: {manual_priority_level}")

    conn = get_connection()
    if manual_priority_level is None:
        conn.execute(
            """
            UPDATE incidents
            SET manual_priority_level = NULL,
                priority_override = 0,
                priority_level = COALESCE(suggested_priority_level, priority_level),
                updated_at = ?
            WHERE incident_id = ?
            """,
            (get_now_iso(), incident_id),
        )
    else:
        conn.execute(
            """
            UPDATE incidents
            SET suggested_priority_score = COALESCE(suggested_priority_score, priority_score),
                suggested_priority_level = COALESCE(suggested_priority_level, priority_level),
                manual_priority_level = ?,
                priority_override = 1,
                priority_level = ?,
                updated_at = ?
            WHERE incident_id = ?
            """,
            (manual_priority_level, manual_priority_level, get_now_iso(), incident_id),
        )
    conn.commit()
    conn.close()


def get_dashboard_stats() -> Dict[str, Any]:
    conn = get_connection()
    rows = {
        "total_complaints": conn.execute("SELECT COUNT(*) as count FROM complaints").fetchone()["count"],
        "total_incidents": conn.execute("SELECT COUNT(*) as count FROM incidents").fetchone()["count"],
        "critical_priority": conn.execute("SELECT COUNT(*) as count FROM incidents WHERE priority_level = 'Critical'").fetchone()["count"],
        "high_priority": conn.execute("SELECT COUNT(*) as count FROM incidents WHERE priority_level = 'High'").fetchone()["count"],
        "resolved": conn.execute("SELECT COUNT(*) as count FROM incidents WHERE status = 'Resolved'").fetchone()["count"],
        "pending": conn.execute("SELECT COUNT(*) as count FROM incidents WHERE status != 'Resolved'").fetchone()["count"],
    }
    category_rows = conn.execute(
        "SELECT category, COUNT(*) as count FROM incidents GROUP BY category ORDER BY count DESC"
    ).fetchall()
    priority_rows = conn.execute(
        "SELECT priority_level, COUNT(*) as count FROM incidents GROUP BY priority_level ORDER BY count DESC"
    ).fetchall()
    time_rows = conn.execute(
        "SELECT substr(created_at, 1, 10) as date, COUNT(*) as count FROM incidents GROUP BY substr(created_at, 1, 10) ORDER BY date DESC LIMIT 10"
    ).fetchall()
    conn.close()

    rows["category_distribution"] = [dict(r) for r in category_rows]
    rows["priority_distribution"] = [dict(r) for r in priority_rows]
    rows["incident_over_time"] = [dict(r) for r in time_rows]
    return rows


def get_public_transparency_stats() -> Dict[str, Any]:
    """Return complaint-level aggregates without citizen names or descriptions."""
    conn = get_connection()
    totals = conn.execute(
        """
        SELECT COUNT(*) AS total_complaints,
               SUM(CASE WHEN incidents.status = 'Resolved' THEN 1 ELSE 0 END) AS resolved,
               SUM(CASE WHEN incidents.status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress,
               SUM(CASE
                   WHEN incidents.status IS NULL
                     OR incidents.status NOT IN ('Resolved', 'In Progress')
                   THEN 1 ELSE 0
               END) AS pending
        FROM complaints
        LEFT JOIN incidents ON incidents.incident_id = complaints.incident_id
        """
    ).fetchone()
    category_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized') AS category,
               COUNT(*) AS count
        FROM complaints
        GROUP BY COALESCE(NULLIF(TRIM(category), ''), 'Uncategorized')
        ORDER BY count DESC, category
        """
    ).fetchall()
    area_rows = conn.execute(
        """
        SELECT MIN(TRIM(location)) AS area, COUNT(*) AS count
        FROM complaints
        WHERE location IS NOT NULL AND TRIM(location) != ''
        GROUP BY LOWER(TRIM(location))
        ORDER BY count DESC, area
        """
    ).fetchall()
    resolved_rows = conn.execute(
        """
        SELECT complaints.created_at AS complaint_created_at,
               incidents.resolved_at AS incident_resolved_at
        FROM complaints
        JOIN incidents ON incidents.incident_id = complaints.incident_id
        WHERE incidents.status = 'Resolved'
          AND incidents.resolved_at IS NOT NULL
        """
    ).fetchall()
    conn.close()

    total_complaints = int(totals["total_complaints"] or 0)
    resolved = int(totals["resolved"] or 0)
    resolution_hours = []
    for row in resolved_rows:
        try:
            created_at = datetime.fromisoformat(row["complaint_created_at"])
            resolved_at = datetime.fromisoformat(row["incident_resolved_at"])
        except (TypeError, ValueError):
            continue
        if created_at.tzinfo is not None and resolved_at.tzinfo is None:
            resolved_at = resolved_at.replace(tzinfo=created_at.tzinfo)
        elif resolved_at.tzinfo is not None and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=resolved_at.tzinfo)
        duration_hours = (resolved_at - created_at).total_seconds() / 3600
        if duration_hours >= 0:
            resolution_hours.append(duration_hours)

    return {
        "total_complaints": total_complaints,
        "resolved_complaints": resolved,
        "pending_complaints": int(totals["pending"] or 0),
        "in_progress_complaints": int(totals["in_progress"] or 0),
        "resolution_percentage": round((resolved / total_complaints) * 100, 1)
        if total_complaints
        else 0.0,
        "average_resolution_hours": (
            round(sum(resolution_hours) / len(resolution_hours), 1)
            if resolution_hours
            else None
        ),
        "timed_resolved_complaints": len(resolution_hours),
        "category_distribution": [dict(row) for row in category_rows],
        "area_distribution": [dict(row) for row in area_rows],
    }


def get_incident_details(incident_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    incident = conn.execute(
        """
        SELECT incidents.*,
               (SELECT COUNT(*) FROM complaints
                WHERE complaints.incident_id = incidents.incident_id) AS actual_report_count
        FROM incidents
        WHERE incident_id = ?
        """,
        (incident_id,),
    ).fetchone()
    if incident is None:
        conn.close()
        return None
    complaint_rows = conn.execute(
        "SELECT complaint_id, citizen_name, title, description, category, image_path, location, latitude, longitude, created_at FROM complaints WHERE incident_id = ? ORDER BY created_at DESC",
        (incident_id,),
    ).fetchall()
    conn.close()
    payload = dict(incident)
    payload["report_count"] = payload.pop("actual_report_count")
    payload["complaints"] = [dict(row) for row in complaint_rows]
    return payload


def clear_demo_data() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM complaints")
    conn.execute("DELETE FROM incidents")
    conn.commit()
    conn.close()


def add_demo_data() -> List[str]:
    clear_demo_data()
    demo_data = [
        {
            "title": "Large pothole near college gate",
            "issue_type": "Pothole",
            "category": "Road Damage",
            "description": "A large pothole near the college gate is causing traffic problems and has been reported by many road users.",
            "location": "College Gate, Demo Town",
            "latitude": 28.6139,
            "longitude": 77.2090,
            "severity": 8,
            "impact_score": 75,
            "report_count": 4,
            "priority_score": 74.0,
            "priority_level": "High",
            "department": "Public Works Department",
            "recommended_action": "Inspect the pothole immediately and repair the road before traffic worsens.",
            "status": "Reported",
        },
        {
            "title": "Garbage accumulation near market",
            "issue_type": "Overflowing garbage",
            "category": "Garbage / Sanitation",
            "description": "Garbage is piling up near the market and producing a foul smell. Nearby shops and passersby are affected.",
            "location": "Market Road, Demo Town",
            "latitude": 28.6142,
            "longitude": 77.2096,
            "severity": 7,
            "impact_score": 68,
            "report_count": 3,
            "priority_score": 69.0,
            "priority_level": "Medium",
            "department": "Municipal Sanitation Department",
            "recommended_action": "Schedule waste collection and clean the market edge before it attracts pests.",
            "status": "Under Review",
        },
        {
            "title": "Water leakage near residential street",
            "issue_type": "Water main leak",
            "category": "Water Leakage",
            "description": "Water is leaking near a residential street, creating puddles and posing a slip hazard for pedestrians.",
            "location": "Residential Street, Demo Town",
            "latitude": 28.6128,
            "longitude": 77.2085,
            "severity": 6,
            "impact_score": 60,
            "report_count": 2,
            "priority_score": 58.0,
            "priority_level": "Medium",
            "department": "Water Supply Department",
            "recommended_action": "Isolate the leak and inspect nearby underground lines for the root cause.",
            "status": "Assigned",
        },
        {
            "title": "Broken streetlight near bus stop",
            "issue_type": "Streetlight outage",
            "category": "Electricity / Streetlights",
            "description": "A streetlight near the bus stop is broken and the area is dark during evening hours.",
            "location": "Bus Stop Junction, Demo Town",
            "latitude": 28.6150,
            "longitude": 77.2104,
            "severity": 5,
            "impact_score": 55,
            "report_count": 2,
            "priority_score": 48.0,
            "priority_level": "Medium",
            "department": "Electrical Maintenance Department",
            "recommended_action": "Repair or replace the streetlight fixture and confirm the surrounding area remains safe.",
            "status": "In Progress",
        },
        {
            "title": "Blocked drainage near school",
            "issue_type": "Drainage blockage",
            "category": "Drainage",
            "description": "The drainage channel near the school is blocked, causing water to stagnate after rain.",
            "location": "School Lane, Demo Town",
            "latitude": 28.6135,
            "longitude": 77.2110,
            "severity": 7,
            "impact_score": 62,
            "report_count": 3,
            "priority_score": 64.2,
            "priority_level": "Medium",
            "department": "Storm Water & Drainage Department",
            "recommended_action": "Clear the blocked drain and inspect the flow path to prevent flooding.",
            "status": "Reported",
        },
    ]

    inserted_ids = []
    for item in demo_data:
        incident_id = insert_incident(item)
        inserted_ids.append(incident_id)
        insert_complaint(
            {
                "citizen_name": "Demo User",
                "title": item["title"],
                "description": item["description"],
                "category": item["category"],
                "image_path": "",
                "location": item["location"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "incident_id": incident_id,
            }
        )
    return inserted_ids
