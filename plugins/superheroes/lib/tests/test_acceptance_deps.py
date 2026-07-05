# plugins/superheroes/lib/tests/test_acceptance_deps.py
#
# Covers two review findings against acceptance_deps.py:
#
# test-001: `_lease_liveness` (the UFR-4 fail-closed tri-state safety classifier feeding
# `real_reclaim_probe` -> `acceptance_reclaim.decide`) had zero test coverage. Pins each
# branch, including the two fail-open mutants the finding calls out by name: a foreign-host
# lease must NEVER report "dead" (only "unconfirmable"), and a PermissionError from os.kill
# must report "unconfirmable", not "alive" or "dead".
#
# architecture-reviewer (real_run_outcome field mismatch): `real_run_outcome` must read the
# actual `run_readout.run_outcome` projection's field names (`status`/`checks`/`reason`/
# `prUrl`/`phasesTraversed`), not invented ones (`terminal`/`checksGreen`/`failureKind`) that
# the real showrunner projection never emits. Pins that a genuinely-green run-outcome record
# projects to a `terminal: "ready"` / `readout_claimed_checks_green: True` fact set — the
# exact shape `acceptance_verdict.decide` needs to compute a pass.
import os
import socket
import sys
import tempfile
import shutil
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import acceptance_deps as deps
import acceptance_result
import acceptance_retry
import hostinfo
import control_plane
import journal


# --- _lease_liveness -------------------------------------------------------------------


def test_liveness_unconfirmable_when_lease_is_not_a_dict_or_missing():
    assert deps._lease_liveness(None) == "unconfirmable"
    assert deps._lease_liveness("not-a-dict") == "unconfirmable"
    assert deps._lease_liveness({}) == "unconfirmable"


def test_liveness_unconfirmable_when_no_pid_recorded():
    assert deps._lease_liveness({"host": socket.gethostname()}) == "unconfirmable"


def test_liveness_foreign_host_is_unconfirmable_never_dead(monkeypatch):
    # This is the mutant the finding calls out: flipping this branch to "dead" would let
    # the harness reclaim and trample a genuinely-alive run on another host.
    lease = {"pid": 123, "host": "some-other-host-xyz"}
    monkeypatch.setattr(socket, "gethostname", lambda: "this-host")
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_liveness_dead_when_boot_id_differs():
    lease = {"pid": 123, "host": socket.gethostname(), "bootId": "boot-A"}
    import hostinfo as hi
    orig = hi.boot_id
    hi.boot_id = lambda: "boot-B"
    try:
        assert deps._lease_liveness(lease) == "dead"
    finally:
        hi.boot_id = orig


