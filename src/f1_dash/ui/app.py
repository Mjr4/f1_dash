"""UI Streamlit: solo renderiza. Toda la lógica vive en data/sampling/panels/layout."""
import json

import streamlit as st

from f1_dash.data.schedule import events, seasons
from f1_dash.data.sessions import DataError
from f1_dash.layout import Layout
from f1_dash.panels import REGISTRY, render

SESSION_TYPES = ["FP1", "FP2", "FP3", "SQ", "S", "Q", "R"]

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
    session_type = st.selectbox("Sesión", SESSION_TYPES, index=SESSION_TYPES.index("R"))

    st.divider()
    panel_id = st.selectbox("Panel", list(REGISTRY), format_func=lambda p: REGISTRY[p].title)
    st.button("Agregar panel", on_click=attempt, args=(layout.add, panel_id), width='stretch')

    st.divider()
    st.download_button("Descargar layout", layout.model_dump_json(indent=2), "layout.json", "application/json", width='stretch')
    upload = st.file_uploader("Cargar layout", type="json")

    def load():
        st.session_state.layout = Layout.loads(upload.getvalue())

    st.button("Cargar", on_click=attempt, args=(load,), disabled=upload is None, width='stretch')

if err := st.session_state.pop("error", None):
    st.error(err)

if not layout.panels:
    st.info("Agrega paneles desde la barra lateral.")

def draw(i: int, item):
    panel = item.panel()
    with st.container(border=True):
        head, nar, wid, up, down, rm = st.columns([5, 1, 1, 1, 1, 1])
        head.subheader(panel.title)
        nar.button("←", key=f"nr{i}", help="Estrechar", on_click=attempt, args=(layout.set_span, i, item.span - 1), disabled=item.span == 1)
        wid.button("→", key=f"wd{i}", help="Ensanchar", on_click=attempt, args=(layout.set_span, i, item.span + 1), disabled=item.span == 3)
        up.button("↑", key=f"up{i}", help="Mover atrás", on_click=attempt, args=(layout.move, i, max(i - 1, 0)), disabled=i == 0)
        down.button("↓", key=f"dn{i}", help="Mover adelante", on_click=attempt, args=(layout.move, i, i + 1), disabled=i == len(layout.panels) - 1)
        rm.button("✕", key=f"rm{i}", on_click=attempt, args=(layout.remove, i))
        if REGISTRY[item.panel_id].model_fields:
            with st.expander("Parámetros"):
                key = f"params{i}-{item.panel_id}-{json.dumps(panel.model_dump(), sort_keys=True)}"
                st.text_area("JSON", json.dumps(panel.model_dump(), indent=2), key=key, label_visibility="collapsed")
                st.button("Aplicar", key=f"ap{i}", on_click=apply_params, args=(i, key))
        try:
            with st.spinner("Cargando datos..."):
                st.plotly_chart(render(panel, year, event, session_type), key=f"fig{i}", width='stretch')
        except DataError as e:
            st.warning(str(e))


for row in layout.rows():
    spans = [layout.panels[i].span for i in row]
    cols = st.columns(spans + [3 - sum(spans)] if sum(spans) < 3 else spans)
    for col, i in zip(cols, row):
        with col:
            draw(i, layout.panels[i])
