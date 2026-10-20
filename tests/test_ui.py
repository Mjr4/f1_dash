from streamlit.testing.v1 import AppTest


def test_app_add_and_move():
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    assert not at.exception
    at.selectbox[0].select(2021)
    at.run()
    at.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("tyre_strategy").run()
    at.sidebar.button[0].click().run()  # Agregar panel
    at.sidebar.selectbox[3].select("lap_times").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    ids = lambda: [i.panel_id for i in at.session_state.layout.panels]
    assert ids() == ["tyre_strategy", "lap_times"]
    at.button(key="dn0").click().run()
    assert not at.exception
    assert ids() == ["lap_times", "tyre_strategy"]


def test_app_span():
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("tyre_strategy").run()
    at.sidebar.button[0].click().run()
    at.button(key="nr0").click().run()
    assert not at.exception
    assert at.session_state.layout.panels[0].span == 2


def test_panel_fallido_no_se_reejecuta(monkeypatch):
    import f1_dash.panels as panels
    from f1_dash.data.sessions import SessionNotAvailable

    calls = []
    real = panels.render

    def render(panel, *a):
        calls.append(panel.id)
        if panel.id == "positions":
            raise SessionNotAvailable("sin posiciones")
        return real(panel, *a)

    monkeypatch.setattr(panels, "render", render)
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("positions").run()
    at.sidebar.button[0].click().run()
    at.sidebar.selectbox[3].select("lap_times").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert [w.value for w in at.warning] == ["sin posiciones"]
    assert calls.count("positions") == 1  # reruns posteriores usan el aviso cacheado


def test_error_transitorio_no_se_cachea(monkeypatch):
    """Un fallo de red (TransientError) no se cachea: el segundo render reintenta y muestra la figura."""
    import f1_dash.panels as panels
    from f1_dash.data.sessions import TransientError

    calls = []
    real = panels.render

    def render(panel, *a):
        n = calls.count(panel.id)
        calls.append(panel.id)
        if panel.id == "results" and n == 0:  # primer render: fallo de red
            raise TransientError("fallo de red al descargar")
        return real(panel, *a)

    monkeypatch.setattr(panels, "render", render)
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("results").run()
    at.sidebar.button[0].click().run()  # 1er render: TransientError -> st.error, no cacheado
    assert not at.exception
    assert calls.count("results") == 1
    assert [e.value for e in at.error] == ["fallo de red al descargar"]
    assert not at.get("plotly_chart")
    # 2do render (rerun): se reintenta y ahora tiene éxito
    at.run()
    assert calls.count("results") == 2
    assert not at.exception
    assert not at.error
    assert len(at.get("plotly_chart")) == 1


def test_excepcion_inesperada_no_rompe_la_pagina(monkeypatch):
    """Un panel que lanza RuntimeError muestra un error y los demás se dibujan."""
    import f1_dash.panels as panels

    real = panels.render

    def render(panel, *a):
        if panel.id == "results":
            raise RuntimeError("boom")
        return real(panel, *a)

    monkeypatch.setattr(panels, "render", render)
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("results").run()
    at.sidebar.button[0].click().run()
    at.sidebar.selectbox[3].select("lap_times").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert [e.value for e in at.error] == ["RuntimeError: boom"]
    assert len(at.get("plotly_chart")) == 1


def test_aviso_sesion_reciente(monkeypatch):
    import f1_dash.data.schedule as schedule

    monkeypatch.setattr(schedule, "session_is_recent", lambda *a: True)
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    assert not at.exception
    assert any("muy reciente" in i.value for i in at.info)


def test_catalogo_filtra_por_sesion():
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    assert "Posiciones por vuelta" in at.sidebar.selectbox[3].options
    at.sidebar.selectbox[2].select("Q").run()
    assert not at.exception
    assert "Posiciones por vuelta" not in at.sidebar.selectbox[3].options
    assert "Tiempos por vuelta" in at.sidebar.selectbox[3].options


def test_evento_sin_sesiones_disputadas(monkeypatch):
    import f1_dash.data.schedule as schedule

    monkeypatch.setattr(schedule, "sessions_held", lambda *a: [])
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    assert not at.exception
    assert any("aún no tiene sesiones" in i.value for i in at.info)
    assert not at.get("plotly_chart")


def test_controles_equivalen_al_json():
    """Cambiar un parámetro con su control da el mismo panel que aplicar el JSON equivalente."""
    from f1_dash.panels import create

    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("race_pace").run()
    at.sidebar.button[0].click().run()
    [c for c in at.checkbox if c.label == "by_compound"][0].uncheck().run()
    assert not at.exception
    assert at.session_state.layout.panels[0].panel() == create("race_pace", {"by_compound": False})
    [w for w in at.multiselect if w.label == "drivers"][0].set_value(["AAA"]).run()
    assert not at.exception
    assert at.session_state.layout.panels[0].panel() == create("race_pace", {"by_compound": False, "drivers": ["AAA"]})


def test_controles_numerico_y_opcional():
    from f1_dash.panels import create

    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    for pid in ("best_laps", "telemetry"):
        at.sidebar.selectbox[3].select(pid).run()
        at.sidebar.button[0].click().run()
    [n for n in at.number_input if n.label == "top"][0].set_value(5).run()
    [c for c in at.checkbox if c.label == "lap: automático"][0].uncheck().run()  # None -> 1
    [n for n in at.number_input if n.label == "lap"][0].set_value(3).run()
    assert not at.exception
    panels = [p.panel() for p in at.session_state.layout.panels]
    assert panels == [create("best_laps", {"top": 5}), create("telemetry", {"lap": 3})]


def test_alerta_una_vez_por_error(monkeypatch):
    """Una excepción inesperada avisa por webhook; los reruns del mismo fallo no repiten el aviso."""
    import requests

    import f1_dash.panels as panels

    posts = []
    monkeypatch.setenv("F1_DASH_ALERT_WEBHOOK", "http://alertas.test")
    monkeypatch.setattr(requests, "post", lambda url, **kw: posts.append((url, kw["json"]["content"])))
    monkeypatch.setattr(panels, "render", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    at.sidebar.selectbox[0].select(2021)
    at.run()
    at.sidebar.selectbox[1].select("French Grand Prix")
    at.sidebar.selectbox[3].select("results").run()
    at.sidebar.button[0].click().run()
    at.run()
    at.run()
    import time
    time.sleep(0.2)  # el aviso va en un hilo
    assert len(posts) == 1
    assert posts[0][0] == "http://alertas.test" and "results" in posts[0][1] and "RuntimeError: boom" in posts[0][1]


def test_app_cached_only_sin_cache_no_falla(tmp_path, monkeypatch):
    from f1_dash.data import schedule
    monkeypatch.setattr(schedule, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("F1_DASH_CACHED_ONLY", "1")
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    assert not at.exception
    assert "sesiones" in at.info[0].value
