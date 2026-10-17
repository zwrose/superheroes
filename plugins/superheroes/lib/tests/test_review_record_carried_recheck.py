"""Guards for the carried-finding re-check: a left-for-owner finding moves to fixed only on a check made at the final head."""
import copy
import json
import os
import subprocess
from pathlib import Path

import pytest

import pr_sheet
import review_record as rr
import review_record_session as rs
from test_review_record_session import CODEX, GREEN, HEAD, THIRD, Fake, _by_key, _first_record, _second_session

FIX = "d" * 40  # the commit that fixed X
WORDS = json.loads((Path(__file__).resolve().parents[2] / "theme" / "sheet-words.json").read_text(encoding="utf-8"))["pr"]
X = {"id": "f-1", "title": "Unchecked index", "severity": "Important", "file": "a.py", "line": 9, "body": "b",
     "consequence": "the total on the page is wrong", "outcome": "left-for-owner", "reason": "waits for the owner",
     "reviewer": "r1"}
X_KEY = rr._key(X)
PRIOR = {"findings": [dict(X, findingKey=X_KEY)]}


def entry(**over):
    return {"key": X_KEY, "settled": "fixed", "commit": FIX, "checkedHead": HEAD, "evidence": "ran the test; it passes", **over}


def account(checks, findings=None):
    return {"schema": rr.ACCOUNT_SCHEMA, "pr": 7, "repo": "o/r", "sessionId": "s-1", "lane": "light", "laneReason": None,
            "finalCommit": HEAD, "ci": "green", "reviewers": [{"name": "r1", "vendor": "codex", "model": CODEX,
                                                                   "planned": True, "ran": True, "runDir": None}],
            "findings": copy.deepcopy([X] if findings is None else findings), "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "carriedChecks": checks}


def readers(ancestor=True, head=HEAD, calls=None):
    fake = Fake(head=head).readers()

    def is_ancestor(root, commit, to):
        if calls is not None:
            calls.append((root, commit, to))
        return ancestor
    return {**fake, "is_ancestor": is_ancestor}


def build(checks, prior=PRIOR, **kw):
    return rr.build_record(account(checks), readers(**kw), prior=prior)


def the_finding(rec):
    (f,) = rec["findings"]
    return f


def test_a_fixed_check_at_the_final_head_marks_the_carried_finding_fixed_and_the_sheet_does_not_ask():
    # Axis: the one path that moves left-for-owner to fixed, and what the owner's sheet then shows.
    calls = []
    rec = build([entry()], calls=calls)
    f = the_finding(rec)
    assert f["outcome"] == "fixed" and f["sheetPart"] == rr.rfs.OUTCOME_SHEET_PART["fixed"] and rec["leftForOwner"] == []
    assert f["reason"] == (f"fixed after its review at {FIX[:7]}: ran the test; it passes "
                           f"(checked against the final commit {HEAD[:7]} when this record was written); earlier: waits for the owner")
    assert rec["carriedRechecks"] == [{"finding": "f-1", "settled": "fixed", "result": "fixed", "why": "fixed", "commit": FIX,
                                       "checkedHead": HEAD, "evidence": "ran the test; it passes"}]
    assert calls == [(None, FIX, HEAD)]
    sheet = pr_sheet.build([rec], {"schema": "pr-sheet-input/1", "kind": "pr", "number": 7, "title": "T", "summary": "S"}, WORDS)
    assert not [c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]
    assert X["title"] in sheet["prSheet"]["whatChanged"]["caught"]


@pytest.mark.parametrize("settled, said", [("applies", "the check found it still applies: "),
                                           ("unsettled", "the check could not settle it: ")])
def test_an_applies_or_unsettled_check_keeps_the_finding_for_the_owner(settled, said):
    # Axis: a check that did not find it fixed keeps it left for the owner, with the check's evidence in the reason.
    rec = build([entry(settled=settled, commit=None, checkedHead=HEAD, evidence="still reads past the end")])
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    assert f["reason"] == ("waits for the owner; a check against the final commit kept it for the owner: "
                           + said + "still reads past the end")
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["settled"], row["why"]) == ("kept", settled, said + "still reads past the end")
    advisor = {"schema": "pr-sheet-input/1", "kind": "pr", "number": 7, "title": "T", "summary": "S"}
    with pytest.raises(pr_sheet.Refusal) as refused:
        pr_sheet.build([rec], advisor, WORDS)
    assert any(X["title"] in p or "f-1" in p for p in refused.value.problems)
    leftovers = {"f-1": {"why": "the check found it open", "context": "the index is read unchecked", "options": "none"}}
    sheet = pr_sheet.build([rec], {**advisor, "leftovers": leftovers}, WORDS)
    assert len([c for c in sheet["cards"] if c["callKind"].startswith(WORDS["leftoverKind"])]) == 1


