"""C4-A: every finding names its kind of mistake and the other places in the PR that share it; a fix is judged on all of them.

The invariants: a finding's `kindOfMistake` keeps only places on lines the PR touched (a place elsewhere goes to the
raising reviewer's outside entry), never its own citation, never twice, and a merge keeps the union including every
merged member's own citation; the fix auditor answers every named place and a place left unfixed or unanswered makes the
ruling not discharged; the per-place results are written once to the live row and the ledger entry and survive the archive
and the record; a null or blank `kindOfMistake` / `searchDescription` is removed, not refused, and counted in
`kindMissing`; a `searchDescription` is stamped with its author only at the panel and seams folds, from the executed
provenance, and never for a maker family.

T1 places kept and rendered · T2 a context-line place goes outside · T3 merges keep the union · T4 the audit arm
(a-d) · T5 results survive save, archive and render · T6 null normalization · T7 the author stamp · T8 the schemas ·
T9 the fix guidance names every place.

Bite-proof record: c4_wo1_kind
"""
import copy
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import audits  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import model_registry  # noqa: E402
import review_findings_schema as RFS  # noqa: E402
import review_record as rr  # noqa: E402
import review_record_session as rs  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_driver as RD  # noqa: E402
import round_records as RR  # noqa: E402
import test_break_it_loop as BL  # noqa: E402
import verification  # noqa: E402
from test_review_record_session import Fake, Session, extras, ledger_row, put_extras  # noqa: E402

CONSEQUENCE = "a defect stays in the change"
KIND = "unchecked retry"

# src/a.py touched head lines: 2, 3 (next to a deleted run) and 19 (added); 1, 4 and 20 are context.
DIFF = (
    "diff --git a/src/a.py b/src/a.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/src/a.py\n"
    "+++ b/src/a.py\n"
    "@@ -1,7 +1,5 @@\n"
    " l1\n l2\n-d3\n-d4\n l5\n l6\n l7\n"
    "@@ -20,3 +18,4 @@\n"
    " c18\n+add19\n c20\n c21\n")


def _place(line, file="src/a.py"):
    return {"file": file, "line": line}


def _kind(*lines, kind=KIND):
    return {"kind": kind, "places": [_place(line) for line in lines]}


def _description(**over):
    return dict({"kind": KIND, "looksLike": "a retry with no cap", "examples": ["while True: retry()"]}, **over)


def _finding(title, line=2, file="src/a.py", severity="Important", **extra):
    out = {"title": title, "file": file, "line": line, "severity": severity, "consequence": CONSEQUENCE,
           "body": "the body", "confidence": "High"}
    out.update(extra)
    return out


@pytest.fixture
def world(tmp_path):
    w = BL.World(tmp_path)
    w.state["reviewedDiff"] = DIFF
    return w


def _panel(world, ran=None, seat_map=None, **by_seat):
    """Fold one panel round whose seats return the given findings (`code_reviewer=[...]` -> seat `code-reviewer`)."""
    seats = {d: {"findings": []} for d in RD.DIMENSIONS}
    for name, found in by_seat.items():
        seats[name.replace("_", "-")] = {"findings": list(found)}
    artifact = {"seats": seats}
    if ran is not None:
        artifact["ranManifest"] = ran
    if seat_map is not None:
        artifact["seatMap"] = seat_map
    RD._fold(world.state, world.state["config"], RD.P_PANEL, artifact, session_dir=str(world.session))
    return world.state


def _hits(state):
    return [(e["source"]["name"], [(h["file"], h["line"], h["title"]) for h in e["hits"]])
            for e in state.get("outsideThisPR") or []]


def _record_body(tmp_path, **row):
    """Write the review record for a session whose one ledger row carries `row`; return the posted summary text."""
    session = Session(tmp_path / "acct", dispositionLedger=[ledger_row(**row)]).seat("code-reviewer").save()
    fake = Fake()
    assert rs.write_from_session(session, put_extras(tmp_path, extras()), str(tmp_path), fake.readers())["ok"]
    return fake.marked()[-1]["body"], rr.read(7, readers=fake.readers())


# ---- T1 ------------------------------------------------------------------------------------------------------


def test_t1_a_panel_finding_keeps_two_touched_places_and_the_record_renders_them(world, tmp_path):
    # axis: places on touched lines are kept on the compiled finding, whole — see bite-proof record c4_wo1_kind
    state = _panel(world, code_reviewer=[_finding("Retry without a cap", kindOfMistake=_kind(3, 19))])
    (staged,) = state["_toVerify"]
    assert staged["kindOfMistake"] == _kind(3, 19)
    assert "outsideThisPR" not in state
    body, record = _record_body(tmp_path, kindOfMistake=staged["kindOfMistake"])
    assert "kind of mistake: unchecked retry" in body
    assert "also in this PR: src/a.py:3, src/a.py:19 (0 of 2 fixed)" in body
    assert record["findings"][0]["kindOfMistake"] == _kind(3, 19)


