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
import review_record as REC  # noqa: E402
import review_record_session as RS  # noqa: E402
import round_adapters as RA  # noqa: E402
import round_records as RR  # noqa: E402
import session_checkout as SCO  # noqa: E402
import test_round_driver as TRD  # noqa: E402
import test_round_driver_integration as TRI  # noqa: E402
import test_second_test_c1l7 as C1L7  # noqa: E402
import test_synthesis_seat_1858 as S1858  # noqa: E402
from test_review_record_session import Fake as SessionFake, extras as session_extras, put_extras  # noqa: E402

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


# ---- the pool ---------------------------------------------------------------------------------
# The module's own readings (decision table, code_changed, the file, exact_match) are tested in
# test_repeat_marks_module_c1l8a.py; the tests here need the driver.

def test_t10_the_pool_lists_session_rows_then_record_findings_with_refs_from_e1():
    state = _state()
    _earlier(state, _raw("session one", line=1), "fixed")
    _earlier(state, _raw("session two", line=2), "refuted", grade=_WRONG, refutedReason="guard holds")
    RD._stage_findings(state, _compile([_raw("still open", line=3)]))
    record = [RM.record_entry(_record_finding(_raw("record one", line=4), "craft"))]
    pool = RM.build_pool(state, 2, record)
    assert [(e["ref"], e["title"], e["outcome"]) for e in pool] == [
        ("e1", "session one", "fixed"), ("e2", "session two", "shown-wrong"), ("e3", "record one", "craft")]
    assert [sorted(e) for e in RM.order_list(pool)] == [sorted(["ref", "id", "file", "line", "title", "outcome"])] * 3
    # a decision of the current round, or a record finding the session already holds, is not listed again
    assert [e["title"] for e in RM.build_pool(state, 1, [])] == []
    held = RM.record_entry(_record_finding(_raw("session one", line=1), "fixed"))
    assert [e["title"] for e in RM.build_pool(state, 2, [held])] == ["session one", "session two"]


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


def test_b1_a_merged_members_exact_repeat_is_marked_a_repeat_and_keeps_its_representatives_outcome():
    state = _state()
    rep, member = _raw("rep one", line=1), _raw("member one", line=2)
    RD._stage_findings(state, _compile([rep, member]))
    RD._record_merged_into(state, _key(member), _key(rep))
    RD._record_disposition(state, _key(rep), "craft", 1, settledReason="code quality only")
    assert "disposition" not in _row(state, member), "premise: the member holds no decision of its own"
    state["round"] = 2
    _verify(state, [member], {"member one": "CONFIRMED"})
    assert [(e["title"], e["outcome"]) for e in RD._earlier_pool(state)] == [("rep one", "craft"), ("member one", "craft")]
    _synth(state, None)
    row = _row(state, member)
    assert row["repeatOf"]["findingKey"] == _key(member)
    assert row["repeatKept"]["outcome"] == "craft" and row["disposition"] == "craft"
    assert _titles(state) == [] and _batch(state) == []


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
    grouping = [_group(_ids(state)["new one"], ref="e1")]  # the judge names the open finding, which the order never offered
    fault = RD.synthesis_staged_id_fault(state, {"grouping": grouping})
    assert fault is not None and fault.startswith(RD.STAGED_ID_UNRESOLVABLE_CAUSE) and "repeatOf 'e1'" in fault, fault
    RD._fold_synthesis(state, state["config"], {"grouping": grouping})  # the fold ignores a name that does not validate
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


