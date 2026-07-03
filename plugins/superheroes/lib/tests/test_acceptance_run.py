# plugins/superheroes/lib/tests/test_acceptance_run.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_run as run


def _deps(**over):
    """A fully-stubbed happy-path dep bundle; override any seam per test."""
    state = {"records_written": [], "lease_released": False}
    base = dict(
        reclaim_probe=lambda: ({"in_flight": False, "stamp": None, "has_record": False}, "dead"),
        preflight_ok=lambda wi: {"ok": True},
        materialize=lambda: {"work_item": "wi-s1", "branch": "b-s1", "pr_title": "PR s1",
                             "stamp": "s1"},
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "exited", "terminal_location": "/t.json", "spend_partial": False,
            "spend": 1.25, "elapsed_sec": 42.0},
        run_outcome=lambda loc: {"terminal": "ready", "phases": ["plan", "tasks", "build",
                                 "review", "ship"], "readout_pr_link": "https://x/pr/1",
                                 "readout_claimed_checks_green": True,
                                 "readout_claimed_pr": "https://x/pr/1"},
        gh_reader=lambda: {"pr_exists": True, "pr_ready_for_review": True, "checks_green": True,
                           "live_checks_green": True, "live_pr": "https://x/pr/1", "unreadable": []},
        expected_phases=lambda: ["plan", "tasks", "build", "review", "ship"],
        discover_artifacts=lambda stamp: [{"kind": "branch", "name": "b-s1"}],
        reap=lambda planned: {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []},
        write_record=lambda rec: state["records_written"].append(rec) or "/rec.json",
        release_lease=lambda: state.__setitem__("lease_released", True),
        clock_now=lambda: "2026-07-02T00:00:00Z",
        _state=state,
    )
    base.update(over)
    return base


def test_happy_path_is_pass_one_record_one_report_lease_released():
    d = _deps()
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    assert len(d["_state"]["records_written"]) == 1
    assert r["record_path"] == "/rec.json"
    assert d["_state"]["lease_released"] is True   # released AFTER the record write
    # the FR-5-required spend/elapsed come from the launcher result, not invented downstream.
    rec = d["_state"]["records_written"][0]
    assert rec["spend"] == 1.25 and rec["elapsed_sec"] == 42.0


def test_confirmed_alive_prior_run_refuses_creating_nothing():
    d = _deps(reclaim_probe=lambda: ({"in_flight": True, "stamp": "old", "has_record": True},
                                     "alive"))
    calls = []
    d["materialize"] = lambda: calls.append("m") or {"work_item": "x"}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "in flight" in r["report"].lower() or "in-flight" in r["report"].lower()
    assert calls == []   # nothing materialized/launched


def test_parked_terminal_is_fail_but_teardown_still_runs():
    d = _deps(run_outcome=lambda loc: {"terminal": "parked", "phases": ["plan"],
                                       "readout_pr_link": "", "readout_claimed_checks_green": False,
                                       "readout_claimed_pr": "", })
    reaped = []
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": ["b-s1"], "left_behind": []}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert reaped   # teardown still ran on the non-ready terminal (UFR-1)


def test_internal_harness_error_still_teardowns_and_fails_never_pass():
    boom = _deps()
    boom["gh_reader"] = lambda: (_ for _ in ()).throw(RuntimeError("gh blew up"))
    reaped = []
    boom["reap"] = lambda planned: reaped.append(1) or {"cleaned_up": [], "left_behind": []}
    r = run.invoke(boom)
    assert r["verdict"] == "fail"
    assert "gh blew up" in r["report"] or "error" in r["report"].lower()
    assert reaped   # teardown ran despite the internal error


def test_record_write_failure_ends_with_lease_held():
    d = _deps(write_record=lambda rec: (_ for _ in ()).throw(OSError("disk full")))
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert d["_state"]["lease_released"] is False   # lease held so UFR-8 backstop stays armed


