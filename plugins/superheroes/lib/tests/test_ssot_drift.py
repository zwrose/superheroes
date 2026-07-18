"""CONVENTIONS §11 single-source-of-truth drift guards for cross-boundary facts that
are re-typed across the surviving Python libs, their Workflow-JS twins, and schema literals.

Each guard reads the authoritative home (or, where no single named home exists, pins
the shared vocabulary across every enumerated copy-holder) and **fails closed** on an
unparseable literal — so a change to the truth breaks CI in every copy-holder rather
than letting them silently diverge (the PR #205 class). Per the §11.2 caveat, every
test enumerates its copy-holders explicitly: a NEW copy must be added here.

Clusters covered (post spine-retirement #468 — the execution-spine copy-holders
`showrunner.js` / `build_phase.js` / `model_tier.js` / `engine_pref.js` and the
`task_review` / `review_loop_plan` / `journal` producers are retired, so their clusters
are gone with them):
- Severity tiers + BLOCKING / SEV_RANK / NON_BLOCKING  (home: rubric/review-base.md)
- Terminal-state vocabulary                            (home: panel_tally.py)
- Codex translation/effort policy (docs + adapter default) (home: engine_pref.py)

The reviewer-roster and docs-location clusters live in their topical sibling guards
(test_dispatch_tables.py, test_definition_doc.py).
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
    a `== home` assertion pass vacuously."""
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
    """Which tiers BLOCK a verdict, read from the rubric's verdict-mapping section."""
    blocking = {t for t in tiers if re.search(r"≥\s*1\s+%s\b" % re.escape(t), text)}
    assert blocking, "rubric: no blocking tiers derived from the verdict mapping"
    return blocking


def test_severity_vocabulary_is_single_sourced():
    """CONVENTIONS §11: the severity tiers, the blocking/non-blocking partition, and the
    Critical<Important<Minor<Nit rank are re-typed across the surviving Python + JS
    copy-holders. All must agree with the rubric home — the ordered tier vocabulary and
    the blocking set are both READ from review-base.md (the enum + the verdict mapping)."""
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

    # Python copy-holders (read at runtime) — every BLOCKING constant.
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

    # #276: the shared FAIL-CLOSED blocking predicate has ONE home (circuit_breaker).
    non_blocking_lc = {t.lower() for t in non_blocking}
    assert {s.lower() for s in circuit_breaker._NON_BLOCKING} == non_blocking_lc, (
        "circuit_breaker.py _NON_BLOCKING drifted from the rubric non-blocking tiers %r" % non_blocking)
    assert circuit_breaker.is_blocking("Critical") and circuit_breaker.is_blocking("Important")
    assert not circuit_breaker.is_blocking("Minor") and not circuit_breaker.is_blocking("Nit")
    assert circuit_breaker.is_blocking("blocker") and circuit_breaker.is_blocking(None)  # fail closed

    # #291: the shared TIER-specific Critical predicate (case-normalized).
    assert circuit_breaker.is_critical("Critical") and circuit_breaker.is_critical("critical")
    assert not circuit_breaker.is_critical("Important") and not circuit_breaker.is_critical("blocker")
    assert not circuit_breaker.is_critical(None) and not circuit_breaker.is_critical("")

    # JS copy-holders (regex-extracted, fail-closed) — the surviving review-panel twins.
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

    # The rubric's shared findings schema (the panel reviewers' single source) must forbid
    # the foreign scale, not just name the tiers — the live panel escape emitted high/medium/low.
    assert "closed enum" in text and "no `high`/`medium`/`low`" in text, (
        "review-base.md: findings schema must forbid off-scale severities (the panel-vocabulary fix)")


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


# --- Cluster 3b: Codex translation/effort policy (docs + adapter default) -----

def test_complete_codex_policy_single_sourced():
    """The Python home (engine_pref.py) owns the Codex translation/effort policy; the
    engine_adapter no-tier default and the owner-facing docs must agree with it."""
    import engine_pref

    adapter = _read(os.path.join("lib", "engine_adapter.py"))
    assert '_CODEX_MODEL = _CODEX_MODEL_BY_TIER["opus"]' in adapter, (
        "engine_adapter's no-tier default must derive from the authoritative tier map")

    expected_ids = set(engine_pref.CODEX_MODELS)
    for rel in ("../../README.md", "../../CONVENTIONS.md",
                "skills/configure/reference/set-up.md",
                "skills/configure/reference/view-and-tune.md"):
        doc = _read(rel)
        documented_ids = set(re.findall(r"gpt-5\.(?:5|6-(?:sol|terra|luna))", doc))
        assert documented_ids == expected_ids, "%s Codex model IDs drifted from engine_pref.py" % rel
        mapping_text = _one(re.findall(r"Codex tier map:\s*([^\n]+(?:\n(?!\s*\n)[^\n]+)?)", doc),
                            "Codex tier map", rel, "tier=model, ...")
        documented_map = dict(re.findall(
            r"(haiku|sonnet|opus|fable)=(gpt-5\.6-(?:sol|terra|luna))", mapping_text))
        assert documented_map == engine_pref.CODEX_MODEL_BY_TIER, (
            "%s Codex tier map drifted from engine_pref.py" % rel)
        for model in engine_pref.CODEX_MAX_UNSUPPORTED_MODELS:
            assert re.search(r"%s.{0,80}(?:\+|with).{0,20}`?max`?" % re.escape(model), doc,
                             flags=re.IGNORECASE | re.DOTALL), (
                "%s max-effort compatibility guidance drifted for %s" % (rel, model))
