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
                         "PitInTime": [pd.NaT] * 4, "PitOutTime": [pd.NaT] * 4})
    return SessionData(2021, "X GP", session_type, results, laps, None, None, None)


def test_registry_and_schema():
    assert set(REGISTRY) == {"results", "lap_times", "telemetry", "tyre_strategy", "best_laps"}
    assert "drivers" in create("lap_times").model_json_schema()["properties"]


def test_panels_render(monkeypatch):
    tel = pd.DataFrame({"Distance": [0.0, 50, 100], "Speed": [100.0, 200, 300], "Throttle": [0.0, 50, 100], "Brake": [False, True, False]})
    monkeypatch.setattr(builtin, "telemetry", lambda *a: tel)
    for sess in ("R", "Q"):
        for pid in REGISTRY:
            assert create(pid).figure(_data(sess)).data
