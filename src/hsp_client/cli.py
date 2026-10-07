"""Command-line access to the HSP API.

Credentials are read from ``NRDP_USERNAME`` and ``NRDP_PASSWORD``. There
is no ``--password`` flag, because it would end up in shell history.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import TYPE_CHECKING

from hsp_client.client import VALID_DAYS, HspClient
from hsp_client.errors import HspError
from hsp_client.parsing import parse_service_details, parse_service_metrics

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd


def _write(frame: pd.DataFrame, args: argparse.Namespace) -> int:
    if args.csv:
        frame.to_csv(args.csv, index=False)
        print(f"Wrote {len(frame):,} row(s) to {args.csv}", file=sys.stderr)
        return 0
    if frame.empty:
        print(
            "No services returned. HSP excludes trains whose public times or operator "
            "do not match exactly, and those with no recorded actual arrival, so an "
            "empty result does not prove that nothing ran.",
            file=sys.stderr,
        )
        return 0
    with_all_columns = frame.to_string(index=False)
    print(with_all_columns)
    return 0


def _cmd_metrics(args: argparse.Namespace) -> int:
    client = HspClient()
    raw = client.service_metrics(
        args.origin,
        args.destination,
        from_time=args.from_time,
        to_time=args.to_time,
        from_date=args.from_date,
        to_date=args.to_date,
        days=args.days,
        toc_filter=args.toc,
        tolerance=args.tolerance,
    )
    if args.raw:
        json.dump(raw, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    return _write(parse_service_metrics(raw), args)


def _cmd_details(args: argparse.Namespace) -> int:
    client = HspClient()
    raw = client.service_details(args.rid)
    if args.raw:
        json.dump(raw, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    return _write(parse_service_details(raw), args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hsp-client",
        description=(
            "Query the Historic Service Performance API. Needs a National Rail Data "
            "Portal account with the HSP subscription enabled; set NRDP_USERNAME and "
            "NRDP_PASSWORD in the environment."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log each request")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_output(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--csv", metavar="PATH", help="write the table to a CSV file")
        sub.add_argument("--raw", action="store_true", help="print the raw JSON response")

    metrics = subparsers.add_parser(
        "metrics",
        help="Punctuality between two stations.",
        description="Punctuality for every departure pattern between two stations.",
    )
    metrics.add_argument("origin", help="origin CRS code, e.g. BTN")
    metrics.add_argument("destination", help="destination CRS code, e.g. VIC")
    metrics.add_argument("--from-time", required=True, metavar="HHMM")
    metrics.add_argument("--to-time", required=True, metavar="HHMM")
    metrics.add_argument("--from-date", required=True, metavar="YYYY-MM-DD")
    metrics.add_argument("--to-date", required=True, metavar="YYYY-MM-DD")
    metrics.add_argument(
        "--days",
        default="WEEKDAY",
        choices=sorted(VALID_DAYS),
        help="day type (default: WEEKDAY)",
    )
    metrics.add_argument("--toc", nargs="+", metavar="CODE", help="restrict to these operators")
    metrics.add_argument(
        "--tolerance",
        nargs="+",
        metavar="MINS",
        help="lateness tolerances in minutes, up to three",
    )
    add_output(metrics)
    metrics.set_defaults(func=_cmd_metrics)

    details = subparsers.add_parser(
        "details",
        help="Stop-by-stop times for one service.",
        description="Actual against scheduled times at every calling point of one service.",
    )
    details.add_argument("rid", help="a RID from a metrics response")
    add_output(details)
    details.set_defaults(func=_cmd_details)

    # -v also works after the subcommand.
    for subcommand in subparsers.choices.values():
        subcommand.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            default=argparse.SUPPRESS,
            help="log progress",
        )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    try:
        return int(args.func(args))
    except HspError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
