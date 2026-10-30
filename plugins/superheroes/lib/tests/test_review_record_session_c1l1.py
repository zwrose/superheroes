"""The session adapter carries the review record's new parts and loses no finding.

Finding parts (`grade`, `repeatOf`, `breakItRuns`, `kindOfMistake`) survive a newer row; the round parts and the
reviewer read lists reach the account; an abandoned session lists every finding a stored seat result held that the
loop never took in; a later session keeps what the latest earlier record held.

Edges: E1 a live row without a part keeps the ledger's · E2 a live part wins · E3 neither has it, the key is absent ·
E4 a re-run list that is not a list · E5 a synthesis row that does not count · E6 an unfolded finding the account
already lists · E7 the same unfolded finding from two seats · E8 an unfolded finding the compile dropped · E9 a
terminal session adds nothing · E10 an envelope that cannot be read · E11 an earlier record that cannot be read ·
E12 a break-it run both sides hold.
"""
import json

import record_paths
import review_record as rr
import review_record_session as rs
import round_phases

from test_review_record_session import (
    CODEX, KEY, Fake, Session, extras, ledger_row, put_envelope, put_extras, send,
)

REASON = "owner stopped the loop"
GRADE = {"verdict": "confirmed", "reason": "reproduced on the changed code"}
OTHER_GRADE = {"verdict": "plausible", "reason": "read, not reproduced"}
REPEAT = {"findingKey": "a.py::t@L3", "id": "f-0", "fixHolds": True}
STORED_REPEAT = dict(REPEAT, findingKey=rr._key({"findingKey": REPEAT["findingKey"]}))
KIND = {"kind": "unchecked index", "places": [{"file": "b.py", "line": 4, "fixed": True}]}
RUN_1 = {"test": "tests/test_a.py::test_t", "commit": "abc1234", "status": "ran", "exitCode": 1,
         "output": "AssertionError: boom", "reason": None, "changedWhy": None}
RUN_2 = dict(RUN_1, commit="def5678", exitCode=0, output="ok")
PARTS = ("grade", "repeatOf", "breakItRuns", "kindOfMistake")
VALUES = {"grade": GRADE, "repeatOf": REPEAT, "breakItRuns": [RUN_1], "kindOfMistake": KIND}
LIVE = {"findingKey": KEY, "id": "f-1", "title": "t", "severity": "Important", "file": "a.py", "line": 3,
        "detail": "d", "dimension": "code-reviewer"}
UNFOLDED = {"title": "Unfolded defect", "severity": "Important", "file": "u.py", "line": 8,
            "consequence": "a defect stays in the change"}
SYNTHESIS = {"outcome": "recorded", "cmd": "record-result", "phase": round_phases.P_SYNTHESIS, "seat": "synthesis",
             "attempt": 0}


def _sub(tmp_path, name):
    root = tmp_path / name
    root.mkdir()
    return root


def _account(session, abandoned=None):
    return rs.account_from_session(session, extras(), Fake().readers(), abandoned=abandoned)


def _write(tmp_path, session, fake, abandoned=None):
    return rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers(), abandoned=abandoned)


def _record(fake):
    return rr.read(7, readers=fake.readers())


def _body(fake):
    return fake.marked()[-1]["body"]


def _later(tmp_path, name, **state):
    """A new session directory with one panel seat, saved."""
    return Session(_sub(tmp_path, name), **state).seat("code-reviewer").save()


def _abandoned(tmp_path, seats=(("code-reviewer", [UNFOLDED]),), **state):
    """A session (by default one with no terminal, abandoned) whose stored seat results hold the given findings, none folded."""
    s = Session(tmp_path, **{"terminal": None, **state})
    for seat, _ in seats:
        s.seat(seat)
    session = s.save()
    for seat, found in seats:
        put_envelope(session, seat, {"vendor": "codex", "model": CODEX, "payload": {"findings": found}})
    return session


def test_e1_a_live_row_without_a_part_keeps_the_ledger_rows(tmp_path):
    # axis: a newer row never erases a finding part an older row held, for each of the four parts — see bite-proof record c1l1_wo_b_session_seam
    session = Session(tmp_path, findings=[LIVE], dispositionLedger=[ledger_row(**VALUES)]).seat("code-reviewer").save()
    (row,) = _account(session)["findings"]
    assert {p: row[p] for p in PARTS} == dict(VALUES, repeatOf=STORED_REPEAT)


