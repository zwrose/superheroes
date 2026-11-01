import copy
import json
import os
import shutil
import string
import subprocess
import sys
from urllib.parse import parse_qs

import pytest

import canon
import core_md
import gh_pages
import mode_registry
import model_registry
import pr_comment
import review_record as rr
import sanitized_view
import seat_map as seat_map_module

HEAD = "b" * 40
EARLIER = "a" * 40
CODEX = model_registry.codex_models()[0]
NO_STATUS = {"state": "pending", "total_count": 0, "statuses": []}
CI_RUN = {"id": 11, "name": "CI", "event": "push", "status": "completed", "conclusion": "success"}
GREEN = ({"total_count": 1, "check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]},
         NO_STATUS, {"workflow_runs": [CI_RUN]})
PENDING = ({"check_runs": [{"name": "validate", "status": "in_progress", "conclusion": None}]}, NO_STATUS,
           {"workflow_runs": [CI_RUN]})
RED = ({"check_runs": [{"name": "validate", "status": "completed", "conclusion": "failure"}]}, NO_STATUS,
       {"workflow_runs": [CI_RUN]})
GOOD_RUN = {"source": "codex", "engineModel": CODEX, "viewHeadSha": HEAD,
            "observation": {"tokens": 100, "wallSeconds": 120, "read": "engaged"}, "graded": True, "runKind": "review"}
PHRASES = ("no bugs", "bug-free", "bug free")
CANON_ID = "2026-01-02-abcd1234-1"
CANON_SOURCES = {"canonText": canon.entry_line(CANON_ID, "2026-01-02", "standing", "a ruling",
                                               'owner\'s words: "go"', "issue thread")}


class Fake:
    """Injectable readers with an in-memory comment list; records create calls."""

    def __init__(self, ci=GREEN, meta=None, marker=None, runs=None, issue_bodies=None, sources=None):
        self.comments, self.writes = [], []
        self.sources = sources or {}
        self.changed = ["README.md"]
        self.ci = ci
        self.meta = {"head": HEAD, "body": "", "issues": []} if meta is None else meta
        self.marker, self.runs, self.issue_bodies = marker, runs or {}, issue_bodies or {}

    def readers(self):
        return {
            "pr_meta": lambda pr, repo: self.meta,
            "issue_body": lambda n, repo: self.issue_bodies.get(n),
            "check_data": lambda sha, repo: self.ci,
            "ci_workflow": lambda root: ("absent", None),
            "lane_marker": lambda root: self.marker,
            "engine_run": lambda d: self.runs.get(d, (copy.deepcopy(GOOD_RUN), None)),
            "repo_name": lambda root: "o/r",
            "list_comments": lambda pr, repo: list(self.comments),
            "create_comment": self._create,
            "changed_paths": lambda pr, repo: self.changed,
            "decision_sources": self._sources,
        }

    def _sources(self, root, base_ref, sheet_answers, pr):
        extra = {"sheetAnswers": sheet_answers, "pr": pr} if isinstance(sheet_answers, dict) else {}
        return {**self.sources, **extra}

    def _create(self, pr, repo, body):
        c = {"id": len(self.comments) + 1, "author": "bot", "body": body, "url": f"http://c/{len(self.comments) + 1}"}
        self.comments.append(c)
        self.writes.append("create")
        return {"id": c["id"], "url": c["url"]}

    def marked(self):
        return [c for c in self.comments if c["body"].startswith(rr.MARKER)]

    def raws(self):
        return [c for c in self.comments if c["body"].startswith(rr.RAW_MARKER)]


def reviewer(name="code-reviewer", **over):
    return {"name": name, "vendor": "codex", "model": CODEX, "planned": True, "ran": True,
            "runDir": f"/run/{name}", **over}


def finding(fid="code-001", **over):
    return {"id": fid, "title": "t", "severity": "Minor", "file": "a.py", "line": 3, "body": "b",
            "consequence": "c", "outcome": "fixed", "reason": "fixed in 1a2b3c4", "reviewer": "code-reviewer", **over}


WRONG = {"verdict": "wrong", "reason": "the verifier showed the cited line does not exist"}


def wrong(fid="code-001", **over):
    """A finding the driver's verifier closed as wrong: the shown-wrong outcome with the verifier's wrong grade."""
    return finding(fid, outcome="shown-wrong", grade=WRONG, **over)


def closed(*findings):
    """The set the session writer passes `rr.write`: the record keys of the findings the verifier fold closed."""
    return {rr._key(f) for f in findings}


def account(**over):
    base = {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big",
            "finalCommit": HEAD, "ci": "green", "reviewers": [reviewer()], "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"],
            "makers": [{"family": "anthropic"}]}
    return {**base, **over}


def put(tmp_path, acct, name="account.json"):
    path = tmp_path / name
    path.write_text(json.dumps(acct))
    return str(path)


def build(acct, fake=None):
    return rr.build_record(acct, (fake or Fake()).readers())


def send(tmp_path, fake, **over):
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
    assert out["ok"], out
    return out


def test_each_lane_writes_one_record_with_every_key(tmp_path):
    # axis: lane resolution and the record's key set; a lane taking the wrong source or a record missing a key
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b", "issue": 9}
    cases = [
        (Fake(meta={"head": HEAD, "body": "x\n**Lane call:** light. small and safe\n", "issues": []}),
         "light", "PR lane call", "small and safe"),
        (Fake(meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "**Lane call:** micro: one line"}),
         "micro", "issue lane call", "one line"),
        (Fake(), "full", "reported by the session", "big"),
        (Fake(marker=marker, meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "no call"}),
         "full", "build lane marker", "big"),
    ]
    keys = {"schema", "pr", "sessionId", "lane", "finalCommit", "ci", "reviewers", "findings", "unreadFiles",
            "rawOutputs", "leftForOwner", "missingReviews", "rounds", "cost", "sessionDisagreements", "checked",
            "previousRecord", "writtenAt", "status", "parked", "whatIsMissing", "makers"}
    for fake, lane, source, reason in cases:
        out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
        assert out["ok"] and out["action"] == "created"
        assert len(fake.marked()) == 1
        rec = rr.read(7, readers=fake.readers())
        assert keys <= set(rec) and not {"owed", "archives", "rawFindings", "ownerWord"} & set(rec)
        assert (rec["lane"]["value"], rec["lane"]["source"], rec["lane"]["reason"]) == (lane, source, reason)
        if source == "build lane marker":
            assert rec["lane"]["reasonSource"] == "reported by the session"
        assert rec["finalCommit"]["sha"] == HEAD and rec["ci"]["state"] == "green" and rec["writtenAt"]


def test_branch_mismatched_marker_does_not_count():
    # axis: the build-lane marker's branch check; a marker from another branch deciding the lane
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "other", "currentBranch": "b", "issue": 9}
    fake = Fake(marker=marker, meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "no call"})
    assert build(account(lane="micro"), fake)["lane"]["source"] == "reported by the session"


def test_marker_for_another_issue_does_not_count():
    # axis: the build-lane marker's PR binding; a marker whose issue is not the PR's closing issue deciding the lane
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b", "issue": 5}
    fake = Fake(marker=marker, meta={"head": HEAD, "body": "**Lane call:** light. small\n", "issues": [9]},
                issue_bodies={9: "no call"})
    lane = build(account(lane="micro"), fake)["lane"]
    assert (lane["value"], lane["source"]) == ("light", "PR lane call")


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


def test_session_only_review_counts_only_on_the_final_commit():
    # axis: commit binding; a session-only review of an earlier or unstated commit credited as a review of the final commit
    reviewers = [reviewer(runDir=None)]
    rec = build(account(reviewers=reviewers, finalCommit=EARLIER))
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run"
    assert v["runNote"] == f"the session reported a review of {EARLIER[:7]}, not the final commit {HEAD[:7]}"
    assert {"fact": "code-reviewer ran", "session": True, "code": "not-run"} in rec["sessionDisagreements"]
    assert [m["name"] for m in rec["missingReviews"]] == ["code-reviewer"]
    assert (rec["status"], rec["parked"]) == ("not-reviewed", True)
    rec = build(account(reviewers=reviewers, finalCommit=None))
    assert rec["reviewers"][0]["ran"] == "not-run"
    assert rec["reviewers"][0]["runNote"] == "the session did not say which commit it reviewed"
    assert (rec["status"], rec["parked"]) == ("not-reviewed", True)
    rec = build(account(reviewers=reviewers, finalCommit=HEAD))
    assert rec["reviewers"][0]["ran"] == "reported-by-session"
    assert rec["missingReviews"] == [] and rec["status"] == "reviewed"


def test_code_wins_over_the_session_account():
    # axis: code over account; lane, final commit and CI taking the session's claim over code's reading
    fake = Fake(ci=PENDING, meta={"head": HEAD, "body": "", "issues": [9]},
                marker={"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b", "issue": "9"})
    rec = build(account(lane="light", finalCommit=EARLIER, ci="green"), fake)
    assert (rec["lane"]["value"], rec["finalCommit"]["sha"], rec["ci"]["state"]) == ("full", HEAD, "pending")
    assert {d["fact"] for d in rec["sessionDisagreements"]} == {"lane", "finalCommit", "ci"}
    assert len(rec["sessionDisagreements"]) == 3


def test_a_session_that_ended_on_another_commit_than_the_pr_head_is_not_reviewed():
    # axis: outcome binding; fixes finished on a later commit certifying a PR head they never reached
    rec = build(account(finalCommit=EARLIER))
    assert rec["reviewers"][0]["ran"] == "engine-record" and rec["reviewers"][0]["coversFinalCommit"]
    assert rec["status"] == "not-reviewed"
    assert f"the session ended on {EARLIER[:7]}, but the PR's final commit is {HEAD[:7]}" in rr.render(rec)
    assert build(account(finalCommit=HEAD))["status"] == "reviewed"


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
    ruling = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": CANON_ID}
    rec = build(account(reviewers=[reviewer(), sec], goAheads=[ruling]), Fake(sources=CANON_SOURCES))
    assert (rec["status"], rec["parked"]) == ("not-reviewed", False)
    assert rec["missingReviews"] == [{"name": "security-reviewer", "goAhead": ruling}]
    assert f"standing ruling {CANON_ID}" in " ".join(rec["whatIsMissing"])
    words = {"reviewer": "security-reviewer", "kind": "owner-words", "words": "skip it", "where": "PR comment"}
    rec = build(account(reviewers=[reviewer(), sec], goAheads=[words]))
    assert (rec["status"], rec["parked"]) == ("not-reviewed", False)
    assert "owner's words (PR comment)" in " ".join(rec["whatIsMissing"])


def test_go_ahead_missing_its_proof_does_not_count():
    # axis: go-ahead proof; a go-ahead without its canon id or words accepted
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    for bad in ({"kind": "standing-ruling"}, {"kind": "owner-words", "words": "go"},
                {"kind": "owner-words", "where": "PR comment"},
                {"kind": "owner-words", "where": "PR comment", "words": ""}):
        rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", **bad}]))
        assert rec["parked"] is True and rec["missingReviews"][0]["goAhead"] is None
        assert "the go-ahead for security-reviewer is incomplete" in rec["whatIsMissing"]


def test_malformed_go_ahead_does_not_lift_the_park():
    # axis: go-ahead proof; a go-ahead whose words, where or canon id is not a non-blank string lifting the park
    sec = reviewer("security-reviewer", ran=False, runDir=None)
    for bad in ({"kind": "owner-words", "words": True, "where": "PR comment"},
                {"kind": "owner-words", "words": "go", "where": True},
                {"kind": "owner-words", "words": "", "where": "PR comment"},
                {"kind": "owner-words", "words": "go"},
                {"kind": "owner-words", "words": "   ", "where": "PR comment"},
                {"kind": "owner-words", "words": ["go"], "where": "PR comment"},
                {"kind": "owner-words", "words": "go", "where": 7},
                {"kind": "standing-ruling", "canonId": True},
                {"kind": "standing-ruling", "canonId": ""},
                {"kind": "standing-ruling", "canonId": 7}):
        rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", **bad}]))
        assert rec["parked"] is True and rec["missingReviews"][0]["goAhead"] is None
        assert "the go-ahead for security-reviewer is incomplete" in rec["whatIsMissing"]
    good = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": CANON_ID}
    rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", "kind": "standing-ruling",
                                                    "canonId": True}, good]), Fake(sources=CANON_SOURCES))
    assert rec["parked"] is False and rec["missingReviews"][0]["goAhead"] == good


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
    assert fake.comments == [] and fake.writes == []


def test_read_back_survives_the_session_dir(tmp_path):
    # axis: the record as the one source; read-back needing the session's files, or the raw output lost
    session = tmp_path / "session"
    session.mkdir()
    raw = session / "code.json"
    raw.write_text(json.dumps([{"id": f"n{i}", "title": "nit", "severity": "Nit"} for i in range(7)]))
    findings = [finding(f"n{i}", severity="Nit") for i in range(7)]
    findings += [finding("c1", outcome="craft", reason="style call"), wrong("w1", reason="x")]
    fake = Fake()
    out = rr.write(put(session, account(findings=findings, rawFindingsFiles=[str(raw)])), str(tmp_path), fake.readers(),
                   verifier_closed=closed(findings[-1]))
    assert out["ok"]
    shutil.rmtree(session)
    rec = rr.read(7, readers=fake.readers())
    assert [f["id"] for f in rec["findings"]] == [f["id"] for f in findings]
    assert {f["outcome"] for f in rec["findings"]} >= {"craft", "shown-wrong"}
    assert [r["file"] for r in rec["rawOutputs"]] == ["code.json"] and rec["url"]
    assert '"title": "nit"' in fake.raws()[0]["body"]


def test_unreadable_raw_output_file_is_named_not_fatal(tmp_path):
    # axis: unreadable raw output; a missing or undecodable file hidden, or one that aborts the write
    rec = build(account(rawFindingsFiles=[str(tmp_path / "gone.json")]))
    assert rec["whatIsMissing"] == [f"the raw output file {tmp_path / 'gone.json'} could not be read"]
    assert rec["status"] == "not-reviewed"
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\xff\xfe\x00bad")
    rec = build(account(rawFindingsFiles=[str(bad)]))
    assert rec["status"] == "not-reviewed" and f"the raw output file {bad} could not be read" in rec["whatIsMissing"]


@pytest.mark.parametrize("secret", ["password", "pwd", "passphrase", "authorization", "cookie"])
def test_a_secret_named_field_is_redacted_whole_in_the_record(secret):
    # axis: structured credentials; a value scrubbed without its field name keeping a password or header credential
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {secret: "hunter2", "Nested": {"API_KEY": "abc", "note": "ok"}}
    body = rr.render(build(account(findings=[f])))
    assert "hunter2" not in body and "abc" not in body and '"note":"ok"' in body


def test_unknown_model_takes_the_one_family_of_its_vendor(monkeypatch):
    # axis: family inference; an unknown model given a family when its vendor has several
    assert rr._family("claude", "opus-9") == "anthropic"
    assert rr._family("elsewhere", "x") is None
    two = {"claude": lambda: ("opus-5.5", CODEX)}
    monkeypatch.setattr(rr, "_VENDOR_MODELS", dict(rr._VENDOR_MODELS, **two))
    monkeypatch.setattr(model_registry, "model_family",
                        lambda v, m: {"opus-5.5": "anthropic", CODEX: "openai"}.get(m))
    assert rr._family("claude", "opus-9") is None


def test_an_unparseable_prior_is_superseded_and_named_never_blocking(tmp_path):
    # axis: an unreadable latest record blocking every later write, or superseded without being named for the vet
    fake = Fake()
    fake.comments = [{"id": 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u1"}]
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert out["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and rec["earlierRecordsNotChecked"] == [{"id": 1, "url": "u1", "why": "unreadable"}]
    assert rec["previousRecord"]["id"] == 1 and rec["earlierRecords"] == ["u1"]
    assert "Earlier records not checked by code, which the vet reads directly: u1 (unreadable)." in fake.marked()[-1]["body"]
    send(tmp_path, fake)  # a further write still lists the unreadable record
    assert rr.read(7, readers=fake.readers())["earlierRecordsNotChecked"] == [{"id": 1, "url": "u1", "why": "unreadable"}]


def test_a_readable_prior_names_no_unreadable_record(tmp_path):
    # axis: the unreadable-earlier note shown when the earlier record read fine
    fake = Fake()
    send(tmp_path, fake)
    send(tmp_path, fake)
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and rec["earlierRecordsNotChecked"] == []
    assert "not checked by code" not in fake.marked()[-1]["body"]


def test_read_with_no_record_is_missing():
    # axis: read with no record; a missing record not refused as missing
    assert rr.read(7, readers=Fake().readers())["reason"] == "review-record-missing"


def test_ci_state_truth_table():
    # axis: CI state mapping; a check-run or status combination mapped to the wrong state
    done = lambda c: {"check_runs": [{"status": "completed", "conclusion": c}]}  # noqa: E731
    ran = {"workflow_runs": [CI_RUN]}
    assert rr.ci_state({"check_runs": []}, NO_STATUS) == "none"
    assert rr.ci_state({"check_runs": []}, {"state": "success", "total_count": 1, "statuses": [{"state": "success"}]}) == "none"
    assert rr.ci_state(done("success"), NO_STATUS, ran) == "green"
    assert rr.ci_state({"check_runs": [{"status": "in_progress"}]}, NO_STATUS) == "pending"
    assert rr.ci_state(done("failure"), NO_STATUS) == "red"
    assert rr.ci_state({"check_runs": [{"status": "in_progress"}, {"status": "completed", "conclusion": "timed_out"}]},
                       NO_STATUS) == "red"
    assert rr.ci_state(done("success"), {"state": "error", "total_count": 1, "statuses": [{"state": "error"}]}, ran) == "red"
    assert rr.ci_state(done("success"), {"state": "pending", "total_count": 1, "statuses": [{"state": "pending"}]}, ran) == "pending"


def test_unreadable_pr_is_not_reviewed():
    # axis: unreadable PR; a final commit from the session counted as read from the PR, or CI read without a commit
    fake = Fake()
    fake.meta = None
    rec = build(account(finalCommit=EARLIER), fake)
    assert rec["finalCommit"] == {"sha": EARLIER, "source": "reported by the session"}
    assert rec["status"] == "not-reviewed" and "the final commit could not be read from the PR" in rec["whatIsMissing"]
    fake.meta, fake.ci = None, None
    rec = build(account(finalCommit=None), fake)
    assert rec["ci"] == {"state": "none", "sha": None, "source": "unavailable", "workflow": None, "read": "CI could not be read"}


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


def test_a_large_body_posts_whole_in_parts_instead_of_being_refused(tmp_path):
    # axis: body size; an oversized record refused, trimmed or posted over the comment limit
    fake = Fake()
    big = [finding(f"f{i}", body="x" * 5000) for i in range(20)]
    out = rr.write(put(tmp_path, account(findings=big)), str(tmp_path), fake.readers())
    assert out["ok"] and out["parts"] >= 1
    assert all(len(c["body"]) <= rr.MAX_BODY_CHARS for c in fake.comments)
    assert [f["body"] for f in rr.read(7, readers=fake.readers())["findings"]] == ["x" * 5000] * 20


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


def test_credentials_are_scrubbed_before_the_record_is_published(tmp_path):
    # axis: scrubbing; a credential in account text reaching the posted comment
    token = "ghp_" + "A" * 36
    fake = Fake()
    acct = account(findings=[finding(body=f"key {token}", reason=f"saw {token}")])
    assert rr.write(put(tmp_path, acct), str(tmp_path), fake.readers())["ok"]
    assert token not in fake.marked()[0]["body"]
    assert rr.read(7, readers=fake.readers())["findings"][0]["body"] == "key [REDACTED]"


def test_every_reviewers_findings_coverage_is_marked_as_reported_by_the_session():
    # axis: findings coverage; an engine run shown as if the code held its findings
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)})
    rec = build(account(reviewers=[reviewer(runDir="/run/code-reviewer")]), fake)
    assert rec["reviewers"][0]["ran"] == "engine-record"
    assert all(v["findingsCoverage"] == "reported by the session" for v in rec["reviewers"])
    assert "findings: reported by the session" in rr.render(rec)


def cloud_proxy(routes, seen=None, override=None):
    """A stand-in for rr._run that answers as the cloud session's GitHub proxy does (#1890): any argv with
    --paginate, or naming repositories/, is refused (None); repos/... ?per_page=N&page=M is served as the M-th
    slice of the route's rows, [] past the end. routes maps a path to (rows, key): with a key the slice is
    wrapped as {"total_count": n, key: slice}. override maps a page number to the text served for it
    (None is a failed read); /status is served as NO_STATUS."""
    def run(argv, cwd=None):
        if seen is not None:
            seen.append(list(argv))
        if "--paginate" in argv or any("repositories/" in a for a in argv):
            return None
        path, _, query = argv[2].partition("?")
        if path.endswith("/status"):
            return json.dumps(NO_STATUS)
        q = parse_qs(query)
        number, size = int(q.get("page", ["1"])[0]), int(q.get("per_page", ["30"])[0])
        if override and number in override:
            return override[number]
        if path not in routes:
            return None
        rows, key = routes[path]
        piece = rows[(number - 1) * size:number * size]
        return json.dumps(piece if key is None else {"total_count": len(rows), key: piece})
    return run


def test_check_runs_are_read_across_every_page_and_a_failed_page_is_unavailable(monkeypatch):
    # axis: CI pagination; a failing check on a later page hidden behind a green first page
    ok, bad = {"status": "completed", "conclusion": "success"}, {"status": "completed", "conclusion": "failure"}
    path = f"repos/o/r/commits/{HEAD}/check-runs"
    actions = {"repos/o/r/actions/runs": ([], "workflow_runs")}
    seen = []
    monkeypatch.setattr(rr, "_run", cloud_proxy({path: ([ok] * 100 + [bad], "check_runs"), **actions}, seen))
    runs, st, wf = rr._check_data(HEAD, "o/r")
    assert len(runs["check_runs"]) == 101 and rr.ci_state(runs, st, wf) == "red"
    # each page is asked for by number on the same repos/... path; --paginate is never passed
    assert [a[2] for a in seen if "/check-runs" in a[2]] == [f"{path}?per_page=100&page=1", f"{path}?per_page=100&page=2"]
    assert not any("--paginate" in argv for argv in seen)
    monkeypatch.setattr(rr, "_run", cloud_proxy({path: ([ok] * 100 + [bad], "check_runs"), **actions}, override={2: "{broken"}))
    assert rr._check_data(HEAD, "o/r") is None
    monkeypatch.setattr(rr, "_run", cloud_proxy({path: ([ok] * 100 + [bad], "check_runs"), **actions}, override={2: None}))
    assert rr._check_data(HEAD, "o/r") is None


