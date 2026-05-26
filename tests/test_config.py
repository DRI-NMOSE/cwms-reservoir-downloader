import pytest

from cwms_reservoir_downloader.config import OFFICES_BY_STATE, offices_for_state


def test_nm_maps_to_spa():
    assert "SPA" in offices_for_state("NM")
    assert "SPA" in offices_for_state("nm")


def test_unknown_state_raises():
    with pytest.raises(KeyError):
        offices_for_state("ZZ")


def test_all_offices_are_strings():
    for state, offices in OFFICES_BY_STATE.items():
        assert isinstance(state, str) and len(state) == 2
        assert offices and all(isinstance(o, str) and o.isupper() for o in offices)
