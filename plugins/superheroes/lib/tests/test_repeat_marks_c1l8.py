"""Repeat marks in the review loop's synthesis step (C1-L8, WO-A).

Each new finding of a round that repeats one of the PR's earlier findings is marked, and the decision table
(`repeat_marks.decide`, the one decision home) says whether it keeps the earlier outcome. A kept repeat never
reaches the fix or an owner hold; a repeat the table does not keep routes as a new finding; every repeat
carries `repeatOf` on its ledger row.

Edges: T1-T7 the seven rows of the decision table · T8 `code_changed` fails closed · T9 the `--earlier-findings`
file's readings and the pool entries (a malformed entry is never matched) · T10 pool order and refs · FR-18 a
same-root-cause group is still one finding and one fix row · FR-19 a reworded finding named by the judge repeats
a session finding, a new finding repeats a record finding, and the fold reads only the pre-staging snapshot ·
FR-20 a refuted repeat of a fixed finding keeps `fixed`, a confirmed one is new · FR-21 a shown-wrong finding
raised again is new when the code changed and kept when it did not · FR-22 a kept craft or left-for-owner repeat
reaches no fix batch or owner hold · mixed group, all-kept group, repeat-only synthesis, exact-only marking when
no seat judges, exact identity over the judge's name, the validated and bound repeat name, the execution-evidence
binding, the strict-mode schema and the adapter carry, the `--earlier-findings` flag, the order and its sidecar.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/c1l8_wo_a_repeat_marks.md
"""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import engine_adapter as EA  # noqa: E402
import engine_dispatch as ED  # noqa: E402
import engine_result_channel as ERC  # noqa: E402
import payload_contracts as PC  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_records as RR  # noqa: E402
import session_checkout as SCO  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402

RD = TRD.RD
SC = RD.session_contract
RM = RD.repeat_marks
V = RD.verification

_CONSEQUENCE = "a reviewer-found defect stays in the change"
_WRONG = {"verdict": "wrong", "reason": "the guard at line 40 returns early"}


# ---- fixtures and helpers ---------------------------------------------------------------------

def _git(root, *args):
    """git in the fixture repo: no user or system config, an inline identity, no signing."""
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        ["git", "-c", "user.name=superheroes-test", "-c", "user.email=superheroes-test@example.invalid",
         "-c", "commit.gpgsign=false", "-C", root, *args],
        check=True, capture_output=True, text=True, env=env).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A real repo with three heads: `first`, `changed` (a different tree) and `same` (changed's tree)."""
    root = str(tmp_path / "repo")
    os.makedirs(root)
    with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as fh:
        fh.write("one\n")
    first = SCO.make_checkout(root)
    with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as fh:
        fh.write("two\n")
    _git(root, "commit", "-a", "-q", "-m", "change the tree")
    changed = _git(root, "rev-parse", "HEAD")
    _git(root, "commit", "-q", "--allow-empty", "-m", "same tree")
    return SimpleNamespace(root=root, first=first, changed=changed, same=_git(root, "rev-parse", "HEAD"))


def _raw(title, line=1, **extra):
    return dict({"severity": "Important", "file": "f.py", "consequence": _CONSEQUENCE},
                title=title, line=line, **extra)


def _key(raw):
    return SC.finding_identity_key(raw)


def _state(repo_root=None, **over):
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": "d", "fixerVendor": "codex",
           "seatMap": {"hostFamily": "anthropic"}}
    if repo_root:
        cfg["repoRoot"] = repo_root
    cfg.update(over)
    return RD.new_state(cfg)


def _compile(raws):
    return RD.mechanical_compile([dict(r) for r in raws], None)[0]


def _anchors(state, heads):
    """The verifier-phase orders anchors the fold reads a round's judged head from."""
    state["_ordersAnchors"] = {"%s:%s:1" % (rnd, RD.P_VERIFIERS): {"headSha": sha} for rnd, sha in heads.items()}


def _earlier(state, raw, disposition, grade=None, **fields):
    """Raise ``raw`` in the state's current round and close it with ``disposition``, as an earlier round did."""
    RD._stage_findings(state, _compile([raw]))
    key = _key(raw)
    if grade:
        RD._record_grade(state, key, grade)
    RD._record_disposition(state, key, disposition, state["round"], **fields)
    return key


def _verify(state, raws, verdicts):
    """Stage ``raws`` and fold the verifier's ``verdicts`` ({title: CONFIRMED | PLAUSIBLE | REFUTED}); a
    title without a verdict is left unverified."""
    RD._stage_findings(state, _compile(raws))
    vs = []
    for staged in V.stage_ids(state["_toVerify"]):
        verdict = verdicts.get(staged["title"])
        if verdict is not None:
            vs.append(dict({"id": staged["id"], "verdict": verdict, "reason": "checked: " + verdict},
                           **({"evidence": "ran"} if verdict == "CONFIRMED" else {})))
    RD._fold_verifiers(state, state["config"], {
        "verdicts": vs, "verifierVendor": RD._nonpanel_selection(state, None, RD.P_VERIFIERS)[0]})


def _payload(state):
    return RD._advance(state, state["config"])["payload"]


def _ids(state):
    payload = _payload(state)
    return {f["title"]: f["id"] for f in payload["findings"] + payload["refuted"]}


def _group(*ids, ref=None, group_id="g"):
    return {"group_id": group_id, "member_ids": list(ids), "repeatOf": ref}


def _synth(state, grouping):
    """The submit check, then the fold, on the pending synthesis step."""
    fault = RD.synthesis_staged_id_fault(state, {"grouping": grouping})
    assert fault is None, fault
    RD._fold_synthesis(state, state["config"], {"grouping": grouping})


def _ledger(state):
    return {SC.finding_identity_key(row): row for row in state[SC.DISPOSITION_LEDGER_KEY]}


def _row(state, raw):
    return _ledger(state)[_key(raw)]


def _titles(state):
    return [f["title"] for f in state.get("findings") or []]


def _batch(state):
    return [f["title"] for f in state.get("_fixBatch") or []]


def _record_finding(raw, outcome, **extra):
    return dict(raw, findingKey=RM.opaque_key(raw), outcome=outcome, **extra)


def _record_payload(findings, sha="a" * 40):
    return {"ok": True, "findings": findings, "finalCommit": {"sha": sha}}


# ---- the decision table (one test per row) ----------------------------------------------------

def test_t1_a_fixed_finding_raised_again_and_found_wrong_is_kept_and_the_fix_holds():
    assert RM.decide("fixed", "wrong", False) == (True, True)
    assert RM.decide("fixed", "wrong", True) == (True, True)


