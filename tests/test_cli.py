from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from hsp_client import cli
from hsp_client.cli import build_parser

from .conftest import DETAILS_RESPONSE, METRICS_RESPONSE, RecordingOpener, http_error

if TYPE_CHECKING:
    import pathlib

    from _pytest.capture import CaptureFixture

pytestmark = pytest.mark.usefixtures("credentials")

METRICS_ARGS = [
    "metrics",
    "BTN",
    "VIC",
    "--from-time",
    "0700",
    "--to-time",
    "0800",
    "--from-date",
    "2024-01-08",
    "--to-date",
    "2024-01-12",
]


SMOKE_ARGS = ["details", "123"]


@pytest.fixture
def opener(monkeypatch: pytest.MonkeyPatch) -> RecordingOpener:
    """Patch the client's default opener for every CLI invocation."""
    recorder = RecordingOpener(METRICS_RESPONSE)
    monkeypatch.setattr("hsp_client.client.urllib.request.urlopen", recorder)
    return recorder


def test_metrics_prints_a_table(opener: RecordingOpener, capsys: CaptureFixture[str]) -> None:
    assert cli.main(METRICS_ARGS) == 0
    out = capsys.readouterr().out
    assert "percent_tolerance" in out
    assert "GX" in out


def test_metrics_raw_prints_the_json(opener: RecordingOpener, capsys: CaptureFixture[str]) -> None:
    assert cli.main([*METRICS_ARGS, "--raw"]) == 0
    assert json.loads(capsys.readouterr().out) == METRICS_RESPONSE


def test_metrics_writes_csv(
    opener: RecordingOpener, tmp_path: pathlib.Path, capsys: CaptureFixture[str]
) -> None:
    target = tmp_path / "metrics.csv"
    assert cli.main([*METRICS_ARGS, "--csv", str(target)]) == 0
    assert target.exists()
    assert "percent_tolerance" in target.read_text()
    assert "2 row(s)" in capsys.readouterr().err


def test_default_day_type_is_weekday(opener: RecordingOpener) -> None:
    assert cli.main(METRICS_ARGS) == 0
    assert opener.last_body["days"] == "WEEKDAY"


def test_day_type_can_be_overridden(opener: RecordingOpener) -> None:
    assert cli.main([*METRICS_ARGS, "--days", "SUNDAY"]) == 0
    assert opener.last_body["days"] == "SUNDAY"


def test_toc_and_tolerance_reach_the_request(opener: RecordingOpener) -> None:
    assert cli.main([*METRICS_ARGS, "--toc", "GX", "--tolerance", "5", "10"]) == 0
    assert opener.last_body["toc_filter"] == ["GX"]
    assert opener.last_body["tolerance"] == ["5", "10"]


def test_details_prints_calling_points(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    recorder = RecordingOpener(DETAILS_RESPONSE)
    monkeypatch.setattr("hsp_client.client.urllib.request.urlopen", recorder)
    assert cli.main(["details", "201601013091406"]) == 0
    out = capsys.readouterr().out
    assert "HHE" in out
    assert "arrival_delay" in out


def test_empty_result_explained(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    recorder = RecordingOpener({"Services": []})
    monkeypatch.setattr("hsp_client.client.urllib.request.urlopen", recorder)
    assert cli.main(METRICS_ARGS) == 0
    assert "does not prove that nothing ran" in capsys.readouterr().err


def test_auth_failure_is_reported_not_raised(
    monkeypatch: pytest.MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    recorder = RecordingOpener(error=http_error(401))
    monkeypatch.setattr("hsp_client.client.urllib.request.urlopen", recorder)
    assert cli.main(METRICS_ARGS) == 1
    assert "Subscription type" in capsys.readouterr().err


@pytest.mark.usefixtures("no_credentials")
def test_missing_credentials(capsys: CaptureFixture[str]) -> None:
    assert cli.main(METRICS_ARGS) == 1
    assert "NRDP_USERNAME" in capsys.readouterr().err


def test_there_is_no_password_flag() -> None:
    # Credentials must come from the environment, never shell history.
    with pytest.raises(SystemExit):
        cli.main([*METRICS_ARGS, "--password", "hunter2"])


def test_no_subcommand_is_an_error() -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main([])
    assert exit_info.value.code != 0


@pytest.mark.parametrize(
    ("argv", "verbose"),
    [(SMOKE_ARGS, False), (["-v", *SMOKE_ARGS], True), ([*SMOKE_ARGS, "-v"], True)],
)
def test_verbose_flag(argv: list[str], verbose: bool) -> None:
    assert build_parser().parse_args(argv).verbose is verbose
