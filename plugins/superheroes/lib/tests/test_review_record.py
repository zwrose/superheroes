import copy
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import pytest

import model_registry
import review_record as rr

HEAD = "b" * 40
EARLIER = "a" * 40
CODEX = model_registry.codex_models()[0]
NO_STATUS = {"state": "pending", "total_count": 0, "statuses": []}
GREEN = ({"total_count": 1, "check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]},
         NO_STATUS)
PENDING = ({"check_runs": [{"name": "validate", "status": "in_progress", "conclusion": None}]}, NO_STATUS)
RED = ({"check_runs": [{"name": "validate", "status": "completed", "conclusion": "failure"}]}, NO_STATUS)
GOOD_RUN = {"runKind": "review", "resultKind": "findings", "resultDigest": "d1", "graded": True, "source": "codex",
            "engineModel": CODEX, "viewHeadSha": HEAD, "observation": {"tokens": 100, "wallSeconds": 120}}
PHRASES = ("no bugs", "bug-free", "bug free")


class Fake:
    """Injectable readers with an in-memory comment list; records create/edit calls."""

    def __init__(self, ci=GREEN, meta=None, marker=None, runs=None, issue_bodies=None):
        self.comments, self.writes, self.edits = [], [], []
        self.ci = ci
        self.meta = {"head": HEAD, "body": "", "issues": []} if meta is None else meta
        self.marker, self.runs, self.issue_bodies = marker, runs or {}, issue_bodies or {}

    def readers(self):
        return {
            "pr_meta": lambda pr, repo: self.meta,
            "issue_body": lambda n, repo: self.issue_bodies.get(n),
            "check_data": lambda sha, repo: self.ci,
            "lane_marker": lambda root: self.marker,
            "engine_run": lambda d: self.runs.get(d, (copy.deepcopy(GOOD_RUN), None)),
            "list_comments": lambda pr, repo: list(self.comments),
            "create_comment": self._create,
            "edit_comment": self._edit,
        }

    def _create(self, pr, repo, body):
        c = {"id": len(self.comments) + 1, "author": "bot", "body": body, "url": f"http://c/{len(self.comments) + 1}"}
        self.comments.append(c)
        self.writes.append("create")
        return {"id": c["id"], "url": c["url"]}

    def _edit(self, cid, repo, body):
        c = next(c for c in self.comments if c["id"] == cid)
        c["body"] = body
        self.writes.append("edit")
        self.edits.append(cid)
        return {"id": cid, "url": c["url"]}

    def marked(self):
        return [c for c in self.comments if c["body"].startswith(rr.MARKER)]


def reviewer(name="code-reviewer", **over):
    return {"name": name, "vendor": "codex", "model": CODEX, "planned": True, "ran": True,
            "runDir": f"/run/{name}", "ownerWord": None, **over}


def finding(fid="code-001", **over):
    return {"id": fid, "title": "t", "severity": "Minor", "file": "a.py", "line": 3, "body": "b",
            "consequence": "c", "outcome": "fixed", "reason": "fixed in 1a2b3c4", "reviewer": "code-reviewer", **over}


def account(**over):
    base = {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big",
            "finalCommit": HEAD, "ci": "green", "makers": [{"family": "anthropic", "source": "builder"}],
            "reviewers": [reviewer()], "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"]}
    return {**base, **over}


def put(tmp_path, acct, name="account.json"):
    path = tmp_path / name
    path.write_text(json.dumps(acct))
    return str(path)


def build(acct, fake=None, prior=None):
    return rr.build_record(acct, (fake or Fake()).readers(), prior)


def test_each_lane_writes_one_record_with_every_key(tmp_path):
    # axis: lane resolution and the record's key set; a lane taking the wrong source or a record missing a key
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b"}
    cases = [
        (Fake(meta={"head": HEAD, "body": "x\n**Lane call:** light. small and safe\n", "issues": []}),
         "light", "PR lane call", "small and safe"),
        (Fake(meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "**Lane call:** micro: one line"}),
         "micro", "issue lane call", "one line"),
        (Fake(), "full", "reported by the session", "big"),
        (Fake(marker=marker), "full", "build lane marker", None),
    ]
    keys = {"schema", "pr", "sessionId", "lane", "finalCommit", "ci", "makers", "reviewers", "findings",
            "rawFindings", "leftForOwner", "missingReviews", "rounds", "cost", "status", "parked",
            "whatIsMissing", "sessionDisagreements", "checked", "archives", "owed", "writtenAt"}
    for fake, lane, source, reason in cases:
        out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
        assert out["ok"] and out["action"] == "created"
        assert len(fake.marked()) == 1
        rec = rr.read(7, readers=fake.readers())
        assert keys <= set(rec)
        assert (rec["lane"]["value"], rec["lane"]["source"], rec["lane"]["reason"]) == (lane, source, reason)
        assert rec["finalCommit"]["sha"] == HEAD and rec["ci"]["state"] == "green" and rec["writtenAt"]


