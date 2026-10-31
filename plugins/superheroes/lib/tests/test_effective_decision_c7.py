"""One effective decision per finding, carried across rewording (review fix loop).

A finding has exactly one effective decision: the latest of a ``rule`` ruling and an owner-gate
decision by one sequence, read through ``_live_ruling_by_key``. It binds the finding under any
wording a later round gives it at the same file and line, and the `apply-fixes` guidance file carries only it.
"""
import ast
import copy
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import session_contract  # noqa: E402
import test_layer2e_follow_up_1272 as L2E  # noqa: E402
import test_rulings_channel_1445 as RC  # noqa: E402
from test_round_driver import _cfg_cert  # noqa: E402

RD = RC.RD

FILE = "a.py"
LINE = 10


def _key(title, line=LINE, file=FILE):
    return session_contract.minted_identity_key({"file": file, "line": line, "title": title})


def _finding(title, line=LINE, file=FILE, **extra):
    row = {"file": file, "line": line, "title": title, "severity": "Important",
           "detail": "%s at %s:%s" % (title, file, line),
           "consequence": "a reviewer-found defect stays in the change"}
    row.update(extra)
    return row


def _mem_state(round_no=2):
    state = RD.new_state(_cfg_cert())
    state["round"] = round_no
    return state


def _add_rule(state, key, ruling, *, guidance=None, file=FILE, line=LINE, rnd=None, **extra):
    """Append a ``rulingsLog`` row the way the ``rule`` verb writes one (sequence from the counter)."""
    row = {"seq": RD._next_ruling_seq(state), "round": rnd or state["round"], "phase": RD.P_APPLY_FIXES,
           "attempt": 0, "id": key, "findingKey": key, "ruling": ruling, "reason": "because",
           "by": "owner"}
    if file is not None:
        row["file"] = file
    if line is not None:
        row["line"] = line
    if guidance is not None:
        row["guidance"] = guidance
    row.update(extra)
    state.setdefault("rulingsLog", []).append(row)
    return row


def _add_gate(state, rnd, key, disposition, *, guidance=None, seq=None, title="t", file=FILE,
              line=LINE, reason="why"):
    """Append an owner-gate entry the way the judgment fold writes one."""
    entry = {"id": key, session_contract.FINDING_KEY_FIELD: key, "title": title, "file": file,
             "line": line, "disposition": disposition}
    if disposition == "skip":
        entry["reason"] = reason
    if guidance is not None:
        entry[RD.GATE_GUIDANCE_RECORD_KEY] = guidance
    if seq is not None:
        entry["rulingSeq"] = seq
    state["rounds"].setdefault(str(rnd), {}).setdefault("judgmentDispositions", []).append(entry)
    return entry


def _batch(state, *findings):
    state["_fixBatch"] = [dict(f) for f in findings]
    state["_fixQueue"] = []
    state["_fixBatchIndex"] = 0


def _entries(state):
    return RD._gate_guidance_entries(state, state["round"])


def _carried_decisions(state):
    return [d for d in state["decisions"] if d["kind"] == "ruling-carried"]


def _no_carry(state):
    assert not state.get("findingLineage")
    assert _carried_decisions(state) == []


def test_t1_reword_carries_guidance_to_next_fix(tmp_path):
    """axis: a ruling recorded with its location binds a reworded finding at the next fixer order.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-1)
    """
    session_dir, _, _, row_a, _row_b = RC._pending_apply_fixes_two_findings(tmp_path)
    key_a = RD._fix_batch_row_key(row_a)
    path = RC._write_ruling_file(tmp_path / "r.json", [
        {"id": key_a, "ruling": "guidance", "reason": "keep it small", "guidance": "G1"}])
    assert RC._rule(session_dir, path)["ok"]
    state = RC._state(session_dir)
    logged = state["rulingsLog"][-1]
    assert (logged["file"], logged["line"]) == (row_a["file"], row_a["line"])
    state["round"] += 1
    reworded = _finding("bounds A, said differently", line=row_a["line"], file=row_a["file"])
    key_new = RD._finding_identity_key(reworded)
    assert key_new != key_a
    RD._stage_findings(state, [reworded])
    assert state["findingLineage"] == {key_new: key_a}
    assert len(_carried_decisions(state)) == 1
    state["findings"] = [dict(reworded)]
    _batch(state, reworded)
    entries = _entries(state)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["id"] == key_new
    assert entry["guidance"] == "G1"
    assert entry["carriedFrom"] == key_a
    assert entry["rulingChannel"] is True
    assert entry["title"] == "bounds A, said differently"
    assert "G1" in RD._gate_guidance_block(entries)


