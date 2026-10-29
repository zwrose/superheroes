import copy
import json
import os
import shutil
import subprocess
import sys

import pytest

import canon
import circuit_breaker
import decision_kinds
import model_registry
import receipt_disclosures
import record_paths
import review_record as rr
import review_record_session as rs
import round_driver

HEAD = "b" * 40  # the PR's head in the default Fake, and the final commit of the built sessions
EARLIER = "a" * 40
THIRD = "c" * 40
CODEX = model_registry.codex_models()[0]
NO_STATUS = {"state": "pending", "total_count": 0, "statuses": []}
GREEN = ({"total_count": 1, "check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]},
         NO_STATUS,
         {"workflow_runs": [{"id": 11, "name": "CI", "event": "push", "status": "completed", "conclusion": "success"}]})
GOOD_RUN = {"source": "codex", "engineModel": CODEX, "viewHeadSha": HEAD,
            "observation": {"tokens": 100, "wallSeconds": 120}, "graded": True, "runKind": "review"}
KEY = "a.py::t@L3"
WRONG = {"verdict": "wrong", "reason": "the verifier showed the cited line does not exist"}  # the grade the driver's verifier fold writes
STANDING = "2026-01-02-abcd1234-1"
CANON_SOURCES = {"canonText": canon.entry_line(STANDING, "2026-01-02", "standing", "a ruling",
                                               'owner\'s words: "go"', "issue thread")}


class Fake:
    """Injectable readers with an in-memory comment list; records create calls."""

    def __init__(self, head=HEAD, runs=None, sources=None):
        self.comments, self.writes = [], []
        self.head, self.runs, self.sources = head, runs or {}, sources or {}

    def readers(self):
        return {
            "pr_meta": lambda pr, repo: {"head": self.head, "body": "", "issues": []},
            "issue_body": lambda n, repo: None,
            "check_data": lambda sha, repo: GREEN,
            "ci_workflow": lambda root: ("absent", None),
            "lane_marker": lambda root: None,
            "engine_run": lambda d: self.runs.get(d, (copy.deepcopy(GOOD_RUN), None)),
            "repo_name": lambda root: "o/r",
            "list_comments": lambda pr, repo: list(self.comments),
            "create_comment": self._create,
            "changed_paths": lambda pr, repo: ["README.md"],
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


class Session:
    """A session directory built by hand: loop-state.json, meta.json, the journal and the stored envelopes."""

    def __init__(self, root, **state):
        self.dir = str(root / "session")
        os.makedirs(self.dir)
        self.state = {"terminal": "converged", "round": 1, "config": {"maxRounds": 7}, "rounds": {"1": {}},
                      "findings": [], "dispositionLedger": [], "decisions": [], "seatMapReceipts": [], **state}
        self.meta = {"sessionId": "s-1", "headSha": EARLIER, "fixFoldHeadSha": HEAD}
        self.rows = []

    def seat(self, seat, phase="dispatch-panel", rnd=1, cmd="record-result", attempt=0, head=EARLIER, nonce=None,
             occurrence=0, envelope=True):
        self.rows.append({"outcome": "recorded", "cmd": cmd, "phase": phase, "round": rnd, "seat": seat,
                          "attempt": attempt, "occurrence": occurrence, "citedHead": head,
                          "citedHeadSource": "order-anchor",
                          "executionEvidence": {"runnerNonce": nonce} if nonce else None})
        if envelope:
            path = record_paths.store_path(self.dir, rnd, phase, record_paths.storage_key(seat, occurrence), attempt)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"vendor": "codex", "model": CODEX, "payload": {"findings": []}}, fh)
        return self

    def save(self):
        for name, body in (("loop-state.json", self.state), ("meta.json", self.meta)):
            with open(os.path.join(self.dir, name), "w", encoding="utf-8") as fh:
                json.dump(body, fh)
        if self.rows:
            with open(os.path.join(self.dir, "driver-journal.jsonl"), "w", encoding="utf-8") as fh:
                fh.write("".join(json.dumps(r) + "\n" for r in self.rows))
        return self.dir


def ledger_row(key=KEY, **over):
    return {"findingKey": key, "id": "f-1", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
            "detail": "d", "dimension": "code-reviewer", "raisedRound": 1, "raisedSeq": 1, "disposition": "fixed",
            "dispositionRound": 2, "dispositionSeq": 4, **over}


def extras(**over):
    return {"schema": rs.EXTRAS_SCHEMA, "pr": 7, **over}


def put_extras(tmp_path, body):
    path = tmp_path / "extras.json"
    path.write_text(json.dumps(body))
    return str(path)


def send(tmp_path, session, fake, **over):
    out = rs.write_from_session(session, put_extras(tmp_path, extras(**over)), str(tmp_path), fake.readers())
    return out


def fix_session(tmp_path, nonces=True):
    """Specialists on an earlier commit, a fix audit on the final commit, the one finding fixed."""
    s = Session(tmp_path, dispositionLedger=[ledger_row()], config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": [{"title": "t", "file": "a.py"}]}}},
                seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}])
    s.seat("code-reviewer", nonce="n1" if nonces else None)
    s.seat("security-reviewer", nonce="n2" if nonces else None)
    s.seat(KEY, phase="dispatch-audits", rnd=2, head=HEAD, nonce="n3" if nonces else None)
    runs = {f"/run/{n}": (dict(GOOD_RUN, runnerNonce=n, viewHeadSha=head), None)
            for n, head in (("n1", EARLIER), ("n2", EARLIER), ("n3", HEAD))}
    return s.save(), runs, {"runDirs": sorted(runs)}


