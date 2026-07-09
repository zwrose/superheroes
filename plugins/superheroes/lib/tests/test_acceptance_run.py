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


def test_spine_provenance_seam_stamps_record_and_report():
    # #235: when the deps carry a spine_provenance seam (a `--spine-lib` run), the single
    # record AND the plain-language report must both name which spine was under test.
    prov = {"lib_path": "/repo/plugins/superheroes/lib",
            "bundle_sha256": "cafef00d", "version": "0.11.0"}
    d = _deps(spine_provenance=lambda: prov)
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    rec = d["_state"]["records_written"][0]
    assert rec["spine_provenance"] == prov
    assert "/repo/plugins/superheroes/lib" in r["report"]
    assert "cafef00d" in r["report"]


def test_spine_provenance_resolved_once_record_and_report_agree():
    # premortem #235: the seam re-hashes the bundle on every call, so resolving it twice
    # (once for the report, once for the record) could record a hash that disagrees with
    # the report's. invoke must resolve it ONCE and thread the same value to both.
    calls = {"n": 0}

    def _counting_seam():
        calls["n"] += 1
        return {"lib_path": "/repo/lib", "bundle_sha256": "hash-%d" % calls["n"],
                "version": "0.11.0"}

    d = _deps(spine_provenance=_counting_seam)
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    rec = d["_state"]["records_written"][0]
    # exactly one resolution across the whole invocation...
    assert calls["n"] == 1
    # ...so the record's hash and the report's hash are the SAME single read.
    assert rec["spine_provenance"]["bundle_sha256"] == "hash-1"
    assert "hash-1" in r["report"]


def test_default_run_records_driver_through_invoke():
    # Stitch the default-run provenance shape through the WHOLE lifecycle: a seam that
    # returns child_model only (no spine keys, as on a non-override run) must land in the
    # written record AND the rendered report — so a mutant dropping invoke's default-path
    # provenance thread is caught end-to-end, not just at the unit layer.
    d = _deps(spine_provenance=lambda: {"child_model": "sonnet"})
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    rec = d["_state"]["records_written"][0]
    assert rec["spine_provenance"] == {"child_model": "sonnet"}
    assert "sonnet" in r["report"]
    assert "not pinned" in r["report"]      # no spine keys -> "installed plugin (not pinned)"


def test_no_spine_provenance_seam_leaves_record_and_report_unchanged():
    # A fake deps bundle with no seam at all -> no spine_provenance key, no report section
    # (the real build() always wires the seam; this pins the seam-absent fallback).
    d = _deps()
    r = run.invoke(d)
    rec = d["_state"]["records_written"][0]
    assert "spine_provenance" not in rec
    assert "Provenance" not in r["report"]


# --- issue #298: root-lineage refusal (a non-ancestor --root checkout) -------------------
#
# A run rooted at a release-branch checkout (HEAD carries the release version-bump commit,
# not on origin/main) traverses the front half then false-parks mid-workhorse on UFR-7. The
# guard refuses BEFORE reclaim/lease/stamp so a refusal never holds the lease. The seam does
# the git I/O; these drive it with a fake seam (no fetch).


def test_ancestor_clean_root_proceeds_to_a_normal_run():
    launched = []
    d = _deps(root_ancestry=lambda: {"ok": True, "checked": True, "head_sha": "abc123"})
    base_launch = d["launcher"]
    d["launcher"] = lambda stamped, budget_consumed=None, attempt=1: (
        launched.append(attempt) or base_launch(stamped, budget_consumed=budget_consumed,
                                                 attempt=attempt))
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    assert launched == [1]                       # the clean root launched normally
    assert len(d["_state"]["records_written"]) == 1


