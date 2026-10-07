# Every test uses a fake opener; nothing here reaches the network.

from __future__ import annotations

import base64

import pytest

from hsp_client import (
    DETAILS_URL,
    METRICS_URL,
    AuthenticationError,
    HspClient,
    HspRequestError,
    InvalidRequestError,
    MissingCredentialsError,
)

from .conftest import METRICS_RESPONSE, RecordingOpener, http_error

pytestmark = pytest.mark.usefixtures("credentials")


class TestCredentials:
    def test_environment_variables_are_used(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        client = HspClient(opener=opener)
        client.service_details("123")
        header = opener.requests[-1].get_header("Authorization")
        expected = base64.b64encode(b"someone@example.com:hunter2").decode()
        assert header == f"Basic {expected}"

    def test_explicit_credentials_win(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        client = HspClient("other@example.com", "s3cret", opener=opener)
        client.service_details("123")
        header = opener.requests[-1].get_header("Authorization")
        expected = base64.b64encode(b"other@example.com:s3cret").decode()
        assert header == f"Basic {expected}"

    @pytest.mark.usefixtures("no_credentials")
    def test_missing_credentials_message(self) -> None:
        with pytest.raises(MissingCredentialsError, match="Subscription type"):
            HspClient()

    @pytest.mark.usefixtures("no_credentials")
    def test_half_credentials_is_still_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NRDP_USERNAME", "someone@example.com")
        with pytest.raises(MissingCredentialsError):
            HspClient()


class TestServiceMetricsRequest:
    def test_posts_to_the_metrics_endpoint(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        HspClient(opener=opener).service_metrics(
            "btn",
            "vic",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days="WEEKDAY",
        )
        assert opener.last_url == METRICS_URL
        assert opener.requests[-1].get_method() == "POST"

    def test_crs_codes_are_normalised(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        HspClient(opener=opener).service_metrics(
            " btn ",
            "vic",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days="WEEKDAY",
        )
        assert opener.last_body["from_loc"] == "BTN"
        assert opener.last_body["to_loc"] == "VIC"

    def test_day_type_is_normalised(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        HspClient(opener=opener).service_metrics(
            "BTN",
            "VIC",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days=" weekday ",
        )
        assert opener.last_body["days"] == "WEEKDAY"

    def test_filters_omitted(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        HspClient(opener=opener).service_metrics(
            "BTN",
            "VIC",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days="WEEKDAY",
        )
        # Sending an empty list is not the same as omitting it.
        assert "toc_filter" not in opener.last_body
        assert "tolerance" not in opener.last_body

    def test_filters_sent(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        HspClient(opener=opener).service_metrics(
            "BTN",
            "VIC",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days="WEEKDAY",
            toc_filter=["GX"],
            tolerance=["5", "10"],
        )
        assert opener.last_body["toc_filter"] == ["GX"]
        assert opener.last_body["tolerance"] == ["5", "10"]

    def test_invalid_day_type(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        with pytest.raises(InvalidRequestError, match="WEEKDAY"):
            HspClient(opener=opener).service_metrics(
                "BTN",
                "VIC",
                from_time="0700",
                to_time="0800",
                from_date="2024-01-08",
                to_date="2024-01-12",
                days="TUESDAY",
            )
        assert opener.requests == []

    def test_response_unchanged(self) -> None:
        opener = RecordingOpener(METRICS_RESPONSE)
        raw = HspClient(opener=opener).service_metrics(
            "BTN",
            "VIC",
            from_time="0700",
            to_time="0800",
            from_date="2024-01-08",
            to_date="2024-01-12",
            days="WEEKDAY",
        )
        assert raw == METRICS_RESPONSE


class TestServiceDetailsRequest:
    def test_details_posts_rid(self) -> None:
        opener = RecordingOpener({"serviceAttributesDetails": {}})
        HspClient(opener=opener).service_details("201601013091406")
        assert opener.last_url == DETAILS_URL
        assert opener.last_body == {"rid": "201601013091406"}

    def test_empty_rid(self) -> None:
        opener = RecordingOpener()
        with pytest.raises(InvalidRequestError, match="rid"):
            HspClient(opener=opener).service_details("   ")
        assert opener.requests == []


class TestErrorMapping:
    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_failures_name_the_subscription(self, status: int) -> None:
        opener = RecordingOpener(error=http_error(status))
        with pytest.raises(AuthenticationError, match="Subscription type"):
            HspClient(opener=opener).service_details("123")

    def test_other_http_errors(self) -> None:
        opener = RecordingOpener(error=http_error(500, "upstream exploded"))
        with pytest.raises(HspRequestError, match="upstream exploded") as raised:
            HspClient(opener=opener).service_details("123")
        assert raised.value.status == 500

    def test_timeout_is_passed_through(self) -> None:
        opener = RecordingOpener({"serviceAttributesDetails": {}})
        HspClient(opener=opener, timeout=12.5).service_details("123")
        assert opener.timeouts == [12.5]
