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
