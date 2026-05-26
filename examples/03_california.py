"""Example 3 — Folsom Lake, California (USACE Sacramento District, SPK).

Downloads one year of pool elevation, inflow, and outflow for Folsom Lake and
writes a multi-panel plot to ``examples/figures/ca_folsom.png``.

Run with::

    python examples/03_california.py
"""

from __future__ import annotations

from _plot_helpers import ReservoirExample, SeriesSpec, run_example


EXAMPLE = ReservoirExample(
    state="CA",
    office="SPK",
    location="Folsom Lake",
    title="Folsom Lake",
    days=365,
    series=(
        SeriesSpec(
            ts_id="Folsom Lake.Elev.Inst.~1Day.0.Rev-USBR-Combined",
            label="Pool Elevation (ft)",
            color="tab:blue",
        ),
        SeriesSpec(
            ts_id="Folsom Lake.Flow-Res In.Ave.~1Day.1Day.Rev-USBR-Combined",
            label="Reservoir Inflow (cfs)",
            color="tab:orange",
        ),
        SeriesSpec(
            ts_id="Folsom Lake.Flow-Res Out.Ave.~1Day.1Day.Calc-usbr",
            label="Reservoir Outflow (cfs)",
            color="tab:red",
        ),
    ),
)


if __name__ == "__main__":
    run_example(EXAMPLE, filename="ca_folsom.png")
