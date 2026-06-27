import os
import subprocess

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

SHOWRUNNER_SMOKES = [
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
    "plugins/superheroes/lib/tests/showrunner_ship_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_startup_gate_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_label_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_workhorse_wire_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_test_pilot_phase_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_exec_persist_smoke.js",
    # #115: the two new in-memory review-panel smokes.
    "plugins/superheroes/lib/tests/showrunner_review_crash_resume_smoke.js",
    "plugins/superheroes/lib/tests/showrunner_review_breaker_halt_smoke.js",
    # #115: the build_phase smokes — registered here (the discovery guard now also matches
    # build_phase_*_smoke.js). The loop/setup/pertask smokes exercise the build LOOP (unchanged until
    # Task 15) and pass as-is; only build_phase_final_review_smoke.js is rewritten to the in-memory
    # contract in this task (runFinalReview is rewritten here).
    "plugins/superheroes/lib/tests/build_phase_loop_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_setup_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_pertask_smoke.js",
    "plugins/superheroes/lib/tests/build_phase_final_review_smoke.js",
]


def test_showrunner_node_smokes_are_enforced():
    smoke_dir = os.path.join(ROOT, "plugins", "superheroes", "lib", "tests")
    discovered = {
        os.path.join("plugins", "superheroes", "lib", "tests", name)
        for name in os.listdir(smoke_dir)
        if (name.startswith("showrunner_") or name.startswith("build_phase_"))
        and name.endswith("_smoke.js")
    }
    assert discovered == set(SHOWRUNNER_SMOKES)


@pytest.mark.parametrize("rel", SHOWRUNNER_SMOKES)
def test_showrunner_node_smoke_passes(rel):
    # One independent test per smoke so a failure names the offending file instead of collapsing the
    # whole suite into a single red assertion.
    result = subprocess.run(["node", rel], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
