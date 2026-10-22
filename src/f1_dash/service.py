"""Render con caché y alertas: lo que la UI necesita además de `panels.render`, sin depender de ninguna UI."""
import json
import os
import threading
import time
from collections import OrderedDict

import plotly.graph_objects as go
import requests

import f1_dash.panels as panels
from f1_dash.data.sessions import DataError

_TTL = 3600  # segundos; solo se evalúa al acceder
_MAX = 64
_CACHE: OrderedDict[tuple, tuple[go.Figure | str, float]] = OrderedDict()
_LOCK = threading.Lock()  # ponytail: lock global; se acepta render duplicado ocasional
_ALERTED: set = set()


def render_cached(panel_id: str, params: dict, year: int, event: str, session_type: str) -> go.Figure | str:
    """Figura (o texto del DataError) cacheada por panel+params+sesión; así un panel fallido no se re-ejecuta en cada petición.

    Los errores deterministas (`transient=False`) se devuelven como texto y se cachean.
    Los transitorios (`transient=True`, ej. fallo de red) se relanzan sin cachear: la siguiente llamada reintenta.
    """
    key = (panel_id, json.dumps(params, sort_keys=True), year, event, session_type)
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and time.monotonic() - hit[1] <= _TTL:
            _CACHE.move_to_end(key)
            return hit[0]
    try:
        out = panels.render(panels.create(panel_id, params), year, event, session_type)
        out = out.update_layout(height=300 + 80 * len(list(out.select_yaxes())), margin=dict(l=10, r=10, t=30, b=10))
    except DataError as e:
        if getattr(e, "transient", False):
            raise
        out = str(e)
    with _LOCK:
        _CACHE[key] = (out, time.monotonic())
        while len(_CACHE) > _MAX:
            _CACHE.popitem(last=False)
    return out


def alertar(panel_id: str, year: int, event: str, session_type: str, e: Exception) -> None:
    """Avisa por webhook (F1_DASH_ALERT_WEBHOOK: Discord o Slack) una vez por panel+sesión+tipo de error."""
    url = os.environ.get("F1_DASH_ALERT_WEBHOOK")
    clave = (panel_id, year, event, session_type, type(e).__name__)
    with _LOCK:
        if not url or clave in _ALERTED:
            return
        _ALERTED.add(clave)
    msg = f"F1 Dash: el panel {panel_id} falló en {year} {event} {session_type}: {type(e).__name__}: {e}"
    threading.Thread(target=lambda: requests.post(url, json={"content": msg, "text": msg}, timeout=5), daemon=True).start()