def test_t2_replaced_guidance_never_returns():
    """axis: a ruling given on the reworded key is the group's decision; the original wording reads it.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-2)
    """
    state = _mem_state(2)
    key_f = _key("original wording")
    _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
    reworded = _finding("reworded wording")
    key_k = RD._finding_identity_key(reworded)
    RD._stage_findings(state, [reworded])
    assert state["findingLineage"] == {key_k: key_f}
    _add_rule(state, key_k, "guidance", guidance="G2")
    state["round"] = 3
    original = _finding("original wording")
    RD._stage_findings(state, [original])
    assert state["findingLineage"] == {key_k: key_f}
    assert RD._live_ruling_by_key(state)[key_f]["guidance"] == "G2"
    _batch(state, original)
    entries = _entries(state)
    assert [(e["id"], e["guidance"], e["carriedFrom"]) for e in entries] == [
        (key_f, "G2", key_k)]
    assert "G1" not in RD._gate_guidance_block(entries)


def test_t3_precedence_latest_decision_renders_alone():
    """axis: gate guidance and rule guidance on one key render one text — the later by one sequence.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-3)
    """
    key = L2E._TRADEOFF_ID
    row = _finding("widen the API", line=1, file="f.py")
    # gate guidance "A" (an earlier version recorded it), then a rule guidance "B" -> only "B"
    state = _mem_state(1)
    gate = _add_gate(state, 1, key, "fix-with-guidance", guidance="A", title="widen the API",
                     file="f.py", line=1, seq=RD._next_ruling_seq(state))
    assert gate["rulingSeq"] == state["rulingSeqCounter"]
    _batch(state, row)
    assert key in {RD._fix_batch_row_key(r) for r in state["_fixBatch"]}
    _add_rule(state, key, "guidance", guidance="B", file="f.py", line=1)
    entries = _entries(state)
    assert [(e["id"], e["guidance"], bool(e.get("rulingChannel"))) for e in entries] == [
        (key, "B", True)]
    block = RD._gate_guidance_block(entries)
    assert "B" in block and "> A" not in block
    # a rule guidance, then a later sequenced gate guidance "A" -> only "A"
    state = _mem_state(1)
    _add_rule(state, key, "guidance", guidance="B", file="f.py", line=1)
    gate = _add_gate(state, 1, key, "fix-with-guidance", guidance="A", title="widen the API",
                     file="f.py", line=1, seq=RD._next_ruling_seq(state))
    assert gate["rulingSeq"] == 2
    _batch(state, row)
    entries = _entries(state)
    assert [(e["id"], e["guidance"], bool(e.get("rulingChannel"))) for e in entries] == [
        (key, "A", False)]
    assert "> B" not in RD._gate_guidance_block(entries)


