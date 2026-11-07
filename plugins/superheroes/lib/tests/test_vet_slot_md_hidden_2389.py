"""#2389 (layer 2 of #2366): ``vet_slot.py`` decides hidden-or-visible in one way, ``md_hidden.scan``.

The invariant: ``vet_slot`` never reads as visible any text GitHub renders hidden, and where ``md_hidden`` is unsure the
write refuses. The oracle is ``fixtures/md_hidden_github_renders_2366.json`` (GitHub's own render of 60 shapes in two
forms, run here on the ``stored`` bytes GitHub rendered). Guard tests are named ``test_gN_*`` (N = 1..6); the bite-proof
record is ``bite_proofs/i2389_vet_slot_md_hidden.md``. Fake-runner units; no real gh, no network."""
import inspect

import pytest

import md_hidden
import vet_slot as vs
from test_md_hidden_2366 import _ROWS, _github_headings, _norm
from test_vet_slot import BODY, RECEIPT, SLOT, FakeGh, _comment, _pages
from test_vet_slot_no_build_record_2342 import BOT_BODY, RECEIPT_NONE

PR = 42
REPO = "owner/example"
MARKER = "<!-- superheroes:advisor-vet -->"
V, H, U = md_hidden.VISIBLE, md_hidden.HIDDEN, md_hidden.UNSURE


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(vs.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _fake(body, receipt=RECEIPT_NONE):
    return FakeGh([body], _pages([_comment(receipt)]))


def _write(fake, tmp_path, slot=SLOT):
    path = tmp_path / "slot.md"
    path.write_text(slot, encoding="utf-8")
    return vs.run_verb("write", PR, REPO, slot_file=str(path), run=fake)


def _evaluate(body, receipt=RECEIPT_NONE, slot=SLOT):
    return vs.evaluate("write", body, [_comment(receipt)], slot, advisor_login="advisor")


def _emptied(body):
    """The ``body-emptied`` refusal ``check_not_emptied`` raises for ``body``, or None."""
    try:
        vs.check_not_emptied(body)
    except vs._Refusal as exc:
        assert exc.reason == "body-emptied", (exc.reason, exc.detail)
        return exc
    return None


def _refused(result, fake, reason, detail=None):
    assert result["ok"] is False, result
    assert result["reason"] == reason, result
    if detail is not None:
        assert detail in result["detail"], result
    assert fake.edit_calls() == []


# --- The table: GitHub's render of each shape, stated per row ----------------------------------------------------------
# route: which path ``vet_slot.no_build_record`` sends the bot form (PRE2389-5): "bot", or "builder" for the three shapes
# whose bot form carries a builder sign (a heading naming the owner half). github: whether GitHub shows the owner heading
# (builder form) and the Advisor vet heading (bot form) top-level: "shown", "hidden", or "shown-unsure" (GitHub shows it
# and md_hidden holds an unsure point, so either answer is safe).
_S, _HID, _SU = "shown", "hidden", "shown-unsure"
_TABLE = {
    "control_plain": ("bot", _S), "control_closed_comment": ("bot", _S), "control_unclosed_comment": ("bot", _HID),
    "pre_quoted_opener": ("bot", _HID), "pre_raw_opener": ("bot", _HID), "div_plain_closer": ("bot", _HID),
    "div_escaped_closer": ("bot", _HID), "inline_code_opener": ("bot", _S), "escaped_opener": ("bot", _S),
    "false_fence_u2028": ("bot", _HID), "false_fence_nel": ("bot", _HID), "false_fence_ff": ("bot", _HID),
    "div_u2028_then_quoted": ("bot", _S), "div_nel_then_quoted": ("bot", _S), "div_ff_then_quoted": ("bot", _S),
    "decl_block": ("bot", _HID), "cdata_block": ("bot", _S), "pi_block": ("bot", _HID),
    "div_then_quoted": ("bot", _HID), "task_item_div": ("bot", _S), "footnote_div": ("bot", _SU),
    "linkref_div": ("bot", _S), "autolink_then_quoted": ("bot", _S), "closed_comment_then_div": ("bot", _S),
    "atx_div": ("bot", _S), "table_cell_div": ("bot", _S), "email_autolink": ("bot", _S),
    "abrupt_comment_div": ("bot", _S), "fenced_div": ("bot", _S), "quote_tab_div": ("bot", _HID),
    "crlf_div": ("bot", _HID), "cr_div": ("bot", _HID), "alert_div": ("bot", _HID), "u2028_mid_quoted": ("bot", _S),
    "div_open_then_inline_comment": ("bot", _SU), "div_open_then_inline_dashdash": ("bot", _SU),
    "bang_close": ("bot", _S), "abrupt_three": ("bot", _S), "textarea_block": ("bot", _HID),
    "script_attr_opener": ("bot", _HID), "unclosed_attr": ("bot", _HID), "lower_decl": ("bot", _S),
    "list_div_opener": ("bot", _HID), "list_lazy_opener": ("bot", _HID), "quote_opener_ends": ("bot", _HID),
    "indented_opener": ("bot", _S), "source_tag": ("bot", _HID), "search_tag": ("bot", _HID),
    "noscript_tag": ("bot", _HID), "setext_then_opener": ("bot", _HID), "type7_interrupt": ("bot", _HID),
    "type7_alone": ("bot", _HID), "fence_tilde_256_cap": ("bot", _HID), "fence_tilde_255_control": ("bot", _S),
    "fence_tick_256_cap": ("bot", _HID), "fence_tilde_300_close_256": ("bot", _SU),
    "image_heading": ("builder", _S), "div_title_unclosed_mid": ("bot", _HID),
    "inline_comment_in_heading": ("builder", _S), "link_heading": ("builder", _S),
}
_BUILDER_SIGNED_BOT = ("image_heading", "inline_comment_in_heading", "link_heading")


def _github_shows(row, key_prefix):
    """GitHub shows a top-level heading whose text starts with ``key_prefix`` (a ``_heading_key`` prefix)."""
    return any(not nested and vs._heading_key(_norm(text)).startswith(key_prefix)
               for text, nested in _github_headings(row["html"]))


def _label(row):
    return "%s-%s" % (row["id"], row["form"])


_BUILDER_ROWS = [r for r in _ROWS if r["form"] == "builder"]
_BOT_ROWS = [r for r in _ROWS if r["form"] == "bot"]
_BOT_ROUTE_BOT = [r for r in _BOT_ROWS if r["id"] not in _BUILDER_SIGNED_BOT]
_BOT_ROUTE_BUILDER = [r for r in _BOT_ROWS if r["id"] in _BUILDER_SIGNED_BOT]
_TRANSIT = [r for r in _ROWS if r["transitChanged"]]


def _ids(rows):
    return [_label(r) for r in rows]


def test_g1_visible_headings_only_table_covers_every_row_and_matches_github():
    """The table states what GitHub shows, and it equals what the fixture's HTML says (so the table is the oracle's)."""
    assert len(_ROWS) == 120
    assert {r["id"] for r in _ROWS} == set(_TABLE)
    for row in _ROWS:
        github = _TABLE[row["id"]][1]
        # builder form: the owner heading; bot form: the appended Advisor vet heading
        key = "whats changing" if row["form"] == "builder" else "advisor vet"
        assert _github_shows(row, key) == (github != _HID), (_label(row), github)


@pytest.mark.parametrize("row", _BOT_ROWS, ids=_ids(_BOT_ROWS))
def test_g4_bot_path_visibility_route_is_the_table_entry(row):
    """PRE2389-5: the route is derived with ``no_build_record`` and equals the table's entry."""
    route = "bot" if vs.no_build_record(row["stored"]) else "builder"
    assert route == _TABLE[row["id"]][0], _label(row)


# --- Fixture oracle: builder form --------------------------------------------------------------------------------------

@pytest.mark.parametrize("row", _BUILDER_ROWS, ids=_ids(_BUILDER_ROWS))
def test_g1_visible_headings_only_builder_form_oracle(row):
    stored = row["stored"]
    assert stored.index("What's changing, and why") < stored.index(MARKER)  # the owner heading is above the marker
    refusal = _emptied(stored)
    github = _TABLE[row["id"]][1]
    shown = _github_shows(row, "whats changing")
    # the invariant: never "no refusal" where GitHub hides the owner heading
    if not shown:
        assert github == _HID
        assert refusal is not None, "GitHub hides the owner heading but check_not_emptied passes: %r" % row["id"]
    elif not md_hidden.scan(stored).unsure:
        assert refusal is None, "GitHub shows the owner heading, scan is sure, yet: %s" % (refusal.detail,)


@pytest.mark.parametrize("row", _BOT_ROUTE_BUILDER, ids=_ids(_BOT_ROUTE_BUILDER))
def test_g1_visible_headings_only_bot_rows_with_builder_signs_take_the_builder_check(row):
    """image_heading, inline_comment_in_heading and link_heading carry builder signs in their bot form: they take the
    builder path, so the owner check answers for them (GitHub's own render says whether the owner heading shows)."""
    stored = row["stored"]
    refusal = _emptied(stored)
    if not _github_shows(row, "whats changing"):
        assert refusal is not None, "GitHub hides the owner heading but check_not_emptied passes: %r" % row["id"]
    elif not md_hidden.scan(stored).unsure:
        assert refusal is None, refusal.detail


# --- Fixture oracle: bot form -------------------------------------------------------------------------------------------

def _bot_offsets(body):
    """Marker, appended heading and verdict line of a composed bot body (the fixture's shape)."""
    return body.rindex(MARKER), body.rindex("## Advisor vet"), body.rindex("**Verdict: READY**")


@pytest.mark.parametrize("row", _BOT_ROUTE_BOT, ids=_ids(_BOT_ROUTE_BOT))
def test_g4_bot_path_visibility_fixture_oracle(row):
    stored = row["stored"]
    marker_at, heading_at, slot_at = _bot_offsets(stored)
    problem = vs._unrendered_slot(stored, marker_at, heading_at, slot_at)
    github = _TABLE[row["id"]][1]
    shown = _github_shows(row, "advisor vet")
    # the invariant: never "no problem" where GitHub hides the Advisor vet heading
    if not shown:
        assert github == _HID
        assert problem is not None, "GitHub hides the Advisor vet heading but the check passes: %r" % row["id"]
        assert "would not render" in problem
    elif not md_hidden.scan(stored).unsure:
        assert problem is None, "GitHub shows the Advisor vet heading, scan is sure, yet: %s" % problem


# --- Transit-changed rows: the sent bytes, md_hidden's own reading only -------------------------------------------------
# MODEL-ONLY: transit rewrote these bytes (U+2028, U+0085, form feed and CR line ends to LF, <![CDATA[ to <[CDATA[), so
# GitHub's render does not answer for the sent bytes. The checks below hold the code to md_hidden's own reading of them.

@pytest.mark.parametrize("row", [r for r in _TRANSIT if r["form"] == "builder" or r["id"] in _BUILDER_SIGNED_BOT],
                         ids=lambda r: _label(r))
def test_g1_visible_headings_only_model_only_builder_on_sent_bytes(row):
    sent = row["sent"]
    scan = md_hidden.scan(sent)
    markers = vs._find_live_standalone_markers(sent, MARKER)
    limit = min(markers) if markers else len(sent) + 1
    held = any(state == V and at < limit and "![" not in text and vs._heading_key(text).startswith("whats changing")
               for at, text, state in scan.headings)
    refusal = _emptied(sent)
    assert (refusal is None) == held, (_label(row), refusal and refusal.detail)


@pytest.mark.parametrize("row", [r for r in _TRANSIT if r["form"] == "bot" and r["id"] not in _BUILDER_SIGNED_BOT],
                         ids=lambda r: _label(r))
def test_g4_bot_path_visibility_model_only_bot_on_sent_bytes(row):
    sent = row["sent"]
    marker_at, heading_at, slot_at = _bot_offsets(sent)
    scan = md_hidden.scan(sent)
    visible = (vs._line_state(scan, marker_at) == V and vs._line_state(scan, slot_at) == V
               and {at: st for at, _t, st in scan.headings}.get(heading_at) == V)
    problem = vs._unrendered_slot(sent, marker_at, heading_at, slot_at)
    assert (problem is None) == visible, (_label(row), problem)


# --- Both bot paths through evaluate and run_verb ------------------------------------------------------------------------

PRE_QUOTED = "Bumps requests from 2.31.0 to 2.32.3.\n\n<pre>\n\n`<!--`\n</pre>\n"  # GitHub hides what follows (fixture
# pre_quoted_opener): the quoted opener sits in a raw HTML block, so it is a real comment
BOT_MARKER_PRESENT = "\n## Advisor vet\n" + MARKER + "\n\nold slot text\n"
HIDES = {"marker-absent": PRE_QUOTED, "marker-present": PRE_QUOTED + BOT_MARKER_PRESENT}
CONTROLS = {"marker-absent": BOT_BODY, "marker-present": BOT_BODY + BOT_MARKER_PRESENT}


@pytest.mark.parametrize("name", sorted(HIDES))
def test_g4_bot_path_visibility_a_hidden_shape_refuses_write_failed_through_evaluate(name):
    result = _evaluate(HIDES[name])
    assert result["ok"] is False and result["reason"] == "write-failed", result
    assert "would not render" in result["detail"], result


@pytest.mark.parametrize("name", sorted(HIDES))
def test_g4_bot_path_visibility_a_hidden_shape_refuses_write_failed_through_run_verb(name, tmp_path):
    fake = _fake(HIDES[name])
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


@pytest.mark.parametrize("name", sorted(CONTROLS))
def test_g4_bot_path_visibility_the_control_writes_through_evaluate_and_run_verb(name, tmp_path):
    assert _evaluate(CONTROLS[name])["ok"] is True
    fake = _fake(CONTROLS[name])
    result = _write(fake, tmp_path)
    assert result["ok"] is True, result
    assert len(fake.edit_calls()) == 1


@pytest.mark.parametrize("marker, slot, heading, expected", [
    (V, H, V, "the slot's verdict line reads hidden"),
    (V, U, V, "the slot's verdict line reads unsure (the render could not be decided)"),
    (H, V, V, "the advisor-vet marker line reads hidden"),
    (U, V, V, "the advisor-vet marker line reads unsure (the render could not be decided)"),
    (V, V, H, "the appended Advisor vet heading reads hidden"),
    (V, V, U, "the appended Advisor vet heading reads unsure (the render could not be decided)"),
])
def test_g4_bot_path_visibility_each_of_the_three_reads_is_its_own_sentence(marker, slot, heading, expected):
    """One synthetic rendering per case: the marker line, the verdict line and the appended heading are each read."""
    rendering = md_hidden.Rendering([(0, V), (10, marker), (20, slot)], [(0, "Advisor vet", heading)], [])
    problem = vs._visibility_problem(rendering, 12, 20, 0)  # the marker offset sits inside its line
    assert problem is not None and "would not render" in problem and expected in problem


def test_g4_bot_path_visibility_all_three_visible_is_no_problem():
    rendering = md_hidden.Rendering([(0, V), (10, V), (20, V)], [(0, "Advisor vet", V)], [])
    assert vs._visibility_problem(rendering, 12, 20, 0) is None
    assert vs._visibility_problem(rendering, 12, 20) is None  # no heading asked for (marker present)


def test_g4_bot_path_visibility_a_heading_offset_that_is_not_a_heading_is_a_problem():
    rendering = md_hidden.Rendering([(0, V), (10, V), (20, V)], [], [])
    problem = vs._visibility_problem(rendering, 12, 20, 0)
    assert problem is not None and "not a heading" in problem


# --- Image-owner isolation (BRIEF-4) ------------------------------------------------------------------------------------

IMAGE_OWNER_BODY = BODY.replace("## What's changing, and why", "## ![What's changing, and why](x.png)", 1)


def test_g2_image_heading_is_never_the_owner_heading():
    refusal = _emptied(IMAGE_OWNER_BODY)
    assert refusal is not None and "What's changing, and why" in refusal.detail
    assert _emptied(BODY) is None  # the same body with a plain heading holds the owner half


def test_g2_image_heading_through_evaluate_and_run_verb(tmp_path):
    result = _evaluate(IMAGE_OWNER_BODY, receipt=RECEIPT)
    assert result["ok"] is False and result["reason"] == "body-emptied", result
    fake = _fake(IMAGE_OWNER_BODY, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied")
    assert _evaluate(BODY, receipt=RECEIPT)["ok"] is True


def test_g2_image_heading_alongside_a_plain_owner_heading_still_holds():
    both = "## ![img](x.png)\n\n" + BODY
    assert _emptied(both) is None


# --- Unsure detail (G3) -------------------------------------------------------------------------------------------------

def _row(shape, form="builder"):
    return next(r for r in _ROWS if r["id"] == shape and r["form"] == form)


@pytest.mark.parametrize("shape", ["fence_tick_256_cap", "fence_tilde_256_cap"])
def test_g3_unsure_detail_a_256_character_fence_above_the_owner_heading_says_so(shape):
    body = _row(shape)["stored"]
    unsure = md_hidden.scan(body).unsure
    assert unsure and unsure[0][0] < body.index(MARKER)
    refusal = _emptied(body)
    assert refusal is not None
    assert "edit history" not in refusal.detail
    assert "could not be decided" in refusal.detail and "by hand" in refusal.detail
    assert unsure[0][1] in refusal.detail  # the first unsure point's why


def test_g3_unsure_detail_through_evaluate_names_no_edit_history(tmp_path):
    body = _row("fence_tick_256_cap")["stored"]
    result = _evaluate(body, receipt=RECEIPT)
    assert result["ok"] is False and result["reason"] == "body-emptied", result
    assert "edit history" not in result["detail"]
    fake = _fake(body, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "body-emptied", "by hand")


def test_g3_unsure_detail_without_an_unsure_point_keeps_the_edit_history_remedy():
    body = "## Advisor vet\n" + MARKER + "\n\nstuff\n"
    assert md_hidden.scan(body).unsure == ()
    refusal = _emptied(body)
    assert refusal is not None and "edit history" in refusal.detail and "could not be decided" not in refusal.detail


def test_g3_unsure_detail_an_unsure_point_below_the_marker_does_not_change_the_detail():
    body = "## Advisor vet\n" + MARKER + "\n\n" + "`" * 256 + "\nx\n"
    assert md_hidden.scan(body).unsure
    refusal = _emptied(body)
    assert refusal is not None and "edit history" in refusal.detail


def test_g3_unsure_detail_an_internal_md_hidden_error_refuses_never_passes(monkeypatch):
    def boom(_body):
        raise RuntimeError("boom")

    monkeypatch.setattr(md_hidden, "_scan", boom)
    refusal = _emptied(BODY)
    assert refusal is not None and "could not be decided" in refusal.detail and "internal error" in refusal.detail


# --- BRIEF-1: the builder path (G5) -------------------------------------------------------------------------------------

DIV_TITLE_BODY = BODY.replace("## Advisor vet\n", '<div title="\n\n## Advisor vet\n', 1)


def test_g5_builder_path_visibility_an_unclosed_div_title_before_the_slot_refuses_write_failed(tmp_path):
    scan = md_hidden.scan(DIV_TITLE_BODY)
    assert scan.unsure  # the shape: layer 1 marks it unsure
    assert _emptied(DIV_TITLE_BODY) is None  # the owner heading sits above it: this is not the owner check's refusal
    result = _evaluate(DIV_TITLE_BODY, receipt=RECEIPT)
    assert result["ok"] is False and result["reason"] == "write-failed", result
    assert "would not render" in result["detail"] and "reads unsure" in result["detail"], result
    fake = _fake(DIV_TITLE_BODY, receipt=RECEIPT)
    _refused(_write(fake, tmp_path), fake, "write-failed", "would not render")


def test_g5_builder_path_visibility_the_fixture_shape_refuses_write_failed():
    stored = _row("div_title_unclosed_mid")["stored"]
    result = _evaluate(stored, receipt=RECEIPT)
    assert result["ok"] is False
    assert result["reason"] in ("write-failed", "body-emptied"), result  # never ok, never a pass


def test_g5_builder_path_visibility_a_hidden_marker_line_refuses_write_failed():
    """A comment opened above the owner heading's ... marker: the marker line itself reads hidden."""
    body = BODY.replace("## Advisor vet\n", "<pre>\n\n`<!--`\n</pre>\n\n## Advisor vet\n", 1)
    result = _evaluate(body, receipt=RECEIPT)
    assert result["ok"] is False and result["reason"] == "write-failed", result
    assert "advisor-vet marker line reads hidden" in result["detail"], result


def test_g5_builder_path_visibility_the_plain_body_still_writes(tmp_path):
    result = _evaluate(BODY, receipt=RECEIPT)
    assert result["ok"] is True, result
    fake = _fake(BODY, receipt=RECEIPT)
    assert _write(fake, tmp_path)["ok"] is True


def test_g5_builder_path_visibility_an_internal_md_hidden_error_refuses_never_passes(monkeypatch):
    # The failure fires only on a scan of a text other than the builder's own BODY, i.e. on the composed body. Found by
    # reading vet_slot.py: the only md_hidden reader before composition is check_not_emptied (it scans BODY itself); the
    # leftover check (leftover_accepting._visible -> md_hidden.scan) runs in run_verb, not in evaluate. So the failure
    # reaches the composed body's visibility check at vet_slot.py:911, and write-failed is the one reason that can refuse.
    real_scan = md_hidden._scan
    seen = []

    def fail_composed(text):
        if text != BODY:
            seen.append(text)
            raise RuntimeError("boom")
        return real_scan(text)

    monkeypatch.setattr(md_hidden, "_scan", fail_composed)
    result = _evaluate(BODY, receipt=RECEIPT)
    assert seen  # the composed body was scanned, and that scan failed
    assert result["ok"] is False and result["reason"] == "write-failed", result
    # md_hidden.scan reports an internal failure as an unsure point on every line, which _visibility_problem words so
    assert "the render could not be decided" in result["detail"] and "so the slot would not render" in result["detail"], result


def test_g4_bot_path_visibility_an_internal_md_hidden_error_refuses_never_passes(monkeypatch):
    def boom(_body):
        raise RuntimeError("boom")

    monkeypatch.setattr(md_hidden, "_scan", boom)
    result = _evaluate(CONTROLS["marker-absent"])
    assert result["ok"] is False and result["reason"] == "write-failed", result


# --- Fail-closed edges kept ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", ["", "  \n\t\n", "\n"])
def test_an_empty_or_whitespace_body_still_refuses_body_emptied_before_any_marker_check(body):
    result = _evaluate(body)
    assert result["ok"] is False and result["reason"] == "body-emptied", result
    assert "PR body is empty" in result["detail"]


@pytest.mark.parametrize("body", [None, 7, b"x", ["x"]])
def test_a_non_string_body_still_reaches_analyze_body_and_refuses_read_failed(body):
    result = _evaluate(body)
    assert result["ok"] is False and result["reason"] == "read-failed", result


# --- PRE2389-1: the line holding an offset (G6) ---------------------------------------------------------------------------

WHITESPACE = [("u2028", " "), ("nbsp", " "), ("u3000", "　")]


def _marker_variants(ws):
    """Bot and builder bodies whose marker line carries ``ws`` before it, and after it."""
    bot = "Bumps requests from 2.31.0 to 2.32.3.\n\n## Advisor vet\n%s\n\nold slot text\n"
    builder = BODY.replace(MARKER, "%s", 1)
    return {
        "bot-leading": bot % (ws + MARKER), "bot-trailing": bot % (MARKER + ws),
        "builder-leading": builder % (ws + MARKER), "builder-trailing": builder % (MARKER + ws),
    }


def _structured(result):
    assert isinstance(result, dict) and isinstance(result.get("ok"), bool), result
    if not result["ok"]:
        assert isinstance(result["reason"], str) and result["reason"] and isinstance(result["detail"], str), result


@pytest.mark.parametrize("variant", ["bot-leading", "bot-trailing", "builder-leading", "builder-trailing"])
@pytest.mark.parametrize("name, ws", WHITESPACE, ids=[n for n, _ in WHITESPACE])
def test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_evaluate(name, ws, variant):
    body = _marker_variants(ws)[variant]
    receipt = RECEIPT if variant.startswith("builder") else RECEIPT_NONE
    _structured(_evaluate(body, receipt=receipt))  # never an exception


@pytest.mark.parametrize("variant", ["bot-leading", "bot-trailing", "builder-leading", "builder-trailing"])
@pytest.mark.parametrize("name, ws", WHITESPACE, ids=[n for n, _ in WHITESPACE])
def test_g6_line_holding_a_marker_line_with_unicode_whitespace_through_run_verb(name, ws, variant, tmp_path):
    body = _marker_variants(ws)[variant]
    receipt = RECEIPT if variant.startswith("builder") else RECEIPT_NONE
    fake = _fake(body, receipt=receipt)
    result = _write(fake, tmp_path)
    _structured(result)
    if not result["ok"]:
        assert fake.edit_calls() == []  # no edit pushed on a refusal


@pytest.mark.parametrize("name, ws", WHITESPACE, ids=[n for n, _ in WHITESPACE])
def test_g6_line_holding_a_leading_whitespace_marker_offset_sits_inside_its_line(name, ws):
    """The shape that made ``state_at`` raise: the marker offset is not a line start."""
    body = "Bumps x.\n\n" + ws + MARKER + "\n\nold\n"
    (marker_at,) = vs._find_live_standalone_markers(body, MARKER)
    scan = md_hidden.scan(body)
    assert marker_at not in dict(scan.lines)  # inside the line, one past its start
    assert vs._line_state(scan, marker_at) == scan.state_at(marker_at - len(ws))


def test_g6_line_holding_returns_the_state_of_the_last_line_at_or_before_the_offset():
    body = "a\n\n<!-- open\n\nb\n"
    scan = md_hidden.scan(body)
    assert [state for _at, state in scan.lines][-1] == H  # the unclosed comment hides the tail
    assert vs._line_state(scan, len(body) - 1) == H
    assert vs._line_state(scan, len(body) + 5) == H  # past the end: the last line
    assert vs._line_state(scan, 0) == V
    assert vs._line_state(scan, 1) == V  # inside the first line (its terminator)


def test_g6_line_holding_no_line_at_or_before_the_offset_reads_unsure():
    scan = md_hidden.scan("a\nb\n")
    assert vs._line_state(scan, -1) == U
    assert vs._line_state(md_hidden.scan(""), 0) == U


# --- Census (the removal) -------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["_comment_scan", "_could_open_html_block", "_SPLITLINES_ONLY_BREAKS",
                                  "_BLOCK_LEAD_ASCII", "_BLOCK_START_RE", "_AUTOLINK_RE"])
