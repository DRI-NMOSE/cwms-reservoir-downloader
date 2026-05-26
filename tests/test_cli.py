import pytest

from cwms_reservoir_downloader.cli import build_parser


def test_default_state_is_nm():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.state == "NM"
    assert args.format == "csv"
    assert args.unit_system == "EN"


def test_repeatable_office_flag():
    parser = build_parser()
    args = parser.parse_args(["--office", "SPA", "--office", "SWT"])
    assert args.office == ["SPA", "SWT"]


def test_list_offices_flag():
    parser = build_parser()
    args = parser.parse_args(["--list-offices"])
    assert args.list_offices is True


def test_invalid_date_rejected():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--begin", "not-a-date"])


def test_parallelism_flag_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    assert args.max_catalog_workers == 4
    assert args.max_download_workers == 4


def test_parallelism_flags_override():
    parser = build_parser()
    args = parser.parse_args(
        ["--max-catalog-workers", "1", "--max-download-workers", "8"]
    )
    assert args.max_catalog_workers == 1
    assert args.max_download_workers == 8