@pytest.mark.parametrize("settled, said", [("applies", "the check found it still applies: "),
                                           ("unsettled", "the check could not settle it: ")])
@pytest.mark.parametrize("seen, clause", [
    pytest.param(THIRD, f"a check on {THIRD[:7]} (not the final commit {HEAD[:7]})", id="older-checked-head"),
    pytest.param(None, "a check on no named commit", id="no-checked-head"),
])
def test_a_kept_reason_names_the_commit_the_check_was_made_on(settled, said, seen, clause):
    # Axis: an applies or unsettled check made on another commit, or none, never reads as a check on the final commit.
    rec = build([entry(settled=settled, commit=None, checkedHead=seen, evidence="still reads past the end")])
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    assert f["reason"] == f"waits for the owner; {clause} kept it for the owner: {said}still reads past the end"
    assert "against the final commit" not in f["reason"]
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["checkedHead"]) == ("kept", seen)


@pytest.mark.parametrize("checks, prior, kw, why", [
    pytest.param([], PRIOR, {}, None, id="no-entry"),
    pytest.param([entry()], {"findings": []}, {}, "not carried from an earlier record", id="not-carried"),
    pytest.param([entry()], None, {}, "not carried from an earlier record", id="no-earlier-record"),
    pytest.param([entry(checkedHead=THIRD)], PRIOR, {}, f"checked on {THIRD[:7]}, not the final commit {HEAD[:7]}",
                 id="head-moved-after-the-check"),
    pytest.param([entry()], PRIOR, {"ancestor": False}, f"its fix commit {FIX[:7]} is not in the final commit's history",
                 id="fix-commit-not-in-history"),
    pytest.param([entry()], PRIOR, {"ancestor": None}, "its fix commit's place in the history could not be read",
                 id="history-unreadable"),
    pytest.param([entry(checkedHead=HEAD)], PRIOR, {"head": THIRD}, f"checked on {HEAD[:7]}, not the final commit {THIRD[:7]}",
                 id="github-head-differs-from-the-session-head"),
])
def test_every_other_case_keeps_the_finding_for_the_owner(checks, prior, kw, why):
    # Axis: fail closed, a finding stays left-for-owner unless every condition of the check holds; it is never removed.
    rec = build(checks, prior, **kw)
    f = the_finding(rec)
    assert f["outcome"] == "left-for-owner" and rec["leftForOwner"] == ["f-1"]
    if why is None:
        assert f["reason"] == "waits for the owner" and rec["carriedRechecks"] == []
        return
    assert f["reason"] == f"waits for the owner; a check against the final commit kept it for the owner: {why}"
    (row,) = rec["carriedRechecks"]
    assert (row["result"], row["why"]) == ("kept", why)


def test_a_check_on_a_finding_that_is_not_left_for_the_owner_changes_nothing_and_is_listed():
    # Axis: every entry that names a finding produces one row, moved or not.
    fixed = dict(X, outcome="fixed", reason="done")
    rec = rr.build_record(account([entry()], [fixed]), readers(), prior=PRIOR)
    assert the_finding(rec)["reason"] == "done"
    assert [(r["result"], r["why"]) for r in rec["carriedRechecks"]] == [("unchanged", "not left for the owner")]


