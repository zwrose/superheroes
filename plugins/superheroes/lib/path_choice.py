# plugins/superheroes/lib/path_choice.py
"""Advisory post-approval path choice (FR-1): does this approved work-item run on the
showrunner path or the manual bridged path? Recorded once at discovery's hand-off, it is
ADVISORY only — the run state is authoritative, so a never-started showrunner pick simply
re-enters via the showrunner skill (UFR-6/FR-7). Stored as `path-choice.json` under the
work-item's control-plane issue dir; an absent/unreadable record reads back as None.
"""
import json
import os

import control_plane


def _path(work_item, cwd, root):
    return os.path.join(control_plane.issue_dir(cwd, work_item, root), "path-choice.json")


def record(work_item, choice, cwd, root=None):
    """Write the advisory path choice for a work-item (atomic; creates the issue dir)."""
    control_plane.atomic_write(_path(work_item, cwd, root), json.dumps({"choice": choice}))


def read(work_item, cwd, root=None):
    """Return the recorded choice string, or None if absent/unreadable (tolerant)."""
    try:
        with open(_path(work_item, cwd, root), encoding="utf-8") as fh:
            return json.load(fh).get("choice")
    except (OSError, ValueError):
        return None
