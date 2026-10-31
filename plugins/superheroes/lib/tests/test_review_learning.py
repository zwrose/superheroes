"""Tests for lib/review_learning.py (#1718, review C10): the adoption day, the owner-approved
calibration change, and the seat tally."""
import datetime
import types
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import canon  # noqa: E402
import core_md  # noqa: E402
import definition_doc  # noqa: E402
import mode_registry  # noqa: E402
import project_config  # noqa: E402
import review_learning as RL  # noqa: E402
import review_record_session  # noqa: E402
import review_round_policy  # noqa: E402
import review_seats  # noqa: E402
import risk_areas  # noqa: E402
import round_driver  # noqa: E402

PAYMENTS = {"name": "Payments", "covers": ["src/payments/*"], "why": "Charges customers.",
            "undo": "Hard: a charge needs a refund."}
AUTH = {"name": "Auth", "covers": ["src/auth/*"], "why": "Decides who gets in.",
        "undo": "Moderate: rotate keys and sessions."}
RULING = "Auth is a risk area: changes under src/auth/ get the risk-area review."
APPROVAL = {"answer": "yes", "words": "Yes, add auth as a risk area.",
            "where": "session abcd1234, 14:05 UTC", "date": "2026-10-13"}
SID = "abcd1234-ffff"
CANON_REL = "docs/superheroes/canon.md"
CARRIED = review_record_session.CARRIED


def _proposal(**over):
    base = {"schema": "calibration-proposal/1", "kind": "risk-and-trust", "half": "riskAreas",
            "value": [PAYMENTS, AUTH], "ruling": RULING}
    base.update(over)
    return base


def _git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


def _identity(cwd):
    _git(cwd, "config", "commit.gpgsign", "false")  # the ambient config signs through a service a test cannot reach
    _git(cwd, "config", "user.name", "t")  # the fixture repo's own identity; production code passes none
    _git(cwd, "config", "user.email", "t@example.com")


@pytest.fixture
def proj(tmp_path, monkeypatch):
    """A project whose core.md holds one risk area, payments, covering src/payments/."""
    repo, store = str(tmp_path / "proj"), str(tmp_path / "store")
    os.makedirs(repo)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", store)  # the ambient store is the fixture's: Canon's lookup follows it
    _git(repo, "init", "-q")
    _git(repo, "remote", "add", "origin", "git@github.com:o/r.git")
    mode_registry.write_registry(repo, mode_registry.IN_REPO, "rk", root=store)
    core_md.write(repo, {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
                         "patterns": "- x: a.ts:1"}, "confirmed", root=store, now="2026-06-26")
    assert project_config.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS]}, root=store)["action"] == "written"
    return repo, store


@pytest.fixture
def canon_root(tmp_path, monkeypatch):
    """A Canon repo-home fixture: its own git repository, the lookup pinned to it."""
    work = str(tmp_path / "canonrepo")
    os.makedirs(work)
    _git(work, "init", "-q", "-b", "main")
    _identity(work)
    with open(os.path.join(work, "README"), "w") as fh:
        fh.write("x\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "init")
    loc = {"path": os.path.join(work, CANON_REL), "home": "repo", "gitRoot": work, "exists": False,
           "defaultRef": None}
    monkeypatch.setattr(definition_doc, "resolve_canon", lambda root: dict(loc))
    return work


def _bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _state(proj_, canon_):
    repo, store = proj_
    return (_bytes(core_md.core_path(repo, store)), _bytes(os.path.join(canon_, CANON_REL)),
            _git(canon_, "rev-parse", "HEAD"))


def _touched(proj_):
    repo, store = proj_
    return [t["area"]["name"] for t in risk_areas.touched(repo, ["src/auth/login.py"], root=store)["touched"]]


def _apply(proj_, canon_, proposal, approval):
    repo, store = proj_
    return RL.apply(repo, proposal, approval, canon_root=canon_, session_id=SID, root=store)


# --- FR-75 / I1: calibration changes only on the owner's yes ---

# axis: the guarding test for the no-owner-yes refusal — nothing is written without the owner's exact yes
def test_no_owner_yes_writes_nothing(proj, canon_root):
    before = _state(proj, canon_root)
    no_words = dict(APPROVAL, words="")
    cases = [None, dict(APPROVAL, answer="not yet"), dict(APPROVAL, answer="Yes"), no_words,
             dict(APPROVAL, where=" "), dict(APPROVAL, date="13/10/2026"), {k: v for k, v in APPROVAL.items() if k != "date"}]
    for approval in cases:
        got = _apply(proj, canon_root, _proposal(), approval)
        assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "no-owner-yes"), approval
        assert _state(proj, canon_root) == before
    assert _touched(proj) == []


def test_apply_refuses_a_canon_root_that_resolves_to_another_project(proj, canon_root, tmp_path, monkeypatch):
    repo, store = proj
    other = str(tmp_path / "otherrepo")
    os.makedirs(other)
    _git(other, "init", "-q", "-b", "main")
    _identity(other)
    with open(os.path.join(other, "README"), "w") as fh:
        fh.write("x\n")
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "init")
    homes = {os.path.realpath(repo): canon_root, os.path.realpath(other): other}

    def resolve(root):  # Canon's lookup per project: each project's Canon lives in its own repository
        work = homes[os.path.realpath(root)]
        return {"path": os.path.join(work, CANON_REL), "home": "repo", "gitRoot": work, "exists": False, "defaultRef": None}
    monkeypatch.setattr(definition_doc, "resolve_canon", resolve)
    before, other_before = _state(proj, canon_root), _git(other, "rev-parse", "HEAD")
    got = RL.apply(repo, _proposal(), APPROVAL, canon_root=other, session_id=SID, root=store)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "canon-root-mismatch")
    assert os.path.join(other, CANON_REL) in got["detail"] and os.path.join(canon_root, CANON_REL) in got["detail"]
    assert _state(proj, canon_root) == before and _git(other, "rev-parse", "HEAD") == other_before
    assert not os.path.exists(os.path.join(other, CANON_REL)) and _touched(proj) == []


def test_apply_refuses_a_store_override_canon_cannot_carry(proj, canon_root, tmp_path):
    repo, _ = proj
    before = _state(proj, canon_root)
    got = RL.apply(repo, _proposal(), APPROVAL, canon_root=canon_root, session_id=SID, root=str(tmp_path / "other"))
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "store-override-unsupported")
    assert _state(proj, canon_root) == before and _touched(proj) == []


# --- FR-76 / I2: recorded in Canon by Canon's procedure, then applied ---

def test_valid_yes_records_canon_commits_and_applies(proj, canon_root):
    before = _state(proj, canon_root)
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["calibration"]) == (True, "applied", "risk-and-trust")
    shown = _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()
    entries = [l for l in shown if l.startswith("- **")]
    assert entries == [got["canonEntry"]] and len(entries) == 1
    assert RULING in entries[0] and "standing" in entries[0] and 'owner\'s words: "%s"' % APPROVAL["words"] in entries[0]
    assert entries[0].split(" · ")[1] == APPROVAL["date"] and entries[0].endswith("where: " + APPROVAL["where"])
    touched = set(_git(canon_root, "show", "--name-only", "--format=", "HEAD").split())
    assert touched == {CANON_REL, "docs/superheroes/.gitattributes"}
    assert _git(canon_root, "rev-parse", "HEAD").strip() == got["canonCommit"] != before[2].strip()
    assert _touched(proj) == ["Auth"]
    repo, store = proj
    assert project_config.get_item(repo, "riskAndTrust", root=store)["raw"]["riskAreas"] == [PAYMENTS, AUTH]


def test_supersedes_is_validated_and_carried_into_canon(proj, canon_root):
    old = _apply(proj, canon_root, {"schema": "calibration-proposal/1", "kind": "standing-ruling", "ruling": RULING}, APPROVAL)
    old_id = old["canonEntry"].split("**")[1]
    before = _state(proj, canon_root)
    for bad in ("", "not-an-id", 7, None):
        got = _apply(proj, canon_root, _proposal(supersedes=bad), APPROVAL)
        assert (got["ok"], got["reason"]) == (False, "proposal-invalid"), bad
    assert _state(proj, canon_root) == before
    new = {"schema": "calibration-proposal/1", "kind": "standing-ruling", "ruling": "Auth is no longer a risk area.",
           "supersedes": old_id}
    got = _apply(proj, canon_root, new, APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied")
    assert "supersedes: " + old_id in got["canonEntry"]
    assert got["canonEntry"] in _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()


def test_standing_ruling_is_canon_only(proj, canon_root):
    before = _state(proj, canon_root)
    got = _apply(proj, canon_root, {"schema": "calibration-proposal/1", "kind": "standing-ruling", "ruling": RULING}, APPROVAL)
    assert (got["ok"], got["outcome"], got["calibration"]) == (True, "applied", "canon-only")
    assert got["canonEntry"] in _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()
    assert _state(proj, canon_root)[0] == before[0]
    assert _touched(proj) == []


@pytest.mark.parametrize("proposal", [
    _proposal(threatModel="Outsiders only."),
    _proposal(kind="something-else"),
    _proposal(kind=["risk-and-trust"]),
    _proposal(kind=None),
    _proposal(value=[{"name": "Auth"}]),
    _proposal(half="owners"),
    _proposal(ruling="one · two"),
    _proposal(ruling="two\nlines"),
    _proposal(ruling=" "),
    _proposal(schema="calibration-proposal/2"),
    "not an object",
    None,
])
def test_invalid_proposal_refuses_and_writes_nothing(proj, canon_root, proposal):
    before = _state(proj, canon_root)
    got = _apply(proj, canon_root, proposal, APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "proposal-invalid")
    assert got["detail"]
    assert _state(proj, canon_root) == before


def test_canon_stays_out_refusal_writes_nothing(proj, canon_root):
    before = _state(proj, canon_root)
    got = _apply(proj, canon_root, _proposal(), dict(APPROVAL, words="merge it"))
    assert (got["outcome"], got["reason"]) == ("refused", "proposal-invalid")
    assert _state(proj, canon_root) == before


def test_partial_when_the_calibration_write_refuses(proj, canon_root, monkeypatch):
    monkeypatch.setattr(project_config, "set_item", lambda *a, **k: {"action": "refused", "reason": "boom"})
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"]) == (False, "partial")
    assert got["canonEntry"] in _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()
    assert got["canonEntry"] in got["detail"] and got["set"]["reason"] == "boom"
    assert _touched(proj) == []


def test_partial_when_the_calibration_write_raises_after_the_canon_commit(proj, canon_root, monkeypatch):
    def boom(*a, **k):
        raise ValueError("verify-command-malformed: core.md verifyCommand must be a non-empty string")
    monkeypatch.setattr(project_config, "set_item", boom)
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "partial", "calibration-not-written")
    assert got["canonEntry"] in _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()
    assert got["canonCommit"] and got["canonEntry"] in got["detail"]
    assert "ValueError" in got["detail"] and "verify-command-malformed" in got["detail"]