# ---- T2 ------------------------------------------------------------------------------------------------------


def test_t2_a_place_on_a_context_line_leaves_places_for_the_raising_seats_outside_entry(world):
    # axis: a place on an untouched line is outside the PR: it leaves `places` for the raising seat's outside entry — see bite-proof record c4_wo1_kind
    state = _panel(world, code_reviewer=[_finding("Retry without a cap", kindOfMistake=_kind(3, 1))])
    (staged,) = state["_toVerify"]
    assert staged["kindOfMistake"] == _kind(3)  # the touched place stays, the context line (1) left
    assert _hits(state) == [("code-reviewer", [("src/a.py", 1, KIND)])]
    assert state["rounds"]["1"]["compileDrops"] == []  # an outside place is no compile drop and no refusal


def test_t2_edges_own_citation_duplicates_and_unusable_places_are_dropped_and_no_diff_keeps_places():
    # axis: a place equal to the finding's own citation, a repeat, or an unusable one is dropped from `places`, and with no diff the rest are kept unchecked
    own, dup, blank, bad_line = _place(2), _place(3), _place(3, file="  "), {"file": "src/a.py", "line": "x"}
    kom = {"kind": KIND, "places": [own, dup, dict(dup), blank, bad_line, "src/a.py:3", _place(None)]}
    compiled, drops = RD.mechanical_compile([_finding("t", kindOfMistake=kom)], None)
    assert compiled[0]["kindOfMistake"]["places"] == [_place(3), _place(None)]  # no diff: kept unchecked (E3)
    assert drops == []
    compiled, drops = RD.mechanical_compile([_finding("t", kindOfMistake={"kind": KIND, "places": "not a list"})], DIFF)
    assert compiled[0]["kindOfMistake"] == {"kind": KIND, "places": []}
    compiled, drops = RD.mechanical_compile([_finding("t", kindOfMistake=_kind(None))], DIFF)  # a null line is no touched line
    assert compiled[0]["kindOfMistake"]["places"] == [] and [d["line"] for d in drops] == [None]


# ---- T3 ------------------------------------------------------------------------------------------------------


def test_t3_a_merge_keeps_the_union_of_places_and_every_members_own_citation():
    # axis: a merged-away member's own citation joins the kept finding's places — see bite-proof record c4_wo1_kind
    big = _finding("Retry without a cap", line=2, kindOfMistake=_kind(3), severity="Important")
    small = _finding("Retry without a cap", line=19, kindOfMistake=_kind(2, 20), severity="Minor")
    merged = RD._merge_same_finding(big, small)
    assert (merged["file"], merged["line"]) == ("src/a.py", 2)
    assert merged["kindOfMistake"] == _kind(3, 20, 19)  # own (2) dropped; the member's citation (19) joined
    group = verification._merge_group([small, big])
    assert (group["file"], group["line"]) == ("src/a.py", 2)
    assert group["kindOfMistake"]["places"] == _kind(3, 20, 19)["places"]
    assert group["kindOfMistake"]["kind"] == KIND


def test_t3_a_member_without_a_kind_still_leaves_its_citation_as_a_place_of_the_one_that_has_one():
    # axis: a member that names no kind still contributes its own citation as a place of the member that does, and a merge of two kindless findings gains none — see bite-proof record c4_wo1_kind
    kept = _finding("t", line=2, kindOfMistake=_kind(3), severity="Important")
    other = _finding("t", line=19, severity="Minor")
    assert RD._merge_same_finding(kept, other)["kindOfMistake"] == _kind(3, 19)
    assert "kindOfMistake" not in RD._merge_same_finding(_finding("t"), _finding("t", line=19))


# ---- T4 ------------------------------------------------------------------------------------------------------

CHECKS = {name: {"answer": "yes", "why": "checked"} for name in audits.CHECK_NAMES}


def _target(kind=None, fid="t-1"):
    row = {"id": fid, "file": "src/a.py", "line": 2, "title": "Retry without a cap", "severity": "Important",
           "auditorVendor": "codex"}
    if kind is not None:
        row["kindOfMistake"] = kind
    return row


