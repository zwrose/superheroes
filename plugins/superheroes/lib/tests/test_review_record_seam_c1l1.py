"""The review record's new optional parts: round-level (`rounds.extraAudit`, `rerunChecks`, `synthesisRounds`,
`outsideThisPR`, `unreadShare`), reviewer-row (`readParts`, the writer's own `cost`) and finding-level (`grade`,
`repeatOf`, `breakItRuns`, `kindOfMistake`).

Every part shows in the record and the summary exactly when the account carries it; a malformed one refuses
`review-account-invalid` before anything is posted; an absent one leaves no trace; every record reviewer row carries
a `cost` no trim step removes.

Edges: E1 no new key · E2 each malformed shape refused, nothing posted · E3 bool where an int is required · E4 exit
code and status coupled · E5 exactly two runs · E6 sweep id coupled to the source kind, hits non-empty · E7 unread
within countable, ranges real · E8 a repeat names its finding key · E9 read words · E10 a demoted row's cost ·
E11 a missing or bool measure is null · E12 the trim steps keep cost · E13 an account cost is ignored · E14 an empty
outside list · E15 compact levels · E16 the claim check leaves out the findings block and the outside list.
"""
import copy

import pytest

import review_record as rr
from test_review_record import CODEX, GOOD_RUN, HEAD, Fake, account, build, finding, put, reviewer

ROUNDS = {"count": 3, "cap": 4, "stoppedAtCap": False}
WHY = "the advisor ordered one audit of round 4's fixes"
NEW_PREFIXES = ("Extra audit round", "Re-run after", "Findings:", "Outside this PR", "Left unread")


def lines_of(summary):
    return summary.split("\n")


def summary_of(acct, level=0, fake=None):
    return rr._summary(build(acct, fake), level)


def run(status="ran", code=0, **over):
    return {"status": status, "exitCode": code if status == "ran" else None, "output": "out", "reason": None, **over}


def check(runs=None, **over):
    return {"round": 1, "check": "pytest -q tests/x.py", "runs": runs or [run(code=1), run(code=0)], **over}


def hit(**over):
    return {"id": "H-1", "file": "lib/x.py", "line": 12, "title": "unused import", **over}


def outside(**over):
    return {"source": {"kind": "reviewer", "name": "code-reviewer", "sweepId": None}, "hits": [hit()], **over}


def sweep(**over):
    return {**outside(), "source": {"kind": "sweep", "name": "sweeper", "sweepId": "sw-1"}, **over}


def break_run(**over):
    return {"test": "tests/test_x.py::test_y", "commit": "abc1234", "status": "ran", "exitCode": 1,
            "output": "AssertionError", "reason": None, "changedWhy": None, **over}


def parts(**over):
    return {"file": "a.py", "lines": [[1, 10]], **over}


UNREAD = {"unreadLines": 40, "countableLines": 400, "parts": [parts()]}