@pytest.mark.parametrize("grade", ["confirmed", "plausible", None])
def test_t2_a_fixed_finding_raised_again_with_any_other_grade_is_a_new_finding(grade):
    assert RM.decide("fixed", grade, False) == (False, False)
    assert RM.decide("fixed", grade, True) == (False, False)


def test_t3_a_shown_wrong_finding_after_a_code_change_and_found_wrong_again_is_kept():
    assert RM.decide("shown-wrong", "wrong", True) == (True, None)


@pytest.mark.parametrize("grade", ["confirmed", "plausible", None])
def test_t4_a_shown_wrong_finding_after_a_code_change_with_any_other_grade_is_new(grade):
    assert RM.decide("shown-wrong", grade, True) == (False, None)


@pytest.mark.parametrize("grade", ["wrong", "confirmed", "plausible", None])
def test_t5_a_shown_wrong_finding_on_unchanged_code_is_kept_whatever_the_grade(grade):
    assert RM.decide("shown-wrong", grade, False) == (True, None)


def test_t5_the_change_is_read_only_for_a_shown_wrong_outcome_and_unknown_counts_as_changed(monkeypatch):
    reads = []

    def changed():
        reads.append(1)
        return True

    for outcome in ("fixed", "craft", "left-for-owner", "ruling"):
        RM.decide(outcome, "confirmed", changed)
    assert reads == []
    assert RM.decide("shown-wrong", "confirmed", changed) == (False, None)
    assert reads == [1]


@pytest.mark.parametrize("outcome", ["craft", "left-for-owner", "ruling"])
@pytest.mark.parametrize("grade", ["wrong", "confirmed", None])
def test_t6_a_settled_outcome_is_kept_whatever_the_grade_and_the_code(outcome, grade):
    assert RM.decide(outcome, grade, True) == (True, None)
    assert RM.decide(outcome, grade, False) == (True, None)


def test_t6_an_out_of_scope_ledger_row_counts_as_a_ruling_and_a_refuted_one_as_shown_wrong():
    assert RM.outcome_of("out-of-scope") == "ruling"
    assert RM.outcome_of("refuted") == "shown-wrong"
    assert RM.outcome_of("fixed") == "fixed" and RM.outcome_of("left-for-owner") == "left-for-owner"
    assert RM.outcome_of("shown-wrong") is None and RM.outcome_of(None) is None


@pytest.mark.parametrize("grade", ["wrong", "confirmed", None])
def test_t7_an_undecided_earlier_finding_is_a_new_finding(grade):
    assert RM.decide(None, grade, False) == (False, None)
    assert RM.decide("open", grade, True) == (False, None)


# ---- the code-changed read (edge 4) -----------------------------------------------------------

def test_t8_code_changed_reads_the_tree_and_a_head_or_git_failure_counts_as_changed(repo):
    assert RM.code_changed(repo.root, repo.first, repo.changed) is True
    assert RM.code_changed(repo.root, repo.changed, repo.same) is False
    assert RM.code_changed(repo.root, None, repo.same) is True
    assert RM.code_changed(repo.root, repo.changed, "") is True
    assert RM.code_changed(repo.root, "-oops", repo.same) is True
    assert RM.code_changed(repo.root, "0" * 40, repo.same) is True
    assert RM.code_changed(repo.root + "-absent", repo.changed, repo.same) is True
    assert RM.code_changed(None, repo.changed, repo.same) is True


# ---- the earlier-findings file (edge 1, edge 2) -----------------------------------------------

def test_t9_a_record_reads_into_pool_entries_with_its_judged_head():
    keep = _record_finding(_raw("kept", id="R-1"), "craft")
    entries, reason = RM.read_earlier_findings(_record_payload([keep], sha="b" * 40))
    assert reason is None
    assert [(e["source"], e["key"], e["id"], e["outcome"], e["head"]) for e in entries] == [
        ("record", keep["findingKey"], "R-1", "craft", "b" * 40)]


def test_t9_only_a_missing_record_is_silent_every_other_refusal_names_its_reason():
    assert RM.read_earlier_findings({"ok": False, "reason": "review-record-missing"}) == ([], None)
    assert RM.read_earlier_findings({"ok": False, "reason": "review-record-unreadable"}) == (
        [], "review-record-unreadable")
    assert RM.read_earlier_findings({"ok": False}) == ([], "refused")
    for malformed in ([], "x", None, {"findings": []}, {"ok": True, "findings": "x"}):
        assert RM.read_earlier_findings(malformed) == ([], "malformed"), malformed


def test_t9_a_record_finding_without_a_key_or_file_and_title_or_an_outcome_is_never_pooled():
    rows = [
        _record_finding(_raw("good"), "ruling"),
        {"outcome": "craft", "title": "titled only"},                          # no stored key, no file
        {"outcome": "craft", "file": "f.py"},                                   # no stored key, no title
        {"findingKey": "", "outcome": "craft"},                                 # empty key, nothing to mint
        _raw("undecided", line=3),                                               # no outcome: still open
        dict(_raw("odd outcome", line=4), findingKey="rr1:x", outcome="open"),  # not an outcome
        "not a dict", None, 7,
    ]
    entries, reason = RM.read_earlier_findings(_record_payload(rows))
    assert reason is None
    assert [e["title"] for e in entries] == ["good"]
    minted = {"outcome": "craft", "file": "f.py", "title": "no stored key", "line": 9}
    entries, _ = RM.read_earlier_findings(_record_payload([minted]))
    assert entries[0]["key"] == RM.opaque_key(minted)


def test_t9_the_file_reading_names_a_missing_unreadable_or_not_json_file(tmp_path):
    missing = str(tmp_path / "absent.json")
    assert RM.read_file(missing) == (None, [], "file-missing")
    assert RM.read_file(str(tmp_path)) == (None, [], "unreadable")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert RM.read_file(str(bad)) == (None, [], "not-json")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(_record_payload([_record_finding(_raw("a"), "craft")])), encoding="utf-8")
    payload, entries, reason = RM.read_file(str(good))
    assert payload["ok"] is True and len(entries) == 1 and reason is None


