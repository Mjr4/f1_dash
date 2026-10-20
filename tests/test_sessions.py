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
    data = SimpleNamespace(year=2021, event="X", session_type="R", _raw=SimpleNamespace(laps=laps, car_data={"1": 1}))
    with pytest.raises(SessionNotAvailable, match="99"):
        telemetry(data, "VER", 99)


def test_cache_ttl_y_lru(monkeypatch):
    from types import SimpleNamespace

    from f1_dash.data import sessions

    monkeypatch.setattr(sessions, "_resolve", lambda y, e, st: SimpleNamespace(event={"EventName": str(e)}))
    monkeypatch.setattr(sessions, "_load", lambda s, y, st, *f: (y, st))
    monkeypatch.setattr(sessions, "_MAX", 2)
    now = [0.0]
    monkeypatch.setattr(sessions.time, "monotonic", lambda: now[0])
    sessions._CACHE.clear()
    sessions.load_session(1, "A", "R")
    sessions.load_session(1, "B", "R")
    sessions.load_session(1, "A", "R")  # A pasa a ser la más reciente
    sessions.load_session(1, "C", "R")  # expulsa B (LRU)
    assert set(sessions._CACHE) == {(1, "A", "R"), (1, "C", "R")}
    now[0] = sessions._TTL + 1
    sessions.load_session(1, "A", "R")  # vencida: recarga con t nuevo
    assert sessions._CACHE[(1, "A", "R")][2] == now[0]
    sessions._CACHE.clear()


def test_clave_normalizada(monkeypatch):
    from types import SimpleNamespace

    from f1_dash.data import sessions

    monkeypatch.setattr(sessions, "_resolve", lambda y, e, st: SimpleNamespace(event={"EventName": "Monza"}))
    monkeypatch.setattr(sessions, "_load", lambda s, y, st, *f: object())
    sessions._CACHE.clear()
    assert sessions.load_session(1, 5, "R") is sessions.load_session(1, "Monza", "R")
    sessions._CACHE.clear()


def test_datos_no_cargados_son_dataerror():
    import pandas as pd
    from fastf1.exceptions import DataNotLoadedError

    from f1_dash.data import sessions

    def boom(self):
        raise DataNotLoadedError("no cargado")

    class S:  # como FastF1: load() no falla, pero el acceso a lo que no cargó sí
        event = {"EventName": "X"}
        results = pd.DataFrame()
        def load(self, **kw): pass

    class SinClima(S):
        laps = pd.DataFrame()
        weather_data = property(boom)

    class SinVueltas(S):
        laps = property(boom)

    assert sessions._load(SinClima(), 2021, "R", False, True, False).weather is None
    with pytest.raises(SessionNotAvailable):
        sessions._load(SinVueltas(), 2021, "R", False, False, False)
    with pytest.raises(SessionNotAvailable, match="cuenta F1 TV"):
        sessions._load(SinVueltas(), 2024, "R", False, False, False)


def test_telemetry_sesion_sin_telemetria():
    from types import SimpleNamespace

    from f1_dash.data.sessions import SessionNotAvailable, telemetry

    data = SimpleNamespace(year=2026, event="X", session_type="R", _raw=SimpleNamespace(car_data={}))
    with pytest.raises(SessionNotAvailable, match="no tiene telemetría"):
        telemetry(data, "VER")


def test_load_clasifica_errores_de_carga():
    import pytest
    import requests

    from f1_dash.data import sessions
    from f1_dash.data.sessions import SessionNotAvailable, TransientError

    def fallar(exc):
        class S:
            event = {"EventName": "X"}
            def load(self, **kw): raise exc
        return S()

    with pytest.raises(TransientError):
        sessions._load(fallar(requests.ConnectionError("sin red")), 2021, "R", False, False, False)
    with pytest.raises(TransientError):
        sessions._load(fallar(TimeoutError()), 2021, "R", False, False, False)
    with pytest.raises(SessionNotAvailable) as ei:  # la fuente no tiene datos: determinista, se cachea
        sessions._load(fallar(ValueError("sin datos")), 2021, "R", False, False, False)
    assert not isinstance(ei.value, TransientError)


