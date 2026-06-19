# plugins/review-crew/lib/tests/test_model_tier_resolve_timeout.py
import subprocess
import model_tier_resolve as mtr


def test_subprocess_json_none_on_timeout(monkeypatch):
    monkeypatch.setattr(mtr.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(
                            subprocess.TimeoutExpired(cmd="x", timeout=1)))
    assert mtr._subprocess_json("lib.py", ["resolve"]) is None
