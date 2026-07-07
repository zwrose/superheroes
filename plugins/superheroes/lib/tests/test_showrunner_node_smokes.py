import os
import subprocess

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

SHOWRUNNER_SMOKES = [
    "plugins/superheroes/lib/tests/courier_exec_smoke.js",
    "plugins/superheroes/lib/tests/test_pilot_deciders_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_test_pilot_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ship_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_leaf_budget_labels_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_bundle_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_entry_await_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_boundary_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_extras_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_panel_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_produce_smoke.js",
    # storage-mode-aware front-half doc/marker/ledger paths (out-of-repo project regression).
    "plugins/superheroes/lib/tests/showrunner_fronthalf_docdir_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_switch_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fullrun_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_io_seam_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js",
    # #174: confirmation-bar economics — certify-after-scoped, severity-gated re-arm, hard cap.
    "plugins/superheroes/lib/tests/showrunner_confirmation_economics_smoke.js",
    # mega-JSON regression: loop persistence ships paths + small scalars, never the record body.
    "plugins/superheroes/lib/tests/showrunner_reviewloop_payload_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_terminal_record_compose_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_defer_confirmation_fence_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reconcile_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_resume_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_verify_readback_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_phase_progress_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_readout_fencing_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ship_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_startup_fold_smoke.js",
    # #221: the startup gather resolves engine prefs from an OUT-OF-REPO core.md — runs the REAL gather
    # script (store-base=None), asserting the owner's non-claude prefs round-trip and that the (root,root)
    # bug degrades to all-claude (the canned-answer smokes were blind to the real Python resolution).
    "plugins/superheroes/lib/tests/showrunner_startup_engineprefs_smoke.js",
    # #25 quick discovery (PR 1 — showrunner leg): route decider + fresh-quick skip journaling +
    # loop entry at build + fail-closed refuse of a missing/malformed tasks artifact + full unchanged.
    "plugins/superheroes/lib/tests/showrunner_quick_route_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_front_half_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_label_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_wire_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_park_release_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_exec_persist_smoke.js",
    # BUG B: persistPhase resolves the SAVE result from a two-JSON-line side-effect && save chain.
    "plugins/superheroes/lib/tests/showrunner_persist_sideeffect_smoke.js",
    # #115: the two new in-memory review-panel smokes.
    "plugins/superheroes/lib/tests/showrunner_review_crash_resume_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_review_round_state_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_review_breaker_halt_smoke.js",
    # #157: code-fixer changedSubjects derivation (file paths + object fixes -> policy subjects).
    "plugins/superheroes/lib/tests/showrunner_policy_changed_subjects_smoke.js",
    # #157 follow-up: circuit breaker ignores transport-failed (all-missing) rounds.
    "plugins/superheroes/lib/tests/showrunner_circuit_breaker_reviewed_rounds_smoke.js",
    # #141 fold 2: reviewPanel honors the preloaded review_setup_gather.py result (mkdir + deferred
    # seed + entry-bootstrap + coverage folded into ONE leaf); no preloaded -> unfolded fallback.
    "plugins/superheroes/lib/tests/showrunner_review_setup_gather_smoke.js",
    # #211 Phase 4c — the ADVERSARIAL proof: mangling any >4KB courier answer never breaks the loop
    # (nothing that big crosses), and a mangled SMALL decider answer fails closed, never silently wrong.
    "plugins/superheroes/lib/tests/showrunner_reviewloop_adversarial_smoke.js",
    # #211 PR 3 — the JS reassembler's regression net: force the receipt+chunk EMERGENCY FALLBACK and
    # pin _readReceiptText's raw-text reassembly (happy multi-chunk) + both fail-closed guards (per-chunk
    # chunkHash, final reassembly-hash backstop) -> a mangled chunk parks round-memory-unreadable.
    "plugins/superheroes/lib/tests/showrunner_reviewloop_fallback_smoke.js",
    # #115 Task 13a: args-based front-half selector (globalThis flags + bundle ENTRY text assertion).
    "plugins/superheroes/lib/tests/showrunner_fronthalf_argsel_smoke.js",
    # #115 Task 16: draft-PR twin-boundary (adopt/create/gate via exec world-read + prAction twin).
    "plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ready_pr_readback_smoke.js",
    # #228 mark-ready DoD filler leg: dod-park -> one filler -> one re-decide (0.10.0 qualification).
    "plugins/superheroes/lib/tests/showrunner_markready_dod_filler_smoke.js",
    # #115 Task 17: startup overrides read + unconditional cheapest dumb-pipe pin (bundle wrapper).
    "plugins/superheroes/lib/tests/showrunner_task17_smoke.js",
    # #38 Task 12: reviewCodeLeaves engine branch (reviewer/synthesis read-only on reviewer engine,
    # fixStep write on implementation engine) + startup __SR_ENGINE_PREFS load.
    "plugins/superheroes/lib/tests/showrunner_engine_review_smoke.js",
    # #115 Task 18: front_half.renderRunOutcome twin — phase_records embed + stub renderer.
    "plugins/superheroes/lib/tests/showrunner_front_half_render_outcome_smoke.js",
    # #115: the build_phase smokes — registered here (the discovery guard now also matches
    # build_phase_*_smoke.js). The loop/setup/pertask smokes exercise the build LOOP (unchanged until
    # Task 15) and pass as-is; only build_phase_final_review_smoke.js is rewritten to the in-memory
    # contract in this task (runFinalReview is rewritten here).
    "plugins/superheroes/lib/tests/build_phase_loop_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_setup_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_pertask_smoke.js",
    # #222: the workhorse build + per-task reviewer prompts carry the mode-aware tasks-doc pointer +
    # no-sweep guardrail (out-of-repo storage blind-build), and needs_context retry genuinely adds context.
    "plugins/superheroes/lib/tests/build_phase_docpointer_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_record_budget_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_final_review_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_final_coverage_smoke.js",
    # #115 courier-drop retry: execJson/execText retry the cheap haiku exec courier ONCE on a
    # dropped/garbled stdout (journal recover/park/no-retry-on-real-fail/happy-path + read-gate recover).
    "plugins/superheroes/lib/tests/build_phase_courier_retry_smoke.js",
    # back-half cluster: task-list leaf shape guards (BUG-2/3) + silent-zero park.
    "plugins/superheroes/lib/tests/build_phase_tasklist_shape_smoke.js",
    # configurable base branch: --base threading to ship freshness, draft-PR, gather + bundle ENTRY.
    "plugins/superheroes/lib/tests/showrunner_base_smoke.js",
    # FIX A: resolveTarget seam targets build worktree + null-resolver parks (never reviews root).
    "plugins/superheroes/lib/tests/showrunner_reviewcode_resolver_smoke.js",
    # FR-5 cwd-rooting for cmdRunner: selfContained() in cmdRunner pins cwd to repo root when
    # __SR_ROOT is set (RED->GREEN after the fix); no-op when unset; no double-cd guard.
    "plugins/superheroes/lib/tests/showrunner_cmdrunner_cwd_smoke.js",
    # #38: engine_dispatch.js dispatchExternal — review/build happy paths, stdin-redirect delivery,
    # UFR-5 timeout, UFR-6 unauditable, sec-101 commit-failure audit symmetry. Named
    # showrunner_engine_dispatch_smoke.js (not engine_dispatch_smoke.js) so the discovery-equality
    # guard below (which only auto-matches showrunner_*/build_phase_* names) stays satisfied.
    "plugins/superheroes/lib/tests/showrunner_engine_dispatch_smoke.js",
    # plan-author engine route: author-plan external dispatch (commit-free write, --model
    # threading, notify, UFR-6) + producePhase planAuthor wiring (plan-only, fall-open).
    "plugins/superheroes/lib/tests/showrunner_engine_author_smoke.js",
    # #38 Task 11: build_phase.js worker/fixer/final-review engine-branch routing (UFR-2/4, FR-15,
    # FIX I5 final-fixer report contract). Name starts build_phase_ so the discovery guard auto-matches.
    "plugins/superheroes/lib/tests/build_phase_engine_smoke.js",
    # #120: native ship-phase catch-up stretch (freshen loop, conflict-abort, fence, FR-2 give-up).
    "plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js",
    # #120: native ship-phase CI-fix stretch (fix loop, fixer dispatch, revert-to-draft, UFR-3/5/6).
    "plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js",
    # #120-deferred settle-poll: pending CI waits (bounded), never dispatches the fixer (0.10.0 qualification).
    "plugins/superheroes/lib/tests/showrunner_ship_settle_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ship_leaf_budget_smoke.js",
    # #120: native ship-phase structured hand-back (FR-6/FR-7, scrubbed, best-effort delivery).
    "plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js",
    # #120: ship-phase guard invariants (UFR-2 unreadable-park, UFR-4 fence fail-closed, FR-8 never-merge).
    "plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js",
    # #120: forged-ship DoD walkthrough — catch-up + fix-loop + return-to-draft + hand-back end-to-end.
    "plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js",
    # #118 conformance: canned full run through the COMMITTED BUNDLE — per-phase courier-leaf
    # budgets (the Labels matrix as fixture), the unconditional cheapest-model pin on every
    # dumb pipe, the one-save-phase-progress tail, and the two-leaf startup stretch.
    "plugins/superheroes/lib/tests/showrunner_stretch_budget_smoke.js",
    # the misbehaving-courier regression net (live 2026-07-02, 4 runs parked at review-plan):
    # prose answers for missing-file reads, chatty write acks, one mangled persist answer,
    # and terminal-record compose — the canned full run must still reach 'ready' with
    # correct terminal records written, and no courier text may enter a fence.
    "plugins/superheroes/lib/tests/showrunner_misbehaving_courier_smoke.js",
    # the terminal-record compose-persist regression (live 2026-07-02, run wf_94c879e0-747):
    # the full ~14KB verdict staged through one courier writeFile was byte-dropped and the phase
    # parked payload-stage-failed; the record is now composed Python-side from on-disk state so no
    # oversized blob crosses the courier, and it survives a byte-dropping courier fake.
    "plugins/superheroes/lib/tests/showrunner_terminal_record_compose_smoke.js",
    # #170: the libRoot compose guard — no raw `plugins/superheroes/lib` compose survives the bundle,
    # an absolute __SR_LIB resolves composes under it, and a missing absolute code root fails closed
    # to a named park.
    "plugins/superheroes/lib/tests/showrunner_compose_libroot_smoke.js",
    # #130 token telemetry: the cost_meter accumulator (proxy dispatch counts + budget-measured
    # output-token deltas) and the spine's best-effort phase_cost / run_completed emit path.
    "plugins/superheroes/lib/tests/showrunner_cost_meter_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_cost_emit_smoke.js",
    # spec showrunner-preflight-readout Task 9: the pin-or-resolve fork (FR-8, UFR-2 second clause) —
    # a pinned frozen-snapshot value wins over the config-derived map; an unpinned field resolves
    # live; no snapshot present -> the config-derived maps are returned unchanged (rollback state).
    "plugins/superheroes/lib/tests/showrunner_preflight_freeze_smoke.js",
    # spec showrunner-preflight-readout Task 10: roster-parity guard — preflight_readout.PHASES must
    # equal showrunner.js's exported PHASES, so a phase add in the spine fails a test rather than
    # silently under-reporting in the readout (Risk: roster drift).
    "plugins/superheroes/lib/tests/showrunner_preflight_roster_smoke.js",
    # freeze-consume hardening (B): the JS consumer's READOUT_VERSION is a COPY of the Python writer's
    # preflight_readout.READOUT_VERSION — dumped via python3 -c and asserted equal, so a Python bump
    # that isn't mirrored in the migration gate fails CI (roster-parity pattern).
    "plugins/superheroes/lib/tests/showrunner_freeze_version_drift_smoke.js",
    # freeze-consume hardening (E): showrunner.js's _TIER_ROLE (review-code tier vocabulary) must match
    # review_code_config._TIER_ROLE AND appear in preflight_readout._PHASE_ROLES — a rename on either
    # Python home fails CI rather than silently mis-routing a frozen pin.
    "plugins/superheroes/lib/tests/showrunner_reviewcode_tier_role_drift_smoke.js",
]


def test_showrunner_node_smokes_are_enforced():
    smoke_dir = os.path.join(ROOT, "plugins", "superheroes", "lib", "tests")
    discovered = {
        os.path.join("plugins", "superheroes", "lib", "tests", name)
        for name in os.listdir(smoke_dir)
        if (name.startswith("showrunner_") or name.startswith("build_phase_") or name.startswith("courier_")
            or name.startswith("test_pilot_"))
        and name.endswith("_smoke.js")
    }
    assert discovered == set(SHOWRUNNER_SMOKES)


@pytest.mark.parametrize("rel", SHOWRUNNER_SMOKES)
def test_showrunner_node_smoke_passes(rel):
    # One independent test per smoke so a failure names the offending file instead of collapsing the
    # whole suite into a single red assertion.
    result = subprocess.run(["node", rel], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
