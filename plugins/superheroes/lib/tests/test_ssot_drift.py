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
- Omission floor + PR-body marker semantics (§10.7)   (home: CONVENTIONS.md §10.7)
- `configRead` CLI field set                             (home: preflight_probe.py)

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


# --- Cluster: review payload shape tokens (engine_adapter → auto-fix-loop.md) ---


def _review_payload_shape_tokens_from_home():
    import engine_adapter

    return set(engine_adapter.REVIEW_PAYLOAD_SHAPES)


def _review_payload_shape_tokens_from_auto_fix_loop_doc(doc):
    """The payloadShape `parsed` enumeration in auto-fix-loop.md — scoped to that block only."""
    m = re.search(
        r"`parsed`\s*\(one of\s*(.*?)\)\s*,\s*`topLevelKeys`",
        doc,
        re.DOTALL,
    )
    assert m, (
        "auto-fix-loop.md: payloadShape `parsed` enumeration not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"`([^`]+)`", m.group(1)))
    assert tokens, (
        "auto-fix-loop.md: payloadShape `parsed` enumeration parsed to zero tokens "
        "(regex drift or empty enumeration?)"
    )
    return tokens


def test_review_payload_shape_tokens_in_auto_fix_loop_doc():
    """§11: auto-fix-loop.md restates the payloadShape `parsed` vocabulary from engine_adapter."""
    home = _review_payload_shape_tokens_from_home()
    doc = _read("skills/review-code/reference/auto-fix-loop.md")
    doc_tokens = _review_payload_shape_tokens_from_auto_fix_loop_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "auto-fix-loop.md payloadShape `parsed` vocabulary drift from "
        "engine_adapter.REVIEW_PAYLOAD_SHAPES — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


# --- Cluster: configRead CLI field set (preflight_probe → preflight.md §B) ---


def _config_read_fields_from_home():
    import preflight_probe

    return set(preflight_probe.CONFIG_READ_FIELDS)


def _config_read_fields_from_preflight_doc(doc):
    """The `configRead` field enumeration in preflight.md §B — scoped to that paragraph only."""
    m = re.search(
        r"`configRead`\s+object\s+[—-]\s*`\{([^}]+)\}`",
        doc,
    )
    assert m, (
        "preflight.md: configRead field enumeration not found "
        "(moved or reworded?)"
    )
    tokens = {t.strip() for t in m.group(1).split(",")}
    assert tokens, (
        "preflight.md: configRead field enumeration parsed to zero tokens "
        "(regex drift or empty enumeration?)"
    )
    return tokens


def test_config_read_fields_in_preflight_doc():
    """§11: preflight.md §B restates the `configRead` field vocabulary from preflight_probe."""
    home = _config_read_fields_from_home()
    doc = _read("skills/configure/reference/preflight.md")
    doc_tokens = _config_read_fields_from_preflight_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "preflight.md configRead field vocabulary drift from "
        "preflight_probe.CONFIG_READ_FIELDS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


# --- Cluster: schema refusal tokens (engine_dispatch → auto-fix-loop.md) ---


def _schema_refusal_tokens_from_home():
    import engine_dispatch

    return set((
        engine_dispatch.SCHEMA_REFUSAL_MISSING,
        engine_dispatch.SCHEMA_REFUSAL_UNREADABLE,
        engine_dispatch.SCHEMA_REFUSAL_NOT_FINDINGS_SHAPED,
    ))


def _schema_refusal_tokens_from_auto_fix_loop_doc(doc):
    """The `--schema-path` refusal `detail` enumeration in auto-fix-loop.md — scoped to that block only."""
    m = re.search(
        r"`detail`\s+is one of\s+(.*?)\)\s+with\s+`attempts:",
        doc,
        re.DOTALL,
    )
    assert m, (
        "auto-fix-loop.md: schema refusal detail enumeration not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"`([^`]+)`", m.group(1)))
    assert tokens, (
        "auto-fix-loop.md: schema refusal detail enumeration parsed to zero tokens "
        "(regex drift or empty enumeration?)"
    )
    return tokens


def test_schema_refusal_tokens_in_auto_fix_loop_doc():
    """§11: auto-fix-loop.md restates the schema-path refusal detail tokens from engine_dispatch."""
    home = _schema_refusal_tokens_from_home()
    doc = _read("skills/review-code/reference/auto-fix-loop.md")
    doc_tokens = _schema_refusal_tokens_from_auto_fix_loop_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "auto-fix-loop.md schema refusal detail vocabulary drift from "
        "engine_dispatch.py — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


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


# --- Cluster: omission floor (CONVENTIONS §10.7 authoritative home) ----------

def _conventions_section_10_7():
    text = _read("../../CONVENTIONS.md")
    m = re.search(
        r"### 10\.7 PR-body honesty markers.*?(?=\n### |\n## 11\.)",
        text,
        re.DOTALL,
    )
    assert m, "CONVENTIONS §10.7 section not found (renumbered or moved?)"
    return m.group(0)


def _workhorse_section_11():
    text = _read("skills/workhorse/SKILL.md")
    m = re.search(r"## 11\. Hand back the ready PR.*?(?=\n## 12\.)", text, re.DOTALL)
    assert m, "workhorse SKILL.md §11 not found"
    return m.group(0)


def _review_discipline_ship_phase_honesty():
    text = _read("rubric/review-discipline.md")
    m = re.search(r"## Ship-phase honesty.*?(?=\n## )", text, re.DOTALL)
    assert m, "review-discipline.md Ship-phase honesty section not found"
    return m.group(0)


def _review_code_step_8():
    text = _read("skills/review-code/SKILL.md")
    m = re.search(
        r"8\. \*\*PR-body honesty check.*?(?=\n9\. |\nDetermine the verdict)",
        text,
        re.DOTALL,
    )
    assert m, "review-code SKILL.md step 8 not found"
    return m.group(0)


# CONVENTIONS §10.7 carries two distinct marker families, and only one of them propagates.
#
# The OMISSION FLOOR family is a PR-body contract every copy-holder restates, so §11 drift
# applies to it: review-discipline.md, workhorse §11 and review-code step 8 must each carry it.
_FLOOR_MARKERS = frozenset({
    "<!-- superheroes:build-record -->",
    "<!-- superheroes:degradations -->",
})
# The VET-RECEIPT family (#672 ratified, built in #694) is advisor-authored AT VET, after
# handback: two of the three live in the vet-receipt comment, not the PR body. It is
# deliberately NOT propagated to the copy-holders — a build's pre-handback review-code runs in
# BRANCH mode, before any PR body or vet exists, so requiring these of review-code step 8 would
# manufacture a finding nothing can satisfy (CONVENTIONS §13: no machinery without a consumer).
_VET_RECEIPT_MARKERS = frozenset({
    "<!-- superheroes:vet-receipt -->",
    "<!-- superheroes:pending-proposals -->",
    "<!-- superheroes:advisor-vet -->",
})
# Closed world over BOTH families: any new marker added to §10.7 fails this test on purpose,
# forcing a decision about whether it propagates. Never relax this to a subset check.
_SECTION_10_7_MARKERS = _FLOOR_MARKERS | _VET_RECEIPT_MARKERS


def _omission_floor_expectations_from_home(home):
    """Parse §10.7's three floor rows and missing-marker rule from the home, validate the
    floor marker family against that rule, and return the floor family for copy-holders."""
    m = re.search(
        r"under `## What we're accepting`:\s*\n\n(.*?)\n\nA \*\*missing\*\*",
        home,
        re.DOTALL,
    )
    assert m, "§10.7 omission floor rows not found (moved or reworded?)"
    block = m.group(1)
    rows = re.findall(
        r"^\d+\.\s+(.+?)(?=^\d+\.\s+|\Z)",
        block,
        re.MULTILINE | re.DOTALL,
    )
    assert len(rows) == 3, "expected three omission floor rows, got %r" % rows
    row_terms = []
    for row in rows:
        terms = [t.strip() for t in re.findall(r"\*\*([^*]+)\*\*", row)]
        assert terms, "no bold load-bearing terms in floor row: %r" % row
        row_terms.append(terms)
    markers = re.findall(r"(<!-- superheroes:[^>]+ -->)", home)
    assert set(markers) == set(_SECTION_10_7_MARKERS), (
        "unexpected §10.7 marker set: %r — a new marker must be sorted into "
        "_FLOOR_MARKERS (propagates to every copy-holder) or _VET_RECEIPT_MARKERS "
        "(advisor-authored at vet; must not be required of the copy-holders)" % markers
    )
    # v12: family membership must be DERIVED from the home, never trusted from the constant.
    # §10.7's missing-marker rule names exactly the floor family, so moving a literal between
    # _FLOOR_MARKERS and _VET_RECEIPT_MARKERS now FAILS instead of silently dropping a
    # copy-holder requirement.
    rule = re.search(
        r"A \*\*missing\*\*.*?is \*\*itself\*\* a review finding",
        home,
        re.DOTALL,
    )
    assert rule, "§10.7 missing-marker rule not found (moved or reworded?)"
    floor_from_home = set(re.findall(r"(<!-- superheroes:[^>]+ -->)", rule.group(0)))
    assert floor_from_home == set(_FLOOR_MARKERS), (
        "§10.7's missing-marker rule names %r but _FLOOR_MARKERS is %r — the floor family "
        "must be derived from the home, not reclassified in the test" % (
            sorted(floor_from_home), sorted(_FLOOR_MARKERS))
    )
    assert re.search(
        r"A \*\*missing\*\* `<!-- superheroes:build-record -->`.*?review finding",
        home,
        re.DOTALL,
    ), "§10.7 missing-marker-as-finding rule not found"
    assert re.search(
        r"marker absence and \*\*None\*\* are different states",
        home,
    ), "§10.7 None vs marker-absence rule not found"
    # Only the floor family propagates to the copy-holders (see _VET_RECEIPT_MARKERS).
    return row_terms, sorted(_FLOOR_MARKERS)


