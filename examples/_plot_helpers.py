"""Shared helpers for the reservoir example scripts.

Each example downloads a handful of pre-selected time series for one reservoir
and renders a multi-panel matplotlib figure. Keeping the download/plot logic
here lets the per-state scripts stay short and read like configuration.
"""

from __future__ import annotations

import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

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

FIGURES_DIR = Path(__file__).resolve().parent / "figures"


@dataclass(frozen=True)
class SeriesSpec:
    """One panel of a reservoir figure."""

    ts_id: str
    label: str
    color: str = "tab:blue"


@dataclass(frozen=True)
class ReservoirExample:
    """Configuration for a single example run."""

    state: str
    office: str
    location: str
    title: str
    series: tuple[SeriesSpec, ...]
    days: int = 365
    unit_system: str = "EN"


def fetch_series(
    spec: SeriesSpec,
    office: str,
    begin: datetime,
    end: datetime,
    unit_system: str,
) -> pd.DataFrame:
    """Download one time series and return a DataFrame with date-time and value."""
    data = cwms.get_timeseries(
        ts_id=spec.ts_id,
        office_id=office,
        unit=unit_system,
        begin=begin,
        end=end,
    )
    df = data.df
    if df is None or df.empty:
        return pd.DataFrame(columns=["date-time", "value"])
    df = df.copy()
    df["date-time"] = pd.to_datetime(df["date-time"], utc=True)
    return df.sort_values("date-time")


def render(example: ReservoirExample, output: Path) -> Path:
    """Download every series in *example* and write a PNG to *output*."""
    cwms.init_session(api_root="https://cwms-data.usace.army.mil/cwms-data/")

    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    begin = end - timedelta(days=example.days)

    # Fan the per-series fetches out to a small thread pool. executor.map
    # preserves submission order so plot panels stay in the order declared
    # by example.series.
    workers = min(len(example.series), 4) or 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        dfs = list(
            ex.map(
                lambda spec: fetch_series(spec, example.office, begin, end, example.unit_system),
                example.series,
            )
        )
    frames = list(zip(example.series, dfs))

    n = len(frames)
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.6 * n + 0.6), sharex=True)
    if n == 1:
        axes = [axes]

    for ax, (spec, df) in zip(axes, frames):
        if df.empty:
            ax.text(
                0.5,
                0.5,
                f"No data returned for\n{spec.ts_id}",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color="firebrick",
            )
        else:
            ax.plot(df["date-time"], df["value"], color=spec.color, linewidth=1.1)
            ax.set_ylabel(spec.label)
            ax.grid(True, alpha=0.3)
        ax.set_title(spec.ts_id, fontsize=9, loc="left", color="dimgray")

    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=10))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[-1].set_xlabel("Date (UTC)")

    fig.suptitle(
        f"{example.title}  ({example.state} / {example.office})  "
        f"— last {example.days} days",
        fontsize=13,
    )
    fig.autofmt_xdate()
    fig.tight_layout(rect=(0, 0, 1, 0.97))

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output


def run_example(example: ReservoirExample, *, filename: str | None = None) -> Path:
    """Convenience wrapper used by the per-state scripts."""
    name = filename or f"{example.state.lower()}_{example.location.lower().replace(' ', '_')}.png"
    out = FIGURES_DIR / name
    print(f"[{example.state}] downloading {len(example.series)} series for "
          f"{example.location} ({example.office}) → {out}")
    render(example, out)
    print(f"[{example.state}] saved {out}")
    return out


__all__ = [
    "FIGURES_DIR",
    "ReservoirExample",
    "SeriesSpec",
    "render",
    "run_example",
]