def test_left_for_owner_finding_reads_awaits_owner_until_decided():
    # axis: left-for-owner; an undecided owner finding counted as reviewed
    rec = build(account(findings=[finding("f1", outcome="left-for-owner", reason="needs owner")]))
    assert rec["status"] == "awaits-owner" and not rr.cleared(rec["status"])
    assert "finding f1 waits for the owner's decision" in rec["whatIsMissing"]
    assert rec["leftForOwner"] == ["f1"]


def test_build_lane_marker_layout_comes_from_build_lane():
    # axis: marker layout; the writer spelling the marker's schema itself instead of reading it from build_lane
    assert rr.build_lane.BUILD_LANE_SCHEMA == "build-lane/1"


def test_lane_marker_is_none_when_the_marker_path_cannot_be_resolved(tmp_path, monkeypatch):
    # axis: marker read; an unresolvable or absent marker raising instead of reading as no marker
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t",
                    "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    # a real repo with no marker file: _lane_marker reaches the real _marker_path and finds the file absent
    assert rr._lane_marker(str(tmp_path)) is None

    def unresolvable(root):
        raise rr.store_core.RepoRootUnavailable("git could not be run")
    monkeypatch.setattr(rr.build_lane, "_marker_path", unresolvable)
    assert rr._lane_marker(str(tmp_path)) is None
    monkeypatch.setattr(rr.build_lane, "_marker_path", lambda root: str(tmp_path / "absent.json"))
    assert rr._lane_marker(str(tmp_path)) is None


def test_a_roster_with_no_planned_reviewer_that_ran_is_not_reviewed():
    # axis: nothing ran; an unplanned, unrun roster counted as reviewed
    rec = build(account(reviewers=[reviewer(planned=False, ran=False, runDir=None)]))
    assert rec["status"] == "not-reviewed" and "no planned reviewer ran" in rec["whatIsMissing"]


def test_a_single_account_too_large_refuses_before_any_comment_is_posted(tmp_path):
    # axis: refusal ordering; a comment created before the record is known to fit
    fake = Fake()
    huge = [{"family": "f" * 40000}, {"family": "g" * 40000}]  # a summary line no part can hold
    out = rr.write(put(tmp_path, account(makers=huge)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and fake.comments == []


def test_a_record_too_large_to_post_leaves_the_earlier_comments_untouched(tmp_path):
    # axis: pre-check ordering; a comment created or changed before the new record is known to fit
    fake = Fake()
    send(tmp_path, fake)
    before, writes = [dict(c) for c in fake.comments], list(fake.writes)
    huge = [{"family": "f" * 40000}, {"family": "g" * 40000}]  # a summary line no part can hold
    out = rr.write(put(tmp_path, account(makers=huge)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large")
    assert fake.writes == writes and fake.comments == before


def test_same_title_at_another_line_is_another_finding(tmp_path):
    # axis: finding identity; two findings sharing file and title collapsing into one, so settling one settles both
    fake = Fake()
    two = [finding("c1", title="Leak", line=10), finding("c2", title="Leak", line=90)]
    send(tmp_path, fake, findings=two)
    out = rr.write(put(tmp_path, account(findings=[two[1]])), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unaccounted") and "c1" in out["detail"]
    assert "c2" not in out["detail"]


def test_finding_identity_is_not_the_reviewer_id(tmp_path):
    # axis: finding identity; the unaccounted check comparing reviewer ids, which recur across sessions
    fake = Fake()
    send(tmp_path, fake, findings=[finding("code-001", title="Leak", line=10)])
    other = finding("code-001", title="Leak", line=90)
    out = rr.write(put(tmp_path, account(findings=[other])), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unaccounted")
    assert len(fake.comments) == 1
    renamed = finding("renamed-9", title="Leak", line=10)
    out = rr.write(put(tmp_path, account(findings=[renamed])), str(tmp_path), fake.readers())
    assert out["ok"] and len(fake.comments) == 2


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


def test_w1_only_creates(tmp_path):
    # axis: create-only writes; an earlier record or raw comment edited, or a later record not linking the one before it
    fake = Fake()
    a1, a2 = finding("a-1"), finding("a-2")
    send(tmp_path, fake, sessionId="A", findings=[a1])
    first = fake.comments[0]["body"]
    send(tmp_path, fake, sessionId="B", findings=[a1, a2])
    second = fake.comments[1]["body"]
    send(tmp_path, fake, sessionId="C", findings=[a1, a2])
    assert len(fake.marked()) == 3 and len(fake.comments) == 3 and fake.writes == ["create"] * 3
    links = [rr._parse_body(c["body"])["previousRecord"] for c in fake.comments]
    assert links[0] is None
    assert links[1:] == [{"id": c["id"], "url": c["url"]} for c in fake.comments[:2]]
    assert fake.comments[0]["body"] == first and fake.comments[1]["body"] == second


def test_w2_the_one_check_across_sessions(tmp_path):
    # axis: the unaccounted check; an earlier finding dropped by a later account, or a pending one refused on relisting
    fake = Fake()
    send(tmp_path, fake, findings=[finding("a-1", outcome="left-for-owner", reason="owner call")])
    out = rr.write(put(tmp_path, account(findings=[])), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unaccounted")
    assert out["detail"] == "earlier findings with no outcome in this account: a-1"
    assert len(fake.comments) == 1
    out = rr.write(put(tmp_path, account(findings=[finding("a-1", outcome=None, reason="")])), str(tmp_path), fake.readers())
    assert out["ok"] and out["action"] == "created" and len(fake.comments) == 2
    assert rr.read(7, readers=fake.readers())["status"] == "not-reviewed"
    shown = wrong("a-1", reason="not a bug here")
    out = rr.write(put(tmp_path, account(findings=[shown])), str(tmp_path), fake.readers(), verifier_closed=closed(shown))
    assert out["ok"] and out["action"] == "created" and len(fake.comments) == 3


def test_w3_raw_output_verbatim_and_linked(tmp_path):
    # axis: raw output; a raw file holding a credential posted, or not linked as withheld
    text = 'intro\n```python\nprint(1)\n```\n{"pwd": "hunter2"}\nthe reviewer says no bugs here\n'
    raw = tmp_path / "raw.txt"
    raw.write_text(text)
    fake = Fake()
    send(tmp_path, fake, rawFindingsFiles=[str(raw)])
    (comment,) = fake.raws()
    body = comment["body"]
    assert len(fake.comments) == 2
    assert body == (f"{rr.RAW_MARKER}\nRaw output of one reviewer withheld: raw.txt. It contains credential-shaped "
                    "assignments on 1 line(s), so it is not posted. Its findings are in the review record on this PR.")
    assert "hunter2" not in body and "no bugs here" not in body and "print(1)" not in body
    rec = rr.read(7, readers=fake.readers())
    assert rec["rawOutputs"] == [{"file": "raw.txt", "id": comment["id"], "url": comment["url"], "withheld": True}]


def test_a_withheld_and_a_clean_raw_file_are_posted_as_withheld_and_verbatim(tmp_path):
    # axis: per-file withholding; a clean raw file withheld with its neighbour, or a credential file posted verbatim
    secret, clean = tmp_path / "secret.txt", tmp_path / "clean.txt"
    secret.write_text('line one\npassword = "LEAKMARK"\n')
    text = 'intro\n```python\nprint(1)\n```\nthe reviewer says no bugs here\n'
    clean.write_text(text)
    fake = Fake()
    send(tmp_path, fake, rawFindingsFiles=[str(secret), str(clean)])
    first, second = fake.raws()
    assert first["body"].startswith(f"{rr.RAW_MARKER}\nRaw output of one reviewer withheld: secret.txt.")
    assert "LEAKMARK" not in first["body"] and "line one" not in first["body"]
    assert second["body"].startswith(f"{rr.RAW_MARKER}\nRaw output of one reviewer, kept verbatim: clean.txt.")
    assert text in second["body"] and "\n````\n" in second["body"] and second["body"].endswith("\n````")
    rec = rr.read(7, readers=fake.readers())
    assert [(r["file"], r["withheld"]) for r in rec["rawOutputs"]] == [("secret.txt", True), ("clean.txt", False)]
    assert "LEAKMARK" not in "".join(c["body"] for c in fake.comments)


def test_w4_unreadable_raw_file_is_listed_and_not_posted(tmp_path):
    # axis: unreadable raw output on write; an unreadable file posted as an empty comment or left out of the record
    gone = str(tmp_path / "gone.txt")
    fake = Fake()
    send(tmp_path, fake, rawFindingsFiles=[gone])
    rec = rr.read(7, readers=fake.readers())
    assert rec["unreadFiles"] == [gone] and rec["status"] == "not-reviewed" and rec["rawOutputs"] == []
    assert fake.raws() == [] and len(fake.comments) == 1


def test_w5_raw_body_too_large_refuses_before_any_post(tmp_path):
    # axis: raw size; an oversized raw comment sent, or sent after the first raw comment was already posted
    small, huge = tmp_path / "small.txt", tmp_path / "huge.txt"
    small.write_text("fine")
    huge.write_text("x" * rr.GITHUB_MAX_CHARS)
    fake = Fake()
    out = rr.write(put(tmp_path, account(rawFindingsFiles=[str(small), str(huge)])), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and "huge.txt" in out["detail"]
    assert fake.comments == []


def test_raw_comment_create_failure_posts_no_record(tmp_path):
    # axis: raw create failure; a record posted linking a raw comment that was never created
    raw = tmp_path / "raw.txt"
    raw.write_text("text")
    fake = Fake()
    readers = dict(fake.readers(), create_comment=lambda pr, repo, body: None)
    out = rr.write(put(tmp_path, account(rawFindingsFiles=[str(raw)])), str(tmp_path), readers)
    assert (out["ok"], out["reason"]) == (False, "review-record-gh-failed") and fake.comments == []


def test_w6_ran_means_a_run_record_for_the_final_commit():
    # axis: the final-commit run test; a run record of another or no commit, or an engine error, counted as a run
    assert "resultKind" not in GOOD_RUN and GOOD_RUN["graded"] is True
    rec = build(account(), Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)}))
    v = rec["reviewers"][0]
    assert v["ran"] == "engine-record" and v["observation"] == GOOD_RUN["observation"]
    assert rec["status"] == "reviewed" and rec["sessionDisagreements"] == []
    cases = [
        ((dict(GOOD_RUN, viewHeadSha=EARLIER), None), f"the run record covers {EARLIER[:7]}, not the final commit {HEAD[:7]}"),
        ((dict(GOOD_RUN, viewHeadSha=None), None), "the run record names no commit"),
        (({k: x for k, x in GOOD_RUN.items() if k != "viewHeadSha"}, None), "the run record names no commit"),
        ((None, "attempt-not-completed"), "attempt-not-completed"),
        ((None, None), "no run record"),
        (([GOOD_RUN], "ignored"), "ignored"),
    ]
    for result, note in cases:
        rec = build(account(), Fake(runs={"/run/code-reviewer": result}))
        v = rec["reviewers"][0]
        assert v["ran"] == "not-run" and v["runNote"] == note and "observation" not in v
        assert rec["status"] == "not-reviewed"
        assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]
    rec = build(account(reviewers=[reviewer(ran=False)]), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, viewHeadSha=EARLIER), None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["sessionDisagreements"] == []


def test_w6b_a_run_record_on_the_final_commit_that_was_not_graded_is_not_a_review():
    # axis: forfeit vs run; a forfeited or failed run on the final commit credited as a completed review
    note = "the run on the final commit did not complete a review (forfeit or failure)"
    for graded in (False, None):
        bad = dict(GOOD_RUN, graded=graded)
        rec = build(account(), Fake(runs={"/run/code-reviewer": (bad, None)}))
        v = rec["reviewers"][0]
        assert v["ran"] == "not-run" and v["runNote"] == note and "observation" not in v
        assert rec["status"] == "not-reviewed" and rec["parked"] is True
        assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]
    rec = build(account(reviewers=[reviewer(ran=False)]), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, graded=False), None)}))
    assert rec["reviewers"][0]["ran"] == "not-run" and rec["status"] == "not-reviewed"


def test_w6c_a_graded_write_run_on_the_final_commit_is_not_a_review():
    # axis: run kind; a successful dispatch-write on the final commit credited as a completed review
    rec = build(account(), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, runKind="write"), None)}))
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and v["runNote"] == "the run on the final commit was not a completed review run"
    assert "observation" not in v and rec["status"] == "not-reviewed" and rec["parked"] is True


def test_an_account_that_omits_its_findings_is_refused():
    # axis: findings presence; an omitted findings member published as a clean review
    acct = account()
    del acct["findings"]
    with pytest.raises(rr.Refusal) as e:
        build(acct)
    assert (e.value.reason, e.value.detail) == ("review-account-invalid", "findings")


@pytest.mark.parametrize("title", ["Hardcoded " + "ghp_" + "A" * 36, 'leaks "password": [REDACTED] in logs'])
def test_the_stored_finding_key_is_opaque_and_survives_redaction(tmp_path, title):
    # axis: identity under redaction; a key built from title text changed or leaked by the scrubber
    fake = Fake()
    titled = finding("a-1", title=title)
    send(tmp_path, fake, findings=[titled])
    stored = rr.read(7, readers=fake.readers())["findings"][0]
    assert stored["findingKey"] == rr._key(titled) and stored["findingKey"].startswith("rr1:")
    assert "s3cret" not in stored["findingKey"] and "ghp_" not in stored["findingKey"]
    assert "password" not in stored["findingKey"]
    shown = dict(titled, outcome="shown-wrong", reason="r", grade=WRONG)
    out = rr.write(put(tmp_path, account(findings=[shown])), str(tmp_path), fake.readers(), verifier_closed=closed(shown))
    assert out["ok"] and out["action"] == "created"


@pytest.mark.parametrize("text", ['{"passphrase":"EXAMPLE_SECRET"}', '{\\"passphrase\\":\\"EXAMPLE_SECRET\\"}',
                                  '{"Authorization":"Basic dXNlcjpwYXNz"}', "passphrase=EXAMPLE_SECRET",
                                  '{"passphrase":"pre\\"EXAMPLE_SECRET"}'])
def test_quoted_credentials_are_redacted_in_raw_output_and_record_strings(tmp_path, text):
    # axis: quoted credentials; a passphrase or JSON Authorization value published from raw output or a finding string
    raw, withheld = rr.render_raw("r.txt", text)
    assert withheld and "EXAMPLE_SECRET" not in raw and "dXNlcjpwYXNz" not in raw
    f = finding("a-1", outcome="fixed", reason="r", body=text)
    body = rr.render(build(account(findings=[f])))
    assert "EXAMPLE_SECRET" not in body and "dXNlcjpwYXNz" not in body and "[REDACTED FIELD]" in body


def test_w7_read_returns_the_latest(tmp_path):
    # axis: read of several records; the first record returned, or the earlier ones left unlisted
    fake = Fake()
    send(tmp_path, fake, sessionId="A")
    send(tmp_path, fake, sessionId="B")
    rec = rr.read(7, readers=fake.readers())
    assert rec["ok"] and rec["sessionId"] == "B" and rec["url"] == fake.comments[1]["url"]
    assert rec["earlierRecords"] == [fake.comments[0]["url"]]


def test_w8_the_repository_is_resolved_once_from_the_repo_root(tmp_path):
    # axis: repo binding; GitHub calls left to the current directory, or the resolved repo not passed to every reader
    seen, roots = [], []
    fake = Fake(meta={"head": HEAD, "body": "", "issues": [9]}, issue_bodies={9: "no lane call here"})
    base = fake.readers()

    def spy(name):
        def reader(*args):
            seen.append((name, args[1]))  # every GitHub reader takes the repo second
            return base[name](*args)
        return reader
    readers = dict(base, repo_name=lambda root: roots.append(root) or "o/r",
                   **{n: spy(n) for n in ("pr_meta", "issue_body", "check_data", "list_comments", "create_comment")})
    out = rr.write(put(tmp_path, account()), str(tmp_path / "root"), readers)
    assert out["ok"] and roots == [str(tmp_path / "root")]
    assert {n for n, _ in seen} >= {"pr_meta", "issue_body", "check_data", "list_comments", "create_comment"}
    assert all(repo == "o/r" for _, repo in seen)
    # an account naming its repo needs no lookup
    roots.clear()
    assert rr.write(put(tmp_path, account(repo="x/y")), str(tmp_path), readers)["ok"] and roots == []
    # an unresolvable repo refuses before any GitHub call
    seen.clear()
    nothing = Fake()
    called = []
    out = rr.write(put(tmp_path, account()), str(tmp_path),
                   dict(nothing.readers(), repo_name=lambda root: None, list_comments=lambda *a: called.append(a)))
    assert called == []
    assert (out["ok"], out["reason"]) == (False, "review-record-gh-failed") and nothing.comments == []


def test_w9_the_stored_key_is_compared_not_one_recomputed_from_redacted_text(tmp_path):
    # axis: identity before redaction; a finding whose title was redacted in the record read as unaccounted
    fake = Fake()
    titled = finding("a-1", title='leaks "password": "s3cret" in logs')
    send(tmp_path, fake, findings=[titled])
    stored = rr.read(7, readers=fake.readers())["findings"][0]
    assert "s3cret" not in stored["title"] and stored["findingKey"] == rr._key(titled)
    assert rr._key({k: v for k, v in stored.items() if k != "findingKey"}) != stored["findingKey"]
    shown = dict(titled, outcome="shown-wrong", reason="r", grade=WRONG)
    out = rr.write(put(tmp_path, account(findings=[shown])), str(tmp_path), fake.readers(), verifier_closed=closed(shown))
    assert out["ok"] and out["action"] == "created"


@pytest.mark.parametrize("bad", [{"a": 1}, "x", None, [1], [None]])
def test_w10_a_malformed_earlier_findings_list_is_superseded_and_named(tmp_path, bad):
    # axis: malformed prior; a findings field that is not a list of objects read as having no findings, or blocking every later write
    fake = Fake()
    rec = build(account())
    rec["findings"] = bad
    fake.comments = [{"id": 1, "author": "a", "body": rr.render(rec), "url": "u1"}]
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert out["ok"] and len(fake.marked()) == 2
    assert rr.read(7, readers=fake.readers())["earlierRecordsNotChecked"] == [{"id": 1, "url": "u1", "why": "unreadable"}]


MAKERS = [{"family": "anthropic", "source": "builder"}]
OWNER_WORD = {"words": "go ahead", "where": "http://c/9"}


CLAUDE = model_registry.claude_models()[0]
CLAUDE_RUN = dict(GOOD_RUN, source="claude", engineModel=CLAUDE)


def maker_family_reviewer(name="code-reviewer", **over):
    return reviewer(name, vendor="claude", model=CLAUDE, **over)


def test_x1_makers_and_owner_word_pass_through_and_independence_shows(tmp_path):
    # axis: makers and ownerWord dropped or altered; notIndependent shown only for a computed same-family row
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
    send(tmp_path, fake, makers=MAKERS, reviewers=[maker_family_reviewer(ownerWord=OWNER_WORD)])
    rec = rr.read(7, readers=fake.readers())
    assert rec["makers"] == MAKERS
    assert rec["reviewers"][0]["notIndependent"] is True and rec["reviewers"][0]["ownerWord"] == OWNER_WORD
    body = fake.marked()[0]["body"]
    assert "Makers: anthropic." in body and "not independent of the makers" in body
    assert "owner's word: http://c/9" in body


def test_x2_the_account_cannot_claim_independence_or_its_absence():
    # axis: notIndependent taken from the account; an independent reviewer shown as not independent, or the reverse
    claimed = build(account(makers=MAKERS, reviewers=[reviewer(notIndependent=True, ownerWord=OWNER_WORD)]))
    without = build(account())
    assert [claimed[k] for k in ("status", "parked", "whatIsMissing")] == \
        [without[k] for k in ("status", "parked", "whatIsMissing")]
    assert "notIndependent" not in claimed["reviewers"][0] and claimed["reviewers"][0]["ownerWord"] == OWNER_WORD
    denied = build(account(reviewers=[maker_family_reviewer(notIndependent=False, ownerWord=OWNER_WORD)]),
                   Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)}))
    assert denied["reviewers"][0]["notIndependent"] is True


@pytest.mark.parametrize("over, key", [
    ({"makers": "anthropic"}, "makers"),
    ({"makers": [{}]}, "makers[0]"),
    ({"makers": [{"family": ""}]}, "makers[0]"),
    ({"makers": [{"family": 3}]}, "makers[0]"),
    ({"reviewers": [reviewer(notIndependent="yes")]}, "reviewers[0].notIndependent"),
    ({"reviewers": [reviewer(ownerWord="ok")]}, "reviewers[0].ownerWord"),
])
def test_x3_malformed_pass_through_fields_refuse(tmp_path, over, key):
    # axis: validation of the pass-through fields; a malformed value accepted, or refused without naming its key
    fake = Fake()
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", key)
    assert fake.writes == []


def test_x3_none_and_false_are_accepted_and_ignored():
    # axis: optional fields; None refused, or False dropped instead of carried as given
    rec = build(account(makers=None, reviewers=[reviewer(notIndependent=False, ownerWord=None)]))
    assert rec["makers"] == [] and "notIndependent" not in rec["reviewers"][0]
    assert "ownerWord" not in rec["reviewers"][0]


SAFE_TAIL = "SAFE_TAIL_TEXT"


