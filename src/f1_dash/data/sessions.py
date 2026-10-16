"""Carga de sesiones: devuelve DataFrames/dataclasses, no objetos de FastF1."""
from dataclasses import dataclass, field

import fastf1
import fastf1.plotting
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


_CACHE: dict[tuple, tuple[tuple[bool, ...], SessionData]] = {}  # (año, evento, sesión) -> (flags, datos)


def load_session(
    year: int,
    event: str | int,
    session_type: str,
    telemetry: bool = False,
    weather: bool = False,
    messages: bool = False,
) -> SessionData:
    """`event` es el nombre exacto del calendario o el número de ronda.

    Cacheada en memoria por (año, evento, sesión): `session.load()` es lento incluso con
    caché de disco. Si lo cacheado no cubre los flags pedidos, recarga una vez con la unión.
    """
    key = (year, event, session_type)
    want = (telemetry, weather, messages)
    if key in _CACHE:
        have, data = _CACHE[key]
        if all(h or not w for h, w in zip(have, want)):
            return data
        want = tuple(h or w for h, w in zip(have, want))
        telemetry, weather, messages = want
    data = _load(year, event, session_type, telemetry, weather, messages)
    if len(_CACHE) >= 8 and key not in _CACHE:
        _CACHE.pop(next(iter(_CACHE)))  # descarta la más antigua
    _CACHE[key] = (want, data)
    return data


def _load(year, event, session_type, telemetry, weather, messages) -> SessionData:
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
    if lap is None:
        l = laps.pick_fastest()
    else:
        sel = laps[laps["LapNumber"] == lap]
        l = sel.iloc[0] if len(sel) else None
    if l is None:
        raise SessionNotAvailable(f"{driver}: sin vuelta {'válida' if lap is None else lap}")
    return pd.DataFrame(l.get_telemetry().add_distance())


def driver_style(data: SessionData, driver: str) -> dict:
    """Estilo Plotly de un piloto: color de equipo y trazo (discontinuo para el 2º del equipo).

    Vacío si FastF1 no lo conoce (Plotly usa entonces su paleta por defecto).
    """
    try:
        st = fastf1.plotting.get_driver_style(driver, ["color", "linestyle"], data._raw)
    except Exception:
        return {}
    return {"color": st["color"], "dash": "dash" if st["linestyle"] == "dashed" else "solid"}
