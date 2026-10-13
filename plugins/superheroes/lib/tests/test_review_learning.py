"""Tests for lib/review_learning.py (#1718, review C10): the adoption day, the owner-approved
calibration change, and the seat tally."""
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
def proj(tmp_path):
    """A project whose core.md holds one risk area, payments, covering src/payments/."""
    repo, store = str(tmp_path / "proj"), str(tmp_path / "store")
    os.makedirs(repo)
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


def test_failed_canon_commit_leaves_calibration_alone(proj, canon_root):
    hook = os.path.join(canon_root, ".git", "hooks", "pre-commit")
    with open(hook, "w") as fh:
        fh.write("#!/bin/sh\nexit 1\n")
    os.chmod(hook, 0o755)
    core_before = _state(proj, canon_root)[0]
    got = _apply(proj, canon_root, _proposal(), APPROVAL)
    assert (got["ok"], got["outcome"], got["reason"]) == (False, "canon-not-committed", "canon-commit-failed")
    assert _state(proj, canon_root)[0] == core_before and _touched(proj) == []


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
    core_md.write_project_config_item(repo, RL.SINCE_KEY, "garbage", root=store)
    assert RL.adoption_day(repo, store) == {"since": None, "reason": "malformed"}
    got = RL.record_adoption_day(repo, "2026-10-13", store)
    assert (got["outcome"], got["reason"], got["detail"]) == ("refused", "adoption-day-already-recorded", "garbage")


def test_the_extra_key_does_not_break_the_item_read_and_survives_a_set(proj):
    repo, store = proj
    RL.record_adoption_day(repo, "2026-10-13", store)
    assert len(project_config.view(repo, root=store)["items"]) == 14
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
    return {"pr": pr, "sessionId": session, "writtenAt": day + "T10:00:00Z", "reviewers": list(rows),
            "findings": list(findings)}


def _truth_table_records():
    return [
        _record(1, "s1", "2026-10-09", [_row("code-reviewer")], [_finding("k-old", "Code")]),
        _record(2, "s2", D, [_row("code-reviewer"), _row("confirm security", "reported-by-session"), _row("test-role", "not-run")],
                [_finding("k-new", "Code, Security"), _finding("k-none", ""), _finding("k-open", "Test", "left-for-owner")]),
        _record(1, "s1b", "2026-10-11", [_row("code-reviewer")], [_finding("k-old", "Code")]),
        _record(2, "s2b", "2026-10-11", [_row("code-reviewer")], [_finding("k-new", "Code, Security")]),
    ]


def _escapes():
    return [{"pr": 1, "reviewedAt": "2026-10-09", "call": "missed", "record": "r"},
            {"pr": 2, "reviewedAt": D, "call": "missed", "record": "r"},
            {"pr": 2, "reviewedAt": D, "call": "seen-and-left", "record": "r"}]


def test_tally_truth_table():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11")
    assert (got["measured"], got["reason"], got["since"]) == (True, None, D)
    assert got["window"] == {"from": D, "until": "2026-10-11"}
    # reviews: the D-1 record and the not-run test-role row never count; one catch each for a comma-joined finding
    assert got["seats"] == {"code-reviewer": {"reviews": 3, "caught": 1}, "security-reviewer": {"reviews": 1, "caught": 1}}
    assert got["unattributedCatches"] == 1
    assert got["escapes"] == {"missed": 1, "seenAndLeft": 1}
    assert got["leftOut"] == {"beforeWindow": 2, "afterWindow": 0, "undated": 0, "malformed": 0}


# axis: the guarding test for the before-adoption exclusion — an event dated before the adoption day never counts
def test_tally_nothing_before_the_adoption_day_counts():
    records = [_record(1, "s1", "2026-10-09", [_row("code-reviewer")], [_finding("k-old", "Code")])]
    escapes = [{"pr": 1, "reviewedAt": "2026-10-09", "call": "missed", "record": "r"}]
    got = RL.tally(records, escapes, D, until="2026-10-11")
    assert got["seats"] == {} and got["unattributedCatches"] == 0
    assert got["escapes"] == {"missed": 0, "seenAndLeft": 0}
    assert got["leftOut"]["beforeWindow"] == 2