@pytest.mark.parametrize("text", [
    'password: "LEAKMARK"',
    '"password": "pre\\"LEAKMARK"',
    '{"token": ["LEAKMARK","q4r5s6"]}',
    'PASSPHRASE="a b LEAKMARK"',
    "authorization=Basic LEAKMARK",
    'password: "line1\nLEAKMARK"',
    '{"passphrase": [\n  "LEAKMARK"\n]}',
    "private_key: |\n  AAAA\n  LEAKMARK\nnext: ok",
    "note\n-----BEGIN RSA PRIVATE KEY-----\nLEAKMARK\n-----END RSA PRIVATE KEY-----\nafter",
    '{"credentials": {"user":"u","password":"p1",\n"deep":{"k":["LEAKMARK"]}}, "ok": 1}',
    '{"secret": [{"a":"x"},\n{"b":"LEAKMARK"}]}',
    '{"secret": {"a": "has ] bracket",\n "b": "LEAKMARK"}}',
    '{"secret": {"a": "LEAKMARK", "b": [1,\nmore',
    "password: hunter LEAKMARK & more",
    "password: &db_password LEAKMARK",
    '{\\"cookie\\": \\"LEAKMARK\\"}',
    "api key = LEAKMARK",
    "credentials:\n  plainnested\n  LEAKMARK\nafter: ok",
    '{"password":"x","credentials":{\n"nested":"LEAKMARK"\n}}',
    "password: | # note\n  LEAKMARK",
    'password = """\nLEAKMARK\n"""',
    'os.environ["PASSWORD"] = "LEAKMARK"',
    "params[password]=LEAKMARK",
    "{token}: LEAKMARK",
    "db_password: LEAKMARK",
    '"db.password": "LEAKMARK"',
    "x-api-key=LEAKMARK",
    'config.SECRET_KEY = "LEAKMARK"',
    "aws_secret_access_key: LEAKMARK",
])
def test_every_credential_form_is_withheld_or_redacted_whole(text):
    # axis: withholding; a credential value form (quoted, escaped, array, block, PEM, spaced, second key) reaching a posted comment
    assert "LEAKMARK" in text
    body, withheld = rr.render_raw("f.json", text)
    assert withheld is True and "LEAKMARK" not in body
    f = finding("a-1", body=text, reason="r")
    posted = rr.render(build(account(findings=[f])))
    assert "LEAKMARK" not in posted
    assert rr._parse_body(posted)["findings"][0]["body"] == "[REDACTED FIELD]"


def test_numeric_and_other_typed_secret_fields_are_redacted():
    # axis: typed redaction; a number, bool or float under a secret-named key published because only str/list/dict were redacted
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {"password": 123456, "token": True, "pwd": 1.5, "note": "ok", "cookie": None}
    posted = rr.render(build(account(findings=[f])))
    assert "123456" not in posted and '"token": true' not in posted and '"pwd": 1.5' not in posted
    assert rr._parse_body(posted)["findings"][0]["evidence"] == {
        "password": "[REDACTED]", "token": "[REDACTED]", "pwd": "[REDACTED]", "note": "ok", "cookie": None}


def test_text_holding_an_escaped_credential_object_is_withheld():
    # axis: whole-text withholding; an escaped credential object inside a larger text posted with the text around it
    obj = json.dumps({"credentials": {"password": "EXAMPLE_SECRET"}})
    text = json.dumps({"body": "see " + obj}) + "\n" + SAFE_TAIL
    assert rr._scrub_text(text) == "[REDACTED FIELD]"
    nested = json.dumps({"body": obj, "suggestion": "keep", "evidence": SAFE_TAIL}, indent=1)
    assert rr._scrub_text(nested) == "[REDACTED FIELD]"
    body, withheld = rr.render_raw("r.json", text)
    assert withheld is True and "EXAMPLE_SECRET" not in body and SAFE_TAIL not in body


def test_a_prose_mention_without_a_separator_is_kept():
    # axis: over-withholding; a text that only names a secret-shaped word treated as an assignment
    text = "the password field is unchecked\nsecond line"
    assert rr._has_secret(text) is False and rr._scrub_text(text) == text
    body, withheld = rr.render_raw("r.txt", text)
    assert withheld is False and text in body and "kept verbatim: r.txt." in body


def test_scrub_text_is_linear_on_adversarial_input():
    # axis: resource exhaustion; key-prefix runs making detection quadratic before publication
    import time
    for n in ("pass" * 50000, "p" * 200000, "password " * 22000, "password" + " " * 200000 + "x", '"' * 200000):
        start = time.monotonic()
        rr._has_secret(n[:200000])
        rr._scrub_text(n[:200000])
        assert time.monotonic() - start < 2


def test_the_module_has_one_detector_and_no_value_end_tracking():
    # axis: one home; an old line scanner, block indicator or bracket-balancer left beside the detector
    for gone in ("_open_after", "_REDACTED_LINE", "_BLOCK_INDICATOR", "_PEM_END", "_balanced_end", "_KEYED_SECRET"):
        assert not hasattr(rr, gone)
    assert callable(rr._has_secret)


@pytest.mark.parametrize("row", [
    {"id": "f1", "outcome": "left-for-owner", "reason": "owner call"},
    {"id": "f1", "title": "t", "outcome": "fixed", "reason": "r"},
    {"id": "f1", "file": "a.py", "outcome": "fixed", "reason": "r"},
])
def test_a_finding_row_without_identity_inputs_is_refused(tmp_path, row):
    # axis: finding identity; id-only rows sharing one key so the carry-forward guard cannot see an omission
    fake = Fake()
    out = rr.write(put(tmp_path, account(findings=[row])), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-account-invalid")
    assert fake.comments == []


def test_cli_write_then_read_round_trip_through_a_real_journal_and_a_gh_process(tmp_path, monkeypatch):
    # axis: the CLI entry point; write/read composed with the real engine journal and a gh executable at the process boundary
    import test_engine_dispatch as ted
    stream = ted._codex_event_stream(json.dumps({"resultKind": "findings", **ted._native_review_branch("findings")}))
    run_dir = str(tmp_path / "run")
    res = ted.ED.dispatch_review(
        seat=ted._codex_seat(), prompt_path=ted._valid_prompt(tmp_path), repo_root=ted._repo(tmp_path),
        run_engine=ted.FakeRunner([(stream, False, 0, "")]), build_view=ted._fake_build_view(tmp_path),
        run_dir=run_dir)
    assert res["ok"] is True
    journal, jerr = ted.ED.run_execution_record(run_dir)
    assert jerr is None and journal["graded"] is True
    head = journal["viewHeadSha"]
    state = tmp_path / "gh-state.json"
    state.write_text(json.dumps({"comments": []}))
    gh_dir = tmp_path / "bin"
    gh_dir.mkdir()
    gh = gh_dir / "gh"
    gh.write_text(f"""#!{sys.executable}
import json, sys
a = sys.argv[1:]
state = {str(state)!r}
head = {head!r}
s = json.load(open(state))
if "--paginate" in a:
    sys.exit(3)
if a[:2] == ["repo", "view"]:
    print(json.dumps({{"nameWithOwner": "o/r"}}))
elif a[:2] == ["pr", "view"]:
    print(json.dumps({{"headRefOid": head, "body": "", "closingIssuesReferences": []}}))
elif a[0] == "api" and "/check-runs?per_page=100&page=" in a[1]:
    page = int(a[1].rsplit("page=", 1)[1])
    rows = [{{"name": "v", "status": "completed", "conclusion": "success"}}] if page == 1 else []
    print(json.dumps({{"total_count": 1, "check_runs": rows}}))
elif a[0] == "api" and a[1].endswith("/status"):
    print(json.dumps({{"state": "pending", "total_count": 0, "statuses": []}}))
elif a[0] == "api" and "-X" in a:
    body = open(a[a.index("-F") + 1].split("=@", 1)[1]).read()
    n = len(s["comments"]) + 1
    s["comments"].append({{"id": n, "user": {{"login": "bot"}}, "body": body, "html_url": "http://c/%d" % n}})
    json.dump(s, open(state, "w"))
    print(json.dumps({{"id": n, "html_url": "http://c/%d" % n}}))
elif a[0] == "api" and "/comments?per_page=100&page=" in a[1]:
    page = int(a[1].rsplit("page=", 1)[1])
    print(json.dumps(s["comments"][(page - 1) * 100:page * 100]))
else:
    sys.exit(2)
""")
    gh.chmod(0o755)
    env = {"PATH": f"{gh_dir}:/usr/bin:/bin", "HOME": str(tmp_path)}
    raw = tmp_path / "code.json"
    raw.write_text(json.dumps([{"id": "n1", "title": "nit", "token": "ghp_" + "A" * 36}], indent=1))
    acct = account(finalCommit=head, reviewers=[reviewer(runDir=run_dir)], findings=[finding("f1")],
                   rawFindingsFiles=[str(raw)])
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "write", "--account", put(tmp_path, acct),
                           "--repo-root", str(tmp_path)], capture_output=True, text=True, env=env)
    out = json.loads(proc.stdout)
    assert proc.returncode == 0 and out["ok"] and out["action"] == "created", (proc.stdout, proc.stderr)
    stored = json.loads(state.read_text())["comments"]
    assert [c["body"].startswith(rr.RAW_MARKER) for c in stored] == [True, False]
    assert stored[0]["body"].startswith(f"{rr.RAW_MARKER}\nRaw output of one reviewer withheld: code.json.")
    assert "ghp_" not in stored[0]["body"] and "nit" not in stored[0]["body"]
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "read", "--pr", "7"], capture_output=True,
                          text=True, env=env)
    got = json.loads(proc.stdout)
    assert proc.returncode == 0 and got["ok"] and got["url"] == "http://c/2", (proc.stdout, proc.stderr)
    assert [f["id"] for f in got["findings"]] == ["f1"]
    assert got["reviewers"][0]["ran"] == "engine-record"
    assert [r["file"] for r in got["rawOutputs"]] == ["code.json"] and got["rawOutputs"][0]["url"] == "http://c/1"
    assert got["rawOutputs"][0]["withheld"] is True


def test_cloud_cli_write_reads_through_rest_only_and_takes_the_issue_from_the_body_first_line(tmp_path):
    # axis: the CLI entry point in a cloud session; no gh pr/issue/repo call, and the first-line issue reaches the lane read
    import test_engine_dispatch as ted
    stream = ted._codex_event_stream(json.dumps({"resultKind": "findings", **ted._native_review_branch("findings")}))
    run_dir = str(tmp_path / "run")
    res = ted.ED.dispatch_review(
        seat=ted._codex_seat(), prompt_path=ted._valid_prompt(tmp_path), repo_root=ted._repo(tmp_path),
        run_engine=ted.FakeRunner([(stream, False, 0, "")]), build_view=ted._fake_build_view(tmp_path),
        run_dir=run_dir)
    assert res["ok"] is True
    journal, jerr = ted.ED.run_execution_record(run_dir)
    assert jerr is None and journal["graded"] is True
    head = journal["viewHeadSha"]
    state, argv_log = tmp_path / "gh-state.json", tmp_path / "gh-argv.log"
    state.write_text(json.dumps({"comments": []}))
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    gh_dir = tmp_path / "bin"
    gh_dir.mkdir()
    gh = gh_dir / "gh"
    gh.write_text(f"""#!{sys.executable}
import json, os, sys
a = sys.argv[1:]
state = {str(state)!r}
head = {head!r}
checkout = {str(checkout)!r}
with open({str(argv_log)!r}, "a") as log:
    log.write(json.dumps(a) + "\\n")
s = json.load(open(state))
if "--paginate" in a:
    sys.exit(3)
if a == ["api", "repos/{{owner}}/{{repo}}", "--jq", ".full_name"]:
    if os.path.realpath(os.getcwd()) != os.path.realpath(checkout):
        sys.exit(2)
    print("o/r")
elif a == ["api", "repos/o/r/pulls/7"]:
    print(json.dumps({{"head": {{"sha": head}}, "body": "Closes #9.\\nmore"}}))
elif a == ["api", "repos/o/r/issues/9"]:
    print(json.dumps({{"body": "intro\\n**Lane call:** light because small\\n"}}))
elif a[0] == "api" and "/check-runs?per_page=100&page=" in a[1]:
    page = int(a[1].rsplit("page=", 1)[1])
    rows = [{{"name": "v", "status": "completed", "conclusion": "success"}}] if page == 1 else []
    print(json.dumps({{"total_count": 1, "check_runs": rows}}))
elif a[0] == "api" and a[1].endswith("/status"):
    print(json.dumps({{"state": "pending", "total_count": 0, "statuses": []}}))
elif a[0] == "api" and "-X" in a:
    body = open(a[a.index("-F") + 1].split("=@", 1)[1]).read()
    n = len(s["comments"]) + 1
    s["comments"].append({{"id": n, "user": {{"login": "bot"}}, "body": body, "html_url": "http://c/%d" % n}})
    json.dump(s, open(state, "w"))
    print(json.dumps({{"id": n, "html_url": "http://c/%d" % n}}))
elif a[0] == "api" and "/comments?per_page=100&page=" in a[1]:
    page = int(a[1].rsplit("page=", 1)[1])
    print(json.dumps(s["comments"][(page - 1) * 100:page * 100]))
else:
    sys.exit(2)
""")
    gh.chmod(0o755)
    env = {"PATH": f"{gh_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_CODE_REMOTE": "true"}
    acct = account(finalCommit=head, reviewers=[reviewer(runDir=run_dir)])
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "write", "--account", put(tmp_path, acct),
                           "--repo-root", str(checkout)], capture_output=True, text=True, env=env,
                          cwd=str(tmp_path))
    out = json.loads(proc.stdout)
    assert proc.returncode == 0 and out["ok"] and out["action"] == "created", (proc.stdout, proc.stderr)
    calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    assert not [c for c in calls if c[0] in ("pr", "issue", "repo")], calls
    assert ["api", "repos/o/r/pulls/7"] in calls and ["api", "repos/o/r/issues/9"] in calls
    posted = rr._parse_body(json.loads(state.read_text())["comments"][-1]["body"])
    assert posted["lane"]["value"] == "light" and posted["lane"]["source"] == "issue lane call"


def test_the_default_readers_are_the_rest_set_only_when_the_cloud_variable_is_true(monkeypatch):
    # axis: reader selection; a cloud session on the old gh pr/issue/repo readers, or an off-cloud session moved off them
    old = {"pr_meta": rr._pr_meta, "issue_body": rr._issue_body, "repo_name": rr._repo_name}
    rest = {"pr_meta": rr._pr_meta_rest, "issue_body": rr._issue_body_rest, "repo_name": rr._repo_name_rest}
    own = {"pr_meta": "mine", "issue_body": "mine", "repo_name": "mine"}
    monkeypatch.delenv(rr.cloud_pass.CLOUD_ENV, raising=False)
    got = rr._readers(None)
    assert {k: got[k] for k in old} == old
    assert {k: v for k, v in rr._readers(own).items() if k in own} == own
    monkeypatch.setenv(rr.cloud_pass.CLOUD_ENV, "true")
    got = rr._readers(None)
    assert {k: got[k] for k in rest} == rest
    assert {k: v for k, v in rr._readers(own).items() if k in own} == own
    monkeypatch.setenv(rr.cloud_pass.CLOUD_ENV, "1")
    got = rr._readers(None)
    assert {k: got[k] for k in old} == old


@pytest.mark.parametrize("body,repo,expected", [
    pytest.param(None, "o/r", [], id="body-none"),
    pytest.param("", "o/r", [], id="body-empty"),
    pytest.param("Part of #4.", "o/r", [], id="non-closing-verb"),
    pytest.param("Closes #12.", "o/r", [12], id="closes"),
    pytest.param("closes #12", "o/r", [12], id="lowercase"),
    pytest.param("Fixes: #3", "o/r", [3], id="colon"),
    pytest.param("Closes #3. Resolves #5. Closes #3.", "o/r", [3, 5], id="several-deduplicated"),
    pytest.param("Closes #3, #5", "o/r", [3], id="one-issue-per-keyword"),
    pytest.param("Intro\nCloses #3.", "o/r", [], id="not-on-the-first-line"),
    pytest.param("Closes #3.\r\nx", "o/r", [3], id="crlf"),
    pytest.param("Closes O/R#8", "o/r", [8], id="qualified-same-repo"),
    pytest.param("Closes x/y#8", "o/r", [], id="qualified-other-repo"),
    pytest.param("Encloses #3", "o/r", [], id="not-a-whole-word-keyword"),
    pytest.param("Closes #3a", "o/r", [], id="not-a-whole-number"),
])
def test_closing_issues_reads_only_the_first_line_and_fails_closed(body, repo, expected):
    # axis: the closing-issue rule; a later line, another repository, a non-closing verb or a partial word read as a closed issue
    assert rr._closing_issues(body, repo) == expected


def test_rest_pr_and_issue_readers_fail_closed_on_a_missing_or_malformed_answer(monkeypatch):
    # axis: the REST readers; an absent, headless or non-object answer read as PR or issue data
    for answer in (None, {"body": "Closes #1."}, {"head": {}, "body": ""}, ["x"]):
        monkeypatch.setattr(rr, "_gh_json", lambda *a, answer=answer: answer)
        assert rr._pr_meta_rest(7, "o/r") is None
    for answer in (None, ["x"], "text"):
        monkeypatch.setattr(rr, "_gh_json", lambda *a, answer=answer: answer)
        assert rr._issue_body_rest(9, "o/r") is None
    monkeypatch.setattr(rr, "_gh_json", lambda *a: {"head": {"sha": HEAD}, "body": None})
    assert rr._pr_meta_rest(7, "o/r") == {"head": HEAD, "body": "", "issues": []}


def test_a_credential_used_as_a_dictionary_key_is_redacted_and_colliding_keys_survive():
    # axis: key scrubbing; a credential quoted as a mapping key published verbatim, or two redacted keys overwriting each other
    k1, k2 = "ghp_" + "A" * 36, "ghp_" + "B" * 36
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {k1: "source one", k2: "source two", "note": "ok", "password=x": "v"}
    posted = rr.render(build(account(findings=[f])))
    assert k1 not in posted and k2 not in posted and "password=x" not in posted
    ev = rr._parse_body(posted)["findings"][0]["evidence"]
    assert ev["note"] == "ok"
    assert len([k for k in ev if k.startswith("[REDACTED KEY]")]) == 3
    assert "[REDACTED KEY]" in ev and "[REDACTED KEY]-1" in ev and "[REDACTED KEY]-2" in ev
    assert all(ev[k] == "[REDACTED]" for k in ev if k.startswith("[REDACTED KEY]"))


def test_cost_and_observation_token_counts_survive_the_credential_scrub():
    # axis: count fields; the number-of-tokens fields redacted although "tokens" is not a secret-shaped key
    posted = rr.render(build(account()))
    rec = rr._parse_body(posted)
    assert rec["cost"]["tokens"] == 100
    assert rec["reviewers"][0]["observation"]["tokens"] == 100
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {"token": "x"}
    assert rr._parse_body(rr.render(build(account(findings=[f]))))["findings"][0]["evidence"] == {"token": "[REDACTED]"}


@pytest.mark.parametrize("val", ["password: LEAKMARK", ["password: LEAKMARK"], {"service": "password: LEAKMARK"}])
def test_tokens_key_holding_a_credential_shaped_string_is_still_withheld(val):
    # axis: "tokens" is an allowlisted count key, but only for a number; a non-number under it is secret at the key level
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {"tokens": val}
    posted = rr.render(build(account(findings=[f])))
    assert "LEAKMARK" not in posted
    assert rr._parse_body(posted)["findings"][0]["evidence"] == {"tokens": "[REDACTED]"}


@pytest.mark.parametrize("text", [
    json.dumps({"msg": "config:\npassword: LEAKMARK"}),
    "note config:" + "\\" + "n" + "password: LEAKMARK",
    '{"pass' + '\\' + 'u0077ord": "LEAKMARK"}',
], ids=["json-escaped-newline", "non-json-escaped-newline", "unicode-escaped-key"])
def test_escaped_newline_and_unicode_escaped_keys_are_withheld(text):
    # axis: decoded view; a credential key hidden behind a JSON escape ("\npassword", "password") read as another key
    assert "LEAKMARK" in text and "\n" not in text
    if "u0077" in text:
        assert "\\" + "u0077" in text
    else:
        assert "\\" + "n" in text
    assert rr._has_secret(text) is True
    body, withheld = rr.render_raw("f.json", text)
    assert withheld is True and "LEAKMARK" not in body
    assert rr._scrub_text(text) == "[REDACTED FIELD]"


_ESCAPED_SPACE = "\\" + "u0020"
_ESCAPED_HEADER = _ESCAPED_SPACE.join(["-----BEGIN", "RSA", "PRIVATE", "KEY-----"])


@pytest.mark.parametrize("text", [
    '{"note": "' + _ESCAPED_HEADER + "\\" + 'nLEAKMARK"}',
    "see the attached block " + _ESCAPED_HEADER + " LEAKMARK",
], ids=["json-escaped-spaces", "non-json-escaped-spaces"])
def test_private_key_block_behind_json_escapes_is_withheld(text):
    # axis: decoded view; a private-key header written with JSON-escaped spaces posted because only the raw text was matched
    assert "LEAKMARK" in text
    assert rr._PEM_BEGIN.search(text) is None
    assert rr._has_secret(text) is True
    body, withheld = rr.render_raw("f.json", text)
    assert withheld is True and "LEAKMARK" not in body
    assert rr._scrub_text(text) == "[REDACTED FIELD]"


@pytest.mark.parametrize("text", [
    "the `password`: LEAKMARK",
    "`db_password` = LEAKMARK",
    "**password**: LEAKMARK",
    "*api_key*: LEAKMARK",
    "<password>: LEAKMARK",
], ids=["backtick-quoted", "backtick-spaced", "bold", "italic", "angle-brackets"])
def test_a_marked_up_secret_key_is_withheld(text):
    # axis: withholding of a marked-up key; a backtick, asterisk or angle bracket between the key and its separator hid the assignment
    assert "LEAKMARK" in text
    body, withheld = rr.render_raw("f.md", text)
    assert withheld is True and "LEAKMARK" not in body
    assert rr._scrub_text(text) == "[REDACTED FIELD]"
    f = finding("a-1", outcome="fixed", reason="r", body=text)
    posted = rr.render(build(account(findings=[f])))
    assert "[REDACTED FIELD]" in posted and "LEAKMARK" not in posted


