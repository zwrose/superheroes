"""Parity suite: Python oracle + JS twin + self-enforcement checks.

Each entry in PARITY_TWINS:  (twin_file, twin_fn, py_module, py_fn)
Each entry in JS_ONLY_TWINS: (twin_file, twin_fn)  — no Python oracle (hand-authored goldens).
PARITY_TARGET_MODULES: the exhaustive list of twin .js files (without extension) that must be
parity-tested.  Self-enforcement clause (c) cross-checks this against bundle_showrunner.js MODULES.
"""
import importlib
import json
import os
import re
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Registry — append new entries here as each twin task lands
# ---------------------------------------------------------------------------

# (twin_file_stem, twin_fn, py_module, py_fn)
PARITY_TWINS = [
    ("phase_step", "decide", "phase_step", "decide"),
    ("ci_status", "classify", "ci_status", "classify"),
    ("model_tier", "resolveModel", "model_tier", "resolve_model"),
    ("circuit_breaker", "normalizeTitle", "circuit_breaker", "normalize_title"),
    ("circuit_breaker", "findingIdentity", "circuit_breaker", "finding_identity"),
    ("circuit_breaker", "checkCircuitBreaker", "circuit_breaker", "check_circuit_breaker"),
    ("loop_state", "decide", "loop_state", "decide"),
    ("loop_synthesis", "consume", "loop_synthesis", "consume"),
    ("panel_tally", "compileFindings", "panel_tally", "compile_findings"),
    ("panel_tally", "roundGate", "panel_tally", "round_gate"),
    ("panel_tally", "presentDeferred", "panel_tally", "present_deferred"),
    ("panel_tally", "decideTerminal", "panel_tally", "decide_terminal"),
    ("recover", "reconcile", "recover", "reconcile"),
    ("recover", "prAction", "recover", "pr_action"),
    ("recover", "rearmAction", "recover", "rearm_action"),
    ("front_half", "gateForTerminal", "front_half", "gate_for_terminal"),
    ("front_half", "isUsableDraft", "front_half", "is_usable_draft"),
    ("front_half", "renderRunOutcome", "front_half", "render_run_outcome"),
    ("build_progress", "reconcile", "build_progress", "reconcile"),
    ("worker_recovery", "decide", "worker_recovery", "decide"),
    ("task_review", "decide", "task_review", "decide"),
]

# (twin_file_stem, twin_fn) — no Python oracle; goldens are hand-authored
JS_ONLY_TWINS = [
    ("verify_gate", "classify"),
]

# The exhaustive list of twin module stems; clause (c) cross-checks against bundler MODULES.
PARITY_TARGET_MODULES = ["phase_step", "ci_status", "verify_gate", "model_tier", "circuit_breaker", "loop_state", "loop_synthesis", "panel_tally", "recover", "front_half", "build_progress", "worker_recovery", "task_review"]

# Python fns that return a tuple whose JS twin returns an object — map (py_mod, py_fn) to field names.
# Used by test_python_oracle to normalize the result before comparison with an object fixture.
_TUPLE_TO_DICT_FIELDS = {
    ("panel_tally", "round_gate"): ["gate", "confidence", "incomplete"],
    ("panel_tally", "decide_terminal"): ["terminal", "reason"],
}

# Bundled modules that are NOT twins (spine shells, not pure deciders).
BUNDLED_NON_TWINS = {
    "showrunner.js",
    "review_panel_shell.js",
    "build_phase.js",
    "test_pilot_phase.js",
    "courier_exec.js",
    "pr_comment_scrub.js",
    "test_pilot_deciders.js",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.dirname(_TESTS_DIR)
_BUNDLE_JS = os.path.join(_LIB_DIR, "bundle_showrunner.js")


def _fixture_dir(twin_stem, fn):
    return os.path.join(_TESTS_DIR, "parity", twin_stem, fn)


def _load_cases(twin_stem, fn):
    d = _fixture_dir(twin_stem, fn)
    cases = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".json"):
            with open(os.path.join(d, name)) as f:
                cases.append((name, json.load(f)))
    return cases