def _audit(target, places, ruling="discharged", **extra):
    result = {"id": target["id"], "ruling": ruling, "reason": "the fix holds", "checks": CHECKS}
    if places is not None:
        result["places"] = places
    result.update(extra)
    return audits.apply_audit_results([target], [result], expected_auditors={target["id"]: "codex"},
                                      collection_manifest={target["id"]: "codex"})


def _row(line, fixed):
    return {"file": "src/a.py", "line": line, "fixed": fixed}


def test_t4_one_of_two_places_answered_unfixed_is_not_discharged_with_the_disclosure():
    # axis: every place the kind of mistake names must be answered fixed or the clearing ruling is refused — see bite-proof record c4_wo1_kind
    out = _audit(_target(_kind(3, 19)), [_row(3, True), _row(19, False)])
    assert out["discharged"] == [] and out["notDischarged"] == ["t-1"] and out["placesUnfixed"] == ["t-1"]
    (entry,) = out["audits"]
    assert entry["ruling"] == "not-discharged"
    assert "left unfixed: src/a.py:19" in entry["reason"] and "not answered" not in entry["reason"]
    assert entry["places"] == [_row(3, True), _row(19, False)]


def test_t4b_places_left_unanswered_are_not_discharged_and_disclosed():
    # axis: an absent, empty, partial or malformed `places` answer leaves the named places unanswered, so the clearing ruling is refused with the disclosure — see bite-proof record c4_wo1_kind
    for places in (None, [], [_row(3, True)], "not a list"):
        out = _audit(_target(_kind(3, 19)), places)
        assert out["discharged"] == [] and out["placesUnfixed"] == ["t-1"], places
        assert "not answered: " in out["audits"][0]["reason"]


def test_t4c_every_place_fixed_is_discharged_and_the_record_reads_all_fixed(tmp_path):
    # axis: an answer of fixed for every named place discharges the target and the record renders "all fixed"
    out = _audit(_target(_kind(3, 19)), [_row(3, True), _row(19, True)])
    assert out["discharged"] == ["t-1"] and out["placesUnfixed"] == [] and out["placesIgnored"] == []
    kind = RD._with_place_results(_kind(3, 19), {("src/a.py", p["line"]): p["fixed"] for p in out["audits"][0]["places"]})
    assert [p["fixed"] for p in kind["places"]] == [True, True]
    body, _record = _record_body(tmp_path, kindOfMistake=kind)
    assert "also in this PR: src/a.py:3, src/a.py:19 (all fixed)" in body


def test_t4_edges_an_unlisted_place_is_ignored_and_disclosed_and_a_target_without_places_is_unchanged():
    # axis: an answered place the target does not name is ignored and disclosed without blocking, and a target with no places is audited exactly as before
    out = _audit(_target(_kind(3)), [_row(3, True), _row(7, False)])
    assert out["discharged"] == ["t-1"] and out["placesIgnored"] == ["t-1"]
    assert out["audits"][0]["placesIgnored"] == [{"file": "src/a.py", "line": 7}]
    for target in (_target(), _target({"kind": KIND, "places": []})):
        out = _audit(target, None)
        assert out["discharged"] == ["t-1"] and "places" not in out["audits"][0]
    assert _audit(_target(_kind(3)), [_row(3, False)], ruling="not-discharged")["audits"][0]["places"] == [_row(3, False)]


def test_t4d_a_fix_of_only_the_representative_of_a_merged_pair_is_not_discharged():
    # axis: a merged-away member's citation is a place the audit must answer, so fixing only the representative's places is not a discharge — see bite-proof record c4_wo1_kind
    rep = _finding("Retry without a cap", line=2, kindOfMistake=_kind(3), severity="Important")
    member = _finding("Retry without a cap", line=19, kindOfMistake=_kind(3), severity="Minor")
    merged = verification._merge_group([rep, member])
    target = dict(_target(merged["kindOfMistake"]))
    out = _audit(target, [_row(3, True)])  # the representative's own place was fixed; the member's citation (19) was not
    assert out["discharged"] == [] and "not answered: src/a.py:19" in out["audits"][0]["reason"]
    assert _audit(target, [_row(3, True), _row(19, True)])["discharged"] == ["t-1"]


