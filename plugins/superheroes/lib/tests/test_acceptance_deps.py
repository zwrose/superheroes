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


def test_real_run_outcome_rejects_symlink_handoff(tmp_path):
    # Security review PR #266: a symlink at the handoff path could redirect a planted
    # record into the release-gating verdict — reject it, never follow it.
    real = tmp_path / "planted.json"
    real.write_text(json.dumps({"status": "ready", "checks": "green"}), encoding="utf-8")
    link = tmp_path / "terminal-record.json"
    os.symlink(real, link)
    out = deps.real_run_outcome(str(tmp_path), lambda: None)(str(link))
    assert out["terminal"] == "parked"
    assert out["failure_kind"] == "terminal-record-symlink-rejected"


def test_real_run_outcome_unlinks_handoff_after_read(tmp_path):
    # Finding #2: the transient handoff must not linger after the parent reads it.
    rec = tmp_path / "terminal-record.json"
    rec.write_text(json.dumps({"status": "ready", "checks": "green"}), encoding="utf-8")
    out = deps.real_run_outcome(str(tmp_path), lambda: None)(str(rec))
    assert out["terminal"] == "ready"
    assert not rec.exists()


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


def test_real_launcher_terminal_path_is_non_sensitive(monkeypatch):
    # Finding #16: the child→parent handoff record must NOT live under ~/.claude (the
    # sensitive tree) — that forced the guard-evasion prompt a child correctly refused.
    import tempfile
    captured = {}

    def fake_factory(stamped, terminal_path=None, **kw):
        captured["terminal_path"] = terminal_path
        class _C:
            def terminal_location(self):
                return terminal_path
        return _C()

    def fake_run(stamped, ceilings, child_factory, *a, **kw):
        child_factory()   # trigger the factory so terminal_path is built
        return {"outcome": "exited", "terminal_location": captured["terminal_path"],
                "spend_partial": False, "spend": None, "elapsed_sec": 0.0}

    monkeypatch.setattr(deps.acceptance_launch, "_default_child_factory", fake_factory)
    monkeypatch.setattr(deps.acceptance_launch, "_set_live_child", lambda c: None)
    monkeypatch.setattr(deps.acceptance_launch, "run", fake_run)
    deps.real_launcher("/repo/root")({"stamp": "s9", "work_item": "accept-harness-z"})

    tp = captured["terminal_path"]
    assert tp.startswith(tempfile.gettempdir())
    assert ".claude" not in tp and "s9" in tp and tp.endswith("terminal-record.json")


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


# --- real_root_ancestry (issue #298) ---------------------------------------------------
#
# Refuse a --root checkout whose HEAD is not an ancestor of origin/<default-branch> (a
# release-branch checkout false-parks on UFR-7 mid-run). All git I/O flows through an
# injected run seam so every branch is driven without a real fetch.


def _ancestry_run(default_symbolic=True, head_sha="deadbeef12", fetch_rc=0,
                  ref_rc=0, is_ancestor_rc=0, recorder=None):
    """Build a fake `run(args, timeout=?) -> (rc, out, err)` for real_root_ancestry."""
    def fake_run(args, timeout=15):
        if recorder is not None:
            recorder.append(args)
        if args[:2] == ["git", "symbolic-ref"]:
            return (0, "refs/remotes/origin/main\n", "") if default_symbolic else (128, "", "no HEAD")
        if args[:3] == ["git", "rev-parse", "--verify"]:
            return (ref_rc, "aa\n" if ref_rc == 0 else "", "")
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return (0, head_sha + "\n", "")
        if args[:2] == ["git", "fetch"]:
            return (fetch_rc, "", "" if fetch_rc == 0 else "no remote")
        if args[:2] == ["git", "merge-base"]:
            return (is_ancestor_rc, "", "")
        return (1, "", "")
    return fake_run


def test_root_ancestry_ancestor_clean_proceeds():
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(is_ancestor_rc=0), warn=lambda m: None)()
    assert res["ok"] is True
    assert res["checked"] is True
    assert res["default_branch"] == "main"


