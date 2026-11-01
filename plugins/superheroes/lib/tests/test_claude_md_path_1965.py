"""#1965 — every review seat gets the project's CLAUDE.md by absolute path.

External review seats run in a sanitized view with CLAUDE.md stripped, so a bare relative
`CLAUDE.md` in a reviewer order opens nothing. The round driver resolves the live-checkout path
once (`_claude_md_path_placeholder`) and every `dispatch-review` order template names it only
through the `CLAUDE_MD_PATH` placeholder. The build session applies the fixes in place and has no order.
"""
import os
import re
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import round_driver as RD
import round_orders as RO
import round_phases as RP
import sanitized_view as sv
from test_round_orders import _base_context

_PLACEHOLDER = "{{CLAUDE_MD_PATH}}"
# A bare relative CLAUDE.md in a path slot: "...: CLAUDE.md" at end of line, a line that is only
# the name, "(CLAUDE.md)" tail, or "...: CLAUDE.md and ..." (the five "Project conventions" lines).
_BARE_SLOT = re.compile(r"(?:^|[:(]\s*)CLAUDE\.md\)?\s*$|:\s*CLAUDE\.md\s+and\b")
# The sweep's seats are searchers, not reviewers: they search a fixed file list for one described mistake and judge nothing, so they need no CLAUDE.md.
_REVIEWER_PHASES = [phase for phase in RO.ORDER_PHASES if phase != RP.P_SWEEP]


def _template(phase):
    template, reason = RO._read_template(phase)
    assert reason is None, reason
    return template


# --- (a) the invariant, keyed to the chokepoint -----------------------------------


@pytest.mark.parametrize("phase", _REVIEWER_PHASES)
def test_reviewer_template_names_claude_md_only_through_placeholder(phase):
    template = _template(phase)
    assert _PLACEHOLDER in template, "%s does not carry %s" % (phase, _PLACEHOLDER)
    bare = [line for line in template.splitlines() if _BARE_SLOT.search(line)]
    assert bare == [], "%s names CLAUDE.md as a bare relative path: %r" % (phase, bare)


def test_reviewer_phase_set_is_every_order_phase():
    assert _REVIEWER_PHASES == [
        RP.P_PANEL, RP.P_VERIFIERS, RP.P_SYNTHESIS, RP.P_SEAMS, RP.P_SECOND_TEST, RP.P_AUDITS,
        RP.P_SCOPED]
    assert "CLAUDE_MD_PATH" in RD.ORDER_DERIVED_PLACEHOLDERS


def test_sweep_is_an_order_phase_whose_template_has_no_bare_claude_md_slot():
    # axis: the sweep stays a real order phase (t1) and its searcher template names no bare CLAUDE.md (t2)
    # — see bite-proof record c4_wo2c_test_doubles
    assert RP.P_SWEEP in RO.ORDER_PHASES
    bare = [line for line in _template(RP.P_SWEEP).splitlines() if _BARE_SLOT.search(line)]
    assert bare == [], "%s names CLAUDE.md as a bare relative path: %r" % (RP.P_SWEEP, bare)


# --- (b)(c) the placeholder value ---------------------------------------------------


