"""Prometheus metrics for the watchtower.

Design principles:
    - Low-cardinality labels only (collection, error_type — never product_id)
    - Counter for things that monotonically increase
    - Histogram for distributions of measurements
    - Gauge for current-state values
    - Suffix counters with `_total` (Prometheus convention)
    - Suffix duration histograms with `_seconds` (Prometheus convention)
    - Prefix everything with `sentinel_` to namespace our metrics
"""
from prometheus_client import Counter, Gauge, Histogram


# ──────────────────────────────────────────────────────────────────────
# Volume of work done (Counters)
# ──────────────────────────────────────────────────────────────────────

PRODUCTS_OBSERVED = Counter(
    "sentinel_products_observed_total",
    "New products observed by the collector since process start.",
    ["collection"],
)

POLLS_TOTAL = Counter(
    "sentinel_polls_total",
    "Total polling cycles attempted, by collection and outcome.",
    ["collection", "outcome"],  # outcome: "success" | "failure"
)


# ──────────────────────────────────────────────────────────────────────
# Failures (Counter)
# ──────────────────────────────────────────────────────────────────────

POLL_FAILURES = Counter(
    "sentinel_poll_failures_total",
    "Polling failures, sliced by collection and error type.",
    ["collection", "error_type"],
)


# ──────────────────────────────────────────────────────────────────────
# Speed of work (Histograms)
# ──────────────────────────────────────────────────────────────────────

POLL_DURATION = Histogram(
    "sentinel_poll_duration_seconds",
    "Time taken to complete one collection's poll.",
    ["collection"],
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 300),
)

PUBLICATION_LATENCY = Histogram(
    "sentinel_publication_latency_seconds",
    "Publication latency: time from sensing_end to ingested.",
    ["collection"],
    # Buckets sized for both fast (MSG ~30-50s) and slow (Metop ~30-90 min) collections
    buckets=(60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400),
)


# ──────────────────────────────────────────────────────────────────────
# State of the system (Gauges)
# ──────────────────────────────────────────────────────────────────────

SCHEDULER_RUNNING = Gauge(
    "sentinel_scheduler_running",
    "1 if the polling scheduler is active, 0 otherwise.",
)

LAST_SUCCESSFUL_POLL_TIMESTAMP = Gauge(
    "sentinel_last_successful_poll_timestamp",
    "Unix timestamp of the last successful poll, per collection.",
    ["collection"],
)