def test_e2_a_live_part_wins_over_the_ledger_rows(tmp_path):
    # axis: when both rows hold a part, the live row's value is the one carried
    session = Session(tmp_path, findings=[dict(LIVE, grade=OTHER_GRADE)],
                      dispositionLedger=[ledger_row(**VALUES)]).seat("code-reviewer").save()
    (row,) = _account(session)["findings"]
    assert row["grade"] == OTHER_GRADE and row["repeatOf"] == STORED_REPEAT


def test_e3_a_part_neither_row_holds_is_absent_not_none(tmp_path):
    # axis: no part key at all on a row that never held one, so the writer adds no empty key
    session = Session(tmp_path, findings=[LIVE], dispositionLedger=[ledger_row()]).seat("code-reviewer").save()
    (row,) = _account(session)["findings"]
    assert not set(PARTS) & set(row)
    live_only = Session(_sub(tmp_path, "b"), findings=[dict(LIVE, grade=GRADE)]).seat("code-reviewer").save()
    (only,) = _account(live_only)["findings"]
    assert only["grade"] == GRADE and not set(PARTS[1:]) & set(only)


def test_e4_a_rerun_list_that_is_not_a_list_contributes_nothing(tmp_path):
    # axis: rerunChecks is present on the account only when some round's list gave an entry
    check = {"check": "pytest -q tests/test_a.py", "runs": [{"status": "ran", "exitCode": 1, "output": "x", "reason": None},
                                                            {"status": "ran", "exitCode": 0, "output": "", "reason": None}]}
    none = Session(tmp_path, rounds={"1": {"rerunChecks": "x"}, "2": {}, "3": {"rerunChecks": None}}).seat("code-reviewer").save()
    assert "rerunChecks" not in _account(none)["rounds"] and "rerunChecks" not in _account(none)
    some = Session(_sub(tmp_path, "b"), rounds={"10": {"rerunChecks": [dict(check, round=99)]}, "2": {"rerunChecks": [check]},
                                                "1": {"rerunChecks": 5}}).seat("code-reviewer").save()
    assert [(c["round"], c["check"]) for c in _account(some)["rerunChecks"]] == [(2, check["check"]), (10, check["check"])]


def test_e5_only_a_recorded_synthesis_row_with_an_int_round_counts(tmp_path):
    # axis: synthesisRounds lists the sorted distinct rounds of recorded synthesis rows with an int round, a boolean round never — see bite-proof record c1l1_wo_b_session_seam
    s = Session(tmp_path, rounds={"1": {}, "2": {}, "3": {}}).seat("code-reviewer")
    s.rows += [dict(SYNTHESIS, round=2), dict(SYNTHESIS, round=1), dict(SYNTHESIS, round=1, attempt=1),
               dict(SYNTHESIS, round=3, outcome="rejected"), dict(SYNTHESIS, round="3"), dict(SYNTHESIS, round=None)]
    assert _account(s.save())["synthesisRounds"] == [1, 2]
    bare = Session(_sub(tmp_path, "b")).seat("code-reviewer")
    bare.rows.append(dict(SYNTHESIS, round=1, outcome="rejected"))
    assert "synthesisRounds" not in _account(bare.save())
    # a boolean round alone: True == 1, so beside a real round-1 row it would collapse into it and hide an accepted bool
    boolean = Session(_sub(tmp_path, "c")).seat("code-reviewer")
    boolean.rows.append(dict(SYNTHESIS, round=True))
    assert "synthesisRounds" not in _account(boolean.save())


def test_an_accepted_synthesis_row_counts_as_a_synthesis_round(tmp_path):
    # axis: a hand submit journals outcome "accepted" and counts like "recorded"; record-missing never does — see bite-proof record c1l1_wo_b_session_seam
    s = Session(tmp_path, rounds={"1": {}, "2": {}, "3": {}}).seat("code-reviewer")
    s.rows += [dict(SYNTHESIS, round=1, outcome="accepted", cmd="submit"), dict(SYNTHESIS, round=3, outcome="accepted",
                                                                                 cmd="record-missing")]
    assert _account(s.save())["synthesisRounds"] == [1]


def test_a_synthesis_seat_recorded_missing_is_not_a_synthesis_round(tmp_path):
    # axis: a record-missing synthesis row (outcome "recorded") is no result; record-result and a row with no cmd count — see bite-proof record c1l1_wo_b_session_seam
    missing = Session(tmp_path).seat("code-reviewer")
    missing.rows.append(dict(SYNTHESIS, round=1, cmd="record-missing"))
    assert "synthesisRounds" not in _account(missing.save())
    both = Session(_sub(tmp_path, "b")).seat("code-reviewer")
    both.rows += [dict(SYNTHESIS, round=1, cmd="record-missing"), dict(SYNTHESIS, round=2, cmd="record-result"),
                  {k: v for k, v in dict(SYNTHESIS, round=3).items() if k != "cmd"}]
    assert _account(both.save())["synthesisRounds"] == [2, 3]