def test_t10_the_pool_lists_session_rows_then_record_findings_with_refs_from_e1():
    state = _state()
    _earlier(state, _raw("session one", line=1), "fixed")
    _earlier(state, _raw("session two", line=2), "refuted", refutedReason="guard holds")
    RD._stage_findings(state, _compile([_raw("still open", line=3)]))
    ledger = state[SC.DISPOSITION_LEDGER_KEY]
    record = [RM.record_entry(_record_finding(_raw("record one", line=4), "craft"), "c" * 40)]
    pool = RM.build_pool(ledger, 2, record)
    assert [(e["ref"], e["title"], e["outcome"]) for e in pool] == [
        ("e1", "session one", "fixed"), ("e2", "session two", "shown-wrong"), ("e3", "record one", "craft")]
    assert [sorted(e) for e in RM.order_list(pool)] == [sorted(["ref", "id", "file", "line", "title", "outcome"])] * 3
    # a decision of the current round, or a record finding the session already holds, is not listed again
    assert [e["title"] for e in RM.build_pool(ledger, 1, [])] == []
    held = RM.record_entry(_record_finding(_raw("session one", line=1), "fixed"), "c" * 40)
    assert [e["title"] for e in RM.build_pool(ledger, 2, [held])] == ["session one", "session two"]


def test_t10_exact_match_reads_a_session_raw_key_and_a_record_stored_key():
    session = RM.session_entry(
        dict(_compile([_raw("s")])[0], disposition="craft", dispositionRound=1, raisedSeq=1, dispositionSeq=2), 2)
    stored = RM.record_entry(_record_finding(_raw("r", line=2), "ruling"), None)
    pool = RM.build_pool([], 2, [stored])
    pool = [dict(session, ref="e0")] + pool
    assert RM.exact_match(_raw("s"), pool)["key"] == _key(_raw("s"))
    assert RM.exact_match(_raw("r", line=2), pool)["source"] == "record"
    assert RM.exact_match(_raw("other"), pool) is None


# ---- the snapshot (I4) ------------------------------------------------------------------------

def test_i4_the_pool_is_snapshotted_before_staging_strips_a_reraised_rows_disposition():
    state = _state()
    raw = _raw("alpha")
    _earlier(state, raw, "craft", settledReason="code quality only")
    state["round"] = 2
    RD._stage_findings(state, _compile([raw]))
    assert "disposition" not in _row(state, raw), "premise: staging strips the re-raised row's disposition"
    pool = RD._earlier_pool(state)
    assert [(e["outcome"], e["family"]["disposition"], e["round"]) for e in pool] == [("craft", "craft", 1)]
    RD._stage_findings(state, _compile([raw]))  # a second staging of the round (a gap sweep) keeps it
    assert RD._earlier_pool(state) == pool


def test_i4_a_decision_of_the_current_round_is_not_an_earlier_finding():
    state = _state()
    _earlier(state, _raw("alpha"), "craft", settledReason="cq")
    assert RD._earlier_pool(state) == []


# ---- FR-18: the grouping of same-root-cause survivors stays as it is ---------------------------

def test_fr18_two_same_root_cause_survivors_group_into_one_finding_and_one_fix_row():
    state = _state()
    first, second = _raw("one root", line=1), _raw("one root again", line=2)
    _verify(state, [first, second], {"one root": "CONFIRMED", "one root again": "CONFIRMED"})
    ids = _ids(state)
    _synth(state, [_group(ids["one root"], ids["one root again"])])
    assert len(state["findings"]) == 1 and len(state["_fixBatch"]) == 1
    assert [m["member_ids"] for m in state["rounds"]["1"]["merges"]] == [[ids["one root"], ids["one root again"]]]
    assert [bool(_row(state, r).get(SC.MERGED_INTO_FIELD)) for r in (first, second)].count(True) == 1


# ---- FR-19: the judge names a repeat ------------------------------------------------------------

def test_fr19_a_reworded_later_round_finding_named_by_the_judge_repeats_a_session_finding():
    state = _state()
    earlier = _raw("alpha bug", id="F-1")
    _earlier(state, earlier, "craft", settledReason="code quality only")
    state["round"] = 2
    reworded = _raw("alpha defect, reworded")
    _verify(state, [reworded], {"alpha defect, reworded": "CONFIRMED"})
    # the fold reads only the pre-staging snapshot, not the ledger as staging left it
    state[SC.DISPOSITION_LEDGER_KEY] = [r for r in state[SC.DISPOSITION_LEDGER_KEY] if r["title"] != "alpha bug"]
    assert _payload(state)["earlier"] == [
        {"ref": "e1", "id": "F-1", "file": "f.py", "line": 1, "title": "alpha bug", "outcome": "craft"}]
    _synth(state, [_group(_ids(state)["alpha defect, reworded"], ref="e1")])
    row = _row(state, reworded)
    assert row["repeatOf"] == {"findingKey": _key(earlier), "id": "F-1", "fixHolds": None}
    assert row["repeatKept"]["outcome"] == "craft" and "F-1" in row["repeatKept"]["reason"]
    assert (row["disposition"], row["settledReason"]) == ("craft", row["repeatKept"]["reason"])
    assert _titles(state) == [] and _batch(state) == []


def test_fr19_a_new_finding_named_as_a_repeat_of_a_record_finding_repeats_it():
    stored = _record_finding(_raw("record bug", id="R-7"), "ruling")
    entries, _ = RM.read_earlier_findings(_record_payload([stored]))
    state = _state(earlierFindings=entries)
    reworded = _raw("record bug, reworded")
    _verify(state, [reworded], {"record bug, reworded": "CONFIRMED"})
    _synth(state, [_group(_ids(state)["record bug, reworded"], ref="e1")])
    row = _row(state, reworded)
    assert row["repeatOf"] == {"findingKey": stored["findingKey"], "id": "R-7", "fixHolds": None}
    assert row["repeatKept"]["outcome"] == "ruling" and row["disposition"] == "ruling"
    assert _titles(state) == [] and _batch(state) == []


def test_fr19_a_judge_name_on_a_finding_whose_earlier_finding_is_open_routes_it_normally():
    state = _state()
    RD._stage_findings(state, _compile([_raw("still open")]))  # raised, never decided: not an earlier finding
    state["round"] = 2
    _verify(state, [_raw("new one", line=2)], {"new one": "CONFIRMED"})
    assert _payload(state)["earlier"] == []
    _synth(state, [_group(_ids(state)["new one"])])
    assert _titles(state) == ["new one"] and "repeatOf" not in _row(state, _raw("new one", line=2))


# ---- FR-20: a repeat of a fixed finding ---------------------------------------------------------

