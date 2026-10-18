"""Carga de sesiones: devuelve DataFrames/dataclasses, no objetos de FastF1."""
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import fastf1
import fastf1.plotting
from fastf1.exceptions import DataNotLoadedError
import pandas as pd
import requests

from .cache import enable_cache


class DataError(Exception):
    """Base de los errores de la capa de datos.

    `transient` distingue un fallo transitorio (red, descarga: no debe cachearse)
    de un error determinista ("la fuente no tiene datos", cacheable).
    """

    transient: bool = False


class EventNotFound(DataError):
    pass


class SessionNotAvailable(DataError):
    """La fuente no tiene datos para esta sesión (determinista, cacheable)."""

    transient = False


class TransientError(DataError):
    """Fallo transitorio al descargar (red, sesión no publicada aún): no debe cachearse."""

    transient = True


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


_MAX = 3  # el costo real es `_raw` (fastf1.Session, con telemetría pesa mucho)
_TTL = 1800  # segundos; solo se evalúa al acceder
_CACHE: OrderedDict[tuple, tuple[tuple[bool, ...], SessionData, float]] = OrderedDict()  # (año, evento, sesión) -> (flags, datos, t)
_LOCK = threading.Lock()  # ponytail: lock global; se acepta carga duplicada ocasional, por clave si hay contención


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
    s = _resolve(year, event, session_type)
    key = (year, s.event["EventName"], session_type)  # "Monza" y 5 comparten entrada
    want = (telemetry, weather, messages)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[2] > _TTL:
            del _CACHE[key]
            hit = None
        if hit:
            have, data, _ = hit
            if all(h or not w for h, w in zip(have, want)):
                _CACHE.move_to_end(key)
                return data
            want = tuple(h or w for h, w in zip(have, want))
    data = _load(s, year, session_type, *want)  # fuera del lock: es lento
    with _LOCK:
        _CACHE[key] = (want, data, time.monotonic())
        _CACHE.move_to_end(key)
        while len(_CACHE) > _MAX:
            _CACHE.popitem(last=False)  # descarta la menos usada
    return data


def _resolve(year, event, session_type):
    enable_cache()
    try:
        s = fastf1.get_session(year, event, session_type)
    except ValueError as e:  # identificador de sesión inválido
        raise SessionNotAvailable(str(e)) from e
    if isinstance(event, str) and s.event["EventName"].lower() != event.lower():
        raise EventNotFound(f"{event!r} no coincide; ¿quisiste decir {s.event['EventName']!r}?")
    return s


def _load(s, year, session_type, telemetry, weather, messages) -> SessionData:
    try:
        s.load(laps=True, telemetry=telemetry, weather=weather, messages=messages)
    except (requests.RequestException, ConnectionError, TimeoutError) as e:  # red caída: transitorio, no debe cachearse
        raise TransientError(f"{year} {s.event['EventName']} {session_type}: {e}") from e
    except Exception as e:  # FastF1 lanza tipos variados si la sesión no tiene datos
        raise SessionNotAvailable(f"{year} {s.event['EventName']} {session_type}: {e}") from e
    try:
        results, laps = pd.DataFrame(s.results), pd.DataFrame(s.laps)
    except DataNotLoadedError as e:  # load() registra el fallo en el log y sigue; el acceso lo revela
        raise SessionNotAvailable(f"{year} {s.event['EventName']} {session_type}: {e}") from e
    return SessionData(
        year=year,
        event=s.event["EventName"],
        session_type=session_type,
        results=results,
        laps=laps,
        weather=_opt(lambda: s.weather_data) if weather else None,
        messages=_opt(lambda: s.race_control_messages) if messages else None,
        _raw=s,
    )


def _opt(get) -> pd.DataFrame | None:
    """Dato opcional: None si FastF1 no pudo cargarlo (el panel decide qué avisar)."""
    try:
        return pd.DataFrame(get())
    except DataNotLoadedError:
        return None


def telemetry(data: SessionData, driver: str, lap: int | None = None) -> pd.DataFrame:
    """Telemetría de una vuelta (por defecto la más rápida) con columna Distance.

    Requiere `load_session(..., telemetry=True)`.
    """
    try:
        sin_telemetria = not data._raw.car_data  # load() solo lo registra en el log: "Car telemetry data is unavailable!"
    except DataNotLoadedError:
        sin_telemetria = True
    if sin_telemetria:
        raise SessionNotAvailable(f"{data.year} {data.event} {data.session_type}: la fuente no tiene telemetría de esta sesión.")
    laps = data._raw.laps.pick_drivers(driver)
    if lap is None:
        l = laps.pick_fastest()
    else:
        sel = laps[laps["LapNumber"] == lap]
        l = sel.iloc[0] if len(sel) else None
    if l is None:
        raise SessionNotAvailable(f"{driver}: sin vuelta {'válida' if lap is None else lap}")
    try:
        return pd.DataFrame(l.get_telemetry().add_distance())
    except (DataNotLoadedError, KeyError) as e:  # KeyError: FastF1 no trae car/pos data de ese piloto
        raise SessionNotAvailable(f"{driver}: sin telemetría en esta sesión") from e


def driver_style(data: SessionData, driver: str) -> dict:
    """Estilo Plotly de un piloto: color de equipo y trazo (discontinuo para el 2º del equipo).

    Vacío si FastF1 no lo conoce (Plotly usa entonces su paleta por defecto).
    """
    try:
        st = fastf1.plotting.get_driver_style(driver, ["color", "linestyle"], data._raw)
    except Exception:
        return {}
    return {"color": st["color"], "dash": "dash" if st["linestyle"] == "dashed" else "solid"}
