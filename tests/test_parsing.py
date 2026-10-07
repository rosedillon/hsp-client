from __future__ import annotations

import pandas as pd
import pytest

from hsp_client import (
    DETAILS_COLUMNS,
    METRICS_COLUMNS,
    delay_minutes,
    parse_hhmm,
    parse_service_details,
    parse_service_metrics,
)

from .conftest import DETAILS_RESPONSE, METRICS_RESPONSE


class TestParseHhmm:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("0000", 0),
            ("0712", 432),
            ("1259", 779),
            ("2359", 1439),
        ],
    )
    def test_valid_times(self, value: str, expected: int) -> None:
        assert parse_hhmm(value) == expected

    @pytest.mark.parametrize("value", ["", None, "   ", "abcd", "712", "07:12", "99"])
    def test_unparseable_returns_none(self, value: str | None) -> None:
        # An empty string is HSP's way of saying "does not apply here".
        assert parse_hhmm(value) is None

    def test_impossible_minutes_rejected(self) -> None:
        assert parse_hhmm("0760") is None

    def test_surrounding_whitespace_tolerated(self) -> None:
        assert parse_hhmm(" 0712 ") == 432


class TestDelayMinutes:
    def test_late_is_positive(self) -> None:
        assert delay_minutes("0722", "0724") == 2

    def test_early_is_negative(self) -> None:
        assert delay_minutes("0822", "0819") == -3

    def test_on_time_is_zero(self) -> None:
        assert delay_minutes("0722", "0722") == 0

    def test_missing_either_side_is_none(self) -> None:
        assert delay_minutes("", "0724") is None
        assert delay_minutes("0722", "") is None
        assert delay_minutes(None, None) is None

    def test_crossing_midnight_late(self) -> None:
        # Scheduled 23:58, arrived 00:03: five late, not 1,435 early.
        assert delay_minutes("2358", "0003") == 5

    def test_crossing_midnight_early(self) -> None:
        # Scheduled 00:02, arrived 23:57: five early.
        assert delay_minutes("0002", "2357") == -5


class TestParseServiceMetrics:
    @pytest.fixture
    def frame(self) -> pd.DataFrame:
        return parse_service_metrics(METRICS_RESPONSE)

    def test_one_row_per_pattern_per_tolerance(self, frame: pd.DataFrame) -> None:
        # Two tolerances on the first pattern; the second has no
        # Metrics.
        assert len(frame) == 2

    def test_columns_are_the_declared_ones(self, frame: pd.DataFrame) -> None:
        assert list(frame.columns) == METRICS_COLUMNS

    def test_pattern_per_tolerance(self, frame: pd.DataFrame) -> None:
        assert set(frame["gbtt_ptd"]) == {"0722"}
        assert set(frame["toc_code"]) == {"GX"}

    def test_numbers_are_coerced_from_strings(self, frame: pd.DataFrame) -> None:
        assert frame["percent_tolerance"].tolist() == [88, 100]
        assert frame["matched_services"].tolist() == [9, 9]
        assert pd.api.types.is_numeric_dtype(frame["num_tolerance"])

    def test_rids_are_joined_for_csv_safety(self, frame: pd.DataFrame) -> None:
        assert frame["rids"].iloc[0] == "201601013091406;201601023091406"

    def test_booleans_survive(self, frame: pd.DataFrame) -> None:
        assert frame["global_tolerance"].tolist() == [True, False]

    def test_pattern_without_metrics(self, frame: pd.DataFrame) -> None:
        assert "0752" not in set(frame["gbtt_ptd"])

    def test_empty_response(self) -> None:
        frame = parse_service_metrics({})
        assert frame.empty
        assert list(frame.columns) == METRICS_COLUMNS

    def test_null_services_is_treated_as_empty(self) -> None:
        assert parse_service_metrics({"Services": None}).empty


class TestParseServiceDetails:
    @pytest.fixture
    def frame(self) -> pd.DataFrame:
        return parse_service_details(DETAILS_RESPONSE)

    def test_one_row_per_calling_point(self, frame: pd.DataFrame) -> None:
        assert list(frame["location"]) == ["BTN", "HHE", "VIC"]

    def test_columns_are_the_declared_ones(self, frame: pd.DataFrame) -> None:
        assert list(frame.columns) == DETAILS_COLUMNS

    def test_service_attributes(self, frame: pd.DataFrame) -> None:
        assert set(frame["rid"]) == {"201601013091406"}
        assert set(frame["date_of_service"]) == {"2016-01-01"}

    def test_delays_are_derived(self, frame: pd.DataFrame) -> None:
        assert frame["departure_delay"].tolist()[0] == 2
        assert frame["arrival_delay"].tolist()[2] == -3

    def test_inapplicable_times_give_no_delay(self, frame: pd.DataFrame) -> None:
        # Origin has no public arrival; terminus has no public
        # departure.
        assert pd.isna(frame["arrival_delay"].iloc[0])
        assert pd.isna(frame["departure_delay"].iloc[2])

    def test_delay_columns_are_nullable_integers(self, frame: pd.DataFrame) -> None:
        assert str(frame["arrival_delay"].dtype) == "Int64"
        assert str(frame["departure_delay"].dtype) == "Int64"

    def test_empty_response(self) -> None:
        frame = parse_service_details({})
        assert frame.empty
        assert list(frame.columns) == DETAILS_COLUMNS