def test_fr20_a_repeat_of_a_fixed_finding_the_verifier_refutes_keeps_fixed_and_the_fix_holds():
    state = _state()
    earlier = _raw("alpha bug", id="F-1")
    _earlier(state, earlier, "fixed", dispositionReceipt={"headSha": "a" * 40})
    state["round"] = 2
    reworded = _raw("alpha defect, reworded")
    _verify(state, [reworded], {"alpha defect, reworded": "REFUTED"})
    _synth(state, [_group(_ids(state)["alpha defect, reworded"], ref="e1")])
    row = _row(state, reworded)
    assert row["disposition"] == "fixed" and RD._disposition_is_current(row)
    assert row["repeatOf"] == {"findingKey": _key(earlier), "id": "F-1", "fixHolds": True}
    assert row["repeatKept"]["outcome"] == "fixed"
    assert row["repeatKept"]["reason"].endswith("; the verifier found the fix still holds")
    assert row["grade"]["verdict"] == "wrong"
    assert _titles(state) == [] and _batch(state) == []


def test_fr20_a_repeat_of_a_fixed_finding_the_verifier_confirms_is_a_new_finding_in_the_fix_batch():
    state = _state()
    earlier = _raw("alpha bug", id="F-1")
    _earlier(state, earlier, "fixed", dispositionReceipt={"headSha": "a" * 40})
    state["round"] = 2
    reworded = _raw("alpha defect, reworded")
    _verify(state, [reworded], {"alpha defect, reworded": "CONFIRMED"})
    _synth(state, [_group(_ids(state)["alpha defect, reworded"], ref="e1")])
    row = _row(state, reworded)
    assert row["repeatOf"] == {"findingKey": _key(earlier), "id": "F-1", "fixHolds": False}
    assert "repeatKept" not in row and "disposition" not in row
    assert _titles(state) == ["alpha defect, reworded"] and _batch(state) == ["alpha defect, reworded"]


def test_fr20_a_same_key_refuted_repeat_of_a_fixed_finding_takes_the_fixed_family_back():
    state = _state()
    raw = _raw("alpha bug")
    receipt = {"headSha": "a" * 40}
    _earlier(state, raw, "fixed", dispositionReceipt=receipt)
    state["round"] = 2
    _verify(state, [raw], {"alpha bug": "REFUTED"})
    assert _payload(state)["findings"] == [] and _payload(state)["refuted"][0]["title"] == "alpha bug"
    _synth(state, None)
    row = _row(state, raw)
    assert (row["disposition"], row["dispositionRound"], row["dispositionReceipt"]) == ("fixed", 1, receipt)
    assert row["repeatOf"]["fixHolds"] is True and row["grade"]["verdict"] == "wrong"
    assert RD._disposition_is_current(row)


def test_edge5_a_repeat_with_no_grade_follows_the_table(repo):
    state = _state(repo.root)
    fixed, wrong = _raw("fixed one", line=1), _raw("wrong one", line=2)
    _earlier(state, fixed, "fixed")
    _earlier(state, wrong, "refuted", grade=_WRONG, refutedReason="guard holds")
    _anchors(state, {1: repo.first, 2: repo.changed})
    state["round"] = 2
    _verify(state, [fixed, wrong], {})  # the verifier was silent: no grade
    assert all("grade" not in f for f in _payload(state)["findings"])
    _synth(state, None)
    assert sorted(_titles(state)) == ["fixed one", "wrong one"]
    assert _row(state, fixed)["repeatOf"]["fixHolds"] is False
    assert _row(state, wrong)["repeatOf"]["fixHolds"] is None


# ---- FR-21: a shown-wrong finding raised again ---------------------------------------------------

def _shown_wrong_round(repo, judged, now, verdict="CONFIRMED"):
    state = _state(repo.root)
    raw = _raw("beta bug")
    _earlier(state, raw, "refuted", grade=_WRONG, refutedReason="guard holds")
    _anchors(state, {1: judged, 2: now})
    state["round"] = 2
    _verify(state, [raw], {"beta bug": verdict})
    _synth(state, None)
    return state, raw


def test_fr21_a_shown_wrong_finding_raised_again_after_a_fix_that_changed_the_tree_is_a_new_finding(repo):
    state, raw = _shown_wrong_round(repo, repo.first, repo.changed)
    row = _row(state, raw)
    assert row["repeatOf"] == {"findingKey": _key(raw), "id": None, "fixHolds": None}
    assert "repeatKept" not in row and "disposition" not in row
    assert _titles(state) == ["beta bug"] and _batch(state) == ["beta bug"]


def test_fr21_the_same_finding_on_an_unchanged_tree_keeps_shown_wrong_and_the_grade_that_closed_it(repo):
    state, raw = _shown_wrong_round(repo, repo.changed, repo.same)
    row = _row(state, raw)
    assert row["disposition"] == "refuted" and row["dispositionRound"] == 1 and RD._disposition_is_current(row)
    assert row["repeatKept"]["outcome"] == "shown-wrong" and row["refutedReason"] == row["repeatKept"]["reason"]
    assert row["grade"] == _WRONG  # the snapshotted `wrong` grade, not this round's `confirmed`
    marks = state["rounds"]["2"]["repeatMarks"]
    assert [(m["kept"], m["grade"]["verdict"]) for m in marks] == [(True, "confirmed")]
    assert _titles(state) == [] and _batch(state) == []


def test_fr21_a_shown_wrong_repeat_found_wrong_again_after_a_change_keeps_its_own_wrong_grade(repo):
    state, raw = _shown_wrong_round(repo, repo.first, repo.changed, verdict="REFUTED")
    row = _row(state, raw)
    assert row["repeatKept"]["outcome"] == "shown-wrong" and row["disposition"] == "refuted"
    assert row["grade"]["verdict"] == "wrong" and row["grade"]["reason"] == "checked: REFUTED"


@pytest.mark.parametrize("unreadable", ["no-anchor", "no-repo-root", "bad-repo-root"])
def test_edge4_an_unreadable_head_or_a_failed_diff_counts_as_changed(repo, unreadable):
    state = _state(None if unreadable == "no-repo-root" else (
        repo.root + "-absent" if unreadable == "bad-repo-root" else repo.root))
    raw = _raw("beta bug")
    _earlier(state, raw, "refuted", grade=_WRONG, refutedReason="guard holds")
    if unreadable != "no-anchor":
        _anchors(state, {1: repo.changed, 2: repo.same})  # the same tree, were it readable
    state["round"] = 2
    _verify(state, [raw], {"beta bug": "CONFIRMED"})
    _synth(state, None)
    assert _titles(state) == ["beta bug"] and "repeatKept" not in _row(state, raw)


# ---- FR-22: a kept repeat leaves every fix and owner path ----------------------------------------

