"""Interim receipt at non-terminal stops — per-pass verdict totals (#1107 WO-C)."""
import importlib.util
import json
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_ROUND_DRIVER_DOC = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")
_WHICH_STOPS_MARKER = "**Which stops invoke it.**"
_WHICH_STOPS_END_MARKER = "**Terminal receipt preserved.**"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RD = _load("round_driver")
verification = _load("verification")
model_registry = _load("model_registry")

DIFF = ("diff --git a/f.py b/f.py\nindex 1..2 100644\n--- a/f.py\n+++ b/f.py\n"
        "@@ -1 +1,2 @@\n-old\n+new\n+more\n")


def _cfg(**over):
    base = {"leg": "code", "vendors": ["claude", "codex"], "diff": DIFF, "fixerVendor": "claude"}
    base.update(over)
    return base


def _session(tmp_path, name="s", **cfg_over):
    d = str(tmp_path / name)
    os.makedirs(d, exist_ok=True)
    out = RD.cmd_next(d, _cfg(**cfg_over))
    assert out["ok"], out
    return d


def _state(session_dir):
    ok, state = RD.load_state(session_dir)
    assert ok, state
    return state


def _finding(fid="v0", **over):
    base = {"file": "f.py", "line": 1, "title": "issue", "severity": "Important", "id": fid}
    base.update(over)
    return base


def _nonpanel_cell_proof(vendors):
    """The seat-map keys proving each vendor's dispatched non-panel cells (`verifier`, `reviewer-deep`)
    live: the non-panel selector seats a non-claude reviewer only on proven cells."""
    cells = []
    for role in ("verifier", "reviewer-deep"):
        for vendor in vendors:
            cell = model_registry.matrix_config(role, vendor)
            if cell is not None:
                cells.append([vendor, cell[0], cell[1]])
    return {"nonPanelLiveCells": cells, "nonPanelLiveCellsSource": "synthesized"}


def _fold_verifiers(state, findings, verdicts):
    staged = verification.stage_ids(findings)
    state["_toVerify"] = staged
    # the verifier seat is a non-claude vendor, seated only on a cell the seat map proves live
    if not state["config"].get("seatMap"):
        state["config"]["seatMap"] = _nonpanel_cell_proof(state["config"].get("vendors") or [])
    RD._fold_verifiers(state, state["config"], {"verdicts": verdicts,
                                                "verifierVendor": RD._nonpanel_selection(state, None, RD.P_VERIFIERS)[0]})


# --- per-pass append --------------------------------------------------------------------------

def test_verify_passes_records_two_waves_without_overwrite():
    # axis: each verifier fold appends one verifyPasses entry; a second wave must not overwrite.
    state = RD.new_state(_cfg())
    f0, f1 = _finding("v0"), _finding("v1", line=2)
    _fold_verifiers(state, [f0], [{"id": "v0", "verdict": "CONFIRMED", "reason": "ran", "evidence": "ran"}])
    _fold_verifiers(state, [f1], [{"id": "v0", "verdict": "REFUTED", "reason": "not real"}])
    passes = state["rounds"]["1"]["verifyPasses"]
    assert len(passes) == 2
    assert passes[0]["CONFIRMED"] == 1 and passes[0]["REFUTED"] == 0
    assert passes[1]["CONFIRMED"] == 0 and passes[1]["REFUTED"] == 1


def test_build_receipt_projects_verify_passes(tmp_path):
    state = RD.new_state(_cfg())
    _fold_verifiers(state, [_finding()], [{"id": "v0", "verdict": "PLAUSIBLE", "reason": "x"}])
    receipt = RD.build_receipt(state, str(tmp_path))
    assert receipt["rounds"][0]["verifyPasses"][0]["PLAUSIBLE"] == 1


def test_verify_passes_absent_from_certified_v2_with_truthy_list(tmp_path):
    """v2 certified receipts omit verifyPasses even when the round recorded a non-empty list."""
    state = RD.new_state(_cfg())
    state["schemaVersion"] = 2
    _fold_verifiers(state, [_finding()], [{"id": "v0", "verdict": "CONFIRMED", "reason": "ran", "evidence": "ran"}])
    assert state["rounds"]["1"]["verifyPasses"]
    receipt = RD.build_receipt(state, str(tmp_path))
    assert "verifyPasses" not in receipt["rounds"][0]
    interim = RD.build_interim_receipt(state, str(tmp_path), "park")
    assert interim["rounds"][0]["verifyPasses"][0]["CONFIRMED"] == 1


