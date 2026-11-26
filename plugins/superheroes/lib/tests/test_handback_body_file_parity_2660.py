"""#2660: every ``vet_slot.py handback`` path with a PR to read runs the same checks, in the same order, through one
function (``_handback_checks``): caught-up, the body markers, then (comments read once) leftovers, calibration
disclosures and costly-not-accepted. ``--body-file`` beside ``--pr`` and ``--repo`` checks the file's body through that
same function; ``--body-file`` alone has no PR to read, runs the body checks and says which three checks it did not run.
No real gh: every call is faked.

Bite-proof record: i2660_handback_one_check_set
"""
import json
import os
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import test_calibration_disclosure_2364 as C  # noqa: E402
import test_handback_costly_unlisted_2633 as K  # noqa: E402
import test_vet_slot_leftovers_2280 as L  # noqa: E402
import vet_slot as vs  # noqa: E402

REPO = "owner/example"
PR = 42
PULL = ["gh", "api", "repos/owner/example/pulls/42"]
COMMENTS = "repos/owner/example/issues/42/comments?per_page=100&page="
NOT_RUN = list(vs.HANDBACK_PR_CHECKS)  # the one home of the skipped-check names; never restated here
FOLLOWUPS_LINE = "<!-- superheroes:followups none -->\n"


class Gh:
    """One fake gh: the PR REST read, the compare read, the paginated comments read. Every call is recorded; any other
    argv raises."""

    def __init__(self, rest_body, comments=(), base_ref="main", default="main", behind=0, pr_fails=False,
                 comments_fail=False):
        self.rest_body, self.comments, self.calls = rest_body, list(comments), []
        self.base_ref, self.default, self.behind = base_ref, default, behind
        self.pr_fails, self.comments_fail = pr_fails, comments_fail

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        if list(argv) == PULL:
            if self.pr_fails:
                return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 502")
            payload = {"body": self.rest_body, "base": {"ref": self.base_ref, "repo": {"default_branch": self.default}},
                       "head": {"sha": "a" * 40}}
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")
        if argv[:2] == ["gh", "api"] and "/compare/" in argv[2]:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"behind_by": self.behind}), stderr="")
        if argv[:2] == ["gh", "api"] and argv[2].startswith(COMMENTS):
            if self.comments_fail:
                return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 500")
            page = int(argv[2].rsplit("=", 1)[1])
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.comments[(page - 1) * 100:page * 100]),
                                   stderr="")
        raise AssertionError("unexpected argv %r" % (argv,))

    def comment_reads(self):
        return [c for c in self.calls if len(c) > 2 and "/comments?" in c[2]]

    def compare_reads(self):
        return [c for c in self.calls if len(c) > 2 and "/compare/" in c[2]]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _go(capsys, argv, fake):
    rc = vs.main(argv, run=fake)
    return rc, json.loads(capsys.readouterr().out)


def _file(tmp_path, text):
    path = tmp_path / "body.md"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _pr_argv():
    return ["handback", "--pr", str(PR), "--repo", REPO]


def _combined_argv(path):
    return _pr_argv() + ["--body-file", path]


def _no_followups(text):
    assert FOLLOWUPS_LINE in text
    return text.replace(FOLLOWUPS_LINE, "")


HEALTHY = L.body(L.ACCEPT_ONLY_F1)  # accepts f-1 by id and title
LEAVES_F1 = [L.record_comment([L.F1])]
FAILS_LEFTOVER = L.body("None\n")  # the record leaves f-1, this body names nothing
MARKERS_INVALID = _no_followups(HEALTHY)
CAL_RECORD = [C.record_comment([C.row(C.CODE1), C.row(C.SEC1)])]
CAL_CONTRADICTED = C.bullet(C.mark(C.CODE1, "core.md"))  # the record grades CODE1 as having read core.md


def _both(capsys, tmp_path, file_text, rest_body, pr_path_body, comments, **gh):
    """The combined form (REST body ``rest_body``, file ``file_text``) and the --pr path (REST body ``pr_path_body``)."""
    fake_c = Gh(rest_body, comments, **gh)
    combined = _go(capsys, _combined_argv(_file(tmp_path, file_text)), fake_c)
    fake_p = Gh(pr_path_body, comments, **gh)
    pr_path = _go(capsys, _pr_argv(), fake_p)
    return combined, pr_path, fake_c, fake_p


# --- row 1: caught-up --------------------------------------------------------------------------------------------

