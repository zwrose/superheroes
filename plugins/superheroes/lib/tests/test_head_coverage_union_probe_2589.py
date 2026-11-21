# plugins/superheroes/lib/tests/test_head_coverage_union_probe_2589.py
"""Issue 2589: the tested-union proof in the head-coverage check, on real repositories.

A hand-resolved merge of the base into a reviewed pull request has no three-way reconstruction, so the check reads it
needs-review. With a union proof (the vet's tested probe, a two-parent commit of the base and a covered commit, plus the
test receipt of the probe's tree) the answer is proven only when git itself shows the head's tree is the probe's tree.

One test per row of the issue, and the fail-closed edges:

E1  a proof that is not exactly the union-probe/1 object reads ``malformed``;
E2  a probe without a good test receipt on its own tree reads ``no-receipt``;
E3  a probe of another base, even one with the same tree, reads ``other-base``;
E4  a probe git cannot read as a commit reads ``probe-unreadable``;
E5  a tree claim git does not confirm reads ``tree-unconfirmed``;
E6  a probe that is not a merge of the base and a covered commit reads ``other-commit``;
E7  a head that does not contain the base reads ``head-not-current``;
E8  a head whose tree differs by a byte or a mode reads ``other-tree``;
E9  a check that could not read its inputs does not consult the proof (``not-consulted``);
E10 an already-proven answer is left as it is;
E11 with no proof the result is today's, key set included;
E12 an exception on the union path reads ``check-failed``, never proven.

Bite-proof record: i2589_head_coverage_union_probe
"""
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import head_coverage as HC  # noqa: E402
import returning_review as R  # noqa: E402
import test_returning_review_c1l11 as TR  # noqa: E402
from test_returning_review_c1l11 import _isolated_git  # noqa: E402,F401  (autouse: no global git config)

_SCRIPT = os.path.join(_LIB, "head_coverage.py")
SHARED = "src/shared.py"
APP = "src/app.py"
KEYS = {"answer", "why", "certified", "head", "base", "files", "reconstructed", "copies", "hunks", "commits"}
MISSING = "0123456789012345678901234567890123456789"

BASE_FUNC = "def total(items):\n    subtotal = 0\n    for item in items:\n        subtotal += item.price\n    return subtotal\n"
PR_FUNC = BASE_FUNC.replace("item.price\n", "item.price + item.tax\n")
MAIN_FUNC = BASE_FUNC.replace("item.price\n", "item.price - item.discount\n")
RESOLVED = BASE_FUNC.replace("item.price\n", "item.price - item.discount + item.tax\n")


def tokens(got):
    return [w.split(":", 1)[0] for w in got["why"]]


def run_check(repo, base, record, head, union_proof=None, **kwargs):
    """``head_coverage.check`` over ``repo``, with the result's shape asserted every time: the old ten keys, plus
    ``unionProbe`` exactly when a proof was passed."""
    got = HC.check(repo.root, base, record, head, union_proof=union_proof, **kwargs)
    want = KEYS | ({"unionProbe"} if union_proof is not None else set())
    assert set(got) == want and got["answer"] in HC.ANSWERS and got["why"], got
    assert all(w.split(":", 1)[0] in HC.WHY_TOKENS for w in got["why"]), got
    if union_proof is not None:
        assert got["unionProbe"]["reason"] in (None, *HC.UNION_REASONS), got
    return got


def conflict_merge(repo, ref="main"):
    """Start a merge of ``ref`` into the checked-out branch that must conflict; leave it for the caller to resolve."""
    argv = ["git", "-C", repo.root, "-c", "user.name=T", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
            "merge", "--no-ff", "--no-commit", ref]
    proc = subprocess.run(argv, capture_output=True, text=True)
    assert proc.returncode != 0, "the fixture needs a real conflict"


