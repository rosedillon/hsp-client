"""HTTP access to the two HSP endpoints.

HSP (Historic Service Performance) holds historical Darwin data for
Great Britain. There is no bulk download, so it is queried live through
two POST endpoints, both documented at
https://wiki.openraildata.com/index.php/HSP:

``serviceMetrics``
    Punctuality for every departure pattern between two stations over a
    date range, time window and day type: how many services arrived
    within a chosen tolerance of their scheduled time.

``serviceDetails``
    Actual against scheduled times at every stop of one service, looked
    up by a RID from a ``serviceMetrics`` response.

Authentication is HTTP Basic against a National Rail Data Portal account
(https://opendata.nationalrail.co.uk) with HSP ticked under Subscription
type. An NRDP account without that box ticked works for the other feeds
but gets a 401 here, and it is the usual reason a request fails.

What HSP will not return
------------------------
A service is only included if its public times and operator match
exactly, it is not marked deleted, and, at a location it calls at, it
has a recorded actual arrival. "Rules for Inclusion of Trains" on the
wiki page above has the details. An empty result does not prove that no
train ran.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any, Literal

from hsp_client.errors import (
    AuthenticationError,
    HspRequestError,
    InvalidRequestError,
    MissingCredentialsError,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)

METRICS_URL = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"
DETAILS_URL = "https://hsp-prod.rockshore.net/api/v1/serviceDetails"

DEFAULT_TIMEOUT_SECONDS = 60

DayType = Literal["WEEKDAY", "SATURDAY", "SUNDAY"]
VALID_DAYS: frozenset[str] = frozenset({"WEEKDAY", "SATURDAY", "SUNDAY"})

USERNAME_ENV = "NRDP_USERNAME"
PASSWORD_ENV = "NRDP_PASSWORD"


class HspClient:
    """A credentialed connection to the HSP API.

    Credentials default to the ``NRDP_USERNAME`` and ``NRDP_PASSWORD``
    environment variables. They can also be passed in, for tests and for
    callers that keep them in a secret store. Do not put them in a
    config file that goes into version control.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        opener: Any = None,
    ) -> None:
        resolved_username = username or os.environ.get(USERNAME_ENV)
        resolved_password = password or os.environ.get(PASSWORD_ENV)
        if not resolved_username or not resolved_password:
            raise MissingCredentialsError
        self._username = resolved_username
        self._password = resolved_password
        self._timeout = timeout
        # Injectable so the tests can exercise the request-building and
        # error-mapping paths without a network or real credentials.
        self._opener = opener or urllib.request.urlopen

    @property
    def _authorization(self) -> str:
        token = base64.b64encode(f"{self._username}:{self._password}".encode()).decode("ascii")
        return f"Basic {token}"

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": self._authorization,
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                payload: dict[str, Any] = json.loads(response.read())
                return payload
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise AuthenticationError(error.code) from error
            detail = error.read().decode("utf-8", "replace") if error.fp else ""
            raise HspRequestError(error.code, detail) from error

    def service_metrics(
        self,
        from_loc: str,
        to_loc: str,
        *,
        from_time: str,
        to_time: str,
        from_date: str,
        to_date: str,
        days: DayType | str,
        toc_filter: Iterable[str] | None = None,
        tolerance: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Punctuality for every departure pattern between two stations.

        Parameters
        ----------
        from_loc, to_loc
            Origin and destination CRS codes, e.g. ``"BTN"``, ``"VIC"``.
        from_time, to_time
            Clock times bounding the departures to include, ``"HHMM"``.
        from_date, to_date
            Historical date range, ``"YYYY-MM-DD"``. HSP holds about a
            year.
        days
            ``"WEEKDAY"``, ``"SATURDAY"`` or ``"SUNDAY"``. HSP has no
            all-days option; query the three separately if you need
            them.
        toc_filter
            Restrict to these operator codes, e.g. ``["GX"]``.
        tolerance
            Up to three lateness tolerances in minutes, such as
            ``["5", "10"]``. HSP's own defaults apply when unset.

        Returns
        -------
        dict
            The raw JSON response. Pass it to
            :func:`hsp_client.parsing.parse_service_metrics` for a
            table.
        """
        normalised_days = str(days).strip().upper()
        if normalised_days not in VALID_DAYS:
            raise InvalidRequestError(f"days must be one of {sorted(VALID_DAYS)}, got {days!r}")

        body: dict[str, Any] = {
            "from_loc": from_loc.strip().upper(),
            "to_loc": to_loc.strip().upper(),
            "from_time": from_time,
            "to_time": to_time,
            "from_date": from_date,
            "to_date": to_date,
            "days": normalised_days,
        }
        if toc_filter:
            body["toc_filter"] = list(toc_filter)
        if tolerance:
            body["tolerance"] = list(tolerance)

        logger.info(
            "HSP serviceMetrics %s->%s %s-%s over %s..%s (%s)",
            body["from_loc"],
            body["to_loc"],
            from_time,
            to_time,
            from_date,
            to_date,
            normalised_days,
        )
        return self._post(METRICS_URL, body)

    def service_details(self, rid: str) -> dict[str, Any]:
        """Actual and scheduled times at every stop of one service.

        Parameters
        ----------
        rid
            A RID from a ``serviceMetrics`` response
            (``serviceAttributesMetrics.rids``).
        """
        if not str(rid).strip():
            raise InvalidRequestError("rid must not be empty")
        logger.info("HSP serviceDetails for RID %s", rid)
        return self._post(DETAILS_URL, {"rid": str(rid).strip()})