def test_placeholder_is_absolute_path_when_claude_md_is_a_file(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# conventions\n")
    value = RD._claude_md_path_placeholder(str(tmp_path))
    assert value == os.path.join(str(tmp_path), "CLAUDE.md")
    assert os.path.isabs(value)


def test_placeholder_is_absolute_path_when_claude_md_is_a_symlink_to_a_file(tmp_path):
    target = tmp_path / "real.md"
    target.write_text("# conventions\n")
    os.symlink(str(target), str(tmp_path / "CLAUDE.md"))
    assert RD._claude_md_path_placeholder(str(tmp_path)) == os.path.join(
        str(tmp_path), "CLAUDE.md")


def test_placeholder_is_no_claude_md_sentence_when_absent(tmp_path):
    assert RD._claude_md_path_placeholder(str(tmp_path)) == (
        "(this project has no CLAUDE.md at %s)" % str(tmp_path))


def test_placeholder_is_no_claude_md_sentence_when_claude_md_is_a_directory(tmp_path):
    (tmp_path / "CLAUDE.md").mkdir()
    assert RD._claude_md_path_placeholder(str(tmp_path)) == (
        "(this project has no CLAUDE.md at %s)" % str(tmp_path))


@pytest.mark.parametrize("bad_root", [None, "", 0, 12, ["x"], {"a": 1}, b"/tmp"])
def test_placeholder_never_raises_and_never_names_the_bare_file(bad_root):
    value = RD._claude_md_path_placeholder(bad_root)
    assert value == "(this project has no CLAUDE.md at %s)" % (bad_root,)
    assert value != "CLAUDE.md"


# --- (d) end to end through _order_placeholders and render_order ---------------------


def _panel_placeholders_for(repo_root, monkeypatch, phase=RP.P_PANEL, seat="code-reviewer"):
    import calibration_resolve as cr

    monkeypatch.setattr(
        cr, "resolve", lambda _cwd, **kw: {"dispatch_core": None, "dispatch_layer": None})
    session_dir = os.path.join(repo_root, ".session")
    os.makedirs(session_dir, exist_ok=True)
    state = {"config": {"repoRoot": repo_root}, "reviewedDiff": ""}
    paths = {
        "storage_key": "code-reviewer.a0",
        "landing_path": os.path.join(session_dir, "landing.json"),
        "envelope_landing_path": os.path.join(session_dir, "env-landing.json"),
        "bare_payload_path": os.path.join(session_dir, "bare.json"),
        "envelope_stub_path": os.path.join(session_dir, "stub.json"),
        "order_path": os.path.join(session_dir, "order.md"),
    }
    return RD._order_placeholders(
        phase, seat, 0, state, state["config"], {}, session_dir, 1, paths, RD.CHANNEL_FILE)


def test_panel_order_names_claude_md_by_absolute_path_end_to_end(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    with open(os.path.join(repo, "CLAUDE.md"), "w") as fh:
        fh.write("# conventions\n")
    ph = _panel_placeholders_for(repo, monkeypatch)
    expected = os.path.join(repo, "CLAUDE.md")
    assert ph["CLAUDE_MD_PATH"] == expected
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", _base_context(placeholders=ph))
    assert reason is None, reason
    lines = text.splitlines()
    assert "- CLAUDE.md (project conventions): %s" % expected in lines
    assert "- CLAUDE.md (project conventions): CLAUDE.md" not in lines
    assert os.path.isabs(expected)


def test_panel_order_renders_no_claude_md_sentence_end_to_end(tmp_path, monkeypatch):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    ph = _panel_placeholders_for(repo, monkeypatch)
    text, reason = RO.render_order(RP.P_PANEL, "code-reviewer", _base_context(placeholders=ph))
    assert reason is None, reason
    assert ("- CLAUDE.md (project conventions): (this project has no CLAUDE.md at %s)" % repo
            ) in text.splitlines()


# --- (e) the sanitized-view notice -----------------------------------------------------


def test_sanitized_view_notice_points_seats_at_absolute_paths_outside_the_view():
    notice = sv.sanitized_view_notice({"stripped": ["CLAUDE.md"], "headSha": "abc"})
    assert "readable at that path" in notice
    assert "their absence is NOT a finding" not in notice
    assert "Where your instructions name" in notice
    assert "CLAUDE.md or its core and review-crew files" in notice
    assert "calibration" not in notice


@pytest.mark.parametrize("line", [
    "- CLAUDE.md (project conventions): CLAUDE.md",
    "- Project conventions: CLAUDE.md and the project profile.",
    "- Project conventions (CLAUDE.md)",
])
def test_bare_slot_regex_matches_bare_relative_claude_md(line):
    assert _BARE_SLOT.search(line)


@pytest.mark.parametrize("line", [
    "- CLAUDE.md (project conventions): {{" + "CLAUDE_MD_PATH}}",
    "- Project conventions: CLAUDE.md at /abs/CLAUDE.md, and the project profile.",
    "and CLAUDE.md for threat model, scope, focus hints, canonical patterns, and",
    "Base rubric (binding) > CLAUDE.md (conventions) > core + layer (adder over CLAUDE.md)",
])
def test_bare_slot_regex_ignores_placeholder_absolute_and_prose_mentions(line):
    assert not _BARE_SLOT.search(line)
