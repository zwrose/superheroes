import copy
import json
import os
import shutil
import subprocess
import sys

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
GOOD_RUN = {"runKind": "review", "resultKind": "findings", "resultDigest": "d1", "source": "codex",
            "engineModel": CODEX, "viewHeadSha": HEAD, "observation": {"tokens": 100, "wallSeconds": 120}}
PHRASES = ("no bugs", "bug-free", "bug free")


class Fake:
    """Injectable readers with an in-memory comment list; records create/edit calls."""

    def __init__(self, ci=GREEN, meta=None, marker=None, runs=None, issue_bodies=None):
        self.comments, self.writes = [], []
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
            "whatIsMissing", "sessionDisagreements", "checked", "history", "writtenAt"}
    for fake, lane, source, reason in cases:
        out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
        assert out["ok"] and out["action"] == "created"
        assert len(fake.marked()) == 1
        rec = rr.read(7, readers=fake.readers())
        assert keys <= set(rec)
        assert (rec["lane"]["value"], rec["lane"]["source"], rec["lane"]["reason"]) == (lane, source, reason)
        assert rec["finalCommit"]["sha"] == HEAD and rec["ci"]["state"] == "green" and rec["writtenAt"]


def test_branch_mismatched_marker_does_not_count():
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "other", "currentBranch": "b"}
    assert build(account(lane="micro"), Fake(marker=marker))["lane"]["source"] == "reported by the session"


def test_planned_reviewer_that_did_not_run_is_missing():
    rec = build(account(reviewers=[reviewer(ran=False, runDir=None)]))
    assert rec["reviewers"][0]["ran"] == "not-run"
    assert [m["name"] for m in rec["missingReviews"]] == ["code-reviewer"]


def test_session_only_run_counts_and_is_labelled():
    fake = Fake()
    acct = account(reviewers=[reviewer(runDir=None)])
    rec = build(acct, fake)
    assert rec["reviewers"][0]["ran"] == "reported-by-session" and rec["missingReviews"] == []
    assert rec["status"] == "reviewed"
    assert "- code-reviewer: ran (reported by the session)" in rr.render(rec)


def test_code_wins_over_the_session_account():
    fake = Fake(ci=PENDING, marker={"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b"})
    rec = build(account(lane="light", finalCommit=EARLIER, ci="green"), fake)
    assert (rec["lane"]["value"], rec["finalCommit"]["sha"], rec["ci"]["state"]) == ("full", HEAD, "pending")
    assert {d["fact"] for d in rec["sessionDisagreements"]} == {"lane", "finalCommit", "ci"}
    assert len(rec["sessionDisagreements"]) == 3


def test_null_outcome_is_not_reviewed():
    rec = build(account(findings=[finding(outcome=None)]))
    assert rec["status"] == "not-reviewed" and "finding code-001 has no outcome" in rec["whatIsMissing"]


def test_finding_without_reason_is_not_reviewed():
    rec = build(account(findings=[finding(reason="")]))
    assert rec["status"] == "not-reviewed" and "finding code-001 has no reason" in rec["whatIsMissing"]


@pytest.mark.parametrize("ci,word", [(RED, "red"), (PENDING, "pending"), (None, "none")])
def test_ci_that_is_not_green_is_not_reviewed(ci, word):
    rec = build(account(), Fake(ci=ci))
    assert rec["status"] == "not-reviewed" and rec["ci"]["state"] == word


def test_green_claimed_on_an_earlier_sha_is_not_reviewed():
    fake = Fake(ci=None, meta={"head": HEAD, "body": "", "issues": []})
    assert build(account(finalCommit=EARLIER, ci="green"), fake)["status"] == "not-reviewed"


def test_status_rejects_ci_read_on_a_different_sha_than_the_final_commit():
    rec = build(account())
    assert rec["status"] == "reviewed"
    rec["ci"] = dict(rec["ci"], sha=EARLIER)
    status, _, lines = rr._status(rec)
    assert status == "not-reviewed" and "not on the final commit" in lines[0]


def test_missing_security_review_parks_unless_the_owner_went_ahead():
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
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    for bad in ({"kind": "standing-ruling"}, {"kind": "owner-words", "words": "go"}):
        rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", **bad}]))
        assert rec["parked"] is True and rec["missingReviews"][0]["goAhead"] is None
        assert "the go-ahead for security-reviewer is incomplete" in rec["whatIsMissing"]