def test_root_ancestry_non_ancestor_refuses_naming_sha_and_hatch():
    warned = []
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(head_sha="cafef00d99", is_ancestor_rc=1),
        warn=warned.append)()
    assert res["ok"] is False
    assert res["head_sha"] == "cafef00d99"
    # the refusal reason names the sha, the remote default, and the escape hatch + fix.
    assert "cafef00d99" in res["reason"]
    assert "origin/main" in res["reason"]
    assert "--allow-unmerged-root" in res["reason"]
    assert "--spine-lib" in res["reason"]
    assert warned == []                          # a clean refusal is not a degrade warning


def test_root_ancestry_fetch_failure_warns_and_continues():
    warned = []
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(fetch_rc=1), warn=warned.append)()
    assert res["ok"] is True                      # never a hard block for offline
    assert res["checked"] is False                # but the check did NOT actually run
    assert warned and "fetch" in warned[0].lower()  # the degrade is loud, never silent


def test_root_ancestry_unresolvable_remote_ref_warns_and_continues():
    warned = []
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(ref_rc=1), warn=warned.append)()
    assert res["ok"] is True
    assert res["checked"] is False
    assert warned                                 # loud degrade, not a silent pass


def test_root_ancestry_default_falls_back_to_main_without_symbolic_ref():
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(default_symbolic=False, is_ancestor_rc=0),
        warn=lambda m: None)()
    assert res["ok"] is True
    assert res["default_branch"] == "main"        # fell back to main when symbolic-ref failed


def test_root_ancestry_merge_base_error_degrades_not_refuses():
    warned = []
    # rc 128 (neither 0 ancestor nor 1 not-ancestor) is an error -> degrade, never a refusal.
    res = deps.real_root_ancestry(
        "/root", run=_ancestry_run(is_ancestor_rc=128), warn=warned.append)()
    assert res["ok"] is True
    assert res["checked"] is False
    assert warned


def test_root_ancestry_preserves_slash_in_default_branch_name():
    # A slash-containing default (e.g. release/stable) must survive intact — the parse strips
    # the full refs/remotes/origin/ prefix, not rsplit on the last '/'.
    seen = []

    def fake_run(args, timeout=15):
        seen.append(args)
        if args[:2] == ["git", "symbolic-ref"]:
            return (0, "refs/remotes/origin/release/stable\n", "")
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return (0, "abc123\n", "")
        if args[:3] == ["git", "rev-parse", "--verify"]:
            return (0, "x\n", "") if args[-1] == "origin/release/stable" else (1, "", "")
        if args[:2] == ["git", "fetch"]:
            return (0, "", "")
        if args[:2] == ["git", "merge-base"]:
            return (0, "", "")
        return (1, "", "")

    res = deps.real_root_ancestry("/root", run=fake_run, warn=lambda m: None)()
    assert res["ok"] is True and res["checked"] is True
    assert res["default_branch"] == "release/stable"
    # the fetch and the merge-base both used the FULL slash-containing branch, not a truncation
    # (fetch now via the explicit tracking refspec — #298 review r1, Code finding).
    assert ["git", "fetch", "origin",
            "+refs/heads/release/stable:refs/remotes/origin/release/stable"] in seen
    assert ["git", "merge-base", "--is-ancestor", "HEAD", "origin/release/stable"] in seen


def test_root_ancestry_merge_base_subprocess_failure_degrades_not_false_refusal(monkeypatch):
    # Review finding: the shared _run collapses a subprocess failure to rc 1, which is EXACTLY
    # git's merge-base "not an ancestor" code — so a merge-base timeout must not launder into a
    # false refusal. The dedicated default runner maps the failure to rc 128 instead, landing in
    # the degrade branch. Drive it with the REAL default runner (no injected `run`), forcing ONLY
    # merge-base to raise.
    import subprocess as _sp

    def selective(args, cwd=None, capture_output=None, text=None, timeout=None):
        if "merge-base" in args:
            raise _sp.TimeoutExpired(cmd=args, timeout=timeout or 1)
        out = ""
        if args[:2] == ["git", "symbolic-ref"]:
            out = "refs/remotes/origin/main\n"
        elif args[:3] == ["git", "rev-parse", "HEAD"]:
            out = "abc123\n"
        elif args[:3] == ["git", "rev-parse", "--verify"]:
            out = "def456\n"
        return _sp.CompletedProcess(args, 0, out, "")

    monkeypatch.setattr(deps.subprocess, "run", selective)
    warned = []
    res = deps.real_root_ancestry("/root", warn=warned.append)()
    assert res["ok"] is True           # a merge-base subprocess failure must NEVER refuse
    assert res["checked"] is False     # it degrades (warn + continue) instead
    assert warned