def test_d2_a_preserved_link_takes_this_rounds_fix_holds_and_keeps_its_target():
    state = _state()
    original = _raw("alpha bug", id="F-1")
    _earlier(state, original, "fixed", dispositionReceipt={"headSha": "a" * 40})
    state["round"] = 2
    reworded = _raw("alpha defect, reworded")
    _verify(state, [reworded], {"alpha defect, reworded": "REFUTED"})
    _synth(state, [_group(_ids(state)["alpha defect, reworded"], ref="e1")])
    held = {"findingKey": _key(original), "id": "F-1", "fixHolds": True}
    assert _row(state, reworded)["repeatOf"] == held, "premise: round 2 kept it as a repeat of the fixed finding"
    state["round"] = 3
    _verify(state, [reworded], {"alpha defect, reworded": "CONFIRMED"})
    _synth(state, None)
    (mark,) = state["rounds"]["3"]["repeatMarks"]
    assert mark["source"] == "exact" and mark["kept"] is False
    expected = dict(held, fixHolds=False)  # still the fixed finding's link, with this round's confirmed grade
    assert mark["repeatOf"] == expected and _row(state, reworded)["repeatOf"] == expected


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


@pytest.mark.parametrize("verdict,kept", [("CONFIRMED", False), ("REFUTED", True)])
def test_c1_a_record_finding_is_judged_on_an_unknown_head_so_a_confirmed_repeat_is_new_on_unchanged_code(
        repo, verdict, kept):
    raw = _raw("beta bug")
    stored = _record_finding(raw, "shown-wrong", id="R-4")
    entries, _ = RM.read_earlier_findings(_record_payload([stored], sha=repo.same))  # the record ended on the head
    assert [e["head"] for e in entries] == [None]
    state = _state(repo.root, earlierFindings=entries)
    _anchors(state, {1: repo.same})  # this round judges on the very commit the record ended on
    _verify(state, [raw], {"beta bug": verdict})
    _synth(state, None)
    row = _row(state, raw)
    assert row["repeatOf"]["findingKey"] == stored["findingKey"] and row["repeatOf"]["id"] == "R-4"
    if kept:
        assert row["repeatKept"]["outcome"] == "shown-wrong" and row["disposition"] == "refuted"
        assert _titles(state) == [] and _batch(state) == []
    else:
        assert "repeatKept" not in row and "disposition" not in row
        assert _titles(state) == ["beta bug"] and _batch(state) == ["beta bug"]


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
    assert state["findings"] == [] and state["step"] != RD.P_APPLY_FIXES and state["rounds"]["2"]["blockingCount"] == 0


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
    state = _state(earlierFindings=[RM.record_entry(_record_finding(_raw("record one", line=7), "craft"))])
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
    (_record_payload([_record_finding(_raw("a"), "craft"), _raw("open one", line=2)]), 2, None),
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
    assert os.path.isfile(canonical) == isinstance(content, dict)


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
    assert "earlierFindingsUnavailable" not in missing["rounds"].get("1", {})


# ---- end to end: a record-sourced exact repeat through the CLI path -------------------------------

def test_e2e_a_new_finding_that_is_a_record_finding_exactly_is_kept_and_reaches_no_apply_fixes_step(tmp_path):
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
    assert RD.P_SYNTHESIS in seen and RD.P_APPLY_FIXES not in seen, seen
    row = _row(state, raw)
    assert row["repeatOf"]["id"] == "R-3" and row["repeatKept"]["outcome"] == "craft"
    assert state["findings"] == [] and state["rounds"]["1"]["repeatMatching"] == "judge"


# ---- a refuted finding of the first verifier pass reaches the repeat plan (T-2) ----------------------------------

_PASSED_RUN = {"outcome": "passed"}
_MISSED_PATH = {"verdict": "PLAUSIBLE", "reason": "the first test never calls the retry path", "pathReached": False}
_CONFIRMED_V = {"verdict": "CONFIRMED", "reason": "reproduced", "evidence": "ran: 1 failed"}
_REFUTED_V = {"verdict": "REFUTED", "reason": "the guard holds"}


def _fold_pass(state, table):
    """One verifier fold over the staged ``_toVerify``; ``table`` is {title: verdict}, a missing title is silent."""
    verdicts = [dict(table[s["title"]], id=s["id"]) for s in V.stage_ids(state["_toVerify"]) if s["title"] in table]
    RD._fold_verifiers(state, state["config"], {
        "verdicts": verdicts, "verifierVendor": RD._nonpanel_selection(state, None, RD.P_VERIFIERS)[0]})


