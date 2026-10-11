import copy
import json
import os
import shutil
import subprocess
import sys

import pytest

import model_registry
import receipt_disclosures
import record_paths
import review_record as rr
import review_record_session as rs

HEAD = "b" * 40  # the PR's head in the default Fake, and the final commit of the built sessions
EARLIER = "a" * 40
THIRD = "c" * 40
CODEX = model_registry.codex_models()[0]
NO_STATUS = {"state": "pending", "total_count": 0, "statuses": []}
GREEN = ({"total_count": 1, "check_runs": [{"name": "validate", "status": "completed", "conclusion": "success"}]},
         NO_STATUS)
GOOD_RUN = {"source": "codex", "engineModel": CODEX, "viewHeadSha": HEAD,
            "observation": {"tokens": 100, "wallSeconds": 120}, "graded": True, "runKind": "review"}
KEY = "a.py::t@L3"


class Fake:
    """Injectable readers with an in-memory comment list; records create calls."""

    def __init__(self, head=HEAD, runs=None):
        self.comments, self.writes = [], []
        self.head, self.runs = head, runs or {}

    def readers(self):
        return {
            "pr_meta": lambda pr, repo: {"head": self.head, "body": "", "issues": []},
            "issue_body": lambda n, repo: None,
            "check_data": lambda sha, repo: GREEN,
            "lane_marker": lambda root: None,
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
    s = Session(tmp_path, dispositionLedger=[ledger_row()])
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
    {"kind": "standing-ruling", "canonId": "standing-1"},
    {"kind": "owner-words", "words": "go on without it", "where": "the issue thread"},
])
def test_a_specialist_that_did_not_run_parks_unless_the_owner_went_ahead(tmp_path, go_ahead):
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer", cmd="record-missing")
    fake = Fake()
    gone = "security-reviewer (round 1)"
    out = send(tmp_path, s.save(), fake, goAheads=[dict(go_ahead, reviewer=gone)] if go_ahead else [])
    # bites on: a seat that never reported being left out of the record, or a go-ahead lifting the parking wrongly
    assert out["ok"] and out["status"] == "not-reviewed", out
    rec = rr.read(7, readers=fake.readers())
    assert [m["name"] for m in rec["missingReviews"]] == [gone]
    assert out["parked"] is (go_ahead is None)
    assert (rec["missingReviews"][0]["goAhead"] or {}).get("kind") == (go_ahead or {}).get("kind")