def test_the_round_parts_the_state_holds_reach_the_account_as_they_are(tmp_path):
    # axis: extraAudit, outsideThisPR and unreadShare are carried as the state holds them, the writer validates them
    outside = [{"source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None},
                "hits": [{"id": "H-1", "file": "x.py", "line": 2, "title": "unused import"}]}]
    share = {"unreadLines": 4, "countableLines": 40, "parts": []}
    session = Session(tmp_path, extraAudit={"why": "the vet wanted one more look"}, outsideThisPR=outside,
                      unreadShare=share).seat("code-reviewer").save()
    account = _account(session)
    assert account["rounds"]["extraAudit"] == {"why": "the vet wanted one more look"}
    assert account["outsideThisPR"] == outside and account["unreadShare"] == share
    plain = _account(Session(_sub(tmp_path, "b"), extraAudit="later").seat("code-reviewer").save())
    assert "extraAudit" not in plain["rounds"] and "outsideThisPR" not in plain and "unreadShare" not in plain


def test_a_panel_reviewers_read_list_reaches_its_row_and_the_summary(tmp_path):
    # axis: a panel row carries the readParts its stored result reported, a ran panel reviewer with no list reads nothing ([])
    s = Session(tmp_path).seat("code-reviewer").seat("security-reviewer").seat("test-role")
    session = s.save()
    put_envelope(session, "code-reviewer", {"vendor": "codex", "model": CODEX, "payload": {
        "findings": [], "readParts": [{"file": "a.py", "lines": [[1, 10], [20, 24]]}]}})
    put_envelope(session, "security-reviewer", {"vendor": "codex", "model": CODEX, "payload": {"findings": [], "readParts": []}})
    rows = {v["name"]: v for v in _account(session)["reviewers"]}
    assert rows["code-reviewer (round 1)"]["readParts"] == [{"file": "a.py", "lines": [[1, 10], [20, 24]]}]
    assert rows["security-reviewer (round 1)"]["readParts"] == []
    assert rows["test-role (round 1)"]["readParts"] == []
    fake = Fake()
    assert _write(tmp_path, session, fake)["ok"]
    assert "; read 1 files, 15 lines" in _body(fake) and "; read nothing" in _body(fake)


def test_crash_before_the_fold_lists_the_unfolded_finding_open(tmp_path):
    # axis: an abandoned session lists a finding recorded in a stored seat result and never folded, open, with its reviewer — see bite-proof record c1l1_wo_b_session_seam
    account = _account(_abandoned(tmp_path), REASON)
    (row,) = account["findings"]
    assert (row["id"], row["title"], row["outcome"], row["reason"], row["reviewer"], row["decidedBy"]) == (
        row["findingKey"], "Unfolded defect", None, rs.UNFOLDED_OPEN, "code-reviewer", None)
    assert (row["severity"], row["file"], row["line"], row["consequence"]) == ("Important", "u.py", 8, UNFOLDED["consequence"])
    assert rs.UNFOLDED_FINDINGS_CHECKED in account["checked"]
    fake = Fake()
    assert _write(tmp_path, str(tmp_path / "session"), fake, REASON)["ok"]
    assert [(f["title"], f["outcome"], f["reason"]) for f in _record(fake)["findings"]] == [
        ("Unfolded defect", None, rs.UNFOLDED_OPEN)]


def test_an_unfolded_finding_takes_the_id_and_body_it_was_recorded_with(tmp_path):
    # axis: a non-blank string id and the body (or detail) of the stored finding are kept on the open row
    session = _abandoned(tmp_path, seats=(("code-reviewer", [dict(UNFOLDED, id="X-1", detail="the detail"),
                                                             dict(UNFOLDED, title="Second", id="  ", body="the body")]),))
    first, second = _account(session, REASON)["findings"]
    assert (first["id"], first["body"]) == ("X-1", "the detail")
    assert (second["id"], second["body"]) == (second["findingKey"], "the body")


