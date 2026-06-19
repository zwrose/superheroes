# plugins/workhorse/lib/tests/test_kill_resume_spike.py
import subprocess
import ci_loop
import control_plane as cp
import journal
import recover


def _store(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    return cp.ensure_store(str(tmp_path), root=str(tmp_path / "store"))


def test_crash_after_pr_create_before_checkpoint_no_double_create():
    # The ③ idempotency decision is REAL code (recover.pr_action), not a test closure.
    # Crash after the PR-create world-write but before the checkpoint advanced past ②:
    # on re-entry the world shows the PR exists -> the decision is ADOPT, never CREATE.
    world = {"store_ok": True, "current_content_hash": "abc",
             "pr": {"state": "open", "number": 1}, "seeded_empty": True}
    assert recover.reconcile({"branch": "superheroes/wi-abc"}, world)["action"] == "continue"
    assert recover.pr_action(world) == "adopt"          # exactly-once: NO second PR
    assert recover.pr_action({"pr": None}) == "create"  # creates exactly one only when truly absent
    assert recover.pr_action({"pr": "unknown"}) == "gate"  # transient read never re-creates


def test_crash_loop_does_not_reset_ci_bound(tmp_path):
    _store(tmp_path)
    p = cp.paths(str(tmp_path), "wi", root=str(tmp_path / "store"))
    # two write-ahead CI attempts, then "crash" — the count must SURVIVE re-entry.
    journal.append(p["events"], "ci_fix_attempt", payload={"round": 1, "failing": ["lint"]}, root=str(tmp_path))
    journal.append(p["events"], "ci_fix_attempt", payload={"round": 2, "failing": ["lint"]}, root=str(tmp_path))
    rounds, history = journal.ci_attempts(p["events"])
    assert rounds == 2                          # not reset to 0 by the crash
    # a third recurrence of the same failing set -> ci_loop halts (no infinite crash-loop)
    assert ci_loop.decide(["lint"], history, rounds + 1)[0] == "revert_and_gate"


def test_missing_checkpoint_degrades_to_world_derive():
    # the cursor write was lost entirely -> reconcile returns world_derive (today's behavior)
    assert recover.reconcile(None, {"store_ok": True})["action"] == "world_derive"
