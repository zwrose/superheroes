"""Focus notes reach the scoped finder, or their absence is disclosed (#2382).

Invariant: focus notes given to a review session reach every seat order whose template can carry
them, and every order emitted while notes are set whose template cannot carry them is disclosed on
the round record (`focusNotesNotCarried`) and in the receipt's `degraded` list. With no focus notes
nothing changes.

These tests read the order file the driver actually RENDERS and writes in a fixture session (via the
manifest's `orderPath`), never the renderer alone: the defect was upstream of the renderer — the
driver never handed the scoped finder's notes to it.
"""
import importlib.util
import json
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
RR = _load("round_records")
RO = _load("round_orders")
RDISC = _load("receipt_disclosures")
MR = _load("model_registry")

ENGINE_SEAT = RD.DIMENSIONS[0]


def _section(path, third):
    return ("diff --git a/%s b/%s\n" % (path, path)
            + "index 1111111..2222222 100644\n"
            + "--- a/%s\n" % path
            + "+++ b/%s\n" % path
            + "@@ -1,2 +1,4 @@\n alpha\n+beta\n+%s\n delta\n" % third)


DIFF = "".join(_section("src/f%02d.py" % i, "gamma") for i in range(3))


def _mixed_seat_map():
    seats = {}
    for dim in RD.DIMENSIONS:
        if dim == ENGINE_SEAT:
            seats[dim] = {"vendor": "codex", "model": "gpt-5.1-codex-max", "engine": "codex"}
        else:
            seats[dim] = {"vendor": "claude", "model": "sonnet-5.5", "engine": "claude"}
    return {"seats": seats}


def _nonpanel_cell_proof(vendors):
    """The seat-map keys proving each vendor's dispatched non-panel cells live: without them the
    non-panel selector seats no reviewer and no order is rendered at all."""
    cells = []
    for role in ("verifier", "reviewer-deep"):
        for vendor in vendors:
            cell = MR.matrix_config(role, vendor)
            if cell is not None:
                cells.append([vendor, cell[0], cell[1]])
    return {"nonPanelLiveCells": cells, "nonPanelLiveCellsSource": "synthesized"}


def _seat_for(phase):
    if phase == RD.P_VERIFIERS:
        return "verifier:c1"
    return phase


def _payload_for(phase, clusters=("c1",)):
    if phase == RD.P_VERIFIERS:
        return {"clusters": [{"key": key, "issues": []} for key in clusters]}
    return {}


def _session(tmp_path, monkeypatch, name, focus_notes):
    """A fixture session after `next`, ready for `_emit_orders_manifest` on any phase."""
    session_dir = str(tmp_path / name)
    os.makedirs(session_dir, exist_ok=True)
    cfg = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF,
           "fixerVendor": "claude", "verifyCommand": "none",
           "seatMap": dict(_mixed_seat_map(), **_nonpanel_cell_proof(["claude", "codex"]))}
    if focus_notes is not None:
        cfg["focusNotes"] = focus_notes
    out = RD.cmd_next(session_dir, cfg)
    assert out["ok"], out
    ok, state = RD.load_state(session_dir)
    assert ok, state
    state["headDiff"] = DIFF
    state["_fixDeltaDiff"] = DIFF
    state["rounds"].setdefault(str(state["round"]), {}).pop("focusNotesNotCarried", None)
    monkeypatch.setattr(RD.engine_pref, "load_engine_prefs", lambda _root: {})
    monkeypatch.setattr(RD.engine_pref, "resolve_engine", lambda _role, _prefs: "claude")
    return session_dir, state


def _emit(session_dir, state, phase, attempt=0, seats=None, clusters=("c1",)):
    seats = seats if seats is not None else [_seat_for(phase)]
    RD._emit_orders_manifest(session_dir, state, state["round"], phase, attempt, seats,
                             journal_cmd="next", pending_payload=_payload_for(phase, clusters),
                             seat_map={})


def _manifest(session_dir, state, phase, attempt=0):
    with open(RD._orders_manifest_path(session_dir, state["round"], phase, attempt),
              encoding="utf-8") as fh:
        return json.load(fh)


def _order_texts(session_dir, state, phase, attempt=0):
    texts = {}
    for skey, entry in _manifest(session_dir, state, phase, attempt)["seats"].items():
        with open(entry["orderPath"], encoding="utf-8") as fh:
            texts[skey] = fh.read()
    return texts


def _round_rec(state):
    return state["rounds"].get(str(state["round"])) or {}


def test_t1_scoped_finder_order_carries_the_focus_notes(tmp_path, monkeypatch):
    session_dir, state = _session(tmp_path, monkeypatch, "t1", "check the fix order item 3")
    _emit(session_dir, state, RD.P_SCOPED)
    texts = _order_texts(session_dir, state, RD.P_SCOPED)
    assert len(texts) == 1, texts
    (text,) = texts.values()
    assert "- Focus: check the fix order item 3" in text.split("\n"), text[:1500]
    rows = _round_rec(state).get("focusNotesNotCarried") or []
    assert not any(r.get("phase") == RD.P_SCOPED for r in rows), rows


