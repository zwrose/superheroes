"""Deterministic DoD disposition splice (issue #228's fill leg; PR #251 review batch).

The mark-ready filler MODEL leaf only PROPOSES dispositions (JSON rows). This CLI holds
the pen: it splices the Disposition/Evidence cells of MATCHING table rows in place and
touches no other byte of the PR body — closing the review-panel findings against a model
rewriting the whole body at a certification boundary (truncation of the stubbed-seams
disclosure, minutes-wide read-modify-write clobber window, unbounded fabrication surface):

  - Only lines inside the TABLE_MARKER-anchored table change; everything else is spliced
    back byte-identical by construction (asserted, plus a STUBS_MARKER presence check).
  - Row matching reuses dod_gate's own cellsafe/_norm equality — the single home of the
    matching rule (CONVENTIONS §11) — so a proposal for an unknown bullet is REJECTED,
    never appended.
  - Mechanical honesty checks convert the two cheapest fabrication shapes into parks:
    a `deferred` row's #NNN must be a real, fetchable issue (gh issue view), and a
    path-shaped `done` evidence pointer must exist under --root. Rows failing any check
    are rejected (left blank) and the fail-closed gate parks with its usual reason.
  - Read-back: after `gh pr edit`, the body is re-fetched and every spliced row verified
    present; an unconfirmed write reports ok=false (the caller skips the gate re-run).

Output: {"ok": bool, "filled": n, "rejected": [{"bullet","reason"}...], "reason"?}
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dod_gate
import pr_body as pr_body_lib

_PATHISH = re.compile(r"^[\w./-]+$")


def _gh(args, timeout=30):
    try:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=timeout)
        return out.returncode, out.stdout
    except Exception:
        return 1, ""


def _issue_exists(num):
    rc, _ = _gh(["issue", "view", str(num), "--json", "state"])
    return rc == 0


def _validate(proposal, root, *, _issue_exists=_issue_exists):
    disp = str(proposal.get("disposition") or "").strip().lower()
    detail = str(proposal.get("detail") or "").strip()
    if disp not in ("done", "deferred"):
        return "disposition must be done or deferred"
    if not detail:
        return "empty detail"
    if disp == "deferred":
        m = re.search(r"#([1-9]\d*)", detail)
        if not m:
            return "deferred without a filed issue (#NNN)"
        if not _issue_exists(m.group(1)):
            return "deferred issue #%s does not resolve on GitHub" % m.group(1)
    if disp == "done" and _PATHISH.match(detail) and "/" in detail:
        # a path-shaped evidence pointer must actually exist (mechanical anti-fabrication)
        if not os.path.exists(os.path.join(root, detail)):
            return "path-shaped evidence %r does not exist under the root" % detail
    return None


def _table_data_line_indexes(lines):
    """Indexes of the table's DATA rows (marker-anchored, mirrors dod_gate._parse_table's
    walk — header and separator excluded)."""
    idx = next((i for i, l in enumerate(lines) if dod_gate.TABLE_MARKER in l), None)
    if idx is None:
        return []
    out, started, seen_rows = [], False, 0
    for i in range(idx + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("|"):
            started = True
            cells = dod_gate._split_row(lines[i])
            seen_rows += 1
            if seen_rows == 1 or dod_gate._is_separator(cells):
                continue
            out.append(i)
        elif s.startswith("#"):
            break
        elif started and s == "":
            continue
        elif started:
            break
    return out


def fill(body, proposals, root, *, _issue_exists=_issue_exists):
    """Pure splice: (new_body, filled, rejected, changed_line_texts). Never touches a byte
    outside matching data rows; unknown bullets and invalid proposals are rejected.

    One deliberate exception to equality-only matching (#422 mixed-version healing): a
    proposal that exact-matches no row may rewrite exactly ONE still-blank row whose cell
    is a word-boundary strict prefix of the proposal — the shape a pre-fold spine's seeded
    table leaves behind for a wrapped bullet. Guards: blank disposition only (no recorded
    data can be lost), unique candidate only, and the healed identity still has to satisfy
    dod_gate.decide's exact match against the freshly parsed spec — a bad heal parks."""
    lines = str(body).split("\n")
    data_idx = _table_data_line_indexes(lines)
    rejected, changed = [], []
    filled = 0
    for prop in proposals or []:
        bullet = str(prop.get("bullet") or "")
        why = _validate(prop, root, _issue_exists=_issue_exists)
        if why:
            rejected.append({"bullet": bullet, "reason": why})
            continue
        target = dod_gate._norm(dod_gate.cellsafe(bullet))
        hit = None
        for i in data_idx:
            cells = dod_gate._split_row(lines[i])
            if cells and dod_gate._norm(cells[0]) == target:
                hit = (i, cells)
                break
        if hit is None:
            # #422 mixed-version healing: a table seeded by a pre-fold spine carries a bullet
            # cell TRUNCATED at the wrapped bullet's first physical line, which can never
            # exact-match the full folded text — without this, such a run parks at mark-ready
            # forever (re-seeding is marker-idempotent; nothing else rewrites a bullet cell).
            # Heal the one provably-safe case: exactly ONE still-BLANK row (placeholder
            # disposition, so no recorded data can be lost) whose cell is a strict prefix of
            # the proposed bullet — rewrite that row's bullet cell along with its disposition.
            # Ambiguity (two prefix candidates) or any non-blank candidate stays a rejection.
            candidates = []
            for i in data_idx:
                cells = dod_gate._split_row(lines[i])
                if not cells or len(cells) < 2:
                    continue
                cell_norm = dod_gate._norm(cells[0])
                disposition_blank = dod_gate._norm(cells[1]) in dod_gate._PLACEHOLDERS
                # word-boundary prefix only: a real pre-fold truncation ends at a physical
                # line break, so the folded text is exactly `cell + ' ' + rest` — mid-word
                # extensions (the forgery shape both reviewers flagged) never qualify.
                if disposition_blank and cell_norm and target.startswith(cell_norm + " "):
                    candidates.append((i, cells))
            if len(candidates) == 1:
                i, cells = candidates[0]
                cells = [dod_gate.cellsafe(bullet)] + list(cells[1:])
                hit = (i, cells)
        if hit is None:
            rejected.append({"bullet": bullet, "reason": "no matching table row for this bullet"})
            continue
        i, cells = hit
        new_line = "| %s | %s | %s |" % (
            cells[0],
            dod_gate.cellsafe(str(prop["disposition"]).strip().lower()),
            dod_gate.cellsafe(str(prop["detail"]).strip()),
        )
        if lines[i] != new_line:
            lines[i] = new_line
            changed.append(new_line)
        filled += 1
    new_body = "\n".join(lines)
    # Belt-and-braces invariants: nothing outside the table moved.
    assert (pr_body_lib.STUBS_MARKER in new_body) == (pr_body_lib.STUBS_MARKER in str(body))
    assert len(new_body.split("\n")) == len(str(body).split("\n"))
    return new_body, filled, rejected, changed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pr", required=True)
    ap.add_argument("--rows", required=True, help="JSON file: [{bullet, disposition, detail}...]")
    ap.add_argument("--root", default=".")
    a = ap.parse_args(argv)
    try:
        proposals = json.load(open(a.rows, encoding="utf-8"))
    except Exception as e:
        print(json.dumps({"ok": False, "reason": "rows file unreadable: %s" % e})); return 0
    rc, body = _gh(["pr", "view", str(a.pr), "--json", "body", "-q", ".body"])
    if rc != 0 or not body.strip():
        print(json.dumps({"ok": False, "reason": "PR body unreadable"})); return 0
    body = body.rstrip("\n")
    root = os.path.realpath(a.root)
    new_body, filled, rejected, changed = fill(body, proposals, root)
    if filled == 0:
        print(json.dumps({"ok": False, "filled": 0, "rejected": rejected,
                          "reason": "no valid proposal matched a table row"})); return 0
    if new_body != body:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(new_body)
            tmp = fh.name
        rc, _ = _gh(["pr", "edit", str(a.pr), "--body-file", tmp], timeout=60)
        os.unlink(tmp)
        if rc != 0:
            print(json.dumps({"ok": False, "filled": 0, "rejected": rejected,
                              "reason": "gh pr edit failed"})); return 0
    # Read-back: every spliced row must be present in the live body.
    rc, after = _gh(["pr", "view", str(a.pr), "--json", "body", "-q", ".body"])
    if rc != 0 or any(line not in after for line in changed):
        print(json.dumps({"ok": False, "filled": 0, "rejected": rejected,
                          "reason": "read-back could not confirm the spliced rows"})); return 0
    print(json.dumps({"ok": True, "filled": filled, "rejected": rejected}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
