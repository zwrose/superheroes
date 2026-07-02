"""Layer 3 golden tests — run is_usable_draft against architect-format docs.

Pins the correct heading format for tasks docs so producer/check drift fails CI.
These tests use the REAL is_usable_draft + the real _SECTIONS from front_half_usable.py.
No stubs; no mocks.
"""
import json
import os
import subprocess
import sys

import front_half as fh
import front_half_usable as fhu

LIB = os.path.dirname(os.path.abspath(__file__)) + "/.."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(body):
    """Wrap a body in valid frontmatter."""
    return "---\ndocType: tasks\ngates: {review: pending}\n---\n" + body


def _plan_doc(body):
    return "---\ndocType: plan\ngates: {review: pending}\n---\n" + body


# ---------------------------------------------------------------------------
# Golden tasks doc — new ## heading format (Layer 1 fix: what we now require)
# ---------------------------------------------------------------------------

_TASKS_NEW_FORMAT = _make_doc(
    "# My Feature — Tasks\n\n"
    "## Goal\n\n"
    "Implement X so that users can do Y.\n\n"
    "## Architecture\n\n"
    "The feature lives in plugins/superheroes/lib/foo.py and its JS twin foo.js.\n"
    "Data flows from the spine through the exec pipe.\n\n"
    "## Tech Stack\n\n"
    "Python 3.9+, Node 18+, pytest, node --test.\n\n"
    "## Tasks\n\n"
    "- [ ] Task 1 — Write failing test\n"
    "- [ ] Task 2 — Implement to green\n"
)

_TASKS_SECTIONS = tuple(fhu._SECTIONS["tasks"])   # ("Goal", "Architecture", "Tech Stack")


def test_tasks_new_heading_format_is_usable():
    """Golden: tasks doc with ## headings -> usable:true (Layer 1 fix accepted)."""
    assert fh.is_usable_draft(_TASKS_NEW_FORMAT, "h1", "h1",
                               required_sections=_TASKS_SECTIONS) is True


# ---------------------------------------------------------------------------
# Golden tasks doc — OLD bold-label format (the bug we fixed)
# ---------------------------------------------------------------------------

_TASKS_OLD_FORMAT = _make_doc(
    "# My Feature — Tasks\n\n"
    "**Goal:** Implement X so that users can do Y.\n\n"
    "**Architecture:** The feature lives in plugins/superheroes/lib/foo.py.\n\n"
    "**Tech Stack:** Python 3.9+, Node 18+.\n\n"
    "## Tasks\n\n"
    "- [ ] Task 1 — Write failing test\n"
    "- [ ] Task 2 — Implement to green\n"
)


def test_tasks_old_bold_label_format_is_not_usable():
    """Golden: tasks doc with **Goal:** bold labels (old writing-plans format) -> usable:false.

    Documents the bug this PR fixes: is_usable_draft requires ## headings, not bold inline labels.
    A regression back to bold labels would re-open this bug — caught here.
    """
    assert fh.is_usable_draft(_TASKS_OLD_FORMAT, "h1", "h1",
                               required_sections=_TASKS_SECTIONS) is False


# ---------------------------------------------------------------------------
# Golden plan doc — ## headings (plan already correct before this PR)
# ---------------------------------------------------------------------------

_PLAN_SECTIONS = tuple(fhu._SECTIONS["plan"])

_PLAN_DOC = _plan_doc(
    "# My Feature — Plan\n\n"
    "## Overview\n\n"
    "We are adding X to support Y.\n\n"
    "## Goals & non-goals\n\n"
    "Goals: deliver X. Non-goals: rewire Z.\n\n"
    "## Architecture\n\n"
    "A new module in lib/ with a JS twin.\n\n"
    "## Components & interfaces\n\n"
    "foo.py exposes bar(). foo.js twin exposes bar().\n\n"
    "## How the requirements are met\n\n"
    "Each requirement maps to a task. FR-1 via Task 1.\n\n"
    "## Key decisions & alternatives\n\n"
    "Decision: use exec pipe. Alternative: in-process. Rejected (sandbox).\n\n"
    "## Risks & mitigations\n\n"
    "Risk: parity drift. Mitigation: parity suite.\n\n"
    "## Dependencies & assumptions\n\n"
    "Depends on #104 loop. Assumes Python 3.9+.\n\n"
)


