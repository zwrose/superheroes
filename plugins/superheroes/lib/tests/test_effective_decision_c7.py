"""One effective decision per finding, carried across rewording (review fix loop).

A finding has exactly one effective decision: the latest of a ``rule`` ruling and an owner-gate
decision by one sequence, read through ``_live_ruling_by_key``. It binds the finding under any
wording a later round gives it at the same file and line, and the fixer order renders only it.
"""
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
    row = {"seq": RD._next_ruling_seq(state), "round": rnd or state["round"], "phase": RD.P_FIXER,
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
    session_dir, _, _, row_a, _row_b = RC._pending_fixer_two_findings(tmp_path)
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


def test_t3_precedence_latest_decision_renders_alone(tmp_path):
    """axis: gate guidance and rule guidance on one key render one text — the later by one sequence.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-3)
    """
    # gate guidance "A", then a rule guidance "B" -> only "B"
    session_dir = L2E._parked_judgment_session(tmp_path, name="gate-then-rule")
    out = L2E._pending_submit(session_dir, {"dispositions": [
        {"id": L2E._TRADEOFF_ID, "disposition": "fix-with-guidance", "guidance": "A"}]})
    assert out["ok"] is True, out
    state = L2E._load_state(session_dir)
    key = L2E._TRADEOFF_ID
    gate_rows = state["rounds"][str(state["round"])]["judgmentDispositions"]
    assert gate_rows[0]["rulingSeq"] == state["rulingSeqCounter"]
    assert key in {RD._fix_batch_row_key(r) for r in state["_fixBatch"]}
    _add_rule(state, key, "guidance", guidance="B", file="f.py", line=1)
    entries = _entries(state)
    assert [(e["id"], e["guidance"], bool(e.get("rulingChannel"))) for e in entries] == [
        (key, "B", True)]
    block = RD._gate_guidance_block(entries)
    assert "B" in block and "> A" not in block
    # a rule guidance, then a later sequenced gate guidance "A" -> only "A"
    session_dir = L2E._parked_judgment_session(tmp_path, name="rule-then-gate")
    state = L2E._load_state(session_dir)
    _add_rule(state, key, "guidance", guidance="B", file="f.py", line=1)
    RD.save_state(session_dir, state)
    out = L2E._pending_submit(session_dir, {"dispositions": [
        {"id": key, "disposition": "fix-with-guidance", "guidance": "A"}]})
    assert out["ok"] is True, out
    state = L2E._load_state(session_dir)
    gate_rows = state["rounds"][str(state["round"])]["judgmentDispositions"]
    assert gate_rows[0]["rulingSeq"] == 2
    entries = _entries(state)
    assert [(e["id"], e["guidance"], bool(e.get("rulingChannel"))) for e in entries] == [
        (key, "A", False)]
    assert "> B" not in RD._gate_guidance_block(entries)


def test_t4_gate_skip_binds_a_reword(tmp_path):
    """axis: an owner-gate skip is a decision — it keeps binding the finding after a reword.

    bite-proof: plugins/superheroes/lib/tests/bite_proofs/wo1a_c7_effective_decision.md (BP-4)
    """
    session_dir = L2E._parked_judgment_session(tmp_path)
    out = L2E._pending_submit(session_dir, {"dispositions": [
        {"id": L2E._TRADEOFF_ID, "disposition": "skip", "reason": "product choice",
         "followUp": dict(L2E._WELL_FORMED)}]})
    assert out["ok"] is True, out
    state = L2E._load_state(session_dir)
    skip_row = state["rounds"][str(state["round"])]["judgmentDispositions"][0]
    assert (skip_row["file"], skip_row["line"]) == ("f.py", 1)
    assert skip_row["rulingSeq"] == state["rulingSeqCounter"]
    assert skip_row["followUp"] == L2E._WELL_FORMED
    state["round"] += 1
    reworded = _finding("widen the public API", line=1, file="f.py", tradeoff=True)
    key_new = RD._finding_identity_key(reworded)
    RD._stage_findings(state, [reworded])
    assert state["findingLineage"] == {key_new: L2E._TRADEOFF_ID}
    carried = L2E._ledger_by_key(state)[key_new]
    assert carried["disposition"] == "out-of-scope"
    assert carried["followUp"] == L2E._WELL_FORMED
    assert key_new in RD._live_out_of_scope_ruling_keys(state)
    assert RD._filter_excluded_discharged_fixes(state, [reworded]) == ([], None)
    # the review record's rulings list stays rule-sourced only
    assert RD._standing_rulings_for_orders(state) == ([], None)
    # normal routing: the carried skip is honored, never put to the owner again
    state["findings"] = [dict(reworded, verdict="CONFIRMED")]
    RD._after_findings_settled(state, state["config"])
    assert state["step"] != RD.P_JUDGMENT
    assert not state.get("_judgmentFindings")
    assert any(d["kind"] == "fix-batch-excluded" for d in state["decisions"])
    # the original wording restaged a round later keeps the whole decision, follow-up included
    state["round"] += 1
    RD._stage_findings(state, [_finding("widen the API", line=1, file="f.py")])
    restaged = L2E._ledger_by_key(state)[L2E._TRADEOFF_ID]
    assert restaged["disposition"] == "out-of-scope"
    assert restaged["followUp"] == L2E._WELL_FORMED


def test_t5_edge1_two_compiled_findings_at_the_location_do_not_carry():
    state = _mem_state()
    _add_rule(state, _key("original"), "guidance", guidance="G1", rnd=1)
    RD._stage_findings(state, [_finding("first rewording"), _finding("second rewording")])
    _no_carry(state)
    _batch(state, _finding("first rewording"))
    assert _entries(state) == []


def test_t6_edge2_decided_finding_reraised_in_the_same_compile_does_not_carry():
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
    state = _mem_state()
    _add_rule(state, _key("original"), "guidance", guidance="G1", file=None, rnd=1)
    RD._stage_findings(state, [_finding("reworded")])
    _no_carry(state)


def test_t9_edge5_unsequenced_gate_guidance_loses_to_a_later_rule_guidance():
    state = _mem_state(2)
    key = _key("subject")
    _add_gate(state, 1, key, "fix-with-guidance", guidance="LEGACY GATE", seq=None)
    _add_rule(state, key, "guidance", guidance="RULE", rnd=2)
    _batch(state, _finding("subject"))
    entries = _entries(state)
    assert [(e["id"], e["guidance"], e.get("rulingChannel")) for e in entries] == [
        (key, "RULE", True)]


def test_t10_edge6_sequenced_gate_guidance_after_a_rule_guidance_renders_alone():
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
    state = _mem_state(3)
    key = _key("subject")
    _add_gate(state, 1, key, "fix-with-guidance", guidance="OLD", seq=None)
    _add_gate(state, 2, key, "fix-with-guidance", guidance="NEWER", seq=None)
    assert RD._live_ruling_by_key(state)[key]["guidance"] == "NEWER"
    _batch(state, _finding("subject"))
    assert [e["guidance"] for e in _entries(state)] == ["NEWER"]


def test_gate_skip_after_rule_guidance_renders_nothing():
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
    _add_rule(state, key_f, "out-of-scope", rnd=1)
    # control: the gap finding alone in the round carries
    control = copy.deepcopy(state)
    RD._stage_findings(control, [_finding("independent gap issue")])
    assert control["findingLineage"] == {_key("independent gap issue"): key_f}
    # the panel re-raises the decided original; the gap sweep then stages an independent finding
    RD._stage_findings(state, [_finding("original")])
    gap = _finding("independent gap issue")
    RD._stage_findings(state, [gap])
    _no_carry(state)
    assert RD._filter_excluded_discharged_fixes(state, [gap]) == ([gap], None)
    # another finding already raised at the location this round blocks the carry the same way
    state = _mem_state()
    _add_rule(state, key_f, "out-of-scope", rnd=1)
    RD._stage_findings(state, [_finding("unrelated panel issue")])
    state.pop("findingLineage", None)
    state["decisions"] = [d for d in state["decisions"] if d["kind"] != "ruling-carried"]
    RD._stage_findings(state, [_finding("independent gap issue")])
    assert _key("independent gap issue") not in (state.get("findingLineage") or {})


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


@pytest.mark.parametrize("disposition", [{"disposition": "fix-as-suggested"}, {}])
def test_fix_at_the_gate_after_a_skip_reaches_the_fixer(disposition):
    """axis: through the judgment fold, a fix choice (explicit or fail-closed) on a finding an earlier
    round skipped clears the restaged out-of-scope disposition and queues the fix."""
    state = _mem_state(2)
    finding = _finding("subject", tradeoff=True)
    key = RD._finding_identity_key(finding)
    _add_gate(state, 1, key, "skip", seq=RD._next_ruling_seq(state))
    RD._stage_findings(state, [finding])
    assert L2E._ledger_by_key(state)[key]["disposition"] == "out-of-scope"
    state["findings"] = [dict(finding)]
    state["_judgmentFindings"] = [dict(finding)]
    state["_judgmentMechanical"] = []
    RD._fold_judgment(state, state["config"], {"dispositions": [dict(disposition, id=key)]})
    logged = state["rounds"]["2"]["judgmentDispositions"][-1]
    assert logged["rulingSeq"] == state["rulingSeqCounter"]
    assert RD._live_ruling_by_key(state)[key]["ruling"] == "fix"
    assert state["step"] == RD.P_FIXER
    assert key in {RD._fix_batch_row_key(r) for r in state["_fixBatch"]}
    assert L2E._ledger_by_key(state)[key].get("disposition") != "out-of-scope"


@pytest.mark.parametrize("later", ["original", "second independent issue"])
def test_a_same_round_carry_is_undone_when_a_later_staging_makes_it_ambiguous(later):
    """axis: a carry is provisional until the round's last staging — a gap sweep that raises the
    decided original (or another finding at the place) after the panel's carry undoes it, along
    with the skip it inherited; a carry from an earlier round stands."""
    state = _mem_state()
    key_f = _key("original")
    _add_gate(state, 1, key_f, "skip", title="original", seq=RD._next_ruling_seq(state))
    panel = _finding("first independent issue")
    key_p = RD._finding_identity_key(panel)
    RD._stage_findings(state, [panel])
    assert state["findingLineage"] == {key_p: key_f}
    assert L2E._ledger_by_key(state)[key_p]["disposition"] == "out-of-scope"
    RD._stage_findings(state, [_finding(later)])
    assert key_p not in (state.get("findingLineage") or {})
    assert key_p not in RD._live_out_of_scope_ruling_keys(state)
    assert L2E._ledger_by_key(state)[key_p].get("disposition") != "out-of-scope"
    assert RD._filter_excluded_discharged_fixes(state, [panel]) == ([panel], None)
    assert [d["kind"] for d in state["decisions"]].count("ruling-carry-revoked") == 1
    # a carry made in an earlier round is not revisited by this round's stagings
    state = _mem_state()
    _add_gate(state, 1, key_f, "skip", title="original", seq=RD._next_ruling_seq(state))
    RD._stage_findings(state, [panel])
    state["round"] += 1
    RD._stage_findings(state, [panel])
    RD._stage_findings(state, [_finding("second independent issue")])
    assert state["findingLineage"] == {key_p: key_f}
