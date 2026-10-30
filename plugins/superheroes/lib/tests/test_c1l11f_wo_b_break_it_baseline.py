"""C1-L11f (WO-B, collector item 436): which version of a break-it test is the reviewer's, and where a removal anchors.

Pins, each at the place the rule is enforced:

B1  the audit's `breakIt.match` compares the committed test with the reviewer's version up to `break_it_body`'s
    equivalence (formatting, title, supported relocation within the final diff): `same` for the reviewer's version,
    `changed-explained` for the explained build-session version, `changed-unexplained` for any real change;
B3  the reviewer's version is the latest test a test-role seat wrote for the finding: a second test replaces the
    first as the baseline, and the first test's explanation stops counting;
B2  a removed hunk-body line anchors on a line of the PR hunk it belonged to as that hunk survives in the head
    diff, never on another hunk's line;
B4  (in `test_c1l10_audit_checks.py`) the pending-step test drives a real session.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l11f_wo_b_break_it_baseline.md
"""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import break_it  # noqa: E402
import round_driver as RD  # noqa: E402
import session_contract as SC  # noqa: E402
import test_c1l10_audit_checks as C10  # noqa: E402
import test_second_test_c1l7 as ST  # noqa: E402

# The throwaway fixture repo's commits carry an inline identity; nothing is signed.
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
TEST_PATH = C10.TEST_PATH
OTHER_PATH = "tests/test_charge_moved.py"
ROLE_TEST = C10.ROLE_TEST
FIXED_TEST = C10.FIXED_TEST
WEAKER_TEST = C10.WEAKER_TEST
WHY = C10.WHY
# the same statements, spelled with other whitespace
ROLE_TEST_REFORMATTED = "def test_charge():\n    assert charge( 2 )   ==   2\n"
FIXED_TEST_REFORMATTED = "def test_charge():\n    import charge_mod\n    assert charge( 2 )   ==   2\n"


@pytest.fixture(autouse=True)
def _pinned_git_config(monkeypatch, tmp_path):
    for name in ("home", "xdg-config"):
        (tmp_path / name).mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _repo(tmp_path, files):
    """A scratch repository: a base commit holding only a README, then a head commit adding `files`
    (`{path: text}`); returns the config (`repoRoot`, `baseRef`) and the head sha."""
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "README.md").write_text("fixture\n")
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "base")
    base = _git(root, "rev-parse", "HEAD")
    for path, text in files.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "fix")
    return {"repoRoot": str(root), "baseRef": base}, _git(root, "rev-parse", "HEAD")


def _facts(tmp_path, files, finding):
    config, head = _repo(tmp_path, files)
    return RD._break_it_target_facts({}, config, finding, head)


def _explained(committed_version=FIXED_TEST):
    """A finding whose test the build session changed to `committed_version` with a reason; the test role's
    version is `ROLE_TEST`."""
    return C10._finding(content=committed_version, reviewer_test=ROLE_TEST, changed_why=WHY)


# ---- B1: the reviewer's and the explained version, up to the body-equivalence rule ------------------------------

def test_b1_an_explained_correction_later_only_reformatted_is_changed_explained(tmp_path):
    # bites on: the body-equivalence `changed-explained` leg (B-G2)
    facts = _facts(tmp_path, {TEST_PATH: FIXED_TEST_REFORMATTED}, _explained())
    assert facts["match"] == "changed-explained" and facts["changedWhy"] == WHY
    assert facts["reviewerTest"] == ROLE_TEST and facts["committedTest"] == FIXED_TEST_REFORMATTED


def test_b1_an_explained_correction_later_only_relocated_is_changed_explained(tmp_path):
    # bites on: the relocation leg (B-G3); the test is no longer at its path, it sits in another file of the diff
    facts = _facts(tmp_path, {OTHER_PATH: FIXED_TEST}, _explained())
    assert facts["match"] == "changed-explained" and facts["changedWhy"] == WHY
    assert facts["committedTest"] == FIXED_TEST


def test_b1_an_unchanged_reviewer_test_only_reformatted_is_same(tmp_path):
    # bites on: the body-equivalence `same` leg (B-G1)
    facts = _facts(tmp_path, {TEST_PATH: ROLE_TEST_REFORMATTED}, C10._finding())
    assert facts["match"] == "same" and facts["committedTest"] == ROLE_TEST_REFORMATTED


