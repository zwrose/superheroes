# plugins/superheroes/lib/dod_gate.py
"""Ship-phase Definition-of-done disposition gate (issue #228).

A PURE decider (house style: `decide()` over dicts/lists, fail-closed on malformed
input — mirrors `ship_gate.decide` / `recover.pr_action`). It verifies that the PR
body carries a **DoD disposition table** with one row per spec Definition-of-done
bullet, each row marked either:

  - `done`     — with a non-placeholder evidence pointer (test name / quoted record / link), or
  - `deferred` — with a filed issue number (`#NNN`) AND a one-line reason.

Any bullet with no row, or a row with neither evidence nor an issue number, is a
`park` verdict naming the unaddressed bullet — it NEVER flips the PR ready. The gate
checks *presence and shape* of the claims, not their quality (a weak evidence pointer
passes): it converts a silent omission into a visible claim the owner judges at review.

Fail-closed anchoring (issue #228): a spec-driven run with a missing/empty DoD section
parks (never silently skips). A spec-less run (the #25 quick route: a tasks doc with a
null parent, no spec) returns `not-applicable` so the caller can skip the gate.
"""
import re

# The spec's Definition-of-done heading — the template writes "## Definition of done / success"
# (CONVENTIONS §3.2). Anchor on the leading phrase, tolerant of the "/ success" suffix and the
# heading level, so a reworded suffix does not read as "no DoD section" (which would park).
_DOD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+definition of done\b", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
# Top-level markdown list items only (column 0) — nested sub-bullets do not inflate the count.
_LIST_ITEM = re.compile(r"^([-*]|\d+\.)\s+(.*)")

# The machine-anchor for the disposition table in the PR body (seeded at draft-PR time by
# pr_body.seed_dod_block). Anchoring on this marker, not on prose, keeps the parse robust.
TABLE_MARKER = "superheroes:dod-table"

_PLACEHOLDERS = {"", "-", "—", "–", "tbd", "todo", "n/a", "na", "none", "…", "..."}


def cellsafe(text):
    """Collapse a bullet to a single safe table cell: no raw pipes (they break the row),
    whitespace collapsed. The SAME transform is applied when seeding the table and when
    matching a bullet to its row, so the two sides always agree."""
    return re.sub(r"\s+", " ", str(text).replace("|", "/")).strip()


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def parse_dod_bullets(spec_text):
    """Extract the Definition-of-done bullets from a spec's raw text.

    Returns the list of bullet strings under the DoD heading. A section with top-level
    list items yields one entry per item; a prose-only section collapses to a single
    bullet (still one disposable row). Returns None when the heading is absent, and []
    when the section is present but empty — the caller parks on either (fail-closed).
    """
    if spec_text is None:
        return None
    lines = str(spec_text).split("\n")
    start = None
    for i, ln in enumerate(lines):
        if _DOD_HEADING.match(ln):
            start = i + 1
            break
    if start is None:
        return None
    bullets, prose = [], []
    for ln in lines[start:]:
        if _HEADING.match(ln):
            break
        m = _LIST_ITEM.match(ln)
        if m:
            bullets.append(m.group(2).strip())
        elif ln.strip():
            prose.append(ln.strip())
    if bullets:
        return bullets
    if prose:
        return [" ".join(prose)]
    return []


def _split_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator(cells):
    return all((not c) or set(c) <= set("-:") for c in cells)


