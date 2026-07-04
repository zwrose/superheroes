import json
import os
from pathlib import Path
import subprocess
import sys

import checkpoint
import control_plane
import pr_entry
import pr_phase
import test_pilot_status


def test_already_ready_pr_skips_flip():
    # world-read says the PR is already non-draft -> idempotent skip
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": False}) == "skip"


def test_draft_pr_flips():
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": True}) == "flip"


def test_unreadable_pr_gates():
    assert pr_phase.mark_ready_action("unknown") == "gate"
    assert pr_phase.mark_ready_action({"number": 7}) == "gate"            # missing isDraft -> don't guess
    assert pr_phase.mark_ready_action({"number": 7, "isDraft": None}) == "gate"  # null isDraft -> don't guess


def test_status_guard_blocks_mark_ready_when_not_ok():
    decision = pr_phase.mark_ready_status_action({"ok": False, "reason": "test-pilot stale"})
    assert decision == {"action": "gate", "reason": "test-pilot stale"}


def test_status_guard_allows_mark_ready_when_ok():
    assert pr_phase.mark_ready_status_action({"ok": True}) == {"action": "proceed"}


def test_status_guard_gates_malformed_result():
    decision = pr_phase.mark_ready_status_action("oops")
    assert decision["action"] == "gate"
    assert "test-pilot status" in decision["reason"]


def _init_mark_ready_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-b", "codex/issue-90"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"], check=True)
    paths = control_plane.paths(str(repo), "issue-90", root=str(tmp_path / "store"))
    checkpoint.write(paths["checkpoint"], checkpoint.new("issue-90", "codex/issue-90"))
    return repo, paths


def _fake_gh(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    gh = bindir / "gh"
    gh.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

if sys.argv[1:3] == ["pr", "list"]:
    ready = os.path.exists(os.environ.get("READY_MARKER", ""))
    print(json.dumps([{"number": 7, "url": "https://example.test/pr/7", "isDraft": not ready, "state": "OPEN"}]))
    raise SystemExit(0)
if sys.argv[1:3] == ["pr", "ready"]:
    with open(os.environ["READY_MARKER"], "a", encoding="utf-8") as fh:
        fh.write(sys.argv[-1] + "\\n")
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return bindir


def _run_mark_ready(repo, tmp_path):
    marker = tmp_path / "ready-called.txt"
    env = os.environ.copy()
    env["WORKHORSE_STORE_ROOT"] = str(tmp_path / "store")
    env["READY_MARKER"] = str(marker)
    env["PATH"] = "%s%s%s" % (_fake_gh(tmp_path), os.pathsep, env["PATH"])
    script = Path(__file__).resolve().parents[1] / "pr_entry.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--step", "mark-ready", "--work-item", "issue-90"],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout), marker


def test_mark_ready_entrypoint_blocks_without_current_test_pilot_status(tmp_path):
    repo, _paths = _init_mark_ready_repo(tmp_path)

    result, marker = _run_mark_ready(repo, tmp_path)

    assert result["ok"] is False
    assert "test-pilot" in result["reason"]
    assert not marker.exists()


def test_mark_ready_entrypoint_flips_after_current_test_pilot_status(tmp_path):
    repo, _paths = _init_mark_ready_repo(tmp_path)
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "codex/issue-90"], text=True).strip()
    test_pilot_status.write(
        test_pilot_status.status_path(str(repo), "issue-90", root=str(tmp_path / "store")),
        {
            "verdict": "not_applicable",
            "head": head,
            "branch": "codex/issue-90",
            "rationale": "docs-only change",
        },
    )

    result, marker = _run_mark_ready(repo, tmp_path)

    assert result == {"ok": True, "read_back": True}
    assert marker.read_text(encoding="utf-8") == "7\n"


# ---------------------------------------------------------------------------
# Configurable base branch (--base) tests for pr_entry.py
# ---------------------------------------------------------------------------

