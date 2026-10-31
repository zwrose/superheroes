"""Tests for lib/review_measures.py (#2189): the review-loop measures row, one fixed-shape row per gardening window."""
import datetime
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import review_learning  # noqa: E402
import review_measures as RM  # noqa: E402

D = datetime.date.fromisoformat
FROM, UNTIL = D("2026-10-01"), D("2026-10-07")
U = RM.UNMEASURED


def _row(name, commit="c1", ran="engine-record", tokens=100, minutes=1.5):
    return {"name": name, "ran": ran, "commit": commit, "cost": {"tokens": tokens, "minutes": minutes}}


def _rec(pr, session="s1", at="2026-10-03T10:00:00Z", rows=None, findings=(), count=2, status="reviewed"):
    return {"pr": pr, "sessionId": session, "writtenAt": at, "status": status, "rounds": {"count": count},
            "reviewers": rows if rows is not None else [_row("security-reviewer (round 1)")],
            "findings": list(findings)}


def _f(key, outcome="fixed", reviewer="Security"):
    return {"id": key, "findingKey": key, "outcome": outcome, "reviewer": reviewer}


def _full(**over):
    inp = {"records": [_rec(1)], "ciRuns": [{"pr": 1, "minutes": 4, "suiteMinutes": 3}], "escapes": [],
           "vetReceipts": [], "capChoicesSince": "2026-09-01",
           "costly": {"lateFindsOnUnchangedCode": {"basis": "monthly", "value": 0}}}
    inp.update(over)
    return inp


def _why(row):
    return {u["measure"]: u["reason"] for u in row["unmeasured"]}


def test_the_row_shape_is_pinned():
    assert RM.MEASURES == ("roundsPerPr", "sessionsPerPr", "reviewerCostPerPr", "seats", "ci", "panels",
                           "vetSendBacksOnCleanLoops", "escapes", "capChoices", "lateFindsOnUnchangedCode",
                           "repeatFindingLocations")
    assert RM.ROW_KEYS == ("schema", "window", "writtenAt", "prs", "measures", "seatingRow", "leftOut", "unmeasured")
    row = RM.compute(_full(), FROM, UNTIL)
    assert tuple(row) == RM.ROW_KEYS and tuple(row["measures"]) == RM.MEASURES and RM.problems(row) == []


@pytest.mark.parametrize("damage", [lambda r: r.pop("seatingRow"), lambda r: r["measures"].pop("ci"),
                                    lambda r: r.update(unmeasured=[]), lambda r: r["measures"].update(ci=0)])
def test_a_row_off_its_shape_is_named(damage):
    row = RM.compute(_full(), FROM, UNTIL)  # repeatFindingLocations reads unmeasured, so clearing the reasons is a fault
    damage(row)
    assert RM.problems(row)


def test_every_input_missing_reads_unmeasured_with_its_reason_never_zero():
    row = RM.compute({}, FROM, UNTIL)
    assert all(v == U for v in row["measures"].values())
    assert row["prs"] == U
    why = _why(row)
    assert why["roundsPerPr"] == "no-records-input" and why["escapes"] == "no-misses-log-input"
    assert why["capChoices"] == "no-cap-choices-since" and why["repeatFindingLocations"] == "not-run-this-pass"
    assert set(why) == set(RM.MEASURES)


def test_a_full_window_is_measured():
    row = RM.compute(_full(), FROM, UNTIL)
    m = row["measures"]
    assert m["roundsPerPr"] == {"median": 2, "p90": 2}
    assert m["sessionsPerPr"]["shareOverOne"] == 0
    assert m["ci"] == {"runsPerPr": {"median": 1, "p90": 1}, "minutesPerPr": {"median": 4, "p90": 4},
                       "suiteMedianMinutes": 3}
    assert m["escapes"] == {"missed": 0, "seenAndLeft": 0, "falsePrClaims": 0}
    assert m["lateFindsOnUnchangedCode"] == {"basis": "monthly", "value": 0}
    assert m["panels"] == {"sizes": {"1": 1}, "withoutGrounding": 1, "sessions": 1}
    assert set(_why(row)) == {"repeatFindingLocations"}