def make_proof(repo, probe, base, tree=None):
    """A well-formed union proof for ``probe``, built from git."""
    tree = repo.git("rev-parse", probe + "^{tree}") if tree is None else tree
    return {"schema": HC.UNION_SCHEMA, "probe": probe, "tree": tree, "base": base,
            "receipt": {"command": "pytest -q", "exitCode": 0, "tree": tree}}


class Shape:
    """The #2585 shape. ``main`` holds a function; the pull request changes one line of it (reviewed at X, the
    ``reviewed`` attribute); main changes the same line (a real conflict, ``base`` is main's tip); the vet's probe is a
    branch from the pull request's tip merging main, resolved by hand and committed. The builder's head is made by
    ``head()``: ``pr`` merging main with the resolution it is given."""

    def __init__(self, tmp_path, later=False):
        repo = self.repo = TR.Repo(tmp_path)
        repo.write(SHARED, BASE_FUNC)
        repo.commit("shared function")
        repo.git("branch", "-f", "main", "pr")
        self.old_base = repo.git("rev-parse", "main")
        _, self.reviewed, self.record = TR.returning(repo, first={SHARED: PR_FUNC})
        self.base = repo.main_commit(SHARED, MAIN_FUNC)
        self.later = None
        if later:
            repo.write(APP, "def added():\n    return 1\n")
            self.later = repo.commit("a later commit nobody reviewed")
        repo.git("checkout", "-q", "-b", "probe")
        conflict_merge(repo)
        repo.write(SHARED, RESOLVED)
        self.probe = repo.commit("tested union probe")
        repo.git("checkout", "-q", "pr")

    def proof(self, **kwargs):
        return make_proof(self.repo, self.probe, self.base, **kwargs)

    def head(self, text=RESOLVED, chmod=False, message="merge main"):
        repo = self.repo
        conflict_merge(repo)
        repo.write(SHARED, text)
        if not chmod:
            return repo.commit(message)
        repo.git("add", "-A")
        repo.git("update-index", "--chmod=+x", SHARED)
        repo.git("commit", "-q", "-m", message)
        return repo.git("rev-parse", "HEAD")

    def flat_head(self):
        """A single-parent commit on ``pr`` that holds the probe's files and does not contain the base."""
        self.repo.write(SHARED, RESOLVED)
        head = self.repo.commit("the probe's files, no merge")
        assert self.repo.git("rev-parse", head + "^{tree}") == self.repo.git("rev-parse", self.probe + "^{tree}")
        return head

    def single_parent_probe(self):
        repo = self.repo
        repo.git("checkout", "-q", "-b", "single")
        repo.write(SHARED, RESOLVED)
        sha = repo.commit("one parent")
        repo.git("checkout", "-q", "pr")
        return sha

    def without_proof(self, head):
        return run_check(self.repo, self.base, self.record, head)


def refused(shape, head, proof, reason, answer="needs-review", **kwargs):
    """The check with ``proof`` is the check without it, plus one ignored line and an unused ``unionProbe``. ``answer``
    is the one the check gives for that head without a proof."""
    got = run_check(shape.repo, shape.base, shape.record, head, proof, **kwargs)
    without = run_check(shape.repo, shape.base, shape.record, head, **kwargs)
    assert got["answer"] == without["answer"] == answer, got
    assert got["unionProbe"] == {"probe": proof.get("probe") if isinstance(proof, dict) and isinstance(proof.get("probe"), str)
                                 else None, "used": False, "reason": reason, "covers": []}, got
    assert got["why"][:-1] == without["why"] and tokens(got)[-1] == HC.WHY_UNION_IGNORED, got
    assert got["why"][-1].endswith(" " + reason), got
    assert {k: v for k, v in got.items() if k not in ("why", "unionProbe")} == {k: v for k, v in without.items() if k != "why"}, got
    return got


# --- row 1: the #2585 shape -------------------------------------------------------------------------------------


