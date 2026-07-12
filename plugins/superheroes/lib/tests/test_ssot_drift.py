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
- Accepted-model set (KNOWN_MODELS)                    (home: model_tier_overrides.py)
- Accepted-engine set (ENGINES)                        (home: engine_pref.py)
- haltKind cap-halt discriminator                      (home: review_loop_plan.py)

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
    import review_memory
    import review_telemetry

    # Python copy-holders (read at runtime) — every BLOCKING constant. #276/#291 consolidated the
    # blocking + Critical PARTITION decisions into two predicates (circuit_breaker.is_blocking /
    # is_critical); circuit_breaker._blocking, task_review, panel_tally (the panel gate), loop_state
    # (review-code's continuation gate), loop_synthesis, review_panel_shell, review_loop_plan and
    # loop_plan_common (the confirmation re-arm/park feeders + gate) all route through them now. The
    # remaining sets below are the drift-guarded canonical vocabulary declarations. review_memory /
    # review_telemetry keep a case-sensitive set BY DESIGN — non-gating recurrence/telemetry consumers
    # (a case mismatch there mis-counts a stat, it does not pass a defect through a gate).
    py_blocking = {
        "circuit_breaker.BLOCKING": set(circuit_breaker.BLOCKING),
        "loop_plan_common.BLOCKING": set(loop_plan_common.BLOCKING),
        "panel_tally.BLOCKING": set(panel_tally.BLOCKING),
        "review_memory.BLOCKING": set(review_memory.BLOCKING),
        "review_telemetry._BLOCKING": set(review_telemetry._BLOCKING),
    }
    for label, val in py_blocking.items():
        assert val == blocking, "%s drifted from the rubric blocking set %r" % (label, blocking)

    assert list(loop_state._ALL_SEVERITIES) == tiers, "loop_state._ALL_SEVERITIES order/vocab drift"
    assert list(loop_synthesis._TIERS) == tiers, "loop_synthesis._TIERS order/vocab drift"
    assert panel_tally.SEV_RANK == rank, "panel_tally.SEV_RANK drift"

    # #276: the shared FAIL-CLOSED blocking predicate has ONE home (circuit_breaker). Its non-blocking
    # set (the ONLY tiers that demote; everything else fails closed to blocking) must equal the rubric's
    # non-blocking tiers, case-folded — Python home + JS twin. The predicate's cross-language behavior
    # (canonical + foreign/mis-cased/degenerate corpus) is pinned by the isBlocking parity twin.
    non_blocking_lc = {t.lower() for t in non_blocking}
    assert {s.lower() for s in circuit_breaker._NON_BLOCKING} == non_blocking_lc, (
        "circuit_breaker.py _NON_BLOCKING drifted from the rubric non-blocking tiers %r" % non_blocking)
    assert circuit_breaker.is_blocking("Critical") and circuit_breaker.is_blocking("Important")
    assert not circuit_breaker.is_blocking("Minor") and not circuit_breaker.is_blocking("Nit")
    assert circuit_breaker.is_blocking("blocker") and circuit_breaker.is_blocking(None)  # fail closed

    # #291: the shared TIER-specific Critical predicate (case-normalized) — the confirmation re-arm/park
    # gate reads it. Distinct from is_blocking: Important blocks but is not Critical. Cross-language
    # behavior is pinned by the isCritical parity twin; here we assert it exists and case-normalizes.
    assert circuit_breaker.is_critical("Critical") and circuit_breaker.is_critical("critical")
    assert not circuit_breaker.is_critical("Important") and not circuit_breaker.is_critical("blocker")
    assert not circuit_breaker.is_critical(None) and not circuit_breaker.is_critical("")

    # JS copy-holders (regex-extracted, fail-closed).
    cb = _read(os.path.join("lib", "circuit_breaker.js"))
    assert _js_str_set(cb, "BLOCKING", "circuit_breaker.js") == blocking
    assert {s.lower() for s in _js_str_set(cb, "_NON_BLOCKING", "circuit_breaker.js")} == non_blocking_lc, (
        "circuit_breaker.js _NON_BLOCKING drifted from the rubric non-blocking tiers %r" % non_blocking)
    rmjs = _read(os.path.join("lib", "review_memory.js"))
    assert _js_str_set(rmjs, "BLOCKING", "review_memory.js") == blocking
    lsjs = _read(os.path.join("lib", "loop_synthesis.js"))
    assert _js_str_set(lsjs, "_TIERS", "loop_synthesis.js") == vocab
    ptjs = _read(os.path.join("lib", "panel_tally.js"))
    assert _js_str_set(ptjs, "BLOCKING", "panel_tally.js") == blocking
    assert _js_rank_map(ptjs, "SEV_RANK", "panel_tally.js") == rank

    # Schema enum copy (showrunner.js findings-severity enum).
    srjs = _read(os.path.join("lib", "showrunner.js"))
    enum = re.findall(r"severity:\s*\{\s*enum:\s*(\[[^\]]+\])", srjs)
    assert len(enum) == 1, "showrunner.js: expected exactly one severity enum, found %d" % len(enum)
    assert ast.literal_eval(enum[0]) == tiers, "showrunner.js severity enum drift"

    # #276: the per-task AND whole-branch final reviewers' schema enums must speak the SAME tier
    # vocabulary — the live escape (2026-07-06) was reviewers emitting a foreign scale
    # (blocker/critical/high) the partition then demoted. build_phase.js now carries two such enums
    # (REVIEW_TASK_SCHEMA + FINAL_REVIEW_SCHEMA); EVERY one must equal the rubric tiers.
    bp = _read(os.path.join("lib", "build_phase.js"))
    bp_enums = re.findall(r"severity:\s*\{\s*enum:\s*(\[[^\]]+\])", bp)
    assert len(bp_enums) == 2, "build_phase.js: expected two severity enums, found %d" % len(bp_enums)
    for e in bp_enums:
        assert ast.literal_eval(e) == tiers, "build_phase.js severity enum drift: %s" % e
    # The reviewer PROMPTS (not just the schemas) name the closed vocabulary so an off-scale label is
    # forbidden at the source. Anchor to the exact prompt sentence — a whole-file `\bNit\b` search would
    # pass on the schema enum alone (the mutant that reverts the prompt hint must NOT survive). Both the
    # per-task and whole-branch reviewer prompts carry it, so require both occurrences.
    prompt_sentence = "severity MUST be one of Critical, Important, Minor, Nit (no other scale)"
    assert bp.count(prompt_sentence) == 2, (
        "build_phase.js: expected the closed-severity prompt sentence in both reviewer prompts (per-task "
        "+ whole-branch), found %d" % bp.count(prompt_sentence))
    # The rubric's shared findings schema (the panel reviewers' single source) must also forbid the
    # foreign scale, not just name the tiers — the live panel escape emitted high/medium/low.
    assert "closed enum" in text and "no `high`/`medium`/`low`" in text, (
        "review-base.md: findings schema must forbid off-scale severities (the panel-vocabulary fix)")


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


