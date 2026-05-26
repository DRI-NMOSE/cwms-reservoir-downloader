"""Core download logic: discover reservoir locations and pull their time series."""

from __future__ import annotations

import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd

import cwms

from .config import (
    DEFAULT_API_ROOT,
    RESERVOIR_LOCATION_KINDS,
    offices_for_state,
)

log = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Summary of a `download_state` run."""

    state: str
    offices: tuple[str, ...]
    reservoirs: pd.DataFrame
    timeseries_catalog: pd.DataFrame
    downloaded: list[Path] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    output_dir: Path = field(default_factory=lambda: Path("data"))


def init_cdaclient(
    api_root: str = DEFAULT_API_ROOT,
    api_key: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """Configure the underlying `cwms-python` session."""
    cwms.init_session(api_root=api_root, api_key=api_key, token=token)


def _normalize_kinds(kinds: Sequence[str]) -> str:
    """Build a Posix regex matching the requested location kinds."""
    cleaned = [k.strip().upper() for k in kinds if k and k.strip()]
    if not cleaned:
        return ""
    return "(" + "|".join(cleaned) + ")"


def list_reservoirs(
    state: str,
    offices: Optional[Sequence[str]] = None,
    location_kinds: Sequence[str] = RESERVOIR_LOCATION_KINDS,
) -> pd.DataFrame:
    """Return a DataFrame of reservoir/project locations physically located in *state*.

    Parameters
    ----------
    state:
        Two-letter U.S. state code (e.g. ``"NM"``).
    offices:
        USACE office IDs to query. Defaults to the mapping in :data:`config.OFFICES_BY_STATE`.
    location_kinds:
        CWMS location-kind values that count as reservoir infrastructure.
    """
    state_code = state.strip().upper()
    office_ids = tuple(offices) if offices else offices_for_state(state_code)
    kind_regex = _normalize_kinds(location_kinds)

    frames: list[pd.DataFrame] = []
    for office in office_ids:
        log.info("Fetching locations catalog for office=%s", office)
        catalog = cwms.get_locations_catalog(
            office_id=office,
            location_kind_like=kind_regex or None,
            page_size=5000,
        )
        df = catalog.df
        if df is None or df.empty:
            log.warning("No locations returned for office=%s", office)
            continue
        df = df.copy()
        df["query-office"] = office
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    # Filter to the requested state. The catalog response uses dotted/dashed names;
    # accept either flat or nested representations.
    state_col = _resolve_column(combined, ("state-initial", "stateInitial", "state"))
    if state_col is None:
        log.warning(
            "Locations catalog did not include a state column; returning unfiltered "
            "results for office(s) %s. Inspect the output and refine manually.",
            office_ids,
        )
        return combined

    mask = combined[state_col].astype(str).str.upper() == state_code
    filtered = combined.loc[mask].reset_index(drop=True)
    log.info(
        "Found %d reservoir locations in %s across offices %s",
        len(filtered),
        state_code,
        office_ids,
    )
    return filtered


def _resolve_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def list_timeseries_for_locations(
    locations: pd.DataFrame,
    office_column: str = "office-id",
    name_column: str = "name",
    timeseries_group_like: Optional[str] = None,
    max_catalog_workers: int = 4,
) -> pd.DataFrame:
    """For each location, query the CWMS timeseries catalog for matching IDs.

    CWMS time series IDs are dotted strings of the form
    ``Location.Param.Type.Interval.Duration.Version``. We match every series
    whose ID starts with the location name.

    Set ``max_catalog_workers`` > 1 to fan the per-location catalog queries
    out to a thread pool; pick a small number (default 4) to stay polite to
    the public CDA endpoint.
    """
    if locations.empty:
        return pd.DataFrame()

    office_col = _resolve_column(locations, (office_column, "office", "officeId"))
    name_col = _resolve_column(locations, (name_column, "location-id", "id"))
    if office_col is None or name_col is None:
        raise ValueError(
            f"locations DataFrame is missing required columns "
            f"(need an office column and a name column); got {list(locations.columns)}"
        )

    pairs: list[tuple[str, str]] = [
        (row[office_col], row[name_col])
        for _, row in locations[[office_col, name_col]].drop_duplicates().iterrows()
        if isinstance(row[office_col], str) and isinstance(row[name_col], str)
    ]

    def _fetch_one(office: str, location: str) -> Optional[pd.DataFrame]:
        like = re.escape(location) + r"\..*"
        try:
            catalog = cwms.get_timeseries_catalog(
                office_id=office,
                like=like,
                timeseries_group_like=timeseries_group_like,
                page_size=5000,
            )
        except Exception as exc:  # noqa: BLE001 - network/API errors vary by office
            log.warning("Timeseries catalog query failed for %s/%s: %s", office, location, exc)
            return None
        df = catalog.df
        if df is None or df.empty:
            return None
        df = df.copy()
        df["location"] = location
        df["office-id"] = office
        return df

    frames: list[pd.DataFrame] = []
    workers = max(1, int(max_catalog_workers))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_fetch_one, office, location) for office, location in pairs]
        for fut in as_completed(futures):
            df = fut.result()
            if df is not None:
                frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _safe_filename(name: str) -> str:
    """Sanitize a CWMS time series ID for use as a filename."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def download_state(
    state: str,
    begin: datetime,
    end: datetime,
    output_dir: Path,
    offices: Optional[Sequence[str]] = None,
    location_kinds: Sequence[str] = RESERVOIR_LOCATION_KINDS,
    timeseries_group_like: Optional[str] = None,
    file_format: str = "csv",
    unit_system: str = "EN",
    max_workers: int = 20,
    max_days_per_chunk: int = 30,
    max_catalog_workers: int = 4,
    max_download_workers: int = 4,
    api_root: str = DEFAULT_API_ROOT,
    api_key: Optional[str] = None,
    token: Optional[str] = None,
) -> DownloadResult:
    """Discover reservoir locations in *state* and download their time series.

    Files are written to ``<output_dir>/<state>/<office>/<location>/<ts_id>.<ext>``.
    A manifest CSV is written to ``<output_dir>/<state>/manifest.csv``.

    Parallelism is layered:

    * ``max_catalog_workers`` — threads fanning per-location catalog queries.
    * ``max_download_workers`` — threads fanning the per-timeseries downloads.
    * ``max_workers`` / ``max_days_per_chunk`` — passed through to
      ``cwms.get_timeseries`` for *intra*-series chunking. The effective peak
      concurrency against CDA is ``max_download_workers * max_workers``, so
      keep the outer pool modest on the public endpoint.
    """
    init_cdaclient(api_root=api_root, api_key=api_key, token=token)

    if begin.tzinfo is None:
        begin = begin.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    state_code = state.strip().upper()
    state_dir = Path(output_dir) / state_code
    state_dir.mkdir(parents=True, exist_ok=True)

    reservoirs = list_reservoirs(state_code, offices=offices, location_kinds=location_kinds)
    reservoirs.to_csv(state_dir / "reservoirs.csv", index=False)
    log.info("Wrote %d reservoir records → %s", len(reservoirs), state_dir / "reservoirs.csv")

    catalog = list_timeseries_for_locations(
        reservoirs,
        timeseries_group_like=timeseries_group_like,
        max_catalog_workers=max_catalog_workers,
    )
    catalog.to_csv(state_dir / "timeseries_catalog.csv", index=False)
    log.info(
        "Wrote %d timeseries catalog entries → %s",
        len(catalog),
        state_dir / "timeseries_catalog.csv",
    )

    result = DownloadResult(
        state=state_code,
        offices=tuple(offices) if offices else offices_for_state(state_code),
        reservoirs=reservoirs,
        timeseries_catalog=catalog,
        output_dir=state_dir,
    )

    if catalog.empty:
        log.warning("No timeseries to download for state %s", state_code)
        return result

    ts_id_col = _resolve_column(catalog, ("name", "timeseries-id", "ts-id"))
    office_col = _resolve_column(catalog, ("office-id", "office"))
    if ts_id_col is None or office_col is None:
        raise ValueError(
            f"Cannot locate timeseries id/office columns in catalog: {list(catalog.columns)}"
        )

    jobs: list[tuple[str, str, str]] = [
        (row[ts_id_col], row[office_col], row["location"])
        for _, row in catalog[[ts_id_col, office_col, "location"]].drop_duplicates().iterrows()
        if isinstance(row[ts_id_col], str) and isinstance(row[office_col], str)
    ]

    result_lock = threading.Lock()

    def _download_one(ts_id: str, office: str, location: str) -> None:
        ts_dir = state_dir / office / _safe_filename(str(location))
        ts_dir.mkdir(parents=True, exist_ok=True)
        out_path = ts_dir / f"{_safe_filename(ts_id)}.{file_format}"

        try:
            data = cwms.get_timeseries(
                ts_id=ts_id,
                office_id=office,
                unit=unit_system,
                begin=begin,
                end=end,
                max_workers=max_workers,
                max_days_per_chunk=max_days_per_chunk,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to fetch %s @ %s: %s", ts_id, office, exc)
            with result_lock:
                result.skipped.append((ts_id, str(exc)))
            return

        df = data.df
        if df is None or df.empty:
            log.info("No data in window for %s", ts_id)
            with result_lock:
                result.skipped.append((ts_id, "empty"))
            return

        _write_dataframe(df, out_path, file_format)
        with result_lock:
            result.downloaded.append(out_path)
        log.info("Saved %s (%d rows)", out_path, len(df))

    workers = max(1, int(max_download_workers))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_download_one, ts_id, office, location)
                   for ts_id, office, location in jobs]
        for fut in as_completed(futures):
            fut.result()  # surface unexpected exceptions

    manifest_path = state_dir / "manifest.csv"
    pd.DataFrame(
        {"path": [str(p) for p in sorted(result.downloaded)]}
    ).to_csv(manifest_path, index=False)
    log.info("Wrote manifest → %s (%d files)", manifest_path, len(result.downloaded))
    return result


def _write_dataframe(df: pd.DataFrame, path: Path, fmt: str) -> None:
    fmt = fmt.lower()
    if fmt == "csv":
        df.to_csv(path, index=False)
    elif fmt == "parquet":
        df.to_parquet(path, index=False)
    elif fmt == "json":
        df.to_json(path, orient="records", date_format="iso")
    else:
        raise ValueError(f"Unsupported file format: {fmt!r} (use csv, parquet, or json)")