def test_fr22_a_repeat_of_a_craft_and_of_a_left_for_owner_finding_is_kept_and_reaches_no_fix_or_owner_hold():
    state = _state()
    craft = _raw("craft one", line=1, consequenceKind="code-quality")
    owner = _raw("owner call", line=2, tradeoff=True)
    fresh_tradeoff, fresh = _raw("fresh tradeoff", line=3, tradeoff=True), _raw("fresh plain", line=4)
    _earlier(state, craft, "craft", settledReason="code quality only")
    _earlier(state, owner, "left-for-owner", settledReason="only the owner can settle this")
    state["round"] = 2
    _verify(state, [craft, owner, fresh_tradeoff, fresh], {t: "CONFIRMED" for t in (
        "craft one", "owner call", "fresh tradeoff", "fresh plain")})
    _synth(state, None)
    for raw, outcome in ((craft, "craft"), (owner, "left-for-owner")):
        row = _row(state, raw)
        assert row["disposition"] == outcome and RD._disposition_is_current(row), row
        assert row["repeatKept"]["outcome"] == outcome and row["repeatOf"]["findingKey"] == _key(raw)
    assert sorted(_titles(state)) == ["fresh plain", "fresh tradeoff"]  # the kept ones are not findings
    assert _batch(state) == ["fresh plain"]
    assert state["ownerChoiceHeld"] == [_key(fresh_tradeoff)], "only the fresh tradeoff is held for the owner"


def test_fr22_a_repeat_only_round_of_kept_findings_converges_with_nothing_to_fix():
    state = _state()
    craft = _raw("craft one")
    _earlier(state, craft, "craft", settledReason="code quality only")
    state["round"] = 2
    _verify(state, [craft], {"craft one": "CONFIRMED"})
    _synth(state, None)
    assert state["findings"] == [] and state["step"] != RD.P_FIXER and state["rounds"]["2"]["blockingCount"] == 0


@pytest.mark.parametrize("kept_severity,fresh_severity", [("Critical", "Important"), ("Important", "Critical")])
def test_fr22_a_group_of_a_kept_member_and_a_fresh_member_fixes_the_fresh_one_alone(kept_severity,
                                                                                   fresh_severity):
    state = _state()
    kept, fresh = _raw("kept one", line=1, severity=kept_severity), _raw("fresh one", line=2,
                                                                         severity=fresh_severity)
    _earlier(state, kept, "craft", settledReason="code quality only")
    state["round"] = 2
    _verify(state, [kept, fresh], {"kept one": "CONFIRMED", "fresh one": "CONFIRMED"})
    ids = _ids(state)
    _synth(state, [_group(ids["kept one"], ids["fresh one"])])
    assert [(f["title"], f["severity"]) for f in state["findings"]] == [("fresh one", fresh_severity)]
    assert _batch(state) == ["fresh one"]
    assert [m["member_ids"] for m in state["rounds"]["2"]["merges"]] == [[ids["fresh one"]]]
    assert not SC.MERGED_INTO_FIELD in _row(state, kept) and not _row(state, fresh).get(SC.MERGED_INTO_FIELD)
    assert _row(state, kept)["disposition"] == "craft" and "disposition" not in _row(state, fresh)


def test_edge7_a_group_whose_members_are_all_kept_leaves_the_merge_and_nothing_is_dropped(monkeypatch):
    state = _state()
    a, b, c, d = (_raw(t, line=i) for i, t in enumerate(("kept a", "kept b", "fresh c", "fresh d"), 1))
    _earlier(state, a, "craft", settledReason="cq")
    _earlier(state, b, "ruling", settledReason="decided")
    state["round"] = 2
    _verify(state, [a, b, c, d], {t: "CONFIRMED" for t in ("kept a", "kept b", "fresh c", "fresh d")})
    ids = _ids(state)
    seen = []
    real = V.merge_and_rank
    monkeypatch.setattr(V, "merge_and_rank", lambda s, g=None: (seen.append((s, g)), real(s, g))[1])
    _synth(state, [_group(ids["kept a"], ids["kept b"], group_id="g1"),
                   _group(ids["fresh c"], ids["fresh d"], group_id="g2")])
    survivors, grouping = seen[-1]
    assert sorted(s["id"] for s in survivors) == sorted([ids["fresh c"], ids["fresh d"]])
    assert [g["member_ids"] for g in grouping] == [[ids["fresh c"], ids["fresh d"]]]
    assert len(state["findings"]) == 1
    assert {"kept a", "kept b", "fresh c", "fresh d"} <= {r["title"] for r in state[SC.DISPOSITION_LEDGER_KEY]}
    assert _row(state, a)["disposition"] == "craft" and _row(state, b)["disposition"] == "ruling"


# ---- repeat-only synthesis, refuted ids in groups (I7, I5) ---------------------------------------

def test_i7_refuted_findings_against_a_non_empty_pool_still_dispatch_synthesis_to_name_repeats_only():
    state = _state()
    _earlier(state, _raw("craft A"), "craft", settledReason="cq")
    state["round"] = 2
    _verify(state, [_raw("gone", line=5)], {"gone": "REFUTED"})
    assert state["step"] == RD.P_SYNTHESIS
    assert "synthesis-no-survivors" not in [d["kind"] for d in state["decisions"]]
    payload = _payload(state)
    assert payload["findings"] == [] and [f["title"] for f in payload["refuted"]] == ["gone"]
    assert [e["ref"] for e in payload["earlier"]] == ["e1"]
    # the seat names the repeat in a group of the refuted id alone
    _synth(state, [_group(_ids(state)["gone"], ref="e1")])
    row = _row(state, _raw("gone", line=5))
    assert row["disposition"] == "craft" and row["repeatKept"]["outcome"] == "craft"
    assert row["grade"]["verdict"] == "wrong"
    assert RD._fold_synthesis and state["findings"] == []


def test_i7_with_an_empty_pool_the_no_survivors_shortcut_is_unchanged():
    state = _state()
    _verify(state, [_raw("gone")], {"gone": "REFUTED"})
    assert state["step"] != RD.P_SYNTHESIS
    assert "synthesis-no-survivors" in [d["kind"] for d in state["decisions"]]
    assert "repeatMatching" not in state["rounds"]["1"]


