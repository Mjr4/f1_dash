# F1 Dash

Dashboard personalizable de Fórmula 1 sobre [FastF1](https://docs.fastf1.dev/). El usuario elige un evento (incluidas carreras pasadas), trae sus datos y arma su propio dash eligiendo y ordenando paneles.

**Requisito clave:** mantenibilidad y poder migrar el frontend más adelante. La lógica vive en un núcleo Python independiente de la UI; la UI es una capa delgada y reemplazable.

## Alcance inicial

Calendario, resultados, vueltas y telemetría (FastF1 cubre 2018 en adelante).

Fuera de alcance por ahora: drag & drop libre, datos pre-2018 (Ergast), datos en vivo, multiusuario. La cuenta F1 TV solo se usa como credencial del proceso (ver "Fuente de datos"), no hay login en la UI.

## Arquitectura

Cada capa solo depende de la anterior.

```
src/f1_dash/
  data/       Fase 1  Obtención: wrappers de FastF1 + caché
    cache.py      activa el caché de disco solo si se define F1_DASH_CACHE
    schedule.py   temporadas, eventos y sesiones disputadas; modos de fuente
    sessions.py   load_session, caché en memoria, errores de datos
  sampling/   Fase 2  Muestreo: reducir/normalizar datos para visualizar
    laps.py, telemetry.py
  panels/     Fase 3  Componentes: transforman datos -> figura Plotly
    registry.py   clase base Panel, @register y render()
    builtin.py    los paneles incluidos
  service.py          render con caché TTL+LRU y alertas por webhook (usado por la UI)
  layout/     Fase 4  Modelo de dashboard: paneles, orden y config (JSON)
    model.py      v1: lista ordenada con span (lo usa la UI Streamlit)
    grid.py       v2: grilla libre de 12 columnas (x, y, w, h); migra v1 al cargar
  api/        Fase 5b FastAPI: expone data/panels/layout/service por HTTP (app.py)
  ui/         Fase 5  Frontend (Streamlit): solo renderiza
    app.py
tests/        pytest por capa, sin red (conftest.py reemplaza FastF1 por una sesión falsa)
  test_sessions.py  data/ (sesiones, calendario, modos de fuente)
  test_sampling.py, test_panels.py, test_layout.py, test_service.py
  test_api.py       endpoints con TestClient (catálogo, render y sus errores, validación/migración de layout)
  test_ui.py        la UI de punta a punta con streamlit.testing (AppTest)
scripts/      phase1_check.py: verificación manual de la capa de datos contra la red
.github/workflows/ci.yml   pytest + comprobación de aislamiento de Streamlit
pyproject.toml            dependencias (fastf1 fijada a 3.9.0a0) y extra [dev]
```

**Regla de migración:** `data`, `sampling`, `panels`, `layout` y `service` no importan Streamlit ni ninguna librería de UI. Migrar a FastAPI + frontend JS implica agregar una capa `api/` que exponga esas mismas funciones, sin reescribir la lógica.

## Fases

### Fase 0 – Base del proyecto
- `pyproject.toml` (fastf1, pandas, plotly, streamlit, pytest), entorno virtual, `.gitignore` (incluye la carpeta de caché).
- Activar el caché de FastF1 en una sola función (`data/cache.py`), con ruta configurable.

### Fase 1 – Capa de datos (`data/`)
- `schedule.py`: temporadas y eventos disponibles (`fastf1.get_event_schedule`).
- `sessions.py`: `load_session(year, event, session_type)` con `session.load()` y carga parcial (telemetría, clima y mensajes opcionales).
- Devuelve DataFrames (vueltas, telemetría) y dataclasses (metadatos de evento/sesión) en vez de exponer objetos de FastF1 hacia arriba.
- `load_session` va con un caché en memoria TTL+LRU (stdlib, en `data/sessions.py`): la sesión se carga una sola vez y se reutiliza entre paneles e interacciones de la UI (el caché de disco de FastF1 no evita el costo de `session.load()`).
- Errores: sesión inexistente, datos no disponibles, coincidencia difusa de nombre (validar el evento devuelto).

### Fase 2 – Capa de muestreo (`sampling/`)
- Funciones puras DataFrame -> DataFrame: filtrar por pilotos/vueltas, vueltas válidas (`pick_quicklaps`, excluir in/out laps), remuestreo de telemetría a distancia común, downsampling para gráficos.

### Fase 3 – Paneles (`panels/`)
- Interfaz común: un panel es una clase pydantic cuyos campos son sus parámetros (su JSON Schema permite generar los controles en cualquier UI). Declara qué dataset necesita y devuelve una figura Plotly (serializable a JSON).
- Una única función `render(panel, year, event, session_type)` carga la sesión (con la telemetría solo si el panel la necesita) y dibuja; la UI solo la llama.
- Registro de paneles (`registry.py`) para agregar uno nuevo sin tocar el resto.
- Paneles iniciales: tabla de resultados, tiempos por vuelta, comparativa de telemetría (velocidad/acelerador/freno vs distancia), estrategia de neumáticos.
- Paneles adicionales: posiciones por vuelta (solo carreras/sprints), ritmo de carrera (boxplot), mapa del circuito coloreado por velocidad, clima, gap al líder (solo carreras/sprints), degradación de neumáticos (sin corregir por combustible) y mensajes de dirección de carrera. Un panel declara lo que necesita (`needs_telemetry`, `needs_weather`, `needs_messages`) y `render` se lo pide a `load_session`.

### Fase 4 – Layout personalizable (`layout/`)
- Modelo: `{"version": 1, "panels": [{panel_id, params}, ...]}` (lista ordenada, con `span` opcional de 1 a 3 tercios de fila, por defecto 3), serializable a JSON; guardar y cargar desde disco.
- Operaciones: agregar, quitar, reordenar y configurar paneles.

### Fase 5 – UI Streamlit (`ui/app.py`)
- Barra lateral: temporada -> evento -> sesión, y catálogo de paneles.
- Área principal: renderiza el layout; el usuario agrega, quita y ordena paneles.
- Descargar/subir el layout como JSON (sin estado en el servidor: el disco de Streamlit Community Cloud es efímero y compartido).
- Alertas: si `F1_DASH_ALERT_WEBHOOK` está definida (URL de webhook de Discord o Slack; en Streamlit Community Cloud, como secret), una excepción inesperada en un panel manda un aviso, una sola vez por panel, sesión y tipo de error. Los `SessionNotAvailable` no avisan.
- Aviso de sesión reciente: si la sesión empezó hace menos de 24 h (`RECENT_HOURS` en `data/schedule.py`) la UI avisa que sus datos pueden estar incompletos. FastF1 publica resultados y telemetría horas después de la sesión, y si se cargan antes puede guardar datos parciales en el caché de disco (`.fastf1_cache`); si pasa, borra la carpeta de esa sesión dentro de ese caché.

## Fuente de datos

Desde octubre de 2026 F1 exige una cuenta F1 TV (Access o superior) para el archivo de livetiming; el mirror de FastF1 solo conserva 2021 y 2022. Por eso hay tres caminos:

| Camino | Cómo se activa | Datos |
|---|---|---|
| **Mirror** (servidor público) | `F1_DASH_SOURCE=mirror` | 2021–2022, sin credenciales |
| **Cuenta F1 TV** (local) | `F1_USERNAME` y `F1_PASSWORD` en el entorno | Todas las temporadas; requiere `fastf1==3.9.0a0` (ya fijada en `pyproject.toml`) |
| **Caché propio** | `F1_DASH_CACHED_ONLY=1` y tu caché en la carpeta que indiques con `F1_DASH_CACHE` | Solo las sesiones que ya tengas en disco |

El caché de FastF1 no se versiona (`.fastf1_cache/` está en `.gitignore`) ni se sube al servidor: cada quien trae el suyo.

## Desarrollo

```
pip install -e .[dev]                     # dependencias + pytest
pytest -q                                 # tests, sin red
streamlit run src/f1_dash/ui/app.py       # la app
```

## Verificación

- Tests con pytest por capa, con fixtures pequeños de una sesión real para no depender de la red.
- Fase 1: script que carga una sesión (ej. 2021 French GP, `'Q'`), imprime resultados y vuelta más rápida; la segunda ejecución debe ser rápida (caché).
- Aislamiento: `grep -rE "streamlit|fastapi" src/f1_dash/{data,sampling,panels,layout,service.py}` no debe devolver nada.
- End-to-end: `streamlit run src/f1_dash/ui/app.py`, elegir un evento pasado, agregar 2-3 paneles, reordenarlos (↑ ↓) y ajustar su ancho (← →), descargar y volver a subir el layout.

## Estado

Fases 0 a 5 hechas (`data/`, `sampling/`, `panels/`, `layout/`, `ui/app.py`). Paneles: resultados, tiempos por vuelta, telemetría, estrategia de neumáticos, mejor vuelta, posiciones, ritmo de carrera, mapa del circuito, clima, gap al líder, degradación de neumáticos y mensajes de dirección de carrera. La UI solo ofrece las sesiones ya disputadas y los paneles que aplican a la sesión, genera un control por parámetro (con el JSON como modo avanzado), avisa de sesiones recientes y aísla los errores por panel. CI en GitHub Actions.

### Migración a FastAPI (en curso, rama `migracion-fastapi`)
`f1_dash.api.app` expone `/api/seasons|events|sessions|recent|panels`, `POST /api/render` (`{figure}`, `{warning}`, 503 transitorio, 500 bug con alerta) y `POST /api/layout/validate` (acepta layout v1 o v2 y devuelve v2). Prueba local: `uvicorn f1_dash.api.app:app`. Falta el frontend con drag & drop (GridStack) y retirar Streamlit.