def test_any_non_word_run_before_the_separator_is_detected():
    # axis: withholding at the gap; a mark or a run of marks between a secret key and its separator listed instead of excluded
    for c in (ch for ch in string.punctuation + " \t" if ch not in ":=_"):
        for s in ":=":
            assert rr._has_secret(f"password{c}{s} LEAKMARK") is True, (c, s)
            assert rr._has_secret(f"password{c}{c} {s}LEAKMARK") is True, (c, s)
    assert rr._has_secret("“password”: LEAKMARK") is True
    assert rr._has_secret("password" + "*" * 64 + ": LEAKMARK") is True
    assert rr._has_secret("password" + " " * 64 + "= LEAKMARK") is True
    for gap in (65, 200):
        for sep in ("= ", ": "):
            text = "password" + " " * gap + sep + "LEAKMARK"
            assert rr._has_secret(text) is True, (gap, sep)
            body, withheld = rr.render_raw("f.md", text)
            assert withheld is True and "LEAKMARK" not in body
            assert rr._scrub_text(text) == "[REDACTED FIELD]"
    assert rr._has_secret("password" + "*" * 5000 + ": LEAKMARK") is True


def test_marked_up_count_keys_and_split_lines_stay_readable():
    # axis: over-withholding; a marked-up count key with a number, or a key and separator on different lines, withheld
    for text in ("tokens: 12", "**input_tokens**: 12"):
        body, withheld = rr.render_raw("f.md", text)
        assert withheld is False and text in body
        assert rr._scrub_text(text) == text
    assert rr.render_raw("f.md", "**input_tokens**: abc")[1] is True
    assert rr._has_secret("the password\n: see the note below") is False


def test_a_long_run_with_no_separator_is_kept():
    # axis: over-withholding; a secret-shaped word followed by a long run of marks and no ':' or '=' withheld
    text = "the password " + "-" * 70 + " rotated last week"
    assert rr._has_secret(text) is False
    body, withheld = rr.render_raw("f.md", text)
    assert withheld is False and text in body
    assert rr._scrub_text(text) == text


@pytest.mark.parametrize("key", ["dbpassword", "apikeys", "passwordhash", "mytoken", "xsecret", "PRIVATEKEYS"])
def test_compound_keys_are_secret(key):
    # axis: key shape; a compound key written with no separator slipping past whole-word matching
    assert rr._secret_key(key) is True
    body, withheld = rr.render_raw("f.json", f'"{key}": "LEAKMARK"')
    assert withheld is True and "LEAKMARK" not in body


def test_numeric_count_keys_post_and_non_numeric_ones_do_not():
    # axis: count exemption; a count key exempted whatever its value, or a key outside the allowlist exempted
    counts = '"input_tokens": 12, "output_tokens": 3, "output_tokens_count": 7'
    body, withheld = rr.render_raw("f.json", counts)
    assert withheld is False and counts in body
    assert rr.render_raw("f.json", '"token_count": 7')[1] is True
    body, withheld = rr.render_raw("f.json", '"input_tokens": "abc"')
    assert withheld is True and "abc" not in body
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {"tokens": 100}
    assert rr._parse_body(rr.render(build(account(findings=[f]))))["findings"][0]["evidence"] == {"tokens": 100}
    f["evidence"] = {"tokens": "x"}
    assert rr._parse_body(rr.render(build(account(findings=[f]))))["findings"][0]["evidence"] == {"tokens": "[REDACTED]"}


def test_count_exemption_needs_the_whole_value_to_be_a_number():
    # axis: count exemption; a count key exempted because its value merely starts with a digit
    leak = '{"tokens":"1234LEAKMARK"}'
    body, withheld = rr.render_raw("f.json", leak)
    assert withheld is True and "LEAKMARK" not in body
    ok = '{"input_tokens": 1234, "output_tokens": "56"}'
    body, withheld = rr.render_raw("f.json", ok)
    assert withheld is False and ok in body
    assert rr.render_raw("f.json", '"input_tokens": 12abc')[1] is True
    # fail-closed edges: text after the number, and a mismatched quote pair, are not counts
    assert rr.render_raw("f.json", '"input_tokens": 12 abc')[1] is True
    assert rr.render_raw("f.json", '"input_tokens": "123' + "'")[1] is True


CODEX_STDOUT = "\n".join([
    '{"type":"thread.started","thread_id":"0199a213-81c0-7800-8aa1-bbab2a035a53"}',
    '{"type":"turn.started"}',
    '{"type":"item.completed","item":{"id":"item_0","type":"reasoning","text":"Reading the diff for a.py"}}',
    '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"{\\"findings\\": [{\\"title\\": '
    '\\"Off by one in the loop\\", \\"file\\": \\"a.py\\", \\"line\\": 3, \\"severity\\": \\"Minor\\", '
    '\\"body\\": \\"The range stops one short.\\"}]}"}}',
    '{"type":"turn.completed","usage":{"input_tokens":1234,"cached_input_tokens":0,"cache_write_input_tokens":0,'
    '"output_tokens":56,"reasoning_output_tokens":12}}',
])


def test_codex_stdout_with_usage_counts_is_posted_not_withheld():
    # axis: over-withholding; ordinary Codex output withheld because a usage-count key contains the substring "token"
    assert '"input_tokens":1234' in CODEX_STDOUT
    body, withheld = rr.render_raw("codex.json", CODEX_STDOUT)
    assert withheld is False and CODEX_STDOUT in body


@pytest.mark.parametrize("key,secret", [
    ("access_token", True), ("api_token", True), ("client_secret", True), ("db_password", True),
    ("API_KEY", True), ("api key", True), ("private key", True), ("privateKey", True),
    ("accessToken", True), ("Authorization", True), ("x-auth-token", True),
    ("SECRET_KEY", True), ("aws_secret_access_key", True), ("secretKey", True), ("credentials", True),
    ("db_passwords", True), ("password_hash", True),
    ("token_count", True),
    # fail-closed over-redaction: a secret substring anywhere makes the key secret; the count exemption (below)
    # alone decides whether a number under a count key posts
    ("tokenizer", True), ("passwordless", True), ("secretary", True), ("tokens", True),
    ("input_tokens", True), ("output_tokens", True), ("cached_tokens", True), ("cached_input_tokens", True),
    ("note", False),
])
def test_key_shape_decides_secret(key, secret):
    # axis: key shape; a key judged secret by whole words only, instead of any secret substring of the normalised key
    assert rr._secret_key(key) is secret
    if key.endswith("tokens"):
        assert rr._is_count_key(key) is True


def test_numeric_values_under_secret_keys_stay_withheld_or_redacted():
    # axis: value type; a number under a secret-shaped key exempted from withholding or redaction
    assert rr.render_raw("f.json", '"access_token": "1234"')[1] is True
    assert rr.render_raw("f.json", "password: 1234")[1] is True
    for evidence in ({"password": 4321}, {"api key": 4321}):
        f = finding("a-1", outcome="fixed", reason="r")
        f["evidence"] = evidence
        posted = rr.render(build(account(findings=[f])))
        assert "4321" not in posted
        assert rr._parse_body(posted)["findings"][0]["evidence"] == {next(iter(evidence)): "[REDACTED]"}


def test_spaced_secret_keys_are_redacted_in_structured_fields():
    # axis: spaced keys; "api key" and "private key" as mapping keys leaving their values in a posted record
    f = finding("a-1", outcome="fixed", reason="r")
    f["evidence"] = {"api key": "LEAKMARK", "private key": "LEAKMARK"}
    posted = rr.render(build(account(findings=[f])))
    assert "LEAKMARK" not in posted


def test_one_run_record_claimed_by_two_reviewers_credits_neither(tmp_path):
    # axis: run binding; one engine run credited to several reviewers (the same directory, even spelled differently)
    real = tmp_path / "run"
    real.mkdir()
    alias = str(tmp_path / "x" / ".." / "run")
    (tmp_path / "x").mkdir()
    a, b = reviewer("code-reviewer", runDir=str(real)), reviewer("security-reviewer", runDir=alias)
    fake = Fake(runs={str(real): (copy.deepcopy(GOOD_RUN), None), alias: (copy.deepcopy(GOOD_RUN), None)})
    rec = build(account(reviewers=[a, b]), fake)
    assert [v["ran"] for v in rec["reviewers"]] == ["not-run", "not-run"]
    assert all(v["runNote"] == "the run record is claimed by more than one reviewer" for v in rec["reviewers"])
    assert rec["status"] != "reviewed"
    solo = build(account(reviewers=[a]), fake)
    assert solo["reviewers"][0]["ran"] == "engine-record"


THIRD = "c" * 40


def _fix_round_account(**over):
    specialists = [reviewer(n, commit=EARLIER) for n in ("security-reviewer", "design-reviewer")]
    return account(reviewers=[*specialists, reviewer("auditor")], **over)


def _fix_round_runs():
    return {"/run/security-reviewer": (dict(GOOD_RUN, viewHeadSha=EARLIER), None),
            "/run/design-reviewer": (dict(GOOD_RUN, viewHeadSha=EARLIER), None),
            "/run/auditor": (copy.deepcopy(GOOD_RUN), None)}


def test_a_fix_round_review_reads_reviewed():
    # axis: which commit a run is credited for; specialists who reviewed the earlier commit counted as not run
    rec = build(_fix_round_account(), Fake(runs=_fix_round_runs()))
    spec = [v for v in rec["reviewers"] if v["name"] != "auditor"]
    assert [(v["ran"], v["commit"], v["coversFinalCommit"]) for v in spec] == [("engine-record", EARLIER, False)] * 2
    auditor = rec["reviewers"][2]
    assert (auditor["ran"], auditor["commit"], auditor["coversFinalCommit"]) == ("engine-record", None, True)
    assert rec["status"] == "reviewed" and rec["missingReviews"] == [] and rec["sessionDisagreements"] == []
    text = rr.render(rec)
    assert f"- security-reviewer: ran (engine record) on {EARLIER[:7]}" in text
    assert f"- design-reviewer: ran (engine record) on {EARLIER[:7]}" in text
    assert "- auditor: ran (engine record);" in text


def test_a_head_moved_after_the_last_round_reads_not_reviewed():
    # axis: reviewed status when no credited run covers the final commit; a head that moved after the last round
    fake = Fake(runs=_fix_round_runs(), meta={"head": THIRD, "body": "", "issues": []})
    rec = build(_fix_round_account(), fake)
    assert [v["ran"] for v in rec["reviewers"]] == ["engine-record"] * 2 + ["not-run"]
    assert not any(v["coversFinalCommit"] for v in rec["reviewers"])
    assert rec["status"] == "not-reviewed"
    assert f"no planned reviewer's run covers the final commit {THIRD[:7]}" in rec["whatIsMissing"]


def test_a_row_listed_for_one_commit_is_not_credited_for_another():
    # axis: refusal of a mismatched run; a run record of one commit credited to a row listed for another
    rec = build(account(reviewers=[reviewer(commit=EARLIER)]), Fake())
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and v["coversFinalCommit"] is False and "observation" not in v
    assert v["runNote"] == f"the run record covers {HEAD[:7]}, not the commit this reviewer was listed for {EARLIER[:7]}"
    assert [m["name"] for m in rec["missingReviews"]] == ["code-reviewer"]
    assert {"fact": "code-reviewer ran", "session": True, "code": "not-run"} in rec["sessionDisagreements"]
    assert rec["status"] == "not-reviewed"


def test_a_session_only_row_naming_a_commit_is_reported_by_the_session():
    # axis: session-only commit binding; a session-reported review of a named earlier commit dropped or credited as final
    rec = build(account(reviewers=[reviewer(runDir=None, commit=EARLIER), reviewer("auditor", runDir=None)]))
    v = rec["reviewers"][0]
    assert (v["ran"], v["commit"], v["coversFinalCommit"]) == ("reported-by-session", EARLIER, False)
    assert rec["sessionDisagreements"] == [] and rec["status"] == "reviewed"


@pytest.mark.parametrize("bad", [7, ["x"], True])
def test_a_non_string_commit_is_refused(bad):
    # axis: the commit key's type; a non-string commit accepted into the account
    with pytest.raises(rr.Refusal) as e:
        build(account(reviewers=[reviewer(commit=bad)]))
    assert (e.value.reason, e.value.detail) == ("review-account-invalid", "reviewers[0].commit")


@pytest.mark.parametrize("empty", ["", None])
def test_an_empty_commit_is_the_same_as_none(empty):
    # axis: the empty commit; an empty or null commit read as a named commit
    same = build(account(reviewers=[reviewer()]))["reviewers"][0]
    rec = build(account(reviewers=[reviewer(commit=empty)]))
    assert rec["reviewers"][0] == same and rec["reviewers"][0]["commit"] is None
    assert rec["status"] == "reviewed" and rec["reviewers"][0]["coversFinalCommit"] is True


def test_the_marker_decided_lane_keeps_its_reason():
    # axis: the lane reason's presence; a marker-decided lane returning no reason or a reason with no source
    marker = {"schema": "build-lane/1", "lane": "full", "branch": "b", "currentBranch": "b", "issue": 9}
    meta = {"head": HEAD, "body": "", "issues": [9]}
    fake = Fake(marker=marker, meta=meta, issue_bodies={9: "**Lane call:** full. spans three contracts"})
    rec = build(account(), fake)
    assert rec["lane"] == {"value": "full", "source": "build lane marker", "reason": "spans three contracts",
                           "reasonSource": "issue lane call"}
    assert "Lane: full (build lane marker), because spans three contracts (issue lane call)." in rr.render(rec)
    fake = Fake(marker=marker, meta=meta, issue_bodies={9: "no call"})
    rec = build(account(), fake)
    assert rec["lane"] == {"value": "full", "source": "build lane marker", "reason": "big",
                           "reasonSource": "reported by the session"}
    assert "Lane: full (build lane marker), because big (reported by the session)." in rr.render(rec)
    rec = build(account(laneReason=None), fake)
    assert rec["lane"]["reason"] is None and rec["lane"]["reasonSource"] is None
    assert "Lane: full (build lane marker)." in rr.render(rec)


# --- the risk floor: the record's laneBasis and its below-floor line ---

PAYMENTS = {"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
            "undo": "Hard: a charge needs a refund."}
LIGHT_PR = {"head": HEAD, "body": "**Lane call:** light. small and safe\n", "issues": []}
BASIS_KEYS = {"floor", "lane", "why", "riskAreas", "touched", "unmatchable", "proposed", "proposalTaken", "source"}
FILES_SOURCE = "lane rule over the PR's changed files"
UNREAD = rr.lane_call.WHY_NO_PATHS + " the PR's changed files could not be read"
PAY_FLOOR = rr.lane_call.WHY_TOUCHES + " Payments (src/payments/charge.py)"


def risk_repo(tmp_path, areas=(PAYMENTS,)):
    """A repo whose core.md holds the given risk areas, in the test's isolated store."""
    repo = str(tmp_path)
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
                         "patterns": "- x: a.ts:1"}, "confirmed", now="2026-06-26")
    assert core_md.write_project_config_item(repo, core_md.RISK_AREAS_KEY, list(areas))["action"] == "written"
    return repo


def gh_files(*entries):
    """The PR files endpoint's rows, served by canned_gh one page of 100 at a time."""
    return list(entries)


def canned_gh(monkeypatch, out):
    """Stub rr._run. A list is the PR's files, served page by page as the cloud proxy does; any other value
    (None, text) is the one answer given to every call."""
    calls = []
    if isinstance(out, list):
        # the endpoint is served under either repo spelling: o/r when the caller names the repo, {owner}/{repo}
        # when it leaves gh to fill the current one in (the record path, changed_paths(7, None))
        serve = cloud_proxy({"repos/o/r/pulls/7/files": (out, None),
                             "repos/{owner}/{repo}/pulls/7/files": (out, None)})
        monkeypatch.setattr(rr, "_run", lambda argv, cwd=None: calls.append(argv) or serve(argv))
    else:
        monkeypatch.setattr(rr, "_run", lambda argv, cwd=None: calls.append(argv) or out)
    return calls


def real_reader_record(repo, monkeypatch, out):
    """A light-lane record built with the real changed_paths reader over canned gh output."""
    canned_gh(monkeypatch, out)
    readers = {**Fake(meta=LIGHT_PR).readers(), "changed_paths": rr.changed_paths}
    return rr.build_record(account(repoRoot=repo), readers)


def test_the_record_carries_the_lane_basis_with_one_shape(tmp_path):
    # axis: the record's laneBasis key; a record without it, or with a basis not carrying every lane_call key
    repo = risk_repo(tmp_path)
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(repoRoot=repo), fake)
    assert set(rec["laneBasis"]) == BASIS_KEYS and rec["laneBasis"]["source"] == FILES_SOURCE
    assert rec["laneBasis"]["floor"] == "full" and rec["laneBasis"]["why"][0] == PAY_FLOOR
    assert rec["laneBasis"]["touched"] == [{"name": "Payments", "matched": ["src/payments/charge.py"]}]
    fake.changed = None
    assert set(build(account(repoRoot=repo), fake)["laneBasis"]) == BASIS_KEYS
    out = rr.write(put(tmp_path, account()), repo, fake.readers())
    assert out["ok"]
    stored = rr.read(7, readers=fake.readers())
    assert set(stored["laneBasis"]) == BASIS_KEYS and stored["laneBasis"]["source"] == "unavailable"


def test_render_shows_the_risk_floor_after_the_lane_line(tmp_path):
    # axis: the Risk floor line; a floor, or its absence, missing from the posted summary
    repo = risk_repo(tmp_path)
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    lines = rr.render(build(account(repoRoot=repo), fake)).split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("Lane: "))
    assert lines[at + 1].startswith(f"Risk floor: full — {PAY_FLOOR}; ") and lines[at + 1].endswith(".")
    fake.changed = ["README.md"]
    assert "Risk floor: none — " + rr.lane_call.WHY_NO_FLOOR + " " in rr.render(build(account(repoRoot=repo), fake))
    fake.changed = None
    assert f"Risk floor: full — {UNREAD}" in rr.render(build(account(repoRoot=repo), fake))


def test_e9_a_lane_below_the_floor_is_not_reviewed_with_that_line(tmp_path):
    # axis: the below-floor line; a light lane over a risk-area change leaving the record reviewed
    repo = risk_repo(tmp_path)
    fake = Fake(meta=LIGHT_PR)
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(repoRoot=repo), fake)
    assert rec["lane"]["value"] == "light" and rec["laneBasis"]["floor"] == "full"
    line = f"the lane (light) is below the risk floor (full); the Risk floor line gives why"
    assert rec["status"] == "not-reviewed" and line in rec["whatIsMissing"]
    assert line in rr.render(rec)


def test_a_full_lane_over_a_risk_area_change_is_unaffected(tmp_path):
    # axis: the below-floor line; a lane at the floor refused as below it
    repo = risk_repo(tmp_path)
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(repoRoot=repo), fake)
    assert rec["lane"]["value"] == "full" and rec["laneBasis"]["floor"] == "full"
    assert rec["status"] == "reviewed" and rec["whatIsMissing"] == []


def test_a_light_lane_over_a_change_outside_every_area_stays_reviewed(tmp_path):
    # axis: the no-floor path; a change with no floor refused for its lane
    repo = risk_repo(tmp_path)
    rec = build(account(repoRoot=repo), Fake(meta=LIGHT_PR))
    assert rec["laneBasis"]["floor"] is None and rec["lane"]["value"] == "light"
    assert rec["status"] == "reviewed" and rec["whatIsMissing"] == []


@pytest.mark.parametrize("value", ["medium", None])
def test_a_lane_value_the_rule_does_not_know_counts_as_below_a_full_floor(tmp_path, value):
    # axis: the unknown-lane rank; a lane the rule does not know passing a full floor
    repo = risk_repo(tmp_path)
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(lane=value, repoRoot=repo), fake)
    assert rec["status"] == "not-reviewed"
    assert f"the lane ({value}) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]


def test_e8_changed_files_that_cannot_be_read_give_the_full_floor_marked_unavailable(tmp_path):
    # axis: the unavailable basis; unreadable changed files leaving no floor for a light lane
    repo = risk_repo(tmp_path)
    fake = Fake(meta=LIGHT_PR)
    fake.changed = None
    rec = build(account(repoRoot=repo), fake)
    basis = rec["laneBasis"]
    assert set(basis) == BASIS_KEYS and basis["source"] == "unavailable"
    assert basis["floor"] == "full" and basis["why"][0] == UNREAD
    assert [w.split(": ")[0] for w in basis["why"]].count(rr.lane_call.WHY_NO_PATHS.rstrip(":")) == 1
    assert rec["status"] == "not-reviewed"
    assert f"the lane (light) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]


def _refuse_any_read(monkeypatch):
    """Make the store reader and the changed-files reader raise, and return readers wired to the latter."""
    def boom(*args, **kwargs):
        raise AssertionError("the basis read a store or the PR's changed files")
    monkeypatch.setattr(rr.lane_call.risk_areas, "touched", boom)
    return {**Fake().readers(), "changed_paths": boom}


@pytest.mark.parametrize("over", [{}, {"repoRoot": None}, {"repoRoot": ""}])
def test_f1_f2_an_account_naming_no_repository_reads_no_store_and_no_changed_files(monkeypatch, over):
    # axis: the no-repoRoot leg of the basis; an account naming no repository falling back to the ambient project
    readers = _refuse_any_read(monkeypatch)
    rec = rr.build_record(account(**over), readers)
    basis = rec["laneBasis"]
    assert set(basis) == BASIS_KEYS and basis["source"] == "unavailable"
    assert basis["floor"] == "full" and basis["lane"] == "full"
    assert basis["why"][0].startswith(rr.lane_call.WHY_NOT_SET + " the account names no repository")
    assert basis["riskAreas"]["state"] == "not-set" and basis["touched"] == [] and basis["unmatchable"] == []
    assert basis["proposed"] == "full" and basis["proposalTaken"] is True
    assert rec["lane"]["value"] == "full" and rec["status"] == "reviewed"


