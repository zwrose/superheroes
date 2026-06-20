# plugins/superheroes/lib/recover.py
"""reconcile-on-entry: (checkpoint, world) -> the safe next action. Pure decision
logic (the reset.plan_reset / ci_loop.decide pattern); the orchestrator skill gathers
the world reads and sequences the result. Reality wins; the checkpoint only speeds a
resume, never authorizes an action (design §2, §5).

`world` values may be the string "unknown" to mean 'could not determine' — the
transient-read rule turns those into GATEs, never into 'absent' (which under
auto-continue would re-do a mutating step).
"""

_UNKNOWN = "unknown"


def _branch_hash(branch):
    """The trailing <content-hash> of superheroes/<work-item>-<hash> (§6.3)."""
    if not isinstance(branch, str) or "-" not in branch:
        return None
    return branch.rsplit("-", 1)[1]


def reconcile(checkpoint, world):
    world = world or {}

    # (a) control-plane store wedged / lock unobtainable -> FAIL CLOSED, never lockless
    #     (design §2; premortem-201 — the lock lives in the store).
    if world.get("store_ok") is False:
        return {"action": "park_gate",
                "reason": "control-plane store unusable — fail closed (no lockless run)"}

    # (b) no durable record (or it failed closed on a bad schema) -> world-derive
    if not checkpoint:
        return {"action": "world_derive", "reason": "no checkpoint — re-derive from reality"}

    # (c) stale-spec cascade (§6.3): the approved tasks changed under the in-flight branch.
    cur = world.get("current_content_hash")
    if cur is None:
        return {"action": "gate",
                "reason": "could not recompute the tasks content-hash (transient) — not resuming blind"}
    bh = _branch_hash(checkpoint.get("branch"))
    if bh is not None and bh != cur:
        return {"action": "gate",
                "reason": "approved tasks changed since this run started (stale spec)"}

    # (d) the owner ended the work by merging.
    pr = world.get("pr")
    if isinstance(pr, dict) and pr.get("state") == "merged":
        return {"action": "gate",
                "reason": "PR already merged — the work is done (merge is the owner's)"}

    # (e) transient-read rule: a read we'd act on that we could not determine -> GATE.
    if pr == _UNKNOWN:
        return {"action": "gate",
                "reason": "could not read PR state (transient) — not creating a second PR"}
    if world.get("seeded_empty") == _UNKNOWN:
        return {"action": "gate",
                "reason": "could not read seeded state (transient) — cannot confirm a clean baseline"}

    # (f) safe to auto-continue from the recorded cursor.
    return {"action": "continue", "from_step": checkpoint.get("lastGoodStep"),
            "reason": "reconciled — resume"}


# --- step 3 idempotency + step 0 floor-re-arm decisions as PURE CODE (not SKILL prose), so they
#     are deterministically testable (plan red-team test-001/test-002). ---

def pr_action(world):
    """The step 3 world-read-before-write decision: 'adopt' an existing open PR (one with a
    real number), 'gate' a merged / unreadable / malformed read, else 'create'. The
    exactly-once anchor, as code."""
    pr = (world or {}).get("pr")
    if pr == _UNKNOWN:
        return "gate"          # transient read -> never create a second PR
    if isinstance(pr, dict):
        if not pr.get("number"):
            return "gate"      # malformed/empty PR read -> don't guess (anomalous)
        return "gate" if pr.get("state") == "merged" else "adopt"
    if pr is not None:
        return "gate"          # unexpected type/value -> don't guess (fail-closed)
    return "create"            # pr is None -> no PR exists -> create exactly one


FLOOR_RETRY_MAX = 3


def rearm_action(attempt, armed, *, max_retry=FLOOR_RETRY_MAX):
    """The step 0 floor re-arm disposition (design §5 step 3): armed -> 'proceed'; a
    transient miss -> 'retry' while attempt < max_retry (attempts 1..max_retry-1 retry),
    then the max_retry-th attempt -> 'park_gate' (fail-closed, visible — never resume
    unguarded, never silent-wedge). `attempt` is 1-based (max_retry=3 → 2 retries then park)."""
    if armed:
        return "proceed"
    if attempt < max_retry:
        return "retry"
    return "park_gate"
