import unittest
from datetime import datetime, timedelta, timezone

from soc_lab.rules import detect_all_rules
from soc_lab.simulator import generate_events


class DetectionRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.start = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)

    def authentication_event(
        self, minute: int, source_ip: str, username: str, outcome: str
    ) -> dict[str, str]:
        return {
            "timestamp": (self.start + timedelta(minutes=minute)).isoformat(),
            "event_type": "authentication",
            "source_ip": source_ip,
            "username": username,
            "outcome": outcome,
        }

    def test_all_five_rules_fire_in_combined_scenario(self) -> None:
        events = [
            self.authentication_event(minute, "203.0.113.10", "admin", "failure")
            for minute in range(5)
        ]
        events.append(
            self.authentication_event(5, "203.0.113.10", "admin", "success")
        )
        events.extend(
            self.authentication_event(minute, "203.0.113.20", f"user-{minute}", "failure")
            for minute in range(5)
        )
        events.extend(
            {
                "timestamp": (
                    self.start + timedelta(minutes=minute // 2)
                ).isoformat(),
                "event_type": "firewall_connection",
                "source_ip": "203.0.113.30",
                "destination_port": str(8000 + minute),
                "outcome": "denied",
            }
            for minute in range(10)
        )
        events.append(
            {
                "timestamp": self.start.isoformat(),
                "event_type": "process_creation",
                "hostname": "workstation-01",
                "username": "analyst",
                "process_name": "powershell.exe",
                "command_line": "powershell.exe -EncodedCommand ZQBjAGgAbwA=",
            }
        )

        alerts = detect_all_rules(events)
        rules = {alert["rule"] for alert in alerts}

        self.assertEqual(
            rules,
            {
                "multiple_failed_logins",
                "successful_login_after_failures",
                "password_spraying",
                "firewall_port_sweep",
                "encoded_powershell_command",
            },
        )

    def test_normal_authentication_does_not_raise_alert(self) -> None:
        events = [
            self.authentication_event(minute, "198.51.100.8", "ana", "success")
            for minute in range(5)
        ]

        self.assertEqual(detect_all_rules(events), [])

    def test_full_suite_scenario_exercises_all_rules(self) -> None:
        alerts = detect_all_rules(generate_events("full-suite"))
        rules = {alert["rule"] for alert in alerts}

        self.assertEqual(
            rules,
            {
                "multiple_failed_logins",
                "successful_login_after_failures",
                "password_spraying",
                "firewall_port_sweep",
                "encoded_powershell_command",
            },
        )


if __name__ == "__main__":
    unittest.main()