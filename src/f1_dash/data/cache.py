"""Activación del caché de FastF1 (único punto de configuración)."""
import os
from pathlib import Path

import fastf1

# Solo existe si se define F1_DASH_CACHE: sin la variable no se toca ningún caché de disco.
CACHE_DIR = Path(os.environ["F1_DASH_CACHE"]) if os.environ.get("F1_DASH_CACHE") else None


def enable_cache(path: Path | str | None = None) -> Path | None:
    cache_dir = Path(path) if path else CACHE_DIR
    if cache_dir is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    return cache_dir