def _assert_omission_floor_matches_home(copy_text, label, home):
    row_terms, markers = _omission_floor_expectations_from_home(home)
    lower = copy_text.lower()
    missing = []
    for i, terms in enumerate(row_terms, 1):
        for term in terms:
            if term.lower() not in lower:
                missing.append("row%d term %r" % (i, term))
    for marker in markers:
        if marker not in copy_text:
            missing.append("marker %r" % marker)
    if not re.search(
        r"missing[\s\S]{0,400}?superheroes:build-record[\s\S]{0,400}?"
        r"(?:review finding|itself[\s\S]{0,40}?finding|same finding shape)",
        copy_text,
        re.IGNORECASE,
    ):
        missing.append("missing-marker-as-finding rule")
    if "none" not in lower or ("absent" not in lower and "absence" not in lower):
        missing.append("None vs marker absence")
    assert not missing, (
        "%s: omission floor substance drift — missing: %r" % (label, missing)
    )


def test_omission_floor_matches_conventions_10_7():
    """§11: the omission floor and marker semantics in every copy-holder match CONVENTIONS §10.7."""
    home = _conventions_section_10_7()

    copies = (
        ("rubric/review-discipline.md (Ship-phase honesty)", _review_discipline_ship_phase_honesty()),
        ("skills/workhorse/SKILL.md §11", _workhorse_section_11()),
        ("skills/review-code/SKILL.md step 8", _review_code_step_8()),
    )
    for label, text in copies:
        _assert_omission_floor_matches_home(text, label, home)