def test_row_1_a_hand_resolved_conflict_is_proven_by_the_tested_probe(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    without = s.without_proof(head)
    assert without["answer"] == "judgement" and without["files"] == [SHARED]
    got = run_check(s.repo, s.base, s.record, head, s.proof())
    assert got["answer"] == "proven" and got["files"] == [] and got["hunks"] == [] and got["certified"] == s.reviewed
    assert tokens(got) == [HC.WHY_PROVEN_UNION] and len(got["why"]) == 1
    union = got["unionProbe"]
    assert union["used"] is True and union["reason"] is None and union["covers"] == [SHARED]
    assert union["probe"] == s.probe and union["parent"] == s.reviewed and union["base"] == s.base
    assert union["tree"] == s.repo.git("rev-parse", head + "^{tree}") and union["receipt"] == s.proof()["receipt"]
    assert HC.outcome(got["answer"], "green") == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "none"}


# --- row 2 and 3: the head is not the tested tree ------------------------------------------------------------------


def test_row_2_one_byte_different_in_the_builders_resolution_reads_other_tree(tmp_path):
    s = Shape(tmp_path)
    head = s.head(RESOLVED.replace("item.tax", "item.tex"))
    got = refused(s, head, s.proof(), "other-tree", "judgement")
    assert HC.outcome(got["answer"], "green")["outcome"] == "NOT-READY"


def test_row_3_a_mode_difference_only_reads_other_tree(tmp_path):
    s = Shape(tmp_path)
    head = s.head(chmod=True)
    modes = s.repo.git("ls-tree", head, "--", SHARED).split()[0], s.repo.git("ls-tree", s.probe, "--", SHARED).split()[0]
    assert modes == ("100755", "100644")
    refused(s, head, s.proof(), "other-tree")


# --- row 4: another base --------------------------------------------------------------------------------------------


