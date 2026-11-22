PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    issue_type TEXT,
    category TEXT,
    description TEXT,
    location TEXT,
    latitude REAL,
    longitude REAL,
    severity INTEGER,
    impact_score INTEGER,
    report_count INTEGER DEFAULT 1,
    priority_score REAL,
    priority_level TEXT,
    department TEXT,
    recommended_action TEXT,
    status TEXT DEFAULT 'Reported',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    suggested_priority_score REAL,
    suggested_priority_level TEXT,
    priority_reason TEXT,
    manual_priority_level TEXT,
    priority_override INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS complaints (
    complaint_id TEXT PRIMARY KEY,
    citizen_name TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT,
    image_path TEXT,
    location TEXT,
    latitude REAL,
    longitude REAL,
    incident_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS geocode_cache (
    query TEXT PRIMARY KEY,
    results_json TEXT NOT NULL,
    cached_at TEXT NOT NULL
);