def test_vet_receipt_markers_match_conventions_10_7():
    """§11 + §12.3: the vet-receipt marker literals agree across every hand-maintained copy.

    These three markers are grep anchors — the advisor's own backstops key on their exact
    bytes — so a rename in one copy that misses another silently breaks the anchor. §10.7
    names vet-receipt.md as the authoritative home; this binds the copies to it.
    """
    home = _conventions_section_10_7()
    in_home = set(re.findall(r"(<!-- superheroes:[^>]+ -->)", home)) - set(_FLOOR_MARKERS)
    assert in_home == set(_VET_RECEIPT_MARKERS), (
        "CONVENTIONS §10.7 names vet-receipt markers %r but _VET_RECEIPT_MARKERS is %r"
        % (sorted(in_home), sorted(_VET_RECEIPT_MARKERS))
    )

    # The authoritative home's own `## Markers` section — NOT the whole file: the `## Skeleton`
    # section below it repeats two of the three literals (advisor-vet lives in the PR body, not the
    # receipt), so a whole-file scan would pass vacuously for either of those two.
    receipt = _read("skills/showrunner/reference/vet-receipt.md")
    section = re.search(r"^## Markers$\n(.*?)(?=^## )", receipt, re.MULTILINE | re.DOTALL)
    assert section, "vet-receipt.md `## Markers` section not found (moved or renamed?)"
    in_receipt = set(re.findall(r"(<!-- superheroes:[^>]+ -->)", section.group(1)))
    assert in_receipt == set(_VET_RECEIPT_MARKERS), (
        "vet-receipt.md `## Markers` lists %r but CONVENTIONS §10.7 names %r — the marker "
        "literals drifted between the home and the section that documents them"
        % (sorted(in_receipt), sorted(_VET_RECEIPT_MARKERS))
    )

    # DERIVED, never hand-typed. A literal spelled out here passes the one drift this test exists to
    # catch: a coordinated rename landing in §10.7, the receipt and the constant but NOT the charter
    # leaves the charter stale while the assertion happily finds its own stale copy (verified live —
    # the whole suite passed in exactly that state). So instead: every marker the charter carries must
    # be one §10.7 names, and the charter must carry at least one of the vet family it tells the
    # advisor to stamp.
    charter = _read("skills/showrunner/SKILL.md")
    charter_markers = set(re.findall(r"(<!-- superheroes:[^>]+ -->)", charter))
    stale = charter_markers - (in_home | set(_FLOOR_MARKERS))
    assert not stale, (
        "showrunner/SKILL.md carries marker literal(s) %r that CONVENTIONS §10.7 does not name — "
        "a rename reached the home but not the charter" % sorted(stale)
    )
    assert charter_markers & in_home, (
        "showrunner/SKILL.md carries no vet-receipt marker literal at all — it tells the advisor to "
        "stamp one and to re-check it whenever it next reads the PR body"
    )


