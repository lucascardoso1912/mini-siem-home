# SOC Home Lab

A local, reproducible mini SOC for practicing event generation and normalization, deterministic detection rules, persistence, alert monitoring and analyst triage. The interface and rules work on local data only; the simulator creates synthetic records and generates no network traffic.

## Architecture

`simulator -> JSONL -> CLI/rules -> SQLite <-> FastAPI <-> static frontend`

The frontend in `frontend/` only consumes the HTTP API; the FastAPI backend reads and writes `data/soc_lab.sqlite` and also serves the static files from the same origin. No Node.js or build step is required. Generated events and alerts are runtime data ignored by Git; the versioned sample events are synthetic.

## Dashboard screenshots

![SOC dashboard overview with lab metrics](docs/screenshots/soc-dashboard.png)

![Synthetic alert queue with severity and triage status](docs/screenshots/alert-queue.png)

## Detection rules

| Rule | Default condition | Severity |
| --- | --- | --- |
| `multiple_failed_logins` | 5 failed logins from the same IP within 10 minutes | medium |
| `successful_login_after_failures` | 5 failures for the same IP/account followed by a success within 5 minutes | high |
| `password_spraying` | Failures against 5 distinct accounts from the same IP within 10 minutes | high |
| `firewall_port_sweep` | Denied connections to 10 distinct ports within 10 minutes | medium |
| `encoded_powershell_command` | PowerShell process creation with an encoded-command argument | high |

These rules classify the supplied events; on their own they do not confirm a real incident.

## Setup and usage

Requires Python 3.10 or later. FastAPI and Uvicorn are runtime dependencies; the first install needs access to the Python package index.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Generate the data and analyze it, saving the run to SQLite:

```bash
.venv/bin/python -m soc_lab.simulator --scenario full-suite --seed 42
.venv/bin/python -m soc_lab.cli --input data/generated_events.jsonl
```

Start the API and the interface:

```bash
.venv/bin/python -m uvicorn soc_lab.api:app --host 127.0.0.1 --port 8000 --limit-concurrency 50 --backlog 128 --timeout-keep-alive 5
```

Open `http://127.0.0.1:8000` for the console and `http://127.0.0.1:8000/docs` for the interactive API documentation. The dashboard shows metrics, filters alerts, displays evidence, and lets you change the triage status and save analyst notes. Use `--output` in the simulator and `--db` in the CLI to change destinations. The same simulator seed reproduces the same events.

Main endpoints: `GET /api/health`, `GET /api/overview`, `GET /api/runs`, `GET /api/alerts`, `GET /api/events` and `PATCH /api/alerts/{alert_id}/triage`.

## Scenarios

`normal`, `brute-force`, `compromised`, `password-spray`, `port-scan`, `encoded-powershell` and `full-suite`. IP addresses come from ranges reserved for documentation. The simulator does not run PowerShell, does not test passwords and does not connect to any host.

To analyze your own JSONL, each line must be an object with a `timestamp` that includes a time zone. Additional fields depend on the event type: authentication uses `source_ip`, `username` and `outcome`; firewall uses `source_ip`, `destination_port` and `outcome`; process creation uses `process_name` and `command_line`.

## Synthetic incident report

See [docs/incident-triage.md](docs/incident-triage.md) and its [PDF version](docs/reports/incident-triage-001.pdf). It documents the `compromised` scenario with seed `2026`, is marked as simulated, and walks through evidence, decision and next investigation steps; no real systems or accounts were involved.

To regenerate the PDF, install the optional reporting dependency and run:

```bash
.venv/bin/python -m pip install -r requirements-report.txt
.venv/bin/python scripts/export_incident_report.py
```

The file is written to `docs/reports/incident-triage-001.pdf`.

## API security and deployment scope

The default configuration is meant for a local lab: it binds to `127.0.0.1`, accepts only the `127.0.0.1` and `localhost` hosts, limits reads to 120 requests/minute per IP, writes to 20/minute per IP and the total to 600/minute per process. HTTP bodies are capped at 64 KiB; pagination parameters and IDs have bounded size/format; security headers and a same-origin CSP for the frontend are added to responses. SQLite queries are parameterized, and the triage model rejects unexpected fields.

The Uvicorn command limits the server to 50 concurrent connections and cuts keep-alive to 5 seconds. These controls complement the application rate limit; they are not protection against distributed DDoS.

The in-memory limits are deliberately local to one process: restarting the API resets the windows, and multiple workers do not share counters. Values can be tuned with `SOC_API_RATE_PER_MINUTE`, `SOC_API_WRITE_RATE_PER_MINUTE`, `SOC_API_GLOBAL_RATE_PER_MINUTE`, `SOC_API_MAX_BODY_BYTES` and `SOC_ALLOWED_HOSTS` (comma-separated list). The service does not trust `X-Forwarded-For`; behind a proxy, configure the trusted proxy correctly before relying on client identity.

There is no user authentication or authorization. **Do not expose this API publicly or use it for real telemetry as-is.** A public deployment needs authentication/authorization, TLS, a reverse proxy with shared rate limiting (for example, Redis), connection/concurrency limits, durable managed storage and a reviewed secret-management setup. SQLite data, generated JSONL, virtual environments and `.env` files are excluded from Git.

## Limitations and next steps

This is not a full SIEM: it does not yet collect Windows Event Logs, syslog or firewall logs from real hosts, does not parse live network traffic, and does not replace tools such as Splunk or Elastic. To integrate a VM, normalize its logs to the JSONL schema and use only machines and networks you control. See [docs/roadmap.md](docs/roadmap.md) for the evolution notes.

Do not publish real logs, credentials, tokens, database dumps or personal data. Triage is manual: the lab does not block accounts or run automated responses.
