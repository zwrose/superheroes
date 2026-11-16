# plugins/superheroes/lib/tests/test_head_coverage_carry_answer_v962.py
"""Vet 962 on issue 2496: a verdict carries onto a moved head only when the check run from the published sheet's own
commit covers it, the sheet's commit and the head are full shas, and a failed mode read at the reviewed commit alone
keeps a copied file changed.

Bite-proof record: i2496_v962_carry_answer
"""
import hashlib
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
APP = "src/app.py"
A40 = "a" * 40
B40 = "b" * 40


def _cli(*argv):
    return subprocess.run([sys.executable, "-B", _SCRIPT, *argv], capture_output=True, text=True)


def test_a_sheet_at_a_whose_code_fix_b_was_reviewed_republishes_unsigned(tmp_path):
    # axis: the head's own record proving it never carries the verdict; the check from the sheet's commit must cover
    # the head, and code changed since the sheet reads needs-review, so the sheet is republished unsigned — see
    # bite-proof record i2496_v962_carry_answer (E-carry)
    repo = TR.Repo(tmp_path)
    base, sheet_at, sheet_record = TR.returning(repo)  # commit A: the sheet was published on this review
    repo.write(APP, repo.read(APP) + "def fix():\n    return 2\n")
    fix = repo.commit("a code fix")  # commit B, reviewed before the vet runs the check
    fix_record = TR.earlier_record(fix)
    head_answer = HC.check(repo.root, base, fix_record, fix)
    assert head_answer["answer"] == "proven", head_answer
    carry = HC.check(repo.root, base, sheet_record, fix)
    assert carry["answer"] == "needs-review" and APP in carry["files"], carry
    got = HC.outcome(head_answer["answer"], "green", sheet="live", sheet_commit=sheet_at, head=fix,
                     carry_answer=carry["answer"])
    assert got == {"outcome": "READY", "why": "covered", "review": "none", "sheet": "republish-unsigned"}


@pytest.mark.parametrize("carry, cleared, action", [
    ("proven", False, "republish-carried"),
    ("judgement", True, "republish-carried"),
    ("judgement", False, "republish-unsigned"),
    ("needs-review", False, "republish-unsigned"),
    ("needs-review", True, "republish-unsigned"),
], ids=["proven", "judgement-cleared", "judgement-uncleared", "needs-review", "needs-review-cleared-flag"])
def test_a_ready_head_past_a_live_sheet_carries_only_on_a_covering_carry_answer(carry, cleared, action):
    # axis: republish-carried needs the carry answer proven, or judgement with carry_judged_clear; every other carry
    # answer is republish-unsigned — see bite-proof record i2496_v962_carry_answer (E-carry)
    got = HC.outcome("proven", "green", sheet="live", sheet_commit=A40, head=B40, carry_answer=carry,
                     carry_judged_clear=cleared)
    assert got["outcome"] == "READY" and got["sheet"] == action


def test_the_carry_answer_does_not_change_a_sheet_on_its_own_head_or_a_verdict_that_is_not_ready():
    assert HC.outcome("proven", "green", sheet="live", sheet_commit=A40, head=A40)["sheet"] == "keep"
    assert HC.outcome("needs-review", "green", sheet="live", sheet_commit=A40, head=B40,
                      carry_answer="proven")["sheet"] == "take-down"
    assert HC.outcome("proven", "pending", sheet="live", sheet_commit=A40, head=B40,
                      carry_answer="proven")["sheet"] == "keep"


@pytest.mark.parametrize("ci, answer", [("green", "proven"), ("pending", "proven"), ("green", "needs-review")])
def test_a_live_sheet_whose_head_moved_with_no_carry_answer_is_a_usage_error(ci, answer):
    # axis: a live sheet past which the head moved never gets an action without the second check's answer — see
    # bite-proof record i2496_v962_carry_answer (E-carry-required)
    with pytest.raises(ValueError, match="carry answer"):
        HC.outcome(answer, ci, sheet="live", sheet_commit=A40, head=B40)
    proc = _cli("outcome", "--answer", answer, "--ci", ci, "--sheet", "live", "--sheet-commit", A40, "--head", B40)
    assert proc.returncode == 2 and proc.stdout == "" and "carry answer" in proc.stderr


