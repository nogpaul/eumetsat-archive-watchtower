"""Integration tests for storage.py — the database layer.

These are 'integration' tests because they exercise a real database
(in-memory SQLite). They confirm that:
    - tables get created
    - Product objects round-trip through the DB
    - the UNIQUE constraint on product_id is enforced
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from watchtower.models import Product
from watchtower.storage import session


def test_can_insert_and_read_back_a_product(in_memory_db):
    """A Product round-trips correctly through the database."""
    # Arrange
    product = Product(
        collection_id="TEST:COLL_A",
        product_id="TEST_PROD_001",
        sensing_start=datetime(2026, 5, 5, 8, 0, 0, tzinfo=UTC),
        sensing_end=datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC),
        ingested=datetime(2026, 5, 5, 8, 13, 0, tzinfo=UTC),
        publication_latency_seconds=60.0,
    )

    # Act
    with session() as s:
        s.add(product)
        s.commit()

    with session() as s:
        rows = s.exec(select(Product)).all()

    # Assert
    assert len(rows) == 1
    assert rows[0].product_id == "TEST_PROD_001"
    assert rows[0].publication_latency_seconds == 60.0
    assert rows[0].id is not None  # DB assigned a primary key


def test_duplicate_product_id_raises_integrity_error(in_memory_db):
    """The UNIQUE constraint on product_id prevents duplicate inserts."""
    # Arrange
    base_kwargs = dict(
        collection_id="TEST:COLL_A",
        product_id="DUPLICATE_ID",
        sensing_start=datetime(2026, 5, 5, 8, 0, 0, tzinfo=UTC),
        sensing_end=datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC),
        ingested=datetime(2026, 5, 5, 8, 13, 0, tzinfo=UTC),
    )

    # Act: first insert succeeds
    with session() as s:
        s.add(Product(**base_kwargs))
        s.commit()

    # Assert: second insert with the same product_id fails
    with pytest.raises(IntegrityError):
        with session() as s:
            s.add(Product(**base_kwargs))
            s.commit()


def test_observed_at_default_is_per_instance(in_memory_db):
    """Two products created seconds apart have different observed_at timestamps."""
    # Arrange & Act
    p1 = Product(
        collection_id="TEST:COLL_A",
        product_id="P1",
        sensing_start=datetime(2026, 5, 5, 8, 0, 0, tzinfo=UTC),
        sensing_end=datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC),
    )
    # Tiny delay to ensure timestamps differ
    import time; time.sleep(0.01)
    p2 = Product(
        collection_id="TEST:COLL_A",
        product_id="P2",
        sensing_start=datetime(2026, 5, 5, 8, 0, 0, tzinfo=UTC),
        sensing_end=datetime(2026, 5, 5, 8, 12, 0, tzinfo=UTC),
    )

    # Assert: each got its own fresh timestamp (not the class-load timestamp!)
    assert p1.observed_at != p2.observed_at
    assert p2.observed_at > p1.observed_at