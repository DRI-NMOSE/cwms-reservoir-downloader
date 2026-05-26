"""Static configuration: state-to-office mappings and CDA defaults."""

from __future__ import annotations

DEFAULT_API_ROOT = "https://cwms-data.usace.army.mil/cwms-data/"

# USACE District offices that own CWMS data for projects located in each state.
# A state can be covered by more than one district; we query each in turn and
# then filter results by `state-initial` to drop locations physically outside
# the requested state (districts often own gauges in neighboring states).
#
# Sources: USACE district boundaries, plus the office-id values seen in the
# CDA `state-initial` test fixtures of cwms-data-api.
OFFICES_BY_STATE: dict[str, tuple[str, ...]] = {
    "NM": ("SPA",),                 # Albuquerque District (primary)
    "CO": ("SPA", "NWO"),           # Albuquerque + Omaha
    "TX": ("SWF", "SWG", "SWT"),    # Fort Worth, Galveston, Tulsa
    "OK": ("SWT",),                 # Tulsa
    "KS": ("SWT", "NWK"),           # Tulsa + Kansas City
    "AZ": ("SPL",),                 # Los Angeles
    "CA": ("SPK", "SPL"),           # Sacramento, Los Angeles
    "NV": ("SPK",),                 # Sacramento
    "UT": ("SPK",),                 # Sacramento
    "OR": ("NWP", "NWW"),           # Portland, Walla Walla
    "WA": ("NWS", "NWW"),           # Seattle, Walla Walla
    "ID": ("NWW",),                 # Walla Walla
    "MT": ("NWO", "NWS"),           # Omaha, Seattle
    "ND": ("NWO", "MVP"),           # Omaha, St. Paul
    "SD": ("NWO",),                 # Omaha
    "NE": ("NWO", "NWK"),           # Omaha, Kansas City
    "WY": ("NWO",),                 # Omaha
    "MN": ("MVP",),                 # St. Paul
    "WI": ("MVP", "MVR", "LRE"),    # St. Paul, Rock Island, Detroit
    "IA": ("MVR", "NWK"),           # Rock Island, Kansas City
    "MO": ("MVS", "NWK"),           # St. Louis, Kansas City
    "IL": ("MVS", "MVR", "MVM"),    # St. Louis, Rock Island, Memphis
    "AR": ("SWL", "MVK", "MVM"),    # Little Rock, Vicksburg, Memphis
    "LA": ("MVN", "MVK"),           # New Orleans, Vicksburg
    "MS": ("MVK", "MVN"),           # Vicksburg, New Orleans
    "TN": ("MVM", "LRN"),           # Memphis, Nashville
    "KY": ("LRN", "LRL", "LRH"),    # Nashville, Louisville, Huntington
    "OH": ("LRH", "LRP", "LRB"),    # Huntington, Pittsburgh, Buffalo
    "WV": ("LRH", "LRP"),           # Huntington, Pittsburgh
    "PA": ("LRP", "NAB", "NAP"),    # Pittsburgh, Baltimore, Philadelphia
    "NY": ("LRB", "NAN"),           # Buffalo, New York
    "MD": ("NAB",),                 # Baltimore
    "VA": ("NAO", "NAB"),           # Norfolk, Baltimore
    "NC": ("SAW",),                 # Wilmington
    "SC": ("SAC", "SAS"),           # Charleston, Savannah
    "GA": ("SAS", "SAM"),           # Savannah, Mobile
    "FL": ("SAJ", "SAM"),           # Jacksonville, Mobile
    "AL": ("SAM",),                 # Mobile
    "MI": ("LRE",),                 # Detroit
    "IN": ("LRL", "LRE"),           # Louisville, Detroit
    "MA": ("NAE",),                 # New England
    "CT": ("NAE",),                 # New England
    "VT": ("NAE",),                 # New England
    "NH": ("NAE",),                 # New England
    "ME": ("NAE",),                 # New England
    "RI": ("NAE",),                 # New England
    "NJ": ("NAP", "NAN"),           # Philadelphia, New York
    "DE": ("NAP",),                 # Philadelphia
    "AK": ("POA",),                 # Alaska
    "HI": ("POH",),                 # Honolulu
}

# Location kinds in CWMS that represent reservoir / dam infrastructure.
# A "PROJECT" location is the canonical reservoir record; the others describe
# components of a project (embankment, outlet works, etc.).
RESERVOIR_LOCATION_KINDS: tuple[str, ...] = (
    "PROJECT",
    "EMBANKMENT",
    "OUTLET",
    "OVERFLOW",
    "TURBINE",
    "LOCK",
    "GATE",
)


def offices_for_state(state: str) -> tuple[str, ...]:
    """Return the tuple of USACE office IDs that cover the given U.S. state.

    Raises KeyError if the state has no known mapping.
    """
    key = state.strip().upper()
    if key not in OFFICES_BY_STATE:
        raise KeyError(
            f"No office mapping for state {key!r}. "
            f"Pass --office explicitly or extend OFFICES_BY_STATE."
        )
    return OFFICES_BY_STATE[key]