def test_failed_canon_commit_leaves_calibration_alone(proj, canon_root):
    hooks = os.path.join(canon_root, ".git", "hooks")
    _git(canon_root, "config", "core.hooksPath", hooks)  # the fixture's own hooks dir, whatever the ambient config says
    hook = os.path.join(hooks, "pre-commit")
    with open(hook, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(hook, 0o755)
    core_before = _state(proj, canon_root)[0]
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "canon-not-committed", "canon-commit-failed")
    assert _state(proj, canon_root)[0] == core_before and _touched(proj) == []


def test_canon_commit_timeout_reads_canon_not_committed(proj, canon_root, monkeypatch):
    real = RL._run_git

    def hang(cwd, *args):
        if args[0] == "commit":
            raise subprocess.TimeoutExpired(["git", "-C", cwd, *args], RL.GIT_TIMEOUT_SECONDS)
        return real(cwd, *args)
    monkeypatch.setattr(RL, "_run_git", hang)
    core_before = _state(proj, canon_root)[0]
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "canon-not-committed", "canon-commit-failed")
    assert "timed out" in got["detail"]
    assert _state(proj, canon_root)[0] == core_before and _touched(proj) == []


def test_canon_commit_carries_only_canons_paths(proj, canon_root):
    with open(os.path.join(canon_root, "unrelated.txt"), "w") as fh:
        fh.write("staged by someone else\n")
    _git(canon_root, "add", "unrelated.txt")
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert got["ok"] is True
    touched = set(_git(canon_root, "show", "--name-only", "--format=", "HEAD").split())
    assert "unrelated.txt" not in touched and CANON_REL in touched
    assert "unrelated.txt" in _git(canon_root, "diff", "--cached", "--name-only").split()


def test_tally_escape_with_a_non_string_call_reads_malformed_not_a_crash():
    for call in (["missed"], {"a": 1}, 7, None):
        got = RL.tally([], [{"pr": 1, "reviewedAt": "2026-10-05", "call": call}], D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence", call
        assert got["leftOut"]["malformed"] == 1


# --- I3: the adoption day is recorded once ---

def test_adopt_records_then_reads_back_and_same_day_is_unchanged(proj):
    repo, store = proj
    assert RL.adoption_day(repo, store) == {"since": None, "reason": "not-recorded"}
    got = RL.record_adoption_day(repo, "2026-10-13", store)
    assert (got["ok"], got["outcome"], got["since"], got["reason"], got["detail"]) == (True, "recorded", "2026-10-13", None, None)
    assert RL.adoption_day(repo, store) == {"since": "2026-10-13", "reason": None}
    assert RL.record_adoption_day(repo, "2026-10-13", store)["outcome"] == "unchanged"


# axis: the guarding test for the adoption day being set once — a different day never overwrites it
def test_adopt_other_day_refuses_and_names_the_stored_day(proj):
    repo, store = proj
    RL.record_adoption_day(repo, "2026-10-13", store)
    got = RL.record_adoption_day(repo, "2026-10-20", store)
    assert (got["ok"], got["outcome"], got["reason"], got["detail"]) == (False, "refused", "adoption-day-already-recorded", "2026-10-13")
    assert RL.adoption_day(repo, store)["since"] == "2026-10-13"


@pytest.mark.parametrize("day", ["tomorrow", "2026-13-01", "2026-10-1", "20261013", None, ""])
def test_adopt_bad_date(proj, day):
    repo, store = proj
    got = RL.record_adoption_day(repo, day, store)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "bad-date")
    assert RL.adoption_day(repo, store)["reason"] == "not-recorded"


def test_malformed_stored_day_reads_malformed_and_is_not_overwritten(proj):
    repo, store = proj
    core_md.write_project_config_item(repo, "reviewLearningSince", "garbage", root=store)
    assert RL.adoption_day(repo, store) == {"since": None, "reason": "malformed"}
    got = RL.record_adoption_day(repo, "2026-10-13", store)
    assert (got["outcome"], got["reason"], got["detail"]) == ("refused", "adoption-day-already-recorded", "garbage")


def test_the_extra_key_does_not_break_the_item_read_and_survives_a_set(proj):
    repo, store = proj
    before = len(project_config.view(repo, root=store)["items"])
    RL.record_adoption_day(repo, "2026-10-13", store)
    assert len(project_config.view(repo, root=store)["items"]) == before
    assert project_config.set_item(repo, "riskAndTrust", {"riskAreas": [PAYMENTS, AUTH]}, root=store)["action"] == "written"
    assert RL.adoption_day(repo, store)["since"] == "2026-10-13"


# --- I4 / FR-81: the tally ---

D = "2026-10-10"


def _row(name, ran="engine-record"):
    return {"name": name, "ran": ran}


def _finding(key, reviewer, outcome="fixed", fid=None):
    f = {"id": fid or key.upper(), "outcome": outcome, "reviewer": reviewer}
    if key:
        f["findingKey"] = key
    return f


def _record(pr, session, day, rows, findings=()):
    return {"pr": pr, "sessionId": session, "writtenAt": day + "T10:00:00Z", "reviewers": list(rows), "findings": list(findings)}


def _truth_table_records():
    """One latest record per PR, as the record writer reads it."""
    return [
        _record(1, "s1", "2026-10-09", [_row("code-reviewer")], [_finding("k-old", "Code")]),
        _record(2, "s2", D, [_row("code-reviewer"), _row("confirm security", "reported-by-session"), _row("test-role", "not-run")],
                [_finding("k-new", "Code, Security"), _finding("k-open", "Test", "left-for-owner")]),
        _record(3, "s3", "2026-10-11", [_row("code-reviewer")], [_finding("k-late", "Security"), _finding("k-late", "Security")]),
    ]


def _escapes():
    return [{"pr": 1, "reviewedAt": "2026-10-09", "call": "missed", "record": "r"},
            {"pr": 2, "reviewedAt": D, "call": "missed", "record": "r"},
            {"pr": 2, "reviewedAt": D, "call": "seen-and-left", "record": "r"}]


def test_tally_truth_table():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11")
    assert (got["measured"], got["reason"], got["since"]) == (True, None, D)
    assert got["window"] == {"from": D, "until": "2026-10-11"}
    # each PR is dated by its record: PR 1 (before adoption) is out, the others count, and a repeated finding key is one catch
    assert got["seats"] == {"code-reviewer": {"reviews": 2, "caught": 1}, "security-reviewer": {"reviews": 1, "caught": 2}}
    assert got["unattributedCatches"] == 0
    assert got["escapes"] == {"missed": 1, "seenAndLeft": 1}
    assert got["leftOut"] == {"beforeWindow": 2, "afterWindow": 0, "undated": 0, "malformed": 0}  # PR 1's record and the escape dated before adoption


# axis: the guarding test for the before-adoption exclusion — an event dated before the adoption day never counts
def test_tally_nothing_before_the_adoption_day_counts():
    records = [_record(1, "s1", "2026-10-09", [_row("code-reviewer")], [_finding("k-old", "Code")])]
    escapes = [{"pr": 1, "reviewedAt": "2026-10-09", "call": "missed", "record": "r"}]
    got = RL.tally(records, escapes, D, until="2026-10-11")
    assert got["seats"] == {} and got["unattributedCatches"] == 0
    assert got["escapes"] == {"missed": 0, "seenAndLeft": 0}
    assert got["leftOut"]["beforeWindow"] == 2


def test_tally_a_pr_dated_before_adoption_is_out_by_its_record():
    got = RL.tally(_truth_table_records()[:2], [], D, until="2026-10-11")
    assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}, "security-reviewer": {"reviews": 1, "caught": 1}}
    assert got["unattributedCatches"] == 0 and got["leftOut"]["beforeWindow"] == 1


