"""Order-input contract guards (#1107 WO-A): guidance key sync, head-diff materialization,
readable-input registry census."""
import json
import os

import pytest

import round_orders as RO
import round_phases as RP
import round_records as RR

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_LIB = os.path.normpath(os.path.join(_HERE, ".."))

import round_driver as RD  # noqa: E402

_GUIDANCE_COPY_SURFACES = [
    "rubric/orders/dispatch-fixer.md",
    "lib/tests/fixtures/orders/golden/dispatch-fixer.txt",
    "skills/review-code/reference/auto-fix-loop.md",
]

_TRADEOFF = {"title": "widen the API", "severity": "Important",
             "file": "f.py", "line": 1, "tradeoff": True}
_TRADEOFF_ID = "f.py::widen the api@L1"


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _cfg(tmp_path):
    return {"repoRoot": str(tmp_path), "verifyCommand": "none"}


def _judgment_state():
    state = RD.new_state(_cfg(os.path.join("/tmp", "judgment-probe")))
    RD._route_judgment_blockers(state, [dict(_TRADEOFF)])
    return state


def _minimal_paths(session_dir):
    return {
        "storage_key": "probe.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }


def _template_placeholders(phase):
    path = RO.order_template_path(phase)
    with open(path, encoding="utf-8") as fh:
        return set(RO._PLACEHOLDER_RE.findall(fh.read()))


def _order_placeholder_keys(phase, session_dir, state, payload, seat_key):
    paths = _minimal_paths(session_dir)
    return set(
        RD._order_placeholders(
            phase, seat_key, 0, state, state.get("config") or {},
            payload, session_dir, 2, paths, RD.CHANNEL_FILE,
        ).keys()
    )


def _placeholder_partition():
    return (
        RD.ORDER_READABLE_FILE_INPUTS
        | RD.ORDER_SHIPPED_RESOURCE_INPUTS
        | RD.ORDER_OUTPUT_PLACEHOLDERS
        | RD.ORDER_DERIVED_PLACEHOLDERS
        | RO._AUX_PLACEHOLDER_INPUTS
    )


# --- guidance key drift pin (bite axis: constant ↔ copy surfaces) -------------------------


@pytest.mark.parametrize("rel", _GUIDANCE_COPY_SURFACES, ids=_GUIDANCE_COPY_SURFACES)
def test_fix_batch_guidance_key_present_on_copy_surface(rel):
    # axis: FIX_BATCH_GUIDANCE_KEY literal appears on every enumerated copy surface
    literal = RD.FIX_BATCH_GUIDANCE_KEY
    text = _read(rel)
    assert literal in text, (
        "expected %r on copy surface %s — rename must update all copies" % (literal, rel)
    )


@pytest.mark.parametrize("rel", _GUIDANCE_COPY_SURFACES, ids=_GUIDANCE_COPY_SURFACES)
def test_gate_guidance_heading_present_on_copy_surface(rel):
    # axis: Owner-gate guidance section heading pinned on every copy surface
    heading = "## Owner-gate guidance"
    text = _read(rel)
    assert heading in text, (
        "expected %r on copy surface %s — GATE_GUIDANCE block drift" % (heading, rel)
    )


# --- guidance emission (bite axis: fold writes FIX_BATCH_GUIDANCE_KEY) ---------------------


def test_fold_judgment_writes_user_guidance_key():
    # axis: fix-with-guidance folds owner text under FIX_BATCH_GUIDANCE_KEY
    state = _judgment_state()
    RD._fold_judgment(state, state["config"], {"dispositions": [
        {"id": _TRADEOFF_ID, "disposition": "fix-with-guidance",
         "guidance": "keep it backward compatible"}]})
    batch = state["_fixBatch"][0]
    assert batch[RD.FIX_BATCH_GUIDANCE_KEY] == "keep it backward compatible"
    assert "guidance" not in batch


# --- gate guidance block (WO #1221) ------------------------------------------------------


def test_gate_guidance_block_non_list_yields_no_guidance_form():
    # edge 1: non-list input → no-guidance form, never crash or empty string
    assert RD._gate_guidance_block(None) == RD._GATE_GUIDANCE_NO_GUIDANCE
    assert RD._gate_guidance_block("not-a-list") == RD._GATE_GUIDANCE_NO_GUIDANCE


def test_gate_guidance_block_empty_or_non_dict_rows_yields_no_guidance_form():
    # edge 1: empty list or non-dict rows → no-guidance form
    assert RD._gate_guidance_block([]) == RD._GATE_GUIDANCE_NO_GUIDANCE
    assert RD._gate_guidance_block([None, "x"]) == RD._GATE_GUIDANCE_NO_GUIDANCE


def test_gate_guidance_block_skips_non_guided_rows():
    # edge 2: absent/None/non-string/whitespace userGuidance is not guided
    rows = [
        {"title": "a", "file": "f.py", "line": 1},
        {"title": "b", "file": "f.py", "line": 2, RD.FIX_BATCH_GUIDANCE_KEY: None},
        {"title": "c", "file": "f.py", "line": 3, RD.FIX_BATCH_GUIDANCE_KEY: 1},
        {"title": "d", "file": "f.py", "line": 4, RD.FIX_BATCH_GUIDANCE_KEY: "   "},
    ]
    assert RD._gate_guidance_block(rows) == RD._GATE_GUIDANCE_NO_GUIDANCE


def _minimal_render_ctx(session_dir, repo_root, ph, paths):
    return {
        "session_dir": session_dir,
        "round": 2,
        "attempt": 0,
        "diff_path": os.path.join(session_dir, "round-2", "diff.txt"),
        "rubric_path": RD._shipped_rubric_path(),
        "core_path": "",
        "layer_path": "",
        "repo_root": repo_root,
        "landing_path": paths["landing_path"],
        "envelope_stub_path": paths["envelope_stub_path"],
        "ratified_residuals": "",
        "residuals_provenance": "",
        "residuals_read_failure": None,
        "payload": {},
        "host_seat": True,
        "placeholders": ph,
    }


def test_gate_guidance_block_renders_guided_row_verbatim():
    rows = [{"title": "widen the API", "file": "f.py", "line": 1,
             RD.FIX_BATCH_GUIDANCE_KEY: "keep backward compatible",
             RD.FIX_BATCH_GUIDANCE_ID_KEY: "f.py::widen the api@L1"}]
    block = RD._gate_guidance_block(rows)
    assert "f.py::widen the api@L1" in block
    assert "widen the API" in block
    assert "> keep backward compatible" in block
    assert "BEGIN owner-gate guidance" in block
    assert "END owner-gate guidance" in block


def test_gate_guidance_block_missing_stamped_id_uses_no_finding_id_label():
    # E1: guided row with no stamped id → "(no finding id)" label; row still appears
    rows = [{"title": "widen the API", "file": "f.py", "line": 1,
             RD.FIX_BATCH_GUIDANCE_KEY: "keep backward compatible"}]
    block = RD._gate_guidance_block(rows)
    assert "### (no finding id) — widen the API" in block
    assert "> keep backward compatible" in block


def test_gate_guidance_block_non_string_stamped_id_uses_no_finding_id_label():
    # E2: non-string stamped id → same as E1
    rows = [{"title": "widen the API", "file": "f.py", "line": 1,
             RD.FIX_BATCH_GUIDANCE_KEY: "keep backward compatible",
             RD.FIX_BATCH_GUIDANCE_ID_KEY: 1}]
    block = RD._gate_guidance_block(rows)
    assert "### (no finding id) — widen the API" in block
    assert "> keep backward compatible" in block


def test_gate_guidance_round_placeholder_neutralized_in_rendered_order(tmp_path):
    # edge 3: {{ROUND}} in guidance must not substitute into the order
    import round_orders as RO
    session_dir = str(tmp_path / "gate-round")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "leak", "file": "a.py", "line": 3,
                       RD.FIX_BATCH_GUIDANCE_KEY: "use round {{ROUND}} here"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "{ {ROUND}}" in ph["GATE_GUIDANCE"]
    assert "{{ROUND}}" not in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "use round { {ROUND}} here" in text
    assert "use round 2 here" not in text


def test_gate_guidance_unknown_placeholder_does_not_wedge_render(tmp_path):
    # edge 4: unknown {{FOO}} in guidance must not trip unknown-placeholder-remaining
    import round_orders as RO
    session_dir = str(tmp_path / "gate-unknown")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "x", "file": "b.py", "line": 1,
                       RD.FIX_BATCH_GUIDANCE_KEY: "see {{UNKNOWN_THING}}"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "{ {UNKNOWN_THING}}" in text


def test_gate_guidance_triple_brace_round_placeholder_neutralized_in_rendered_order(tmp_path):
    """E1: odd brace run {{{ROUND}}} must not leave live {{ROUND}} or substitute the round."""
    import round_orders as RO
    session_dir = str(tmp_path / "gate-triple")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "leak", "file": "a.py", "line": 3,
                       RD.FIX_BATCH_GUIDANCE_KEY: "use {{{ROUND}} exactly"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "{{ROUND}}" not in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "{{ROUND}}" not in text
    assert "use round 2" not in text


def test_gate_guidance_long_odd_brace_run_neutralized_in_rendered_order(tmp_path):
    """E2: long odd brace run must render without surviving {{ or wedging render."""
    import round_orders as RO
    session_dir = str(tmp_path / "gate-odd")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "x", "file": "b.py", "line": 1,
                       RD.FIX_BATCH_GUIDANCE_KEY: "{{{{{FOO}}"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "{{" not in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "{{" not in text


def test_gate_guidance_title_placeholder_neutralized_in_rendered_order(tmp_path):
    """E3: {{UNKNOWN_THING}} in the finding title must not wedge render_order."""
    import round_orders as RO
    session_dir = str(tmp_path / "gate-title")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "review {{UNKNOWN_THING}} handling", "file": "b.py", "line": 1,
                       RD.FIX_BATCH_GUIDANCE_KEY: "ship narrow",
                       RD.FIX_BATCH_GUIDANCE_ID_KEY: "b.py::review@L1"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "review { {UNKNOWN_THING}} handling" in ph["GATE_GUIDANCE"]
    assert "{{UNKNOWN_THING}}" not in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "review { {UNKNOWN_THING}} handling" in text


def test_gate_guidance_stamped_id_placeholder_neutralized_in_rendered_order(tmp_path):
    """E4: {{ROUND}} in the stamped finding id must not wedge render_order."""
    import round_orders as RO
    session_dir = str(tmp_path / "gate-id")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "leak", "file": "a.py", "line": 3,
                       RD.FIX_BATCH_GUIDANCE_KEY: "keep narrow",
                       RD.FIX_BATCH_GUIDANCE_ID_KEY: "a.py::{{ROUND}}@L3"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "a.py::{{ROUND}}@L3" not in ph["GATE_GUIDANCE"]
    assert "a.py::{ {ROUND}}@L3" in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "a.py::{ {ROUND}}@L3" in text


def test_gate_guidance_all_fields_placeholder_neutralized_in_rendered_order(tmp_path):
    """E5: placeholder syntax in id, title, and guidance together still renders."""
    import round_orders as RO
    session_dir = str(tmp_path / "gate-all")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "review {{FOO}}", "file": "a.py", "line": 1,
                       RD.FIX_BATCH_GUIDANCE_KEY: "use {{{ROUND}}}",
                       RD.FIX_BATCH_GUIDANCE_ID_KEY: "a.py::{{BAR}}@L1"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "{{" not in ph["GATE_GUIDANCE"]
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    assert "{{" not in text


def test_gate_guidance_markdown_in_guidance_stays_inside_delimiters(tmp_path):
    # edge 5: fenced block, heading, backticks stay inside delimiters
    import round_orders as RO
    guidance = "# heading\n```py\nx = 1\n```\nuse `foo`"
    session_dir = str(tmp_path / "gate-md")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "fmt", "file": "c.py", "line": 2,
                       RD.FIX_BATCH_GUIDANCE_KEY: guidance}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    ctx = _minimal_render_ctx(session_dir, str(tmp_path), ph, paths)
    text, reason = RO.render_order(RP.P_FIXER, "fixer", ctx)
    assert reason is None, reason
    begin = text.index("BEGIN owner-gate guidance")
    end = text.index("END owner-gate guidance")
    section = text[begin:end]
    assert "# heading" in section
    assert "```py" in section
    assert "`foo`" in section


