# plugins/superheroes/lib/tests/test_manual_completion_entry.py
"""#450 manual-completion receipt — IO leaf + record-reader integration. A real subprocess over
the conftest-isolated control-plane store (no monkeypatched journal/checkpoint seam): the CLI
must write a terminal `manual_completion` journal event AND advance the checkpoint to the terminal
phase, so that the run record — which today reads "parked, never resumed" — reads the truth:
"manually completed to PR #N". Exercises the exact dark-record shape from the issue (frozen
checkpoint at phase build/lastGoodPhase workhorse, pr:null, last journal event a park)."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
CLI = str(HERE.parent / "manual_completion_entry.py")
LIB = str(HERE.parent)
sys.path.insert(0, LIB)
import checkpoint as ckpt_lib  # noqa: E402
import control_plane  # noqa: E402
import journal  # noqa: E402
import manual_completion_entry as entry  # noqa: E402
import run_watch  # noqa: E402
import token_trend  # noqa: E402


def _run(repo, work_item, extra):
    env = os.environ.copy()
    env["PYTHONPATH"] = LIB
    return subprocess.run([sys.executable, CLI, "--work-item", work_item, *extra],
                          cwd=str(repo), env=env, capture_output=True, text=True)


def _events(repo, work_item):
    return journal.read_events(control_plane.paths(str(repo), work_item)["events"])


def _seed_dark_parked_run(repo, work_item):
    """Reproduce the #397 / weekly-eats dark record: a checkpoint frozen mid-build with pr:null,
    whose last journal event is a park — the exact "parked, never resumed" lie."""
    paths = control_plane.paths(str(repo), work_item)
    cp = ckpt_lib.new(work_item, "feat/dark", phase="build",
                      last_good_step=4, last_good_phase="workhorse", pr=None)
    ckpt_lib.write(paths["checkpoint"], cp)
    journal.append(paths["events"], "run_started", root=str(repo))
    journal.append(paths["events"], "parked", detail="assumption gate — owner away", root=str(repo))


def test_receipt_flips_a_dark_parked_record_to_completed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-397"
    _seed_dark_parked_run(repo, wi)

    # Before: the record lies — every reader reconstructs "parked, never resumed".
    assert run_watch._read_run(str(repo), wi, _events(repo, wi))["state"] == "parked"
    assert token_trend.classify(_events(repo, wi)) == "parked"
    assert run_watch._read_checkpoint(str(repo), wi)[0]["value"] != "shipped-manual"

    proc = _run(repo, wi, ["--pr", "431", "--head-sha", "deadbeef", "--note", "hand-finished to ready"])
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["ok"] is True and out.get("already") is not True

    events = _events(repo, wi)
    receipts = [e for e in events if e.get("type") == "manual_completion"]
    assert len(receipts) == 1, "exactly one manual_completion receipt must be journaled"
    payload = receipts[0].get("payload") or {}
    assert payload.get("pr") == 431 and payload.get("headSha") == "deadbeef"
    assert payload.get("note") == "hand-finished to ready"

    # After: every record reader now tells the truth.
    run = run_watch._read_run(str(repo), wi, events)
    assert run["state"] == "completed"
    assert run["detail"] == "manual"
    assert token_trend.classify(events) == "completed"


def test_receipt_advances_the_checkpoint_to_the_terminal_phase_with_the_pr(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-stg"
    _seed_dark_parked_run(repo, wi)

    proc = _run(repo, wi, ["--pr", "420", "--url", "https://x/pr/420"])
    assert proc.returncode == 0, proc.stderr

    paths = control_plane.paths(str(repo), wi)
    cp = ckpt_lib.read(paths["checkpoint"])
    assert not cp.get("_incompatible")
    assert cp["phase"] == "shipped-manual"
    assert cp["pr"]["isDraft"] is False and cp["pr"]["number"] == 420

    # The phase the watch DISPLAYS is now the terminal marker (it wins over the stale
    # lastGoodPhase resume cursor), not "workhorse".
    phase_info, _gates, _updated = run_watch._read_checkpoint(str(repo), wi)
    assert phase_info["value"] == "shipped-manual"


def test_receipt_is_idempotent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-idem"
    _seed_dark_parked_run(repo, wi)

    first = json.loads(_run(repo, wi, ["--pr", "7"]).stdout)
    assert first["ok"] is True and first.get("already") in (False, None)
    second = json.loads(_run(repo, wi, ["--pr", "7"]).stdout)
    assert second["ok"] is True and second["already"] is True

    receipts = [e for e in _events(repo, wi) if e.get("type") == "manual_completion"]
    assert len(receipts) == 1, "a second invocation must not append a duplicate receipt"


def test_note_is_scrubbed_before_it_lands_in_the_durable_payload(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-secret"
    _seed_dark_parked_run(repo, wi)
    # A note the finisher pasted that happens to embed a secret must never be written raw.
    secret = "ghp_" + "A" * 36
    proc = _run(repo, wi, ["--pr", "9", "--note", "token %s leaked" % secret])
    assert proc.returncode == 0, proc.stderr
    # The receipt landed AND the note was scrubbed — an absence-only check would also pass if the
    # note were silently dropped or the receipt never written, so assert both the presence and the
    # redaction (kills the 'note dropped' and 'scrub bypassed' mutants distinctly).
    receipts = [e for e in _events(repo, wi) if e.get("type") == "manual_completion"]
    assert len(receipts) == 1
    note = (receipts[0].get("payload") or {}).get("note")
    assert note and secret not in note and "[REDACTED]" in note
    raw = Path(control_plane.paths(str(repo), wi)["events"]).read_text()
    assert secret not in raw


def test_missing_checkpoint_still_records_a_truthful_terminal_record(tmp_path):
    # Fail-soft (#327): even with no prior checkpoint, the receipt makes the record truthful
    # rather than crashing — it mints a terminal checkpoint and journals the event.
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-nockpt"
    proc = _run(repo, wi, ["--pr", "12"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
    cp = ckpt_lib.read(control_plane.paths(str(repo), wi)["checkpoint"])
    assert cp["phase"] == "shipped-manual"
    assert token_trend.classify(_events(repo, wi)) == "completed"


def test_malformed_incompatible_checkpoint_fails_closed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-bad"
    paths = control_plane.paths(str(repo), wi)
    os.makedirs(os.path.dirname(paths["checkpoint"]), exist_ok=True)
    # An unknown/newer durable shape must NOT be overwritten blindly — fail closed.
    Path(paths["checkpoint"]).write_text(json.dumps({"schemaVersion": 999}))
    proc = _run(repo, wi, ["--pr", "3"])
    out = json.loads(proc.stdout)
    assert out["ok"] is False and "incompatible" in out["error"]
    # No receipt was written over an unreadable record.
    assert not [e for e in _events(repo, wi) if e.get("type") == "manual_completion"]


def _capsys_json(capsys):
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_checkpoint_write_failure_still_leaves_the_run_reading_completed(tmp_path, monkeypatch, capsys):
    """The module's core resilience claim: the receipt event is journaled BEFORE the checkpoint
    advance, so a checkpoint-write failure still leaves every journal-reading consumer reading
    'completed'. Pins the append→write ordering the guarantee depends on (a reorder would break it
    silently and the subprocess happy-path tests would all still pass)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-ckptfail"
    _seed_dark_parked_run(repo, wi)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(entry.ckpt_lib, "write",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))

    rc = entry.main(["--work-item", wi, "--pr", "5"])
    assert rc == 0
    out = _capsys_json(capsys)
    assert out["ok"] is True and out["checkpointWritten"] is False and "disk full" in out["error"]
    # The receipt DID land (append ran first) → the run reads completed despite the failed advance.
    events = _events(repo, wi)
    assert [e for e in events if e.get("type") == "manual_completion"]
    assert run_watch._read_run(str(repo), wi, events)["state"] == "completed"
    assert token_trend.classify(events) == "completed"