# axis: the guarding test for the duplicate-PR rule — a PR supplied twice (a retried record) is incomplete evidence, never a second catch
@pytest.mark.parametrize("second_pr", [1, "1"])
def test_tally_a_pr_supplied_twice_reads_incomplete_evidence(second_pr):
    one = _record(1, "same", D, [_row("code-reviewer")], [_finding("k", "Code")])
    got = RL.tally([one, dict(one, pr=second_pr)], [], D, until="2026-10-11")
    assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
    assert got["leftOut"]["malformed"] == 1
    assert RL.tally([one], [], D, until="2026-10-11")["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}}


def test_tally_finding_without_a_key_falls_back_to_its_id():
    one, two = _finding(None, "Code", fid="F-1"), _finding(None, "Code", fid="F-2")
    got = RL.tally([_record(1, "a", D, [_row("code-reviewer")], [one, two])], [], D, until="2026-10-11")
    assert got["seats"]["code-reviewer"]["caught"] == 2  # two distinct keyless findings are two catches, not one


def test_tally_no_adoption_day_is_unmeasured_with_no_counts():
    got = RL.tally(_truth_table_records(), _escapes(), None, until="2026-10-11")
    assert (got["measured"], got["reason"]) == (False, "no-adoption-day")
    assert got["seats"] == {} and got["unattributedCatches"] is None
    assert got["escapes"] == {"missed": None, "seenAndLeft": None}
    assert set(got["leftOut"].values()) == {None}


def test_tally_window_reaching_before_adoption_is_short_of_window_and_still_counts_from_adoption():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11", window_days=5)
    assert (got["measured"], got["reason"]) == (False, "short-of-window")
    assert got["window"] == {"from": "2026-10-07", "until": "2026-10-11"}
    assert got["seats"]["code-reviewer"] == {"reviews": 2, "caught": 1}
    assert got["leftOut"]["beforeWindow"] == 2


def test_tally_window_inside_the_adoption_period_is_measured_and_excludes_earlier_days():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11", window_days=1)
    assert (got["measured"], got["window"]["from"]) == (True, "2026-10-11")
    assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 0}, "security-reviewer": {"reviews": 0, "caught": 1}}
    assert got["unattributedCatches"] == 0
    assert got["leftOut"]["beforeWindow"] == 5  # the two records before the window, and the three escapes dated D-1 and D


def test_tally_records_after_until_are_ignored_and_counted():
    got = RL.tally([_record(1, "s", "2026-10-20", [_row("code-reviewer")], [_finding("k", "Code")])], [], D, until="2026-10-11")
    assert got["seats"] == {} and got["leftOut"]["afterWindow"] == 1


def test_tally_undated_and_malformed_records_contribute_nothing():
    bad = [{"pr": 1, "sessionId": "x", "reviewers": [_row("code-reviewer")], "findings": [_finding("k", "Code")]},
           {"pr": 1, "sessionId": "y", "writtenAt": "yesterday", "reviewers": [_row("code-reviewer")]}, "junk"]
    got = RL.tally(bad, [], D, until="2026-10-11")
    assert got["seats"] == {} and got["unattributedCatches"] is None  # unmeasured, never a zero
    assert (got["measured"], got["reason"]) == (False, "incomplete-evidence")
    assert got["leftOut"]["undated"] == 2 and got["leftOut"]["malformed"] == 1


def test_tally_until_defaults_to_today_utc():
    before = datetime.datetime.now(datetime.timezone.utc).date()
    got = RL.tally([], [], D)
    after = datetime.datetime.now(datetime.timezone.utc).date()
    assert got["window"]["until"] in {before.isoformat(), after.isoformat()}  # a run crossing UTC midnight stays green
    assert got["measured"] is True


@pytest.mark.parametrize("name, seats", [
    ("Code", ["code-reviewer"]), ("code-reviewer", ["code-reviewer"]), ("Test", ["test-role"]),
    ("architecture", ["architecture-reviewer"]), ("Security (round 2)", ["security-reviewer"]),
    ("failure-mode", ["premortem-reviewer"]), ("confirm security", ["security-reviewer"]),
    ("Audit Code (round 3)", ["code-reviewer"]), ("Code, Security", ["code-reviewer", "security-reviewer"]),
    ("Code, code-reviewer", ["code-reviewer"]), ("Fresh Eyes", []), ("custom-seat", []),
    ("", []), (None, []), ("confirm", []), ("audits code-001 (round 2)", []), ("Audit Code, verifier", ["code-reviewer"]),
])
def test_seat_normalization(name, seats):
    assert RL._seats(name) == seats


def test_seat_dimension_mapping_has_one_home_with_dispatch():
    # every dispatched seat is reachable from the learning loop's dimension names, derived from dispatch's own tables
    assert RL.DIMENSION_SEAT is review_seats.DIMENSION_SEAT
    assert round_driver.AGENT_SUFFIX is review_seats.AGENT_SUFFIX
    assert review_round_policy.SUBJECT_FALLBACK is review_seats.SUBJECT_FALLBACK
    for seat in round_driver.AGENT_SUFFIX:
        label = round_driver._panel_dimension_label(seat)
        assert RL.DIMENSION_SEAT[label.lower()] == seat
        assert RL._seats(label) == [seat]


def test_tally_incomplete_evidence_reads_unmeasured_never_zero():
    base = _record(1, "x", D, [_row("code-reviewer")])
    refusal = dict(base, ok=False, reason="review-record-unreadable")
    no_findings = {k: v for k, v in base.items() if k != "findings"}
    no_reviewers = {k: v for k, v in base.items() if k != "reviewers"}
    for records, escapes in (([refusal], []), ([no_findings], []), ([no_reviewers], []), (["junk"], []),
                             ([{"pr": 1, "reviewers": [], "findings": []}], []), ([dict(base, reviewers=[])], []),
                             ([dict(base, reviewers=[_row("")])], []), ([dict(base, reviewers=[_row("  ")])], []),
                             ([], [{"call": "missed"}]), ([], ["junk"]),
                             ([], [{"reviewedAt": "2026-10-05", "call": "other"}])):
        got = RL.tally(records, escapes, D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence", (records, escapes)
        assert got["unattributedCatches"] is None and got["escapes"] == {"missed": None, "seenAndLeft": None}
        assert got["seats"] == {}


def test_tally_an_unread_record_outside_the_range_is_left_out_not_incomplete():
    old = dict(_record(1, "s1", "2026-10-09", [_row("code-reviewer")], []), unreadFiles=["lost-old-output.json"])
    cur = _record(2, "s2", D, [_row("code-reviewer")], [_finding("k", "Code")])
    got = RL.tally([old, cur], [], D, until="2026-10-11")
    assert got["measured"] is True and got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}}
    assert got["leftOut"]["beforeWindow"] == 1 and got["leftOut"]["malformed"] == 0
    inside = dict(old, writtenAt=D + "T10:00:00Z")  # the same damage inside the range still reads incomplete
    assert RL.tally([inside, cur], [], D, until="2026-10-11")["reason"] == "incomplete-evidence"


def test_tally_unread_reviewer_output_reads_incomplete_evidence():
    for unread in (["lost-raw.json"], "lost-raw.json", {"a": 1}):
        rec = dict(_record(1, "s", D, [_row("code-reviewer")], []), unreadFiles=unread, status="not-reviewed")
        got = RL.tally([rec], [], D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence" and got["seats"] == {}
    clean = dict(_record(1, "s", D, [_row("code-reviewer")], []), unreadFiles=[])
    assert RL.tally([clean], [], D, until="2026-10-11")["measured"] is True


def test_tally_non_lens_labels_are_not_seats_and_unlabelled_catches_are_unattributed():
    rec = _record(1, "s", D, [_row("code-reviewer"), _row("audits code-001 (round 2)"), _row("verifier")],
                  [_finding("k", "audits code-001 (round 2)")])
    got = RL.tally([rec], [], D, until="2026-10-11")
    assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 0}} and got["unattributedCatches"] == 1


