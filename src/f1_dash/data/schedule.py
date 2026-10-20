"""Temporadas y eventos disponibles."""
import os
from datetime import date
from functools import lru_cache

import fastf1
import pandas as pd

from .cache import CACHE_DIR

FIRST_SEASON = 2018  # límite de FastF1 (sin Ergast)
RECENT_HOURS = 24  # FastF1 publica resultados/telemetría horas después; antes de eso el caché de disco puede quedar con datos parciales
SESSION_TYPES = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"]
_CODES = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Qualifying": "Q", "Race": "R", "Sprint": "S",
          "Sprint Qualifying": "SQ", "Sprint Shootout": "SQ"}  # nombres del calendario de FastF1 -> código de sesión
COLUMNS = ["RoundNumber", "EventName", "Country", "Location", "EventDate"]
MIN_CACHED_BYTES = 100_000  # menos que esto = carga fallida (carpeta casi vacía), no datos reales


MIRROR_SEASONS = [2022, 2021]  # el mirror de FastF1 (livetiming-mirror.fastf1.dev) solo tiene esos años; desde oct-2026 el resto exige cuenta F1 TV


def mirror_only() -> bool:
    """F1_DASH_SOURCE=mirror: servidor público, sin credenciales; solo temporadas que sirve el mirror.

    Sin la variable se usa FastF1 con la cuenta de F1_USERNAME/F1_PASSWORD (fastf1>=3.9.0a0).
    """
    mirror = os.environ.get("F1_DASH_SOURCE") == "mirror"
    if mirror and cached_only():
        raise ValueError("F1_DASH_SOURCE=mirror y F1_DASH_CACHED_ONLY=1 son excluyentes: elige uno.")
    return mirror


def cached_only() -> bool:
    """F1_DASH_CACHED_ONLY=1: ofrecer solo lo que ya está en el caché de disco (la fuente de datos exige suscripción)."""
    return os.environ.get("F1_DASH_CACHED_ONLY") == "1"


def _cached() -> set[tuple[int, str, str]]:
    """(año, evento, código de sesión) con datos reales en el caché de disco.

    Deduce el nombre del evento y de la sesión de las carpetas de FastF1 (`2026-10-11_Singapore_Grand_Prix/2026-10-11_Race`).
    ponytail: nombres con caracteres que FastF1 transforma en la carpeta pueden no coincidir; revisar si falta algún evento.
    """
    out = set()
    for d in CACHE_DIR.glob("*/*/*") if CACHE_DIR else []:
        if d.is_dir() and sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) >= MIN_CACHED_BYTES:
            event = d.parent.name.split("_", 1)[1].replace("_", " ")
            session = d.name.split("_", 1)[1].replace("_", " ")
            if session in _CODES and d.parts[-3].isdigit():
                out.add((int(d.parts[-3]), event, _CODES[session]))
    return out


def seasons() -> list[int]:
    if mirror_only():
        return MIRROR_SEASONS
    if cached_only():
        return sorted({y for y, _, _ in _cached()}, reverse=True)
    return list(range(date.today().year, FIRST_SEASON - 1, -1))


@lru_cache(maxsize=None)
def events(year: int) -> pd.DataFrame:
    """Eventos de la temporada (sin testing)."""
    return fastf1.get_event_schedule(year, include_testing=False)[COLUMNS].reset_index(drop=True)


def available_events(year: int) -> pd.DataFrame:
    """`events`, y con F1_DASH_CACHED_ONLY solo los que tienen alguna sesión en el caché."""
    df = events(year)
    if not cached_only():
        return df
    names = {e for y, e, _ in _cached() if y == year}
    return df[df["EventName"].isin(names)].reset_index(drop=True)


def session_is_recent(year: int, event: str, session_type: str, hours: int = RECENT_HOURS) -> bool:
    """True si la sesión empezó hace menos de `hours` (o aún no empieza): sus datos pueden estar incompletos."""
    try:
        start = fastf1.get_event(year, event).get_session_date(session_type, utc=True)
    except Exception:  # sin red o sesión inexistente en el evento: no avisar, el aviso es opcional
        return False
    return pd.Timestamp.now("UTC").tz_localize(None) - start < pd.Timedelta(hours=hours)


def sessions_held(year: int, event: str) -> list[str]:
    held = _held(year, event)
    if not cached_only():
        return held
    cached = {c for y, e, c in _cached() if y == year and e == event}
    return [s for s in held if s in cached]


def _held(year: int, event: str) -> list[str]:
    """Tipos de sesión del evento que ya empezaron (UTC), en orden cronológico.

    Sin calendario disponible (sin red) devuelve todos los tipos: es un filtro, no debe bloquear la UI.
    """
    try:
        ev = fastf1.get_event(year, event)
        now = pd.Timestamp.now("UTC").tz_localize(None)
        return [_CODES[ev[f"Session{i}"]] for i in range(1, 6)
                if ev[f"Session{i}"] in _CODES and ev[f"Session{i}DateUtc"] <= now]
    except Exception:
        return SESSION_TYPES
