"""C1-L10: every round after the first runs only the fix auditor and the scoped finder; the review ends on a round's
audit and scoped finder, never a panel.

Pins four things, each at the place the rule is enforced:

I1  no path schedules a panel in round 2 or later: a converged review that needed fixes ends `audited-chain` on a
    round's audit and scoped finder, and a fix surface the driver cannot work out hands the PR back
    (`fix-surface-unknown`), never a panel;
I2  the scoped finder is given only the round's own fix delta (`fix-delta.diff` and the scoped hunks), not the
    untouched hunks of a file the fixes touched;
I3  a proven copy is in neither the fix auditor's nor the scoped finder's inputs;
I4  a session saved at a panel in round 2 or later, or at the verify gate that was to lead to one, is handed back
    when it is next loaded.

Drives the real round driver through the CLI functions (`cmd_next`, `cmd_submit`) on a session directory built the
way production builds one.

Bite-proof record: c1l10_wo1_later_rounds
"""
import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
for _p in (_HERE, _LIB):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import countable_lines  # noqa: E402
import review_record as RR  # noqa: E402
import review_record_session as RS  # noqa: E402
import session_contract as SC  # noqa: E402
import test_review_record_session as TRRS  # noqa: E402
import test_round_driver as TRD  # noqa: E402

RD = TRD.RD  # the driver module these sessions run on is test_round_driver's own load of it

VENDORS = ["claude", "codex"]
FIX_SURFACE_UNKNOWN = "fix-surface-unknown"
LATER_PANEL_RETIRED = "later-round-panel-retired"


# --- a session driven through the CLI functions ----------------------------------------------------------

def _start(tmp_path, **cfg_over):
    d = str(tmp_path / "session")
    os.makedirs(d)
    checkout = str(tmp_path / "checkout")
    TRD.enter_checkout(checkout)
    TRD._seed_repo_root_if_missing(d, checkout)
    return d, TRD._cfg(maxRounds=4, **cfg_over)


def _drive(d, respond, cfg, stop_at=None, max_steps=120):
    """next/submit until `next` emits the terminal (or `stop_at`, a phase); returns that `next` answer and every
    `(action, round)` emitted."""
    seen = []
    for step in range(max_steps):
        n = RD.cmd_next(d, cfg if step == 0 else None)
        assert n["ok"], n
        seen.append((n["action"], n["round"]))
        if n["action"] == RD.P_TERMINAL or n["phase"] == stop_at:
            return n, seen
        art = TRD._claim_reviewer(d, n["phase"], respond(n["phase"], n["payload"], n["round"]))
        s = RD.cmd_submit(d, n["phase"], n["attempt"], n["expectedStateHash"], art)
        assert s["ok"], s
    raise AssertionError("the session did not reach its stop in %d steps" % max_steps)


def _respond(finding=None, head=None):
    """Scripted answers: the round-1 panel raises one blocker, the fix reports `head`, every audit discharges and
    the scoped finder raises nothing."""
    return TRD._responder(round1_findings=[finding or dict(TRD._A_FINDING[0])], vendors=VENDORS,
                          head=head or TRD._headf_ns(1))


def _state(d):
    ok, state = RD.load_state(d)
    assert ok and isinstance(state, dict), state
    return state


def _no_panel_after_round_one(seen):
    assert [(a, r) for a, r in seen if a == RD.P_PANEL and r >= 2] == [], seen
    assert (RD.P_PANEL, 1) in seen, seen


def _every_finding_has_an_outcome(d, state):
    ledger = {SC.finding_identity_key(row): row for row in state.get(SC.DISPOSITION_LEDGER_KEY) or []}
    assert ledger, state.get(SC.DISPOSITION_LEDGER_KEY)
    for key, row in ledger.items():
        assert row.get("disposition") in SC.DISPOSITIONS, (key, row)
    account = RS.account_from_session(d, TRRS.extras())
    RR._validate(account)
    assert account["findings"] and all(f.get("outcome") for f in account["findings"]), account["findings"]
    return account


# --- I1: no panel after round 1 ----------------------------------------------------------------------------

def test_i1_a_review_that_needed_fixes_ends_on_a_rounds_audit_and_scoped_finder(tmp_path):
    d, cfg = _start(tmp_path)
    terminal, seen = _drive(d, _respond(), cfg)
    state = _state(d)
    assert terminal["payload"]["verdict"] == "converged", terminal
    assert terminal["payload"]["certification"]["shape"] == "audited-chain"
    assert terminal["payload"]["certification"]["fullPanel"] is False
    assert state["terminal"] == "converged" and state["round"] == 2
    assert state["rounds"]["2"]["roundKind"] == "delta"
    assert (RD.P_AUDITS, 2) in seen and (RD.P_SCOPED, 2) in seen, seen
    _no_panel_after_round_one(seen)


