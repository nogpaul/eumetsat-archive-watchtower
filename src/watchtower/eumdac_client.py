"""EUMDAC client wrapper.

This module is the *only* place in the application that imports `eumdac`.
Everywhere else uses plain dicts returned by this class. That keeps the
EUMDAC dependency at a single boundary -- if EUMDAC changes, only this
file needs updating.
"""
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

import eumdac
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

log = structlog.get_logger()


class EumdacClient:
    """Authenticated client for the EUMETSAT Data Store.

    Acquires an access token lazily on first use and caches the
    DataStore handle for subsequent calls.
    """

    def __init__(self, consumer_key: str, consumer_secret: str) -> None:
        self._credentials = (consumer_key, consumer_secret)
        self._token: eumdac.AccessToken | None = None
        self._datastore: eumdac.DataStore | None = None

    def _ensure(self) -> eumdac.DataStore:
        """Acquire token + DataStore on first use, then reuse."""
        if self._datastore is None:
            self._token = eumdac.AccessToken(self._credentials)
            self._datastore = eumdac.DataStore(self._token)
            log.info(
                "eumdac.token_acquired",
                expires=str(self._token.expiration),
            )
        return self._datastore

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def list_recent_products(
        self,
        collection_id: str,
        since: timedelta = timedelta(hours=24),
    ) -> Iterator[dict[str, Any]]:
        """Yield products published in the last `since` window.

        Returns plain dicts (not EUMDAC objects) so callers don't need
        to import or know about EUMDAC internals.
        """
        ds = self._ensure()
        collection = ds.get_collection(collection_id)
        end = datetime.now(UTC)
        start = end - since

        log.info(
            "eumdac.search.start",
            collection=collection_id,
            window_start=start.isoformat(),
            window_end=end.isoformat(),
        )

        count = 0
        for product in collection.search(dtstart=start, dtend=end):
            count += 1
            yield {
                "collection_id": collection_id,
                "product_id": str(product),
                "sensing_start": product.sensing_start,
                "sensing_end": product.sensing_end,
                "ingested": getattr(product, "ingested", None),
            }

        log.info(
            "eumdac.search.complete",
            collection=collection_id,
            product_count=count,
        )