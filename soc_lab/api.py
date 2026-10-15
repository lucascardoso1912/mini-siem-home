"""FastAPI backend for the SOC lab interface."""

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Path as ApiPath, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from soc_lab.security import ApiProtectionMiddleware
from soc_lab.storage import LabStore

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("SOC_LAB_DB", ROOT / "data" / "soc_lab.sqlite"))
store = LabStore(DB_PATH)


def _positive_setting(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


app = FastAPI(
    title="Local SOC API",
    description="Local alert, event, and analyst-triage API for the home lab.",
    version="1.0.0",
)
allowed_hosts = [
    host.strip()
    for host in os.environ.get("SOC_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]
if not allowed_hosts:
    raise ValueError("SOC_ALLOWED_HOSTS must contain at least one host")
app.add_middleware(
    ApiProtectionMiddleware,
    requests_per_minute=_positive_setting("SOC_API_RATE_PER_MINUTE", 120),
    writes_per_minute=_positive_setting("SOC_API_WRITE_RATE_PER_MINUTE", 20),
    global_requests_per_minute=_positive_setting("SOC_API_GLOBAL_RATE_PER_MINUTE", 600),
    max_body_bytes=_positive_setting("SOC_API_MAX_BODY_BYTES", 65_536),
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


class TriageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["open", "investigating", "closed"]
    analyst_notes: str = Field(default="", max_length=5000)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict:
    return store.get_metrics()


@app.get("/api/runs")
def runs(limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    return store.list_runs(limit)


@app.get("/api/alerts")
def alerts(
    status: Literal["open", "investigating", "closed"] | None = None,
    severity: Literal["high", "medium", "low"] | None = None,
    run_id: str | None = Query(
        default=None,
        min_length=32,
        max_length=32,
        pattern=r"^[a-f0-9]{32}$",
    ),
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[dict]:
    return store.list_alerts(
        status=status,
        severity=severity,
        run_id=run_id,
        limit=limit,
    )


@app.get("/api/alerts/{alert_id}")
def alert_detail(
    alert_id: str = ApiPath(
        min_length=32,
        max_length=32,
        pattern=r"^[a-f0-9]{32}$",
    ),
) -> dict:
    alert = store.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@app.patch("/api/alerts/{alert_id}/triage")
def update_alert_triage(
    update: TriageUpdate,
    alert_id: str = ApiPath(
        min_length=32,
        max_length=32,
        pattern=r"^[a-f0-9]{32}$",
    ),
) -> dict[str, str]:
    if store.get_alert(alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    store.update_triage(alert_id, update.status, update.analyst_notes)
    return {"alert_id": alert_id, "status": update.status}


@app.get("/api/events")
def events(
    run_id: str | None = Query(
        default=None,
        min_length=32,
        max_length=32,
        pattern=r"^[a-f0-9]{32}$",
    ),
    limit: int = Query(default=500, ge=1, le=1000),
) -> list[dict]:
    return store.list_events(run_id=run_id, limit=limit)


app.mount(
    "/",
    StaticFiles(directory=ROOT / "frontend", html=True),
    name="frontend",
)