def _unknown_baseline(value):
    """A driver whose round advance leaves `value` where the round's baseline diff record goes."""
    advance = RD._advance_round

    def advancing(state, config, *, reason):
        moved = advance(state, config, reason=reason)
        if moved and state["round"] >= 2:
            if value == "absent":
                state.pop("deltaBaseline", None)
            else:
                state["deltaBaseline"] = value(state) if callable(value) else value
        return moved

    return advancing


def _surface_unknown_cases():
    """(id, how the delta surface is made unknown): the fail-closed edges of a fix surface."""
    return [
        ("baseline-absent", lambda mp: mp.setattr(RD, "_advance_round", _unknown_baseline("absent"))),
        ("baseline-not-a-record", lambda mp: mp.setattr(RD, "_advance_round", _unknown_baseline("text"))),
        ("baseline-stamped-for-another-round", lambda mp: mp.setattr(
            RD, "_advance_round", _unknown_baseline(lambda st: {"round": st["round"] + 1, "diff": st["reviewedDiff"]}))),
        ("baseline-diff-not-text", lambda mp: mp.setattr(
            RD, "_advance_round", _unknown_baseline(lambda st: {"round": st["round"], "diff": 7}))),
        ("split-unknown", lambda mp: mp.setattr(
            RD.delta_surface, "split_fix_surface", lambda *a, **k: {"unknown": True, "auditTargets": {}, "newSurface": {}})),
        ("fix-delta-not-computable", lambda mp: mp.setattr(RD, "_fix_delta_groups", lambda *a, **k: None)),
    ]


@pytest.mark.parametrize("how", [c[1] for c in _surface_unknown_cases()], ids=[c[0] for c in _surface_unknown_cases()])
def test_i1_a_fix_surface_the_driver_cannot_work_out_hands_the_pr_back_and_runs_no_panel(tmp_path, monkeypatch, how):
    how(monkeypatch)
    d, cfg = _start(tmp_path)
    terminal, seen = _drive(d, _respond(), cfg)
    state = _state(d)
    assert terminal["payload"]["verdict"] == "handed-back", terminal
    assert state["terminal"] == "handed-back" and state["decisions"][-1]["kind"] == FIX_SURFACE_UNKNOWN, state["decisions"]
    assert state["certification"]["shape"] is None
    _no_panel_after_round_one(seen)
    assert (RD.P_AUDITS, 2) not in seen and (RD.P_SCOPED, 2) not in seen, seen
    account = _every_finding_has_an_outcome(d, state)
    assert account["rounds"]["stoppedAtCap"] is False  # cap=False: this is no round-cap stop


def test_i1_a_post_fix_head_diff_that_cannot_be_read_hands_the_pr_back_and_runs_no_panel(tmp_path):
    respond = _respond()

    def lost_head(phase, payload, rnd):
        art = respond(phase, payload, rnd)
        return {"fixes": []} if phase == RD.P_APPLY_FIXES else art

    d, cfg = _start(tmp_path)
    terminal, seen = _drive(d, lost_head, cfg)
    state = _state(d)
    assert terminal["payload"]["verdict"] == "handed-back", terminal
    assert state["decisions"][-1]["kind"] == FIX_SURFACE_UNKNOWN, state["decisions"]
    assert state["headDiff"] is None
    _no_panel_after_round_one(seen)
    _every_finding_has_an_outcome(d, state)


# --- I2: the scoped finder reads only the fixes' own delta ----------------------------------------------------

def _hunk(start, old, new):
    """One hunk of seven lines (three of context each side), changing line `start + 3`."""
    lines = ["c%d" % (start + i) for i in range(3)]
    tail = ["c%d" % (start + 4 + i) for i in range(3)]
    return ("@@ -%d,7 +%d,7 @@\n" % (start, start) + "".join(" %s\n" % ln for ln in lines)
            + "-%s\n+%s\n" % (old, new) + "".join(" %s\n" % ln for ln in tail))


def _file_diff(path, *hunks):
    return ("diff --git a/%s b/%s\nindex 1..2 100644\n--- a/%s\n+++ b/%s\n" % (path, path, path, path)
            + "".join(hunks))