def test_f4_an_unknown_lane_value_is_invalid_and_leaves_the_record_not_reviewed(monkeypatch):
    # axis: the invalid proposal; an unknown lane value read as a proposal that lowers the lane
    rec = rr.build_record(account(lane="medium"), _refuse_any_read(monkeypatch))
    basis = rec["laneBasis"]
    assert basis["source"] == "unavailable" and basis["floor"] == "full" and basis["lane"] == "full"
    assert basis["proposed"] == "medium" and basis["proposalTaken"] is False
    assert [w.split(": ")[0] for w in basis["why"]] == [rr.lane_call.WHY_NOT_SET.rstrip(":"), rr.lane_call.WHY_PROPOSAL_INVALID.rstrip(":")]
    why0 = basis["why"][0]
    assert rec["status"] == "not-reviewed"
    assert f"the lane (medium) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]


def test_f4_an_unknown_lane_value_over_a_read_basis_is_invalid_and_not_reviewed(tmp_path):
    # axis: the invalid proposal on the read path; an unknown lane value read as a proposal that lowers the lane
    repo = risk_repo(tmp_path)
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(lane="medium", repoRoot=repo), fake)
    assert rec["laneBasis"]["floor"] == "full" and rec["laneBasis"]["source"] == FILES_SOURCE
    assert rr.lane_call.WHY_PROPOSAL_INVALID.rstrip(":") in [w.split(": ")[0] for w in rec["laneBasis"]["why"]]
    assert rec["status"] == "not-reviewed"
    assert f"the lane (medium) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]


def test_the_basis_says_how_the_records_own_lane_compares_with_the_floor(tmp_path):
    # axis: the lane threaded in as the proposal; the basis reading no proposal whatever lane the record holds
    repo = risk_repo(tmp_path)
    fake = Fake(meta=LIGHT_PR)
    fake.changed = ["src/payments/charge.py"]
    below = build(account(repoRoot=repo), fake)["laneBasis"]
    assert below["proposed"] == "light" and below["proposalTaken"] is False and below["lane"] == "full"
    assert rr.lane_call.WHY_PROPOSAL_BELOW.rstrip(":") in [w.split(": ")[0] for w in below["why"]]
    fake = Fake()
    fake.changed = ["src/payments/charge.py"]
    taken = build(account(repoRoot=repo), fake)["laneBasis"]
    assert taken["proposed"] == "full" and taken["proposalTaken"] is True
    assert rr.lane_call.WHY_PROPOSAL_TAKEN.rstrip(":") in [w.split(": ")[0] for w in taken["why"]]
    assert rr.lane_call.WHY_NO_PROPOSAL.rstrip(":") not in [w.split(": ")[0] for w in taken["why"]]
    fake.changed = None
    gone = build(account(repoRoot=repo), fake)["laneBasis"]
    assert gone["source"] == "unavailable" and gone["proposed"] == "full" and gone["proposalTaken"] is True


def test_e10_an_entry_with_no_string_filename_makes_the_files_unavailable(monkeypatch):
    # axis: the complete-or-absent list; a file entry with no filename read as a complete list
    for bad in ({"status": "added"}, {"filename": 7}, {"filename": None}, "src/a.py", 5):
        canned_gh(monkeypatch, gh_files({"filename": "src/payments/a.py"}, bad))
        assert rr.changed_paths(7, "o/r") is None
    canned_gh(monkeypatch, gh_files({"filename": "a.py", "previous_filename": 7}))
    assert rr.changed_paths(7, "o/r") is None
    for out in (None, "not json", "[{"):
        canned_gh(monkeypatch, out)
        assert rr.changed_paths(7, "o/r") is None
    calls = canned_gh(monkeypatch, gh_files({"filename": "a.py"}))
    assert rr.changed_paths(7, "o/r") == ["a.py"]
    assert calls == [["gh", "api", "repos/o/r/pulls/7/files?per_page=100&page=1"]]


def test_e10_3000_entries_is_the_ceiling_and_makes_the_files_unavailable(tmp_path, monkeypatch):
    # axis: the 3000-file ceiling; a list GitHub may have cut short read as the whole change
    repo = risk_repo(tmp_path)

    def entry(i):
        return {"filename": f"docs/f{i}.md", "status": "added"}
    canned_gh(monkeypatch, gh_files(*[entry(i) for i in range(2999)]))
    assert len(rr.changed_paths(7, "o/r")) == 2999
    out = gh_files(*[entry(i) for i in range(3000)])
    canned_gh(monkeypatch, out)
    assert rr.changed_paths(7, "o/r") is None
    rec = real_reader_record(repo, monkeypatch, out)
    assert rec["laneBasis"]["source"] == "unavailable" and rec["laneBasis"]["floor"] == "full"
    assert rec["status"] == "not-reviewed"


def test_e11_a_removed_file_inside_a_risk_area_touches_it(tmp_path, monkeypatch):
    # axis: removed files kept in the list; a deletion inside a risk area dropped so the area looks untouched
    repo = risk_repo(tmp_path)
    out = gh_files({"filename": "docs/readme.md", "status": "modified"},
                   {"filename": "src/payments/old.py", "status": "removed"})
    canned_gh(monkeypatch, out)
    assert rr.changed_paths(7, "o/r") == ["docs/readme.md", "src/payments/old.py"]
    rec = real_reader_record(repo, monkeypatch, out)
    assert rec["laneBasis"]["source"] == FILES_SOURCE and rec["laneBasis"]["floor"] == "full"
    assert rec["laneBasis"]["touched"] == [{"name": "Payments", "matched": ["src/payments/old.py"]}]
    assert rec["status"] == "not-reviewed"


def test_e11_a_rename_out_of_a_risk_area_touches_it_through_the_previous_name(tmp_path, monkeypatch):
    # axis: previous_filename kept in the list; a rename out of a risk area looking like a change outside it
    repo = risk_repo(tmp_path)
    out = gh_files({"filename": "docs/moved.py", "previous_filename": "src/payments/charge.py", "status": "renamed"})
    canned_gh(monkeypatch, out)
    assert rr.changed_paths(7, "o/r") == ["docs/moved.py", "src/payments/charge.py"]
    rec = real_reader_record(repo, monkeypatch, out)
    assert rec["laneBasis"]["floor"] == "full"
    assert rec["laneBasis"]["touched"] == [{"name": "Payments", "matched": ["src/payments/charge.py"]}]
    assert rec["status"] == "not-reviewed"
    assert f"the lane (light) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]


def test_a_broad_change_renders_under_the_cap_with_the_floor_full(tmp_path):
    # axis: the record's laneBasis evidence is bounded; a change touching thousands of paths still publishes
    repo = risk_repo(tmp_path)
    fake = Fake()
    matched = ["src/payments/%s%04d.py" % ("x" * 50, i) for i in range(3100)]
    unmatched = ["/abs/%s%04d.py" % ("y" * 55, i) for i in range(3100)]
    fake.changed = matched + unmatched
    rec = build(account(repoRoot=repo), fake)
    basis = rec["laneBasis"]
    assert basis["floor"] == "full" and basis["source"] == FILES_SOURCE
    assert basis["touched"] == [{"name": "Payments", "matched": matched[:10], "matchedCount": 3100}]
    assert basis["unmatchable"] == unmatched[:10] and basis["unmatchableCount"] == 3100
    assert len(rr.render(rec)) < rr.MAX_BODY_CHARS


def test_many_risk_areas_with_long_paths_render_under_the_cap_with_the_floor_full(tmp_path):
    # axis: the total lane-basis evidence (kept paths and reason lines across all areas) is bounded; many areas still publish
    areas = [dict(PAYMENTS, name="Area%02d%s" % (n, "n" * 60), covers=["src/area%02d/*" % n]) for n in range(60)]
    repo = risk_repo(tmp_path, areas=areas)
    fake = Fake()
    fake.changed = ["src/area%02d/%s%02d.py" % (n, "z" * 200, i) for n in range(60) for i in range(10)]
    rec = build(account(repoRoot=repo), fake)
    basis = rec["laneBasis"]
    assert basis["floor"] == "full" and basis["source"] == FILES_SOURCE
    assert len(basis["touched"]) == rr.BASIS_AREAS_MAX and basis["touchedCount"] == 60
    assert sum(len(t["matched"]) for t in basis["touched"]) == rr.BASIS_PATHS_MAX
    assert all(t["matchedCount"] == 10 for t in basis["touched"] if len(t["matched"]) < 10)
    assert len(basis["why"]) <= rr.BASIS_WHY_MAX and basis["whyCount"] > rr.BASIS_WHY_MAX
    assert any("more %s lines omitted" % rr.lane_call.WHY_TOUCHES.rstrip(":") in w for w in basis["why"])
    assert basis["why"][0].startswith(rr.lane_call.WHY_TOUCHES)
    assert len(rr.render(rec)) < rr.MAX_BODY_CHARS


def _astral_record(tmp_path, per_area, area_chars=60, path_chars=290):
    glyph = "\U0001F600"
    areas = [dict(PAYMENTS, name="Area%02d%s" % (n, glyph * area_chars), covers=["src/area%02d/*" % n])
             for n in range(20)]
    repo = risk_repo(tmp_path, areas=areas)
    fake = Fake()
    fake.changed = ["src/area%02d/%s%04d.py" % (n, glyph * path_chars, i) for n in range(20) for i in range(per_area)]
    return build(account(repoRoot=repo), fake)


def test_four_byte_paths_across_many_areas_render_under_the_cap_with_the_floor_full(tmp_path):
    # axis: the size bound is on the posted (JSON-escaped) body, so non-ASCII paths shed evidence rather than refuse
    rec = _astral_record(tmp_path, per_area=150)
    assert sum(t.get("matchedCount", len(t["matched"])) for t in rec["laneBasis"]["touched"]) == 3000
    body = rr.render(rec)
    assert len(body) <= rr.MAX_BODY_CHARS
    shed = json.loads(body.split("```json\n", 1)[1].rsplit("\n```", 1)[0])["laneBasis"]
    assert shed["basisShed"] in ("why-paths", "matched", "unmatchable")
    assert shed["floor"] == "full" and shed["lane"] == rec["laneBasis"]["lane"]
    assert shed["proposalTaken"] == rec["laneBasis"]["proposalTaken"]
    assert [t["name"] for t in shed["touched"]] == [t["name"] for t in rec["laneBasis"]["touched"]]
    assert "basisShed" not in rec["laneBasis"]


def test_a_shed_that_reaches_the_last_resort_still_fits(tmp_path, monkeypatch):
    # axis: the shed terminates by construction: the last resort holds the floor, lane, first reason and counts
    rec = _astral_record(tmp_path, per_area=2, area_chars=290)
    body = rr.render(rec)
    assert len(body) <= rr.MAX_BODY_CHARS
    shed = json.loads(body.split("```json\n", 1)[1].rsplit("\n```", 1)[0])["laneBasis"]
    assert shed["basisShed"] == "floor-only" and shed["floor"] == "full"
    assert set(shed) == {"floor", "lane", "proposalTaken", "source", "why", "whyCount", "touchedCount",
                         "matchedCount", "unmatchableCount", "basisShed"}
    assert shed["touchedCount"] == 20 and shed["matchedCount"] == 40 and len(shed["why"]) == 1


def test_a_floor_only_basis_counts_the_matched_paths_of_the_areas_the_area_cap_cut(tmp_path):
    # axis: the floor-only basis's matchedCount counts every matched path in every touched area, cut areas included
    glyph = "\U0001F600"
    areas = [dict(PAYMENTS, name="Area%02d%s" % (n, glyph * 290), covers=["src/area%02d/*" % n])
             for n in range(60)]
    repo = risk_repo(tmp_path, areas=areas)
    fake = Fake()
    fake.changed = ["src/area%02d/f%d.py" % (n, i) for n in range(60) for i in range(2)]
    body = rr.render(build(account(repoRoot=repo), fake))
    assert len(body) <= rr.MAX_BODY_CHARS
    shed = json.loads(body.split("```json\n", 1)[1].rsplit("\n```", 1)[0])["laneBasis"]
    assert shed["basisShed"] == "floor-only" and shed["touchedCount"] == 60 and shed["matchedCount"] == 120


def _head_moving_readers(heads):
    """Readers whose pr_meta returns the given heads in turn (the last one repeats)."""
    fake, seen = Fake(), []

    def meta(pr, repo):
        seen.append(1)
        return {"head": heads[min(len(seen), len(heads)) - 1], "body": "", "issues": []}
    return {**fake.readers(), "pr_meta": meta}


def test_a_head_that_moves_between_the_meta_read_and_the_files_read_gives_the_unavailable_basis(tmp_path):
    # axis: the changed-file evidence bound to the recorded commit; files of a newer head judged against the earlier one
    repo = risk_repo(tmp_path)
    rec = rr.build_record(account(repoRoot=repo), _head_moving_readers([HEAD, "f" * 40]))
    basis = rec["laneBasis"]
    assert basis["source"] == "unavailable" and basis["floor"] == "full"
    assert basis["why"][0] == rr.lane_call.WHY_NO_PATHS + " the PR head moved while its changed files were read"
    assert rec["finalCommit"]["sha"] == HEAD
    assert basis["headMoved"] is True
    assert rec["status"] == "not-reviewed"
    assert "the PR head moved while the record was written; this record does not cover the new head" in rec["whatIsMissing"]


def test_a_head_that_cannot_be_re_read_gives_the_could_not_be_re_read_reason_and_no_moved_head(tmp_path):
    # axis: the unreadable-head reason kept apart from the moved-head one; a head never read called a moved head
    repo = risk_repo(tmp_path)
    fake = Fake()
    count = []

    def meta(pr, repo_name):
        count.append(1)
        return fake.readers()["pr_meta"](pr, repo_name) if len(count) == 1 else None
    rec = rr.build_record(account(repoRoot=repo), {**fake.readers(), "pr_meta": meta})
    basis = rec["laneBasis"]
    assert len(count) >= 2
    assert basis["source"] == "unavailable" and basis["floor"] == "full"
    assert basis["why"][0] == rr.lane_call.WHY_NO_PATHS + " the PR head could not be re-read while its changed files were read"
    assert "headMoved" not in basis
    assert "the PR head moved while the record was written; this record does not cover the new head" not in rec["whatIsMissing"]


def _unavailable_files_readers(heads):
    readers = _head_moving_readers(heads)
    return {**readers, "changed_paths": lambda pr, repo: None}


def test_files_unavailable_and_head_moved_reads_not_reviewed_with_the_moved_head_line(tmp_path):
    # axis: the head re-read on the unavailable-files path; a head that moved during a failed file read left unflagged
    repo = risk_repo(tmp_path)
    rec = rr.build_record(account(repoRoot=repo), _unavailable_files_readers([HEAD, "f" * 40]))
    basis = rec["laneBasis"]
    assert basis["source"] == "unavailable" and basis["headMoved"] is True
    assert rec["status"] == "not-reviewed"
    assert "the PR head moved while the record was written; this record does not cover the new head" in rec["whatIsMissing"]


def test_files_unavailable_and_head_stable_has_no_moved_head_line(tmp_path):
    # axis: the moved-head line absent when the head is stable on the unavailable-files path
    repo = risk_repo(tmp_path)
    rec = rr.build_record(account(repoRoot=repo), _unavailable_files_readers([HEAD]))
    basis = rec["laneBasis"]
    assert basis["source"] == "unavailable" and "headMoved" not in basis
    assert "the PR head moved while the record was written; this record does not cover the new head" not in rec["whatIsMissing"]


def test_a_stable_head_gives_the_normal_basis(tmp_path):
    repo = risk_repo(tmp_path)
    rec = rr.build_record(account(repoRoot=repo), _head_moving_readers([HEAD]))
    assert rec["laneBasis"]["source"] == FILES_SOURCE


DOCS_AREA = {"name": "Docs", "covers": ["docs/*"], "why": "Owner-facing docs.", "undo": "Easy: revert the page."}


def test_a_changed_file_named_bug_free_still_publishes(tmp_path, monkeypatch):
    # axis: the claim guard at the render boundary; a path in the lane basis's reason lines blocking the record
    repo = risk_repo(tmp_path, areas=(DOCS_AREA,))
    rec = real_reader_record(repo, monkeypatch, gh_files({"filename": "docs/bug-free.md"}))
    assert "docs/bug-free.md" in "; ".join(rec["laneBasis"]["why"])
    body = rr.render(rec)
    assert "docs/bug-free.md" in body


def test_composed_prose_claiming_no_bugs_is_still_refused_with_a_path_in_the_basis(tmp_path, monkeypatch):
    # axis: the claim guard still reading writer-composed summary text; the path exemption widening to prose
    repo = risk_repo(tmp_path, areas=(DOCS_AREA,))
    rec = real_reader_record(repo, monkeypatch, gh_files({"filename": "docs/bug-free.md"}))
    rec["whatIsMissing"] = ["the change has no bugs"]
    with pytest.raises(rr.Refusal) as e:
        rr.render(rec)
    assert e.value.reason == "review-record-forbidden-claim"


def test_a_below_floor_oversized_record_with_a_bug_free_path_publishes_not_reviewed(tmp_path):
    # axis: the below-floor warning carrying no basis free text; an oversized record's shed leaving a path in a claim-checked line
    glyph = "\U0001F600"
    areas = [dict(PAYMENTS, name="Area%d%s" % (n, glyph * 60), covers=["docs/area%d/*" % n]) for n in range(20)]
    repo = risk_repo(tmp_path, areas=areas)
    fake = Fake(meta=LIGHT_PR)
    fake.changed = ["docs/area0/bug-free.md"] + [
        "docs/area%d/%s%04d.md" % (n, glyph * 290, i) for n in range(20) for i in range(150)]
    rec = build(account(repoRoot=repo), fake)
    assert rec["lane"]["value"] == "light" and rec["laneBasis"]["floor"] == "full"
    assert rec["status"] == "not-reviewed"
    assert "docs/area0/bug-free.md" in "; ".join(rec["laneBasis"]["why"])
    assert "the lane (light) is below the risk floor (full); the Risk floor line gives why" in rec["whatIsMissing"]
    assert not any("bug-free" in line for line in rec["whatIsMissing"])
    body = rr.render(rec)
    assert len(body) <= rr.MAX_BODY_CHARS


def test_composed_prose_claiming_no_bugs_is_refused_on_a_below_floor_record(tmp_path):
    # axis: the claim guard excluding only the Risk floor line; every other summary line still checked
    repo = risk_repo(tmp_path)
    fake = Fake(meta=LIGHT_PR)
    fake.changed = ["src/payments/charge.py"]
    rec = build(account(repoRoot=repo), fake)
    rec["whatIsMissing"] = rec["whatIsMissing"] + ["the change is bug-free"]
    with pytest.raises(rr.Refusal) as e:
        rr.render(rec)
    assert e.value.reason == "review-record-forbidden-claim"


SHED_LINE = ("Reviewer detail trimmed to fit this comment (%s); the reviewers' findings are in the raw-output "
             "comments linked under rawOutputs, and the trimmed engine detail is in the engines' own run records.")
SHED_LINE_RUN_RECORDS = ("Reviewer detail trimmed to fit this comment (%s); the engines' own run records hold the "
                         "full output.")
PROTECTED_ROW_KEYS = ("name", "ran", "planned", "vendor", "model", "family", "commit", "coversFinalCommit")
RULING = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": CANON_ID}


def _long_session(reviewers=45, body_chars=1400):
    """A long session's record: many engine-run reviewer rows, each with a long runDir and a full observation, a
    planned reviewer that did not run but has a go-ahead, and findings with long bodies."""
    runs, rows = {}, []
    for i in range(reviewers):
        run_dir = f"/run/r{i:02d}/".ljust(140, "d")
        observation = {"tokens": 1000 + i, "toolCalls": 40 + i, "stdoutBytes": 90000 + i, "wallSeconds": 120 + i,
                       "source": "codex", "read": f"read the diff and {'the files it touches, ' * 8}round {i}",
                       "telemetry": {"model": CODEX, "turns": i, "cached": 3 * i, "notes": "n" * 120, "tail": "t" * 60}}
        runs[run_dir] = (dict(GOOD_RUN, observation=observation), None)
        rows.append(reviewer(f"reviewer-{i:02d}", runDir=run_dir))
    rows.append(reviewer("security-reviewer", ran=False, runDir=None))
    found = [finding(f"code-{i:03d}", title=f"title {i}", body="b" * body_chars, reason=f"fixed in 1a2b3c{i:x}",
                     reviewer="reviewer-00") for i in range(15)]
    return build(account(reviewers=rows, findings=found, goAheads=[RULING]), Fake(runs=runs, sources=CANON_SOURCES))


def _protected(rec):
    return {"status": rec["status"], "whatIsMissing": rec["whatIsMissing"],
            "findings": [{k: f[k] for k in ("outcome", "reason")} for f in rec["findings"]],
            "missingReviews": rec["missingReviews"],
            "reviewers": [{k: v[k] for k in PROTECTED_ROW_KEYS} for v in rec["reviewers"]]}


