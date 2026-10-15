# Roadmap: From Local Lab to SIEM

## Current project

- Deterministic synthetic JSONL scenarios.
- Five local detection rules.
- SQLite history and analyst status/notes.
- FastAPI JSON API and independent static HTML/CSS/JavaScript frontend.
- Alert queue, event/run views, and analyst triage through the API.
- A clearly labeled synthetic triage write-up.

## Next: authorized host telemetry

1. Create one Linux or Windows VM that you own and keep its networking host-only/internal.
2. Export a small, sanitized sample of its authentication and process events.
3. Write and test a parser that maps those records to the lab's normalized JSON event fields.
4. Record the source type and host name so a triage report can trace each alert to evidence.

## Then: SIEM integration

Choose one SIEM after checking available memory, storage, and whether Docker or a hypervisor is available. Splunk and Elastic are both valid portfolio directions; avoid running multiple stacks at once in a small lab. Document the exact version, setup, data source, and limitations. Do not expose the SIEM or VM services to the public internet.

## GitHub publication checklist

- Include architecture and detection-rule documentation.
- Keep the incident report explicitly labeled synthetic until it is based on logs from a system you control.
- Add screenshots of the dashboard and example detections.
- Keep generated SQLite databases, virtual environments, secrets, and real logs out of Git.
- Explain false-positive cases and how each rule was tested.