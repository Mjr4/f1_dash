"""UI Streamlit: solo renderiza. Toda la lógica vive en data/sampling/panels/layout."""
import json
import logging
import os
import threading

import requests
import streamlit as st

from f1_dash.data.schedule import events, seasons, session_is_recent, sessions_held
from f1_dash.data.sessions import DataError, TransientError
from f1_dash.layout import Layout
from f1_dash.panels import REGISTRY, create, for_session, render

st.set_page_config(page_title="F1 Dash", layout="wide")
if "layout" not in st.session_state:
    st.session_state.layout = Layout()
layout: Layout = st.session_state.layout


def attempt(fn, *args):
    """Callback que muestra el error de validación en vez de romper la app."""
    try:
        fn(*args)
    except Exception as e:
        st.session_state.error = str(e)


def apply_params(i: int, key: str):
    attempt(lambda: layout.configure(i, json.loads(st.session_state[key])))


with st.sidebar:
    st.title("F1 Dash")
    year = st.selectbox("Temporada", seasons())
    event = st.selectbox("Evento", events(year)["EventName"])
    held = sessions_held(year, event)
    session_type = st.selectbox("Sesión", held, index=held.index("R") if "R" in held else 0)

    st.divider()
    panel_id = st.selectbox("Panel", for_session(session_type), format_func=lambda p: REGISTRY[p].title)
    st.button("Agregar panel", on_click=attempt, args=(layout.add, panel_id), width='stretch')

    st.divider()
    st.download_button("Descargar layout", layout.model_dump_json(indent=2), "layout.json", "application/json", width='stretch')
    upload = st.file_uploader("Cargar layout", type="json")

    def load():
        st.session_state.layout = Layout.loads(upload.getvalue())

    st.button("Cargar", on_click=attempt, args=(load,), disabled=upload is None, width='stretch')

if session_type is None:
    st.info("Este evento aún no tiene sesiones disputadas.")
    st.stop()

if err := st.session_state.pop("error", None):
    st.error(err)

if session_is_recent(year, event, session_type):
    st.info("Esta sesión es muy reciente: sus datos pueden estar incompletos y FastF1 podría guardarlos así en el caché de disco.")

if not layout.panels:
    st.info("Agrega paneles desde la barra lateral.")

@st.cache_data(max_entries=64, ttl=3600, show_spinner="Cargando datos...")
def cached_figure(panel_id: str, params_json: str, year: int, event: str, session_type: str):
    """Figura (o texto del DataError) cacheada por panel+params+sesión; así un panel fallido no se re-ejecuta en cada rerun.

    Los errores deterministas (`transient=False`) se devuelven como texto y se cachean.
    Los transitorios (`transient=True`, ej. fallo de red) se relanzan: `st.cache_data`
    no cachea excepciones, así que el siguiente rerun vuelve a intentar la descarga.
    """
    try:
        fig = render(create(panel_id, json.loads(params_json)), year, event, session_type)
    except DataError as e:
        if getattr(e, "transient", False):
            raise
        return str(e)
    return fig.update_layout(height=300 + 80 * len(list(fig.select_yaxes())), margin=dict(l=10, r=10, t=30, b=10))


@st.cache_resource
def _alertados() -> set:
    return set()  # compartido por todas las sesiones del servidor; sobrevive a los reruns del script


def alertar(panel_id: str, year: int, event: str, session_type: str, e: Exception):
    """Avisa por webhook (F1_DASH_ALERT_WEBHOOK: Discord o Slack) una vez por panel+sesión+tipo de error."""
    url = os.environ.get("F1_DASH_ALERT_WEBHOOK")
    clave = (panel_id, year, event, session_type, type(e).__name__)
    if not url or clave in _alertados():
        return
    _alertados().add(clave)
    msg = f"F1 Dash: el panel {panel_id} falló en {year} {event} {session_type}: {type(e).__name__}: {e}"
    threading.Thread(target=lambda: requests.post(url, json={"content": msg, "text": msg}, timeout=5), daemon=True).start()


