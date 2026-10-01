"""Temporadas y eventos disponibles."""
from datetime import date
from functools import lru_cache

import fastf1
import pandas as pd

FIRST_SEASON = 2018  # límite de FastF1 (sin Ergast)
COLUMNS = ["RoundNumber", "EventName", "Country", "Location", "EventDate"]


def seasons() -> list[int]:
    return list(range(date.today().year, FIRST_SEASON - 1, -1))


@lru_cache(maxsize=None)
def events(year: int) -> pd.DataFrame:
    """Eventos de la temporada (sin testing)."""
    return fastf1.get_event_schedule(year, include_testing=False)[COLUMNS].reset_index(drop=True)