def test_branch_mismatched_marker_does_not_count():
    # axis: the build-lane marker's branch check; a marker from another branch deciding the lane
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "other", "currentBranch": "b"}
    assert build(account(lane="micro"), Fake(marker=marker))["lane"]["source"] == "reported by the session"


def test_planned_reviewer_that_did_not_run_is_missing():
    # axis: planned-review accounting; a planned reviewer that did not run going unlisted
    rec = build(account(reviewers=[reviewer(ran=False, runDir=None)]))
    assert rec["reviewers"][0]["ran"] == "not-run"
    assert [m["name"] for m in rec["missingReviews"]] == ["code-reviewer"]


def test_session_only_run_counts_and_is_labelled():
    # axis: the session-reported run label; a run only the session reports shown as an engine record
    fake = Fake()
    acct = account(reviewers=[reviewer(runDir=None)])
    rec = build(acct, fake)
    assert rec["reviewers"][0]["ran"] == "reported-by-session" and rec["missingReviews"] == []
    assert rec["status"] == "reviewed"
    assert "- code-reviewer: ran (reported by the session)" in rr.render(rec)


def test_code_wins_over_the_session_account():
    # axis: code over account; lane, final commit and CI taking the session's claim over code's reading
    fake = Fake(ci=PENDING, marker={"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b"})
    rec = build(account(lane="light", finalCommit=EARLIER, ci="green"), fake)
    assert (rec["lane"]["value"], rec["finalCommit"]["sha"], rec["ci"]["state"]) == ("full", HEAD, "pending")
    assert {d["fact"] for d in rec["sessionDisagreements"]} == {"lane", "finalCommit", "ci"}
    assert len(rec["sessionDisagreements"]) == 3


def test_null_outcome_is_not_reviewed():
    # axis: the outcome condition; a finding with no outcome counted as reviewed
    rec = build(account(findings=[finding(outcome=None)]))
    assert rec["status"] == "not-reviewed" and "finding code-001 has no outcome" in rec["whatIsMissing"]


def test_finding_without_reason_is_not_reviewed():
    # axis: the reason condition; a finding with no reason counted as reviewed
    rec = build(account(findings=[finding(reason="")]))
    assert rec["status"] == "not-reviewed" and "finding code-001 has no reason" in rec["whatIsMissing"]


@pytest.mark.parametrize("ci,word", [(RED, "red"), (PENDING, "pending"), (None, "none")])
def test_ci_that_is_not_green_is_not_reviewed(ci, word):
    # axis: the CI condition; red, pending or unreadable CI counted as reviewed
    rec = build(account(), Fake(ci=ci))
    assert rec["status"] == "not-reviewed" and rec["ci"]["state"] == word


def test_green_claimed_on_an_earlier_sha_is_not_reviewed():
    # axis: final-commit CI; CI read on the account's earlier commit rather than the PR head, or the disagreement going unrecorded
    seen = []
    readers = dict(Fake().readers(), check_data=lambda sha, repo: seen.append(sha) or GREEN)
    rec = rr.build_record(account(finalCommit=EARLIER, ci="green"), readers)
    assert seen == [HEAD]
    assert {"fact": "finalCommit", "session": EARLIER, "code": HEAD} in rec["sessionDisagreements"]
    assert rec["finalCommit"]["sha"] == HEAD and rec["ci"]["sha"] == HEAD


def test_status_rejects_ci_read_on_a_different_sha_than_the_final_commit():
    # axis: status CI-sha check; green CI read on another commit counted as reviewed
    rec = build(account())
    assert rec["status"] == "reviewed"
    rec["ci"] = dict(rec["ci"], sha=EARLIER)
    status, _, lines = rr._status(rec)
    assert status == "not-reviewed" and "not on the final commit" in lines[0]


def test_missing_security_review_parks_unless_the_owner_went_ahead():
    # axis: go-ahead handling; a missing review not parked, or a go-ahead lifting the not-reviewed status
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    base = account(reviewers=[reviewer(), sec])
    rec = build(base)
    assert (rec["status"], rec["parked"]) == ("not-reviewed", True)
    assert "security-reviewer did not run" in rec["whatIsMissing"]
    ruling = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": "canon-7"}
    rec = build(account(reviewers=[reviewer(), sec], goAheads=[ruling]))
    assert (rec["status"], rec["parked"]) == ("not-reviewed", False)
    assert rec["missingReviews"] == [{"name": "security-reviewer", "goAhead": ruling}]
    assert "standing ruling canon-7" in " ".join(rec["whatIsMissing"])
    words = {"reviewer": "security-reviewer", "kind": "owner-words", "words": "skip it", "where": "PR comment"}
    rec = build(account(reviewers=[reviewer(), sec], goAheads=[words]))
    assert (rec["status"], rec["parked"]) == ("not-reviewed", False)
    assert "owner's words (PR comment)" in " ".join(rec["whatIsMissing"])


