# plugins/superheroes/lib/tests/test_timeouts.py
import subprocess
import reset

# Equivalence note: test_classify_path_passes_timeout_and_denies and
# test_scrub_passes_timeout_and_drops are DELETED. They patched band_lib.resolve_target plus the
# subprocess.run seam on enforcer/readout; after the resolver collapse classify_path/scrub call
# the in-tree core DIRECTLY (no subprocess, no timeout=), so those branches no longer exist.
# Their fail-closed deny/drop posture is now covered by the re-expressed test_enforcer.py
# (test_path_fail_closed_on_guard_exception) and test_readout.py
# (test_scrub_fails_closed_when_scrubber_raises).
# The `enforcer`/`readout` imports are dropped — only `reset` is still exercised here.


def _raise_timeout(*a, **k):
    raise subprocess.TimeoutExpired(cmd="x", timeout=1)


def test_reset_engine_json_gates_on_timeout(monkeypatch):
    # PRESERVED: reset.engine_json drives the in-tree engine.py CLI via reset.subprocess.run —
    # a real in-tree subprocess that never went through band_lib and is unaffected by the
    # resolver collapse. On timeout it returns (124, None) and plan_reset gates.
    monkeypatch.setattr(reset.subprocess, "run", _raise_timeout)
    rc, parsed = reset.engine_json("engine.py", ["status"])
    assert rc == 124 and parsed is None
    assert reset.plan_reset(parsed)[0] == "gate"
