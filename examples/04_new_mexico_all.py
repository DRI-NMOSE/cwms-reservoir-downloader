"""Example 4 — Full elevation record for every reservoir in New Mexico (SPA).

Discovers every reservoir location in NM via the CWMS Data API, downloads the
*entire* available pool-elevation record for each one, writes per-reservoir
CSVs to ``examples/data/nm_elevations/``, and renders a combined plot to
``examples/figures/nm_all_elevations.png``.

Run with::

    python examples/04_new_mexico_all.py
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

# Silence an upstream pandas FutureWarning emitted by cwms-python's internal
# pd.concat call. Nothing we can fix at the call site; remove once cwms-python
# updates.
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
    category=FutureWarning,
    module=r"cwms\.timeseries\.timeseries",
)

import cwms  # noqa: E402  (import after warnings filter is intentional)
from cwms_reservoir_downloader import list_reservoirs, list_timeseries_for_locations  # noqa: E402

from _plot_helpers import FIGURES_DIR  # noqa: E402

STATE = "NM"
UNIT_SYSTEM = "EN"

# CWMS records do not predate the mid-20th century; this is a safe lower bound
# for "everything available".
HISTORY_BEGIN = datetime(1900, 1, 1, tzinfo=timezone.utc)

DATA_DIR = Path(__file__).resolve().parent / "data" / "nm_elevations"
PLOT_OUTPUT = FIGURES_DIR / "nm_all_elevations.png"


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def elevation_series_per_location(catalog: pd.DataFrame) -> pd.DataFrame:
    """Pick one elevation series per location.

    CWMS time series IDs are ``Location.Param.Type.Interval.Duration.Version``.
    We keep rows where ``Param == "Elev"`` and, when a location has several
    candidates, prefer the ``DCP-rev`` version (long district SCADA history,
    typically back to the late 1990s) over the short-history ``MRS`` series.
    Within a single version we then prefer daily over sub-daily so the CSV
    stays a manageable size when both cadences exist.
    """
    name_col = "name" if "name" in catalog.columns else "timeseries-id"
    parts = catalog[name_col].str.split(".", expand=True)
    parts.columns = ["loc", "param", "type", "interval", "duration", "version"]
    elev = catalog.assign(**parts).query("param == 'Elev'").copy()

    version_rank = {"DCP-rev": 0, "MRS-Rev": 1, "MRS": 2}
    interval_rank = {"~1Day": 0, "1Day": 1, "1Hour": 2, "~1Hour": 3}
    elev["v_rank"] = elev["version"].map(version_rank).fillna(9).astype(int)
    elev["i_rank"] = elev["interval"].map(interval_rank).fillna(9).astype(int)
    elev = (
        elev.sort_values(["location", "v_rank", "i_rank"])
        .drop_duplicates("location", keep="first")
    )
    return elev[[name_col, "office-id", "location"]].rename(columns={name_col: "ts_id"})


def fetch_and_save(
    picks: pd.DataFrame, begin: datetime, end: datetime, data_dir: Path
) -> list[tuple[str, str, pd.DataFrame, Path]]:
    """Download each picked series in full and write its CSV.

    Reservoirs are downloaded sequentially. ``cwms.get_timeseries`` still
    parallelizes the *within-series* time-window chunks for us, so each
    reservoir's download is itself multi-threaded under the hood.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, str, pd.DataFrame, Path]] = []
    for _, row in picks.iterrows():
        ts_id = row["ts_id"]
        location = row["location"]
        print(f"  → {location}: starting ({ts_id})", flush=True)
        try:
            data = cwms.get_timeseries(
                ts_id=ts_id,
                office_id=row["office-id"],
                unit=UNIT_SYSTEM,
                begin=begin,
                end=end,
            )
        except Exception as exc:  # noqa: BLE001 - API/network errors vary
            print(f"  ! {ts_id}: {exc}", flush=True)
            continue

        df = data.df
        if df is None or df.empty:
            print(f"  - {ts_id}: no data returned", flush=True)
            continue

        df = df.copy()
        df["date-time"] = pd.to_datetime(df["date-time"], utc=True)
        df = df.sort_values("date-time")

        csv_path = data_dir / f"{_safe_filename(location)}__{_safe_filename(ts_id)}.csv"
        df.to_csv(csv_path, index=False)
        print(f"  + {location}: {len(df):,} rows → {csv_path.name}", flush=True)
        results.append((location, ts_id, df, csv_path))

    return results


def render(
    series: list[tuple[str, str, pd.DataFrame, Path]], output: Path
) -> Path:
    fig, ax = plt.subplots(figsize=(12, 6))
    cmap = plt.get_cmap("tab20")
    for i, (location, _ts_id, df, _path) in enumerate(series):
        ax.plot(
            df["date-time"],
            df["value"],
            color=cmap(i % cmap.N),
            linewidth=1.0,
            label=location,
        )

    ax.set_ylabel("Elevation (ft)")
    ax.set_xlabel("Date (UTC)")
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
    fig.suptitle("All NM reservoirs — pool elevation (full available record)", fontsize=13)
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 0.85, 0.97))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output


def main() -> Path:
    cwms.init_session(api_root="https://cwms-data.usace.army.mil/cwms-data/")

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    print(f"[{STATE}] discovering reservoirs…", flush=True)
    reservoirs = list_reservoirs(STATE)
    print(f"[{STATE}] found {len(reservoirs)} reservoir locations", flush=True)
    if reservoirs.empty:
        raise SystemExit(f"No reservoirs returned for state {STATE!r}")

    print(f"[{STATE}] cataloging time series…", flush=True)
    catalog = list_timeseries_for_locations(reservoirs)
    if catalog.empty:
        raise SystemExit(f"No timeseries catalog entries for state {STATE!r}")

    picks = elevation_series_per_location(catalog)
    print(f"[{STATE}] {len(picks)} reservoirs have an elevation series", flush=True)

    print(
        f"[{STATE}] downloading full elevation records "
        f"(sequential; the long DCP-rev series can take several minutes "
        f"each) → {DATA_DIR}",
        flush=True,
    )
    series = fetch_and_save(picks, HISTORY_BEGIN, end, DATA_DIR)
    if not series:
        raise SystemExit("No elevation data returned for any NM reservoir")

    out = render(series, PLOT_OUTPUT)
    print(
        f"[{STATE}] saved {out} "
        f"({len(series)} reservoirs plotted, CSVs in {DATA_DIR})",
        flush=True,
    )
    return out


if __name__ == "__main__":
    main()
