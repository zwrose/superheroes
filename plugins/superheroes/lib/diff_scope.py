#!/usr/bin/env python3
"""Map a unified diff to the RIGHT-side line numbers a finding may be anchored to.

`round_driver.mechanical_compile` uses `parse_touched_lines` to route findings that cite a
line the PR did not touch to the review record's "Outside this PR" list (SKILL.md § Compile
+ Dedupe, step 2): the touched lines are the added lines plus the head line just before and
just after each run of deleted lines; context lines are not touched. `parse_diff_lines`
(added AND context lines) is kept for its other readers. Both walk `@@` hunk headers so a
diff line number is never mistaken for a file line number.

Provenance, quoted from the deleted module: this parser was carved out of
`lib/resolve_diff_lines.py` when that module was removed with `--post` (#1121),
and that module described itself as a port of a `resolve-diff-lines.ts` original.
That TypeScript file has never existed in this repository — it is upstream
history, not a path to look for here. Deviation from it that the port made
deliberately: each diff line has a trailing '\\r' stripped so CRLF diffs don't
leave '\\r' in filenames. Limitation: --no-prefix diffs ('+++ <path>' without
'b/') are NOT recognized; no line of such a file is anchorable.
"""
import re

_HUNK_NEWSTART = re.compile(r"\+(\d+)")


def parse_diff_lines(diff_text):
    """Map each RIGHT-side file path to the set of line numbers valid as anchors
    (added '+' lines and context ' ' lines)."""
    valid = {}
    current_file = None
    new_line = None
    in_hunk = False

    for raw in diff_text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw  # CRLF-safe
        if line.startswith("diff --git"):
            in_hunk = False
            current_file = None
        elif line.startswith("+++ b/"):
            current_file = line[6:]
            valid.setdefault(current_file, set())
            in_hunk = False
        elif line.startswith("+++ "):
            # +++ /dev/null or --no-prefix form — not a recognized RIGHT file.
            current_file = None
            in_hunk = False
        elif line.startswith("@@ "):
            m = _HUNK_NEWSTART.search(line)
            if m and current_file:
                new_line = int(m.group(1))
                in_hunk = True
            else:
                in_hunk = False
        elif in_hunk and current_file is not None and new_line is not None:
            if line.startswith("+"):
                valid[current_file].add(new_line)
                new_line += 1
            elif line.startswith("-"):
                pass  # deletion: does not advance the new-file counter
            elif line.startswith(" ") or line.startswith("\\"):
                if line.startswith(" "):
                    valid[current_file].add(new_line)
                    new_line += 1
            else:
                in_hunk = False
    return valid


def parse_touched_lines(diff_text):
    """Map each RIGHT-side file path to the set of head line numbers the PR touched: every
    added '+' line, plus, for each run of one or more deleted '-' lines, the head line just
    before the run (when the hunk has one) and the head line just after it (the line the
    new-file counter holds when the run ends — it may not exist in the file, which is
    harmless). Context ' ' lines are NOT touched. Same hunk walking, CRLF handling and
    '+++ b/' recognition as `parse_diff_lines`."""
    touched = {}
    current_file = None
    new_line = None
    in_hunk = False
    have_prev = False  # a head-side line (added or context) already seen in this hunk
    in_run = False  # inside a run of deleted lines

    def close_run():
        nonlocal in_run
        # axis: the head line just after a deletion run counts as touched — see bite-proof record c3_wo_a_outside
        if in_run and current_file is not None and new_line is not None:
            touched[current_file].add(new_line)
        in_run = False

    for raw in diff_text.split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw  # CRLF-safe
        if line.startswith("diff --git"):
            close_run()
            in_hunk = False
            current_file = None
        elif line.startswith("+++ b/"):
            close_run()
            current_file = line[6:]
            touched.setdefault(current_file, set())
            in_hunk = False
        elif line.startswith("+++ "):
            close_run()
            current_file = None
            in_hunk = False
        elif line.startswith("@@ "):
            close_run()
            m = _HUNK_NEWSTART.search(line)
            if m and current_file:
                new_line = int(m.group(1))
                in_hunk = True
                have_prev = False
            else:
                in_hunk = False
        elif in_hunk and current_file is not None and new_line is not None:
            if line.startswith("+"):
                close_run()
                touched[current_file].add(new_line)
                new_line += 1
                have_prev = True
            elif line.startswith("-"):
                if not in_run:
                    in_run = True
                    # axis: the head line just before a deletion run counts as touched, only when the hunk has one — see bite-proof record c3_wo_a_outside
                    if have_prev:
                        touched[current_file].add(new_line - 1)
            elif line.startswith("\\"):
                pass  # "\ No newline at end of file" belongs to the line above; it ends nothing
            elif line.startswith(" "):
                # axis: a context line is never touched, only the line just after a deletion run is (close_run) — see bite-proof record c3_wo_a_outside
                close_run()
                new_line += 1
                have_prev = True
            else:
                close_run()
                in_hunk = False
    close_run()
    return touched
