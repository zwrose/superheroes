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