def test_go_ahead_missing_its_proof_does_not_count():
    # axis: go-ahead proof; a go-ahead without its canon id or words accepted
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    for bad in ({"kind": "standing-ruling"}, {"kind": "owner-words", "words": "go"}):
        rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", **bad}]))
        assert rec["parked"] is True and rec["missingReviews"][0]["goAhead"] is None
        assert "the go-ahead for security-reviewer is incomplete" in rec["whatIsMissing"]


def test_clean_fixture_is_reviewed_and_never_claims_bug_free(tmp_path):
    # axis: the clean path; a complete account not reviewed, or any rendering claiming no bugs
    fake = Fake()
    rec = build(account(findings=[finding()]), fake)
    assert rec["status"] == "reviewed" and rec["whatIsMissing"] == [] and rec["parked"] is False
    text = (json.dumps(rec) + rr.render(rec)).lower()
    assert not any(p in text for p in PHRASES)
    assert rec["cost"] == {"unit": "reviewer-minutes", "minutes": 2.0, "tokens": 100,
                           "source": "engine records", "notCounted": []}


@pytest.mark.parametrize("phrase", PHRASES)
def test_bug_free_claim_guard_raises(phrase):
    # axis: the forbidden-claim helper; a bug-free phrase in any case passing it
    with pytest.raises(rr.Refusal):
        rr._assert_no_bug_free_claim(f"This change is {phrase.upper()}.")