# Each malformed shape the contract names: (edge, the path the refusal detail starts with, the account override).
BAD = {
    "extraAudit": [
        ("E2", "rounds.extraAudit", {"rounds": {**ROUNDS, "extraAudit": {"why": "  "}}}),
        ("E2", "rounds.extraAudit", {"rounds": {**ROUNDS, "extraAudit": {"why": 3}}}),
        ("E2", "rounds.extraAudit", {"rounds": {**ROUNDS, "extraAudit": {}}}),
        ("E2", "rounds.extraAudit", {"rounds": {**ROUNDS, "extraAudit": {"why": "x", "count": 1}}}),
        ("E2", "rounds.extraAudit", {"rounds": {**ROUNDS, "extraAudit": "later"}}),
    ],
    "rerunChecks": [
        ("E2", "rerunChecks", {"rerunChecks": "x"}),
        ("E2", "rerunChecks[0].round", {"rerunChecks": [check(round=0)]}),
        ("E3", "rerunChecks[0].round", {"rerunChecks": [check(round=True)]}),
        ("E2", "rerunChecks[0].check", {"rerunChecks": [check(check=" ")]}),
        ("E5", "rerunChecks[0].runs", {"rerunChecks": [check(runs=[run()])]}),
        ("E5", "rerunChecks[0].runs", {"rerunChecks": [check(runs=[run(), run(), run()])]}),
        ("E2", "rerunChecks[0].runs[1].status", {"rerunChecks": [check(runs=[run(), run(status="hung")])]}),
        ("E3", "rerunChecks[0].runs[0].exitCode", {"rerunChecks": [check(runs=[run(code=True), run()])]}),
        ("E4", "rerunChecks[0].runs[1].exitCode",
         {"rerunChecks": [check(runs=[run(), run("timed-out", exitCode=1)])]}),
        ("E4", "rerunChecks[0].runs[0].exitCode", {"rerunChecks": [check(runs=[run(code=None), run()])]}),
        ("E2", "rerunChecks[0].runs[0].output", {"rerunChecks": [check(runs=[run(output=None), run()])]}),
        ("E2", "rerunChecks[0].runs[0].reason", {"rerunChecks": [check(runs=[run(reason=4), run()])]}),
    ],
    "synthesisRounds": [
        ("E2", "synthesisRounds", {"synthesisRounds": 1}),
        ("E2", "synthesisRounds", {"synthesisRounds": [0]}),
        ("E3", "synthesisRounds", {"synthesisRounds": [True]}),
        ("E2", "synthesisRounds", {"synthesisRounds": [2, 1]}),
        ("E2", "synthesisRounds", {"synthesisRounds": [1, 1]}),
        ("E2", "synthesisRounds", {"synthesisRounds": ["1"]}),
    ],
    "outsideThisPR": [
        ("E2", "outsideThisPR", {"outsideThisPR": {}}),
        ("E2", "outsideThisPR[0].source.kind", {"outsideThisPR": [outside(source={"kind": "x", "name": "n", "sweepId": None})]}),
        ("E2", "outsideThisPR[0].source.name", {"outsideThisPR": [outside(source={"kind": "reviewer", "name": " ", "sweepId": None})]}),
        ("E6", "outsideThisPR[0].source.sweepId", {"outsideThisPR": [sweep(source={"kind": "sweep", "name": "n", "sweepId": None})]}),
        ("E6", "outsideThisPR[0].source.sweepId", {"outsideThisPR": [sweep(source={"kind": "sweep", "name": "n", "sweepId": " "})]}),
        ("E6", "outsideThisPR[0].source.sweepId", {"outsideThisPR": [outside(source={"kind": "reviewer", "name": "n", "sweepId": "sw-1"})]}),
        ("E6", "outsideThisPR[0].hits", {"outsideThisPR": [outside(hits=[])]}),
        ("E2", "outsideThisPR[0].hits[0].title", {"outsideThisPR": [outside(hits=[hit(title="")])]}),
        ("E3", "outsideThisPR[0].hits[0].line", {"outsideThisPR": [outside(hits=[hit(line=False)])]}),
    ],
    "unreadShare": [
        ("E2", "unreadShare", {"unreadShare": []}),
        ("E7", "unreadShare.unreadLines", {"unreadShare": {**UNREAD, "unreadLines": 401}}),
        ("E2", "unreadShare.countableLines", {"unreadShare": {**UNREAD, "countableLines": -1}}),
        ("E3", "unreadShare.unreadLines", {"unreadShare": {**UNREAD, "unreadLines": True}}),
        ("E2", "unreadShare.parts", {"unreadShare": {"unreadLines": 1, "countableLines": 2}}),
        ("E7", "unreadShare.parts[0].lines[0]", {"unreadShare": {**UNREAD, "parts": [parts(lines=[[9, 3]])]}}),
        ("E7", "unreadShare.parts[0].lines[0]", {"unreadShare": {**UNREAD, "parts": [parts(lines=[[0, 3]])]}}),
    ],
    "readParts": [
        ("E2", "reviewers[0].readParts", {"reviewers": [reviewer(readParts="a.py")]}),
        ("E2", "reviewers[0].readParts[0].file", {"reviewers": [reviewer(readParts=[parts(file=" ")])]}),
        ("E2", "reviewers[0].readParts[0].lines", {"reviewers": [reviewer(readParts=[{"file": "a.py"}])]}),
        ("E7", "reviewers[0].readParts[0].lines[0]", {"reviewers": [reviewer(readParts=[parts(lines=[[5, 2]])])]}),
        ("E3", "reviewers[0].readParts[0].lines[0]", {"reviewers": [reviewer(readParts=[parts(lines=[[True, 2]])])]}),
    ],
    "grade": [
        ("E2", "findings[0].grade.verdict", {"findings": [finding(grade={"verdict": "great", "reason": "r"})]}),
        ("E2", "findings[0].grade.reason", {"findings": [finding(grade={"verdict": "confirmed", "reason": "  "})]}),
        ("E2", "findings[0].grade", {"findings": [finding(grade="confirmed")]}),
    ],
    "repeatOf": [
        ("E8", "findings[0].repeatOf.findingKey", {"findings": [finding(repeatOf={"id": "F-1"})]}),
        ("E8", "findings[0].repeatOf.findingKey", {"findings": [finding(repeatOf={"findingKey": " "})]}),
        ("E8", "findings[0].repeatOf.findingKey", {"findings": [finding(repeatOf={"findingKey": 3})]}),
        ("E2", "findings[0].repeatOf.id", {"findings": [finding(repeatOf={"findingKey": "k", "id": 3})]}),
        ("E2", "findings[0].repeatOf.fixHolds", {"findings": [finding(repeatOf={"findingKey": "k", "fixHolds": "yes"})]}),
    ],
    "breakItRuns": [
        ("E2", "findings[0].breakItRuns", {"findings": [finding(breakItRuns="x")]}),
        ("E2", "findings[0].breakItRuns[0].test", {"findings": [finding(breakItRuns=[break_run(test="")])]}),
        ("E2", "findings[0].breakItRuns[0].commit", {"findings": [finding(breakItRuns=[break_run(commit=" ")])]}),
        ("E2", "findings[0].breakItRuns[0].changedWhy", {"findings": [finding(breakItRuns=[break_run(changedWhy=2)])]}),
        ("E2", "findings[0].breakItRuns[0].status", {"findings": [finding(breakItRuns=[break_run(status="hung")])]}),
        ("E3", "findings[0].breakItRuns[0].exitCode", {"findings": [finding(breakItRuns=[break_run(exitCode=True)])]}),
        ("E4", "findings[0].breakItRuns[0].exitCode",
         {"findings": [finding(breakItRuns=[break_run(status="timed-out", exitCode=1)])]}),
        ("E4", "findings[0].breakItRuns[0].exitCode", {"findings": [finding(breakItRuns=[break_run(exitCode=None)])]}),
    ],
    "kindOfMistake": [
        ("E2", "findings[0].kindOfMistake.kind", {"findings": [finding(kindOfMistake={"kind": " ", "places": []})]}),
        ("E2", "findings[0].kindOfMistake.places", {"findings": [finding(kindOfMistake={"kind": "k"})]}),
        ("E2", "findings[0].kindOfMistake.places[0].file",
         {"findings": [finding(kindOfMistake={"kind": "k", "places": [{"file": "", "line": 1, "fixed": True}]})]}),
        ("E3", "findings[0].kindOfMistake.places[0].line",
         {"findings": [finding(kindOfMistake={"kind": "k", "places": [{"file": "a", "line": False, "fixed": True}]})]}),
        ("E2", "findings[0].kindOfMistake.places[0].fixed",
         {"findings": [finding(kindOfMistake={"kind": "k", "places": [{"file": "a", "line": 1, "fixed": "yes"}]})]}),
    ],
}


