# plugins/superheroes/lib/tests/test_acceptance_verdict.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_verdict as v

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