def test_forbidden_phrase_in_the_summary_refuses_the_write_and_posts_nothing(tmp_path):
    # axis: the render guard at the publication boundary; a forbidden phrase in writer-authored summary text being posted
    fake = Fake()
    acct = account(reviewers=[reviewer("bug free")])
    out = rr.write(put(tmp_path, acct), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-forbidden-claim")


def test_forbidden_phrase_in_a_reviewers_finding_text_does_not_refuse_the_archive():
    # axis: the archive guard's scope; reviewers' quoted finding text in the kept body refusing the archive write
    prior_body = rr.MARKER + "\nthe README claims no bugs"
    assert rr.render_archive(prior_body).endswith(prior_body)


def test_forbidden_phrase_in_the_archive_intro_still_refuses(monkeypatch):
    # axis: the archive guard; a forbidden phrase in the writer's own archive intro passing
    monkeypatch.setattr(rr, "FORBIDDEN_CLAIMS", ("kept verbatim",))
    with pytest.raises(rr.Refusal) as e:
        rr.render_archive(rr.MARKER + "\nbody")
    assert e.value.reason == "review-record-forbidden-claim"


@pytest.mark.parametrize("shape", ["array", "object"])
def test_read_back_survives_the_session_dir(tmp_path, shape):
    # axis: the record as the one source; read-back needing the session's files, or raw findings lost
    session = tmp_path / "session"
    session.mkdir()
    raw = session / "code.json"
    members = [{"id": f"n{i}", "title": "nit", "severity": "Nit"} for i in range(7)] + [{"id": "c1", "severity": "Minor"}]
    raw.write_text(json.dumps(members if shape == "array" else {"findings": members}))
    findings = [finding(f"n{i}", severity="Nit") for i in range(7)]
    findings += [finding("c1", outcome="craft", reason="style call"), finding("w1", outcome="shown-wrong", reason="x")]
    fake = Fake()
    out = rr.write(put(session, account(findings=findings, rawFindingsFiles=[str(raw)])), str(tmp_path), fake.readers())
    assert out["ok"]
    shutil.rmtree(session)
    rec = rr.read(7, readers=fake.readers())
    assert [f["id"] for f in rec["findings"]] == [f["id"] for f in findings]
    assert {f["outcome"] for f in rec["findings"]} >= {"craft", "shown-wrong"}
    assert sum(1 for r in rec["rawFindings"] if r["severity"] == "Nit") == 7
    assert rec["rawFindings"][0]["sourceFile"] == "code.json" and rec["url"]


def test_unreadable_raw_findings_file_is_named_not_fatal(tmp_path):
    # axis: unreadable raw findings; a missing file hidden, or one that aborts the write
    rec = build(account(rawFindingsFiles=[str(tmp_path / "gone.json")]))
    assert rec["whatIsMissing"] == [f"the findings file {tmp_path / 'gone.json'} could not be read"]
    assert rec["status"] == "not-reviewed"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    rec = build(account(rawFindingsFiles=[str(bad)]))
    assert rec["status"] == "not-reviewed" and f"the findings file {bad} could not be read" in rec["whatIsMissing"]


@pytest.mark.parametrize("secret", ["password", "pwd", "passphrase"])
def test_a_secret_named_field_is_redacted_whole_in_the_record(secret):
    # axis: structured credentials; a value scrubbed without its field name keeping a password
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {secret: "hunter2", "Nested": {"API_KEY": "abc", "note": "ok"}}
    body = rr.render(build(account(findings=[f])))
    assert "hunter2" not in body and "abc" not in body and '"note": "ok"' in body


def test_engine_record_without_result_kind_is_not_run():
    # axis: the engine receipt's result kind; a receipt with no result counted as a run
    weak = {k: v for k, v in GOOD_RUN.items() if k != "resultKind"}
    rec = build(account(), Fake(runs={"/run/code-reviewer": (weak, None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["reviewers"][0]["runNote"] == "no review result"
    assert rec["status"] == "not-reviewed"


def test_engine_record_of_another_run_kind_is_not_run():
    # axis: the engine receipt's run kind; a non-review run counted as a review
    rec = build(account(), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, runKind="write"), None)}))
    assert rec["reviewers"][0]["ran"] == "not-run"


def test_engine_error_while_session_says_ran_is_a_disagreement():
    # axis: engine errors; a run the session claims but the engine cannot show passing unrecorded
    rec = build(account(), Fake(runs={"/run/code-reviewer": (None, "attempt-not-completed")}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["reviewers"][0]["runNote"] == "attempt-not-completed"
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]


def test_same_family_reviewer_needs_the_owner_word():
    # axis: reviewer independence; a maker-family reviewer counted without complete owner words
    same = reviewer(vendor="claude", model="opus-5.5")
    claude = {"/run/code-reviewer": (dict(GOOD_RUN, source="claude", engineModel="opus-5.5"), None)}
    rec = build(account(reviewers=[same]), Fake(runs=claude))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["status"] == "not-reviewed"
    assert rec["reviewers"][0]["runNote"] == "not shown independent of the makers"
    word = {"words": "fine by me", "where": "PR comment"}
    rec = build(account(reviewers=[reviewer(vendor="claude", model="opus-5.5", ownerWord=word)]), Fake(runs=claude))
    assert rec["reviewers"][0]["ran"] == "engine-record" and rec["reviewers"][0]["notIndependent"] is True
    assert rec["status"] == "reviewed"
    half = {"words": "fine by me", "where": ""}
    assert build(account(reviewers=[reviewer(vendor="claude", model="opus-5.5", ownerWord=half)]), Fake(runs=claude))[
        "reviewers"][0]["ran"] == "not-run"


def test_unknown_model_takes_the_one_family_of_its_vendor(monkeypatch):
    # axis: family inference; an unknown model given a family when its vendor has several
    assert rr._family("claude", "opus-9") == "anthropic"
    assert rr._family("elsewhere", "x") is None
    two = {"claude": lambda: ("opus-5.5", CODEX)}
    monkeypatch.setattr(rr, "_VENDOR_MODELS", dict(rr._VENDOR_MODELS, **two))
    monkeypatch.setattr(model_registry, "model_family",
                        lambda v, m: {"opus-5.5": "anthropic", CODEX: "openai"}.get(m))
    assert rr._family("claude", "opus-9") is None


def test_two_marker_comments_refuse_without_writing(tmp_path):
    # axis: one record per PR; duplicate marker comments written over or read past
    fake = Fake()
    assert rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())["ok"]
    fake.comments.append(dict(fake.comments[0], id=2, url="u2"))
    fake.writes.clear()
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out.get("reason")) == (False, "review-record-duplicate")
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-duplicate"