def test_tally_damaged_rows_read_incomplete_not_measured_zero():
    row, fin = _row("code-reviewer"), _finding("k", "Code")
    for rec in (_record(1, "s", D, [row], [{"outcome": "fixed", "reviewer": "Code"}]),
                _record(1, "s", D, [row], [{}]), _record(1, "s", D, [row], ["junk"]),
                _record(1, "s", D, [{"name": "code-reviewer"}], [fin]),
                _record(1, "s", D, ["junk"], [fin])):
        got = RL.tally([rec], [], D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence", rec
    ok = RL.tally([_record(1, "s", D, [row], [dict(fin, outcome=None), _finding("k2", "")])], [], D, until="2026-10-11")
    assert ok["measured"] is True and ok["unattributedCatches"] == 1


def test_tally_merged_plus_label_credits_every_reviewer():
    import panel_tally
    label = panel_tally._merge_dims({"dimension": "Code"}, {"dimension": "Security"})
    assert label == "Code + Security"
    rec = _record(1, "s", D, [_row("code-reviewer"), _row("security-reviewer")], [_finding("k", label)])
    got = RL.tally([rec], [], D, until="2026-10-11")
    assert got["seats"]["code-reviewer"]["caught"] == 1 and got["seats"]["security-reviewer"]["caught"] == 1


def test_supersedes_id_grammar_is_canons():
    assert RL._canon_id("2026-10-13-abcdefgh-1") and not RL._canon_id("2026-10-13-abcdefgh-0")
    assert not RL._canon_id("2026-10-13-abcdefgh-1**x") and not RL._canon_id("2026-10-13-abcdefgh-1\nx")


# --- the CLI ---

def _json_file(tmp_path, name, value):
    path = str(tmp_path / name)
    with open(path, "w") as fh:
        json.dump(value, fh)
    return path


def _cli(capsys, *argv):
    code = RL.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_cli_adopt_and_since(proj, capsys):
    repo, store = proj
    code, out = _cli(capsys, "since", "--cwd", repo, "--root", store)
    assert (code, out["ok"], out["since"], out["reason"]) == (0, True, None, "not-recorded")
    code, out = _cli(capsys, "adopt", "--cwd", repo, "--root", store, "--date", D)
    assert (code, out["outcome"], out["since"]) == (0, "recorded", D)
    assert set(out) >= {"ok", "outcome", "reason", "detail"}
    code, out = _cli(capsys, "since", "--cwd", repo, "--root", store)
    assert (code, out["since"], out["reason"]) == (0, D, None)
    code, out = _cli(capsys, "adopt", "--cwd", repo, "--root", store, "--date", "2026-10-20")
    assert (code, out["reason"], out["detail"]) == (1, "adoption-day-already-recorded", D)
    code, out = _cli(capsys, "adopt", "--cwd", repo, "--root", store, "--date", "soon")
    assert (code, out["reason"]) == (1, "bad-date")


def test_cli_apply(proj, canon_root, tmp_path, capsys):
    repo, store = proj
    args = ["apply", "--cwd", repo, "--root", store, "--canon-root", canon_root, "--session-id", SID]
    prop = _json_file(tmp_path, "p.json", _proposal())
    code, out = _cli(capsys, *args, "--proposal", prop, "--approval", _json_file(tmp_path, "no.json", {"answer": "no"}))
    assert (code, out["outcome"], out["reason"]) == (1, "refused", "no-owner-yes")
    code, out = _cli(capsys, *args, "--proposal", prop, "--approval", str(tmp_path / "missing.json"))
    assert (code, out["reason"]) == (1, "no-owner-yes")
    code, out = _cli(capsys, *args, "--proposal", prop, "--approval", _json_file(tmp_path, "yes.json", APPROVAL))
    assert (code, out["ok"], out["outcome"], out["calibration"]) == (0, True, "applied", "risk-and-trust")
    assert _touched(proj) == ["Auth"]


def test_tally_bad_input_carries_ok_false():
    got = RL.tally([], [], "2026-10-10", until="2026-10-09")
    assert got["ok"] is False and got["reason"] == "bad-input"


def test_cli_tally(proj, tmp_path, capsys):
    repo, store = proj
    recs, escs = _json_file(tmp_path, "r.json", _truth_table_records()), _json_file(tmp_path, "e.json", _escapes())
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--since", D, "--until", "2026-10-11")
    assert code == 0 and out["measured"] is True and out["seats"]["code-reviewer"]["reviews"] == 2
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--cwd", repo, "--root", store, "--until", "2026-10-11")
    assert (code, out["measured"], out["reason"]) == (0, False, "no-adoption-day")
    RL.record_adoption_day(repo, D, store)
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--cwd", repo, "--root", store,
                     "--until", "2026-10-11", "--window-days", "5")
    assert (code, out["reason"], out["since"]) == (0, "short-of-window", D)
    code, out = _cli(capsys, "tally", "--records", str(tmp_path / "missing"), "--escapes", escs, "--since", D)
    assert (code, out["reason"]) == (1, "bad-input")


def test_tally_unknown_or_unhashable_finding_fields_read_incomplete():
    row = _row("code-reviewer")
    for bad in (dict(_finding("k", "Code"), outcome="fxed"), dict(_finding("k", "Code"), outcome=["fixed"]),
                dict(_finding("k", "Code"), findingKey=["k"])):
        got = RL.tally([_record(1, "s", D, [row], [bad])], [], D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence", bad
    for good in ("shown-wrong", "craft", "left-for-owner", "ruling", None):
        got = RL.tally([_record(1, "s", D, [row], [dict(_finding("k", "Code"), outcome=good)])], [], D, until="2026-10-11")
        assert got["measured"] is True, good


def test_tally_a_merged_member_is_not_a_second_catch():
    rows = [_row("code-reviewer"), _row("security-reviewer")]
    rep = _finding("b", "Code + Security")
    member = dict(_finding("a", "Security"), reason="folded (merged into B)")
    got = RL.tally([_record(1, "s", D, rows, [member, rep])], [], D, until="2026-10-11")
    assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}, "security-reviewer": {"reviews": 1, "caught": 1}}


# --- review C10 round 5 fixes ---

@pytest.mark.parametrize("drop", [{"pr": None}, {"sessionId": None}, {"pr": True}, {"sessionId": ""}, {"pr": [1]}, {"sessionId": 7}])
def test_tally_record_missing_review_identity_is_incomplete_evidence(drop):
    rec = dict(_record(1, "s", "2026-10-11", [_row("code-reviewer")], [_finding("k", "Code")]), **drop)
    got = RL.tally([rec], [], D, until="2026-10-11")
    assert (got["measured"], got["reason"], got["seats"]) == (False, "incomplete-evidence", {})
    assert got["leftOut"]["malformed"] == 1
    for gone in ("pr", "sessionId"):
        bare = {k: v for k, v in rec.items() if k != gone}
        assert RL.tally([bare], [], D, until="2026-10-11")["reason"] == "incomplete-evidence"


def test_tally_until_before_adoption_day_is_bad_input():
    got = RL.tally([], [], "2026-10-10", until="2026-10-09")
    assert (got["measured"], got["reason"], got["seats"]) == (False, "bad-input", {})


def test_tally_catch_is_credited_to_the_lens_seat():
    rec = _record(1, "s", D, [_row("code-reviewer"), _row("security-reviewer")], [_finding("k", "Security")])
    got = RL.tally([rec], [], D, until="2026-10-11")
    assert got["seats"]["security-reviewer"]["caught"] == 1 and got["seats"]["code-reviewer"]["caught"] == 0


def test_merged_member_marker_round_trips_through_the_record_writer():
    import review_record_session as rs
    for rep_id in ("rep-1", "pkg/a.py::title@L3", "weird (id)"):
        reason = "fixed and audited in round 2" + rs.MERGED_INTO_FORMAT.format(rep_id)
        assert rs.merged_into(reason) == rep_id
        assert RL._merged_member({"reason": reason})
    assert rs.merged_into("fixed and audited in round 2") is None and rs.merged_into(None) is None
    assert not RL._merged_member({"reason": "no mark"})


def test_merged_member_carried_into_a_later_review_still_names_its_representative(monkeypatch):
    import review_record
    import review_record_session as rs
    member = {"id": "A", "findingKey": "ka", "outcome": "fixed", "reviewer": "Code",
              "reason": "fixed and audited" + rs.MERGED_INTO_FORMAT.format("kb")}
    rep = {"id": "B", "findingKey": "kb", "outcome": "fixed", "reviewer": "Code", "reason": "fixed"}
    monkeypatch.setattr(review_record, "read", lambda pr, repo, readers: {"ok": True, "findings": [member, rep]})
    account = {"pr": 1, "findings": []}
    carried = rs._carried(account, rs._earlier(account, {"repo": "r"}, "/unused", None))
    carried_member = next(f for f in carried if f["id"] == "A")
    assert carried_member["reason"].endswith(rs.CARRIED)
    assert rs.merged_into(carried_member["reason"]) == "kb"
    later = _record(1, "s2", "2026-10-11", [_row("code-reviewer")], carried)
    got = RL.tally([later], [], D, until="2026-10-11")
    assert got["measured"] is True and got["seats"]["code-reviewer"]["caught"] == 1


@pytest.mark.parametrize("bad", [{"findingKey": ["x"]}, {"id": ["x"]}, {"id": {"u": 1}, "findingKey": "k"}])
def test_tally_unhashable_finding_identity_reads_incomplete_evidence(bad):
    row = dict(_finding("k", "Code"), **bad)
    got = RL.tally([_record(1, "s", D, [_row("code-reviewer")], [row])], [], D, until="2026-10-11")
    assert (got["measured"], got["reason"]) == (False, "incomplete-evidence")


# --- review C10 round 7 fixes ---

def test_the_persisted_adoption_key_is_the_literal_core_md_spelling(proj):
    repo, store = proj
    assert RL.SINCE_KEY == "reviewLearningSince"
    RL.record_adoption_day(repo, "2026-10-13", store)
    assert core_md.read(repo, store)["projectConfiguration"]["reviewLearningSince"] == "2026-10-13"


def test_canon_commit_that_landed_before_the_timeout_continues(proj, canon_root, monkeypatch):
    real = RL._run_git

    def slow_hook(cwd, *args):
        got = real(cwd, *args)
        if args[0] == "commit":
            raise subprocess.TimeoutExpired(["git", "-C", cwd, *args], RL.GIT_TIMEOUT_SECONDS)
        return got
    monkeypatch.setattr(RL, "_run_git", slow_hook)
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied")
    assert got["canonEntry"] in _git(canon_root, "show", "HEAD:" + CANON_REL).splitlines()
    assert got["canonCommit"] == _git(canon_root, "rev-parse", "HEAD").strip()
    assert _touched(proj) == ["Auth"]


