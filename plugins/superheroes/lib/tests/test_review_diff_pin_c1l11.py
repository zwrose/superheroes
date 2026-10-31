"""Tests for the review diff's pinned shape (C1-L11): one argv, so no user git setting reaches the counter.

Every test builds a real throwaway repo with its own config pinned (no global or system config) and sets the
hostile settings (copy detection, zero context, no prefixes) in that repo's own config.
"""
import os
import re
import subprocess

import pytest

import countable_lines
import review_base_guard as rbg
import review_diff_bytes

_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
_SKILL = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "review-code", "SKILL.md"
)


@pytest.fixture(autouse=True)
def _pin_git_for_the_module(monkeypatch, tmp_path):
    # The producer under test inherits this process's environment, so the pin is set on the process.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *_IDENTITY, *args],
        capture_output=True, text=True, check=True,
    ).stdout


def _hostile_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    _git(root, "config", "diff.renames", "copies")
    _git(root, "config", "diff.context", "0")
    _git(root, "config", "diff.noprefix", "true")
    return root


def _write(root, rel, text):
    (root / rel).write_text(text, encoding="utf-8")


def _commit(root, message):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD").strip()


def _lines(prefix, n):
    return "".join("%s%d\n" % (prefix, i) for i in range(1, n + 1))


def _pinned_diff(root, base):
    head = _git(root, "rev-parse", "HEAD").strip()
    proc = review_diff_bytes.run_git_diff_three_dot(str(root), base, head, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8")


def _plain_diff(root, base):
    return _git(root, "diff", base + "...HEAD")


def _rows(result):
    return {row["file"]: row for row in result["files"]}


def _copy_of_a(tmp_path, extra="", modify_a=True):
    """Base: a.txt of 30 lines. Head: b.txt is a.txt plus ``extra``, and a.txt is edited (a copy source)."""
    root = _hostile_repo(tmp_path)
    _write(root, "a.txt", _lines("line", 30))
    base = _commit(root, "base")
    _write(root, "b.txt", _lines("line", 30) + extra)
    if modify_a:
        _write(root, "a.txt", _lines("line", 29) + "changed\n")
    _commit(root, "copy")
    return root, base


def test_t1_a_copy_is_a_new_file_and_its_lines_are_counted(tmp_path):
    root, base = _copy_of_a(tmp_path, extra="appended\n")
    # the hostile config does produce a copy section from a plain diff
    assert "copy from a.txt" in _plain_diff(root, base)
    diff = _pinned_diff(root, base)
    assert "copy from" not in diff and "copy to" not in diff
    assert "new file mode 100644" in diff.split("diff --git a/b.txt b/b.txt")[1]
    result = countable_lines.count(diff, str(root))
    row = _rows(result)["b.txt"]
    assert row["counted"] is True and row["lines"] == 31 and row["why"] is None
    assert result["unsettled"] == []


def test_t2_shape1_an_edited_copy_whose_edit_equals_a_deleted_file_is_counted(tmp_path):
    root = _hostile_repo(tmp_path)
    _write(root, "a.txt", _lines("line", 30))
    _write(root, "d.txt", "x1\nx2\nx3\n")
    base = _commit(root, "base")
    (root / "d.txt").unlink()
    _write(root, "b.txt", _lines("line", 30) + "x1\nx2\nx3\n")
    _write(root, "a.txt", _lines("line", 29) + "changed\n")
    _commit(root, "copy with an edit equal to a deleted file")
    diff = _pinned_diff(root, base)
    assert "copy from" not in diff
    result = countable_lines.count(diff, str(root))
    rows = _rows(result)
    assert rows["b.txt"]["counted"] is True and rows["b.txt"]["lines"] == 33
    assert rows["b.txt"]["why"] is None
    assert rows["d.txt"]["why"] == "deleted-whole"


def test_t2_shape2_deleting_a_files_last_lines_leaves_nothing_unread(tmp_path):
    root = _hostile_repo(tmp_path)
    _write(root, "f.txt", _lines("line", 20))
    base = _commit(root, "base")
    _write(root, "f.txt", _lines("line", 17))
    _commit(root, "drop the last three lines")
    diff = _pinned_diff(root, base)
    head_lines = 17
    # Base 20 lines, head 17: the diff is one hunk "@@ -15,6 +15,3 @@" (three context lines 15-17, then lines 18-20
    # removed). A deletion sits where it was removed (head line 18) but never past the hunk's last head line
    # (15 + 3 - 1 = 17), so all three removed lines are placed at head line 17.
    expected = [{"file": "f.txt", "lines": [[17, 17]]}]
    assert countable_lines.changed_parts(diff) == expected
    assert countable_lines.unread_surface(diff, []) == expected
    assert countable_lines.unread_surface(diff, [[{"file": "f.txt", "lines": [[1, head_lines]]}]]) == []
    # no changed line is placed past the head file
    assert all(end <= head_lines for part in countable_lines.changed_parts(diff) for _, end in part["lines"])


def test_t2_shape3_a_tail_deletion_beside_an_earlier_edit_leaves_nothing_unread(tmp_path):
    root = _hostile_repo(tmp_path)
    _write(root, "f.txt", _lines("line", 40))
    base = _commit(root, "base")
    _write(root, "f.txt", "edited\n" + _lines("line", 38)[len("line1\n"):])
    _commit(root, "edit the first line and drop the last two lines")
    diff = _pinned_diff(root, base)
    head_lines = 38
    # Base 40 lines, head 38 (the first line replaced, lines 39-40 dropped): two hunks. "@@ -1,4 +1,4 @@" replaces
    # line 1 (the removed line and the added line both sit at head line 1). "@@ -36,5 +36,3 @@" holds context
    # lines 36-38 and the two removed lines; their place would be head line 39, but the hunk's last head line is
    # 36 + 3 - 1 = 38, so both sit at 38.
    expected = [{"file": "f.txt", "lines": [[1, 1], [38, 38]]}]
    assert countable_lines.changed_parts(diff) == expected
    assert countable_lines.unread_surface(diff, []) == expected
    assert countable_lines.unread_surface(diff, [[{"file": "f.txt", "lines": [[1, head_lines]]}]]) == []
    assert all(end <= head_lines for part in countable_lines.changed_parts(diff) for _, end in part["lines"])


def test_t2_shape4_a_copy_the_proof_does_not_cover_is_among_the_changed_parts(tmp_path):
    root, base = _copy_of_a(tmp_path)
    assert "copy from a.txt" in _plain_diff(root, base)
    diff = _pinned_diff(root, base)
    parts = {part["file"]: part["lines"] for part in countable_lines.changed_parts(diff)}
    assert parts["b.txt"] == [[1, 30]]
    unread = {part["file"]: part["lines"] for part in countable_lines.unread_surface(diff, [])}
    assert unread["b.txt"] == [[1, 30]]


def test_t4_a_delete_plus_add_of_equal_size_is_not_a_move(tmp_path):
    root = _hostile_repo(tmp_path)
    _write(root, "old.txt", _lines("old", 5))
    base = _commit(root, "base")
    (root / "old.txt").unlink()
    _write(root, "new.txt", _lines("new", 5))
    _commit(root, "delete old, add new")
    diff = _pinned_diff(root, base)
    assert "rename from" not in diff
    result = countable_lines.count(diff, str(root))
    rows = _rows(result)
    # the counter excludes a file deleted whole, so the five lines of new.txt are the countable ones
    assert rows["new.txt"]["counted"] is True and rows["new.txt"]["lines"] == 5
    assert rows["new.txt"]["why"] is None
    assert rows["old.txt"]["lines"] == 5 and rows["old.txt"]["why"] == "deleted-whole"
    assert result["countable"] == 5
    assert "moved-unchanged" not in {row["why"] for row in result["files"]}


def test_t5_the_numstat_check_agrees_with_the_pinned_producer(tmp_path):
    root, base = _copy_of_a(tmp_path, extra="appended\n")
    diff = _pinned_diff(root, base)
    stats, per_file_ok, added, deleted = rbg._expected_diff_stats(base, str(root), None)
    act_stats, headers_ok, act_added, act_deleted = rbg._artifact_diff_stats(diff)
    assert per_file_ok and headers_ok
    assert stats == act_stats and set(stats) == {"a.txt", "b.txt"}
    assert stats["b.txt"] == (31, 0)
    assert (added, deleted) == (act_added, act_deleted)
    assert rbg.check_diff_binding(diff, base, str(root)) == {"ok": True, "binding": "file-set+line-counts"}


def test_t6_the_skill_command_is_the_constant():
    with open(_SKILL, encoding="utf-8") as handle:
        text = handle.read()
    fences = re.findall(r"```bash\n(.*?)```", text, flags=re.DOTALL)
    fence = next(block for block in fences if "diff.txt.tmp" in block)
    expected = 'git diff ' + " ".join(review_diff_bytes.REVIEW_DIFF_ARGS) + ' "$BASE_REF"...HEAD'
    assert fence.startswith(expected + " > ")


def test_the_constants_are_exactly_the_ordered_shape():
    assert review_diff_bytes.REVIEW_DIFF_ARGS == (
        "--no-ext-diff", "--no-textconv", "--no-color", "-M", "-U3", "--src-prefix=a/", "--dst-prefix=b/",
    )
    assert review_diff_bytes.REVIEW_NUMSTAT_ARGS == ("--no-ext-diff", "--no-textconv", "-M")
