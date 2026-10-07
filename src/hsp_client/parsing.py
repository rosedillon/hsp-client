"""Flatten HSP's nested JSON responses into tables.

HSP returns numbers as JSON strings, and gives a time that does not
apply at a location (a terminus has no departure) as an empty string
rather than null. Both are normalised here: numeric fields are coerced,
and an empty time becomes ``None``.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# One row per departure pattern per tolerance value.
METRICS_COLUMNS = [
    "origin_location",
    "destination_location",
    "gbtt_ptd",
    "gbtt_pta",
    "toc_code",
    "matched_services",
    "rids",
    "tolerance_value",
    "num_not_tolerance",
    "num_tolerance",
    "percent_tolerance",
    "global_tolerance",
]

# One row per calling point of one historic service.
DETAILS_COLUMNS = [
    "rid",
    "date_of_service",
    "toc_code",
    "location",
    "gbtt_pta",
    "gbtt_ptd",
    "actual_ta",
    "actual_td",
    "late_canc_reason",
    # Not returned by HSP; derived from the scheduled/actual pairs
    # above.
    "arrival_delay",
    "departure_delay",
]


def _number(value: Any) -> float | None:
    """Coerce one of HSP's string-encoded numbers, else ``None``.

    Every numeric field in an HSP response arrives as a JSON string, and
    an absent field arrives as no key at all. Both end up here.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_hhmm(value: str | None) -> int | None:
    """Minutes since midnight for an HSP ``"HHMM"`` string, or ``None``.

    HSP writes times as four digits with no separator (``"0712"``), and
    uses an empty string for a time that does not apply at a location: a
    terminus has no public departure and an origin no public arrival.
    Anything that is not four digits returns ``None`` instead of
    raising, so one malformed time cannot stop a long response being
    parsed.

    >>> parse_hhmm("0712")
    432
    >>> parse_hhmm("") is None
    True
    """
    if not value:
        return None
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        return None
    hours, minutes = int(text[:2]), int(text[2:])
    if minutes >= 60:
        return None
    return hours * 60 + minutes


def delay_minutes(scheduled: str | None, actual: str | None) -> int | None:
    """Minutes late at one calling point, negative if early.

    Returns ``None`` if either time is missing or unparseable. Crossing
    midnight is handled: a train scheduled at 2358 and arriving 0003 is
    five minutes late, not 1,435 minutes early.
    """
    scheduled_minutes = parse_hhmm(scheduled)
    actual_minutes = parse_hhmm(actual)
    if scheduled_minutes is None or actual_minutes is None:
        return None
    difference = actual_minutes - scheduled_minutes
    half_day = 12 * 60
    if difference > half_day:
        difference -= 24 * 60
    elif difference < -half_day:
        difference += 24 * 60
    return difference


def parse_service_metrics(response: dict[str, Any]) -> pd.DataFrame:
    """Flatten ``serviceMetrics`` to a row per pattern and tolerance.

    A departure pattern with no ``Metrics`` entries contributes no rows.
    The ``rids`` list is joined with ``;`` so the frame survives a round
    trip through CSV.
    """
    rows: list[dict[str, Any]] = []
    for service in response.get("Services") or []:
        attributes = service.get("serviceAttributesMetrics") or {}
        shared = {
            "origin_location": attributes.get("origin_location"),
            "destination_location": attributes.get("destination_location"),
            "gbtt_ptd": attributes.get("gbtt_ptd"),
            "gbtt_pta": attributes.get("gbtt_pta"),
            "toc_code": attributes.get("toc_code"),
            "matched_services": _number(attributes.get("matched_services")),
            "rids": ";".join(attributes.get("rids") or []),
        }
        for metric in service.get("Metrics") or []:
            rows.append(
                {
                    **shared,
                    "tolerance_value": _number(metric.get("tolerance_value")),
                    "num_not_tolerance": _number(metric.get("num_not_tolerance")),
                    "num_tolerance": _number(metric.get("num_tolerance")),
                    "percent_tolerance": _number(metric.get("percent_tolerance")),
                    "global_tolerance": metric.get("global_tolerance"),
                }
            )
    return pd.DataFrame(rows, columns=METRICS_COLUMNS)


def parse_service_details(response: dict[str, Any]) -> pd.DataFrame:
    """Flatten ``serviceDetails`` to one row per calling point.

    Adds ``arrival_delay`` and ``departure_delay`` columns (minutes
    late, negative if early) that HSP does not itself return.
    """
    attributes = response.get("serviceAttributesDetails") or {}
    shared = {
        "rid": attributes.get("rid"),
        "date_of_service": attributes.get("date_of_service"),
        "toc_code": attributes.get("toc_code"),
    }
    rows = []
    for location in attributes.get("locations") or []:
        scheduled_arrival = location.get("gbtt_pta")
        scheduled_departure = location.get("gbtt_ptd")
        actual_arrival = location.get("actual_ta")
        actual_departure = location.get("actual_td")
        rows.append(
            {
                **shared,
                "location": location.get("location"),
                "gbtt_pta": scheduled_arrival,
                "gbtt_ptd": scheduled_departure,
                "actual_ta": actual_arrival,
                "actual_td": actual_departure,
                "late_canc_reason": location.get("late_canc_reason"),
                "arrival_delay": delay_minutes(scheduled_arrival, actual_arrival),
                "departure_delay": delay_minutes(scheduled_departure, actual_departure),
            }
        )
    frame = pd.DataFrame(rows, columns=DETAILS_COLUMNS)
    # Nullable integers: a calling point with no applicable time has no
    # delay, and <NA> keeps the column integral where a float NaN would
    # not.
    for column in ("arrival_delay", "departure_delay"):
        frame[column] = frame[column].astype("Int64")
    return frame