def test_tally_an_outcome_recorded_after_until_does_not_make_a_catch():
    first = _record(1, "s", D, [_row("code-reviewer")], [_finding("k", "Code", "left-for-owner")])
    later = _record(2, "s2", "2026-10-20", [_row("code-reviewer")], [_finding("k", "Code")])
    got = RL.tally([first, later], [], D, until="2026-10-11")
    assert got["measured"] is True and got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 0}}
    assert got["leftOut"]["afterWindow"] == 1


def test_tally_reused_display_ids_across_sessions_never_merge_distinct_keys():
    rows = [_row("code-reviewer")]
    one = _record(1, "s1", D, rows, [_finding("k1", "Code", fid="code-001")])
    two = _record(2, "s2", D, rows, [_finding("k2", "Code", fid="code-001")])
    got = RL.tally([one, two], [], D, until="2026-10-12")
    assert got["seats"]["code-reviewer"] == {"reviews": 2, "caught": 2}


def test_tally_each_pr_counts_its_own_catches():
    rows = [_row("code-reviewer")]
    first = _record(1, "s1", D, rows, [_finding("k1", "Code")])
    last = _record(2, "s2", "2026-10-11", rows, [_finding("k2", "Security")])
    for order in ([first, last], [last, first]):
        got = RL.tally(order, [], D, until="2026-10-12")
        assert got["seats"]["code-reviewer"]["caught"] == 1 and got["seats"]["security-reviewer"]["caught"] == 1


def test_canon_commit_recovery_ignores_an_inherited_git_dir(proj, canon_root, monkeypatch, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    _git(str(other), "init", "-q")
    real = RL._run_git

    def slow_hook(cwd, *args):
        got = real(cwd, *args)
        if args[0] == "commit":
            raise subprocess.TimeoutExpired(["git", "-C", cwd, *args], RL.GIT_TIMEOUT_SECONDS)
        return got
    monkeypatch.setattr(RL, "_run_git", slow_hook)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied")
    assert os.environ["GIT_DIR"] == str(other / ".git")


def test_apply_a_failed_read_back_is_partial_and_unconfirmed(proj, canon_root, monkeypatch):
    monkeypatch.setattr(RL.project_config, "set_item", lambda *a, **k: {"action": "refused", "reason": RL.project_config.REASON_SET_MISMATCH})
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "partial", "calibration-unconfirmed")
    assert "may have landed" in got["detail"]


# --- the real git runner is bounded ---

def test_run_git_passes_the_timeout_to_subprocess(monkeypatch):
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(RL.subprocess, "run", fake_run)
    RL._run_git("/nowhere", "commit", "-m", "x")
    assert seen.get("timeout") == RL.GIT_TIMEOUT_SECONDS and RL.GIT_TIMEOUT_SECONDS > 0


# --- Canon's write procedure step 1: refresh the default branch first ---

def _origin_with_newer_canon(tmp_path, canon_root, canon_text="newer canon\n"):
    """A bare origin whose default branch holds a commit the canon_root clone has not fetched."""
    bare = str(tmp_path / "origin.git")
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", bare)
    _git(canon_root, "remote", "add", "origin", bare)
    _git(canon_root, "push", "-q", "origin", "main")
    other = str(tmp_path / "other")
    _git(tmp_path, "clone", "-q", bare, other)
    _identity(other)
    os.makedirs(os.path.join(other, "docs", "superheroes"))
    with open(os.path.join(other, CANON_REL), "w") as fh:
        fh.write(canon_text)
    _git(other, "add", "-A")
    _git(other, "commit", "-qm", "canon on the default branch")
    _git(other, "push", "-q", "origin", "main")
    return bare, _git(other, "rev-parse", "HEAD").strip()


def test_apply_fetches_origin_before_the_canon_lookup(proj, canon_root, tmp_path, monkeypatch):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    class _PinnedDatetime(datetime.datetime):  # pin the UTC day so a midnight crossing cannot split the minted id's day
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime.strptime(today, "%Y-%m-%d").replace(hour=12, tzinfo=tz)

    monkeypatch.setattr(canon, "datetime", types.SimpleNamespace(datetime=_PinnedDatetime, timezone=datetime.timezone))
    remote_id = today + "-abcd1234-1"  # the id apply would mint first: only the fetched default branch holds it
    remote = canon.build_line(RL._append_args(canon_root, SID[:8], _proposal(ruling="Remote ruling."), APPROVAL), remote_id)
    loc = dict(definition_doc.resolve_canon(canon_root), defaultRef="origin/main")
    _, newest = _origin_with_newer_canon(tmp_path, canon_root, remote + "\n")
    stale = _git(canon_root, "rev-parse", "origin/main").strip()
    assert stale != newest
    seen = []  # the tracking sha at every resolver call, whichever resolver makes it

    def observe(root):
        seen.append(_git(canon_root, "rev-parse", "origin/main").strip())

    monkeypatch.setattr(definition_doc, "resolve_canon", lambda root: (observe(root), dict(loc))[1])
    real = canon._locate
    monkeypatch.setattr(canon, "_locate", lambda root: (observe(root), real(root))[1])
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert got["ok"] is True and got["detail"] is None
    assert len(seen) >= 3 and set(seen) == {newest}  # every lookup, the binding check's first, saw the refreshed ref
    assert remote_id not in canon.ids_in(got["canonEntry"]) and canon.ids_in(got["canonEntry"]) == {today + "-abcd1234-2"}  # and read its Canon


def test_apply_says_so_when_the_fetch_fails_and_continues(proj, canon_root, tmp_path):
    _git(canon_root, "remote", "add", "origin", str(tmp_path / "gone.git"))
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied")
    assert "not refreshed" in got["detail"] and "fetch origin" in got["detail"]


# --- a second apply appends its own entry ---

def _entries(canon_root):
    with open(os.path.join(canon_root, CANON_REL), encoding="utf-8") as fh:
        return [l for l in fh.read().splitlines() if l.startswith("- **")]


def test_a_second_apply_appends_its_own_entry(proj, canon_root):
    first = _apply(proj, canon_root, _proposal(), APPROVAL)
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert got["ok"] is True and got["canonEntry"] != first["canonEntry"] and len(_entries(canon_root)) == 2


def test_tally_two_fixed_rows_sharing_a_key_are_one_catch_crediting_every_seat():
    rows = [_row("code-reviewer"), _row("security-reviewer")]
    pair = [_finding("k", "Code"), _finding("k", "Security", fid="K2")]
    for order in (pair, pair[::-1]):
        got = RL.tally([_record(1, "s", D, rows, order)], [], D, until="2026-10-11")
        assert got["measured"] is True and got["unattributedCatches"] == 0
        assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 1}, "security-reviewer": {"reviews": 1, "caught": 1}}


