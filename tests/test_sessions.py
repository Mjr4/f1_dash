import pytest

from f1_dash.data.sessions import EventNotFound, SessionNotAvailable, load_session


def test_fuzzy_name_rejected():
    with pytest.raises(EventNotFound):
        load_session(2021, "French GP", "Q")


def test_bad_session_type():
    with pytest.raises(SessionNotAvailable):
        load_session(2021, "French Grand Prix", "ZZ")
