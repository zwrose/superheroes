"""CONVENTIONS §11 single-source-of-truth drift guards for cross-boundary facts that
are re-typed across the Python libs, the Workflow JS, and schema literals.

Each guard reads the authoritative home (or, where no single named home exists, pins
the shared vocabulary across every enumerated copy-holder) and **fails closed** on an
unparseable literal — so a change to the truth breaks CI in every copy-holder rather
than letting them silently diverge (the PR #205 class). Per the §11.2 caveat, every
test enumerates its copy-holders explicitly: a NEW copy must be added here.

Clusters covered (sweep follow-up of #231):
- Severity tiers + BLOCKING / SEV_RANK / NON_BLOCKING  (home: rubric/review-base.md)
- Task-review required verdicts                        (home: task_review.py)
- Terminal-state vocabulary                            (home: panel_tally.py)
- Route vocabulary full/quick    (shared vocabulary: preflight.py + showrunner.js)

The generated showrunner.bundle.js copies of these facts are guarded separately by
test_bundle_drift. The reviewer-roster, docs-location, and Failure-Mode-taxonomy
clusters live in their topical sibling guards (test_dispatch_tables.py,
test_definition_doc.py, test_taxonomy_sync.py).
"""
import ast
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))


def _read(rel):
    with open(os.path.join(PLUGIN, rel), encoding="utf-8") as f:
        return f.read()


# --- fail-closed JS literal readers (CONVENTIONS §11.2) ----------------------
# Each asserts exactly one match and a well-formed literal; parsing nothing raises
# (never returns an empty value that would make a downstream equality pass vacuously).
# The sibling test_dispatch_tables.py carries the same fail-closed contract for its own
# roster reader (`_parse_js_const_str_list`); these are kept per-file rather than shared
# because the literal SHAPES differ (array / Set / object-map here vs a plain array
# there) — connascence of algorithm, accepted for test helpers. The fail-closed behavior
# below is exercised by `test_js_readers_fail_closed`.

def _one(matches, name, label, shape):
    assert len(matches) == 1, (
        "%s: expected exactly one `const %s = %s`, found %d (a rename, or a reformat "
        "the drift parser can't read)" % (label, name, shape, len(matches)))
    return matches[0]


def _js_str_array(text, name, label):
    """`const NAME = ['a', 'b', ...]` → list[str]."""
    m = _one(re.findall(r"\bconst\s+%s\s*=\s*(\[[^\]]+\])" % re.escape(name), text),
             name, label, "[...]")
    value = ast.literal_eval(m)
    assert isinstance(value, list) and value and all(
        isinstance(x, str) and x for x in value), (
        "%s: `%s` must be a non-empty list of strings" % (label, name))
    return value


def _js_str_set(text, name, label):
    """`const NAME = new Set(['a', ...])` → set[str]."""
    m = _one(re.findall(r"\bconst\s+%s\s*=\s*new Set\((\[[^\]]+\])\)" % re.escape(name), text),
             name, label, "new Set([...])")
    value = ast.literal_eval(m)
    assert isinstance(value, list) and value and all(
        isinstance(x, str) and x for x in value), (
        "%s: `%s` Set must contain a non-empty list of strings" % (label, name))
    return set(value)


def _js_rank_map(text, name, label):
    """`const NAME = { Key: 0, Key2: 1, ... }` (unquoted keys, int values) → dict[str,int]."""
    m = _one(re.findall(r"\bconst\s+%s\s*=\s*\{([^}]+)\}" % re.escape(name), text),
             name, label, "{ ... }")
    pairs = re.findall(r"([A-Za-z_]\w*)\s*:\s*(\d+)", m)
    assert pairs, "%s: `%s` object literal has no `key: int` pairs" % (label, name)
    return {k: int(v) for k, v in pairs}