def test_non_ancestor_root_refuses_pre_launch_no_lease_no_stamp():
    calls = {"reclaim": 0, "materialize": 0}
    reason = ("--root checkout HEAD deadbeef12 is not an ancestor of origin/main: it carries "
              "commit(s) not on origin/main (e.g. a release-please version bump) — UFR-7's "
              "trailer gate will false-park on them mid-run. Root the run at merged main; "
              "--spine-lib + the recorded bundle sha bind the pass to the release. ... "
              "--allow-unmerged-root.")
    d = _deps(root_ancestry=lambda: {"ok": False, "head_sha": "deadbeef12",
                                     "default_branch": "main", "reason": reason})
    base_reclaim, base_mat = d["reclaim_probe"], d["materialize"]
    d["reclaim_probe"] = lambda: (calls.__setitem__("reclaim", calls["reclaim"] + 1)
                                  or base_reclaim())
    d["materialize"] = lambda: (calls.__setitem__("materialize", calls["materialize"] + 1)
                                or base_mat())
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "deadbeef12" in r["report"]           # the message names the offending sha
    assert calls["reclaim"] == 0                 # refused BEFORE reclaim -> no lease acquired
    assert calls["materialize"] == 0             # nothing stamped
    assert len(d["_state"]["records_written"]) == 0
    # a refusal record (not a normal record) captures the refusal, no lease released.
    assert len(d["_state"]["refusal_records_written"]) == 1
    assert "deadbeef12" in d["_state"]["refusal_records_written"][0]["reason"]
    assert d["_state"]["lease_released"] is False
    assert r["record_path"] == "/refusal-rec.json"


def test_allow_unmerged_root_bypass_seam_proceeds():
    # The escape hatch wires a seam that short-circuits to ok=True (bypassed) — the run
    # proceeds exactly as a clean root would.
    d = _deps(root_ancestry=lambda: {"ok": True, "bypassed": True, "checked": False})
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    assert len(d["_state"]["records_written"]) == 1


def test_fetch_failure_degrade_continues_the_run():
    # The seam's offline degrade (fetch failed -> ok=True, checked=False, warning already
    # emitted by the seam) must let the run proceed, never silently pass AND never hard-block.
    d = _deps(root_ancestry=lambda: {"ok": True, "checked": False,
                                     "reason": "fetch failed; ancestor check skipped"})
    r = run.invoke(d)
    assert r["verdict"] == "pass"
    assert len(d["_state"]["records_written"]) == 1


def test_absent_root_ancestry_seam_skips_the_check():
    # A fake deps bundle with no seam (an injected bare builder) proceeds unchanged — the
    # guard is opt-in via the seam the real build() always wires.
    d = _deps()
    assert "root_ancestry" not in d
    r = run.invoke(d)
    assert r["verdict"] == "pass"


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


# --- issue #245: SIGTERM/SIGINT routes through the kill+teardown+record path ------------
#
# Before #245 no signal handler existed anywhere in the harness stack: a SIGTERM to the
# harness (observed live during the 0.10.0 qualification) exited WITHOUT killing the child
# group or running teardown, orphaning the `claude -p` group. The handler now raises
# `_SignalTermination` (carrying the live child captured at delivery time), and invoke's
# except path hard-kills that group FIRST, then routes through the EXISTING teardown/record
# machinery — kill-unconfirmed quarantine semantics preserved. These exercise that logic by
# raising `_SignalTermination` from a fake launcher (and calling the handler directly), so no
# real signal is ever sent to the test process.
import signal as _signal          # noqa: E402
import acceptance_launch as _al    # noqa: E402


class _SigChild:
    """Fake live child for the signal-kill path. Records signals; `group_empty()` returns
    `confirm` (True = confirmed empty on first probe, False = never confirmable -> the bounded
    escalation ends unconfirmed)."""

    def __init__(self, confirm=True):
        self.signals = []
        self._confirm = confirm

    def killpg(self, sig):
        self.signals.append(sig)

    def group_empty(self):
        return self._confirm

    def poll(self):
        return 0


def test_signal_termination_hard_kills_group_then_teardown_and_records():
    child = _SigChild(confirm=True)

    def _launcher(stamped, budget_consumed=None, attempt=1):
        raise run._SignalTermination(_signal.SIGTERM, child)

    reaped = []
    d = _deps(launcher=_launcher)
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": ["b-s1"],
                                                           "left_behind": []}
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "terminated by signal" in r["report"].lower()
    # the live group was hard-killed FIRST (SIGTERM), reusing the existing escalation.
    assert child.signals and child.signals[0] == _signal.SIGTERM
    assert reaped                                  # confirmed kill -> normal teardown ran
    rec = d["_state"]["records_written"][0]
    assert rec["reason"].startswith("terminated by signal")
    assert d["_state"]["lease_released"] is True   # confirmed kill releases the lease