def refused(tmp_path, path, over):
    fake = Fake()
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
    assert (out["ok"], out.get("reason")) == (False, "review-account-invalid"), (path, out)
    assert out["detail"].startswith(path), (path, out)
    assert fake.comments == [], path


def every_variant_refused(tmp_path, element):
    for edge, path, over in BAD[element]:
        refused(tmp_path, path, over)


# --- the shapes the contract names are refused (one test per guarded element) ---

def test_bp1_extra_audit_is_a_reason_and_nothing_else(tmp_path):
    # axis: rounds.extraAudit refuses a blank or missing reason and any other key
    every_variant_refused(tmp_path, "extraAudit")


def test_bp2_a_rerun_check_has_exactly_two_coherent_runs(tmp_path):
    # axis: rerunChecks refuses a run count other than two and an exit code that does not match the status
    every_variant_refused(tmp_path, "rerunChecks")


def test_bp3_synthesis_rounds_are_distinct_ascending_rounds(tmp_path):
    # axis: synthesisRounds refuses non-ints, bools, rounds below 1, repeats and a descending order
    every_variant_refused(tmp_path, "synthesisRounds")


def test_bp4_an_outside_entry_names_its_source_and_a_hit(tmp_path):
    # axis: outsideThisPR refuses a sweep with no sweep id, a reviewer with one, and an entry with no hit
    every_variant_refused(tmp_path, "outsideThisPR")