def test_clean_fixture_is_reviewed_and_never_claims_bug_free(tmp_path):
    fake = Fake()
    rec = build(account(findings=[finding()]), fake)
    assert rec["status"] == "reviewed" and rec["whatIsMissing"] == [] and rec["parked"] is False
    text = (json.dumps(rec) + rr.render(rec)).lower()
    assert not any(p in text for p in PHRASES)
    assert rec["cost"] == {"unit": "reviewer-minutes", "minutes": 2.0, "tokens": 100,
                           "source": "engine records", "notCounted": []}


@pytest.mark.parametrize("phrase", PHRASES)
def test_bug_free_claim_guard_raises(phrase):
    with pytest.raises(rr.Refusal):
        rr._assert_no_bug_free_claim(f"This change is {phrase.upper()}.")


@pytest.mark.parametrize("shape", ["array", "object"])
def test_read_back_survives_the_session_dir(tmp_path, shape):
    session = tmp_path / "session"
    session.mkdir()
    raw = session / "code.json"
    members = [{"id": f"n{i}", "title": "nit", "severity": "Nit"} for i in range(7)] + [{"id": "c1", "severity": "Minor"}]
    raw.write_text(json.dumps(members if shape == "array" else {"findings": members}))
    findings = [finding(f"n{i}", severity="Nit") for i in range(5)]
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
    rec = build(account(rawFindingsFiles=[str(tmp_path / "gone.json")]))
    assert rec["whatIsMissing"] == ["the findings file gone.json could not be read"]


def test_earlier_session_findings_survive_in_history(tmp_path):
    fake = Fake()
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    a_findings = [finding("a-1", outcome="left-for-owner", reason="owner call")]
    assert rr.write(put(a, account(sessionId="A", findings=a_findings)), str(a), fake.readers())["action"] == "created"
    assert rr.write(put(b, account(sessionId="B")), str(b), fake.readers())["action"] == "edited"
    shutil.rmtree(a), shutil.rmtree(b)
    rec = rr.read(7, readers=fake.readers())
    assert rec["sessionId"] == "B" and rec["findings"] == [] and len(fake.marked()) == 1
    assert [h["sessionId"] for h in rec["history"]] == ["A"]
    assert rec["history"][0]["findings"][0]["reason"] == "owner call"
    prior = rec
    again = build(account(sessionId="B"), fake, prior)
    assert [h["sessionId"] for h in again["history"]] == ["A"]


def test_engine_record_without_result_kind_is_not_run():
    weak = {k: v for k, v in GOOD_RUN.items() if k != "resultKind"}
    rec = build(account(), Fake(runs={"/run/code-reviewer": (weak, None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["reviewers"][0]["runNote"] == "no review result"
    assert rec["status"] == "not-reviewed"


def test_engine_record_of_another_run_kind_is_not_run():
    rec = build(account(), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, runKind="write"), None)}))
    assert rec["reviewers"][0]["ran"] == "not-run"


def test_engine_error_while_session_says_ran_is_a_disagreement():
    rec = build(account(), Fake(runs={"/run/code-reviewer": (None, "attempt-not-completed")}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["reviewers"][0]["runNote"] == "attempt-not-completed"
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]


def test_same_family_reviewer_needs_the_owner_word():
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
    assert rr._family("claude", "opus-9") == "anthropic"
    assert rr._family("elsewhere", "x") is None
    two = {"claude": lambda: ("opus-5.5", CODEX)}
    monkeypatch.setattr(rr, "_VENDOR_MODELS", dict(rr._VENDOR_MODELS, **two))
    monkeypatch.setattr(model_registry, "model_family",
                        lambda v, m: {"opus-5.5": "anthropic", CODEX: "openai"}.get(m))
    assert rr._family("claude", "opus-9") is None


def test_two_marker_comments_refuse_without_writing(tmp_path):
    fake = Fake()
    assert rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())["ok"]
    fake.comments.append(dict(fake.comments[0], id=2, url="u2"))
    fake.writes.clear()
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out.get("reason")) == (False, "review-record-duplicate") and fake.writes == []
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-duplicate"