def control(label: str, prop: dict, value, key: str):
    """Un widget por campo del JSON Schema del panel; devuelve el valor elegido.

    `X | None` = widget de X + casilla "automático" (None). Tipos no previstos caen al JSON avanzado.
    """
    help = prop.get("description")
    if "anyOf" in prop:  # opcional: [X, null]
        if st.checkbox(f"{label}: automático", value is None, key=f"{key}-auto", help=help):
            return None
        prop = next(p for p in prop["anyOf"] if p["type"] != "null")
        value = {"integer": 1, "string": ""}[prop["type"]] if value is None else value
    match prop["type"]:
        case "boolean":
            return st.checkbox(label, value, key=key, help=help)
        case "integer":
            return int(st.number_input(label, value=value, step=1, key=key, help=help))
        case "number":
            return st.number_input(label, value=float(value), key=key, help=help)
        case "string":
            return st.text_input(label, value, key=key, help=help)
        case "array":
            enum = prop["items"].get("enum")  # sin enum (pilotos): se escriben y se confirman con Enter
            return st.multiselect(label, enum or value, value, accept_new_options=not enum, key=key, help=help)


def draw(i: int, item):
    panel = item.panel()
    with st.container(border=True):
        compact = item.span == 1  # a 1/3 no caben los botones: van en un popover
        head, *menu = st.columns([6, 2] if compact else [5, 1, 1, 1, 1, 1])
        head.markdown(f"**{panel.title}**")
        nar, wid, up, down, rm = menu[0].popover("⚙", width="stretch").columns(5) if compact else menu
        nar.button("←", key=f"nr{i}", help="Estrechar", on_click=attempt, args=(layout.set_span, i, item.span - 1), disabled=item.span == 1)
        wid.button("→", key=f"wd{i}", help="Ensanchar", on_click=attempt, args=(layout.set_span, i, item.span + 1), disabled=item.span == 3)
        up.button("↑", key=f"up{i}", help="Mover atrás", on_click=attempt, args=(layout.move, i, max(i - 1, 0)), disabled=i == 0)
        down.button("↓", key=f"dn{i}", help="Mover adelante", on_click=attempt, args=(layout.move, i, i + 1), disabled=i == len(layout.panels) - 1)
        rm.button("✕", key=f"rm{i}", on_click=attempt, args=(layout.remove, i))
        if schema := REGISTRY[item.panel_id].model_json_schema().get("properties"):
            with st.expander("Parámetros"):
                current = panel.model_dump()
                tag = f"{i}-{item.panel_id}-{json.dumps(current, sort_keys=True)}"  # al cambiar el valor, el widget se recrea con el nuevo
                values = {n: control(n, p, current[n], f"{n}-{tag}") for n, p in schema.items()}
                if values != current:
                    try:
                        layout.configure(i, values)
                    except Exception as e:
                        st.error(str(e))
                    else:
                        st.rerun()
                with st.expander("JSON (avanzado)"):
                    key = f"params{tag}"
                    st.text_area("JSON", json.dumps(current, indent=2), key=key, label_visibility="collapsed")
                    st.button("Aplicar", key=f"ap{i}", on_click=apply_params, args=(i, key))
        try:
            fig = cached_figure(item.panel_id, json.dumps(panel.model_dump(), sort_keys=True), year, event, session_type)
        except DataError as e:
            if getattr(e, "transient", False):
                st.error(str(e))
            else:
                st.warning(str(e))
            fig = None
        except Exception as e:  # bug del panel o error raro de FastF1: que no tumbe el resto de la página
            logging.getLogger(__name__).exception("panel %s falló", item.panel_id)
            alertar(item.panel_id, year, event, session_type, e)
            st.error(f"{type(e).__name__}: {e}")
            fig = None
        if isinstance(fig, str):
            st.warning(fig)
        elif fig is not None:
            st.plotly_chart(fig, key=f"fig{i}", width='stretch')


for row in layout.rows():
    spans = [layout.panels[i].span for i in row]
    cols = st.columns(spans + [3 - sum(spans)] if sum(spans) < 3 else spans)
    for col, i in zip(cols, row):
        with col:
            draw(i, layout.panels[i])