def test_signal_termination_unconfirmed_kill_skips_cleanup_and_quarantines(monkeypatch):
    # A group that can't be confirmed dead must NOT reclaim: record kill-unconfirmed, SKIP
    # artifact cleanup for the stamp, quarantine + HOLD the lease — exactly the ceiling-kill
    # kill-unconfirmed semantics, now honored on the signal path too.
    monkeypatch.setattr(_al.time, "sleep", lambda s: None)  # don't sleep through the escalation
    child = _SigChild(confirm=False)

    def _launcher(stamped, budget_consumed=None, attempt=1):
        raise run._SignalTermination(_signal.SIGINT, child)

    d = _deps(launcher=_launcher)
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    rec = d["_state"]["records_written"][0]
    assert rec["reason"].startswith("terminated by signal")
    assert "cleanup skipped" in rec["reason"]
    assert rec["cleaned_up"] == []                 # the current stamp was NOT torn down
    assert rec["left_behind"] and "cleanup skipped" in str(rec["left_behind"][0])
    assert d["_state"]["lease_quarantined"] == "s1"
    assert d["_state"]["lease_released"] is False  # lease held under a possibly-live orphan
    assert len(child.signals) >= 2                 # SIGTERM then SIGKILL escalation


def test_signal_termination_with_no_live_child_still_teardowns_and_records():
    # A signal arriving with no live child (e.g. during preflight/materialize, or after the
    # launcher already returned) still routes through teardown + a single honest record.
    def _launcher(stamped, budget_consumed=None, attempt=1):
        raise run._SignalTermination(_signal.SIGTERM, None)

    reaped = []
    d = _deps(launcher=_launcher)
    d["reap"] = lambda planned: reaped.append(planned) or {"cleaned_up": [], "left_behind": []}
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "terminated by signal" in r["report"].lower()
    assert reaped                                  # no live child -> confirmed -> teardown ran
    assert d["_state"]["lease_released"] is True
    assert len(d["_state"]["records_written"]) == 1


def test_termination_handler_captures_live_child_and_disarms_without_real_signal(monkeypatch):
    # The handler itself, driven directly (no OS signal): it must capture the CURRENT live
    # child, disarm further SIGTERM/SIGINT (so a second signal can't re-enter teardown), and
    # raise _SignalTermination carrying that child + signum.
    sentinel = object()
    monkeypatch.setattr(_al, "_live_child", sentinel)
    prev_term = _signal.getsignal(_signal.SIGTERM)
    prev_int = _signal.getsignal(_signal.SIGINT)
    try:
        raised = None
        try:
            run._termination_handler(_signal.SIGTERM, None)
        except run._SignalTermination as exc:
            raised = exc
        assert raised is not None
        assert raised.child is sentinel
        assert raised.signum == _signal.SIGTERM
        # further termination signals disarmed while teardown runs (double-report guard).
        assert _signal.getsignal(_signal.SIGTERM) == _signal.SIG_IGN
        assert _signal.getsignal(_signal.SIGINT) == _signal.SIG_IGN
    finally:
        _signal.signal(_signal.SIGTERM, prev_term)
        _signal.signal(_signal.SIGINT, prev_int)


def test_install_termination_handlers_installs_and_restore_reverts():
    prev_term = _signal.getsignal(_signal.SIGTERM)
    prev_int = _signal.getsignal(_signal.SIGINT)
    try:
        restore = run._install_termination_handlers()
        assert _signal.getsignal(_signal.SIGTERM) is run._termination_handler
        assert _signal.getsignal(_signal.SIGINT) is run._termination_handler
        restore()
        assert _signal.getsignal(_signal.SIGTERM) == prev_term
        assert _signal.getsignal(_signal.SIGINT) == prev_int
    finally:
        _signal.signal(_signal.SIGTERM, prev_term)
        _signal.signal(_signal.SIGINT, prev_int)


