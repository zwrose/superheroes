"""#2349: a delta round cuts the diff sections the fix did not change before it parses.

Invariant: in a delta round (round 2 or later, `_enter_delta_round`) a per-file diff section whose exact text both
the reviewed diff and the head diff hold never reaches `delta_surface.parse_hunks`; a section the fix changed always
does. So a PR whose diff holds a rename or a binary file the fix did not touch gets a scoped delta round, and a fix
that itself renames a file or changes a binary file still hands back `fix-surface-unknown`.

T1 an unchanged rename · T2 an unchanged binary · T3 the fix renames a file · T4 the fix changes a binary ·
T5 plain modified files only (the cut changes nothing on a parseable pair).

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/delta_round_unchanged_sections_2349.md
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines  # noqa: E402
import delta_surface  # noqa: E402
import review_diff_bytes  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
import test_round_driver as TRD  # noqa: E402
from test_c1l11b_returning_session import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

RD = TRD.RD

# a binary file as git reads one: it has NUL bytes. Every character is ASCII, so the text-mode fixture writer
# puts down exactly these bytes.
LOGO = "assets/logo.bin"
BIN_A = "".join(chr(i % 128) for i in range(1024))
BIN_B = BIN_A[::-1]
BIN_C = BIN_A[5:] + BIN_A[:5]

FINDING = {"title": "bug", "severity": "Important", "consequence": TRD._CONSEQUENCE, "file": "keep.py", "line": 10}


def _diff(repo, base, head):
    proc = review_diff_bytes.run_git_diff_three_dot(repo.root, base, head, timeout=60)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8")


def _set_line_10(repo, path, text):
    lines = repo.read(path).splitlines(True)
    lines[9] = text + "\n"
    repo.write(path, "".join(lines))


def _diffs(tmp_path, pr, fix):
    """``(reviewed, head)``: ``base...reviewed`` after ``pr(repo)`` and ``base...fixed`` after ``fix(repo)`` on top of it."""
    repo = TR.Repo(tmp_path)
    repo.write("keep.py", TR.numbered("keep", 30))
    repo.write("other.py", TR.numbered("other", 30))
    repo.write(LOGO, BIN_A)
    base = repo.commit("base files")
    pr(repo)
    reviewed_sha = repo.commit("the pull request")
    fix(repo)
    fixed_sha = repo.commit("the fix")
    return _diff(repo, base, reviewed_sha), _diff(repo, base, fixed_sha)


def _round_two(reviewed, head):
    cfg = TRD._cfg(diff=reviewed)
    state = RD.new_state(cfg)
    state.update(round=2, rounds={"2": {}}, decisions=[], reviewedDiff=head, headDiff=head,
                 deltaBaseline={"round": 2, "diff": reviewed}, fixBatch=[dict(FINDING)])
    RD._enter_delta_round(state, cfg)
    return state


def _section_texts(diff, file):
    return [sec["text"] for sec in countable_lines.parse_sections(diff) if sec["file"] == file]


def _premise_unchanged_unparseable(reviewed, head, file):
    """Neither diff reads in a hunk parser as it stands, and the section of ``file`` is the same in both."""
    assert delta_surface.parse_hunks(reviewed) is None and delta_surface.parse_hunks(head) is None
    assert _section_texts(reviewed, file) == _section_texts(head, file) != []


def _assert_scoped_without(state, *files):
    assert state["step"] == RD.P_AUDITS and not state.get("terminal"), state.get("decisions")
    assert not [d for d in state["decisions"] if d.get("kind") == "fix-surface-unknown"]
    assert state["rounds"]["2"]["roundKind"] == "delta"
    audited = [t["file"] for t in state["_auditTargets"]]
    assert "keep.py" in state["_newSurface"] or "keep.py" in audited
    for file in files:
        assert file not in state["_fixDeltaDiff"] and file not in str(state["_newSurface"]), file


def _assert_handed_back(state):
    assert state["terminal"] == "handed-back"
    assert state["decisions"][-1]["kind"] == "fix-surface-unknown"


def test_t1_an_unchanged_rename_beside_a_fixed_file_gets_the_scoped_delta_round(tmp_path):
    # axis: an unchanged rename section never reaches the hunk parser, so it cannot hand the PR back
    def pr(repo):
        repo.git("mv", "src/shared.py", "src/moved.py")
        _set_line_10(repo, "keep.py", "reviewed = 1")

    reviewed, head = _diffs(tmp_path, pr, lambda repo: _set_line_10(repo, "keep.py", "fixed = 1"))
    assert "rename from src/shared.py\nrename to src/moved.py\n" in reviewed
    _premise_unchanged_unparseable(reviewed, head, "src/moved.py")
    _assert_scoped_without(_round_two(reviewed, head), "shared.py", "moved.py")


def test_t2_an_unchanged_binary_beside_a_fixed_file_gets_the_scoped_delta_round(tmp_path):
    # axis: an unchanged binary section never reaches the hunk parser, so it cannot hand the PR back
    def pr(repo):
        repo.write(LOGO, BIN_B)
        _set_line_10(repo, "keep.py", "reviewed = 1")

    reviewed, head = _diffs(tmp_path, pr, lambda repo: _set_line_10(repo, "keep.py", "fixed = 1"))
    assert "Binary files" in reviewed and "Binary files" in head
    _premise_unchanged_unparseable(reviewed, head, LOGO)
    _assert_scoped_without(_round_two(reviewed, head), "logo.bin")


def test_t3_a_fix_that_renames_a_file_still_hands_the_pr_back(tmp_path):
    # axis: a rename section the fix changed (here, added) still reaches the parser and fails closed
    def fix(repo):
        repo.git("mv", "src/shared.py", "src/moved.py")
        _set_line_10(repo, "keep.py", "fixed = 1")

    reviewed, head = _diffs(tmp_path, lambda repo: _set_line_10(repo, "keep.py", "reviewed = 1"), fix)
    assert "rename to src/moved.py\n" in head and "rename to" not in reviewed
    _assert_handed_back(_round_two(reviewed, head))


def test_t4_a_fix_that_changes_a_binary_still_hands_the_pr_back(tmp_path):
    # axis: a binary section the fix changed still reaches the parser and fails closed
    def pr(repo):
        repo.write(LOGO, BIN_B)
        _set_line_10(repo, "keep.py", "reviewed = 1")

    def fix(repo):
        repo.write(LOGO, BIN_C)
        _set_line_10(repo, "keep.py", "fixed = 1")

    reviewed, head = _diffs(tmp_path, pr, fix)
    assert _section_texts(reviewed, LOGO) != _section_texts(head, LOGO)
    _assert_handed_back(_round_two(reviewed, head))


def test_t5_plain_modified_files_give_the_same_surface_as_the_uncut_pair(tmp_path):
    # axis: on a parseable pair the cut changes nothing: surface, fix delta and audit hunks equal the uncut pair's
    def pr(repo):
        _set_line_10(repo, "keep.py", "reviewed = 1")
        _set_line_10(repo, "other.py", "reviewed = 1")

    reviewed, head = _diffs(tmp_path, pr, lambda repo: _set_line_10(repo, "keep.py", "fixed = 1"))
    assert delta_surface.parse_hunks(reviewed) is not None and delta_surface.parse_hunks(head) is not None
    state = _round_two(reviewed, head)
    assert state["step"] == RD.P_AUDITS and not state.get("terminal")
    split = delta_surface.split_fix_surface(reviewed, head, [dict(FINDING)])
    assert not split.get("unknown")
    assert (state["_newSurface"], state["_fixDeltaDiff"]) == RD._fix_delta_surface(state, reviewed, head)
    [target] = state["_auditTargets"]
    assert target["fixHunks"] == RD._fix_hunks_over_line(split["auditTargets"], "keep.py", 10) != []