def test_t4_the_submit_guard_judges_the_places_answer():
    # axis: the submit guard refuses a malformed `places` answer (and accepts a well-formed or absent one) through the same judge the fold uses
    assert audits.place_answers_fault({"places": [_row(3, True)]}) is None
    assert audits.place_answers_fault({}) is None and audits.place_answers_fault({"places": None}) is None
    for bad in ("x", [{"file": "", "line": 1, "fixed": True}], [{"file": "a", "line": "1", "fixed": True}],
                [{"file": "a", "line": 1, "fixed": "yes"}], ["a"]):
        assert audits.place_answers_fault({"places": bad}) is not None, bad
    contract, reason = RD.payload_contracts.payload_contract(RD.P_AUDITS)
    assert reason is None and "places" in contract["optional"]
    target = _target(_kind(3))
    good = {"results": [{"id": "t-1", "ruling": "not-discharged", "reason": "no", "checks": CHECKS,
                         "places": [_row(3, True)]}]}
    assert RD.audit_results_fault(good, [target]) is None
    bad = {"results": [dict(good["results"][0], places="src/a.py:3")]}
    assert "places" in RD.audit_results_fault(bad, [target])


# ---- T5 ------------------------------------------------------------------------------------------------------


def test_t5_place_results_survive_save_reload_audit_archive_and_render(world, tmp_path):
    # axis: the per-place results land on the live row and the ledger entry together, and survive the archive and the record — see bite-proof record c4_wo1_kind
    state = _panel(world, code_reviewer=[_finding("Retry without a cap", kindOfMistake=_kind(3, 19))])
    (staged,) = state["_toVerify"]
    key = RD._finding_identity_key(staged)
    state["findings"] = [copy.deepcopy(staged)]  # the live copy the fold keeps
    state = json.loads(json.dumps(state))  # save and reload
    state["_auditTargets"] = [dict(_target(_kind(3, 19), fid=key), independence="independent")]
    state["_verifyThen"] = RD.VERIFY_THEN_POST_AUDITS
    result = {"id": key, "ruling": "discharged", "reason": "the fix holds", "checks": CHECKS,
              "places": [_row(3, True), _row(19, False)]}
    # the audit fold itself writes the answers: removing its enrichment step fails this test
    RD._fold(state, state["config"], RD.P_AUDITS, {"results": [result], "collectionManifest": {key: "codex"}},
             session_dir=str(world.session))
    live = state["findings"][0]["kindOfMistake"]["places"]
    held = state["dispositionLedger"][0]["kindOfMistake"]["places"]
    assert [p.get("fixed") for p in live] == [True, False] and live == held
    # the departing live copy (a fresh row without results) replaces the ledger entry and keeps the results
    fresh = copy.deepcopy(state["findings"][0])
    fresh["kindOfMistake"]["places"] = [_place(3), _place(19)]
    RD._archive_departures(state, [fresh])
    assert [p.get("fixed") for p in state["dispositionLedger"][0]["kindOfMistake"]["places"]] == [True, False]
    # the live row without results and the ledger row with them: the record reads "n of m fixed"
    live_row = {"findingKey": key, "id": "f-1", "title": "Retry without a cap", "severity": "Important",
                "file": "src/a.py", "line": 2, "kindOfMistake": {"kind": KIND, "places": [_place(3), _place(19)]}}
    parts = rs._finding_parts(live_row, state["dispositionLedger"][0])
    assert [p.get("fixed") for p in parts["kindOfMistake"]["places"]] == [True, False]
    body, _record = _record_body(tmp_path, kindOfMistake=parts["kindOfMistake"])
    assert "(1 of 2 fixed)" in body


def test_t5_place_answers_reach_the_rows_of_members_merged_into_the_audited_finding(tmp_path):
    # axis: a merged member's own row takes the audited representative's answer for each place it names that the audit answered, and a place the audit did not answer keeps `fixed` unset — see bite-proof record c4_wo1_kind
    def row(key, line, kind, **extra):
        return dict(_finding("Retry without a cap", line=line, kindOfMistake=kind), findingKey=key, **extra)

    rep = row("k-rep", 2, _kind(3, 19))
    shared = row("k-shared", 19, _kind(3, 2), mergedInto="k-rep")  # names only places the audit answered
    partial = row("k-partial", 20, _kind(3, 7), mergedInto="k-rep")  # names a place (7) the audit did not answer
    stranger = row("k-other", 4, _kind(3, 19))  # not merged into the audited finding: its places are not answered
    rows = [rep, shared, partial, stranger]
    state = {"findings": copy.deepcopy(rows), "dispositionLedger": copy.deepcopy(rows)}
    # the real audit output: line 2 is the representative's own place, which the audit ignores even when answered
    outcome = _audit(_target(rep["kindOfMistake"], fid="k-rep"), [_row(3, True), _row(19, True), _row(2, True)])
    RD._record_place_results(state, outcome["audits"])
    for holder in (state["findings"], state["dispositionLedger"]):
        by_key = {r["findingKey"]: r["kindOfMistake"]["places"] for r in holder}
        assert [p.get("fixed") for p in by_key["k-rep"]] == [True, True]
        assert [p.get("fixed") for p in by_key["k-shared"]] == [True, True]
        assert [p.get("fixed") for p in by_key["k-partial"]] == [True, None]  # 7 was never answered: unset
        assert [p.get("fixed") for p in by_key["k-other"]] == [None, None]
    # the record shows a merged member's places as fixed once the shared places were repaired, and an unanswered one open
    shared_row = next(r for r in state["dispositionLedger"] if r["findingKey"] == "k-shared")
    body, _record = _record_body(tmp_path, kindOfMistake=shared_row["kindOfMistake"])
    assert "also in this PR: src/a.py:3, src/a.py:2 (all fixed)" in body
    partial_row = next(r for r in state["dispositionLedger"] if r["findingKey"] == "k-partial")
    (tmp_path / "partial").mkdir()
    body, _record = _record_body(tmp_path / "partial", kindOfMistake=partial_row["kindOfMistake"])
    assert "also in this PR: src/a.py:3, src/a.py:7 (1 of 2 fixed)" in body


