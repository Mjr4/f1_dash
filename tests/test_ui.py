from streamlit.testing.v1 import AppTest


def test_app_add_and_move():
    at = AppTest.from_file("../src/f1_dash/ui/app.py", default_timeout=120).run()
    assert not at.exception
    at.selectbox[0].select(2021)
    at.run()
    at.selectbox[1].select("French Grand Prix")
    at.selectbox[3].select("tyre_strategy").run()
    at.sidebar.button[0].click().run()  # Agregar panel
    at.selectbox[3].select("lap_times").run()
    at.sidebar.button[0].click().run()
    assert not at.exception
    ids = lambda: [i.panel_id for i in at.session_state.layout.panels]
    assert ids() == ["tyre_strategy", "lap_times"]
    at.button(key="dn0").click().run()
    assert not at.exception
    assert ids() == ["lap_times", "tyre_strategy"]
