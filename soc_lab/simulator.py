"""Generate reproducible synthetic authentication events for the lab."""

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCENARIOS = (
    "normal",
    "brute-force",
    "compromised",
    "password-spray",
    "port-scan",
    "encoded-powershell",
    "full-suite",
)
DEFAULT_START = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)


def generate_events(
    scenario: str,
    seed: int = 42,
    start: datetime | None = None,
) -> list[dict[str, str]]:
    """Generate timestamped events without interacting with any network."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of: {', '.join(SCENARIOS)}")

    start = start or DEFAULT_START
    if start.tzinfo is None:
        raise ValueError("start must include a timezone")

    generator = random.Random(seed)
    events: list[dict[str, str]] = []
    source_ips = ["192.0.2.15", "198.51.100.8", "198.51.100.23"]
    usernames = ["ana", "lucas", "marina"]

    for minute in range(0, 20, 2):
        outcome = "failure" if minute in {4, 18} else "success"
        events.append(
            {
                "timestamp": (start + timedelta(minutes=minute)).isoformat(),
                "source_ip": generator.choice(source_ips),
                "username": generator.choice(usernames),
                "outcome": outcome,
                "event_type": "authentication",
                "hostname": "auth-server-01",
            }
        )

    if scenario in {"brute-force", "compromised", "full-suite"}:
        incident_start = start + timedelta(minutes=30)
        for minute in range(5):
            events.append(
                {
                    "timestamp": (incident_start + timedelta(minutes=minute)).isoformat(),
                    "source_ip": "203.0.113.66",
                    "username": "admin",
                    "outcome": "failure",
                    "event_type": "authentication",
                    "hostname": "auth-server-01",
                }
            )

        if scenario in {"compromised", "full-suite"}:
            events.append(
                {
                    "timestamp": (incident_start + timedelta(minutes=5)).isoformat(),
                    "source_ip": "203.0.113.66",
                    "username": "admin",
                    "outcome": "success",
                    "event_type": "authentication",
                    "hostname": "auth-server-01",
                }
            )

    if scenario in {"password-spray", "full-suite"}:
        for minute in range(5):
            events.append(
                {
                    "timestamp": (start + timedelta(minutes=40 + minute)).isoformat(),
                    "source_ip": "203.0.113.67",
                    "username": f"user-{minute + 1}",
                    "outcome": "failure",
                    "event_type": "authentication",
                    "hostname": "auth-server-01",
                }
            )

    if scenario in {"port-scan", "full-suite"}:
        for port_offset in range(10):
            events.append(
                {
                    "timestamp": (
                        start + timedelta(minutes=50 + port_offset // 2)
                    ).isoformat(),
                    "source_ip": "203.0.113.68",
                    "destination_ip": "192.0.2.10",
                    "destination_port": str(8000 + port_offset),
                    "outcome": "denied",
                    "event_type": "firewall_connection",
                    "hostname": "edge-firewall-01",
                }
            )

    if scenario in {"encoded-powershell", "full-suite"}:
        events.append(
            {
                "timestamp": (start + timedelta(minutes=60)).isoformat(),
                "hostname": "workstation-01",
                "username": "analyst",
                "process_name": "powershell.exe",
                "command_line": "powershell.exe -EncodedCommand ZQBjAGgAbwA=",
                "event_type": "process_creation",
            }
        )

    events.sort(key=lambda event: event["timestamp"])
    for event_number, event in enumerate(events, start=1):
        event["event_id"] = f"evt-{event_number:04d}"
        event["scenario"] = scenario

    return events


def main() -> None:
    default_output = Path(__file__).parent.parent / "data" / "generated_events.jsonl"
    parser = argparse.ArgumentParser(description="Generate synthetic SOC lab events")
    parser.add_argument("--scenario", choices=SCENARIOS, default="normal")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()

    events = generate_events(args.scenario, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as event_file:
        for event in events:
            event_file.write(json.dumps(event, sort_keys=True) + "\n")

    print(f"Generated {len(events)} events for '{args.scenario}' in {args.output}")


if __name__ == "__main__":
    main()