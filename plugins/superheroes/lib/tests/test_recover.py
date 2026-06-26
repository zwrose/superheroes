# plugins/superheroes/lib/tests/test_recover.py
import recover
import recover_entry

CKPT = {"workItem": "wi", "branch": "superheroes/wi-abc123",
        "lastGoodStep": "5", "lastGoodPhase": "review-code"}
OK_WORLD = {"store_ok": True, "current_content_hash": "abc123", "pr": None,
            "seeded_empty": True}


def test_wedged_store_fails_closed():
    r = recover.reconcile(CKPT, {**OK_WORLD, "store_ok": False})
    assert r["action"] == "park_gate"


def test_no_checkpoint_world_derives():
    assert recover.reconcile(None, OK_WORLD)["action"] == "world_derive"


def test_incompatible_checkpoint_parks_instead_of_world_deriving():
    r = recover.reconcile({"_incompatible": True, "reason": "newer schema"}, OK_WORLD)
    assert r["action"] == "park_gate"
    assert "newer schema" in r["reason"]


def test_recover_entry_parks_when_cursor_phase_does_not_match_phase_list():
    r = recover_entry._phase_cursor_guard(
        {"lastGoodStep": 2, "lastGoodPhase": "review-plan"},
        ["plan", "review-plan", "tasks"],
    )
    assert r["action"] == "park_gate"
    assert "lastGoodPhase" in r["reason"]
    assert "tasks" in r["reason"]


def test_unreadable_content_hash_gates_not_resumes_blind():
    r = recover.reconcile(CKPT, {**OK_WORLD, "current_content_hash": None})
    assert r["action"] == "gate"


def test_stale_spec_cascade_gates():
    r = recover.reconcile(CKPT, {**OK_WORLD, "current_content_hash": "DIFFERENT"})
    assert r["action"] == "gate" and "stale spec" in r["reason"]


def test_matching_hash_continues():
    r = recover.reconcile(CKPT, OK_WORLD)
    assert r["action"] == "continue" and r["from_step"] == "5"


def test_merged_pr_gates():
    r = recover.reconcile(CKPT, {**OK_WORLD, "pr": {"state": "merged"}})
    assert r["action"] == "gate" and "merged" in r["reason"]


def test_transient_pr_read_gates_never_absent():
    r = recover.reconcile(CKPT, {**OK_WORLD, "pr": "unknown"})
    assert r["action"] == "gate"


def test_transient_seeded_read_gates():
    r = recover.reconcile(CKPT, {**OK_WORLD, "seeded_empty": "unknown"})
    assert r["action"] == "gate"


def test_pr_action_adopt_create_gate():
    assert recover.pr_action({"pr": {"state": "open", "number": 1}}) == "adopt"
    assert recover.pr_action({"pr": None}) == "create"
    assert recover.pr_action({"pr": "unknown"}) == "gate"
    assert recover.pr_action({"pr": {"state": "merged", "number": 1}}) == "gate"
    assert recover.pr_action({"pr": {}}) == "gate"   # malformed/empty read -> don't guess
    assert recover.pr_action({"pr": "closed"}) == "gate"   # unexpected string sentinel -> fail-closed


def test_rearm_action_proceeds_retries_then_parks():
    assert recover.rearm_action(1, True) == "proceed"
    assert recover.rearm_action(1, False) == "retry"
    assert recover.rearm_action(2, False) == "retry"   # inner boundary: < vs <= mutant guard
    assert recover.rearm_action(3, False) == "park_gate"
