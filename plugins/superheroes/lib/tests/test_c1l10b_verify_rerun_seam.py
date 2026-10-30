"""One home for "did the verify re-run run on the same code?": the driver decides, the record reads.

`_fold_verify` records its decision on the `rerunChecks` entry (`went-on`, `head-moved`, `tree-changed`,
`failed`, plus the two heads for `head-moved`); the review record's re-run line says "on unchanged code"
only for `went-on` and never works the decision out again. The working-tree digest the decision rests on
covers the untracked files that are not ignored. A cloud session's footer on a PATCHed PR body is not a
difference when the body is read back.

Edges, as the work order numbers them: (1) no `decision` never reads as unchanged code; (2) an unknown or
non-string `decision` is refused by `_rerun_fault`; (3) `head-moved` with an unknown head names what it has;
(4) `git diff` or `git ls-files` failing, or an untracked file that cannot be read, gives no digest, while a
path with spaces or a newline digests like any other; (5) an untracked symlink digests as its link text and a
nested repository as a directory marker; (6) ignored files are not in the digest; (7) a body already ending
with the footer, a body with two footers, and a read-back that fails.

Bite-proof record: c1l10b_wo3_verify_rerun_seam
"""
import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import test_round_driver_advance as TA  # noqa: E402
from test_round_driver_advance import adapters  # noqa: E402,F401  (a fixture)
# The fold helpers, the real-repo helper and the record builders are the neighbouring tests' own, imported rather than copied.
from test_verify_rerun_ufr3 import H1, H2, _artifact, _entries, _fold, _git, _kinds, _state  # noqa: E402
from test_review_record_rerun_heads import rerun_lines  # noqa: E402
import test_pr_body_stage as TPB  # noqa: E402

import cloud_builder  # noqa: E402
import pr_body_stage as PBS  # noqa: E402
import review_record  # noqa: E402

RD = TA.RD
RR = TA.RR
UNCHANGED = "on unchanged code"
DECISIONS = ("went-on", "head-moved", "tree-changed", "failed")


# =============================================================================================
# item 1: the decision is the driver's, recorded on the entry, and the record reads it
# =============================================================================================

def _rerun_entry(state):
    (entry,) = _entries(state)
    return dict(entry, round=1)


def _tree_changed_state():
    state = _state()
    first = _artifact("fail")
    first["treeSha"] = "a" * 64
    second = _artifact("pass")
    second["treeSha"] = "b" * 64
    _fold(state, first)
    _fold(state, second)
    return state


def _state_for(decision):
    state = _state()
    if decision == "went-on":
        _fold(state, _artifact("fail"))
        _fold(state, _artifact("pass"))
    elif decision == "head-moved":
        _fold(state, _artifact("fail", head=H1), fold_head=H1)
        _fold(state, _artifact("pass", head=H2), fold_head=H2)
    elif decision == "tree-changed":
        state = _tree_changed_state()
    else:
        _fold(state, _artifact("fail"))
        _fold(state, _artifact("fail"))
    return state


@pytest.mark.parametrize("decision", DECISIONS)
def test_the_driver_records_its_decision_on_the_entry_and_the_validator_accepts_it(decision):
    entry = _rerun_entry(_state_for(decision))
    assert entry["decision"] == decision
    assert ("heads" in entry) == (decision == "head-moved")
    assert review_record._rerun_fault(entry) is None


def test_a_head_moved_entry_names_the_two_heads_the_driver_named():
    entry = _rerun_entry(_state_for("head-moved"))
    assert entry["heads"] == [H1, H2]


def test_1a_a_re_run_that_starts_at_another_head_and_ends_at_the_first_heads_halts_and_is_not_unchanged_code():
    # axis: the record reads the driver's decision, not the runs' heads alone
    state = _state()
    _fold(state, _artifact("fail", head=H1), fold_head=H1)
    # the landing: the re-run began at H2 (headSha) and ended at the first run's head H1 (headShaAfter)
    _fold(state, _artifact("pass", head=H2, after=H1), fold_head=H2)

    assert state["terminal"] == "halted"
    assert _kinds(state)[-1] == "verify-rerun-head-moved"
    entry = _rerun_entry(state)
    assert entry["decision"] == "head-moved" and entry["heads"] == [H2, H1]
    full, compact = rerun_lines([entry])
    assert UNCHANGED not in full and UNCHANGED not in compact
    assert "unchanged code" not in full and "unchanged code" not in compact
    assert f"different head ({H2[:12]} then {H1[:12]})" in full


