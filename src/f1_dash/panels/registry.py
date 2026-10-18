"""Contrato de paneles y registro. Un panel nuevo = subclase de Panel + @register."""
from typing import ClassVar

import plotly.graph_objects as go
from pydantic import BaseModel

from f1_dash.data.sessions import SessionData, SessionNotAvailable, load_session


class Panel(BaseModel):
    """Los campos son los parámetros del panel (`model_json_schema()` los describe a cualquier UI)."""

    id: ClassVar[str]
    title: ClassVar[str]
    needs_telemetry: ClassVar[bool] = False
    needs_weather: ClassVar[bool] = False
    sessions: ClassVar[frozenset[str] | None] = None  # tipos de sesión donde tiene sentido; None = todas

    def figure(self, data: SessionData) -> go.Figure:
        raise NotImplementedError


REGISTRY: dict[str, type[Panel]] = {}


def register(cls: type[Panel]) -> type[Panel]:
    REGISTRY[cls.id] = cls
    return cls


def for_session(session_type: str) -> list[str]:
    """Ids de los paneles que tienen sentido en este tipo de sesión (para el catálogo de la UI)."""
    return [i for i, c in REGISTRY.items() if c.sessions is None or session_type in c.sessions]


def create(panel_id: str, params: dict | None = None) -> Panel:
    return REGISTRY[panel_id](**(params or {}))


def render(panel: Panel, year: int, event: str | int, session_type: str) -> go.Figure:
    """Único punto de entrada para la UI: carga (con caché) lo que el panel necesita y dibuja."""
    data = load_session(year, event, session_type, telemetry=panel.needs_telemetry, weather=panel.needs_weather)
    fig = panel.figure(data)
    if not fig.data:  # filtros/nulos que dejan el gráfico en blanco: mejor un aviso
        raise SessionNotAvailable("Sin datos para mostrar en esta sesión.")
    return fig