def test_t5_a_weakened_test_is_blocked_even_when_a_place_is_unanswered():
    # axis: a weakened committed test is blocked before an incomplete-place return, so the mandatory restore is scheduled — see bite-proof record c4_wo1_kind
    target = dict(_target(_kind(3, 19)), breakIt={"match": "changed-explained", "path": "tests/test_a.py"})
    out = _audit(target, [], testMatch={"answer": "weakened", "why": "coverage narrowed"})
    assert out["testMismatch"] == ["t-1"] and out["notDischarged"] == ["t-1"] and out["discharged"] == []
    assert out["audits"][0]["testMatch"]["blocking"] is True


def test_t5_a_narrower_reraise_keeps_the_places_an_unresolved_target_still_owes():
    # axis: the kept entry owes every place a deduplicated sibling still names — see bite-proof record c4_wo1_kind
    fresh = _finding("Retry without a cap", line=2)  # the scoped finder's report names no kind
    held = dict(fresh, kindOfMistake={"kind": KIND, "places": [dict(_place(3), fixed=True), _place(19)]})
    (batch,) = RD._union_open_blockers([fresh], [held])
    assert batch["kindOfMistake"]["kind"] == KIND
    assert batch["kindOfMistake"]["places"] == [dict(_place(3), fixed=True), _place(19)]


def test_t5_a_reraise_and_an_open_blocker_dedup_keep_the_places_but_gain_no_description(world):
    # axis: a re-raise and an open-blocker dedup keep the places the earlier report still owes but never give the kept finding a search description it did not name — see bite-proof record c4_wo1_kind
    state = world.state
    fresh = _finding("Retry without a cap", line=2)  # the new report names neither a kind nor a description
    owed = {"kind": KIND, "places": [dict(_place(3), fixed=True), _place(19)]}
    held = dict(fresh, kindOfMistake=owed, searchDescription=_description())
    (batch,) = RD._union_open_blockers([fresh], [held])  # the open-blocker dedup
    assert batch["kindOfMistake"]["places"] == owed["places"]
    assert "searchDescription" not in batch
    key = RD._finding_identity_key(fresh)
    ledger, seen = [dict(held, findingKey=key)], {key: 0}
    entry = RD._seed_ledger_entry(state, ledger, seen, dict(fresh), key, 2)  # the re-raise of an unresolved finding
    assert entry["kindOfMistake"]["places"] == owed["places"]
    assert "searchDescription" not in entry
    # a finding that did name a description keeps its own on both paths
    named = dict(fresh, searchDescription=_description(looksLike="its own"))
    (batch,) = RD._union_open_blockers([named], [held])
    assert batch["searchDescription"]["looksLike"] == "its own"


# ---- T6 ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, "text", ["a"], {"kind": "  ", "places": []}, {"places": []}])
def test_t6_a_null_or_blank_kind_of_mistake_is_removed_counted_and_never_refused(world, tmp_path, bad):
    # axis: a null, non-object or blank-kind member is removed from the finding, which stays — see bite-proof record c4_wo1_kind
    state = _panel(world, code_reviewer=[
        _finding("Retry without a cap", kindOfMistake=bad, searchDescription=bad),
        _finding("Another defect", line=3, kindOfMistake=_kind(2))])
    staged = {f["title"]: f for f in state["_toVerify"]}
    assert set(staged) == {"Retry without a cap", "Another defect"}  # the finding itself is kept
    assert "kindOfMistake" not in staged["Retry without a cap"] and "searchDescription" not in staged["Retry without a cap"]
    assert state["rounds"]["1"]["kindMissing"] == 1
    body, record = _record_body(tmp_path, title="Retry without a cap")
    assert record["findings"][0]["title"] == "Retry without a cap" and "kind of mistake" not in body
    # a null that reaches the account from a live row is not carried either: the record would refuse it
    assert "kindOfMistake" not in rs._finding_parts({"kindOfMistake": None}, None)