def test_a_real_driven_session_with_a_fix_round_writes_one_record(tmp_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import test_round_driver_integration as drive
    session, gitdir, head_path = drive._bootstrap(tmp_path)
    drive._drive_to_terminal(session, gitdir, [drive._blocking_finding("missing bounds guard", 2)], head_path)
    fake = Fake()
    out = send(tmp_path, session, fake)
    assert out["ok"], out
    # bites on: the adapter writing nothing, or more than one record, for a session the real driver produced
    assert len(fake.marked()) == 1
    rec = rr.read(7, readers=fake.readers())
    assert {"lane", "reviewers", "findings", "finalCommit", "ci", "leftForOwner", "rounds", "missingReviews", "cost",
            "makers"} <= set(rec)
    assert rec["lane"]["value"] == "full" and {"count", "cap", "stoppedAtCap"} <= set(rec["rounds"])
    assert rec["reviewers"] and all("family" in v for v in rec["reviewers"])
    assert all({"consequence", "outcome", "reason"} <= set(f) for f in rec["findings"])
    fixed = [f for f in rec["findings"] if f["title"] == "missing bounds guard"]
    assert [f["outcome"] for f in fixed] == ["fixed"]


def test_a_fix_round_session_reads_reviewed(tmp_path):
    session, runs, body = fix_session(tmp_path)
    fake = Fake(runs=runs)
    out = send(tmp_path, session, fake, ci="green", **body)
    # bites on: a reviewed fix round reading otherwise (a dir not bound, a finding undecided, a commit not carried)
    assert out["ok"] and out["status"] == "reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert [v["ran"] for v in rec["reviewers"]] == ["engine-record"] * 3
    assert [v["commit"] for v in rec["reviewers"]] == [EARLIER, EARLIER, HEAD]


def test_the_same_session_with_the_head_moved_reads_not_reviewed(tmp_path):
    session, runs, body = fix_session(tmp_path)
    fake = Fake(head=THIRD, runs=runs)
    out = send(tmp_path, session, fake, ci="green", **body)
    # bites on: a review that covered an earlier commit counting for a head that moved after it
    assert out["ok"] and out["status"] == "not-reviewed", out
    assert any("covers the final commit" in line for line in out["whatIsMissing"])


@pytest.mark.parametrize("go_ahead", [
    None,
    {"kind": "standing-ruling", "canonId": STANDING},
    {"kind": "owner-words", "words": "go on without it", "where": "the issue thread"},
])
def test_a_specialist_that_did_not_run_parks_unless_the_owner_went_ahead(tmp_path, go_ahead):
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer", cmd="record-missing")
    fake = Fake(sources=CANON_SOURCES)
    gone = "security-reviewer (round 1)"
    out = send(tmp_path, s.save(), fake, goAheads=[dict(go_ahead, reviewer=gone)] if go_ahead else [])
    # bites on: a seat that never reported being left out of the record, or a go-ahead lifting the parking wrongly
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert [m["name"] for m in rec["missingReviews"]] == [gone]
    assert out["parked"] is (go_ahead is None)
    assert (rec["missingReviews"][0]["goAhead"] or {}).get("kind") == (go_ahead or {}).get("kind")


def test_a_standing_ruling_go_ahead_whose_canon_entry_is_not_on_record_leaves_the_pr_parked(tmp_path):
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer", cmd="record-missing")
    fake = Fake()
    gone = "security-reviewer (round 1)"
    out = send(tmp_path, s.save(), fake, goAheads=[{"kind": "standing-ruling", "canonId": STANDING, "reviewer": gone}])
    # bites on: a standing-ruling go-ahead lifting the parking with no Canon entry on record behind it
    assert out["ok"] and out["status"] == "not-reviewed", out
    assert out["parked"] is True
    assert not rr.read(7, readers=fake.readers())["missingReviews"][0]["goAhead"]


def test_a_record_written_through_this_files_fake_never_reaches_the_real_changed_paths_reader(tmp_path, monkeypatch):
    def boom(pr, repo):
        raise AssertionError("the real changed_paths reader (gh api) was reached")
    monkeypatch.setattr(rr, "changed_paths", boom)
    fake = Fake()
    out = send(tmp_path, Session(tmp_path).seat("code-reviewer").save(), fake)
    # bites on: a record written through the Fake reading the PR's changed files from GitHub
    assert out["ok"], out
    assert rr.read(7, readers=fake.readers())["laneBasis"]["source"] == "lane rule over the PR's changed files"


def test_a_missing_slot_recovered_by_a_later_round_is_not_a_missing_review(tmp_path):
    s = Session(tmp_path, rounds={"1": {}, "2": {}})
    s.seat("code-reviewer").seat("security-reviewer", cmd="record-missing").seat("security-reviewer", rnd=2)
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    # bites on: a seat missed in one round and run in a later one still reading as a missing review
    assert [(v["name"], v["ran"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", True), ("security-reviewer (round 2)", True)]


def test_the_fixers_family_joins_the_makers_and_the_session_marks_no_reviewer_independent_or_not(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}},
                "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}]}
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": []}}}, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer").seat("security-reviewer")
    fam = receipt_disclosures.author_family(s.state)
    assert fam
    session = s.save()
    account = rs.account_from_session(session, extras(makers=[{"family": "other", "source": "the extras"}]))
    # bites on: the fixer's family missing from the makers, or the session marking independence (the record writer decides it)
    assert account["makers"] == [{"family": "other", "source": "the extras"}, {"family": fam, "source": "review loop fixer", "fromStep": 3}]
    marks = {v["name"]: v.get("notIndependent") for v in account["reviewers"]}
    assert marks == {"code-reviewer (round 1)": None, "security-reviewer (round 1)": None}
    listed = rs.account_from_session(session, extras(makers=[{"family": fam, "source": "the extras"}]))
    assert listed["makers"] == [{"family": fam, "source": "the extras"}]
    fake = Fake()
    assert send(tmp_path, session, fake)["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert "code-reviewer (round 1)" in {v["name"] for v in rec["reviewers"]}


UNFILLED_SEAT = {"vendor": None, "model": None, "effort": None, "tier": "deep", "family": None, "source": "unfilled"}


def test_an_unfilled_seat_is_listed_as_planned_and_not_run_even_with_no_slot_journaled(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX},
                          "security-reviewer": dict(UNFILLED_SEAT)}}
    s = Session(tmp_path, rounds={"1": {}, "2": {"seatStatus": {}}},
                seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    # bites on: an unfilled seat vanishing from the account, or reading as a reviewer that ran
    rows = {v["name"]: v for v in account["reviewers"]}
    assert set(rows) == {"code-reviewer (round 1)", "security-reviewer (round 1)", "security-reviewer (round 2)"}
    for name in ("security-reviewer (round 1)", "security-reviewer (round 2)"):
        assert rows[name] == {"name": name, "planned": True, "ran": False, "vendor": "unfilled",
                              "model": "unfilled", "commit": None, "runDir": None}
    assert rows["code-reviewer (round 1)"]["ran"] is True


def test_an_unfilled_retired_seat_in_an_older_map_is_no_reviewer_row_and_does_not_park(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX},
                          "grounding-seat": dict(UNFILLED_SEAT)}}
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    # bites on: a seat the map names but no panel round schedules turning into a reviewer row, or parking a complete review
    assert {v["name"] for v in account["reviewers"]} == {"code-reviewer (round 1)"}
    assert not any("notRunReason" in v for v in account["reviewers"])
    assert send(tmp_path, s.dir, Fake())["parked"] is False


