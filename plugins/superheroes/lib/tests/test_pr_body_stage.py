"""#2083: a review finding about the PR body is fixed in a staged copy inside the review session,
audited there, and copied onto the PR only by `pr_body_stage.publish`, which publishes only bytes an
audit discharged and never overwrites a live body that moved. The build session never writes to GitHub.

Bite-proof record: wo_pr_body_stage_2083
"""
import hashlib
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pr_body_stage as PBS  # noqa: E402
import record_paths  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_orders as RO  # noqa: E402
import round_phases as RP  # noqa: E402
import round_records as RR  # noqa: E402
import sanitized_view  # noqa: E402
import test_review_record_refusals as TRF  # noqa: E402
import test_review_record_session as TRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_orders as TRO  # noqa: E402

RD = TRD.RD

MARKER = "<!-- superheroes:build-record -->"
BODY = (
    "## Summary\nAdds the retry budget to the sync client.\n\n"
    "## Test answers\n"
    "- `test_retry_stops_at_budget` Protects:\n"
    "- `test_retry_resets_on_success` Fails on:\n"
    "- `test_retry_backoff_is_capped`\n\n"
    + MARKER + "\n"
)
FIXED = (
    "## Summary\nAdds the retry budget to the sync client.\n\n"
    "## Test answers\n"
    "- `test_retry_stops_at_budget` Protects: a runaway retry loop. Fails on: a budget of zero.\n"
    "- `test_retry_resets_on_success` Protects: the budget after a success. Fails on: a counter never reset.\n"
    "- `test_retry_backoff_is_capped` Protects: the wait ceiling. Fails on: an uncapped backoff.\n\n"
    + MARKER + "\n"
)
CONSEQUENCE = "the PR body leaves the test answers unstated, so a reviewer cannot tell what the tests protect"


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _session(tmp_path, body=BODY, mode="pr", pr_json=True):
    sd = str(tmp_path / "session")
    os.makedirs(sd)
    _write(os.path.join(sd, RR.META_FILE),
           json.dumps({"mode": mode, "repo": "acme/widget", "branch": "feature/retry",
                       "repoRoot": str(tmp_path)}))
    if pr_json:
        _write(os.path.join(sd, "pr.json"), json.dumps({"number": 7, "body": body}))
    return sd


def _converge(sd, verdict="converged", audited=None):
    """Write the terminal receipt and the loop state; `audited` maps round -> the sha it recorded."""
    _write(os.path.join(sd, "round-receipt.json"), json.dumps({"verdict": verdict}))
    rounds = {str(n): {"prBodyAudited": s} for n, s in (audited or {}).items()}
    _write(os.path.join(sd, "loop-state.json"), json.dumps({"rounds": rounds}))


def _staged_fixed(tmp_path, fixed=FIXED, audited=True, **kw):
    """A converged session whose staged copy holds `fixed`, audited unless told otherwise."""
    sd = _session(tmp_path, **kw)
    assert PBS.stage(sd)["ok"]
    _write(PBS.paths(sd)["staged"], fixed)
    _converge(sd, audited={1: sha(fixed)} if audited else None)
    return sd


class _Done:
    def __init__(self, returncode, stdout=""):
        self.returncode, self.stdout = returncode, stdout


def read_argv(pr=7):
    return ["gh", "api", "repos/{owner}/{repo}/pulls/%s" % pr]


def edit_argv(staged, pr=7):
    return ["gh", "api", "-X", "PATCH", "repos/{owner}/{repo}/pulls/%s" % pr, "-F", "body=@%s" % staged]


class FakeGh:
    """A `gh` runner double over the REST API: `views` are the bodies successive pull reads return
    (the last repeats), `edit_rc` is the PATCH exit code. Any `gh` call that is not `gh api` fails."""

    def __init__(self, views=(), edit_rc=0, view_rc=0, view_raw=None, boom=False):
        self.calls, self.views = [], list(views)
        self.edit_rc, self.view_rc, self.view_raw, self.boom = edit_rc, view_rc, view_raw, boom

    def __call__(self, argv):
        self.calls.append(list(argv))
        if self.boom:
            raise OSError("gh is not installed")
        if argv[:2] != ["gh", "api"]:
            raise AssertionError("unexpected gh call: %r" % (argv,))
        if argv[2:4] == ["-X", "PATCH"]:
            return _Done(self.edit_rc)
        if len(argv) == 3 and argv[2].startswith("repos/{owner}/{repo}/pulls/"):
            if self.view_rc:
                return _Done(self.view_rc)
            if self.view_raw is not None:
                return _Done(0, self.view_raw)
            body = self.views.pop(0) if len(self.views) > 1 else self.views[0]
            return _Done(0, json.dumps({"body": body, "number": 7}))
        raise AssertionError("unexpected gh call: %r" % (argv,))

    def edits(self):
        return [c for c in self.calls if c[2:4] == ["-X", "PATCH"]]


