"""data.gov.in mandi price API client (spec 6.3). STUB: not called yet.

data.gov.in is unreachable for now and `sources.datagov.enabled` is false, so nothing in the
pipeline calls this. The pagination logic is implemented and unit-tested with mocked
responses so the daily feed can be switched on later.

Pagination rule (spec 6.3): keep requesting the next offset until a page comes back EMPTY.
Never assume the server honours the requested limit (it may return 10 rows when asked for
1000), so the offset advances by the number of rows actually received. Log the rows
received on every page.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mandipulse.config import get_settings

log = logging.getLogger(__name__)

BASE_URL = "https://api.data.gov.in/resource/{resource_id}"


class TransientAPIError(RuntimeError):
    """5xx or 429: worth retrying."""


@dataclass
class PageLog:
    """What one API page returned (for the ingest log)."""

    page: int
    offset: int
    requested: int
    received: int


@dataclass
class DataGovClient:
    """Paginated data.gov.in client with retries (not used until the feed is enabled)."""

    api_key: str
    resource_id: str
    page_size: int = 1000
    timeout_s: float = 30
    max_retries: int = 5
    max_pages: int = 100_000  # guard against a server that ignores `offset`
    retry_wait_s: float = 2.0  # base of the exponential backoff (0 in tests)
    session: requests.Session = field(default_factory=requests.Session)
    pages: list[PageLog] = field(default_factory=list)

    def fetch_page(self, offset: int, filters: dict[str, str] | None = None) -> list[dict]:
        """One page of records. Retries timeouts, connection errors, 429 and 5xx."""

        @retry(
            retry=retry_if_exception_type(
                (requests.ConnectionError, requests.Timeout, TransientAPIError)
            ),
            wait=wait_exponential(multiplier=self.retry_wait_s, max=60),
            stop=stop_after_attempt(self.max_retries),
            reraise=True,
        )
        def _get() -> list[dict]:
            params = {
                "api-key": self.api_key,
                "format": "json",
                "limit": self.page_size,
                "offset": offset,
            }
            for key, value in (filters or {}).items():
                params[f"filters[{key}]"] = value
            resp = self.session.get(
                BASE_URL.format(resource_id=self.resource_id), params=params, timeout=self.timeout_s
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise TransientAPIError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            return resp.json().get("records") or []

        return _get()

    def iter_records(self, filters: dict[str, str] | None = None) -> Iterator[dict]:
        """Yield every record, page by page, until the API returns an empty page."""
        offset = 0
        for page in range(1, self.max_pages + 1):
            records = self.fetch_page(offset, filters)
            self.pages.append(PageLog(page, offset, self.page_size, len(records)))
            log.info(
                "data.gov.in page %d: offset=%d requested=%d received=%d",
                page,
                offset,
                self.page_size,
                len(records),
            )
            if not records:
                return
            yield from records
            offset += len(records)  # rows actually received, NOT page_size
        raise RuntimeError(f"Stopped after max_pages={self.max_pages} without an empty page")

    def fetch_all(self, filters: dict[str, str] | None = None) -> list[dict]:
        return list(self.iter_records(filters))


def client_from_settings(api_key: str) -> DataGovClient:
    """Client configured from settings.yaml; refuses while sources.datagov.enabled is false."""
    cfg = get_settings()
    if not cfg["sources"]["datagov"]["enabled"]:
        raise RuntimeError("data.gov.in is disabled (sources.datagov.enabled = false).")
    api = cfg["api"]
    return DataGovClient(
        api_key=api_key,
        resource_id=api["datagov_resource_id"],
        page_size=api["page_size"],
        timeout_s=api["timeout_s"],
        max_retries=api["max_retries"],
    )
