# plugins/superheroes/lib/pr_body.py
"""Pure PR-body composition for the ship-phase honesty gates (issue #228).

Two generated sections are seeded into the draft PR's body so the build/ship legs FILL
them rather than invent them:

  - the **Definition of done** disposition table (skeleton: one blank row per spec DoD
    bullet), anchored on `dod_gate.TABLE_MARKER`; the mark-ready DoD gate reads it back.
  - the generated **Stubbed seams** section (one line per `STUB(#NNN)` marker in the PR
    diff), anchored on `STUBS_MARKER`. Generated, not authored, so it cannot be omitted;
    an empty section is omitted entirely (no noise on stub-free PRs).

Composition is idempotent: a body that already carries a section's marker is left as-is
(so re-seeding on resume never double-appends)."""
import dod_gate

STUBS_MARKER = "superheroes:stubbed-seams"


def seed_dod_block(dod_bullets):
    """The DoD disposition-table skeleton (blank Disposition/Evidence per bullet), or "" when
    there are no bullets to seed."""
    if not dod_bullets:
        return ""
    lines = [
        "## Definition of done",
        "",
        "<!-- %s — one row per spec Definition-of-done bullet. Set Disposition to `done`"
        % dod_gate.TABLE_MARKER,
        "     (+ evidence: test name / quoted record / link) or `deferred` (+ a filed issue",
        "     `#NNN` and a one-line reason). mark-ready parks the run on any unaddressed bullet. -->",
        "",
        "| DoD bullet | Disposition | Evidence / deferral |",
        "| --- | --- | --- |",
    ]
    for b in dod_bullets:
        lines.append("| %s |  |  |" % dod_gate.cellsafe(b))
    return "\n".join(lines) + "\n"


def stubbed_seams_block(markers):
    """The generated "Stubbed seams" section from diff markers (see stub_markers.markers_in_diff),
    or "" when there are none (the section is omitted entirely on a stub-free PR)."""
    if not markers:
        return ""
    lines = [
        "## Stubbed seams",
        "",
        "<!-- %s — generated from STUB(#NNN) markers in this PR's diff. Do not edit by hand. -->"
        % STUBS_MARKER,
        "",
    ]
    for m in markers:
        desc = str(m.get("description") or "").strip() or "(no description)"
        lines.append("- `%s` — %s (#%s)" % (m.get("file", "?"), desc, m.get("issue")))
    return "\n".join(lines) + "\n"


def compose_body(base_body, dod_block, stubs_block):
    """Append whichever generated blocks are non-empty and not already present (by marker) to
    `base_body`. Idempotent: re-seeding a body that already carries a block is a no-op for it."""
    base = (base_body or "").rstrip()
    parts = [base] if base else []
    if dod_block and dod_gate.TABLE_MARKER not in base:
        parts.append(dod_block.rstrip())
    if stubs_block and STUBS_MARKER not in base:
        parts.append(stubs_block.rstrip())
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"
