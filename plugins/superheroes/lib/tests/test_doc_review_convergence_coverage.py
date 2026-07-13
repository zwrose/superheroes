"""Task 23 (#397): sweep the spec requirement → task map and confirm each FR/UFR is covered."""

import os
import re

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
LIB_TESTS = os.path.join(ROOT, "plugins", "superheroes", "lib", "tests")


def _read(rel):
    path = os.path.join(ROOT, rel)
    assert os.path.isfile(path), f"missing coverage artifact: {rel}"
    with open(path, encoding="utf-8") as f:
        return f.read()


def _lib_test(name):
    return _read(os.path.join("plugins", "superheroes", "lib", "tests", name))


# requirement id -> (artifact paths relative to ROOT, marker regexes that must appear)
REQ_COVERAGE = {
    "FR-1": (
        [
            "plugins/superheroes/rubric/review-base.md",
            "plugins/superheroes/lib/tests/showrunner_doc_severity_frame_smoke.js",
            "plugins/superheroes/lib/tests/test_skill_shape.py",
            "plugins/superheroes/reference/review-loop.md",
        ],
        [r"Document-review severity", r"DOC_SEVERITY_FRAME|document-severity", r"doc_severity_addendum", r"document review"],
    ),
    "FR-2": (
        ["plugins/superheroes/lib/tests/showrunner_plan_handoff_smoke.js"],
        [r"plan-handoff", r"FR-2|hand-off"],
    ),
    "FR-3": (
        [
            "plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js",
            "plugins/superheroes/eval/produce-leaf.md",
        ],
        [r"handoff_provided", r"Hand-off from the plan review"],
    ),
    "FR-4": (
        ["plugins/superheroes/lib/tests/showrunner_tasks_routed_smoke.js"],
        [r"routed_forward"],
    ),
    "FR-5": (
        ["plugins/superheroes/lib/tests/test_tasks_routed_not_in_build.py"],
        [r"routed_tasks_finding_absent_from_build_worklist|routed forward"],
    ),
    "FR-6": (
        [
            "plugins/superheroes/lib/tests/test_review_round_policy.py",
            "plugins/superheroes/lib/tests/showrunner_confirmation_economics_smoke.js",
        ],
        [r"doc_mode", r"confirmation"],
    ),
    "FR-7": (
        ["plugins/superheroes/lib/tests/showrunner_fronthalf_boundary_smoke.js"],
        [r"front-half-boundary"],
    ),
    "FR-8": (
        [
            "plugins/superheroes/lib/tests/showrunner_doc_cap_smoke.js",
            "plugins/superheroes/lib/tests/test_review_setup_gather_doc_mode.py",
        ],
        [r"doc-mode|doc_mode", r"max-rounds"],
    ),
    "FR-9": (
        [
            "plugins/superheroes/lib/tests/test_doc_cap_agreement.py",
            "plugins/superheroes/lib/tests/test_skill_markdown.py",
        ],
        [r"doc_mode|doc-mode|max.rounds.*3|three completed rounds"],
    ),
    "FR-10": (
        [
            "plugins/superheroes/lib/tests/test_review_park.py",
            "plugins/superheroes/lib/tests/showrunner_park_disclosure_smoke.js",
        ],
        [r"review_park|decision list|FR-10"],
    ),
    "FR-11": (
        ["plugins/superheroes/lib/phase_progress_entry.py"],
        [r"FR-11|decision list|parked"],
    ),
    "FR-12": (
        [
            "plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js",
        ],
        [r"gateForTerminal|gate.*passed|open.*blocker|accepted"],
    ),
    "FR-13": (
        [
            "plugins/superheroes/lib/tests/test_parity.py",
            "plugins/superheroes/lib/tests/test_ssot_drift.py",
        ],
        [r"parity|PARITY_TWINS|doc_mode|doc-review"],
    ),
    "FR-14": (
        [
            "plugins/superheroes/lib/tests/test_review_acceptance.py",
            "plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js",
            "plugins/superheroes/lib/tests/test_gate_write_callers.py",
        ],
        [r"acceptance|FR-14|ledger"],
    ),
    "FR-15": (
        [
            "plugins/superheroes/lib/tests/test_review_convergence.py",
            "plugins/superheroes/lib/tests/showrunner_convergence_smoke.js",
        ],
        [r"review_convergence|convergence"],
    ),
    "UFR-1": (
        [
            "plugins/superheroes/lib/tests/showrunner_plan_handoff_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_park_disclosure_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_convergence_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_acceptance_rereview_smoke.js",
        ],
        [r"UFR-1|disclos"],
    ),
    "UFR-2": (
        [
            "plugins/superheroes/lib/tests/showrunner_doc_round_retry_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_reviewer_denied_probe_smoke.js",
        ],
        [r"UFR-2|retry|denied"],
    ),
    "UFR-3": (
        ["plugins/superheroes/lib/tests/test_review_handoff.py"],
        [r"fail.closed|scrub|handoff"],
    ),
    "UFR-4": (
        ["plugins/superheroes/lib/tests/showrunner_doc_round_retry_smoke.js"],
        [r"UFR-4|two attempts|retry"],
    ),
    "UFR-5": (
        [
            "plugins/superheroes/lib/tests/showrunner_handoff_delivery_smoke.js",
            "plugins/superheroes/lib/tests/showrunner_fronthalf_phase_smoke.js",
        ],
        [r"UFR-5|un-recorded|handoff_provided|gate write"],
    ),
}


@pytest.mark.parametrize("req_id", sorted(REQ_COVERAGE))
def test_requirement_has_landed_coverage(req_id):
    """Each spec FR/UFR named in Task 23 maps to at least one on-disk test artifact."""
    paths, markers = REQ_COVERAGE[req_id]
    corpus = "\n".join(_read(p) for p in paths)
    missing = [m for m in markers if not re.search(m, corpus, re.IGNORECASE)]
    assert not missing, f"{req_id}: no artifact matched {missing!r} in {paths}"


def test_doc_review_smokes_registered_in_pytest_wrapper():
    """Task 12+ smokes from the convergence epic are wired into the node-smoke pytest gate."""
    text = _lib_test("test_showrunner_node_smokes.py")
    required = [
        "showrunner_doc_severity_frame_smoke.js",
        "showrunner_doc_cap_smoke.js",
        "showrunner_plan_handoff_smoke.js",
        "showrunner_handoff_delivery_smoke.js",
        "showrunner_tasks_routed_smoke.js",
        "showrunner_park_disclosure_smoke.js",
        "showrunner_convergence_smoke.js",
        "showrunner_acceptance_rereview_smoke.js",
        "showrunner_doc_round_retry_smoke.js",
        "showrunner_fronthalf_argsel_smoke.js",
    ]
    absent = [s for s in required if s not in text]
    assert not absent, f"SHOWRUNNER_SMOKES missing: {absent}"
