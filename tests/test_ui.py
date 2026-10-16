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