def test_unparseable_prior_refuses_without_writing(tmp_path):
    # axis: hand-edited record; an unreadable prior overwritten
    fake = Fake()
    fake.comments = [{"id": 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u1"}]
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unreadable")
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def test_read_with_no_record_is_missing():
    # axis: read with no record; a missing record not refused as missing
    assert rr.read(7, readers=Fake().readers())["reason"] == "review-record-missing"


def test_ci_state_truth_table():
    # axis: CI state mapping; a check-run or status combination mapped to the wrong state
    done = lambda c: {"check_runs": [{"status": "completed", "conclusion": c}]}  # noqa: E731
    assert rr.ci_state({"check_runs": []}, NO_STATUS) == "none"
    assert rr.ci_state({"check_runs": []}, {"state": "success", "total_count": 1, "statuses": [{"state": "success"}]}) == "green"
    assert rr.ci_state(done("success"), NO_STATUS) == "green"
    assert rr.ci_state({"check_runs": [{"status": "in_progress"}]}, NO_STATUS) == "pending"
    assert rr.ci_state(done("failure"), NO_STATUS) == "red"
    assert rr.ci_state({"check_runs": [{"status": "in_progress"}, {"status": "completed", "conclusion": "timed_out"}]},
                       NO_STATUS) == "red"
    assert rr.ci_state(done("success"), {"state": "error", "total_count": 1, "statuses": [{"state": "error"}]}) == "red"
    assert rr.ci_state(done("success"), {"state": "pending", "total_count": 1, "statuses": [{"state": "pending"}]}) == "pending"


def test_unreadable_pr_is_not_reviewed():
    # axis: unreadable PR; a final commit from the session counted as read from the PR, or CI read without a commit
    fake = Fake()
    fake.meta = None
    rec = build(account(finalCommit=EARLIER), fake)
    assert rec["finalCommit"] == {"sha": EARLIER, "source": "reported by the session"}
    assert rec["status"] == "not-reviewed" and "the final commit could not be read from the PR" in rec["whatIsMissing"]
    fake.meta, fake.ci = None, None
    rec = build(account(finalCommit=None), fake)
    assert rec["ci"] == {"state": "none", "sha": None, "source": "unavailable"}


def test_no_makers_is_not_reviewed():
    # axis: makers recorded; a record with no maker families counted as reviewed
    rec = build(account(makers=[]))
    assert rec["status"] == "not-reviewed" and "the makers' model families were not recorded" in rec["whatIsMissing"]
    assert rec["reviewers"][0]["independent"] is None and rec["reviewers"][0]["ran"] == "engine-record"


def test_null_outcome_writes_and_a_foreign_outcome_is_refused(tmp_path):
    # axis: outcome spelling; a foreign outcome accepted, or a null outcome refused
    fake = Fake()
    ok = rr.write(put(tmp_path, account(findings=[finding(outcome=None)])), str(tmp_path), fake.readers())
    assert ok["ok"] and ok["status"] == "not-reviewed"
    bad = rr.write(put(tmp_path, account(findings=[finding(outcome="done")])), str(tmp_path), fake.readers())
    assert (bad["ok"], bad["reason"]) == (False, "review-account-invalid") and "outcome" in bad["detail"]
    assert all(o in bad["detail"] for o in rr.rfs.OUTCOMES)


@pytest.mark.parametrize("key", ["schema", "pr", "sessionId", "reviewers"])
def test_missing_required_key_is_refused_naming_the_key(tmp_path, key):
    # axis: account validation; a missing required key accepted or refused without naming it
    acct = account()
    del acct[key]
    out = rr.write(put(tmp_path, acct), str(tmp_path), Fake().readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", key)


def test_too_large_body_is_refused(tmp_path):
    # axis: body size; an oversized record posted or trimmed
    fake = Fake()
    big = [finding(f"f{i}", body="x" * 5000) for i in range(20)]
    out = rr.write(put(tmp_path, account(findings=big)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large")


def test_gh_failures_refuse(tmp_path):
    # axis: GitHub failures; an unreadable comment list or failed create treated as success
    readers = dict(Fake().readers(), list_comments=lambda pr, repo: None)
    assert rr.write(put(tmp_path, account()), str(tmp_path), readers)["reason"] == "review-record-gh-failed"
    readers = dict(Fake().readers(), create_comment=lambda pr, repo, body: None)
    assert rr.write(put(tmp_path, account()), str(tmp_path), readers)["reason"] == "review-record-gh-failed"


def test_cli_read_without_gh_refuses(tmp_path):
    # axis: the CLI without gh; a missing gh raising instead of printing a refusal and exiting 1
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "read", "--pr", "1"], capture_output=True,
                          text=True, env={"PATH": str(empty), "HOME": str(tmp_path)})
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_receipt_of_another_family_decides_independence():
    # axis: receipt family; the account's family claim winning over the run's own engine and model
    claude_run = dict(GOOD_RUN, source="claude", engineModel="opus-5.5")
    rec = build(account(), Fake(runs={"/run/code-reviewer": (claude_run, None)}))
    v = rec["reviewers"][0]
    assert v["family"] == "anthropic" and v["ran"] == "not-run" and rec["status"] == "not-reviewed"
    assert {"fact": "code-reviewer family", "session": "openai", "code": "anthropic"} in rec["sessionDisagreements"]


@pytest.mark.parametrize("seen", [EARLIER, None])
def test_receipt_for_another_or_unknown_commit_is_not_a_review(seen):
    # axis: receipt commit; a review of another or unknown commit counted for the final commit
    run = dict(GOOD_RUN, viewHeadSha=seen)
    rec = build(account(), Fake(runs={"/run/code-reviewer": (run, None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["status"] == "not-reviewed"
    assert rec["reviewers"][0]["runNote"]


def test_credentials_are_scrubbed_before_the_record_is_published(tmp_path):
    # axis: scrubbing; a credential in account text reaching the posted comment
    token = "ghp_" + "A" * 36
    fake = Fake()
    acct = account(findings=[finding(body=f"key {token}", reason=f"saw {token}")])
    assert rr.write(put(tmp_path, acct), str(tmp_path), fake.readers())["ok"]
    assert token not in fake.marked()[0]["body"]
    assert rr.read(7, readers=fake.readers())["findings"][0]["body"] == "key [REDACTED]"


def test_same_title_at_another_line_is_another_finding():
    # axis: finding identity; two findings sharing file and title collapsing into one, so settling one settles both
    two = [finding("c1", title="Leak", line=10, outcome="left-for-owner", reason="r"),
           finding("c2", title="Leak", line=90, outcome="left-for-owner", reason="r")]
    old = build(account(sessionId="A", findings=two))
    rec = build(account(sessionId="B", findings=[finding("c2", title="Leak", line=90, reason="fixed it")]), prior=old)
    assert [e["id"] for e in rec["owed"]] == ["c1"] and rec["status"] == "not-reviewed"


def test_raw_findings_match_by_identity_not_by_reused_id(tmp_path):
    # axis: raw coverage; one outcome for a reused reviewer id covering a different, undecided finding
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "code-001", "title": "t", "file": "a.py", "line": 3, "severity": "Minor"},
                               {"id": "code-001", "title": "Auth gap", "file": "auth.py", "line": 5,
                                "severity": "Important"}]))
    rec = build(account(rawFindingsFiles=[str(raw)], findings=[finding("code-001")]))
    assert rec["status"] == "not-reviewed" and rec["owed"] == []
    assert [m for m in rec["whatIsMissing"] if "has no recorded outcome" in m] == [
        "reviewer finding code-001 in code.json has no recorded outcome"]
    assert [r["file"] for r in rec["rawFindings"]] == ["a.py", "auth.py"]


def test_every_reviewers_findings_coverage_is_marked_as_reported_by_the_session():
    # axis: findings coverage; a graded engine run shown as if the code held its findings
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)})
    rec = build(account(reviewers=[reviewer(runDir="/run/code-reviewer")]), fake)
    assert rec["reviewers"][0]["ran"] == "engine-record"
    assert all(v["findingsCoverage"] == "reported by the session" for v in rec["reviewers"])
    assert "findings: reported by the session" in rr.render(rec)