def test_b1_an_unchanged_reviewer_test_only_relocated_is_same(tmp_path):
    facts = _facts(tmp_path, {OTHER_PATH: ROLE_TEST}, C10._finding())
    assert facts["match"] == "same" and facts["committedTest"] == ROLE_TEST


def test_b1_the_exact_bytes_stay_same_and_changed_explained_without_a_base(tmp_path):
    # no `baseRef`: no body search, the exact comparison the audit always made
    root, head = C10._repo_with(tmp_path, ROLE_TEST)
    assert RD._break_it_target_facts({}, {"repoRoot": str(root)}, C10._finding(), head)["match"] == "same"
    (tmp_path / "second").mkdir()
    reformatted, head2 = C10._repo_with(tmp_path / "second", ROLE_TEST_REFORMATTED)
    assert RD._break_it_target_facts({}, {"repoRoot": str(reformatted)}, C10._finding(), head2)[
        "match"] == "changed-unexplained"


def test_b1_a_real_content_change_of_the_reviewers_test_is_changed_unexplained(tmp_path):
    # edge 1
    facts = _facts(tmp_path, {TEST_PATH: WEAKER_TEST}, C10._finding())
    assert facts["match"] == "changed-unexplained" and facts["committedTest"] == WEAKER_TEST


def test_b1_a_real_change_of_the_reviewers_test_is_unexplained_even_when_it_is_also_reformatted(tmp_path):
    facts = _facts(tmp_path, {TEST_PATH: "def test_charge():\n    assert  True\n"}, C10._finding())
    assert facts["match"] == "changed-unexplained"
    # relocated and really changed: no committed version of the test is found anywhere
    elsewhere = _facts(tmp_path / "elsewhere", {OTHER_PATH: WEAKER_TEST}, C10._finding())
    assert elsewhere["match"] == "missing" and elsewhere["committedTest"] is None


def test_b1_a_real_content_change_of_the_explained_version_is_changed_unexplained(tmp_path):
    # edge 2: the reason was given for FIXED_TEST, the fixer committed something else
    facts = _facts(tmp_path, {TEST_PATH: WEAKER_TEST}, _explained())
    assert facts["match"] == "changed-unexplained", facts
    # the same elsewhere is never credited
    moved = _facts(tmp_path / "moved", {OTHER_PATH: WEAKER_TEST}, _explained())
    assert moved["match"] == "missing", moved


def test_b1_an_explained_test_at_its_path_is_judged_before_a_relocated_reviewer_copy(tmp_path):
    # the audited test must be the one the final kept check runs: the changed test at the recorded path
    facts = _facts(tmp_path, {TEST_PATH: WEAKER_TEST, OTHER_PATH: ROLE_TEST}, _explained(WEAKER_TEST))
    assert facts["match"] == "changed-explained", facts
    assert facts["committedTest"] == WEAKER_TEST and "committedPath" not in facts


def test_b1_an_explained_version_with_no_reason_is_changed_unexplained(tmp_path):
    finding = C10._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST)
    assert _facts(tmp_path, {TEST_PATH: FIXED_TEST_REFORMATTED}, finding)["match"] == "changed-unexplained"


def test_b1_a_test_found_twice_is_never_credited(tmp_path):
    # edge 3: the body search is ambiguous (two copies in the diff), so nothing is credited
    both = {TEST_PATH: ROLE_TEST_REFORMATTED, OTHER_PATH: ROLE_TEST}
    assert _facts(tmp_path / "a", both, C10._finding())["match"] == "changed-unexplained"
    two_elsewhere = {"tests/test_one.py": ROLE_TEST, "tests/test_two.py": ROLE_TEST}
    assert _facts(tmp_path / "b", two_elsewhere, C10._finding())["match"] == "missing"
    explained_twice = {TEST_PATH: FIXED_TEST_REFORMATTED, OTHER_PATH: FIXED_TEST}
    assert _facts(tmp_path / "c", explained_twice, _explained())["match"] == "changed-unexplained"