def _parse_table(pr_body):
    """Parse the disposition table that follows the TABLE_MARKER into a list of data rows
    (each a list of cells). Returns None when the marker or a table is absent."""
    if not pr_body or TABLE_MARKER not in pr_body:
        return None
    lines = str(pr_body).split("\n")
    idx = next(i for i, l in enumerate(lines) if TABLE_MARKER in l)
    table_lines, started = [], False
    for ln in lines[idx + 1:]:
        s = ln.strip()
        if s.startswith("|"):
            started = True
            table_lines.append(ln)
        elif s.startswith("#"):
            break                      # a heading ends the section (and the table)
        elif started and s == "":
            continue                   # tolerate a blank line between rows (don't truncate)
        elif started:
            break                      # other prose after the table ends it
        # else: blank/comment lines before the table starts -> keep scanning
    if not table_lines:
        return None
    rows = []
    for i, tl in enumerate(table_lines):
        cells = _split_row(tl)
        if i == 0:
            continue  # header row
        if _is_separator(cells):
            continue  # the |---|---| divider
        rows.append(cells)
    return rows


def _match_row(bullet, rows):
    """Find the disposition row whose bullet cell EQUALS this bullet (both cellsafe-normalized).
    Exact match, not prefix: a prefix match would bind a bullet to a sibling row whose text merely
    starts with it (e.g. 'Ship it' vs 'Ship it end to end'), reading the wrong disposition. The
    seed writes the bullet cell verbatim and the fill legs edit only Disposition/Evidence, so equality
    holds. An empty bullet (a bare `- ` in the spec) matches nothing -> the caller parks (fail-closed)."""
    target = _norm(cellsafe(bullet))
    if not target:
        return None
    for r in rows:
        if r and _norm(r[0]) == target:
            return r
    return None


def _row_ok(row):
    """(ok, why): is this disposition row validly marked? done needs an evidence pointer;
    deferred needs a filed issue (#NNN) AND a one-line reason beyond the issue ref."""
    disp = _norm(row[1]) if len(row) > 1 else ""
    detail = row[2].strip() if len(row) > 2 else ""
    if disp.startswith("done"):
        if _norm(detail) in _PLACEHOLDERS or detail.startswith("<"):
            return False, "marked done but no evidence pointer"
        return True, ""
    if disp.startswith("deferred"):
        if not re.search(r"#[1-9]\d*", detail):   # GitHub issues start at 1; `#0` is not a ref
            return False, "marked deferred but no filed issue (#NNN)"
        reason = re.sub(r"#[1-9]\d*", "", detail).strip(" -–—,.;:")
        if not reason:
            return False, "marked deferred with an issue but no reason"
        return True, ""
    return False, "no disposition (expected done or deferred)"


def _short(text, n=90):
    t = re.sub(r"\s+", " ", str(text)).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def decide(dod_bullets, pr_body, *, spec_present):
    """Pure DoD-disposition decision. Returns {"verdict", "reason"}.

    verdict ∈ {"proceed", "park", "not-applicable"}:
      - not-applicable: no spec doc (the #25 quick route) — caller skips the gate.
      - park: fail-closed — spec present but the DoD section is missing/empty, the PR body
        has no disposition table, or some bullet is unaddressed (reason names it).
      - proceed: every bullet is disposed (done+evidence or deferred+issue).
    """
    if not spec_present:
        return {"verdict": "not-applicable",
                "reason": "no spec doc (quick route) — DoD disposition gate not applicable"}
    if not dod_bullets:
        return {"verdict": "park",
                "reason": "spec Definition-of-done section missing or empty — "
                          "cannot verify disposition (fail-closed)"}
    rows = _parse_table(pr_body)
    if rows is None:
        return {"verdict": "park",
                "reason": "PR body has no DoD disposition table (%s) — "
                          "every Definition-of-done bullet must be disposed before ready"
                          % TABLE_MARKER}
    for bullet in dod_bullets:
        row = _match_row(bullet, rows)
        if row is None:
            return {"verdict": "park",
                    "reason": "Definition-of-done bullet has no disposition row: %s" % _short(bullet)}
        ok, why = _row_ok(row)
        if not ok:
            return {"verdict": "park",
                    "reason": "Definition-of-done bullet %s — %s" % (_short(bullet), why)}
    return {"verdict": "proceed",
            "reason": "every Definition-of-done bullet is disposed (done+evidence or deferred+issue)"}
