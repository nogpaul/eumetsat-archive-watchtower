"""Shared pytest fixtures for the watchtower test suite."""
from datetime import UTC, datetime
from typing import Any

import pytest


# ──────────────────────────────────────────────────────────────────────
# Environment fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_env(monkeypatch):
    """Set the bare-minimum env vars Settings requires."""
    monkeypatch.setenv("EUMETSAT_CONSUMER_KEY", "fake-key")
    monkeypatch.setenv("EUMETSAT_CONSUMER_SECRET", "fake-secret")
    monkeypatch.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A,TEST:COLL_B")
    return monkeypatch


# ──────────────────────────────────────────────────────────────────────
# Database fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def in_memory_db(monkeypatch, tmp_path):
    """Use a temporary on-disk SQLite database for the test, then discard it."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("WATCHTOWER_DB_URL", db_url)
    from watchtower import config, storage
    config.get_settings.cache_clear()
    storage.get_engine.cache_clear()
    yield db_url
    config.get_settings.cache_clear()
    storage.get_engine.cache_clear()


# ──────────────────────────────────────────────────────────────────────
# Fake EUMDAC client
# ──────────────────────────────────────────────────────────────────────

class FakeEumdacClient:
    """Minimal stand-in for EumdacClient."""

    def __init__(self, products: list[dict[str, Any]] | None = None,
                 raise_on: str | None = None):
        self._products = products or []
        self._raise_on = raise_on

    def list_recent_products(self, collection_id, since=None):
        if collection_id == self._raise_on:
            raise RuntimeError(f"Simulated failure for {collection_id}")
        for product in self._products:
            if product["collection_id"] == collection_id:
                yield product


@pytest.fixture
def fake_client_factory():
    """Factory fixture that builds configured FakeEumdacClient instances."""
    def _make(products=None, raise_on=None):
        return FakeEumdacClient(products=products, raise_on=raise_on)
    return _make


# ──────────────────────────────────────────────────────────────────────
# Product factory fixture
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_product():
    """Factory for building product dicts with sensible defaults.

    Tests just override the fields they care about. The _SENTINEL
    pattern lets callers pass `ingested=None` explicitly to test the
    "missing ingested" case.
    """
    _SENTINEL = object()

    def _make(
        collection_id: str = "TEST:COLL_A",
        product_id: str = "TEST_PROD_001",
        sensing_start=_SENTINEL,
        sensing_end=_SENTINEL,
        ingested=_SENTINEL,
    ) -> dict[str, Any]:
        if sensing_start is _SENTINEL:
            sensing_start = datetime(2026, 5, 5, 8, 0, 0, tzinfo=UTC)
        if sensing_end is _SENTINEL:
            sensing_end = datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC)
        if ingested is _SENTINEL:
            ingested = datetime(2026, 5, 5, 8, 13, 0, tzinfo=UTC)
        return {
            "collection_id": collection_id,
            "product_id": product_id,
            "sensing_start": sensing_start,
            "sensing_end": sensing_end,
            "ingested": ingested,
        }
    return _make