def test_an_unfilled_seat_the_driver_journaled_as_missing_is_still_listed_once_as_unfilled(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX},
                          "security-reviewer": dict(UNFILLED_SEAT)}}
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer").seat("security-reviewer", cmd="advance")
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    rows = [v for v in account["reviewers"] if v["name"] == "security-reviewer (round 1)"]
    assert len(rows) == 1 and rows[0]["ran"] is False and rows[0]["vendor"] == "unfilled"
    fake = Fake()
    assert send(tmp_path, s.dir, fake)["ok"]


def test_the_maps_maker_families_join_the_makers_once(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}},
                "makerFamilies": ["anthropic", "openai"]}
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer")
    account = rs.account_from_session(
        s.save(), extras(makers=[{"family": "openai", "source": "the extras"}]), Fake().readers())
    # bites on: the map's maker list not reaching the account, or a family already listed being repeated
    assert account["makers"] == [{"family": "openai", "source": "the extras"},
                                 {"family": "anthropic", "source": "seat map maker list"}]


def test_a_later_map_omitting_an_earlier_maker_family_does_not_release_it(tmp_path):
    first = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}}, "makerFamilies": ["anthropic", "openai"]}
    later = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}}, "makerFamilies": ["anthropic"]}
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": first}, {"round": "2", "map": later}])
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    # bites on: the final record dropping a maker family an earlier receipt named
    assert {m["family"] for m in account["makers"]} == {"anthropic", "openai"}


def test_later_map_omitting_an_earlier_maker_does_not_make_that_maker_the_independent_auditor():
    seat = {"code-reviewer": {"vendor": "cursor", "source": "rotated"}}
    state = round_driver.new_state({"vendors": ["claude", "codex", "cursor"], "fixerVendor": "claude"})
    state["seatMapReceipts"] = [
        {"round": "1", "map": {"seats": seat, "makerFamilies": ["anthropic", "openai"]}},
        {"round": "2", "map": {"seats": seat, "makerFamilies": ["anthropic"]}}]
    state["fixBatch"] = [{"file": "f.py", "line": 1, "title": "bug", "severity": "Important"}]
    targets = round_driver._audit_targets(state, state["config"], {})
    # bites on: audit selection reading only the latest map, seating the earlier maker (codex, openai) as independent
    assert targets[0]["auditorVendor"] == "cursor"
    assert receipt_disclosures.accumulated_maker_families(state) == frozenset({"anthropic", "openai"})


def _fixer_then_reviewer_account(tmp_path, review_round, original_makers=None):
    claude = {"vendor": "claude", "model": "sonnet-5.5"}
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": []}}, "2": {}} if review_round == 2 else {"1": {"fix": {"fixes": []}}},
                seatMapReceipts=[{"round": str(review_round), "map": {"seats": {"code-reviewer": claude},
                                                                                   **({"makerFamilies": original_makers} if original_makers else {})}}])
    s.seat("code-reviewer", rnd=review_round, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, source="claude", engineModel="sonnet-5.5", runnerNonce="n1",
                             viewHeadSha=EARLIER), None)}
    account = rs.account_from_session(s.save(), extras(runDirs=["/run/n1"]), Fake(runs=runs).readers())
    account["reviewers"][0].update(claude)  # the stored envelope names codex; this reviewer is the fixer's family
    account["reviewers"].append({"name": "audit (round 1)", "vendor": "codex", "model": CODEX, "planned": True,
                                 "ran": True, "runDir": "/run/n3", "commit": None, "step": 3})
    runs["/run/n3"] = (dict(GOOD_RUN, runnerNonce="n3", viewHeadSha=HEAD), None)
    return account, Fake(runs=runs)


def test_a_reviewer_before_the_fix_is_judged_against_the_makers_it_faced(tmp_path):
    account, fake = _fixer_then_reviewer_account(tmp_path, 1, original_makers=["xai"])
    fixer = next(m for m in account["makers"] if m["source"] == "review loop fixer")
    assert fixer["fromStep"] == 3 and account["reviewers"][0]["step"] == 2
    rec = rr.build_record(account, fake.readers())
    # bites on: a reviewer credited to an earlier commit demoted because its family later made a fix
    by_name = {v["name"]: v for v in rec["reviewers"]}
    assert by_name["code-reviewer (round 1)"]["ran"] == "engine-record"
    assert by_name["audit (round 1)"]["ran"] == "engine-record" and by_name["audit (round 1)"]["coversFinalCommit"]
    assert rec["missingReviews"] == [] and rec["status"] == "reviewed"


def test_an_original_maker_that_also_fixes_keeps_its_whole_review_maker_status(tmp_path):
    account, fake = _fixer_then_reviewer_account(tmp_path, 1, original_makers=["anthropic"])
    anthropic = [m for m in account["makers"] if m["family"] == "anthropic"]
    # bites on: the fixer's delayed fromStep shadowing the seat map's baseline entry for the same family
    assert anthropic == [{"family": "anthropic", "source": "seat map maker list"}]
    rec = rr.build_record(account, fake.readers())
    by_name = {v["name"]: v for v in rec["reviewers"]}
    assert by_name["code-reviewer (round 1)"]["ran"] == "not-run"
    assert rec["status"] != "reviewed"