def _make_pr_create_capture_gh(tmp_path):
    """A fake `gh` that records the full argv to a file on `pr create`, and
    returns a PR-list (for emit-world) and pr-view JSON as needed."""
    bindir = tmp_path / "bin2"
    bindir.mkdir()
    gh = bindir / "gh"
    capture_file = tmp_path / "gh-create-args.txt"
    gh.write_text(
        f"""#!/usr/bin/env python3
import json, os, sys
capture = {str(capture_file)!r}
argv = sys.argv[1:]
if argv[:2] == ["pr", "list"]:
    # No open PR exists yet (emit-world returns None -> 'create').
    print(json.dumps([]))
    raise SystemExit(0)
if argv[:2] == ["pr", "create"]:
    with open(capture, "w") as fh:
        fh.write("\\n".join(argv) + "\\n")
    # Emit the created-PR JSON so the read-back succeeds.
    print(json.dumps([{{"number": 42, "url": "https://example.test/pr/42", "isDraft": True, "state": "OPEN"}}]))
    raise SystemExit(0)
raise SystemExit(2)
""",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return bindir, capture_file


def _make_draft_pr_env(tmp_path, repo, branch, extra_args=None):
    """Set up a draft-PR run environment with provenance + checkpoint wired."""
    # Import pure library modules only (not CLIs that parse args at module level).
    import ship_gate
    import checkpoint as ckpt_lib, control_plane as cp_lib

    env = os.environ.copy()
    store = tmp_path / "store"
    env["WORKHORSE_STORE_ROOT"] = str(store)
    paths = cp_lib.paths(str(repo), "wi-base", root=str(store))
    ckpt_lib.write(paths["checkpoint"], ckpt_lib.new("wi-base", branch))
    # Write build + review provenance so ship_gate.decide proceeds.
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", branch], text=True).strip()
    ship_gate.write_build(paths["provenance"], engine="subagent-driven-development", head=head)
    ship_gate.set_review_covers(paths["provenance"], head)
    # Write a clean review_result so ship_gate.decide sees exit_clean (write JSON directly).
    import json as _json
    review_path = paths["review_result"]
    os.makedirs(os.path.dirname(review_path), exist_ok=True)
    with open(review_path, "w", encoding="utf-8") as fh:
        _json.dump({"action": "exit_clean"}, fh)
    return env, paths


def _run_pr_entry_draft(repo, tmp_path, branch, extra_args=None):
    """Run pr_entry.py --step draft in a bare repo with a wired environment."""
    env, _paths = _make_draft_pr_env(tmp_path, repo, branch)
    bindir, capture = _make_pr_create_capture_gh(tmp_path)
    env["PATH"] = "%s%s%s" % (str(bindir), os.pathsep, env["PATH"])
    script = Path(__file__).resolve().parents[1] / "pr_entry.py"
    cmd = [sys.executable, str(script), "--step", "draft", "--work-item", "wi-base"]
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, cwd=str(repo), env=env,
                          capture_output=True, text=True)
    return proc, capture


def _make_bare_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "init"], check=True)
    subprocess.run(["git", "-C", str(repo), "checkout", "-b", "feature/wi-base"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "feat"], check=True)
    # A local bare origin so pr_entry's pre-create `git push origin <branch>` (the ordering-hole
    # fix) succeeds — the branch must exist on the remote before `gh pr create --head`.
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(origin)], check=True)
    return repo


def test_pr_entry_draft_omits_base_arg_when_unset(tmp_path):
    """When --base is absent, gh pr create must NOT receive --base (default behavior)."""
    repo = _make_bare_repo(tmp_path)
    proc, capture = _run_pr_entry_draft(repo, tmp_path, "feature/wi-base")
    # May gate (ship_gate) because test infra doesn't wire full review result;
    # what matters is that IF gh pr create ran, --base was NOT passed.
    if capture.exists():
        args_text = capture.read_text(encoding="utf-8")
        assert "--base" not in args_text, "no --base arg expected when base is unset"


def test_pr_entry_draft_uses_fill_first_not_bare_fill(tmp_path):
    """gh pr create must use --fill-first (conventional title from the first commit), not bare
    --fill (which uses the branch NAME as the title and fails a conventional-title CI check)."""
    repo = _make_bare_repo(tmp_path)
    proc, capture = _run_pr_entry_draft(repo, tmp_path, "feature/wi-base")
    # _make_draft_pr_env wires provenance + review_result so ship_gate.decide proceeds and gh pr create
    # MUST run — assert the capture exists so this test cannot pass vacuously (the gh argv is recorded).
    assert capture.exists(), f"gh pr create did not run (ship gate?) — proc: {proc.stdout}\n{proc.stderr}"
    args = capture.read_text(encoding="utf-8").splitlines()  # the fake gh writes one argv per line
    assert "--fill-first" in args, "draft PR must use --fill-first for a conventional-commit title"
    assert "--fill" not in args, "draft PR must NOT use bare --fill (yields the branch name as title)"


