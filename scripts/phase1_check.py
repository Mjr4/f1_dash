"""Verificación Fase 1: carga 2021 French GP 'Q' e imprime resultados y vuelta más rápida.

Ejecutar dos veces: la segunda debe ser notablemente más rápida (caché de disco).
"""
import time

from f1_dash.data.schedule import events
from f1_dash.data.sessions import load_session, telemetry

t = time.perf_counter()
print(events(2021)[["RoundNumber", "EventName"]].head(3))
d = load_session(2021, "French Grand Prix", "Q", telemetry=True)
print(d.results[["Position", "Abbreviation", "Q3"]].head(5))
best = d.laps.loc[d.laps["LapTime"].idxmin()]
print("Más rápida:", best["Driver"], best["LapTime"])
print(telemetry(d, best["Driver"]).shape)
print(f"{time.perf_counter() - t:.1f}s")