def test_apply_canon_lookups_ignore_an_inherited_git_dir(proj, monkeypatch, tmp_path):
    repo, _store = proj
    other = tmp_path / "other"
    other.mkdir()
    _git(str(other), "init", "-q")
    _identity(repo)
    bare = str(tmp_path / "origin.git")
    _git(str(tmp_path), "init", "-q", "--bare", "-b", "main", bare)
    _git(repo, "checkout", "-q", "-B", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "init", "--allow-empty")
    _git(repo, "remote", "set-url", "origin", bare)
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")
    home = definition_doc.resolve_canon(root=repo)["gitRoot"]
    os.makedirs(home, exist_ok=True)
    _git(home, "init", "-q")
    _identity(home)
    # the other checkout carries its own in-repo calibration; the redirected variables must not carry the write there
    _identity(str(other))
    mode_registry.write_registry(str(other), mode_registry.IN_REPO, "rk2", root=_store)
    core_md.write(str(other), {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
                              "patterns": "- x: a.ts:1"}, "confirmed", root=_store, now="2026-06-26")
    # both paths are resolved before the routing variables are set, so the assertions read each project's own file
    other_path = core_md.core_path(str(other), _store)
    mine_path = core_md.core_path(repo, _store)
    assert other_path != mine_path
    other_before = _bytes(other_path)
    mine_before = _bytes(mine_path)
    assert other_before is not None and other_before != mine_before
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    got = _apply(proj, repo, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied"), got
    assert os.environ["GIT_DIR"] == str(other / ".git") and os.environ["GIT_WORK_TREE"] == str(other)
    assert _bytes(mine_path) != mine_before  # the calibration landed in the requested project
    assert _bytes(other_path) == other_before  # and the other checkout's core.md is untouched


def test_adoption_day_reads_and_writes_the_requested_project_under_an_inherited_git_dir(proj, monkeypatch, tmp_path):
    repo, store = proj
    other = tmp_path / "other"
    other.mkdir()
    _git(str(other), "init", "-q")
    _identity(str(other))
    mode_registry.write_registry(str(other), mode_registry.IN_REPO, "rk3", root=store)
    core_md.write(str(other), {"verifyCommand": "npm test", "stackTags": ["node"], "threatModel": "single-user",
                              "patterns": "- x: a.ts:1"}, "confirmed", root=store, now="2026-06-26")
    other_path = core_md.core_path(str(other), store)  # resolved before the routing variables are set
    other_before = _bytes(other_path)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    got = RL.record_adoption_day(repo, "2026-10-13", store)
    assert (got["ok"], got["outcome"]) == (True, "recorded"), got
    assert os.environ["GIT_DIR"] == str(other / ".git") and os.environ["GIT_WORK_TREE"] == str(other)
    assert _bytes(other_path) == other_before  # the other checkout's core.md is untouched
    assert RL.adoption_day(repo, store) == {"since": "2026-10-13", "reason": None}
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_WORK_TREE")
    assert RL.adoption_day(repo, store) == {"since": "2026-10-13", "reason": None}
    assert RL.adoption_day(str(other), store) == {"since": None, "reason": "not-recorded"}


# --- the revisit checks: the false PR claim count and the seating numbers ---

_PLUGIN = os.path.dirname(_LIB)
_DOCTRINE = {"owner-decisions": os.path.join(_PLUGIN, "skills", "showrunner", "reference", "owner-decisions.md"),
             "vet-receipt": os.path.join(_PLUGIN, "skills", "showrunner", "reference", "vet-receipt.md"),
             "glossary": os.path.join(_PLUGIN, "rubric", "glossary.md")}
UNMEASURED = "unmeasured"
SEAT_ROW = {"outcomes": {"fixed": 3, "shown-wrong": 0, "craft": 1, "left-for-owner": 2.5, "ruling": 0}, "tokens": 12000, "minutes": 4.5}


def _claim(day=D, call="missed", **over):
    return dict({"pr": 9, "reviewedAt": day, "call": call, "record": "r", "marker": RL.FALSE_CLAIM_MARKER}, **over)


def _tally_escapes(escapes):
    return RL.tally([], escapes, D, until="2026-10-11")


# axis: the guarding test for the false-claim count — a false PR claim is counted apart and never adds to missed or seen-and-left
def test_tally_false_pr_claims_are_counted_apart_from_escapes():
    escapes = _escapes() + [_claim(D, "missed"), _claim("2026-10-11", "seen-and-left")]
    got = RL.tally(_truth_table_records(), escapes, D, until="2026-10-11")
    assert got["measured"] is True and got["reason"] is None
    assert got["escapes"] == {"missed": 1, "seenAndLeft": 1}
    assert got["falsePrClaims"] == 2
    assert got["leftOut"] == {"beforeWindow": 2, "afterWindow": 0, "undated": 0, "malformed": 0}


def test_tally_an_item_without_a_marker_counts_as_an_escape():
    got = _tally_escapes([{"pr": 1, "reviewedAt": D, "call": "missed"}, {"pr": 2, "reviewedAt": D, "call": "seen-and-left"}])
    assert got["escapes"] == {"missed": 1, "seenAndLeft": 1} and got["falsePrClaims"] == 0


def test_tally_falsePrClaims_is_zero_when_there_are_none_and_the_tally_is_measured():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11")
    assert got["measured"] is True
    assert got["falsePrClaims"] == 0 and isinstance(got["falsePrClaims"], int) and not isinstance(got["falsePrClaims"], bool)
    short = RL.tally([], [_claim()], D, until="2026-10-11", window_days=5)
    assert short["reason"] == "short-of-window" and short["falsePrClaims"] == 1


# axis: the guarding test for the unmeasured false-claim count — an unmeasured tally leaves it None, never zero
def test_tally_falsePrClaims_is_none_wherever_the_tally_is_unmeasured():
    undated = _record(1, "s1", D, [_row("code-reviewer")])
    undated["writtenAt"] = "soon"
    cases = [RL.tally([undated], [_claim()], D, until="2026-10-11"),
             RL.tally([], [_claim()], None),
             RL.tally([], [_claim()], D, until="2026-10-09")]
    assert [c["reason"] for c in cases] == ["incomplete-evidence", "no-adoption-day", "bad-input"]
    for got in cases:
        assert got["measured"] is False and got["falsePrClaims"] is None, got["reason"]
        assert got["escapes"] == {"missed": None, "seenAndLeft": None}


# E1 — axis: the guarding test for an unknown marker — it reads malformed and incomplete, never a claim or an escape
@pytest.mark.parametrize("marker", ["false-pr-claim ", "False-PR-Claim", "review-escape", "", None, 7, True, ["false-pr-claim"], {"a": 1}])
def test_tally_an_unknown_marker_reads_malformed_not_counted(marker):
    got = _tally_escapes([_claim(marker=marker)])
    assert got["measured"] is False and got["reason"] == "incomplete-evidence"
    assert got["leftOut"]["malformed"] == 1 and got["leftOut"]["undated"] == 0
    assert got["falsePrClaims"] is None and got["escapes"] == {"missed": None, "seenAndLeft": None}


@pytest.mark.parametrize("item", [{"call": "missed"}, {"reviewedAt": "2026-13-45", "call": "missed"}, {"reviewedAt": "soon", "call": "missed"},
                                  {"reviewedAt": None, "call": "missed"}])
def test_tally_a_marked_item_without_a_valid_date_reads_undated_and_incomplete(item):  # E2
    got = _tally_escapes([dict(item, marker=RL.FALSE_CLAIM_MARKER)])
    assert got["measured"] is False and got["reason"] == "incomplete-evidence"
    assert got["leftOut"]["undated"] == 1 and got["leftOut"]["malformed"] == 0
    assert got["falsePrClaims"] is None


@pytest.mark.parametrize("item", [{"reviewedAt": D}, {"reviewedAt": D, "call": "other"}, {"reviewedAt": D, "call": None},
                                  {"reviewedAt": D, "call": ["missed"]}])
def test_tally_a_marked_item_without_a_known_call_reads_malformed_and_incomplete(item):  # E3
    got = _tally_escapes([dict(item, marker=RL.FALSE_CLAIM_MARKER)])
    assert got["measured"] is False and got["reason"] == "incomplete-evidence"
    assert got["leftOut"]["malformed"] == 1 and got["leftOut"]["undated"] == 0
    assert got["falsePrClaims"] is None


def test_tally_a_marked_item_outside_the_window_is_left_out_and_does_not_make_the_tally_incomplete():  # E4, T5
    got = _tally_escapes([_claim("2026-10-09"), _claim("2026-10-12"), _claim(D), _claim("2026-10-11", "seen-and-left")])
    assert got["measured"] is True and got["reason"] is None
    assert got["falsePrClaims"] == 2 and got["escapes"] == {"missed": 0, "seenAndLeft": 0}
    assert got["leftOut"] == {"beforeWindow": 1, "afterWindow": 1, "undated": 0, "malformed": 0}
    only_early = _tally_escapes([_claim("2026-10-09")])
    assert only_early["measured"] is True and only_early["falsePrClaims"] == 0 and only_early["leftOut"]["beforeWindow"] == 1


def test_tally_a_non_dict_escape_item_reads_malformed_and_the_claim_count_none():
    got = _tally_escapes(["junk"])
    assert got["measured"] is False and got["falsePrClaims"] is None
    assert got["reason"] == "incomplete-evidence"
    assert got["leftOut"] == {"beforeWindow": 0, "afterWindow": 0, "undated": 0, "malformed": 1}


# --- the seating numbers ---

def _seat_row(**over):
    return {"security": SEAT_ROW, "premortem": {"outcomes": dict.fromkeys(RL.review_findings_schema.OUTCOMES, 0), "tokens": 0, "minutes": 0}, **over}


def test_seating_echoes_the_numbers_read_and_keeps_a_real_zero():
    got = RL.seating(_seat_row(**{"other-seat": SEAT_ROW}))
    assert got["ok"] is True and got["unmeasured"] == []
    assert list(got["seats"]) == list(RL.SEATING_SEATS) == ["security", "premortem"]
    assert list(got["seats"]["security"]["outcomes"]) == list(RL.review_findings_schema.OUTCOMES)
    assert got["seats"]["security"] == SEAT_ROW
    zero = got["seats"]["premortem"]
    assert zero["tokens"] == 0 and type(zero["tokens"]) is int
    assert zero["minutes"] == 0 and type(zero["minutes"]) is int
    assert all(n == 0 and type(n) is int for n in zero["outcomes"].values())
    ignored = RL.seating({"security": dict(SEAT_ROW, outcomes=dict(SEAT_ROW["outcomes"], bogus=4))})
    assert "bogus" not in ignored["seats"]["security"]["outcomes"]


def test_seating_a_number_not_given_reads_unmeasured_never_zero():
    row = {"security": {"outcomes": {"fixed": True, "shown-wrong": -1, "craft": "5", "left-for-owner": 2}, "minutes": None}}
    got = RL.seating(row)
    sec, pre = got["seats"]["security"], got["seats"]["premortem"]
    assert sec["outcomes"] == {"fixed": UNMEASURED, "shown-wrong": UNMEASURED, "craft": UNMEASURED, "left-for-owner": 2, "ruling": UNMEASURED}
    assert sec["tokens"] == UNMEASURED and sec["minutes"] == UNMEASURED
    assert pre == {"outcomes": dict.fromkeys(RL.review_findings_schema.OUTCOMES, UNMEASURED), "tokens": UNMEASURED, "minutes": UNMEASURED}
    expected = (["security.outcomes.%s" % o for o in ("fixed", "shown-wrong", "craft", "ruling")] + ["security.tokens", "security.minutes"]
                + ["premortem.outcomes.%s" % o for o in RL.review_findings_schema.OUTCOMES] + ["premortem.tokens", "premortem.minutes"])
    assert got["unmeasured"] == sorted(expected)


# axis: the guarding test for _measured — a missing, null, boolean, negative or non-numeric number is never shown as 0
@pytest.mark.parametrize("bad", [None, True, False, -1, -0.5, "5", "", [], {}, float("nan"), float("inf"), float("-inf")])
def test_seating_measured_never_turns_a_bad_number_into_zero(bad):
    assert RL._measured(bad) == UNMEASURED
    got = RL.seating({"security": {"outcomes": {"fixed": bad}, "tokens": bad, "minutes": bad}})
    sec = got["seats"]["security"]
    assert sec["outcomes"]["fixed"] == UNMEASURED and sec["tokens"] == UNMEASURED and sec["minutes"] == UNMEASURED
    assert {"security.outcomes.fixed", "security.tokens", "security.minutes"} <= set(got["unmeasured"])


@pytest.mark.parametrize("good", [0, 0.0, 7, 2.5])
def test_seating_measured_keeps_a_real_number(good):
    assert RL._measured(good) == good and type(RL._measured(good)) is type(good)


# axis: the guarding test for the huge-integer branch of _measured — an integer past the float range never raises and never reads as a float
def test_seating_measured_a_huge_integer_never_raises():
    huge = 10 ** 400
    assert RL._measured(-huge) == UNMEASURED
    kept = RL._measured(huge)
    assert kept == huge and type(kept) is int
    got = RL.seating({"security": {"tokens": huge, "minutes": -huge}})
    sec = got["seats"]["security"]
    assert sec["tokens"] == huge and type(sec["tokens"]) is int and sec["minutes"] == UNMEASURED
    assert "security.minutes" in got["unmeasured"] and "security.tokens" not in got["unmeasured"]


@pytest.mark.parametrize("seat", ["lots", 5, None, [], {"outcomes": [1, 2], "tokens": 3}])
def test_seating_a_seat_that_is_not_a_usable_dict_reads_unmeasured_where_it_is_missing(seat):
    got = RL.seating({"security": seat})
    outcomes = got["seats"]["security"]["outcomes"]
    assert all(n == UNMEASURED for n in outcomes.values())
    assert got["seats"]["security"]["minutes"] == UNMEASURED
    assert got["seats"]["security"]["tokens"] == (3 if isinstance(seat, dict) else UNMEASURED)


@pytest.mark.parametrize("row", [None, [], "x", 5, True])
def test_seating_a_row_that_is_not_a_dict_is_refused(row):
    got = RL.seating(row)
    assert got["ok"] is False and got["outcome"] == "refused" and got["reason"] == "bad-input"
    assert got["seats"] is None and got["unmeasured"] is None


def test_cli_seating_round_trip_and_exit_codes(tmp_path, capsys):
    code, out = _cli(capsys, "seating", "--row", _json_file(tmp_path, "row.json", _seat_row()))
    assert code == 0 and out["ok"] is True and out["seats"]["security"] == SEAT_ROW and out["unmeasured"] == []
    code, out = _cli(capsys, "seating", "--row", _json_file(tmp_path, "part.json", {"security": {"tokens": 5}}))
    assert code == 0 and out["seats"]["security"]["tokens"] == 5 and "premortem.tokens" in out["unmeasured"]
    assert RL.main(["review_learning.py", "seating", "--row", _json_file(tmp_path, "again.json", _seat_row())]) == 0
    capsys.readouterr()
    code, out = _cli(capsys, "seating", "--row", str(tmp_path / "missing.json"))
    assert (code, out["ok"], out["reason"], out["seats"]) == (1, False, "bad-input", None)
    (tmp_path / "text.json").write_text("not json")
    code, out = _cli(capsys, "seating", "--row", str(tmp_path / "text.json"))
    assert (code, out["reason"]) == (1, "bad-input")
    code, out = _cli(capsys, "seating", "--row", _json_file(tmp_path, "list.json", []))
    assert (code, out["reason"]) == (1, "bad-input")


def test_cli_seating_a_huge_integer_is_echoed_or_read_unmeasured(tmp_path, capsys):
    huge = 10 ** 400
    row = _json_file(tmp_path, "huge.json", {"security": {"tokens": huge, "minutes": -huge}})
    code, out = _cli(capsys, "seating", "--row", row)
    assert code == 0 and out["ok"] is True
    assert out["seats"]["security"]["tokens"] == huge and out["seats"]["security"]["minutes"] == UNMEASURED


def test_cli_tally_carries_falsePrClaims(tmp_path, capsys):
    recs = _json_file(tmp_path, "r.json", _truth_table_records())
    escs = _json_file(tmp_path, "e.json", _escapes() + [_claim()])
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--since", D, "--until", "2026-10-11")
    assert code == 0 and out["falsePrClaims"] == 1 and out["escapes"] == {"missed": 1, "seenAndLeft": 1}
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", _json_file(tmp_path, "none.json", _escapes()), "--since", D,
                     "--until", "2026-10-11")
    assert code == 0 and out["falsePrClaims"] == 0