def test_check_runs_are_read_across_every_page_and_a_failed_page_is_unavailable(monkeypatch):
    # axis: CI pagination; a failing check on a later page hidden behind a green first page
    page1 = json.dumps({"total_count": 2, "check_runs": [{"status": "completed", "conclusion": "success"}]})
    page2 = json.dumps({"total_count": 2, "check_runs": [{"status": "completed", "conclusion": "failure"}]})
    status = json.dumps(NO_STATUS)
    def reader(out):
        return lambda argv: status if argv[2].endswith("/status") else out
    monkeypatch.setattr(rr, "_run", reader(page1 + page2))
    runs, st = rr._check_data(HEAD, "o/r")
    assert len(runs["check_runs"]) == 2 and rr.ci_state(runs, st) == "red"
    monkeypatch.setattr(rr, "_run", reader(page1 + "{broken"))
    assert rr._check_data(HEAD, "o/r") is None
    monkeypatch.setattr(rr, "_run", reader(None))
    assert rr._check_data(HEAD, "o/r") is None


def test_ungraded_or_forfeited_engine_receipt_is_not_a_completed_review():
    # axis: receipt grading; an ungraded or forfeited run counted as a review
    weak = dict(GOOD_RUN, graded=False)
    rec = build(account(), Fake(runs={"/run/code-reviewer": (weak, None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["status"] == "not-reviewed"


def test_raw_finding_without_a_recorded_outcome_keeps_the_record_not_reviewed(tmp_path):
    # axis: raw findings; a reviewer's finding with no recorded outcome counted as reviewed
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "raw-1", "severity": "Important", "body": "b"}]))
    rec = build(account(rawFindingsFiles=[str(raw)]))
    assert rec["status"] == "not-reviewed"
    assert "reviewer finding raw-1 in code.json has no recorded outcome" in rec["whatIsMissing"]


def test_left_for_owner_finding_is_not_reviewed_until_decided():
    # axis: left-for-owner; an undecided owner finding counted as reviewed
    rec = build(account(findings=[finding("f1", outcome="left-for-owner", reason="needs owner")]))
    assert rec["status"] == "not-reviewed" and "finding f1 waits for the owner's decision" in rec["whatIsMissing"]


def test_build_lane_marker_layout_comes_from_build_lane():
    # axis: marker layout; the writer spelling the marker's schema itself instead of reading it from build_lane
    assert rr.build_lane.BUILD_LANE_SCHEMA == "build-lane/1"