def test_t4_gate_skip_binds_its_finding_but_never_a_reword():
    """axis: an owner-gate skip recorded by an earlier version is a decision on its own finding
    (restaged, it stays skipped and is not held for the owner again) — and it never carries: a later,
    different finding at the skipped location is judged fresh and reaches the fix batch.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-4, BP-5)
    """
    state = _mem_state(1)
    original = _finding("widen the API", line=1, file="f.py", tradeoff=True)
    RD._stage_findings(state, [original])
    RD._record_disposition(state, L2E._TRADEOFF_ID, "out-of-scope", 1,
                           outOfScopeReason="product choice", followUp=dict(L2E._WELL_FORMED))
    skip_row = _add_gate(state, 1, L2E._TRADEOFF_ID, "skip", title="widen the API", file="f.py",
                         line=1, reason="product choice", seq=RD._next_ruling_seq(state))
    skip_row["followUp"] = dict(L2E._WELL_FORMED)
    assert (skip_row["file"], skip_row["line"]) == ("f.py", 1)
    assert skip_row["rulingSeq"] == state["rulingSeqCounter"]
    base = copy.deepcopy(state)
    # the skipped finding itself, restaged a round later: the whole decision, follow-up included
    state["round"] += 1
    RD._stage_findings(state, [original])
    restaged = L2E._ledger_by_key(state)[L2E._TRADEOFF_ID]
    assert restaged["disposition"] == "out-of-scope"
    assert restaged["followUp"] == L2E._WELL_FORMED
    assert RD._filter_excluded_discharged_fixes(state, [original]) == ([], None)
    # normal routing honors it: never held for the owner again
    state["findings"] = [dict(original, verdict="CONFIRMED")]
    RD._after_findings_settled(state, state["config"])
    assert not state.get("ownerChoiceHeld")
    assert any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])
    # the review record's rulings list stays rule-sourced only
    assert RD._standing_rulings_for_orders(state) == ([], None)
    # a later, different finding at the skipped location is judged fresh: it reaches the fix batch
    state = base
    state["round"] += 1
    different = _finding("widen the public API", line=1, file="f.py")
    key_new = RD._finding_identity_key(different)
    RD._stage_findings(state, [different])
    assert key_new not in (state.get("findingLineage") or {})
    assert L2E._ledger_by_key(state)[key_new].get("disposition") != "out-of-scope"
    assert key_new not in RD._live_out_of_scope_ruling_keys(state)
    state["findings"] = [dict(different, verdict="CONFIRMED")]
    RD._after_findings_settled(state, state["config"])
    assert state["step"] == RD.P_APPLY_FIXES
    assert key_new in {RD._fix_batch_row_key(r) for r in state["_fixBatch"]}


def test_t5_edge1_two_compiled_findings_at_the_location_do_not_carry():
    """axis: two compiled findings at the decided location are ambiguous — neither inherits the
    decision and the fixer order renders no guidance."""
    state = _mem_state()
    _add_rule(state, _key("original"), "guidance", guidance="G1", rnd=1)
    RD._stage_findings(state, [_finding("first rewording"), _finding("second rewording")])
    _no_carry(state)
    _batch(state, _finding("first rewording"))
    assert _entries(state) == []


def test_t6_edge2_decided_finding_reraised_in_the_same_compile_does_not_carry():
    """axis: the decided finding re-raised under its own key in the same compile makes the reword
    ambiguous — it does not carry (control: without the re-raise it does)."""
    state = _mem_state()
    key_f = _key("original")
    _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
    reworded = _finding("reworded")
    # control: with the decided finding absent from the compile, the reword carries
    control = copy.deepcopy(state)
    RD._stage_findings(control, [reworded])
    assert control["findingLineage"] == {RD._finding_identity_key(reworded): key_f}
    # the decided finding re-raised under its own key (it moved to another line) in this compile
    moved = _finding("original", line=LINE + 2, **{session_contract.FINDING_KEY_FIELD: key_f})
    RD._stage_findings(state, [moved, reworded])
    _no_carry(state)
    assert RD._live_ruling_by_key(state)[key_f]["guidance"] == "G1"
    assert RD._finding_identity_key(reworded) not in RD._live_ruling_by_key(state)


def test_t7_edge3_two_decided_roots_at_the_location_do_not_carry():
    """axis: two decided roots (a rule ruling and a gate decision) at the location are ambiguous — a
    reword carries neither."""
    state = _mem_state()
    _add_rule(state, _key("original one"), "guidance", guidance="G1", rnd=1)
    _add_gate(state, 1, _key("original two"), "fix-with-guidance", guidance="G2", seq=None)
    RD._stage_findings(state, [_finding("reworded")])
    _no_carry(state)


