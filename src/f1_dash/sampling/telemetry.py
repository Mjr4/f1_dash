"""Remuestreo y reducción de telemetría."""
import numpy as np
import pandas as pd


def distance_grid(tels: list[pd.DataFrame], points: int = 500) -> np.ndarray:
    """Grilla común: de 0 a la menor distancia máxima entre las vueltas."""
    return np.linspace(0, min(t["Distance"].max() for t in tels), points)


def resample_distance(tel: pd.DataFrame, grid: np.ndarray) -> pd.DataFrame:
    """Interpola las columnas numéricas/booleanas sobre `grid` (Distance).
    Las columnas timedelta (Time, SessionTime) pasan a segundos."""
    cols = [c for c in tel.select_dtypes(include=["number", "bool"]).columns if c != "Distance"]
    out = {"Distance": grid}
    for c in cols:
        v = tel[c]
        v = v.dt.total_seconds() if pd.api.types.is_timedelta64_dtype(v) else v.astype(float)
        out[c] = np.interp(grid, tel["Distance"], v)
    if "nGear" in out:
        out["nGear"] = np.round(out["nGear"])
    return pd.DataFrame(out)


def downsample(df: pd.DataFrame, max_points: int = 1000) -> pd.DataFrame:
    """Toma 1 de cada n filas para no pasar de `max_points`."""
    step = -(-len(df) // max_points)  # ceil
    return df.iloc[::step] if step > 1 else df