@pytest.mark.parametrize("reader, text, name, match", [
    # missing literal → zero matches
    (_js_str_array, "const OTHER = ['a']\n", "A", "expected exactly one"),
    (_js_str_set, "const OTHER = new Set(['a'])\n", "B", "expected exactly one"),
    (_js_rank_map, "const OTHER = { A: 0 }\n", "M", "expected exactly one"),
    # declared twice → ambiguous
    (_js_str_array, "const A = ['a']\nconst A = ['b']\n", "A", "found 2"),
    (_js_str_set, "const B = new Set(['a'])\nconst B = new Set(['b'])\n", "B", "found 2"),
    # not the expected shape (a bare value, not a Set/array/object)
    (_js_str_set, "const B = 1\n", "B", "expected exactly one"),
    # malformed contents
    (_js_str_array, "const A = ['a', 2]\n", "A", "non-empty list of strings"),
    (_js_str_set, "const B = new Set(['a', 3])\n", "B", "non-empty list of strings"),
    (_js_rank_map, "const M = {  }\n", "M", "no `key: int` pairs"),
])
def test_js_readers_fail_closed(reader, text, name, match):
    """§11.2: the JS literal readers are the trust anchor for every drift guard in this
    file — parsing nothing must RAISE, never return an empty/partial value that would let
    a `== home` assertion pass vacuously. Mirrors the sibling fail-closed tests
    (test_dispatch_tables.py, test_acceptance_fixture.py). Without these, a regression
    that defeats fail-closed would ship undetected (the PR #205 class)."""
    with pytest.raises(AssertionError, match=match):
        reader(text, name, "<test>")


# --- Cluster 1: severity tiers + blocking partition + rank order -------------

def _rubric_severity_tiers():
    """Home: the ordered severity vocabulary declared in the rubric findings schema
    (`"severity": "Critical | Important | Minor | Nit"`), cross-checked against the
    Severity-tiers table so the rubric's own two statements can't disagree."""
    text = _read(os.path.join("rubric", "review-base.md"))
    m = re.search(r'"severity":\s*"([A-Z][A-Za-z |]*)"', text)
    assert m, "rubric: findings-schema severity enum not found"
    tiers = [t.strip() for t in m.group(1).split("|")]
    assert tiers == ["Critical", "Important", "Minor", "Nit"], tiers
    for t in tiers:  # every tier is a bolded row in the Severity tiers table
        assert re.search(r"\|\s*\*\*%s\*\*\s*\|" % re.escape(t), text), (
            "rubric: severity tier %r missing from the Severity tiers table" % t)
    return tiers


def _rubric_blocking_tiers(text, tiers):
    """Which tiers BLOCK a verdict, read from the rubric's verdict-mapping section: a
    tier blocks iff `≥1 <tier>` yields a non-READY label (`0 Critical, ≥1 Important →
    REVISE`, `≥1 Critical → MAJOR`; `Minor/Nit → READY` do not block). Read from the home
    rather than assumed positionally, so the blocking set traces to the rubric (§11.3)."""
    blocking = {t for t in tiers if re.search(r"≥\s*1\s+%s\b" % re.escape(t), text)}
    assert blocking, "rubric: no blocking tiers derived from the verdict mapping"
    return blocking