def test_a_missing_slot_recovered_by_a_later_round_is_not_a_missing_review(tmp_path):
    s = Session(tmp_path, rounds={"1": {}, "2": {}})
    s.seat("code-reviewer").seat("security-reviewer", cmd="record-missing").seat("security-reviewer", rnd=2)
    account = rs.account_from_session(s.save(), extras(), Fake().readers())
    # bites on: a seat missed in one round and run in a later one still reading as a missing review
    assert [(v["name"], v["ran"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", True), ("security-reviewer (round 2)", True)]


def test_the_fixers_family_joins_the_makers_and_a_same_family_reviewer_is_marked(tmp_path):
    seat_map = {"seats": {"code-reviewer": {"vendor": "codex", "model": CODEX}},
                "degradations": [{"constraint": "same-family", "seat": "code-reviewer"}]}
    s = Session(tmp_path, config={"maxRounds": 7, "fixerVendor": "claude"},
                rounds={"1": {"fix": {"fixes": []}}}, seatMapReceipts=[{"round": "1", "map": seat_map}])
    s.seat("code-reviewer").seat("security-reviewer")
    fam = receipt_disclosures.author_family(s.state)
    assert fam
    session = s.save()
    account = rs.account_from_session(session, extras(makers=[{"family": "other", "source": "the extras"}]))
    # bites on: the fixer's family missing from the makers, or the same-family mark landing on the wrong reviewer
    assert account["makers"] == [{"family": "other", "source": "the extras"}, {"family": fam, "source": "review loop fixer"}]
    marks = {v["name"]: v.get("notIndependent") for v in account["reviewers"]}
    assert marks == {"code-reviewer (round 1)": True, "security-reviewer (round 1)": None}
    listed = rs.account_from_session(session, extras(makers=[{"family": fam, "source": "the extras"}]))
    assert listed["makers"] == [{"family": fam, "source": "the extras"}]
    fake = Fake()
    assert send(tmp_path, session, fake)["ok"]
    rec = rr.read(7, readers=fake.readers())
    assert {v["name"]: v.get("notIndependent") for v in rec["reviewers"]}["code-reviewer (round 1)"] is True


def _merged(member_over, rep_over):
    return [ledger_row("m::t@L1", id="m-1", disposition=None, mergedInto=KEY, **member_over),
            ledger_row(KEY, id="rep-1", **rep_over)]


OOS = {"disposition": "out-of-scope", "outOfScopeReason": "belongs to the follow-up"}
RULED = {"findingKey": KEY, "ruling": "out-of-scope", "provenance": {"ruledBy": "the owner", "ruledAt": "2030-01-02"}}
CASES = [
    pytest.param([ledger_row()], [], KEY, "fixed", "fixed and audited in round 2", id="fresh-fixed"),
    pytest.param([ledger_row(disposition="refuted", refutedReason="the cited line does not exist")], [], KEY,
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


def test_superseded_attempts_are_not_reviewers(tmp_path):
    s = Session(tmp_path)
    s.seat("code-reviewer", attempt=0).seat("security-reviewer", attempt=0)
    s.rows.append({"outcome": "orders-superseded", "cmd": "re-emit", "phase": "dispatch-panel", "round": 1, "attempt": 0})
    s.seat("code-reviewer", attempt=1, head=HEAD)
    s.seat("test-reviewer", attempt=0).seat("test-reviewer", attempt=1, head=HEAD)
    s.rows.append({"outcome": "recorded", "cmd": "record-result", "phase": "dispatch-panel", "round": 1, "seat": 5})
    s.rows.append({"outcome": "recorded", "cmd": "record-result", "phase": None, "round": 1, "seat": "x"})
    account = rs.account_from_session(s.save(), extras())
    # bites on: an attempt the orders superseded still counting, or two attempts of one slot counting twice
    assert [(v["name"], v["commit"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", HEAD), ("test-reviewer (round 1)", HEAD)]


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


def test_a_hand_driven_session_reports_its_reviewers_by_the_session(tmp_path):
    rounds = {"1": {"seatStatus": {"code-reviewer": "run", "test-reviewer": "missing"}},
              "2": {"seatStatus": {"code-reviewer": "run"}}}
    s = Session(tmp_path, rounds=rounds)
    s.meta.pop("fixFoldHeadSha")
    session = s.save()
    assert not os.path.exists(os.path.join(session, "driver-journal.jsonl"))
    account = rs.account_from_session(session, extras())
    # bites on: a session with no journal being refused or read as having no reviewers
    assert [(v["name"], v["ran"], v["commit"], v["runDir"]) for v in account["reviewers"]] == [
        ("code-reviewer (round 1)", True, EARLIER, None), ("test-reviewer (round 1)", False, EARLIER, None),
        ("code-reviewer (round 2)", True, None, None)]
    fake = Fake(head=EARLIER)
    out = send(tmp_path, session, fake)
    assert out["ok"], out
    rec = rr.read(7, readers=fake.readers())
    assert [v["ran"] for v in rec["reviewers"]] == ["reported-by-session", "not-run", "reported-by-session"]


@pytest.mark.parametrize("terminal,decision,max_rounds,cap,stopped", [
    ("capped-with-open-blocker", None, 3, 3, True), ("capped-with-open-critical", None, None, None, True),
    ("halted", "round-ceiling", 3, 3, True), ("halted", "something-else", 3, 3, False),
    ("converged", None, True, None, False)])
def test_rounds_report_the_count_the_cap_and_whether_the_cap_stopped_it(tmp_path, terminal, decision, max_rounds, cap,
                                                                      stopped):
    s = Session(tmp_path, terminal=terminal, rounds={"1": {}, "2": {}},
                decisions=[{"kind": decision, "round": 2}] if decision else [])
    s.state["config"] = {"maxRounds": max_rounds}
    s.seat("code-reviewer")
    # bites on: the round count, a non-integer cap, or a stop at the cap read from the wrong terminal
    rounds = rs.account_from_session(s.save(), extras())["rounds"]
    assert rounds == {"count": 2, "cap": cap, "stoppedAtCap": stopped}


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
        "payload": {"findings": [{"title": "Unchecked index in parse", "severity": "Important"}]}})
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


def test_a_finding_the_later_session_raises_again_appears_once_with_its_outcome(tmp_path):
    fake = Fake()
    _first_record(tmp_path, fake)
    out = send(tmp_path, _second_session(tmp_path, [ledger_row(disposition="out-of-scope")]), fake)
    assert out["ok"], out
    (only,) = _by_key(fake)
    assert only["outcome"] == "left-for-owner" and "carried" not in (only["reason"] or "")


def test_a_carried_finding_with_no_outcome_stays_undecided_and_the_record_reads_not_reviewed(tmp_path):
    fake = Fake()
    s = Session(tmp_path, findings=[{"findingKey": KEY, "id": "f-1", "title": "t", "severity": "Important",
                                     "file": "a.py", "line": 3, "detail": "d", "dimension": "code-reviewer"}])
    assert send(tmp_path, s.seat("code-reviewer").save(), fake)["ok"]
    out = send(tmp_path, _second_session(tmp_path), fake)
    assert out["ok"], out
    (carried,) = _by_key(fake)
    assert carried["outcome"] is None
    assert out["status"] != "reviewed"


def test_no_earlier_record_means_nothing_is_carried(tmp_path):
    fake = Fake()
    out = send(tmp_path, _second_session(tmp_path), fake)
    assert out["ok"], out
    assert _by_key(fake) == []