def test_liveness_alive_when_pid_signalable(monkeypatch):
    lease = {"pid": os.getpid(), "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "alive"


def test_liveness_dead_when_pid_lookup_error(monkeypatch):
    def fake_kill(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(os, "kill", fake_kill)
    lease = {"pid": 99999999, "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "dead"


def test_liveness_unconfirmable_on_permission_error_never_alive_or_dead(monkeypatch):
    # The other fail-open mutant the finding calls out: dropping the PermissionError
    # handling would let an unsignalable-but-possibly-alive pid be misjudged.
    def fake_kill(pid, sig):
        raise PermissionError()
    monkeypatch.setattr(os, "kill", fake_kill)
    lease = {"pid": 1, "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_liveness_unconfirmable_on_malformed_pid(monkeypatch):
    lease = {"pid": "not-an-int", "host": socket.gethostname(), "bootId": None}
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_quarantined_lease_is_unconfirmable(tmp_path):
    root = str(tmp_path)
    deps.real_quarantine_lease(root)("accept-harness-unsafe")

    lease = deps._read_lease(root)

    assert lease["stamp"] == "accept-harness-unsafe"
    assert lease["reason"] == "kill-unconfirmed"
    assert deps._lease_liveness(lease) == "unconfirmable"


def test_record_belongs_to_stamp_does_not_accept_unstamped_refusal_record():
    assert deps._record_belongs_to_stamp({"attempts": []}, "old-run") is False
    assert deps._record_belongs_to_stamp({"run_stamp": "old-run", "attempts": []},
                                         "old-run") is True
    assert deps._record_belongs_to_stamp({"attempts": [{"stamp": "old-run"}]},
                                         "old-run") is True


# --- real_run_outcome --------------------------------------------------------------------


def _write_json(path, obj):
    import json
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


def test_real_run_outcome_reads_the_actual_run_readout_projection_shape():
    """A genuinely green run_readout.run_outcome() record must project to facts that
    acceptance_verdict.decide can pass — not the harness's invented (wrong) field names."""
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "ready",
            "phase": "ship",
            "reason": "merge-ready",
            "prUrl": "https://github.com/o/r/pull/9",
            "checks": "green",
            "phasesTraversed": ["plan", "tasks", "build", "review", "ship"],
            "readoutPath": "/some/readout.md",
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)

        read = deps.real_run_outcome("root")
        out = read(path)

        assert out["terminal"] == "ready"
        assert out["phases"] == ["plan", "tasks", "build", "review", "ship"]
        assert out["readout_pr_link"] == "https://github.com/o/r/pull/9"
        assert out["readout_claimed_checks_green"] is True
        assert out["readout_claimed_pr"] == "https://github.com/o/r/pull/9"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_derives_phases_from_durable_journal_not_terminal_json(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    events = control_plane.paths(str(repo), "accept-harness-abc")["events"]
    journal.append(events, "phase_record", payload={"phase": "plan"}, root=str(repo))
    journal.append(events, "phase_record", payload={"phase": "review-plan"}, root=str(repo))
    journal.append(events, "run_completed", detail="done", root=str(repo))
    terminal = tmp_path / "terminal-record.json"
    terminal.write_text(json.dumps({
        "status": "ready",
        "phase": "ship",
        "reason": "merge-ready",
        "prUrl": "https://github.com/o/r/pull/9",
        "checks": "green",
        "phasesTraversed": ["made-up-by-the-child"],
    }), encoding="utf-8")

    out = deps.real_run_outcome(str(repo), lambda: "accept-harness-abc")(str(terminal))

    assert out["phases"] == ["plan", "review-plan", "ship"]


def test_real_run_outcome_no_required_checks_is_not_claimed_green():
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "ready", "prUrl": "https://x/pr/1", "checks": "none",
            "phasesTraversed": ["plan"],
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)
        out = deps.real_run_outcome("root")(path)
        assert out["readout_claimed_checks_green"] is False
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_parked_state_projects_to_non_ready_terminal():
    d = tempfile.mkdtemp()
    try:
        record = {
            "status": "parked", "reason": "ceiling breached", "checks": "none",
            "phasesTraversed": ["plan"],
        }
        path = os.path.join(d, "terminal-record.json")
        _write_json(path, record)
        out = deps.real_run_outcome("root")(path)
        assert out["terminal"] == "parked"
        assert out["failure_kind"] == "ceiling breached"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_real_run_outcome_missing_file_fails_closed_to_parked_default():
    out = deps.real_run_outcome("root")("/no/such/path/terminal-record.json")
    assert out["terminal"] == "parked"
    assert out["failure_kind"] == "no-terminal-record"


def test_real_run_outcome_corrupt_json_fails_closed():
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "terminal-record.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        out = deps.real_run_outcome("root")(path)
        assert out["terminal"] == "parked"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --- real_gh_reader: PR discovery by head-branch prefix, not the synthetic pr_title ----
#
# premortem-001: the live showrunner titles its PR from the first commit's Conventional-
# Commit subject (`gh pr create --fill-first`), never `stamped["pr_title"]`, so a title
# search never reliably finds the real PR. `real_gh_reader` must instead match by the
# real build-branch prefix (`buildtree.branch_name`: `superheroes/<work_item>-<hash>`).


def test_real_gh_reader_matches_by_superheroes_branch_prefix_not_title(monkeypatch):
    calls = []

    def fake_run(args, cwd, timeout=15):
        calls.append(args)
        if args[:3] == ["gh", "pr", "list"]:
            import json as _json
            return 0, _json.dumps([
                {"number": 1, "url": "https://x/pr/1", "isDraft": False,
                 "headRefName": "superheroes/accept-harness-abc-def456",
                 "statusCheckRollup": [{"conclusion": "SUCCESS"}]},
                {"number": 2, "url": "https://x/pr/2", "isDraft": True,
                 "headRefName": "claude/unrelated-branch", "statusCheckRollup": []},
            ]), ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    read = deps.real_gh_reader("root", {"work_item": "accept-harness-abc",
                                        "pr_title": "totally different title never used"})
    result = read()
    assert result["pr_exists"] is True
    assert result["live_pr"] == "https://x/pr/1"
    assert result["checks_green"] is True
    # No --search flag naming the synthetic pr_title was ever used.
    assert not any("--search" in c for c in calls)


def test_real_gh_reader_no_matching_branch_prefix_returns_pr_not_exists(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            import json as _json
            return 0, _json.dumps([
                {"number": 9, "url": "https://x/pr/9", "isDraft": False,
                 "headRefName": "claude/unrelated-branch", "statusCheckRollup": []},
            ]), ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    read = deps.real_gh_reader("root", {"work_item": "accept-harness-abc"})
    result = read()
    assert result["pr_exists"] is False


def test_real_gh_reader_missing_work_item_is_unreadable():
    read = deps.real_gh_reader("root", {})
    result = read()
    assert result["unreadable"] == ["pr_exists"]


def test_real_gh_reader_classifies_host_unreachable_from_required_read_probe(monkeypatch):
    import gh_preflight

    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 1, "", "network down"
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    monkeypatch.setattr(gh_preflight, "probe", lambda root: {"ok": False})

    def fake_decide(probe, required="write"):
        assert required == "read"
        return (False, "indeterminate", "retry")

    monkeypatch.setattr(gh_preflight, "decide", fake_decide)

    result = deps.real_gh_reader("root", {"work_item": "accept-harness-abc"})()

    assert result["unreadable"] == ["pr_exists"]
    assert result["failure_kind"] == "host-unreachable"


def test_real_gh_reader_classifies_infra_check_runner_error(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 0, json.dumps([
                {"number": 1, "url": "https://x/pr/1", "isDraft": False,
                 "headRefName": "superheroes/accept-harness-abc-def456",
                 "statusCheckRollup": [{"conclusion": "STARTUP_FAILURE"}]},
            ]), ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    result = deps.real_gh_reader("root", {"work_item": "accept-harness-abc"})()
    assert result["failure_kind"] == "check-runner-errored-before-running"


def test_check_failure_kind_covers_all_runner_infra_shapes():
    for rollup in (
        [{"conclusion": "STARTUP_FAILURE"}],
        [{"status": "ERROR"}],
        [{"state": "ERROR"}],
    ):
        assert deps._check_failure_kind(rollup) == "check-runner-errored-before-running"


def test_check_failure_kind_keeps_behavioral_red_checks_unclassified():
    assert deps._check_failure_kind([{"conclusion": "FAILURE"}]) is None
    assert deps._check_failure_kind([{"conclusion": "CANCELLED"}]) is None
    assert deps._check_failure_kind([{"conclusion": "TIMED_OUT"}]) is None


def test_timed_out_check_does_not_trigger_environmental_retry():
    kind = deps._check_failure_kind([{"conclusion": "TIMED_OUT"}])

    retry = acceptance_retry.classify({
        "kind": kind,
        "unreadable": False,
        "attempt": 1,
    })

    assert kind is None
    assert retry["retry"] is False


def test_real_gh_reader_keeps_behavioral_red_check_non_retryable(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:3] == ["gh", "pr", "list"]:
            return 0, json.dumps([
                {"number": 1, "url": "https://x/pr/1", "isDraft": False,
                 "headRefName": "superheroes/accept-harness-abc-def456",
                 "statusCheckRollup": [{"conclusion": "FAILURE"}]},
            ]), ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    result = deps.real_gh_reader("root", {"work_item": "accept-harness-abc"})()
    assert result["checks_green"] is False
    assert result["failure_kind"] is None


def test_real_write_refusal_record_uses_sidecar_not_canonical_record(tmp_path):
    root = str(tmp_path)
    record = {
        "verdict": "fail",
        "reason": "refused",
        "pr_link": "",
        "phases": [],
        "spend": None,
        "spend_partial": True,
        "elapsed_sec": 0.0,
        "launched_at": "2026-07-02T00:00:00Z",
        "terminated_at": "2026-07-02T00:00:00Z",
        "retried": False,
        "attempts": [],
        "cleaned_up": [],
        "left_behind": [],
    }

    path = deps.real_write_refusal_record(root)(record)

    assert "/refusals/" in path
    assert acceptance_result.read_record(deps._record_dir(root)) is None
    assert acceptance_result.read_record(os.path.dirname(path))["reason"] == "refused"


def test_real_preflight_combines_fixture_drift_and_showrunner_preflight(monkeypatch, tmp_path):
    import acceptance_fixture
    import preflight

    monkeypatch.setattr(acceptance_fixture, "drift_check",
                        lambda fixture, phases, target_exists: {"ok": True, "reason": "fixture ok"})
    monkeypatch.setattr(preflight, "probe", lambda work_item, root: {"gh": {"ok": False}})
    monkeypatch.setattr(preflight, "decide", lambda probes, work_item: {
        "ok": False,
        "blocking": [{"check": "github-access", "status": "fail",
                      "remediation": "verify GitHub is reachable and retry"}],
    })
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")

    result = deps.real_preflight_ok(str(fixture), "root")("accept-harness-abc")

    assert result["ok"] is False
    assert "github-access" in result["reason"]


def test_real_preflight_refuses_when_config_does_not_resolve(monkeypatch, tmp_path):
    import acceptance_fixture
    import preflight

    monkeypatch.setattr(acceptance_fixture, "drift_check",
                        lambda fixture, phases, target_exists: {"ok": True, "reason": "fixture ok"})
    monkeypatch.setattr(preflight, "probe",
                        lambda work_item, root: {"gh": {"ok": True}, "config_resolves": False})
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")

    result = deps.real_preflight_ok(str(fixture), "root")("accept-harness-abc")

    assert result["ok"] is False
    assert "config-resolves" in result["reason"]


def test_real_preflight_returns_fixture_drift_without_running_live_probe(monkeypatch, tmp_path):
    import acceptance_fixture
    import preflight

    monkeypatch.setattr(acceptance_fixture, "drift_check",
                        lambda fixture, phases, target_exists: {
                            "ok": False, "reason": "fixture drift"})
    monkeypatch.setattr(preflight, "probe",
                        lambda work_item, root: (_ for _ in ()).throw(
                            AssertionError("live probe should not run after fixture drift")))
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")

    result = deps.real_preflight_ok(str(fixture), "root")("accept-harness-abc")

    assert result == {"ok": False, "reason": "fixture drift"}


def test_real_preflight_accepts_when_fixture_and_live_probes_pass(monkeypatch, tmp_path):
    import acceptance_fixture
    import preflight

    monkeypatch.setattr(acceptance_fixture, "drift_check",
                        lambda fixture, phases, target_exists: {"ok": True, "reason": "fixture ok"})
    monkeypatch.setattr(preflight, "probe",
                        lambda work_item, root: {"gh": {"ok": True}, "config_resolves": True})
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")

    result = deps.real_preflight_ok(str(fixture), "root")("accept-harness-abc")

    assert result["ok"] is True


def test_real_preflight_fails_closed_when_phase_source_unreadable(monkeypatch, tmp_path):
    import acceptance_phases

    monkeypatch.setattr(acceptance_phases, "read_pipeline_phases",
                        lambda: (_ for _ in ()).throw(RuntimeError("missing PHASES")))
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "target.txt").write_text("x\n", encoding="utf-8")

    result = deps.real_preflight_ok(str(fixture), "root")("accept-harness-abc")

    assert result["ok"] is False
    assert "pipeline phase source drift" in result["reason"]


def test_real_launcher_threads_owner_configured_ceilings(monkeypatch):
    captured = {}

    def fake_run(stamped, ceilings, child_factory, clock, spend_sampler, engine_pref_reader,
                 budget_consumed=None, attempt=1):
        captured["ceilings"] = ceilings
        return {"outcome": "exited", "terminal_location": "/t.json",
                "spend_partial": False, "spend": None, "elapsed_sec": 0.0}

    monkeypatch.setattr(deps.acceptance_launch, "run", fake_run)
    launch = deps.real_launcher("root", ceilings={"elapsed_sec": 7.0})
    launch({"stamp": "s1", "work_item": "accept-harness-abc"})

    assert captured["ceilings"]["elapsed_sec"] == 7.0
    assert captured["ceilings"]["spend"] == 5_000_000.0


def test_real_spend_sampler_reads_measured_token_telemetry(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    events = control_plane.paths(str(repo), "accept-harness-abc")["events"]
    journal.append(events, "phase_cost", payload={
        "phase": "workhorse",
        "dispatches": {"total": 1, "byModel": {}},
        "tokens": {"output": 123, "measured": True},
    }, root=str(repo))

    spend, readable = deps.real_spend_sampler(str(repo), lambda: "accept-harness-abc")()

    assert readable is True
    assert spend == 123.0


def test_real_spend_sampler_no_phase_cost_events_is_unreadable(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    spend, readable = deps.real_spend_sampler(str(repo), lambda: "accept-harness-abc")()

    assert spend is None
    assert readable is False


def test_real_spend_sampler_unmeasured_summary_is_unreadable(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    events = control_plane.paths(str(repo), "accept-harness-abc")["events"]
    journal.append(events, "phase_cost", payload={
        "phase": "workhorse",
        "dispatches": {"total": 1, "byModel": {}},
        "tokens": {"output": 123, "measured": True},
    }, root=str(repo))
    monkeypatch.setattr(deps.cost_report, "summarize",
                        lambda events: {"measured": False, "outputTokens": 123})

    spend, readable = deps.real_spend_sampler(str(repo), lambda: "accept-harness-abc")()

    assert spend is None
    assert readable is False

    monkeypatch.setattr(deps.cost_report, "summarize",
                        lambda events: {"measured": True, "outputTokens": None})
    spend, readable = deps.real_spend_sampler(str(repo), lambda: "accept-harness-abc")()

    assert spend is None
    assert readable is False


# --- real_discover_artifacts: real showrunner branch/PR naming ------------------------
#
# code-reviewer finding: branch discovery globbed only the harness's own legacy
# `wi-<stamp>*` naming, never the real showrunner build-branch naming
# (`superheroes/<work_item>-<hash>`), so a live run's fixture branch was never discovered
# (and never reaped). PR discovery must key off `headRefName`, not a free-text title
# search on the reserved prefix (which the showrunner's own PR title never carries).


def test_real_discover_artifacts_finds_superheroes_prefixed_branch(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:2] == ["git", "branch"] and "superheroes/*accept-harness-*" in args:
            return 0, "  superheroes/accept-harness-xyz-abc123\n", ""
        if args[:2] == ["git", "branch"]:
            return 0, "", ""
        if args[:3] == ["gh", "pr", "list"]:
            return 0, "[]", ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("root")
    artifacts = discover("accept-harness-xyz")
    branch_names = [a["name"] for a in artifacts if a["kind"] == "branch"]
    assert "superheroes/accept-harness-xyz-abc123" in branch_names


def test_real_discover_artifacts_finds_pr_by_head_ref_not_title(monkeypatch):
    def fake_run(args, cwd, timeout=15):
        if args[:2] == ["git", "branch"]:
            return 0, "", ""
        if args[:3] == ["gh", "pr", "list"]:
            import json as _json
            return 0, _json.dumps([
                {"title": "fix: unrelated conventional commit subject",
                 "headRefName": "superheroes/accept-harness-xyz-abc123"},
                {"title": "some other PR", "headRefName": "claude/unrelated"},
            ]), ""
        return 1, "", ""

    monkeypatch.setattr(deps, "_run", fake_run)
    discover = deps.real_discover_artifacts("root")
    artifacts = discover("accept-harness-xyz")
    pr_artifacts = [a for a in artifacts if a["kind"] == "pr"]
    assert len(pr_artifacts) == 1
    # The artifact's name is the head branch (embeds the stamp for parse_stamp routing),
    # not the PR's own (unrelated) title.
    assert pr_artifacts[0]["name"] == "superheroes/accept-harness-xyz-abc123"
