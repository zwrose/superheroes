# plugins/superheroes/lib/recover_entry.py
"""Leaf entry: Step-0 guards (enforcer armed + the §4.4 work-item lease, UFR-3), then ensure
the store, read checkpoint + a world snapshot, print recover.reconcile(...) as JSON. Gathers
IO here so recover stays pure. (The per-work-item lease is the sole mutex; the old §4.5
per-checkout startup.lock was removed in #170 — it never serialized anything.)"""
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
# checkpoint.py is the single source of truth for the phase list (§4.3); don't redefine it.
CURRENT_PHASES = ckpt_lib.CURRENT_PHASES


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
        if not arr:
            return None
        return {"number": arr[0]["number"], "state": arr[0]["state"].lower()}
    except (ValueError, KeyError, IndexError, TypeError):
        return "unknown"   # a 0-exit non-array / malformed payload -> transient (reconcile GATEs)


def _phase_cursor_guard(cp, phases=None):
    phases = phases or CURRENT_PHASES
    if not cp:
        return None
    if cp.get("_incompatible"):
        return {"action": "park_gate",
                "reason": "checkpoint incompatible — %s" % cp.get("reason", "unknown reason")}
    step = cp.get("lastGoodStep")
    phase = cp.get("lastGoodPhase")
    if step is None:
        if phase is None:
            return None
        return {"action": "park_gate",
                "reason": "checkpoint lastGoodPhase is set but lastGoodStep is empty"}
    try:
        idx = int(step)
    except (TypeError, ValueError):
        return {"action": "park_gate",
                "reason": "checkpoint lastGoodStep is not numeric"}
    if idx < 0 or idx >= len(phases):
        return {"action": "park_gate",
                "reason": "checkpoint lastGoodStep %s is outside the current phase list" % step}
    expected = phases[idx]
    if phase != expected:
        return {"action": "park_gate",
                "reason": "checkpoint lastGoodPhase %r does not match current phase[%s] %r" %
                          (phase, idx, expected)}
    return None


def _checkout_root(cwd, root_arg):
    if root_arg:
        return os.path.realpath(root_arg)
    return os.path.realpath(cwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--root", default=None,
                    help="checkout root the store is keyed to; default cwd at invoke time")
    ap.add_argument("--snapshot", action="store_true",
                    help="Return {checkpoint, world, generation, early_park?} without calling reconcile; "
                         "the JS twin calls recover.reconcile() in-process (#115 Task 12).")
    args = ap.parse_args()
    cwd = os.getcwd()
    checkout_root = _checkout_root(cwd, args.root)
    store = control_plane.ensure_store(checkout_root)
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
    # Step-0 guard B: the §4.4 work-item lease (UFR-3 — a live holder fails the 2nd run). This
    # is the sole mutex; because the store is common-dir keyed, the lease is visible from every
    # worktree of the clone, so a duplicate launch of the same work item is refused wherever it
    # was launched from.
    ok, generation, reason = ref_lock.acquire(store, args.work_item)
    if not ok:
        return _park("work-item lease %s — another run is in progress (UFR-3)" % reason)
    paths = control_plane.paths(checkout_root, args.work_item)
    cp = ckpt_lib.read(paths["checkpoint"])
    cursor_gate = _phase_cursor_guard(cp)
    if cursor_gate:
        cursor_gate["generation"] = generation
        cursor_gate["root"] = checkout_root
        print(json.dumps(cursor_gate))
        return
    # Back-half (a branch exists): recompute the content-hash so reconcile can detect a stale spec;
    # front-half (no branch yet): None is expected and the Task-5 guard skips that gate.
    # A missing/malformed tasks doc must NOT crash the leaf with no JSON (cmdRunner fails closed on
    # empty stdout) — leave chash None so reconcile GATEs cleanly ("could not recompute … transient").
    chash = None
    if cp and cp.get("branch"):
        try:
            chash = docload.content_hash_for(args.work_item, checkout_root)
        except (OSError, ValueError):
            chash = None
    world = {"store_ok": True, "current_content_hash": chash,
             "pr": _read_pr(cp), "seeded_empty": True}
    if args.snapshot:
        # #115 Task 12: return the raw snapshot so the JS spine can call recover.reconcile() in-process
        # via the JS twin. The cursor_gate check (phase-list guard) already ran above and returned early
        # if it triggered, so reaching here means the checkpoint is cursor-safe.
        print(json.dumps({"checkpoint": cp, "world": world, "generation": generation,
                          "root": checkout_root}))
        return
    out = recover.reconcile(cp, world)
    out["generation"] = generation     # UFR-10: thread the entry generation to build_entry
    out["root"] = checkout_root
    print(json.dumps(out))


if __name__ == "__main__":
    main()