def _showrunner_orchestration_duty():
    """Duty 9 (Orchestration — dispatch and preflight) through the tempted-table heading."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"9\. \*\*Orchestration.*?(?=\n## When you're tempted)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner/SKILL.md duty 9 (Orchestration) not found (moved or renumbered?)"
    return m.group(0)


def _showrunner_tempted_tier_row():
    """The tempted-table row pairing account-default inheritance with the tier doctrine."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"\| \"The account default tier is fine[^|]+\|[^|]+\|",
        text,
    )
    assert m, (
        "showrunner/SKILL.md tempted-table tier row not found "
        "(moved or reworded?)"
    )
    return m.group(0)


def _launch_doctrine_builder_dispatch_section():
    """The Builder dispatch tier artifact-home section in launch-doctrine.md."""
    text = _read("rubric/launch-doctrine.md")
    m = re.search(
        r"## Builder dispatch tier \(artifact home\)\n(.*?)(?=\n## )",
        text,
        re.DOTALL,
    )
    assert m, (
        "launch-doctrine.md Builder dispatch tier (artifact home) section not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def test_showrunner_charter_carries_builder_dispatch_tier_doctrine():
    """§11: loaded advisor surfaces and the doctrine artifact home must carry the builder-dispatch
    tier rule keyed to model_registry.FABLE_NEVER_DEFAULT — builder launches default to opus; fable
    is never a launch default. A failure means the rule drifted out of a surface the advisor or
    doctrine actually loads."""
    # axis: each guarded region (duty-9 orchestration passage, tempted-table tier row, and the
    # launch-doctrine artifact home) must name engine_pref.BUILDER_DISPATCH_TIER_DEFAULT and each
    # registry-refused launch tier; partial drift in any one region alone must fail this guard.
    import engine_pref
    import model_registry

    assert model_registry.FABLE_NEVER_DEFAULT is True
    default_tier = engine_pref.BUILDER_DISPATCH_TIER_DEFAULT
    refused_tiers = set(model_registry.known_claude_models()) - set(
        model_registry.claude_dispatch_tokens()
    )
    assert refused_tiers, "expected at least one registry-refused launch tier"

    regions = (
        ("showrunner/SKILL.md duty 9 orchestration passage", _showrunner_orchestration_duty()),
        ("showrunner/SKILL.md tempted-table tier row", _showrunner_tempted_tier_row()),
        ("launch-doctrine.md artifact home", _launch_doctrine_builder_dispatch_section()),
    )

    for label, region in regions:
        lower = re.sub(r"\s+", " ", region.lower())
        assert default_tier in lower, (
            "%s missing the %s builder-launch default — "
            "sessions may let launches inherit the account default tier"
            % (label, default_tier)
        )
        for refused in sorted(refused_tiers):
            assert refused in lower, (
                "%s missing the refused launch tier %r — "
                "sessions will not see that %s is refused as a builder launch tier"
                % (label, refused, refused)
            )
            assert "never a launch default" in lower, (
                "%s missing the never-a-launch-default clause for %s"
                % (label, refused)
            )
