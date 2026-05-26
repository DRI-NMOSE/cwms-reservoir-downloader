"""Download USACE reservoir data via the CWMS Data API (CDA).

This package wraps the official `cwms-python` client to make it easy to
retrieve reservoir locations and their associated time series for an entire
U.S. state from the command line.
"""

from importlib.metadata import PackageNotFoundError, version

from .config import OFFICES_BY_STATE, RESERVOIR_LOCATION_KINDS
from .downloader import (
    DownloadResult,
    download_state,
    list_reservoirs,
    list_timeseries_for_locations,
)

try:
    __version__ = version("cwms-reservoir-downloader")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = [
    "OFFICES_BY_STATE",
    "RESERVOIR_LOCATION_KINDS",
    "DownloadResult",
    "download_state",
    "list_reservoirs",
    "list_timeseries_for_locations",
    "__version__",
]
