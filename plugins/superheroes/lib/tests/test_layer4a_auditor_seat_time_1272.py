#!/usr/bin/env python3
"""#1272 layer 4a WO-B — auditor seating: runner-channel only on the durable-record path."""
import importlib.util
import inspect
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import receipt_disclosures  # noqa: E402
import round_driver  # noqa: E402
import session_contract  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "test_round_driver_integration",
    os.path.join(_HERE, "test_round_driver_integration.py"))
_TDI = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_TDI)

_bootstrap = _TDI._bootstrap
_state = _TDI._state
_fake_git = _TDI._fake_git


def _journal_refused(session_dir, cmd, reason):
    return [
        e for e in round_driver.read_journal(session_dir)
        if e.get("cmd") == cmd and e.get("outcome") == "refused" and e.get("reason") == reason
    ]


def _claude_only_session(tmp_path):
    return _bootstrap(tmp_path, vendors=["claude"])


# T1 — unit tests on _auditor_vendor / independent_auditor (edges 1–3, 6–7)


def test_t1_edge1_runner_only_claude_codex_fixer_cursor():
    """Edge 1 — durable path picks codex, not claude, when fixer is cursor."""
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "cursor"}
    vendor, independence = round_driver._auditor_vendor(cfg, "cursor", runner_only=True)
    assert vendor == "codex"
    assert independence == "independent"
    auditor, _fam = receipt_disclosures.independent_auditor(cfg, "cursor", runner_only=True)
    assert auditor == "codex"
    vendor_hand, ind_hand = round_driver._auditor_vendor(cfg, "cursor", runner_only=False)
    assert vendor_hand == "claude"
    assert ind_hand == "independent"


def test_t1_edge2_codex_cursor_fixer_cursor_unchanged():
    """Edge 2 — codex/cursor pool with cursor fixer stays codex independent."""
    cfg = {"vendors": ["codex", "cursor"], "fixerVendor": "cursor"}
    assert round_driver._auditor_vendor(cfg, "cursor", runner_only=True) == ("codex", "independent")
    assert round_driver._auditor_vendor(cfg, "cursor", runner_only=False) == ("codex", "independent")


def test_t1_edge3_claude_codex_fixer_codex_runner_vs_hand():
    """Edge 3 — codex fixer: degraded codex on durable path, claude independent on hand path."""
    cfg = {"vendors": ["claude", "codex"], "fixerVendor": "codex"}
    assert round_driver._auditor_vendor(cfg, "codex", runner_only=True) == ("codex", "degraded")
    assert round_driver._auditor_vendor(cfg, "codex", runner_only=False) == ("claude", "independent")


def test_t1_edge6_unknown_fixer_runner_only_degraded_fallback():
    """Edge 6 — unknown fixer: first runner-channel vendor or unseatable."""
    cfg = {"vendors": ["claude", "codex"]}
    assert receipt_disclosures.independent_auditor(cfg, None) == (None, None)
    assert round_driver._auditor_vendor(cfg, None, runner_only=True) == ("codex", "degraded")
    assert round_driver._auditor_vendor(cfg, None, runner_only=False) == ("claude", "degraded")
    claude_only = {"vendors": ["claude"]}
    assert round_driver._auditor_vendor(claude_only, None, runner_only=True) == (None, "unseatable")


def test_t1_edge7_unknown_vendor_not_runner_channel():
    """Edge 7 — unknown vendor strings are never runner-channel auditors."""
    assert session_contract.runner_channel_vendor("unknown") is False
    assert session_contract.runner_channel_vendor("") is False
    cfg = {"vendors": ["claude", "unknown", "codex"], "fixerVendor": "cursor"}
    vendor, independence = round_driver._auditor_vendor(cfg, "cursor", runner_only=True)
    assert vendor == "codex"
    assert independence == "independent"


# T2 — edge 4 through real durable-path verbs


def test_t2_edge4_record_result_auditor_unseatable(tmp_path):
    session_dir, _gitdir, _head_path = _claude_only_session(tmp_path)
    out = round_driver.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is False
    assert out["reason"] == round_driver.AUDITOR_UNSEATABLE_CAUSE
    rows = _journal_refused(session_dir, "record-result", round_driver.AUDITOR_UNSEATABLE_CAUSE)
    assert len(rows) == 1


def test_t2_edge4_record_missing_auditor_unseatable(tmp_path):
    session_dir, _gitdir, _head_path = _claude_only_session(tmp_path)
    state = _state(session_dir)
    pend = state["pending"]
    out = round_driver.cmd_record_missing(
        session_dir, "code-reviewer", pend["attempt"], "no-artifact")
    assert out["ok"] is False
    assert out["reason"] == round_driver.AUDITOR_UNSEATABLE_CAUSE
    rows = _journal_refused(session_dir, "record-missing", round_driver.AUDITOR_UNSEATABLE_CAUSE)
    assert len(rows) == 1


def test_t2_edge4_advance_auditor_unseatable(tmp_path):
    session_dir, gitdir, _head_path = _claude_only_session(tmp_path)
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] == round_driver.AUDITOR_UNSEATABLE_CAUSE
    rows = _journal_refused(session_dir, "advance", round_driver.AUDITOR_UNSEATABLE_CAUSE)
    assert len(rows) == 1


# T3 — edge 5: hand path bypasses auditor-unseatable refusal


def test_t3_edge5_submit_used_no_auditor_unseatable_refusal(tmp_path):
    session_dir, gitdir, _head_path = _claude_only_session(tmp_path)
    state = _state(session_dir)
    state["_submitUsed"] = True
    round_driver.save_state(session_dir, state)
    out = round_driver.cmd_record_result(session_dir, sweep=True)
    assert out["ok"] is False
    assert out["reason"] != round_driver.AUDITOR_UNSEATABLE_CAUSE
    assert out["reason"] == "record-submit-interleaved"
    out = round_driver.cmd_advance(session_dir, git=_fake_git(gitdir))
    assert out["ok"] is False
    assert out["reason"] != round_driver.AUDITOR_UNSEATABLE_CAUSE
    assert out["reason"] == "advance-submit-interleaved"


# T4 — one-home census


def test_t4_one_home_runner_channel_vendor_census():
    src = inspect.getsource(round_driver._vendor_is_external_engine)
    assert "session_contract.runner_channel_vendor" in src
    lib_dir = _LIB
    defs = []
    for name in os.listdir(lib_dir):
        if not name.endswith(".py"):
            continue
        path = os.path.join(lib_dir, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if "def runner_channel_vendor" in text:
            defs.append(path)
    assert defs == [os.path.join(lib_dir, "session_contract.py")]