def test_row1_a_stacked_head_behind_refuses_on_the_combined_form_as_on_the_pr_path(capsys, tmp_path):
    (rc_c, out_c), (rc_p, out_p), fake_c, _ = _both(capsys, tmp_path, HEALTHY, HEALTHY, HEALTHY, LEAVES_F1,
                                                    base_ref="lower", behind=2)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["ok"] is False and out_c["reason"] == vs.REASON_STACK_NOT_CAUGHT_UP == "stack-not-caught-up"
    assert out_c == out_p
    assert fake_c.comment_reads() == [] and len(fake_c.compare_reads()) == 1


# --- row 2: caught-up before the body is read (BRIEF-2) ------------------------------------------------------------

def test_row2_caught_up_runs_before_the_body_even_when_the_rest_body_is_not_a_string(capsys, tmp_path):
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, HEALTHY, 5, 5, LEAVES_F1, base_ref="lower",
                                               behind=2)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["reason"] == "stack-not-caught-up"
    assert out_c == out_p


# --- row 3: leftovers ----------------------------------------------------------------------------------------------

def test_row3_a_file_body_that_leaves_a_finding_unaccepted_refuses_leftover_not_accepted(capsys, tmp_path):
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, FAILS_LEFTOVER, HEALTHY, FAILS_LEFTOVER, LEAVES_F1)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["ok"] is False and out_c["reason"] == "leftover-not-accepted"
    assert out_c == out_p


# --- row 4: calibration --------------------------------------------------------------------------------------------

def test_row4_a_file_body_with_a_contradicted_calibration_marker_refuses(capsys, tmp_path):
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, CAL_CONTRADICTED, C.body(None), CAL_CONTRADICTED,
                                               CAL_RECORD)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["ok"] is False and out_c["reason"] == "calibration-disclosure-contradicted"
    assert out_c == out_p


# --- row 5: the order of the two record checks ---------------------------------------------------------------------

def test_row5_leftovers_refuse_before_calibration_on_both_paths(capsys, tmp_path):
    both_failing = C.bullet(C.mark(C.CODE1, "core.md"))  # accepts the bullet's text, never names f-1
    record = [C.record_comment([C.row(C.CODE1), C.row(C.SEC1)], findings=[L.F1], left=["f-1"])]
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, both_failing, C.body(None), both_failing, record)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["reason"] == "leftover-not-accepted"
    assert out_c == out_p


# --- row 5b: costly-not-accepted reads the file's body, last ------------------------------------------------------

def test_row5b_a_file_body_with_an_unlisted_costly_degradation_refuses_costly_not_accepted(capsys, tmp_path):
    # Bites on: the combined form passing the REST body, not the file's, to check_costly_accepted.
    costly, clean = K.REFUSED["costly"], K.PASSED["no-degradations"]
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, costly, clean, costly, CAL_RECORD)
    assert (rc_c, rc_p) == (1, 1)
    assert out_c["ok"] is False and out_c["reason"] == "costly-not-accepted"
    assert out_c == out_p


# --- row 6: a healthy file beside an unhealthy REST body -----------------------------------------------------------

def test_row6_a_healthy_file_passes_whatever_the_rest_body_says(capsys, tmp_path):
    (rc_c, out_c), (rc_p, out_p), _, _ = _both(capsys, tmp_path, HEALTHY, MARKERS_INVALID, HEALTHY, LEAVES_F1)
    assert (rc_c, rc_p) == (0, 0)
    assert out_c["ok"] is True and "notRun" not in out_c
    assert out_c == out_p == {"ok": True, "verb": "handback", "followups": []}


# --- row 7: a marker refusal in the file reads no comments ---------------------------------------------------------

def test_row7_a_marker_refusal_in_the_file_is_that_refusal_and_reads_no_comments(capsys, tmp_path):
    fake = Gh(HEALTHY, LEAVES_F1)
    rc, out = _go(capsys, _combined_argv(_file(tmp_path, MARKERS_INVALID)), fake)
    assert rc == 1 and out["ok"] is False and out["reason"] == "markers-invalid"
    assert fake.calls == [PULL] and fake.comment_reads() == []


# --- row 8: the file-only form -------------------------------------------------------------------------------------

def test_row8_file_only_pass_says_which_three_checks_it_did_not_run(capsys, tmp_path):
    fake = Gh(HEALTHY)
    rc, out = _go(capsys, ["handback", "--body-file", _file(tmp_path, HEALTHY)], fake)
    assert rc == 0
    assert out == {"ok": True, "verb": "handback", "followups": [], "notRun": NOT_RUN}
    assert fake.calls == []


def test_row8_file_only_refusal_carries_no_not_run_key(capsys, tmp_path):
    fake = Gh(HEALTHY)
    rc, out = _go(capsys, ["handback", "--body-file", _file(tmp_path, MARKERS_INVALID)], fake)
    assert rc == 1 and out["ok"] is False and out["reason"] == "markers-invalid"
    assert "notRun" not in out and fake.calls == []