def test_gate_guidance_per_row_cap_renders_full_at_boundary():
    """E7: guidance at the 2000-byte row cap renders in full; one byte over withholds exactly one."""
    row = {"title": "big", "file": "d.py", "line": 1, RD.FIX_BATCH_GUIDANCE_KEY: "x"}
    at_cap = dict(row, **{RD.FIX_BATCH_GUIDANCE_KEY: "x" * 2000})
    block_full = RD._gate_guidance_block([at_cap])
    assert "bytes withheld" not in block_full
    assert "> %s" % ("x" * 2000) in block_full
    over_cap = dict(row, **{RD.FIX_BATCH_GUIDANCE_KEY: "x" * 2001})
    block_over = RD._gate_guidance_block([over_cap])
    assert "(1 bytes withheld" in block_over


def test_gate_guidance_aggregate_cap_admits_and_omits_at_boundary():
    """E8: the 8000-byte aggregate cap renders fitting rows in full and names the rest."""
    guidance = "y" * 500
    rows = [{"title": "row-%02d" % i, "file": "e%d.py" % i, "line": i + 1,
             RD.FIX_BATCH_GUIDANCE_KEY: guidance} for i in range(20)]
    block = RD._gate_guidance_block(rows)
    assert "not rendered in full" in block
    rendered = [r for r in rows if "### (no finding id) — %s" % r["title"] in block]
    omitted = [r for r in rows if r not in rendered]
    assert rendered, "expected at least one row under the 8000-byte aggregate cap"
    assert omitted, "expected at least one row omitted by the 8000-byte aggregate cap"
    assert len(rendered) + len(omitted) == len(rows)
    assert "%d guided finding(s) not rendered in full" % len(omitted) in block
    for row in rendered:
        assert "> %s" % guidance in block
    for row in omitted:
        assert row["title"] not in block