def test_t6_kind_missing_counts_every_compile_and_is_zero_when_all_findings_name_a_kind(world):
    # axis: `kindMissing` counts exactly the compiled findings without a usable kind of mistake, and is zero when every one names a kind
    state = _panel(world, code_reviewer=[_finding("a", kindOfMistake=_kind())])
    assert state["rounds"]["1"]["kindMissing"] == 0
    stats = {}
    RD.mechanical_compile([_finding("a"), _finding("b", line=3, kindOfMistake=_kind())], DIFF, stats=stats)
    assert stats == {"compiled": 2, "kindMissing": 1}


def test_t6_the_first_panel_wave_adds_its_kind_missing_count_to_the_one_an_earlier_audit_recorded(world):
    # axis: the panel's `kindMissing` is added to the count the round already holds (an audit that ran before the panel), never written over it, and with no earlier count it is the panel's own — see bite-proof record c4_wo1_kind
    RD._add_kind_missing(world.state, 2)  # what an audit of a full returning review recorded before the panel
    state = _panel(world, code_reviewer=[_finding("a"), _finding("b", line=3, kindOfMistake=_kind())])
    assert state["rounds"]["1"]["kindMissing"] == 3  # 2 held + the panel's 1 finding without a kind


# ---- T7 ------------------------------------------------------------------------------------------------------

INDEPENDENT = "codex"


def _author_of(state, title="Retry without a cap"):
    (staged,) = [f for f in state["_toVerify"] if f["title"] == title]
    return staged.get("searchDescription", {}).get("author", "unstamped")


def test_t7_an_author_is_stamped_from_the_executed_provenance(world):
    # axis: the author is the executed vendor and its family — see bite-proof record c4_wo1_kind
    state = _panel(world, ran={"code-reviewer": INDEPENDENT},
                   code_reviewer=[_finding("Retry without a cap", kindOfMistake=_kind(3), searchDescription=_description())])
    assert _author_of(state) == {"seat": "code-reviewer", "vendor": INDEPENDENT,
                                 "family": model_registry.family_for("reviewer", INDEPENDENT)}
    assert state["_toVerify"][0]["searchDescription"]["examples"] == ["while True: retry()"]


@pytest.mark.parametrize("ran", [None, {}, {"code-reviewer": "not-a-vendor"}, {"code-reviewer": 7}])
def test_t7_unavailable_provenance_leaves_the_description_unstamped(world, ran):
    # axis: a missing, empty, unknown-vendor or non-string executed provenance leaves the description unstamped
    state = _panel(world, ran=ran,
                   code_reviewer=[_finding("Retry without a cap", searchDescription=_description())])
    assert _author_of(state) == "unstamped"


def test_t7_a_transport_row_naming_an_independent_vendor_does_not_stamp_when_the_executed_family_is_a_maker(world):
    # axis: the stamp reads the executed provenance, never the configured transport row, and a maker family is never stamped — see bite-proof record c4_wo1_kind
    seat_map = {"seats": {"code-reviewer": {"vendor": INDEPENDENT, "source": "pinned"}}}
    state = _panel(world, ran={"code-reviewer": "claude"}, seat_map=seat_map,
                   code_reviewer=[_finding("Retry without a cap", searchDescription=_description())])
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"  # the seat ran: only the stamp is withheld
    assert state["config"]["fixerVendor"] == "claude"
    assert _author_of(state) == "unstamped"


def test_t7_a_known_maker_family_is_never_stamped(world):
    # axis: a maker family is never stamped even when the host family is known, so the family resolves and only the maker bar withholds the stamp — see bite-proof record c4_wo1_kind
    seat_map = {"seats": {"code-reviewer": {"vendor": "claude", "source": "pinned"}},
                "hostFamily": "claude", "makerFamilies": ["claude"]}
    state = _panel(world, ran={"code-reviewer": "claude"}, seat_map=seat_map,
                   code_reviewer=[_finding("Retry without a cap", searchDescription=_description())])
    assert state["rounds"]["1"]["seatStatus"]["code-reviewer"] == "run"  # the seat ran: only the stamp is withheld
    assert _author_of(state) == "unstamped"


