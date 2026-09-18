"""Retirement pin for fixer file-scope guard removal (#1299).

Bites on: code surfaces this order owns — the escalation module must not expose the
guard machinery, and the rendered dispatch-fixer order must not cite the wrapper or
guard step — plus prose surfaces: retired vocabulary absent and the owner-authority-gate
family rule re-homed in review-discipline.md.
"""
import os

import escalation as ESC
import round_orders as RO
import round_phases as RP

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_SESSION = "/tmp/superheroes-session-1299-pin"
_REPO = "/home/user/proj"
_PLUGIN_RUBRIC = os.path.join(_PLUGIN_ROOT, "rubric", "review-base.md")
_REVIEW_DISCIPLINE = os.path.join(_PLUGIN_ROOT, "rubric", "review-discipline.md")
_AUTO_FIX_LOOP = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_escalation_module_has_no_file_scope_guard():
    assert not hasattr(ESC, "SAFETY_MACHINERY")
    assert not hasattr(ESC, "is_safety_machinery")


def test_dispatch_fixer_order_has_no_guard_instruction():
    ctx = {
        "session_dir": _SESSION,
        "round": 2,
        "attempt": 0,
        "diff_path": os.path.join(_SESSION, "round-2", "diff.txt"),
        "rubric_path": _PLUGIN_RUBRIC,
        "core_path": "",
        "layer_path": "",
        "repo_root": _REPO,
        "landing_path": os.path.join(_SESSION, "round-2", "landing", "dispatch-fixer",
                                    "fixer.a0.payload.json"),
        "envelope_stub_path": os.path.join(_SESSION, "round-2", "stubs", "seat.json"),
        "ratified_residuals": "- Flaky integration test in CI lane B is accepted",
        "residuals_provenance": "Residuals below are read from the review base commit (base-pinned).",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": True,
        "placeholders": {
            "FIX_BATCH_PATH": os.path.join(_SESSION, "round-2", "fix-batch.json"),
            "PROFILE_PATH": "(Project profile not resolved for this project)",
            "RUBRIC_PATH": _PLUGIN_RUBRIC,
            "CWD": _REPO,
            "REPO_ROOT": _REPO,
            "VERIFY_COMMAND": "npm test",
            "ROUND": "2",
            "GATE_GUIDANCE": "No owner-gate guidance is attached to this batch.",
        },
    }
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None
    assert "ESCALATION_WRAPPER_PATH" not in text
    assert "Escalation guard" not in text
    assert "file-scope guard" not in text


def test_review_discipline_retired_guard_vocabulary_absent():
    text = _read(_REVIEW_DISCIPLINE)
    assert "### The safety-machinery route" not in text
    assert "safety machinery" not in text


def test_auto_fix_loop_retired_guard_vocabulary_absent():
    text = _read(_AUTO_FIX_LOOP)
    assert "safety machinery" not in text
    assert "file-scope guard" not in text


def test_review_discipline_owner_authority_gate_family_survives():
    text = _read(_REVIEW_DISCIPLINE)
    assert "### The owner-authority-gate family — the owner's word, per change" in text
    assert "owner's word first, per change" in text