def test_b1_a_language_the_body_search_does_not_read_compares_exact_bytes_only(tmp_path):
    # edge 4: `.rb` has no front, so a reformatted copy is a change
    path = "tests/charge_test.rb"
    block = "def test_charge\n  assert_equal 2, charge(2)\nend\n"
    finding = C10._finding(content=block)
    finding["suggestion"] = RD._break_it_block_text({"path": path, "run": C10.RUN}, block)
    finding["file"] = path
    reformatted = "def test_charge\n  assert_equal  2,   charge(2)\nend\n"
    assert _facts(tmp_path / "a", {path: reformatted}, finding)["match"] == "changed-unexplained"
    assert _facts(tmp_path / "b", {path: block}, finding)["match"] == "same"


def test_b1_a_committed_test_git_cannot_read_is_missing(tmp_path):
    # edge 5
    config, head = _repo(tmp_path, {TEST_PATH: ROLE_TEST})
    assert RD._break_it_target_facts({}, config, C10._finding(), "0" * 40)["match"] == "missing"
    assert RD._break_it_target_facts({}, dict(config, repoRoot=str(tmp_path / "nowhere")), C10._finding(),
                                     head)["match"] == "missing"
    assert RD._break_it_target_facts({}, dict(config, baseRef="0" * 40), C10._finding(),
                                     head)["match"] == "same"


# ---- B3: a second test replaces the first as the reviewer's version ----------------------------------------------

_FIRST_CONTENT = "print('first try')\n"
_FIRST_CHANGED = "print('first try, changed')\n"
_SECOND_CONTENT = "print('second try')\n"
_SECOND_CHANGED = "print('second try, changed')\n"
_RUN = {"outcome": "passed", "exitCode": 0, "output": "", "head": "a" * 40}


def _held_with_explained_first_test(r, n):
    """Make the held finding (and its ledger row) read as a finding whose first test the build session changed
    with a reason, the way `break-it-change` leaves it."""
    state = r.state()
    runs = [{"test": ST.FIRST_PATH, "changedWhy": None, "status": "ran", "exitCode": 0, "output": "",
             "reason": None, "commit": "a" * 40},
            {"test": ST.FIRST_PATH, "changedWhy": WHY, "status": "ran", "exitCode": 0, "output": "",
             "reason": None, "commit": "a" * 40}]
    changed = RD._break_it_block_text({"path": ST.FIRST_PATH, "run": "python %s" % ST.FIRST_PATH}, _FIRST_CHANGED)
    rows = [row["finding"] for row in state["_secondTestHeld"]]
    ledger = [row for row in state[SC.DISPOSITION_LEDGER_KEY] if row.get("title") == ST._HELD["title"]]
    assert len(rows) == 1 and len(ledger) == 1
    for copy_ in rows + ledger:
        copy_["suggestion"] = changed
        copy_[RD.REVIEWER_TEST_FIELD] = _FIRST_CONTENT
        copy_[break_it.RUNS_FIELD] = [dict(run) for run in runs]
    return state


def _fold_second_test(tmp_path):
    r = ST.Round(tmp_path)
    n = r.to_second_test()
    state = _held_with_explained_first_test(r, n)
    artifact = r.second_artifact(r.second_result(n["payload"]))
    RD._fold_second_test(state, state["config"], artifact, session_dir=r.dir)
    (staged,) = [f for f in state["_toVerify"] if f.get("title") == ST._HELD["title"]]
    (ledger,) = [row for row in state[SC.DISPOSITION_LEDGER_KEY] if row.get("title") == ST._HELD["title"]]
    return state, staged, ledger


def _committed_second(tmp_path, content):
    config, head = _repo(tmp_path / "audit", {ST.SECOND_PATH: content})
    return config, head


def test_b3_after_a_second_test_the_unchanged_second_test_reads_same(tmp_path):
    # bites on: the baseline-aware explanation lookup (B-G4) and the second-test baseline reset (B-G5)
    state, staged, ledger = _fold_second_test(tmp_path)
    assert staged["suggestion"] == ST._SECOND and ledger["suggestion"] == ST._SECOND
    config, head = _committed_second(tmp_path, _SECOND_CONTENT)
    for row in (staged, ledger):
        facts = RD._break_it_target_facts({}, config, row, head)
        assert facts["match"] == "same", (row is staged, facts)
        assert facts["reviewerTest"] == _SECOND_CONTENT and facts["changedWhy"] is None


