"""Command-line interface for ``cwms-reservoir-downloader``."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .config import DEFAULT_API_ROOT, OFFICES_BY_STATE, RESERVOIR_LOCATION_KINDS
from .downloader import download_state, init_cdaclient, list_reservoirs


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO-8601 datetime; assume UTC if no tzinfo provided."""
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date {value!r}; expected ISO-8601 (YYYY-MM-DD[THH:MM:SSZ])"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cwms-reservoir-downloader",
        description=(
            "Download USACE reservoir data for a U.S. state from the CWMS Data API. "
            "Reservoir locations are discovered automatically; their time series are "
            "saved to disk one file per series."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument(
        "--state",
        default="NM",
        help="Two-letter U.S. state code to download (default: NM).",
    )
    parser.add_argument(
        "--office",
        action="append",
        default=None,
        help=(
            "USACE district office ID (e.g. SPA). May be passed multiple times. "
            "Overrides the built-in state→office mapping."
        ),
    )
    parser.add_argument(
        "--location-kind",
        action="append",
        default=None,
        help=(
            "CWMS location-kind value to include "
            f"(default: {','.join(RESERVOIR_LOCATION_KINDS)}). "
            "May be passed multiple times."
        ),
    )
    parser.add_argument(
        "--timeseries-group",
        default=None,
        help=(
            "Regex for `timeseries-group-like` filter when querying the catalog. "
            "Defaults to None, which returns every series for the location. "
            "Set to 'DMZ Include List' for the public DMZ subset."
        ),
    )

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    parser.add_argument(
        "--begin",
        type=_parse_datetime,
        default=today - timedelta(days=30),
        help="Start of the download window (ISO-8601). Default: 30 days ago (UTC).",
    )
    parser.add_argument(
        "--end",
        type=_parse_datetime,
        default=today,
        help="End of the download window (ISO-8601). Default: today (UTC).",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Directory to write outputs into (default: ./data).",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "parquet", "json"),
        default="csv",
        help="File format for per-series outputs (default: csv).",
    )
    parser.add_argument(
        "--unit-system",
        choices=("EN", "SI"),
        default="EN",
        help="Unit system: EN (English) or SI (default: EN).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=20,
        help="Max parallel worker threads per time series request (default: 20).",
    )
    parser.add_argument(
        "--max-days-per-chunk",
        type=int,
        default=30,
        help="Max days of data per parallel request chunk (default: 30).",
    )
    parser.add_argument(
        "--max-catalog-workers",
        type=int,
        default=4,
        help=(
            "Max parallel threads fanning the per-location timeseries catalog "
            "queries (default: 4). Set to 1 to query sequentially."
        ),
    )
    parser.add_argument(
        "--max-download-workers",
        type=int,
        default=4,
        help=(
            "Max parallel threads fanning the per-timeseries downloads "
            "(default: 4). Effective peak concurrency against CDA is this "
            "value times --max-workers; keep modest on the public endpoint."
        ),
    )

    parser.add_argument(
        "--api-root",
        default=DEFAULT_API_ROOT,
        help=f"CDA root URL (default: {DEFAULT_API_ROOT}).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CDA_API_KEY"),
        help="CDA API key (or set CDA_API_KEY env var). Optional for public data.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("CDA_TOKEN"),
        help="OIDC bearer token (or set CDA_TOKEN env var). Optional for public data.",
    )

    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list reservoir locations and exit (no time series download).",
    )
    parser.add_argument(
        "--list-offices",
        action="store_true",
        help="Print the built-in state→office mapping and exit.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v INFO, -vv DEBUG).",
    )
    return parser


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    if args.list_offices:
        for state, offices in sorted(OFFICES_BY_STATE.items()):
            print(f"{state}: {', '.join(offices)}")
        return 0

    if args.end <= args.begin:
        parser.error("--end must be strictly after --begin")

    location_kinds = tuple(args.location_kind) if args.location_kind else RESERVOIR_LOCATION_KINDS
    offices = tuple(args.office) if args.office else None

    if args.list_only:
        init_cdaclient(api_root=args.api_root, api_key=args.api_key, token=args.token)
        df = list_reservoirs(args.state, offices=offices, location_kinds=location_kinds)
        if df.empty:
            print(f"No reservoir locations found for state {args.state}.", file=sys.stderr)
            return 1
        args.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = args.output_dir / f"{args.state.upper()}_reservoirs.csv"
        df.to_csv(out_path, index=False)
        print(f"{len(df)} reservoirs → {out_path}")
        return 0

    result = download_state(
        state=args.state,
        begin=args.begin,
        end=args.end,
        output_dir=args.output_dir,
        offices=offices,
        location_kinds=location_kinds,
        timeseries_group_like=args.timeseries_group,
        file_format=args.format,
        unit_system=args.unit_system,
        max_workers=args.max_workers,
        max_days_per_chunk=args.max_days_per_chunk,
        max_catalog_workers=args.max_catalog_workers,
        max_download_workers=args.max_download_workers,
        api_root=args.api_root,
        api_key=args.api_key,
        token=args.token,
    )
    print(
        f"State={result.state} offices={','.join(result.offices)} "
        f"reservoirs={len(result.reservoirs)} "
        f"timeseries={len(result.timeseries_catalog)} "
        f"downloaded={len(result.downloaded)} skipped={len(result.skipped)} "
        f"→ {result.output_dir}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