def _unshed_size(rec, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(rr, "MAX_BODY_CHARS", 10 ** 9)
        return len(rr.render(rec))


def test_a_long_session_sheds_reviewer_detail_to_fit_and_says_so(monkeypatch):
    # axis: the reviewer shed steps and the shed line; a long session refused for size, or trimmed without saying so
    rec = _long_session()
    assert _unshed_size(rec, monkeypatch) > rr.MAX_BODY_CHARS
    body = rr.render(rec)
    assert len(body) <= rr.MAX_BODY_CHARS
    lines = body.split("\n")
    shed = SHED_LINE_RUN_RECORDS % "engine telemetry"
    assert lines.count(shed) == 1 and sum(l.startswith("Reviewer detail trimmed") for l in lines) == 1
    # the Test lens line sits right after the reviewer bullets, so the shed line follows it
    assert lines[lines.index(shed) - 1].startswith("Test lens:")
    assert lines[lines.index(shed) - 2].startswith("- security-reviewer: did not run")
    posted = rr._parse_body(body)
    assert posted["reviewerShed"] == ["observation"]
    assert _protected(posted) == _protected(rec)
    assert all(set(v["observation"]) == {"read", "toolCalls"} for v in posted["reviewers"][:-1])
    assert "reviewerShed" not in rec and all(v["runDir"] for v in rec["reviewers"][:-1])


def test_a_never_shed_census_of_the_decision_content_over_a_shed_record():
    # axis: the never-shed set; a shed step emptying the status, a missing line, an outcome or reason, a go-ahead or a row's identity
    rec = _long_session()
    posted = rr._parse_body(rr.render(rec))
    assert "reviewerShed" in posted
    assert rec["whatIsMissing"] and rec["missingReviews"] == [{"name": "security-reviewer", "goAhead": RULING}]
    assert posted["status"] == rec["status"] == "not-reviewed"
    assert posted["whatIsMissing"] == rec["whatIsMissing"]
    assert [(f["outcome"], f["reason"]) for f in posted["findings"]] == [
        ("fixed", f"fixed in 1a2b3c{i:x}") for i in range(15)]
    assert posted["missingReviews"] == rec["missingReviews"]
    assert [{k: v[k] for k in PROTECTED_ROW_KEYS} for v in posted["reviewers"]] == [
        {k: v[k] for k in PROTECTED_ROW_KEYS} for v in rec["reviewers"]]
    assert len(posted["reviewers"]) == 46 and posted["reviewers"][0]["ran"] == "engine-record"


def test_the_shed_line_names_exactly_what_was_shed(monkeypatch):
    # axis: the shed line's wording; the line naming run directories when only telemetry went, or the reverse
    rec = _long_session()
    # pinned: the lane-basis steps are off so the caps below are exact; in production they shave a few characters
    # first, so the reviewer steps start a little later than this test shows
    with monkeypatch.context() as m:
        m.setattr(rr, "_SHED_STEPS", ())
        after_observation = _unshed_size(dict(rr._shed_observation(rec), reviewerShed=["observation"]), m)
    with monkeypatch.context() as m:
        m.setattr(rr, "_SHED_STEPS", ())
        m.setattr(rr, "MAX_BODY_CHARS", after_observation)
        only = rr.render(rec)
        m.setattr(rr, "MAX_BODY_CHARS", after_observation - 1)
        both = rr.render(rec)
    assert rr._parse_body(only)["reviewerShed"] == ["observation"]
    assert SHED_LINE_RUN_RECORDS % "engine telemetry" in only.split("\n")
    assert rr._parse_body(both)["reviewerShed"] == ["observation", "runDir"]
    assert SHED_LINE_RUN_RECORDS % "engine telemetry and run directories" in both.split("\n")
    assert SHED_LINE_RUN_RECORDS % "engine telemetry" not in both.split("\n")
    kept = rr._parse_body(only)["reviewers"][0]
    assert set(kept["observation"]) == {"read", "toolCalls"} and kept["runDir"] == rec["reviewers"][0]["runDir"]


def test_rows_with_no_observation_that_fit_after_run_dirs_say_run_directories_only(monkeypatch):
    # axis: a step that changed nothing being named; the line claiming engine telemetry went when no row had any
    rec = _long_session()
    for v in rec["reviewers"]:
        v.pop("observation", None)
    with monkeypatch.context() as m:
        m.setattr(rr, "_SHED_STEPS", ())
        after_run_dir = _unshed_size(dict(rr._shed_run_dir(rec), reviewerShed=["runDir"]), m)
        assert _unshed_size(rec, m) > after_run_dir
        m.setattr(rr, "MAX_BODY_CHARS", after_run_dir)
        body = rr.render(rec)
    lines = body.split("\n")
    posted = rr._parse_body(body)
    assert posted["reviewerShed"] == ["runDir"]
    assert SHED_LINE_RUN_RECORDS % "run directories" in lines
    assert sum(l.startswith("Reviewer detail trimmed") for l in lines) == 1
    assert "engine telemetry" not in "\n".join(lines)
    assert all(v["runDir"] is None for v in posted["reviewers"])


def _shed_line_of(rec):
    body = rr.render(rec)
    assert "reviewerShed" in rr._parse_body(body)
    (line,) = [l for l in body.split("\n") if l.startswith("Reviewer detail trimmed")]
    return line


def test_a_record_with_empty_raw_outputs_points_at_the_engines_run_records():
    # axis: the shed line's pointer; naming a raw-output comment the record does not link
    rec = _long_session()
    assert rec["rawOutputs"] == []
    assert _shed_line_of(rec) == SHED_LINE_RUN_RECORDS % "engine telemetry"


def test_a_record_with_only_withheld_raw_outputs_points_at_the_engines_run_records():
    # axis: the shed line's pointer; a withheld raw output counted as a linked one
    rec = _long_session()
    rec["rawOutputs"] = [{"file": "a.txt", "id": 1, "url": "u", "withheld": True},
                         {"file": "b.txt", "id": 2, "url": "u", "withheld": True}]
    assert _shed_line_of(rec) == SHED_LINE_RUN_RECORDS % "engine telemetry"


def test_a_record_with_one_linked_raw_output_points_at_the_raw_output_comment():
    # axis: the shed line's pointer; a linked raw output not pointed at
    rec = _long_session()
    rec["rawOutputs"] = [{"file": "a.txt", "id": 1, "url": "u", "withheld": True},
                         {"file": "b.txt", "id": 2, "url": "u", "withheld": False}]
    assert _shed_line_of(rec) == SHED_LINE % "engine telemetry"


def test_a_raw_outputs_value_that_is_not_a_list_of_dicts_counts_as_no_linked_output():
    # axis: the pointer on malformed rawOutputs; a crash, or a pointer at output that is not linked
    for bad in ("linked", None, {"file": "a.txt", "withheld": False}, ["a.txt", 3]):
        rec = _long_session()
        rec["rawOutputs"] = bad
        assert _shed_line_of(rec) == SHED_LINE_RUN_RECORDS % "engine telemetry", bad


def test_a_reviewer_row_without_a_dict_observation_is_left_as_it_is():
    # axis: the observation step on a row with no dict observation; a crash, or an observation made up for the row
    rec = _long_session()
    rec["reviewers"][1].pop("observation")
    rec["reviewers"][2]["observation"] = None
    rec["reviewers"][3]["observation"] = "read it all"
    rec["reviewers"][4]["observation"] = ["tokens", 5]
    posted = rr._parse_body(rr.render(rec))
    assert "reviewerShed" in posted
    assert "observation" not in posted["reviewers"][1]
    assert [posted["reviewers"][i]["observation"] for i in (2, 3, 4)] == [None, "read it all", ["tokens", 5]]
    assert set(posted["reviewers"][0]["observation"]) == {"read", "toolCalls"}


def test_a_record_that_cannot_fit_after_every_step_goes_to_parts_not_cut():
    # axis: the spill after the last shed step; a body still over the cap posted, cut to fit, or refused
    for field in ("whatIsMissing", "reason"):
        rec = _long_session()
        if field == "whatIsMissing":
            rec["whatIsMissing"] = rec["whatIsMissing"] + ["w" * rr.MAX_BODY_CHARS]
        else:
            rec["findings"][0]["reason"] = "r" * rr.MAX_BODY_CHARS
        plan = rr.render_plan(rec)
        assert plan.parts
        assert all(len(b) <= rr.MAX_BODY_CHARS for b in [*plan.parts, plan.head([1] * len(plan.parts))])
        text = "".join(rr._part_slice(b) for b in plan.parts)
        assert ("w" if field == "whatIsMissing" else "r") * rr.MAX_BODY_CHARS in text


def test_a_record_under_the_cap_renders_with_no_shed_line_and_no_reviewer_shed(monkeypatch):
    # axis: the reviewer steps run only while over the cap; a record that fits trimmed or marked as shed
    rec = _long_session(reviewers=3, body_chars=20)
    body = rr.render(rec)
    assert _unshed_size(rec, monkeypatch) == len(body) < rr.MAX_BODY_CHARS
    assert "Reviewer detail trimmed" not in body and "reviewerShed" not in rr._parse_body(body)
    posted = rr._parse_body(body)
    assert all(v["runDir"] and set(v["observation"]) >= {"tokens", "telemetry"} for v in posted["reviewers"][:-1])


def test_a_record_that_needed_only_the_lane_basis_steps_carries_no_shed_line(tmp_path):
    # axis: the reviewer steps start only after the lane-basis steps; a lane-basis shed also trimming reviewers
    body = rr.render(_astral_record(tmp_path, per_area=150))
    posted = rr._parse_body(body)
    assert posted["laneBasis"]["basisShed"] in ("why-paths", "matched", "unmatchable")
    assert "Reviewer detail trimmed" not in body and "reviewerShed" not in posted
    assert posted["reviewers"][0]["runDir"]


def test_lane_call_pattern_alternatives_equal_the_lane_vocabulary():
    # axis: one lane vocabulary; the parser's alternatives must equal lane_call.LANES, whatever either home holds
    import lane_call

    probe = rr._LANE_RE.pattern.split(r"\s*(", 1)[1].split(")", 1)[0]
    assert sorted(probe.split("|")) == sorted(lane_call.LANES)
    for lane in lane_call.LANES:
        assert rr._LANE_RE.search("**Lane call:** " + lane + ". why").group(1) == lane


# --- the reading rule, run identity and maker independence ---

LIGHT = {"lane": "light"}


def _run_with(observation):
    return dict(GOOD_RUN, observation=observation)


def test_an_engaged_light_lane_reviewer_counts_and_carries_its_reading():
    # axis: a light-lane reviewer whose engine record reads engaged being credited, and carrying reading "engaged"
    v = build(account(**LIGHT))["reviewers"][0]
    assert v["ran"] == "engine-record" and v["reading"] == "engaged" and "runNote" not in v


@pytest.mark.parametrize("lane", [None, "micro", "something-new"])
def test_a_lane_that_is_not_full_applies_the_reading_rule(lane):
    # axis: lane None, micro or unrecognised being treated as full, so a no-reading run is credited
    fake = Fake(runs={"/run/code-reviewer": (_run_with({"read": "unknown"}), None)})
    v = build(account(lane=lane), fake)["reviewers"][0]
    assert v["ran"] == "not-run" and v["reading"] == "not-shown"


@pytest.mark.parametrize("observation", [
    {"tokens": 1, "read": "unknown"}, {"tokens": 1}, None, "engaged", ["engaged"]])
def test_a_light_lane_reading_that_is_not_engaged_is_not_run(observation):
    # axis: the engine-record branch of the reading rule; an unknown, absent or malformed reading being credited
    fake = Fake(runs={"/run/code-reviewer": (_run_with(observation), None)})
    rec = build(account(**LIGHT), fake)
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and v["reading"] == "not-shown" and "observation" not in v
    assert v["runNote"] == "the engine's record of the run does not show that the reviewer read the change"
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]
    assert rec["missingReviews"][0]["name"] == "code-reviewer" and rec["status"] == "not-reviewed"
    assert "code-reviewer did not run" in rec["whatIsMissing"]


def test_a_session_only_light_lane_reviewer_is_not_run():
    # axis: the session-reported branch of the reading rule; a reviewer with no run directory credited on a light lane
    rec = build(account(**LIGHT, reviewers=[reviewer(runDir="")]))
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and v["reading"] == "not-shown"
    assert v["runNote"] == "no engine record of the run shows that the reviewer read the change"
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]


def test_a_full_lane_reading_that_is_unknown_still_counts_and_carries_no_reading():
    # axis: the full lane staying unchanged; the reading rule leaking into it
    fake = Fake(runs={"/run/code-reviewer": (_run_with({"read": "unknown"}), None)})
    full = build(account(), fake)["reviewers"][0]
    assert full["ran"] == "engine-record" and "reading" not in full
    session_only = build(account(reviewers=[reviewer(runDir="")]))["reviewers"][0]
    assert session_only["ran"] == "reported-by-session" and "reading" not in session_only


def test_a_reviewer_that_never_ran_on_a_light_lane_is_not_shown_as_reading():
    # axis: reading "engaged" on a row that did not run
    v = build(account(**LIGHT, reviewers=[reviewer(ran=False, runDir="")]))["reviewers"][0]
    assert v["ran"] == "not-run" and v["reading"] == "not-shown"


def test_a_mislabelled_engine_run_is_not_run():
    # axis: the run-identity check; a codex run record credited to a row that names a claude reviewer
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)})
    rec = build(account(makers=[{"family": "someone-else"}], reviewers=[maker_family_reviewer()]), fake)
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and v["runNote"] == "the run record names a different reviewer than the account row"
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]


@pytest.mark.parametrize("record", [
    {k: v for k, v in GOOD_RUN.items() if k != "source"},
    {k: v for k, v in GOOD_RUN.items() if k != "engineModel"},
    dict(GOOD_RUN, engineModel=model_registry.codex_models()[1]),
])
def test_an_engine_record_that_does_not_name_the_row_reviewer_is_not_run(record):
    # axis: the run-identity check; a missing or disagreeing source or model credited
    v = build(account(), Fake(runs={"/run/code-reviewer": (record, None)}))["reviewers"][0]
    assert v["ran"] == "not-run" and v["runNote"] == "the run record names a different reviewer than the account row"


@pytest.mark.parametrize("vendor,alias,model_id", [
    ("claude", model_registry.dispatch_token("claude", "sonnet-5.5"), "sonnet-5.5"),
    ("cursor", "cursor-grok-4.6-xhigh", "cursor-grok-4.6"),
])
def test_a_supported_dispatch_spelling_of_the_model_names_the_same_reviewer(vendor, alias, model_id):
    # axis: the run-identity check; a dispatch spelling (tier alias, effort suffix) of the engine record's model demoted
    run = dict(GOOD_RUN, source=vendor, engineModel=model_id)
    fake = Fake(runs={"/run/code-reviewer": (run, None)})
    v = build(account(makers=[{"family": "someone-else"}], reviewers=[reviewer(vendor=vendor, model=alias)]), fake)["reviewers"][0]
    # bites on: the raw string comparison rejecting a completed review for naming the model by its dispatch token
    assert v["ran"] == "engine-record" and "runNote" not in v
    other = model_registry.codex_models()[1]
    run = dict(GOOD_RUN, source="codex", engineModel=other)
    fake = Fake(runs={"/run/code-reviewer": (run, None)})
    assert build(account(), fake)["reviewers"][0]["ran"] == "not-run"


def test_the_family_comes_from_the_credited_run_record(monkeypatch):
    # axis: the family read from the row rather than from the engine record that was credited
    seen = []
    real = rr._family
    monkeypatch.setattr(rr, "_family", lambda vendor, model: seen.append((vendor, model)) or real(vendor, model))
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(GOOD_RUN), None)})
    v = build(account(), fake)["reviewers"][0]
    assert v["family"] == "openai" and seen[-1] == (GOOD_RUN["source"], GOOD_RUN["engineModel"])


def test_empty_or_omitted_makers_is_not_reviewed_with_the_fixed_line():
    # axis: the no-maker line; a record with no named maker reading reviewed
    line = "no maker is named, so independence cannot be shown"
    omitted = {k: v for k, v in account().items() if k != "makers"}
    for acct in (omitted, account(makers=[]), account(makers=None)):
        rec = build(acct)
        assert rec["status"] == "not-reviewed" and line in rec["whatIsMissing"]
        assert rec["reviewers"][0]["ran"] == "engine-record"
    assert line not in build(account())["whatIsMissing"]


def test_a_reviewer_whose_family_cannot_be_read_is_not_run_while_makers_are_named():
    # axis: a row with no readable family credited when makers are named
    run = dict(GOOD_RUN, source="elsewhere", engineModel="x")
    fake = Fake(runs={"/run/code-reviewer": (run, None)})
    rec = build(account(reviewers=[reviewer(vendor="elsewhere", model="x")]), fake)
    v = rec["reviewers"][0]
    assert v["family"] is None and v["ran"] == "not-run"
    assert v["runNote"] == "the reviewer's model family could not be read, so independence cannot be shown"
    unnamed = build(account(makers=[], reviewers=[reviewer(vendor="elsewhere", model="x")]), fake)
    assert unnamed["reviewers"][0]["ran"] == "engine-record"


def test_a_same_family_reviewer_without_the_owners_word_is_not_run():
    # axis: the maker-family branch; a reviewer from a maker's family credited with no owner's word
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
    rec = build(account(reviewers=[maker_family_reviewer(notIndependent=False)]), fake)
    v = rec["reviewers"][0]
    assert v["ran"] == "not-run" and "notIndependent" not in v
    assert v["runNote"] == "the reviewer is from a maker's family and no owner's word for this change lets it run"
    assert rec["status"] == "not-reviewed" and "code-reviewer did not run" in rec["whatIsMissing"]
    assert rec["sessionDisagreements"] == [{"fact": "code-reviewer ran", "session": True, "code": "not-run"}]


def test_a_same_family_reviewer_with_a_complete_owners_word_counts_and_shows_not_independent():
    # axis: the owner's word admitting a same-family reviewer, and the render naming it not independent
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
    rec = build(account(reviewers=[maker_family_reviewer(ownerWord=OWNER_WORD)]), fake)
    v = rec["reviewers"][0]
    assert v["ran"] == "engine-record" and v["notIndependent"] is True
    body = rr.render(rec)
    assert "- code-reviewer: ran (engine record); not independent of the makers (owner's word: http://c/9)" in body


@pytest.mark.parametrize("word", [
    None, {}, {"words": "go ahead"}, {"where": "http://c/9"}, {"words": "", "where": "http://c/9"},
    {"words": "go ahead", "where": "  "}, {"words": 3, "where": "http://c/9"}])
def test_an_incomplete_owners_word_does_not_admit_a_same_family_reviewer(word):
    # axis: the owner's-word completeness check; a missing, blank or non-text words or where admitting the reviewer
    fake = Fake(runs={"/run/code-reviewer": (copy.deepcopy(CLAUDE_RUN), None)})
    rec = build(account(reviewers=[maker_family_reviewer(ownerWord=word)]), fake)
    assert rec["reviewers"][0]["ran"] == "not-run" and "notIndependent" not in rec["reviewers"][0]


# --- reading-next ---

PANEL = list(seat_map_module.PANEL_ROSTER)
SEAT_MAP = seat_map_module.to_receipt(
    seat_map_module.build(PANEL, ["codex", "cursor", "gemini"], "anthropic", 0), "anthropic")
ENGAGED_RUN = {"runKind": "review", "graded": True, "observation": {"read": "engaged"}}
NO_READING = dict(ENGAGED_RUN, observation={"read": "unknown"})


def _seats(**over):
    return dict(SEAT_MAP, **over)


def test_reading_next_with_one_run_and_no_reading_reruns():
    assert rr.reading_next([NO_READING], SEAT_MAP, ["anthropic"])["next"] == "rerun"
    assert rr.reading_next([None], SEAT_MAP, ["anthropic"])["next"] == "rerun"


def test_reading_next_accepts_when_any_run_shows_a_reading():
    assert rr.reading_next([NO_READING, ENGAGED_RUN], None, [])["next"] == "accept"
    assert rr.reading_next([ENGAGED_RUN], None, [])["next"] == "accept"


def test_reading_next_does_not_accept_an_engaged_run_the_record_writer_would_not_credit():
    forfeited = dict(ENGAGED_RUN, graded=False)
    wrote = dict(ENGAGED_RUN, runKind="write")
    # bites on: a forfeited or non-review run that merely engaged ending the retry
    assert rr.reading_next([forfeited], None, ["anthropic"])["next"] == "rerun"
    assert rr.reading_next([wrote], None, ["anthropic"])["next"] == "rerun"


def test_reading_next_counts_only_the_first_two_runs():
    assert rr.reading_next([NO_READING, NO_READING, ENGAGED_RUN], SEAT_MAP, ["anthropic"])["next"] == "move-up"


def test_reading_next_moves_up_over_a_valid_independent_map():
    out = rr.reading_next([NO_READING, None], SEAT_MAP, ["anthropic"])
    assert out["next"] == "move-up" and out["reason"]


def test_reading_next_parks_when_no_run_is_given():
    assert rr.reading_next([], SEAT_MAP, ["anthropic"])["next"] == "park"


def test_reading_next_parks_when_a_roster_seat_is_unfilled():
    # axis: the unfilled-seat park; a map with an unfilled roster seat letting the lane move up
    seats = dict(SEAT_MAP["seats"], **{PANEL[0]: {"source": "unfilled", "family": "openai"}})
    out = rr.reading_next([NO_READING, NO_READING], _seats(seats=seats), ["anthropic"])
    assert out == {"next": "park", "reason": "a roster seat in the seat map is unfilled"}


def test_reading_next_parks_when_a_roster_seat_is_a_makers_family():
    # axis: the maker-family-seat park; a map with a seat from a maker's family letting the lane move up
    seats = dict(SEAT_MAP["seats"], **{PANEL[-1]: {"source": "live", "family": "anthropic"}})
    out = rr.reading_next([NO_READING, NO_READING], _seats(seats=seats), ["anthropic"])
    assert out == {"next": "park", "reason": "a roster seat in the seat map is from a maker's family"}


def test_a_reviewer_before_the_only_makers_joined_is_not_reviewed():
    # axis: a panel reviewer at a step no maker faced counted as independent because a later fixer named a maker
    fake = Fake(runs={"/run/code-reviewer": (dict(CLAUDE_RUN, viewHeadSha=EARLIER), None)})
    rev = [maker_family_reviewer(commit=EARLIER, step=2), reviewer("audit", step=3)]
    rec = build(account(makers=[{"family": "anthropic", "fromStep": 3}], reviewers=rev), fake)
    assert rec["status"] == "not-reviewed" and rec["reviewers"][0]["ran"] == "not-run"


