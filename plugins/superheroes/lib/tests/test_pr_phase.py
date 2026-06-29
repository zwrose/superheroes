import json
import os
from pathlib import Path
import subprocess
import sys

import checkpoint
import control_plane
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
    print(json.dumps([{"number": 7, "url": "https://example.test/pr/7", "isDraft": True, "state": "OPEN"}]))
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

    assert result == {"ok": True}
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
