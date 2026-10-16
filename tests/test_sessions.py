import pytest

from f1_dash.data.sessions import EventNotFound, SessionNotAvailable, load_session


def test_fuzzy_name_rejected():
    with pytest.raises(EventNotFound):
        load_session(2021, "French GP", "Q")


def test_bad_session_type():
    with pytest.raises(SessionNotAvailable):
        load_session(2021, "French Grand Prix", "ZZ")


def test_flags_reuse_cache(monkeypatch):
    from unittest.mock import MagicMock

    import pandas as pd

    from f1_dash.data import sessions

    s = MagicMock()
    s.event = {"EventName": "X Grand Prix"}
    s.results = s.laps = s.weather_data = s.race_control_messages = pd.DataFrame()
    monkeypatch.setattr(sessions.fastf1, "get_session", MagicMock(return_value=s))
    monkeypatch.setattr(sessions, "enable_cache", lambda: None)
    sessions._CACHE.clear()
    args = (2099, "X Grand Prix", "R")
    sessions.load_session(*args)
    sessions.load_session(*args, telemetry=True)
    assert s.load.call_count == 2  # sin telemetría, luego la unión
    sessions.load_session(*args)
    sessions.load_session(*args, telemetry=True)
    assert s.load.call_count == 2  # lo cacheado ya cubre ambos
    sessions._CACHE.clear()


def test_telemetry_vuelta_inexistente():
    import pandas as pd
    import pytest
    from types import SimpleNamespace
    from f1_dash.data.sessions import SessionNotAvailable, telemetry

    laps = pd.DataFrame({"LapNumber": [1, 2]})
    laps.pick_drivers = lambda d: laps  # DataFrame admite atributos sueltos solo vía asignación
    data = SimpleNamespace(_raw=SimpleNamespace(laps=laps))
    with pytest.raises(SessionNotAvailable, match="99"):
        telemetry(data, "VER", 99)