def test_t2_placeholder_syntax_in_notes_renders_escaped(tmp_path, monkeypatch):
    notes = "see " + "{" * 2 + "HUNKS_PATH" + "}" * 2 + " first"
    session_dir, state = _session(tmp_path, monkeypatch, "t2", notes)
    _emit(session_dir, state, RD.P_SCOPED)
    (text,) = _order_texts(session_dir, state, RD.P_SCOPED).values()
    assert "- Focus: see { {HUNKS_PATH" + "}" * 2 + " first" in text, text[:1500]


def test_t3_an_order_that_cannot_carry_the_notes_is_disclosed_on_the_round_and_receipt(
        tmp_path, monkeypatch):
    session_dir, state = _session(tmp_path, monkeypatch, "t3", "check the fix order item 3")
    _emit(session_dir, state, RD.P_VERIFIERS)
    skey = RR.storage_key("verifier:c1", 0)
    assert _round_rec(state).get("focusNotesNotCarried") == [
        {"phase": RD.P_VERIFIERS, "seats": [skey]}], _round_rec(state)
    degraded, _skipped = RDISC.build_degraded_prose(state, RD.RECEIPT_FORM_CERTIFIED)
    lines = [line for line in degraded if line.startswith("focus-notes-not-carried (round ")]
    assert len(lines) == 1, degraded
    assert RD.P_VERIFIERS in lines[0] and skey in lines[0], lines[0]


def test_t4_carrying_phases_are_derived_from_the_templates():
    needle = "{" * 2 + "FOCUS_CONTEXT_LINE" + "}" * 2
    carrying = set()
    for phase in RO.ORDER_PHASES:
        ctx = {"payload": {}}
        carries, reason = RO.order_carries_focus(phase, ctx)
        with open(RO.order_template_path(RO._template_name(phase, ctx)), encoding="utf-8") as fh:
            has_needle = needle in fh.read()
        assert carries is has_needle, (phase, carries, reason)
        if carries:
            carrying.add(phase)
            assert reason is None
        else:
            assert isinstance(reason, str) and reason, (phase, reason)
    assert carrying == {RD.P_PANEL, RD.P_SCOPED}, carrying
    # the second-test correction form reads its own template, which carries no focus line
    carries, _reason = RO.order_carries_focus(RD.P_SECOND_TEST, {"payload": {"correction": True}})
    assert carries is False


def test_t4b_a_phase_without_a_template_cannot_carry_and_never_raises():
    carries, reason = RO.order_carries_focus("no-such-phase", {})
    assert carries is False and isinstance(reason, str) and reason, (carries, reason)
    carries, reason = RO.order_carries_focus(RD.P_PANEL, None)
    assert carries is True and reason is None


@pytest.mark.parametrize("notes", [None, "", "   \n\t "])
def test_t5_no_focus_notes_changes_nothing(tmp_path, monkeypatch, notes):
    session_dir, state = _session(tmp_path, monkeypatch, "t5", notes)
    _emit(session_dir, state, RD.P_SCOPED)
    _emit(session_dir, state, RD.P_VERIFIERS)
    texts = {}
    texts.update(_order_texts(session_dir, state, RD.P_SCOPED))
    texts.update(_order_texts(session_dir, state, RD.P_VERIFIERS))
    assert len(texts) == 2, sorted(texts)
    for skey, text in texts.items():
        assert "- Focus:" not in text, (skey, text[:1500])
    assert "focusNotesNotCarried" not in _round_rec(state), _round_rec(state)
    degraded, _skipped = RDISC.build_degraded_prose(state, RD.RECEIPT_FORM_CERTIFIED)
    assert not any("focus-notes-not-carried" in line for line in degraded), degraded