PR_DIFF = _file_diff("big.py", _hunk(7, "a10", "b10"), _hunk(97, "a100", "b100"))
FIXED_AT_10 = _file_diff("big.py", _hunk(7, "a10", "fixed10"), _hunk(97, "a100", "b100"))
BLOCKER_AT_10 = {"title": "bug", "severity": "Important", "consequence": TRD._CONSEQUENCE,
                 "file": "big.py", "line": 10}


def _at_the_scoped_finder(tmp_path, head=FIXED_AT_10, diff=PR_DIFF, finding=BLOCKER_AT_10):
    d, cfg = _start(tmp_path, diff=diff)
    n, seen = _drive(d, _respond(finding=dict(finding), head=head), cfg, stop_at=RD.P_SCOPED)
    assert n["phase"] == RD.P_SCOPED, (n["action"], seen)
    return d, n


def _read(d, rnd, name):
    with open(os.path.join(d, "round-%d" % rnd, name), encoding="utf-8") as fh:
        return fh.read()


def test_i2_a_fix_that_touched_only_line_10_gives_the_scoped_finder_nothing_of_the_hunk_at_line_100(tmp_path):
    d, n = _at_the_scoped_finder(tmp_path)
    hunks = _read(d, 2, "scoped-hunks.json")
    fix_delta = _read(d, 2, "fix-delta.diff")
    state = _state(d)
    # the surface is the fix's own change (non-empty, though the fix changed only its own finding's hunk)
    assert list(json.loads(hunks)) == ["big.py"] and n["payload"]["hunks"] == json.loads(hunks)
    assert [(h["start"], h["end"]) for h in json.loads(hunks)["big.py"]] == [(10, 10)]
    assert "fixed10" in fix_delta and fix_delta.startswith("diff --git a/big.py b/big.py\n")
    # ... and nothing of the untouched sibling hunk
    for text in (hunks, fix_delta, state["_fixDeltaDiff"]):
        for sibling in ("a100", "b100", "c97", "c101", "@@ -97"):
            assert sibling not in text, (sibling, text)
    assert all(h["start"] < 90 for h in state["_newSurface"]["big.py"]), state["_newSurface"]


def test_i2_the_scoped_finders_order_cites_the_fix_delta_and_no_head_diff(tmp_path):
    d, _n = _at_the_scoped_finder(tmp_path)
    orders = os.path.join(d, "round-2", "orders", RD.P_SCOPED)
    [name] = [f for f in os.listdir(orders) if f.endswith(".md")]
    with open(os.path.join(orders, name), encoding="utf-8") as fh:
        order = fh.read()
    fix_delta = os.path.join(d, "round-2", "fix-delta.diff")
    assert "The fixes' own diff (read cited hunks here; nothing else of the change): %s\n" % fix_delta in order
    assert os.path.isfile(fix_delta)
    assert "head.diff" not in order and "{{" not in order


def test_i2_a_hunk_header_that_only_renumbers_is_not_part_of_the_fix_delta(tmp_path):
    # the fix adds a line in the first hunk, so git renumbers the second hunk's header: no content changed there
    grown = _file_diff("big.py", _hunk(7, "a10", "b10").replace("@@ -7,7 +7,7 @@", "@@ -7,7 +7,8 @@")
                       .replace("+b10\n", "+b10\n+extra\n"),
                       _hunk(97, "a100", "b100").replace("+97,7", "+98,7"))
    d, _n = _at_the_scoped_finder(tmp_path, head=grown)
    fix_delta = _read(d, 2, "fix-delta.diff")
    assert "extra" in fix_delta
    # nothing of the second hunk's content is in the delta (its renumbered header may ride as context)
    for sibling in ("a100", "b100", "c101"):
        assert sibling not in fix_delta, (sibling, fix_delta)
    hunks = _state(d)["_newSurface"]["big.py"]
    assert [(h["start"], h["end"]) for h in hunks] == [(11, 11)], hunks  # the added line, and no line near 100


def test_i2_a_file_the_fix_removed_keeps_the_removal_marker_on_the_surface(tmp_path):
    reviewed = _file_diff("keep.py", _hunk(7, "a10", "b10")) + _file_diff("gone.py", _hunk(7, "a10", "b10"))
    head = _file_diff("keep.py", _hunk(7, "a10", "fixed10"))
    state = RD.new_state(TRD._cfg(diff=reviewed))
    state.update(round=2, rounds={"2": {}}, decisions=[], reviewedDiff=head, headDiff=head,
                 deltaBaseline={"round": 2, "diff": reviewed},
                 fixBatch=[dict(BLOCKER_AT_10, file="keep.py")])
    RD._enter_delta_round(state, TRD._cfg(diff=reviewed))
    assert state["step"] == RD.P_AUDITS
    assert state["_newSurface"]["gone.py"] == [
        {"start": 0, "end": 0, "removed": True, "text": "@@ file removed between the reviewed and head diffs @@"}]
    assert "diff --git a/gone.py b/gone.py\n" in state["_fixDeltaDiff"]
    assert [(h["start"], h["end"]) for h in state["_newSurface"]["keep.py"]] == [(10, 10)]


