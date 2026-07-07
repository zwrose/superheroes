# plugins/superheroes/lib/ship_gate.py
"""The step 3 ship-readiness gate: deterministic, fail-closed proof that step 1 Build (SDD) and
step 2 Review (review-code) ran over the shipped code before the producer opens a PR.

`decide` is a PURE function (dicts + the HEAD string in -> action out), mirroring
`recover.pr_action`. The provenance read/write helpers (Task 2) are colocated here the way
`review-crew/lib/review_result.py` colocates its writer + fail-closed reader. All reads
fail CLOSED: absent/garbled/stale evidence GATEs, never reads as clean.

Threat posture: the producer is an LLM that *rationalizes shortcuts*, not an adversary.
This gate makes a *rationalized* skip leave no evidence (-> GATE). It is NOT un-forgeable
(`review_result.py` is an ungated CLI) — best-effort against a deliberate, transcript-
evident forge. See the work-item plan.
"""

import json
import os

import control_plane
import journal

_TERMINAL = "exit_clean"


class ProvenanceError(Exception):
    """provenance.json exists but is unparseable — callers fail closed (never clobber)."""


def read_provenance(path):
    """Absent -> {}; a valid JSON object -> the dict; present-but-unparseable -> raise
    ProvenanceError (so a writer aborts rather than clobbering a sibling key, and the
    orchestrator GATEs rather than reading a transient garble as 'build absent')."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError) as e:
        raise ProvenanceError(f"{path}: {e}") from e
    if not isinstance(obj, dict):
        raise ProvenanceError(f"{path}: not a JSON object")
    return obj


def write_build(path, *, engine, head):
    """Record that the build ran via `engine` at `head` (read-modify-write; never clobbers)."""
    prov = read_provenance(path)
    prov["build"] = {"engine": engine, "head": head}
    control_plane.atomic_write(path, json.dumps(prov))
    return prov


def record_build_denial(path, *, step, command):
    """Record that a substantive build sub-step was denied by the 15-min timeout.

    Read-modify-write: append to the `buildDenials` list (never clobber a sibling key or a
    prior denial). A denial marks the build evidence incomplete/tainted so `decide` GATEs
    (UFR-6/UFR-8) — the PR is held a draft even though the build step nominally "ran"."""
    prov = read_provenance(path)
    prov.setdefault("buildDenials", []).append({"step": step, "command": command})
    control_plane.atomic_write(path, json.dumps(prov))
    return prov


def set_review_covers(path, head):
    """Record the HEAD review-code's clean exit covered (read-modify-write; never clobbers)."""
    prov = read_provenance(path)
    prov.setdefault("review", {})["covers"] = head
    control_plane.atomic_write(path, json.dumps(prov))
    return prov


def journal_build_denials(events_path):
    """The SECOND build-denial carrier (premortem-001): the run's journal `permission_denied`
    events whose `step` is a build step (`build:<id>`). buildOneTask writes this best-effort
    (courier-retried) event BEFORE the fail-closed provenance write, so a build denial survives
    even when the provenance write itself fails and the task then parks — a resume that skips
    buildOneTask (its commit already exists) would otherwise drop the denial forever.

    Fail-SAFE toward provenance-only: a journal read error (or absent file) swallows to `[]`, so
    this carrier can only ever ADD denials to the provenance carrier, never clear one."""
    try:
        evs = journal.read_events(events_path)
    except Exception:
        return []
    out = []
    for ev in evs:
        if not isinstance(ev, dict) or ev.get("type") != "permission_denied":
            continue
        step = ev.get("step")
        if isinstance(step, str) and step.startswith("build:"):
            out.append({"step": step, "command": ev.get("detail")})
    return out


def decide(provenance, review_result, head, *, journal_denials=None):
    """Pure step 3 ship-gate decision; fail-closed (anything unproven -> gate).

    `provenance`: from read_provenance (a dict, or {} when absent).
    `review_result`: from a fail-closed parse of review-code's --result-file
        ({"action": ...}, or {"action": "halt"} on missing/garbled).
    `head`: the current branch HEAD (`git rev-parse HEAD`).
    `journal_denials`: the SECOND build-denial carrier (premortem-001) — the run's journal
        `build:` permission_denied events (from `journal_build_denials`). EITHER carrier gates;
        the fold is additive (fail-safe), so an unreadable journal (`[]`) never weakens the
        provenance carrier.
    """
    # 1. Build evidence (FR-3 / UFR-4): SDD must have run.
    if not isinstance(provenance, dict) or not provenance.get("build"):
        return {"action": "gate",
                "reason": "build provenance absent — subagent-driven-development did not run "
                          "(build bypassed)"}
    # 1b. Denied build evidence (UFR-6 / UFR-8): a substantive build sub-step denied by the
    # 15-min timeout means the build step "ran" but its evidence is incomplete/tainted. GATE
    # so the PR stays a draft (reused draft-hold path via mark_ready_action / revert-draft).
    # DUAL-CARRIER (premortem-001): the provenance list AND the run's journal `build:` denial
    # events are independent carriers — EITHER gates. The journal carrier catches a denial that
    # was journaled before a failed provenance write parked the task (a resume then skips the
    # already-committed leaf, so provenance.buildDenials stays empty). The fold only ADDs.
    denials = provenance.get("buildDenials") if isinstance(provenance, dict) else None
    jdenials = journal_denials or []
    if denials or jdenials:
        return {"action": "gate",
                "reason": "build evidence incomplete — a substantive build step was denied "
                          "by the 15-min timeout (%d step(s))" % (len(denials or []) + len(jdenials))}
    # 2. Review evidence (FR-1 / FR-2 / UFR-1 / UFR-3), reason keyed by action.
    action = review_result.get("action") if isinstance(review_result, dict) else None
    if action != _TERMINAL:
        reason = {
            "exit_skipped": "review skipped a blocking finding — not shipping it",
            "review": "review loop did not terminate (non-terminal state)",
        }.get(action, "review did not run / did not finish clean")
        return {"action": "gate", "reason": reason}
    # 3. Freshness (FR-4 / UFR-5): review must cover the shipped HEAD. A falsy
    # covers/head (absent stamp, or a failed `git rev-parse`) must GATE, never proceed.
    rev = provenance.get("review")
    covers = rev.get("covers") if isinstance(rev, dict) else None
    if not covers or covers != head:
        return {"action": "gate",
                "reason": "review evidence stale — covered HEAD != shipped HEAD; "
                          "re-run review-code"}
    return {"action": "proceed", "reason": "build + review evidence present and current"}