def _scoped_render_context(focus_notes):
    """A direct `render_order` context for the scoped finder; `focus_notes=None` leaves the key out."""
    session = "/tmp/superheroes-session-t7"
    rubric = os.path.join(os.path.dirname(_LIB), "rubric", "review-base.md")
    ph = {
        "HUNKS_PATH": os.path.join(session, "round-2", "scoped-hunks.json"),
        "FIX_DIFF_PATH": os.path.join(session, "round-2", "fix-delta.diff"),
        "RUBRIC_PATH": rubric,
        "CORE_PATH": "(Core calibration not resolved for this project)",
        "LAYER_PATH": "(Review-crew layer calibration not resolved for this project)",
        "VERIFICATION_ROOT": "/home/user/proj",
        "CLAUDE_MD_PATH": "/home/user/proj/CLAUDE.md",
        "FINDINGS_OUTPUT_PATH": os.path.join(session, "round-2", "scoped-findings.json"),
        "CHANNEL": "file",
    }
    if focus_notes is not None:
        ph["FOCUS_NOTES"] = focus_notes
    return {
        "session_dir": session, "round": 2, "attempt": 0,
        "diff_path": os.path.join(session, "round-2", "diff.txt"),
        "rubric_path": rubric, "core_path": "", "layer_path": "", "repo_root": "/home/user/proj",
        "landing_path": os.path.join(session, "round-2", "landing", "scoped-finder.a0.payload.json"),
        "envelope_stub_path": os.path.join(session, "round-2", "stubs", "seat.json"),
        "ratified_residuals": "- Flaky integration test in CI lane B is accepted",
        "residuals_provenance": "Residuals below are read from the review base commit (base-pinned).",
        "residuals_read_failure": None,
        "threat_model": "Attackers can forge session cookies.",
        "threat_model_read_failure": None,
        "standing_rulings": [], "standing_rulings_read_failure": None,
        "payload": {}, "host_seat": True, "placeholders": ph,
    }


def test_t7_whitespace_only_notes_render_the_scoped_order_byte_identically_to_no_notes():
    absent, reason_a = RO.render_order(RD.P_SCOPED, "seat", _scoped_render_context(None))
    blank, reason_b = RO.render_order(RD.P_SCOPED, "seat", _scoped_render_context("   "))
    assert reason_a is None and reason_b is None, (reason_a, reason_b)
    assert absent == blank
    assert "- Focus:" not in absent
    (conv,) = [line for line in absent.split("\n") if line.startswith("- Project conventions:")]
    assert ("%s\n\n## Your assignment" % conv) in absent, absent[:1500]


def test_t6_a_phase_emitted_twice_in_a_round_unions_its_seats_and_keeps_earlier_rows(
        tmp_path, monkeypatch):
    session_dir, state = _session(tmp_path, monkeypatch, "t6", "check the fix order item 3")
    _emit(session_dir, state, RD.P_SEAMS)
    _emit(session_dir, state, RD.P_VERIFIERS, attempt=0, seats=["verifier:c1"], clusters=("c1",))
    _emit(session_dir, state, RD.P_VERIFIERS, attempt=1, seats=["verifier:c2"], clusters=("c2",))
    rows = _round_rec(state).get("focusNotesNotCarried")
    by_phase = {r["phase"]: r for r in rows}
    assert len(rows) == len(by_phase) == 2, rows
    assert by_phase[RD.P_VERIFIERS]["seats"] == sorted(
        [RR.storage_key("verifier:c1", 0), RR.storage_key("verifier:c2", 0)]), rows
    assert by_phase[RD.P_SEAMS]["seats"] == [RR.storage_key(RD.P_SEAMS, 0)], rows


def test_e3_a_malformed_row_is_skipped_by_the_receipt_never_raised(tmp_path, monkeypatch):
    session_dir, state = _session(tmp_path, monkeypatch, "e3", "notes")
    state["rounds"][str(state["round"])]["focusNotesNotCarried"] = [
        {"phase": "", "seats": ["a"]}, {"phase": RD.P_SEAMS, "seats": "a"},
        {"phase": RD.P_SEAMS, "seats": [1]}, {"phase": RD.P_SEAMS},
    ]
    degraded, _skipped = RDISC.build_degraded_prose(state, RD.RECEIPT_FORM_CERTIFIED)
    assert not any("focus-notes-not-carried" in line for line in degraded), degraded


@pytest.mark.parametrize("malformed", [
    {"phase": "", "seats": ["a"]},
    {"phase": RD.P_SEAMS, "seats": "a"},
    {"phase": RD.P_SEAMS, "seats": [1]},
    {"phase": RD.P_SEAMS},
    "not-a-row",
])
def test_e3b_a_malformed_row_is_skipped_and_a_later_valid_row_still_surfaces(
        tmp_path, monkeypatch, malformed):
    session_dir, state = _session(tmp_path, monkeypatch, "e3b", "notes")
    state["rounds"][str(state["round"])]["focusNotesNotCarried"] = [
        malformed, {"phase": RD.P_VERIFIERS, "seats": ["kept-seat"]},
    ]
    degraded, _skipped = RDISC.build_degraded_prose(state, RD.RECEIPT_FORM_CERTIFIED)
    lines = [line for line in degraded if "focus-notes-not-carried" in line]
    if isinstance(malformed, str):
        # the shape check drops a list holding a non-dict member, so no line appears
        assert lines == [], degraded
        return
    assert len(lines) == 1, degraded
    assert RD.P_VERIFIERS in lines[0] and "kept-seat" in lines[0], lines[0]
    assert "dispatch-seams-check" not in lines[0], lines[0]
