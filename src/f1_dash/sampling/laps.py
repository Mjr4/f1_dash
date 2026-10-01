"""Filtros de vueltas: DataFrame -> DataFrame, sin dependencias de FastF1."""
import pandas as pd


def filter_laps(
    laps: pd.DataFrame,
    drivers: list[str] | None = None,
    lap_range: tuple[int, int] | None = None,
) -> pd.DataFrame:
    """Filtra por pilotos (abreviatura) y rango inclusivo de LapNumber."""
    if drivers is not None:
        laps = laps[laps["Driver"].isin(drivers)]
    if lap_range is not None:
        laps = laps[laps["LapNumber"].between(*lap_range)]
    return laps


def valid_laps(laps: pd.DataFrame, threshold: float = 1.07) -> pd.DataFrame:
    """Vueltas con tiempo, sin in/out laps y dentro de `threshold` x la más rápida
    (mismo criterio que `pick_quicklaps` de FastF1)."""
    laps = laps[laps["LapTime"].notna() & laps["PitInTime"].isna() & laps["PitOutTime"].isna()]
    return laps[laps["LapTime"] <= laps["LapTime"].min() * threshold]
