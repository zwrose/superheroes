# plugins/superheroes/lib/tests/test_acceptance_verdict.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_verdict as v

# These phase names are arbitrary self-consistent verdict-logic inputs; the real
# pipeline phase list is read from showrunner.js via acceptance_phases.
PASS = dict(
    terminal="ready", pr_exists=True, pr_ready_for_review=True, checks_green=True,
    phases_traversed=["plan", "tasks", "build", "review", "ship"],
    expected_phases=["plan", "tasks", "build", "review", "ship"],
    readout_exists=True, readout_pr_link="https://x/pr/1",
    readout_claimed_checks_green=True, live_checks_green=True,
    readout_claimed_pr="https://x/pr/1", live_pr="https://x/pr/1",
    unreadable=[],
)


def test_all_facts_true_is_pass():
    assert v.decide(dict(PASS))["verdict"] == "pass"


def test_terminal_not_ready_is_fail_naming_it():
    f = dict(PASS); f["terminal"] = "parked"
    r = v.decide(f); assert r["verdict"] == "fail" and "terminal" in r["reason"].lower()


def test_missing_pr_is_fail():
    f = dict(PASS); f["pr_exists"] = False
    assert v.decide(f)["verdict"] == "fail"


def test_red_checks_is_fail():
    f = dict(PASS); f["checks_green"] = False
    assert v.decide(f)["verdict"] == "fail"


def test_missing_phase_is_fail():
    f = dict(PASS); f["phases_traversed"] = ["plan", "tasks", "build", "review"]
    assert v.decide(f)["verdict"] == "fail"


def test_readout_missing_or_no_pr_link_is_fail():
    f = dict(PASS); f["readout_pr_link"] = ""
    assert v.decide(f)["verdict"] == "fail"


def test_readout_claims_green_but_live_red_is_inconsistent_fail():
    f = dict(PASS); f["readout_claimed_checks_green"] = True; f["live_checks_green"] = False
    r = v.decide(f)
    assert r["verdict"] == "fail" and "inconsistent" in r["reason"].lower()


def test_readout_pr_differs_from_live_pr_is_inconsistent_fail():
    f = dict(PASS); f["readout_claimed_pr"] = "https://x/pr/9"; f["live_pr"] = "https://x/pr/1"
    r = v.decide(f)
    assert r["verdict"] == "fail" and "inconsistent" in r["reason"].lower()


def test_unreadable_required_fact_is_fail_naming_it_never_pass():
    f = dict(PASS); f["unreadable"] = ["live_checks_green"]
    r = v.decide(f)
    assert r["verdict"] == "fail" and "live_checks_green" in r["reason"]


# --- #310 engine authenticity ----------------------------------------------------------
# A run whose calibration routed a role externally must prove the external dispatch chain
# actually worked at least once. Without this gate a silent/total fall-open to Claude is
# byte-identical to a healthy run in every terminal fact above — the exact 0.11.0 escape
# (9 external dispatches, all failed, PASSED).

def _dispatch(engine, outcome, role_kind="review"):
    return {"type": "external_dispatch",
            "payload": {"engine": engine, "roleKind": role_kind, "effort": "high",
                        "verify": None, "outcome": outcome}}


def test_tally_counts_ok_failed_by_engine_and_reasons():
    events = [_dispatch("codex", "ok"), _dispatch("codex", "timeout"),
              _dispatch("cursor", "commit-failed", "build"),
              _dispatch("cursor", "engine-unavailable", "build"),
              {"type": "phase_record", "payload": {"phase": "review"}}]  # non-dispatch ignored
    t = v.tally_external_dispatches(events)
    assert t["ok"] == 1 and t["failed"] == 2
    assert t["by_engine"] == {"codex": {"ok": 1, "total": 2}, "cursor": {"ok": 0, "total": 1}}
    assert t["acceptable_reasons"] == ["engine-unavailable"]   # not counted as a failure


def test_tally_never_raises_on_garbage():
    assert v.tally_external_dispatches(None) == {"ok": 0, "failed": 0, "by_engine": {},
                                                 "acceptable_reasons": []}
    # Two malformed external_dispatch events (no payload / non-dict payload) each read as an
    # unnamed "external" engine with a None (=> failed) outcome; non-dispatch garbage is skipped.
    assert v.tally_external_dispatches([None, "x", {"type": "external_dispatch"},
                                        {"type": "external_dispatch", "payload": "nope"}]) == \
        {"ok": 0, "failed": 2, "by_engine": {"external": {"ok": 0, "total": 2}},
         "acceptable_reasons": []}


