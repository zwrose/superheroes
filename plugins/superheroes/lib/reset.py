"""step 6 Reset orchestration: drive test-pilot's engine.py clean + verify empty, with
the held-lock decision (unlock-or-GATE). Workhorse never re-implements teardown
and never auto-passes --allow-protected — the protected-target gate is the
engine's, and --allow-protected is the owner's call. Pure decision logic here;
the orchestrator skill (Task 13) sequences the actual engine subprocess calls.
"""
import json
import subprocess
import sys


def engine_json(engine, args, cwd=None):
    """Run test-pilot's engine.py with --json; return (returncode, parsed|None).
    A hung engine times out -> (124, None) -> plan_reset GATEs (fail-closed)."""
    try:
        p = subprocess.run([sys.executable, engine, *args, "--json"],
                           capture_output=True, text=True, cwd=cwd, timeout=30)
    except subprocess.TimeoutExpired:
        return (124, None)
    try:
        return p.returncode, json.loads(p.stdout.strip())
    except (ValueError, json.JSONDecodeError):
        return p.returncode, None


def plan_reset(status_obj):
    """Decide the reset action from an engine `status` result.
    ('clean' | 'unlock_then_clean' | 'gate', reason). Fail-CLOSED to gate on an
    unreadable status or a live (non-stale) held lock — never claim a clean
    baseline that wasn't achieved."""
    if not isinstance(status_obj, dict):
        return ("gate", "unreadable engine status (fail-closed)")
    lock = status_obj.get("lock")
    if lock and status_obj.get("lockStale") is True:
        return ("unlock_then_clean", "stale lock holder — reclaim then clean")
    if lock and status_obj.get("lockStale") is not True:
        return ("gate", "engine lock held by a live holder — cannot guarantee a clean baseline")
    return ("clean", "no lock — clean directly")


def verify_empty(status_obj):
    """True iff the engine has no seeded entries left (world-observable baseline)."""
    return isinstance(status_obj, dict) and not status_obj.get("entries")