def test_pr_entry_draft_passes_base_arg_when_set(tmp_path):
    """When --base <branch> is supplied, gh pr create must receive --base <branch>."""
    repo = _make_bare_repo(tmp_path)
    proc, capture = _run_pr_entry_draft(repo, tmp_path, "feature/wi-base",
                                        extra_args=["--base", "live-showrunner-102"])
    if capture.exists():
        args_text = capture.read_text(encoding="utf-8")
        assert "--base" in args_text, "--base must be forwarded to gh pr create"
        assert "live-showrunner-102" in args_text, "base branch name must appear in gh pr create args"


# ---------------------------------------------------------------------------
# Push the build branch BEFORE draft-PR creation (ordering hole from acceptance
# run 27: review-code CERTIFIED clean, then draft-PR parked "gh pr create failed"
# because the branch lived only locally). These stub subprocess.run so the push
# rejection / timeout branches — impractical to force against a real remote — are
# exercised deterministically.
# ---------------------------------------------------------------------------

def _stub_run(scenario, calls, real_run):
    """A subprocess.run stub: fakes `gh pr *` and `git push origin <branch>` per `scenario`,
    delegating every other git call (control-plane introspection, `git rev-parse <branch>`) to
    the REAL git so the fixture repo answers them. Records each argv in `calls` for ordering."""
    def run(cmd, *args, **kwargs):
        c = list(cmd)
        calls.append(c)
        if c[:2] == ["gh", "pr"]:
            sub = c[2] if len(c) > 2 else ""
            if sub == "list":
                if scenario.get("pr_created"):
                    body = json.dumps([{"number": 77, "url": "https://ex.test/pr/77",
                                        "isDraft": True, "state": "OPEN"}])
                else:
                    body = "[]"                                  # no PR yet -> recover -> 'create'
                return subprocess.CompletedProcess(c, 0, body, "")
            if sub == "create":
                if scenario.get("create_fail"):
                    return subprocess.CompletedProcess(c, 1, "", scenario.get("create_stderr", ""))
                scenario["pr_created"] = True
                return subprocess.CompletedProcess(c, 0, "https://ex.test/pr/77\n", "")
        if c[:3] == ["git", "push", "origin"]:
            mode = scenario.get("push", "ok")
            if mode == "timeout":
                raise subprocess.TimeoutExpired(c, kwargs.get("timeout", 120))
            if mode == "reject":
                return subprocess.CompletedProcess(c, 1, "", scenario.get("push_stderr", ""))
            return subprocess.CompletedProcess(c, 0, "", "")
        return real_run(cmd, *args, **kwargs)
    return run


def _run_draft_in_process(tmp_path, monkeypatch, capsys, scenario):
    """Wire a draft-ready work-item, stub subprocess.run per `scenario`, and call
    pr_entry.main(['--step','draft', ...]) in-process. Returns (parsed_output, calls)."""
    import ship_gate
    repo = _make_bare_repo(tmp_path)
    branch = "feature/wi-base"
    monkeypatch.chdir(repo)
    monkeypatch.delenv("SUPERHEROES_STORE_ROOT", raising=False)
    store = tmp_path / "store"
    monkeypatch.setenv("WORKHORSE_STORE_ROOT", str(store))
    root = os.getcwd()                                            # == pr_entry's os.getcwd()
    paths = control_plane.paths(root, "wi-base", root=str(store))
    checkpoint.write(paths["checkpoint"], checkpoint.new("wi-base", branch))
    head = subprocess.check_output(["git", "rev-parse", branch], text=True).strip()
    ship_gate.write_build(paths["provenance"], engine="subagent-driven-development", head=head)
    ship_gate.set_review_covers(paths["provenance"], head)
    os.makedirs(os.path.dirname(paths["review_result"]), exist_ok=True)
    with open(paths["review_result"], "w", encoding="utf-8") as fh:
        json.dump({"action": "exit_clean"}, fh)                   # ship_gate.decide -> proceed
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(subprocess, "run", _stub_run(scenario, calls, real_run))
    try:
        pr_entry.main(["--step", "draft", "--work-item", "wi-base"])
    except SystemExit:
        pass
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return out, calls


