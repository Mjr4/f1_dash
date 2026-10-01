"""Activación del caché de FastF1 (único punto de configuración)."""
import os
from pathlib import Path

import fastf1

DEFAULT_CACHE_DIR = Path(os.environ.get("F1_DASH_CACHE", ".fastf1_cache"))


def enable_cache(path: Path | str | None = None) -> Path:
    cache_dir = Path(path) if path else DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    return cache_dir