def test_a_carry_answer_outside_the_answers_is_a_usage_error():
    with pytest.raises(ValueError, match="carry answer"):
        HC.outcome("proven", "green", sheet="live", sheet_commit=A40, head=B40, carry_answer="maybe")
    proc = _cli("outcome", "--answer", "proven", "--ci", "green", "--sheet", "live", "--sheet-commit", A40,
                "--head", B40, "--carry-answer", "maybe")
    assert proc.returncode == 2 and proc.stdout == ""


@pytest.mark.parametrize("sheet", ["live", "held"])
@pytest.mark.parametrize("which, bad", [
    ("sheet_commit", None), ("sheet_commit", "a" * 7), ("sheet_commit", "A" * 40), ("sheet_commit", "g" * 40),
    ("sheet_commit", "main"), ("head", None), ("head", "b" * 12), ("head", "b" * 41), ("head", 5),
], ids=["commit-absent", "commit-short", "commit-upper", "commit-not-hex", "commit-ref",
        "head-absent", "head-short", "head-long", "head-not-a-string"])
def test_a_sheet_needs_full_40_hex_shas_for_its_commit_and_the_head(sheet, which, bad):
    # axis: with a sheet, both commits are full 40-hex shas, never an abbreviation, a ref, another case or nothing —
    # see bite-proof record i2496_v962_carry_answer (E-sha)
    kwargs = {"sheet_commit": A40, "head": B40, "carry_answer": "proven", which: bad}
    with pytest.raises(ValueError, match="full 40-hex sha"):
        HC.outcome("proven", "green", sheet=sheet, **kwargs)


def test_the_cli_refuses_a_short_sheet_commit_or_head_and_accepts_full_ones():
    for flag, value in (("--sheet-commit", "a" * 7), ("--head", "b" * 7)):
        argv = {"--sheet-commit": A40, "--head": B40, flag: value}
        proc = _cli("outcome", "--answer", "proven", "--ci", "green", "--sheet", "held",
                    "--sheet-commit", argv["--sheet-commit"], "--head", argv["--head"])
        assert proc.returncode == 2 and proc.stdout == "" and "full 40-hex sha" in proc.stderr
    ok = _cli("outcome", "--answer", "proven", "--ci", "green", "--sheet", "live", "--sheet-commit", A40, "--head", B40,
              "--carry-answer", "judgement", "--carry-judged-clear")
    assert ok.returncode == 0 and json.loads(ok.stdout)["sheet"] == "republish-carried"
    # no sheet: no commit is needed
    assert _cli("outcome", "--answer", "proven", "--ci", "green").returncode == 0


def test_a_failed_mode_read_at_the_reviewed_commit_only_keeps_a_copied_file_changed(tmp_path):
    # axis: a mode git could not read at the reviewed commit is not an absent file, even when the head reads 100644
    # and a copy proof passes, so the copy proof never drops the file — see bite-proof record
    # i2496_wo_a_head_coverage (E-mode-read)
    repo = TR.Repo(tmp_path)
    copied = "vendor/lib.py"
    old = TR.numbered("vendored", 40)
    base, reviewed, earlier = TR.returning(repo, first={APP: TR.numbered("app", 100), copied: old})
    new = TR.numbered("vendored-v2", 40)
    repo.write(copied, new)
    head = repo.commit("update the vendored copy")
    proof = [{"file": copied, "source": "upstream/lib.py", "sha256": hashlib.sha256(new.encode()).hexdigest()}]
    proven = HC.check(repo.root, base, earlier, head, proof=proof)
    assert proven["answer"] == "proven" and [c["file"] for c in proven["copies"]] == [copied], proven
    assert repo.git("ls-tree", head, "--", copied).split(" ", 1)[0] == "100644"
    real = R.production_git(repo.root)
    failed = []

    def no_mode_at_reviewed(argv):
        if argv[0] == "ls-tree" and argv[1] == reviewed:
            failed.append(argv)
            return 128, ""
        return real(argv)

    got = HC.check(repo.root, base, earlier, head, proof=proof, git=no_mode_at_reviewed)
    assert failed, "the check never read the reviewed commit's mode through the seam"
    assert got["answer"] == "needs-review" and got["copies"] == [] and copied in got["files"], got