def test_bp5_the_unread_share_is_within_the_countable_lines(tmp_path):
    # axis: unreadShare refuses unread above countable and a range that is not 1 <= start <= end
    every_variant_refused(tmp_path, "unreadShare")


def test_bp6_read_parts_are_files_with_real_ranges(tmp_path):
    # axis: readParts refuses a non-list, a blank file and a range that is not 1 <= start <= end
    every_variant_refused(tmp_path, "readParts")


def test_bp7_a_grade_is_a_verdict_with_a_reason(tmp_path):
    # axis: grade refuses a verdict outside the vocabulary and a blank reason
    every_variant_refused(tmp_path, "grade")


def test_bp8_a_repeat_names_the_earlier_finding_by_its_key(tmp_path):
    # axis: repeatOf refuses a missing, blank or non-string findingKey
    for edge, path, over in BAD["repeatOf"]:
        if edge == "E8":
            refused(tmp_path, path, over)


def test_bp9_a_break_it_run_has_an_exit_code_exactly_when_it_ran(tmp_path):
    # axis: breakItRuns refuses an exit code that does not match the status, a bool exit code and a blank test
    every_variant_refused(tmp_path, "breakItRuns")


def test_bp10_a_kind_of_mistake_names_its_kind_and_places(tmp_path):
    # axis: kindOfMistake refuses a blank kind, a missing places list and a place with no file
    every_variant_refused(tmp_path, "kindOfMistake")


def test_the_other_malformed_shapes_of_repeat_of_are_refused(tmp_path):
    # axis: repeatOf refuses a non-string id and a non-bool fixHolds
    for edge, path, over in BAD["repeatOf"]:
        if edge == "E2":
            refused(tmp_path, path, over)


def test_a_well_formed_part_of_each_kind_is_accepted(tmp_path):
    # axis: the validators admit the shapes the contract names, including null where null is allowed
    acct = account(
        rounds={**ROUNDS, "extraAudit": {"why": WHY}},
        rerunChecks=[check(), check(runs=[run("timed-out"), run("not-started", reason="no time")])],
        synthesisRounds=[1, 3], outsideThisPR=[outside(), sweep(hits=[hit(line=None)])], unreadShare=UNREAD,
        reviewers=[reviewer(readParts=[]), reviewer("b", readParts=[parts()])],
        findings=[finding(grade={"verdict": "wrong", "reason": "r"}, repeatOf={"findingKey": "k"},
                          breakItRuns=[break_run(commit=None, status="timed-out", exitCode=None)],
                          kindOfMistake={"kind": "k", "places": []})])
    out = rr.write(put(tmp_path, acct), str(tmp_path), Fake().readers())
    assert out["ok"], out


# --- the summary, and the record ---

def test_dod_the_rounds_line_is_as_before():
    # axis: the rounds line is unchanged when no extra audit ran
    summary = summary_of(account(rounds=ROUNDS))
    assert "Rounds: 3 of 4 (round cap)." in lines_of(summary)
    assert "Extra audit round" not in summary


def test_dod_the_extra_audit_line_follows_the_rounds_line_and_is_not_counted():
    # axis: rounds.extraAudit shows on the line after the rounds line, and rounds.count never includes it
    acct = account(rounds={**ROUNDS, "extraAudit": {"why": WHY}})
    record = build(acct)
    lines = lines_of(rr._summary(record, 0))
    at = lines.index("Rounds: 3 of 4 (round cap).")
    assert lines[at + 1] == f"Extra audit round: ran, ordered at the vet and not counted in the 4 rounds: {WHY}."
    assert record["rounds"]["count"] == 3
    assert record["rounds"]["extraAudit"] == {"why": WHY}


def test_the_extra_audit_line_with_no_cap():
    # axis: with no cap the line says "the rounds", never "the None rounds"
    acct = account(rounds={"count": 2, "cap": None, "stoppedAtCap": False, "extraAudit": {"why": WHY}})
    assert f"Extra audit round: ran, ordered at the vet and not counted in the rounds: {WHY}." in lines_of(summary_of(acct))


