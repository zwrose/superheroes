"""Bounded CI settle-poll for the ship phase (the live-run settle-poll deferred from #120,
owed since the 0.10.0 qualification found pending-as-red dispatching a no-op CI fixer).

Polls the PR's checks for the integrated head until nothing is pending (green, red, or
none — whatever it settles TO) or the budget runs out, then prints one JSON payload:

    {"settled": true|false, "waited_sec": N, "checks": [...]|{"error":...}|{"stale":...}}

The caller (the bundle's ship loop, via a dumb-pipe courier) feeds `checks` back into its
own classify/decide pass — this CLI never decides anything beyond "still pending?", so the
classification stays single-homed in ci_status (CONVENTIONS §11). A read error or stale
head ends the poll immediately (settled=false, payload passed through) — the ship loop's
existing error/stale handling owns those paths. Deterministic and journal-friendly: the
whole wait happens inside this one courier leaf.
"""
import argparse
import json
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import ci_status


def _read_checks_via_cli(work_item, worktree):
    """Shell ship_phase.py --emit-checks — the verified CLI interface the bundle already
    uses (ship_phase parses argv at import, so it is a script to shell, never a module to
    import; same pattern as preflight shelling definition_doc's CLI). Any transport
    failure maps to the loop-stopping {"error": ...} payload the ship loop already owns."""
    # --step ci + --emit-checks = ship_phase's IO-only raw-checks mode (the "ci" step is
    # the emit/read fall-through; "ship-readiness" would run fence/reconcile machinery).
    cmd = ["python3", os.path.join(_HERE, "ship_phase.py"),
           "--step", "ci", "--emit-checks", "--work-item", work_item]
    if worktree:
        cmd.extend(["--worktree", worktree])
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return json.loads((out.stdout or "").strip() or "null")
    except Exception:
        return {"error": "CI status could not be read"}


def settle(work_item, worktree, timeout_sec, interval_sec, *, _read=None, _sleep=None, _clock=None):
    """Poll until checks settle (no pending) or timeout. Pure-ish core for tests: the
    checks reader, sleeper, and clock are injectable."""
    read = _read or (lambda: _read_checks_via_cli(work_item, worktree))
    sleep = _sleep or time.sleep
    clock = _clock or time.monotonic
    start = clock()
    while True:
        checks = read()
        waited = clock() - start
        if not isinstance(checks, list):
            # {"error":...} / {"stale":...} — the ship loop owns these paths; stop polling.
            return {"settled": False, "waited_sec": round(waited, 1), "checks": checks}
        if ci_status.classify(checks)["status"] != "pending":
            return {"settled": True, "waited_sec": round(waited, 1), "checks": checks}
        if waited + interval_sec > timeout_sec:
            return {"settled": False, "waited_sec": round(waited, 1), "checks": checks}
        sleep(interval_sec)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--worktree", default=None)
    ap.add_argument("--timeout-sec", type=float, default=900.0,
                    help="total settle budget (default 15 min — CI on this repo runs ~2-3 min; "
                         "the ship loop parks honestly when the budget ends still-pending)")
    ap.add_argument("--interval-sec", type=float, default=20.0)
    a = ap.parse_args(argv)
    print(json.dumps(settle(a.work_item, a.worktree, a.timeout_sec, a.interval_sec)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
