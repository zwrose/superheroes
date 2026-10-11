import copy
import json
import shutil
import subprocess
import sys

import pytest

import model_registry
import pr_comment
import review_record as rr

HEAD = "b" * 40
EARLIER = "a" * 40
CODEX = model_registry.codex_models()[0]
NO_STATUS = {"state": "pending", "total_count": 0, "statuses": []}
GREEN = ({"total_count": 1, "check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]},
         NO_STATUS)
PENDING = ({"check_runs": [{"name": "validate", "status": "in_progress", "conclusion": None}]}, NO_STATUS)
RED = ({"check_runs": [{"name": "validate", "status": "completed", "conclusion": "failure"}]}, NO_STATUS)
GOOD_RUN = {"source": "codex", "engineModel": CODEX, "viewHeadSha": HEAD,
            "observation": {"tokens": 100, "wallSeconds": 120}, "graded": True, "runKind": "review"}
PHRASES = ("no bugs", "bug-free", "bug free")


class Fake:
    """Injectable readers with an in-memory comment list; records create calls."""

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
            "repo_name": lambda root: "o/r",
            "list_comments": lambda pr, repo: list(self.comments),
            "create_comment": self._create,
        }

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


def account(**over):
    base = {"schema": "review-account/1", "pr": 7, "sessionId": "s1", "lane": "full", "laneReason": "big",
            "finalCommit": HEAD, "ci": "green", "reviewers": [reviewer()], "findings": [], "rawFindingsFiles": [],
            "rounds": {"count": 1, "cap": 3, "stoppedAtCap": False}, "goAheads": [], "checked": ["read the diff"]}
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
    good = {"reviewer": "security-reviewer", "kind": "standing-ruling", "canonId": "canon-7"}
    rec = build(account(reviewers=[sec], goAheads=[{"reviewer": "security-reviewer", "kind": "standing-ruling",
                                                    "canonId": True}, good]))
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
    findings += [finding("c1", outcome="craft", reason="style call"), finding("w1", outcome="shown-wrong", reason="x")]
    fake = Fake()
    out = rr.write(put(session, account(findings=findings, rawFindingsFiles=[str(raw)])), str(tmp_path), fake.readers())
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
    assert "hunter2" not in body and "abc" not in body and '"note": "ok"' in body


def test_unknown_model_takes_the_one_family_of_its_vendor(monkeypatch):
    # axis: family inference; an unknown model given a family when its vendor has several
    assert rr._family("claude", "opus-9") == "anthropic"
    assert rr._family("elsewhere", "x") is None
    two = {"claude": lambda: ("opus-5.5", CODEX)}
    monkeypatch.setattr(rr, "_VENDOR_MODELS", dict(rr._VENDOR_MODELS, **two))
    monkeypatch.setattr(model_registry, "model_family",
                        lambda v, m: {"opus-5.5": "anthropic", CODEX: "openai"}.get(m))
    assert rr._family("claude", "opus-9") is None


def test_unparseable_prior_refuses_without_writing(tmp_path):
    # axis: hand-edited record; an unreadable latest record written past
    fake = Fake()
    fake.comments = [{"id": 1, "author": "a", "body": rr.MARKER + "\nhand edited", "url": "u1"}]
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unreadable")
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"
    assert len(fake.comments) == 1 and fake.writes == []


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
    assert fake.comments == []


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


def test_check_runs_are_read_across_every_page_and_a_failed_page_is_unavailable(monkeypatch):
    # axis: CI pagination; a failing check on a later page hidden behind a green first page
    page1 = json.dumps({"total_count": 2, "check_runs": [{"status": "completed", "conclusion": "success"}]})
    page2 = json.dumps({"total_count": 2, "check_runs": [{"status": "completed", "conclusion": "failure"}]})
    status = json.dumps(NO_STATUS)

    seen = []

    def reader(out):
        # Without --paginate the command returns page one only, as gh does.
        def run(argv):
            seen.append(list(argv))
            if argv[2].endswith("/status"):
                return status
            return out if "--paginate" in argv else page1
        return run
    monkeypatch.setattr(rr, "_run", reader(page1 + page2))
    runs, st = rr._check_data(HEAD, "o/r")
    assert len(runs["check_runs"]) == 2 and rr.ci_state(runs, st) == "red"
    assert any("--paginate" in argv and "/check-runs" in argv[2] for argv in seen)
    monkeypatch.setattr(rr, "_run", reader(page1 + "{broken"))
    assert rr._check_data(HEAD, "o/r") is None
    monkeypatch.setattr(rr, "_run", reader(None))
    assert rr._check_data(HEAD, "o/r") is None


