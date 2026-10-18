"""Temporadas y eventos disponibles."""
from datetime import date
from functools import lru_cache

import fastf1
import pandas as pd

FIRST_SEASON = 2018  # límite de FastF1 (sin Ergast)
RECENT_HOURS = 24  # FastF1 publica resultados/telemetría horas después; antes de eso el caché de disco puede quedar con datos parciales
COLUMNS = ["RoundNumber", "EventName", "Country", "Location", "EventDate"]


def seasons() -> list[int]:
    return list(range(date.today().year, FIRST_SEASON - 1, -1))


@lru_cache(maxsize=None)
def events(year: int) -> pd.DataFrame:
    """Eventos de la temporada (sin testing)."""
    return fastf1.get_event_schedule(year, include_testing=False)[COLUMNS].reset_index(drop=True)


def session_is_recent(year: int, event: str, session_type: str, hours: int = RECENT_HOURS) -> bool:
    """True si la sesión empezó hace menos de `hours` (o aún no empieza): sus datos pueden estar incompletos."""
    try:
        start = fastf1.get_event(year, event).get_session_date(session_type, utc=True)
    except Exception:  # sin red o sesión inexistente en el evento: no avisar, el aviso es opcional
        return False
    return pd.Timestamp.now("UTC").tz_localize(None) - start < pd.Timedelta(hours=hours)