@pytest.mark.parametrize("decided_line,compiled_line", [
    ("absent", LINE),
    (None, LINE),
    (True, 1),
    ("10", LINE),
    (10.0, LINE),
    ([10], LINE),
])
def test_t8_edge4_decision_row_without_an_integer_line_never_carries(decided_line, compiled_line):
    """axis: a rule or gate decision row whose line is absent or not a plain integer never carries to
    a finding at the location."""
    for source in ("rule", "gate"):
        state = _mem_state()
        key_f = _key("original", line=compiled_line)
        if source == "rule":
            row = _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
            if decided_line == "absent":
                row.pop("line")
            else:
                row["line"] = decided_line
        else:
            entry = _add_gate(state, 1, key_f, "fix-with-guidance", guidance="G1", seq=1)
            if decided_line == "absent":
                entry.pop("line")
            else:
                entry["line"] = decided_line
        RD._stage_findings(state, [_finding("reworded", line=compiled_line)])
        _no_carry(state)


def test_t8_edge4_decision_row_without_a_file_never_carries():
    """axis: a rule decision row with no file never carries to a finding at the location."""
    state = _mem_state()
    _add_rule(state, _key("original"), "guidance", guidance="G1", file=None, rnd=1)
    RD._stage_findings(state, [_finding("reworded")])
    _no_carry(state)


def test_t9_edge5_unsequenced_gate_guidance_loses_to_a_later_rule_guidance():
    """axis: an unsequenced gate guidance loses to a later rule guidance — only the rule's renders."""
    state = _mem_state(2)
    key = _key("subject")
    _add_gate(state, 1, key, "fix-with-guidance", guidance="LEGACY GATE", seq=None)
    _add_rule(state, key, "guidance", guidance="RULE", rnd=2)
    _batch(state, _finding("subject"))
    entries = _entries(state)
    assert [(e["id"], e["guidance"], e.get("rulingChannel")) for e in entries] == [
        (key, "RULE", True)]


def test_t10_edge6_sequenced_gate_guidance_after_a_rule_guidance_renders_alone():
    """axis: a sequenced gate guidance recorded after a rule guidance is the one that renders, alone
    and not through the rulings channel."""
    state = _mem_state(2)
    key = _key("subject")
    _add_rule(state, key, "guidance", guidance="RULE", rnd=1)
    _add_gate(state, 2, key, "fix-with-guidance", guidance="GATE", seq=RD._next_ruling_seq(state))
    _batch(state, _finding("subject"))
    entries = _entries(state)
    assert [(e["id"], e["guidance"], e.get("rulingChannel")) for e in entries] == [
        (key, "GATE", None)]


@pytest.mark.parametrize("bad_log", ["not-a-list", [None], [{"ruling": "guidance"}]])
def test_t11_edge7_unreadable_rulings_log_reads_as_empty(bad_log):
    """axis: an unreadable rulings log reads as empty — nothing carries and no rule guidance renders,
    while owner-gate guidance still does."""
    state = _mem_state()
    key_f = _key("original")
    _add_rule(state, key_f, "guidance", guidance="RULE", rnd=1)
    _add_gate(state, 1, _key("gated"), "fix-with-guidance", guidance="GATE", seq=None)
    state["rulingsLog"] = bad_log
    assert RD._live_ruling_by_key(state) == {}
    RD._stage_findings(state, [_finding("reworded")])
    _no_carry(state)
    _batch(state, _finding("original"), _finding("gated"))
    entries = _entries(state)
    # no rendering from rules; the owner-gate guidance is as readable as it was before
    assert [(e["id"], e["guidance"]) for e in entries] == [(_key("gated"), "GATE")]


def test_unsequenced_gate_decisions_later_round_wins():
    """axis: of unsequenced gate decisions on one key, the later round's guidance is the effective
    one."""
    state = _mem_state(3)
    key = _key("subject")
    _add_gate(state, 1, key, "fix-with-guidance", guidance="OLD", seq=None)
    _add_gate(state, 2, key, "fix-with-guidance", guidance="NEWER", seq=None)
    assert RD._live_ruling_by_key(state)[key]["guidance"] == "NEWER"
    _batch(state, _finding("subject"))
    assert [e["guidance"] for e in _entries(state)] == ["NEWER"]