def test_b3_the_rows_after_the_fold_hold_no_reviewer_baseline_of_the_first_test(tmp_path):
    # bites on: the second-test baseline reset (B-G5): neither the staged row nor the ledger row keeps the first
    # test as `reviewerTest`, and the run history stays whole, the second test's own run marking the baseline
    state, staged, ledger = _fold_second_test(tmp_path)
    for row in (staged, ledger):
        assert RD.REVIEWER_TEST_FIELD not in row
        assert [run["test"] for run in row[break_it.RUNS_FIELD]] == [
            ST.FIRST_PATH, ST.FIRST_PATH, ST.SECOND_PATH]
        assert [run.get("changedWhy") for run in row[break_it.RUNS_FIELD]] == [None, WHY, None]
        assert RD._changed_why(row) is None


def test_b3_a_later_explained_change_of_the_second_test_reads_changed_explained(tmp_path):
    # edge 6: the change is judged against the SECOND test, with the later explanation
    state, staged, ledger = _fold_second_test(tmp_path)
    later = "the second draft was missing a setup line"
    text = RD._break_it_block_text({"path": ST.SECOND_PATH, "run": "python %s" % ST.SECOND_PATH},
                                   _SECOND_CHANGED)
    for row in (staged, ledger):
        RD._rewrite_break_it_copy(row, text, dict(_RUN, path=ST.SECOND_PATH), later)
    config, head = _committed_second(tmp_path, _SECOND_CHANGED)
    for row in (staged, ledger):
        facts = RD._break_it_target_facts({}, config, row, head)
        assert facts["match"] == "changed-explained", facts
        assert facts["reviewerTest"] == _SECOND_CONTENT and facts["changedWhy"] == later
    # a different edit than the explained one is not explained
    other, head2 = _repo(tmp_path / "other", {ST.SECOND_PATH: "print('something else')\n"})
    assert RD._break_it_target_facts({}, other, staged, head2)["match"] == "changed-unexplained"


def test_b3_an_explanation_older_than_the_baseline_never_explains_a_change(tmp_path):
    # bites on: the baseline-aware explanation lookup (B-G4): the reason was recorded before the second test's run
    # set the baseline, so a committed test that differs from the reviewer's version is a change nobody explained
    finding = C10._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)
    older = _facts(tmp_path / "older", {TEST_PATH: FIXED_TEST}, finding)
    assert older["match"] == "changed-explained"
    finding[break_it.RUNS_FIELD].append({"test": TEST_PATH, "changedWhy": None, RD.SECOND_TEST_FIELD: True})
    after = _facts(tmp_path / "after", {TEST_PATH: FIXED_TEST}, finding)
    assert after["match"] == "changed-unexplained" and after["changedWhy"] is None
    # a reason recorded after the baseline counts again
    finding[break_it.RUNS_FIELD].append({"test": TEST_PATH, "changedWhy": "a later reason"})
    later = _facts(tmp_path / "later", {TEST_PATH: FIXED_TEST}, finding)
    assert later["match"] == "changed-explained" and later["changedWhy"] == "a later reason"


def test_b3_the_first_tests_explanation_never_makes_the_unchanged_second_test_changed_explained(tmp_path):
    # edge 7: with the first test's explanation still in the history, the second test (not the first's bytes)
    # committed reads `same`, and the first test's committed bytes read a change nobody explained
    state, staged, _ledger = _fold_second_test(tmp_path)
    config, head = _committed_second(tmp_path, _SECOND_CONTENT)
    assert RD._break_it_target_facts({}, config, staged, head)["match"] == "same"
    assert RD._changed_why(staged) is None
    # a finding that never had a second test keeps reading its explanation
    assert RD._changed_why(C10._finding(content=FIXED_TEST, reviewer_test=ROLE_TEST, changed_why=WHY)) == WHY


# ---- B2: a removal anchors inside the surviving PR hunk -----------------------------------------------------------

def _diff(*hunks):
    return ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
            + "".join(h if h.endswith("\n") else h + "\n" for h in hunks))


_EARLIER_HUNK = "@@ -10,3 +10,4 @@\n a10\n a11\n+extra\n a12\n"
_GUARDED_TAIL = ("{header}\n c97\n c98\n c99\n+guard\n c100\n c101\n c102\n-old103\n+new103\n c104\n c105\n c106\n")
_UNGUARDED_TAIL = "@@ -100,7 +{start},7 @@\n c100\n c101\n c102\n-old103\n+new103\n c104\n c105\n c106\n"


def _surface(reviewed, head):
    result = RD._fix_delta_surface({}, reviewed, head)
    assert result is not None
    return result[0]["f.py"]


