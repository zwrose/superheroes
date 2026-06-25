# plugins/superheroes/lib/recover_entry.py
"""Leaf entry: Step-0 guards (enforcer armed + store lease, UFR-3), then ensure the store,
read checkpoint + a world snapshot, print recover.reconcile(...) as JSON. Gathers IO here so
recover stays pure."""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import control_plane
import checkpoint as ckpt_lib
import docload
import recover
import ref_lock

_HERE = os.path.dirname(os.path.abspath(__file__))


def _park(reason):
    print(json.dumps({"action": "park_gate", "reason": reason}))


def _read_pr(cp):
    """The world-read of the run's PR (reality wins). None = no PR; 'unknown' = transient read
    (reconcile GATEs, never creating a 2nd PR); else {number, state}."""
    branch = (cp or {}).get("branch")
    if not branch:
        return None
    try:
        r = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "all",
                            "--json", "number,state"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "unknown"                                 # a hung gh read -> transient (reconcile GATEs)
    if r.returncode != 0:
        return "unknown"
    try:
        arr = json.loads(r.stdout or "[]")
    except ValueError:
        return "unknown"
    return {"number": arr[0]["number"], "state": arr[0]["state"].lower()} if arr else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    args = ap.parse_args()
    cwd = os.getcwd()
    store = control_plane.ensure_store(cwd)
    if store is None:
        return _park("control-plane store unusable")
    # Step-0 guard A: the enforcer PreToolUse hook must be armed before any write.
    try:
        armed = subprocess.run([sys.executable, os.path.join(_HERE, "enforcer.py"), "selfcheck"],
                               capture_output=True, timeout=10).returncode == 0  # capture: its JSON must not pollute our stdout
    except subprocess.TimeoutExpired:
        armed = False                                       # a hung self-check -> fail closed
    if not armed:
        return _park("enforcer hook not armed — refusing to run (fail closed)")
    # Step-0 guard B: the §4.4 startup + work-item leases (UFR-3 — a live holder fails the 2nd run).
    if not ref_lock.acquire_startup(store)[0]:
        return _park("another run holds the per-checkout startup lock")
    ok, generation, reason = ref_lock.acquire(store, args.work_item)
    if not ok:
        return _park("work-item lease %s — another run is in progress (UFR-3)" % reason)
    paths = control_plane.paths(cwd, args.work_item)
    cp = ckpt_lib.read(paths["checkpoint"])
    # Back-half (a branch exists): recompute the content-hash so reconcile can detect a stale spec;
    # front-half (no branch yet): None is expected and the Task-5 guard skips that gate.
    # A missing/malformed tasks doc must NOT crash the leaf with no JSON (cmdRunner fails closed on
    # empty stdout) — leave chash None so reconcile GATEs cleanly ("could not recompute … transient").
    chash = None
    if cp and cp.get("branch"):
        try:
            chash = docload.content_hash_for(args.work_item, cwd)
        except (OSError, ValueError):
            chash = None
    world = {"store_ok": True, "current_content_hash": chash,
             "pr": _read_pr(cp), "seeded_empty": True}
    out = recover.reconcile(cp, world)
    out["generation"] = generation     # UFR-10: thread the entry generation to build_entry
    print(json.dumps(out))


if __name__ == "__main__":
    main()