def test_tally_a_catch_first_recorded_before_adoption_never_counts_when_carried():
    got = RL.tally(_truth_table_records()[::2], [], D, until="2026-10-11")
    assert got["seats"] == {"code-reviewer": {"reviews": 1, "caught": 0}}


def test_tally_a_catch_counts_once_when_carried_forward():
    got = RL.tally(_truth_table_records()[1::2], [], D, until="2026-10-11")
    assert got["seats"]["code-reviewer"]["caught"] == 1 and got["seats"]["security-reviewer"]["caught"] == 1


def test_tally_finding_without_a_key_falls_back_to_its_id():
    f = _finding(None, "Code", fid="F-1")
    got = RL.tally([_record(1, "a", D, [], [f]), _record(1, "b", "2026-10-11", [], [f])], [], D, until="2026-10-11")
    assert got["seats"]["code-reviewer"]["caught"] == 1


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
    assert got["seats"]["code-reviewer"] == {"reviews": 3, "caught": 1}
    assert got["leftOut"]["beforeWindow"] == 2


def test_tally_window_inside_the_adoption_period_is_measured_and_excludes_earlier_days():
    got = RL.tally(_truth_table_records(), _escapes(), D, until="2026-10-11", window_days=1)
    assert (got["measured"], got["window"]["from"]) == (True, "2026-10-11")
    assert got["seats"]["code-reviewer"] == {"reviews": 2, "caught": 0}
    assert got["seats"].keys() == {"code-reviewer"}
    assert got["leftOut"]["beforeWindow"] == 5  # the D-1 and D records, and the three escapes dated D-1 and D


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
    got = RL.tally([], [], D)
    assert got["window"]["until"] and got["measured"] is True


@pytest.mark.parametrize("name, seats", [
    ("Code", ["code-reviewer"]), ("code-reviewer", ["code-reviewer"]), ("Test", ["test-role"]),
    ("architecture", ["architecture-reviewer"]), ("Security (round 2)", ["security-reviewer"]),
    ("failure-mode", ["premortem-reviewer"]), ("confirm security", ["security-reviewer"]),
    ("Audit Code (round 3)", ["code-reviewer"]), ("Code, Security", ["code-reviewer", "security-reviewer"]),
    ("Code, code-reviewer", ["code-reviewer"]), ("Fresh Eyes", ["fresh eyes"]), ("custom-seat", ["custom-seat"]),
    ("", []), (None, []), ("confirm", ["confirm"]),
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
    refusal = {"ok": False, "reason": "review-record-unreadable"}
    no_findings = {"pr": 1, "sessionId": "x", "writtenAt": "2026-10-05T00:00:00Z", "reviewers": [_row("code-reviewer")]}
    for records, escapes in (([refusal], []), ([no_findings], []), (["junk"], []),
                             ([{"pr": 1, "reviewers": [], "findings": []}], []),
                             ([], [{"call": "missed"}]), ([], ["junk"]),
                             ([], [{"reviewedAt": "2026-10-05", "call": "other"}])):
        got = RL.tally(records, escapes, D, until="2026-10-11")
        assert got["measured"] is False and got["reason"] == "incomplete-evidence", (records, escapes)
        assert got["unattributedCatches"] is None and got["escapes"] == {"missed": None, "seenAndLeft": None}
        assert got["seats"] == {}


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


def test_cli_tally(proj, tmp_path, capsys):
    repo, store = proj
    recs, escs = _json_file(tmp_path, "r.json", _truth_table_records()), _json_file(tmp_path, "e.json", _escapes())
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--since", D, "--until", "2026-10-11")
    assert code == 0 and out["measured"] is True and out["seats"]["code-reviewer"]["reviews"] == 3
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--cwd", repo, "--root", store, "--until", "2026-10-11")
    assert (code, out["measured"], out["reason"]) == (0, False, "no-adoption-day")
    RL.record_adoption_day(repo, D, store)
    code, out = _cli(capsys, "tally", "--records", recs, "--escapes", escs, "--cwd", repo, "--root", store,
                     "--until", "2026-10-11", "--window-days", "5")
    assert (code, out["reason"], out["since"]) == (0, "short-of-window", D)
    code, out = _cli(capsys, "tally", "--records", str(tmp_path / "missing"), "--escapes", escs, "--since", D)
    assert (code, out["reason"]) == (1, "bad-input")