def test_1b_a_re_run_halted_on_changed_contents_is_not_unchanged_code_and_names_the_changed_contents():
    # axis: the record reads the driver's decision, not the runs' heads alone
    state = _tree_changed_state()
    assert _kinds(state)[-1] == "verify-rerun-tree-changed"
    full, compact = rerun_lines([_rerun_entry(state)])
    assert "unchanged code" not in full and "unchanged code" not in compact
    assert "changed working-tree contents" in full


def test_1c_only_a_decision_of_went_on_reads_as_unchanged_code():
    # axis: the record reads the driver's decision, not the runs' heads alone
    for decision in DECISIONS:
        full, compact = rerun_lines([_rerun_entry(_state_for(decision))])
        said = UNCHANGED in full and UNCHANGED in compact
        assert said == (decision == "went-on"), (decision, full, compact)
        assert (UNCHANGED in full) == (UNCHANGED in compact), decision
    entry = _rerun_entry(_state_for("went-on"))
    del entry["decision"]
    full, compact = rerun_lines([entry])
    assert "unchanged code" not in full and "unchanged code" not in compact


def test_the_compact_form_says_unchanged_code_only_when_every_entry_went_on():
    went_on, halted = _rerun_entry(_state_for("went-on")), _rerun_entry(_state_for("tree-changed"))
    assert UNCHANGED in rerun_lines([went_on, dict(went_on, round=2)])[1]
    assert UNCHANGED not in rerun_lines([went_on, halted])[1]
    assert UNCHANGED not in rerun_lines([halted, went_on])[0]


@pytest.mark.parametrize("heads", [None, [None, H2], [H1, None], [None, None]])
def test_3_a_head_moved_entry_with_an_unknown_head_names_what_it_has_and_never_says_unchanged_code(heads):
    entry = _rerun_entry(_state_for("head-moved"))
    entry.pop("heads")
    if heads is not None:
        entry["heads"] = heads
    full, compact = rerun_lines([entry])
    assert "unchanged code" not in full and "unchanged code" not in compact
    assert "different head" in full


@pytest.mark.parametrize("heads", [[], [H1], ["", ""], 5, [1, 2, 3]])
def test_3_the_line_does_not_raise_on_malformed_heads_the_validator_would_refuse(heads):
    entry = dict(_rerun_entry(_state_for("head-moved")), heads=heads)
    for compact in (False, True):
        line = review_record._rerun_line([entry], compact)
        assert "unchanged code" not in line


def test_3_the_known_side_of_a_head_moved_entry_is_named():
    entry = dict(_rerun_entry(_state_for("head-moved")), heads=[H1, None])
    assert f"different head ({H1[:12]} then unknown)" in rerun_lines([entry])[0]


@pytest.mark.parametrize("decision", ["", "moved", "went_on", "WENT-ON", None, 3, True, ["went-on"], {}])
def test_2_an_unknown_or_non_string_decision_is_a_fault(decision):
    entry = dict(_rerun_entry(_state_for("went-on")), decision=decision)
    assert review_record._rerun_fault(entry) == ".decision"


@pytest.mark.parametrize("heads", ["x", [H1], [H1, H2, H1], [1, 2], {"a": 1}])
def test_2_a_malformed_heads_field_is_a_fault(heads):
    entry = dict(_rerun_entry(_state_for("head-moved")), heads=heads)
    assert review_record._rerun_fault(entry) == ".heads"


def test_1_an_entry_with_no_decision_is_still_a_valid_old_record():
    entry = _rerun_entry(_state_for("went-on"))
    del entry["decision"]
    assert review_record._rerun_fault(entry) is None