def full_account(**over):
    place_fixed = {"kind": "wrong unit", "places": [{"file": "a.py", "line": 3, "fixed": True},
                                                    {"file": "b.py", "line": None, "fixed": False}]}
    base = dict(
        rounds={**ROUNDS, "extraAudit": {"why": WHY}},
        rerunChecks=[check(round=2, check="pytest -q tests/x.py", decision="went-on"),
                     check(round=3, check="make test", runs=[run("timed-out"), run("not-started")], decision="failed")],
        synthesisRounds=[1, 3],
        outsideThisPR=[outside(hits=[hit(), hit(id="H-2", file="lib/y.py", line=None, title="stale doc")]),
                       sweep(hits=[hit(id="H-3", file="lib/z.py", line=7, title="dead branch")])],
        unreadShare=UNREAD,
        reviewers=[reviewer("code-reviewer (round 1)", readParts=[parts(lines=[[1, 10], [20, 29]]), parts(file="b.py", lines=[[5, 5]])]),
                   reviewer("verifiers code-reviewer (round 1)")],
        findings=[
            finding("F-1", title="one", grade={"verdict": "confirmed", "reason": "reproduced on the head"},
                    kindOfMistake=place_fixed),
            finding("F-2", title="two", severity="Important", outcome="shown-wrong",
                    repeatOf={"findingKey": "rr1:0123456789abcdef0123", "id": None, "fixHolds": False},
                    breakItRuns=[break_run(), break_run(exitCode=0, output="SECRET OUTPUT TEXT")],
                    kindOfMistake={"kind": "wrong unit", "places": [{"file": "c.py", "line": 1, "fixed": True}]}),
            finding("F-3", title="three", outcome="left-for-owner", reason="needs owner",
                    repeatOf={"findingKey": "k", "id": "F-1", "fixHolds": None}),
        ])
    return account(**{**base, **over})


def test_dod_an_account_with_every_new_field_renders_each_part():
    # axis: each new part renders in the contract's shape and order, and run output stays out of the summary
    record = build(full_account())
    summary = rr._summary(record, 0)
    lines = lines_of(summary)
    assert lines[lines.index("Rounds: 3 of 4 (round cap).") + 1].startswith("Extra audit round: ran,")
    rerun = ("Re-run after one failure: round 2 `pytest -q tests/x.py`: failed (exit 1) then passed; "
             "round 3 `make test`: timed out then did not start")
    assert rerun in lines
    assert "Reviewers: code · verifier · synthesis" in lines
    assert any(l.startswith("- code-reviewer: ran in round 1 (engine record);") and l.endswith("; read 2 files, 21 lines")
               for l in lines)
    at = lines.index("Findings:")
    assert lines[at + 1:at + 4] == [
        "- F-1 Minor · fixed · confirmed: reproduced on the head · kind of mistake: wrong unit"
        " · also in this PR: a.py:3, b.py (fixed in 1 of 2 places)",
        "- F-2 Important · shown wrong · repeat of rr1:01234567 · fix no longer holds"
        " · break-it: 2 run(s) (failed (exit 1), passed) · kind of mistake: wrong unit"
        " · also in this PR: c.py:1 (all fixed)",
        "- F-3 Minor · left for the owner · repeat of F-1"]
    at = lines.index("Outside this PR (3)")
    assert lines[at + 1:at + 5] == [
        "- H-1 lib/x.py:12 · unused import (from code-reviewer)",
        "- H-2 lib/y.py · stale doc (from code-reviewer)",
        "- H-3 lib/z.py:7 · dead branch (from sweep sw-1 by sweeper)",
        "For the advisor to sort at the vet."]
    assert "Left unread by the slice reviewers: 40 of 400 countable lines (10.0%)." in lines
    assert "SECRET OUTPUT TEXT" not in summary
    assert record["findings"][1]["breakItRuns"][1]["output"] == "SECRET OUTPUT TEXT"
    order = [next(i for i, l in enumerate(lines) if l.startswith(p))
             for p in ("Rounds:", "Extra audit round", "Re-run after", "Reviewers:", "Findings:", "Outside this PR",
                       "Left unread")]
    assert order == sorted(order)