def test_signal_after_unconfirmed_ceiling_kill_does_not_downgrade_quarantine():
    # PR #246 review (premortem BLOCKER): a signal arriving AFTER the launcher already returned
    # kill-unconfirmed (the live-child slot was cleared as run() unwound, so the handler
    # captures child=None) must NOT downgrade the kill-unconfirmed quarantine into a full reap +
    # lease release. The prior unsafe verdict is honored: cleanup skipped, lease quarantined+held.
    quarantine_calls = []

    def _quarantine(stamp):
        quarantine_calls.append(stamp)
        if len(quarantine_calls) == 1:
            # the signal lands mid-step-8, after the launcher already reported unconfirmed
            raise run._SignalTermination(_signal.SIGTERM, None)

    d = _deps(
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "kill-unconfirmed", "ceiling": "elapsed", "terminal_location": None,
            "spend_partial": False, "spend": 0.25, "elapsed_sec": 99.0, "teardown_safe": False},
        run_outcome=lambda loc: (_ for _ in ()).throw(AssertionError("unsafe kill has no terminal")),
        quarantine_lease=_quarantine,
    )
    stamp_reaps = []
    d["reap"] = lambda planned: stamp_reaps.append(planned) or {
        "cleaned_up": [a["name"] for a in planned["reap"]], "left_behind": []}

    r = run.invoke(d)

    assert r["verdict"] == "fail"
    rec = d["_state"]["records_written"][0]
    # cleanup skipped for the stamp, lease quarantined + HELD — never reclaimed by the signal path.
    assert rec["cleaned_up"] == []
    assert rec["left_behind"] and "cleanup skipped" in str(rec["left_behind"][0])
    assert d["_state"]["lease_released"] is False
    assert quarantine_calls   # quarantine was (re-)invoked; the lease stays held, never released
    # the stamp's own artifacts were never reaped (no full teardown of a possibly-live orphan).
    assert all(
        not any(a.get("name") == "b-s1" for a in call.get("reap") or [])
        for call in stamp_reaps)


def test_signal_after_record_written_does_not_rewrite_or_double_release(monkeypatch):
    # PR #246 review: a signal in the window AFTER the record was durably written + the lease
    # handled (during return-dict construction) must echo the already-computed result — not
    # re-run teardown, rewrite the record, or release the lease a second time.
    calls = {"report": 0}
    real_report = run._report

    def _report_that_signals(*a, **k):
        calls["report"] += 1
        if calls["report"] == 1:
            # first _report call is the success path's, AFTER _finalize wrote the record +
            # released the lease; simulate the signal landing right then.
            raise run._SignalTermination(_signal.SIGTERM, None)
        return real_report(*a, **k)

    monkeypatch.setattr(run, "_report", _report_that_signals)
    d = _deps()
    r = run.invoke(d)

    # exactly ONE record write, exactly ONE lease release — the signal did not double them.
    assert len(d["_state"]["records_written"]) == 1
    assert d["_state"]["lease_released"] is True
    # the echoed result still names the durably-written record.
    assert r["record_path"] == "/rec.json"


# --- #298 review r1 (premortem, fail-direction): the pre-lease window ---------------------


def test_signal_during_root_ancestry_never_releases_or_quarantines_the_lease():
    # A SIGTERM/SIGINT while step 0's root-ancestry probe is blocked in git (the probe does
    # network I/O, so this window is real and wide) must NOT release the lease: this
    # invocation has not acquired it yet, run_stamp is still None, and release_lease(None)
    # is the legacy UNCONDITIONAL remove — it would delete a CONCURRENT run's lease.
    def _ancestry():
        raise run._SignalTermination(_signal.SIGTERM, None)

    d = _deps(root_ancestry=_ancestry)
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "terminated by signal" in r["report"].lower()
    assert d["_state"]["lease_released"] is False        # the load-bearing assertion
    assert d["_state"]["lease_quarantined"] is None      # nor quarantined — we never owned it
    assert len(d["_state"]["records_written"]) == 1      # the honest record still lands


def test_internal_error_during_root_ancestry_never_releases_the_lease():
    # Same pre-lease window, generic-exception flavor: an internal error inside the probe
    # routes through the fail-closed except path, which must also skip the lease release.
    def _ancestry():
        raise RuntimeError("git exploded")

    d = _deps(root_ancestry=_ancestry)
    r = run.invoke(d)

    assert r["verdict"] == "fail"
    assert "internal harness error" in r["report"]
    assert d["_state"]["lease_released"] is False
    assert len(d["_state"]["records_written"]) == 1


