import os
import subprocess

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

SHOWRUNNER_SMOKES = [
    "plugins/superheroes/lib/tests/courier_exec_smoke.js",
    "plugins/superheroes/lib/tests/test_pilot_deciders_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_bundle_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_entry_await_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_boundary_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_extras_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_panel_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_produce_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fronthalf_switch_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fullpipeline_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_fullrun_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_io_seam_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_panel_shell_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reconcile_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_resume_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_loop_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_reviewcode_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_phase_progress_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ship_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_startup_fold_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_front_half_leaf_budget_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_label_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_wire_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_exec_persist_smoke.js",
    # #115: the two new in-memory review-panel smokes.
    "plugins/superheroes/lib/tests/showrunner_review_crash_resume_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_review_round_state_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_review_breaker_halt_smoke.js",
    # #115 Task 13a: args-based front-half selector (globalThis flags + bundle ENTRY text assertion).
    "plugins/superheroes/lib/tests/showrunner_fronthalf_argsel_smoke.js",
    # #115 Task 16: draft-PR twin-boundary (adopt/create/gate via exec world-read + prAction twin).
    "plugins/superheroes/lib/tests/showrunner_draftpr_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_ready_pr_readback_smoke.js",
    # #115 Task 17: startup overrides read + unconditional cheapest dumb-pipe pin (bundle wrapper).
    "plugins/superheroes/lib/tests/showrunner_task17_smoke.js",
    # #115 Task 18: front_half.renderRunOutcome twin — phase_records embed + stub renderer.
    "plugins/superheroes/lib/tests/showrunner_front_half_render_outcome_smoke.js",
    # #115: the build_phase smokes — registered here (the discovery guard now also matches
    # build_phase_*_smoke.js). The loop/setup/pertask smokes exercise the build LOOP (unchanged until
    # Task 15) and pass as-is; only build_phase_final_review_smoke.js is rewritten to the in-memory
    # contract in this task (runFinalReview is rewritten here).
    "plugins/superheroes/lib/tests/build_phase_loop_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_setup_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_pertask_smoke.js",
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
    # #120: native ship-phase catch-up stretch (freshen loop, conflict-abort, fence, FR-2 give-up).
    "plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js",
    # #120: native ship-phase CI-fix stretch (fix loop, fixer dispatch, revert-to-draft, UFR-3/5/6).
    "plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js",
    # #120: native ship-phase structured hand-back (FR-6/FR-7, scrubbed, best-effort delivery).
    "plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js",
    # #120: ship-phase guard invariants (UFR-2 unreadable-park, UFR-4 fence fail-closed, FR-8 never-merge).
    "plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js",
    # #120: forged-ship DoD walkthrough — catch-up + fix-loop + return-to-draft + hand-back end-to-end.
    "plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js",
]


def test_showrunner_node_smokes_are_enforced():
    smoke_dir = os.path.join(ROOT, "plugins", "superheroes", "lib", "tests")
    discovered = {
        os.path.join("plugins", "superheroes", "lib", "tests", name)
        for name in os.listdir(smoke_dir)
        if (name.startswith("showrunner_") or name.startswith("build_phase_") or name.startswith("courier_"))
        and name.endswith("_smoke.js")
    }
    assert discovered == set(SHOWRUNNER_SMOKES)


@pytest.mark.parametrize("rel", SHOWRUNNER_SMOKES)
def test_showrunner_node_smoke_passes(rel):
    # One independent test per smoke so a failure names the offending file instead of collapsing the
    # whole suite into a single red assertion.
    result = subprocess.run(["node", rel], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