def test_a_fixer_family_first_named_after_the_first_fix_keeps_its_delayed_start(tmp_path):
    claude = {"vendor": "claude", "model": "sonnet-5.5"}
    first = {"seats": {"code-reviewer": claude}, "makerFamilies": ["openai"]}
    later = {"seats": {"code-reviewer": claude}, "makerFamilies": ["openai", "anthropic"]}
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": []}}, "2": {}},
                seatMapReceipts=[{"round": "1", "map": first}, {"round": "2", "map": later}])
    s.seat("code-reviewer", rnd=1, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, source="claude", engineModel="sonnet-5.5", runnerNonce="n1",
                             viewHeadSha=EARLIER), None)}
    account = rs.account_from_session(s.save(), extras(runDirs=["/run/n1"]), Fake(runs=runs).readers())
    # bites on: the cumulative union standing in for the original makers, dropping the fixer's fromStep entry
    assert {"family": "anthropic", "source": "review loop fixer", "fromStep": 3} in account["makers"]
    assert not any(m["family"] == "anthropic" and "fromStep" not in m for m in account["makers"])
    assert {m["family"] for m in account["makers"]} == {"openai", "anthropic"}


def test_a_reviewer_after_the_fix_from_the_fixers_family_is_still_not_independent(tmp_path):
    account, fake = _fixer_then_reviewer_account(tmp_path, 2)
    assert account["reviewers"][0]["step"] == 4
    rec = rr.build_record(account, fake.readers())
    # bites on: the temporal rule releasing a reviewer that read the fixer's own change
    by_name = {v["name"]: v for v in rec["reviewers"]}
    assert by_name["code-reviewer (round 2)"]["ran"] == "not-run"


def test_an_unfilled_seat_a_later_round_filled_is_recovered_not_left_missing(tmp_path):
    unfilled = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}, "security-reviewer": dict(UNFILLED_SEAT)}}
    filled = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX},
                        "security-reviewer": {"vendor": "codex", "model": CODEX}}}
    s = Session(tmp_path, rounds={"1": {}, "2": {}},
                seatMapReceipts=[{"round": "1", "map": unfilled}, {"round": "2", "map": filled}])
    s.seat("code-reviewer").seat("security-reviewer", rnd=2)
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    names = {v["name"] for v in account["reviewers"]}
    # bites on: a round-1 unfilled row surviving a round-2 run of the same seat and keeping the record parked
    assert "security-reviewer (round 2)" in names and "security-reviewer (round 1)" not in names


def test_an_old_map_without_maker_families_or_source_changes_nothing(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}}}
    s = Session(tmp_path, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    assert account["makers"] == []
    assert [v["name"] for v in account["reviewers"]] == ["code-reviewer (round 1)"]


def _merged(member_over, rep_over):
    return [ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY, **member_over),
            ledger_row(KEY, id="rep-1", **rep_over)]


OOS = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
RULED = {"findingKey": KEY, "ruling": "out-of-scope", "provenance": {"ruledBy": "the owner", "ruledAt": "2030-01-02"}}
CASES = [
    pytest.param([ledger_row()], [], KEY, "fixed", "fixed and audited in round 2", id="fresh-fixed"),
    pytest.param([ledger_row(disposition="refuted", refutedReason="the cited line does not exist", grade=WRONG)], [], KEY,
                 "shown-wrong", "the cited line does not exist", id="verifier-refuted"),
    pytest.param([ledger_row(disposition="refuted", refutedReason="author-justified: kept on purpose")], [], KEY,
                 "left-for-owner", "author-justified: kept on purpose", id="author-justified"),
    pytest.param([ledger_row(**OOS)], [RULED], KEY, "ruling",
                 "belongs to the follow-up (ruled by the owner, 2030-01-02)", id="attributed-out-of-scope"),
    pytest.param([ledger_row(**OOS)], [], KEY, "left-for-owner", "belongs to the follow-up",
                 id="unattributed-out-of-scope"),
    pytest.param([ledger_row(disposition=None)], [], KEY, None, rs.STILL_OPEN, id="no-disposition"),
    pytest.param([ledger_row(dispositionSeq=1)], [], KEY, None, rs.STILL_OPEN, id="stale"),
    pytest.param(_merged({}, {}), [], "m::t@L1", "fixed", "fixed and audited in round 2 (merged into rep-1)",
                 id="merged-member"),
    pytest.param(_merged({"raisedSeq": 9}, {}), [], "m::t@L1", None, rs.STILL_OPEN + " (merged into rep-1)",
                 id="merged-member-raised-after-the-disposition"),
]


@pytest.mark.parametrize("ledger,rulings,key,outcome,reason", CASES)
def test_dispositions_map_to_outcomes(tmp_path, ledger, rulings, key, outcome, reason):
    s = Session(tmp_path, dispositionLedger=ledger, rulingsLog=rulings)
    s.seat("code-reviewer")
    found = {f["findingKey"]: f for f in rs.account_from_session(s.save(), extras())["findings"]}[key]
    # bites on: a disposition counting when it is stale, an author-justified drop or an unattributed
    # out-of-scope reading as decided by someone else, a merged member losing its representative
    assert (found["outcome"], found["reason"]) == (outcome, reason)


def _applied(source="owner-supplied", prov=True, target=KEY, phase="present-judgment"):
    action = {"dispositions": [{"id": target, "disposition": "skip", "reason": "later"}]}
    if prov:
        action["_provenance"] = {"ruledBy": "the owner", "ruledAt": "2030-01-02"}
    return [{"phase": phase, "source": source, "layers": [], "matches": [], "action": action}]


@pytest.mark.parametrize("applied,outcome", [
    pytest.param(_applied(), "ruling", id="attributed-judgment-skip"),
    pytest.param(_applied(prov=False), "left-for-owner", id="no-provenance"),
    pytest.param(_applied(source="gate-policy"), "left-for-owner", id="gate-policy"),
    pytest.param(_applied(target="other.py::x@L9"), "left-for-owner", id="another-finding"),
])
def test_an_attributed_gate_skip_settles_its_own_finding_only(tmp_path, applied, outcome):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**OOS)], _policyApplied=applied)
    found = rs.account_from_session(s.seat("code-reviewer").save(), extras())["findings"][0]
    # bites on: an owner-supplied gate decision ignored, or one read as settling a finding it does not name
    assert found["outcome"] == outcome
    if outcome == "ruling":
        assert found["reason"] == "belongs to the follow-up (ruled by the owner, 2030-01-02)"


def test_findings_from_a_missing_seat_are_kept_whether_or_not_a_later_round_recovered_it(tmp_path):
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer").seat("security-reviewer", rnd=2)
    session = s.save()
    put_envelope(session, "security-reviewer", {"payload": {"findings": [{"title": "lost"}], "receiptMissing": True}})
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    account = rs.account_from_session(session, extras(), Fake().readers(), str(raw_dir))
    # bites on: a seat classified missing dropping the findings it did hand back
    assert len(account["rawFindingsFiles"]) == 3
    assert [r["name"] for r in account["reviewers"]].count("security-reviewer (round 1)") == 0


