"""Unit tests for the anomaly detector."""
from datetime import UTC, datetime, timedelta

from sqlmodel import select

from watchtower.detector import (
    MIN_SAMPLES,
    Z_THRESHOLD,
    detect_anomalies,
)
from watchtower.models import Product
from watchtower.storage import session


def _insert_products_with_latencies(latencies, collection_id="TEST:COLL_A"):
    """Persist products. The LAST item in `latencies` is the most recent."""
    now = datetime.now(UTC)
    n = len(latencies)
    with session() as s:
        for i, lat in enumerate(latencies):
            s.add(Product(
                collection_id=collection_id,
                product_id=f"FAKE_{collection_id}_{i:04d}",
                sensing_start=now - timedelta(minutes=15),
                sensing_end=now - timedelta(minutes=10),
                ingested=now - timedelta(minutes=10) + timedelta(seconds=lat),
                publication_latency_seconds=lat,
                observed_at=now - timedelta(minutes=(n - i)),
            ))
        s.commit()


def test_returns_insufficient_data_when_too_few_samples(fake_env, in_memory_db):
    """With fewer than MIN_SAMPLES samples, return insufficient_data."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    _insert_products_with_latencies([40.0] * 10)  # only 10 samples

    findings = detect_anomalies()

    assert len(findings) == 1
    assert findings[0]["collection_id"] == "TEST:COLL_A"
    assert findings[0]["kind"] == "insufficient_data"
    assert findings[0]["samples"] == 10
    assert findings[0]["needed"] == MIN_SAMPLES


def test_classifies_typical_value_as_normal(fake_env, in_memory_db):
    """When the latest latency is close to the mean, kind is 'normal'."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    # 40 historical products around 40s, then one more at 42s (typical)
    historical = [40.0 + (i % 5) - 2 for i in range(40)]  # ~40s ± 2s
    _insert_products_with_latencies(historical + [42.0])

    findings = detect_anomalies()

    assert findings[0]["kind"] == "normal"
    assert abs(findings[0]["z_score"]) < Z_THRESHOLD


def test_classifies_extreme_value_as_anomaly(fake_env, in_memory_db):
    """When the latest latency is far from the mean, kind is 'anomaly'."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    # 40 historical products around 40s, then one HUGE outlier
    historical = [40.0 + (i % 5) - 2 for i in range(40)]
    _insert_products_with_latencies(historical + [500.0])  # massive spike

    findings = detect_anomalies()

    assert findings[0]["kind"] == "anomaly"
    assert abs(findings[0]["z_score"]) >= Z_THRESHOLD
    assert findings[0]["latency_seconds"] == 500.0


def test_returns_one_finding_per_collection(fake_env, in_memory_db):
    """Each configured collection gets exactly one finding."""
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A,TEST:COLL_B")
    _insert_products_with_latencies([40.0] * 10, collection_id="TEST:COLL_A")
    # COLL_B has zero samples — should still appear in output

    findings = detect_anomalies()

    assert len(findings) == 2
    collections = {f["collection_id"] for f in findings}
    assert collections == {"TEST:COLL_A", "TEST:COLL_B"}


def test_baseline_excludes_the_latest_value(fake_env, in_memory_db):
    """The latest measurement should not be part of its own baseline.

    Concrete check: if the baseline (without latest) has stdev = 0
    and the latest equals the baseline mean, z must be 0 (the
    sigma=1e-9 guard kicks in but latest - mean = 0 → z = 0).
    """
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    # 40 historical at exactly 40s, latest also 40s
    _insert_products_with_latencies([40.0] * 41)

    findings = detect_anomalies()

    assert findings[0]["kind"] == "normal"
    assert findings[0]["z_score"] == 0.0