#!/usr/bin/env python3
"""SessionStart hook (best-effort, non-fatal). On source=='compact', inject context
telling the resumed orchestrator to RECONCILE + RE-ARM THE FLOOR before continuing,
and where the resume brief is. The actual reconcile / floor re-arm is the
orchestrator's job (recover.py + SKILL ⓪) — this only surfaces the instruction.
Always exits 0."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if payload.get("source") != "compact":
        return 0                      # only the post-compaction case
    cwd = payload.get("cwd") or os.getcwd()
    try:
        import control_plane
        wi = control_plane.get_current(cwd)
        if not wi:
            return 0
        brief = control_plane.paths(cwd, wi)["resume_brief"]
        ctx = ("Workhorse resume: this session was compacted mid-run on work-item "
               "'%s'. Before continuing, RECONCILE against reality and RE-ARM the ⓪ "
               "enforcer floor self-check (bounded retry → parked-GATE). Resume brief: %s"
               % (wi, brief))
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart",
                                   "additionalContext": ctx}}) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
