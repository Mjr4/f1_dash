---
name: add-panel
description: Añade un panel nuevo al dashboard F1 (clase Panel + @register + test + README). Úsala cuando se pida un panel, gráfico o visualización nueva en f1_dash.
---

# Añadir un panel

Un panel = una clase pydantic en `src/f1_dash/panels/builtin.py` con `@register`. La UI (`ui/app.py`), el layout y el catálogo lo recogen solos desde `REGISTRY`: **no se toca nada más** salvo el test y el README.

Reglas del proyecto: `data/`, `sampling/`, `panels/` y `layout/` no importan Streamlit. Lo más pequeño que funcione.

## Pasos

1. **Reutiliza antes de escribir.** Mira lo que ya hay en `builtin.py` y úsalo:
   - `_fmt` (timedelta -> `m:ss.mmm`), `_top_drivers(data, n)`, `COMPOUND_COLORS`
   - `valid_laps`, `filter_laps` (`sampling/laps.py`); `distance_grid`, `downsample`, `resample_distance` (`sampling/telemetry.py`)
   - `driver_style(data, drv)` para el color de equipo en cada traza
   - `telemetry(data, drv, lap)` para telemetría de una vuelta
2. **Escribe la clase** siguiendo este patrón:
   ```python
   @register
   class MiPanel(Panel):
       id = "mi_panel"            # snake_case, único; es la clave del REGISTRY y del JSON del layout
       title = "Mi panel"         # texto del catálogo, en español
       needs_telemetry = True     # solo si usa telemetry(); needs_weather = True si usa data.weather
       drivers: list[str] = Field([], description='Códigos de piloto, ej. ["VER", "HAM"]. Vacío = todos.')

       def figure(self, data: SessionData) -> go.Figure:
           ...
   ```
   - **Todo campo lleva `Field(..., description=...)`**: un test lo exige y de ahí salen los controles de la UI.
   - Defaults que funcionen sin configurar nada.
   - Devuelve siempre `go.Figure`.
3. **Sesiones sin los datos.** Si la sesión no los trae (p. ej. `Position` es NaN en Q y prácticas, `weather` puede ser `None`), lanza `SessionNotAvailable("mensaje legible en español")` (de `f1_dash.data.sessions`). La UI lo muestra como aviso. No devuelvas una figura vacía ni dejes que salte un `KeyError`/`ValueError` crudo. Si el panel elige un piloto por defecto, no sustituyas en silencio uno que el usuario pidió explícitamente (ver `TrackMap`).
4. **Test** en `tests/test_panels.py`:
   - Añade el `id` al set de `test_registry_and_schema`.
   - `test_panels_render` ya recorre todo el `REGISTRY` con `_data("R")` y `_data("Q")`. Si el panel necesita columnas nuevas en el DataFrame de prueba (`_data`), añádelas ahí. Si falla en Q por diseño, cambia ese test para esperar `SessionNotAvailable` en vez de saltártelo.
   - Si lanza `SessionNotAvailable`, añade el caso en `test_sin_datos_error_legible`.
   - Si usa `telemetry()`, el test ya lo parchea con `monkeypatch.setattr(builtin, "telemetry", ...)`.
5. **README**: añade el panel a la línea "Paneles adicionales" (Fase 3) y a "Estado".
6. **Verifica**: `.venv/bin/python -m pytest -q` en la raíz. Para verlo en la UI: `.venv/bin/streamlit run src/f1_dash/ui/app.py` con un evento pasado (si hay telemetría en caché, mejor).
7. **Comprobación de aislamiento**: `grep -r streamlit src/f1_dash/{data,sampling,panels,layout}` no debe devolver nada.

## Errores típicos
- Olvidar `description` en un campo -> falla `test_all_params_documented`.
- Pedir telemetría/clima sin declarar `needs_telemetry`/`needs_weather` -> `data.telemetry`/`data.weather` llega `None`.
- Asumir que una columna sin NaN en R también lo está en Q (p. ej. `Position` es 100 % NaN en Q; compruébalo con una sesión real).
- Ordenar pilotos por orden alfabético en vez de por `results.Position`.