def test_gate_skip_after_rule_guidance_renders_nothing():
    """axis: a gate skip recorded after a rule guidance is the effective decision (out-of-scope) — no
    guidance renders."""
    state = _mem_state(2)
    key = _key("subject")
    _add_rule(state, key, "guidance", guidance="RULE", rnd=1)
    _add_gate(state, 2, key, "skip", seq=RD._next_ruling_seq(state))
    _batch(state, _finding("subject"))
    assert RD._live_ruling_by_key(state)[key]["ruling"] == "out-of-scope"
    assert _entries(state) == []


def test_gap_sweep_in_the_same_round_never_aliases_to_a_reraised_decided_finding():
    """axis: the ambiguity guards span the whole round — a gap sweep staged after the panel sees the
    panel's findings (the decided original re-raised, or another finding at the location)."""
    state = _mem_state()
    key_f = _key("original")
    _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
    key_g = _key("independent gap issue")
    # control: the gap finding alone in the round carries
    control = copy.deepcopy(state)
    RD._stage_findings(control, [_finding("independent gap issue")])
    assert control["findingLineage"] == {key_g: key_f}
    # the panel re-raises the decided original; the gap sweep then stages an independent finding
    RD._stage_findings(state, [_finding("original")])
    RD._stage_findings(state, [_finding("independent gap issue")])
    _no_carry(state)
    assert key_g not in RD._live_ruling_by_key(state)
    # another finding already raised at the location this round blocks the carry the same way
    state = _mem_state()
    _add_rule(state, key_f, "guidance", guidance="G1", rnd=1)
    RD._stage_findings(state, [_finding("unrelated panel issue")])
    state.pop("findingLineage", None)
    state["decisions"] = [d for d in state["decisions"] if d["kind"] != "ruling-carried"]
    RD._stage_findings(state, [_finding("independent gap issue")])
    assert key_g not in (state.get("findingLineage") or {})


def test_fix_as_suggested_supersedes_an_earlier_skip_and_guidance():
    """axis: the owner's later fix-as-suggested is the effective decision — an earlier skip no longer
    excludes the finding and earlier guidance no longer renders."""
    state = _mem_state(3)
    key = _key("subject")
    _add_gate(state, 1, key, "skip", seq=RD._next_ruling_seq(state))
    _add_gate(state, 2, key, "fix-as-suggested", seq=RD._next_ruling_seq(state))
    assert RD._live_ruling_by_key(state)[key]["ruling"] == "fix"
    row = _finding("subject")
    assert RD._filter_excluded_discharged_fixes(state, [row]) == ([row], None)
    state = _mem_state(3)
    _add_rule(state, key, "guidance", guidance="OLD GUIDANCE", rnd=1)
    _add_gate(state, 2, key, "fix-as-suggested", seq=RD._next_ruling_seq(state))
    _batch(state, _finding("subject"))
    assert _entries(state) == []


@pytest.mark.parametrize("later", ["original", "second independent issue"])
def test_a_same_round_carry_is_undone_when_a_later_staging_makes_it_ambiguous(later):
    """axis: a carry is provisional until the round's last staging — a gap sweep that raises the
    decided original (or another finding at the place) after the panel's carry undoes it; a carry
    from an earlier round stands."""
    state = _mem_state()
    key_f = _key("original")
    _add_gate(state, 1, key_f, "fix-with-guidance", guidance="G1", title="original",
              seq=RD._next_ruling_seq(state))
    panel = _finding("first independent issue")
    key_p = RD._finding_identity_key(panel)
    RD._stage_findings(state, [panel])
    assert state["findingLineage"] == {key_p: key_f}
    assert RD._live_ruling_by_key(state)[key_p]["guidance"] == "G1"
    RD._stage_findings(state, [_finding(later)])
    assert key_p not in (state.get("findingLineage") or {})
    assert key_p not in RD._live_ruling_by_key(state)
    assert [d["kind"] for d in state["decisions"]].count("ruling-carry-revoked") == 1
    # a carry made in an earlier round is not revisited by this round's stagings
    state = _mem_state()
    _add_gate(state, 1, key_f, "fix-with-guidance", guidance="G1", title="original",
              seq=RD._next_ruling_seq(state))
    RD._stage_findings(state, [panel])
    state["round"] += 1
    RD._stage_findings(state, [panel])
    RD._stage_findings(state, [_finding("second independent issue")])
    assert state["findingLineage"] == {key_p: key_f}


