"""Unit tests for dispatch_selftest.py (issue #636 WO-D)."""
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "dispatch_selftest.py")


def _load():
    spec = importlib.util.spec_from_file_location("dispatch_selftest", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DST = _load()


def test_run_ok_with_nonzero_checked():
    result = DST.run()
    assert result["ok"] is True
    assert result["checked"] > 0
    assert result["failures"] == []


def test_probe_result_shape_when_ok():
    run_out = DST.run()
    pr = DST.probe_result()
    assert pr["tool"] == "dispatch-vocab"
    assert pr["ok"] is True
    assert pr["detail"] == "ok (%d checks)" % run_out["checked"]


def test_probe_result_not_ok_when_checked_zero(monkeypatch):
    monkeypatch.setattr(DST, "run", lambda config=None: {"ok": True, "checked": 0, "failures": []})
    pr = DST.probe_result()
    assert pr["ok"] is False
    assert "zero checks" in pr["detail"]


def test_main_run_prints_json_and_exits_zero():
    from io import StringIO
    from contextlib import redirect_stdout

    buf = StringIO()
    with redirect_stdout(buf):
        rc = DST.main(["dispatch_selftest.py", "run"])
    assert rc == 0
    payload = json.loads(buf.getvalue())
    assert payload["ok"] is True
    assert payload["checked"] > 0


def test_main_run_exits_one_on_failure(monkeypatch):
    monkeypatch.setattr(
        DST,
        "run",
        lambda config=None: {"ok": False, "checked": 1, "failures": [{"where": "t", "detail": "d"}]},
    )
    rc = DST.main(["run"])
    assert rc == 1


def test_run_never_raises():
    DST.run()


def test_run_with_config_violations_fails_leg_five():
    config = {
        "prefs": {"implementation": "codex"},
        "tiers": {"implementer": "fable"},
    }
    result = DST.run(config)
    assert result["ok"] is False
    assert any("configured implementer/codex" in f["where"] for f in result["failures"])
    assert any(
        f["detail"] == "fable-on-external-engine"
        for f in result["failures"]
    )


def test_run_with_clean_config_still_ok():
    config = {
        "prefs": {"implementation": "claude"},
        "tiers": {"implementer": "sonnet"},
    }
    result = DST.run(config)
    assert result["ok"] is True


def test_format_probe_detail_caps_failures(monkeypatch):
    monkeypatch.setattr(
        DST,
        "run",
        lambda config=None: {
            "ok": False,
            "checked": 1,
            "failures": [{"where": "w%d" % i, "detail": "d"} for i in range(10)],
        },
    )
    pr = DST.probe_result()
    assert pr["ok"] is False
    assert "w0" in pr["detail"]
    assert "more failure" in pr["detail"]
