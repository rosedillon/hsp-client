"""Fixtures for the HSP client tests.

The responses below follow the shapes documented at
https://wiki.openraildata.com/index.php/HSP, including HSP's two habits
that most often trip up a parser: every number arrives as a JSON
*string*, and a time that does not apply at a location (a terminus has
no departure) arrives as ``""`` rather than ``null``.

No test here touches the network.
"""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

METRICS_RESPONSE: dict[str, Any] = {
    "header": {"used_tolerance_value": "5"},
    "Services": [
        {
            "serviceAttributesMetrics": {
                "origin_location": "BTN",
                "destination_location": "VIC",
                "gbtt_ptd": "0722",
                "gbtt_pta": "0822",
                "toc_code": "GX",
                "matched_services": "9",
                "rids": ["201601013091406", "201601023091406"],
            },
            "Metrics": [
                {
                    "tolerance_value": "5",
                    "num_not_tolerance": "1",
                    "num_tolerance": "8",
                    "percent_tolerance": "88",
                    "global_tolerance": True,
                },
                {
                    "tolerance_value": "10",
                    "num_not_tolerance": "0",
                    "num_tolerance": "9",
                    "percent_tolerance": "100",
                    "global_tolerance": False,
                },
            ],
        },
        {
            # A pattern HSP matched but produced no metrics for;
            # contributes no rows rather than a row of nulls.
            "serviceAttributesMetrics": {
                "origin_location": "BTN",
                "destination_location": "VIC",
                "gbtt_ptd": "0752",
                "gbtt_pta": "0852",
                "toc_code": "GX",
                "matched_services": "0",
                "rids": [],
            },
            "Metrics": [],
        },
    ],
}

DETAILS_RESPONSE: dict[str, Any] = {
    "serviceAttributesDetails": {
        "date_of_service": "2016-01-01",
        "toc_code": "GX",
        "rid": "201601013091406",
        "locations": [
            {
                "location": "BTN",
                "gbtt_ptd": "0722",
                "gbtt_pta": "",  # origin: no public arrival
                "actual_td": "0724",
                "actual_ta": "",
                "late_canc_reason": "",
            },
            {
                "location": "HHE",
                "gbtt_ptd": "0740",
                "gbtt_pta": "0739",
                "actual_td": "0742",
                "actual_ta": "0741",
                "late_canc_reason": "",
            },
            {
                "location": "VIC",
                "gbtt_ptd": "",  # terminus: no public departure
                "gbtt_pta": "0822",
                "actual_td": "",
                "actual_ta": "0819",  # three minutes early
                "late_canc_reason": "",
            },
        ],
    }
}


class FakeResponse(io.BytesIO):
    """Stands in for the object `urlopen` returns."""

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class RecordingOpener:
    """A fake `urlopen` that records requests and replays a response."""

    def __init__(self, payload: Any = None, error: Exception | None = None) -> None:
        self.payload = payload if payload is not None else {}
        self.error = error
        self.requests: list[Any] = []
        self.timeouts: list[float] = []

    def __call__(self, request: Any, timeout: float | None = None) -> FakeResponse:
        self.requests.append(request)
        if timeout is not None:
            self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return FakeResponse(json.dumps(self.payload).encode())

    @property
    def last_body(self) -> dict[str, Any]:
        """The JSON body of the most recent request."""
        body: dict[str, Any] = json.loads(self.requests[-1].data.decode())
        return body

    @property
    def last_url(self) -> str:
        url: str = self.requests[-1].full_url
        return url


def http_error(code: int, body: str = "") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://hsp-prod.rockshore.net/api/v1/serviceMetrics",
        code=code,
        msg="error",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(body.encode()),
    )


@pytest.fixture
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NRDP_USERNAME", "someone@example.com")
    monkeypatch.setenv("NRDP_PASSWORD", "hunter2")


@pytest.fixture
def no_credentials(credentials: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantees an unauthenticated environment.

    Depends on `credentials` so it is ordered *after* it: the client
    tests apply `credentials` module-wide, and without the dependency
    the two fixtures race and the environment may end up populated.
    """
    del credentials
    monkeypatch.delenv("NRDP_USERNAME", raising=False)
    monkeypatch.delenv("NRDP_PASSWORD", raising=False)
