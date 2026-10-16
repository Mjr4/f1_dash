"""Paneles iniciales."""
from typing import Literal

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pydantic import Field

from f1_dash.data.sessions import SessionData, SessionNotAvailable, driver_style, telemetry
from f1_dash.sampling.laps import filter_laps, valid_laps
from f1_dash.sampling.telemetry import distance_grid, downsample, resample_distance

from .registry import Panel, register

COMPOUND_COLORS = {"SOFT": "#e8002d", "MEDIUM": "#ffd12e", "HARD": "#f0f0f0",
                   "INTERMEDIATE": "#39b54a", "WET": "#0067ff"}


def _fmt(s):
    """Timedelta -> m:ss.mmm; NaN/NaT -> ""; el resto tal cual."""
    if pd.isna(s):
        return ""
    if hasattr(s, "total_seconds"):
        t = s.total_seconds()
        return f"{int(t // 60)}:{t % 60:06.3f}"
    return s


def _top_drivers(data: SessionData, n: int = 2) -> list[str]:
    return data.results.sort_values("Position")["Abbreviation"].head(n).tolist()


@register
class ResultsTable(Panel):
    id = "results"
    title = "Resultados"

    def figure(self, data: SessionData) -> go.Figure:
        cols = ["Position", "Abbreviation", "TeamName"]
        cols += ["Q1", "Q2", "Q3"] if data.session_type.startswith("Q") else ["GridPosition", "Time", "Status", "Points"]
        df = data.results.sort_values("Position")[cols]
        cells = [[_fmt(v) for v in df[c]] for c in cols]
        return go.Figure(go.Table(header={"values": cols}, cells={"values": cells}))


@register
class LapTimes(Panel):
    id = "lap_times"
    title = "Tiempos por vuelta"
    drivers: list[str] = Field([], description='Códigos de piloto, ej. ["VER", "HAM"]. Vacío = todos.')
    only_valid: bool = Field(True, description="true = solo vueltas rápidas válidas (sin in/out laps ni lentas); false = todas.")

    def figure(self, data: SessionData) -> go.Figure:
        laps = valid_laps(data.laps) if self.only_valid else data.laps
        laps = filter_laps(laps, self.drivers or None)
        fig = go.Figure()
        for drv, g in laps.groupby("Driver"):
            fig.add_scatter(x=g["LapNumber"], y=g["LapTime"].dt.total_seconds(), name=drv, mode="lines+markers", line=driver_style(data, drv))
        return fig.update_layout(xaxis_title="Vuelta", yaxis_title="Tiempo (s)")


@register
class TelemetryCompare(Panel):
    id = "telemetry"
    title = "Telemetría"
    needs_telemetry = True
    drivers: list[str] = Field([], description='Códigos de piloto, ej. ["VER", "HAM"]. Vacío = los 2 primeros del resultado.')
    lap: int | None = Field(None, description="Número de vuelta. null = la más rápida de cada piloto.")
    channels: list[Literal["Speed", "Throttle", "Brake"]] = Field(
        ["Speed", "Throttle", "Brake"], description='Canales a mostrar: "Speed", "Throttle", "Brake".')

    def figure(self, data: SessionData) -> go.Figure:
        drivers = self.drivers or _top_drivers(data)
        tels = [telemetry(data, d, self.lap) for d in drivers]
        grid = distance_grid(tels)
        fig = make_subplots(rows=len(self.channels), cols=1, shared_xaxes=True,
                            subplot_titles=self.channels, vertical_spacing=0.06)
        for drv, t in zip(drivers, tels):
            r = downsample(resample_distance(t, grid))
            for i, ch in enumerate(self.channels, 1):
                fig.add_scatter(x=r["Distance"], y=r[ch], name=drv, legendgroup=drv,
                                showlegend=i == 1, row=i, col=1, line=driver_style(data, drv))
        return fig.update_xaxes(title_text="Distancia (m)", row=len(self.channels), col=1)


@register
class TyreStrategy(Panel):
    id = "tyre_strategy"
    title = "Estrategia de neumáticos"

    def figure(self, data: SessionData) -> go.Figure:
        order = data.results.sort_values("Position")["Abbreviation"].tolist()
        stints = (data.laps.groupby(["Driver", "Stint", "Compound"])["LapNumber"]
                  .agg(["min", "max"]).reset_index())
        fig = go.Figure()
        for comp, g in stints.groupby("Compound"):
            fig.add_bar(y=g["Driver"], x=g["max"] - g["min"] + 1, base=g["min"] - 1, orientation="h",
                        name=comp, marker={"color": COMPOUND_COLORS.get(comp, "#888"), "line": {"color": "black", "width": 1}})
        return fig.update_layout(barmode="overlay", xaxis_title="Vuelta",
                                 yaxis={"categoryorder": "array", "categoryarray": order[::-1]})


