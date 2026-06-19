# plugins/workhorse/lib/tests/test_timeouts.py
import subprocess
import enforcer
import reset
import readout


def _raise_timeout(*a, **k):
    raise subprocess.TimeoutExpired(cmd="x", timeout=1)


def test_classify_path_passes_timeout_and_denies(monkeypatch, tmp_path):
    # Resolve the escalation lib so classify_path REACHES the subprocess (else it denies
    # early on the unresolvable-lib path, never exercising the timeout). Capture kwargs so
    # the test is RED until the production edit actually passes timeout=.
    calls = {}
    def fake_run(*a, **k):
        calls.update(k)
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(enforcer.band_lib, "resolve_target",
                        lambda *a, **k: str(tmp_path / "escalation.py"))
    monkeypatch.setattr(enforcer.subprocess, "run", fake_run)
    assert enforcer.classify_path(str(tmp_path / "x.py"))[0] == "deny"
    assert "timeout" in calls          # the edit must pass timeout= (fails before the edit)


def test_reset_engine_json_gates_on_timeout(monkeypatch):
    monkeypatch.setattr(reset.subprocess, "run", _raise_timeout)
    rc, parsed = reset.engine_json("engine.py", ["status"])
    assert rc == 124 and parsed is None
    assert reset.plan_reset(parsed)[0] == "gate"


def test_scrub_passes_timeout_and_drops(monkeypatch, tmp_path):
    # Resolve the scrubber lib so scrub REACHES the subprocess, then time it out + capture.
    calls = {}
    def fake_run(*a, **k):
        calls.update(k)
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)
    monkeypatch.setattr(readout.band_lib, "resolve_target",
                        lambda *a, **k: str(tmp_path / "pr_comment.py"))
    monkeypatch.setattr(readout.subprocess, "run", fake_run)
    out, ok = readout.scrub("SECRET=1", root=str(tmp_path))
    assert ok is False and "SECRET" not in out
    assert "timeout" in calls