def test_e6_an_unfolded_finding_the_account_already_lists_is_not_added_twice(tmp_path):
    # axis: an unfolded finding whose key a live finding already holds adds no second row
    session = _abandoned(tmp_path, seats=(("code-reviewer", [dict(UNFOLDED, findingKey=KEY), {"title": " "}, "text"]),),
                         findings=[LIVE])
    (row,) = _account(session, REASON)["findings"]
    assert row["findingKey"] == KEY and row["reason"] == rs.STILL_OPEN


def test_e7_the_same_unfolded_finding_from_two_seats_is_added_once_under_the_first_seat(tmp_path):
    # axis: an unfolded finding stored by two seats is listed once, under the first seat in journal order
    session = _abandoned(tmp_path, seats=(("code-reviewer", [UNFOLDED]), ("security-reviewer", [UNFOLDED])))
    (row,) = _account(session, REASON)["findings"]
    assert row["reviewer"] == "code-reviewer"


def test_e8_an_unfolded_finding_the_compile_dropped_stays_under_refused(tmp_path):
    # axis: a finding the round's compile dropped is accounted for under refused and not listed a second time — see bite-proof record c1l1_wo_b_session_seam
    drops = [{"title": "Dropped", "file": "a.py", "line": 1, "reason": "no consequence named"},
             {"title": "No file", "file": None, "line": None, "reason": "no place named"}]
    found = [{"title": "Dropped", "file": "a.py", "line": 1}, {"title": "Dropped", "file": "b.py", "line": 1},
             {"title": "Dropped", "file": None, "line": 1}, {"title": "No file"}]
    account = _account(_abandoned(tmp_path, seats=(("code-reviewer", found),), rounds={"1": {"compileDrops": drops}}), REASON)
    assert [(f["title"], f["file"]) for f in account["findings"]] == [("Dropped", "b.py"), ("Dropped", None)]
    assert [(r["title"], r["file"]) for r in account["refused"]] == [("Dropped", "a.py"), ("No file", None)]
    later = _abandoned(_sub(tmp_path, "b"), seats=(("code-reviewer", [{"title": "Dropped", "file": "a.py", "line": 1}]),),
                       rounds={"1": {}, "2": {"compileDrops": drops}})
    assert [f["title"] for f in _account(later, REASON)["findings"]] == ["Dropped"]  # another round's drop does not cover it


def test_e9_a_terminal_session_adds_nothing_for_an_unfolded_finding(tmp_path):
    # axis: the open rows are an abandoned session's alone, a session that ended lists what the loop held
    session = _abandoned(tmp_path, terminal="converged")
    assert _account(session)["findings"] == []


def test_e10_an_envelope_that_cannot_be_read_or_has_no_findings_list_contributes_nothing(tmp_path):
    # axis: an unreadable envelope, a payload that is not a dict and a findings value that is not a list add no row and no refusal
    session = _abandoned(tmp_path, seats=(("code-reviewer", [UNFOLDED]), ("security-reviewer", [UNFOLDED]),
                                          ("test-role", [UNFOLDED]), ("premortem-reviewer", [UNFOLDED])))
    with open(record_paths.store_path(session, 1, "dispatch-panel", record_paths.storage_key("code-reviewer", 0), 0), "w") as fh:
        fh.write("{not json")
    put_envelope(session, "security-reviewer", {"vendor": "codex", "model": CODEX, "payload": ["x"]})
    put_envelope(session, "test-role", {"vendor": "codex", "model": CODEX, "payload": {"findings": "nope"}})
    put_envelope(session, "premortem-reviewer", ["x"])
    assert _account(session, REASON)["findings"] == []


def test_e11_an_earlier_record_that_cannot_be_read_fills_and_carries_nothing(tmp_path):
    # axis: any read failure of the earlier record reads as no earlier findings
    fake = Fake()
    fake.comments.append({"id": 1, "author": "bot", "body": rr.MARKER + "\nnot a record", "url": "http://c/1"})
    account = rs.account_from_session(_later(tmp_path, "b", dispositionLedger=[ledger_row()]), extras(), fake.readers())
    assert rr.read(7, readers=fake.readers())["reason"] == "review-record-unreadable"
    assert rs._earlier(account, extras(), str(tmp_path), fake.readers()) == []
    before = json.dumps(account["findings"], sort_keys=True)
    rs._fill(account, rs._earlier(account, extras(), str(tmp_path), fake.readers()))
    assert json.dumps(account["findings"], sort_keys=True) == before