def test_a_malformed_record_makes_the_record_measures_unmeasured_not_zero():
    row = RM.compute(_full(records=[_rec(1), {"pr": 2}]), FROM, UNTIL)
    assert row["measures"]["roundsPerPr"] == U and _why(row)["roundsPerPr"] == "incomplete-evidence"
    assert row["leftOut"]["malformed"] == 1 and row["prs"] == U


def test_records_outside_the_window_are_left_out():
    recs = [_rec(1), _rec(2, at="2026-09-30T23:00:00Z"), _rec(3, at="2026-10-08T00:00:00Z")]
    row = RM.compute(_full(records=recs), FROM, UNTIL)
    assert row["prs"] == 1 and row["leftOut"]["outsideWindow"] == 2


def test_rounds_and_sessions_per_pr_read_each_sessions_latest_record():
    recs = [_rec(1, "a", "2026-10-02T00:00:00Z", count=1), _rec(1, "a", "2026-10-03T00:00:00Z", count=3),
            _rec(1, "b", "2026-10-04T00:00:00Z", count=1), _rec(2, count=1)]
    m = RM.compute(_full(records=recs, ciRuns=[{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]), FROM, UNTIL)["measures"]
    assert m["roundsPerPr"] == {"median": 2.5, "p90": 4}
    assert m["sessionsPerPr"] == {"median": 1.5, "p90": 2, "shareOverOne": 0.5}


def test_reviewer_cost_dedupes_by_name_and_commit_and_skips_rows_that_did_not_run():
    rows_a = [_row("security-reviewer (round 1)"), _row("premortem-reviewer (round 1)", ran="not-run", tokens=None)]
    rows_b = [_row("security-reviewer (round 1)"), _row("security-reviewer (round 1)", commit="c2", tokens=50, minutes=0.5)]
    recs = [_rec(1, "a", rows=rows_a), _rec(1, "b", "2026-10-04T00:00:00Z", rows=rows_b)]
    row = RM.compute(_full(records=recs), FROM, UNTIL)
    cost = row["measures"]["reviewerCostPerPr"]
    assert cost["tokens"]["total"] == 150 and cost["minutes"]["total"] == 2.0
    assert row["measures"]["seats"]["security-reviewer"]["tokens"] == 150
    assert "premortem-reviewer" not in row["measures"]["seats"]


def test_a_seat_with_no_cost_recorded_reads_unmeasured_never_zero():
    rows = [_row("security-reviewer (round 1)"), _row("premortem-reviewer (round 1)", tokens=None, minutes=None)]
    rows_old = [{"name": "code-reviewer (round 1)", "ran": "engine-record", "commit": "c1"}]  # a record from before the cost field
    recs = [_rec(1, rows=rows), _rec(2, rows=rows_old)]
    row = RM.compute(_full(records=recs, ciRuns=[{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]), FROM, UNTIL)
    seats, why = row["measures"]["seats"], _why(row)
    assert seats["security-reviewer"]["tokens"] == 100
    assert seats["premortem-reviewer"]["tokens"] == U and why["seats.premortem-reviewer.tokens"] == "cost-not-recorded"
    assert seats["code-reviewer"]["minutes"] == U
    assert row["measures"]["reviewerCostPerPr"] == {"tokens": U, "minutes": U}
    assert why["reviewerCostPerPr.tokens"] == "cost-not-recorded"


def test_the_top_tenth_share_is_the_costliest_tenth_of_prs():
    recs = [_rec(n, rows=[_row("code-reviewer (round 1)", tokens=10 if n < 10 else 910)]) for n in range(1, 11)]
    ci = [{"pr": n, "minutes": 1} for n in range(1, 11)]
    cost = RM.compute(_full(records=recs, ciRuns=ci), FROM, UNTIL)["measures"]["reviewerCostPerPr"]["tokens"]
    assert cost["total"] == 1000 and cost["topTenthShare"] == 0.91


def test_finding_outcomes_by_lens_key_an_undecided_finding_open_and_feed_the_seating_check():
    findings = [_f("k1"), _f("k2", None), _f("k3", "craft", "Failure-Mode"), _f("k4", "fixed", "Nonesuch")]
    rows = [_row("security-reviewer (round 1)"), _row("premortem-reviewer (round 1)", tokens=7, minutes=0.2)]
    row = RM.compute(_full(records=[_rec(1, rows=rows, findings=findings)]), FROM, UNTIL)
    seats = row["measures"]["seats"]
    assert seats["security-reviewer"]["outcomes"] == {"fixed": 1, "open": 1}
    assert seats["premortem-reviewer"]["outcomes"] == {"craft": 1}
    assert seats["unattributed"] == {"outcomes": {"fixed": 1}, "tokens": U, "minutes": U}
    shown = review_learning.seating(row["seatingRow"])["seats"]
    assert shown["security"]["tokens"] == 100 and shown["premortem"]["minutes"] == 0.2
    assert shown["security"]["outcomes"]["fixed"] == 1


def test_ci_reads_unmeasured_when_a_window_pr_has_no_receipt_or_a_receipt_is_damaged():
    recs = [_rec(1), _rec(2)]
    row = RM.compute(_full(records=recs, ciRuns=[{"pr": 1, "minutes": 2}]), FROM, UNTIL)
    assert row["measures"]["ci"] == U and _why(row)["ci"] == "pr-without-ci-receipt"
    row = RM.compute(_full(ciRuns=[{"pr": 1, "minutes": "two"}]), FROM, UNTIL)
    assert _why(row)["ci"] == "incomplete-evidence"
    row = RM.compute(_full(ciRuns=[{"pr": 1, "minutes": 2}]), FROM, UNTIL)
    assert row["measures"]["ci"]["suiteMedianMinutes"] == U


def test_escapes_by_kind_count_the_window_and_keep_false_claims_apart():
    esc = [{"reviewedAt": "2026-10-02", "call": "missed"}, {"reviewedAt": "2026-10-02", "call": "seen-and-left"},
           {"reviewedAt": "2026-10-02", "call": "missed", "marker": "false-pr-claim"},
           {"reviewedAt": "2026-09-01", "call": "missed"}]
    assert RM.compute(_full(escapes=esc), FROM, UNTIL)["measures"]["escapes"] == {
        "missed": 1, "seenAndLeft": 1, "falsePrClaims": 1}
    row = RM.compute(_full(escapes=[{"call": "missed"}]), FROM, UNTIL)
    assert row["measures"]["escapes"] == U and _why(row)["escapes"] == "incomplete-evidence"


def test_vet_send_backs_count_only_loops_that_came_back_clean():
    recs = [_rec(1), _rec(2, findings=[_f("k", "left-for-owner")]), _rec(3)]
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": True, "body": ""},
            {"pr": 2, "at": "2026-10-04T00:00:00Z", "sentBack": True, "body": ""},
            {"pr": 3, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": ""}]
    ci = [{"pr": n, "minutes": 1} for n in (1, 2, 3)]
    m = RM.compute(_full(records=recs, vetReceipts=vets, ciRuns=ci), FROM, UNTIL)["measures"]
    assert m["vetSendBacksOnCleanLoops"] == {"sentBack": 1, "cleanLoopsVetted": 2}


def _cap(choice, key="k1"):
    return "<!-- superheroes:cap-choice choice=%s vet=7 record=https://x/r key=%s -->" % (choice, key)


def test_a_window_with_no_capped_handback_reads_zero_choices():
    m = RM.compute(_full(), FROM, UNTIL)["measures"]
    assert m["capChoices"] == {c: {"count": 0, "outcomes": {}} for c in RM.CAP_CHOICES}


@pytest.mark.parametrize("since", ["2026-10-02", "2026-11-01"])
def test_a_window_before_the_rework_reads_cap_choices_unmeasured(since):
    row = RM.compute(_full(capChoicesSince=since), FROM, UNTIL)
    assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == "before-cap-choice-recording"


def test_cap_choices_are_counted_with_what_happened_next():
    body = "\n".join([_cap("extra-audit-round", "k a"), _cap("rethink", "k2"), _cap("leftover", "k3")])
    recs = [_rec(1, "a", findings=[_f("k a", None)]),
            _rec(1, "b", "2026-10-05T00:00:00Z", findings=[_f("k a"), _f("k2")]), _rec(2)]
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": body},
            {"pr": 2, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": _cap("rethink")}]
    esc = [{"reviewedAt": "2026-10-03", "call": "seen-and-left", "pr": 1, "key": "k3"}]
    ci = [{"pr": 1, "minutes": 1}, {"pr": 2, "minutes": 1}]
    cap = RM.compute(_full(records=recs, vetReceipts=vets, escapes=esc, ciRuns=ci), FROM, UNTIL)["measures"]["capChoices"]
    assert cap["extra-audit-round"] == {"count": 1, "outcomes": {"settled": 1}}
    assert cap["rethink"] == {"count": 2, "outcomes": {"converged": 1, "pending": 1}}
    assert cap["leftover"] == {"count": 1, "outcomes": {"escaped": 1}}


def test_an_unknown_cap_choice_spelling_reads_unmeasured():
    vets = [{"pr": 1, "at": "2026-10-04T00:00:00Z", "sentBack": False, "body": _cap("redo")}]
    row = RM.compute(_full(vetReceipts=vets), FROM, UNTIL)
    assert row["measures"]["capChoices"] == U and _why(row)["capChoices"] == "incomplete-evidence"


@pytest.fixture
def repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    subprocess.run(["git", "init", "-q", str(d)], check=True)
    return str(d)


def _cli(tmp_path, repo, *args):
    out = subprocess.run([sys.executable, "-B", os.path.join(_LIB, "review_measures.py"), *args,
                          "--cwd", repo, "--root", str(tmp_path / "store")], capture_output=True, text=True)
    return out.returncode, json.loads(out.stdout)


def test_one_command_appends_the_row_and_a_second_run_replaces_that_windows_row(tmp_path, repo):
    inp = tmp_path / "in.json"
    inp.write_text(json.dumps(_full()))
    base = ("row", "--input", str(inp), "--until", "2026-10-07")
    code, got = _cli(tmp_path, repo, *base, "--from", "2026-10-01")
    assert code == 0 and got["outcome"] == "appended"
    inp.write_text(json.dumps(_full(records=[_rec(1, count=5)])))
    code, got = _cli(tmp_path, repo, *base, "--from", "2026-10-01")
    assert code == 0 and got["outcome"] == "replaced"
    _cli(tmp_path, repo, *base, "--from", "2026-10-02")
    with open(got["table"], encoding="utf-8") as fh:
        rows = [json.loads(x) for x in fh]
    assert [r["window"]["from"] for r in rows] == ["2026-10-01", "2026-10-02"]
    assert rows[0]["measures"]["roundsPerPr"]["median"] == 5 and all(RM.problems(r) == [] for r in rows)
    code, shown = _cli(tmp_path, repo, "render")
    assert code == 0 and "| roundsPerPr.median | 5 |" in shown["markdown"]
    assert "median rounds per PR" in shown["markdown"] and "Unmeasured: repeatFindingLocations" in shown["markdown"]


def test_the_cli_refuses_bad_dates_and_a_non_object_input(tmp_path, repo):
    inp = tmp_path / "in.json"
    inp.write_text("[]")
    code, got = _cli(tmp_path, repo, "row", "--input", str(inp), "--from", "2026-10-01", "--until", "2026-10-07")
    assert code == 1 and got["reason"] == "bad-input"
    inp.write_text("{}")
    code, got = _cli(tmp_path, repo, "row", "--input", str(inp), "--from", "2026-10-08", "--until", "2026-10-07")
    assert code == 1 and got["reason"] == "bad-input"


def test_render_with_no_table_says_so(tmp_path, repo):
    assert _cli(tmp_path, repo, "render")[1]["markdown"] == "No review-loop measures row yet."