def _run_node_twin(twin_stem, fn):
    """Run parity_runner.js for the given twin/fn; return (returncode, stderr)."""
    runner = os.path.join(_TESTS_DIR, "parity_runner.js")
    result = subprocess.run(
        ["node", runner, twin_stem, fn],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stderr.strip()


# ---------------------------------------------------------------------------
# Python oracle tests (PARITY_TWINS only)
# ---------------------------------------------------------------------------
def _oracle_params():
    params = []
    for twin_stem, twin_fn, py_mod, py_fn in PARITY_TWINS:
        for case_name, case in _load_cases(twin_stem, twin_fn):
            params.append(pytest.param(py_mod, py_fn, case, id=f"{twin_stem}/{twin_fn}/{case_name}"))
    return params


@pytest.mark.parametrize("py_mod,py_fn,case", _oracle_params())
def test_python_oracle(py_mod, py_fn, case):
    """Python pure function must return expected for each fixture input."""
    mod = importlib.import_module(py_mod)
    fn = getattr(mod, py_fn)
    got = fn(*case["input"])
    # Normalize: Python tuples serialise to JSON arrays; compare as list when expected is a list.
    if isinstance(got, tuple) and isinstance(case["expected"], list):
        got = list(got)
    # Normalize: some fns return a tuple whose JS twin returns an object; convert to dict.
    elif isinstance(got, tuple) and isinstance(case["expected"], dict):
        fields = _TUPLE_TO_DICT_FIELDS.get((py_mod, py_fn))
        if fields:
            got = dict(zip(fields, got))
    assert got == case["expected"], f"oracle mismatch: got {got!r}, expected {case['expected']!r}"


# ---------------------------------------------------------------------------
# JS twin tests (all twins)
# ---------------------------------------------------------------------------
def _twin_params():
    params = []
    for twin_stem, twin_fn, _py_mod, _py_fn in PARITY_TWINS:
        params.append(pytest.param(twin_stem, twin_fn, id=f"{twin_stem}/{twin_fn}"))
    for twin_stem, twin_fn in JS_ONLY_TWINS:
        params.append(pytest.param(twin_stem, twin_fn, id=f"{twin_stem}/{twin_fn}"))
    return params


@pytest.mark.parametrize("twin_stem,twin_fn", _twin_params())
def test_js_twin(twin_stem, twin_fn):
    """JS twin must produce expected output for all fixture cases (node parity_runner.js)."""
    rc, stderr = _run_node_twin(twin_stem, twin_fn)
    assert rc == 0, f"parity_runner.js exited {rc}:\n{stderr}"


# ---------------------------------------------------------------------------
# Self-enforcement checks (clauses a, b, c)
# ---------------------------------------------------------------------------
def test_self_enforcement_all_twins_have_fixtures():
    """Clause (a): every registered twin/fn must have a non-empty fixtures dir."""
    all_twins = [(s, f) for s, f, *_ in PARITY_TWINS] + list(JS_ONLY_TWINS)
    missing = []
    for twin_stem, fn in all_twins:
        d = _fixture_dir(twin_stem, fn)
        if not os.path.isdir(d) or not any(n.endswith(".json") for n in os.listdir(d)):
            missing.append(f"{twin_stem}/{fn}")
    assert not missing, f"Registered twins with empty/missing fixtures dirs: {missing}"


def test_self_enforcement_target_modules_match_twins():
    """Clause (b): PARITY_TARGET_MODULES == set of twin stems across PARITY_TWINS + JS_ONLY_TWINS."""
    registered_stems = set()
    for twin_stem, _fn, *_ in PARITY_TWINS:
        registered_stems.add(twin_stem)
    for twin_stem, _fn in JS_ONLY_TWINS:
        registered_stems.add(twin_stem)
    target = set(PARITY_TARGET_MODULES)
    assert target == registered_stems, (
        f"PARITY_TARGET_MODULES {target} != twin stems {registered_stems}"
    )


def test_self_enforcement_bundled_modules_are_parity_targets():
    """Clause (c): every MODULES entry in bundle_showrunner.js that is not BUNDLED_NON_TWINS must
    be in PARITY_TARGET_MODULES.  This makes it impossible to bundle a new twin without registering it."""
    with open(_BUNDLE_JS) as f:
        src = f.read()
    # Parse the MODULES array — find the first occurrence of `const MODULES = [...]`
    m = re.search(r"const\s+MODULES\s*=\s*\[([^\]]*)\]", src)
    assert m, "Could not find MODULES array in bundle_showrunner.js"
    raw = m.group(1)
    # Extract quoted module names
    bundled = set(re.findall(r"'([^']+)'|\"([^\"]+)\"", raw))
    bundled_names = {a or b for a, b in bundled}
    non_twins = BUNDLED_NON_TWINS
    need_parity = bundled_names - non_twins
    target = set(PARITY_TARGET_MODULES)
    # Convert need_parity stems (strip .js) for comparison
    need_parity_stems = {n.replace(".js", "") for n in need_parity}
    unlisted = need_parity_stems - target
    assert not unlisted, (
        f"Bundled modules missing from PARITY_TARGET_MODULES: {unlisted}. "
        "Add them to PARITY_TARGET_MODULES or BUNDLED_NON_TWINS."
    )
