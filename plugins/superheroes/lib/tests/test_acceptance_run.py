# plugins/superheroes/lib/tests/test_acceptance_run.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as real_deps
import acceptance_result
import acceptance_run as run


def _deps(**over):
    """A fully-stubbed happy-path dep bundle; override any seam per test."""
    state = {"records_written": [], "refusal_records_written": [], "lease_released": False,
             "lease_quarantined": None, "orphan_records_written": []}
    # These phase names are arbitrary self-consistent verdict-logic inputs; the real
    # pipeline phase list is read from showrunner.js via acceptance_phases.
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
        write_refusal_record=lambda rec: state["refusal_records_written"].append(rec)
        or "/refusal-rec.json",
        write_orphan_record=lambda rec: state["orphan_records_written"].append(rec)
        or "/orphan-rec.json",
        quarantine_lease=lambda stamp: state.__setitem__("lease_quarantined", stamp),
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


def test_confirmed_alive_prior_run_writes_refusal_record_without_releasing_other_lease():
    d = _deps(reclaim_probe=lambda: ({"in_flight": True, "stamp": "old", "has_record": True},
                                     "alive"))
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert r["record_path"] == "/refusal-rec.json"
    assert len(d["_state"]["records_written"]) == 0
    assert len(d["_state"]["refusal_records_written"]) == 1
    rec = d["_state"]["refusal_records_written"][0]
    assert rec["verdict"] == "fail"
    assert "prior acceptance run" in rec["reason"]
    assert d["_state"]["lease_released"] is False


def test_free_lease_still_runs_recordless_discovery_cleanup_before_new_run():
    discover_calls = []
    reap_calls = []

    def discover_artifacts(stamp):
        discover_calls.append(stamp)
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-leftover"}]
        return [{"kind": "branch", "name": "b-s1"}]

    def reap(planned):
        reap_calls.append(planned)
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(discover_artifacts=discover_artifacts, reap=reap)
    r = run.invoke(d)

    assert r["verdict"] == "pass"
    assert discover_calls[0] is None
    rec = d["_state"]["records_written"][0]
    assert "wi-accept-harness-leftover" in rec["cleaned_up"]


def test_preflight_refusal_record_includes_prior_discovery_cleanup():
    def discover_artifacts(stamp):
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-leftover"}]
        return [{"kind": "branch", "name": "b-s1"}]

    def reap(planned):
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(
        discover_artifacts=discover_artifacts,
        reap=reap,
        preflight_ok=lambda wi: {"ok": False, "reason": "config-resolves preflight failed"},
    )
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    rec = d["_state"]["records_written"][0]
    assert "wi-accept-harness-leftover" in rec["cleaned_up"]
    assert rec["run_stamp"] == "s1"


def test_reclaimed_dead_run_reaps_its_own_leftover_artifacts_before_proceeding():
    # UFR-8: a confirmed-dead prior run's leftover branch/PR/work-item-dir artifacts must
    # be reaped via a record-less discovery cleanup (run_stamp=None), not just backstopped
    # with an orphan record. Pins the discover_artifacts(None)/reap(run_stamp=None) call
    # that must happen BEFORE this invocation's own materialize/launch.
    discover_calls = []
    reap_calls = []

    def discover_artifacts(stamp):
        discover_calls.append(stamp)
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-deadrun"}]
        return [{"kind": "branch", "name": "b-s1"}]

    def reap(planned):
        reap_calls.append(planned)
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(
        reclaim_probe=lambda: ({"in_flight": True, "stamp": "accept-harness-deadrun",
                                "has_record": False}, "dead"),
        discover_artifacts=discover_artifacts,
        reap=reap,
    )
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    # The record-less discovery call (run_stamp=None) happened, and its plan reaped the
    # dead run's own branch — proving _discovery_teardown actually executed the reap, not
    # just planned it.
    assert None in discover_calls
    assert any(
        any(a.get("name") == "wi-accept-harness-deadrun" for a in call.get("reap") or [])
        for call in reap_calls
    )
    # The orphan record for the dead run reflects what was actually cleaned up, not a
    # hardcoded empty list.
    assert len(d["_state"]["orphan_records_written"]) == 1
    assert d["_state"]["orphan_records_written"][0]["cleaned_up"] == [
        "wi-accept-harness-deadrun"
    ]