def test_severity_vocabulary_is_single_sourced():
    """CONVENTIONS §11: the severity tiers, the blocking/non-blocking partition, and the
    Critical<Important<Minor<Nit rank are re-typed across ~13 Python + JS copy-holders.
    All must agree with the rubric home — the ordered tier vocabulary and the blocking
    set are both READ from review-base.md (the enum + the verdict mapping), not assumed."""
    text = _read(os.path.join("rubric", "review-base.md"))
    tiers = _rubric_severity_tiers()          # ['Critical','Important','Minor','Nit']
    vocab = set(tiers)
    blocking = _rubric_blocking_tiers(text, tiers)   # read from the verdict mapping
    non_blocking = vocab - blocking
    rank = {t: i for i, t in enumerate(tiers)}

    import circuit_breaker
    import loop_state
    import loop_synthesis
    import loop_plan_common
    import panel_tally
    import review_loop_plan
    import review_memory
    import review_telemetry

    # Python copy-holders (read at runtime) — every BLOCKING constant.
    py_blocking = {
        "circuit_breaker.BLOCKING": set(circuit_breaker.BLOCKING),
        "loop_state._BLOCKING": set(loop_state._BLOCKING),
        "loop_synthesis._BLOCKING": set(loop_synthesis._BLOCKING),
        "loop_plan_common.BLOCKING": set(loop_plan_common.BLOCKING),
        "panel_tally.BLOCKING": set(panel_tally.BLOCKING),
        "review_loop_plan.BLOCKING": set(review_loop_plan.BLOCKING),
        "review_memory.BLOCKING": set(review_memory.BLOCKING),
        "review_telemetry._BLOCKING": set(review_telemetry._BLOCKING),
    }
    for label, val in py_blocking.items():
        assert val == blocking, "%s drifted from the rubric blocking set %r" % (label, blocking)

    assert list(loop_state._ALL_SEVERITIES) == tiers, "loop_state._ALL_SEVERITIES order/vocab drift"
    assert list(loop_synthesis._TIERS) == tiers, "loop_synthesis._TIERS order/vocab drift"
    assert set(loop_synthesis._NON_BLOCKING) == non_blocking, "loop_synthesis._NON_BLOCKING drift"
    assert panel_tally.SEV_RANK == rank, "panel_tally.SEV_RANK drift"

    # JS copy-holders (regex-extracted, fail-closed).
    cb = _read(os.path.join("lib", "circuit_breaker.js"))
    assert _js_str_set(cb, "BLOCKING", "circuit_breaker.js") == blocking
    rps = _read(os.path.join("lib", "review_panel_shell.js"))
    assert _js_str_set(rps, "BLOCKING", "review_panel_shell.js") == blocking
    rmjs = _read(os.path.join("lib", "review_memory.js"))
    assert _js_str_set(rmjs, "BLOCKING", "review_memory.js") == blocking
    lsjs = _read(os.path.join("lib", "loop_synthesis.js"))
    assert _js_str_set(lsjs, "_TIERS", "loop_synthesis.js") == vocab
    assert _js_str_set(lsjs, "_BLOCKING", "loop_synthesis.js") == blocking
    assert _js_str_set(lsjs, "_NON_BLOCKING", "loop_synthesis.js") == non_blocking
    ptjs = _read(os.path.join("lib", "panel_tally.js"))
    assert _js_str_set(ptjs, "BLOCKING", "panel_tally.js") == blocking
    assert _js_rank_map(ptjs, "SEV_RANK", "panel_tally.js") == rank

    # Schema enum copy (showrunner.js findings-severity enum).
    srjs = _read(os.path.join("lib", "showrunner.js"))
    enum = re.findall(r"severity:\s*\{\s*enum:\s*(\[[^\]]+\])", srjs)
    assert len(enum) == 1, "showrunner.js: expected exactly one severity enum, found %d" % len(enum)
    assert ast.literal_eval(enum[0]) == tiers, "showrunner.js severity enum drift"

    # #276: the per-task reviewer's schema enum + prompt must speak the SAME tier vocabulary — the
    # live escape (2026-07-06) was the reviewer emitting a foreign scale (blocker/critical/high) the
    # partition then demoted. Schema enum:
    bp = _read(os.path.join("lib", "build_phase.js"))
    bp_enum = re.findall(r"severity:\s*\{\s*enum:\s*(\[[^\]]+\])", bp)
    assert len(bp_enum) == 1, "build_phase.js: expected exactly one severity enum, found %d" % len(bp_enum)
    assert ast.literal_eval(bp_enum[0]) == tiers, "build_phase.js REVIEW_TASK_SCHEMA severity enum drift"
    # Prompt shape hint names every tier (so a reviewer sees the allowed values, not just the schema).
    for t in tiers:
        assert re.search(r"\b%s\b" % re.escape(t), bp), (
            "build_phase.js: per-task reviewer prompt/schema does not name severity tier %r" % t)

    # #276: task_review's non-blocking set (the ONLY tiers that demote; everything else fails closed
    # to blocking) must equal the rubric's non-blocking tiers, case-folded. Python home + JS twin.
    import task_review
    non_blocking_lc = {t.lower() for t in non_blocking}
    assert {s.lower() for s in task_review._NON_BLOCKING} == non_blocking_lc, (
        "task_review.py _NON_BLOCKING drifted from the rubric non-blocking tiers %r" % non_blocking)
    trjs = _read(os.path.join("lib", "task_review.js"))
    assert {s.lower() for s in _js_str_set(trjs, "_NON_BLOCKING", "task_review.js")} == non_blocking_lc, (
        "task_review.js _NON_BLOCKING drifted from the rubric non-blocking tiers %r" % non_blocking)