def test_fixer_order_placeholders_include_guided_gate_block(tmp_path):
    # G1 axis: P_FIXER wiring emits guided guidance from state batch
    session_dir = str(tmp_path / "guided-batch")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "widen the API", "file": "f.py", "line": 1,
                       RD.FIX_BATCH_GUIDANCE_KEY: "ship narrow API"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert "ship narrow API" in ph["GATE_GUIDANCE"]
    assert ph["GATE_GUIDANCE"] != RD._GATE_GUIDANCE_NO_GUIDANCE


def test_mechanical_batch_emits_no_guidance_form(tmp_path):
    # edge 11: mechanical batch → no-guidance form without gate-ran claims
    session_dir = str(tmp_path / "mech-batch")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path), "verifyCommand": "none"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "_fixBatch": [{"title": "unchecked index", "file": "f.py", "line": 2,
                       "severity": "Important"}],
    }
    paths = _minimal_paths(session_dir)
    ph = RD._order_placeholders(
        RP.P_FIXER, "fixer", 0, state, state["config"], {},
        session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert ph["GATE_GUIDANCE"] == RD._GATE_GUIDANCE_NO_GUIDANCE
    lowered = ph["GATE_GUIDANCE"].lower()
    assert "gate ran" not in lowered
    assert "gate did not" not in lowered


# --- head diff materialization (bite axis: head.diff exists when cited) ---------------------


def test_ensure_round_head_diff_writes_when_cited(tmp_path):
    # axis: _ensure_round_head_diff materializes head.diff from state
    session_dir = str(tmp_path / "head-session")
    os.makedirs(session_dir)
    head = "diff --git a/x b/x\n"
    state = {"headDiff": head}
    path = RD._ensure_round_head_diff(session_dir, 2, state)
    assert path == os.path.join(session_dir, "round-2", "head.diff")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == head


def test_ensure_round_head_diff_materializes_empty_post_fix_diff(tmp_path):
    # axis: an authoritative empty inline headDiff is a real state — materialize, never wedge
    session_dir = str(tmp_path / "empty-head-session")
    os.makedirs(session_dir)
    state = {"headDiff": ""}
    path = RD._ensure_round_head_diff(session_dir, 2, state)
    assert path == os.path.join(session_dir, "round-2", "head.diff")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == ""


def test_empty_head_diff_audits_placeholders_do_not_refuse(tmp_path):
    # axis: empty post-fix head diff must not refuse audits order render before save_state
    session_dir = str(tmp_path / "empty-head-audits")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path)},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": "",
    }
    paths = _minimal_paths(session_dir)
    payload = {"targets": [{"id": "finding::auth.py::12"}]}
    ph = RD._order_placeholders(
        RP.P_AUDITS, "finding::auth.py::12", 0, state, state["config"],
        payload, session_dir, 2, paths, RD.CHANNEL_FILE,
    )
    assert ph["HEAD_DIFF_PATH"] == os.path.join(session_dir, "round-2", "head.diff")
    assert os.path.isfile(ph["HEAD_DIFF_PATH"])