def test_the_decision_on_a_non_pass_second_result_is_failed_whatever_the_heads():
    state = _state()
    _fold(state, _artifact("fail", head=H1), fold_head=H1)
    _fold(state, _artifact("fail", head=H2), fold_head=H2)
    entry = _rerun_entry(state)
    assert entry["decision"] == "failed" and "heads" not in entry
    assert _kinds(state)[-1] == "verify-fail"


# =============================================================================================
# item 2: untracked files that are not ignored are working-tree contents
# =============================================================================================

def _repo(tmp_path, name="repo"):
    repo = tmp_path / name
    repo.mkdir()
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "first")
    return repo


def test_an_untracked_file_changes_the_digest_and_its_bytes_count(tmp_path):
    repo = _repo(tmp_path)
    clean = RD._verify_run_tree(str(repo))
    assert isinstance(clean, str) and clean
    (repo / "new.txt").write_text("one\n", encoding="utf-8")
    one = RD._verify_run_tree(str(repo))
    (repo / "new.txt").write_text("two\n", encoding="utf-8")
    two = RD._verify_run_tree(str(repo))
    assert len({clean, one, two}) == 3
    assert RD._verify_run_tree(str(repo)) == two


def test_6_an_ignored_file_is_not_in_the_digest(tmp_path):
    repo = _repo(tmp_path)
    clean = RD._verify_run_tree(str(repo))
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("a\n", encoding="utf-8")
    assert RD._verify_run_tree(str(repo)) == clean
    (repo / "build" / "out.txt").write_text("b\n", encoding="utf-8")
    assert RD._verify_run_tree(str(repo)) == clean


def test_4_a_path_with_spaces_or_a_newline_digests_like_any_other(tmp_path):
    repo = _repo(tmp_path)
    clean = RD._verify_run_tree(str(repo))
    (repo / "a b.txt").write_text("1\n", encoding="utf-8")
    spaced = RD._verify_run_tree(str(repo))
    (repo / "c\nd.txt").write_text("2\n", encoding="utf-8")
    newline = RD._verify_run_tree(str(repo))
    assert isinstance(spaced, str) and isinstance(newline, str)
    assert len({clean, spaced, newline}) == 3


def test_5_an_untracked_symlink_digests_as_its_link_text_and_a_nested_repository_as_a_directory(tmp_path):
    repo = _repo(tmp_path)
    clean = RD._verify_run_tree(str(repo))
    os.symlink("f.txt", repo / "link")
    first = RD._verify_run_tree(str(repo))
    os.remove(repo / "link")
    os.symlink("elsewhere", repo / "link")
    second = RD._verify_run_tree(str(repo))
    assert len({clean, first, second}) == 3
    os.remove(repo / "link")
    os.symlink("dangling-target", repo / "dangling")
    assert isinstance(RD._verify_run_tree(str(repo)), str)
    os.remove(repo / "dangling")
    nested = repo / "nested"
    nested.mkdir()
    _git(nested, "init", "-q")
    (nested / "g.txt").write_text("g\n", encoding="utf-8")
    _git(nested, "add", "-A")
    _git(nested, "commit", "-q", "-m", "n")
    one = RD._verify_run_tree(str(repo))
    assert isinstance(one, str) and one != clean
    assert RD._verify_run_tree(str(repo)) == one


def test_4_a_tracked_edit_still_changes_the_digest(tmp_path):
    repo = _repo(tmp_path)
    clean = RD._verify_run_tree(str(repo))
    (repo / "f.txt").write_text("y\n", encoding="utf-8")
    assert RD._verify_run_tree(str(repo)) not in (None, clean)


