"""Example 2 — Eufaula Lake, Oklahoma (USACE Tulsa District, SWT).

Downloads one year of pool elevation, controlled outflow, and tailwater
elevation for Eufaula Lake and writes a multi-panel plot to
``examples/figures/ok_eufaula.png``.

Run with::

    python examples/02_oklahoma.py
"""

from __future__ import annotations

from _plot_helpers import ReservoirExample, SeriesSpec, run_example


EXAMPLE = ReservoirExample(
    state="OK",
    office="SWT",
    location="EUFA",
    title="Eufaula Lake",
    days=365,
    series=(
        SeriesSpec(
            ts_id="EUFA.Elev.Inst.1Hour.0.Ccp-Rev",
            label="Pool Elevation (ft)",
            color="tab:blue",
        ),
        SeriesSpec(
            ts_id="EUFA.Flow-Res Out.Ave.1Hour.1Hour.Rev-Regi-Flowgroup",
            label="Reservoir Outflow (cfs)",
            color="tab:red",
        ),
        SeriesSpec(
            ts_id="EUFA.Elev-Tailwater.Inst.1Hour.0.Ccp-Rev",
            label="Tailwater Elev (ft)",
            color="tab:purple",
        ),
    ),
)


if __name__ == "__main__":
    run_example(EXAMPLE, filename="ok_eufaula.png")