def test_g2_a_refuted_id_beside_survivors_that_share_its_root_cause_carries_its_mark_and_is_never_merged():
    state = _state()
    earlier = _raw("fixed B", line=9)
    _earlier(state, earlier, "fixed")
    state["round"] = 2
    fresh, gone = _raw("fresh", line=5), _raw("gone", line=6)
    _verify(state, [fresh, gone], {"fresh": "CONFIRMED", "gone": "REFUTED"})
    ids = _ids(state)
    _synth(state, [_group(ids["fresh"], ids["gone"], ref="e1")])
    assert _row(state, gone)["disposition"] == "fixed" and _row(state, gone)["repeatOf"]["fixHolds"] is True
    assert _row(state, fresh)["repeatOf"]["fixHolds"] is False and "disposition" not in _row(state, fresh)
    assert _titles(state) == ["fresh"] and state["rounds"]["2"]["merges"][0]["member_ids"] == [ids["fresh"]]
    assert not _row(state, gone).get(SC.MERGED_INTO_FIELD)


# ---- exact marking (I6, edge 6) ------------------------------------------------------------------

def test_g3_exact_identity_wins_over_the_judges_name():
    state = _state()
    craft, fixed = _raw("craft A", line=1), _raw("fixed B", line=2)
    _earlier(state, craft, "craft", settledReason="cq")
    _earlier(state, fixed, "fixed")
    state["round"] = 2
    _verify(state, [craft], {"craft A": "CONFIRMED"})
    assert [e["title"] for e in _payload(state)["earlier"]] == ["craft A", "fixed B"]
    _synth(state, [_group(_ids(state)["craft A"], ref="e2")])  # the judge names the fixed finding
    row = _row(state, craft)
    assert row["repeatOf"]["findingKey"] == _key(craft) and row["repeatKept"]["outcome"] == "craft"
    assert state["rounds"]["2"]["repeatMarks"][0]["source"] == "exact"
    assert _titles(state) == []


def test_g3_exact_identity_marks_a_finding_the_judge_named_nothing_for():
    state = _state()
    craft = _raw("craft A")
    _earlier(state, craft, "craft", settledReason="cq")
    state["round"] = 2
    _verify(state, [craft], {"craft A": "CONFIRMED"})
    _synth(state, [_group(_ids(state)["craft A"], ref=None)])
    assert _row(state, craft)["repeatKept"]["outcome"] == "craft" and _titles(state) == []


def test_g3_a_record_findings_stored_key_is_an_exact_match():
    raw = _raw("record bug")
    entries, _ = RM.read_earlier_findings(_record_payload([_record_finding(raw, "craft", id="R-1")]))
    state = _state(earlierFindings=entries)
    _verify(state, [raw], {"record bug": "CONFIRMED"})
    _synth(state, None)
    row = _row(state, raw)
    assert row["repeatOf"] == {"findingKey": RM.opaque_key(raw), "id": "R-1", "fixHolds": None}
    assert row["repeatKept"]["outcome"] == "craft" and _titles(state) == []


def test_g3_with_no_synthesis_seat_the_round_is_marked_by_exact_identity_alone_and_says_so():
    cfg = S1858._cfg(**S1858._VERIFIER_ONLY)
    cfg.update({"leg": "code", "diff": "d"})
    cfg.pop("repoRoot")
    state = RD.new_state(cfg)
    craft, reworded = _raw("craft A", line=1), _raw("craft A, reworded", line=1)
    _earlier(state, craft, "craft", settledReason="cq")
    state["round"] = 2
    _verify(state, [craft, reworded], {"craft A": "CONFIRMED", "craft A, reworded": "CONFIRMED"})
    assert RD._nonpanel_unseatable(state, None, RD.P_SYNTHESIS) is True
    rec = state["rounds"]["2"]
    assert (rec["repeatMatching"], rec["repeatMatchingReason"]) == ("exact-only", "synthesis-unseatable")
    assert _row(state, craft)["repeatKept"]["outcome"] == "craft"
    assert "repeatOf" not in _row(state, reworded)
    assert _titles(state) == ["craft A, reworded"]


# ---- the repeat name is validated and bound (I5, edge 3) ------------------------------------------

def _validation_state():
    state = _state()
    _earlier(state, _raw("fixed B", line=9), "fixed")
    state["round"] = 2
    _verify(state, [_raw("fresh", line=5), _raw("gone", line=6)], {"fresh": "CONFIRMED", "gone": "REFUTED"})
    return state, _ids(state)


@pytest.mark.parametrize("make,expect", [
    (lambda i: [_group(i["fresh"], ref="e9")], "repeatOf 'e9'"),
    (lambda i: [_group(i["fresh"], ref=5)], "repeatOf 5"),
    (lambda i: [_group(i["fresh"], ref="")], "repeatOf ''"),
    (lambda i: [_group(i["fresh"], "v9")], "'v9' maps to no entry"),
    (lambda i: [_group(i["fresh"], i["gone"], group_id="a"), _group(i["gone"], group_id="b")],
     "duplicate member"),
    (lambda i: [_group(i["gone"], ref="e1")], "grouping omits staged id"),
])
def test_g1_a_group_with_an_unvalidated_name_or_id_is_refused_at_the_submit_chokepoint(make, expect):
    state, ids = _validation_state()
    fault = RD.synthesis_staged_id_fault(state, {"grouping": make(ids)})
    assert fault is not None and fault.startswith(RD.STAGED_ID_UNRESOLVABLE_CAUSE) and expect in fault, fault


def test_i5_a_refuted_id_may_sit_alone_or_beside_survivors_and_a_group_ref_may_be_null_or_listed():
    state, ids = _validation_state()
    for grouping in (
            [_group(ids["fresh"]), _group(ids["gone"], ref="e1")],
            [_group(ids["fresh"], ids["gone"], ref="e1")],
            [_group(ids["fresh"], ref=None)],
            [dict(_group(ids["fresh"]), repeatOf="e1")],
            [{"group_id": "g", "member_ids": [ids["fresh"]]}]):  # `repeatOf` omitted reads as null
        assert RD.synthesis_staged_id_fault(state, {"grouping": grouping}) is None, grouping


def test_edge3_the_fold_never_applies_a_name_that_does_not_validate():
    state = _state()
    craft = _raw("craft A")
    _earlier(state, craft, "craft", settledReason="cq")
    state["round"] = 2
    reworded = _raw("craft A, reworded")
    _verify(state, [reworded], {"craft A, reworded": "CONFIRMED"})
    RD._fold_synthesis(state, state["config"], {"grouping": [_group(_ids(state)["craft A, reworded"], ref="e9")]})
    rec = state["rounds"]["2"]
    assert (rec["repeatMatching"], rec["repeatMatchingReason"]) == ("exact-only", "grouping-invalid")
    assert "repeatOf" not in _row(state, reworded) and _titles(state) == ["craft A, reworded"]


