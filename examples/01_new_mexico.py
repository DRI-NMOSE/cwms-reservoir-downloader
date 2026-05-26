"""Example 1 — Abiquiu Reservoir, New Mexico (USACE Albuquerque District, SPA).

Downloads one year of elevation, storage, and inflow for Abiquiu Reservoir
and writes a multi-panel plot to ``examples/figures/nm_abiquiu.png``.

Run with::

    python examples/01_new_mexico.py
"""

from __future__ import annotations

from _plot_helpers import ReservoirExample, SeriesSpec, run_example


EXAMPLE = ReservoirExample(
    state="NM",
    office="SPA",
    location="Abiquiu",
    title="Abiquiu Reservoir",
    days=365,
    series=(
        SeriesSpec(
            ts_id="Abiquiu.Elev.Inst.~1Day.0.MRS",
            label="Elevation (ft)",
            color="tab:blue",
        ),
        SeriesSpec(
            ts_id="Abiquiu.Stor.Inst.~1Day.0.MRS",
            label="Storage (ac-ft)",
            color="tab:green",
        ),
        SeriesSpec(
            ts_id="Abiquiu.Flow-Res In.Ave.~1Day.1Day.MRS",
            label="Inflow (cfs)",
            color="tab:orange",
        ),
    ),
)


if __name__ == "__main__":
    run_example(EXAMPLE, filename="nm_abiquiu.png")