# --- row 9: the fail-closed edges ----------------------------------------------------------------------------------

@pytest.mark.parametrize("extra", [["--pr", str(PR)], ["--repo", REPO]], ids=["only-pr", "only-repo"])
def test_E_a_body_file_with_only_one_of_pr_and_repo_is_bad_argument_with_no_gh_call(capsys, tmp_path, extra):
    fake = Gh(HEALTHY, LEAVES_F1)
    rc, out = _go(capsys, ["handback", "--body-file", _file(tmp_path, HEALTHY)] + extra, fake)
    assert rc == 1 and out["ok"] is False and out["reason"] == "bad-argument"
    assert fake.calls == []


@pytest.mark.parametrize("verb, slot_file", [("check", None), ("write", "slot.md"), ("handback", "slot.md")])
def test_E_b_body_file_beside_check_write_or_a_slot_file_is_bad_argument(tmp_path, verb, slot_file):
    fake = Gh(HEALTHY, LEAVES_F1)
    result = vs.run_verb(verb, PR, REPO, slot_file=slot_file, run=fake, body_file=_file(tmp_path, HEALTHY))
    assert result["ok"] is False and result["reason"] == "bad-argument"
    assert fake.calls == []


@pytest.mark.parametrize("pr, repo", [(0, REPO), (-3, REPO), (PR, "no-slash"), (PR, "a/b/c")])
def test_E_c_a_bad_pr_or_repo_on_the_combined_form_is_bad_argument(tmp_path, pr, repo):
    fake = Gh(HEALTHY, LEAVES_F1)
    result = vs.run_verb("handback", pr, repo, run=fake, body_file=_file(tmp_path, HEALTHY))
    assert result["ok"] is False and result["reason"] == "bad-argument"
    assert fake.calls == []


def test_E_d_the_combined_form_without_gh_on_path_is_read_failed(capsys, tmp_path, monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: None)
    fake = Gh(HEALTHY, LEAVES_F1)
    rc, out = _go(capsys, _combined_argv(_file(tmp_path, HEALTHY)), fake)
    assert rc == 1 and out["reason"] == "read-failed" and out["detail"] == "gh not on PATH"
    assert fake.calls == []


def test_E_e_a_failed_pr_read_is_read_failed_before_the_file_is_read(capsys, tmp_path):
    fake = Gh(HEALTHY, LEAVES_F1, pr_fails=True)
    rc, out = _go(capsys, _combined_argv(str(tmp_path / "absent.md")), fake)
    assert rc == 1 and out["reason"] == "read-failed"
    assert "body file unreadable" not in out["detail"] and out["detail"].startswith("PR body: exit 1")
    assert fake.calls == [PULL]


def test_E_g_an_unreadable_body_file_is_read_failed_after_the_pr_read_and_the_catch_up(capsys, tmp_path):
    fake = Gh(HEALTHY, LEAVES_F1, base_ref="lower", behind=0)
    rc, out = _go(capsys, _combined_argv(str(tmp_path / "absent.md")), fake)
    assert rc == 1 and out["reason"] == "read-failed" and "body file unreadable" in out["detail"]
    assert fake.calls[0] == PULL and len(fake.compare_reads()) == 1 and fake.calls[1] == fake.compare_reads()[0]
    assert len(fake.calls) == 2 and fake.comment_reads() == []


def test_E_g_a_file_that_is_not_utf_8_is_unreadable_too(capsys, tmp_path):
    path = tmp_path / "body.md"
    path.write_bytes(b"\xff\xfe\x00bad")
    rc, out = _go(capsys, _combined_argv(str(path)), Gh(HEALTHY, LEAVES_F1))
    assert rc == 1 and out["reason"] == "read-failed" and "body file unreadable" in out["detail"]


def test_E_i_a_failed_comments_read_is_read_failed(capsys, tmp_path):
    fake = Gh(HEALTHY, LEAVES_F1, comments_fail=True)
    rc, out = _go(capsys, _combined_argv(_file(tmp_path, HEALTHY)), fake)
    assert rc == 1 and out["reason"] == "read-failed" and "comments" in out["detail"]
    assert len(fake.comment_reads()) == 1


def test_E_j_an_unreadable_review_record_refuses_review_record_unreadable(capsys, tmp_path):
    fake = Gh(HEALTHY, [L.comment("chatter")])
    rc, out = _go(capsys, _combined_argv(_file(tmp_path, HEALTHY)), fake)
    assert rc == 1 and out["reason"] == "review-record-unreadable"