def _held_round(state, raws, held_title, table):
    """Round 2 of ``state`` through pass 1, the second-test seat (which gives no result) and up to pass 2's fold:
    ``raws`` are staged with ``held_title``'s break-it test marked passed, and ``table`` is pass 1's verdicts.
    Returns with pass 2 pending (the held finding staged as `secondTest`)."""
    state["round"] = 2
    compiled = _compile(raws)
    for finding in compiled:
        if finding["title"] == held_title:
            finding["breakItRun"] = dict(_PASSED_RUN)
    RD._stage_findings(state, compiled)
    _fold_pass(state, dict(table, **{held_title: _MISSED_PATH}))
    assert state["step"] == RD.P_SECOND_TEST and state["_secondTestHeld"], "premise: pass 1 holds the finding"
    RD._fold_second_test(state, state["config"], {"findings": []})
    assert state["step"] == RD.P_VERIFIERS and state["_secondTestPass"] is True, "premise: pass 2 is pending"
    assert [f["title"] for f in state["_toVerify"]] == [held_title]


def test_t2a_a_refuted_same_key_repeat_of_the_first_pass_takes_the_fixed_family_back_after_the_second_pass():
    state = _state()
    repeat, held, plain = _raw("alpha bug", line=1), _raw("held one", line=2), _raw("plain one", line=3)
    receipt = {"headSha": "a" * 40}
    _earlier(state, repeat, "fixed", dispositionReceipt=receipt)
    _held_round(state, [held, plain, repeat], "held one",
                {"alpha bug": _REFUTED_V, "plain one": _CONFIRMED_V})
    _fold_pass(state, {"held one": _CONFIRMED_V})
    assert state["step"] == RD.P_SYNTHESIS
    _synth(state, None)
    row = _row(state, repeat)
    assert row["repeatOf"] == {"findingKey": _key(repeat), "id": None, "fixHolds": True}
    assert row["repeatKept"]["outcome"] == "fixed"
    assert (row["disposition"], row["dispositionRound"], row["dispositionReceipt"]) == ("fixed", 1, receipt)
    assert RD._disposition_is_current(row) and row["grade"]["verdict"] == "wrong"
    assert sorted(_titles(state)) == ["held one", "plain one"] and "alpha bug" not in _batch(state)


def test_t2b_after_the_second_pass_the_round_holds_both_passes_findings_under_pairwise_unique_ids():
    state = _state()
    repeat, held, plain = _raw("alpha bug", line=1), _raw("held one", line=2), _raw("plain one", line=3)
    _earlier(state, repeat, "fixed")
    _held_round(state, [held, plain, repeat], "held one",
                {"alpha bug": _REFUTED_V, "plain one": _CONFIRMED_V})
    assert state["_secondTestRefutedCarry"][0]["title"] == "alpha bug"
    _fold_pass(state, {"held one": _CONFIRMED_V})
    assert [f["title"] for f in state["_refuted"]] == ["alpha bug"]
    assert sorted(f["title"] for f in state["_verified"]) == ["held one", "plain one"]
    ids = [f["id"] for f in state["_verified"] + state["_refuted"]]
    assert len(ids) == 3 and len(set(ids)) == 3 and all(V.is_staged_id(i) for i in ids)
    assert not {"_secondTestCarry", "_secondTestRefutedCarry", "_secondTestHeld", "_secondTestPass"} & set(state)


def test_t2c_a_second_pass_with_nothing_left_still_dispatches_synthesis_when_the_first_pass_refuted_against_a_pool():
    state = _state()
    _earlier(state, _raw("craft A"), "craft", settledReason="cq")
    _held_round(state, [_raw("held one", line=2), _raw("gone", line=5)], "held one", {"gone": _REFUTED_V})
    state["_toVerify"] = []  # the second pass returns nothing: no survivor, nothing refuted in it
    _fold_pass(state, {})
    assert state["step"] == RD.P_SYNTHESIS
    assert "synthesis-no-survivors" not in [d["kind"] for d in state["decisions"]]
    payload = _payload(state)
    assert payload["findings"] == [] and [f["title"] for f in payload["refuted"]] == ["gone"]
    _synth(state, [_group(_ids(state)["gone"], ref="e1")])
    row = _row(state, _raw("gone", line=5))
    assert row["disposition"] == "craft" and row["repeatKept"]["outcome"] == "craft"
    assert state["findings"] == []


