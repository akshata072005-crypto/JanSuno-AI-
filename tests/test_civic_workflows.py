from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import db
from modules.complaint_service import save_confirmed_complaint
from modules.duplicate_detector import find_possible_duplicate_complaint
from modules.priority_engine import calculate_priority


class CivicWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temporary_directory.name) / "test.db"
        db.initialize_database()
        self.uploads_dir = Path(self.temporary_directory.name) / "uploads"

    def tearDown(self) -> None:
        db.DB_PATH = self.original_db_path
        self.temporary_directory.cleanup()

    def _complaint(self, title: str, description: str) -> dict:
        return {
            "citizen_name": "Test Citizen",
            "title": title,
            "description": description,
            "category": "Road Damage",
            "location": "Main Street",
        }

    def _location(self, latitude: float = 28.6, longitude: float = 77.2) -> dict:
        return {
            "latitude": latitude,
            "longitude": longitude,
        }

    def test_priority_is_explainable_and_safety_keywords_increase_it(self) -> None:
        routine = calculate_priority(
            "Road Damage",
            "Road crack",
            "Small road crack reported.",
            1,
        )
        urgent = calculate_priority(
            "Public Safety",
            "Exposed live wire",
            "Exposed live wire with electric shock hazard.",
            4,
        )

        self.assertIn(routine["priority_level"], {"Critical", "High", "Medium", "Low"})
        self.assertTrue(routine["priority_reason"])
        self.assertEqual(urgent["priority_level"], "Critical")
        self.assertGreater(urgent["severity"], routine["severity"])
        self.assertGreater(urgent["priority_score"], routine["priority_score"])

    def test_duplicate_is_only_linked_after_explicit_confirmation(self) -> None:
        first = save_confirmed_complaint(
            self._complaint(
                "Large pothole on Main Street",
                "A large pothole is damaging cars near the school entrance.",
            ),
            self._location(),
            self.uploads_dir,
        )
        first_incident_id = first["incident_id"]

        second_complaint = self._complaint(
            "Large pothole near school",
            "A large pothole is damaging cars close to the school entrance.",
        )
        possible_match = find_possible_duplicate_complaint(
            title=second_complaint["title"],
            description=second_complaint["description"],
            category=second_complaint["category"],
            location=second_complaint["location"],
            latitude=28.6004,
            longitude=77.2,
            existing_complaints=db.get_duplicate_complaint_candidates(),
        )

        self.assertIsNotNone(possible_match)
        self.assertEqual(len(db.list_incidents()), 1)

        linked = save_confirmed_complaint(
            second_complaint,
            self._location(28.6004, 77.2),
            self.uploads_dir,
            duplicate_incident_id=possible_match["incident_id"],
        )
        self.assertEqual(linked["incident_id"], first_incident_id)
        self.assertEqual(db.get_incident_by_id(first_incident_id)["report_count"], 2)

        separate = save_confirmed_complaint(
            second_complaint,
            self._location(28.6004, 77.2),
            self.uploads_dir,
        )
        self.assertNotEqual(separate["incident_id"], first_incident_id)
        self.assertEqual(len(db.list_incidents()), 2)

    def test_priority_override_can_be_set_and_cleared(self) -> None:
        result = save_confirmed_complaint(
            self._complaint("Pothole", "A pothole is blocking the road."),
            self._location(),
            self.uploads_dir,
        )
        incident_id = result["incident_id"]
        suggested_level = result["incident"]["suggested_priority_level"]

        db.set_manual_priority_override(incident_id, "Critical")
        overridden = db.get_incident_by_id(incident_id)
        self.assertEqual(overridden["priority_level"], "Critical")
        self.assertEqual(overridden["manual_priority_level"], "Critical")
        self.assertEqual(overridden["suggested_priority_level"], suggested_level)

        db.set_manual_priority_override(incident_id, None)
        restored = db.get_incident_by_id(incident_id)
        self.assertEqual(restored["priority_level"], suggested_level)
        self.assertEqual(restored["priority_override"], 0)

    def test_public_statistics_use_complaints_and_valid_resolution_times(self) -> None:
        incident_id = db.insert_incident(
            {
                "title": "Streetlight repair",
                "category": "Electricity / Streetlights",
                "status": "In Progress",
            }
        )
        db.insert_complaint(
            {
                "citizen_name": "Private Test Name",
                "title": "Streetlight is out",
                "description": "Private complaint details must not appear in aggregates.",
                "category": "Electricity / Streetlights",
                "location": "North Park",
                "incident_id": incident_id,
            }
        )
        conn = db.get_connection()
        conn.execute(
            "UPDATE complaints SET created_at = ? WHERE incident_id = ?",
            ("2026-01-01 00:00:00", incident_id),
        )
        conn.commit()
        conn.close()

        in_progress = db.get_public_transparency_stats()
        self.assertEqual(in_progress["total_complaints"], 1)
        self.assertEqual(in_progress["in_progress_complaints"], 1)
        self.assertEqual(in_progress["pending_complaints"], 0)
        self.assertEqual(in_progress["average_resolution_hours"], None)
        self.assertEqual(in_progress["area_distribution"], [{"area": "North Park", "count": 1}])
        self.assertNotIn("citizen_name", in_progress)
        self.assertNotIn("description", in_progress)

        db.update_incident_status(incident_id, "Resolved")
        conn = db.get_connection()
        conn.execute(
            "UPDATE incidents SET resolved_at = ? WHERE incident_id = ?",
            ("2026-01-03 00:00:00", incident_id),
        )
        conn.commit()
        conn.close()

        resolved = db.get_public_transparency_stats()
        self.assertEqual(resolved["resolved_complaints"], 1)
        self.assertEqual(resolved["resolution_percentage"], 100.0)
        self.assertEqual(resolved["average_resolution_hours"], 48.0)

    def test_schema_upgrade_preserves_existing_incident_and_complaint(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.db"
        self.assertIsNotNone(legacy_path)
        old_path = db.DB_PATH
        db.DB_PATH = legacy_path
        conn = sqlite3.connect(legacy_path)
        conn.executescript(
            """
            CREATE TABLE incidents (
                incident_id TEXT PRIMARY KEY, title TEXT NOT NULL, issue_type TEXT,
                category TEXT, description TEXT, location TEXT, latitude REAL,
                longitude REAL, severity INTEGER, impact_score INTEGER,
                report_count INTEGER, priority_score REAL, priority_level TEXT,
                department TEXT, recommended_action TEXT, status TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE complaints (
                complaint_id TEXT PRIMARY KEY, citizen_name TEXT, title TEXT NOT NULL,
                description TEXT NOT NULL, category TEXT, image_path TEXT, location TEXT,
                latitude REAL, longitude REAL, incident_id TEXT, created_at TEXT NOT NULL
            );
            INSERT INTO incidents (
                incident_id, title, category, location, report_count, priority_score,
                priority_level, status, created_at, updated_at
            ) VALUES ('INC-KEEP', 'Existing report', 'Road Damage', 'Main Street', 5,
                      65, 'Medium', 'Reported', '2026-01-01', '2026-01-01');
            INSERT INTO complaints (
                complaint_id, title, description, category, location, incident_id, created_at
            ) VALUES ('CMP-KEEP', 'Existing complaint', 'Pothole', 'Road Damage',
                      'Main Street', 'INC-KEEP', '2026-01-01');
            """
        )
        conn.commit()
        conn.close()

        db.initialize_database()
        incident = db.get_incident_by_id("INC-KEEP")
        details = db.get_incident_details("INC-KEEP")

        self.assertEqual(incident["title"], "Existing report")
        self.assertEqual(incident["report_count"], 1)
        self.assertEqual(details["complaints"][0]["complaint_id"], "CMP-KEEP")
        self.assertEqual(incident["suggested_priority_level"], "Low")
        self.assertTrue(incident["priority_reason"])
        db.DB_PATH = old_path


if __name__ == "__main__":
    unittest.main()