def test_plan_heading_format_is_usable():
    """Golden: plan doc with all required ## sections -> usable:true."""
    assert fh.is_usable_draft(_PLAN_DOC, "h1", "h1",
                               required_sections=_PLAN_SECTIONS) is True


# ---------------------------------------------------------------------------
# Golden tasks doc — missing a required section -> usable:false
# ---------------------------------------------------------------------------

_TASKS_MISSING_SECTION = _make_doc(
    "# My Feature — Tasks\n\n"
    "## Goal\n\n"
    "Implement X.\n\n"
    "## Architecture\n\n"
    "Lives in lib/foo.py.\n\n"
    # NOTE: "Tech Stack" section is intentionally absent
    "## Tasks\n\n"
    "- [ ] Task 1\n"
)


def test_tasks_missing_required_section_is_not_usable():
    """Golden: tasks doc missing Tech Stack -> usable:false (section enforcement)."""
    assert fh.is_usable_draft(_TASKS_MISSING_SECTION, "h1", "h1",
                               required_sections=_TASKS_SECTIONS) is False


# ---------------------------------------------------------------------------
# Golden plan doc — missing a required section -> usable:false
# ---------------------------------------------------------------------------

_PLAN_MISSING_SECTION = _plan_doc(
    "# My Feature — Plan\n\n"
    "## Overview\n\nWe are adding X.\n\n"
    "## Goals & non-goals\n\nGoals: deliver X.\n\n"
    # Missing: Architecture, Components & interfaces, How the requirements are met,
    #          Key decisions & alternatives, Risks & mitigations, Dependencies & assumptions
)


def test_plan_missing_required_section_is_not_usable():
    """Golden: plan doc missing Architecture (and others) -> usable:false."""
    assert fh.is_usable_draft(_PLAN_MISSING_SECTION, "h1", "h1",
                               required_sections=_PLAN_SECTIONS) is False


# ---------------------------------------------------------------------------
# Confirm via CLI: front_half_usable.py --emit-signals returns the gap fields (Layer 2a)
# The CLI test uses a real doc file on disk and the real --emit-signals output.
# ---------------------------------------------------------------------------

def test_emit_signals_new_format_emits_gap_fields(tmp_path):
    """--emit-signals with the new heading format: usable=True, missing_sections=[], placeholder=False."""
    import subprocess, sys
    d = tmp_path / "docs" / "superheroes" / "wi"
    d.mkdir(parents=True)
    # spec.md anchors the mode-aware resolver in-repo (a live run always has an approved spec).
    (d / "spec.md").write_text("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
    (d / "tasks.md").write_text(_TASKS_NEW_FORMAT)
    # Write the marker so the signal matches.
    r = subprocess.run(
        [sys.executable, LIB + "/front_half_usable.py",
         "--work-item", "wi", "--doc", "tasks", "--root", str(tmp_path), "--write-marker"],
        capture_output=True, text=True)
    assert json.loads(r.stdout)["wrote"] is True

    r = subprocess.run(
        [sys.executable, LIB + "/front_half_usable.py",
         "--work-item", "wi", "--doc", "tasks", "--root", str(tmp_path), "--emit-signals"],
        capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert out["usable"] is True
    assert out["missing_sections"] == [], f"expected no gaps, got {out.get('missing_sections')}"
    assert out["placeholder"] is False


def test_emit_signals_old_format_emits_specific_gaps(tmp_path):
    """--emit-signals with old bold-label format: usable=False, missing_sections lists all 3 sections."""
    import subprocess, sys
    d = tmp_path / "docs" / "superheroes" / "wi"
    d.mkdir(parents=True)
    # spec.md anchors the mode-aware resolver in-repo (a live run always has an approved spec).
    (d / "spec.md").write_text("---\ndocType: spec\ngates: {review: passed}\n---\n# S\n")
    (d / "tasks.md").write_text(_TASKS_OLD_FORMAT)

    r = subprocess.run(
        [sys.executable, LIB + "/front_half_usable.py",
         "--work-item", "wi", "--doc", "tasks", "--root", str(tmp_path), "--emit-signals"],
        capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert out["usable"] is False
    # All three required sections are absent as headings -> all should be in missing_sections
    for sec in ("Goal", "Architecture", "Tech Stack"):
        assert sec in out["missing_sections"], (
            f"Expected '{sec}' in missing_sections, got {out.get('missing_sections')}"
        )
    assert out["placeholder"] is False
