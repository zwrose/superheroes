"""#1272 layer 3 WO-D — driver-rendered orders and the order lint's result-shape arm."""
import os

import order_contract
import order_lint as OL
import round_orders as RO
import round_phases as RP

_TESTS = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(_TESTS))
_REPO = "/home/user/proj"
_SESSION = "/tmp/superheroes-session-wo4-golden"
_PLUGIN_RUBRIC = os.path.join(_PLUGIN_ROOT, "rubric", "review-base.md")
_PAYLOAD_HEADING = order_contract.PAYLOAD_CONTRACT_HEADING


def _tokens(result):
    return [f["token"] for f in result.get("findings") or []]


def _shape_tokens(result):
    return [
        f["token"] for f in result.get("findings") or []
        if f["token"] == OL.TOKEN_RESULT_SHAPE_AMBIGUOUS
    ]


def _base_context(**over):
    ctx = {
        "session_dir": _SESSION,
        "round": 2,
        "attempt": 0,
        "diff_path": os.path.join(_SESSION, "round-2", "diff.txt"),
        "rubric_path": _PLUGIN_RUBRIC,
        "core_path": "",
        "layer_path": "",
        "repo_root": _REPO,
        "landing_path": os.path.join(_SESSION, "round-2", "landing", "seat.a0.payload.json"),
        "envelope_stub_path": os.path.join(_SESSION, "round-2", "stubs", "seat.json"),
        "ratified_residuals": "- Flaky integration test in CI lane B is accepted",
        "residuals_provenance": "Residuals below are read from the review base commit (base-pinned).",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": True,
        "placeholders": {},
    }
    ctx.update(over)
    return ctx


def _panel_placeholders():
    return {
        "MODE": "branch",
        "MODE_EVIDENCE": "Review session mode branch (from session metadata).",
        "REPO": "acme/widget",
        "TARGET": "feature/wo4",
        "DIFF_PATH": os.path.join(_SESSION, "round-2", "diff.txt"),
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CORE_PATH": "(Core calibration not resolved for this project)",
        "LAYER_PATH": "(Review-crew layer calibration not resolved for this project)",
        "CLAUDE_MD_PATH": "/home/user/proj/CLAUDE.md",
        "PRIOR_COMMENTS_PATH": os.path.join(_SESSION, "prior-comments.json"),
        "FOCUS_NOTES": "touch auth paths carefully",
        "DIMENSION": "Code",
        "CHANNEL": "file",
        "FINDINGS_OUTPUT_PATH": os.path.join(_SESSION, "round-2", "findings-code.json"),
    }


def _render(phase, placeholders):
    ctx = _base_context(
        landing_path=os.path.join(_SESSION, "round-2", "landing", phase, "seat.a0.payload.json"),
        placeholders=placeholders,
    )
    text, reason = RO.render_order(phase, "seat", ctx)
    assert reason is None, reason
    return text


def test_l3_d1_control_other_phase_payload_contract_unchanged():
    # axis: the panel phase still renders the payload-contract block byte-for-byte in structure
    panel_text = _render(RP.P_PANEL, _panel_placeholders())
    assert _PAYLOAD_HEADING in panel_text
    assert "Required keys:" in panel_text


def test_l3_d2_edge4_expect_items_still_fires_ambiguous_arm(tmp_path):
    # axis: non-empty expect_items keeps the existing ambiguous arm unchanged
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    text = "# Fix\n\nReturn " + OL._FIXES_LITERAL + " on stdout.\n"
    r = OL.check_text(text, repo, expect_items=("lib/new.py",), kind="implementer")
    assert _shape_tokens(r) == [OL.TOKEN_RESULT_SHAPE_AMBIGUOUS]


def test_l3_d2_edge5_non_string_text_unchanged():
    # axis: check_text's not-text guard is unchanged
    r = OL.check_text(None, _REPO, kind="implementer")
    assert r["ok"] is False
    assert _tokens(r) == [OL.TOKEN_UNREADABLE]
