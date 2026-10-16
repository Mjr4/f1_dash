"""Los tests no tocan la red: FastF1 se reemplaza por una sesión falsa y los sockets fallan."""
import socket
from types import SimpleNamespace

import pandas as pd
import pytest

from f1_dash.data import schedule, sessions

T = pd.Timedelta
EVENT = "French Grand Prix"


def fake_session():
    results = pd.DataFrame({"Position": [1.0, 2.0], "Abbreviation": ["AAA", "BBB"], "TeamName": ["X", "Y"],
                            "GridPosition": [2.0, 1.0], "Time": [T(seconds=5400), T(seconds=5410)],
                            "Status": ["Finished"] * 2, "Points": [25.0, 18.0],
                            "Q1": [T(seconds=90)] * 2, "Q2": [T(seconds=89)] * 2, "Q3": [pd.NaT, T(seconds=88)]})
    laps = pd.DataFrame({"Driver": ["AAA", "AAA", "BBB", "BBB"], "LapNumber": [1, 2, 1, 2],
                         "LapTime": [T(seconds=s) for s in (90, 91, 90.5, 92)], "Stint": [1, 2, 1, 1],
                         "Compound": ["SOFT", "HARD", "MEDIUM", "MEDIUM"],
                         "PitInTime": [pd.NaT] * 4, "PitOutTime": [pd.NaT] * 4})
    return SimpleNamespace(event={"EventName": EVENT}, load=lambda **kw: None, results=results, laps=laps,
                           weather_data=pd.DataFrame(), race_control_messages=pd.DataFrame())


def fake_get_session(year, event, session_type):
    if session_type not in {"FP1", "FP2", "FP3", "SQ", "S", "Q", "R"}:
        raise ValueError(f"Invalid session type: {session_type!r}")
    return fake_session()  # como FastF1: devuelve el evento más parecido, sea cual sea `event`


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def no_network(*a, **kw):
        raise RuntimeError("test sin red: no se permite abrir sockets")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(sessions.fastf1, "get_session", fake_get_session)
    monkeypatch.setattr(sessions, "enable_cache", lambda: None)
    monkeypatch.setattr(schedule.fastf1, "get_event_schedule", lambda year, include_testing=True: pd.DataFrame(
        {c: [EVENT] for c in schedule.COLUMNS}))
    schedule.events.cache_clear()
    sessions._CACHE.clear()
    import streamlit as st
    st.cache_data.clear()