# --- the doctrine census ---

def _doctrine(name):
    with open(_DOCTRINE[name], encoding="utf-8") as fh:
        return " ".join(fh.read().split())


# axis: the guarding test for the misses-log census — every site that lists the classes names the false PR claim
@pytest.mark.parametrize("name, sites", [("owner-decisions", 1), ("vet-receipt", 2), ("glossary", 1)])
def test_every_misses_log_class_list_names_the_false_pr_claim(name, sites):
    text = _doctrine(name)
    starts = [i for i in range(len(text)) if text.startswith("declined-then-escaped", i)]
    assert len(starts) == sites, "a class list was added or removed: update this census"
    for i in starts:
        assert "false PR claim" in text[i:i + 260], (name, text[i:i + 260])


# axis: the guarding test for the closed duties list — the revisit checks sit after the memory-gardening lead-in, outside the eight duties
def test_owner_decisions_revisit_checks_sit_outside_the_closed_duties_list():
    text = _doctrine("owner-decisions")
    lead = "**The two revisit checks at the pass.**"
    assert text.count(lead) == 1
    after = text.index(lead)
    assert after > text.index("**Memory gardening at the pass.**")
    assert text.index("**The false-claim check.**") > after
    assert text.index("**The seating check.**") > after


def test_owner_decisions_spells_the_marker_line_and_the_tally_marker():
    text = _doctrine("owner-decisions")
    assert "false PR claim: <the claim> — shown false by <what showed it false>" in text
    assert '`"marker": "%s"`' % RL.FALSE_CLAIM_MARKER in text and RL.FALSE_CLAIM_MARKER == "false-pr-claim"
    assert "The false-claim check." in text and "The seating check." in text
    assert "falsePrClaims" in text and "seating --row" in text


# --- #2190: each escape names what would have caught it; two text proposal kinds ---

def _kind_escapes():
    return [{"pr": 2, "reviewedAt": D, "call": "missed", "kind": "focus-hint", "fix": "look for x"},
            {"pr": 2, "reviewedAt": D, "call": "missed", "kind": "focus-hint", "fix": "look for y"},
            {"pr": 3, "reviewedAt": D, "call": "seen-and-left", "kind": "risk-setting-or-leftover-rule", "fix": "z"},
            {"pr": 3, "reviewedAt": D, "call": "missed", "kind": "nothing-reachable"},
            {"pr": 4, "reviewedAt": D, "call": "missed"},  # logged before #2190: no kind
            {"pr": 4, "reviewedAt": D, "call": "missed", "kind": None}]


def test_tally_counts_escapes_by_kind_beside_the_seat_tally():
    got = RL.tally(_truth_table_records(), _kind_escapes(), D, until="2026-10-11")
    assert got["measured"] is True
    assert got["escapes"] == {"missed": 5, "seenAndLeft": 1}
    assert set(got["escapesByKind"]) == set(RL.ESCAPE_KINDS) | {RL.UNMEASURED} and len(RL.ESCAPE_KINDS) == 8
    assert {k: n for k, n in got["escapesByKind"].items() if n} == {
        "focus-hint": 2, "risk-setting-or-leftover-rule": 1, "nothing-reachable": 1, RL.UNMEASURED: 2}
    assert sum(got["escapesByKind"].values()) == sum(got["escapes"].values())
    assert got["seats"] == RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11")["seats"]  # the per-seat tally stays


# axis: the guarding test for a missing kind — it reads unmeasured, never as nothing reachable
def test_tally_an_escape_with_no_kind_reads_unmeasured_never_nothing_reachable():
    got = RL.tally([], [{"pr": 1, "reviewedAt": D, "call": "missed"}], D, until=D)
    assert got["escapesByKind"]["nothing-reachable"] == 0
    assert got["escapesByKind"][RL.UNMEASURED] == 1


@pytest.mark.parametrize("kind", ["unmeasured", "", "CLAUDE.md rule", 3, ["focus-hint"]])
def test_tally_an_unknown_kind_reads_malformed_and_unmeasured(kind):
    got = RL.tally([], [{"pr": 1, "reviewedAt": D, "call": "missed", "kind": kind}], D, until=D)
    assert (got["measured"], got["reason"]) == (False, "incomplete-evidence")
    assert got["escapesByKind"] is None and got["escapes"] == {"missed": None, "seenAndLeft": None}
    assert got["leftOut"]["malformed"] == 1


def test_tally_a_false_pr_claim_with_a_kind_is_not_an_escape_by_kind():
    claim = {"pr": 1, "reviewedAt": D, "call": "missed", "kind": "permanent-check", "marker": RL.FALSE_CLAIM_MARKER}
    got = RL.tally([], [claim], D, until=D)
    assert got["falsePrClaims"] == 1 and not any(got["escapesByKind"].values())