def test_unparseable_prior_refuses_without_writing(tmp_path):
    fake = Fake()
    fake.comments = [{"id": 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u1"}]
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unreadable") and fake.writes == []
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"


def test_read_with_no_record_is_missing():
    assert rr.read(7, readers=Fake().readers())["reason"] == "review-record-missing"


def test_ci_state_truth_table():
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
    fake = Fake()
    fake.meta = None
    rec = build(account(finalCommit=EARLIER), fake)
    assert rec["finalCommit"] == {"sha": EARLIER, "source": "reported by the session"}
    assert rec["status"] == "not-reviewed" and "the final commit could not be read from the PR" in rec["whatIsMissing"]
    fake.meta, fake.ci = None, None
    rec = build(account(finalCommit=None), fake)
    assert rec["ci"] == {"state": "none", "sha": None, "source": "unavailable"}


def test_no_makers_is_not_reviewed():
    rec = build(account(makers=[]))
    assert rec["status"] == "not-reviewed" and "the makers' model families were not recorded" in rec["whatIsMissing"]
    assert rec["reviewers"][0]["independent"] is None and rec["reviewers"][0]["ran"] == "engine-record"


def test_null_outcome_writes_and_a_foreign_outcome_is_refused(tmp_path):
    fake = Fake()
    ok = rr.write(put(tmp_path, account(findings=[finding(outcome=None)])), str(tmp_path), fake.readers())
    assert ok["ok"] and ok["status"] == "not-reviewed"
    bad = rr.write(put(tmp_path, account(findings=[finding(outcome="done")])), str(tmp_path), fake.readers())
    assert (bad["ok"], bad["reason"]) == (False, "review-account-invalid") and "outcome" in bad["detail"]


@pytest.mark.parametrize("key", ["schema", "pr", "sessionId", "reviewers"])
def test_missing_required_key_is_refused_naming_the_key(tmp_path, key):
    acct = account()
    del acct[key]
    out = rr.write(put(tmp_path, acct), str(tmp_path), Fake().readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", key)


def test_too_large_body_is_refused(tmp_path):
    fake = Fake()
    big = [finding(f"f{i}", body="x" * 5000) for i in range(20)]
    out = rr.write(put(tmp_path, account(findings=big)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and fake.writes == []


def test_gh_failures_refuse(tmp_path):
    readers = dict(Fake().readers(), list_comments=lambda pr, repo: None)
    assert rr.write(put(tmp_path, account()), str(tmp_path), readers)["reason"] == "review-record-gh-failed"
    readers = dict(Fake().readers(), create_comment=lambda pr, repo, body: None)
    assert rr.write(put(tmp_path, account()), str(tmp_path), readers)["reason"] == "review-record-gh-failed"


def test_cli_read_without_gh_refuses(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "read", "--pr", "1"], capture_output=True,
                          text=True, env={"PATH": str(empty), "HOME": str(tmp_path)})
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False


def test_receipt_of_another_family_decides_independence():
    claude_run = dict(GOOD_RUN, source="claude", engineModel="opus-5.5")
    rec = build(account(), Fake(runs={"/run/code-reviewer": (claude_run, None)}))
    v = rec["reviewers"][0]
    assert v["family"] == "anthropic" and v["ran"] == "not-run" and rec["status"] == "not-reviewed"
    assert {"fact": "code-reviewer family", "session": "openai", "code": "anthropic"} in rec["sessionDisagreements"]


@pytest.mark.parametrize("seen", [EARLIER, None])
def test_receipt_for_another_or_unknown_commit_is_not_a_review(seen):
    run = dict(GOOD_RUN, viewHeadSha=seen)
    rec = build(account(), Fake(runs={"/run/code-reviewer": (run, None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["status"] == "not-reviewed"
    assert rec["reviewers"][0]["runNote"]


def test_credentials_are_scrubbed_before_the_record_is_published(tmp_path):
    token = "ghp_" + "A" * 36
    fake = Fake()
    acct = account(findings=[finding(body=f"key {token}", reason=f"saw {token}")])
    assert rr.write(put(tmp_path, acct), str(tmp_path), fake.readers())["ok"]
    assert token not in fake.marked()[0]["body"]
    assert rr.read(7, readers=fake.readers())["findings"][0]["body"] == "key [REDACTED]"


def test_inherited_history_that_would_overflow_is_compacted(tmp_path):
    fake = Fake()
    old = [finding("old-1", body="x" * 62700, outcome="left-for-owner", reason="owner call")]
    assert rr.write(put(tmp_path, account(sessionId="A", findings=old)), str(tmp_path), fake.readers())["ok"]
    out = rr.write(put(tmp_path, account(sessionId="B")), str(tmp_path), fake.readers())
    assert out["ok"] and out["action"] == "edited"
    hist = rr.read(7, readers=fake.readers())["history"]
    assert [h["sessionId"] for h in hist] == ["A"] and hist[0]["compacted"] is True
    assert hist[0]["findings"][0]["id"] == "old-1" and hist[0]["findings"][0]["reason"] == "owner call"
    assert "body" not in hist[0]["findings"][0]