# --- Cluster 2: task-review required verdicts --------------------------------

def test_task_review_required_verdicts_single_sourced():
    """CONVENTIONS §11: the required task-review verdict keys are re-typed in
    task_review.js and the build_phase.js result schema. Home: task_review.py."""
    import task_review
    home = list(task_review.REQUIRED_VERDICTS)   # ('spec_compliance', 'code_quality')
    assert home == ["spec_compliance", "code_quality"], home

    js = _read(os.path.join("lib", "task_review.js"))
    assert _js_str_array(js, "REQUIRED_VERDICTS", "task_review.js") == home

    bp = _read(os.path.join("lib", "build_phase.js"))
    req = re.findall(r"required:\s*(\['spec_compliance'[^\]]*\])", bp)
    assert len(req) == 1, "build_phase.js: verdicts schema `required` not found uniquely"
    assert ast.literal_eval(req[0]) == home, "build_phase.js verdicts `required` drift"
    for v in home:  # each verdict also has a properties entry
        assert re.search(r"\b%s:\s*\{\s*enum:" % re.escape(v), bp), (
            "build_phase.js: verdict %r missing its schema properties entry" % v)


# --- Cluster 3: terminal-state vocabulary ------------------------------------

def test_terminal_vocabulary_single_sourced():
    """CONVENTIONS §11: the action→terminal map is re-typed in panel_tally.js.
    Home: panel_tally.py `_ACTION_TO_TERMINAL`."""
    import panel_tally
    home = dict(panel_tally._ACTION_TO_TERMINAL)
    js = _read(os.path.join("lib", "panel_tally.js"))
    m = re.findall(r"\bconst\s+_ACTION_TO_TERMINAL\s*=\s*\{([^}]+)\}", js)
    assert len(m) == 1, "panel_tally.js: `_ACTION_TO_TERMINAL` literal not found uniquely"
    js_map = {k: v for k, v in re.findall(r"(\w+)\s*:\s*'([^']+)'", m[0])}
    assert js_map, "panel_tally.js: `_ACTION_TO_TERMINAL` parsed no `key: 'value'` pairs"
    assert js_map == home, "panel_tally.js `_ACTION_TO_TERMINAL` drifted from panel_tally.py"


# --- Cluster 4: route vocabulary (full / quick) ------------------------------

def test_route_vocabulary_single_sourced():
    """CONVENTIONS §11: the route vocabulary {'full','quick'} has no single named home —
    preflight.py emits it and showrunner.js resolveIntake recognizes it. Pin the
    vocabulary at both canonical decision expressions so a rename/new route in either
    (a producer emitting a value the consumer won't recognize) fails closed."""
    routes = {"full", "quick"}

    pf = _read(os.path.join("lib", "preflight.py"))
    norm = re.search(
        r'route\s*=\s*"quick"\s*if\s*probes\.get\("route"\)\s*==\s*"quick"\s*else\s*"full"', pf)
    assert norm, "preflight.py: route normalizer expression not found (drift or reformat)"
    assert set(re.findall(r'"(quick|full)"', norm.group(0))) == routes

    sr = _read(os.path.join("lib", "showrunner.js"))
    derived = re.search(
        r"const derived = specPresent \? '(\w+)' : \(tasksPresent \? '(\w+)' : null\)", sr)
    assert derived, "showrunner.js: resolveIntake `derived` route expression not found"
    assert set(derived.groups()) == routes
    declared = re.search(
        r"const declared = \(explicit === '(\w+)' \|\| explicit === '(\w+)'\)", sr)
    assert declared, "showrunner.js: resolveIntake `declared` route expression not found"
    assert set(declared.groups()) == routes
