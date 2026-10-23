"""API HTTP (FastAPI): solo expone data/panels/layout/service. Sin estado: el layout vive en el cliente."""
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import plotly
from pydantic import BaseModel

from f1_dash.data.schedule import available_events, cached_only, seasons, session_is_recent, sessions_held
from f1_dash.data.sessions import DataError
from f1_dash.layout import GridLayout
from f1_dash.panels import REGISTRY, for_session
from f1_dash.service import alertar, render_cached

app = FastAPI(title="F1 Dash")


class RenderRequest(BaseModel):
    panel_id: str
    params: dict = {}
    year: int
    event: str
    session_type: str


@app.get("/api/seasons")
def get_seasons():
    return {"seasons": seasons(), "cached_only": cached_only()}


@app.get("/api/events")
def get_events(year: int):
    return available_events(year)["EventName"].tolist()


@app.get("/api/sessions")
def get_sessions(year: int, event: str):
    return sessions_held(year, event)


@app.get("/api/recent")
def get_recent(year: int, event: str, session_type: str):
    return {"recent": session_is_recent(year, event, session_type)}


@app.get("/api/panels")
def get_panels(session_type: str):
    """Catálogo para la sesión: id, título y JSON Schema de los parámetros (el cliente genera los controles)."""
    return [{"id": i, "title": REGISTRY[i].title, "schema": REGISTRY[i].model_json_schema()} for i in for_session(session_type)]


@app.post("/api/render")
def post_render(req: RenderRequest):
    """`{figure}` (JSON de Plotly) o `{warning}` (error determinista); 503 si es transitorio, 500 si es un bug."""
    if req.panel_id not in REGISTRY:
        raise HTTPException(404, f"panel desconocido: {req.panel_id}")
    try:
        REGISTRY[req.panel_id](**req.params)
    except ValueError as e:
        raise HTTPException(422, str(e))
    try:
        out = render_cached(req.panel_id, req.params, req.year, req.event, req.session_type)
    except DataError as e:  # solo llegan los transitorios
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:  # bug del panel o error raro de FastF1: que no tumbe al resto de paneles
        alertar(req.panel_id, req.year, req.event, req.session_type, e)
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)
    if isinstance(out, str):
        return {"warning": out}
    return {"figure": json.loads(out.to_json())}  # to_json maneja numpy/fechas, que jsonable_encoder no


@app.post("/api/layout/validate")
def validate_layout(raw: dict[str, Any]):
    """Valida un layout v1 o v2 y lo devuelve normalizado a v2 (así el cliente migra layouts viejos)."""
    try:
        return GridLayout.loads(json.dumps(raw)).model_dump()
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))


@app.get("/plotly.min.js")
def plotly_js():
    """Plotly.js del paquete Python: misma versión que genera las figuras y sin depender de un CDN."""
    return FileResponse(Path(plotly.__file__).parent / "package_data" / "plotly.min.js", media_type="text/javascript")


# Al final: las rutas /api tienen prioridad sobre el montaje en "/"
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web")
