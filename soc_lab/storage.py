"""SQLite persistence for lab runs, events, and analyst triage."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ALERT_STATUSES = {"open", "investigating", "closed"}


class LabStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    scenario TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    event_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(run_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(run_id),
                    rule TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source_ip TEXT,
                    username TEXT,
                    summary TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open'
                        CHECK(status IN ('open', 'investigating', 'closed')),
                    analyst_notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_status_severity
                    ON alerts(status, severity);
                CREATE INDEX IF NOT EXISTS idx_events_run_timestamp
                    ON events(run_id, timestamp);
                """
            )

    def save_run(
        self,
        events: list[dict[str, Any]],
        alerts: list[dict[str, Any]],
        scenario: str,
    ) -> str:
        run_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs(run_id, scenario, created_at) VALUES (?, ?, ?)",
                (run_id, scenario, created_at),
            )
            for index, event in enumerate(events, start=1):
                event_id = str(event.get("event_id", f"event-{index}"))
                connection.execute(
                    """INSERT INTO events
                    (run_id, event_id, timestamp, event_type, payload_json)
                    VALUES (?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        event_id,
                        event["timestamp"],
                        event.get("event_type", "authentication"),
                        json.dumps(event, sort_keys=True),
                    ),
                )

            for alert in alerts:
                connection.execute(
                    """INSERT INTO alerts
                    (alert_id, run_id, rule, severity, source_ip, username,
                     summary, details_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uuid.uuid4().hex,
                        run_id,
                        alert["rule"],
                        alert["severity"],
                        alert.get("source_ip"),
                        alert.get("username"),
                        alert["summary"],
                        json.dumps(alert, sort_keys=True),
                        created_at,
                        created_at,
                    ),
                )
        return run_id

    def list_alerts(
        self,
        status: str | None = None,
        severity: str | None = None,
        run_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = """SELECT alerts.*, runs.scenario
                 FROM alerts JOIN runs USING(run_id)"""
        filters = []
        parameters: list[Any] = []
        if status is not None:
            filters.append("alerts.status = ?")
            parameters.append(status)
        if severity is not None:
            filters.append("alerts.severity = ?")
            parameters.append(severity)
        if run_id is not None:
            filters.append("alerts.run_id = ?")
            parameters.append(run_id)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(max(1, min(limit, 1000)))

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def list_events(
        self,
        run_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        query = """SELECT events.*, runs.scenario
                 FROM events JOIN runs USING(run_id)"""
        parameters: list[Any] = []
        if run_id is not None:
            query += " WHERE events.run_id = ?"
            parameters.append(run_id)
        query += " ORDER BY timestamp DESC LIMIT ?"
        parameters.append(max(1, min(limit, 5000)))

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT runs.*,
                          (SELECT COUNT(*) FROM events WHERE events.run_id = runs.run_id)
                              AS event_count,
                          (SELECT COUNT(*) FROM alerts WHERE alerts.run_id = runs.run_id)
                              AS alert_count
                   FROM runs ORDER BY created_at DESC LIMIT ?""",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT alerts.*, runs.scenario
                   FROM alerts JOIN runs USING(run_id)
                   WHERE alert_id = ?""",
                (alert_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_metrics(self) -> dict[str, Any]:
        with self._connect() as connection:
            totals = connection.execute(
                """SELECT
                       (SELECT COUNT(*) FROM runs) AS runs,
                       (SELECT COUNT(*) FROM events) AS events,
                       (SELECT COUNT(*) FROM alerts) AS alerts,
                       (SELECT COUNT(*) FROM alerts WHERE status = 'open')
                           AS open_alerts"""
            ).fetchone()
            severities = connection.execute(
                "SELECT severity, COUNT(*) AS count FROM alerts GROUP BY severity"
            ).fetchall()
        return {
            **dict(totals),
            "alerts_by_severity": {
                row["severity"]: row["count"] for row in severities
            },
        }

    def update_triage(self, alert_id: str, status: str, analyst_notes: str) -> None:
        if status not in ALERT_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(ALERT_STATUSES))}")

        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE alerts
                   SET status = ?, analyst_notes = ?, updated_at = ?
                   WHERE alert_id = ?""",
                (status, analyst_notes, updated_at, alert_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"unknown alert id: {alert_id}")