# --- Cluster 5: accepted-model set (KNOWN_MODELS) ----------------------------

def test_known_models_single_sourced():
    """CONVENTIONS §11: the accepted-model set is validated Python-side in
    model_tier_overrides.KNOWN_MODELS (the home) and re-typed JS-side in model_tier.js
    (the freeze-consume merge boundary validates a snapshot's pinned model against it).
    A model added/renamed in one place must break CI in the other, so a valid new model
    isn't silently refused at the merge boundary (or a stale one silently pinned). Order
    is not semantically load-bearing for a membership set, so compare as sets."""
    import model_tier_overrides
    home = list(model_tier_overrides.KNOWN_MODELS)  # ('haiku', 'sonnet', 'opus', 'fable')

    mt = _read(os.path.join("lib", "model_tier.js"))
    assert set(_js_str_array(mt, "KNOWN_MODELS", "model_tier.js")) == set(home), (
        "model_tier.js KNOWN_MODELS drifted from model_tier_overrides.KNOWN_MODELS")


# --- Cluster 6: accepted-engine set (ENGINES) --------------------------------

def test_engines_single_sourced():
    """CONVENTIONS §11: the accepted-engine set is re-typed across the engine_pref
    pair — engine_pref.py's authoritative ENGINES tuple (the resolver that falls open to
    'claude' on anything outside it) and engine_pref.js's ENGINES array (the same
    membership gate on the Workflow side). An engine added/renamed in one place must break
    CI in the other, so a valid new engine isn't silently rejected on one side (or a stale
    one silently still-accepted). Order is not semantically load-bearing for a membership
    set, so compare as sets — mirrors the KNOWN_MODELS cluster."""
    import engine_pref
    home = list(engine_pref.ENGINES)  # ('claude', 'codex', 'cursor')

    js = _read(os.path.join("lib", "engine_pref.js"))
    assert set(_js_str_array(js, "ENGINES", "engine_pref.js")) == set(home), (
        "engine_pref.js ENGINES drifted from engine_pref.py ENGINES")


# --- Cluster 7: haltKind cap-halt discriminator (#381) -----------------------

def _halt_kind_literals_home():
    """Home: review_loop_plan.py tally-round verdict assembly — the four halt_kind
    assignments inside `if terminal == "halted":`. Read from the producer, not
    restated."""
    text = _read(os.path.join("lib", "review_loop_plan.py"))
    m = re.search(
        r'if terminal == "halted":\s+'
        r'if verify_red:\s+halt_kind = "([^"]+)"\s+'
        r'elif fix_status == "failed":\s+halt_kind = "([^"]+)"\s+'
        r'elif breaker_halt and brk\.get\("reason"\) == "max-iterations":.*?'
        r'halt_kind = \("([^"]+)" if gate == "blocking" and confidence == "high"\s+'
        r'else "([^"]+)"\)',
        text, re.DOTALL)
    assert m, (
        "review_loop_plan.py: #381 halt_kind assignment block not found "
        "(drift or reformat)")
    return [m.group(1), m.group(2), m.group(3), m.group(4)]