def _receipt(sd):
    return json.loads(_read(PBS.paths(sd)["published"]))


# ---- constants ---------------------------------------------------------------------------------

def test_the_citation_is_the_name_the_sanitized_view_gives_the_pr_body():
    assert PBS.CITATION == sanitized_view.PR_BODY_FILE_NAME == "SUPERHEROES_PR_BODY.md"


def test_the_fixer_copy_lives_in_the_fixer_landing_dir_under_the_reserved_prefix(tmp_path):
    sd = _session(tmp_path)
    path = PBS.fixer_copy_path(sd, 2)
    assert path == os.path.join(record_paths.landing_dir(sd, 2, PBS.FIXER_PHASE), "_pr-body.md")
    assert os.path.basename(path).startswith(record_paths.RESERVED_PREFIX)


# ---- compile -----------------------------------------------------------------------------------

def _pr_body_finding(**over):
    f = {"title": "Test answers are incomplete", "severity": "Important", "file": PBS.CITATION,
         "line": 4, "consequence": CONSEQUENCE, "dimension": "Docs"}
    f.update(over)
    return f


def test_a_finding_citing_the_pr_body_passes_compile_against_a_diff_that_does_not_hold_it():
    # axis: the PR body is never in the git diff, so the scope check must exempt its citation
    compiled, drops = RD.mechanical_compile([_pr_body_finding()], TRD.DIFF)
    assert [c["file"] for c in compiled] == [PBS.CITATION] and drops == []


def test_a_finding_citing_another_file_outside_the_diff_is_still_dropped():
    compiled, drops = RD.mechanical_compile([_pr_body_finding(file="docs/NOTES.md")], TRD.DIFF)
    assert compiled == [] and drops[0]["reason"] == "outside the round diff scope"


# ---- stage (E1-E3) -----------------------------------------------------------------------------

def test_E1_branch_mode_without_pr_json_stages_nothing(tmp_path):
    sd = _session(tmp_path, mode="branch", pr_json=False)
    assert PBS.stage(sd) == {"ok": True, "staged": False, "reason": "no-pr"}
    assert not os.path.exists(os.path.join(sd, "pr-body"))


def test_stage_writes_original_and_staged_from_the_pr_body(tmp_path):
    sd = _session(tmp_path)
    out = PBS.stage(sd)
    p = PBS.paths(sd)
    assert out["ok"] and out["staged"] and out["reason"] is None
    assert (out["originalPath"], out["stagedPath"]) == (p["original"], p["staged"])
    assert out["stagedSha256"] == sha(BODY) and _read(p["original"]) == _read(p["staged"]) == BODY
    assert os.path.isabs(out["stagedPath"])


@pytest.mark.parametrize("raw,reason", [
    ("{not json", "pr-json-unparseable"),
    ("[1, 2]", "pr-json-unparseable"),
    ('{"number": 7}', "pr-body-not-text"),
    ('{"body": null}', "pr-body-not-text"),
    ('{"body": 12}', "pr-body-not-text"),
    (None, "pr-json-unreadable"),
])
def test_E2_a_pr_json_that_cannot_give_a_text_body_is_a_named_refusal_with_no_file(tmp_path, raw, reason):
    sd = _session(tmp_path, pr_json=False)
    if raw is None:
        os.makedirs(os.path.join(sd, "pr.json"))  # present but not readable as a file
    else:
        _write(os.path.join(sd, "pr.json"), raw)
    out = PBS.stage(sd)
    assert out["ok"] is False and out["reason"] == reason and out["staged"] is False
    assert not os.path.exists(os.path.join(sd, "pr-body", "staged.md"))
    assert not os.path.exists(os.path.join(sd, "pr-body", "original.md"))