@pytest.mark.parametrize("blank", ["   ", None])
def test_blank_gate_guidance_is_a_fix_decision_that_supersedes_earlier_guidance(blank):
    """axis: a later fix-with-guidance with no usable text never lets earlier guidance return."""
    state = _mem_state(2)
    key = _key("subject")
    _add_gate(state, 1, key, "fix-with-guidance", guidance="OLD OWNER INSTRUCTION",
              seq=RD._next_ruling_seq(state))
    entry = _add_gate(state, 2, key, "fix-with-guidance", seq=RD._next_ruling_seq(state))
    if blank is not None:
        entry[RD.GATE_GUIDANCE_RECORD_KEY] = blank
    assert RD._live_ruling_by_key(state)[key]["ruling"] == "fix"
    _batch(state, _finding("subject"))
    assert "OLD OWNER INSTRUCTION" not in RD._gate_guidance_block(_entries(state))


def _restaged_after_skip(ledger_reason, skip_reason, follow_up, *, sequenced):
    """Round 1 records ``follow_up`` on the ledger under ``ledger_reason``; the gate skip on the same
    finding carries ``skip_reason`` (sequenced or legacy); round 2 restages the finding. Returns the
    restaged ledger entry."""
    state = _mem_state(1)
    original = _finding("original")
    key = RD._finding_identity_key(original)
    RD._stage_findings(state, [original])
    RD._record_disposition(state, key, "out-of-scope", 1, outOfScopeReason=ledger_reason,
                           followUp=dict(follow_up))
    _add_gate(state, 1, key, "skip", reason=skip_reason,
              seq=RD._next_ruling_seq(state) if sequenced else None)
    state["round"] = 2
    RD._stage_findings(state, [original])
    return L2E._ledger_by_key(state)[key]


def test_a_sequenced_skip_without_a_follow_up_keeps_none_though_the_reason_matches():
    """axis: follow-up recovery is for legacy (unsequenced) gate skips only — a sequenced skip whose
    reason equals the ledger entry's still gets no follow-up."""
    restaged = _restaged_after_skip("same skip", "same skip", L2E._WELL_FORMED, sequenced=True)
    assert restaged["outOfScopeReason"] == "same skip"
    assert restaged.get("followUp") is None


def test_a_legacy_skip_recovers_the_follow_up_recorded_for_its_own_decision():
    """axis: a legacy (unsequenced) gate skip recovers the follow-up of the ledger entry recorded
    for that same decision — that entry's value, not any other."""
    recorded = dict(L2E._WELL_FORMED, item="split the legacy recovery out",
                    revisitTrigger="when #1301 lands")
    assert session_contract.follow_up_shape_fault(recorded) is None
    assert recorded != L2E._WELL_FORMED
    restaged = _restaged_after_skip("old skip", "old skip", recorded, sequenced=False)
    assert restaged["outOfScopeReason"] == "old skip"
    assert restaged["followUp"] == recorded


def test_a_legacy_skip_never_recovers_a_follow_up_recorded_for_a_different_reason():
    """axis: a legacy (unsequenced) gate skip recovers a follow-up only from a ledger entry recorded
    for the same decision — one recorded for a different reason is not inherited."""
    restaged = _restaged_after_skip("old skip", "a different skip", L2E._WELL_FORMED,
                                    sequenced=False)
    assert restaged["outOfScopeReason"] == "a different skip"
    assert restaged.get("followUp") is None