@register
class BestLaps(Panel):
    id = "best_laps"
    title = "Mejor vuelta por piloto"
    top: int = Field(10, description="Cuántos pilotos mostrar (los más rápidos).")

    def figure(self, data: SessionData) -> go.Figure:
        best = data.laps.dropna(subset=["LapTime"]).groupby("Driver")["LapTime"].min().nsmallest(self.top)
        secs = best.dt.total_seconds()
        fig = go.Figure(go.Bar(y=best.index, x=secs - secs.min(), orientation="h",
                               text=[_fmt(t) for t in best]))
        return fig.update_layout(xaxis_title="Diferencia vs. la mejor (s)",
                                 yaxis={"categoryorder": "array", "categoryarray": best.index[::-1]})


@register
class Positions(Panel):
    id = "positions"
    title = "Posiciones por vuelta"
    drivers: list[str] = Field([], description='Códigos de piloto, ej. ["VER", "HAM"]. Vacío = todos.')

    def figure(self, data: SessionData) -> go.Figure:
        laps = filter_laps(data.laps, self.drivers or None).dropna(subset=["Position"])
        if laps.empty:  # Q y prácticas no traen Position
            raise SessionNotAvailable("Esta sesión no tiene posiciones por vuelta (solo carreras y sprints).")
        fig = go.Figure()
        for drv, g in laps.groupby("Driver"):
            fig.add_scatter(x=g["LapNumber"], y=g["Position"], name=drv, mode="lines", line=driver_style(data, drv))
        return fig.update_layout(xaxis_title="Vuelta", yaxis={"title": "Posición", "autorange": "reversed"})


@register
class RacePace(Panel):
    id = "race_pace"
    title = "Ritmo de carrera"
    drivers: list[str] = Field([], description='Códigos de piloto, ej. ["VER", "HAM"]. Vacío = todos.')
    by_compound: bool = Field(True, description="true = una caja por compuesto; false = una por piloto.")

    def figure(self, data: SessionData) -> go.Figure:
        laps = filter_laps(valid_laps(data.laps), self.drivers or None)
        present = set(laps["Driver"])
        order = [d for d in data.results.sort_values("Position")["Abbreviation"] if d in present]
        fig = go.Figure()
        for comp, g in (laps.groupby("Compound") if self.by_compound else [(None, laps)]):
            fig.add_box(x=g["Driver"], y=g["LapTime"].dt.total_seconds(), name=comp or "Todas",
                        marker_color=COMPOUND_COLORS.get(comp))
        return fig.update_layout(boxmode="group", yaxis_title="Tiempo (s)",
                                 xaxis={"categoryorder": "array", "categoryarray": order})


@register
class TrackMap(Panel):
    id = "track_map"
    title = "Mapa del circuito (velocidad)"
    needs_telemetry = True
    driver: str | None = Field(None, description="Código de piloto. null = el primero del resultado.")
    lap: int | None = Field(None, description="Número de vuelta. null = la más rápida del piloto.")

    def figure(self, data: SessionData) -> go.Figure:
        for drv in [self.driver] if self.driver else _top_drivers(data, 3):  # el 1º puede no tener posición
            try:
                t = telemetry(data, drv, self.lap).dropna(subset=["X", "Y"])
                break
            except SessionNotAvailable as e:
                if self.driver:
                    raise
                err = e
        else:
            raise err  # sin telemetría en toda la sesión, o ninguno de los 3 primeros tiene datos
        fig = go.Figure(go.Scatter(x=t["X"], y=t["Y"], mode="markers", marker={
            "color": t["Speed"], "colorscale": "Turbo", "colorbar": {"title": "km/h"}, "size": 4}))
        return fig.update_layout(title=drv, yaxis={"scaleanchor": "x", "visible": False}, xaxis={"visible": False})


@register
class Weather(Panel):
    id = "weather"
    title = "Clima"
    needs_weather = True
    channels: list[Literal["AirTemp", "TrackTemp", "Humidity", "WindSpeed"]] = Field(
        ["AirTemp", "TrackTemp"], description='Canales a mostrar: "AirTemp", "TrackTemp", "Humidity", "WindSpeed".')

    def figure(self, data: SessionData) -> go.Figure:
        w = data.weather
        if w is None or w.empty:
            raise SessionNotAvailable("Esta sesión no tiene datos de clima.")
        x = w["Time"].dt.total_seconds() / 60
        fig = go.Figure()
        for ch in self.channels:  # humedad y viento van en el eje derecho: otra escala
            fig.add_scatter(x=x, y=w[ch], name=ch, mode="lines", yaxis="y2" if ch in ("Humidity", "WindSpeed") else "y")
        return fig.update_layout(xaxis_title="Minutos de sesión", yaxis2={"overlaying": "y", "side": "right"})
