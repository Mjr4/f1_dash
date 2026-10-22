import pytest
from fastapi.testclient import TestClient

import f1_dash.panels as panels
from f1_dash.api.app import app
from f1_dash.data.sessions import SessionNotAvailable, TransientError
from f1_dash.layout import GridLayout, Layout

client = TestClient(app, raise_server_exceptions=False)
SESION = {"year": 2021, "event": "French Grand Prix", "session_type": "R"}


def test_catalogo_por_sesion():
    r = client.get("/api/panels", params={"session_type": "Q"}).json()
    ids = [p["id"] for p in r]
    assert "lap_times" in ids and "positions" not in ids
    assert "only_valid" in next(p for p in r if p["id"] == "lap_times")["schema"]["properties"]


def test_navegacion():
    assert 2021 in client.get("/api/seasons").json()["seasons"]
    assert "French Grand Prix" in client.get("/api/events", params={"year": 2021}).json()


def test_render_devuelve_figura():
    r = client.post("/api/render", json={"panel_id": "lap_times", "params": {}, **SESION})
    assert r.status_code == 200 and r.json()["figure"]["data"]


def test_render_errores(monkeypatch):
    real = panels.render
    fallos = {"results": SessionNotAvailable("sin datos"), "lap_times": TransientError("red"), "tyre_strategy": RuntimeError("boom")}

    def render(panel, *a):
        if panel.id in fallos:
            raise fallos[panel.id]
        return real(panel, *a)

    monkeypatch.setattr(panels, "render", render)
    post = lambda pid, **kw: client.post("/api/render", json={"panel_id": pid, **SESION, **kw})
    assert post("results").json() == {"warning": "sin datos"}
    r = post("lap_times")
    assert (r.status_code, r.json()) == (503, {"error": "red"})
    r = post("tyre_strategy")
    assert (r.status_code, r.json()) == (500, {"error": "RuntimeError: boom"})
    assert post("nope").status_code == 404
    assert post("lap_times", params={"only_valid": "quizás"}).status_code == 422


def test_layout_v1_se_migra_a_v2():
    v1 = Layout()
    v1.add("results")
    v1.add("lap_times")
    v1.set_span(0, 1)
    v1.add("telemetry")
    v1.set_span(1, 2)
    r = client.post("/api/layout/validate", json=v1.model_dump())
    assert r.status_code == 200
    cells = [(c["panel_id"], c["x"], c["y"], c["w"]) for c in r.json()["panels"]]
    assert cells == [("results", 0, 0, 4), ("lap_times", 4, 0, 8), ("telemetry", 0, 8, 12)]
    assert GridLayout.loads(GridLayout(**r.json()).model_dump_json()) == GridLayout(**r.json())


@pytest.mark.parametrize("cell", [{"x": 10, "y": 0, "w": 4}, {"x": -1, "y": 0, "w": 4}, {"x": 0, "y": 0, "w": 0}])
def test_layout_celda_fuera_de_grilla(cell):
    r = client.post("/api/layout/validate", json={"version": 2, "panels": [{"panel_id": "results", **cell}]})
    assert r.status_code == 422


def test_layout_version_y_panel_invalidos():
    assert client.post("/api/layout/validate", json={"version": 3, "panels": []}).status_code == 422
    assert client.post("/api/layout/validate", json={"version": 2, "panels": [{"panel_id": "nope", "x": 0, "y": 0, "w": 4}]}).status_code == 422