def test_verify_passes_second_wave_appends(tmp_path):
    """A round that already holds a verifyPasses wave plus a new verifier fold must append, not replace."""
    wave0 = [{"CONFIRMED": 1, "PLAUSIBLE": 0, "REFUTED": 0, "drops": 0,
              "downgrades": 0, "unverified": 0, "ambiguous": 0}]
    state = RD.new_state(_cfg())
    state["round"] = 1
    state["rounds"]["1"] = {"verifyPasses": wave0}
    _fold_verifiers(state, [_finding("v1", line=2)],
                    [{"id": "v0", "verdict": "REFUTED", "reason": "no"}])
    passes = state["rounds"]["1"]["verifyPasses"]
    assert len(passes) == 2
    assert passes[0]["CONFIRMED"] == 1 and passes[1]["REFUTED"] == 1


def test_interim_receipt_validates_with_empty_verify_passes(tmp_path):
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is True
    with open(os.path.join(d, RD.RECEIPT_INTERIM_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok is True, reason
    round_entry = receipt["rounds"][0] if receipt["rounds"] else {}
    assert "verifyPasses" in round_entry
    assert round_entry["verifyPasses"] == []


# --- interim schema / receipt_kind ------------------------------------------------------------

def test_receipt_kind_recognizes_interim_before_certified():
    # axis: interim schema must classify as receipt-interim/1, not receipt-certified/*.
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "park")
    assert RD.receipt_kind(interim) == RD.RECEIPT_INTERIM_SCHEMA
    assert RD.receipt_kind(interim) != RD.RECEIPT_CERTIFIED_SCHEMA % 3


def test_validate_interim_rejects_certification_keys():
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "park")
    interim["certification"] = {"shape": "smuggled"}
    ok, reason = RD.validate_receipt(interim)
    assert ok is False
    assert "certification" in reason


# --- terminal gate ---------------------------------------------------------------------------

def test_verify_terminal_receipt_rejects_interim_on_disk(tmp_path):
    # axis: _verify_terminal_receipt must fault on a legacy interim at the terminal path.
    d = _session(tmp_path)
    interim = RD.build_interim_receipt(_state(d), d, "tripwire")
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        json.dump(interim, fh)
    fault = RD._verify_terminal_receipt(d)
    assert fault is not None
    assert "interim" in fault


def test_terminal_receipt_written_over_interim(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "park")["ok"] is True
    state = _state(d)
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "test halt"}
    RD.save_state(d, state)
    RD._journal_append(d, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1, "attempt": 0})
    fault = RD._terminal_receipt_gate(d, state)
    assert fault is None
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert RD.receipt_kind(on_disk) == RD.RECEIPT_CERTIFIED_SCHEMA % RD.STATE_SCHEMA_VERSION


# --- checkpoint command ----------------------------------------------------------------------

def test_checkpoint_refuses_session_already_terminal(tmp_path):
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "halted"
    RD.save_state(d, state)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is False and out["reason"] == "checkpoint-session-terminal"


def test_checkpoint_refuses_when_terminal_receipt_on_disk(tmp_path):
    # axis: checkpoint must refuse once a terminal receipt exists on disk.
    d = _session(tmp_path)
    state = _state(d)
    state["terminal"] = "halted"
    state["certification"] = {"shape": None, "reason": "halt"}
    RD._journal_append(d, {"cmd": "submit", "phase": RD.P_PANEL, "round": 1, "attempt": 0})
    RD._write_receipt(d, state)
    out = RD.cmd_checkpoint(d, "park")
    assert out["ok"] is False and out["reason"] == "checkpoint-terminal-receipt-exists"


