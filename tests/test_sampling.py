import numpy as np
import pandas as pd

from f1_dash.sampling.laps import filter_laps, valid_laps
from f1_dash.sampling.telemetry import distance_grid, downsample, resample_distance

T = pd.Timedelta


def _laps():
    return pd.DataFrame({
        "Driver": ["A", "A", "A", "B", "B"],
        "LapNumber": [1, 2, 3, 1, 2],
        "LapTime": [T(seconds=s) for s in (100, 90, 130, 91)] + [pd.NaT],
        "PitInTime": [pd.NaT, pd.NaT, pd.NaT, pd.NaT, pd.NaT],
        "PitOutTime": [pd.NaT, pd.NaT, T(seconds=1), pd.NaT, pd.NaT],
    })


def test_filter_laps():
    out = filter_laps(_laps(), drivers=["A"], lap_range=(2, 3))
    assert out["LapNumber"].tolist() == [2, 3]


def test_valid_laps_drops_slow_outlap_nat():
    # 100 > 90*1.07 (lenta), 130 es out lap, NaT sin tiempo
    assert valid_laps(_laps()).index.tolist() == [1, 3]


def test_resample_and_downsample():
    a = pd.DataFrame({"Distance": [0, 10, 20], "Speed": [0, 100, 200], "nGear": [1, 2, 3], "Brake": [False, True, False]})
    b = pd.DataFrame({"Distance": [0, 15], "Speed": [0, 150]})
    grid = distance_grid([a, b], points=4)
    assert grid[-1] == 15
    r = resample_distance(a, grid)
    assert r["Speed"].tolist() == [0, 50, 100, 150]
    assert len(downsample(r, 2)) == 2