# ---- a session row is pooled as the record writer reads it (T-3), through the driver -----------------------------

def _driven(title, line):
    """A finding inside the surface every round of `_Rounds` reviews (lines 1 and 2 of `newsurf.py`)."""
    return dict(_raw(title, line=line), file="newsurf.py")


class _Rounds(C1L7.Round):
    """C1-L7's driven session with its own script: the code reviewer raises ``round1`` in round 1, the scoped scan of
    round ``n`` raises ``scoped(n, state)``, the verifier answers each (round, title) from ``verdicts`` (CONFIRMED
    when absent) and the synthesis seat answers ``synth(round, payload)``. Each fix leaves a new surface, so a
    fix is followed by a round whose audits decide the fix and whose scoped scan can raise a finding again: a
    finding decided in round ``n`` is an earlier finding from round ``n + 1`` on."""

    def __init__(self, tmp_path, round1, scoped, verdicts=None, synth=None):
        super().__init__(tmp_path, first={})
        self.cfg["diff"] = C1L7._DIFF + TRD._newsurf("0")
        self.cfg["repoRoot"] = self.checkout  # the repeat table reads whether the code changed between two heads
        self.round1, self.scoped, self.verdicts = list(round1), scoped, verdicts or {}
        self.synth = synth or (lambda rnd, payload: None)
        self.scanned = set()

    def respond(self, phase, payload, rnd):
        self.seen.append(phase)
        if phase == RD.P_PANEL:
            seats = {d: {"findings": []} for d in RD.DIMENSIONS}
            if rnd == 1:
                seats["code-reviewer"] = {"findings": [dict(f) for f in self.round1]}
            return {"seats": seats}
        if phase == RD.P_SCOPED:
            found = [] if rnd in self.scanned else [dict(f) for f in self.scoped(rnd, self.state())]
            self.scanned.add(rnd)
            return {"findings": found}
        if phase == RD.P_VERIFIERS:
            verdicts = []
            for cluster in payload.get("clusters", []):
                for finding, fid in zip(cluster["findings"], cluster["ids"]):
                    verdicts.append(dict(self.verdicts.get((rnd, finding["title"]), C1L7._CONFIRMED), id=fid))
            return {"verdicts": verdicts,
                    "verifierVendor": RD._nonpanel_selection(self.state(), self.dir, phase)[0]}
        if phase == RD.P_SYNTHESIS:
            return {"grouping": self.synth(rnd, payload)}
        if phase == RD.P_APPLY_FIXES:  # each fix leaves a new surface, so the next round's scoped scan runs
            return {"fixes": [], "headDiff": TRD._headf_ns(self.seen.count(RD.P_APPLY_FIXES)), "changedSubjects": ["Code"]}
        return TRD._responder()(phase, payload, rnd)

    def fixer_runs(self):
        return self.seen.count(RD.P_APPLY_FIXES)