LAYER_BODY = "## Scope exclusions\n\n- vendor/\n\n## Focus hints\n\n- check the retry path\n\n## Conventions\n\n- none\n"
HINT = "Look for a cache read that skips the owner check."
CLAUDE_RULE = "Every new CLI verb gets a round-trip test through main()."


def _text_proposal(kind, text, **over):
    field = {"focus-hint": "hint", "claude-md-rule": "rule"}[kind]
    base = {"schema": "calibration-proposal/1", "kind": kind, field: text, "ruling": "Adopt this %s." % kind}
    base.update(over)
    return base


def _layer(proj_):
    repo, store = proj_
    return core_md.layer_path(repo, "review-crew", store)


def _with_layer(proj_):
    repo, store = proj_
    assert core_md.write_layer(repo, "review-crew", LAYER_BODY, "confirmed", root=store, now="2026-06-26")["action"] == "written"


def _claude_md(proj_):
    return os.path.join(proj_[0], "CLAUDE.md")


def _canon_lines(canon_):
    return [l for l in _git(canon_, "show", "HEAD:" + CANON_REL).splitlines() if l.startswith("- **")]


def test_focus_hint_joins_the_focus_hints_section_and_canon(proj, canon_root):
    _with_layer(proj)
    got = _apply(proj, canon_root, _text_proposal("focus-hint", HINT), APPROVAL)
    assert (got["ok"], got["outcome"], got["calibration"]) == (True, "applied", "focus-hint")
    assert got["set"] == {"action": "written", "path": _layer(proj)}
    assert _canon_lines(canon_root) == [got["canonEntry"]] and "Adopt this focus-hint." in got["canonEntry"]
    text = open(_layer(proj), encoding="utf-8").read()
    focus = text.split("## Focus hints", 1)[1].split("## Conventions", 1)[0]
    assert focus.strip().splitlines() == ["- check the retry path", "- " + HINT]
    assert "- vendor/" in text and "- none" in text
    again = _apply(proj, canon_root, _text_proposal("focus-hint", HINT), APPROVAL)
    assert again["set"]["action"] == "noop" and open(_layer(proj), encoding="utf-8").read() == text


def test_claude_md_rule_is_appended_once_and_left_uncommitted(proj, canon_root):
    with open(_claude_md(proj), "w", encoding="utf-8") as fh:
        fh.write("# CLAUDE.md\n\n- an existing rule\n")
    got = _apply(proj, canon_root, _text_proposal("claude-md-rule", CLAUDE_RULE), APPROVAL)
    assert (got["ok"], got["outcome"], got["calibration"]) == (True, "applied", "claude-md-rule")
    assert os.path.realpath(got["set"]["path"]) == os.path.realpath(_claude_md(proj))
    assert open(_claude_md(proj), encoding="utf-8").read() == "# CLAUDE.md\n\n- an existing rule\n\n%s\n" % CLAUDE_RULE
    assert got["canonEntry"] in _canon_lines(canon_root)
    assert "CLAUDE.md" in _git(proj[0], "status", "--porcelain")  # the advisor lands it; apply commits only Canon
    assert _apply(proj, canon_root, _text_proposal("claude-md-rule", CLAUDE_RULE), APPROVAL)["set"]["action"] == "noop"


# axis: the guarding test for a symlinked home — the rule is written through to the target and the link survives
def test_claude_md_rule_writes_through_a_symlinked_claude_md(proj, canon_root):
    shared = os.path.join(proj[0], "AGENTS.md")
    with open(shared, "w", encoding="utf-8") as fh:
        fh.write("# shared\n")
    os.symlink("AGENTS.md", _claude_md(proj))
    got = _apply(proj, canon_root, _text_proposal("claude-md-rule", CLAUDE_RULE), APPROVAL)
    assert (got["ok"], got["outcome"]) == (True, "applied")
    assert os.path.basename(got["set"]["path"]) == "CLAUDE.md"  # reported as given, not as the link's target
    assert os.path.islink(_claude_md(proj)) and os.readlink(_claude_md(proj)) == "AGENTS.md"
    assert open(shared, encoding="utf-8").read() == "# shared\n\n%s\n" % CLAUDE_RULE


# axis: the guarding test for the cloud guard — a symlinked layer in a cloud session is refused before anything is written
def test_focus_hint_through_a_symlinked_layer_is_refused_in_a_cloud_session(proj, canon_root, tmp_path, monkeypatch):
    _with_layer(proj)
    outside = str(tmp_path / "shared-hints.md")
    with open(outside, "w", encoding="utf-8") as fh:
        fh.write(open(_layer(proj), encoding="utf-8").read())
    os.remove(_layer(proj))
    os.symlink(outside, _layer(proj))
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    before = (_state(proj, canon_root), _bytes(outside))
    got = _apply(proj, canon_root, _text_proposal("focus-hint", HINT), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", RL.store_core.CLOUD_REFUSAL_REASON)
    assert (_state(proj, canon_root), _bytes(outside)) == before and os.path.islink(_layer(proj))


# axis: the guarding test for a missing home — a text kind with no file to join writes nothing, Canon included
@pytest.mark.parametrize("kind, text", [("focus-hint", HINT), ("claude-md-rule", CLAUDE_RULE)])
def test_text_kind_with_no_home_file_writes_nothing(proj, canon_root, kind, text):
    before = _state(proj, canon_root)
    got = _apply(proj, canon_root, _text_proposal(kind, text), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "refused", "target-missing")
    assert _state(proj, canon_root) == before
    assert not os.path.exists(_layer(proj)) and not os.path.exists(_claude_md(proj))


@pytest.mark.parametrize("kind", ["focus-hint", "claude-md-rule"])
def test_text_kind_needs_the_owners_yes(proj, canon_root, kind):
    _with_layer(proj)
    with open(_claude_md(proj), "w", encoding="utf-8") as fh:
        fh.write("# CLAUDE.md\n")
    before = (_state(proj, canon_root), _bytes(_layer(proj)), _bytes(_claude_md(proj)))
    got = _apply(proj, canon_root, _text_proposal(kind, HINT), dict(APPROVAL, answer="no"))
    assert (got["ok"], got["reason"]) == (False, "no-owner-yes")
    assert (_state(proj, canon_root), _bytes(_layer(proj)), _bytes(_claude_md(proj))) == before


# axis: the guarding test for the one-line shape — a hint or rule never adds a heading or a second line
@pytest.mark.parametrize("kind", ["focus-hint", "claude-md-rule"])
@pytest.mark.parametrize("text", ["", " ", "two\nlines", "cr\rline", " padded", "## A heading", None, 7])
def test_text_kind_line_must_be_one_plain_line(proj, canon_root, kind, text):
    _with_layer(proj)
    before = (_state(proj, canon_root), _bytes(_layer(proj)))
    got = _apply(proj, canon_root, _text_proposal(kind, text), APPROVAL)
    assert (got["ok"], got["reason"]) == (False, "proposal-invalid")
    assert (_state(proj, canon_root), _bytes(_layer(proj))) == before


@pytest.mark.parametrize("proposal", [
    _text_proposal("focus-hint", HINT, rule=CLAUDE_RULE),
    _text_proposal("claude-md-rule", CLAUDE_RULE, half="riskAreas"),
    {"schema": "calibration-proposal/1", "kind": "focus-hint", "rule": HINT, "ruling": "r"},
])
def test_text_kind_carries_exactly_its_keys(proj, canon_root, proposal):
    got = _apply(proj, canon_root, proposal, APPROVAL)
    assert (got["ok"], got["reason"]) == (False, "proposal-invalid")


def test_text_kind_write_failure_after_canon_reads_partial(proj, canon_root, monkeypatch):
    _with_layer(proj)
    def boom(path, text):
        raise OSError("disk full")
    monkeypatch.setattr(RL.store_core, "atomic_write", boom)
    got = _apply(proj, canon_root, _text_proposal("focus-hint", HINT), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "partial", "calibration-not-written")
    assert got["canonEntry"] in _canon_lines(canon_root) and "disk full" in got["detail"]


@pytest.mark.parametrize("layer, expected", [
    ("<!-- p -->\n\n## Focus hints\n## Conventions\n", "<!-- p -->\n\n## Focus hints\n\n- h\n\n## Conventions\n"),
    ("<!-- p -->\n", "<!-- p -->\n\n## Focus hints\n\n- h\n"),
    ("<!-- p -->\n\n## Focus hints\n\n- a\n", "<!-- p -->\n\n## Focus hints\n\n- a\n- h\n"),
])
def test_focus_hint_placement(layer, expected):
    assert RL._with_focus_hint(layer, "- h") == expected


def test_owner_decisions_states_the_kinds_and_six_questions_once():
    text = _doctrine("owner-decisions")
    for kind in RL.ESCAPE_KINDS:
        assert "`%s`" % kind in text, kind
    assert text.count("Could reading code see it, or only running it?") == 1
    q = [text.index(s) for s in ("Could reading code see it", "Was the line in the diff?", "Did a reviewer flag it and leave it?",
                                 "a rule a builder could follow up front", "about this project's domain", "Has the class escaped before?")]
    assert q == sorted(q)
    assert "escapesByKind" in text and "may produce a proposal without waiting" in text