def test_a_finding_without_a_reason_gets_only_the_checks_clause():
    # Axis: the reason of a kept finding never starts with a stray separator.
    rec = rr.build_record(account([entry(settled="applies")], [dict(X, reason=None)]), readers(), prior=PRIOR)
    assert the_finding(rec)["reason"] == ("a check against the final commit kept it for the owner: "
                                          "the check found it still applies: ran the test; it passes")


def test_a_check_may_name_the_finding_by_its_id():
    # Axis: an entry's key matches the finding's id as well as its stored identity key.
    assert the_finding(build([entry(key="f-1")]))["outcome"] == "fixed"


Y = dict(X, id="f-2", title="Another")


@pytest.mark.parametrize("checks, findings, detail", [
    pytest.param([entry(settled="done")], None, "carriedChecks[0].settled (allowed: fixed, applies, unsettled)",
                 id="unknown-settled"),
    pytest.param([entry(commit=None)], None, "carriedChecks[0].commit", id="fixed-without-commit"),
    pytest.param([entry(checkedHead=None)], None, "carriedChecks[0].checkedHead", id="fixed-without-checked-head"),
    pytest.param([entry(commit="")], None, "carriedChecks[0].commit", id="fixed-with-empty-commit"),
    pytest.param([entry(evidence="")], None, "carriedChecks[0].evidence", id="empty-evidence"),
    pytest.param([entry(evidence=None)], None, "carriedChecks[0].evidence", id="no-evidence"),
    pytest.param([entry(evidence="   ")], None, "carriedChecks[0].evidence", id="spaces-evidence"),
    pytest.param([entry(evidence="\n\t")], None, "carriedChecks[0].evidence", id="newline-tab-evidence"),
    pytest.param([entry(settled="applies", commit=5)], None, "carriedChecks[0].commit", id="commit-not-a-string"),
    pytest.param([entry(key="")], None, "carriedChecks[0].key", id="empty-key"),
    pytest.param(["f-1"], None, "carriedChecks[0].key", id="entry-not-an-object"),
    pytest.param([entry(key="nobody")], None, "carriedChecks[0].key names no finding", id="key-names-no-finding"),
    pytest.param([entry(key="f-1")], [X, dict(Y, id="f-1")], "carriedChecks[0].key names more than one finding",
                 id="key-names-two-findings"),
    pytest.param([entry(), entry(key="f-1")], None, "carriedChecks[1].key names a finding another entry names",
                 id="two-entries-for-one-finding"),
])
def test_a_malformed_or_unmatched_entry_is_refused(checks, findings, detail):
    # Axis: the account's carriedChecks shape and naming are validated before anything is written.
    with pytest.raises(rr.Refusal) as caught:
        rr.build_record(account(checks, findings), readers(), prior=PRIOR)
    assert (caught.value.reason, caught.value.detail) == ("review-account-invalid", detail)


def test_carried_checks_is_not_a_list_is_refused_and_absent_defaults_to_empty():
    # Axis: carriedChecks is an optional list like the other optional lists.
    bad = account([])
    bad["carriedChecks"] = {}
    with pytest.raises(rr.Refusal) as caught:
        rr.build_record(bad, readers())
    assert caught.value.detail == "carriedChecks"
    plain = account([])
    del plain["carriedChecks"]
    assert rr.build_record(plain, readers())["carriedRechecks"] == []


def test_a_direct_write_rechecks_a_finding_carried_from_the_earlier_record(tmp_path):
    # Axis: the check sits in build_record, so the direct lane (an account file) gets it with no session adapter.
    fake, calls = Fake(), []
    rd = readers(calls=calls)
    rd["list_comments"], rd["create_comment"] = fake.readers()["list_comments"], fake.readers()["create_comment"]
    path = tmp_path / "account.json"
    path.write_text(json.dumps(account([])))
    assert rr.write(str(path), str(tmp_path), rd)["ok"]
    assert rr.read(7, readers=rd)["findings"][0]["outcome"] == "left-for-owner"
    path.write_text(json.dumps(account([entry()])))
    assert rr.write(str(path), str(tmp_path), rd)["ok"]
    rec = rr.read(7, readers=rd)
    assert the_finding(rec)["outcome"] == "fixed" and rec["leftForOwner"] == []
    assert [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]
    assert calls == [(str(tmp_path), FIX, HEAD)]