def test_left_for_owner_finding_is_not_reviewed_until_decided():
    # axis: left-for-owner; an undecided owner finding counted as reviewed
    rec = build(account(findings=[finding("f1", outcome="left-for-owner", reason="needs owner")]))
    assert rec["status"] == "not-reviewed" and "finding f1 waits for the owner's decision" in rec["whatIsMissing"]
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
    huge = [finding("h-1", body="h" * (rr.MAX_BODY_CHARS + 10))]
    out = rr.write(put(tmp_path, account(findings=huge)), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-too-large") and fake.comments == []


def test_a_record_too_large_to_post_leaves_the_earlier_comments_untouched(tmp_path):
    # axis: pre-check ordering; a comment created or changed before the new record is known to fit
    fake = Fake()
    send(tmp_path, fake)
    before, writes = [dict(c) for c in fake.comments], list(fake.writes)
    huge = [finding("h-1", body="h" * (rr.MAX_BODY_CHARS + 10))]
    out = rr.write(put(tmp_path, account(findings=huge)), str(tmp_path), fake.readers())
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
    out = rr.write(put(tmp_path, account(findings=[finding("a-1", outcome="shown-wrong", reason="not a bug here")])),
                   str(tmp_path), fake.readers())
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
    out = rr.write(put(tmp_path, account(findings=[dict(titled, outcome="shown-wrong", reason="r")])),
                   str(tmp_path), fake.readers())
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
    out = rr.write(put(tmp_path, account(findings=[dict(titled, outcome="shown-wrong", reason="r")])),
                   str(tmp_path), fake.readers())
    assert out["ok"] and out["action"] == "created"


@pytest.mark.parametrize("bad", [{"a": 1}, "x", None, [1], [None]])
def test_w10_a_malformed_earlier_findings_list_is_unreadable(tmp_path, bad):
    # axis: malformed prior; a findings field that is not a list of objects read as having no findings
    fake = Fake()
    rec = build(account())
    rec["findings"] = bad
    fake.comments = [{"id": 1, "author": "a", "body": rr.render(rec), "url": "u1"}]
    out = rr.write(put(tmp_path, account()), str(tmp_path), fake.readers())
    assert (out["ok"], out["reason"]) == (False, "review-record-unreadable") and len(fake.comments) == 1


MAKERS = [{"family": "anthropic", "source": "builder"}]
OWNER_WORD = {"words": "go ahead", "where": "http://c/9"}


def test_x1_maker_and_independence_fields_pass_through_and_show(tmp_path):
    # axis: pass-through fields; makers, notIndependent or ownerWord dropped, altered or left out of the summary
    fake = Fake()
    send(tmp_path, fake, makers=MAKERS, reviewers=[reviewer(notIndependent=True, ownerWord=OWNER_WORD)])
    rec = rr.read(7, readers=fake.readers())
    assert rec["makers"] == MAKERS
    assert rec["reviewers"][0]["notIndependent"] is True and rec["reviewers"][0]["ownerWord"] == OWNER_WORD
    body = fake.marked()[0]["body"]
    assert "Makers: anthropic." in body and "not independent of the makers" in body
    assert "owner's word: http://c/9" in body


def test_x2_the_pass_through_fields_change_no_status():
    # axis: no logic on the pass-through fields; status, parked or whatIsMissing depending on them
    with_fields = build(account(makers=MAKERS, reviewers=[reviewer(notIndependent=True, ownerWord=OWNER_WORD)]))
    without = build(account())
    assert [with_fields[k] for k in ("status", "parked", "whatIsMissing")] == \
        [without[k] for k in ("status", "parked", "whatIsMissing")]
    assert without["makers"] == [] and not {"notIndependent", "ownerWord"} & set(without["reviewers"][0])


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


def test_x3_none_and_false_are_accepted_as_given():
    # axis: optional fields; None refused, or False dropped instead of carried as given
    rec = build(account(makers=None, reviewers=[reviewer(notIndependent=False, ownerWord=None)]))
    assert rec["makers"] == [] and rec["reviewers"][0]["notIndependent"] is False
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
if a[:2] == ["repo", "view"]:
    print(json.dumps({{"nameWithOwner": "o/r"}}))
elif a[:2] == ["pr", "view"]:
    print(json.dumps({{"headRefOid": head, "body": "", "closingIssuesReferences": []}}))
elif a[0] == "api" and a[1].endswith("/check-runs?per_page=100"):
    print(json.dumps({{"total_count": 1, "check_runs": [{{"name": "v", "status": "completed", "conclusion": "success"}}]}}))
elif a[0] == "api" and a[1].endswith("/status"):
    print(json.dumps({{"state": "pending", "total_count": 0, "statuses": []}}))
elif a[0] == "api" and "-X" in a:
    body = open(a[a.index("-F") + 1].split("=@", 1)[1]).read()
    n = len(s["comments"]) + 1
    s["comments"].append({{"id": n, "user": {{"login": "bot"}}, "body": body, "html_url": "http://c/%d" % n}})
    json.dump(s, open(state, "w"))
    print(json.dumps({{"id": n, "html_url": "http://c/%d" % n}}))
elif a[0] == "api" and a[1].endswith("/comments"):
    print(json.dumps(s["comments"]))
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