def test_root_ancestry_bypass_never_touches_git():
    def boom(args, timeout=15):
        raise AssertionError("git must not run under --allow-unmerged-root")
    res = deps.real_root_ancestry("/root", allow_unmerged_root=True, run=boom)()
    assert res["ok"] is True
    assert res.get("bypassed") is True


def test_build_wires_root_ancestry_seam(tmp_path):
    d = deps.build(str(tmp_path / "fixture"), str(tmp_path))
    assert callable(d["root_ancestry"])


# --- #298 review round 1 additions ------------------------------------------------------


def test_root_ancestry_fetch_uses_explicit_tracking_refspec():
    # r1 Code finding: a bare `git fetch origin main` updates the tracking ref only via the
    # remote's configured refspec (a narrowed/single-branch clone leaves it stale, and step 4
    # would refuse a genuinely-merged root). Pin the explicit-refspec form.
    seen = []
    deps.real_root_ancestry(
        "/root", run=_ancestry_run(recorder=seen), warn=lambda m: None)()
    fetches = [a for a in seen if a[:2] == ["git", "fetch"]]
    assert fetches == [["git", "fetch", "origin",
                        "+refs/heads/main:refs/remotes/origin/main"]]


def test_root_ancestry_refusal_recovery_command_is_paste_safe():
    # r1 Security finding: `default` derives from origin/HEAD and git ref names may carry
    # shell metacharacters — the pasteable remediation must quote it.
    evil = "main;rm -rf x"

    def fake_run(args, timeout=15):
        if args[:2] == ["git", "symbolic-ref"]:
            return (0, "refs/remotes/origin/%s\n" % evil, "")
        if args[:3] == ["git", "rev-parse", "--verify"]:
            return (0, "aa\n", "")
        if args[:3] == ["git", "rev-parse", "HEAD"]:
            return (0, "cafef00d99\n", "")
        if args[:2] == ["git", "fetch"]:
            return (0, "", "")
        if args[:2] == ["git", "merge-base"]:
            return (1, "", "")
        return (1, "", "")

    res = deps.real_root_ancestry("/root", run=fake_run, warn=lambda m: None)()
    assert res["ok"] is False
    import shlex as _shlex
    assert ("git checkout %s && git pull" % _shlex.quote(evil)) in res["reason"]
    assert "checkout main;rm" not in res["reason"]   # the raw metachar form never appears


def test_root_ancestry_fallback_names_share_one_home_with_build_state_cli():
    # r1 Architecture finding (CONVENTIONS §11): the default-branch NAME preference has ONE
    # home — build_state_cli.DEFAULT_BRANCH_FALLBACK — consumed by both the UFR-7 base
    # resolution and this gate. Pin the home and that _base still derives its historical
    # ref order from it.
    import build_state_cli as bsc
    assert bsc.DEFAULT_BRANCH_FALLBACK == ("main", "master")
    seen = []
    deps.real_root_ancestry(
        "/root", run=_ancestry_run(default_symbolic=False, ref_rc=0, recorder=seen),
        warn=lambda m: None)()
    # With origin/HEAD unset, the first candidate probed is origin/<first fallback name>.
    probes = [a for a in seen if a[:3] == ["git", "rev-parse", "--verify"]]
    assert probes and probes[0][-1] == "origin/%s" % bsc.DEFAULT_BRANCH_FALLBACK[0]


def test_build_escape_hatch_threads_to_a_bypassing_seam(tmp_path):
    # r1 Test finding: prove build(allow_unmerged_root=True) yields a seam that BYPASSES —
    # a mutant dropping the kwarg inside build() must fail here. The bypass path returns
    # before any git I/O, so this is deterministic with real deps.
    d = deps.build(str(tmp_path / "fixture"), str(tmp_path), allow_unmerged_root=True)
    res = d["root_ancestry"]()
    assert res["ok"] is True
    assert res.get("bypassed") is True
