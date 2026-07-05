# plugins/superheroes/lib/stub_markers.py
"""No-silent-stubs marker convention + parsing (issue #228).

A deliberately-unwired seam (a placeholder function, or a hardcoded default standing in
for a real source) must carry a machine-findable marker on/above it:

    # STUB(#NNN): <one-line description of what is unwired and the live effect>

The issue number is MANDATORY — a stub without a tracked follow-up is a violation. This
module is the single source of truth for finding markers; three callers share it:

  - `validate_stubs.py` (CI): fails on any stub marker whose parenthesised content is not a
    bare issue reference — see `find_violations`.
  - the draft-PR seam (pr_entry): greps the PR *diff* for valid markers to generate the
    "Stubbed seams" PR-body section — see `markers_in_diff`.
  - tests.

The literal token `#NNN` is RESERVED as the documentation placeholder (as shown above): it
is neither a valid marker nor a violation, so this module and the docs can spell the
convention out without tripping the CI validator over their own example.

It intentionally does NOT detect *unmarked* stubs (that is issue-3/issue-4 territory) —
only markers that are present but malformed.
"""
import re

# The STUB marker: capture ONLY the parenthesised content. The description is sliced out
# separately (see _markers_on_line) so a greedy tail can't swallow a SECOND marker on the same
# line — two markers on one line must both be seen (else a malformed one escapes the validator).
_STUB_RE = re.compile(r"STUB\(([^)\n]*)\)")
# A well-formed marker's parenthesised content is exactly one issue reference: `#123`. GitHub
# issue numbers start at 1, so `#0` is not a valid reference.
_ISSUE_RE = re.compile(r"^#([1-9]\d*)$")
# The reserved documentation placeholder (see module docstring) — exempt from violations.
_PLACEHOLDER = "#NNN"


def _markers_on_line(line):
    """Yield (match, inner, description) for every STUB marker on `line`. The description runs from
    the marker's close paren to the NEXT marker (or end of line), with a leading `:`/space trimmed —
    so two markers on one line are both surfaced, neither folded into the other's description."""
    matches = list(_STUB_RE.finditer(line))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        desc = re.sub(r"^\s*:?[ \t]*", "", line[m.end():end]).strip()
        yield m, m.group(1).strip(), desc


def find_markers(text):
    """Every WELL-FORMED marker in `text`: [{"issue": int, "description": str, "line": int}].
    Malformed markers (parens not holding a bare #NNN) are ignored here — see find_violations."""
    out = []
    for lineno, line in enumerate(str(text or "").split("\n"), start=1):
        for _m, inner, desc in _markers_on_line(line):
            iss = _ISSUE_RE.match(inner)
            if iss:
                out.append({"issue": int(iss.group(1)), "description": desc, "line": lineno})
    return out


def find_violations(text):
    """Every MALFORMED marker: [{"line": int, "marker": str, "reason": str}]. A marker is
    malformed when the parens do not hold exactly a `#NNN` issue reference."""
    out = []
    for lineno, line in enumerate(str(text or "").split("\n"), start=1):
        for m, inner, _desc in _markers_on_line(line):
            if _ISSUE_RE.match(inner) or inner == _PLACEHOLDER:
                continue
            reason = ("STUB marker has no issue reference — the parens need a real #<issue>"
                      if not inner else
                      "STUB marker issue reference is malformed (expected a bare #<issue>): %r" % inner)
            out.append({"line": lineno, "marker": m.group(0).strip(), "reason": reason})
    return out


def markers_in_diff(diff_text):
    """Well-formed markers on ADDED lines of a unified diff:
    [{"file": str, "issue": int, "description": str}], in diff order.

    Only `+` lines (not `+++` headers) are considered, so a marker already present on an
    unchanged line does not resurface. `file` is the post-image path from the `+++ b/...`
    header (fail-safe to "?" if a hunk has no readable header)."""
    out = []
    cur = "?"
    for line in str(diff_text or "").split("\n"):
        if line.startswith("+++ "):
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            cur = path if path and path != "/dev/null" else "?"
            continue
        if line.startswith("+++") or not line.startswith("+"):
            continue
        for m in find_markers(line[1:]):
            out.append({"file": cur, "issue": m["issue"], "description": m["description"]})
    return out
