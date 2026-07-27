"""CONVENTIONS §11 single-source-of-truth drift guards for cross-boundary facts that
are re-typed across the surviving Python libs and schema literals.

Each guard reads the authoritative home (or, where no single named home exists, pins
the shared vocabulary across every enumerated copy-holder) and **fails closed** on an
unparseable literal — so a change to the truth breaks CI in every copy-holder rather
than letting them silently diverge (the PR #205 class). Per the §11.2 caveat, every
test enumerates its copy-holders explicitly: a NEW copy must be added here.

Clusters covered (post spine-retirement #468 — execution-spine JS twins
`showrunner.js` / `build_phase.js` / `model_tier.js` / `engine_pref.js` and the
`task_review` / `review_loop_plan` / `journal` producers are retired, so their clusters
are gone with them; no lib/*.js copy-holders remain):
- Severity tiers + BLOCKING / SEV_RANK / NON_BLOCKING  (home: rubric/review-base.md)
- Terminal-state vocabulary                            (home: panel_tally.py)
- Codex translation/effort policy (docs + adapter default) (home: engine_pref.py)
- Model-registry ids + family vocabulary                (home: model_registry.py)
- Base-guard refusal reasons                           (home: review_base_guard.py)

The reviewer-roster and docs-location clusters live in their topical sibling guards
(test_dispatch_tables.py, test_definition_doc.py).
"""
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.abspath(os.path.join(HERE, "..", ".."))


def _read(rel):
    with open(os.path.join(PLUGIN, rel), encoding="utf-8") as f:
        return f.read()


def _one(matches, name, label, shape):
    assert len(matches) == 1, (
        "%s: expected exactly one `const %s = %s`, found %d (a rename, or a reformat "
        "the drift parser can't read)" % (label, name, shape, len(matches)))
    return matches[0]


def test_one_raises_on_zero_matches():
    with pytest.raises(AssertionError, match=r"doc\.md: expected exactly one"):
        _one([], "FOO", "doc.md", "...")


def test_one_raises_on_two_matches():
    with pytest.raises(AssertionError, match=r"doc\.md: expected exactly one"):
        _one(["a", "b"], "FOO", "doc.md", "...")


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
    Critical<Important<Minor<Nit rank are re-typed across the surviving Python copy-holders.
    All must agree with the rubric home — the ordered tier vocabulary and the blocking set are
    both READ from review-base.md (the enum + the verdict mapping)."""
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
    import verification

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
    assert list(verification._TIERS) == tiers, "verification._TIERS order/vocab drift"
    assert verification._SEV_RANK == rank, "verification._SEV_RANK drift"
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

    # The rubric's shared findings schema (the panel reviewers' single source) must forbid
    # the foreign scale, not just name the tiers — the live panel escape emitted high/medium/low.
    assert "closed enum" in text and "no `high`/`medium`/`low`" in text, (
        "review-base.md: findings schema must forbid off-scale severities (the panel-vocabulary fix)")


# --- Cluster 3b: Codex translation/effort policy (docs + adapter default) -----

def test_complete_codex_policy_single_sourced():
    """The Python home (engine_pref.py) owns the Codex translation/effort policy; the
    engine_adapter no-tier default and the owner-facing docs must agree with it."""
    import engine_pref
    import model_registry

    expected_ids = set(model_registry.codex_models())
    for rel in ("../../CONVENTIONS.md",  # README is a high-level overview in v2 — no longer a Codex-policy copy-holder (policy home: engine_pref.py; CONVENTIONS + configure refs remain drift-checked)
                "skills/configure/reference/set-up.md",
                "skills/configure/reference/view-and-tune.md"):
        doc = _read(rel)
        documented_ids = set(re.findall(r"gpt-5\.6-(?:sol|terra)", doc))
        assert documented_ids == expected_ids, "%s Codex model IDs drifted from model_registry" % rel
        mapping_text = _one(re.findall(r"Codex tier map:\s*([^\n]+(?:\n(?!\s*\n)[^\n]+)?)", doc),
                            "Codex tier map", rel, "tier=model, ...")
        documented_map = dict(re.findall(
            r"(haiku|sonnet|opus)=(gpt-5\.6-(?:sol|terra))", mapping_text))
        assert documented_map == engine_pref.CODEX_MODEL_BY_TIER, (
            "%s Codex tier map drifted from engine_pref.py" % rel)


# --- Cluster: base-guard refusal reasons (review_base_guard → round-driver.md) -

def _reason_tokens_from_home():
    """Every module-level REASON_* string constant in review_base_guard.py."""
    import review_base_guard

    reasons = {}
    for name in dir(review_base_guard):
        if not name.startswith("REASON_"):
            continue
        val = getattr(review_base_guard, name)
        assert isinstance(val, str) and val, (
            "review_base_guard.%s must be a non-empty str, got %r" % (name, val))
        reasons[name] = val
    assert reasons, "review_base_guard: no REASON_* constants discovered (rename/refactor?)"
    assert len(reasons) >= 15, (
        "review_base_guard: expected >= 15 REASON_* constants, found %d"
        % len(reasons))
    return reasons


def test_base_guard_reason_tokens_in_round_driver_doc():
    """§11: round-driver.md is the hand-maintained copy of review_base_guard's REASON_* tokens."""
    reasons = _reason_tokens_from_home()
    doc = _read("skills/review-code/reference/round-driver.md")
    missing = [name for name, token in sorted(reasons.items()) if token not in doc]
    assert not missing, (
        "round-driver.md missing refusal token(s) from review_base_guard.py "
        "(plain substring `token in doc` — a shorter token could be falsely satisfied "
        "if only a longer confusable substring appears, e.g. base-repo-mismatch vs "
        "base-repo-root-mismatch; each token value must appear literally): %r"
        % [(n, reasons[n]) for n in missing])


