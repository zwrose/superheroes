"""Cleanup planner for the acceptance harness (FR-7 / UFR-3 / UFR-8).

Pure `plan(discovered_artifacts, run_stamp)` over a list of `{kind, name}` artifacts: it
decides which harness-minted artifacts to reap and which to leave behind, and it NEVER
mutates state — it only produces a plan the orchestrator acts on. Every routing decision
goes through `acceptance_fixture.parse_stamp` (imported, never re-implemented), so the
harness only ever plans to reap a name that embeds a structurally-valid *full* stamp.

Three routes per artifact:

  1. Its name parses to a valid full stamp and (when `run_stamp` is pinned) equals it →
     `reap`. When `run_stamp` is None (record-less UFR-8 discovery) any valid full stamp
     is reaped — each name is judged independently.
  2. Its name matches the reserved prefix but fails the full-stamp parse (prefix + invalid
     chars, or a bare prefix) → `leave_behind` with a reason (UFR-3 reported path). Such a
     name is NEVER reaped: an unparseable-but-reserved name is a potential real artifact
     the harness must not delete.
  3. Its name has no reserved prefix at all → ignored (a real owner artifact — never
     touched, never reported).

On already-clean input (nothing matching) the plan is empty (idempotent — a re-run of the
same cleanup is a no-op). Mirrors the other deciders: pure, no I/O, never raises.
"""
import acceptance_fixture


def plan(discovered_artifacts, run_stamp):
    """Pure cleanup plan over the injected `discovered_artifacts` list.

    Returns `{"reap": [{kind, name}], "leave_behind": [{kind, name, reason}]}`.

    An artifact is reaped only when its name parses (via
    `acceptance_fixture.parse_stamp`) to a valid full stamp AND — when `run_stamp` is
    pinned — equals it. A name matching the reserved prefix but failing the full-stamp
    parse is left behind (never reaped). A name with no reserved prefix is ignored.
    """
    reap = []
    leave_behind = []

    for art in discovered_artifacts or []:
        name = art.get("name")
        kind = art.get("kind")
        parsed = acceptance_fixture.parse_stamp(name)

        if parsed is None:
            # No valid full stamp. Reserved-prefix-but-unparseable is reported and left
            # behind (UFR-3, never deleted); anything else is a real owner artifact —
            # ignored entirely.
            if name and name.startswith(acceptance_fixture.RESERVED_PREFIX):
                leave_behind.append({
                    "kind": kind,
                    "name": name,
                    "reason": "name carries the reserved prefix but does not parse to a "
                              "valid full stamp; left behind, never reaped",
                })
            continue

        # A structurally-valid full stamp.
        if run_stamp is not None and parsed != run_stamp:
            # A different run's artifact — not this invocation's target. Ignored.
            continue

        reap.append({"kind": kind, "name": name})

    return {"reap": reap, "leave_behind": leave_behind}
