#!/usr/bin/env python3
"""#1720 — the new-model admission check survives the planted-bug control's removal."""
import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import conformance_probe  # noqa: E402

from test_model_registry import MR  # noqa: E402

_MODEL = "gpt-6-astra"
_ROLE = "reviewer-deep"


def _allowlist_models():
    return [model for model, _effort in MR.allowlist(_ROLE, "codex")]


def test_newly_registered_model_is_held_back_until_its_admission_mark_is_removed(monkeypatch):
    models = copy.deepcopy(MR._MODELS)
    row = dict(models["codex"][_MODEL])
    row["registration"] = "probe-pending"
    models["codex"][_MODEL] = row
    monkeypatch.setattr(MR, "_MODELS", models)

    assert _MODEL not in _allowlist_models()
    ok, reason = MR.codex_pin_verdict(_ROLE, _MODEL)
    assert ok is False
    assert reason.startswith("pin-probe-pending")

    del models["codex"][_MODEL]["registration"]

    assert _MODEL in _allowlist_models()
    ok, reason = MR.codex_pin_verdict(_ROLE, _MODEL)
    assert ok is True
    assert reason is None


def test_admission_check_keeps_its_own_planted_example():
    CP = conformance_probe
    assert CP.PLANT_FILE in CP.REGISTRATION_PROBE_DIFF
    text, err = CP._registration_probe_prompt()
    assert err is None
    assert CP.REGISTRATION_PROBE_DIFF in text

    hit = {"file": CP.PLANT_FILE, "line": CP.PLANT_LINES[0], "severity": CP.PLANT_SEVERITY,
           "title": "fails open"}
    matched, summary = CP._grade_registration_findings([hit])
    assert matched is True
    assert summary["line"] == CP.PLANT_LINES[0]

    past = dict(hit, line=CP.PLANT_LINES[-1] + 1)
    matched, summary = CP._grade_registration_findings([past])
    assert matched is False
    assert summary is None