def test_lane_marker_is_none_when_the_marker_path_cannot_be_resolved(tmp_path, monkeypatch):
    # axis: marker read; an unresolvable or absent marker raising instead of reading as no marker
    def unresolvable(root):
        raise rr.store_core.RepoRootUnavailable("git could not be run")
    monkeypatch.setattr(rr.build_lane, "_marker_path", unresolvable)
    assert rr._lane_marker(str(tmp_path)) is None
    monkeypatch.setattr(rr.build_lane, "_marker_path", lambda root: str(tmp_path / "absent.json"))
    assert rr._lane_marker(str(tmp_path)) is None


def test_raw_finding_keeps_every_canonical_member_and_a_non_object_member_blocks_reviewed(tmp_path):
    # axis: raw evidence fidelity; evidence/suggestion/tradeoff dropped, or a malformed member read as an empty file
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "c-1", "title": "t", "file": "a.py", "line": 3, "severity": "Minor",
                                "body": "b", "evidence": "receipt", "suggestion": "fix", "tradeoff": True}]))
    row = build(account(rawFindingsFiles=[str(raw)]))["rawFindings"][0]
    assert (row["evidence"], row["suggestion"], row["tradeoff"], row["sourceFile"]) == ("receipt", "fix", True, "code.json")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([None, "reviewer error"]))
    rec = build(account(rawFindingsFiles=[str(bad)]))
    assert rec["status"] == "not-reviewed" and f"the findings file {bad} could not be read" in rec["whatIsMissing"]


def test_a_roster_with_no_planned_reviewer_that_ran_is_not_reviewed():
    # axis: nothing ran; an unplanned, unrun roster counted as reviewed
    rec = build(account(reviewers=[reviewer(planned=False, ran=False, runDir=None)]))
    assert rec["status"] == "not-reviewed" and "no planned reviewer ran" in rec["whatIsMissing"]


def test_a_single_account_too_large_refuses_before_any_archive_is_written(tmp_path):
    # axis: refusal ordering; an archive comment created and left unreferenced before the refusal
    fake = Fake()
    huge = [finding("h-1", body="h" * (rr.MAX_BODY_CHARS + 10))]
    out = rr.write(put(tmp_path, account(findings=huge)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and fake.comments == []


class Clock:
    """A datetime whose now() moves one second per call, so two writes never share a writtenAt."""
    n = 0

    @classmethod
    def now(cls, tz=None):
        cls.n += 1
        return datetime(2026, 1, 1, 0, 0, cls.n, tzinfo=timezone.utc)


def send(tmp_path, fake, **over):
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
    assert out["ok"], out
    return out


def test_every_earlier_record_is_kept_verbatim_in_its_own_append_only_archive(tmp_path):
    # axis: append-only archive; an earlier record rewritten, merged, or an archive comment edited instead of created
    fake = Fake()
    send(tmp_path, fake, sessionId="A")
    body1 = fake.marked()[0]["body"]
    send(tmp_path, fake, sessionId="B")
    body2 = fake.marked()[0]["body"]
    send(tmp_path, fake, sessionId="A")
    archives = [c for c in fake.comments if c["body"].startswith(rr.ARCHIVE_MARKER)]
    assert len(fake.marked()) == 1 and len(archives) == 2 and len(fake.comments) == 3
    assert archives[0]["body"].endswith(body1) and archives[1]["body"].endswith(body2)
    assert [a["id"] for a in rr.read(7, readers=fake.readers())["archives"]] == [a["id"] for a in archives]
    assert fake.edits == [fake.marked()[0]["id"]] * 2


def test_a_key_the_new_account_omits_is_owed_by_key_alone(tmp_path, monkeypatch):
    # axis: the set difference; an omitted earlier finding cleared by omission, or its body copied into the record
    monkeypatch.setattr(rr, "datetime", Clock)
    fake = Fake()
    send(tmp_path, fake, findings=[finding("a-1", body="LONGBODY " * 200)])
    since = rr.read(7, readers=fake.readers())["writtenAt"]
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert rec["status"] == "not-reviewed" and len(rec["owed"]) == 1
    (owed,) = rec["owed"]
    assert owed["id"] == "a-1" and owed["since"] == since and owed["findingKey"] and "body" not in owed
    assert any("a-1" in m and since in m for m in rec["whatIsMissing"])
    assert "LONGBODY" not in fake.marked()[0]["body"]
    assert "LONGBODY" in next(c for c in fake.comments if c["body"].startswith(rr.ARCHIVE_MARKER))["body"]


def test_an_owed_key_carries_across_writes_until_it_is_relisted(tmp_path, monkeypatch):
    # axis: owed carry; an owed key forgotten by the next write, its original since replaced, or never cleared by a relist
    monkeypatch.setattr(rr, "datetime", Clock)
    fake = Fake()
    send(tmp_path, fake, findings=[finding("a-1")])
    since = rr.read(7, readers=fake.readers())["writtenAt"]
    send(tmp_path, fake)
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert rec["status"] == "not-reviewed" and [(o["id"], o["since"]) for o in rec["owed"]] == [("a-1", since)]
    send(tmp_path, fake, findings=[finding("a-1")])
    rec = rr.read(7, readers=fake.readers())
    assert rec["owed"] == [] and rec["status"] == "reviewed"


def test_an_earlier_raw_key_is_owed_too(tmp_path):
    # axis: the set difference over raw rows; a reviewer finding the earlier record held dropped by a later account
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "r-1", "title": "t", "file": "a.py", "line": 3, "severity": "Minor"}]))
    fake = Fake()
    send(tmp_path, fake, findings=[finding("r-1")], rawFindingsFiles=[str(raw)])
    assert rr.read(7, readers=fake.readers())["status"] == "reviewed"
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert rec["status"] == "not-reviewed" and [o["id"] for o in rec["owed"]] == ["r-1"]
    # a key only a raw file held (never in the account) is owed by id, without an outcome
    only = Fake()
    send(tmp_path, only, rawFindingsFiles=[str(raw)])
    send(tmp_path, only)
    (owed,) = rr.read(7, readers=only.readers())["owed"]
    assert owed["id"] == "r-1" and "outcome" not in owed and "body" not in owed