def test_session_is_recent(monkeypatch):
    from types import SimpleNamespace

    import pandas as pd

    from f1_dash.data import schedule

    ahora = pd.Timestamp.now("UTC").tz_localize(None)
    for delta, esperado in ((pd.Timedelta(hours=-2), True), (pd.Timedelta(days=-3), False), (pd.Timedelta(days=1), True)):
        ev = SimpleNamespace(get_session_date=lambda t, utc: ahora + delta)
        monkeypatch.setattr(schedule.fastf1, "get_event", lambda y, e, ev=ev: ev)
        assert schedule.session_is_recent(2026, "X", "R") is esperado

    def sin_red(y, e):
        raise OSError

    monkeypatch.setattr(schedule.fastf1, "get_event", sin_red)
    assert schedule.session_is_recent(2026, "X", "R") is False


def test_sessions_held(monkeypatch):
    import pandas as pd

    from f1_dash.data import schedule

    ahora = pd.Timestamp.now("UTC").tz_localize(None)
    h = pd.Timedelta(hours=1)
    ev = {"Session1": "Practice 1", "Session1DateUtc": ahora - 48 * h, "Session2": "Sprint Shootout", "Session2DateUtc": ahora - 24 * h,
          "Session3": "Sprint", "Session3DateUtc": ahora - h, "Session4": "Qualifying", "Session4DateUtc": ahora + h,
          "Session5": "Race", "Session5DateUtc": ahora + 24 * h}
    monkeypatch.setattr(schedule.fastf1, "get_event", lambda y, e: ev)
    assert schedule.sessions_held(2023, "X") == ["FP1", "SQ", "S"]  # Q y R no han empezado
    monkeypatch.setattr(schedule.fastf1, "get_event", lambda y, e: (_ for _ in ()).throw(OSError))
    assert schedule.sessions_held(2023, "X") == schedule.SESSION_TYPES  # sin calendario: no bloquea


def test_cached_only_filtra_a_lo_que_hay_en_cache(tmp_path, monkeypatch):
    from f1_dash.data import schedule
    race = tmp_path / "2026" / "2026-10-11_Singapore_Grand_Prix" / "2026-10-11_Race"
    race.mkdir(parents=True)
    (race / "laps.ff1pkl").write_bytes(b"x" * schedule.MIN_CACHED_BYTES)
    (tmp_path / "2026" / "2026-10-11_Singapore_Grand_Prix" / "2026-10-10_Qualifying").mkdir()  # carga fallida: vacía
    monkeypatch.setattr(schedule, "DEFAULT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(schedule, "_held", lambda y, e: ["Q", "R"])
    monkeypatch.setenv("F1_DASH_CACHED_ONLY", "1")
    assert schedule.seasons() == [2026]
    assert schedule.sessions_held(2026, "Singapore Grand Prix") == ["R"]
    monkeypatch.delenv("F1_DASH_CACHED_ONLY")
    assert schedule.sessions_held(2026, "Singapore Grand Prix") == ["Q", "R"]


def test_mirror_only_limita_las_temporadas(monkeypatch):
    from f1_dash.data import schedule
    monkeypatch.setenv("F1_DASH_SOURCE", "mirror")
    assert schedule.seasons() == [2022, 2021]
    monkeypatch.delenv("F1_DASH_SOURCE")
    assert schedule.seasons()[-1] == schedule.FIRST_SEASON


def test_available_events_filtra_por_cache(tmp_path, monkeypatch):
    import pandas as pd

    from f1_dash.data import schedule
    race = tmp_path / "2026" / "2026-10-11_Singapore_Grand_Prix" / "2026-10-11_Race"
    race.mkdir(parents=True)
    (race / "laps.ff1pkl").write_bytes(b"x" * schedule.MIN_CACHED_BYTES)
    df = pd.DataFrame({"EventName": ["Singapore Grand Prix", "Italian Grand Prix"]})
    monkeypatch.setattr(schedule, "DEFAULT_CACHE_DIR", tmp_path)
    monkeypatch.setattr(schedule, "events", lambda y: df)
    assert len(schedule.available_events(2026)) == 2
    monkeypatch.setenv("F1_DASH_CACHED_ONLY", "1")
    assert schedule.available_events(2026)["EventName"].tolist() == ["Singapore Grand Prix"]


def test_mirror_y_cached_only_juntos_es_error(monkeypatch):
    from f1_dash.data import schedule
    monkeypatch.setenv("F1_DASH_SOURCE", "mirror")
    monkeypatch.setenv("F1_DASH_CACHED_ONLY", "1")
    with pytest.raises(ValueError, match="F1_DASH_SOURCE"):
        schedule.seasons()
