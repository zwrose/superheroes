"""Pure launch-time preflight readout for the showrunner (spec showrunner-preflight-readout).
Composes the run's OWN resolvers into a JSON-able snapshot and renders it — never a parallel
table, so the readout cannot drift from dispatch. Zero model tokens; stdlib only. Fail-soft:
a per-field read error degrades that one field to 'unavailable' (UFR-2); only a total failure
to build any frame is fail-closed (UFR-3)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_tier
import engine_pref

READOUT_VERSION = 1

# The spine's phase roster is the single source of truth. Kept as a literal that MUST equal
# showrunner.js's PHASES; the roster-parity node smoke (Task 12) asserts they match so a phase
# add in the spine fails a test rather than silently under-reporting in the readout.
PHASES = ["plan", "review-plan", "tasks", "review-tasks", "workhorse",
          "review-code", "draft-PR", "test-pilot", "mark-ready", "ship"]

# Per phase: the ordered roles it dispatches. Each role is (roleLabel, model_tier role, role_kind,
# kind-tag). kind-tag drives engine selection (review/build/fix) + the orchestration/None marker.
# 'draft-PR' and 'mark-ready' dispatch no agent (deterministic spine steps): they contribute a single
# non-agent placeholder row (kind "none") so the readout still NAMES every spine phase and the roster
# stays row-for-phase complete against showrunner.js's PHASES (roster-parity guard) — a phase can
# never be silently dropped from the readout. A "none"-kind row pins no engine/model/effort.
_PHASE_ROLES = {
    "plan":         [("author", "author", None, "author")],
    "review-plan":  [("reviewer", "reviewer", "review", "review")],
    "tasks":        [("author", "author", None, "author")],
    "review-tasks": [("reviewer", "reviewer", "review", "review")],
    "workhorse":    [("builder", "mechanical", "build", "build"),
                     ("per-task reviewer", "reviewer", "review", "review"),
                     ("fixer", "fixer", "fix", "fix"),
                     ("final reviewer", "reviewer-deep", "review", "review-deep")],
    "review-code":  [("deep reviewer", "reviewer-deep", "review", "review-deep")],
    "draft-PR":     [("no agent (deterministic step)", None, None, "none")],
    "test-pilot":   [("orchestration", "orchestrator", None, "orchestration")],
    "mark-ready":   [("no agent (deterministic step)", None, None, "none")],
    "ship":         [("fixer (on CI failure)", "fixer", "fix", "fix")],
}


def _engine_for(kind, prefs):
    """The engine for a role kind. author/orchestration/None-kind roles run on claude (model_tier
    governs); review/build/fix defer to engine_pref."""
    if kind in ("review", "review-deep"):
        return engine_pref.resolve_engine("review", prefs)
    if kind == "build":
        return engine_pref.resolve_engine("build", prefs)
    if kind == "fix":
        return engine_pref.resolve_engine("fix", prefs)
    return "claude"


def _effort_for(engine, kind, prefs):
    effort_overrides = prefs.get("effort") if isinstance(prefs, dict) else None
    role_kind = "review-deep" if kind == "review-deep" else ("review" if kind == "review"
                else ("build" if kind == "build" else ("fix" if kind == "fix" else None)))
    if role_kind is None:
        return None
    return engine_pref.resolve_effort(engine, role_kind, effort_overrides)


def enumerate_dispatch(prefs, tier_overrides, run_overrides=None):
    """The per-(phase,role) dispatch roster. `prefs` = load_engine_prefs shape; `tier_overrides` =
    {role: model}; `run_overrides` = {role: {engine?,model?,effort?}} applied last (FR-11).
    Returns rows in PHASES order; a phase with no dispatching role contributes no row."""
    run_overrides = run_overrides if isinstance(run_overrides, dict) else {}
    tier_overrides = tier_overrides if isinstance(tier_overrides, dict) else {}
    rows = []
    for phase in PHASES:
        for (label, tier_role, _kind_key, kind) in _PHASE_ROLES.get(phase, []):
            if kind == "none":
                # A deterministic spine step that dispatches no agent. It still gets a row so the
                # readout names every phase, but pins no engine/model/effort and is never overridable.
                rows.append({"phase": phase, "role": tier_role, "roleLabel": label,
                             "engine": "claude", "model": None, "effort": None, "kind": kind,
                             "configuredOrDefault": "default"})
                continue
            model = model_tier.resolve_model(tier_role, tier_overrides,
                                             "code" if tier_role == "fixer" else None)
            engine = _engine_for(kind, prefs)
            effort = _effort_for(engine, kind, prefs)
            # FR-5 (second criterion): label each row configured-vs-default. A row is "configured"
            # when the project's model-tier policy carries an EXPLICIT entry for this tier role
            # (the reader returned an owner-set value); otherwise the value fell back to the
            # built-in tier default and the row is "default". Rendered as a per-line [default]
            # label by _phase_line; a run override later re-marks the row overridden (FR-11).
            configured = tier_role in tier_overrides
            row = {"phase": phase, "role": tier_role, "roleLabel": label,
                   "engine": engine, "model": model, "effort": effort, "kind": kind,
                   "configuredOrDefault": "configured" if configured else "default"}
            _apply_override(row, run_overrides.get(tier_role))
            rows.append(row)
    return rows


def _apply_override(row, ov):
    """Apply a per-run override (engine/model/effort) to a row in place, marking it overridden.
    A None/empty override is a no-op. Filled in by Task 5."""
    return row
