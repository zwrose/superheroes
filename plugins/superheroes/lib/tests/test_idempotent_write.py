import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import idempotent_write as iw


def test_already_reflected_is_a_noop():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (True, "isDraft=false"),
                              apply_fn=lambda: calls.append("applied") or (True, "pushed"))
    assert res["already"] is True
    assert res["applied"] is False
    assert res["ok"] is True
    assert calls == []                     # apply must NOT run when reality already reflects the write


def test_not_reflected_applies_once():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (False, "isDraft=true"),
                              apply_fn=lambda: (calls.append("a"), (True, "flipped"))[1])
    assert res["already"] is False
    assert res["applied"] is True
    assert res["ok"] is True
    assert calls == ["a"]


def test_unreadable_current_state_fails_closed():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (None, "gh read failed"),
                              apply_fn=lambda: calls.append("a") or (True, "x"))
    assert res["ok"] is False
    assert res["applied"] is False
    assert calls == []                     # fail-closed: never apply against an unreadable state


def test_apply_failure_propagates_not_ok():
    res = iw.idempotent_apply("head=abc",
                              current_reader=lambda: (False, "behind"),
                              apply_fn=lambda: (False, "push rejected"))
    assert res["applied"] is True
    assert res["ok"] is False
    assert res["reason"]


def test_reconcile_head_pattern_in_sync_and_local_ahead():
    # Teeth for ship_phase reconcile-head (UFR-6 call-site 1): it wires reader=(remote==local),
    # applier=push, key='head=<local>'. Drive both happy paths through the primitive with that exact
    # shape — in sync (remote==local) is a no-op; local-ahead (remote!=local) applies the push once.
    pushed = []
    in_sync = iw.idempotent_apply("head=abc",
                                  current_reader=lambda: (True, "remote=abc local=abc"),
                                  apply_fn=lambda: pushed.append(1) or (True, "pushed"))
    assert in_sync["already"] is True and in_sync["ok"] is True and pushed == []
    ahead = iw.idempotent_apply("head=abc",
                                current_reader=lambda: (False, "remote=old local=abc"),
                                apply_fn=lambda: (pushed.append(1), (True, "pushed"))[1])
    assert ahead["applied"] is True and ahead["ok"] is True and pushed == [1]