def test_t3a_a_non_representative_member_of_a_fixed_group_raised_again_is_marked_a_repeat_and_kept(tmp_path):
    first, second, fresh = _driven("one root cause", 1), _driven("same root cause again", 2), _driven("fresh one", 2)
    raws = {first["title"]: first, second["title"]: second}
    seen = {}

    def scoped(rnd, state):
        if rnd == 2:  # a fresh finding keeps the session going, so the fixed group is an earlier finding in round 3
            return [fresh]
        if rnd != 3:
            return []
        ledger = _ledger(state)
        (linked,) = [row for row in ledger.values() if row.get(SC.MERGED_INTO_FIELD)]
        seen["member"] = raws[linked["title"]]
        seen["representative"] = ledger[linked[SC.MERGED_INTO_FIELD]].get("disposition")
        return [seen["member"]]

    refuted = {(3, title): C1L7._SECOND_REFUTED for title in raws}
    r = _Rounds(tmp_path, [first, second], scoped, verdicts=refuted,
                synth=lambda rnd, payload: [_group(*[f["id"] for f in payload["findings"]])] if rnd == 1 else None)
    r.drive()
    state = r.state()
    assert seen.get("representative") == "fixed", (seen, r.seen, list(state["rounds"]))  # premise: the group was fixed
    assert r.fixer_runs() == 2 and state["terminal"], r.seen  # the group in round 1, the fresh finding in round 2
    row = _row(state, seen["member"])
    assert row["repeatOf"]["findingKey"] == _key(seen["member"]), row
    assert row["repeatKept"]["outcome"] == "fixed" and row["disposition"] == "fixed", row
    assert [f["title"] for f in state["findings"]] == []


def test_t3b_a_judge_named_repeat_kept_as_shown_wrong_is_marked_and_kept_by_exact_identity_when_raised_again(tmp_path):
    shown_wrong, fixme = _driven("shown wrong one", 1), _driven("fix me", 2)
    reworded, fixme_too = _driven("shown wrong one, reworded", 1), _driven("fix me too", 2)
    scripted = {2: [reworded, fixme_too], 3: [reworded]}

    def synth(rnd, payload):
        if rnd == 1:  # the head moves once (to a commit of the same tree) between the judgment and the finding raised again
            _git(r.checkout, "commit", "-q", "--allow-empty", "-m", "move the head")
        if rnd == 2:  # the judge names the reworded finding a repeat of the shown-wrong one, e1
            ref = {e["title"]: e["ref"] for e in payload["earlier"]}["shown wrong one"]
            ids = {f["title"]: f["id"] for f in payload["findings"]}
            return [_group(ids["shown wrong one, reworded"], ref=ref, group_id="a"),
                    _group(ids["fix me too"], group_id="b")]
        return None

    r = _Rounds(tmp_path, [shown_wrong, fixme], lambda rnd, state: scripted.get(rnd, []),
                verdicts={(1, "shown wrong one"): C1L7._SECOND_REFUTED}, synth=synth)
    r.drive()
    state = r.state()
    judged, raised_again = RD._verifier_head(state, r.dir, 1), RD._verifier_head(state, r.dir, 2)
    assert judged and raised_again and judged != raised_again, "premise: the head moved between the two verifier judgments"
    # premise: round 2 kept it as shown-wrong on the judge's name alone, under its own confirmed grade
    (named,) = state["rounds"]["2"]["repeatMarks"]
    assert (named["source"], named["kept"], named["grade"]["verdict"]) == ("judge", True, "confirmed"), named
    assert named["repeatOf"]["findingKey"] == _key(shown_wrong)
    assert r.fixer_runs() == 2 and state["terminal"], r.seen  # rounds 1 and 2 fixed; round 3 reached no fix
    (again,) = state["rounds"]["3"]["repeatMarks"]
    assert (again["source"], again["kept"]) == ("exact", True), again
    row = _row(state, reworded)
    # the exact re-match keeps the original link to the shown-wrong one, never a self-link
    assert again["repeatOf"]["findingKey"] == _key(shown_wrong), again
    assert row["repeatOf"]["findingKey"] == _key(shown_wrong) and row["repeatKept"]["outcome"] == "shown-wrong", row
    assert state["findings"] == []
    # the terminal state goes through the record writer (no earlier posted record): the round-3 finding reads
    # shown-wrong through its original link to the finding the verifier closed, and the write succeeds
    fake = SessionFake()
    extras_dir = tmp_path / "extras"
    extras_dir.mkdir()
    out = RS.write_from_session(r.dir, put_extras(extras_dir, session_extras()), r.checkout, fake.readers())
    assert out["ok"], out
    written = {f["title"]: f for f in REC.read(7, readers=fake.readers())["findings"]}
    assert written["shown wrong one, reworded"]["outcome"] == "shown-wrong", written["shown wrong one, reworded"]
    assert written["shown wrong one, reworded"]["repeatOf"]["findingKey"] == RM.opaque_key(shown_wrong)
    assert written["shown wrong one"]["outcome"] == "shown-wrong"