# --- Cluster 4: negative drift scans (concrete model ids must not leak) ------

_CONCRETE_MODEL_TOKENS = (
    "gpt-5.6-terra",
    "gpt-5.6-sol",
    "gpt-5.5",
    "gpt-5.6-luna",
    "composer-2.5",
    "composer-2.5-fast",
    "cursor-grok-4.5",
    "haiku-4.5",
    "sonnet-5",
    "opus-4.8",
    "opus-5",
    "fable-5",
    "claude-fable-5-thinking",
)

_RETIRED_MODEL_TOKENS = (
    "gpt-5.5",
    "gpt-5.6-luna",
    "composer-2.5-fast",
    "claude-fable-5-thinking",
    "opus-4.8",
)


def _md_files_excluding_configure(*roots):
    """Every *.md under the given plugin-relative roots, skipping skills/configure/."""
    for root in roots:
        base = os.path.join(PLUGIN, root)
        for dirpath, _dirs, files in os.walk(base):
            rel_dir = os.path.relpath(dirpath, PLUGIN)
            if rel_dir == "skills" and "configure" in _dirs:
                _dirs.remove("configure")
            if rel_dir.startswith(os.path.join("skills", "configure")):
                continue
            for name in files:
                if name.endswith(".md"):
                    yield os.path.join(rel_dir, name)


def test_no_concrete_model_id_in_charters_or_skills():
    """Charters and skills reference roles, never concrete model ids — only configure/ may."""
    hits = []
    for rel in _md_files_excluding_configure("agents", "rubric", "skills"):
        text = _read(rel)
        for token in _CONCRETE_MODEL_TOKENS:
            if token in text:
                hits.append((rel, token))
    assert not hits, "concrete model id in charter/skill (use roles, not models): %r" % hits


# --- Cluster 5: model-registry copies (ids + family vocabulary) --------------

def test_concrete_model_tokens_cover_every_registered_model():
    """§11: `_CONCRETE_MODEL_TOKENS` is a hand-maintained copy of the registry's ids — the leak scan
    it drives silently stops covering a model the moment someone registers one without adding it
    here. Read the home and assert coverage (retired ids may stay in the tuple; the check is
    one-directional)."""
    import model_registry

    registered = {m for v in model_registry.vendors() for m in model_registry._MODELS[v]}
    missing = registered - set(_CONCRETE_MODEL_TOKENS)
    assert not missing, "registered model id absent from _CONCRETE_MODEL_TOKENS: %r" % sorted(missing)


def test_conventions_family_keys_match_the_registry():
    """§11: CONVENTIONS' family-key enumeration is a doc copy of the registry's family vocabulary.
    The `cursor` key outlived the family itself until a review caught it (#651) — read the home."""
    import model_registry

    home = {rec["family"] for v in model_registry.vendors() for rec in model_registry._MODELS[v].values()}
    text = _read("../../CONVENTIONS.md")
    m = re.search(r"\*\*Family keys\*\*[^(]*\(([^)]*)\)", text)
    assert m, "CONVENTIONS: family-key enumeration not found"
    documented = set(re.findall(r"`([a-z0-9-]+)`", m.group(1)))
    assert documented == home, (
        "CONVENTIONS family-key list %r drifted from model_registry families %r"
        % (sorted(documented), sorted(home)))


def _scan_retired_tokens(rel_paths):
    hits = []
    for rel in rel_paths:
        text = _read(rel)
        for token in _RETIRED_MODEL_TOKENS:
            if token in text:
                hits.append((rel, token))
    return hits


def test_retired_model_tokens_absent_from_lib():
    """Retired model tokens must not reappear as literals outside model_registry.py."""
    lib_dir = os.path.join(PLUGIN, "lib")
    _skip = {"model_registry.py"}
    py_paths = [
        os.path.join("lib", name)
        for name in os.listdir(lib_dir)
        if name.endswith(".py") and name not in _skip
    ]
    doc_paths = [
        "../../CONVENTIONS.md",
        "skills/configure/reference/set-up.md",
        "skills/configure/reference/view-and-tune.md",
    ]
    hits = _scan_retired_tokens(py_paths + doc_paths)
    assert not hits, "retired model token reappeared: %r" % hits
