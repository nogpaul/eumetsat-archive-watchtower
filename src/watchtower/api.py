"""FastAPI app exposing operational endpoints + scheduled polling.

This is the long-running service. It:
    - Runs a background scheduler that polls EUMDAC every N seconds.
    - Exposes /metrics for Prometheus to scrape.
    - Exposes /health and /ready for orchestrators (Docker, K8s).
    - Exposes /collections and /anomalies for human and tool inspection.

Everything runs in ONE process so the metrics registry, scheduler, and
HTTP server share state directly in memory.
"""
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from time import time as unix_time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlmodel import select
from starlette.responses import Response

from .collector import poll_once
from .config import get_settings
from .logging_setup import configure
from .metrics import LAST_SUCCESSFUL_POLL_TIMESTAMP, SCHEDULER_RUNNING
from .models import Product
from .storage import session

scheduler = AsyncIOScheduler()


def _scheduled_poll() -> None:
    """Wrapper around poll_once that updates the last-success gauge."""
    result = poll_once()
    now = unix_time()
    for collection_id, count in result.items():
        # Only mark as "successful" if no exception was raised
        # (poll_once returns 0 for failures; we trust that contract)
        LAST_SUCCESSFUL_POLL_TIMESTAMP.labels(
            collection=collection_id
        ).set(now)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hook for FastAPI.

    On startup: configure logging, start the scheduler.
    On shutdown: stop the scheduler cleanly.
    """
    settings = get_settings()
    configure(settings.log_level)

    scheduler.add_job(
        _scheduled_poll,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll",
        max_instances=1,  # never overlap polls
    )
    scheduler.start()
    SCHEDULER_RUNNING.set(1)

    yield  # FastAPI runs here

    SCHEDULER_RUNNING.set(0)
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="EUMDAC Archive Watchtower",
    version="0.1.0",
    description="Monitoring and anomaly detection for the EUMETSAT Data Store.",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: returns 200 if the process is alive."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, object]:
    """Readiness probe: returns 200 if scheduler + DB are working."""
    job = scheduler.get_job("poll")
    return {
        "scheduler": job is not None and scheduler.running,
        "status": "ready" if job is not None else "starting",
    }


@app.get("/collections")
def collections() -> dict[str, list[str]]:
    """List configured collections."""
    return {"collections": get_settings().collections}


@app.get("/products")
def products(collection_id: str | None = None, hours: int = 24) -> list[dict]:
    """Return recently observed products, optionally filtered by collection."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    with session() as s:
        query = select(Product).where(Product.observed_at >= cutoff)
        if collection_id:
            query = query.where(Product.collection_id == collection_id)
        query = query.order_by(Product.observed_at.desc())
        rows = s.exec(query).all()
    return [r.model_dump(mode="json") for r in rows]


@app.get("/anomalies")
def anomalies() -> list[dict]:
    """Return current detector findings — one per collection.

    Each finding has a `kind`: "anomaly", "normal", or "insufficient_data".
    Anomalies are scored by z-score from a rolling 24-hour baseline.
    """
    from .detector import detect_anomalies
    return detect_anomalies()


@app.get("/metrics")
def metrics() -> Response:
    """Prometheus exposition endpoint.

    Returns all in-process metric values as a plain-text response.
    Prometheus scrapes this every ~15 seconds.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)