def test_head_diff_unavailable_refuses_emit(tmp_path):
    # axis: missing headDiff refuses before citing HEAD_DIFF_PATH
    session_dir = str(tmp_path / "head-refuse")
    os.makedirs(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path)},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": None,
    }
    paths = _minimal_paths(session_dir)
    payload = {"targets": [{"id": "finding::auth.py::12"}]}
    with pytest.raises(ValueError, match="order-render-refused:head-diff-unavailable"):
        RD._order_placeholders(
            RP.P_AUDITS, "finding::auth.py::12", 0, state, state["config"],
            payload, session_dir, 2, paths, RD.CHANNEL_FILE,
        )


def test_ensure_fix_batch_file_materializes_empty_batch(tmp_path):
    # axis: authoritative empty fix batch is real state — materialize [], never wedge
    session_dir = str(tmp_path / "empty-batch-session")
    os.makedirs(session_dir)
    state = {"_fixBatch": []}
    path = RD._ensure_fix_batch_file(session_dir, 2, state)
    assert path == os.path.join(session_dir, "round-2", "fix-batch.json")
    with open(path, encoding="utf-8") as fh:
        assert fh.read() == "[]"


def test_fix_batch_unavailable_refuses_materialize(tmp_path):
    # axis: absent/non-list fix batch refuses before writing fix-batch.json
    session_dir = str(tmp_path / "batch-refuse")
    os.makedirs(session_dir)
    with pytest.raises(ValueError, match="order-render-refused:fix-batch-unavailable"):
        RD._ensure_fix_batch_file(session_dir, 2, {})
    state = {"_fixBatch": None, "fixBatch": "not-a-list"}
    with pytest.raises(ValueError, match="order-render-refused:fix-batch-unavailable"):
        RD._ensure_fix_batch_file(session_dir, 2, state)


