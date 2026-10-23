from pathlib import Path

import worktree_guard as wg
from test_worktree_guard_merge import _git, _merge_repo


def test_ident_hidden_owner_edit_denies_restore(tmp_path, monkeypatch):
    # Exercise an engaged guard; calibration discovery is outside this test.
    repo = _merge_repo(tmp_path, monkeypatch)
    target = Path(repo) / "a.txt"
    attributes = Path(repo) / ".gitattributes"
    attributes.write_text("a.txt ident\n", encoding="utf-8")
    target.write_bytes(b"main a.txt\n$Id$\n")
    _git(repo, "add", ".gitattributes", "a.txt")
    assert _git(repo, "show", ":a.txt").stdout == "main a.txt\n$Id$\n"

    target.write_bytes(b"main a.txt\n$Id: OWNER_ONLY_DRAFT $\n")
    normalized = _git(
        repo, "diff", "--no-ext-diff", "--no-textconv", "--quiet",
        "--", "a.txt", check=False,
    )
    assert normalized.returncode == 0, normalized.stderr
    assert b"OWNER_ONLY_DRAFT" in target.read_bytes()

    # axis: raw owner text hidden by ident normalization must deny destructive restore.
    decision, reason = wg.classify("git restore --source=main a.txt", repo)
    _git(repo, "restore", "--source=main", "a.txt")
    assert b"OWNER_ONLY_DRAFT" not in target.read_bytes()
    assert decision == "deny", reason
