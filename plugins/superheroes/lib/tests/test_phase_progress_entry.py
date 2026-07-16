import json
import os
import subprocess
import sys

LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, LIB)
import control_plane


def _run(tmp_path, payload, extra=None):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [
        sys.executable,
        os.path.join(LIB, "phase_progress_entry.py"),
        "save",
        "--work-item", "wi",
        "--step", "2",
        "--phase", "build",
        "--payload", json.dumps(payload),
    ] + list(extra or [])
    return subprocess.run(cmd, cwd=str(tmp_path), env=env, text=True, capture_output=True, timeout=30)


def test_phase_progress_idempotent_and_read_back_confirmed(tmp_path):
    first = _run(tmp_path, {"phase": "build", "confidence": "high"})
    assert first.returncode == 0, first.stderr
    out1 = json.loads(first.stdout)
    assert out1["ok"] is True
    assert out1["journal_confirmed"] is True
    assert out1["checkpoint_confirmed"] is True
    second = _run(tmp_path, {"phase": "build", "confidence": "high"})
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    lines = open(events, encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1


def test_phase_progress_journal_only_leaves_checkpoint_untouched(tmp_path):
    # #118 park tail: --journal-only appends the journal record durably but must NOT
    # write the checkpoint cursor (a parked phase did not complete; advancing lastGoodStep
    # would make a resume skip it).
    result = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["journal_confirmed"] is True
    assert "checkpoint_confirmed" not in out
    paths = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))
    lines = open(paths["events"], encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1
    assert not os.path.exists(paths["checkpoint"])


def test_phase_progress_journal_only_is_idempotent(tmp_path):
    first = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert json.loads(first.stdout)["ok"] is True
    second = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    out2 = json.loads(second.stdout)
    assert out2["ok"] is True
    assert out2["already"] is True
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    lines = open(events, encoding="utf-8").read().splitlines()
    assert len([line for line in lines if '"phase_record"' in line]) == 1


def test_phase_progress_journal_only_then_full_save_advances_cursor(tmp_path):
    # a park journaled with --journal-only followed by a later successful full save (the resume
    # re-ran the phase and proceeded) must land the cursor and keep the journal deduped per payload.
    park = _run(tmp_path, {"phase": "build", "gate": "changes-requested"}, ["--journal-only"])
    assert json.loads(park.stdout)["ok"] is True
    done = _run(tmp_path, {"phase": "build", "gate": "passed"})
    out = json.loads(done.stdout)
    assert out["ok"] is True
    assert out["checkpoint_confirmed"] is True
    assert out["step"] == 2


def _run_park(tmp_path, payload, leg_idem=None, cost=None, park="no net progress"):
    extra = ["--journal-only", "--terminal-park", park]
    if cost is not None:
        extra += ["--cost-payload", json.dumps(cost)]
    if leg_idem is not None:
        extra += ["--leg-idem", leg_idem]
    return _run(tmp_path, payload, extra)


def _count(tmp_path, needle):
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    lines = open(events, encoding="utf-8").read().splitlines()
    return len([line for line in lines if needle in line])


def test_phase_progress_relaunch_leg_records_second_park(tmp_path):
    # #434: a relaunched review leg re-enters a PARKED phase, runs it again, and parks again with a
    # byte-identical payload. Keying freshness on payload-equality alone dedupes the second leg's
    # phase_record/phase_cost/parked away (journal quieter than the allowance ledger). With a per-leg
    # idem nonce (minted resume-continuing by the spine) each genuine re-entry earns its own records.
    payload = {"phase": "review-plan", "gate": "changes-requested", "confidence": "high"}
    leg1 = _run_park(tmp_path, payload, leg_idem="pp:wi:s2:build:d1", cost={"dispatches": 38})
    assert json.loads(leg1.stdout)["ok"] is True
    assert json.loads(leg1.stdout)["already"] is False
    leg2 = _run_park(tmp_path, payload, leg_idem="pp:wi:s2:build:d2", cost={"dispatches": 41})
    out2 = json.loads(leg2.stdout)
    assert out2["ok"] is True
    assert out2["already"] is False   # the relaunch is NOT a no-op — it parked again
    assert _count(tmp_path, '"phase_record"') == 2
    assert _count(tmp_path, '"parked"') == 2
    assert _count(tmp_path, '"phase_cost"') == 2


def test_phase_progress_relaunch_leg_same_nonce_dedupes(tmp_path):
    # A courier retry of ONE park-save re-sends the SAME baked --leg-idem; that must dedupe to a single
    # phase_record/parked/cost (the retry landed the first append already).
    payload = {"phase": "review-plan", "gate": "changes-requested"}
    first = _run_park(tmp_path, payload, leg_idem="pp:wi:s2:build:d1", cost={"dispatches": 38})
    assert json.loads(first.stdout)["already"] is False
    retry = _run_park(tmp_path, payload, leg_idem="pp:wi:s2:build:d1", cost={"dispatches": 38})
    out = json.loads(retry.stdout)
    assert out["ok"] is True
    assert out["already"] is True
    assert _count(tmp_path, '"phase_record"') == 1
    assert _count(tmp_path, '"parked"') == 1
    assert _count(tmp_path, '"phase_cost"') == 1


def test_phase_progress_leg_idem_rides_top_level_payload_clean(tmp_path):
    # The per-leg nonce rides the top-level `idem` field (like #350's external_dispatch) so the
    # phase_record `payload` stays semantic + byte-unchanged for consumers.
    payload = {"phase": "review-plan", "gate": "changes-requested"}
    _run_park(tmp_path, payload, leg_idem="pp:wi:s2:build:d1")
    events = control_plane.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))["events"]
    rec = [json.loads(line) for line in open(events, encoding="utf-8").read().splitlines()
           if '"phase_record"' in line][0]
    assert rec["idem"] == "pp:wi:s2:build:d1"
    assert rec["payload"] == payload   # payload carries NO synthetic leg field


def test_phase_progress_no_leg_idem_is_legacy_payload_dedup(tmp_path):
    # Absent --leg-idem the behavior is byte-unchanged: a second identical-payload park is a no-op
    # (the unseedable-journal fail-safe path — never regress crash-resume dedup).
    payload = {"phase": "review-plan", "gate": "changes-requested"}
    _run_park(tmp_path, payload)
    second = _run_park(tmp_path, payload)
    assert json.loads(second.stdout)["already"] is True
    assert _count(tmp_path, '"phase_record"') == 1


def test_phase_progress_malformed_payload_fails_closed(tmp_path):
    env = {**os.environ, "SUPERHEROES_STORE_ROOT": str(tmp_path / "store")}
    cmd = [
        sys.executable,
        os.path.join(LIB, "phase_progress_entry.py"),
        "save",
        "--work-item", "wi",
        "--step", "2",
        "--phase", "build",
        "--payload", "{",
    ]
    result = subprocess.run(cmd, cwd=str(tmp_path), env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert "malformed" in out["error"]