# --- I3: a proven copy is no seat's input ----------------------------------------------------------------------

def _round_two_state_with_a_proven_copy():
    """Round 2 over two files the fix touched; `copy.py`'s head section is the proven one."""
    reviewed = _file_diff("copy.py", _hunk(7, "a10", "pre-fix")) + _file_diff("other.py", _hunk(7, "a10", "b10"))
    head = _file_diff("copy.py", _hunk(7, "a10", "b10")) + _file_diff("other.py", _hunk(7, "a10", "fixed10"))
    cfg = TRD._cfg(diff=reviewed)
    state = RD.new_state(cfg)
    state.update(round=2, rounds={"2": {}}, decisions=[], reviewedDiff=head, headDiff=head,
                 deltaBaseline={"round": 2, "diff": reviewed},
                 fixBatch=[dict(BLOCKER_AT_10, file="other.py")],
                 provenCopies=[{"file": "copy.py", "source": "origin/copy.py", "sha256": "0" * 64,
                                "section": countable_lines.section_digest(head, "copy.py")}])
    assert RD._left_out_files(state) == ["copy.py"]
    return state, cfg


def test_i3_a_proven_copy_the_fix_touched_is_in_no_audit_or_scoped_input(tmp_path):
    state, cfg = _round_two_state_with_a_proven_copy()
    RD._enter_delta_round(state, cfg)
    assert state["step"] == RD.P_AUDITS
    d = str(tmp_path / "session")
    os.makedirs(d)
    targets = state["_auditTargets"]
    roster = [t["id"] for t in targets]
    RD._materialize_order_sidecars(d, 2, RD.P_AUDITS, roster, {"targets": targets})
    RD._materialize_order_sidecars(d, 2, RD.P_SCOPED, ["scoped-finder"], {"hunks": state["_newSurface"]})
    fix_delta = RD._ensure_round_fix_delta(d, 2, state)
    inputs = {}
    for root, _dirs, names in os.walk(d):
        for name in names:
            with open(os.path.join(root, name), encoding="utf-8") as fh:
                inputs[os.path.relpath(os.path.join(root, name), d)] = fh.read()
    assert os.path.relpath(fix_delta, d) in inputs and len(inputs) == len(targets) + 2, sorted(inputs)
    for name, text in inputs.items():
        assert "copy.py" not in text, name  # its path, its hunks and its delta
        assert "pre-fix" not in text, name
    # the file that is not a copy is there, so the absence is the filter's doing
    assert "fixed10" in inputs[os.path.relpath(fix_delta, d)]
    assert list(state["_newSurface"]) == ["other.py"]
    assert all("copy.py" not in json.dumps(t.get("fixHunks")) + json.dumps(t.get("fixerDelta")) for t in targets)
    assert any("fixed10" in json.dumps(t.get("fixerDelta")) for t in targets)


def test_i3_a_round_whose_fixes_touched_only_proven_copies_skips_the_scoped_finder(monkeypatch):
    reviewed = _file_diff("copy.py", _hunk(7, "a10", "pre-fix")) + _file_diff("other.py", _hunk(7, "a10", "b10"))
    head = _file_diff("copy.py", _hunk(7, "a10", "b10")) + _file_diff("other.py", _hunk(7, "a10", "b10"))
    cfg = TRD._cfg(diff=reviewed)
    state = RD.new_state(cfg)
    state.update(round=2, rounds={"2": {}}, decisions=[], reviewedDiff=head, headDiff=head,
                 deltaBaseline={"round": 2, "diff": reviewed},
                 fixBatch=[dict(BLOCKER_AT_10, file="copy.py")],
                 provenCopies=[{"file": "copy.py", "source": "origin/copy.py", "sha256": "0" * 64,
                                "section": countable_lines.section_digest(head, "copy.py")}])
    RD._enter_delta_round(state, cfg)
    assert state["_newSurface"] == {} and state["_fixDeltaDiff"] == ""
    folded = []
    monkeypatch.setattr(RD, "_fold_scoped", lambda st, config, artifact: folded.append(artifact))
    RD._after_audits(state, cfg)
    assert state["rounds"]["2"]["scopedFinder"] == "skipped-empty-surface" and folded == [{}]
    assert state["step"] == RD.P_AUDITS  # no scoped dispatch was scheduled