def _index(calls, prefix):
    for i, c in enumerate(calls):
        if c[:len(prefix)] == prefix:
            return i
    return -1


def test_draft_pushes_branch_before_pr_create(tmp_path, monkeypatch, capsys):
    """(a) The draft step pushes the branch BEFORE `gh pr create`, then proceeds on success."""
    out, calls = _run_draft_in_process(tmp_path, monkeypatch, capsys, {"push": "ok"})
    push_i = _index(calls, ["git", "push", "origin"])
    create_i = _index(calls, ["gh", "pr", "create"])
    assert push_i != -1, "the draft step must push the branch"
    assert create_i != -1, "gh pr create must run after a successful push"
    assert push_i < create_i, "the push must happen BEFORE gh pr create"
    assert out == {"ok": True, "pr": {"number": 77, "url": "https://ex.test/pr/77",
                                      "isDraft": True, "state": "OPEN"}, "read_back": True}


def test_draft_push_rejection_parks_with_stderr_and_skips_create(tmp_path, monkeypatch, capsys):
    """(b) A push rejection parks with the stderr tail in the reason; gh pr create is NOT invoked."""
    marker = "! [rejected] feature/wi-base -> feature/wi-base (fetch first)"
    out, calls = _run_draft_in_process(
        tmp_path, monkeypatch, capsys, {"push": "reject", "push_stderr": marker})
    assert out["ok"] is False
    assert out["read_back"] is False
    assert out["reason"].startswith("branch push failed before PR create:")
    assert "rejected" in out["reason"], "the gh/git stderr tail must appear in the park reason"
    assert _index(calls, ["gh", "pr", "create"]) == -1, "must NOT create a PR after a failed push"


def test_draft_push_timeout_parks_with_own_reason(tmp_path, monkeypatch, capsys):
    """(c) A push timeout parks with its own reason (no PR exists — 'adopt on resume' does not apply)."""
    out, calls = _run_draft_in_process(tmp_path, monkeypatch, capsys, {"push": "timeout"})
    assert out["ok"] is False
    assert out["read_back"] is False
    assert out["reason"] == "branch push timed out before PR create"
    assert "adopt on resume" not in out["reason"]
    assert _index(calls, ["gh", "pr", "create"]) == -1, "must NOT create a PR after a push timeout"


def test_draft_create_failure_park_carries_stderr_tail(tmp_path, monkeypatch, capsys):
    """(d) A `gh pr create` failure park reason now carries a bounded tail of gh's stderr."""
    marker = "pull request create failed: GraphQL: was submitted too quickly"
    out, calls = _run_draft_in_process(
        tmp_path, monkeypatch, capsys, {"push": "ok", "create_fail": True, "create_stderr": marker})
    assert out["ok"] is False
    assert out["reason"].startswith("gh pr create failed:")
    assert "too quickly" in out["reason"], "gh stderr tail must be surfaced for diagnosis"
    assert _index(calls, ["git", "push", "origin"]) != -1, "the push still ran before the failed create"


# --- push_branch unit tests (pure; inject a fake `run`) --------------------

def test_push_branch_success_returns_none():
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 0, "", "")
    assert pr_entry.push_branch("feature/x", run=run) is None


def test_push_branch_rejection_returns_bounded_stderr_tail():
    long_stderr = "A" * 1000 + "REJECTED_TAIL_MARKER"
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, "", long_stderr)
    reason = pr_entry.push_branch("feature/x", run=run)
    assert reason.startswith("branch push failed before PR create:")
    assert "REJECTED_TAIL_MARKER" in reason, "the tail (not the head) of stderr must survive"
    assert "A" * 400 not in reason, "stderr must be bounded (~300 chars), not the full 1000"


def test_push_branch_timeout_returns_plain_reason():
    def run(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, kw.get("timeout", 120))
    assert pr_entry.push_branch("feature/x", run=run) == "branch push timed out before PR create"
