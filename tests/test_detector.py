import unittest

from soc_lab.detector import detect_brute_force
from soc_lab.simulator import generate_events


class DetectBruteForceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.events = [
            {
                "timestamp": f"2026-10-14T10:0{minute}:00+00:00",
                "source_ip": "203.0.113.24",
                "username": "admin",
                "outcome": "failure",
            }
            for minute in range(5)
        ]

    def test_alerts_on_five_failures_within_window(self) -> None:
        alerts = detect_brute_force(self.events)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["failed_attempts"], 5)
        self.assertEqual(alerts[0]["source_ip"], "203.0.113.24")

    def test_does_not_alert_below_threshold(self) -> None:
        alerts = detect_brute_force(self.events[:4])

        self.assertEqual(alerts, [])

    def test_does_not_alert_for_successful_logins(self) -> None:
        successes = [dict(event, outcome="success") for event in self.events]

        self.assertEqual(detect_brute_force(successes), [])

    def test_does_not_alert_when_failures_are_outside_window(self) -> None:
        spaced_events = [
            dict(event, timestamp=f"2026-10-14T10:{minute * 3:02}:00+00:00")
            for minute, event in enumerate(self.events)
        ]

        self.assertEqual(detect_brute_force(spaced_events), [])

    def test_escalates_when_same_user_logs_in_after_failures(self) -> None:
        success = dict(
            self.events[-1],
            timestamp="2026-10-14T10:05:00+00:00",
            outcome="success",
        )

        alerts = detect_brute_force(self.events + [success])

        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["username"], "admin")
        self.assertEqual(
            alerts[0]["correlated_success_at"], "2026-10-14T10:05:00+00:00"
        )

    def test_does_not_escalate_for_successful_login_by_another_user(self) -> None:
        success = dict(
            self.events[-1],
            timestamp="2026-10-14T10:05:00+00:00",
            username="ana",
            outcome="success",
        )

        alerts = detect_brute_force(self.events + [success])

        self.assertEqual(alerts[0]["severity"], "medium")

    def test_does_not_escalate_for_success_outside_correlation_window(self) -> None:
        success = dict(
            self.events[-1],
            timestamp="2026-10-14T10:10:00+00:00",
            outcome="success",
        )

        alerts = detect_brute_force(self.events + [success])

        self.assertEqual(alerts[0]["severity"], "medium")

    def test_does_not_escalate_when_failures_are_split_across_users(self) -> None:
        usernames = ["ana", "ana", "admin", "admin", "root"]
        split_failures = [
            dict(event, username=username)
            for event, username in zip(self.events, usernames)
        ]
        success = dict(
            self.events[-1],
            timestamp="2026-10-14T10:05:00+00:00",
            username="ana",
            outcome="success",
        )

        alerts = detect_brute_force(split_failures + [success])

        self.assertEqual(alerts[0]["severity"], "medium")


class EventSimulatorTests(unittest.TestCase):
    def test_same_seed_produces_same_events(self) -> None:
        first_run = generate_events("compromised", seed=7)
        second_run = generate_events("compromised", seed=7)

        self.assertEqual(first_run, second_run)

    def test_normal_scenario_does_not_raise_alert(self) -> None:
        alerts = detect_brute_force(generate_events("normal"))

        self.assertEqual(alerts, [])

    def test_brute_force_scenario_generates_medium_alert(self) -> None:
        alerts = detect_brute_force(generate_events("brute-force"))

        self.assertEqual(alerts[0]["severity"], "medium")
        self.assertEqual(alerts[0]["source_ip"], "203.0.113.66")

    def test_compromised_scenario_generates_high_alert(self) -> None:
        alerts = detect_brute_force(generate_events("compromised"))

        self.assertEqual(alerts[0]["severity"], "high")
        self.assertEqual(alerts[0]["username"], "admin")

    def test_unknown_scenario_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            generate_events("unknown")


if __name__ == "__main__":
    unittest.main()
