import pytest

from f1_dash.layout import Layout


def test_ops_and_roundtrip(tmp_path):
    lay = Layout()
    lay.add("results")
    lay.add("lap_times", {"drivers": ["VER"]})
    lay.add("tyre_strategy")
    lay.move(2, 0)
    assert [i.panel_id for i in lay.panels] == ["tyre_strategy", "results", "lap_times"]
    lay.configure(2, {"only_valid": False})
    lay.remove(1)
    lay.save(tmp_path / "l.json")
    assert Layout.load(tmp_path / "l.json") == lay
    assert lay.panels[1].params == {"only_valid": False}


def test_invalid_rejected(tmp_path):
    lay = Layout()
    with pytest.raises(KeyError):
        lay.add("nope")
    with pytest.raises(ValueError):
        lay.add("lap_times", {"only_valid": "quizás"})
    assert lay.panels == []
    (tmp_path / "v.json").write_text('{"version": 2, "panels": []}')
    with pytest.raises(ValueError):
        Layout.load(tmp_path / "v.json")


def test_loads_roundtrip():
    lay = Layout()
    lay.add("results")
    assert Layout.loads(lay.model_dump_json().encode()) == lay