def test_g1_a_bad_repeat_name_is_refused_on_the_real_submit_and_the_step_survives_a_corrected_resubmit(tmp_path):
    session_dir = str(tmp_path)
    base = TRD._responder(round1_findings=[_raw("bug")])

    def respond(phase, payload, rnd):
        art = base(phase, payload, rnd)
        if phase == RD.P_VERIFIERS:
            ok, state = RD.load_state(session_dir)
            art = dict(art, verifierVendor=RD._nonpanel_selection(state, session_dir, phase)[0])
        return art

    cfg = S1858._cfg()
    cfg.pop("repoRoot")
    n = TRD._drive_to_phase(session_dir, TRD._cfg(**cfg), respond, RD.P_SYNTHESIS)
    assert n["payload"]["earlier"] == [] and n["payload"]["refuted"] == []
    out = RD.cmd_submit(session_dir, RD.P_SYNTHESIS, n["attempt"], n["expectedStateHash"],
                        {"grouping": [_group("v0", ref="e1")]})
    assert out["ok"] is False and "repeatOf 'e1'" in out["reason"], out
    out = RD.cmd_submit(session_dir, RD.P_SYNTHESIS, n["attempt"], n["expectedStateHash"],
                        {"grouping": [_group("v0", ref=None)]})
    assert out["ok"] is True, out


# ---- the execution-evidence binding (I5) -----------------------------------------------------------

def _evidence_record(grouping):
    return {"orderPromptSha256": "a" * 64, "source": "runner", "runnerNonce": "nonce-repeat",
            "recordDigest": "digest-repeat", "observation": TRI._execution_evidence()["observation"],
            "resultKind": "grouping", "resultDigest": RR.payload_sha256(grouping),
            "runKind": ED.RUN_KIND_REVIEW, "viewHeadSha": "a" * 40}


def test_i5_the_evidence_digest_binds_each_groups_repeat_name(tmp_path, monkeypatch):
    signed = [_group("v0", group_id="a", ref="e1"), _group("v1", group_id="b", ref="e2")]
    altered = [_group("v0", group_id="a", ref="e1"), _group("v1", group_id="b", ref=None)]
    monkeypatch.setattr(ED, "run_execution_record", lambda run_dir: (_evidence_record(signed), None))

    def check(grouping):
        envelope = {"phase": RD.P_SYNTHESIS, "orderSha256": "a" * 64, "payload": {"grouping": grouping}}
        return RD._assemble_dispatch_evidence(str(tmp_path), envelope, "run-dir", "a" * 40, RD.P_SYNTHESIS)

    assembled, refusal, _extra, _source = check(signed)
    assert refusal is None and assembled is not None
    assembled, refusal, extra, _source = check(altered)  # only one group's repeatOf differs
    assert assembled is None and refusal == "evidence-result-mismatch"
    assert extra["resultKind"] == "grouping"
    subject = SC.evidence_digest_subject({"grouping": signed}, "grouping")
    assert subject == (True, signed)


# ---- the payload contract, the strict schema and the adapters (I10) -------------------------------

def test_i10_the_payload_contract_reads_an_omitted_repeat_name_as_null():
    for group in ({"member_ids": ["v0"]}, {"member_ids": ["v0"], "repeatOf": None},
                  {"member_ids": ["v0"], "repeatOf": "e1"}):
        assert PC.payload_fault(PC.P_SYNTHESIS, {"grouping": [group]}, "hand-submit") is None, group
    assert RD.synthesis_results_fault({"grouping": [{"member_ids": ["v0"]}]}) is None


def test_i10_the_strict_mode_schema_lists_the_repeat_name_as_required_and_nullable():
    schema = ERC.declared_schema("codex", ERC.RUN_KIND_REVIEW, expected_result_kind="grouping")
    ERC.assert_strict_mode_valid(schema)
    item = schema["properties"]["result"]["properties"]["grouping"]["items"]
    assert "repeatOf" in item["properties"] and "repeatOf" in item["required"]
    assert sorted(item["properties"]["repeatOf"]["type"]) == ["null", "string"]
    assert item["additionalProperties"] is False and "member_ids" in item["required"]


def test_i10_the_adapters_and_the_library_callback_carry_a_groups_repeat_name_unchanged():
    grouping = [{"group_id": "a", "member_ids": ["v0"], "repeatOf": "e1"},
                {"group_id": "b", "member_ids": ["v1"], "repeatOf": None}]
    parsed = EA._parse_review_grouping_object({"grouping": grouping}, None)
    assert parsed["ok"] is True and parsed["grouping"] == grouping
    indexed = {(RA.SEAT_SYNTHESIS, 0): {"payload": {"grouping": grouping}}}
    assert RA._assemble_synthesis([RA.SEAT_SYNTHESIS], indexed, {}) == {"grouping": grouping}
    state = _state()
    artifact = RD._run_seam({"synthesis": lambda findings, rnd: [dict(g) for g in grouping]},
                            RD.P_SYNTHESIS, {"findings": []}, state, state["config"])
    assert artifact == {"grouping": grouping}


# ---- the order and its sidecar (I11) ---------------------------------------------------------------