def test_the_record_carries_each_round_part_whole():
    # axis: the round-level parts ride into the record under their own names and shapes
    acct = full_account()
    record = build(acct)
    for key in ("rerunChecks", "synthesisRounds", "outsideThisPR", "unreadShare"):
        assert record[key] == acct[key], key
    assert record["reviewers"][0]["readParts"] == acct["reviewers"][0]["readParts"]
    assert "readParts" not in record["reviewers"][1]
    assert [f["grade"] for f in record["findings"] if "grade" in f] == [acct["findings"][0]["grade"]]


def test_dod_an_account_with_no_add_on_field_renders_nothing_of_them(tmp_path):
    # axis: absent add-on parts leave no heading and no JSON key — see bite-proof record c1l1_wo_a_record_seam
    record = build(account(findings=[finding("F-1")], rounds=ROUNDS))
    summary = rr._summary(record, 0)
    for text in ("Outside this PR", "kind of mistake", "Left unread", "Re-run after", "Extra audit round"):
        assert text not in summary, text
    for key in ("outsideThisPR", "unreadShare", "rerunChecks", "synthesisRounds"):
        assert key not in record, key
    assert "extraAudit" not in record["rounds"]
    assert not {"grade", "repeatOf", "breakItRuns", "kindOfMistake"} & set(record["findings"][0])
    assert "readParts" not in record["reviewers"][0]


def test_e1_an_account_with_none_of_the_new_keys_gains_only_cost():
    # axis: nothing is added to the record or the summary beyond each reviewer row's cost
    record = build(account(reviewers=[reviewer(), reviewer("x-seat")]))
    assert all("cost" in row and "readParts" not in row for row in record["reviewers"])
    assert not {"rerunChecks", "synthesisRounds", "outsideThisPR", "unreadShare"} & set(record)
    lines = lines_of(rr._summary(record, 0))
    assert not [l for l in lines if l.startswith(NEW_PREFIXES)]
    assert lines.count("Reviewers: code") == 1
    one = lines_of(summary_of(account(reviewers=[reviewer("x-seat")])))
    assert "Reviewers:" in one
    assert not [l for l in one if l.startswith("Reviewers: ")]


# --- the panel sample ---

SAMPLE_SEATS = ("code-reviewer (round 1)", "test-role (round 1)", "security-reviewer (round 1)",
                "premortem-reviewer (round 1)", "verifiers code-reviewer (round 1)", "audits F-1 (round 2)",
                "scoped-finder s1 (round 3)")


def sample_summary():
    rows = [reviewer(name) for name in SAMPLE_SEATS]
    fake = Fake(runs={row["runDir"]: (copy.deepcopy(GOOD_RUN), None) for row in rows})
    first = finding("F-1", title="one", severity="Important",
                    grade={"verdict": "confirmed", "reason": "reproduced on the head"})
    acct = account(
        reviewers=rows, synthesisRounds=[1], rounds=ROUNDS,
        findings=[first,
                  finding("F-2", title="two", outcome="craft", reason="not worth fixing"),
                  finding("F-4", title="four", severity="Important",
                          repeatOf={"findingKey": rr._key(first), "id": "F-1", "fixHolds": True})])
    return rr._summary(build(acct, fake), 0)


def test_the_panel_7_sample_names_its_roles_and_lists_its_findings():
    # axis: the header lists each role once in the fixed order, and the findings block follows the record order
    lines = lines_of(sample_summary())
    assert "Reviewers: code, test, security, premortem · verifier · synthesis · fix auditor · scoped finder" in lines
    at = lines.index("Findings:")
    assert lines[at + 1:at + 4] == [
        "- F-1 Important · fixed · confirmed: reproduced on the head",
        "- F-2 Minor · craft call",
        "- F-4 Important · fixed · repeat of F-1 · fix still holds"]


def test_a_row_that_did_not_run_names_no_role():
    # axis: only rows with ran != not-run name a role
    rows = [reviewer("code-reviewer (round 1)"), reviewer("test-role (round 1)", ran=False, runDir=None)]
    assert "Reviewers: code" in lines_of(summary_of(account(reviewers=rows)))