def test_census_the_old_comment_scanner_is_gone(name):
    assert not hasattr(vs, name)


@pytest.mark.parametrize("func", [vs._live_lines, vs._span_owned_problem, vs._owner_shell_blocks],
                         ids=lambda f: f.__name__)
def test_census_the_moved_scanners_read_markdown_lines_not_splitlines(func):
    assert ".splitlines(" not in inspect.getsource(func)


# --- U+2028 (one Markdown line, not two), one test per moved scanner ------------------------------------------------------

def test_u2028_live_lines_a_fence_opener_after_u2028_is_not_a_fence():
    text = "intro ```\n" + MARKER + "\n"
    assert (len("intro ```\n"), MARKER) in list(vs._live_lines(text))  # the marker below stays live
    assert [line for _o, line in vs._live_lines(text)] == ["intro ```", MARKER]
    # control: with a newline the fence opens and the marker is dead
    assert MARKER not in [line for _o, line in vs._live_lines("intro\n```\n" + MARKER + "\n")]


def test_u2028_span_owned_problem_a_heading_after_u2028_is_not_a_heading_line():
    verdict = "**Verdict: NOT-READY** · abc"
    assert vs._span_owned_problem(verdict + " ## Not a heading\n\nBody.\n") is None
    problem = vs._span_owned_problem(verdict + "\n## A heading\n\nBody.\n")  # control: a real heading line
    assert problem is not None and problem[2] == "(c) no heading"


def test_u2028_owner_shell_blocks_a_fence_opener_after_u2028_opens_no_fence():
    body = "text ```bash\nmongosh prod\n```\n"
    assert vs.owner_command_blocks(body) == []
    control = vs.owner_command_blocks("text\n```bash\nmongosh prod\n```\n")
    assert [b["tool"] for b in control] == ["mongosh"]