def test_t3c_a_judge_named_confirmed_repeat_of_a_shown_wrong_finding_on_changed_code_is_a_new_finding(tmp_path):
    # FR-21: a confirmed repeat of a finding closed as wrong, raised on changed code, is treated as a new finding
    shown_wrong, fixme = _driven("shown wrong one", 1), _driven("fix me", 2)
    reworded, fixme_too = _driven("shown wrong one, reworded", 1), _driven("fix me too", 2)
    scripted = {2: [reworded, fixme_too]}

    def synth(rnd, payload):
        if rnd == 1:  # the head moves once, to a commit that changes the tree, between the judgment and the finding raised again
            with open(os.path.join(r.checkout, "changed.txt"), "w", encoding="utf-8") as fh:
                fh.write("the tree changes here\n")
            _git(r.checkout, "add", "-A")
            _git(r.checkout, "commit", "-q", "-m", "change the tree")
        if rnd == 2:  # the judge names the reworded finding a repeat of the shown-wrong one, e1
            ref = {e["title"]: e["ref"] for e in payload["earlier"]}["shown wrong one"]
            ids = {f["title"]: f["id"] for f in payload["findings"]}
            return [_group(ids["shown wrong one, reworded"], ref=ref, group_id="a"),
                    _group(ids["fix me too"], group_id="b")]
        return None

    r = _Rounds(tmp_path, [shown_wrong, fixme], lambda rnd, state: scripted.get(rnd, []),
                verdicts={(1, "shown wrong one"): C1L7._SECOND_REFUTED}, synth=synth)
    r.drive()
    state = r.state()
    judged, raised_again = RD._verifier_head(state, r.dir, 1), RD._verifier_head(state, r.dir, 2)
    assert judged and raised_again and judged != raised_again, "premise: the head moved between the two verifier judgments"
    assert RM.code_changed(r.checkout, judged, raised_again) is True, "premise: the two verifier heads' trees differ"
    (named,) = state["rounds"]["2"]["repeatMarks"]
    assert (named["source"], named["grade"]["verdict"]) == ("judge", "confirmed"), named
    assert named["repeatOf"]["findingKey"] == _key(shown_wrong)
    assert named["kept"] is False, named
    # routed as a new finding: the reworded finding is not kept as shown-wrong
    row = _row(state, reworded)
    assert "repeatKept" not in row and row["disposition"] == "fixed", row
    assert r.fixer_runs() == 2 and state["terminal"], r.seen


def test_d1_a_confirmed_repeat_of_a_fixed_finding_keeps_its_mark_through_its_fix_and_the_archive(tmp_path):
    bug, fresh = _driven("bug one", 1), _driven("fresh one", 2)
    scripted = {2: [fresh], 3: [bug]}  # round 3's scan raises the finding the round-2 audit decided fixed
    r = _Rounds(tmp_path, [bug], lambda rnd, state: scripted.get(rnd, []))
    r.drive()
    state = r.state()
    assert state["terminal"] and r.fixer_runs() == 3, r.seen  # rounds 1, 2 and 3 each fixed; round 4's scan was empty
    (again,) = state["rounds"]["3"]["repeatMarks"]
    assert (again["source"], again["kept"], again["repeatOf"]["fixHolds"]) == ("exact", False, False), again
    # the fix departed the live finding and the archive replaced the ledger row with its copy: the mark survives
    row = _row(state, bug)
    assert row["repeatOf"]["findingKey"] == _key(bug) and row["repeatOf"]["fixHolds"] is False, row
    assert state["findings"] == []