def test_i11_the_order_names_the_three_lists_and_keeps_its_placeholders():
    path = os.path.join(os.path.dirname(os.path.dirname(_LIB)), "plugins", "superheroes", "rubric", "orders",
                        "dispatch-synthesis.md")
    path = path if os.path.isfile(path) else os.path.join(_LIB, "..", "rubric", "orders", "dispatch-synthesis.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for name in ("`findings`", "`refuted`", "`earlier`", "repeatOf", "`null`"):
        assert name in text, name
    for placeholder in ("VERIFIED_FINDINGS_PATH", "DIFF_PATH", "VERIFICATION_ROOT", "RUBRIC_PATH",
                        "OUTPUT_CHANNEL_BLOCK", "CLAUDE_MD_PATH"):
        assert "{{%s}}" % placeholder in text, placeholder


def test_i11_the_sidecar_writes_the_three_lists_from_the_pending_payload_with_refs_in_pool_order(tmp_path):
    state = _state(earlierFindings=[RM.record_entry(_record_finding(_raw("record one", line=7), "craft"), "d" * 40)])
    _earlier(state, _raw("session one", line=1), "fixed")
    state["round"] = 2
    _verify(state, [_raw("fresh", line=5), _raw("gone", line=6)], {"fresh": "CONFIRMED", "gone": "REFUTED"})
    payload = _payload(state)
    assert [(e["ref"], e["title"]) for e in payload["earlier"]] == [("e1", "session one"), ("e2", "record one")]
    writes = RD._order_sidecar_writes(str(tmp_path), 2, RD.P_SYNTHESIS, [RA.SEAT_SYNTHESIS], payload)
    assert len(writes) == 1
    body = json.loads(writes[0][1])
    assert sorted(body) == ["earlier", "findings", "refuted"]
    assert [f["title"] for f in body["findings"]] == ["fresh"] and [f["title"] for f in body["refuted"]] == ["gone"]
    assert body["earlier"] == payload["earlier"]
    bare = RD._order_sidecar_writes(str(tmp_path), 2, RD.P_SYNTHESIS, [RA.SEAT_SYNTHESIS], {"findings": []})
    assert json.loads(bare[0][1]) == {"findings": [], "refuted": [], "earlier": []}


# ---- `next --earlier-findings` (I8, edge 1) ----------------------------------------------------------

def _next(session_dir, capsys, *flags, fresh=True):
    rc = RD.main(["next", "--session-dir", session_dir, *flags] + TRD._guard_argv(session_dir, fresh=fresh))
    out = capsys.readouterr().out.strip()
    return rc, json.loads(out.splitlines()[-1]) if out else None


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(obj if isinstance(obj, str) else json.dumps(obj))
    return str(path)


@pytest.mark.parametrize("content,entries,unavailable", [
    (_record_payload([_record_finding(_raw("a"), "craft"), _raw("open one", line=2)]), 1, None),
    ({"ok": False, "reason": "review-record-missing"}, 0, None),
    ({"ok": False, "reason": "review-record-unreadable"}, 0, "review-record-unreadable"),
    ("{not json", 0, "not-json"),
    ([], 0, "malformed"),
    (None, 0, "file-missing"),
])
def test_i8_the_flag_reads_the_record_and_only_a_missing_record_is_silent(tmp_path, capsys, content, entries,
                                                                           unavailable):
    d = str(tmp_path)
    path = str(tmp_path / "record.json") if content is None else _write(tmp_path / "record.json", content)
    rc, out = _next(d, capsys, "--earlier-findings", path)
    assert rc == 0 and out["ok"], out  # never a crash, never a refusal of the session
    ok, state = RD.load_state(d)
    cfg = state["config"]
    assert len(cfg["earlierFindings"]) == entries and cfg.get("earlierFindingsUnavailable") == unavailable
    canonical = os.path.join(d, "earlier-findings.json")
    assert os.path.isfile(canonical) == (content is not None and content != "{not json")


def test_i8_an_explicit_flag_wins_over_a_canonical_copy_and_a_canonical_copy_is_read_without_the_flag(
        tmp_path, capsys):
    canonical = os.path.join(str(tmp_path), "earlier-findings.json")
    _write(canonical, _record_payload([_record_finding(_raw("canonical one"), "craft")]))
    explicit = _write(tmp_path / "explicit.json", _record_payload(
        [_record_finding(_raw("explicit one"), "craft"), _record_finding(_raw("explicit two", line=2), "ruling")]))
    d = str(tmp_path)
    rc, _out = _next(d, capsys, "--earlier-findings", explicit)
    assert rc == 0
    ok, state = RD.load_state(d)
    assert [e["title"] for e in state["config"]["earlierFindings"]] == ["explicit one", "explicit two"]
    with open(canonical, encoding="utf-8") as fh:
        assert [f["title"] for f in json.load(fh)["findings"]] == ["explicit one", "explicit two"]

    other = tmp_path / "other"
    other.mkdir()
    _write(other / "earlier-findings.json", _record_payload([_record_finding(_raw("canonical one"), "craft")]))
    rc, _out = _next(str(other), capsys)
    assert rc == 0
    ok, state = RD.load_state(str(other))
    assert [e["title"] for e in state["config"]["earlierFindings"]] == ["canonical one"]


def test_i8_a_flag_on_a_session_that_has_already_begun_fails_loud_and_changes_nothing(tmp_path, capsys):
    d = str(tmp_path)
    rc, _out = _next(d, capsys)
    assert rc == 0
    path = _write(tmp_path / "late.json", _record_payload([_record_finding(_raw("a"), "craft")]))
    rc, out = _next(d, capsys, "--earlier-findings", path, fresh=False)
    assert rc == 1 and out == {"ok": False, "reason": "earlier-findings-not-fresh-state", "value": path}
    assert not os.path.isfile(os.path.join(d, "earlier-findings.json"))
    ok, state = RD.load_state(d)
    assert state["config"].get("earlierFindings") is None


def test_i8_the_round_record_discloses_why_there_is_no_record_sourced_pool():
    unsupplied = _state()
    RD._stage_findings(unsupplied, _compile([_raw("a")]))
    assert unsupplied["rounds"]["1"]["earlierFindingsUnavailable"] == "not-supplied"
    refused = _state(earlierFindings=[], earlierFindingsUnavailable="review-record-unreadable")
    RD._stage_findings(refused, _compile([_raw("a")]))
    assert refused["rounds"]["1"]["earlierFindingsUnavailable"] == "review-record-unreadable"
    missing = _state(earlierFindings=[])  # `review-record-missing`: no earlier record, nothing disclosed
    RD._stage_findings(missing, _compile([_raw("a")]))
    assert "earlierFindingsUnavailable" not in missing["rounds"]["1"]


# ---- end to end: a record-sourced exact repeat through the CLI path -------------------------------

def test_e2e_a_new_finding_that_is_a_record_finding_exactly_is_kept_and_reaches_no_fixer(tmp_path):
    raw = _raw("known craft")
    entries, _ = RM.read_earlier_findings(_record_payload([_record_finding(raw, "craft", id="R-3")]))
    session_dir = str(tmp_path)
    seen = []
    base = TRD._responder(round1_findings=[dict(raw)])

    def respond(phase, payload, rnd):
        seen.append(phase)
        art = base(phase, payload, rnd)
        if phase == RD.P_VERIFIERS:
            ok, state = RD.load_state(session_dir)
            art = dict(art, verifierVendor=RD._nonpanel_selection(state, session_dir, phase)[0])
        return art

    cfg = S1858._cfg()
    cfg.pop("repoRoot")
    cfg["earlierFindings"] = entries
    TRD._drive_cli(session_dir, TRD._cfg(**cfg), respond)
    ok, state = RD.load_state(session_dir)
    assert ok and state["terminal"], state.get("terminal")
    assert RD.P_SYNTHESIS in seen and RD.P_FIXER not in seen, seen
    row = _row(state, raw)
    assert row["repeatOf"]["id"] == "R-3" and row["repeatKept"]["outcome"] == "craft"
    assert state["findings"] == [] and state["rounds"]["1"]["repeatMatching"] == "judge"