def test_extras_carried_checks_reach_the_record_through_the_session_adapter(tmp_path):
    # Axis: write_from_session passes the extras' carriedChecks into the account that review_record.write checks.
    fake = Fake()
    _first_record(tmp_path, fake, disposition="out-of-scope")
    (before,) = _by_key(fake)
    assert before["outcome"] == "left-for-owner"
    rd = {**fake.readers(), "is_ancestor": lambda root, commit, to: True}
    extras = tmp_path / "extras.json"
    extras.write_text(json.dumps({"schema": rs.EXTRAS_SCHEMA, "pr": 7,
                                  "carriedChecks": [entry(key=before["findingKey"], checkedHead=HEAD)]}))
    out = rs.write_from_session(_second_session(tmp_path), str(extras), str(tmp_path), rd)
    assert out["ok"], out
    rec = rr.read(7, readers=rd)
    assert the_finding(rec)["outcome"] == "fixed" and [r["result"] for r in rec["carriedRechecks"]] == ["fixed"]


def test_extras_carried_checks_must_be_a_list(tmp_path):
    # Axis: the adapter type-checks carriedChecks like the other list extras.
    extras = tmp_path / "extras.json"
    extras.write_text(json.dumps({"schema": rs.EXTRAS_SCHEMA, "pr": 7, "carriedChecks": {}}))
    out = rs.write_from_session(_second_session(tmp_path), str(extras), str(tmp_path), Fake().readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, rs.BAD_EXTRAS, "carriedChecks")


# --- the default reader, against the real binary ---

def _pinned():
    """The environment handed to git: the live one with every GIT_* variable removed (inherited GIT_DIR and
    GIT_WORK_TREE override `git -C`), then the two pinned settings."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {**env, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=_pinned()).stdout.strip()


def _two_commits(repo):
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True, env=_pinned())
    shas = []
    for n in "ab":
        _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", n)
        shas.append(_git(repo, "rev-parse", "HEAD"))
    return shas


def test_the_default_reader_tells_an_ancestor_from_a_non_ancestor_from_an_error(tmp_path):
    # Axis: exit 0 is True, exit 1 is False, and every error (unknown sha, missing repo) is None, never False.
    repo = tmp_path / "repo"
    shas = _two_commits(repo)
    a, b = shas
    assert rr._is_ancestor(str(repo), a, b) is True
    assert rr._is_ancestor(str(repo), b, a) is False
    assert rr._is_ancestor(str(repo), "0" * 40, b) is None
    assert rr._is_ancestor(str(tmp_path / "missing"), a, b) is None
    assert rr._is_ancestor(None, a, b) is None
    assert rr._is_ancestor(str(repo), "--all", b) is None


def test_inherited_git_routing_does_not_reach_the_helper_commits(tmp_path, monkeypatch):
    # Axis: an inherited GIT_DIR/GIT_WORK_TREE aimed at another repository is not passed to git, so the helper's commits land in its own repo.
    sentinel = tmp_path / "sentinel"
    subprocess.run(["git", "init", "-q", str(sentinel)], check=True, capture_output=True, env=_pinned())
    head_file = sentinel / ".git" / "HEAD"
    before = head_file.read_bytes()
    monkeypatch.setenv("GIT_DIR", str(sentinel / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(sentinel))
    assert {"GIT_DIR", "GIT_WORK_TREE"} <= os.environ.keys() and not {"GIT_DIR", "GIT_WORK_TREE"} & _pinned().keys()
    repo = tmp_path / "repo"
    a, b = _two_commits(repo)
    assert head_file.read_bytes() == before
    assert not list((sentinel / ".git" / "refs" / "heads").iterdir())
    assert _git(repo, "rev-list", "--count", b) == "2" and a != b