def test_signal_after_reclaim_still_releases_the_owned_lease():
    # Counter-case: once the reclaim decision resolved to proceed, the lease IS ours — a
    # signal later (here: during launch, no live child) must keep today's release behavior.
    def _launcher(stamped, budget_consumed=None, attempt=1):
        raise run._SignalTermination(_signal.SIGTERM, None)

    d = _deps(launcher=_launcher)
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert d["_state"]["lease_released"] is True


# --- #310 engine-authenticity wiring through invoke() -----------------------------------

def _external_launcher():
    """A happy launcher whose run is EXTERNAL-calibrated (spend_partial True) — the shape the
    fixed engine-pref store-root read produces on a codex/cursor-calibrated project."""
    return lambda stamped, budget_consumed=None, attempt=1: {
        "outcome": "exited", "terminal_location": "/t.json", "spend_partial": True,
        "spend": 1.25, "elapsed_sec": 42.0}


def test_external_run_all_failed_dispatches_fails_the_verdict():
    # Every terminal fact passes, but the injected dispatch tally shows the external engines
    # failed every dispatch -> the run FAILS (the 0.11.0 escape, now closed).
    d = _deps(launcher=_external_launcher(),
              engine_dispatch_tally=lambda: {"ok": 0, "failed": 9,
                  "by_engine": {"codex": {"ok": 0, "total": 8}, "cursor": {"ok": 0, "total": 1}},
                  "acceptable_reasons": []})
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "codex 0/8" in d["_state"]["records_written"][0]["reason"]


def test_external_run_one_ok_dispatch_passes():
    d = _deps(launcher=_external_launcher(),
              engine_dispatch_tally=lambda: {"ok": 1, "failed": 0,
                  "by_engine": {"codex": {"ok": 1, "total": 1}}, "acceptable_reasons": []})
    r = run.invoke(d)
    assert r["verdict"] == "pass"


def test_external_run_unreadable_journal_fails_closed():
    d = _deps(launcher=_external_launcher(),
              engine_dispatch_tally=lambda: {"unreadable": True})
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "unreadable" in d["_state"]["records_written"][0]["reason"].lower()


def test_external_run_missing_tally_seam_fails_closed():
    # An external-calibrated run with NO tally seam wired must not fake a pass — the fact is
    # absent, so the verdict's external branch (no ok, no reasons) fails.
    d = _deps(launcher=_external_launcher())   # no engine_dispatch_tally
    r = run.invoke(d)
    assert r["verdict"] == "fail"


def test_all_claude_run_never_consults_the_dispatch_tally():
    # spend_partial False -> the tally seam is never called and the gate is skipped.
    calls = []
    d = _deps(engine_dispatch_tally=lambda: calls.append(1) or {"unreadable": True})
    r = run.invoke(d)
    assert r["verdict"] == "pass" and calls == []


def test_real_dispatch_tally_reader_flows_through_invoke_0_11_0_shape_fails(tmp_path):
    # #310 review test-002: the run-level tests inject the tally seam and the real-reader test
    # stops at decide(); neither flows the PRODUCTION real_engine_dispatch_tally through
    # run.invoke's wiring (external_calibration derivation -> tally read -> verdict). Wire the
    # REAL reader over a REAL journal written in the 0.11.0 all-failed shape and assert invoke
    # FAILs end-to-end — no injected tally seam on the dispatch leg.
    import control_plane
    import journal
    root = str(tmp_path / "checkout")
    os.makedirs(root)
    wi = "accept-harness-invoke-90fea45e"
    events = control_plane.paths(root, wi)["events"]
    journal.append(events, "external_dispatch", root=root,
                   payload={"engine": "cursor", "roleKind": "build", "outcome": "commit-failed"})
    for _ in range(8):
        journal.append(events, "external_dispatch", root=root,
                       payload={"engine": "codex", "roleKind": "review", "outcome": "unreadable"})

    d = _deps(
        launcher=lambda stamped, budget_consumed=None, attempt=1: {
            "outcome": "exited", "terminal_location": "/t.json", "spend_partial": True,
            "spend": 1.25, "elapsed_sec": 42.0},
        engine_dispatch_tally=real_deps.real_engine_dispatch_tally(root, lambda: wi))
    r = run.invoke(d)
    assert r["verdict"] == "fail"
    assert "codex 0/8" in d["_state"]["records_written"][0]["reason"]