def test_a_stem_less_seat_outside_the_table_names_no_role_and_a_lens_names_itself_once():
    # axis: any other stem-less seat is left out; a lens appearing in two rounds is listed once
    rows = [reviewer("code-reviewer (round 1)"), reviewer("code-reviewer (round 2)"),
            reviewer("architecture-reviewer (round 1)"), reviewer("grounding-reviewer (round 1)"),
            reviewer("seams-check g1 (round 2)"), reviewer("second-test s1 (round 2)")]
    assert "Reviewers: code, architecture · seams check · second test" in lines_of(summary_of(account(reviewers=rows)))


def test_the_unread_line_with_no_countable_lines_has_no_percent():
    # axis: no percentage over zero countable lines
    share = {"unreadLines": 0, "countableLines": 0, "parts": []}
    assert "Left unread by the slice reviewers: 0 of 0 countable lines." in lines_of(summary_of(account(unreadShare=share)))


# --- E9 read words ---

def test_e9_read_parts_say_how_much_was_read_and_an_empty_list_says_nothing_was():
    # axis: [] reads "read nothing", a list sums its ranges, an absent key says nothing about reading
    rows = [reviewer("code-reviewer (round 1)", readParts=[]),
            reviewer("x-seat", readParts=[parts(lines=[[1, 10], [20, 29]]), parts(file="b.py", lines=[[5, 5]])]),
            reviewer("test-role (round 1)")]
    lines = lines_of(summary_of(account(reviewers=rows)))
    assert "- code-reviewer: ran in round 1 (engine record); findings: reported by the session; read nothing" in lines
    assert "- x-seat: ran (engine record); findings: reported by the session; read 2 files, 21 lines" in lines
    assert "- test-role: ran in round 1 (engine record); findings: reported by the session" in lines


# --- cost: E10-E13 ---

def costs(record):
    return [row["cost"] for row in record["reviewers"]]


def test_the_cost_of_a_credited_row_comes_from_its_engine_record():
    # axis: cost is read from the credited run's observation, tokens as an int and minutes as wallSeconds / 60 to one place
    record = build(account(reviewers=[reviewer("a"), reviewer("b"), reviewer("c", ran=False, runDir=None)]),
                   Fake(runs={"/run/a": (dict(GOOD_RUN, observation={"tokens": 100, "wallSeconds": 125, "read": "engaged"}), None)}))
    assert costs(record) == [{"tokens": 100, "minutes": 2.1}, {"tokens": 100, "minutes": 2.0},
                             {"tokens": None, "minutes": None}]


def test_e10_a_row_demoted_after_crediting_has_no_cost():
    # axis: a demoted row is not-run, so its cost is null, never the run record's numbers
    other = dict(GOOD_RUN, source="claude")
    record = build(account(), Fake(runs={"/run/code-reviewer": (other, None)}))
    assert record["reviewers"][0]["ran"] == "not-run"
    assert costs(record) == [{"tokens": None, "minutes": None}]


@pytest.mark.parametrize("observation,expected", [
    ({"wallSeconds": 90.0, "read": "engaged"}, {"tokens": None, "minutes": 1.5}),
    ({"tokens": True, "wallSeconds": 60, "read": "engaged"}, {"tokens": None, "minutes": 1.0}),
    ({"tokens": 7, "read": "engaged"}, {"tokens": 7, "minutes": None}),
    ({"tokens": 7, "wallSeconds": True, "read": "engaged"}, {"tokens": 7, "minutes": None}),
    ({"tokens": "7", "wallSeconds": "60", "read": "engaged"}, {"tokens": None, "minutes": None}),
    ({"tokens": 0, "wallSeconds": 0, "read": "engaged"}, {"tokens": 0, "minutes": 0.0}),
    (None, {"tokens": None, "minutes": None}),
])
def test_e11_a_missing_or_bool_measure_is_null(observation, expected):
    # axis: an absent, bool or non-numeric measure is null (unmeasured), never zero; a measured zero stays zero
    record = build(account(), Fake(runs={"/run/code-reviewer": (dict(GOOD_RUN, observation=observation), None)}))
    assert costs(record) == [expected]


def big_record_inputs(n=110):
    rows = [reviewer(f"r{i}") for i in range(n)]
    blob = {"tokens": 100, "wallSeconds": 120, "read": "engaged", "toolCalls": 3, "log": "x" * 700}
    return account(reviewers=rows), Fake(runs={row["runDir"]: (dict(GOOD_RUN, observation=dict(blob)), None)
                                                for row in rows})