def test_every_test_in_this_file_names_its_axis():
    """axis: every test function in this file carries a docstring whose first line starts ``axis:``."""
    with open(__file__, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    tests = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")]
    assert tests
    unnamed = [n.name for n in tests
               if not (ast.get_docstring(n) or "").startswith("axis:")]
    assert unnamed == []


def test_a_collapsed_nit_at_the_location_blocks_the_carry():
    """axis: a Nit the readout cap collapsed into a summary row is raised this round — it counts at
    its file and line, so a lone Important rewording there does not inherit the decision."""
    state = _mem_state()
    _add_rule(state, _key("old"), "guidance", guidance="G1", rnd=1)
    important = _finding("new")
    control = copy.deepcopy(state)
    RD._stage_findings(control, [important])
    assert control["findingLineage"] == {RD._finding_identity_key(important): _key("old")}
    nits = [_finding("nit%d" % i, line=100 + i if i < 5 else LINE, severity="Nit",
                     consequenceKind=RD.review_findings_schema.CODE_QUALITY) for i in range(6)]
    compiled, _ = RD.mechanical_compile([important] + nits)
    assert any(f.get("summaryEntry") for f in compiled)
    RD._stage_findings(state, compiled)
    _no_carry(state)


def test_a_rule_out_of_scope_ruling_never_carries_to_a_reword():
    """axis: a rule out-of-scope ruling binds its own finding only — a reworded finding at its
    location is judged fresh and is not excluded from the fix batch."""
    state = _mem_state()
    _add_rule(state, _key("original"), "out-of-scope", rnd=1)
    reworded = _finding("reworded")
    RD._stage_findings(state, [reworded])
    _no_carry(state)
    assert RD._filter_excluded_discharged_fixes(state, [reworded]) == ([reworded], None)


@pytest.mark.parametrize("skipped", ["reworded", "original"])
def test_a_skip_never_reaches_another_finding_through_a_guidance_lineage(skipped):
    """axis: guidance carries across a lineage, but a later skip on one member binds that member only
    — the other member, raised again, reaches the fix batch and is not put to the owner as skipped."""
    state = _mem_state(1)
    key_a = _key("original")
    _add_rule(state, key_a, "guidance", guidance="G1", rnd=1)
    state["round"] = 2
    reworded = _finding("reworded")
    key_b = RD._finding_identity_key(reworded)
    RD._stage_findings(state, [reworded])
    assert state["findingLineage"] == {key_b: key_a}
    skip_key, other_key = (key_b, key_a) if skipped == "reworded" else (key_a, key_b)
    _add_gate(state, 2, skip_key, "skip", seq=RD._next_ruling_seq(state))
    assert RD._live_ruling_by_key(state)[skip_key]["ruling"] == "out-of-scope"
    assert RD._live_ruling_by_key(state)[other_key]["ruling"] == "guidance"
    state["round"] = 3
    other = _finding("original" if other_key == key_a else "reworded")
    RD._stage_findings(state, [other])
    assert L2E._ledger_by_key(state)[other_key].get("disposition") != "out-of-scope"
    assert RD._filter_excluded_discharged_fixes(state, [other]) == ([other], None)


def test_a_rule_guidance_reopens_a_skipped_lineage_member(tmp_path):
    """axis: a rule guidance on one lineage member that supersedes another member's own skip clears
    that member's skip and restores it to the fixer queue."""
    session_dir, _, _, row_a, row_b = RC._pending_apply_fixes_two_findings(tmp_path)
    key_a = RD._fix_batch_row_key(row_a)
    key_b = RD._fix_batch_row_key(row_b)
    state = RC._state(session_dir)
    state["findingLineage"] = {key_b: key_a}
    _add_gate(state, state["round"], key_b, "skip", title=row_b["title"], file=row_b["file"],
              line=row_b["line"], seq=RD._next_ruling_seq(state))
    RD._record_disposition(state, key_b, "out-of-scope", state["round"], outOfScopeReason="why")
    state["_fixQueue"] = [r for r in state.get("_fixQueue") or []
                          if RD._fix_batch_row_key(r) != key_b]
    state["_fixBatch"] = [r for r in state.get("_fixBatch") or []
                          if RD._fix_batch_row_key(r) != key_b]
    RD.save_state(session_dir, state)
    path = RC._write_ruling_file(tmp_path / "r.json", [
        {"id": key_a, "ruling": "guidance", "reason": "keep it small", "guidance": "G2"}])
    assert RC._rule(session_dir, path)["ok"]
    state = RC._state(session_dir)
    assert L2E._ledger_by_key(state)[key_b].get("disposition") != "out-of-scope"
    queued = {RD._fix_batch_row_key(r) for r in (state.get("_fixBatch") or [])
              + (state.get("_fixQueue") or [])}
    assert key_b in queued