def test_readable_input_refusal_when_registered_path_missing(tmp_path):
    # axis: unregistered readable input on disk refuses with order-input-missing
    ph = {
        "DIFF_PATH": "/nonexistent/diff.txt",
        "RUBRIC_PATH": RD._shipped_rubric_path(),
    }
    reason = RD._readable_file_input_refusal(ph)
    assert reason == "order-input-missing:DIFF_PATH"


def test_emitted_path_with_space_is_file(tmp_path):
    # axis: driver-generated paths are tested raw — never shell-split on spaces
    spaced = tmp_path / "my dir"
    spaced.mkdir()
    target = spaced / "diff.txt"
    target.write_text("diff\n", encoding="utf-8")
    assert RD._emitted_path_is_file(str(target)) is True


def test_prior_comments_pr_mode_absent_disclosed_not_fabricated(tmp_path):
    # axis: PR-mode absence must not write [] — disclose instead
    session_dir = str(tmp_path / "pr-session")
    os.makedirs(session_dir)
    repo = os.path.join(session_dir, "repo")
    os.makedirs(repo)
    state = RD.new_state(_cfg(tmp_path))
    path = RD._resolve_prior_comments_path(session_dir, state)
    assert path.startswith("(")
    assert not os.path.exists(os.path.join(session_dir, "prior-comments.json"))
    assert state["rounds"]["1"]["priorCommentsUnavailable"] is True
    ph = {"PRIOR_COMMENTS_PATH": path, "RUBRIC_PATH": RD._shipped_rubric_path()}
    assert RD._readable_file_input_refusal(ph) is None
    derived = RO._derived_placeholders(
        RP.P_PANEL,
        {"placeholders": ph, "landing_path": ""},
    )
    block = derived["PRIOR_COMMENTS_INSTRUCTION_BLOCK"]
    assert "No prior-comments.json was supplied" in block
    assert path not in block


