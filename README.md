# F1 Dash

Dashboard personalizable de Fórmula 1 sobre [FastF1](https://docs.fastf1.dev/). El usuario elige un evento (incluidas carreras pasadas), trae sus datos y arma su propio dash eligiendo y ordenando paneles.

**Requisito clave:** mantenibilidad y poder migrar el frontend más adelante. La lógica vive en un núcleo Python independiente de la UI; la UI es una capa delgada y reemplazable.

## Alcance inicial

Calendario, resultados, vueltas y telemetría (FastF1 cubre 2018 en adelante).

Fuera de alcance por ahora: drag & drop libre, datos pre-2018 (Ergast), datos en vivo, autenticación/multiusuario.

## Arquitectura

Cada capa solo depende de la anterior.

```
src/f1_dash/
  data/       Fase 1  Obtención: wrappers de FastF1 + caché
  sampling/   Fase 2  Muestreo: reducir/normalizar datos para visualizar
  panels/     Fase 3  Componentes: transforman datos -> figura Plotly
  layout/     Fase 4  Modelo de dashboard: paneles, orden y config (JSON)
  ui/         Fase 5  Frontend (Streamlit): solo renderiza
tests/
```

**Regla de migración:** `data`, `sampling`, `panels` y `layout` no importan Streamlit ni ninguna librería de UI. Migrar a FastAPI + frontend JS implica agregar una capa `api/` que exponga esas mismas funciones, sin reescribir la lógica.

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
- Paneles adicionales: posiciones por vuelta (solo carreras/sprints), ritmo de carrera (boxplot), mapa del circuito coloreado por velocidad y clima. Un panel declara lo que necesita (`needs_telemetry`, `needs_weather`) y `render` se lo pide a `load_session`.

### Fase 4 – Layout personalizable (`layout/`)
- Modelo: `{"version": 1, "panels": [{panel_id, params}, ...]}` (lista ordenada, con `span` opcional de 1 a 3 tercios de fila, por defecto 3), serializable a JSON; guardar y cargar desde disco.
- Operaciones: agregar, quitar, reordenar y configurar paneles.

### Fase 5 – UI Streamlit (`ui/app.py`)
- Barra lateral: temporada -> evento -> sesión, y catálogo de paneles.
- Área principal: renderiza el layout; el usuario agrega, quita y ordena paneles.
- Descargar/subir el layout como JSON (sin estado en el servidor: el disco de Streamlit Community Cloud es efímero y compartido).
- Aviso de sesión reciente: si la sesión empezó hace menos de 24 h (`RECENT_HOURS` en `data/schedule.py`) la UI avisa que sus datos pueden estar incompletos. FastF1 publica resultados y telemetría horas después de la sesión, y si se cargan antes puede guardar datos parciales en el caché de disco (`.fastf1_cache`); si pasa, borra la carpeta de esa sesión dentro de ese caché.

## Verificación

- Tests con pytest por capa, con fixtures pequeños de una sesión real para no depender de la red.
- Fase 1: script que carga una sesión (ej. 2021 French GP, `'Q'`), imprime resultados y vuelta más rápida; la segunda ejecución debe ser rápida (caché).
- Aislamiento: `grep -r streamlit src/f1_dash/{data,sampling,panels,layout}` no debe devolver nada.
- End-to-end: `streamlit run src/f1_dash/ui/app.py`, elegir un evento pasado, agregar 2-3 paneles, reordenarlos (↑ ↓) y ajustar su ancho (← →), descargar y volver a subir el layout.

## Estado

Fase 0 hecha (`pyproject.toml`, `.gitignore`, esqueleto de paquetes, `data/cache.py`). Fase 1 hecha (`data/schedule.py`, `data/sessions.py`, `scripts/phase1_check.py`). Fase 2 hecha (`sampling/laps.py`, `sampling/telemetry.py`). Fase 3 hecha (`panels/registry.py`, `panels/builtin.py`). Fase 4 hecha (`layout/model.py`). Fase 5 hecha (`ui/app.py`). Proyecto completo según el alcance inicial. Paneles adicionales hechos (posiciones, ritmo, mapa, clima).