def test_e12_the_trim_steps_keep_every_rows_cost():
    # axis: neither reviewer trim step removes cost, called directly or through render_plan — see bite-proof record c1l1_wo_a_record_seam
    record = build(*big_record_inputs(3))
    want = costs(record)
    assert want == [{"tokens": 100, "minutes": 2.0}] * 3
    assert costs(rr._shed_observation(record)) == want
    assert costs(rr._shed_run_dir(record)) == want
    assert all("observation" in row for row in record["reviewers"])
    record = build(*big_record_inputs())
    plan = rr.render_plan(record)
    assert plan.parts == []
    posted = rr._json_block(plan.head())
    assert posted["reviewerShed"][0] == "observation"
    assert costs(posted) == costs(record)
    assert all("log" not in row.get("observation", {}) for row in posted["reviewers"])


def test_e13_an_account_cost_is_ignored():
    # axis: cost is the writer's own, never taken from the account row
    record = build(account(reviewers=[reviewer(cost={"tokens": 999, "minutes": 999})]))
    assert costs(record) == [{"tokens": 100, "minutes": 2.0}]


# --- E14, E15, E16 ---

def test_e14_an_empty_outside_list_is_valid_and_renders_no_heading():
    # axis: an empty list validates, is carried, and renders nothing
    record = build(account(outsideThisPR=[]))
    assert record["outsideThisPR"] == []
    assert "Outside this PR" not in rr._summary(record, 0)
    assert "Outside this PR" not in rr._summary(record, 1)


def test_e15_the_compact_levels_give_the_count_forms():
    # axis: level 1 turns the lists into counts, keeps the reviewer bullets and clips the extra audit reason; level 2 also counts reviewers
    long_why = "w" * 400
    record = build(full_account(rounds={**ROUNDS, "extraAudit": {"why": long_why}}))
    one, two = lines_of(rr._summary(record, 1)), lines_of(rr._summary(record, 2))
    for lines in (one, two):
        assert "Findings: 3 (listed in the full record)." in lines
        assert "Outside this PR (3) (listed in the full record)." in lines
        assert "Re-run after one failure: 2 checks (listed in the full record)." in lines
        assert f"Extra audit round: ran, ordered at the vet and not counted in the 4 rounds: {'w' * 299}…." in lines
        assert "Left unread by the slice reviewers: 40 of 400 countable lines (10.0%)." in lines
        assert not [l for l in lines if l.startswith(("- F-", "- H-", "For the advisor"))]
    assert "Reviewers: code · verifier · synthesis" in one
    assert any(l.startswith("- code-reviewer: ran in round 1") for l in one)
    assert "Reviewers: 2 rows across 2 seats (listed in the full record)." in two
    assert not [l for l in two if l.startswith(("Reviewers: code", "- code-reviewer"))]
    assert f"Extra audit round: ran, ordered at the vet and not counted in the 4 rounds: {long_why}." in lines_of(rr._summary(record, 0))


def write_posted(tmp_path, **over):
    fake = Fake()
    out = rr.write(put(tmp_path, account(**over)), str(tmp_path), fake.readers())
    return out, fake


def test_e16_the_findings_block_and_the_outside_list_are_out_of_the_claim_check(tmp_path):
    # axis: a grade reason and a hit title are reviewers' own text, so the phrase in them does not refuse the write — see bite-proof record c1l1_wo_a_record_seam
    out, fake = write_posted(
        tmp_path, findings=[finding(grade={"verdict": "plausible", "reason": "the author calls it bug-free"},
                                    kindOfMistake={"kind": "no bugs here claim", "places": []})],
        outsideThisPR=[outside(hits=[hit(title="a bug free claim")])])
    assert out["ok"], out
    body = fake.marked()[0]["body"]
    assert "bug-free" in body and "a bug free claim" in body


def test_e16_the_phrase_elsewhere_in_the_summary_still_refuses(tmp_path):
    # axis: only the findings block, the outside list and the header are left out; every other line is still checked
    for over in ({"reviewers": [reviewer("bug free")]},
                 {"rounds": {**ROUNDS, "extraAudit": {"why": "it is bug-free"}}},
                 {"rerunChecks": [check(check="echo no bugs")]}):
        out, fake = write_posted(tmp_path, **over)
        assert (out["ok"], out.get("reason")) == (False, "review-record-forbidden-claim"), over
        assert fake.comments == []