def _js_halt_kind_routing_literals(text, label):
    """`haltKind` / `fr.haltKind` comparisons and assignments in JS copy-holders."""
    literals = re.findall(
        r"(?:fr\.)?haltKind\s*(?:===|!==|=)\s*'([^']+)'", text)
    assert literals, "%s: no haltKind routing literals found (drift or reformat)" % label
    return set(literals)


def _js_halt_kind_assertion_literals(text, label):
    """`assert.strictEqual(...haltKind, 'kind', ...)` in JS smoke tests."""
    literals = re.findall(r"haltKind,\s*'([^']+)'", text)
    return set(literals)


def test_halt_kind_vocabulary_single_sourced():
    """CONVENTIONS §11: the #381 haltKind cap-halt discriminator is produced by
    review_loop_plan.py and consumed by build_phase.js (routing + downgrade) and
    pinned in JS smokes. A rename on the producer must break CI in every
    copy-holder rather than silently mis-routing the handoff."""
    home = _halt_kind_literals_home()
    home_set = set(home)

    bp = _read(os.path.join("lib", "build_phase.js"))
    bp_literals = _js_halt_kind_routing_literals(bp, "build_phase.js")
    assert bp_literals == home_set, (
        "build_phase.js haltKind routing literals %r drifted from review_loop_plan.py home %r"
        % (bp_literals, home_set))

    js_test_holders = [
        ("lib/tests/build_phase_engine_smoke.js", "build_phase_engine_smoke.js"),
        ("lib/tests/build_phase_final_review_smoke.js", "build_phase_final_review_smoke.js"),
    ]
    for rel, label in js_test_holders:
        text = _read(rel)
        test_literals = _js_halt_kind_assertion_literals(text, label)
        assert test_literals, "%s: expected haltKind assertion literals" % label
        assert test_literals <= home_set, (
            "%s haltKind assertion literals %r drifted from review_loop_plan.py home %r"
            % (label, test_literals, home_set))


# --- Cluster 8: uncertified flag (#212 / #381) -----------------------------

def _uncertified_producer_home():
    """Home: review_loop_plan.py sets `uncertified` when gate is cannot-certify."""
    text = _read(os.path.join("lib", "review_loop_plan.py"))
    assert 'if gate == "cannot-certify":' in text and 'out["uncertified"] = True' in text, (
        "review_loop_plan.py: uncertified flag producer block not found (drift or reformat)")


def _js_uncertified_routing_literals(text, label):
    """`uncertified` comparisons on verdict/fr in JS copy-holders."""
    literals = re.findall(r"(?:fr\.|verdict\.)uncertified", text)
    assert literals, "%s: no uncertified routing references found (drift or reformat)" % label
    return len(literals)


def test_uncertified_flag_single_sourced():
    """CONVENTIONS §11: the uncertified flag is produced by review_loop_plan.py and consumed
    by build_phase.js (park + fix-dispatch guard) and review_panel_shell.js (verdict copy).
    A rename on the producer must break CI in every copy-holder."""
    _uncertified_producer_home()

    bp = _read(os.path.join("lib", "build_phase.js"))
    assert _js_uncertified_routing_literals(bp, "build_phase.js") >= 2, (
        "build_phase.js must guard both buildPhase park and runFinalReview fix dispatch on uncertified")

    shell = _read(os.path.join("lib", "review_panel_shell.js"))
    assert 'decided.uncertified' in shell and 'verdictOut.uncertified' in shell, (
        "review_panel_shell.js must copy the decider's uncertified flag onto the verdict")


# --- Cluster 9: journal event vocabulary (#397) ----------------------------

def test_journal_event_types_known_to_renderers():
    """CONVENTIONS §11: journal.EVENT_TYPES is the append writer's single source; run_watch and
    run_readout each carry a known-type map so a new event type can't be added to the journal
    without updating the renderers (the #397 doc-review routing + convergence vocabulary)."""
    import journal
    import run_readout
    import run_watch
    home = journal.EVENT_TYPES
    assert home <= run_watch.KNOWN_JOURNAL_EVENT_TYPES, (
        "run_watch.KNOWN_JOURNAL_EVENT_TYPES missing journal types: %r"
        % (home - run_watch.KNOWN_JOURNAL_EVENT_TYPES))
    assert home <= run_readout.KNOWN_JOURNAL_EVENT_TYPES, (
        "run_readout.KNOWN_JOURNAL_EVENT_TYPES missing journal types: %r"
        % (home - run_readout.KNOWN_JOURNAL_EVENT_TYPES))
