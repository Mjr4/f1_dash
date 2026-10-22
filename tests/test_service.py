import pytest

import f1_dash.panels as panels
import f1_dash.service as service
from f1_dash.data.sessions import SessionNotAvailable, TransientError


def test_error_determinista_se_cachea(monkeypatch):
    calls = []

    def render(*a):
        calls.append(1)
        raise SessionNotAvailable("sin datos")

    monkeypatch.setattr(panels, "render", render)
    assert service.render_cached("results", {}, 2021, "French Grand Prix", "R") == "sin datos"
    assert service.render_cached("results", {}, 2021, "French Grand Prix", "R") == "sin datos"
    assert len(calls) == 1


def test_error_transitorio_no_se_cachea(monkeypatch):
    calls = []

    def render(*a):
        calls.append(1)
        raise TransientError("red")

    monkeypatch.setattr(panels, "render", render)
    for _ in range(2):
        with pytest.raises(TransientError):
            service.render_cached("results", {}, 2021, "French Grand Prix", "R")
    assert len(calls) == 2


def test_alerta_una_vez(monkeypatch):
    import requests

    posts = []
    monkeypatch.setenv("F1_DASH_ALERT_WEBHOOK", "http://alertas.test")
    monkeypatch.setattr(requests, "post", lambda url, **kw: posts.append(url))
    for _ in range(3):
        service.alertar("results", 2021, "X", "R", RuntimeError("boom"))
    import time
    time.sleep(0.2)
    assert posts == ["http://alertas.test"]