def test_a_run_directory_binds_only_by_the_runner_nonce(tmp_path):
    s = Session(tmp_path).seat("code-reviewer", nonce="nonce-a").seat("security-reviewer", nonce="nonce-b")
    records = {"/run/other": ({"runnerNonce": "nonce-z"}, None), "/run/bad": (None, "engine-unavailable"),
               "/run/b": ({"runnerNonce": "nonce-b"}, None)}
    readers = {"engine_run": lambda d: records[d]}
    body = extras(runDirs=["/run/other", "/run/bad", "/run/b"])
    account = rs.account_from_session(s.save(), body, readers)
    # bites on: a directory bound by position or by name rather than by the nonce its engine record carries
    assert [(v["name"], v["runDir"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", None), ("security-reviewer (round 1)", "/run/b")]
    (tmp_path / "twin").mkdir()
    twin = Session(tmp_path / "twin")
    twin.seat("code-reviewer", nonce="same").seat("security-reviewer", nonce="same")
    same = {"engine_run": lambda d: ({"runnerNonce": "same"}, None)}
    shared = rs.account_from_session(twin.save(), extras(runDirs=["/run/s"]), same)
    assert [v["runDir"] for v in shared["reviewers"]] == [None, None]


def test_two_attempts_of_one_slot_keep_the_highest(tmp_path):
    s = Session(tmp_path)
    s.seat("code-reviewer", attempt=0)
    s.seat("code-reviewer", attempt=1, head=HEAD)
    s.seat("test-role", attempt=0).seat("test-role", attempt=1, head=HEAD)
    s.rows.append({"outcome": "recorded", "cmd": "record-result", "phase": "dispatch-panel", "round": 1, "seat": 5})
    s.rows.append({"outcome": "recorded", "cmd": "record-result", "phase": None, "round": 1, "seat": "x"})
    account = rs.account_from_session(s.save(), extras())
    # bites on: the lower attempt of a slot winning over the higher one, or two attempts of one slot counting twice
    assert [(v["name"], v["commit"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", HEAD), ("test-role (round 1)", HEAD)]


@pytest.mark.parametrize("missing", [None, "", 5])
def test_an_archived_candidate_without_a_usable_id_is_listed_by_its_key(tmp_path, missing):
    s = Session(tmp_path, dispositionLedger=[ledger_row(id=missing)]).seat("code-reviewer")
    account = rs.account_from_session(s.save(), extras())
    # bites on: a null or unusable stored id reaching the account, which the writer refuses as a whole
    assert [f["id"] for f in account["findings"]] == [KEY]


def _unreadable_dir(s, t):
    shutil.rmtree(s.save())
    return s.dir, extras()


def _without(name):
    def case(s, t):
        os.remove(os.path.join(s.save(), name))
        return s.dir, extras()
    return case


def _overwrite(name, text):
    def case(s, t):
        with open(os.path.join(s.save(), name), "w", encoding="utf-8") as fh:
            fh.write(text)
        return s.dir, extras()
    return case


def _state_change(**over):
    def case(s, t):
        s.state.update(over)
        return s.save(), extras()
    return case


def _no_session_id(s, t):
    s.meta.pop("sessionId")
    return s.save(), extras()


def _extras_are(body):
    return lambda s, t: (s.save(), body)


REFUSALS = [
    pytest.param(_unreadable_dir, rs.UNREADABLE, id="no-session-dir"),
    pytest.param(_without("loop-state.json"), rs.UNREADABLE, id="no-state"),
    pytest.param(_overwrite("loop-state.json", "[]"), rs.UNREADABLE, id="state-not-an-object"),
    pytest.param(_state_change(terminal=None), rs.NOT_TERMINAL, id="not-terminal"),
    pytest.param(_overwrite("driver-journal.jsonl", "{not json\n"), rs.UNREADABLE, id="journal-line-unparseable"),
    pytest.param(_overwrite("driver-journal-fault.jsonl", "{}\n"), rs.UNREADABLE, id="journal-fault"),
    pytest.param(_state_change(dispositionLedger="x"), rs.UNREADABLE, id="ledger-malformed"),
    pytest.param(lambda s, t: (s.state.pop("dispositionLedger"), s.state.update(dispositionLedgerOwner="ledger"),
                               (s.save(), extras()))[2], rs.UNREADABLE, id="owned-ledger-absent"),
    pytest.param(_extras_are(None), rs.BAD_EXTRAS, id="no-extras"),
    pytest.param(_extras_are(b"{not json"), rs.BAD_EXTRAS, id="extras-unparseable"),
    pytest.param(_extras_are({"schema": "nope", "pr": 7}), rs.BAD_EXTRAS, id="extras-schema"),
    pytest.param(_extras_are({"schema": rs.EXTRAS_SCHEMA, "pr": 0}), rs.BAD_EXTRAS, id="extras-pr-zero"),
    pytest.param(_extras_are({"schema": rs.EXTRAS_SCHEMA, "pr": "7"}), rs.BAD_EXTRAS, id="extras-pr-text"),
    pytest.param(_extras_are({"schema": rs.EXTRAS_SCHEMA, "pr": True}), rs.BAD_EXTRAS, id="extras-pr-bool"),
    pytest.param(_without("meta.json"), rs.UNREADABLE, id="no-meta"),
    pytest.param(_without("driver-journal.jsonl"), rs.UNSUPPORTED, id="hand-driven-session"),
    pytest.param(_state_change(terminal="uncertified-manual"), rs.UNSUPPORTED, id="attested-terminal"),
    pytest.param(_state_change(terminal="mystery"), rs.UNSUPPORTED, id="unknown-terminal"),
    pytest.param(_no_session_id, rs.UNREADABLE, id="meta-without-session-id"),
]


@pytest.mark.parametrize("make,reason", REFUSALS)
def test_refusals(tmp_path, make, reason):
    session, body = make(Session(tmp_path).seat("code-reviewer"), tmp_path)
    path = str(tmp_path / "none.json")
    if isinstance(body, bytes):
        (tmp_path / "extras.json").write_bytes(body)
        path = str(tmp_path / "extras.json")
    elif body is not None:
        path = put_extras(tmp_path, body)
    fake = Fake()
    out = rs.write_from_session(session, path, str(tmp_path), fake.readers())
    # bites on: a session that cannot be read, has not ended, or has no valid extras being written as a record anyway
    assert out["ok"] is False and out["reason"] == reason, out
    assert fake.writes == [] and fake.comments == []


@pytest.mark.parametrize("terminal,decision,max_rounds,cap,kind,stopped", [
    ("capped-with-open-blocker", None, 3, 3, "rounds", True),
    ("capped-with-open-critical", None, None, None, "rounds", True),
    # a round-ceiling stop names the ceiling the driver applied (the default one here), not the configured cap;
    # 10 is the earlier version's default ceiling, which review_record_session._ceiling reads as a literal
    ("halted", "round-ceiling", 3, 10, "ceiling", True),
    ("halted", "something-else", 3, 3, "rounds", False),
    ("converged", None, True, None, "rounds", False)])
def test_rounds_report_the_count_the_cap_and_whether_the_cap_stopped_it(tmp_path, terminal, decision, max_rounds, cap,
                                                                      kind, stopped):
    s = Session(tmp_path, terminal=terminal, rounds={"1": {}, "2": {}},
                decisions=[{"kind": decision, "round": 2}] if decision else [])
    s.state["config"] = {"maxRounds": max_rounds}
    s.seat("code-reviewer")
    # bites on: the round count, a non-integer cap, or a stop at the cap read from the wrong terminal
    rounds = rs.account_from_session(s.save(), extras())["rounds"]
    assert rounds == {"count": 2, "cap": cap, "capKind": kind, "stoppedAtCap": stopped}


def test_write_from_session_never_raises_and_removes_its_temp_file(tmp_path, monkeypatch):
    s = Session(tmp_path).seat("code-reviewer")
    seen = []

    def boom(path, repo_root, readers=None):
        seen.append(path)
        assert os.path.exists(path) and not path.startswith(str(tmp_path))
        raise RuntimeError("boom")
    monkeypatch.setattr(rr, "write", boom)
    out = send(tmp_path, s.save(), Fake())
    # bites on: an exception escaping the adapter, or the temporary account file outliving the call
    assert out["ok"] is False and out["reason"] == "review-record-internal-error"
    assert len(seen) == 1 and not os.path.exists(seen[0])
    assert not os.path.exists(os.path.dirname(seen[0]))
    # bites on: the temporary directory outliving a success or a refusal
    made, real = [], rs.tempfile.mkdtemp
    monkeypatch.setattr(rs.tempfile, "mkdtemp", lambda *a, **k: made.append(real(*a, **k)) or made[-1])
    monkeypatch.setattr(rr, "write", lambda path, repo_root, readers=None: {"ok": True, "action": "created"})
    assert send(tmp_path, s.save(), Fake())["ok"] is True
    assert send(tmp_path, Session(tmp_path / "r", terminal=None).save(), Fake())["ok"] is False
    assert len(made) == 2 and not any(os.path.exists(d) for d in made)


def put_envelope(session, seat, body, phase="dispatch-panel", rnd=1, attempt=0, occurrence=0):
    path = record_paths.store_path(session, rnd, phase, record_paths.storage_key(seat, occurrence), attempt)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh)


def raw_comments(fake):
    return [c["body"] for c in fake.comments if c["body"].startswith(rr.RAW_MARKER)]


def test_raw_output_is_the_seats_payload_and_is_posted_not_withheld(tmp_path):
    s = Session(tmp_path).seat("code-reviewer", nonce="nonce-a")
    session = s.save()
    put_envelope(session, "code-reviewer", {
        "vendor": "codex", "model": CODEX, "runnerNonce": "nonce-a",
        "executionEvidence": {"runnerNonce": "nonce-a", "observation": {"tokens": None, "wallSeconds": 1.0}},
        "payload": {"findings": [{"title": "Unchecked index in parse", "severity": "Important",
                                  "consequence": "a reviewer-found defect stays in the change"}]}})
    fake = Fake()
    out = send(tmp_path, session, fake)
    posted = raw_comments(fake)
    # bites on: what text is posted as a reviewer's raw output (the whole stored envelope reads as a secret and is withheld)
    assert out["ok"] is True and len(posted) == 1
    assert "withheld" not in posted[0] and "Unchecked index in parse" in posted[0]
    assert "executionEvidence" not in posted[0] and "runnerNonce" not in posted[0]


@pytest.mark.parametrize("envelope", [None, "not json", [], {"vendor": "codex"}])
def test_a_ran_seat_whose_output_cannot_be_read_refuses_the_record(tmp_path, envelope):
    session = Session(tmp_path).seat("code-reviewer").save()
    path = record_paths.store_path(session, 1, "dispatch-panel", record_paths.storage_key("code-reviewer", 0), 0)
    if envelope is None:
        os.unlink(path)
    elif isinstance(envelope, str):
        open(path, "w", encoding="utf-8").write(envelope)
    else:
        put_envelope(session, "code-reviewer", envelope)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # bites on: a reviewed record published without the output of a reviewer it credits as run
    with pytest.raises(rs.Refusal) as err:
        rs.account_from_session(session, extras(), Fake().readers(), str(raw_dir))
    assert err.value.args[0] == rs.UNREADABLE and "code-reviewer" in err.value.args[1]
    assert os.listdir(raw_dir) == []


@pytest.mark.parametrize("payload", [{"vacuous": True}, {"reason": "forfeited"}, {"findings": [], "receiptMissing": True},
                                     {"findings": [], "receiptStale": True}])
def test_a_recorded_seat_whose_payload_says_it_did_not_run_is_a_missing_review(tmp_path, payload):
    session = Session(tmp_path).seat("code-reviewer").seat("security-reviewer").save()
    put_envelope(session, "security-reviewer", {"payload": payload})
    account = rs.account_from_session(session, extras(), Fake().readers(), str(tmp_path))
    # bites on: ingestion read as a run, so a vacuous or forfeited seat leaves missingReviews
    assert {r["name"]: r["ran"] for r in account["reviewers"]} == {
        "code-reviewer (round 1)": True, "security-reviewer (round 1)": False}


def test_a_seat_the_rounds_status_calls_missing_is_a_missing_review(tmp_path):
    s = Session(tmp_path, rounds={"1": {"seatStatus": {"code-reviewer": "run", "security-reviewer": "missing"}}})
    account = rs.account_from_session(s.seat("code-reviewer").seat("security-reviewer").save(), extras(),
                                      Fake().readers(), str(tmp_path))
    # bites on: the folded seat status ignored when the journal says a result was recorded
    assert {r["name"]: r["ran"] for r in account["reviewers"]} == {
        "code-reviewer (round 1)": True, "security-reviewer (round 1)": False}


def test_a_missing_seat_envelope_is_a_missing_review_whatever_command_ingested_it(tmp_path):
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer")
    session = s.save()
    put_envelope(session, "security-reviewer", {"schema": rs.sc.SEAT_MISSING_SCHEMA, "reason": "timeout"})
    account = rs.account_from_session(session, extras(), Fake().readers(), str(tmp_path))
    # bites on: a swept seat-missing envelope credited as a run because its journal command was record-result
    assert {r["name"]: r["ran"] for r in account["reviewers"]} == {
        "code-reviewer (round 1)": True, "security-reviewer (round 1)": False}


def test_seats_ingested_by_advance_are_reviewers_classified_by_their_stored_result(tmp_path):
    s = Session(tmp_path).seat("code-reviewer", cmd="advance").seat("security-reviewer", cmd="advance", envelope=False)
    account = rs.account_from_session(s.save(), extras(), Fake().readers(), str(tmp_path))
    # bites on: advance-ingested rows dropped, so a swept missing seat never reaches the record
    assert {r["name"]: r["ran"] for r in account["reviewers"]} == {
        "code-reviewer (round 1)": True, "security-reviewer (round 1)": False}
    assert len(account["rawFindingsFiles"]) == 1


def test_raw_output_phases_are_the_drivers_phase_constants():
    import round_phases
    # bites on: a hand-copied phase list drifting from the driver's phase names
    assert rs._RAW_PHASES == (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_SCOPED)


def test_two_slots_with_the_same_file_name_do_not_collide(tmp_path):
    session = Session(tmp_path).seat("a b").seat("a-b").save()
    put_envelope(session, "a b", {"payload": {"findings": [{"title": "first"}]}})
    put_envelope(session, "a-b", {"payload": {"findings": [{"title": "second"}]}})
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    files = rs.account_from_session(session, extras(), Fake().readers(), str(raw_dir))["rawFindingsFiles"]
    # bites on: a second seat's payload overwriting the first under one file name
    assert sorted(os.path.basename(f) for f in files) == ["panel-a-b-round-1-2.json", "panel-a-b-round-1.json"]
    assert sorted(json.load(open(f))["findings"][0]["title"] for f in files) == ["first", "second"]


def test_no_raw_dir_means_no_raw_files(tmp_path):
    session = Session(tmp_path).seat("code-reviewer").save()
    # bites on: a payload file written, or an envelope path listed, when the caller gave no directory
    assert rs.account_from_session(session, extras(), Fake().readers())["rawFindingsFiles"] == []


def test_the_cli_prints_the_result_and_exits_nonzero_on_refusal(tmp_path, monkeypatch, capsys):
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "review_record_session.py")
    run = subprocess.run([sys.executable, "-B", script, "write", "--session-dir", str(tmp_path / "none"),
                          "--extras", str(tmp_path / "none.json"), "--repo-root", str(tmp_path)],
                         capture_output=True, text=True, timeout=60)
    # bites on: a refusal exiting zero, or the result not printed as one JSON object
    assert run.returncode == 1
    assert json.loads(run.stdout)["reason"] == rs.BAD_EXTRAS
    monkeypatch.setattr(rs, "write_from_session", lambda *a, **k: {"ok": True, "action": "created"})
    argv = ["write", "--session-dir", "d", "--extras", "e", "--repo-root", "r"]
    assert rs.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "action": "created"}


def _second_session(tmp_path, ledger=()):
    root = tmp_path / "later"
    root.mkdir()
    s = Session(root, dispositionLedger=list(ledger))
    s.seat("code-reviewer")
    return s.save()


def _first_record(tmp_path, fake, **ledger_over):
    s = Session(tmp_path, dispositionLedger=[ledger_row(**ledger_over)]).seat("code-reviewer")
    assert send(tmp_path, s.save(), fake)["ok"]


def _by_key(fake):
    return [f for f in rr.read(7, readers=fake.readers())["findings"]]


def test_a_later_session_relists_the_earlier_records_findings_it_did_not_raise(tmp_path):
    fake = Fake()
    _first_record(tmp_path, fake)
    out = send(tmp_path, _second_session(tmp_path), fake)
    # bites on: the adapter not relisting, which the writer refuses as review-record-unaccounted
    assert out["ok"], out
    (carried,) = _by_key(fake)
    assert carried["outcome"] == "fixed" and carried["reason"].endswith(" (carried from the earlier review record)")
    assert len(fake.marked()) == 2


def test_a_finding_carried_across_three_reviews_carries_the_suffix_once(tmp_path):
    fake = Fake()
    _first_record(tmp_path, fake)
    for name in ("second", "third"):
        root = tmp_path / name
        root.mkdir()
        assert send(tmp_path, Session(root).seat("code-reviewer").save(), fake)["ok"]
    (carried,) = _by_key(fake)
    # bites on: the suffix appended again on every carry
    assert carried["reason"].endswith(rs.CARRIED) and carried["reason"].count(rs.CARRIED) == 1


def test_a_finding_the_later_session_raises_again_appears_once_with_its_outcome(tmp_path):
    fake = Fake()
    _first_record(tmp_path, fake)
    out = send(tmp_path, _second_session(tmp_path, [ledger_row(disposition="out-of-scope")]), fake)
    assert out["ok"], out
    (only,) = _by_key(fake)
    assert only["outcome"] == "left-for-owner" and "carried" not in (only["reason"] or "")


def _reviewed_second_session(tmp_path):
    """A later session that on its own reads reviewed: a maker, a reviewer run on the final commit, green CI."""
    root = tmp_path / "later"
    root.mkdir()
    s = Session(root, seatMapReceipts=[{"round": "1", "map": {"seats": {}, "makerFamilies": ["xai"]}}])
    s.seat("code-reviewer", head=HEAD, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, runnerNonce="n1", viewHeadSha=HEAD), None)}
    return s.save(), runs, {"ci": "green", "runDirs": ["/run/n1"]}


def test_a_carried_finding_with_no_outcome_stays_undecided_and_the_record_reads_not_reviewed(tmp_path):
    session, runs, body = _reviewed_second_session(tmp_path)
    control = Fake(runs=runs)
    control_out = send(tmp_path, session, control, **body)
    # bites on: the later session not reading reviewed on its own, so the carried finding proves nothing
    assert control_out["ok"] and control_out["status"] == "reviewed", control_out
    fake = Fake(runs=runs)
    s = Session(tmp_path, findings=[{"findingKey": KEY, "id": "f-1", "title": "t", "severity": "Important",
                                     "file": "a.py", "line": 3, "detail": "d", "dimension": "code-reviewer"}])
    assert send(tmp_path, s.seat("code-reviewer").save(), fake)["ok"]
    out = send(tmp_path, session, fake, **body)
    assert out["ok"], out
    (carried,) = _by_key(fake)
    assert carried["outcome"] is None
    # the only thing left against the record is the carried finding that has no outcome
    assert out["status"] == "not-reviewed"
    assert any("has no outcome" in line for line in out["whatIsMissing"]), out["whatIsMissing"]
    assert not any("covers the final commit" in line for line in out["whatIsMissing"])


def test_a_finding_consequence_reaches_the_posted_record(tmp_path):
    said = "a reviewer-found defect stays in the change"
    s = Session(tmp_path, dispositionLedger=[ledger_row(consequence=said)]).seat("code-reviewer")
    fake = Fake()
    assert send(tmp_path, s.save(), fake)["ok"]
    # bites on: the consequence a finding carries being dropped between the session and the posted record
    (posted,) = _by_key(fake)
    assert posted["consequence"] == said


def test_no_earlier_record_means_nothing_is_carried(tmp_path):
    fake = Fake()
    out = send(tmp_path, _second_session(tmp_path), fake)
    assert out["ok"], out
    assert _by_key(fake) == []


def test_terminal_tables_live_in_decision_kinds():
    assert decision_kinds.CERTIFIED_VERDICTS == round_driver.CERTIFIED_VERDICTS
    assert decision_kinds.ATTESTED_VERDICT == round_driver.ATTESTED_VERDICT
    for verdict in decision_kinds.ALL_VERDICTS:
        assert decision_kinds.map_verdict_to_terminal_state(verdict) is not None, verdict
    assert decision_kinds.map_verdict_to_terminal_state("no-such-verdict") is None
    with open(rs.__file__, encoding="utf-8") as fh:
        assert "round_" + "certification" not in fh.read()


def test_finished_full_lane_session_writes_its_record_without_a_certificate(tmp_path):
    session, runs, body = fix_session(tmp_path)
    assert not os.path.exists(os.path.join(session, "certification-receipt.json"))
    assert not os.path.exists(os.path.join(session, "certification-refusal.json"))
    fake = Fake(runs=runs)
    out = send(tmp_path, session, fake, ci="green", **body)
    assert out["ok"], out
    assert len(fake.marked()) == 1
    text = json.dumps(out, sort_keys=True)
    for token in ("certification-receipt", "handback-no-receipt", "unrun-review"):
        assert token not in text, token


def _verifier_and_synthesis_session(tmp_path):
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"}, rounds={"1": {"fix": {"fixes": []}}})
    s.seat("code-reviewer", nonce="n1")
    s.seat("verifier", phase="dispatch-verifiers", nonce="n2")
    s.seat("synthesis", phase="dispatch-synthesis", nonce="n3")
    runs = {f"/run/{n}": (dict(GOOD_RUN, runnerNonce=n, viewHeadSha=EARLIER), None) for n in ("n1", "n2", "n3")}
    return s.save(), runs


def test_a_verifier_sits_before_the_rounds_fix_and_synthesis_is_not_listed_as_a_reviewer(tmp_path):
    session, runs = _verifier_and_synthesis_session(tmp_path)
    account = rs.account_from_session(session, extras(runDirs=sorted(runs)), Fake(runs=runs).readers())
    steps = {v["name"]: v.get("step") for v in account["reviewers"]}
    # bites on: verification placed after the fix (step 3), or the synthesis judge listed among the reviewers
    assert steps == {"code-reviewer (round 1)": 2, "verifiers verifier (round 1)": 2}


def test_a_claude_synthesis_of_an_anthropic_made_change_leaves_no_synthesis_row_and_no_park(tmp_path):
    session, runs = _verifier_and_synthesis_session(tmp_path)
    fake = Fake(runs=runs)
    account = rs.account_from_session(session, extras(runDirs=sorted(runs), makers=[{"family": "anthropic", "source": "author"}]),
                                      fake.readers())
    rec = rr.build_record(account, fake.readers())
    # bites on: the synthesis step, always seated on claude, being judged against an anthropic maker and parking the record
    assert not any("synthesis" in v["name"] for v in rec["reviewers"])
    assert not any("synthesis" in str(m) for m in rec["missingReviews"])
    assert rec["missingReviews"] == [] and not rec.get("parked")


def test_a_legacy_author_family_before_the_first_fix_stays_an_original_maker(tmp_path):
    claude = {"vendor": "claude", "model": "sonnet-5.5"}
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": []}}, "2": {}},
                seatMapReceipts=[{"round": "0", "map": {"seats": {"code-reviewer": claude}, "authorFamily": "anthropic"}},
                                 {"round": "1", "map": {"seats": {"code-reviewer": claude}, "makerFamilies": ["openai"]}}])
    s.seat("code-reviewer", rnd=1, nonce="n1")
    runs = {"/run/n1": (dict(GOOD_RUN, source="claude", engineModel="sonnet-5.5", runnerNonce="n1",
                             viewHeadSha=EARLIER), None)}
    account = rs.account_from_session(s.save(), extras(runDirs=["/run/n1"]), Fake(runs=runs).readers())
    # bites on: a legacy authorFamily dropped from the pre-fix history, handing its original maker a delayed fromStep
    assert not any(m["family"] == "anthropic" and "fromStep" in m for m in account["makers"])
    assert any(m["family"] == "anthropic" for m in account["makers"])