def test_E3_a_second_stage_overwrites_neither_file(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    p = PBS.paths(sd)
    _write(p["staged"], FIXED)
    _write(os.path.join(sd, "pr.json"), json.dumps({"body": "someone edited the PR meanwhile"}))
    out = PBS.stage(sd)
    assert out["ok"] and out["stagedSha256"] == sha(FIXED) and out["originalSha256"] == sha(BODY)
    assert _read(p["staged"]) == FIXED and _read(p["original"]) == BODY


# ---- the fixer's copy (E4, E5) -----------------------------------------------------------------

def test_seed_copies_staged_once_and_reports_the_before_sha(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    assert PBS.seed_fixer_copy(sd, 1) == sha(BODY)
    copy = PBS.fixer_copy_path(sd, 1)
    assert _read(copy) == BODY
    _write(copy, FIXED)  # the fixer's edit survives a second seeding
    assert PBS.seed_fixer_copy(sd, 1) == sha(BODY)
    assert _read(copy) == FIXED


def test_seed_with_nothing_staged_creates_no_copy(tmp_path):
    sd = _session(tmp_path)
    assert PBS.seed_fixer_copy(sd, 1) is None
    assert not os.path.exists(PBS.fixer_copy_path(sd, 1))


def test_collect_replaces_staged_with_the_fixer_copy_and_returns_its_sha(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    PBS.seed_fixer_copy(sd, 1)
    _write(PBS.fixer_copy_path(sd, 1), FIXED)
    assert PBS.collect_fixer_copy(sd, 1) == sha(FIXED)
    assert _read(PBS.paths(sd)["staged"]) == FIXED and _read(PBS.paths(sd)["original"]) == BODY


def test_E4_an_absent_fixer_copy_changes_nothing(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    assert PBS.collect_fixer_copy(sd, 1) is None
    assert _read(PBS.paths(sd)["staged"]) == BODY
    assert PBS.collect_fixer_copy(_session(tmp_path / "other"), 1) is None  # nothing staged either


# ---- publish (E6-E15) --------------------------------------------------------------------------

def test_publish_copies_the_audited_staged_body_with_exactly_two_reads_and_one_patch(tmp_path):
    # axis: every GitHub call goes through the REST API, never `gh pr view` or `gh pr edit` — see
    # bite-proof record c1l9a_wo2_pr_body_rest
    sd = _staged_fixed(tmp_path)
    gh = FakeGh(views=[BODY, FIXED])
    out = PBS.publish(sd, 7, runner=gh)
    staged = PBS.paths(sd)["staged"]
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
    assert gh.calls == [["gh", "api", "repos/{owner}/{repo}/pulls/7"],
                        ["gh", "api", "-X", "PATCH", "repos/{owner}/{repo}/pulls/7",
                         "-F", "body=@%s" % staged],
                        ["gh", "api", "repos/{owner}/{repo}/pulls/7"]]
    assert gh.calls[0] == read_argv() and gh.calls[1] == edit_argv(staged)
    assert not [c for c in gh.calls if c[:2] == ["gh", "pr"]]
    assert os.path.isabs(staged)
    assert _receipt(sd) == out
    assert out["schema"] == "pr-body-publish/1" and out["pr"] == 7
    assert (out["originalSha256"], out["stagedSha256"], out["liveSha256"]) == (sha(BODY), sha(FIXED), sha(BODY))
    assert out["at"].endswith("Z")


class _StatefulCloudGh:
    """A cloud-shaped `gh` double that holds the live PR body: a pulls read returns it, a PATCH must carry
    `-F body=@<path>` and makes that file's text the live body. Anything that is not `gh api` (the GraphQL
    commands `gh pr view` / `gh pr edit`) is an assertion error."""

    def __init__(self, body):
        self.live, self.calls = body, []

    def __call__(self, argv):
        self.calls.append(list(argv))
        if argv[:2] != ["gh", "api"]:
            raise AssertionError("unexpected gh call: %r" % (argv,))
        if argv[2:4] == ["-X", "PATCH"]:
            assert argv[5] == "-F" and argv[6].startswith("body=@") and len(argv) == 7, argv
            self.live = _read(argv[6][len("body=@"):])
            return _Done(0)
        if len(argv) == 3 and argv[2].startswith("repos/{owner}/{repo}/pulls/"):
            return _Done(0, json.dumps({"body": self.live, "number": 7}))
        raise AssertionError("unexpected gh call: %r" % (argv,))


def test_a_staged_fix_publishes_through_rest_against_a_stateful_cloud_shaped_gh(tmp_path):
    sd = _staged_fixed(tmp_path)
    gh = _StatefulCloudGh(BODY)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "published", None)
    assert gh.live == FIXED
    assert gh.calls[0] == read_argv() and gh.calls[1] == edit_argv(PBS.paths(sd)["staged"])
    assert not [c for c in gh.calls if c[:2] == ["gh", "pr"]]
    assert "did not copy" not in (PBS.record_line(sd) or "")


@pytest.mark.parametrize("verdict", [None, "halted", "held", "stalled", "cannot-certify"])
def test_E6_publish_before_a_converged_terminal_refuses_without_calling_gh(tmp_path, verdict):
    sd = _staged_fixed(tmp_path)
    os.remove(os.path.join(sd, "round-receipt.json"))
    if verdict:
        _converge(sd, verdict=verdict, audited={1: sha(FIXED)})
    gh = FakeGh(views=[BODY])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (False, "refused", "review-not-converged")
    assert gh.calls == [] and _receipt(sd)["reason"] == "review-not-converged"


def test_E7_publish_with_nothing_staged_refuses_without_calling_gh(tmp_path):
    sd = _session(tmp_path)
    _converge(sd)
    gh = FakeGh(views=[BODY])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-not-staged")
    assert gh.calls == [] and _receipt(sd)["reason"] == "pr-body-not-staged"


@pytest.mark.parametrize("gh", [
    FakeGh(view_rc=1), FakeGh(view_raw="not json"), FakeGh(view_raw=json.dumps({"body": 5})),
    FakeGh(view_raw=json.dumps(["x"])), FakeGh(boom=True),
], ids=["nonzero", "bad-json", "body-not-string", "not-an-object", "runner-raises"])
def test_E8_an_unreadable_live_body_refuses_and_never_edits(tmp_path, gh):
    sd = _staged_fixed(tmp_path)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-live-unreadable")
    assert gh.edits() == [] and _receipt(sd)["reason"] == "pr-body-live-unreadable"


def test_E9_staged_equal_to_original_with_the_live_body_unchanged_copies_nothing(tmp_path):
    sd = _staged_fixed(tmp_path, fixed=BODY, audited=False)
    gh = FakeGh(views=[BODY])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "unchanged", None)
    assert gh.edits() == []


def test_E9_staged_equal_to_original_with_the_live_body_moved_says_so_and_copies_nothing(tmp_path):
    sd = _staged_fixed(tmp_path, fixed=BODY, audited=False)
    gh = FakeGh(views=["a human rewrote the description"])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (True, "unchanged", "live-moved")
    assert gh.edits() == []


@pytest.mark.parametrize("audited", [
    pytest.param(None, id="none-recorded"),
    pytest.param({1: "0" * 64}, id="a-different-sha"),
    pytest.param({1: sha(FIXED), 2: sha(BODY)}, id="the-highest-round-governs"),
])
def test_E10_a_staged_body_that_is_not_the_audited_one_is_refused(tmp_path, audited):
    # axis: the audited-sha rule — see bite-proof record wo_pr_body_stage_2083
    sd = _staged_fixed(tmp_path, audited=False)
    _converge(sd, audited=audited)
    gh = FakeGh(views=[BODY])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-not-audited")
    assert gh.edits() == []


def test_E10_a_staged_body_edited_after_its_audit_is_refused(tmp_path):
    sd = _staged_fixed(tmp_path)
    _write(PBS.paths(sd)["staged"], FIXED + "one more line\n")
    gh = FakeGh(views=[BODY])
    assert PBS.publish(sd, 7, runner=gh)["reason"] == "pr-body-not-audited"
    assert gh.edits() == []


def test_the_highest_numbered_audited_round_is_the_one_that_counts(tmp_path):
    sd = _staged_fixed(tmp_path, audited=False)
    _converge(sd, audited={1: "0" * 64, 2: sha(FIXED)})
    out = PBS.publish(sd, 7, runner=FakeGh(views=[BODY, FIXED]))
    assert out["outcome"] == "published"


def test_E11_a_live_body_that_moved_since_the_original_is_never_overwritten(tmp_path):
    # axis: a live body that moved is never overwritten — see bite-proof record wo_pr_body_stage_2083
    sd = _staged_fixed(tmp_path)
    gh = FakeGh(views=["someone ran gh pr edit and wrote this"])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-moved")
    assert gh.edits() == []


def test_E12_a_failing_edit_is_refused(tmp_path):
    sd = _staged_fixed(tmp_path)
    gh = FakeGh(views=[BODY], edit_rc=1)
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-failed")
    assert len(gh.edits()) == 1


@pytest.mark.parametrize("readback", [BODY, "something else"])
def test_E13_a_readback_that_is_not_the_staged_body_is_refused(tmp_path, readback):
    sd = _staged_fixed(tmp_path)
    out = PBS.publish(sd, 7, runner=FakeGh(views=[BODY, readback]))
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")


def test_E13_a_readback_that_fails_is_refused(tmp_path):
    sd = _staged_fixed(tmp_path)
    views = iter([_Done(0, json.dumps({"body": BODY})), _Done(1)])

    def runner(argv):
        return next(views) if argv[2:4] != ["-X", "PATCH"] else _Done(0)
    out = PBS.publish(sd, 7, runner=runner)
    assert (out["ok"], out["reason"]) == (False, "pr-body-publish-unverified")


def test_E14_a_second_publish_after_success_edits_nothing_and_keeps_the_first_time(tmp_path):
    # axis: the already-published branch — see bite-proof record wo_pr_body_stage_2083
    sd = _staged_fixed(tmp_path)
    first = PBS.publish(sd, 7, runner=FakeGh(views=[BODY, FIXED]))
    gh = FakeGh(views=[FIXED])
    again = PBS.publish(sd, 7, runner=gh)
    assert (again["ok"], again["outcome"], again["reason"]) == (True, "published", "already-published")
    assert again["at"] == first["at"] and gh.edits() == []


def test_E14_a_live_body_matching_the_staged_text_without_a_recorded_copy_is_refused(tmp_path):
    sd = _staged_fixed(tmp_path)
    gh = FakeGh(views=[FIXED])  # live holds the audited text, but no receipt says the review copied it
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"], out["reason"]) == (False, "refused", "pr-body-moved")
    assert gh.edits() == []


def test_a_live_body_holding_unaudited_staged_text_is_refused_not_adopted(tmp_path):
    sd = _staged_fixed(tmp_path, audited=False)
    gh = FakeGh(views=[FIXED])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-body-published-unaudited")
    assert gh.edits() == []


def test_E15_a_trailing_newline_alone_is_not_a_difference(tmp_path):
    sd = _staged_fixed(tmp_path)
    stripped = BODY.rstrip("\n")
    out = PBS.publish(sd, 7, runner=FakeGh(views=[stripped, FIXED.rstrip("\n")]))
    assert (out["ok"], out["outcome"]) == (True, "published")


@pytest.mark.parametrize("pr", [None, "", "abc", "-7", 0, True, "7 --repo x"])
def test_an_unusable_pr_number_never_reaches_gh(tmp_path, pr):
    sd = _staged_fixed(tmp_path)
    gh = FakeGh(views=[BODY])
    out = PBS.publish(sd, pr, runner=gh)
    assert (out["ok"], out["reason"]) == (False, "pr-number-invalid") and gh.calls == []


def test_the_default_runner_calls_gh_with_an_argv_list(tmp_path, monkeypatch):
    seen = []

    def fake_run(argv, **kwargs):
        seen.append((argv, kwargs))
        return _Done(1)
    monkeypatch.setattr(PBS.subprocess, "run", fake_run)
    sd = _staged_fixed(tmp_path)
    assert PBS.publish(sd, 7)["reason"] == "pr-body-live-unreadable"
    argv, kwargs = seen[0]
    assert argv == read_argv() and not kwargs.get("shell")


# ---- the review account's line -----------------------------------------------------------------

@pytest.mark.parametrize("receipt,expected", [
    ({"outcome": "published", "reason": None}, "The review copied its audited PR-body fix onto the PR."),
    ({"outcome": "published", "reason": "already-published"},
     "The review copied its audited PR-body fix onto the PR."),
    ({"outcome": "unchanged", "reason": None}, None),
    ({"outcome": "unchanged", "reason": "live-moved"},
     "The PR body changed on GitHub during the review, outside the review; the review had no PR-body fix to copy."),
    ({"outcome": "refused", "reason": "pr-body-moved"},
     "The review did not copy its PR-body fix onto the PR: the live body changed during the review, outside "
     "the review, so the review would not overwrite it."),
    ({"outcome": "refused", "reason": "pr-body-not-audited"},
     "The review did not copy its PR-body fix onto the PR: the staged PR-body text is not the text an audit cleared."),
])
def test_record_line_reads_the_receipt_in_plain_words(tmp_path, receipt, expected):
    sd = _staged_fixed(tmp_path)  # a staged copy that differs from the original: there is a fix to copy
    _write(PBS.paths(sd)["published"], json.dumps(receipt))
    assert PBS.record_line(sd) == expected


def test_record_line_is_none_without_a_readable_receipt(tmp_path):
    sd = _session(tmp_path)
    assert PBS.record_line(sd) is None
    _write(PBS.paths(sd)["published"], "{nope")
    assert PBS.record_line(sd) is None


def _no_fix_session(tmp_path, how):
    """A session with no PR-body fix to copy: nothing staged, one file missing, or staged == original."""
    if how == "nothing-staged":
        return _session(tmp_path)
    sd = _staged_fixed(tmp_path, fixed=BODY, audited=False)
    if how == "staged-missing":
        os.remove(PBS.paths(sd)["staged"])
    elif how == "original-missing":
        os.remove(PBS.paths(sd)["original"])
    elif how == "trailing-newline-only":
        _write(PBS.paths(sd)["staged"], BODY.rstrip("\n"))
    return sd


@pytest.mark.parametrize("how", ["nothing-staged", "staged-missing", "original-missing",
                                 "staged-equals-original", "trailing-newline-only"])
@pytest.mark.parametrize("reason", sorted(PBS._REFUSAL_PHRASES))
def test_a_review_with_no_pr_body_fix_never_says_it_did_not_copy_one(tmp_path, how, reason):
    # axis: the no-fix guard in record_line, whatever the refusal reason — see bite-proof record
    # c1l9a_wo2_pr_body_rest
    sd = _no_fix_session(tmp_path, how)
    _write(PBS.paths(sd)["published"], json.dumps({"outcome": "refused", "reason": reason}))
    assert PBS.record_line(sd) is None


def test_publish_with_nothing_staged_before_convergence_leaves_no_did_not_copy_line(tmp_path):
    sd = _session(tmp_path)
    _write(os.path.join(sd, "round-receipt.json"), json.dumps({"verdict": "halted"}))
    out = PBS.publish(sd, 7, runner=FakeGh(views=[BODY]))
    assert out["reason"] == "review-not-converged"
    assert PBS.record_line(sd) is None


def test_an_unchanged_body_that_moved_on_github_keeps_its_own_sentence_with_no_fix(tmp_path):
    sd = _no_fix_session(tmp_path, "staged-equals-original")
    _write(PBS.paths(sd)["published"], json.dumps({"outcome": "unchanged", "reason": "live-moved"}))
    line = PBS.record_line(sd)
    assert line == ("The PR body changed on GitHub during the review, outside the review; the review "
                    "had no PR-body fix to copy.")
    assert not line.startswith("The review did not copy its PR-body fix")


@pytest.mark.parametrize("reason", ["review-not-converged", "pr-body-moved", "pr-body-publish-failed"])
def test_a_refused_fix_that_differs_from_the_original_still_says_it_did_not_copy_it(tmp_path, reason):
    sd = _staged_fixed(tmp_path)
    _write(PBS.paths(sd)["published"], json.dumps({"outcome": "refused", "reason": reason}))
    assert PBS.record_line(sd) == ("The review did not copy its PR-body fix onto the PR: %s."
                                   % PBS._REFUSAL_PHRASES[reason])


def test_every_refusal_token_has_its_own_plain_phrase(tmp_path):
    sd = _staged_fixed(tmp_path)
    for reason in PBS._REFUSAL_PHRASES:
        _write(PBS.paths(sd)["published"], json.dumps({"outcome": "refused", "reason": reason}))
        line = PBS.record_line(sd)
        assert line.startswith("The review did not copy its PR-body fix onto the PR: ") and reason not in line


def test_the_review_account_carries_the_publish_line(tmp_path):
    # axis: account_from_session includes the line — see bite-proof record wo_pr_body_stage_2083
    session, runs, ex = TRF._session(tmp_path, {"1": TRF._fix()})
    readers = TRS.Fake(runs=runs).readers()
    before = rs.account_from_session(session, TRS.extras(**ex), readers)
    _write(os.path.join(session, "pr-body", "published.json"),
           json.dumps({"outcome": "published", "reason": None}))
    after = rs.account_from_session(session, TRS.extras(**ex), readers)
    line = "The review copied its audited PR-body fix onto the PR."
    assert line in after["checked"] and line not in before["checked"]
    fake = TRS.Fake(runs=runs)
    assert TRS.send(tmp_path, session, fake, **ex)["ok"]  # the record writer accepts the line


# ---- the driver's orders (E1, E5, E16) ---------------------------------------------------------

def _driver_state(tmp_path, **cfg):
    repo = str(tmp_path / "repo")
    os.makedirs(repo, exist_ok=True)
    state = RD.new_state(TRD._cfg(repoRoot=repo, **{RD.FIX_FOLD_HEAD_KEY: "a" * 40}, **cfg))
    state["round"] = 1
    state["fixBatch"] = []
    state["headDiff"] = TRD.HEAD
    return state


def _placeholders(phase, sd, state, seat="t1", payload=None, materialize=True):
    paths = RD._order_paths(sd, 1, phase, 0, seat, 0, True)
    return RD._order_placeholders(phase, seat, 0, state, state["config"], payload or {}, sd, 1, paths,
                                  RD.CHANNEL_FILE, materialize_shared_inputs=materialize), paths


def _render(phase, seat, ph, paths, host_seat=True):
    ctx = TRO._base_context(host_seat=host_seat, placeholders=ph,
                            landing_path=paths["bare_payload_path"] if host_seat else paths["landing_path"])
    text, reason = RO.render_order(phase, seat, ctx)
    assert reason is None, reason
    return text


@pytest.mark.parametrize("mode,pr_json", [
    ("branch", False), ("branch", True), ("pr", False), ("pr", None),
], ids=["branch", "branch-with-pr-json", "pr-without-pr-json", "pr-with-bad-pr-json"])
def test_E1_a_session_without_a_staged_body_hands_the_step_no_pr_body_path(tmp_path, mode, pr_json):
    sd = _session(tmp_path, mode=mode, pr_json=bool(pr_json))
    if pr_json is None:
        _write(os.path.join(sd, "pr.json"), "{broken")
    state = _driver_state(tmp_path)
    state["_fixBatch"] = []
    fields = RD._apply_fixes_payload_fields(sd, state, 1, 0)
    assert "prBodyPath" not in fields and "prBodyFix" not in state["rounds"].get("1", {})


def test_E1_a_staged_body_is_the_step_s_pr_body_path_and_is_the_file_itself(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    state = _driver_state(tmp_path)
    state["_fixBatch"] = []
    fields = RD._apply_fixes_payload_fields(sd, state, 1, 0)
    assert fields["prBodyPath"] == PBS.paths(sd)["staged"]
    assert not os.path.exists(PBS.fixer_copy_path(sd, 1))


def test_E16_a_render_only_audit_order_names_paths_and_creates_nothing(tmp_path):
    sd = _session(tmp_path)
    state = _driver_state(tmp_path)
    ph, _ = _placeholders(RP.P_AUDITS, sd, state, seat="t1", payload={"targets": [{"id": "t1"}]},
                          materialize=False)
    p = PBS.paths(sd)
    assert p["staged"] in ph["PR_BODY_LINE"] and p["original"] in ph["PR_BODY_LINE"]
    assert not os.path.exists(os.path.join(sd, "pr-body"))
    assert "prBodyFix" not in state["rounds"].get("1", {})


# ---- the folds ---------------------------------------------------------------------------------

def _fold_apply_fixes(state, sd):
    state["_fixBatchIndex"] = 0
    RD._fold_apply_fixes(state, state["config"], {"fixes": []}, changed_subjects_seam=lambda *args: [],
                         session_dir=sd, panel_diff_seam=lambda config, head: ("", None))


def test_the_fold_records_the_staged_body_before_and_after_the_session_s_edit(tmp_path):
    # axis: the fold compares the staged body with the sha the step snapshotted — see bite-proof record wo_pr_body_stage_2083
    sd = _session(tmp_path)
    PBS.stage(sd)
    state = _driver_state(tmp_path)
    state["_prBodyAtStep"] = sha(BODY)  # what `next` snapshots when it sets the step
    _write(PBS.paths(sd)["staged"], FIXED)
    _fold_apply_fixes(state, sd)
    assert state["rounds"]["1"]["prBodyFix"] == {"before": sha(BODY), "after": sha(FIXED)}
    assert _read(PBS.paths(sd)["staged"]) == FIXED
    assert "_prBodyAtStep" not in state


def test_E5_several_batches_in_one_round_keep_the_first_before_sha(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    state = _driver_state(tmp_path)
    state["_prBodyAtStep"] = sha(BODY)
    _write(PBS.paths(sd)["staged"], FIXED)
    _fold_apply_fixes(state, sd)  # batch 1 folded
    further = FIXED + "\nA further line.\n"
    state["round"] = 1  # batch 2 folds into the round that held batch 1; the fold of batch 1 moved the loop on
    state["_prBodyAtStep"] = sha(FIXED)  # batch 2's step snapshots the body batch 1 left
    _write(PBS.paths(sd)["staged"], further)
    _fold_apply_fixes(state, sd)
    assert state["rounds"]["1"]["prBodyFix"] == {"before": sha(BODY), "after": sha(further)}


def test_E4_a_fold_with_the_body_unedited_records_nothing(tmp_path):
    sd = _session(tmp_path)
    PBS.stage(sd)
    state = _driver_state(tmp_path)
    state["_prBodyAtStep"] = sha(BODY)
    _fold_apply_fixes(state, sd)
    assert "prBodyFix" not in state["rounds"]["1"]


def test_E4_a_fold_with_no_staged_body_records_and_changes_nothing(tmp_path):
    sd = _session(tmp_path, mode="branch", pr_json=False)
    state = _driver_state(tmp_path)
    _fold_apply_fixes(state, sd)
    assert "prBodyFix" not in state["rounds"]["1"] and not os.path.exists(os.path.join(sd, "pr-body"))


def _audit_state(tmp_path, titles=("Test answers are incomplete",), after=sha(FIXED)):
    state = _driver_state(tmp_path)
    state["fixBatch"] = [_pr_body_finding(title=t, line=4 + i) for i, t in enumerate(titles)]
    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    if after:
        RD._record_round(state, "prBodyFix", {"before": sha(BODY), "after": after})
    state["round"] = 2  # the fix folded in round 1; `_enter_post_fix` moved the loop to the audit round
    return state


def _fold_audits(state, rulings=None, manifest_vendor=None):
    results, manifest = [], {}
    for i, t in enumerate(state["_auditTargets"]):
        ruling = (rulings or {}).get(i, "discharged")
        results.append({"id": t["id"], "ruling": ruling, "reason": "the answers are now stated",
                        "evidence": "read the staged copy", "auditorVendor": t.get("auditorVendor"),
                        "checks": TRD.audit_checks(),
                        **({"newIssues": [{"title": "n", "severity": "Nit", "file": PBS.CITATION,
                                           "line": 1, "consequence": CONSEQUENCE}]}
                           if ruling == "discharged-but-new-issue" else {})})
        manifest[t["id"]] = manifest_vendor or t.get("auditorVendor")
    RD._fold_audits(state, state["config"], {"results": results, "collectionManifest": manifest})


@pytest.mark.parametrize("ruling", ["discharged", "discharged-but-new-issue"])
def test_the_audit_fold_records_the_audited_sha_when_every_target_cleared(tmp_path, ruling):
    # axis: the all-cleared condition — see bite-proof record wo_pr_body_stage_2083
    state = _audit_state(tmp_path, titles=("first answers gap", "second answers gap"))
    assert len(state["_auditTargets"]) == 2
    _fold_audits(state, rulings={0: "discharged", 1: ruling})
    assert state["rounds"]["2"]["prBodyAudited"] == sha(FIXED)


@pytest.mark.parametrize("why", ["one-not-discharged", "unauthenticated", "silence", "no-after-sha",
                                 "no-prBodyFix"])
def test_E10_the_audit_fold_records_nothing_unless_every_target_cleared(tmp_path, why):
    after = None if why in ("no-after-sha", "no-prBodyFix") else sha(FIXED)
    state = _audit_state(tmp_path, titles=("first answers gap", "second answers gap"), after=after)
    if why == "no-after-sha":
        state["rounds"].setdefault("1", {})["prBodyFix"] = {"before": sha(BODY), "after": None}
    if why == "silence":
        results = [{"id": state["_auditTargets"][0]["id"], "ruling": "discharged", "reason": "ok",
                    "evidence": "e", "auditorVendor": state["_auditTargets"][0].get("auditorVendor"),
                    "checks": TRD.audit_checks()}]
        manifest = {state["_auditTargets"][0]["id"]: state["_auditTargets"][0].get("auditorVendor")}
        RD._fold_audits(state, state["config"], {"results": results, "collectionManifest": manifest})
    else:
        _fold_audits(state, rulings={1: "not-discharged"} if why == "one-not-discharged" else None,
                     manifest_vendor="some-other-vendor" if why == "unauthenticated" else None)
    assert "prBodyAudited" not in state["rounds"]["2"]


@pytest.mark.parametrize("host_seat", [True, False], ids=["host-seat", "engine-seat"])
def test_the_audit_order_names_the_staged_copy_and_the_original(tmp_path, host_seat):
    # axis: the audit template's PR-body input line — see bite-proof record wo_pr_body_stage_2083
    sd = _session(tmp_path)
    state = _driver_state(tmp_path)
    ph, paths = _placeholders(RP.P_AUDITS, sd, state, seat="t1", payload={"targets": [{"id": "t1"}]})
    text = _render(RP.P_AUDITS, "t1", ph, paths, host_seat=host_seat)
    p = PBS.paths(sd)
    assert "- PR body: the staged copy %s, to be read against the original %s" % (p["staged"], p["original"]) in text
    assert "lands in the staged copy, not in the head diff" in text


# ---- end to end --------------------------------------------------------------------------------

def test_a_pr_body_finding_is_fixed_audited_and_published_through_the_chokepoint(tmp_path):
    """Drives the real compile, the real `apply-fixes` step's files, the real audit order, the real
    `_fold_apply_fixes` and `_fold_audits`, then `publish` with a fake `gh`."""
    sd = _session(tmp_path)
    PBS.stage(sd)
    state = _driver_state(tmp_path)

    compiled, drops = RD.mechanical_compile([_pr_body_finding()], TRD.DIFF)
    assert len(compiled) == 1 and drops == []
    state["fixBatch"] = state["_fixBatch"] = compiled

    fields = RD._apply_fixes_payload_fields(sd, state, 1, 0)
    assert fields["prBodyPath"] == PBS.paths(sd)["staged"]
    state["_prBodyAtStep"] = sha(BODY)  # what `next` snapshots when it sets the step

    _write(fields["prBodyPath"], FIXED)  # the build session edits the staged file itself
    _fold_apply_fixes(state, sd)
    assert state["rounds"]["1"]["prBodyFix"] == {"before": sha(BODY), "after": sha(FIXED)}
    assert _read(PBS.paths(sd)["staged"]) == FIXED

    state["_auditTargets"] = RD._audit_targets(state, state["config"], {})
    target_id = state["_auditTargets"][0]["id"]
    ph, paths = _placeholders(RP.P_AUDITS, sd, state, seat=target_id,
                              payload={"targets": state["_auditTargets"]})
    audit_order = _render(RP.P_AUDITS, target_id, ph, paths)
    assert PBS.paths(sd)["staged"] in audit_order and PBS.paths(sd)["original"] in audit_order

    assert state["round"] == 2  # the fold moved the loop on to the audit round
    _fold_audits(state)  # the real fold, with an authenticated all-discharged ruling
    assert state["rounds"]["2"]["prBodyAudited"] == sha(FIXED)

    _write(os.path.join(sd, "loop-state.json"), RD._canonical(state))
    _write(os.path.join(sd, "round-receipt.json"), json.dumps({"verdict": "converged"}))
    gh = FakeGh(views=[BODY, FIXED])
    out = PBS.publish(sd, 7, runner=gh)
    assert (out["ok"], out["outcome"]) == (True, "published")
    assert gh.calls == [read_argv(), edit_argv(PBS.paths(sd)["staged"]), read_argv()]
    assert gh.edits() == [edit_argv(PBS.paths(sd)["staged"])]
    assert PBS.record_line(sd) == "The review copied its audited PR-body fix onto the PR."
