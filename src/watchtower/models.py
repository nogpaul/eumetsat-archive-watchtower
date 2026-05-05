"""Database models for the watchtower.

Uses SQLModel, which combines SQLAlchemy (the SQL layer) with Pydantic
(the validation layer). One class definition gives us both a database
table AND a validated Python object. Less boilerplate, fewer bugs.
"""
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    """One row per EUMETSAT Data Store product seen by the collector.

    The (collection_id, product_id) pair uniquely identifies a product
    in the EUMETSAT catalog. We use an auto-incrementing surrogate
    integer `id` as the primary key, and a UNIQUE constraint on
    `product_id` to prevent duplicate ingestion.
    """

    # Surrogate primary key
    id: int | None = Field(default=None, primary_key=True)

    # The EUMETSAT-defined identifiers
    collection_id: str = Field(index=True)
    product_id: str = Field(index=True, unique=True)

    # Timestamps from EUMDAC
    sensing_start: datetime
    sensing_end: datetime
    ingested: datetime | None = None

    # Our own observability metadata
    observed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        index=True,
    )

    # Pre-computed value used by the anomaly detector
    publication_latency_seconds: float | None = None