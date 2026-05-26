"""Entry point for ``python -m cwms_reservoir_downloader``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