def test_row_4a_a_probe_on_an_older_main_commit_reads_other_base(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    refused(s, head, make_proof(s.repo, s.probe, s.old_base), "other-base", "judgement")


def test_row_4b_two_distinct_bases_holding_one_tree_read_other_base(tmp_path):
    s = Shape(tmp_path)
    s.repo.git("checkout", "-q", "main")
    s.repo.git("commit", "-q", "--allow-empty", "-m", "an empty commit on main")
    newer = s.repo.git("rev-parse", "HEAD")
    s.repo.git("checkout", "-q", "pr")
    assert newer != s.base and s.repo.git("rev-parse", newer + "^{tree}") == s.repo.git("rev-parse", s.base + "^{tree}")
    head = s.head()
    # the check's base is the newer commit; the probe merged the older one
    got = run_check(s.repo, newer, s.record, head, s.proof())
    assert got["answer"] == "judgement" and got["unionProbe"]["reason"] == "other-base" and got["unionProbe"]["used"] is False
    # and the older one is the check's base when the proof names the newer one
    again = run_check(s.repo, s.base, s.record, head, make_proof(s.repo, s.probe, newer))
    assert again["unionProbe"]["reason"] == "other-base" and again["answer"] == "needs-review"


# --- row 5: no test receipt -------------------------------------------------------------------------------------------


def _set(key, value):
    def mutate(proof):
        proof["receipt"][key] = value
        return proof
    return mutate


def _replace(**changes):
    def mutate(proof):
        proof.update(changes)
        return proof
    return mutate


def _drop_receipt_key(proof):
    del proof["receipt"]["command"]
    return proof


RECEIPT_CASES = {
    "receipt-none": _replace(receipt=None),
    "receipt-string": _replace(receipt="pytest -q passed"),
    "receipt-list": _replace(receipt=[]),
    "extra-key": _set("extra", 1),
    "missing-key": _drop_receipt_key,
    "blank-command": _set("command", " \n\t"),
    "empty-command": _set("command", ""),
    "command-not-string": _set("command", ["pytest"]),
    "exit-1": _set("exitCode", 1),
    "exit-true": _set("exitCode", True),
    "exit-false": _set("exitCode", False),
    "exit-string": _set("exitCode", "0"),
    "exit-float": _set("exitCode", 0.0),
    "receipt-tree-differs": _set("tree", "f" * 40),
}


@pytest.mark.parametrize("case", sorted(RECEIPT_CASES))
def test_row_5_a_probe_without_a_good_test_receipt_reads_no_receipt(tmp_path, case):
    s = Shape(tmp_path)
    head = s.head()
    refused(s, head, RECEIPT_CASES[case](s.proof()), "no-receipt", "judgement")


# --- row 6: a tree claim git does not confirm, and a probe git cannot read ----------------------------------------------


def test_row_6_a_tree_claim_git_does_not_confirm_reads_tree_unconfirmed(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    reviewed_tree = s.repo.git("rev-parse", s.reviewed + "^{tree}")
    refused(s, head, s.proof(tree=reviewed_tree), "tree-unconfirmed", "judgement")


def test_row_6_a_probe_that_is_not_a_readable_commit_reads_probe_unreadable(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    real_tree = s.repo.git("rev-parse", s.probe + "^{tree}")
    blob = s.repo.git("rev-parse", "pr:" + SHARED)
    for probe, tree in ((MISSING, real_tree), (real_tree, real_tree), (blob, real_tree), (blob, blob)):
        refused(s, head, make_proof(s.repo, probe, s.base, tree=tree), "probe-unreadable", "judgement")


# --- row 7: a probe that does not merge the base and a covered commit --------------------------------------------------------


def test_row_7_a_probe_of_an_unreviewed_later_commit_reads_other_commit(tmp_path):
    s = Shape(tmp_path, later=True)
    head = s.head()
    assert s.repo.git("rev-parse", s.probe + "^1") == s.later
    got = refused(s, head, s.proof(), "other-commit")
    assert APP in got["files"]


def test_row_7_a_one_parent_probe_reads_other_commit(tmp_path):
    s = Shape(tmp_path)
    single = s.single_parent_probe()
    head = s.head()
    refused(s, head, make_proof(s.repo, single, s.base), "other-commit", "judgement")


def test_a_probe_whose_parents_are_both_the_base_or_that_lacks_the_base_reads_other_commit(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    tree = s.repo.git("rev-parse", s.probe + "^{tree}")
    both_base = s.repo.git("commit-tree", tree, "-p", s.base, "-p", s.base, "-m", "both parents are the base")
    no_base = s.repo.git("commit-tree", tree, "-p", s.reviewed, "-p", s.old_base, "-m", "no parent is the base")
    three = s.repo.git("commit-tree", tree, "-p", s.reviewed, "-p", s.base, "-p", s.old_base, "-m", "three parents")
    for probe in (both_base, no_base, three):
        refused(s, head, make_proof(s.repo, probe, s.base), "other-commit", "judgement")


# --- row 8: a head that does not contain the base --------------------------------------------------------------------------


def test_row_8_a_head_that_holds_the_probes_files_but_not_the_base_reads_head_not_current(tmp_path):
    s = Shape(tmp_path)
    head = s.flat_head()
    assert subprocess.run(["git", "-C", s.repo.root, "merge-base", "--is-ancestor", s.base, head]).returncode == 1
    refused(s, head, s.proof(), "head-not-current")


# --- row 9: the proof is not the union-probe/1 object -------------------------------------------------------------------------


def _upper_first(proof):
    proof["probe"] = "A" + proof["probe"][1:]
    return proof


def _lacks(key):
    def mutate(proof):
        del proof[key]
        return proof
    return mutate


MALFORMED_CASES = {
    "list": lambda proof: [proof],
    "string": lambda proof: "union-probe/1",
    "number": lambda proof: 7,
    "empty-dict": lambda proof: {},
    "extra-key": _replace(extra=1),
    "no-receipt-key": _lacks("receipt"),
    "no-base-key": _lacks("base"),
    "no-schema-key": _lacks("schema"),
    "wrong-schema": _replace(schema="union-probe/2"),
    "short-probe": lambda proof: dict(proof, probe=proof["probe"][:7]),
    "upper-case-probe": _upper_first,
    "probe-not-string": _replace(probe=12345),
    "probe-none": _replace(probe=None),
    "short-tree": lambda proof: dict(proof, tree=proof["tree"][:7]),
    "short-base": lambda proof: dict(proof, base=proof["base"][:7]),
}


@pytest.mark.parametrize("case", sorted(MALFORMED_CASES))
def test_row_9_a_proof_that_is_not_exactly_the_object_reads_malformed(tmp_path, case):
    s = Shape(tmp_path)
    head = s.head()
    proof = MALFORMED_CASES[case](s.proof())
    got = run_check(s.repo, s.base, s.record, head, proof)
    without = s.without_proof(head)
    assert got["answer"] == without["answer"] == "judgement"
    assert got["unionProbe"]["used"] is False and got["unionProbe"]["reason"] == "malformed" and got["unionProbe"]["covers"] == []
    assert got["why"][:-1] == without["why"] and tokens(got)[-1] == HC.WHY_UNION_IGNORED
    probe = proof.get("probe") if isinstance(proof, dict) else None
    assert got["unionProbe"]["probe"] == (probe if isinstance(probe, str) else None)


# --- row 10: the check could not read its inputs --------------------------------------------------------------------------------


def test_row_10_an_unusable_record_with_a_valid_proof_is_not_consulted(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    unusable = dict(s.record, ok=False)
    got = run_check(s.repo, s.base, unusable, head, s.proof())
    assert got["answer"] == "needs-review" and got["certified"] is None
    assert tokens(got) == [HC.WHY_RECORD_UNUSABLE, HC.WHY_UNION_IGNORED]
    assert got["unionProbe"] == {"probe": s.probe, "used": False, "reason": "not-consulted", "covers": []}


def test_row_10_invalid_inputs_and_an_unreadable_diff_do_not_consult_the_proof(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    invalid = run_check(s.repo, s.base, s.record, "not-a-sha", s.proof())
    assert invalid["answer"] == "needs-review" and tokens(invalid) == [HC.WHY_INPUT_INVALID, HC.WHY_UNION_IGNORED]
    assert invalid["unionProbe"]["reason"] == "not-consulted" and invalid["unionProbe"]["used"] is False
    unreadable = run_check(s.repo, s.base, s.record, head, s.proof(), git=lambda argv: (128, ""))
    assert unreadable["answer"] == "needs-review" and tokens(unreadable) == [HC.WHY_DIFF_UNREADABLE, HC.WHY_UNION_IGNORED]
    assert unreadable["unionProbe"]["reason"] == "not-consulted"


# --- row 11: an already-proven answer ----------------------------------------------------------------------------------------------


def test_row_11_a_clean_catch_up_with_a_proof_stays_proven_by_the_check_itself(tmp_path):
    repo = TR.Repo(tmp_path)
    base, reviewed, earlier = TR.returning(repo)
    moved = repo.main_commit("docs/other.md", "other\n")
    head = repo.merge_main()
    unused = {"schema": HC.UNION_SCHEMA, "probe": "a" * 40, "tree": "b" * 40, "base": "c" * 40,
              "receipt": {"command": "pytest -q", "exitCode": 0, "tree": "b" * 40}}
    without = run_check(repo, moved, earlier, head)
    got = run_check(repo, moved, earlier, head, unused)
    assert got["answer"] == "proven" and tokens(got) == [HC.WHY_OWN_CHANGE_UNCHANGED]
    assert got["unionProbe"] == {"probe": "a" * 40, "used": False, "reason": None, "covers": []}
    assert {k: v for k, v in got.items() if k != "unionProbe"} == without


# --- row 12: no proof, no key -------------------------------------------------------------------------------------------------------


def test_row_12_without_a_proof_the_result_has_no_union_probe_key(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    needs = run_check(s.repo, s.base, s.record, head)
    assert needs["answer"] == "judgement" and "unionProbe" not in needs
    assert HC.WHY_UNION_IGNORED not in tokens(needs) and HC.WHY_PROVEN_UNION not in tokens(needs)
    same = run_check(s.repo, s.base, s.record, s.reviewed)
    assert same["answer"] == "proven" and "unionProbe" not in same
    failed = HC.check(s.repo.root, s.base, s.record, head, git=lambda argv: 1 / 0)
    assert set(failed) == KEYS and tokens(failed) == [HC.WHY_CHECK_FAILED]


def test_the_union_names_are_exported():
    assert HC.UNION_SCHEMA == "union-probe/1"
    assert HC.WHY_PROVEN_UNION == "proven-union" and HC.WHY_UNION_IGNORED == "union-probe-ignored"
    assert HC.WHY_PROVEN_UNION in HC.WHY_TOKENS and HC.WHY_UNION_IGNORED in HC.WHY_TOKENS
    assert HC.UNION_REASONS == ("malformed", "no-receipt", "other-base", "probe-unreadable", "tree-unconfirmed",
                                "other-commit", "head-not-current", "other-tree", "not-consulted")


# --- row 13: the two-anchor case end to end -------------------------------------------------------------------------------------------


def two_anchor(tmp_path, head_text):
    """Review at X; a clean catch-up of main to S; a sheet at S; main then changes the same line; the vet's tested probe
    of S and main; the builder's head merging main with ``head_text``."""
    repo = TR.Repo(tmp_path)
    repo.write(SHARED, BASE_FUNC)
    repo.commit("shared function")
    repo.git("branch", "-f", "main", "pr")
    _, x, record = TR.returning(repo, first={SHARED: PR_FUNC})
    first_base = repo.main_commit("docs/other.md", "other\n")
    s = repo.merge_main()
    catch_up = run_check(repo, first_base, record, s)
    assert catch_up["answer"] == "proven" and tokens(catch_up) == [HC.WHY_OWN_CHANGE_UNCHANGED]
    second_base = repo.main_commit(SHARED, MAIN_FUNC)
    repo.git("checkout", "-q", "-b", "probe")
    conflict_merge(repo)
    repo.write(SHARED, RESOLVED)
    probe = repo.commit("tested union probe")
    repo.git("checkout", "-q", "pr")
    conflict_merge(repo)
    repo.write(SHARED, head_text)
    head = repo.commit("merge main")
    return repo, x, s, second_base, probe, head, record, {"ok": True, "finalCommit": {"sha": s}}


def test_row_13_the_coverage_and_the_carry_check_both_prove_through_the_covered_parent(tmp_path):
    repo, x, s, base, probe, head, record, carry_record = two_anchor(tmp_path, RESOLVED)
    proof = make_proof(repo, probe, base)
    assert repo.git("rev-parse", probe + "^1") == s
    coverage = run_check(repo, base, record, head, proof)
    assert coverage["answer"] == "proven" and tokens(coverage) == [HC.WHY_PROVEN_UNION]
    assert coverage["unionProbe"]["used"] is True and coverage["unionProbe"]["parent"] == s
    assert run_check(repo, base, record, head)["answer"] == "needs-review"
    carry = run_check(repo, base, carry_record, head, proof)
    assert carry["answer"] == "proven" and carry["unionProbe"]["used"] is True and carry["certified"] == s
    assert run_check(repo, base, carry_record, head)["answer"] == "needs-review"
    moved = HC.outcome(coverage["answer"], "green", sheet="live", sheet_commit=s, head=head, carry_answer=carry["answer"])
    assert moved == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-carried"}


def test_row_13_a_one_byte_different_resolution_takes_the_sheet_down(tmp_path):
    repo, x, s, base, probe, head, record, carry_record = two_anchor(tmp_path, RESOLVED.replace("item.tax", "item.tex"))
    proof = make_proof(repo, probe, base)
    coverage = run_check(repo, base, record, head, proof)
    carry = run_check(repo, base, carry_record, head, proof)
    for got in (coverage, carry):
        assert got["answer"] == "needs-review" and got["unionProbe"]["reason"] == "other-tree" and got["unionProbe"]["used"] is False
    moved = HC.outcome(coverage["answer"], "green", sheet="live", sheet_commit=s, head=head, carry_answer=carry["answer"])
    assert moved["outcome"] == "NOT-READY" and moved["sheet"] == "take-down"


# --- row 14: an exception on the union path ---------------------------------------------------------------------------------------------


def test_row_14_an_exception_on_the_union_path_reads_check_failed_never_proven(tmp_path):
    s = Shape(tmp_path)
    head = s.head()
    real = R.production_git(s.repo.root)

    def raising(argv):
        if argv[:2] == ["cat-file", "-t"]:
            raise RuntimeError("git blew up on the probe")
        return real(argv)

    assert run_check(s.repo, s.base, s.record, head, s.proof(), git=real)["answer"] == "proven"
    got = run_check(s.repo, s.base, s.record, head, s.proof(), git=raising)
    assert got["answer"] == "needs-review" and tokens(got)[0] == HC.WHY_CHECK_FAILED
    assert "RuntimeError" in got["why"][0] and got["unionProbe"]["used"] is False and got["unionProbe"]["reason"] == "not-consulted"


# --- row 15: the CLI ----------------------------------------------------------------------------------------------------------------------


def _cli(*argv):
    return subprocess.run([sys.executable, _SCRIPT, *argv], capture_output=True, text=True)


def test_row_15_the_cli_reads_a_union_proof_file(tmp_path):
    s = Shape(tmp_path / "shape")
    head = s.head()
    record = tmp_path / "record.json"
    record.write_text(json.dumps(s.record), encoding="utf-8")
    proof_file = tmp_path / "union.json"
    proof_file.write_text(json.dumps(s.proof()), encoding="utf-8")
    common = ["check", "--repo-root", s.repo.root, "--base", s.base, "--record", str(record), "--head", head]
    with_proof = _cli(*common, "--union-proof", str(proof_file))
    assert with_proof.returncode == 0, with_proof.stderr
    printed = json.loads(with_proof.stdout)
    assert printed["answer"] == "proven" and printed["unionProbe"]["used"] is True and printed["unionProbe"]["covers"] == [SHARED]
    without = _cli(*common)
    assert without.returncode == 0 and json.loads(without.stdout)["answer"] == "judgement"
    assert "unionProbe" not in json.loads(without.stdout)
    wrong = tmp_path / "wrong.json"
    wrong.write_text(json.dumps({"schema": "union-probe/1"}), encoding="utf-8")
    malformed = _cli(*common, "--union-proof", str(wrong))
    assert malformed.returncode == 0 and json.loads(malformed.stdout)["unionProbe"]["reason"] == "malformed"


def test_row_15_the_cli_refuses_an_unreadable_or_null_union_proof_file(tmp_path):
    s = Shape(tmp_path / "shape")
    head = s.head()
    record = tmp_path / "record.json"
    record.write_text(json.dumps(s.record), encoding="utf-8")
    common = ["check", "--repo-root", s.repo.root, "--base", s.base, "--record", str(record), "--head", head]
    missing = _cli(*common, "--union-proof", str(tmp_path / "missing.json"))
    assert missing.returncode == 2 and missing.stdout == "" and "--union-proof" in missing.stderr
    garbled = tmp_path / "garbled.json"
    garbled.write_text("{not json", encoding="utf-8")
    assert _cli(*common, "--union-proof", str(garbled)).returncode == 2
    null = tmp_path / "null.json"
    null.write_text("null", encoding="utf-8")
    refused_null = _cli(*common, "--union-proof", str(null))
    assert refused_null.returncode == 2 and refused_null.stdout == "" and "no proof" in refused_null.stderr
