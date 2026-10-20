"""Activación del caché de FastF1 (único punto de configuración)."""
import os
from pathlib import Path

import fastf1
from fastf1.exceptions import F1AuthError
from fastf1.internals.f1account import token_manager

# Solo existe si se define F1_DASH_CACHE: sin la variable no se toca ningún caché de disco.
CACHE_DIR = Path(os.environ["F1_DASH_CACHE"]) if os.environ.get("F1_DASH_CACHE") else None


def enable_cache(path: Path | str | None = None) -> Path | None:
    cache_dir = Path(path) if path else CACHE_DIR
    if cache_dir is None:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))
    return cache_dir


def disable_login():
    """Modo mirror: FastF1 no intenta iniciar sesión (ni pregunta usuario y contraseña por terminal)."""
    def no_login():
        raise F1AuthError("modo mirror: sin cuenta F1")  # el adaptador de FastF1 lo captura y sigue sin autenticar

    token_manager._authenticate = no_login  # ponytail: atributo privado de fastf1==3.9.0a0; revisar al actualizar la versión