def test_reading_next_parks_when_a_roster_seat_names_no_vendor_or_model():
    # axis: the dispatchable-seat park; a family-only seat letting the lane move up with no reviewer to dispatch
    seats = {n: {k: v for k, v in e.items() if k not in ("vendor", "model")} for n, e in SEAT_MAP["seats"].items()}
    out = rr.reading_next([NO_READING, NO_READING], _seats(seats=seats), ["anthropic"])
    assert out == {"next": "park", "reason": "a roster seat in the seat map names no vendor or model"}


def _without(name):
    return {"roster": [n for n in PANEL if n != name],
            "seats": {n: v for n, v in SEAT_MAP["seats"].items() if n != name}}


@pytest.mark.parametrize("seat_map", [
    None, "text", [], {}, _seats(roster=[]), _seats(roster="ab"), {"roster": PANEL},
    _seats(seats="x"), _seats(seats={PANEL[0]: SEAT_MAP["seats"][PANEL[0]]}),
    _seats(seats=dict(SEAT_MAP["seats"], **{PANEL[1]: "x"})),
    _seats(seats=dict(SEAT_MAP["seats"], **{PANEL[1]: {"source": "live"}})),
    _seats(seats=dict(SEAT_MAP["seats"], **{PANEL[1]: {"source": "live", "family": ""}})),
    _seats(seats=dict(SEAT_MAP["seats"], **{PANEL[1]: {"source": "live", "family": 3}})),
    {"roster": ["code-reviewer"], "seats": {"code-reviewer": {"source": "live", "family": "openai"}}},
    _without("test-role"),
])
def test_reading_next_parks_on_a_map_that_cannot_show_independence(seat_map):
    out = rr.reading_next([NO_READING, NO_READING], seat_map, ["anthropic"])
    assert out["next"] == "park" and out["reason"]


def test_reading_next_parks_with_no_maker_family():
    assert rr.reading_next([NO_READING, NO_READING], SEAT_MAP, [])["next"] == "park"


def test_reading_next_cli_prints_one_object_and_exits_zero(tmp_path, monkeypatch, capsys):
    maps = tmp_path / "map.json"
    maps.write_text(json.dumps(SEAT_MAP))
    monkeypatch.setattr(rr, "_engine_run", lambda d: ({"a": NO_READING, "b": NO_READING}.get(d), None))
    base = ["reading-next", "--run-dir", "a", "--run-dir", "b", "--maker-family", "anthropic"]
    assert rr.main(base + ["--seat-map", str(maps)]) == 0
    assert json.loads(capsys.readouterr().out)["next"] == "move-up"
    assert rr.main(base + ["--seat-map", str(tmp_path / "missing.json")]) == 0
    assert json.loads(capsys.readouterr().out)["next"] == "park"
    assert rr.main(base) == 0
    assert json.loads(capsys.readouterr().out)["next"] == "park"
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    assert rr.main(base + ["--seat-map", str(bad)]) == 0
    assert json.loads(capsys.readouterr().out)["next"] == "park"
    assert rr.main(["reading-next", "--run-dir", "a", "--maker-family", "anthropic"]) == 0
    assert json.loads(capsys.readouterr().out)["next"] == "rerun"


def test_reading_next_cli_reads_real_engine_journals(tmp_path, capsys):
    # axis: the CLI entry point; reading-next composed with the real persisted run record, no stand-in for _engine_run
    import test_engine_dispatch as ted

    def run(name, outputs):
        run_dir = str(tmp_path / name)
        ted.ED.dispatch_review(
            seat=ted._codex_seat(), prompt_path=ted._valid_prompt(tmp_path), repo_root=ted._repo(tmp_path),
            run_engine=ted.FakeRunner(outputs), build_view=ted._fake_build_view(tmp_path), run_dir=run_dir)
        return run_dir

    engaged = run("engaged", [(ted._VALID_FINDINGS_STDOUT, False, 0, "")])
    forfeited = run("forfeited", [("not json", False, 0, ""), ("not json", False, 0, "")])
    second = run("second", [("not json", False, 0, ""), ("not json", False, 0, "")])
    maps = tmp_path / "map.json"
    maps.write_text(json.dumps(SEAT_MAP))
    tail = ["--maker-family", "anthropic", "--seat-map", str(maps)]

    def nxt(*dirs):
        assert rr.main(["reading-next"] + [a for d in dirs for a in ("--run-dir", d)] + tail) == 0
        return json.loads(capsys.readouterr().out)["next"]

    assert nxt(engaged) == "accept"
    assert nxt(forfeited) == "rerun"
    assert nxt(forfeited, forfeited) == "rerun"  # one persisted run counted twice is still one run
    assert nxt(forfeited, second) == "move-up"


# --- the move-up check follows the composed panel ---

NO_FLOOR_BASIS = {"floor": None}
RISKY_BASIS = {"floor": "full"}
TWO_SEAT_MAP = seat_map_module.to_receipt(
    seat_map_module.build(list(seat_map_module.roster_for(NO_FLOOR_BASIS)),
                          ["codex", "cursor", "gemini"], "anthropic", 0), "anthropic")


def test_move_up_holds_a_no_floor_basis_to_the_two_seat_roster():
    # axis: the move-up check requires the roster the lane basis calls for, not the full panel — see bite-proof record wo_a_1797_roster
    assert len(TWO_SEAT_MAP["roster"]) == 2
    assert rr._move_up_blocker(TWO_SEAT_MAP, frozenset(["anthropic"]), NO_FLOOR_BASIS) is None
    out = rr.reading_next([NO_READING, NO_READING], TWO_SEAT_MAP, ["anthropic"], NO_FLOOR_BASIS)
    assert out["next"] == "move-up"


def test_move_up_blocks_a_three_seat_roster_under_a_risky_basis_and_names_the_missing_seats():
    blocker = rr._move_up_blocker(TWO_SEAT_MAP, frozenset(["anthropic"]), RISKY_BASIS)
    assert blocker.startswith("the seat map's roster omits a panel seat")
    assert "security-reviewer" in blocker and "premortem-reviewer" in blocker
    assert "code-reviewer" not in blocker and "test-role" not in blocker


def test_move_up_with_no_lane_basis_requires_the_full_risky_roster():
    for basis in (None, "full", {}, {"lane": "full"}):
        blocker = rr._move_up_blocker(TWO_SEAT_MAP, frozenset(["anthropic"]), basis)
        assert blocker and "omits a panel seat" in blocker, basis
    out = rr.reading_next([NO_READING, NO_READING], TWO_SEAT_MAP, ["anthropic"])
    assert out["next"] == "park" and "omits a panel seat" in out["reason"]


def test_reading_next_reads_the_lane_basis_the_seat_map_carries_unless_one_is_given():
    carried = dict(TWO_SEAT_MAP, laneBasis=NO_FLOOR_BASIS)
    assert rr.reading_next([NO_READING, NO_READING], carried, ["anthropic"])["next"] == "move-up"
    given = rr.reading_next([NO_READING, NO_READING], carried, ["anthropic"], RISKY_BASIS)
    assert given["next"] == "park" and "security-reviewer" in given["reason"]


def test_a_full_roster_still_moves_up_under_either_basis():
    for basis in (None, NO_FLOOR_BASIS, RISKY_BASIS):
        assert rr._move_up_blocker(SEAT_MAP, frozenset(["anthropic"]), basis) is None, basis


# --- the GitHub reads page by number (#1890): the cloud proxy refuses --paginate's repositories/{id} hops ---

def api_comment(n, body=None):
    return {"id": n, "user": {"login": "bot"}, "body": body if body is not None else f"chat {n}",
            "html_url": f"http://c/{n}"}


def pages_asked(seen, tail):
    """The page numbers requested for the endpoint ending in `tail`, in order."""
    return [int(a[2].rsplit("page=", 1)[1]) for a in seen if a[2].split("?")[0].endswith(tail)]


def test_cloud_cli_read_pages_the_comments_by_number_and_finds_the_latest_record_on_page_three(tmp_path):
    # axis: the CLI read in a cloud session; a PR with over 100 comments read through --paginate, which the proxy refuses
    comments = [api_comment(n) for n in range(1, 261)]
    comments[4] = api_comment(5, rr.render(build(account(sessionId="early"))))
    comments[254] = api_comment(255, rr.render(build(account(sessionId="late"))))
    state, argv_log = tmp_path / "gh-state.json", tmp_path / "gh-argv.log"
    state.write_text(json.dumps(comments))
    gh_dir = tmp_path / "bin"
    gh_dir.mkdir()
    gh = gh_dir / "gh"
    gh.write_text(f"""#!{sys.executable}
import json, sys
a = sys.argv[1:]
with open({str(argv_log)!r}, "a") as log:
    log.write(json.dumps(a) + "\\n")
if "--paginate" in a or any("repositories/" in x for x in a):
    sys.exit(3)
if a[0] == "api" and a[1].startswith("repos/o/r/issues/7/comments?per_page=100&page="):
    page = int(a[1].rsplit("page=", 1)[1])
    print(json.dumps(json.load(open({str(state)!r}))[(page - 1) * 100:page * 100]))
else:
    sys.exit(2)
""")
    gh.chmod(0o755)
    env = {"PATH": f"{gh_dir}:/usr/bin:/bin", "HOME": str(tmp_path), "CLAUDE_CODE_REMOTE": "true"}
    proc = subprocess.run([sys.executable, "-B", rr.__file__, "read", "--pr", "7", "--repo", "o/r"],
                          capture_output=True, text=True, env=env, cwd=str(tmp_path))
    got = json.loads(proc.stdout)
    assert proc.returncode == 0 and got["ok"], (proc.stdout, proc.stderr)
    assert got["url"] == "http://c/255" and got["earlierRecords"] == ["http://c/5"]
    calls = [json.loads(line) for line in argv_log.read_text().splitlines()]
    assert not [c for c in calls if "--paginate" in c], calls
    assert [c[1] for c in calls] == [f"repos/o/r/issues/7/comments?per_page=100&page={n}" for n in (1, 2, 3)]


def test_cloud_check_runs_are_read_page_by_number_and_a_failure_on_page_three_makes_ci_red(monkeypatch):
    # axis: CI pagination under the cloud proxy; a failing check on page three hidden by --paginate being refused or by a first-page read
    path = f"repos/o/r/commits/{HEAD}/check-runs"
    rows = [{"name": f"c{i}", "status": "completed", "conclusion": "success"} for i in range(249)]
    rows.append({"name": "last", "status": "completed", "conclusion": "failure"})
    seen = []
    monkeypatch.setattr(rr, "_run", cloud_proxy(
        {path: (rows, "check_runs"), "repos/o/r/actions/runs": ([], "workflow_runs")}, seen))
    runs, st, wf = rr._check_data(HEAD, "o/r")
    assert runs["check_runs"] == rows and rr.ci_state(runs, st, wf) == "red"
    assert pages_asked(seen, "/check-runs") == [1, 2, 3]


def test_cloud_changed_paths_are_read_page_by_number_in_order(monkeypatch):
    # axis: the PR file list under the cloud proxy; a list over 100 files refused or cut to its first page
    files = [{"filename": f"src/f{i:03d}.py", "status": "added"} for i in range(250)]
    seen = []
    monkeypatch.setattr(rr, "_run", cloud_proxy({"repos/o/r/pulls/7/files": (files, None)}, seen))
    assert rr.changed_paths(7, "o/r") == [f["filename"] for f in files]
    assert pages_asked(seen, "/files") == [1, 2, 3]


@pytest.mark.parametrize("count, pages", [(100, [1, 2]), (200, [1, 2, 3])])
def test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read(monkeypatch, count, pages):
    # axis: the end of a list; a list of exactly 100 or 200 rows treated as unfinished (failing) or read past the empty page
    comments = [api_comment(n) for n in range(count)]
    seen = []
    monkeypatch.setattr(rr, "_run", cloud_proxy({"repos/o/r/issues/7/comments": (comments, None)}, seen))
    got = rr._list_comments(7, "o/r")
    assert [c["id"] for c in got] == list(range(count))
    assert pages_asked(seen, "/comments") == pages


def three_readers_routes(rows=250):
    ok = {"status": "completed", "conclusion": "success"}
    return {"repos/o/r/issues/7/comments": ([api_comment(n) for n in range(rows)], None),
            "repos/o/r/pulls/7/files": ([{"filename": f"f{n}"} for n in range(rows)], None),
            f"repos/o/r/commits/{HEAD}/check-runs": ([ok] * rows, "check_runs"),
            "repos/o/r/actions/runs": ([], "workflow_runs")}


def test_a_page_that_fails_makes_the_whole_read_unavailable_for_every_reader(monkeypatch):
    # axis: the complete-or-absent list; a failed page returning the rows read so far as if they were the whole list
    routes = three_readers_routes()
    for failed in (1, 2, 3):
        monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={failed: None}))
        assert rr._list_comments(7, "o/r") is None
        assert rr.changed_paths(7, "o/r") is None
        assert rr._check_data(HEAD, "o/r") is None
        got = rr.read(7, "o/r")
        assert got["ok"] is False and got["reason"] == "review-record-gh-failed"
    monkeypatch.setattr(rr, "_run", cloud_proxy(routes))
    assert len(rr._list_comments(7, "o/r")) == 250 and len(rr.changed_paths(7, "o/r")) == 250
    assert len(rr._check_data(HEAD, "o/r")[0]["check_runs"]) == 250


def test_a_page_that_is_not_json_or_not_a_list_makes_the_read_unavailable(monkeypatch):
    # axis: page shape; a page that is not JSON, or an object where a list belongs, skipped as an empty page that ends the read
    routes = three_readers_routes(150)
    for page in (1, 2):
        for text in ("not json", "{broken", '{"message": "Not Found"}', "null", '"x"'):
            monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={page: text}))
            assert rr._list_comments(7, "o/r") is None, (page, text)
            assert rr.changed_paths(7, "o/r") is None, (page, text)
            assert rr._check_data(HEAD, "o/r") is None, (page, text)
    # check runs: a page must be an object holding a list under check_runs
    for text in ('{"total_count": 0}', '{"total_count": 1, "check_runs": "x"}', '{"check_runs": {"a": 1}}', "[]"):
        monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={1: text}))
        assert rr._check_data(HEAD, "o/r") is None, text
    monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={2: '{"check_runs": 5}'}))
    assert rr._check_data(HEAD, "o/r") is None
    # comments and files: an object where the list belongs
    monkeypatch.setattr(rr, "_run", cloud_proxy(routes, override={2: '{"check_runs": []}'}))
    assert rr._list_comments(7, "o/r") is None and rr.changed_paths(7, "o/r") is None


def test_a_list_that_never_ends_fails_the_read_after_the_page_cap(monkeypatch):
    # axis: the page cap; a list that never ends returning the rows read so far, or being asked for without end
    assert gh_pages.MAX_PAGES == 1000 and gh_pages.PAGE_ROWS == 100
    monkeypatch.setattr(gh_pages, "MAX_PAGES", 4)
    seen = []

    def endless(argv, cwd=None):
        seen.append(list(argv))
        return json.dumps([{"filename": "f"}] * 100)
    monkeypatch.setattr(rr, "_run", endless)
    assert rr._read_pages("repos/o/r/pulls/7/files") is None
    assert len(seen) == 4
    assert rr.changed_paths(7, "o/r") is None


# --- the paths withheld from reviewers ---

CORE_MD = ".claude/superheroes/core.md"
SETTINGS = ".claude/settings.json"
SRC = "src/a.py"
WITHHELD_LEAD = "Withheld from reviewers (not readable in full; the vet checks these by hand): "


def _regular_blobs(monkeypatch, *paths):
    """Serve the head tree as regular files for `paths`, so the real withheld rule runs without a git repository."""
    entries = [("100644", "blob", str(i) * 40, p) for i, p in enumerate(paths)]
    monkeypatch.setattr(sanitized_view, "_git_ls_tree_export", lambda repo_real, sha: entries)


def _withheld_record(tmp_path, monkeypatch, changed, **over):
    fake = Fake()
    fake.changed = changed
    _regular_blobs(monkeypatch, *changed)
    return build(account(repoRoot=str(tmp_path), **over), fake)


def test_r1_a_changed_calibration_file_is_shown_and_a_changed_settings_file_is_listed(tmp_path, monkeypatch):
    # axis: the withheld list from the one rule; a shown calibration file listed, or a stripped settings file left out
    rec = _withheld_record(tmp_path, monkeypatch, [CORE_MD, SETTINGS, SRC])
    assert rec["withheldFromReviewers"] == [SETTINGS]
    assert f"{WITHHELD_LEAD}{SETTINGS}." in rr.render(rec)


def test_r2_a_change_with_nothing_withheld_records_an_empty_list(tmp_path, monkeypatch):
    # axis: the empty list; a change with nothing withheld read as unknown, or the none line missing
    rec = _withheld_record(tmp_path, monkeypatch, [SRC])
    assert rec["withheldFromReviewers"] == []
    assert "Withheld from reviewers: none." in rr.render(rec)


def test_r3_unreadable_changed_files_record_null_not_an_empty_list(tmp_path):
    # axis: the unread leg; an unreadable changed-file list recorded as an empty list
    fake = Fake()
    fake.changed = None
    rec = build(account(repoRoot=str(tmp_path)), fake)
    assert rec["withheldFromReviewers"] is None
    assert "Withheld from reviewers: could not be read" in rr.render(rec)


def test_r3b_an_account_naming_no_repository_reads_no_changed_files_and_records_null():
    # axis: the no-repoRoot leg of the withheld list; an account naming no repository reading the PR's files anyway
    calls = []
    readers = {**Fake().readers(), "changed_paths": lambda pr, repo: calls.append((pr, repo)) or [SETTINGS]}
    rec = rr.build_record(account(), readers)
    assert rec["withheldFromReviewers"] is None
    assert calls == []


def test_r4_the_changed_files_are_read_once_per_record(tmp_path):
    # axis: the one-read cache; the lane basis and the withheld list each reading the PR's files
    calls = []
    readers = {**Fake().readers(), "changed_paths": lambda pr, repo: calls.append((pr, repo)) or [SRC]}
    rec = rr.build_record(account(repoRoot=str(tmp_path)), readers)
    assert rec["withheldFromReviewers"] == []
    assert len(calls) == 1


def test_r5_a_withheld_path_named_like_a_claim_does_not_trip_the_claim_check(tmp_path, monkeypatch):
    # axis: the withheld line's exemption from the claim check; a path spelling a claim refusing the render
    rec = _withheld_record(tmp_path, monkeypatch, [".claude/bug-free.md"])
    assert rec["withheldFromReviewers"] == [".claude/bug-free.md"]
    rr.render_plan(rec)


def test_r6_five_hundred_withheld_paths_become_a_count_in_the_head_and_are_whole_in_the_parts(tmp_path, monkeypatch):
    # axis: the withheld list across the parts split; paths cut short or dropped when the record goes to parts
    paths = [f".claude/p{i}.md" for i in range(500)]
    rec = _withheld_record(tmp_path, monkeypatch, paths)
    rec["whatIsMissing"] = rec["whatIsMissing"] + ["w" * rr.MAX_BODY_CHARS]
    plan = rr.render_plan(rec)
    assert plan.parts
    ids = list(range(1, len(plan.parts) + 1))
    head = plan.head(ids)
    assert "500 paths" in head
    posted = rr._parse_body(head, {i: {"body": part} for i, part in zip(ids, plan.parts)})
    assert posted["withheldFromReviewers"] == sorted(paths)


def test_r7_withheld_paths_do_not_change_the_status(tmp_path, monkeypatch):
    # axis: the status's independence from the withheld list; a withheld path lowering or raising the status
    plain = _withheld_record(tmp_path, monkeypatch, [SRC])
    held = _withheld_record(tmp_path, monkeypatch, [SRC, SETTINGS])
    assert plain["withheldFromReviewers"] == [] and held["withheldFromReviewers"] == [SETTINGS]
    assert held["status"] == plain["status"]


@pytest.mark.parametrize("root", [None, "tmp"])
def test_r8_a_head_tree_that_cannot_be_read_lists_every_stripped_path(tmp_path, root):
    # axis: the fail-closed head-tree read; an unreadable tree treating a calibration file as shown
    repo_root = str(tmp_path) if root else None
    assert sanitized_view.withheld_review_paths(repo_root, "a" * 40, [CORE_MD, SRC]) == [CORE_MD]


# --- CI green reads only the project's CI workflow ---

def wf_run(name, status="completed", conclusion="success", **over):
    return {"id": over.pop("id", 100), "name": name, "event": "push", "status": status,
            "conclusion": conclusion if status == "completed" else None, **over}


def wfs(*rows):
    return {"workflow_runs": list(rows)}


CHECK_OK = {"check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]}
CHECK_PENDING = {"check_runs": [{"name": "validate", "status": "in_progress", "conclusion": None}]}
VERCEL = {"state": "success", "total_count": 2,
          "statuses": [{"state": "success", "context": "Vercel"}, {"state": "success", "context": "Vercel Preview Comments"}]}
DECLARED_CI = ("declared", "CI")


def test_third_party_checks_alone_never_make_ci_green():
    # axis: green needs the project's CI to have run; third-party statuses or non-Actions check runs reading green on their own
    assert rr.ci_state({"check_runs": []}, VERCEL, wfs()) == "none"
    assert rr.ci_state({"check_runs": []}, VERCEL) == "none"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs()) == "none"
    assert rr.ci_state(CHECK_OK, VERCEL, wfs()) == "none"
    assert rr.ci_reading(CHECK_OK, NO_STATUS, wfs())["read"] == "no CI workflow declared; no GitHub Actions run on this commit"


def chk(name, id, conclusion, suite, app_id=15368, slug="github-actions", status="completed"):
    return {"id": id, "name": name, "app": {"id": app_id, "slug": slug}, "check_suite": {"id": suite},
            "status": status, "conclusion": conclusion if status == "completed" else None}


def suite_run(name, suite, workflow_id=325422332, **over):
    return wf_run(name, id=over.pop("id", suite + 1), workflow_id=workflow_id, event="pull_request",
                  check_suite_id=suite, run_number=suite, **over)


def checks(*rows):
    return {"check_runs": list(rows)}


