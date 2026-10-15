"""Command-line entry point for the local SOC lab."""

import argparse
import json
from pathlib import Path
from typing import Any

from soc_lab.rules import detect_all_rules
from soc_lab.storage import LabStore


def load_events(path: Path) -> list[dict[str, Any]]:
    events = []
    with path.open(encoding="utf-8") as event_file:
        for line_number, line in enumerate(event_file, start=1):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(f"invalid JSON on line {line_number}") from error
    return events


def main() -> None:
    default_input = Path(__file__).parent.parent / "data" / "auth_events.jsonl"
    default_db = Path(__file__).parent.parent / "data" / "soc_lab.sqlite"
    parser = argparse.ArgumentParser(description="Analyze local authentication logs")
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--threshold", type=int, default=5)
    parser.add_argument("--window-minutes", type=int, default=10)
    parser.add_argument("--success-window-minutes", type=int, default=5)
    parser.add_argument("--scenario", help="Label this analysis run")
    parser.add_argument("--db", type=Path, default=default_db)
    args = parser.parse_args()

    events = load_events(args.input)
    alerts = detect_all_rules(
        events,
        threshold=args.threshold,
        window_minutes=args.window_minutes,
        success_window_minutes=args.success_window_minutes,
    )
    scenario = args.scenario or (events[0].get("scenario", "file-import") if events else "file-import")
    run_id = LabStore(args.db).save_run(events, alerts, scenario)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "scenario": scenario,
                "events_analyzed": len(events),
                "alerts_created": len(alerts),
                "alerts": alerts,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
