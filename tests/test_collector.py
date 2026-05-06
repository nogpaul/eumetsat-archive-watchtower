"""Unit + integration tests for collector.py — the orchestration layer.

We use a FakeEumdacClient (defined in conftest.py) to inject deterministic
behaviour without hitting EUMETSAT. The collector's public contract:

    poll_once(client) -> dict[str, int]

is exercised end-to-end against an in-memory SQLite database.
"""
"""Unit + integration tests for collector.py — the orchestration layer."""
from datetime import UTC, datetime

from sqlmodel import select

from watchtower.collector import poll_once
from watchtower.models import Product
from watchtower.storage import session


def test_poll_once_computes_publication_latency_correctly(
    fake_env, in_memory_db, make_product, fake_client_factory
):
    """Latency = ingested - sensing_end, in seconds."""
    # Arrange
    fake_product = make_product(
        collection_id="TEST:COLL_A",
        product_id="LATENCY_TEST_001",
        sensing_end=datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC),
        ingested=datetime(2026, 5, 5, 8, 13, 0, tzinfo=UTC),  # +60s
    )
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    fake_client = fake_client_factory(products=[fake_product])

    # Act
    poll_once(client=fake_client)

    # Assert
    with session() as s:
        rows = s.exec(select(Product)).all()
    assert len(rows) == 1
    assert rows[0].publication_latency_seconds == 60.0


def test_poll_once_is_idempotent(
    fake_env, in_memory_db, make_product, fake_client_factory
):
    """Re-running poll_once with the same data yields zero new products."""
    fake_product = make_product(product_id="IDEMPOTENT_TEST_001")
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    fake_client = fake_client_factory(products=[fake_product])

    first_run = poll_once(client=fake_client)
    second_run = poll_once(client=fake_client)

    assert first_run == {"TEST:COLL_A": 1}
    assert second_run == {"TEST:COLL_A": 0}

    with session() as s:
        rows = s.exec(select(Product)).all()
    assert len(rows) == 1


def test_poll_once_isolates_per_collection_failures(
    fake_env, in_memory_db, make_product, fake_client_factory
):
    """If one collection raises, other collections still get processed."""
    good_product = make_product(
        collection_id="TEST:COLL_A", product_id="GOOD_001"
    )
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A,TEST:COLL_B")
    fake_client = fake_client_factory(
        products=[good_product],
        raise_on="TEST:COLL_B",
    )

    result = poll_once(client=fake_client)

    assert result["TEST:COLL_A"] == 1
    assert result["TEST:COLL_B"] == 0

    with session() as s:
        rows = s.exec(select(Product)).all()
    assert len(rows) == 1
    assert rows[0].collection_id == "TEST:COLL_A"


def test_poll_once_handles_missing_ingested_gracefully(
    fake_env, in_memory_db, make_product, fake_client_factory
):
    """If a product lacks `ingested`, latency is None — no crash."""
    fake_product = make_product(product_id="NO_INGESTED_001", ingested=None)
    fake_env.setenv("WATCHTOWER_COLLECTIONS", "TEST:COLL_A")
    fake_client = fake_client_factory(products=[fake_product])

    poll_once(client=fake_client)

    with session() as s:
        rows = s.exec(select(Product)).all()
    assert len(rows) == 1
    assert rows[0].publication_latency_seconds is None