# --- I4: a session saved at a later-round panel is handed back when loaded ----------------------------------------

def _saved_at_round_one_panel(tmp_path):
    d, cfg = _start(tmp_path)
    n = RD.cmd_next(d, cfg)
    assert n["ok"] and n["action"] == RD.P_PANEL and n["round"] == 1, n
    return d, _state(d)


def _save(d, state):
    RD.save_state(d, state)


def _retired_rows(d):
    return [row for row in RD.read_journal(d) if row.get("outcome") == "retired-gate-hand-back"]


def _assert_handed_back(d, answer):
    assert answer["ok"] and answer["action"] == RD.P_TERMINAL, answer
    assert answer["payload"]["verdict"] == "handed-back", answer
    state = _state(d)
    assert state["terminal"] == "handed-back" and state["pending"]["phase"] == RD.P_TERMINAL
    assert state["decisions"][-1]["kind"] == LATER_PANEL_RETIRED
    assert state["certification"]["shape"] is None and "panel" in state["certification"]["reason"]
    assert len(_retired_rows(d)) == 1, _retired_rows(d)
    account = _every_finding_has_an_outcome(d, state) if state.get(SC.DISPOSITION_LEDGER_KEY) else None
    if account is not None:
        assert account["rounds"]["stoppedAtCap"] is False
    return state


@pytest.mark.parametrize("pending", [True, False], ids=["panel-pending", "panel-step-only"])
def test_i4_a_session_saved_at_a_panel_in_round_two_is_handed_back_before_anything_emits_it(tmp_path, pending):
    d, state = _saved_at_round_one_panel(tmp_path)
    state["round"] = 2
    if pending:
        state["pending"]["round"] = 2
    else:
        state["pending"] = None
    assert state["step"] == RD.P_PANEL
    _save(d, state)
    answer = RD.cmd_next(d)
    _assert_handed_back(d, answer)
    again = RD.cmd_next(d)  # replays the terminal; the hand-back is journaled once
    assert again["ok"] and again["payload"] == answer["payload"] and len(_retired_rows(d)) == 1


def test_i4_a_session_saved_at_the_verify_gate_that_led_to_a_panel_is_handed_back(tmp_path):
    d, state = _saved_at_round_one_panel(tmp_path)
    state.update(round=2, step=RD.P_VERIFY, pending=None, _verifyThen="full-panel")
    _save(d, state)
    answer = RD.cmd_next(d)
    final = _assert_handed_back(d, answer)
    assert "_verifyThen" not in final


def test_i4_a_round_one_panel_is_left_as_it_is(tmp_path):
    d, state = _saved_at_round_one_panel(tmp_path)
    answer = RD.cmd_next(d)
    assert answer["ok"] and answer["action"] == RD.P_PANEL and answer["round"] == 1, answer
    assert _retired_rows(d) == []
    assert _state(d)["terminal"] is None


def test_i4_a_current_generation_state_is_handed_back_by_the_same_load_chokepoint(tmp_path):
    d, state = _saved_at_round_one_panel(tmp_path)
    assert state["sessionGeneration"] == RD.SESSION_GENERATION
    state["round"] = 3
    state["pending"] = None
    _save(d, state)
    assert RD._finish_retired_gate_step(_state(d)) is False  # the earlier-generation guard does not apply ...
    _assert_handed_back(d, RD.cmd_next(d))  # ... and the later-panel check still does


def test_i4_a_round_two_panel_state_at_its_cap_is_retired_but_above_its_cap_hands_back_round_cap(tmp_path):
    # axis: the cap guard owns a loaded state above its round cap; the later-panel retirement leaves it alone
    d, state = _saved_at_round_one_panel(tmp_path / "at-cap")
    cap = state["config"]["maxRounds"]
    assert cap >= 2
    state.update(round=cap, pending=None)
    _save(d, state)
    _assert_handed_back(d, RD.cmd_next(d))  # round == cap: still the retired later panel

    d, state = _saved_at_round_one_panel(tmp_path / "over-cap")
    state.update(round=cap + 1, pending=None)
    _save(d, state)
    answer = RD.cmd_next(d)
    assert answer["ok"] and answer["action"] == RD.P_TERMINAL, answer
    final = _state(d)
    assert final["terminal"] == "handed-back" and final["decisions"][-1]["kind"] == "round-cap"
    assert _retired_rows(d) == []