def test_4_a_directory_that_is_not_a_repository_has_no_digest(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert RD._verify_run_tree(str(plain)) is None


@pytest.mark.parametrize("failing", ["diff", "ls-files"])
def test_4_either_git_call_failing_gives_no_digest(tmp_path, monkeypatch, failing):
    repo = _repo(tmp_path)
    real = subprocess.run

    def run(argv, **kw):
        if failing in argv:
            return subprocess.CompletedProcess(argv, 1, b"", b"boom")
        return real(argv, **kw)
    monkeypatch.setattr(RD.subprocess, "run", run)
    assert RD._verify_run_tree(str(repo)) is None


def test_4_an_untracked_file_that_cannot_be_read_gives_no_digest(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    real = subprocess.run

    def run(argv, **kw):
        done = real(argv, **kw)
        if "ls-files" in argv:
            return subprocess.CompletedProcess(argv, 0, done.stdout + b"vanished.txt\0", b"")
        return done
    monkeypatch.setattr(RD.subprocess, "run", run)
    assert RD._verify_run_tree(str(repo)) is None


# ---- through the real verb and advance --------------------------------------------------------

def _gate(tmp_path, command, repo):
    d = TA._session(tmp_path)
    TA._at_run_verify(tmp_path, d)
    state = TA._state(d)
    state["config"]["verifyCommand"] = command
    state["config"]["repoRoot"] = str(repo)
    RD.save_state(d, state)
    return d


def _run_and_advance(d, tmp_path, **kw):
    out = RD.cmd_run_verify(d, **kw)
    assert out["ok"] is True, out
    adv = TA._advance(d, tmp_path)
    assert adv["ok"] is True, adv
    return out


def _script(repo, body):
    path = repo / "verify.sh"
    path.write_text("#!/bin/bash\nn=$(cat \"$1\" 2>/dev/null || echo 0)\necho $((n + 1)) > \"$1\"\n" + body,
                    encoding="utf-8")
    path.chmod(0o755)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "script")


def test_an_untracked_file_added_between_the_runs_halts_a_passing_re_run(tmp_path, adapters):
    # axis: the digest covers untracked files that are not ignored
    repo = _repo(tmp_path)
    counter = tmp_path / "counter"
    _script(repo, "[ \"$n\" -ge 1 ]\n")
    d = _gate(tmp_path, "./verify.sh %s" % counter, repo)

    first = _run_and_advance(d, tmp_path)
    assert first["result"] == "fail"
    assert not TA._state(d).get("terminal")
    (repo / "appeared.txt").write_text("new\n", encoding="utf-8")
    second = _run_and_advance(d, tmp_path)
    assert second["result"] == "pass"

    end = TA._state(d)
    assert end["terminal"] == "halted"
    assert end["decisions"][-1]["kind"] == "verify-rerun-tree-changed"
    assert end["rounds"]["1"]["rerunChecks"][0]["decision"] == "tree-changed"


def test_a_first_run_that_creates_an_untracked_file_and_fails_halts_a_passing_re_run(tmp_path, adapters):
    # axis: the digest covers untracked files that are not ignored
    repo = _repo(tmp_path)
    counter = tmp_path / "counter"
    _script(repo, "[ \"$n\" -ge 1 ] || { echo made > made.txt; exit 1; }\n")
    d = _gate(tmp_path, "./verify.sh %s" % counter, repo)

    first = _run_and_advance(d, tmp_path)
    assert first["result"] == "fail"
    landed, err = RR.read_json(first["landingPath"])
    assert err is None and landed["treeSha"] != landed["treeShaAfter"]
    second = _run_and_advance(d, tmp_path)
    assert second["result"] == "pass"

    end = TA._state(d)
    assert end["terminal"] == "halted"
    assert end["decisions"][-1]["kind"] == "verify-rerun-tree-changed"


def test_ignored_build_output_written_by_each_run_still_goes_on(tmp_path, adapters):
    repo = _repo(tmp_path)
    counter = tmp_path / "counter"
    _script(repo, "mkdir -p build\necho \"run $n\" > build/out.txt\n[ \"$n\" -ge 1 ]\n")
    d = _gate(tmp_path, "./verify.sh %s" % counter, repo)

    assert _run_and_advance(d, tmp_path)["result"] == "fail"
    assert _run_and_advance(d, tmp_path)["result"] == "pass"

    end = TA._state(d)
    assert end["terminal"] != "halted"
    assert end["rounds"]["1"]["verifyResult"] == "pass"
    assert end["rounds"]["1"]["rerunChecks"][0]["decision"] == "went-on"


# =============================================================================================
# item 3: the verb records the digest, so a tracked edit between the runs is seen
# =============================================================================================

def test_3_a_tracked_file_edited_between_the_runs_halts_a_passing_re_run_and_the_landing_carries_tree_sha(
        tmp_path, adapters):
    # axis: the verb records treeSha on its landing
    repo = _repo(tmp_path)
    d = _gate(tmp_path, "make test", repo)

    first = _run_and_advance(d, tmp_path, run=TA._verb_run(1, b"fail\n"))
    assert first["result"] == "fail"
    (repo / "f.txt").write_text("edited, not committed\n", encoding="utf-8")
    second = _run_and_advance(d, tmp_path, run=TA._verb_run(0, b"pass\n"))
    assert second["result"] == "pass"

    landed, err = RR.read_json(second["landingPath"])
    assert err is None, err
    assert isinstance(landed["treeSha"], str) and landed["treeSha"]
    first_landed, err = RR.read_json(first["landingPath"])
    assert err is None and first_landed["treeSha"] != landed["treeSha"]
    end = TA._state(d)
    assert end["terminal"] == "halted"
    assert end["decisions"][-1]["kind"] == "verify-rerun-tree-changed"
    assert end["rounds"]["1"]["rerunChecks"][0]["decision"] == "tree-changed"


# =============================================================================================
# item 4: the cloud footer on a PATCH read-back
# =============================================================================================

FOOTER = cloud_builder.CLOUD_FOOTER


class _FooterGh(TPB._StatefulCloudGh):
    """The cloud egress: a PATCHed body that does not end with the footer gets it appended, `times` over."""

    def __init__(self, body, times=1, suffix=""):
        super().__init__(body)
        self.times, self.suffix = times, suffix

    def __call__(self, argv):
        done = super().__call__(argv)
        if argv[2:4] == ["-X", "PATCH"]:
            if not self.live.rstrip().endswith(FOOTER):
                self.live = self.live.rstrip("\n") + ("\n\n" + FOOTER) * self.times
            self.live += self.suffix
        return done


def test_4_a_footer_the_cloud_appends_to_the_patched_body_is_not_a_difference(tmp_path):
    # axis: the post-PATCH read-back is compared without one trailing cloud footer
    sd = TPB._staged_fixed(tmp_path)
    gh = _FooterGh(TPB.BODY)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
    assert gh.live.endswith(FOOTER) and gh.live != TPB.FIXED
    assert "copied its audited PR-body fix" in PBS.record_line(sd)
    assert "did not copy" not in PBS.record_line(sd)


def test_7_a_staged_body_that_already_ends_with_the_footer_publishes(tmp_path):
    fixed = TPB.FIXED + "\n" + FOOTER
    sd = TPB._staged_fixed(tmp_path, fixed=fixed)
    gh = _FooterGh(TPB.BODY)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
    assert gh.live.count(FOOTER) == 1


def test_7_two_footers_on_the_read_back_are_unverified_because_only_one_is_stripped(tmp_path):
    sd = TPB._staged_fixed(tmp_path)
    out = PBS.publish(sd, 7, runner=_FooterGh(TPB.BODY, times=2))
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")


def test_4_a_body_changed_in_any_other_way_is_still_unverified(tmp_path):
    sd = TPB._staged_fixed(tmp_path)
    out = PBS.publish(sd, 7, runner=_FooterGh(TPB.BODY, suffix="\nan edit made after the PATCH"))
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")


def test_7_a_read_back_that_fails_is_unverified_with_the_footer_strip_in_place(tmp_path):
    sd = TPB._staged_fixed(tmp_path)
    views = iter([TPB._Done(0, json.dumps({"body": TPB.BODY})), TPB._Done(1)])

    def runner(argv):
        return next(views) if argv[2:4] != ["-X", "PATCH"] else TPB._Done(0)
    out = PBS.publish(sd, 7, runner=runner)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")


def test_4_the_pre_patch_moved_checks_are_not_footer_tolerant(tmp_path):
    # the live body read before the PATCH is compared exactly as before: a footer on it is a moved body
    sd = TPB._staged_fixed(tmp_path)
    gh = _FooterGh(TPB.BODY + "\n\n" + FOOTER)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-moved")
    assert gh.live == TPB.BODY + "\n\n" + FOOTER