@pytest.mark.parametrize("ran,expected", [(None, "unstamped"), ({"code-reviewer": INDEPENDENT}, INDEPENDENT)])
def test_t7_a_payload_supplied_author_is_removed_and_replaced_only_by_the_driver_stamp(world, ran, expected):
    # axis: an `author` that arrives inside a payload is removed before the fold reads it — see bite-proof record c4_wo1_kind
    forged = _description(author={"seat": "x", "vendor": "x", "family": "x"})
    state = _panel(world, ran=ran, code_reviewer=[_finding("Retry without a cap", searchDescription=forged)])
    author = _author_of(state)
    assert author == "unstamped" if expected == "unstamped" else author["vendor"] == expected


def test_t7_a_search_description_from_any_other_phase_carries_no_author(world, monkeypatch):
    # axis: a description arriving in the synthesis, scoped or audit-result payloads loses any `author` it carries, without rewriting the submitted artifact — see bite-proof record c4_wo1_kind
    seen = {}
    monkeypatch.setattr(RD, "_fold_synthesis", lambda state, config, artifact, session_dir=None: seen.update(syn=artifact))
    forged = _description(author={"seat": "x", "vendor": "x", "family": "x"})
    RD._fold(world.state, world.state["config"], RD.P_SYNTHESIS,
             {"grouping": None, "findings": [_finding("t", searchDescription=forged)]})
    assert "author" not in seen["syn"]["findings"][0]["searchDescription"]
    assert "author" in forged  # the submitted artifact itself was not rewritten
    RD._fold(world.state, world.state["config"], RD.P_SCOPED, {"findings": [_finding("From scoped", searchDescription=forged)]})
    (staged,) = [f for f in world.state["_toVerify"] if f["title"] == "From scoped"]
    assert "author" not in staged["searchDescription"] and staged["searchDescription"]["kind"] == KIND
    # a nested authors anywhere in a payload are removed; a payload with none is returned as is
    payload = {"results": [{"newIssues": [{"searchDescription": forged}]}]}
    stripped, changed = RD._without_search_authors(payload)
    assert changed and "author" not in stripped["results"][0]["newIssues"][0]["searchDescription"]
    same, changed = RD._without_search_authors({"findings": [{"searchDescription": _description()}]})
    assert not changed


@pytest.mark.parametrize("ran,stamped", [({RD.SEAMS_SEAT_KEY: INDEPENDENT}, True), ({RD.SEAMS_SEAT_KEY: "claude"}, False),
                                         (None, False)])
def test_t7_the_seams_fold_stamps_from_the_artifacts_executed_provenance(world, ran, stamped):
    # axis: the seams fold stamps from the artifact's executed vendor, and a maker family or no provenance leaves the description unstamped
    state = world.state
    artifact = {"findings": [_finding("From seams", searchDescription=_description())]}
    if ran is not None:
        artifact["ranManifest"] = ran
    RD._fold_seams(state, state["config"], artifact)
    author = _author_of(state, "From seams")
    assert (author["seat"] == RD.SEAMS_SEAT_KEY) if stamped else author == "unstamped"


def _seams_envelope(source, findings):
    """The runner's v2 landing for the seams-check seat: execution evidence names the vendor that ran it."""
    return {"schema": RR.SEAT_RESULT_SCHEMA_V2, "seat": RA.SEAT_SEAMS, "attempt": 0, "vendor": source, "model": "m",
            "provenance": RR.PROVENANCE_DISPATCH_OBSERVED, "executionEvidence": {"source": source},
            "payload": {"findings": findings}}


@pytest.mark.parametrize("envelope,stamped", [
    (_seams_envelope(INDEPENDENT, [_finding("From seams", searchDescription=_description())]), True),
    (_seams_envelope("claude", [_finding("From seams", searchDescription=_description())]), False),
    # a landing with no runner evidence (a v1 envelope, no dispatch manifest) names no executed vendor
    ({"schema": RR.SEAT_RESULT_SCHEMA, "seat": RA.SEAT_SEAMS, "attempt": 0, "vendor": INDEPENDENT, "model": "m",
      "payload": {"findings": [_finding("From seams", searchDescription=_description())]}}, False)])
def test_t7_the_durable_seams_artifact_the_adapter_assembles_is_stamped_through_the_fold(world, envelope, stamped):
    # axis: the adapter carries the executed vendor into the seams artifact so the fold stamps the author on the durable path, and a maker family or no runner evidence leaves the description unstamped — see bite-proof record c4_wo1_kind
    state = world.state
    artifact, reason = RA.assemble(RD.P_SEAMS, [envelope], state, state["config"])
    assert reason is None, reason
    assert ("ranManifest" in artifact) is (envelope["schema"] == RR.SEAT_RESULT_SCHEMA_V2)
    RD._fold_seams(state, state["config"], artifact)  # the artifact as the adapter built it, no hand-built map
    author = _author_of(state, "From seams")
    if stamped:
        assert author == {"seat": RD.SEAMS_SEAT_KEY, "vendor": INDEPENDENT,
                          "family": model_registry.family_for("reviewer", INDEPENDENT)}
    else:
        assert author == "unstamped"


