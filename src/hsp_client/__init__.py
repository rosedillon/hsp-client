"""Client for the Historic Service Performance (HSP) rail API.

Credentials come from ``NRDP_USERNAME`` and ``NRDP_PASSWORD``::

    from hsp_client import HspClient, parse_service_metrics

    raw = HspClient().service_metrics(
        "BTN", "VIC",
        from_time="0700", to_time="0800",
        from_date="2024-01-08", to_date="2024-01-12",
        days="WEEKDAY",
    )
    parse_service_metrics(raw)
"""

from __future__ import annotations

from hsp_client.client import DETAILS_URL, METRICS_URL, HspClient
from hsp_client.errors import (
    AuthenticationError,
    HspError,
    HspRequestError,
    InvalidRequestError,
    MissingCredentialsError,
)
from hsp_client.parsing import (
    DETAILS_COLUMNS,
    METRICS_COLUMNS,
    delay_minutes,
    parse_hhmm,
    parse_service_details,
    parse_service_metrics,
)

__all__ = [
    "DETAILS_COLUMNS",
    "DETAILS_URL",
    "METRICS_COLUMNS",
    "METRICS_URL",
    "AuthenticationError",
    "HspClient",
    "HspError",
    "HspRequestError",
    "InvalidRequestError",
    "MissingCredentialsError",
    "delay_minutes",
    "parse_hhmm",
    "parse_service_details",
    "parse_service_metrics",
]

__version__ = "0.1.0"