def test_reclaimed_dead_run_writes_orphan_sidecar_and_final_record(tmp_path):
    root = str(tmp_path)
    orphan_paths = []
    final_writer = real_deps.real_write_record(root)
    orphan_writer = real_deps.real_write_orphan_record(root)

    def write_orphan_record(record):
        path = orphan_writer(record)
        orphan_paths.append(path)
        return path

    def discover_artifacts(stamp):
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-deadrun"}]
        return [{"kind": "branch", "name": "b-s1"}]

    def reap(planned):
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(
        reclaim_probe=lambda: ({"in_flight": True, "stamp": "accept-harness-deadrun",
                                "has_record": False}, "dead"),
        discover_artifacts=discover_artifacts,
        reap=reap,
        write_record=final_writer,
        write_orphan_record=write_orphan_record,
    )

    r = run.invoke(d)

    assert r["verdict"] == "pass"
    assert len(orphan_paths) == 1
    orphan_record = acceptance_result.read_record(os.path.dirname(orphan_paths[0]))
    final_record = acceptance_result.read_record(real_deps._record_dir(root))
    assert orphan_record["reason"] == "orphan record for a reclaimed dead prior run"
    assert orphan_record["run_stamp"] == "accept-harness-deadrun"
    assert final_record["verdict"] == "pass"
    assert final_record["run_stamp"] == "s1"
    assert orphan_paths[0] in r["report"]


def test_parked_terminal_is_fail_but_teardown_still_runs():
    launches = []
    def _launcher(stamped, budget_consumed=None, attempt=1):
        launches.append(attempt)
        return {"outcome": "exited", "terminal_location": "/t.json", "spend_partial": False,
                "spend": 1.25, "elapsed_sec": 42.0}
    d = _deps(run_outcome=lambda loc: {"terminal": "parked", "phases": ["plan"],
                                       "readout_pr_link": "", "readout_claimed_checks_green": False,
                                       "readout_claimed_pr": "", },
              launcher=_launcher)
    reaped = []
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": ["b-s1"], "left_behind": []}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert reaped   # teardown still ran on the non-ready terminal (UFR-1)
    assert launches == [1]


def test_ceiling_kill_fails_tears_down_and_never_retries():
    launches = []
    d = _deps(
        launcher=lambda stamped, budget_consumed=None, attempt=1: (
            launches.append(attempt) or {
                "outcome": "killed", "ceiling": "elapsed", "terminal_location": None,
                "spend_partial": False, "spend": 0.25, "elapsed_sec": 99.0,
            }),
        run_outcome=lambda loc: (_ for _ in ()).throw(AssertionError("killed run has no terminal")),
    )
    reaped = []
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": ["b-s1"], "left_behind": []}
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "ceiling breached" in r["report"]
    assert launches == [1]
    assert reaped
    rec = d["_state"]["records_written"][0]
    assert rec["retried"] is False
    assert len(rec["attempts"]) == 1


def test_unconfirmed_kill_skips_cleanup_because_process_group_may_still_be_alive():
    def discover_artifacts(stamp):
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-leftover"}]
        return [{"kind": "branch", "name": "b-s1"}]

    def reap(planned):
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(
        discover_artifacts=discover_artifacts,
        reap=reap,
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "kill-unconfirmed", "ceiling": "elapsed", "terminal_location": None,
            "spend_partial": False, "spend": 0.25, "elapsed_sec": 99.0,
            "teardown_safe": False,
        },
        run_outcome=lambda loc: (_ for _ in ()).throw(AssertionError("unsafe kill has no terminal")),
    )
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    rec = d["_state"]["records_written"][0]
    assert rec["cleaned_up"] == ["wi-accept-harness-leftover"]
    assert rec["left_behind"]
    assert "cleanup skipped" in str(rec["left_behind"][0])
    assert d["_state"]["lease_quarantined"] == "s1"
    assert d["_state"]["lease_released"] is False