def _external_pass(**over):
    """A run that passes every TERMINAL fact and is EXTERNAL-calibrated — the engine
    authenticity gate is the only thing that can flip it."""
    f = dict(PASS); f["external_calibration"] = True
    f.update(over)
    return f


def test_external_calibration_absent_ignores_engine_facts_backward_compat():
    # The pre-#310 fact set (no external_calibration) still passes unchanged.
    assert v.decide(dict(PASS))["verdict"] == "pass"
    # Explicitly non-external also skips the gate even with a zero tally present.
    f = dict(PASS); f["external_calibration"] = False
    f["external_dispatch_tally"] = {"ok": 0, "by_engine": {"codex": {"ok": 0, "total": 8}}}
    assert v.decide(f)["verdict"] == "pass"


def test_external_with_one_ok_dispatch_passes():
    f = _external_pass(external_dispatch_tally=v.tally_external_dispatches(
        [_dispatch("codex", "ok"), _dispatch("cursor", "timeout", "build")]))
    assert v.decide(f)["verdict"] == "pass"


def test_external_all_failed_is_fail_naming_the_tallies():
    f = _external_pass(external_dispatch_tally=v.tally_external_dispatches(
        [_dispatch("cursor", "commit-failed", "build")]
        + [_dispatch("codex", "timeout") for _ in range(8)]))
    r = v.decide(f)
    assert r["verdict"] == "fail"
    assert "codex 0/8" in r["reason"] and "cursor 0/1" in r["reason"]
    assert "failed every dispatch" in r["reason"]


def test_external_zero_events_is_fail_silent_fallopen():
    f = _external_pass(external_dispatch_tally={"ok": 0, "failed": 0, "by_engine": {},
                                                "acceptable_reasons": []})
    r = v.decide(f)
    assert r["verdict"] == "fail" and "silent fall-open" in r["reason"]


def test_external_journaled_fallopen_reason_passes():
    # An explicitly journaled authz-denied / engine-unavailable is a VISIBLE, legitimate
    # fall-open — the run honestly disclosed why it fell open (and NOTHING genuinely failed),
    # so it is not failed.
    f = _external_pass(external_dispatch_tally=v.tally_external_dispatches(
        [_dispatch("codex", "authz-denied"), _dispatch("cursor", "engine-unavailable", "build")]))
    assert v.decide(f)["verdict"] == "pass"


def test_external_reason_does_not_excuse_a_co_tenant_engines_total_failure():
    # review #310 (code-001/sec-002): one engine's legitimate fall-open must NOT globally excuse
    # a DIFFERENT engine that genuinely failed every dispatch. cursor legitimately unavailable +
    # codex 0/8 genuine failures -> FAIL naming codex's tally (not a pass off cursor's reason).
    f = _external_pass(external_dispatch_tally=v.tally_external_dispatches(
        [_dispatch("cursor", "engine-unavailable", "build")]
        + [_dispatch("codex", "unreadable") for _ in range(8)]))
    r = v.decide(f)
    assert r["verdict"] == "fail" and "codex 0/8" in r["reason"]


def test_external_unreadable_journal_is_fail_ufr9_never_pass():
    f = _external_pass(external_dispatch_unreadable=True)
    r = v.decide(f)
    assert r["verdict"] == "fail" and "unreadable" in r["reason"].lower()


def test_external_gate_never_masks_a_terminal_failure():
    # A run failing a terminal fact keeps THAT headline reason, not the engine reason.
    f = _external_pass(terminal="parked",
                       external_dispatch_tally={"ok": 0, "by_engine": {}, "acceptable_reasons": []})
    r = v.decide(f)
    assert r["verdict"] == "fail" and "terminal" in r["reason"].lower()


def test_0_11_0_journal_shape_9_failed_dispatches_is_fail():
    # The exact regression this issue exists for: the 0.11.0 acceptance leg journaled nine
    # external dispatches (1 cursor build + 8 codex reviews), ALL failed, and PASSED. Replay
    # that shape and assert FAIL.
    events = [_dispatch("cursor", "commit-failed", "build")] + \
             [_dispatch("codex", "unreadable") for _ in range(8)]
    tally = v.tally_external_dispatches(events)
    assert tally["ok"] == 0 and tally["by_engine"] == {"cursor": {"ok": 0, "total": 1},
                                                       "codex": {"ok": 0, "total": 8}}
    f = _external_pass(external_dispatch_tally=tally)
    r = v.decide(f)
    assert r["verdict"] == "fail"
    assert "codex 0/8" in r["reason"] and "cursor 0/1" in r["reason"]
