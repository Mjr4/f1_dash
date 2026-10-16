import pandas as pd

from f1_dash.data.sessions import SessionData
from f1_dash.panels import REGISTRY, builtin, create

T = pd.Timedelta


def _data(session_type="R"):
    results = pd.DataFrame({"Position": [1.0, 2.0], "Abbreviation": ["AAA", "BBB"], "TeamName": ["X", "Y"],
                            "GridPosition": [2.0, 1.0], "Time": [T(seconds=5400), T(seconds=5410)],
                            "Status": ["Finished"] * 2, "Points": [25.0, 18.0], "Q1": [T(seconds=90)] * 2,
                            "Q2": [T(seconds=89)] * 2, "Q3": [pd.NaT, T(seconds=88)]})
    laps = pd.DataFrame({"Driver": ["AAA", "AAA", "BBB", "BBB"], "LapNumber": [1, 2, 1, 2],
                         "LapTime": [T(seconds=s) for s in (90, 91, 90.5, 92)], "Stint": [1, 2, 1, 1],
                         "Compound": ["SOFT", "HARD", "MEDIUM", "MEDIUM"],
                         "PitInTime": [pd.NaT] * 4, "PitOutTime": [pd.NaT] * 4,
                         "Position": [1.0, 1.0, 2.0, 2.0]})
    weather = pd.DataFrame({"Time": [T(minutes=m) for m in (0, 1, 2)], "AirTemp": [24.0, 24.1, 24.2],
                            "TrackTemp": [30.0, 31, 32], "Humidity": [50.0, 50, 51], "WindSpeed": [1.0, 1, 2]})
    return SessionData(2021, "X GP", session_type, results, laps, weather, None, None)


def test_registry_and_schema():
    assert set(REGISTRY) == {"results", "lap_times", "telemetry", "tyre_strategy", "best_laps",
                           "positions", "race_pace", "track_map", "weather"}
    assert "drivers" in create("lap_times").model_json_schema()["properties"]


def test_panels_render(monkeypatch):
    tel = pd.DataFrame({"Distance": [0.0, 50, 100], "Speed": [100.0, 200, 300], "Throttle": [0.0, 50, 100], "Brake": [False, True, False],
                        "X": [0.0, 50, 100], "Y": [0.0, 40, 0]})
    monkeypatch.setattr(builtin, "telemetry", lambda *a: tel)
    for sess in ("R", "Q"):
        for pid in REGISTRY:
            assert create(pid).figure(_data(sess)).data


def test_all_params_documented():
    from f1_dash.panels import REGISTRY
    for cls in REGISTRY.values():
        for name, f in cls.model_fields.items():
            assert f.description, f"{cls.id}.{name} sin description"


def test_driver_style_desconocido():
    from types import SimpleNamespace
    from f1_dash.data.sessions import driver_style
    assert driver_style(SimpleNamespace(_raw=None), "XXX") == {}


def test_sin_datos_error_legible():
    import dataclasses

    import pytest

    from f1_dash.data.sessions import SessionNotAvailable

    d = _data()
    sin_pos = dataclasses.replace(d, laps=d.laps.assign(Position=float("nan")))  # como en Q real
    with pytest.raises(SessionNotAvailable):
        create("positions").figure(sin_pos)
    with pytest.raises(SessionNotAvailable):
        create("weather").figure(dataclasses.replace(d, weather=None))


def test_render_pide_clima(monkeypatch):
    from f1_dash.panels import registry

    seen = {}
    monkeypatch.setattr(registry, "load_session", lambda *a, **kw: seen.update(kw) or _data())
    registry.render(create("weather"), 2021, "X GP", "R")
    assert seen == {"telemetry": False, "weather": True}
