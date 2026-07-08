"""Expected-vs-actual dispatch-census decider for the acceptance harness (#299).

The #162 preflight readout renders the EXPECTED engine·model·effort per phase/role from the run's
real resolvers. This closes the loop: after a run, diff those expected rows against the run's ACTUAL
dispatch census — `external_dispatch` journal events for engine legs, `phase_cost.byModel` for native
legs — and FAIL LOUD on any divergence that lacks a journaled reason. It encodes "fall-open is legal
but must be VISIBLE" (FR-4 / the #288/#292 honesty family) into a machine check: an all-Claude run
under a codex/cursor calibration must no longer look identical to a healthy externally-routed one.

Pure `decide(census)` over a plain dict the mechanical shell assembles (acceptance_deps.py). Mirrors
`acceptance_verdict.decide` / `preflight.decide`: no I/O, never raises, fail-CLOSED — any divergence
yields `ok:false` naming the first offending fact. Keys on the engine/roleKind PAYLOAD fields, never
display labels or model names.
"""

# Readout row kind → the roleKind an external_dispatch payload carries for that leg. review-deep
# dispatches with roleKind 'review' (build_phase.js final reviewer / review-code deep reviewer both
# pass roleKind:'review' — depth rides the EFFORT, not the roleKind), so both map to 'review'.
_KIND_TO_ROLEKIND = {"review": "review", "review-deep": "review", "build": "build", "fix": "fix",
                     "author-plan": "author-plan"}
_EXTERNAL_ENGINES = ("codex", "cursor")

# roleKinds whose legs are CONDITIONAL — they may legitimately never dispatch in a healthy run, so
# their absence is not evidence of a silent fall-open and is never required:
#   fix         — the workhorse/review-code fixer runs ONLY when a reviewer returns blockers; a clean
#                 build that passes review on the first round never fixes.
#   author-plan — the plan-author leaf resumes a usable draft rather than re-authoring (FR-8), so a
#                 resumed run legitimately makes no author-plan dispatch.
# The unconditional legs (build, review) run whenever their phase is traversed, so THEY carry the
# #277 silent-all-Claude tripwire. A conditional leg that DID dispatch is still validated (its ok /
# reasoned outcome is accounted for); it is only never DEMANDED.
_CONDITIONAL_ROLEKINDS = frozenset({"fix", "author-plan"})


def decide(census):
    """Pure verdict over the assembled census dict. Returns {ok: bool, failures: [str]}.

    census keys:
      expected_rows       — the readout snapshot's `phases` rows (dicts with phase/role/kind/engine/
                            model, plus optional nativeByDesign / fallbackToClaude flags).
      external_dispatches — [{engine, roleKind, outcome}] projected from `external_dispatch` events.
      by_model            — {phase: {model: count}} projected from `phase_cost` events.
      traversed_phases    — the phases the run actually entered (only these are asserted).
      allowed_models      — the model short-names the calibration can legitimately produce
                            (resolver defaults ∪ overrides ∪ the readout's own rows).
      fable_allowed       — True only when the profile/overrides EXPLICITLY configure a role to fable.

    Checks:
      A. Engine coverage — every UNCONDITIONAL readout-expected EXTERNAL row for a TRAVERSED phase
         has ≥1 matching `external_dispatch` (engine + roleKind) with an ok outcome, OR a journaled
         fall-open reason (an (engine, roleKind) dispatch with a non-ok outcome). Skipped: native-by-
         design + fall-back-to-Claude rows (run native by design/authz — no evidence owed), untraversed
         phases (never ran), and CONDITIONAL roleKinds (_CONDITIONAL_ROLEKINDS — a fix/author-plan leg
         may legitimately not run). An empty `traversed_phases` therefore demands nothing (the shell
         treats a journal with no dispatch evidence at all as its own failure).
      B. Model census — every model in any phase's byModel is in `allowed_models`.
      C. Never-Fable (#299 Phase 3a) — 'fable' in ANY byModel fails unless `fable_allowed`, regardless
         of the readout rows (a buggy readout showing fable can't launder it).
    """
    if not isinstance(census, dict):
        census = {}
    rows = census.get("expected_rows") or []
    dispatches = census.get("external_dispatches") or []
    by_model = census.get("by_model") or {}
    traversed = set(census.get("traversed_phases") or [])
    allowed_models = set(census.get("allowed_models") or [])
    fable_allowed = bool(census.get("fable_allowed"))
    failures = []

    # Index the actual external dispatches by (engine, roleKind): pairs that ran OK, and pairs that
    # have a journaled fall-open reason (a non-ok outcome — timeout / unreadable / commit-failed /
    # needs_context / authz-denied). A journaled reason satisfies FR-4 visibility. Keyed on the pair
    # (not roleKind alone) so one engine's journaled failure can't excuse a different engine's row.
    ok_dispatch = set()
    reasoned_dispatch = set()
    for d in dispatches if isinstance(dispatches, list) else []:
        if not isinstance(d, dict):
            continue
        key = (d.get("engine"), d.get("roleKind"))
        (ok_dispatch if d.get("outcome") == "ok" else reasoned_dispatch).add(key)

    # A. Engine coverage — only the UNCONDITIONAL external legs of a TRAVERSED phase are demanded.
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        engine = row.get("engine")
        if engine not in _EXTERNAL_ENGINES:
            continue                       # native leg — no external evidence owed
        if row.get("nativeByDesign"):
            continue                       # dispatch site has no engine axis (doc panels / ship fixer)
        if row.get("fallbackToClaude"):
            continue                       # readout already showed the fall-open (engine unauthorized)
        phase = row.get("phase")
        if phase not in traversed:
            continue                       # phase never ran (or traversal unknown) — nothing to prove
        role_kind = _KIND_TO_ROLEKIND.get(row.get("kind"))
        if role_kind is None or role_kind in _CONDITIONAL_ROLEKINDS:
            continue                       # conditional leg — its absence is not a fall-open
        if (engine, role_kind) in ok_dispatch:
            continue
        if (engine, role_kind) in reasoned_dispatch:
            continue                       # a journaled fall-open reason exists — visible, tolerated
        failures.append(
            "engine evidence missing: calibration routes %s to %s (phase %s) but the run journaled "
            "no matching external_dispatch and no fall-open reason — silent fall-open to Claude"
            % (role_kind, engine, phase))

    # B & C. Model census + never-Fable.
    for phase in sorted(by_model) if isinstance(by_model, dict) else []:
        models = by_model.get(phase) or {}
        for model in sorted(models) if isinstance(models, dict) else []:
            if model == "fable" and not fable_allowed:
                failures.append(
                    "Fable model dispatched in phase %s with no explicit profile/override configuring "
                    "it — Fable must never run on a harness run (#299 never-Fable tripwire)" % phase)
                continue
            if allowed_models and model not in allowed_models:
                failures.append(
                    "unexpected model %r in phase %s — outside the readout-expected model set %s"
                    % (model, phase, sorted(allowed_models)))

    return {"ok": not failures, "failures": failures}
