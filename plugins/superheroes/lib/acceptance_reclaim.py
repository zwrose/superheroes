"""Reclaim decider for the acceptance harness (UFR-4 / UFR-8).

Pure `decide(recorded_state, liveness)` over plain injected facts: judges whether a fresh
harness invocation may proceed when a prior run is recorded as in-flight. It NEVER probes
liveness itself — the caller confirms it and injects the result.

Contract:
  - No recorded run in flight → `proceed` (nothing to arbitrate).
  - A recorded run in flight, prior confirmed ALIVE → `refuse` (UFR-4: never trample a
    live run). The refusal creates nothing.
  - A recorded run in flight, liveness UNCONFIRMABLE → `refuse` (fail-closed, treated as
    UFR-4: an unconfirmable prior run is assumed alive).
  - A recorded run in flight, prior confirmed DEAD → `reclaim` then proceed (UFR-8), writing
    an orphan record ONLY when the dead run left none (`has_record` is false), so the death
    is still accounted for exactly once.

Mirrors `preflight.decide` / `acceptance_ceiling.decide` / `acceptance_retry.classify`
(pure, no I/O; every fact injected). Never raises.
"""


def decide(recorded_state, liveness):
    """Pure reclaim judgment over the injected facts.

    `recorded_state` is `{"in_flight": bool, "stamp": str|None, "has_record": bool}` and
    `liveness` is `"alive"|"dead"|"unconfirmable"`.

    Returns `{"action": "proceed"|"reclaim"|"refuse", "class": str, "reason": str,
    "write_orphan_record": bool}`.
    """
    if not isinstance(recorded_state, dict):
        recorded_state = {}

    # No recorded run in flight — nothing to arbitrate.
    if not recorded_state.get("in_flight"):
        return {
            "action": "proceed",
            "class": "no-in-flight-run",
            "reason": "no recorded run is in flight; proceed",
            "write_orphan_record": False,
        }

    stamp = recorded_state.get("stamp")

    # UFR-8: confirmed death — reclaim then proceed. Write an orphan record only when the
    # dead run left none, so the death is accounted for exactly once.
    if liveness == "dead":
        has_record = bool(recorded_state.get("has_record"))
        return {
            "action": "reclaim",
            "class": "confirmed-dead",
            "reason": "in-flight run %r confirmed dead; reclaim and proceed" % (stamp,),
            "write_orphan_record": not has_record,
        }

    # UFR-4: confirmed alive — refuse; never trample a live run. Creates nothing.
    if liveness == "alive":
        return {
            "action": "refuse",
            "class": "confirmed-alive",
            "reason": "in-flight run %r confirmed alive; refuse (UFR-4)" % (stamp,),
            "write_orphan_record": False,
        }

    # Unconfirmable (or any non-dead, non-alive value) — fail-closed, treat as alive (UFR-4).
    return {
        "action": "refuse",
        "class": "unconfirmable",
        "reason": "in-flight run %r liveness unconfirmable; fail-closed refuse (UFR-4)"
        % (stamp,),
        "write_orphan_record": False,
    }
