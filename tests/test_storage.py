import tempfile
import unittest
from pathlib import Path

from soc_lab.storage import LabStore


class LabStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = LabStore(Path(self.temp_dir.name) / "lab.sqlite")
        self.events = [
            {
                "event_id": "evt-0001",
                "timestamp": "2026-10-14T12:00:00+00:00",
                "event_type": "authentication",
                "source_ip": "203.0.113.5",
                "username": "admin",
                "outcome": "failure",
            }
        ]
        self.alerts = [
            {
                "rule": "multiple_failed_logins",
                "severity": "medium",
                "source_ip": "203.0.113.5",
                "summary": "Repeated failed logins",
            }
        ]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_saves_run_events_and_alerts(self) -> None:
        run_id = self.store.save_run(self.events, self.alerts, "test")

        self.assertEqual(self.store.get_metrics()["runs"], 1)
        self.assertEqual(self.store.get_metrics()["events"], 1)
        saved_alerts = self.store.list_alerts()
        self.assertEqual(len(saved_alerts), 1)
        self.assertEqual(saved_alerts[0]["run_id"], run_id)
        self.assertEqual(self.store.get_alert(saved_alerts[0]["alert_id"]), saved_alerts[0])
        self.assertEqual(self.store.list_runs()[0]["event_count"], 1)

    def test_updates_triage_status_and_notes(self) -> None:
        self.store.save_run(self.events, self.alerts, "test")
        alert_id = self.store.list_alerts()[0]["alert_id"]

        self.store.update_triage(alert_id, "investigating", "Checking the source")

        saved_alert = self.store.list_alerts(status="investigating")[0]
        self.assertEqual(saved_alert["analyst_notes"], "Checking the source")
        self.assertEqual(self.store.get_metrics()["open_alerts"], 0)

    def test_rejects_invalid_triage_status(self) -> None:
        with self.assertRaises(ValueError):
            self.store.update_triage("missing", "invalid", "")


if __name__ == "__main__":
    unittest.main()