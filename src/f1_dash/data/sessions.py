"""Carga de sesiones: devuelve DataFrames/dataclasses, no objetos de FastF1."""
from dataclasses import dataclass, field
from functools import lru_cache

import fastf1
import pandas as pd

from .cache import enable_cache


class DataError(Exception):
    """Base de los errores de la capa de datos."""


class EventNotFound(DataError):
    pass


class SessionNotAvailable(DataError):
    pass


@dataclass(frozen=True)
class SessionData:
    year: int
    event: str
    session_type: str
    results: pd.DataFrame
    laps: pd.DataFrame
    weather: pd.DataFrame | None
    messages: pd.DataFrame | None
    _raw: object = field(repr=False, compare=False)  # fastf1.Session, solo para telemetry()


@lru_cache(maxsize=8)
def load_session(
    year: int,
    event: str | int,
    session_type: str,
    telemetry: bool = False,
    weather: bool = False,
    messages: bool = False,
) -> SessionData:
    """`event` es el nombre exacto del calendario o el número de ronda.

    Cacheada en memoria: `session.load()` es lento incluso con caché de disco.
    """
    enable_cache()
    try:
        s = fastf1.get_session(year, event, session_type)
    except ValueError as e:  # identificador de sesión inválido
        raise SessionNotAvailable(str(e)) from e
    if isinstance(event, str) and s.event["EventName"].lower() != event.lower():
        raise EventNotFound(f"{event!r} no coincide; ¿quisiste decir {s.event['EventName']!r}?")
    try:
        s.load(laps=True, telemetry=telemetry, weather=weather, messages=messages)
    except Exception as e:  # FastF1 lanza tipos variados si la sesión no tiene datos
        raise SessionNotAvailable(f"{year} {s.event['EventName']} {session_type}: {e}") from e
    return SessionData(
        year=year,
        event=s.event["EventName"],
        session_type=session_type,
        results=pd.DataFrame(s.results),
        laps=pd.DataFrame(s.laps),
        weather=pd.DataFrame(s.weather_data) if weather else None,
        messages=pd.DataFrame(s.race_control_messages) if messages else None,
        _raw=s,
    )


def telemetry(data: SessionData, driver: str, lap: int | None = None) -> pd.DataFrame:
    """Telemetría de una vuelta (por defecto la más rápida) con columna Distance.

    Requiere `load_session(..., telemetry=True)`.
    """
    laps = data._raw.laps.pick_drivers(driver)
    l = laps.pick_fastest() if lap is None else laps[laps["LapNumber"] == lap].iloc[0]
    if l is None:
        raise SessionNotAvailable(f"{driver}: sin vuelta válida")
    return pd.DataFrame(l.get_telemetry().add_distance())