def test_e12_a_break_it_run_both_sides_hold_is_kept_once(tmp_path):
    # axis: the earlier record's runs lead, a run of this session equal to one of them adds nothing
    fake = Fake()
    first = Session(tmp_path, dispositionLedger=[ledger_row(breakItRuns=[RUN_1, RUN_2])]).seat("code-reviewer").save()
    assert send(tmp_path, first, fake)["ok"]
    second = _later(tmp_path, "b", dispositionLedger=[ledger_row(breakItRuns=[RUN_2, RUN_1])])
    assert send(tmp_path, second, fake)["ok"]
    (row,) = _record(fake)["findings"]
    assert row["breakItRuns"] == [RUN_1, RUN_2]


def test_fill_a_malformed_current_break_it_runs_value_is_left_for_the_writer_to_refuse():
    # axis: a present non-list breakItRuns is not replaced by the earlier list, so validation still sees it
    account = {"findings": [dict(LIVE, breakItRuns=RUN_2)]}
    rs._fill(account, [dict(LIVE, breakItRuns=[RUN_1])])
    assert account["findings"][0]["breakItRuns"] == RUN_2


def test_fill_a_current_run_the_scrub_changed_is_not_appended_again_beside_its_scrubbed_earlier_form():
    # axis: the earlier runs come from the scrubbed posted record, so a current run is compared in its scrubbed form — see bite-proof record c1l1_wo_b_session_seam
    raw = dict(RUN_1, output="setup ok " + "pass" + "word=" + "x" * 12)
    scrubbed = rr._scrubbed(raw)
    assert scrubbed != raw  # the premise: the writer's scrub changes this run
    account = {"findings": [dict(LIVE, breakItRuns=[raw])]}
    rs._fill(account, [dict(LIVE, breakItRuns=[scrubbed])])
    assert account["findings"][0]["breakItRuns"] == [scrubbed]


def test_fill_a_current_run_that_is_not_a_dict_is_compared_as_it_is():
    # axis: a non-dict run takes no scrub call and is appended once, not dropped and not doubled — see bite-proof record c1l1_wo_b_session_seam
    account = {"findings": [dict(LIVE, breakItRuns=["not a run", "not a run"])]}
    rs._fill(account, [dict(LIVE, breakItRuns=[RUN_1])])
    assert account["findings"][0]["breakItRuns"] == [RUN_1, "not a run"]


def test_fill_the_earlier_grade_and_runs_survive_a_later_session_that_lacks_them(tmp_path):
    # axis: a later row without a grade gets the earlier one, and the earlier runs come before the new run — see bite-proof record c1l1_wo_b_session_seam
    fake = Fake()
    first = Session(tmp_path, dispositionLedger=[ledger_row(grade=GRADE, repeatOf=REPEAT, breakItRuns=[RUN_1])]).seat("code-reviewer").save()
    assert send(tmp_path, first, fake)["ok"]
    second = _later(tmp_path, "b", dispositionLedger=[ledger_row(breakItRuns=[RUN_2], kindOfMistake=KIND)])
    assert send(tmp_path, second, fake)["ok"]
    (row,) = _record(fake)["findings"]
    assert row["grade"] == GRADE and row["repeatOf"] == STORED_REPEAT and row["kindOfMistake"] == KIND
    assert row["breakItRuns"] == [RUN_1, RUN_2]
    fresh = _later(tmp_path, "c", dispositionLedger=[ledger_row(grade=OTHER_GRADE)])
    assert send(tmp_path, fresh, fake)["ok"]
    assert _record(fake)["findings"][0]["grade"] == OTHER_GRADE  # a part the later row holds is not replaced


def test_dod_three_of_four_rounds(tmp_path):
    # axis: a terminal session with a cap of four and three rounds writes a summary reading three of four
    session = Session(tmp_path, config={"maxRounds": 4}, rounds={"1": {}, "2": {}, "3": {}}).seat("code-reviewer").save()
    fake = Fake()
    assert _write(tmp_path, session, fake)["ok"]
    assert "Rounds: 3 of 4 (round cap)." in _body(fake)