def test_checkpoint_failure_then_retry_converges_without_a_duplicate_receipt(tmp_path, monkeypatch, capsys):
    """After a checkpoint-write failure the journal already carries the receipt. A retry must NOT
    append a second receipt (idempotency keyed on the durable append, not only the checkpoint
    marker) yet must still advance the checkpoint so the record fully converges."""
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-retryconv"
    _seed_dark_parked_run(repo, wi)
    monkeypatch.chdir(repo)

    # A checkpoint write that fails ONCE then recovers (a transient disk-full), so the second
    # invocation exercises the real write path. A narrow shim — NOT monkeypatch.undo(), which would
    # also revert conftest's store-root isolation and re-point at the developer's real store.
    real_write = entry.ckpt_lib.write
    calls = {"n": 0}

    def _flaky_write(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real_write(*a, **k)

    monkeypatch.setattr(entry.ckpt_lib, "write", _flaky_write)

    # 1st call: checkpoint write fails after the receipt is journaled.
    entry.main(["--work-item", wi, "--pr", "5"])
    capsys.readouterr()
    assert len([e for e in _events(repo, wi) if e.get("type") == "manual_completion"]) == 1

    # 2nd call (disk recovered): no duplicate receipt, and the checkpoint now converges to terminal.
    rc = entry.main(["--work-item", wi, "--pr", "5"])
    assert rc == 0
    out = _capsys_json(capsys)
    assert out["ok"] is True and out["already"] is True and out["checkpointWritten"] is True
    receipts = [e for e in _events(repo, wi) if e.get("type") == "manual_completion"]
    assert len(receipts) == 1, "a retry must not append a duplicate receipt"
    cp = ckpt_lib.read(control_plane.paths(str(repo), wi)["checkpoint"])
    assert cp["phase"] == "shipped-manual"


def test_durable_journal_write_failure_fails_closed_and_writes_nothing(tmp_path, monkeypatch, capsys):
    """A failed durable append is fail-closed: ok:False, NO checkpoint advance (the record stays
    honestly parked). Guards the ordering symmetry — a reorder that advanced the checkpoint before
    the failed append would flip the record to shipped-manual with no receipt ever journaled."""
    repo = tmp_path / "repo"
    repo.mkdir()
    wi = "wi-journalfail"
    _seed_dark_parked_run(repo, wi)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(entry.journal, "append",
                        lambda *a, **k: (_ for _ in ()).throw(journal.DurableWriteError("ENOSPC")))

    rc = entry.main(["--work-item", wi, "--pr", "5"])
    assert rc == 0
    out = _capsys_json(capsys)
    assert out["ok"] is False and "durable" in out["error"]
    # Nothing was written: no receipt, and the checkpoint is NOT terminal — still parked.
    assert not [e for e in _events(repo, wi) if e.get("type") == "manual_completion"]
    cp = ckpt_lib.read(control_plane.paths(str(repo), wi)["checkpoint"])
    assert cp["phase"] != "shipped-manual"
    assert run_watch._read_run(str(repo), wi, _events(repo, wi))["state"] == "parked"


def test_format_journal_event_renders_the_manual_completion_line():
    """The #450 render branch in run_watch.format_journal_event — surfaces the PR (and note), and
    omits each suffix when absent."""
    full = run_watch.format_journal_event(
        {"ts": "2026-07-03T14:50:00Z", "type": "manual_completion",
         "payload": {"pr": 431, "note": "hand-finished"}})
    assert "✓ manually completed" in full and "PR 431" in full and "hand-finished" in full
    bare = run_watch.format_journal_event(
        {"ts": "2026-07-03T14:50:00Z", "type": "manual_completion", "payload": {}})
    assert "✓ manually completed" in bare and "PR" not in bare and "—" not in bare
