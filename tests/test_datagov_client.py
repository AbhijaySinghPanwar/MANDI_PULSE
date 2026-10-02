"""data.gov.in pagination, with mocked HTTP only (requests_mock blocks real network calls)."""

import logging
from urllib.parse import parse_qs, urlparse

import pytest
import requests_mock

from mandipulse.ingest.datagov_client import BASE_URL, DataGovClient

URL = BASE_URL.format(resource_id="test-resource")


def make_client(**kwargs) -> DataGovClient:
    return DataGovClient(
        api_key="dummy-key", resource_id="test-resource", page_size=1000, retry_wait_s=0, **kwargs
    )


def records(start: int, n: int) -> list[dict]:
    return [{"market": f"M{i}", "modal_price": "1000"} for i in range(start, start + n)]


def paged_server(total: int, server_page: int):
    """A fake API that ignores `limit` and returns at most `server_page` rows per call."""

    def callback(request, context):
        offset = int(parse_qs(urlparse(request.url).query)["offset"][0])
        return {"records": records(offset, max(0, min(server_page, total - offset)))}

    return callback


def offsets(m: requests_mock.Mocker) -> list[int]:
    return [int(parse_qs(urlparse(r.url).query)["offset"][0]) for r in m.request_history]


def test_short_pages_are_followed_until_empty_page():
    # Asked for 1000 per page, the server sends only 10: all 25 rows must still arrive.
    client = make_client()
    with requests_mock.Mocker() as m:
        m.get(URL, json=paged_server(total=25, server_page=10))
        rows = client.fetch_all()
    assert [r["market"] for r in rows] == [f"M{i}" for i in range(25)]
    assert offsets(m) == [0, 10, 20, 25]  # advances by rows received, not by 1000
    assert [p.received for p in client.pages] == [10, 10, 5, 0]


def test_a_short_page_is_not_treated_as_the_last_page():
    # 5 < limit, but only an EMPTY page ends pagination.
    client = make_client()
    with requests_mock.Mocker() as m:
        m.get(
            URL,
            [
                {"json": {"records": records(0, 5)}},
                {"json": {"records": records(5, 3)}},
                {"json": {"records": []}},
            ],
        )
        rows = client.fetch_all()
    assert len(rows) == 8
    assert m.call_count == 3


def test_missing_records_key_counts_as_empty_page():
    client = make_client()
    with requests_mock.Mocker() as m:
        m.get(URL, json={"status": "ok"})
        assert client.fetch_all() == []
    assert m.call_count == 1


def test_rows_received_are_logged_per_page(caplog):
    client = make_client()
    with (
        caplog.at_level(logging.INFO, logger="mandipulse.ingest.datagov_client"),
        requests_mock.Mocker() as m,
    ):
        m.get(URL, json=paged_server(total=12, server_page=10))
        client.fetch_all()
    messages = [r.getMessage() for r in caplog.records]
    assert "data.gov.in page 1: offset=0 requested=1000 received=10" in messages
    assert "data.gov.in page 2: offset=10 requested=1000 received=2" in messages
    assert "data.gov.in page 3: offset=12 requested=1000 received=0" in messages


def test_filters_limit_and_key_are_sent():
    client = make_client()
    with requests_mock.Mocker() as m:
        m.get(URL, json={"records": []})
        client.fetch_all({"state": "Maharashtra", "commodity": "Onion"})
    query = parse_qs(urlparse(m.request_history[0].url).query)
    assert query["filters[state]"] == ["Maharashtra"]
    assert query["filters[commodity]"] == ["Onion"]
    assert query["limit"] == ["1000"]
    assert query["api-key"] == ["dummy-key"]


def test_transient_errors_are_retried():
    client = make_client(max_retries=3)
    with requests_mock.Mocker() as m:
        m.get(
            URL,
            [
                {"status_code": 503},
                {"status_code": 429},
                {"json": {"records": records(0, 2)}},
                {"json": {"records": []}},
            ],
        )
        assert len(client.fetch_all()) == 2
    assert m.call_count == 4


def test_server_that_never_returns_an_empty_page_is_stopped():
    client = make_client(max_pages=5)
    with requests_mock.Mocker() as m:
        m.get(URL, json={"records": records(0, 1)})
        with pytest.raises(RuntimeError, match="max_pages"):
            client.fetch_all()
    assert m.call_count == 5