def test_checkpoint_supersedes_prior_interim(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    out = RD.cmd_checkpoint(d, "park")
    assert out["ok"] is True and out["stop"]["reason"] == "park"
    with open(os.path.join(d, RD.RECEIPT_INTERIM_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["stop"]["reason"] == "park"


def test_checkpoint_refuses_unknown_stop_reason(tmp_path):
    # axis: unknown stop reasons must refuse with an enumerated token, never accept free text.
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "owner-bailout")
    assert out["ok"] is False and out["reason"] == "checkpoint-stop-reason-unknown"


def test_checkpoint_journals_event(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "park")["ok"] is True
    entries = list(RD.read_journal(d))
    assert any(e.get("cmd") == "checkpoint" and e.get("outcome") == "checkpointed"
               for e in entries)


def test_checkpoint_refuses_the_retired_held_stop_reason(tmp_path):
    # axis: held was the stall menu's hold; with the menu retired it is an unknown stop reason.
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "held")
    assert out["ok"] is False and out["reason"] == "checkpoint-stop-reason-unknown"
    assert not os.path.exists(os.path.join(d, RD.RECEIPT_INTERIM_FILE))


def _checkpoint_which_stops_paragraph():
    """Slice round-driver.md's **Which stops invoke it.** paragraph only."""
    with open(_ROUND_DRIVER_DOC, encoding="utf-8") as fh:
        text = fh.read()
    start = text.find(_WHICH_STOPS_MARKER)
    assert start != -1, (
        "round-driver.md missing checkpoint stop-reason paragraph anchor %r"
        % _WHICH_STOPS_MARKER)
    rest = text[start + len(_WHICH_STOPS_MARKER):]
    end = rest.find("\n\n" + _WHICH_STOPS_END_MARKER)
    assert end != -1, (
        "round-driver.md missing end anchor %r after %r"
        % (_WHICH_STOPS_END_MARKER, _WHICH_STOPS_MARKER))
    return rest[:end]


def _checkpoint_stop_reasons_from_doc():
    """Bold stop-reason tokens in the enumeration clause — not incidental ``held`` elsewhere."""
    paragraph = _checkpoint_which_stops_paragraph()
    enum_end = paragraph.find("Once the hold fold")
    assert enum_end != -1, (
        "round-driver.md %r paragraph missing enumeration boundary %r"
        % (_WHICH_STOPS_MARKER, "Once the hold fold"))
    enumeration = paragraph[:enum_end]
    documented = frozenset(re.findall(r"\*\*([a-z][a-z0-9-]*)\*\*", enumeration))
    assert documented, (
        "round-driver.md %r paragraph has no bold stop-reason tokens in its enumeration"
        % _WHICH_STOPS_MARKER)
    return documented


def test_checkpoint_stop_reasons_census_matches_which_stops_invoke_paragraph():
    # axis: CHECKPOINT_STOP_REASONS ↔ round-driver.md "Which stops invoke it" (both directions).
    coded = frozenset(RD.CHECKPOINT_STOP_REASONS)
    documented = _checkpoint_stop_reasons_from_doc()
    only_code = coded - documented
    only_docs = documented - coded
    assert not only_code, (
        "CHECKPOINT_STOP_REASONS member(s) missing from round-driver.md %r paragraph: %s"
        % (_WHICH_STOPS_MARKER, sorted(only_code)))
    assert not only_docs, (
        "round-driver.md %r paragraph names stop reason(s) not in CHECKPOINT_STOP_REASONS: %s"
        % (_WHICH_STOPS_MARKER, sorted(only_docs)))


def test_interim_checkpoint_not_at_terminal_path(tmp_path):
    # axis: interim checkpoint receipt must not occupy the terminal receipt path.
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "park")["ok"] is True
    assert not os.path.exists(os.path.join(d, RD.RECEIPT_FILE))
    assert os.path.exists(os.path.join(d, RD.RECEIPT_INTERIM_FILE))


def test_legacy_interim_at_terminal_path_classified_as_interim(tmp_path):
    # axis: legacy interim at round-receipt.json is interim, not terminal.
    d = _session(tmp_path)
    interim = RD.build_interim_receipt(_state(d), d, "tripwire")
    with open(os.path.join(d, RD.RECEIPT_FILE), "w", encoding="utf-8") as fh:
        json.dump(interim, fh)
    assert RD._on_disk_receipt_class(d) == "interim"
    assert RD._terminal_receipt_on_disk(d) is False


def test_checkpoint_oserror_surfaces_as_refusal(tmp_path, monkeypatch):
    d = _session(tmp_path)

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(RD.round_commit, "begin", boom)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is False and out["reason"] == "interim-receipt-unwritable"


# --- cmd_attest re-key -----------------------------------------------------------------------

def test_attest_allowed_when_only_interim_on_disk(tmp_path, monkeypatch):
    # axis: attest must not refuse merely because the receipt path exists when the receipt is interim.
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    assert RD._terminal_receipt_on_disk(d) is False
    calls = []

    def track_resolve(_sd, ref):
        calls.append(ref)
        return None, "attest-failure-unknown"

    monkeypatch.setattr(RD, "_resolve_failure_ref", track_resolve)
    out = RD.cmd_attest(d, "1", "orphaned record; handing back uncertified")
    assert out["ok"] is False
    assert out["reason"] != "terminal-receipt-exists"
    assert out["reason"] != "terminal-receipt-unreadable"
    assert calls == ["1"]


def test_attest_refuses_unreadable_on_disk_receipt(tmp_path):
    # axis: unreadable on-disk receipt is never permission to overwrite
    d = _session(tmp_path)
    path = os.path.join(d, RD.RECEIPT_FILE)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("not-json{{")
    out = RD.cmd_attest(d, "1", "orphaned record; handing back uncertified")
    assert out["ok"] is False
    assert out["reason"] == "terminal-receipt-unreadable"


def test_checkpoint_calls_commit_recover_before_write(tmp_path, monkeypatch):
    # axis: checkpoint must replay a sealed-unapplied commit before opening its own
    d = _session(tmp_path)
    calls = []
    orig = RD._commit_recover_or_refuse

    def track(sd, cmd, **kw):
        calls.append(cmd)
        return orig(sd, cmd, **kw)

    monkeypatch.setattr(RD, "_commit_recover_or_refuse", track)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
    assert calls == ["checkpoint"]
