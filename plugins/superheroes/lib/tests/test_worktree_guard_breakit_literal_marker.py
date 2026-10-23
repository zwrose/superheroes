from pathlib import Path

import mode_registry
import worktree_guard as wg
from test_worktree_guard_merge import _git, _init_repo


def test_ordinary_marker_like_content_edit_denies_checkout(tmp_path, monkeypatch):
    # Exercise the engaged guard; calibration discovery is outside this test.
    monkeypatch.setattr(mode_registry, "calibration_state", lambda cwd: "calibrated")
    repo = _init_repo(tmp_path / "repo")
    target = Path(repo) / "f.txt"
    tail = "".join(f"unchanged context {i}\n" for i in range(12))
    tail += "||||||| original-example\n"

    def commit_version(first_line, message):
        target.write_text(first_line + "\n" + tail, encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", message)

    commit_version("base", "base")
    _git(repo, "checkout", "-q", "-b", "feature")
    commit_version("feature", "feature")
    _git(repo, "checkout", "-q", "main")
    (Path(repo) / "other.txt").write_text("main change\n", encoding="utf-8")
    commit_version("main", "main")
    _git(repo, "checkout", "-q", "feature")
    merged = _git(repo, "merge", "--no-edit", "main", check=False)
    assert merged.returncode == 1, merged.stdout + merged.stderr

    command = "git checkout --theirs f.txt"
    assert wg.classify(command, repo) == ("allow", "")
    original = target.read_bytes()
    assert original.count(b"||||||| original-example\n") == 1
    edited = original.replace(
        b"||||||| original-example\n", b"||||||| OWNER-ONLY-DRAFT\n"
    )
    target.write_bytes(edited)

    # axis: editing ordinary marker-like content after the merge must deny checkout.
    decision, reason = wg.classify(command, repo)
    _git(repo, "checkout", "--theirs", "f.txt")
    assert b"OWNER-ONLY-DRAFT" not in target.read_bytes()
    assert decision == "deny", reason
