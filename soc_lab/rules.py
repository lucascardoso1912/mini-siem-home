"""Detection rules for normalized authentication, firewall, and process events."""

import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from soc_lab.detector import detect_brute_force


def _event_timestamp(event: dict[str, Any]) -> datetime:
    timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return timestamp


def detect_success_after_failures(
    events: list[dict[str, Any]],
    threshold: int = 5,
    window_minutes: int = 10,
    success_window_minutes: int = 5,
) -> list[dict[str, Any]]:
    """Detect a successful login shortly after repeated failures."""
    alerts = detect_brute_force(
        events,
        threshold,
        window_minutes,
        success_window_minutes,
        include_success_correlation=True,
    )
    return [
        {**alert, "rule": "successful_login_after_failures"}
        for alert in alerts
        if alert.get("severity") == "high"
    ]


def detect_password_spraying(
    events: list[dict[str, Any]],
    username_threshold: int = 5,
    window_minutes: int = 10,
) -> list[dict[str, Any]]:
    """Detect one source failing authentication against many accounts."""
    failures_by_ip: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for event in events:
        if event.get("event_type", "authentication") != "authentication":
            continue
        if event.get("outcome") == "failure":
            failures_by_ip[event["source_ip"]].append(
                (_event_timestamp(event), event["username"])
            )

    alerts = []
    window = timedelta(minutes=window_minutes)
    for source_ip, failures in failures_by_ip.items():
        failures.sort()
        start = 0
        best_usernames: set[str] = set()
        best_window = (failures[0][0], failures[0][0])
        best_attempts = 0

        for end, (timestamp, _) in enumerate(failures):
            while timestamp - failures[start][0] > window:
                start += 1
            usernames = {username for _, username in failures[start : end + 1]}
            if len(usernames) > len(best_usernames):
                best_usernames = usernames
                best_window = (failures[start][0], timestamp)
                best_attempts = end - start + 1

        if len(best_usernames) >= username_threshold:
            alerts.append(
                {
                    "rule": "password_spraying",
                    "severity": "high",
                    "source_ip": source_ip,
                    "unique_usernames": len(best_usernames),
                    "failed_attempts": best_attempts,
                    "window_start": best_window[0].isoformat(),
                    "window_end": best_window[1].isoformat(),
                    "summary": (
                        f"{source_ip} failed authentication against "
                        f"{len(best_usernames)} usernames within "
                        f"{window_minutes} minutes"
                    ),
                }
            )
    return alerts


def detect_firewall_port_sweeps(
    events: list[dict[str, Any]],
    port_threshold: int = 10,
    window_minutes: int = 5,
) -> list[dict[str, Any]]:
    """Detect a source denied access to many distinct destination ports."""
    attempts_by_ip: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    for event in events:
        if event.get("event_type") != "firewall_connection":
            continue
        if event.get("outcome") not in {"denied", "blocked"}:
            continue
        attempts_by_ip[event["source_ip"]].append(
            (_event_timestamp(event), int(event["destination_port"]))
        )

    alerts = []
    window = timedelta(minutes=window_minutes)
    for source_ip, attempts in attempts_by_ip.items():
        attempts.sort()
        start = 0
        best_ports: set[int] = set()
        best_window = (attempts[0][0], attempts[0][0])

        for end, (timestamp, _) in enumerate(attempts):
            while timestamp - attempts[start][0] > window:
                start += 1
            ports = {port for _, port in attempts[start : end + 1]}
            if len(ports) > len(best_ports):
                best_ports = ports
                best_window = (attempts[start][0], timestamp)

        if len(best_ports) >= port_threshold:
            alerts.append(
                {
                    "rule": "firewall_port_sweep",
                    "severity": "medium",
                    "source_ip": source_ip,
                    "unique_destination_ports": len(best_ports),
                    "window_start": best_window[0].isoformat(),
                    "window_end": best_window[1].isoformat(),
                    "summary": (
                        f"{source_ip} was denied on {len(best_ports)} distinct "
                        f"destination ports within {window_minutes} minutes"
                    ),
                }
            )
    return alerts


def detect_encoded_powershell(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag PowerShell process events using an encoded-command switch."""
    encoded_command = re.compile(r"(?:^|\s)-(?:enc|encodedcommand)(?:\s|:|$)", re.I)
    alerts = []
    for event in events:
        if event.get("event_type") != "process_creation":
            continue

        process_name = event.get("process_name", "").lower()
        command_line = event.get("command_line", "")
        if "powershell" not in process_name and "pwsh" not in process_name:
            continue
        if not encoded_command.search(command_line):
            continue

        alerts.append(
            {
                "rule": "encoded_powershell_command",
                "severity": "high",
                "hostname": event.get("hostname", "unknown"),
                "username": event.get("username", "unknown"),
                "timestamp": event["timestamp"],
                "summary": (
                    "PowerShell started with an encoded-command argument"
                ),
            }
        )
    return alerts


def detect_all_rules(
    events: list[dict[str, Any]],
    threshold: int = 5,
    window_minutes: int = 10,
    success_window_minutes: int = 5,
) -> list[dict[str, Any]]:
    """Run all portfolio detection rules against normalized events."""
    alerts = detect_brute_force(
        events,
        threshold=threshold,
        window_minutes=window_minutes,
        include_success_correlation=False,
    )
    alerts.extend(
        detect_success_after_failures(
            events, threshold, window_minutes, success_window_minutes
        )
    )
    alerts.extend(
        detect_password_spraying(events, threshold, window_minutes)
    )
    alerts.extend(
        detect_firewall_port_sweeps(events, threshold * 2, window_minutes)
    )
    alerts.extend(detect_encoded_powershell(events))
    return alerts