def test_unconfirmed_kill_exception_path_skips_cleanup_and_keeps_lease():
    reap_calls = []

    def discover_artifacts(stamp):
        if stamp is None:
            return []
        return [{"kind": "branch", "name": "wi-s1"}]

    def reap(planned):
        reap_calls.append(planned)
        return {"cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    d = _deps(
        discover_artifacts=discover_artifacts,
        reap=reap,
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "kill-unconfirmed", "ceiling": "elapsed", "terminal_location": None,
            "spend_partial": False, "spend": 0.25, "elapsed_sec": 99.0,
            "teardown_safe": False,
        },
        quarantine_lease=lambda stamp: (_ for _ in ()).throw(OSError("lease store read-only")),
        run_outcome=lambda loc: (_ for _ in ()).throw(AssertionError("unsafe kill has no terminal")),
    )
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "lease store read-only" in r["report"]
    assert reap_calls == []
    rec = d["_state"]["records_written"][0]
    assert rec["cleaned_up"] == []
    assert rec["left_behind"]
    assert "cleanup skipped" in str(rec["left_behind"][0])
    assert d["_state"]["lease_released"] is False


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
            return {"terminal": "parked", "phases": [], "readout_pr_link": "",
                    "readout_claimed_checks_green": False, "readout_claimed_pr": "",
                    "failure_kind": "freeform host unreachable text must not matter"}
        return {"terminal": "ready", "phases": ["plan", "tasks", "build", "review", "ship"],
                "readout_pr_link": "https://x/pr/1", "readout_claimed_checks_green": True,
                "readout_claimed_pr": "https://x/pr/1"}

    stamps = iter(["s1", "s2"])
    d = _deps(
        launcher=_launcher, run_outcome=_run_outcome,
        gh_reader=lambda: {"pr_exists": True, "pr_ready_for_review": True, "checks_green": True,
                           "live_checks_green": True, "live_pr": "https://x/pr/1",
                           "unreadable": [], "failure_kind": "host-unreachable"},
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
    # module docstring (line 32): top-level FR-5 spend/elapsed_sec are the INVOCATION
    # total across both attempts, not just the second (successful) attempt's figures.
    assert rec["spend"] == 1.5
    assert rec["elapsed_sec"] == 420.0


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
        return {"terminal": "parked", "phases": [], "readout_pr_link": "",
                "readout_claimed_checks_green": False, "readout_claimed_pr": "",
                "failure_kind": "freeform host unreachable text must not matter"}

    reap_calls = []

    def _discover_artifacts(stamp):
        if stamp is None:
            return [{"kind": "branch", "name": "wi-accept-harness-leftover"}]
        return [{"kind": "branch", "name": "accept-harness-s1-a"}]

    def _reap(planned):
        reap_calls.append(planned)
        if any(a.get("name") == "wi-accept-harness-leftover" for a in planned.get("reap") or []):
            return {"cleaned_up": ["wi-accept-harness-leftover"], "left_behind": []}
        # The pre-retry reap fails to remove the branch -> left_behind is non-empty.
        return {"cleaned_up": [], "left_behind": ["accept-harness-s1-a"]}

    d = _deps(
        launcher=_launcher, run_outcome=_run_outcome, reap=_reap,
        discover_artifacts=_discover_artifacts,
        gh_reader=lambda: {"pr_exists": True, "pr_ready_for_review": True, "checks_green": True,
                           "live_checks_green": True, "live_pr": "https://x/pr/1",
                           "unreadable": [], "failure_kind": "host-unreachable"},
        materialize=lambda: {"work_item": "wi-s1", "branch": "b-s1", "pr_title": "PR s1",
                             "stamp": "s1"},
    )
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "cleanup" in r["report"].lower() or "left" in r["report"].lower()
    # exactly one launch — no second attempt was spun up alongside the surviving artifact.
    assert [l["attempt"] for l in launches] == [1]
    # exactly two reap calls: the pre-launch discovery sweep, then the pre-retry teardown;
    # no duplicate final reap runs after the current-stamp cleanup failed.
    assert len(reap_calls) == 2
    # exactly one record, naming only the single attempt, not retried.
    assert len(d["_state"]["records_written"]) == 1
    rec = d["_state"]["records_written"][0]
    assert rec["retried"] is False
    assert len(rec["attempts"]) == 1
    assert rec["cleaned_up"] == ["wi-accept-harness-leftover"]
    assert rec["left_behind"] == ["accept-harness-s1-a"]


def test_freeform_failure_reason_alone_does_not_trigger_environmental_retry():
    launches = []

    def _launcher(stamped, budget_consumed=None, attempt=1):
        launches.append(attempt)
        return {"outcome": "exited", "terminal_location": "/t1.json",
                "spend_partial": False, "spend": 1.0, "elapsed_sec": 300.0}

    d = _deps(
        launcher=_launcher,
        run_outcome=lambda loc: {"terminal": "parked", "phases": [], "readout_pr_link": "",
                                 "readout_claimed_checks_green": False,
                                 "readout_claimed_pr": "",
                                 "failure_kind": "host-unreachable"},
    )
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert launches == [1]