def test_b2_a_removal_that_trims_a_later_hunks_leading_context_anchors_in_that_hunk():
    # bites on: the surviving-hunk anchor (B-G6): the guard is removed from the SECOND PR hunk, whose header then
    # reads `@@ -100,7 +101,7 @@`; the removal anchors at head line 101, not on the first hunk's lines (10..13)
    reviewed = _diff(_EARLIER_HUNK, _GUARDED_TAIL.format(header="@@ -97,10 +98,11 @@"))
    head = _diff(_EARLIER_HUNK, _UNGUARDED_TAIL.format(start=101))
    entries = _surface(reviewed, head)
    assert entries and all(not e.get("removedOnly") for e in entries), entries
    starts = [e["start"] for e in entries]
    assert min(starts) == 101 and all(start >= 100 for start in starts), entries


def test_b2_the_earliest_removal_in_the_first_hunk_anchors_in_that_hunk():
    reviewed = _diff(_GUARDED_TAIL.format(header="@@ -97,10 +97,11 @@"), "@@ -200,3 +201,4 @@\n a200\n+later\n a201\n a202\n")
    head = _diff(_UNGUARDED_TAIL.format(start=100), "@@ -200,3 +200,4 @@\n a200\n+later\n a201\n a202\n")
    entries = _surface(reviewed, head)
    assert entries and all(not e.get("removedOnly") for e in entries), entries
    assert min(e["start"] for e in entries) == 100 and max(e["start"] for e in entries) < 200, entries


def test_b2_a_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk():
    # bites on: the merged-hunk anchor (B-G7): the fix bridges the gap between two PR hunks, so the second header
    # vanishes with no header to replace it, and removes the guard from the surviving hunk; the removal anchors
    # on the surviving line after it (head line 25, `c23`) or the surface carries the removal marker
    gap = "".join(" g%d\n" % n for n in range(13, 19))
    reviewed = _diff(
        _EARLIER_HUNK,
        "@@ -20,10 +21,11 @@\n c20\n c21\n c22\n+guard\n c23\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n")
    head = _diff(
        "@@ -10,20 +10,23 @@\n a10\n a11\n+extra\n a12\n" + gap + "+bridge1\n g19\n"
        " c20\n c21\n c22\n c23\n+bridge2\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n")
    entries = _surface(reviewed, head)
    covered = [e for e in entries if not e.get("removedOnly") and e["start"] <= 25 <= e["end"]]
    assert covered or any(e.get("removedOnly") for e in entries), entries


def test_b2_every_guard_removed_where_the_fix_merges_two_pr_hunks_anchors_in_the_merged_hunk():
    # bites on: every pending removal position resolves when hunks merge (B-G7): a second guard removed from the
    # merged hunk, just before `c29`, anchors on head line 32 (`c29`) as well as the first guard on `c23` (25)
    gap = "".join(" g%d\n" % n for n in range(13, 19))
    reviewed = _diff(
        _EARLIER_HUNK,
        "@@ -20,10 +21,12 @@\n c20\n c21\n c22\n+guard\n c23\n c24\n c25\n-old26\n+new26\n c27\n c28\n+guard2\n c29\n")
    head = _diff(
        "@@ -10,20 +10,23 @@\n a10\n a11\n+extra\n a12\n" + gap + "+bridge1\n g19\n"
        " c20\n c21\n c22\n c23\n+bridge2\n c24\n c25\n-old26\n+new26\n c27\n c28\n c29\n")
    entries = _surface(reviewed, head)
    assert not any(e.get("removedOnly") for e in entries), entries
    for line in (25, 32):
        assert any(e["start"] <= line <= e["end"] for e in entries), (line, entries)


def test_b2_a_removal_with_no_surviving_line_in_its_hunk_is_marked_removal_only_never_borrowed():
    # the only hunk of a file loses everything: no line of its hunk survives, so the entry is marked, not numbered
    only = "@@ -10,3 +10,4 @@\n a10\n a11\n+extra\n a12\n"
    other = "@@ -50,3 +51,4 @@\n b50\n b51\n+kept\n b52\n"
    reviewed = _diff(only, other)
    head = _diff(other)
    entries = _surface(reviewed, head)
    assert any(e.get("removedOnly") for e in entries), entries
    assert all(e.get("removedOnly") or e["start"] >= 51 for e in entries), entries