def test_prior_comments_branch_mode_absent_is_empty_not_refusal(tmp_path):
    # axis: branch mode legitimately has no prior-comments file
    session_dir = str(tmp_path / "branch-session")
    os.makedirs(session_dir)
    with open(os.path.join(session_dir, RR.META_FILE), "w", encoding="utf-8") as fh:
        json.dump({"mode": "branch"}, fh)
    state = RD.new_state(_cfg(tmp_path))
    assert RD._resolve_prior_comments_path(session_dir, state) == ""
    ph = {"PRIOR_COMMENTS_PATH": "", "RUBRIC_PATH": RD._shipped_rubric_path()}
    assert RD._readable_file_input_refusal(ph) is None


def test_materialize_order_sidecars_refuses_symlinked_clusters_parent(tmp_path):
    # axis: pre-commit sidecar writes must be containment-checked before any byte hits disk
    session_dir = str(tmp_path / "session")
    os.makedirs(session_dir)
    rdir = RR.round_dir(session_dir, 2)
    os.makedirs(rdir)
    external = tmp_path / "external-clusters"
    external.mkdir()
    clusters_link = os.path.join(rdir, RD.ORDER_SIDECAR_CLUSTERS_DIR)
    os.symlink(str(external), clusters_link)
    payload = {"clusters": [{"key": "f.py:0", "findings": []}]}
    external_target = external / "0.json"
    with pytest.raises(ValueError, match="order-render-refused:path-escapes-session"):
        RD._materialize_order_sidecars(
            session_dir, 2, RP.P_VERIFIERS, ["verifier:f.py:0"], payload,
        )
    assert not external_target.exists()


def test_pre_emit_and_commit_sidecar_bytes_match(tmp_path):
    # axis: pre-emit materialization and orders-emit commit write identical sidecar bytes
    session_dir = str(tmp_path / "sidecar-session")
    os.makedirs(session_dir)
    rdir = os.path.join(session_dir, "round-2")
    os.makedirs(rdir)
    roster = ["finding::auth.py::12", "finding::other.py::3"]
    payload = {
        "targets": [
            {"id": "finding::other.py::3", "summary": "other target"},
            {"id": "finding::auth.py::12", "summary": "auth target"},
        ],
    }
    commit_writes = dict(RD._order_sidecar_writes(session_dir, 2, RP.P_AUDITS, roster, payload))
    paths = _minimal_paths(session_dir)
    state = {
        "config": {"repoRoot": str(tmp_path)},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": "diff --git a/f b/f\n",
    }
    RD._order_placeholders(
        RP.P_AUDITS, "finding::auth.py::12", 0, state, state["config"],
        payload, session_dir, 2, paths, RD.CHANNEL_FILE, roster=roster,
    )
    for path, expected in commit_writes.items():
        with open(path, "rb") as fh:
            assert fh.read() == expected


# --- registry census (bite axis: every rendered placeholder is partitioned) ---------------


def test_order_placeholder_registry_partition_is_complete():
    # axis: template + driver placeholder keys partition into registry sets by construction
    partition = _placeholder_partition()
    session_dir = "/tmp/order-input-contract-census"
    state = {
        "config": {"repoRoot": "/tmp"},
        "reviewedDiff": "diff --git a/f b/f\n",
        "headDiff": "diff --git a/f b/f\n",
        "_fixBatch": [],
    }
    payloads = {
        RP.P_PANEL: {},
        RP.P_VERIFIERS: {"clusters": [{"key": "c0", "findings": []}]},
        RP.P_SYNTHESIS: {"findings": []},
        RP.P_GAPSWEEP: {},
        RP.P_AUDITS: {"targets": [{"id": "finding::auth.py::12"}]},
        RP.P_SCOPED: {"hunks": {}},
        RP.P_FIXER: {},
    }
    seat_keys = {
        RP.P_PANEL: "code-reviewer",
        RP.P_VERIFIERS: "verifier:c0",
        RP.P_SYNTHESIS: "synthesis",
        RP.P_GAPSWEEP: "gap-sweep",
        RP.P_AUDITS: "finding::auth.py::12",
        RP.P_SCOPED: "scoped-finder",
        RP.P_FIXER: "fixer",
    }
    missing = []
    for phase in RO.ORDER_PHASES:
        names = _template_placeholders(phase) | _order_placeholder_keys(
            phase, session_dir, state, payloads[phase], seat_keys[phase])
        for name in sorted(names):
            if name not in partition:
                missing.append("%s:%s" % (phase, name))
    assert not missing, "placeholders outside registry partition:\n" + "\n".join(missing)