def test_environmental_retry_folds_two_attempts_into_one_record_sharing_budget():
    # FR-9: attempt 1 fails environmentally -> exactly one retry, one record naming both
    # attempts, and the retry launch is fed the invocation's REMAINING budget (budget_consumed
    # from attempt 1), not a fresh full ceiling.
    launches = []

    def _launcher(stamped, budget_consumed=None, attempt=1):
        launches.append({"attempt": attempt, "budget_consumed": budget_consumed})
        if attempt == 1:
            # environmental first-attempt failure (host unreachable), 300s + $1 consumed.
            return {"outcome": "exited", "terminal_location": "/t1.json",
                    "spend_partial": False, "spend": 1.0, "elapsed_sec": 300.0}
        return {"outcome": "exited", "terminal_location": "/t2.json",
                "spend_partial": False, "spend": 0.5, "elapsed_sec": 120.0}

    def _run_outcome(loc):
        if loc == "/t1.json":
            # a classifiably-environmental terminal (host-unreachable) -> retry.
            return {"terminal": "host-unreachable", "phases": [], "readout_pr_link": "",
                    "readout_claimed_checks_green": False, "readout_claimed_pr": "",
                    "failure_kind": "host-unreachable"}
        return {"terminal": "ready", "phases": ["plan", "tasks", "build", "review", "ship"],
                "readout_pr_link": "https://x/pr/1", "readout_claimed_checks_green": True,
                "readout_claimed_pr": "https://x/pr/1"}

    stamps = iter(["s1", "s2"])
    d = _deps(
        launcher=_launcher, run_outcome=_run_outcome,
        materialize=lambda: (lambda s: {"work_item": "wi-%s" % s, "branch": "b-%s" % s,
                                        "pr_title": "PR %s" % s, "stamp": s})(next(stamps)),
    )
    r = run.invoke(d)
    assert r["verdict"] == "pass"                       # the retry succeeded
    # exactly two launches: the second fed attempt-1's consumed budget (remaining, not fresh).
    assert [l["attempt"] for l in launches] == [1, 2]
    assert launches[1]["budget_consumed"]["elapsed_sec"] == 300.0
    assert launches[1]["budget_consumed"]["spend"] == 1.0
    # exactly one record, naming BOTH attempts.
    assert len(d["_state"]["records_written"]) == 1
    rec = d["_state"]["records_written"][0]
    assert rec["retried"] is True
    assert len(rec["attempts"]) == 2


def test_pre_retry_cleanup_failure_aborts_the_retry_no_second_attempt():
    # FR-9/UFR-3: attempt 1 fails environmentally (retry-eligible), but the pre-retry
    # teardown leaves an artifact behind -> no retry launches; the invocation ends on the
    # cleanup-failure path naming the surviving artifact, with exactly ONE attempt recorded.
    launches = []

    def _launcher(stamped, budget_consumed=None, attempt=1):
        launches.append({"attempt": attempt, "budget_consumed": budget_consumed})
        return {"outcome": "exited", "terminal_location": "/t1.json",
                "spend_partial": False, "spend": 1.0, "elapsed_sec": 300.0}

    def _run_outcome(loc):
        return {"terminal": "host-unreachable", "phases": [], "readout_pr_link": "",
                "readout_claimed_checks_green": False, "readout_claimed_pr": "",
                "failure_kind": "host-unreachable"}

    reap_calls = []

    def _reap(planned):
        reap_calls.append(planned)
        # The pre-retry reap fails to remove the branch -> left_behind is non-empty.
        return {"cleaned_up": [], "left_behind": ["b-s1"]}

    d = _deps(
        launcher=_launcher, run_outcome=_run_outcome, reap=_reap,
        materialize=lambda: {"work_item": "wi-s1", "branch": "b-s1", "pr_title": "PR s1",
                             "stamp": "s1"},
    )
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "cleanup" in r["report"].lower() or "left" in r["report"].lower()
    # exactly one launch — no second attempt was spun up alongside the surviving artifact.
    assert [l["attempt"] for l in launches] == [1]
    # exactly one reap call (the pre-retry teardown) — no duplicate second reap.
    assert len(reap_calls) == 1
    # exactly one record, naming only the single attempt, not retried.
    assert len(d["_state"]["records_written"]) == 1
    rec = d["_state"]["records_written"][0]
    assert rec["retried"] is False
    assert len(rec["attempts"]) == 1
    assert rec["left_behind"] == ["b-s1"]
