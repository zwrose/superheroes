#!/usr/bin/env python3
"""PreCompact hook (best-effort, non-fatal). Refresh resume-brief.md from the on-disk
checkpoint + events at the compaction boundary, so the post-compact session reads
current state. Never raises out — a failure falls back to the cold reconcile (design
§7). Reads {cwd} from the hook payload."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))


def main():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    cwd = payload.get("cwd") or os.getcwd()
    # Wipe any pending owner-approval allowance (issue #14): no approval may survive a
    # context compaction — a post-compact agent has no inherited "approved" state and
    # must re-ask. Best-effort, never fatal.
    try:
        import allowance
        allowance.clear_all(cwd)   # scope to THIS checkout — don't revoke a concurrent loop's approval
    except Exception as exc:
        sys.stderr.write("workhorse precompact: allowance wipe skipped (%s)\n" % exc)
    try:
        import control_plane
        import checkpoint as ck
        import journal
        import ref_lock
        # #170: the active work item(s) come from the common-dir store's live leases (the retired
        # current.json is gone). Refresh each live run's brief — under two parallel runs sharing
        # the clone's store, both get an up-to-date brief; with none, this is a no-op.
        for wi in ref_lock.active_work_items(control_plane.checkout_dir(cwd)):
            p = control_plane.paths(cwd, wi)
            c = ck.read(p["checkpoint"])
            if c is None:
                continue
            journal.render_brief(p["resume_brief"], c, {}, p["events"], root=cwd)
    except Exception as exc:
        # Best-effort + non-fatal (always exit 0 — a crashing hook must not fail the
        # session; the cold reconcile is the fallback). But emit a one-line stderr
        # breadcrumb so a silently-stale brief is at least diagnosable in the hook log.
        sys.stderr.write("workhorse precompact: brief refresh skipped (%s)\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
