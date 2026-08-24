"""Interim receipt at non-terminal stops — per-pass verdict totals (#1107 WO-C)."""
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
HG = _load("handback_gate")
verification = _load("verification")

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


def _fold_verifiers(state, findings, verdicts):
    staged = verification.stage_ids(findings)
    state["_toVerify"] = staged
    RD._fold_verifiers(state, state["config"], {"verdicts": verdicts})


# --- per-pass append --------------------------------------------------------------------------

def test_verify_passes_records_two_waves_without_overwrite():
    # axis: each verifier fold appends one verifyPasses entry; a second wave must not overwrite.
    state = RD.new_state(_cfg())
    f0, f1 = _finding("v0"), _finding("v1", line=2)
    _fold_verifiers(state, [f0], [{"id": "v0", "verdict": "CONFIRMED", "evidence": "ran"}])
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


def test_interim_receipt_validates_with_empty_verify_passes(tmp_path):
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "tripwire")
    assert out["ok"] is True
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    ok, reason = RD.validate_receipt(receipt)
    assert ok is True, reason
    assert "verifyPasses" not in (receipt["rounds"][0] if receipt["rounds"] else {})


# --- interim schema / receipt_kind ------------------------------------------------------------

def test_receipt_kind_recognizes_interim_before_certified():
    # axis: interim schema must classify as receipt-interim/1, not receipt-certified/*.
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "park")
    assert RD.receipt_kind(interim) == RD.RECEIPT_INTERIM_SCHEMA
    assert RD.receipt_kind(interim) != RD.RECEIPT_CERTIFIED_SCHEMA % 3


def test_validate_interim_rejects_certification_keys():
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "held")
    interim["certification"] = {"shape": "smuggled"}
    ok, reason = RD.validate_receipt(interim)
    assert ok is False
    assert "certification" in reason


# --- terminal gate ---------------------------------------------------------------------------

def test_verify_terminal_receipt_rejects_interim_on_disk(tmp_path):
    # axis: _verify_terminal_receipt must fault on an interim receipt, not pass.
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "tripwire")["ok"] is True
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
    with open(os.path.join(d, RD.RECEIPT_FILE), encoding="utf-8") as fh:
        receipt = json.load(fh)
    assert receipt["stop"]["reason"] == "park"


def test_checkpoint_refuses_unknown_stop_reason(tmp_path):
    # axis: unknown stop reasons must refuse with an enumerated token, never accept free text.
    d = _session(tmp_path)
    out = RD.cmd_checkpoint(d, "owner-bailout")
    assert out["ok"] is False and out["reason"] == "checkpoint-stop-reason-unknown"


def test_checkpoint_journals_event(tmp_path):
    d = _session(tmp_path)
    assert RD.cmd_checkpoint(d, "held")["ok"] is True
    entries = list(RD.read_journal(d))
    assert any(e.get("cmd") == "checkpoint" and e.get("outcome") == "checkpointed"
               for e in entries)


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


# --- handback_gate ---------------------------------------------------------------------------

def test_handback_gate_rejects_interim_receipt():
    interim = RD.build_interim_receipt(RD.new_state(_cfg()), None, "tripwire")
    sidecar = {"verdict": "converged"}
    ok, why = HG._receipt_bindings_ok(sidecar, interim)
    assert ok is False
    assert why == "receipt-interim-not-handback-evidence"