def test_a_check_run_a_newer_run_of_the_same_check_replaced_no_longer_reads_red():
    # axis: the check-run reduction; an older cancelled run of a check that a newer run replaced reading CI red, in either row order
    old, new = chk("pr-title", 1, "cancelled", 10), chk("pr-title", 2, "success", 20)
    workflows = wfs(suite_run("pr-title", 10), suite_run("pr-title", 20), wf_run("CI", id=5, workflow_id=7))
    for rows in ([old, new], [new, old]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "green"
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows, DECLARED_CI) == "green"


def test_a_check_whose_newest_run_is_not_green_reads_red():
    # axis: the check-run reduction; keeping the older run, or dropping the only run of a check, hiding a newest run that is red
    workflows = wfs(suite_run("pr-title", 10), suite_run("pr-title", 20), wf_run("CI", id=5, workflow_id=7))
    assert rr.ci_state(checks(chk("pr-title", 1, "cancelled", 10)), NO_STATUS, workflows) == "red"
    older, newest = chk("pr-title", 1, "success", 10), chk("pr-title", 2, "cancelled", 20)
    for rows in ([older, newest], [newest, older]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "red"
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows, DECLARED_CI) == "red"


def test_runs_of_different_checks_never_replace_one_another():
    # axis: the check identity; a failed check hidden by a newer success of a different workflow, app or name
    ci = wf_run("CI", id=5, workflow_id=222, event="pull_request", check_suite_id=20)
    in_progress = wf_run("A", "in_progress", id=3, workflow_id=111, event="pull_request", check_suite_id=10)
    failed, passed = chk("validate", 1, "failure", 10), chk("validate", 2, "success", 20)
    for rows in ([failed, passed], [passed, failed]):
        assert rr.ci_state(checks(*rows), NO_STATUS, wfs(in_progress, ci), DECLARED_CI) == "red"
    other_app = [chk("validate", 1, "failure", 10, app_id=99, slug="circleci"),
                 chk("validate", 2, "success", 20, app_id=100, slug="other-app")]
    for rows in (other_app, other_app[::-1]):
        assert rr.ci_state(checks(*rows), NO_STATUS, wfs(wf_run("CI", id=5))) == "red"
    workflows = wfs(suite_run("pr-title", 10), suite_run("pr-title", 20), wf_run("CI", id=5, workflow_id=7))
    names = [chk("lint", 1, "failure", 10), chk("pr-title", 2, "success", 20)]
    for rows in (names, names[::-1]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "red"


def test_runs_of_the_same_check_on_different_branches_never_replace_one_another():
    # axis: the check identity's head branch; a failed pr-title of one PR hidden by a newer success of another PR sharing the head SHA
    workflows = wfs(suite_run("pr-title", 10, head_branch="a"), suite_run("pr-title", 20, head_branch="b"),
                    wf_run("CI", id=5, workflow_id=7))
    failed, passed = chk("pr-title", 1, "failure", 10), chk("pr-title", 2, "success", 20)
    for rows in ([failed, passed], [passed, failed]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "red"


def test_runs_of_the_same_check_on_different_pull_requests_never_replace_one_another():
    # axis: the check identity's pull request; two PRs from one head branch to different bases sharing the head SHA
    workflows = wfs(suite_run("pr-title", 10, head_branch="a", pull_requests=[{"number": 1}]),
                    suite_run("pr-title", 20, head_branch="a", pull_requests=[{"number": 2}]),
                    wf_run("CI", id=5, workflow_id=7))
    failed, passed = chk("pr-title", 1, "failure", 10), chk("pr-title", 2, "success", 20)
    for rows in ([failed, passed], [passed, failed]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "red"


def test_a_check_run_whose_identity_cannot_be_established_is_never_reduced_away():
    # axis: the fail-closed reduction; a failed row with no app, or an Actions suite mapped to no workflow run, dropped for a newer success
    workflows = wfs(suite_run("pr-title", 20), wf_run("CI", id=5, workflow_id=7))
    no_app = [dict(chk("pr-title", 1, "cancelled", 10), app=None), chk("pr-title", 2, "success", 20)]
    unmapped = [chk("pr-title", 1, "cancelled", 99), chk("pr-title", 2, "success", 100)]
    for rows in (no_app, no_app[::-1], unmapped, unmapped[::-1]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "red"


def test_a_cancelled_run_replaced_by_a_newer_run_still_in_progress_reads_pending():
    # axis: the pending test reading the reduced runs; the superseded cancelled run reading red, or the in-progress run ignored
    workflows = wfs(suite_run("pr-title", 10), suite_run("pr-title", 20), wf_run("CI", id=5, workflow_id=7))
    old, new = chk("pr-title", 1, "cancelled", 10), chk("pr-title", 2, None, 20, status="in_progress")
    for rows in ([old, new], [new, old]):
        assert rr.ci_state(checks(*rows), NO_STATUS, workflows) == "pending"


def test_a_replaced_check_is_reduced_across_pages_and_an_unrelated_failure_on_a_later_page_stays_red(monkeypatch):
    # axis: the reduction over the whole paged check list; a superseded run on page one read red, or a later page's failure dropped
    path = f"repos/o/r/commits/{HEAD}/check-runs"
    actions = [dict(suite_run("pr-title", 10), head_sha=HEAD), dict(suite_run("pr-title", 20), head_sha=HEAD),
               dict(wf_run("CI", id=5, workflow_id=7), head_sha=HEAD)]
    page_one = [chk("pr-title", 1, "cancelled", 10)] + [chk(f"u{i}", 1000 + i, "success", 10) for i in range(99)]
    newer = chk("pr-title", 2, "success", 20)
    for tail, state in (([newer], "green"), ([newer, chk("unrelated", 3, "failure", 20)], "red")):
        seen = []
        monkeypatch.setattr(rr, "_run", cloud_proxy({path: (page_one + tail, "check_runs"),
                                                     "repos/o/r/actions/runs": (actions, "workflow_runs")}, seen))
        runs, st, wf = rr._check_data(HEAD, "o/r")
        assert len(runs["check_runs"]) == 100 + len(tail) and rr.ci_state(runs, st, wf) == state
        assert pages_asked(seen, "/check-runs")[:2] == [1, 2]


def test_a_declared_workflow_alone_decides_pending_and_green():
    # axis: the declared workflow's selection; another workflow's run, or a third-party status, deciding the state
    release = wf_run("Release Please", id=1)
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", "in_progress", id=2), release), DECLARED_CI) == "pending"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(release), DECLARED_CI) == "none"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2), release), DECLARED_CI) == "green"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", conclusion="skipped", id=2)), DECLARED_CI) == "none"
    pending_status = {"state": "pending", "total_count": 1, "statuses": [{"state": "pending", "context": "Vercel"}]}
    assert rr.ci_state(CHECK_PENDING, pending_status, wfs(wf_run("CI", id=2)), DECLARED_CI) == "green"
    got = rr.ci_reading(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2), release), DECLARED_CI)
    assert got == {"state": "green", "workflow": "CI", "read": "workflow CI: run 2 success"}
    assert rr.ci_reading(CHECK_OK, NO_STATUS, wfs(release), DECLARED_CI)["read"] == "workflow CI: no run on this commit"


def test_with_no_declaration_green_needs_a_succeeded_actions_run():
    # axis: the undeclared reading; green check runs counted as green with no GitHub Actions run that succeeded
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2))) == "green"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", conclusion="skipped", id=2))) == "none"
    assert rr.ci_state(CHECK_PENDING, NO_STATUS, wfs(wf_run("CI", id=2))) == "pending"
    got = rr.ci_reading(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2), wf_run("Release Please", id=1)))
    assert got["workflow"] is None
    assert got["read"] == "no CI workflow declared; GitHub Actions runs: Release Please run 1 success, CI run 2 success"


def test_a_declaration_that_cannot_be_read_never_makes_ci_green():
    # axis: an unreadable declaration; falling back to the undeclared reading and reading green
    got = rr.ci_reading(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2)), ("unreadable", None))
    assert got == {"state": "none", "workflow": None, "read": "the CI workflow declaration could not be read"}
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("CI", conclusion="failure", id=2)), ("unreadable", None)) == "red"


def test_any_red_still_reads_red():
    # axis: red wins; a failed status or workflow run hidden behind a green declared workflow or a succeeded Actions run
    failed = {"state": "failure", "total_count": 1, "statuses": [{"state": "failure", "context": "Vercel"}]}
    assert rr.ci_state(CHECK_OK, failed, wfs(wf_run("CI", id=2)), DECLARED_CI) == "red"
    assert rr.ci_state(CHECK_OK, failed, wfs(wf_run("CI", id=2))) == "red"
    other_failed = wfs(wf_run("CI", id=2), wf_run("Release Please", conclusion="failure", id=3))
    assert rr.ci_state(CHECK_OK, NO_STATUS, other_failed, DECLARED_CI) == "red"
    assert rr.ci_state(CHECK_OK, NO_STATUS, other_failed) == "red"


def test_only_the_newest_run_per_workflow_and_event_counts():
    # axis: supersession; an older failed run of a workflow that re-ran at the same commit holding CI red, or an older success hiding a newer failure
    def pr_title(number, conclusion):
        return wf_run("pr-title", conclusion=conclusion, id=50 + number, workflow_id=7, event="pull_request", run_number=number)
    ci = wf_run("CI", id=2)
    mended = wfs(pr_title(1, "failure"), pr_title(2, "success"), ci)
    assert rr.ci_state(CHECK_OK, NO_STATUS, mended, DECLARED_CI) == "green"
    assert rr.ci_state(CHECK_OK, NO_STATUS, mended) == "green"
    broken = wfs(pr_title(1, "success"), pr_title(2, "failure"), ci)
    assert rr.ci_state(CHECK_OK, NO_STATUS, broken, DECLARED_CI) == "red"
    assert rr.ci_state(CHECK_OK, NO_STATUS, broken) == "red"
    # without a run number the larger id is the newer run
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("pr-title", conclusion="failure", id=5),
                                                wf_run("pr-title", id=9), ci)) == "green"


def test_the_newest_run_wins_whatever_order_the_runs_are_listed_in():
    # axis: supersession by rank, not list position; an older run listed last taken as the current one
    def pr_title(number, conclusion):
        return wf_run("pr-title", conclusion=conclusion, id=50 + number, workflow_id=7, event="pull_request", run_number=number)
    ci = wf_run("CI", id=2)
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(pr_title(2, "failure"), pr_title(1, "success"), ci)) == "red"
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(pr_title(2, "success"), pr_title(1, "failure"), ci)) == "green"


def test_two_events_of_one_workflow_are_each_current():
    # axis: supersession is per workflow and event; a newer run of one event hiding an unfinished run of another event of the same workflow
    pending_pr = wf_run("CI", "in_progress", id=51, workflow_id=7, event="pull_request", run_number=1)
    passed_push = wf_run("CI", id=52, workflow_id=7, event="push", run_number=2)
    assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(pending_pr, passed_push), DECLARED_CI) == "pending"


def test_the_record_names_the_workflow_it_read_ci_from(tmp_path):
    # axis: the record's ci field; a record that hides which workflow CI was read from, or drops the source
    fake = Fake(ci=(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2))))
    declared = dict(fake.readers(), ci_workflow=lambda root: DECLARED_CI)
    rec = rr.build_record(account(), declared)
    assert rec["ci"] == {"state": "green", "sha": HEAD, "source": "GitHub checks", "workflow": "CI",
                         "read": "workflow CI: run 2 success"}
    rec = build(account(), fake)
    assert rec["ci"]["source"] == "GitHub checks" and rec["ci"]["workflow"] is None
    assert rec["ci"]["read"] == "no CI workflow declared; GitHub Actions runs: CI run 2 success"
    out = rr.write(put(tmp_path, account()), str(tmp_path), declared)
    assert out["ok"], out
    read_back = rr.read(7, readers=declared)
    assert (read_back["ci"]["workflow"], read_back["ci"]["source"]) == ("CI", "GitHub checks")
    missing = dict(Fake(ci=(CHECK_OK, NO_STATUS, wfs(wf_run("Release Please", id=1)))).readers(),
                   ci_workflow=lambda root: DECLARED_CI)
    rec = rr.build_record(account(), missing)
    assert rec["status"] == "not-reviewed" and rec["ci"]["state"] == "none"
    assert f"CI is none on {HEAD[:7]} (workflow CI: no run on this commit)" in rec["whatIsMissing"]
    unavailable = rr.build_record(account(), dict(declared, check_data=lambda sha, repo: None))
    assert unavailable["ci"] == {"state": "none", "sha": None, "source": "unavailable", "workflow": "CI",
                                 "read": "CI could not be read"}


def test_a_status_line_for_a_record_written_before_the_read_key_keeps_the_old_wording():
    # axis: the missing-line wording; a record with no read key failing to render, or the old wording changing
    rec = build(account(), Fake(ci=RED))
    old = {**rec, "ci": {k: v for k, v in rec["ci"].items() if k not in ("workflow", "read")}}
    lines = rr._status(old)[2]
    assert f"CI is red on {HEAD[:7]}" in lines and not any(line.startswith(f"CI is red on {HEAD[:7]} (") for line in lines)


def write_core(repo, block_extra=None, raw_block=None, schema=core_md.SCHEMA_VERSION):
    d = repo / ".claude" / "superheroes"
    d.mkdir(parents=True, exist_ok=True)
    block = json.dumps({"schemaVersion": schema, "verifyCommand": "npm test", "stackTags": ["node"],
                        **(block_extra or {})}, indent=2) if raw_block is None else raw_block
    (d / "core.md").write_text(
        f"<!-- superheroes-core: schemaVersion={schema} status=confirmed created=2026-06-26 updated=2026-06-26 -->\n\n"
        "## Threat model\n\nsingle-user\n\n## Canonical patterns\n\n- x: a.ts:1\n\n"
        f"```json superheroes-core\n{block}\n```\n")
    return str(repo)


def test_the_declaration_reader_without_a_repo_root_is_unreadable():
    # axis: the reader's no-root edge; an unknown checkout reading as no declaration
    assert rr._ci_workflow(None) == ("unreadable", None)


def test_the_declaration_reader_reads_an_absent_profile_as_absent(tmp_path):
    # axis: the reader's absent-profile edge; a project with no profile reading as an unreadable declaration
    assert rr._ci_workflow(str(tmp_path)) == ("absent", None)


def test_the_declaration_reader_reads_a_corrupt_profile_as_unreadable(tmp_path):
    # axis: the reader's corrupt-profile edge; a profile that cannot be parsed reading as no declaration
    repo = write_core(tmp_path, raw_block="{not json")
    assert rr._ci_workflow(repo) == ("unreadable", None)


def test_the_declaration_reader_reads_a_missing_declaration_as_absent(tmp_path):
    # axis: the reader's undeclared edge; a profile with no ciWorkflow key reading as unreadable
    assert rr._ci_workflow(write_core(tmp_path)) == ("absent", None)
    other = tmp_path / "other"
    other.mkdir()
    assert rr._ci_workflow(write_core(other, {"projectConfiguration": {"stackingTool": "gh-stack"}})) == ("absent", None)


def test_the_declaration_reader_reads_a_non_mapping_configuration_as_unreadable(tmp_path):
    # axis: the reader's non-mapping edge; a projectConfiguration that is not a mapping reading as no declaration
    assert rr._ci_workflow(write_core(tmp_path, {"projectConfiguration": ["ciWorkflow", "CI"]})) == ("unreadable", None)


@pytest.mark.parametrize("value", [None, 5, True, ["CI"], {"name": "CI"}, "", "   "])
def test_the_declaration_reader_reads_a_bad_value_as_unreadable(tmp_path, value):
    # axis: the reader's bad-value edge; a declared key holding null, a non-string or a blank string reading as no declaration
    repo = write_core(tmp_path, {"projectConfiguration": {"ciWorkflow": value}})
    assert rr._ci_workflow(repo) == ("unreadable", None)


def test_the_declaration_reader_reads_the_workflow_name_stripped(tmp_path):
    # axis: the reader's declared edge; the declared name not reaching the reading, or reaching it unstripped
    repo = write_core(tmp_path, {"projectConfiguration": {"ciWorkflow": "  CI "}})
    assert rr._ci_workflow(repo) == ("declared", "CI")


def test_the_declaration_reader_never_raises(tmp_path, monkeypatch):
    # axis: the reader's exception edge; a failing profile read escaping to the record writer
    repo = write_core(tmp_path, {"projectConfiguration": {"ciWorkflow": "CI"}})

    def boom(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(core_md, "read", boom)
    assert rr._ci_workflow(repo) == ("unreadable", None)


def test_the_declaration_reader_writes_nothing(tmp_path, monkeypatch):
    # axis: the reader's purity; reading a profile writing the mode record or the profile
    repo = write_core(tmp_path, {"projectConfiguration": {"ciWorkflow": "CI"}})
    core = tmp_path / ".claude" / "superheroes" / "core.md"
    before, text = sorted(str(p) for p in tmp_path.rglob("*")), core.read_text()
    rr._ci_workflow(repo)
    assert sorted(str(p) for p in tmp_path.rglob("*")) == before and core.read_text() == text

    # a profile with only the in-repo review-crew layer: the mode registry is never backfilled
    repo = tmp_path / "repo"
    layer = repo / ".claude" / "superheroes"
    layer.mkdir(parents=True)
    (layer / "review-crew.md").write_text("# review crew\n")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    calls = []
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    monkeypatch.setattr(mode_registry, "write_registry", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert rr._ci_workflow(str(repo)) == ("absent", None)
    assert calls == []


def test_a_failed_workflow_run_read_makes_check_data_unavailable(monkeypatch):
    # axis: workflow-run pagination; a failed or malformed actions/runs read treated as no workflow runs
    routes = three_readers_routes(3)
    serve = cloud_proxy(routes)
    monkeypatch.setattr(rr, "_run", serve)
    runs, status, workflow_runs = rr._check_data(HEAD, "o/r")
    assert workflow_runs == {"workflow_runs": []} and len(runs["check_runs"]) == 3
    for served in (None, "not json", "{broken", '{"message": "Not Found"}', '{"workflow_runs": "x"}', "[]"):
        monkeypatch.setattr(rr, "_run", lambda argv, cwd=None, served=served: (
            served if "actions/runs" in argv[2] else serve(argv, cwd)))
        assert rr._check_data(HEAD, "o/r") is None, served
    for rows in (["x"], [None], [wf_run("CI"), 5], [[1]]):
        monkeypatch.setattr(rr, "_run", cloud_proxy({**routes, "repos/o/r/actions/runs": (rows, "workflow_runs")}))
        assert rr._check_data(HEAD, "o/r") is None, rows
    monkeypatch.setattr(rr, "_run", cloud_proxy({**routes, "repos/o/r/actions/runs": ([wf_run("CI", head_sha=HEAD)], "workflow_runs")}))
    assert rr._check_data(HEAD, "o/r")[2] == {"workflow_runs": [wf_run("CI", head_sha=HEAD)]}


def test_a_workflow_run_page_that_is_missing_makes_check_data_unavailable(monkeypatch):
    # axis: workflow-run pagination; a failed actions/runs page on a later page treated as the whole list
    routes = {**three_readers_routes(3), "repos/o/r/actions/runs": ([wf_run("CI", head_sha=HEAD)] * 150, "workflow_runs")}
    monkeypatch.setattr(rr, "_run", cloud_proxy(routes))
    assert len(rr._check_data(HEAD, "o/r")[2]["workflow_runs"]) == 150
    serve = cloud_proxy(routes)
    monkeypatch.setattr(rr, "_run", lambda argv, cwd=None: None if "actions/runs" in argv[2] and "page=2" in argv[2] else serve(argv, cwd))
    assert rr._check_data(HEAD, "o/r") is None


def test_an_unfinished_run_under_the_fallback_reads_pending():
    # axis: the fallback's unfinished run; a finished pr-title run reading green while CI is still queued
    for status in ("queued", "waiting", "in_progress", "requested", "pending"):
        assert rr.ci_state(CHECK_OK, NO_STATUS, wfs(wf_run("pr-title", id=1), wf_run("CI", status, id=2))) == "pending", status
    assert rr.ci_state({"check_runs": []}, NO_STATUS, wfs(wf_run("pr-title", id=1), wf_run("CI", "queued", id=2))) == "pending"


def test_a_run_of_another_commit_never_counts(monkeypatch):
    # axis: the exact sha; a run of another commit, or a run with no head_sha, counted as this commit's run
    other = "a" * 40
    runs = [wf_run("CI", head_sha=other, id=1), wf_run("CI", conclusion="failure", head_sha=other, id=2, event="pull_request"),
            wf_run("CI", head_sha=HEAD, id=3), wf_run("CI", id=4)]
    monkeypatch.setattr(rr, "_run", cloud_proxy({**three_readers_routes(3), "repos/o/r/actions/runs": (runs, "workflow_runs")}))
    got = rr._check_data(HEAD, "o/r")
    assert got[2] == {"workflow_runs": [runs[2]]}
    assert rr.ci_state(*got) == "green"
    monkeypatch.setattr(rr, "_run", cloud_proxy({**three_readers_routes(3), "repos/o/r/actions/runs": ([runs[0]], "workflow_runs")}))
    got = rr._check_data(HEAD, "o/r")
    assert rr.ci_state(*got) == "none"
    assert rr.ci_state(*got, DECLARED_CI) == "none"


def test_an_unknown_declaration_kind_reads_none():
    # axis: the declaration kind; a kind other than declared or absent reading as an absent declaration
    got = rr.ci_reading(CHECK_OK, NO_STATUS, wfs(wf_run("CI", id=2)), ("misread", "CI"))
    assert got["state"] == "none" and got["workflow"] is None
    assert got["read"] == "the CI workflow declaration could not be read"


def test_workflow_runs_are_asked_for_by_the_head_sha_page_by_number(monkeypatch):
    # axis: the workflow-run query; runs read for another commit, or the page query not joined to head_sha
    seen = []
    monkeypatch.setattr(rr, "_run", cloud_proxy(three_readers_routes(3), seen))
    rr._check_data(HEAD, "o/r")
    assert [a[2] for a in seen if "actions/runs" in a[2]] == [f"repos/o/r/actions/runs?head_sha={HEAD}&per_page=100&page=1"]
