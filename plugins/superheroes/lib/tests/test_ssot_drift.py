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
- Wave-watch vocabulary                                  (home: wave_watch.py)
- Issue-contract vocabulary                              (home: issue_contract.py)
- Register-check vocabulary                              (home: register_check.py)

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


def test_severity_vocabulary_is_single_sourced(monkeypatch):
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
    # #820: review_telemetry now lives in eval/ (no production consumer); pin bites on
    # review_telemetry._BLOCKING drifting from the rubric's blocking tiers — reach across
    # to the eval tree so this copy-holder stays covered rather than silently unimported.
    monkeypatch.syspath_prepend(os.path.join(PLUGIN, "eval"))
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


# --- Cluster: review resultKind enum (engine_adapter → doc copies) ---


def _review_result_kind_enum_from_home():
    import engine_adapter

    return set(engine_adapter.REVIEW_RESULT_KINDS)


def _review_result_kind_tokens_from_doc_block(block):
    return set(re.findall(r"`([^`]+)`", block))


_REVIEW_RESULT_KIND_ENUM_COPY_COUNTS = {
    "skills/review-code/reference/auto-fix-loop.md": 3,
    "skills/workhorse/reference/dispatch-mechanics.md": 2,
}


def _review_result_kind_enum_copies_from_doc(doc):
    """Every resultKind enumeration copy in a doc file."""
    patterns = [
        r"\(one of\s*(.*?)\)\s*naming the payload",
        r"\(`([^`]+)` or `([^`]+)`\) naming which payload",
        r'exactly `"([^"]+)"` or `"([^"]+)"`',
    ]
    copies = []
    for pat in patterns:
        for m in re.finditer(pat, doc, re.DOTALL):
            if m.lastindex == 2:
                copies.append({m.group(1), m.group(2)})
            else:
                tokens = _review_result_kind_tokens_from_doc_block(m.group(1))
                if tokens:
                    copies.append(tokens)
    assert copies, (
        "doc: no resultKind enumeration copies found (moved or reworded?)"
    )
    return copies


def _assert_review_result_kind_enum_copies_match_home(doc_rel):
    """§11: every pinned resultKind enum copy in doc_rel matches engine_adapter."""
    home = _review_result_kind_enum_from_home()
    doc = _read(doc_rel)
    copies = _review_result_kind_enum_copies_from_doc(doc)
    expected_count = _REVIEW_RESULT_KIND_ENUM_COPY_COUNTS[doc_rel]
    assert len(copies) == expected_count, (
        "%s: expected %d resultKind enum copies, found %d "
        "(a copy dropped out of recognition or a new copy was not registered?)"
        % (doc_rel, expected_count, len(copies))
    )
    for i, doc_tokens in enumerate(copies):
        missing_from_doc = sorted(home - doc_tokens)
        extra_in_doc = sorted(doc_tokens - home)
        assert not missing_from_doc and not extra_in_doc, (
            "%s resultKind enum copy %d drift from "
            "engine_adapter.REVIEW_RESULT_KINDS — "
            "missing from doc: %r; present in doc but not in home: %r"
            % (doc_rel, i, missing_from_doc, extra_in_doc)
        )


def test_review_result_kind_enum_in_auto_fix_loop_doc():
    """§11: every resultKind enum copy in auto-fix-loop.md matches engine_adapter."""
    _assert_review_result_kind_enum_copies_match_home(
        "skills/review-code/reference/auto-fix-loop.md")


def test_review_result_kind_enum_in_dispatch_mechanics_doc():
    """§11: every resultKind enum copy in dispatch-mechanics.md matches engine_adapter."""
    _assert_review_result_kind_enum_copies_match_home(
        "skills/workhorse/reference/dispatch-mechanics.md")


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


# --- Cluster: sanitized-view diff refusal tokens (sanitized_view → auto-fix-loop.md) ---


def _sanitized_view_diff_refusal_tokens_from_home():
    text = _read("lib/sanitized_view.py")
    return set(re.findall(
        r'SanitizedViewError\("(sanitized-view-diff-[^"]+)"\)',
        text,
    ))


