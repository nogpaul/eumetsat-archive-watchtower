"""The collector orchestrates one polling cycle.

For each configured collection:
    1. Fetch recent products from EUMDAC
    2. Compute publication latency (ingested - sensing_end)
    3. Insert new products into the database (skip duplicates)
    4. Log structured events for observability

Failures are isolated per-collection: a network blip on one collection
must NEVER take down the polling for the others. This is how we keep a
24/7 monitoring tool alive through transient upstream issues.
"""
from datetime import timedelta

import structlog
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from .config import get_settings
from .eumdac_client import EumdacClient
from .models import Product
from .storage import session

log = structlog.get_logger()

def poll_once() -> dict[str, int]:
    """Run one polling cycle across all configured collections.

    Returns:
        A dict mapping collection_id -> count of newly inserted products.
        Useful for tests, the CLI, and human eyeballing.
    """
    settings = get_settings()
    client = EumdacClient(
        settings.eumetsat_consumer_key,
        settings.eumetsat_consumer_secret,
    )
    new_products_per_collection: dict[str, int] = {}

    for collection_id in settings.collections:
        log.info("collector.poll.start", collection=collection_id)
        new_count = 0

        try:
            for product_dict in client.list_recent_products(
                collection_id,
                since=timedelta(hours=24),
            ):
                # Compute latency if both timestamps are present
                latency = None
                if product_dict["ingested"] and product_dict["sensing_end"]:
                    delta = product_dict["ingested"] - product_dict["sensing_end"]
                    latency = delta.total_seconds()

                # Build the Product model
                product = Product(
                    collection_id=product_dict["collection_id"],
                    product_id=product_dict["product_id"],
                    sensing_start=product_dict["sensing_start"],
                    sensing_end=product_dict["sensing_end"],
                    ingested=product_dict["ingested"],
                    publication_latency_seconds=latency,
                )

                # Insert with idempotency: skip if product_id already exists
                with session() as s:
                    try:
                        s.add(product)
                        s.commit()
                        new_count += 1
                    except IntegrityError:
                        s.rollback()  # release the failed transaction
                        # Already in the database — that's expected, skip it
                        continue

        except Exception as exc:
            # Per-collection isolation: don't let one bad collection
            # take down the others
            log.error(
                "collector.poll.failed",
                collection=collection_id,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            new_products_per_collection[collection_id] = 0
            continue

        new_products_per_collection[collection_id] = new_count
        log.info(
            "collector.poll.complete",
            collection=collection_id,
            new_products=new_count,
        )

    return new_products_per_collection