def test_dod_crash_then_resume_lists_every_round_one_finding(tmp_path):
    # axis: a session that crashed and was resumed lists every finding the first run recorded, decided or open
    second = dict(LIVE, findingKey="b.py::u@L9", id="f-2", title="u", file="b.py", line=9)
    s = Session(tmp_path, terminal=None, findings=[LIVE, second],
                dispositionLedger=[ledger_row(disposition=None), ledger_row("b.py::u@L9", id="f-2", title="u", file="b.py", line=9,
                                                                             disposition=None)])
    s.seat("code-reviewer")
    fake = Fake()
    crashed = _write(tmp_path, s.save(), fake)
    assert crashed["ok"] is False and crashed["reason"] == rs.NOT_TERMINAL and fake.comments == []
    s.state.update(terminal="converged", rounds={"1": {}, "2": {}},
                   dispositionLedger=[ledger_row(), ledger_row("b.py::u@L9", id="f-2", title="u", file="b.py", line=9, disposition=None)])
    assert _write(tmp_path, s.save(), fake)["ok"]
    got = {f["id"]: (f["outcome"], f["reason"]) for f in _record(fake)["findings"]}
    assert got == {"f-1": ("fixed", "fixed and audited in round 2"), "f-2": (None, rs.STILL_OPEN)}


def test_dod_a_restarted_session_relists_what_the_first_raised(tmp_path):
    # axis: a second, new session directory lists the first record's findings with their outcomes and its own
    fake = Fake()
    first = Session(tmp_path, dispositionLedger=[
        ledger_row(), ledger_row("c.py::b@L5", id="f-2", title="b", file="c.py", line=5, disposition="out-of-scope",
                                 outOfScopeReason="the owner's call")]).seat("code-reviewer").save()
    assert send(tmp_path, first, fake)["ok"]
    third = dict(LIVE, findingKey="d.py::c@L7", id="f-3", title="c", file="d.py", line=7)
    assert send(tmp_path, _later(tmp_path, "b", findings=[third]), fake)["ok"]
    got = {f["id"]: f["outcome"] for f in _record(fake)["findings"]}
    assert got == {"f-1": "fixed", "f-2": "left-for-owner", "f-3": None}
    carried = [f for f in _record(fake)["findings"] if f["id"] != "f-3"]
    assert all(f["reason"].endswith(rs.CARRIED) for f in carried)


def test_dod_a_session_that_drops_a_carried_finding_is_refused_and_posts_nothing(tmp_path):
    # axis: an account missing one of the latest record's findings is refused review-record-unaccounted
    fake = Fake()
    first = Session(tmp_path, dispositionLedger=[ledger_row()]).seat("code-reviewer").save()
    assert send(tmp_path, first, fake)["ok"]
    posted = len(fake.comments)
    account = rs.account_from_session(_later(tmp_path, "b", findings=[dict(LIVE, findingKey="d.py::c@L7", id="f-3")]),
                                      extras(), fake.readers())
    path = tmp_path / "stripped.json"
    path.write_text(json.dumps(account))
    out = rr.write(str(path), str(tmp_path), fake.readers())
    assert out["ok"] is False and out["reason"] == "review-record-unaccounted", out
    assert len(fake.comments) == posted


def test_dod_the_carried_parts_render_in_the_summary(tmp_path):
    # axis: grade, repeat mark, break-it words, re-run line, extra-audit line and the synthesis role reach the posted summary
    check = {"check": "pytest -q tests/test_a.py", "runs": [{"status": "ran", "exitCode": 1, "output": "RUN-OUTPUT", "reason": None},
                                                            {"status": "ran", "exitCode": 0, "output": "", "reason": None}]}
    s = Session(tmp_path, config={"maxRounds": 7}, rounds={"1": {}, "2": {"rerunChecks": [check]}},
                extraAudit={"why": "the advisor ordered one audit of round 2's fixes"},
                dispositionLedger=[ledger_row(grade=GRADE, repeatOf=REPEAT, breakItRuns=[RUN_1], kindOfMistake=KIND)])
    s.seat("code-reviewer").rows.append(dict(SYNTHESIS, round=1))
    fake = Fake()
    assert _write(tmp_path, s.save(), fake)["ok"]
    body = _body(fake)
    assert "Reviewers: code · synthesis" in body
    assert "Extra audit round: ran, ordered at the vet and not counted in the 7 rounds: the advisor ordered one audit of round 2's fixes." in body
    assert "Re-run after one failure on unchanged code: round 2 `pytest -q tests/test_a.py`: failed (exit 1) then passed" in body
    assert ("- f-1 Important · fixed · confirmed: reproduced on the changed code · repeat of f-0 · fix still holds · "
            "break-it: 1 run(s) (failed (exit 1)) · kind of mistake: unchecked index · also in this PR: b.py:4 (all fixed)") in body
    summary = body.split("<details>")[0]
    assert "RUN-OUTPUT" not in summary and "AssertionError: boom" not in summary
    assert "RUN-OUTPUT" in body and "AssertionError: boom" in body  # the runs' output is in the record's JSON