def _sanitized_view_diff_refusal_tokens_from_auto_fix_loop_doc(doc):
    """The six-row diff refusal table in auto-fix-loop.md — scoped to that block only."""
    m = re.search(
        r"\*\*Diff refusals\*\*.*?\n>\n> \| token \| when \|\n> \|---\|---\|\n(.*?)\n>\n",
        doc,
        re.DOTALL,
    )
    assert m, (
        "auto-fix-loop.md: sanitized-view diff refusal table not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r">\s*\|\s*`([^`]+)`\s*\|", m.group(1)))
    assert tokens, (
        "auto-fix-loop.md: sanitized-view diff refusal table parsed to zero tokens "
        "(regex drift or empty table?)"
    )
    return tokens


def test_sanitized_view_diff_refusal_tokens_in_auto_fix_loop_doc():
    """§11: auto-fix-loop.md restates sanitized_view.py diff refusal literals."""
    home = _sanitized_view_diff_refusal_tokens_from_home()
    doc = _read("skills/review-code/reference/auto-fix-loop.md")
    doc_tokens = _sanitized_view_diff_refusal_tokens_from_auto_fix_loop_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "auto-fix-loop.md sanitized-view diff refusal vocabulary drift from "
        "sanitized_view.py — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


# --- Cluster: mode refusal tokens (engine_dispatch → auto-fix-loop.md) ---


def _mode_refusal_tokens_from_home():
    import engine_dispatch

    return {v for k, v in vars(engine_dispatch).items() if k.startswith("MODE_REFUSAL_")}


def _mode_refusal_tokens_from_auto_fix_loop_doc(doc):
    """The mode-refusal table in auto-fix-loop.md — scoped to that block only."""
    m = re.search(
        r"\*\*Mode refusals\*\*.*?\n>\n> \| token \| when \|\n> \|---\|---\|\n(.*?)\n>\n",
        doc,
        re.DOTALL,
    )
    assert m, (
        "auto-fix-loop.md: mode refusal table not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r">\s*\|\s*`([^`]+)`\s*\|", m.group(1)))
    assert tokens, (
        "auto-fix-loop.md: mode refusal table parsed to zero tokens "
        "(regex drift or empty table?)"
    )
    return tokens


def test_mode_refusal_tokens_in_auto_fix_loop_doc():
    """§11: auto-fix-loop.md restates engine_dispatch.py mode refusal literals."""
    home = _mode_refusal_tokens_from_home()
    doc = _read("skills/review-code/reference/auto-fix-loop.md")
    doc_tokens = _mode_refusal_tokens_from_auto_fix_loop_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "auto-fix-loop.md mode refusal vocabulary drift from "
        "engine_dispatch.py — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


# --- Cluster: wave-watch vocabulary (wave_watch → wave-watch.md) --------------


def _wave_watch_events_from_home():
    import wave_watch

    return set(wave_watch.EVENTS)


def _wave_watch_refusals_from_home():
    import wave_watch

    return set(wave_watch.REFUSALS)


def _wave_watch_degradations_from_home():
    import wave_watch

    return set(wave_watch.DEGRADATIONS)


def _wave_watch_string_constants_by_prefix(prefix):
    """Module-level string constants named PREFIX_* — scoped to vocabulary prefixes only."""
    import wave_watch

    derived = set()
    for name in dir(wave_watch):
        if not name.startswith(prefix):
            continue
        val = getattr(wave_watch, name)
        if isinstance(val, str) and val:
            derived.add(val)
    return derived


def _wave_watch_precedence_from_home():
    """Precedence order from wave_watch.EVENT_PRECEDENCE — the tuple run() consumes."""
    import wave_watch

    return list(wave_watch.EVENT_PRECEDENCE)


def _wave_watch_precedence_from_module_docstring():
    """Precedence prose from wave_watch.py's module docstring — checked against EVENT_PRECEDENCE."""
    text = _read("lib/wave_watch.py")
    m = re.search(
        r"- Precedence:\s*(.*?)\.",
        text,
        re.DOTALL,
    )
    assert m, (
        "wave_watch.py: precedence sentence in module docstring not found "
        "(moved or reworded?)"
    )
    order = []
    for part in m.group(1).split(">"):
        token = part.strip().split()[0]
        order.append(token)
    assert order, "wave_watch.py: precedence sentence parsed to zero tokens"
    return order


def _assert_wave_watch_precedence_order_equal(label_a, order_a, label_b, order_b):
    assert len(order_a) == len(order_b), (
        "wave-watch precedence length mismatch — %s: %d tokens %r; %s: %d tokens %r"
        % (label_a, len(order_a), order_a, label_b, len(order_b), order_b)
    )
    for index, (left, right) in enumerate(zip(order_a, order_b)):
        assert left == right, (
            "wave-watch precedence order disagreement at position %d — "
            "%s has %r, %s has %r"
            % (index, label_a, left, label_b, right)
        )


def _wave_watch_verbs_from_home():
    """CLI subcommand names from argparse registration in wave_watch.py.

    Parsed from ``sub.add_parser("…")`` call sites — the parser is the executable
    source of truth and this avoids invoking ``main()`` during import.
    """
    text = _read("lib/wave_watch.py")
    verbs = re.findall(r'sub\.add_parser\("([^"]+)"\)', text)
    assert verbs, (
        "wave_watch.py: no sub.add_parser(...) registrations found "
        "(moved or reworded?)"
    )
    return set(verbs)


def _wave_watch_verbs_from_doc(doc):
    """Documented verbs from the wave-watch.md intro bullet list — scoped to that block."""
    m = re.search(
        r"It has two verbs:\n\n(.*?)\n\n\*\*The re-arm",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: verb intro bullet list not found "
        "(moved or reworded?)"
    )
    verbs = set(re.findall(r"- \*\*`([^`]+)`\*\*", m.group(1)))
    assert verbs, (
        "wave-watch.md: verb intro bullet list parsed to zero verbs "
        "(regex drift or empty list?)"
    )
    return verbs


def _wave_watch_exit_contract_from_home():
    """Exit semantics from main() — ok→N, refusal→M, one JSON line on stdout."""
    text = _read("lib/wave_watch.py")
    main_text = text[text.index("def main(argv):"):]
    m = re.search(
        r'return\s+(\d+)\s+if\s+result\.get\("ok"\)\s+else\s+(\d+)',
        main_text,
    )
    assert m, (
        "wave_watch.py: main() exit contract (ok→N, refusal→M) not found "
        "(moved or reworded?)"
    )
    assert "_emit(result)" in main_text, (
        "wave_watch.py: main() must emit one JSON line via _emit(result) "
        "(moved or reworded?)"
    )
    assert 'if args.cmd == "run"' in main_text, (
        "wave_watch.py: main() run subcommand path not found "
        "(moved or reworded?)"
    )
    assert 'elif args.cmd == "loop"' in main_text, (
        "wave_watch.py: main() loop subcommand path not found "
        "(moved or reworded?)"
    )
    return {True: int(m.group(1)), False: int(m.group(2))}


def _wave_watch_exit_contract_from_doc(doc):
    """Exit semantics from wave-watch.md — scoped to the What-it-tells-you sentence."""
    m = re.search(
        r"The watcher prints \*\*one JSON line on stdout\*\*; "
        r"\*\*exit (\d+) on an event, exit (\d+) on a refusal\*\*\.",
        doc,
    )
    assert m, (
        "wave-watch.md: exit contract sentence not found "
        "(moved or reworded?)"
    )
    return {True: int(m.group(1)), False: int(m.group(2))}


def _wave_watch_suppressible_events_from_home():
    """Suppressible event tokens from wave_watch._SUPPRESSIBLE_EVENTS."""
    import wave_watch

    return set(wave_watch._SUPPRESSIBLE_EVENTS)


def _wave_watch_suppressible_events_from_doc(doc):
    """Suppressible-event list from wave-watch.md — scoped to the lane-keyed sentence."""
    m = re.search(
        r"Only the four \*\*lane-keyed\*\* events are suppressible:\s*"
        r"(.*?)\.\s*\n`pr-set-changed`",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: suppressible-events list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"`([^`]+)`", m.group(1)))
    assert tokens, (
        "wave-watch.md: suppressible-events list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _wave_watch_exit_contract_verbs_from_doc(doc):
    """Verbs whose intro bullets state the one-JSON-line stdout contract."""
    m = re.search(
        r"It has two verbs:\n\n(.*?)\n\n\*\*The re-arm",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: verb intro bullet list not found "
        "(moved or reworded?)"
    )
    covered = set()
    for verb, body in re.findall(
        r"- \*\*`([^`]+)`\*\* — (.*?)(?=\n- \*\*|\n\n\*\*|\Z)",
        m.group(1),
        re.DOTALL,
    ):
        if re.search(r"prints one JSON line", body):
            covered.add(verb)
    assert covered, (
        "wave-watch.md: verb intro bullets parsed to zero JSON-line contracts "
        "(regex drift or reworded?)"
    )
    return covered


def _wave_watch_events_from_doc(doc):
    """The Events bullet list in wave-watch.md — scoped to that block only."""
    m = re.search(
        r"\*\*Events\*\* \(`ok=True`\):\n\n(.*?)\n\n\*\*Precedence\*\*",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: Events bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "wave-watch.md: Events bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _wave_watch_refusals_from_doc(doc):
    """The Refusals bullet list in wave-watch.md — scoped to that block only."""
    m = re.search(
        r"\*\*Refusals\*\* \(exit 1, `ok=False`\):\n\n(.*?)\n\nThe pre-loop",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: Refusals bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "wave-watch.md: Refusals bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _wave_watch_degradations_from_doc(doc):
    """The degradations bullet list in wave-watch.md — scoped to that block only."""
    m = re.search(
        r"\*\*Non-fatal degradations\*\* that ride on a result:\n\n(.*?)\n\nA degradation",
        doc,
        re.DOTALL,
    )
    assert m, (
        "wave-watch.md: degradations bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "wave-watch.md: degradations bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _wave_watch_precedence_from_doc(doc):
    """The precedence line in wave-watch.md — scoped to that paragraph only."""
    m = re.search(
        r"\*\*Precedence\*\*, highest first:\n\n(.*?)\n",
        doc,
    )
    assert m, (
        "wave-watch.md: precedence line not found "
        "(moved or reworded?)"
    )
    tokens = re.findall(r"`([^`]+)`", m.group(1))
    assert tokens, (
        "wave-watch.md: precedence line parsed to zero tokens "
        "(regex drift or empty line?)"
    )
    return tokens


def test_wave_watch_vocabulary_in_wave_watch_doc():
    """§11: wave-watch.md restates wave_watch.py vocabulary on three registry axes and precedence.

    Axis notes:
    - Events, refusals, degradations: the doc's bullet lists must match the module's EVENTS,
      REFUSALS, and DEGRADATIONS frozensets (token registries).
    - Precedence: the doc precedence line and the module docstring's precedence sentence must
      both match ``EVENT_PRECEDENCE``, the tuple ``run()`` consumes.
    """
    import wave_watch

    home_events = _wave_watch_events_from_home()
    home_refusals = _wave_watch_refusals_from_home()
    home_degradations = _wave_watch_degradations_from_home()
    home_precedence = _wave_watch_precedence_from_home()
    module_docstring_precedence = _wave_watch_precedence_from_module_docstring()
    derived_events = _wave_watch_string_constants_by_prefix("EVENT_")
    derived_refusals = _wave_watch_string_constants_by_prefix("REFUSAL_")
    derived_degradations = _wave_watch_string_constants_by_prefix("DEGRADATION_")
    assert derived_events == home_events, (
        "wave_watch EVENT_* constants drift from wave_watch.EVENTS — "
        "symmetric difference: %r"
        % sorted(derived_events ^ home_events)
    )
    assert derived_refusals == home_refusals, (
        "wave_watch REFUSAL_* constants drift from wave_watch.REFUSALS — "
        "symmetric difference: %r"
        % sorted(derived_refusals ^ home_refusals)
    )
    assert derived_degradations == home_degradations, (
        "wave_watch DEGRADATION_* constants drift from wave_watch.DEGRADATIONS — "
        "symmetric difference: %r"
        % sorted(derived_degradations ^ home_degradations)
    )
    doc = _read("skills/showrunner/reference/wave-watch.md")
    doc_events = _wave_watch_events_from_doc(doc)
    missing_events = sorted(home_events - doc_events)
    extra_events = sorted(doc_events - home_events)
    assert not missing_events and not extra_events, (
        "wave-watch.md Events vocabulary drift from wave_watch.EVENTS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_events, extra_events)
    )
    doc_refusals = _wave_watch_refusals_from_doc(doc)
    missing_refusals = sorted(home_refusals - doc_refusals)
    extra_refusals = sorted(doc_refusals - home_refusals)
    assert not missing_refusals and not extra_refusals, (
        "wave-watch.md Refusals vocabulary drift from wave_watch.REFUSALS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_refusals, extra_refusals)
    )
    doc_degradations = _wave_watch_degradations_from_doc(doc)
    missing_degradations = sorted(home_degradations - doc_degradations)
    extra_degradations = sorted(doc_degradations - home_degradations)
    assert not missing_degradations and not extra_degradations, (
        "wave-watch.md degradations vocabulary drift from wave_watch.DEGRADATIONS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_degradations, extra_degradations)
    )
    doc_precedence = _wave_watch_precedence_from_doc(doc)
    _assert_wave_watch_precedence_order_equal(
        "wave-watch.md",
        doc_precedence,
        "wave_watch.EVENT_PRECEDENCE",
        home_precedence,
    )
    _assert_wave_watch_precedence_order_equal(
        "wave_watch.py module docstring",
        module_docstring_precedence,
        "wave_watch.EVENT_PRECEDENCE",
        home_precedence,
    )
    events_registry = set(wave_watch.EVENTS)
    for label, precedence in (
        ("wave_watch.py module docstring", module_docstring_precedence),
        ("wave-watch.md", doc_precedence),
        ("wave_watch.EVENT_PRECEDENCE", home_precedence),
    ):
        prec_set = set(precedence)
        assert prec_set == events_registry and len(precedence) == len(events_registry), (
            "wave-watch precedence tokens drift from wave_watch.EVENTS — "
            "%s: precedence %r (set %r, len %d); EVENTS %r (len %d)"
            % (
                label,
                precedence,
                sorted(prec_set),
                len(precedence),
                sorted(events_registry),
                len(events_registry),
            )
        )


def test_wave_watch_verbs_in_wave_watch_doc():
    """§11: wave-watch.md documents exactly the CLI subcommands wave_watch.py accepts."""
    home_verbs = _wave_watch_verbs_from_home()
    doc = _read("skills/showrunner/reference/wave-watch.md")
    doc_verbs = _wave_watch_verbs_from_doc(doc)
    missing_from_doc = sorted(home_verbs - doc_verbs)
    extra_in_doc = sorted(doc_verbs - home_verbs)
    assert not missing_from_doc and not extra_in_doc, (
        "wave-watch.md verb vocabulary drift from wave_watch CLI — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


def test_wave_watch_exit_contract_in_wave_watch_doc():
    """§11: wave-watch.md restates main()'s exit semantics for both CLI verbs."""
    home_contract = _wave_watch_exit_contract_from_home()
    doc = _read("skills/showrunner/reference/wave-watch.md")
    doc_contract = _wave_watch_exit_contract_from_doc(doc)
    assert doc_contract == home_contract, (
        "wave-watch.md exit contract drift from wave_watch.main() — "
        "doc: %r; home: %r"
        % (doc_contract, home_contract)
    )
    home_verbs = _wave_watch_verbs_from_home()
    doc_verbs_with_json_line = _wave_watch_exit_contract_verbs_from_doc(doc)
    missing_json_line = sorted(home_verbs - doc_verbs_with_json_line)
    assert not missing_json_line, (
        "wave-watch.md exit contract missing one-JSON-line statement for verbs — "
        "home verbs without doc intro coverage: %r"
        % missing_json_line
    )


def test_wave_watch_suppressible_events_in_wave_watch_doc():
    """§11: wave-watch.md restates wave_watch._SUPPRESSIBLE_EVENTS for --ignore-event."""
    home = _wave_watch_suppressible_events_from_home()
    doc = _read("skills/showrunner/reference/wave-watch.md")
    doc_tokens = _wave_watch_suppressible_events_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "wave-watch.md suppressible-events vocabulary drift from "
        "wave_watch._SUPPRESSIBLE_EVENTS — "
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
    "cursor-grok-4.6",
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
    "cursor-grok-4.5",
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


def test_retired_model_tokens_disjoint_from_registry():
    """Retired ids must not re-register in model_registry.py — the authoritative home."""
    import model_registry

    registered_ids = {
        m for v in model_registry.vendors() for m in model_registry._MODELS[v]
    }
    registered_dispatch = {
        rec["dispatch"]
        for v in model_registry.vendors()
        for rec in model_registry._MODELS[v].values()
    }
    overlap_ids = set(_RETIRED_MODEL_TOKENS) & registered_ids
    overlap_dispatch = set(_RETIRED_MODEL_TOKENS) & registered_dispatch
    assert not overlap_ids, "retired token re-registered as model id: %r" % sorted(overlap_ids)
    assert not overlap_dispatch, (
        "retired token re-registered as dispatch value: %r" % sorted(overlap_dispatch)
    )


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


# --- Cluster: retired cursor judge id literal census (post #1008 registry retirement) ---


def _retired_grok_literal():
    """Retired cursor judge id — composed at runtime so this census file can scan itself."""
    # Deliberate self-reference avoidance: a single-string literal of the token here
    # would false-positive when this file is included in the scan paths.
    return "-".join(("cursor", "grok", "4.5"))

# I1: only these two tuple entries may mention the retired id anywhere in the repo.
_INTENTIONAL_RETIRED_GROK_SITES = (
    (os.path.join("lib", "tests", "test_ssot_drift.py"), "_CONCRETE_MODEL_TOKENS"),
    (os.path.join("lib", "tests", "test_ssot_drift.py"), "_RETIRED_MODEL_TOKENS"),
)


def _retired_grok_literal_lines_in_tuple(rel_path, const_name):
    """Line numbers inside `const_name = (...)` that carry the retired literal."""
    text = _read(rel_path)
    m = re.search(r"%s\s*=\s*\(" % re.escape(const_name), text)
    assert m, "%s: %s tuple not found" % (rel_path, const_name)
    depth = 1
    lines = []
    for lineno, line in enumerate(text[m.end():].splitlines(), start=text[:m.end()].count("\n") + 1):
        depth += line.count("(") - line.count(")")
        if _retired_grok_literal() in line:
            lines.append(lineno)
        if depth <= 0:
            break
    return lines


def _allowed_retired_grok_literal_sites():
    allowed = set()
    for rel_path, const_name in _INTENTIONAL_RETIRED_GROK_SITES:
        for lineno in _retired_grok_literal_lines_in_tuple(rel_path, const_name):
            allowed.add((rel_path, lineno))
    assert len(allowed) == 2, (
        "expected exactly two intentional %r declaration lines, found %r"
        % (_retired_grok_literal(), sorted(allowed))
    )
    return allowed


def _scan_paths_for_retired_grok_literal(paths):
    hits = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        rel = os.path.relpath(path, PLUGIN)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                if _retired_grok_literal() in line:
                    hits.append((rel, lineno))
    return hits


_BINARY_SUFFIXES = (".pyc", ".pyo")


def _is_binary_build_artifact_filename(name):
    return name.endswith(_BINARY_SUFFIXES)


def _looks_like_binary_file(path):
    """True when the file is not source text (null-byte probe)."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(8192)
    except OSError:
        return True
    return b"\x00" in chunk


def _collect_plugin_source_paths(root):
    """Repository source paths under root — build artifacts are pruned, never decoded."""
    paths = []
    for dirpath, _dirs, files in os.walk(root):
        _dirs[:] = [d for d in _dirs if d != "__pycache__"]
        for name in files:
            if _is_binary_build_artifact_filename(name):
                continue
            path = os.path.join(dirpath, name)
            if _looks_like_binary_file(path):
                continue
            paths.append(path)
    return paths


def _retired_grok_census_paths():
    conventions = os.path.normpath(os.path.join(PLUGIN, "..", "..", "CONVENTIONS.md"))
    return [conventions] + _collect_plugin_source_paths(PLUGIN)


def test_census_excludes_pycache_but_catches_source_literal(tmp_path):
    """I4: __pycache__ carrying the literal is excluded; equivalent .py source is reported."""
    literal = _retired_grok_literal()
    root = tmp_path / "plugin"
    pycache = root / "lib" / "tests" / "__pycache__"
    pycache.mkdir(parents=True)
    stale_pyc = pycache / "fixture.cpython-314.pyc"
    stale_pyc.write_bytes(b"prefix " + literal.encode() + b" suffix")

    stale_py = root / "lib" / "stale_hit.py"
    stale_py.parent.mkdir(parents=True, exist_ok=True)
    stale_py.write_text('token = "%s"\n' % literal, encoding="utf-8")

    paths = _collect_plugin_source_paths(str(root))
    assert not any("__pycache__" in p for p in paths)
    assert not any(p.endswith(".pyc") for p in paths)
    assert str(stale_pyc) not in paths
    assert str(stale_py) in paths

    scanned = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                if literal in line:
                    scanned.append((path, lineno))
    assert scanned == [(str(stale_py), 1)]


def test_retired_cursor_grok_4_5_literal_census():
    """I4: the retired cursor judge id may appear only in the two drift-guard tuple declarations (I1)."""
    allowed = _allowed_retired_grok_literal_sites()
    paths = _retired_grok_census_paths()
    hits = _scan_paths_for_retired_grok_literal(paths)
    unexpected = sorted(set(hits) - allowed)
    assert not unexpected, (
        "retired literal %r outside intentional declaration sites %r — stale hits: %r"
        % (_retired_grok_literal(), sorted(allowed), unexpected)
    )


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
# The VET-RECEIPT family (#672 ratified, built in #694) is keyed by LIFECYCLE and CONSUMER, not by
# authorship: every one of the three is written or stamped at HANDBACK OR LATER, and the only reader
# that keys on them is the advisor's own backstop. (Authorship is no longer uniform — #794 moved
# advisor-vet to builder-emitted, stamped into the empty slot with a reminder comment beneath it,
# while the other two stay advisor-authored at vet.) It is deliberately NOT propagated to the
# copy-holders — a build's pre-handback review-code runs in BRANCH mode, before any PR body or vet
# exists, so requiring these of review-code step 8 would manufacture a finding nothing can satisfy
# (CONVENTIONS §13: no machinery without a consumer).
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
        "(vet-receipt family at handback or later; must not be required of the copy-holders)"
        % markers
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


def _body_marker_from_conventions(home):
    """§10.7 distinguishes the PR-body vet marker in prose; derive it rather than typing it.

    LEDGERS.md row 236's named closure: a rename could never slip through, but a valid-for-valid
    SUBSTITUTION in a stamp instruction (advisor-vet -> vet-receipt) could, because the charter leg
    only asserted that SOME §10.7-named vet marker was present.
    """
    m = re.search(
        r"- (`<!-- superheroes:[^`]+ -->`) — the only one in the \*\*PR body\*\*",
        home,
    )
    assert m, "§10.7's PR-body marker bullet not found (moved or reworded?)"
    marker = m.group(1).strip("`")
    assert marker in _VET_RECEIPT_MARKERS, (
        "§10.7 names %r as the PR-body marker but it is not in the vet family" % marker
    )
    return marker


def _showrunner_slot_write_bullet():
    """Duty 4's 'Write your verdict into the PR's owner half' bullet — the advisor's stamp
    instruction, and the charter's copy of the owner-half register."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"   - \*\*Write your verdict into the PR's owner half\*\*.*?(?=\n   - \*\*)",
        text,
        re.DOTALL,
    )
    assert m, (
        "showrunner/SKILL.md duty-4 slot-write bullet not found (moved or reworded?)"
    )
    return m.group(0)


def _workhorse_close_link_directive_sentence():
    """§11's close-link directive sentence — the body's first line is the close link."""
    section = _workhorse_section_11()
    m = re.search(
        r"\*\*The body's first line is the close link.*?\*\*",
        section,
        re.DOTALL,
    )
    assert m, (
        "workhorse/SKILL.md §11 close-link directive sentence not found (moved or reworded?)"
    )
    return m.group(0)


def _workhorse_git_identity_section2_paragraph():
    """§2's git-identity cascade paragraph — Third, and at every commit after."""
    text = _read("skills/workhorse/SKILL.md")
    m = re.search(
        r"\*\*Third, and at every commit after.*?(?=\n\nYour own worktree)",
        text,
        re.DOTALL,
    )
    assert m, (
        "workhorse/SKILL.md §2 git-identity cascade paragraph not found (moved or reworded?)"
    )
    return m.group(0)


def _workhorse_git_identity_tempted_row():
    """The tempted-table row for synthesizing git identity on commit."""
    text = _read("skills/workhorse/SKILL.md")
    m = re.search(
        r'\| "Git won\'t say who I am[^|]+\|[^|]+\|',
        text,
    )
    assert m, (
        "workhorse/SKILL.md git-identity tempted-table row not found (moved or reworded?)"
    )
    return m.group(0)


def _workhorse_advisor_vet_bullet():
    """§11's `## Advisor vet` bullet — the builder's stamp instruction and the reminder it seeds."""
    section = _workhorse_section_11()
    m = re.search(
        r"- \*\*`## Advisor vet`\*\*.*?(?=\nThe advisor makes the)",
        section,
        re.DOTALL,
    )
    assert m, "workhorse/SKILL.md §11 `## Advisor vet` bullet not found (moved or reworded?)"
    return m.group(0)


def _owner_half_register_from_home():
    """The four register elements, parsed from their authoritative home in vet-receipt.md."""
    text = _read("skills/showrunner/reference/vet-receipt.md")
    m = re.search(
        r"^## The owner-half write — register$\n(.*?)(?=^## )",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, "vet-receipt.md owner-half register section not found (moved or renamed?)"
    block = m.group(1)
    items = re.findall(r"^\d+\.\s+\*\*([^*]+)\*\*", block, re.MULTILINE)
    assert len(items) == 4, "expected four register elements in the home, got %r" % items
    assert "`<details>`" in block, (
        "the register's home no longer says mechanism goes collapsed in `<details>`"
    )
    return [i.strip().rstrip(".") for i in items]


def _omission_floor_marker_forms():
    """Three accepted enumeration marker shapes; all three rows must use the same one."""
    return (
        ("paren", lambda n: re.compile(r"\(\s*%d\s*\)" % n)),
        ("dot", lambda n: re.compile(r"(?<!\d)%d\." % n)),
        ("paren_close", lambda n: re.compile(r"(?<!\d)(?<!\()%d\)" % n)),
        ("auto", lambda n: re.compile(r"(?<!\d)1\.")),
    )


def _omission_floor_find_enumeration(copy_text):
    """After the omission-floor anchor, locate an ordered triple of one marker form."""
    anchor_m = re.search(r"omission floor", copy_text, re.IGNORECASE)
    if not anchor_m:
        return None, "copy no longer names the omission floor"
    start = anchor_m.end()
    for form_name, maker in _omission_floor_marker_forms():
        positions = []
        pos = start
        if form_name == "auto":
            for _ in range(3):
                m = maker(1).search(copy_text, pos)
                if not m:
                    break
                positions.append(m.start())
                pos = m.end()
        else:
            for n in range(1, 4):
                m = maker(n).search(copy_text, pos)
                if not m:
                    break
                positions.append(m.start())
                pos = m.end()
        if len(positions) == 3:
            return (form_name, positions), None
    return None, (
        "copy must restate the floor as an enumerated triple of three items "
        "(markers (1)/(2)/(3), 1./2./3., 1)/2)/3), or Markdown auto-numbering 1./1./1. "
        "in order after the omission-floor anchor — this is what makes per-row drift detectable"
    )


def _omission_floor_item3_block_end(copy_text, marker3_pos):
    """End of marker-3's containing Markdown block — not the whole section.

    A single blank line may separate wrapped continuation lines within item 3; only a
    second blank line or a dedented sibling block ends the item."""
    tail = copy_text[marker3_pos:]
    end = len(copy_text)
    line_start = copy_text.rfind("\n", 0, marker3_pos) + 1
    line_prefix = copy_text[line_start:marker3_pos]
    indent = len(line_prefix) - len(line_prefix.lstrip())
    blank_count = 0
    for m in re.finditer(r"\n", tail):
        next_line_start = marker3_pos + m.start() + 1
        if next_line_start >= len(copy_text):
            break
        rest = copy_text[next_line_start:]
        nl = rest.find("\n")
        line_content = rest[:nl] if nl != -1 else rest
        if not line_content.strip():
            blank_count += 1
            if blank_count >= 2:
                end = min(end, next_line_start)
                break
            continue
        blank_count = 0
        line_indent = len(line_content) - len(line_content.lstrip())
        if line_indent <= indent:
            stripped = line_content.lstrip()
            if stripped.startswith("-") or stripped.startswith("*"):
                end = min(end, next_line_start)
                break
            if re.match(r"\d+[.)]", stripped):
                end = min(end, next_line_start)
                break
    return end


def test_omission_floor_find_enumeration_all_marker_forms():
    """Each accepted marker shape must yield three ascending positions after the anchor."""
    anchor = "omission floor\n"
    cases = (
        ("paren", anchor + "(1) first\n(2) second\n(3) third\n"),
        ("dot", anchor + "1. first\n2. second\n3. third\n"),
        ("paren_close", anchor + "1) first\n2) second\n3) third\n"),
        ("auto", anchor + "1. first\n1. second\n1. third\n"),
    )
    for expected_form, copy_text in cases:
        result, err = _omission_floor_find_enumeration(copy_text)
        assert err is None, copy_text
        form_name, positions = result
        assert form_name == expected_form
        assert positions == sorted(positions)
        assert len(positions) == 3


def _assert_omission_floor_matches_home(copy_text, label, home):
    # axis: per-row presence of each home-derived floor row inside its own enumeration item
    row_terms, markers = _omission_floor_expectations_from_home(home)
    lower = copy_text.lower()
    missing = []
    enum_result, enum_err = _omission_floor_find_enumeration(copy_text)
    if enum_result is None:
        missing.append(enum_err)
    else:
        _, positions = enum_result
        spans = [
            (positions[0], positions[1]),
            (positions[1], positions[2]),
            (
                positions[2],
                _omission_floor_item3_block_end(copy_text, positions[2]),
            ),
        ]
        for i, terms in enumerate(row_terms, 1):
            item_text = copy_text[spans[i - 1][0]:spans[i - 1][1]]
            item_lower = item_text.lower()
            for term in terms:
                if term.lower() not in item_lower:
                    missing.append(
                        "row%d term %r missing from item %d span" % (i, term, i)
                    )
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


# axis: per-row attribution — decoy prose outside an item cannot satisfy a hollowed row
def test_omission_floor_per_row_attribution_bites_on_hollowed_item():
    home = _conventions_section_10_7()
    row_terms, markers = _omission_floor_expectations_from_home(home)
    row2_decoy = " ".join("**%s**" % t for t in row_terms[1])
    item1 = "1. " + " ".join("**%s**" % t for t in row_terms[0])
    item2_hollow = "2. hollow row — row-two terms appear only in decoy below"
    item3 = "3. " + " ".join("**%s**" % t for t in row_terms[2])
    decoy = "Decoy outside the enumeration repeats row-two terms: " + row2_decoy
    copy_text = "\n".join([
        "Ship-phase honesty names the omission floor explicitly.",
        "",
        item1,
        item2_hollow,
        item3,
        "",
        decoy,
        "",
        "A **missing** `<!-- superheroes:build-record -->` is **itself** a review finding",
        "marker absence and **None** are different states",
    ] + list(markers))
    with pytest.raises(AssertionError, match="row2"):
        _assert_omission_floor_matches_home(copy_text, "synthetic per-row", home)


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


_PREFLIGHT_CHARTER_BEGIN = "<!-- launch-doctrine:preflight-charter:begin -->"
_PREFLIGHT_CHARTER_END = "<!-- launch-doctrine:preflight-charter:end -->"
# Row semantics (`**title**` + check id + always|conditional) are independent of list-marker spelling.
_PREFLIGHT_ENUM_ROW_BODY = (
    r"\*\*[^*]+\*\*\s*\(`[a-z][-a-z0-9]*`,\s*(?:always|conditional)\)"
)
# Any CommonMark list marker may prefix a pasted charter enumeration row.
_PREFLIGHT_ENUM_ITEM = re.compile(
    r"^\s*(?:\d+[.)]|[*+\-])\s+" + _PREFLIGHT_ENUM_ROW_BODY,
    re.MULTILINE,
)
_PREFLIGHT_CHECK_ID = re.compile(r"`([a-z][-a-z0-9]*)`")

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}

_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
}


def _preflight_charter_block(text):
    begin = text.find(_PREFLIGHT_CHARTER_BEGIN)
    end = text.find(_PREFLIGHT_CHARTER_END)
    assert begin != -1 and end != -1 and end > begin, (
        "dispatch-preflight.md preflight-charter block not found (moved or renamed?)"
    )
    body_start = begin + len(_PREFLIGHT_CHARTER_BEGIN)
    if body_start < len(text) and text[body_start] == "\n":
        body_start += 1
    body_end = end
    if body_end > 0 and text[body_end - 1] == "\n":
        body_end -= 1
    return text[body_start:body_end]


def _preflight_check_ids_from_home():
    import launch_doctrine as ld

    home_text = _read("skills/showrunner/reference/dispatch-preflight.md")
    block = _preflight_charter_block(home_text)
    in_block = set(re.findall(r"\(`([^`]+)`,\s*(?:always|conditional)\)", block))
    parsed = ld.charter_checks(home_text)
    assert parsed["ok"], parsed.get("reason")
    home_ids = {c["id"] for c in parsed["checks"]}
    assert in_block == home_ids, (
        "dispatch-preflight.md charter block lists %r but charter_checks parsed %r"
        % (sorted(in_block), sorted(home_ids))
    )
    return home_ids


def test_dispatch_preflight_charter_single_home_guard():
    """§11: dispatch-preflight.md is the single home for the eight enumerated preflight checks.

    showrunner/SKILL.md must point at the home (at least one check id) and must not carry a stale
    pasted enumeration or ids outside the home set.
    """
    home_ids = _preflight_check_ids_from_home()
    charter = _read("skills/showrunner/SKILL.md")

    pasted = _PREFLIGHT_ENUM_ITEM.findall(charter)
    assert not pasted, (
        "showrunner/SKILL.md carries pasted preflight enumeration item(s) %r — "
        "the list belongs only in dispatch-preflight.md" % pasted[:3]
    )

    cited = set(_PREFLIGHT_CHECK_ID.findall(charter))
    enum_form_ids = set(re.findall(r"\(`([^`]+)`,\s*(?:always|conditional)\)", charter))
    stale = enum_form_ids - home_ids
    assert not stale, (
        "showrunner/SKILL.md cites preflight check id(s) %r in enumeration form that "
        "dispatch-preflight.md does not name" % sorted(stale)
    )
    assert cited & home_ids, (
        "showrunner/SKILL.md cites no dispatch-preflight check id at all — the pointer to the "
        "home enumeration is missing"
    )


def test_preflight_enum_item_all_marker_forms():
    """Each accepted CommonMark list marker must match a pasted charter enumeration row."""
    body = "**Account** (`quota`, always)"
    cases = (
        "1. " + body,
        "1) " + body,
        "- " + body,
        "* " + body,
        "+ " + body,
    )
    for line in cases:
        assert _PREFLIGHT_ENUM_ITEM.search(line), line


def test_preflight_enum_form_ids_catches_stale_inline_citation():
    """axis: enum_form_ids — inline (`id`, always|conditional) prose outside the home set must fail."""
    home_ids = {"quota", "real-id"}
    charter = "Duty text cites (`phantom-id`, always) without pasting the enumeration."
    enum_form_ids = set(re.findall(r"\(`([^`]+)`,\s*(?:always|conditional)\)", charter))
    stale = enum_form_ids - home_ids
    with pytest.raises(AssertionError):
        assert not stale


def test_showrunner_preflight_count_prose_matches_home():
    """Duty 9 count words in showrunner/SKILL.md track dispatch-preflight.md's enumeration."""
    import launch_doctrine as ld

    home_text = _read("skills/showrunner/reference/dispatch-preflight.md")
    parsed = ld.charter_checks(home_text)
    assert parsed["ok"], parsed.get("reason")
    check_count = len(parsed["checks"])
    duty = _showrunner_orchestration_duty()

    eight_match = re.search(r"\*\*([A-Za-z]+)\s+checks:\*\*", duty)
    assert eight_match, (
        "showrunner/SKILL.md duty 9 missing '<Word> checks:' count prose (moved or reworded?)"
    )
    eight_word = eight_match.group(1).lower()
    assert eight_word in _NUMBER_WORDS, (
        "showrunner/SKILL.md duty 9 uses unknown check-count word %r" % eight_word
    )
    assert _NUMBER_WORDS[eight_word] == check_count, (
        "showrunner/SKILL.md duty 9 says %r checks but dispatch-preflight.md enumerates %d"
        % (eight_word, check_count)
    )

    ninth_match = re.search(r"not a ([a-z]+) check\b", duty, re.IGNORECASE)
    assert ninth_match, (
        "showrunner/SKILL.md duty 9 missing 'not a <ordinal> check' prose (moved or reworded?)"
    )
    ninth_word = ninth_match.group(1).lower()
    assert ninth_word in _ORDINAL_WORDS, (
        "showrunner/SKILL.md duty 9 uses unknown ordinal %r in ninth-check guard" % ninth_word
    )
    assert _ORDINAL_WORDS[ninth_word] == check_count + 1, (
        "showrunner/SKILL.md 'not a %s check' no longer matches len(home)+1 (%d+1)"
        % (ninth_word, check_count)
    )

    list_match = re.search(r"\b([a-z]+)-check list\b", duty, re.IGNORECASE)
    assert list_match, (
        "showrunner/SKILL.md duty 9 missing '<word>-check list' prose (moved or reworded?)"
    )
    list_word = list_match.group(1).lower()
    assert list_word in _NUMBER_WORDS, (
        "showrunner/SKILL.md duty 9 uses unknown word %r in eight-check-list guard" % list_word
    )
    assert _NUMBER_WORDS[list_word] == check_count, (
        "showrunner/SKILL.md '%s-check list' no longer matches dispatch-preflight enumeration (%d)"
        % (list_word, check_count)
    )


def test_stamp_instructions_name_the_body_marker_specifically():
    """§10.7 + LEDGERS row 236's named closure: both stamp instructions name the BODY marker.

    A rename already failed loudly. What passed was a valid-for-valid substitution — editing a
    stamp instruction from advisor-vet to a sibling such as vet-receipt — which would misdirect the
    stamp and break the detection path. #794 makes the workhorse a stamp-instruction holder too, so
    both legs are pinned, and both are pinned to a marker DERIVED from §10.7.
    """
    body_marker = _body_marker_from_conventions(_conventions_section_10_7())
    for label, text in (
        ("showrunner/SKILL.md duty-4 slot-write bullet", _showrunner_slot_write_bullet()),
        ("workhorse/SKILL.md §11 `## Advisor vet` bullet", _workhorse_advisor_vet_bullet()),
    ):
        found = set(re.findall(r"(<!-- superheroes:[^>]+ -->)", text))
        assert found == {body_marker}, (
            "%s names marker(s) %r; §10.7 says the PR-body marker is %r — a stamp instruction "
            "naming any other marker misdirects the stamp" % (label, sorted(found), body_marker)
        )


def test_pr_body_skeleton_stamps_the_marker_and_seeds_the_advisor_reminder():
    """§10.7 + #794 D1/D3: the §11 skeleton emits the slot marker AND the reminder beneath it.

    D1 exists because the skeleton omitted the marker 7-for-7. D3 exists because pre-stamping the
    marker destroys the signal that told a dropped advisor write from a vet not yet written — the
    reminder takes it over, so the two ship together or the detection path is worse than before.

    The builder-authorship assertion catches swapping the builder-stamps imperative for an
    advisor-stamps claim — D1's original defect reproduced with every other predicate still true.
    """
    bullet = _workhorse_advisor_vet_bullet()
    body_marker = _body_marker_from_conventions(_conventions_section_10_7())
    assert body_marker in bullet, (
        "§11's `## Advisor vet` bullet does not emit %r — the slot ships unstamped" % body_marker
    )
    reminder = re.search(r"<!-- advisor:.*?-->", bullet, re.DOTALL)
    assert reminder, (
        "§11's `## Advisor vet` bullet seeds no `<!-- advisor: ... -->` reminder — a pre-stamped "
        "marker with no reminder cannot distinguish a dropped advisor write from a vet not yet "
        "written (#794 D3)"
    )
    assert "superheroes:advisor-vet" not in reminder.group(0), (
        "the reminder nests the marker literal inside another HTML comment; the marker must be "
        "emitted separately (#794 D3 implementer note)"
    )
    assert "vet-receipt.md" in reminder.group(0), (
        "the reminder does not point the advisor at the receipt contract it exists to name"
    )
    assert "FIRST" in reminder.group(0), (
        "the reminder no longer carries the receipt-first step (FIRST)"
    )
    assert "replace this comment" in reminder.group(0), (
        "the reminder no longer carries the replace-this-comment step"
    )
    assert re.search(r"owner-half\s+register", reminder.group(0)), (
        "the reminder no longer teaches the owner-half register shape"
    )
    elements = _owner_half_register_from_home()
    plain = " ".join(reminder.group(0).split()).replace("**", "").lower()
    missing = [e for e in elements if e.lower() not in plain]
    assert not missing, (
        "§11 advisor reminder is missing register element(s) %r "
        "(home: skills/showrunner/reference/vet-receipt.md)" % missing
    )
    indices = [plain.index(e.lower()) for e in elements]
    for i in range(len(indices) - 1):
        assert indices[i] < indices[i + 1], (
            "§11 advisor reminder register elements out of order: %r before %r"
            % (elements[i], elements[i + 1])
        )
    assert re.search(
        r"builder creates and pre-stamps|You stamp the marker so the advisor never has to",
        bullet,
        re.IGNORECASE,
    ), (
        "§11's `## Advisor vet` bullet no longer asserts the builder creates and pre-stamps the slot"
    )
    assert not re.search(
        r"advisor stamps the marker|the builder never stamps",
        bullet,
        re.IGNORECASE,
    ), (
        "§11's `## Advisor vet` bullet assigns marker stamping to the advisor instead of the builder"
    )
    assert bullet.index(body_marker) < bullet.index(reminder.group(0)), (
        "the reminder must sit BELOW the marker, not above it"
    )


def test_pr_body_skeleton_opens_with_the_close_link():
    """§11 + the 2026-08-02 rider: the body's first line is the close link.

    A close-state sweep of 20 merged PRs found 5 shipped issues left open for want of this one
    mechanical line — a 25% escape rate the template owns, not the builder's memory.
    """
    directive = _workhorse_close_link_directive_sentence()
    assert "`Closes #<issue>.`" in directive, (
        "§11 close-link directive no longer names the `Closes #<issue>.` first line"
    )
    assert re.search(r"first line[^.]{0,80}close link", directive, re.IGNORECASE), (
        "§11 close-link directive names the close link but no longer says it is the body's FIRST line"
    )


def test_owner_half_register_matches_its_home():
    """§10.7 + #794 D2: the showrunner charter's copy of the register matches vet-receipt.md.

    The charter carries the register compactly because advisors re-read the charter and skip the
    reference file — which is the failure #794 D4 names. Two copies means this pin.
    """
    elements = _owner_half_register_from_home()
    bullet = _showrunner_slot_write_bullet()
    plain = bullet.replace("**", "").lower()
    missing = [e for e in elements if e.lower() not in plain]
    assert not missing, (
        "showrunner duty-4 slot-write bullet is missing register element(s) %r "
        "(home: skills/showrunner/reference/vet-receipt.md)" % missing
    )
    indices = [plain.index(e.lower()) for e in elements]
    for i in range(len(indices) - 1):
        assert indices[i] < indices[i + 1], (
            "showrunner duty-4 register elements out of order: %r before %r"
            % (elements[i], elements[i + 1])
        )
    details_idx = plain.index("`<details>`".lower())
    assert indices[-1] < details_idx, (
        "showrunner duty-4 register: `<details>` clause must follow the fourth element"
    )
    assert "`<details>`" in bullet, (
        "the charter's register copy no longer sends probes/accounting to `<details>`"
    )
    assert "vet-receipt.md" in bullet, (
        "the charter's register copy no longer points at its authoritative home"
    )


def test_workhorse_git_identity_prose_matches_the_doctrine():
    """§11 + launch-doctrine: workhorse git-identity prose carries the doctrine's cascade terms.

    Source: launch_doctrine.RULING_TEXT['git-identity'] — the machine-parsed ruling the launcher
    delivers; the workhorse copies speak in charter voice but must not drift from these terms.
    """
    import launch_doctrine as LD

    ruling = LD.RULING_TEXT["git-identity"]
    required = (
        "repo-local",
        "global",
        "`-c user.name`",
        "`-c user.email`",
    )
    for term in required:
        assert term in ruling, "doctrine ruling missing load-bearing term %r" % term

    for label, text in (
        ("workhorse/SKILL.md §2", _workhorse_git_identity_section2_paragraph()),
        ("workhorse/SKILL.md tempted-table", _workhorse_git_identity_tempted_row()),
    ):
        missing = [t for t in required if t not in text]
        assert not missing, (
            "%s: git-identity prose drift — missing doctrine term(s) %r" % (label, missing)
        )


def _showrunner_orchestration_duty():
    """Duty 9 (Orchestration — dispatch and preflight) through duty 10."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"9\. \*\*Orchestration.*?(?=\n10\. \*\*)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner/SKILL.md duty 9 (Orchestration) not found (moved or renumbered?)"
    return m.group(0)


def _showrunner_provisioning_duty():
    """Duty 10 (Provision slots for an authenticated wave) through the tempted-table heading."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"10\. \*\*Provision slots.*?(?=\n## When you're tempted)",
        text,
        re.DOTALL,
    )
    assert m, "showrunner/SKILL.md duty 10 (Provision slots) not found (moved or renumbered?)"
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


def test_amendment_vocabulary_in_showrunner_charter():
    """§11: showrunner charter carries post-terminal amendment vocabulary from launch_ledger."""
    # axis: caller-writable amendment kinds, vet rulings, and the amend verb must appear in the
    # charter pinned in their invocation context (--kind / --value lines), not merely anywhere in prose.
    import launch_ledger

    doc = _read("skills/showrunner/SKILL.md")
    missing = []
    for kind in launch_ledger.CALLER_WRITABLE_AMENDMENT_KINDS:
        if "--kind %s" % kind not in doc:
            missing.append("kind %r" % kind)
    value_lines = [ln for ln in doc.splitlines() if "--value" in ln]
    if not value_lines:
        missing.append("no --value line")
    else:
        value_text = "\n".join(value_lines)
        for ruling in launch_ledger.VET_RULINGS:
            if ruling not in value_text:
                missing.append("ruling %r" % ruling)
    if "amend" not in doc:
        missing.append("verb 'amend'")
    assert not missing, (
        "showrunner/SKILL.md missing amendment vocabulary from launch_ledger.py: %s"
        % ", ".join(missing)
    )


def test_count_result_blocks_in_showrunner_charter():
    """§11: showrunner charter names count-result blocks sourced from launch_ledger."""
    import launch_ledger

    doc = _read("skills/showrunner/SKILL.md")
    duty = _showrunner_orchestration_duty()
    missing = []
    for block in launch_ledger.CHARTER_NAMED_COUNT_BLOCKS:
        if block not in duty:
            missing.append(block)
    assert not missing, (
        "showrunner/SKILL.md duty 9 missing count-result block(s) from "
        "launch_ledger.COUNT_RESULT_BLOCKS: %r" % missing
    )


def test_showrunner_provisioning_duty_load_bearing_content():
    """§11: duty 10 carries load-bearing provisioning clauses."""
    duty = _showrunner_provisioning_duty()
    lower = duty.lower()
    missing = []
    if "without any seeded sign-in" not in lower:
        missing.append("unauthenticated-app-first ordering")
    if "is a no-go" not in lower:
        missing.append("partial-failure no-go rule")
    if "acceptance record (who accepted, when, and why)" not in lower:
        missing.append("weaker-acceptance record")
    if "the launcher carries the slot" not in lower:
        missing.append("launcher-carries-the-slot clause")
    assert not missing, (
        "showrunner/SKILL.md duty 10 missing load-bearing element(s): %s"
        % ", ".join(missing)
    )


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


# --- Cluster: owner-authority allowlist (owner_authority → owner-authority-allowlist.md) ---


def _owner_authority_allowlist_doc():
    return _read("reference/owner-authority-allowlist.md")


def _expand_char_ranges(text):
    """Expand doc range tokens (`A-Z`, `a-z`, `0-9`) into full character sets."""
    chars = set()
    for token in text.split():
        if len(token) == 3 and token[1] == "-" and ord(token[0]) <= ord(token[2]):
            chars.update(chr(c) for c in range(ord(token[0]), ord(token[2]) + 1))
        else:
            chars.update(token)
    return chars


def _charset_lists_from_doc(doc):
    """Parse the supported and refused character lists from the reference doc."""
    marker = "**Supported workflow-name characters:**"
    start = doc.find(marker)
    assert start != -1, (
        "owner-authority-allowlist.md: %s marker not found" % marker)

    consequence = doc.find("**Consequence:**", start)
    section = doc[start:consequence] if consequence != -1 else doc[start:]

    split_phrase = "Any other character anywhere"
    split_at = section.find(split_phrase)
    assert split_at != -1, (
        "owner-authority-allowlist.md: %r phrase not found in charset paragraph"
        % split_phrase)

    accepted_half = section[:split_at]
    refused_rest = section[split_at + len(split_phrase):].lstrip()
    if refused_rest.startswith("—"):
        refused_rest = refused_rest[1:].lstrip()
    terminator = refused_rest.find("—")
    assert terminator != -1, (
        "owner-authority-allowlist.md: refused charset list terminator not found")
    refused_half = refused_rest[:terminator]

    accepted = set()
    for chunk in re.findall(r"`([^`]+)`", accepted_half):
        accepted.update(_expand_char_ranges(chunk))
    # Range notation in backticks (`A-Z a-z 0-9`) is expanded to full character ranges.
    if "space" in accepted_half:
        accepted.add(" ")

    refused = set()
    for chunk in re.findall(r"`([^`]+)`", refused_half):
        refused.update(chunk)
    if "backtick" in refused_half:
        refused.add("`")

    assert accepted, "owner-authority-allowlist.md: no accepted charset parsed"
    assert refused, "owner-authority-allowlist.md: no refused charset parsed"
    return accepted, refused


def _owner_authority_also_asks_bullet(doc):
    """The 'Also asks regardless of the file' bullet under charset limitations."""
    m = re.search(
        r"Also asks regardless of the file:(.*?)(?:\n- |\n## |\Z)",
        doc,
        re.DOTALL,
    )
    assert m, (
        "owner-authority-allowlist.md: 'Also asks regardless of the file' bullet not found")
    return m.group(1)


def _owner_authority_also_asks_enumeration(doc):
    """The flag-enumeration sentences of the 'Also asks' bullet — not example-only tail text."""
    bullet = _owner_authority_also_asks_bullet(doc).strip()
    m = re.match(
        r"(.+?Ref flags\s*\([^)]+\)\s*ask\b[^.]*\.)",
        bullet,
        re.DOTALL | re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = re.match(r"([^:]+\:.+?\.)", bullet, re.DOTALL)
    return m.group(1) if m else bullet


def _owner_authority_flag_in_enumeration(flag, enumeration):
    _flag_token = r"(?<![-\w])%s(?![-\w])"
    return re.search(_flag_token % re.escape(flag), enumeration) is not None


def test_owner_authority_allowlist_doc_matches_code():
    """§11: owner-authority-allowlist.md restates owner_authority.py constants and charset."""
    import owner_authority as oa

    doc = _owner_authority_allowlist_doc()

    assert oa.ALLOW_FILENAME in doc, (
        "owner-authority-allowlist.md missing ALLOW_FILENAME %r" % oa.ALLOW_FILENAME)

    schema_blocks = re.findall(r"```json\n(.*?)\n```", doc, re.DOTALL)
    assert schema_blocks, "owner-authority-allowlist.md: schema JSON block not found"
    # bite-proof axis: every supported schema version is documented in a schema JSON block.
    for ver in oa.ALLOW_SCHEMA_VERSIONS:
        assert any('"schemaVersion": %d' % ver in block for block in schema_blocks), (
            "owner-authority-allowlist.md missing schemaVersion %d in a schema JSON block"
            % ver)
    # bite-proof axis: the v2 opt-in sentinel is documented.
    assert '"ref": "%s"' % oa._REF_ANY_SENTINEL in doc, (
        "owner-authority-allowlist.md missing v2 ref sentinel")

    never_section = re.search(
        r"## What can never be allowlisted\n(.*?)(?=\n## )",
        doc,
        re.DOTALL,
    )
    assert never_section, "owner-authority-allowlist.md: never-allowlistable section not found"
    never_text = never_section.group(1)
    for action in oa.NEVER_ALLOWLISTABLE:
        assert action in never_text, (
            "owner-authority-allowlist.md missing NEVER_ALLOWLISTABLE member %r" % action)

    for action in oa.ALLOWLISTABLE_ACTIONS:
        assert action in doc, (
            "owner-authority-allowlist.md missing ALLOWLISTABLE_ACTIONS member %r" % action)

    also_asks = _owner_authority_also_asks_bullet(doc)
    also_asks_enum = _owner_authority_also_asks_enumeration(doc)
    _flag_token = r"(?<![-\w])%s(?![-\w])"
    # bite-proof axis: every repo flag is named in the always-asks enumeration clause.
    for flag in oa._REPO_FLAGS:
        assert _owner_authority_flag_in_enumeration(flag, also_asks_enum), (
            "owner-authority-allowlist.md 'Also asks' enumeration missing _REPO_FLAGS "
            "member %r" % flag)
    # bite-proof axis: ref-policy conditional — ref flags ask unless v2+sentinel covers them.
    for flag in oa._REF_FLAGS:
        assert _owner_authority_flag_in_enumeration(flag, also_asks_enum), (
            "owner-authority-allowlist.md 'Also asks' enumeration missing _REF_FLAGS "
            "member %r" % flag)
    ref_versions = sorted(oa._REF_KEY_VERSIONS)
    ref_policy = re.compile(
        r"unless.*?schemaVersion:\s*(%s).*?ref:\s*[\"']%s[\"']"
        % ("|".join(str(v) for v in ref_versions),
           re.escape(oa._REF_ANY_SENTINEL)),
        re.I | re.DOTALL,
    )
    assert ref_policy.search(also_asks), (
        "owner-authority-allowlist.md 'Also asks' bullet missing ref-policy conditional "
        "(ref flags ask unless schemaVersion %s entry with ref: %r covers them)"
        % (" or ".join(str(v) for v in ref_versions), oa._REF_ANY_SENTINEL))

    accepted_doc, refused_doc = _charset_lists_from_doc(doc)
    pattern = oa._LITERAL_SAFE_COMMAND

    # chr(32)..chr(126): printable ASCII — complete for this pattern (no tab/newline accepted).
    printable_ascii = {chr(c) for c in range(32, 127)}
    code_accepted = {
        ch for ch in printable_ascii
        if pattern.fullmatch("X" + ch + "Y")
    }
    in_code_not_doc = code_accepted - accepted_doc
    in_doc_not_code = accepted_doc - code_accepted
    assert code_accepted == accepted_doc, (
        "_LITERAL_SAFE_COMMAND charset drift — in code but not documented: %r; "
        "documented but not in code: %r"
        % (sorted(in_code_not_doc), sorted(in_doc_not_code)))

    for ch in refused_doc:
        assert not pattern.fullmatch("X" + ch + "Y"), (
            "doc lists %r as refused but _LITERAL_SAFE_COMMAND accepts it" % ch)


# --- Cluster: issue-contract vocabulary (issue_contract → issue-contract.md) ---


def _issue_contract_slots_from_home():
    import issue_contract

    return list(issue_contract.SLOTS)


def _issue_contract_rendered_headers_from_home():
    import issue_contract

    return [
        issue_contract.ANCHOR_HEADER_FORM,
        issue_contract.SLOT_WHAT + ":",
        issue_contract.SLOT_DOD + ":",
    ]


def _issue_contract_anchor_kinds_from_home():
    import issue_contract

    return set(issue_contract.ANCHOR_KINDS)


def _issue_contract_refusals_from_home():
    import issue_contract

    return set(issue_contract.REFUSALS)


def _issue_contract_string_constants_by_prefix(prefix):
    """Module-level string constants named PREFIX_* — scoped to vocabulary prefixes only."""
    import issue_contract

    derived = set()
    for name in dir(issue_contract):
        if not name.startswith(prefix):
            continue
        val = getattr(issue_contract, name)
        if isinstance(val, str) and val:
            derived.add(val)
    return derived


def _issue_contract_vocabulary_section(doc):
    """The drift-tested vocabulary section in issue-contract.md."""
    m = re.search(
        r"^## Vocabulary \(drift-tested\)\s*\n(.*?)(?:\n## |\Z)",
        doc,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "issue-contract.md: ## Vocabulary (drift-tested) section not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _issue_contract_slots_from_doc(doc):
    """Ordered slot names from the Slots bullet block — scoped to that block only."""
    section = _issue_contract_vocabulary_section(doc)
    m = re.search(
        r"\*\*Slots\*\* \(in order\):\n\n(.*?)(?=\n\*\*|\n## |\Z)",
        section,
        re.DOTALL,
    )
    assert m, (
        "issue-contract.md: Slots bullet list not found "
        "(moved or reworded?)"
    )
    tokens = re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE)
    assert tokens, (
        "issue-contract.md: Slots bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _issue_contract_anchor_kinds_from_doc(doc):
    """Anchor-kind tokens from the Anchor kinds bullet block — scoped to that block only."""
    section = _issue_contract_vocabulary_section(doc)
    m = re.search(
        r"\*\*Anchor kinds\*\*.*?:\n\n(.*?)(?=\n\*\*|\n## |\Z)",
        section,
        re.DOTALL,
    )
    assert m, (
        "issue-contract.md: Anchor kinds bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "issue-contract.md: Anchor kinds bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _issue_contract_refusals_from_doc(doc):
    """Refusal tokens from the Refusal reasons bullet block — scoped to that block only."""
    section = _issue_contract_vocabulary_section(doc)
    m = re.search(
        r"\*\*Refusal reasons\*\*.*?:\n\n(.*?)(?=\n\*\*|\n## |\Z)",
        section,
        re.DOTALL,
    )
    assert m, (
        "issue-contract.md: Refusal reasons bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "issue-contract.md: Refusal reasons bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _issue_contract_refusals_from_doc_table(doc):
    """Refusal tokens from the build-ready refusal-reason table — scoped to that block only."""
    m = re.search(
        r"\*\*Refusal reasons\*\* \(build-ready marking declined\):\n\n"
        r"\| Token \| Meaning \|\n\| --- \| --- \|\n(.*?)(?:\n>|$)",
        doc,
        re.DOTALL,
    )
    assert m, (
        "issue-contract.md: build-ready refusal-reason table not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"\| `([^`]+)` \|", m.group(1)))
    assert tokens, (
        "issue-contract.md: refusal-reason table parsed to zero tokens "
        "(regex drift or empty table?)"
    )
    return tokens


def _issue_contract_rendered_header_from_doc(doc):
    """Rendered Anchor header form from the vocabulary section — scoped to that sentence."""
    section = _issue_contract_vocabulary_section(doc)
    m = re.search(
        r"The Anchor slot's rendered header form is `([^`]+)`\.",
        section,
    )
    assert m, (
        "issue-contract.md: rendered Anchor header form sentence not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _issue_contract_slot_statuses_from_doc(doc):
    """Slot-status tokens from the Slot statuses bullet block — scoped to that block only."""
    section = _issue_contract_vocabulary_section(doc)
    m = re.search(
        r"\*\*Slot statuses\*\*.*?:\n\n(.*?)(?=\n\*\*|\n## |\Z)",
        section,
        re.DOTALL,
    )
    assert m, (
        "issue-contract.md: Slot statuses bullet list not found "
        "(moved or reworded?)"
    )
    tokens = set(re.findall(r"^- `([^`]+)`", m.group(1), re.MULTILINE))
    assert tokens, (
        "issue-contract.md: Slot statuses bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _issue_contract_slot_statuses_from_home():
    import issue_contract

    return set(issue_contract.SLOT_STATUSES)


def _issue_contract_rendered_headers_from_showrunner_skill():
    """Rendered slot headers from showrunner/SKILL.md duty 2 — scoped to that enumeration."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"three-slot skeleton\s*\n\s*\(`([^`]+)`, `([^`]+)`, `([^`]+)`\)",
        text,
    )
    assert m, (
        "showrunner/SKILL.md: duty 2 three-slot skeleton enumeration not found "
        "(moved or reworded?)"
    )
    return [m.group(1), m.group(2), m.group(3)]


def _issue_contract_rendered_headers_from_conventions():
    """Rendered slot headers from CONVENTIONS §11 worked example 3."""
    text = _read("../../CONVENTIONS.md")
    m = re.search(
        r"three slot names and their order\s*\n\(`([^`]+)`, `([^`]+)`, `([^`]+)`\)",
        text,
    )
    assert m, (
        "CONVENTIONS.md §11: issue-contract slot enumeration not found "
        "(moved or reworded?)"
    )
    return [m.group(1), m.group(2), m.group(3)]


def _issue_contract_refusals_from_conventions():
    """Refusal tokens and count word from CONVENTIONS §11 worked example 3."""
    import issue_contract

    text = _read("../../CONVENTIONS.md")
    m = re.search(
        r"(\w+) build-ready\s+refusal-reason tokens \(([^)]+)\)",
        text,
    )
    assert m, (
        "CONVENTIONS.md §11: issue-contract refusal-token list not found "
        "(moved or reworded?)"
    )
    count_word = m.group(1).lower()
    assert count_word in _NUMBER_WORDS, (
        "CONVENTIONS.md §11 uses unknown refusal-count word %r" % count_word
    )
    # axis: the prose count word (six, seven, …) must match len(REFUSALS) — distinct from the
    # adjacent token-set membership check on the same passage.
    assert _NUMBER_WORDS[count_word] == len(issue_contract.REFUSALS), (
        "CONVENTIONS.md §11 refusal count word %r (%d) drift from "
        "len(issue_contract.REFUSALS) (%d)"
        % (count_word, _NUMBER_WORDS[count_word], len(issue_contract.REFUSALS))
    )
    tokens = re.findall(r"`([^`]+)`", m.group(2))
    assert tokens, (
        "CONVENTIONS.md §11: refusal-token list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return set(tokens)


def test_issue_contract_vocabulary_in_issue_contract_doc():
    """§11: issue-contract.md restates issue_contract.py vocabulary on three registry axes
    plus ordered slots.

    Copy-holders enumerated (§11.2 caveat — every known copy must be listed here):
  **Names** (compared against ``issue_contract.SLOTS`` and sibling registries):
    - skills/showrunner/reference/issue-contract.md ## Vocabulary (drift-tested) — Slots,
      Anchor kinds, Refusal reasons bullet lists, Slot statuses bullet list
    - skills/showrunner/reference/issue-contract.md build-ready refusal-reason table
  **Rendered headers** (compared against ``ANCHOR_HEADER_FORM``, ``What:``, ``DoD:``):
    - skills/showrunner/reference/issue-contract.md ## Vocabulary (drift-tested) — rendered
      Anchor header form sentence
    - skills/showrunner/SKILL.md duty 2 three-slot skeleton enumeration
    - CONVENTIONS.md §11 worked example 3 slot-header enumeration
  **Refusal count word** (compared against ``len(issue_contract.REFUSALS)``):
    - CONVENTIONS.md §11 worked example 3 refusal-reason prose
  **Refusal token list** (compared against ``issue_contract.REFUSALS``):
    - CONVENTIONS.md §11 worked example 3 refusal-reason token list

    Axis notes:
    - Slots, anchor kinds, refusals, slot statuses: SLOT_/KIND_/REFUSAL_/SLOT_STATUS_* constants
      must match the module registries; the doc bullet lists must match the home registries.
    - Slot order: the doc Slots block is compared as an ordered sequence against SLOTS.
    - Rendered headers: SKILL.md and CONVENTIONS §11 enumerate header forms, not bare names.
    - ``ANCHOR_HEADER_FORM`` must start with ``SLOT_ANCHOR`` and end with ``:`` so both axes
      move together when the Anchor slot is renamed.
    """
    import issue_contract

    home_slots = _issue_contract_slots_from_home()
    home_rendered = _issue_contract_rendered_headers_from_home()
    # axis: ANCHOR_HEADER_FORM must move with SLOT_ANCHOR — a slot rename cannot leave the rendered
    # header form pointing at a stale prefix or missing the trailing colon.
    assert issue_contract.ANCHOR_HEADER_FORM.startswith(issue_contract.SLOT_ANCHOR), (
        "issue_contract.ANCHOR_HEADER_FORM must start with SLOT_ANCHOR — "
        "form: %r; anchor: %r"
        % (issue_contract.ANCHOR_HEADER_FORM, issue_contract.SLOT_ANCHOR)
    )
    assert issue_contract.ANCHOR_HEADER_FORM.endswith(":"), (
        "issue_contract.ANCHOR_HEADER_FORM must end with ':' — form: %r"
        % issue_contract.ANCHOR_HEADER_FORM
    )
    home_kinds = _issue_contract_anchor_kinds_from_home()
    home_refusals = _issue_contract_refusals_from_home()
    home_slot_statuses = _issue_contract_slot_statuses_from_home()
    derived_slots = _issue_contract_string_constants_by_prefix("SLOT_")
    derived_kinds = _issue_contract_string_constants_by_prefix("KIND_")
    derived_refusals = _issue_contract_string_constants_by_prefix("REFUSAL_")
    derived_slot_statuses = _issue_contract_string_constants_by_prefix("SLOT_STATUS_")
    derived_slots = derived_slots - derived_slot_statuses
    assert derived_slots == set(home_slots), (
        "issue_contract SLOT_* constants drift from issue_contract.SLOTS — "
        "symmetric difference: %r"
        % sorted(derived_slots ^ set(home_slots))
    )
    assert derived_kinds == home_kinds, (
        "issue_contract KIND_* constants drift from issue_contract.ANCHOR_KINDS — "
        "symmetric difference: %r"
        % sorted(derived_kinds ^ home_kinds)
    )
    assert derived_refusals == home_refusals, (
        "issue_contract REFUSAL_* constants drift from issue_contract.REFUSALS — "
        "symmetric difference: %r"
        % sorted(derived_refusals ^ home_refusals)
    )
    assert derived_slot_statuses == home_slot_statuses, (
        "issue_contract SLOT_STATUS_* constants drift from issue_contract.SLOT_STATUSES — "
        "symmetric difference: %r"
        % sorted(derived_slot_statuses ^ home_slot_statuses)
    )
    doc = _read("skills/showrunner/reference/issue-contract.md")
    doc_slots = _issue_contract_slots_from_doc(doc)
    assert doc_slots == home_slots, (
        "issue-contract.md Slots order drift from issue_contract.SLOTS — "
        "doc: %r; home: %r"
        % (doc_slots, home_slots)
    )
    doc_kinds = _issue_contract_anchor_kinds_from_doc(doc)
    missing_kinds = sorted(home_kinds - doc_kinds)
    extra_kinds = sorted(doc_kinds - home_kinds)
    assert not missing_kinds and not extra_kinds, (
        "issue-contract.md Anchor kinds vocabulary drift from issue_contract.ANCHOR_KINDS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_kinds, extra_kinds)
    )
    doc_refusals = _issue_contract_refusals_from_doc(doc)
    missing_refusals = sorted(home_refusals - doc_refusals)
    extra_refusals = sorted(doc_refusals - home_refusals)
    assert not missing_refusals and not extra_refusals, (
        "issue-contract.md Refusal reasons vocabulary drift from issue_contract.REFUSALS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_refusals, extra_refusals)
    )
    table_refusals = _issue_contract_refusals_from_doc_table(doc)
    missing_table = sorted(home_refusals - table_refusals)
    extra_table = sorted(table_refusals - home_refusals)
    assert not missing_table and not extra_table, (
        "issue-contract.md refusal-reason table drift from issue_contract.REFUSALS — "
        "missing from table: %r; present in table but not in home: %r"
        % (missing_table, extra_table)
    )
    doc_rendered_header = _issue_contract_rendered_header_from_doc(doc)
    assert doc_rendered_header == issue_contract.ANCHOR_HEADER_FORM, (
        "issue-contract.md rendered Anchor header form drift from "
        "issue_contract.ANCHOR_HEADER_FORM — doc: %r; home: %r"
        % (doc_rendered_header, issue_contract.ANCHOR_HEADER_FORM)
    )
    doc_slot_statuses = _issue_contract_slot_statuses_from_doc(doc)
    missing_statuses = sorted(home_slot_statuses - doc_slot_statuses)
    extra_statuses = sorted(doc_slot_statuses - home_slot_statuses)
    assert not missing_statuses and not extra_statuses, (
        "issue-contract.md Slot statuses vocabulary drift from issue_contract.SLOT_STATUSES — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_statuses, extra_statuses)
    )
    # axis: SKILL.md and CONVENTIONS §11 enumerate rendered header forms, not bare slot names.
    skill_headers = _issue_contract_rendered_headers_from_showrunner_skill()
    assert skill_headers == home_rendered, (
        "showrunner/SKILL.md duty 2 rendered-header drift from issue_contract — "
        "doc: %r; home: %r"
        % (skill_headers, home_rendered)
    )
    conventions_headers = _issue_contract_rendered_headers_from_conventions()
    assert conventions_headers == home_rendered, (
        "CONVENTIONS.md §11 rendered-header drift from issue_contract — "
        "doc: %r; home: %r"
        % (conventions_headers, home_rendered)
    )
    conventions_refusals = _issue_contract_refusals_from_conventions()
    missing_conv = sorted(home_refusals - conventions_refusals)
    extra_conv = sorted(conventions_refusals - home_refusals)
    assert not missing_conv and not extra_conv, (
        "CONVENTIONS.md §11 refusal vocabulary drift from issue_contract.REFUSALS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_conv, extra_conv)
    )
    assert list(issue_contract.SLOTS) == home_slots


# --- Cluster: register-check vocabulary (register_check → register-check.md) ---


_REGISTER_CHECK_DOC = "skills/showrunner/reference/register-check.md"


def _register_check_string_constants_by_prefix(prefix):
    """Module-level string constants named PREFIX_* — scoped to vocabulary prefixes only."""
    import register_check

    derived = set()
    for name in dir(register_check):
        if not name.startswith(prefix):
            continue
        val = getattr(register_check, name)
        if isinstance(val, str) and val:
            derived.add(val)
    return derived


def _register_check_vocabulary_section(doc):
    """The drift-tested vocabulary section in register-check.md."""
    headings = re.findall(
        r"^## Vocabulary \(drift-tested\)\s*$",
        doc,
        re.MULTILINE,
    )
    assert len(headings) == 1, (
        "register-check.md: expected exactly one "
        "## Vocabulary (drift-tested) heading, found %d"
        % len(headings)
    )
    m = re.search(
        r"^## Vocabulary \(drift-tested\)\s*\n(.*?)(?:\n## |\Z)",
        doc,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "register-check.md: ## Vocabulary (drift-tested) section not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _register_check_tokens_under_label(section, label):
    """Inline-code bullet tokens under a **Label:** block — scoped to that block only."""
    pattern = (
        r"\*\*%s\*\*\s*\n\n(.*?)(?=\n\*\*|\n## |\Z)"
        % re.escape(label)
    )
    matches = list(re.finditer(pattern, section, re.DOTALL))
    assert len(matches) == 1, (
        "register-check.md: expected exactly one **%s:** label, found %d"
        % (label, len(matches))
    )
    tokens = re.findall(r"^- `([^`]+)`", matches[0].group(1), re.MULTILINE)
    assert tokens, (
        "register-check.md: **%s:** bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
        % label
    )
    return set(tokens)


def _register_check_schema_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    tokens = _register_check_tokens_under_label(section, "Schema:")
    return tokens


def _register_check_results_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return _register_check_tokens_under_label(section, "Results:")


def _register_check_finding_kinds_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return _register_check_tokens_under_label(section, "Finding kinds:")


def _register_check_unrunnable_reasons_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return _register_check_tokens_under_label(section, "Unrunnable reasons:")


def _register_check_exit_codes_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    pattern = r"\*\*Exit codes:\*\*\s*\n\n(.*?)(?=\n\*\*|\n## |\Z)"
    matches = list(re.finditer(pattern, section, re.DOTALL))
    assert len(matches) == 1, (
        "register-check.md: expected exactly one **Exit codes:** label, found %d"
        % len(matches)
    )
    pairs = re.findall(
        r"^- `(\d+)` — (\w+)",
        matches[0].group(1),
        re.MULTILINE,
    )
    assert pairs, (
        "register-check.md: **Exit codes:** bullet list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return {int(code): word for code, word in pairs}


def _register_check_exit_codes_from_home():
    import register_check

    return {
        register_check.EXIT_PASS: register_check.RESULT_PASS,
        register_check.EXIT_FAIL: register_check.RESULT_FAIL,
        register_check.EXIT_UNRUNNABLE: register_check.RESULT_UNRUNNABLE,
    }


def test_register_check_schema_in_register_check_doc():
    """§11: register-check.md restates register_check.SCHEMA."""
    import register_check

    home = {register_check.SCHEMA}
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_schema_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "register-check.md Schema vocabulary drift from register_check.SCHEMA — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


def test_register_check_results_in_register_check_doc():
    """§11: register-check.md restates register_check.RESULTS."""
    import register_check

    home = set(register_check.RESULTS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_results_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "register-check.md Results vocabulary drift from register_check.RESULTS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


def test_register_check_finding_kinds_in_register_check_doc():
    """§11: register-check.md restates register_check.FINDING_KINDS."""
    import register_check

    home = set(register_check.FINDING_KINDS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_finding_kinds_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "register-check.md Finding kinds vocabulary drift from "
        "register_check.FINDING_KINDS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


def test_register_check_unrunnable_reasons_in_register_check_doc():
    """§11: register-check.md restates register_check.UNRUNNABLE_REASONS."""
    import register_check

    home = set(register_check.UNRUNNABLE_REASONS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_unrunnable_reasons_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "register-check.md Unrunnable reasons vocabulary drift from "
        "register_check.UNRUNNABLE_REASONS — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_from_doc, extra_in_doc)
    )


def test_register_check_exit_codes_in_register_check_doc():
    """§11: register-check.md restates register_check exit-code mapping."""
    home = _register_check_exit_codes_from_home()
    doc = _read(_REGISTER_CHECK_DOC)
    doc_mapping = _register_check_exit_codes_from_doc(doc)
    missing_from_doc = sorted(
        code for code in home if code not in doc_mapping
    )
    extra_in_doc = sorted(
        code for code in doc_mapping if code not in home
    )
    value_mismatches = sorted(
        code for code in home
        if code in doc_mapping and doc_mapping[code] != home[code]
    )
    assert (
        not missing_from_doc
        and not extra_in_doc
        and not value_mismatches
    ), (
        "register-check.md Exit codes mapping drift from register_check "
        "EXIT_*/RESULT_* — missing from doc: %r; present in doc but not in "
        "home: %r; value mismatches: %r"
        % (missing_from_doc, extra_in_doc, value_mismatches)
    )


def test_register_check_vocabulary_completeness():
    """Every register_check RESULT_*/KIND_*/UNRUNNABLE_* constant is in its frozenset."""
    import register_check

    derived_results = _register_check_string_constants_by_prefix("RESULT_")
    derived_kinds = _register_check_string_constants_by_prefix("KIND_")
    derived_unrunnable = _register_check_string_constants_by_prefix("UNRUNNABLE_")
    home_results = set(register_check.RESULTS)
    home_kinds = set(register_check.FINDING_KINDS)
    home_unrunnable = set(register_check.UNRUNNABLE_REASONS)
    missing_results = sorted(derived_results - home_results)
    extra_results = sorted(home_results - derived_results)
    missing_kinds = sorted(derived_kinds - home_kinds)
    extra_kinds = sorted(home_kinds - derived_kinds)
    missing_unrunnable = sorted(derived_unrunnable - home_unrunnable)
    extra_unrunnable = sorted(home_unrunnable - derived_unrunnable)
    assert not missing_results and not extra_results, (
        "register_check RESULT_* constants drift from register_check.RESULTS — "
        "missing from frozenset: %r; in frozenset but not derived: %r"
        % (missing_results, extra_results)
    )
    assert not missing_kinds and not extra_kinds, (
        "register_check KIND_* constants drift from register_check.FINDING_KINDS — "
        "missing from frozenset: %r; in frozenset but not derived: %r"
        % (missing_kinds, extra_kinds)
    )
    assert not missing_unrunnable and not extra_unrunnable, (
        "register_check UNRUNNABLE_* constants drift from "
        "register_check.UNRUNNABLE_REASONS — "
        "missing from frozenset: %r; in frozenset but not derived: %r"
        % (missing_unrunnable, extra_unrunnable)
    )
