# plugins/review-crew/lib/tests/test_escalation_resolve.py
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ER = _load(os.path.join(_HERE, "..", "escalation_resolve.py"), "escalation_resolve")


def _run(capsys, *args):
    rc = ER.main(["escalation_resolve.py", *args])
    return rc, json.loads(capsys.readouterr().out)


def test_route_resolves_in_repo(capsys):
    rc, out = _run(capsys, "route", "--root", _REPO_ROOT,
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "notify" and out["degraded"] is False


def test_classify_resolves_in_repo(capsys):
    rc, out = _run(capsys, "classify", "--root", _REPO_ROOT, "--action", "git push origin main")
    assert rc == 0 and out["on_floor"] is True and out["degraded"] is False


def test_guard_refuses_band_safety_file_in_repo(capsys):
    # a real review-crew safety file, in-repo (dogfood) -> refused, not degraded
    rc, out = _run(capsys, "guard", "--root", _REPO_ROOT,
                   "--path", os.path.join(_REPO_ROOT, "plugins/review-crew/lib/loop_state.py"))
    assert rc == 0 and out["allow"] is False and out["degraded"] is False


def test_guard_allows_ordinary_file_in_repo(capsys):
    # decisions.py is NOT in the safety set -> allowed
    rc, out = _run(capsys, "guard", "--root", _REPO_ROOT,
                   "--path", os.path.join(_REPO_ROOT, "plugins/review-crew/lib/decisions.py"))
    assert rc == 0 and out["allow"] is True and out["degraded"] is False


def test_rubric_resolves_in_repo(capsys):
    rc, out = _run(capsys, "rubric", "--root", _REPO_ROOT)
    assert rc == 0 and out["degraded"] is False
    assert out["path"].endswith(os.path.join("the-architect", "rubric", "escalation-base.md"))


def test_lib_absent_fails_closed_to_gate(capsys, tmp_path):
    # the-architect not resolvable -> conservative embedded fallback: GATE
    rc, out = _run(capsys, "route", "--root", str(tmp_path),
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "gate" and out["degraded"] is True


def test_guard_lib_absent_fails_closed_to_refuse(capsys, tmp_path):
    rc, out = _run(capsys, "guard", "--root", str(tmp_path), "--path", "src/feature.py")
    assert rc == 0 and out["allow"] is False and out["degraded"] is True


def test_rubric_absent_fails_closed(capsys, tmp_path):
    rc, out = _run(capsys, "rubric", "--root", str(tmp_path))
    assert rc == 0 and out["path"] is None and out["degraded"] is True


def test_route_partial_resolution_fails_closed(capsys, tmp_path, monkeypatch):
    # lib resolves but the subprocess fails / returns garbage -> fail closed to gate.
    monkeypatch.setattr(ER, "_resolve", lambda root: "/some/escalation.py")
    monkeypatch.setattr(ER, "_subprocess_json", lambda lib, cli_args: None)
    rc, out = _run(capsys, "route", "--root", str(tmp_path),
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "gate" and out["degraded"] is True


def test_route_missing_key_reports_degraded(capsys, tmp_path, monkeypatch):
    # lib resolves and subprocess returns a well-formed dict but missing the "mode" key
    # -> fail closed to "gate" AND degraded must be True (not False).
    monkeypatch.setattr(ER, "_resolve", lambda root: "/some/escalation.py")
    monkeypatch.setattr(ER, "_subprocess_json", lambda lib, cli_args: {})
    rc, out = _run(capsys, "route", "--root", str(tmp_path),
                   "--on-floor", "false", "--ground-truth-locus", "owner",
                   "--owner-weighable", "true", "--reversible", "true", "--confidence", "high")
    assert rc == 0 and out["mode"] == "gate" and out["degraded"] is True
