"""Simple detections for authentication events."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any


def _parse_timestamp(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return timestamp


def detect_brute_force(
    events: list[dict[str, Any]],
    threshold: int = 5,
    window_minutes: int = 10,
    success_window_minutes: int = 5,
    include_success_correlation: bool = True,
) -> list[dict[str, Any]]:
    """Detect repeated failures and correlate them with a subsequent login."""
    if threshold < 1 or window_minutes < 1 or success_window_minutes < 1:
        raise ValueError("threshold and time windows must be positive")

    failures_by_ip: dict[str, list[datetime]] = defaultdict(list)
    failures_by_account: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    successes_by_account: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for event in events:
        outcome = event.get("outcome")
        if outcome not in {"failure", "success"}:
            continue

        source_ip = event["source_ip"]
        username = event["username"]
        timestamp = _parse_timestamp(event["timestamp"])
        account = (source_ip, username)
        if outcome == "failure":
            failures_by_ip[source_ip].append(timestamp)
            failures_by_account[account].append(timestamp)
        else:
            successes_by_account[account].append(timestamp)

    if not include_success_correlation:
        successes_by_account.clear()

    correlation_window = timedelta(minutes=success_window_minutes)
    correlated_by_ip: dict[str, dict[str, Any]] = {}
    for (source_ip, username), timestamps in failures_by_account.items():
        timestamps.sort()
        successes = sorted(successes_by_account[(source_ip, username)])
        start = 0

        for end, timestamp in enumerate(timestamps):
            while timestamp - timestamps[start] > timedelta(minutes=window_minutes):
                start += 1
            count = end - start + 1
            if count < threshold:
                continue

            for success_timestamp in successes:
                if success_timestamp <= timestamp:
                    continue
                if success_timestamp - timestamp > correlation_window:
                    break

                existing = correlated_by_ip.get(source_ip)
                if existing is None or count > existing["failed_attempts"]:
                    correlated_by_ip[source_ip] = {
                        "username": username,
                        "failed_attempts": count,
                        "window_start": timestamps[start].isoformat(),
                        "window_end": timestamp.isoformat(),
                        "success_timestamp": success_timestamp.isoformat(),
                    }
                break

    alerts = []
    window = timedelta(minutes=window_minutes)
    for source_ip, timestamps in failures_by_ip.items():
        timestamps.sort()
        start = 0
        max_count = 0
        max_window = (timestamps[0], timestamps[0])

        for end, timestamp in enumerate(timestamps):
            while timestamp - timestamps[start] > window:
                start += 1
            count = end - start + 1
            if count > max_count:
                max_count = count
                max_window = (timestamps[start], timestamp)

        if max_count < threshold:
            continue

        alert: dict[str, Any] = {
            "rule": "multiple_failed_logins",
            "severity": "medium",
            "source_ip": source_ip,
            "failed_attempts": max_count,
            "window_start": max_window[0].isoformat(),
            "window_end": max_window[1].isoformat(),
            "summary": (
                f"{max_count} failed logins from {source_ip} "
                f"within {window_minutes} minutes"
            ),
        }

        correlation = correlated_by_ip.get(source_ip)
        if correlation is not None:
            alert.update(
                {
                    "severity": "high",
                    "username": correlation["username"],
                    "failed_attempts": correlation["failed_attempts"],
                    "window_start": correlation["window_start"],
                    "window_end": correlation["window_end"],
                    "correlated_success_at": correlation["success_timestamp"],
                    "summary": (
                        f"Successful login for {correlation['username']} from "
                        f"{source_ip} occurred within {success_window_minutes} "
                        f"minutes after {correlation['failed_attempts']} "
                        f"failed attempts"
                    ),
                }
            )
        alerts.append(alert)

    return alerts