# ---- T8 ------------------------------------------------------------------------------------------------------


def test_t8_the_shipped_and_built_schemas_are_strict_valid_and_the_example_validates():
    # axis: the shipped and built schemas carry the new members strictly, the example validates, and the fallback literals stay aligned with the shipped file
    jsonschema = pytest.importorskip("jsonschema")
    with open(RFS.REVIEW_FINDINGS_SCHEMA_PATH, encoding="utf-8") as fh:
        shipped = json.load(fh)
    ERC.assert_strict_mode_valid(shipped)
    for kind in ("findings", "ruling"):
        ERC.assert_strict_mode_valid(ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind=kind))
    ERC.assert_strict_mode_valid(ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW))
    jsonschema.validate(RFS.example_findings_object(), shipped)
    member = RFS.example_findings_object()["findings"][0]
    assert member["kindOfMistake"]["places"] and member["searchDescription"]["examples"]
    assert RFS.member_carries_sentinel(member) is True  # an echoed example still grades hollow
    ruling = ERC._branch_payload_schema("ruling")["properties"]["places"]
    assert ruling["type"] == ["array", "null"] and ruling["items"]["required"] == ["file", "line", "fixed"]
    items = ERC._branch_payload_schema("findings")["items"]
    assert {"kindOfMistake", "searchDescription"} <= set(items["required"])
    assert "author" not in items["properties"]["searchDescription"]["properties"]
    shipped_props = shipped["properties"]["findings"]["items"]["properties"]
    for key in ("kindOfMistake", "searchDescription"):  # the fallback literals stay aligned with the shipped schema
        assert RFS._FALLBACK_FINDING_PROPERTY_SCHEMAS[key] == ERC._sanitize_schema_node(shipped_props[key]), key
    assert RFS._FALLBACK_CANONICAL_MEMBER_KEYS == tuple(shipped_props)


def test_t6_the_copy_locations_a_sibling_names_ride_every_audit_context(world):
    # axis: a repair named only in a sibling finding's kind of mistake is attributable by the auditor of the other finding — see bite-proof record c4_wo1_kind
    state = world.state
    first = _finding("First defect", line=2)
    second = _finding("Second defect", line=40, kindOfMistake=_kind(41, 77))
    state["fixBatch"] = [first, second]
    state["findings"] = [dict(first), dict(second), _finding("Outside defect", line=90, kindOfMistake=_kind(91))]
    targets = RD._audit_targets(state, state["config"], {})
    by_title = {t["title"]: t for t in targets}
    (sibling,) = by_title["First defect"]["batchFindings"]
    assert sibling["kindOfMistake"] == {"kind": KIND, "places": [_place(41), _place(77)]}
    (outside,) = by_title["First defect"]["roundFindings"]
    assert outside["kindOfMistake"] == {"kind": KIND, "places": [_place(91)]}
    assert "kindOfMistake" not in by_title["First defect"]


# ---- T9 ------------------------------------------------------------------------------------------------------


def test_t9_the_fix_guidance_names_every_place_for_a_batch_with_places_and_a_batch_without_has_none(world, tmp_path):
    # axis: a batch with a finding that names other places of its kind of mistake guides the fix to cover every one of them — see bite-proof record c4_wo1_kind
    state = world.state
    state["_fixBatch"] = [{"title": "Retry without a cap", "file": "src/a.py", "line": 2, "kindOfMistake": _kind(3, 19)}]
    placed_dir = str(tmp_path / "with-places")
    os.makedirs(placed_dir)
    fields = RD._apply_fixes_payload_fields(placed_dir, state, 1, 0)
    assert fields["guidancePath"] is not None
    with open(fields["guidancePath"], encoding="utf-8") as fh:
        assert RD.KIND_PLACES_GUIDANCE in fh.read()
    state["_fixBatch"] = [{"title": "Retry without a cap", "file": "src/a.py", "line": 2,
                           "kindOfMistake": {"kind": KIND, "places": []}},
                          {"title": "Another defect", "file": "src/a.py", "line": 3}]
    bare_dir = str(tmp_path / "without-places")
    os.makedirs(bare_dir)
    assert RD._apply_fixes_payload_fields(bare_dir, state, 1, 0)["guidancePath"] is None  # no place, no guidance file
