#!/usr/bin/env python3
"""Map a unified diff to the RIGHT-side line numbers a finding may be anchored to.

`round_driver.mechanical_compile` uses this to drop findings that cite a line
outside the round diff's hunks (SKILL.md § Compile + Dedupe, step 2). It walks
`@@` hunk headers so a diff line number is never mistaken for a file line
number.

Deviations from the resolve-diff-lines.ts original this was ported from
(intentional): each diff line has a trailing '\\r' stripped so CRLF diffs don't
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
