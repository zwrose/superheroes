"""#1272 layer 3 WO-D — driver-rendered fixer orders name no graded result shape."""
import os
import shlex

import order_contract
import order_lint as OL
import round_driver as RD
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
        if f["token"] in (OL.TOKEN_RESULT_SHAPE_AMBIGUOUS, OL.TOKEN_RESULT_SHAPE_AUTHORED)
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
        "landing_path": os.path.join(_SESSION, "round-2", "landing", "dispatch-fixer",
                                     "fixer.a0.payload.json"),
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


def _fixer_placeholders():
    return {
        "FIX_BATCH_PATH": os.path.join(_SESSION, "round-2", "fix-batch.json"),
        "FIX_BATCH_SHA256": "0" * 64,
        "PROFILE_PATH": "(Project profile not resolved for this project)",
        "RUBRIC_PATH": _PLUGIN_RUBRIC,
        "CWD": _REPO,
        "REPO_ROOT": shlex.quote(_REPO),
        "VERIFY_BUDGET": (
            "Scoped verify budget for this batch — target files: auth.py. "
            "Run the tests that reference those files plus the project's static validators, "
            "at most once each. The project's full verify command is NOT yours to run inside this "
            "attempt — the orchestrator runs it once after the round's fixes land: pytest -q"
        ),
        "ROUND": "2",
        "GATE_GUIDANCE": "No owner-gate guidance is attached to this batch.",
    }


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
        "PR_CHECKOUT_PATH": "",
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


def test_l3_d1_host_fixer_order_names_required_payload_shape():
    # axis: host-seat dispatch-fixer carries the payload-contract block with required fixes
    text = _render(RP.P_FIXER, _fixer_placeholders())
    assert _PAYLOAD_HEADING in text
    assert "Required keys: fixes" in text
    assert OL._FIXER_LITERAL not in text


def test_l3_d1_engine_fixer_order_names_no_result_shape():
    # axis: engine dispatch-fixer carries no payload-contract heading or fixes literal
    ctx = _base_context(host_seat=False, placeholders=_fixer_placeholders())
    text, reason = RO.render_order(RP.P_FIXER, "seat", ctx)
    assert reason is None, reason
    assert _PAYLOAD_HEADING not in text
    assert OL._FIXER_LITERAL not in text
    assert "see Payload contract" not in text


def _fixer_step_5(text):
    start = text.index("4. Commit ALL changes")
    end = text.index("## Escalation", start)
    block = text[start:end]
    for line in block.splitlines():
        if line.startswith("5."):
            return line.strip()
    raise AssertionError("step 5 not found in fixer order")


def test_l3_d1_fixer_step_5_matches_rendered_payload_contract_block():
    # axis: step 5 is derived from host_seat — host cites Payload contract; engine cites runner appendix
    host_text = _render(RP.P_FIXER, _fixer_placeholders())
    host_step = _fixer_step_5(host_text)
    assert "Payload contract section below" in host_step
    assert "not asked to emit" not in host_step
    assert _PAYLOAD_HEADING in host_text
    assert "Required keys: fixes" in host_text

    engine_ctx = _base_context(host_seat=False, placeholders=_fixer_placeholders())
    engine_text, reason = RO.render_order(RP.P_FIXER, "seat", engine_ctx)
    assert reason is None, reason
    engine_step = _fixer_step_5(engine_text)
    assert "runner appends at dispatch" in engine_step
    assert "not asked to emit" in engine_step
    assert _PAYLOAD_HEADING not in engine_text


def test_l3_d1_control_other_phase_payload_contract_unchanged():
    # axis: non-fixer phases still render the payload-contract block byte-for-byte in structure
    panel_text = _render(RP.P_PANEL, _panel_placeholders())
    assert _PAYLOAD_HEADING in panel_text
    assert "Required keys:" in panel_text
    fixer_text = _render(RP.P_FIXER, _fixer_placeholders())
    assert _PAYLOAD_HEADING in fixer_text


def test_l3_d2_production_emission_refuses_the_old_order_text(tmp_path):
    # axis: production path lint (no expect_items) refuses authored result shape
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    old_shape = (
        "# Fix\n\n"
        + _PAYLOAD_HEADING + "\n\n"
        "Required keys: fixes\n"
    )
    r = OL.check_text(old_shape, repo, kind="fixer")
    assert r["ok"] is False
    assert OL.TOKEN_RESULT_SHAPE_AUTHORED in _tokens(r)


def test_l3_d2_edge1_implementer_kind_skips_authored_arm(tmp_path):
    # axis: implementer orders may declare deliverables — authored arm never fires
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    text = (
        "# WO\n\nBudget: at most 1 command.\n\n"
        + _PAYLOAD_HEADING + "\n\n"
        + OL._FIXER_LITERAL + "\n"
    )
    r = OL.check_text(text, repo, kind="implementer")
    assert OL.TOKEN_RESULT_SHAPE_AUTHORED not in _tokens(r)


def test_l3_d2_edge2_fixer_without_result_shape_passes(tmp_path):
    # axis: fixer order with no result-shape text is clean at production emission
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    r = OL.check_text("# Fix\n\nRun scoped verify.\n", repo, kind="fixer")
    assert r["ok"] is True
    assert _shape_tokens(r) == []


def test_l3_d2_edge3_quoted_data_elision_preserves_lint_skip(tmp_path):
    # axis: result-shape prose inside quoted-data blocks stays elided at production emission
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    trigger = OL._FIXER_LITERAL + ' via marker channel parser with "resultKind".'
    order_text = "You are the fixer.\n\n## Ratified residuals\n\n" + trigger + "\n"
    lint_text = RD._order_lint_text(order_text, {"ratified_residuals": trigger})
    assert trigger not in lint_text
    assert RD.QUOTED_DATA_LINT_ELISION in lint_text
    r = OL.check_text(lint_text, repo, kind="fixer")
    assert r["ok"] is True
    assert _shape_tokens(r) == []


def test_l3_d2_edge4_expect_items_still_fires_ambiguous_arm(tmp_path):
    # axis: non-empty expect_items keeps the existing ambiguous arm unchanged
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    text = "# Fix\n\nReturn " + OL._FIXER_LITERAL + " on stdout.\n"
    r = OL.check_text(text, repo, expect_items=("lib/new.py",), kind="fixer")
    assert _shape_tokens(r) == [OL.TOKEN_RESULT_SHAPE_AMBIGUOUS]
    assert OL.TOKEN_RESULT_SHAPE_AUTHORED not in _tokens(r)


def test_l3_d2_edge5_non_string_text_unchanged():
    # axis: check_text's not-text guard is unchanged
    r = OL.check_text(None, _REPO, kind="fixer")
    assert r["ok"] is False
    assert _tokens(r) == [OL.TOKEN_UNREADABLE]


def test_l3_shape_arm_census_fixer_without_expect_items(tmp_path):
    # axis: exactly one shape arm fires on fixer orders at production emission
    repo = str(tmp_path)
    os.makedirs(repo, exist_ok=True)
    for text in (
        "# Fix\n\n" + _PAYLOAD_HEADING + "\n",
        "# Fix\n\nEmit " + OL._FIXER_LITERAL + ".\n",
    ):
        r = OL.check_text(text, repo, kind="fixer")
        assert len(_shape_tokens(r)) == 1
        assert _shape_tokens(r) == [OL.TOKEN_RESULT_SHAPE_AUTHORED]