def test_a_raw_line_is_normalized_so_it_matches_the_account_finding(tmp_path):
    # axis: raw line normalization; a raw " 291 " keyed apart from an account 291 and left with no recorded outcome
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "r-1", "title": "t", "file": "a.py", "line": " 291 ", "severity": "Minor"}]))
    rec = build(account(findings=[finding("f-1", title="t", file="a.py", line=291)], rawFindingsFiles=[str(raw)]))
    assert rec["rawFindings"][0]["line"] == 291
    assert not any("has no recorded outcome" in m for m in rec["whatIsMissing"]) and rec["status"] == "reviewed"


def test_only_the_current_accounts_raw_files_count(tmp_path):
    # axis: completeness scope; an unreadable file named by an earlier write still blocking a later account that omits it
    gone = str(tmp_path / "gone.json")
    fake = Fake()
    send(tmp_path, fake, rawFindingsFiles=[gone])
    first = rr.read(7, readers=fake.readers())
    assert first["status"] == "not-reviewed" and first["unreadFiles"] == [gone]
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert rec["unreadFiles"] == [] and rec["status"] == "reviewed"


def test_a_left_for_owner_finding_omitted_later_stays_visible(tmp_path):
    # axis: owner decisions across writes; a left-for-owner finding dropped from the owner's wait list by an omission
    fake = Fake()
    send(tmp_path, fake, findings=[finding("a-1", outcome="left-for-owner", reason="owner call")])
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert [(o["id"], o["outcome"]) for o in rec["owed"]] == [("a-1", "left-for-owner")]
    assert rec["leftForOwner"] == ["a-1"] and rec["status"] == "not-reviewed"
    assert "a-1" in rr.render(rec).split("Waiting for the owner:")[1]


def test_a_record_too_large_to_post_refuses_before_any_comment_is_written(tmp_path):
    # axis: pre-check ordering; the earlier record archived, or the record edited, before the new one is known to fit
    fake = Fake()
    send(tmp_path, fake)
    before, writes = [dict(c) for c in fake.comments], list(fake.writes)
    huge = [finding("h-1", body="h" * (rr.MAX_BODY_CHARS + 10))]
    out = rr.write(put(tmp_path, account(findings=huge)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large")
    assert fake.writes == writes and fake.edits == [] and fake.comments == before


def test_a_failed_archive_create_edits_nothing(tmp_path):
    # axis: archive-first ordering; the record comment edited after its earlier version failed to be archived
    fake = Fake()
    send(tmp_path, fake)
    before = fake.marked()[0]["body"]
    readers = dict(fake.readers(), create_comment=lambda pr, repo, body: None)
    out = rr.write(put(tmp_path, account(sessionId="B")), str(tmp_path), readers)
    assert (out["ok"], out["reason"]) == (False, "review-record-gh-failed")
    assert fake.edits == [] and fake.marked()[0]["body"] == before and len(fake.comments) == 1


def test_an_archive_over_the_github_limit_refuses():
    # axis: archive size; an archive past GitHub's comment limit sent instead of refused
    with pytest.raises(rr.Refusal) as e:
        rr.render_archive("x" * rr.GITHUB_MAX_CHARS)
    assert e.value.reason == "review-record-too-large"


def test_a_malformed_prior_never_raises_in_the_key_reader():
    # axis: malformed prior; non-list fields or non-dict items raising instead of being skipped
    assert rr._earlier_keys(None) == {}
    bad = {"findings": "x", "rawFindings": [None, 3, finding("r-1")], "owed": {"a": 1}, "archives": 5}
    assert [e["id"] for e in rr._earlier_keys(bad).values()] == ["r-1"]
    assert build(account(), prior=bad)["archives"] == []
