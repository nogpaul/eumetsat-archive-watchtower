"""Anomaly detection for publication latency.

Algorithm: rolling-window z-score, computed per collection.

For each configured collection:
    1. Pull the publication latencies observed in the last 24 hours
    2. If too few samples (< MIN_SAMPLES), report "insufficient data"
    3. Otherwise: compute the baseline mean & stdev EXCLUDING the latest
    4. Score the latest product: z = (latest - mean) / stdev
    5. If |z| >= Z_THRESHOLD, emit an anomaly finding

Honest output: the detector tells you what it can and can't say.
"insufficient data" is a valid answer.
"""
from datetime import UTC, datetime, timedelta
from statistics import mean, pstdev

import structlog
from sqlmodel import col, select

from .config import get_settings
from .models import Product
from .storage import session

log = structlog.get_logger()

# Algorithm parameters — exposed for testability and documentation.
WINDOW = timedelta(hours=24)
MIN_SAMPLES = 30  # below this, we can't compute a trustworthy baseline
Z_THRESHOLD = 3.0  # ~99.7% of normal data lies within ±3 stdevs


def detect_anomalies() -> list[dict]:
    """Return one finding per configured collection.

    Returns:
        A list of dicts with keys:
            collection_id, kind, latency_seconds, baseline_mean,
            baseline_stdev, z_score, samples_in_baseline
        `kind` is one of: "anomaly", "normal", "insufficient_data".
    """
    findings: list[dict] = []
    cutoff = datetime.now(UTC) - WINDOW

    for collection_id in get_settings().collections:
        with session() as s:
            rows = s.exec(
                select(Product)
                .where(Product.collection_id == collection_id)
                .where(Product.observed_at >= cutoff)
                .where(col(Product.publication_latency_seconds).is_not(None))
                .order_by(col(Product.observed_at).desc())
            ).all()

        latencies = [r.publication_latency_seconds for r in rows]

        # ── Case 1: insufficient data ─────────────────────────────────
        if len(latencies) < MIN_SAMPLES:
            findings.append({
                "collection_id": collection_id,
                "kind": "insufficient_data",
                "samples": len(latencies),
                "needed": MIN_SAMPLES,
            })
            continue

        # ── Case 2: baseline excludes the latest measurement ──────────
        latest = latencies[0]              # rows ordered .desc(), so [0] is most recent
        baseline = latencies[1:]            # everything except the latest

        mu = mean(baseline)
        sigma = pstdev(baseline)
        if sigma == 0:
            # Edge case: all baseline values identical. Avoid div-by-zero.
            # If sigma is 0 and latest != mu, that's noteworthy in itself.
            sigma = 1e-9

        z = (latest - mu) / sigma

        # ── Case 3: classify ──────────────────────────────────────────
        finding = {
            "collection_id": collection_id,
            "latency_seconds": round(latest, 2),
            "baseline_mean": round(mu, 2),
            "baseline_stdev": round(sigma, 2),
            "z_score": round(z, 2),
            "samples_in_baseline": len(baseline),
        }

        if abs(z) >= Z_THRESHOLD:
            finding["kind"] = "anomaly"
            log.warning(
                "detector.anomaly",
                collection=collection_id,
                z_score=z,
                latency_seconds=latest,
                baseline_mean=mu,
            )
        else:
            finding["kind"] = "normal"

        findings.append(finding)

    return findings