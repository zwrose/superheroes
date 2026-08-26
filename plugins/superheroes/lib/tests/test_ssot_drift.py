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
- Omission floor + PR-body marker semantics (§10.7)   (home: CONVENTIONS.md §10.7;
  copy-holders: review-discipline.md, workhorse §11, review-code step 8, grounding_stage.py)
- Session modes                                       (home: review_base_guard.py;
  copy-holder: grounding_stage.py)
- `configRead` CLI field set                             (home: preflight_probe.py)
- Wave-watch vocabulary                                  (home: wave_watch.py)
- Issue-contract vocabulary                              (home: issue_contract.py)
- Register-check vocabulary                              (home: register_check.py)
- Package-read-audit vocabulary                          (home: package_read_audit.py;
  copy-holder: skills/showrunner/reference/decomposition.md § The audit trail)
- R5 weight vocabulary + R7 park surface (pinned literals) (home: epic register when
  reachable; copy-holders: architect-discovery, showrunner SKILL.md, epic children)
- Anchor invariant clauses + inversions       (home: skills/showrunner/reference/issue-contract.md;
  copy-holders: skills/workhorse/SKILL.md (operative resolution bullets, log-side paragraph,
  stop), skills/showrunner/SKILL.md (filing, repair, notice and standing-row clauses),
  skills/showrunner/reference/vet-receipt.md (owner-half delivery clause))
- Pre-doctrine on-ramp structure (home: skills/showrunner/reference/issue-contract.md
  § Pre-doctrine issues; copy-holder: skills/workhorse/SKILL.md anchor-intake repair
  template)
- Four-route drift (R6 register → two charters + five prose/registry copies) (home:
  docs/superheroes/front-half-sdlc-core-6181ee/register.md R6; copy-holders: skills/showrunner/SKILL.md
  routing block + frontmatter description, skills/workhorse/SKILL.md §1 intake,
  skills/configure/reference/preflight.md §E, README.md Showrunner section, CONVENTIONS.md Showrunner
  cast bullet, eval/skills/registry.json requiredPhrases)
- Investigation floor (spot_check_investigated → dispatch-mechanics.md § Findings-only,
  auto-fix-loop.md vacuous-forfeit block)

The reviewer-roster and docs-location clusters live in their topical sibling guards
(test_dispatch_tables.py, test_definition_doc.py).
"""
import json
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
    assert list(circuit_breaker.SEVERITY_TIERS) == tiers, "circuit_breaker.SEVERITY_TIERS order/vocab drift"
    assert {t: i for i, t in enumerate(circuit_breaker.SEVERITY_TIERS)} == rank, (
        "circuit_breaker.SEVERITY_TIERS rank drift")
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


# --- Cluster: gap-sweep stale-landing token (round_records → round-driver.md) -

def test_stale_landing_refusal_token_in_round_driver_doc():
    """§11: round-driver.md's gap-sweep re-emission trap restates round_records.py's own
    `stale-landing` sweep refusal literally — a rename of that refusal reason would silently
    strand the doc's recovery guidance behind a token `record-result --sweep` no longer emits."""
    home = _read(os.path.join("lib", "round_records.py"))
    assert '_refuse("stale-landing"' in home, (
        "round_records.py: expected literal `_refuse(\"stale-landing\", ...)` call not found "
        "(renamed/refactored? update this pin's home check along with the rename)"
    )
    doc = _read("skills/review-code/reference/round-driver.md")
    assert "stale-landing" in doc, (
        "round-driver.md: gap-sweep re-emission trap must name the `stale-landing` refusal "
        "that round_records.sweep_landing raises when a stray landing file maps to no roster "
        "slot in the current manifest"
    )


# --- Cluster: sweep-supersede-unsupported token (round_driver → round-driver.md) -

def test_sweep_supersede_unsupported_refusal_token_in_round_driver_doc():
    """§11: round-driver.md restates round_driver.py's `sweep-supersede-unsupported` refusal
    literally — a rename would strand the doc's recovery guidance behind a token
    `record-result --sweep --supersede` no longer emits."""
    home = _read(os.path.join("lib", "round_driver.py"))
    assert "sweep-supersede-unsupported" in home, (
        "round_driver.py: expected literal `sweep-supersede-unsupported` refusal token not found "
        "(renamed/refactored? update this pin's home check along with the rename)"
    )
    doc = _read("skills/review-code/reference/round-driver.md")
    assert "sweep-supersede-unsupported" in doc, (
        "round-driver.md: must name the `sweep-supersede-unsupported` refusal that "
        "record-result --sweep returns when combined with --supersede or --expect-sha256"
    )


# --- Cluster: addressed-seat unknown-seat token (round_records → round-driver.md) -

def test_unknown_seat_addressed_seat_refusal_token_in_round_driver_doc():
    """§11: round-driver.md distinguishes `unknown-seat` (addressed seat not on roster) from
    `stale-landing` (sweep stray file) — both tokens must stay literal so a cleanup cannot
    collapse them back into one."""
    home = _read(os.path.join("lib", "round_records.py"))
    assert '_refuse("unknown-seat"' in home, (
        "round_records.py: expected literal `_refuse(\"unknown-seat\", ...)` call not found "
        "(renamed/refactored? update this pin's home check along with the rename)"
    )
    doc = _read("skills/review-code/reference/round-driver.md")
    assert "unknown-seat" in doc, (
        "round-driver.md: must name the `unknown-seat` refusal for an addressed seat "
        "(`record-result --seat <key>`) that is not on the current roster — distinct from "
        "the sweep's `stale-landing` stray-file refusal"
    )


# --- Cluster: plugin-version-skew status vocabulary (version_skew → setup.md, CONVENTIONS.md) -


def _plugin_version_skew_statuses_from_home():
    import version_skew

    return set(version_skew.STATUSES)


def _plugin_version_skew_certification_statuses_from_home():
    """Values ``_plugin_version_skew_status`` can project into certification disclosure."""
    import inspect
    import re

    import round_driver
    import version_skew

    src = inspect.getsource(round_driver._plugin_version_skew_status)
    literals = set(re.findall(r'return "([^"]+)"', src))
    assert literals, (
        "_plugin_version_skew_status: no string-literal return values discovered"
    )
    if "return status" in src and "version_skew.STATUSES" in src:
        literals |= set(version_skew.STATUSES)
    return literals


def _certification_plugin_version_skew_disclosure_block(doc):
    m = re.search(
        r"`pluginVersionSkew`\s*—\s*tri-state skew\s*disclosure:\s*(.*?),\s*`shapeDrivers`",
        doc,
        re.DOTALL,
    )
    assert m, (
        "round-driver.md: certification pluginVersionSkew disclosure block not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _certification_plugin_version_skew_enumeration_tokens(doc):
    block = _certification_plugin_version_skew_disclosure_block(doc)
    candidates = set(re.findall(r"`([^`]+)`", block))
    structural = {
        "pluginVersionSkew",
        "seatMap.pluginVersionSkew",
        "status",
        "detail",
        "inspectedRoot",
    }
    return {t for t in candidates if t not in structural and "." not in t}


_PLUGIN_VERSION_SKEW_SKEW_CONTEXT_MARKERS = (
    "plugin-version-skew",
    "pluginVersionSkew",
)

_PLUGIN_VERSION_SKEW_STATUS_TOKEN_COPY_REGISTER = {
    os.path.normpath(os.path.join(PLUGIN, "..", "..", "CONVENTIONS.md")): frozenset({
        "checked-clean",
        "checked-degraded",
    }),
    os.path.normpath(os.path.join(PLUGIN, "..", "..", "LEDGERS.md")): frozenset({
        "checked-degraded",
    }),
    os.path.normpath(os.path.join(PLUGIN, "skills/review-code/reference/setup.md")): frozenset({
        "checked-clean",
        "checked-degraded",
        "not-checked",
    }),
    os.path.normpath(os.path.join(PLUGIN, "skills/review-code/reference/round-driver.md")): frozenset({
        "checked-clean",
        "checked-degraded",
        "not-checked",
    }),
}

_PLUGIN_VERSION_SKEW_DETAIL_TOKEN_COPY_REGISTER = {
    os.path.normpath(os.path.join(PLUGIN, "..", "..", "CONVENTIONS.md")): frozenset({
        "semantics-divergent",
        "evidence-unreadable",
    }),
    os.path.normpath(os.path.join(PLUGIN, "..", "..", "LEDGERS.md")): frozenset({
        "semantics-divergent",
        "evidence-unreadable",
    }),
    os.path.normpath(os.path.join(PLUGIN, "skills/review-code/reference/round-driver.md")): frozenset({
        "semantics-divergent",
        "evidence-unreadable",
    }),
    os.path.normpath(os.path.join(
        PLUGIN, "skills/review-code/reference/auto-fix-loop.md",
    )): frozenset({
        "semantics-divergent",
        "evidence-unreadable",
    }),
}

_PLUGIN_VERSION_SKEW_APPEND_RULE_DOCS = (
    os.path.normpath(os.path.join(PLUGIN, "..", "..", "CONVENTIONS.md")),
    os.path.normpath(os.path.join(PLUGIN, "skills/review-code/reference/setup.md")),
)


def _repo_markdown_files():
    root = os.path.normpath(os.path.join(PLUGIN, "..", ".."))
    tests_root = os.path.normpath(os.path.join(PLUGIN, "lib", "tests"))
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        if os.path.commonpath([dirpath, tests_root]) == tests_root:
            continue
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def _semantics_files_mentioned_on_line(line, semantics_files):
    return [entry for entry in semantics_files if entry in line]


def _skew_context_blocks(text):
    blocks = []
    current = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


_PLUGIN_VERSION_SKEW_STATUS_EXTRACTION_ANCHORS = (
    "tri-state skew",
    "`status` one of",
)


def _skew_status_scan_text(block):
    for anchor in _PLUGIN_VERSION_SKEW_STATUS_EXTRACTION_ANCHORS:
        idx = block.find(anchor)
        if idx != -1:
            return block[idx:]
    return block


def _skew_token_present_in_block(block, token):
    if ("`%s`" % token) in block:
        return True
    return re.search(
        r'(?<![\w-])%s(?![\w-])' % re.escape(token),
        block,
    ) is not None


def _skew_status_tokens_in_text(text, home_statuses):
    found = set()
    for block in _skew_context_blocks(text):
        if not any(marker in block for marker in _PLUGIN_VERSION_SKEW_SKEW_CONTEXT_MARKERS):
            continue
        scan = _skew_status_scan_text(block)
        for token in home_statuses:
            if _skew_token_present_in_block(scan, token):
                found.add(token)
    return found


def _skew_detail_tokens_in_text(text, home_details):
    found = set()
    for block in _skew_context_blocks(text):
        if not any(marker in block for marker in _PLUGIN_VERSION_SKEW_SKEW_CONTEXT_MARKERS):
            continue
        for token in home_details:
            if _skew_token_present_in_block(block, token):
                found.add(token)
    return found


def test_repo_markdown_files_excludes_tests_but_keeps_registered_docs():
    """Anti-vacuity: lib/tests/*.md bite-proof records must not census; registered docs must."""
    paths = {os.path.normpath(p) for p in _repo_markdown_files()}
    register_paths = set(_PLUGIN_VERSION_SKEW_STATUS_TOKEN_COPY_REGISTER)
    assert register_paths <= paths, (
        "registered plugin-version-skew status-token copies missing from census: %r"
        % sorted(register_paths - paths)
    )
    detail_register_paths = set(_PLUGIN_VERSION_SKEW_DETAIL_TOKEN_COPY_REGISTER)
    assert detail_register_paths <= paths, (
        "registered plugin-version-skew detail-token copies missing from census: %r"
        % sorted(detail_register_paths - paths)
    )
    tests_prefix = os.path.normpath(os.path.join(PLUGIN, "lib", "tests")) + os.sep
    under_tests = [p for p in paths if p.startswith(tests_prefix)]
    assert not under_tests, (
        "lib/tests markdown must be excluded from doc census: %r"
        % sorted(os.path.relpath(p, os.path.join(PLUGIN, "..", "..")) for p in under_tests)
    )


def test_plugin_version_skew_watch_set_doc_census():
    """§11: any doc line naming two+ SEMANTICS_FILES must name all of them."""
    import version_skew

    semantics_files = tuple(version_skew.SEMANTICS_FILES)
    violations = []
    for path in _repo_markdown_files():
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                mentioned = _semantics_files_mentioned_on_line(line, semantics_files)
                if len(mentioned) < 2:
                    continue
                missing = sorted(set(semantics_files) - set(mentioned))
                if missing:
                    rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
                    violations.append((rel, lineno, missing))
    assert not violations, (
        "watch-set restatement missing SEMANTICS_FILES entries — "
        "file, line, missing: %r" % violations
    )


def test_plugin_version_skew_status_token_copy_register_census():
    """§11: every .md carrying a skew-scoped STATUSES token must be in the copy register."""
    import version_skew

    home = _plugin_version_skew_statuses_from_home()
    examined = 0
    unregistered = []
    for path in _repo_markdown_files():
        examined += 1
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if not _skew_status_tokens_in_text(text, home):
            continue
        norm = os.path.normpath(path)
        if norm not in _PLUGIN_VERSION_SKEW_STATUS_TOKEN_COPY_REGISTER:
            rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
            unregistered.append(rel)
    assert examined > 0, (
        "plugin-version-skew status-token census examined zero markdown files (vacuous)"
    )
    assert not unregistered, (
        "unregistered plugin-version-skew status-token copy — add to "
        "_PLUGIN_VERSION_SKEW_STATUS_TOKEN_COPY_REGISTER: %r" % sorted(unregistered)
    )


def test_plugin_version_skew_status_token_copy_register_content():
    """§11: each registered STATUSES holder's skew-scoped tokens match the register contract."""
    import version_skew

    home = _plugin_version_skew_statuses_from_home()
    violations = []
    for path, expected in _PLUGIN_VERSION_SKEW_STATUS_TOKEN_COPY_REGISTER.items():
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        actual = _skew_status_tokens_in_text(text, home)
        if actual != expected:
            rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
            violations.append((rel, sorted(expected), sorted(actual)))
    assert not violations, (
        "plugin-version-skew status-token copy content drift — "
        "path, expected, actual: %r" % violations
    )


def test_plugin_version_skew_detail_token_copy_register_census():
    """§11: every .md carrying a skew-scoped DETAILS token must be in the detail register."""
    import version_skew

    home = set(version_skew.DETAILS)
    examined = 0
    unregistered = []
    for path in _repo_markdown_files():
        examined += 1
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if not _skew_detail_tokens_in_text(text, home):
            continue
        norm = os.path.normpath(path)
        if norm not in _PLUGIN_VERSION_SKEW_DETAIL_TOKEN_COPY_REGISTER:
            rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
            unregistered.append(rel)
    assert examined > 0, (
        "plugin-version-skew detail-token census examined zero markdown files (vacuous)"
    )
    assert not unregistered, (
        "unregistered plugin-version-skew detail-token copy — add to "
        "_PLUGIN_VERSION_SKEW_DETAIL_TOKEN_COPY_REGISTER: %r" % sorted(unregistered)
    )


def test_plugin_version_skew_detail_token_copy_register_content():
    """§11: each registered DETAILS holder's skew-scoped tokens match the register contract."""
    import version_skew

    home = set(version_skew.DETAILS)
    violations = []
    for path, expected in _PLUGIN_VERSION_SKEW_DETAIL_TOKEN_COPY_REGISTER.items():
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        actual = _skew_detail_tokens_in_text(text, home)
        if actual != expected:
            rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
            violations.append((rel, sorted(expected), sorted(actual)))
    assert not violations, (
        "plugin-version-skew detail-token copy content drift — "
        "path, expected, actual: %r" % violations
    )


def test_plugin_version_skew_degrading_details_consumer(tmp_path):
    """§11: DEGRADING_DETAILS is the set of detail values detect() returns on degrading paths."""
    import version_skew

    assert version_skew.DEGRADING_DETAILS <= version_skew.DETAILS
    degrading_details = set()

    repo = tmp_path / "repo"
    _write_skew_manifest(repo)
    _write_skew_version_txt(repo)
    _copy_skew_semantics_to(repo)
    plugin_root = tmp_path / "plugin"
    _write_skew_plugin_tree(plugin_root, model_registry_suffix="# divergent\n")
    semantics_record = version_skew.detect(str(repo), str(plugin_root))
    assert semantics_record["status"] == version_skew.STATUS_CHECKED_DEGRADED
    degrading_details.add(semantics_record["detail"])

    unreadable_repo = tmp_path / "repo-unreadable"
    _write_skew_manifest(unreadable_repo)
    _write_skew_version_txt(unreadable_repo)
    _copy_skew_semantics_to(unreadable_repo)
    unreadable_plugin = tmp_path / "plugin-unreadable"
    _write_skew_plugin_tree(unreadable_plugin)
    seat_map_path = unreadable_repo / "plugins" / "superheroes" / "lib" / "seat_map.py"
    seat_map_path.unlink()
    unreadable_record = version_skew.detect(str(unreadable_repo), str(unreadable_plugin))
    assert unreadable_record["status"] == version_skew.STATUS_CHECKED_DEGRADED
    degrading_details.add(unreadable_record["detail"])

    assert degrading_details == version_skew.DEGRADING_DETAILS, (
        "detect() degrading-path details %r != version_skew.DEGRADING_DETAILS %r"
        % (sorted(degrading_details), sorted(version_skew.DEGRADING_DETAILS))
    )


def _write_skew_manifest(base, name="superheroes"):
    path = base / "plugins" / "superheroes" / ".claude-plugin" / "plugin.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"name": name, "version": "0.30.0"}), encoding="utf-8")


def _write_skew_version_txt(base, version="0.31.0"):
    path = base / "plugins" / "superheroes" / "version.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version + "\n", encoding="utf-8")


def _copy_skew_semantics_to(base):
    import version_skew

    lib = base / "plugins" / "superheroes" / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in version_skew.SEMANTICS_FILES:
        src = os.path.join(PLUGIN, entry)
        dst = lib / os.path.basename(entry)
        dst.write_text(open(src, encoding="utf-8").read(), encoding="utf-8")


def _write_skew_plugin_tree(plugin_root, model_registry_suffix=""):
    import version_skew

    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"name": "superheroes", "version": "0.29.0"}), encoding="utf-8")
    lib = plugin_root / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    for entry in version_skew.SEMANTICS_FILES:
        src = os.path.join(PLUGIN, entry)
        content = open(src, encoding="utf-8").read()
        if model_registry_suffix and entry == "lib/model_registry.py":
            content = content + model_registry_suffix
        (lib / os.path.basename(entry)).write_text(content, encoding="utf-8")


def test_plugin_version_skew_append_rule_phrase_pin():
    """§11: append-rule prose is generated from version_skew.APPENDS_DEGRADATION."""
    import version_skew

    appends = version_skew.APPENDS_DEGRADATION
    assert len(appends) == 1, (
        "APPENDS_DEGRADATION changed (%r) — update the doc phrasing contract in this test"
        % sorted(appends)
    )
    status = next(iter(appends))
    required_phrase = "only `%s` appends" % status
    missing = []
    for path in _PLUGIN_VERSION_SKEW_APPEND_RULE_DOCS:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if required_phrase not in text:
            rel = os.path.relpath(path, os.path.join(PLUGIN, "..", ".."))
            missing.append(rel)
    assert not missing, (
        "append-rule phrase %r missing from: %r" % (required_phrase, missing)
    )


def _plugin_python_sources_excluding_tests():
    paths = []
    for dirpath, dirnames, filenames in os.walk(PLUGIN):
        if os.path.basename(dirpath) == "tests" or "tests" in dirpath.split(os.sep):
            continue
        dirnames[:] = [d for d in dirnames if d != "__pycache__" and d != "tests"]
        for name in filenames:
            if name.endswith(".py"):
                paths.append(os.path.join(dirpath, name))
    return paths


def test_plugin_version_skew_chokepoint_census():
    """§11: only version_skew.py may reference STATUS_CHECKED_DEGRADED or checked-degraded."""
    import version_skew

    home = os.path.join(PLUGIN, "lib", "version_skew.py")
    violations = []
    for path in _plugin_python_sources_excluding_tests():
        if os.path.normpath(path) == os.path.normpath(home):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        rel = os.path.relpath(path, PLUGIN)
        if "STATUS_CHECKED_DEGRADED" in text:
            violations.append((rel, "STATUS_CHECKED_DEGRADED"))
        if '"checked-degraded"' in text or "'checked-degraded'" in text:
            violations.append((rel, "checked-degraded literal"))
    assert not violations, (
        "plugin-version-skew chokepoint violation outside version_skew.py: %r" % violations
    )
    seat_map_text = _read("lib/seat_map.py")
    assert "appends_degradation(" in seat_map_text, (
        "seat_map.py must call version_skew.appends_degradation("
    )


def test_plugin_version_skew_status_vocabulary_in_docs():
    """§11: setup.md and CONVENTIONS.md restate version_skew.STATUSES; round-driver.md
    restates the certification ``pluginVersionSkew`` projection vocabulary."""
    import version_skew

    home = _plugin_version_skew_statuses_from_home()
    cert_home = _plugin_version_skew_certification_statuses_from_home()
    setup = _read("skills/review-code/reference/setup.md")
    missing_setup = sorted(token for token in home if token not in setup)
    assert not missing_setup, (
        "setup.md missing plugin-version-skew status token(s) from version_skew.STATUSES: %r"
        % missing_setup
    )
    conventions = _read("../../CONVENTIONS.md")
    missing_conventions = []
    for token in (version_skew.STATUS_CHECKED_CLEAN, version_skew.STATUS_CHECKED_DEGRADED):
        if token not in conventions:
            missing_conventions.append(token)
    if (
        version_skew.STATUS_NOT_CHECKED not in conventions
        and "never-checked" not in conventions
    ):
        missing_conventions.append(
            "%s (CONVENTIONS prose uses never-checked)" % version_skew.STATUS_NOT_CHECKED
        )
    assert not missing_conventions, (
        "CONVENTIONS.md missing plugin-version-skew status vocabulary from "
        "version_skew.STATUSES: %r" % missing_conventions
    )
    round_driver_doc = _read("skills/review-code/reference/round-driver.md")
    doc_tokens = _certification_plugin_version_skew_enumeration_tokens(round_driver_doc)
    assert doc_tokens == cert_home, (
        "round-driver.md certification pluginVersionSkew enumeration drift — "
        "expected %r, doc enumerates %r"
        % (sorted(cert_home), sorted(doc_tokens))
    )


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


def _review_result_kind_quoted_tokens_from_doc_block(block):
    return set(re.findall(r'`"([^"]+)"`', block))


_REVIEW_RESULT_KIND_ENUM_COPY_COUNTS = {
    "skills/review-code/reference/auto-fix-loop.md": 3,
    "skills/workhorse/reference/dispatch-mechanics.md": 2,
}


def _review_result_kind_enum_copies_from_doc(doc):
    """Every resultKind enumeration copy in a doc file."""
    pattern_specs = [
        (
            r"\(one of\s*([^)]*)\)\s*naming the payload",
            _review_result_kind_tokens_from_doc_block,
        ),
        (
            r"\(([^)]*)\)\s*naming which payload",
            _review_result_kind_tokens_from_doc_block,
        ),
        (
            r'exactly ((?:`"[^"]+"`)(?:\s+or\s+`"[^"]+"`)+)',
            _review_result_kind_quoted_tokens_from_doc_block,
        ),
        (
            r"\(`REVIEW_RESULT_KINDS`:\s*([^)]*)\)",
            _review_result_kind_tokens_from_doc_block,
        ),
    ]
    copies = []
    for pat, tokens_from_block in pattern_specs:
        for m in re.finditer(pat, doc):
            tokens = tokens_from_block(m.group(1))
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


# --- Cluster: investigation floor (engine_adapter.spot_check_investigated → prose copies) ---

_DISPATCH_MECHANICS_DOC = "skills/workhorse/reference/dispatch-mechanics.md"
_AUTO_FIX_LOOP_DOC = "skills/review-code/reference/auto-fix-loop.md"


def _spot_check_investigated_source():
    import inspect

    import engine_adapter

    try:
        return inspect.getsource(engine_adapter.spot_check_investigated)
    except (OSError, TypeError) as exc:
        pytest.fail(
            "spot_check_investigated floor could not be read from engine_adapter: %s" % exc
        )


def _investigation_floor_operative_clauses_from_home():
    """Operative clauses from spot_check_investigated — fails closed when unparseable."""
    source = _spot_check_investigated_source()
    checks = (
        (r"not isinstance\(investigated,\s*list\)\s+or\s+not\s+investigated", "non-empty list"),
        (r"len\(accepted\)\s*>=\s*1", "at-least-one accepted-path threshold"),
        (r"os\.path\.isabs\(entry\)", "absolute-path rejection"),
        (r"not os\.path\.exists\(real\)", "missing-path rejection"),
        (r"not os\.path\.isfile\(real\)", "regular-file requirement"),
        (
            r"real != root_real and not real\.startswith\(root_prefix\)",
            "repo-confinement check",
        ),
        (r"generated-artifact", "generated-artifact rejection"),
        (r"A spot check, not an audit:", "spot-check audit clause in docstring"),
    )
    missing = [label for pat, label in checks if not re.search(pat, source, re.I)]
    assert not missing, (
        "spot_check_investigated floor could not be parsed — missing: %r" % missing
    )


def _investigation_floor_threshold_token_from_home():
    """Normalized quantity threshold from spot_check_investigated's docstring.

    Locates the operative clause structurally (introduced by ``A spot check, not an audit:``)
    rather than by searching for the token under test. The load-bearing agreement with
    document copies is the quantity threshold (``at least one`` vs ``ideally one``, etc.).
    """
    source = _spot_check_investigated_source()
    m = re.search(
        r"A spot check, not an audit:\s*([^.]+)\.",
        source,
        re.I,
    )
    assert m, (
        "spot_check_investigated floor could not be parsed — spot-check audit clause"
    )
    clause = m.group(1).strip()
    token_m = re.search(
        r"(?:at\s+least\s+one|ideally\s+one|exactly\s+one)",
        clause,
        re.I,
    )
    assert token_m, (
        "spot_check_investigated floor could not be parsed — quantity threshold in docstring"
    )
    return token_m.group(0).lower()


def _investigation_floor_threshold_token_from_prose(text, label):
    """Normalized quantity threshold from a document's investigation-floor prose."""
    token_m = re.search(
        r"(?:at\s+least\s+one|ideally\s+one|exactly\s+one)",
        text,
        re.I,
    )
    assert token_m, (
        "%s: investigation floor threshold could not be parsed from prose" % label
    )
    return token_m.group(0).lower()


def _assert_investigation_floor_threshold_matches_home(home_token, doc_text, label):
    """Home↔doc binding: quantity threshold in prose must match spot_check_investigated."""
    doc_token = _investigation_floor_threshold_token_from_prose(doc_text, label)
    assert home_token == doc_token, (
        "investigation floor drift: %s and spot_check_investigated disagree on "
        "at-least-one surviving-path threshold (home=%r, doc=%r)"
        % (label, home_token, doc_token)
    )


def _dispatch_mechanics_investigated_threshold_prose(doc):
    """Operative threshold sentence in dispatch-mechanics — scoped pin."""
    m = re.search(
        r"`investigated`\s+is present only when\s+(.+?)\s+spot-checking",
        doc,
        re.I,
    ) or re.search(
        r"\*\*`investigated`\*\*\s+is present only when\s+(.+?)\s+spot-checking",
        doc,
        re.I,
    )
    assert m, (
        "dispatch-mechanics.md: investigation-floor threshold pin could not be located "
        "(moved or reformatted?)"
    )
    return m.group(0)


def _dispatch_mechanics_findings_only_section(doc):
    """Findings-only review prompts — scoped to that subsection only."""
    m = re.search(
        r"### Findings-only review prompts\n(.*?)(?=\nEvery `dispatch-review`|\n### )",
        doc,
        re.DOTALL,
    )
    assert m, (
        "dispatch-mechanics.md: Findings-only review prompts pin could not be located "
        "(moved or reformatted?)"
    )
    return m.group(1)


def _auto_fix_loop_investigation_floor_block(doc):
    """Vacuous-forfeit requirement block — scoped to the operative clause only."""
    m = re.search(
        r"`findings` array is accepted as \*clean\* \*\*only\*\* when `investigated` lists "
        r".*?\*\*vacuous forfeit\*\*",
        doc,
        re.DOTALL | re.I,
    )
    assert m, (
        "auto-fix-loop.md: investigation-floor requirement pin could not be located "
        "(moved or reformatted?)"
    )
    return m.group(0)


def _assert_dispatch_mechanics_investigation_floor_prose(text, label):
    """Operative prose clauses dispatch-mechanics must carry."""
    lower = text.lower()
    missing = []
    if not re.search(r"populated\s+`investigated`", text, re.I):
        missing.append("populated investigated required")
    if "vacuous" not in lower:
        missing.append("vacuous forfeit")
    assert not missing, (
        "%s: investigation floor prose drift — missing: %r" % (label, missing)
    )


def _assert_auto_fix_loop_investigation_floor_prose(text, label):
    """Operative prose clauses auto-fix-loop must carry."""
    lower = text.lower()
    missing = []
    if not re.search(r"`investigated`\s+lists\s+at\s+least\s+one\s+path", text, re.I):
        missing.append("investigated lists at least one path required")
    if "vacuous" not in lower:
        missing.append("vacuous forfeit")
    assert not missing, (
        "%s: investigation floor prose drift — missing: %r" % (label, missing)
    )


def test_investigation_floor_prose_matches_spot_check_investigated():
    """§11: investigation-floor guidance in every copy-holder matches spot_check_investigated.

    Copy-holders: skills/workhorse/reference/dispatch-mechanics.md (Findings-only review prompts),
    skills/review-code/reference/auto-fix-loop.md (vacuous-forfeit block).
    """
    _investigation_floor_operative_clauses_from_home()
    home_threshold = _investigation_floor_threshold_token_from_home()

    dispatch_doc = _read(_DISPATCH_MECHANICS_DOC)
    dispatch_section = _dispatch_mechanics_findings_only_section(dispatch_doc)
    _assert_dispatch_mechanics_investigation_floor_prose(
        dispatch_section, "dispatch-mechanics.md (Findings-only review prompts)"
    )
    assert "spot_check_investigated" in dispatch_section, (
        "dispatch-mechanics.md: investigation floor must name engine_adapter.spot_check_investigated"
    )
    assert re.search(r"repo-relative path to an existing", dispatch_section, re.I), (
        "dispatch-mechanics.md: surviving-path entry requirements drift"
    )
    dispatch_threshold_prose = _dispatch_mechanics_investigated_threshold_prose(dispatch_doc)
    _assert_investigation_floor_threshold_matches_home(
        home_threshold,
        dispatch_threshold_prose,
        "dispatch-mechanics.md (investigated threshold)",
    )

    auto_fix_doc = _read(_AUTO_FIX_LOOP_DOC)
    auto_fix_block = _auto_fix_loop_investigation_floor_block(auto_fix_doc)
    _assert_investigation_floor_threshold_matches_home(
        home_threshold,
        auto_fix_block,
        "auto-fix-loop.md (vacuous-forfeit block)",
    )
    _assert_auto_fix_loop_investigation_floor_prose(
        auto_fix_block, "auto-fix-loop.md (vacuous-forfeit block)"
    )
    assert re.search(r"at least one path", auto_fix_block, re.I), (
        "auto-fix-loop.md: at-least-one surviving-path threshold drift"
    )


def test_review_result_kind_enum_recognizer_cardinality_independent():
    """Recognizer yields full token sets for two-member and four-member phrasings."""
    shape_pairs = [
        (
            "(one of `findings`, `verdicts`) naming the payload",
            "(one of `findings`, `verdicts`, `grouping`, `ruling`) naming the payload",
        ),
        (
            "(`findings` or `verdicts`) naming which payload",
            "(`findings` or `verdicts` or `grouping` or `ruling`) naming which payload",
        ),
        (
            'exactly `"findings"` or `"verdicts"`',
            'exactly `"findings"` or `"verdicts"` or `"grouping"` or `"ruling"`',
        ),
        (
            "(`REVIEW_RESULT_KINDS`: `findings`, `verdicts`)",
            "(`REVIEW_RESULT_KINDS`: `findings`, `verdicts`, `grouping`, `ruling`)",
        ),
    ]
    for two_member, four_member in shape_pairs:
        two_tokens = _review_result_kind_enum_copies_from_doc(two_member)[0]
        four_tokens = _review_result_kind_enum_copies_from_doc(four_member)[0]
        assert two_tokens == {"findings", "verdicts"}
        assert four_tokens == {
            "findings", "verdicts", "grouping", "ruling",
        }


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

# Hard-line sentence pin: §10.7's missing-marker rule names both floor markers byte-for-byte.
_SECTION_10_7_MISSING_MARKER_SENTENCE = (
    "A **missing** `<!-- superheroes:build-record -->` boundary marker or a **missing**\n"
    "`<!-- superheroes:degradations -->` section is **itself** a review finding — same\n"
    "**Important** / `tradeoff` / author-resolved shape as the DoD-table check, not a silent\n"
    "pass."
)

# Contiguous literal-agreement pins: each copy-holder's three-row omission-floor enumeration.
_OMISSION_FLOOR_ENUMERATION_PINS = {
    "rubric/review-discipline.md (Ship-phase honesty)": (
        "(1) every **deferred** DoD row; (2) every **blocking or important** review finding that was\n"
        "  **not fixed**, whatever its disposition is called; (3) every **disclosed degradation**."
    ),
    "skills/workhorse/SKILL.md §11": (
        "(1) every\n"
        "  **deferred** DoD row; (2) every **blocking or important** review finding that was **not fixed**,\n"
        "  whatever its disposition is called; (3) every **disclosed degradation**."
    ),
    "skills/review-code/SKILL.md step 8": (
        "enumerate (1) each deferred DoD row, (2) each blocking or important dispositions-table "
        "finding not fixed (by severity, not disposition label), and (3) each disclosed degradation "
        "under `<!-- superheroes:degradations -->` (bullets, or **None** when empty)"
    ),
}


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
    assert "is **itself** a review finding" in home, (
        "§10.7 missing-marker rule not found (moved or reworded?)"
    )
    assert (
        "A **missing** `<!-- superheroes:build-record -->`" in home
        and "review finding" in home
    ), "§10.7 missing-marker-as-finding rule not found"
    home_norm = _anchor_whitespace_normalize(home)
    sentence_norm = _anchor_whitespace_normalize(_SECTION_10_7_MISSING_MARKER_SENTENCE)
    assert sentence_norm in home_norm, (
        "§10.7 missing-marker sentence drift — _SECTION_10_7_MISSING_MARKER_SENTENCE "
        "not found in home (reworded?)"
    )
    floor_from_sentence = re.findall(
        r"(<!-- superheroes:[^>]+ -->)", _SECTION_10_7_MISSING_MARKER_SENTENCE
    )
    assert set(floor_from_sentence) == set(_FLOOR_MARKERS), (
        "the floor family must be derived from the home, not reclassified in the test"
    )
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


def _grounding_stage_region_markers_from_home(home):
    """Derive grounding_stage.REGION_MARKERS from §10.7 — the four PR-body regions #609 stages.

    dod-table (prose-named), the omission-floor pair, and the PR-body vet marker. Vet-receipt's
    comment-only markers are intentionally excluded — grounding_stage never parses them.
    """
    m = re.search(
        r"\*\*Definition-of-done disposition table\*\* \(`(superheroes:dod-table)` marker\)",
        home,
    )
    assert m, "§10.7 dod-table marker prose not found (moved or reworded?)"
    expected = {"dod-table": "<!-- %s -->" % m.group(1)}
    _, floor_markers = _omission_floor_expectations_from_home(home)
    for marker in floor_markers:
        name = re.search(r"superheroes:([a-z-]+)", marker).group(1)
        expected[name] = marker
    body_marker = _body_marker_from_conventions(home)
    body_name = re.search(r"superheroes:([a-z-]+)", body_marker).group(1)
    expected[body_name] = body_marker
    return expected


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


def _assert_omission_floor_matches_home(copy_text, label, home):
    row_terms, markers = _omission_floor_expectations_from_home(home)
    assert label in _OMISSION_FLOOR_ENUMERATION_PINS, (
        "%s: copy-holder passed with no enumeration pin registered — "
        "add an entry to _OMISSION_FLOOR_ENUMERATION_PINS alongside the caller's copy-holder list"
        % label
    )
    pin_norm = _anchor_whitespace_normalize(_OMISSION_FLOOR_ENUMERATION_PINS[label])
    copy_norm = _anchor_whitespace_normalize(copy_text)
    assert pin_norm in copy_norm, (
        "%s: three-row omission-floor enumeration drifted" % label
    )
    lower = copy_text.lower()
    missing = []
    for i, terms in enumerate(row_terms, 1):
        for term in terms:
            if term.lower() not in lower:
                missing.append("row%d term %r" % (i, term))
    for marker in markers:
        if marker not in copy_text:
            missing.append("marker %r" % marker)
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


def test_grounding_stage_region_markers_match_conventions_10_7():
    """§10.7 + §11: grounding_stage.REGION_MARKERS tracks the PR-body region family."""
    # bite-axis: region-marker SSOT — plugin REGION_MARKERS must match CONVENTIONS §10.7.
    import grounding_stage

    home = _conventions_section_10_7()
    expected = _grounding_stage_region_markers_from_home(home)
    assert dict(grounding_stage.REGION_MARKERS) == expected, (
        "grounding_stage.REGION_MARKERS drift from CONVENTIONS §10.7 — "
        "expected %r, got %r" % (expected, dict(grounding_stage.REGION_MARKERS))
    )


def test_grounding_stage_session_modes_match_review_base_guard():
    """§11: grounding_stage derives session mode through session_mode.resolve."""
    import inspect

    import grounding_stage
    import review_base_guard

    assert review_base_guard.SESSION_MODES == frozenset({"pr", "branch"})
    read_meta_source = inspect.getsource(grounding_stage._read_meta)
    assert "session_mode.resolve" in read_meta_source, (
        "grounding_stage._read_meta must derive through session_mode.resolve"
    )
    gs_source = _read("lib/grounding_stage.py")
    assert not re.search(
        r'\(\s*["\']pr["\']\s*,\s*["\']branch["\']\s*\)', gs_source
    ), "grounding_stage.py must not re-inline a local mode tuple"


# --- Cluster: raw session-mode reads in round_driver.py / review_base_guard.py (#1107 WO-rc1) --

_RAW_MODE_READ_PATTERN = re.compile(r'get\("mode"\)|\["mode"\]|"mode":')

# The pinned census (I2/I3, #1107 WO-rc1): every remaining raw-mode-read-shaped site in these two
# modules, after `round_driver.build_receipt`'s "mode" was routed through `session_mode.resolve`
# (I2) and `review_base_guard.check_base`'s returned "mode" was single-sourced from
# `mode_resolved["mode"]` (I3). Every entry below reads an ALREADY-RESOLVED value (a
# `mode_resolved`/`_mode_resolved` dict produced by `session_mode.resolve` a few lines earlier) or
# is the raw `meta.get("mode")` local kept only for a refusal's diagnostic `detail` text — never a
# second decision path. A genuinely NEW raw read (e.g. a fresh `cfg.get("mode")` or
# `meta.get("mode")` feeding a decision) changes this set and must fail here first.
_EXPECTED_RAW_MODE_READS = {
    "lib/round_driver.py": {
        'base["mode"] = _mode_resolved["mode"]',
        'if mode_resolved["mode"] == session_mode.MODE_BRANCH:',
        '"MODE": mode_resolved["mode"],',
    },
    "lib/review_base_guard.py": {
        'mode = meta.get("mode")',
        'if mode_resolved["mode"] == session_mode.MODE_PR:',
        '"mode": mode_resolved["mode"],',
    },
}


def test_round_driver_and_review_base_guard_raw_mode_read_census():
    """#1107 WO-rc1 census: pins the enumerated set of session-mode-shaped reads in the two
    modules this order's invariants (I2, I3) touch, so a NEW raw-mode-read site cannot appear
    silently — it must show up as a set diff here and get classified (decision / pass-through /
    unrelated) the way this order's own census was."""
    for rel, expected in _EXPECTED_RAW_MODE_READS.items():
        text = _read(rel)
        found = {
            line.strip() for line in text.splitlines() if _RAW_MODE_READ_PATTERN.search(line)
        }
        assert found == expected, (
            "%s: raw-mode-read census drift — expected %r, found %r (a new or removed site "
            "changes this order's I1/I2/I3 analysis and must be reclassified)"
            % (rel, sorted(expected), sorted(found))
        )


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


# --- Cluster: register-check vocabulary (register_check → copy-holders) ---
#
# Copy-holders enumerated (§11.2 caveat — every known copy must be listed here):
# - skills/showrunner/reference/register-check.md ## Vocabulary (drift-tested)
# - skills/showrunner/reference/register-check.md ## The result contract Results table
# - CONVENTIONS.md §11.2 worked example 4 inline vocabulary prose
#
# Drift-tested labels guarded in the vocabulary section: Schema:, Results:, Finding kinds:,
# Undecided reasons:, Exit codes:, Result fields:, Finding fields:.


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
    """Inline-code bullet tokens under a **Label:** block — order preserved."""
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
    return tokens


def _register_check_schema_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return set(_register_check_tokens_under_label(section, "Schema:"))


def _register_check_results_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return set(_register_check_tokens_under_label(section, "Results:"))


def _register_check_finding_kinds_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return set(_register_check_tokens_under_label(section, "Finding kinds:"))


def _register_check_undecided_reasons_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return set(_register_check_tokens_under_label(section, "Undecided reasons:"))


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


def _register_check_result_fields_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return _register_check_tokens_under_label(section, "Result fields:")


def _register_check_finding_fields_from_doc(doc):
    section = _register_check_vocabulary_section(doc)
    return _register_check_tokens_under_label(section, "Finding fields:")


def _register_check_results_table_from_doc(doc):
    """Result tokens and exit-code mapping from ## The result contract Results table."""
    m = re.search(
        r"^## The result contract\s*\n(.*?)(?:\n## |\Z)",
        doc,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "register-check.md: ## The result contract section not found "
        "(moved or reworded?)"
    )
    section = m.group(1)
    table_m = re.search(
        r"\*\*Results:\*\*\s*\n\n\| Result \| Exit code \| Meaning \|\n"
        r"\| --- \| --- \| --- \|\n(.*?)(?:\n\n|\Z)",
        section,
        re.DOTALL,
    )
    assert table_m, (
        "register-check.md: **Results:** table not found in ## The result contract "
        "(moved or reformatted?)"
    )
    rows = re.findall(
        r"^\| `(\w+)` \| (\d+) \|",
        table_m.group(1),
        re.MULTILINE,
    )
    assert len(rows) == 3, (
        "register-check.md: **Results:** table row count drift — expected 3 rows, "
        "found %d (table reformatted?)"
        % len(rows)
    )
    return {int(exit_code): result for result, exit_code in rows}


def _register_check_worked_example_from_conventions():
    """Worked example 4 prose block from CONVENTIONS §11.2."""
    text = _read("../../CONVENTIONS.md")
    m = re.search(
        r"\*Worked example 4 — the register-check vocabulary\.\* (.*?)\n\n",
        text,
        re.DOTALL,
    )
    assert m, (
        "CONVENTIONS.md §11: register-check worked example 4 not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _register_check_inline_tokens_from_conventions(prose, label_pattern):
    """Inline backtick tokens from a worked-example 4 enumeration phrase."""
    m = re.search(label_pattern, prose)
    assert m, (
        "CONVENTIONS.md §11: register-check %s enumeration not found "
        "(moved or reworded?)"
        % label_pattern
    )
    tokens = re.findall(r"`([^`]+)`", m.group(1))
    assert tokens, (
        "CONVENTIONS.md §11: register-check inline list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return tokens


def _register_check_undecided_reasons_from_conventions():
    """Undecided-reason tokens and count word from CONVENTIONS §11.2 worked example 4."""
    import register_check

    prose = _register_check_worked_example_from_conventions()
    m = re.search(
        r"the (\w+) undecided-reason tokens \(([^)]+)\)",
        prose,
    )
    assert m, (
        "CONVENTIONS.md §11: register-check undecided-reason list not found "
        "(moved or reworded?)"
    )
    count_word = m.group(1).lower()
    assert count_word in _NUMBER_WORDS, (
        "CONVENTIONS.md §11 uses unknown undecided-reason count word %r" % count_word
    )
    # axis: the prose count word (seven, eight, …) must match len(UNDECIDED_REASONS).
    assert _NUMBER_WORDS[count_word] == len(register_check.UNDECIDED_REASONS), (
        "CONVENTIONS.md §11 undecided-reason count word %r (%d) drift from "
        "len(register_check.UNDECIDED_REASONS) (%d)"
        % (
            count_word,
            _NUMBER_WORDS[count_word],
            len(register_check.UNDECIDED_REASONS),
        )
    )
    tokens = re.findall(r"`([^`]+)`", m.group(2))
    assert tokens, (
        "CONVENTIONS.md §11: undecided-reason token list parsed to zero tokens "
        "(regex drift or empty list?)"
    )
    return set(tokens)


def _register_check_exit_codes_from_home():
    import register_check

    return {
        register_check.EXIT_PASS: register_check.RESULT_PASS,
        register_check.EXIT_FAIL: register_check.RESULT_FAIL,
        register_check.EXIT_UNDECIDED: register_check.RESULT_UNDECIDED,
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


def test_register_check_undecided_reasons_in_register_check_doc():
    """§11: register-check.md restates register_check.UNDECIDED_REASONS."""
    import register_check

    home = set(register_check.UNDECIDED_REASONS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_undecided_reasons_from_doc(doc)
    missing_from_doc = sorted(home - doc_tokens)
    extra_in_doc = sorted(doc_tokens - home)
    assert not missing_from_doc and not extra_in_doc, (
        "register-check.md Undecided reasons vocabulary drift from "
        "register_check.UNDECIDED_REASONS — "
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


def test_register_check_result_fields_in_register_check_doc():
    """§11: register-check.md restates register_check.RESULT_FIELDS in order."""
    import register_check

    home = list(register_check.RESULT_FIELDS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_result_fields_from_doc(doc)
    assert doc_tokens == home, (
        "register-check.md Result fields drift from register_check.RESULT_FIELDS — "
        "doc: %r; home: %r"
        % (doc_tokens, home)
    )


def test_register_check_finding_fields_in_register_check_doc():
    """§11: register-check.md restates register_check.FINDING_FIELDS in order."""
    import register_check

    home = list(register_check.FINDING_FIELDS)
    doc = _read(_REGISTER_CHECK_DOC)
    doc_tokens = _register_check_finding_fields_from_doc(doc)
    assert doc_tokens == home, (
        "register-check.md Finding fields drift from register_check.FINDING_FIELDS — "
        "doc: %r; home: %r"
        % (doc_tokens, home)
    )


def test_register_check_results_table_in_register_check_doc():
    """§11: register-check.md Results table restates register_check result/exit mapping."""
    home = _register_check_exit_codes_from_home()
    doc = _read(_REGISTER_CHECK_DOC)
    doc_mapping = _register_check_results_table_from_doc(doc)
    missing_codes = sorted(set(home.keys()) - set(doc_mapping.keys()))
    extra_codes = sorted(set(doc_mapping.keys()) - set(home.keys()))
    wrong_results = sorted(
        code
        for code in home
        if code in doc_mapping and doc_mapping[code] != home[code]
    )
    assert (
        not missing_codes and not extra_codes and not wrong_results
    ), (
        "register-check.md Results table drift from register_check exit mapping — "
        "missing exit codes: %r; extra exit codes: %r; wrong result tokens: %r"
        % (missing_codes, extra_codes, wrong_results)
    )


def test_register_check_vocabulary_in_conventions():
    """§11: CONVENTIONS §11.2 worked example 4 restates register_check vocabulary."""
    import register_check

    prose = _register_check_worked_example_from_conventions()
    home_results = set(register_check.RESULTS)
    home_kinds = set(register_check.FINDING_KINDS)
    home_undecided = set(register_check.UNDECIDED_REASONS)
    home_exit = _register_check_exit_codes_from_home()
    home_schema = {register_check.SCHEMA}

    doc_results = set(
        _register_check_inline_tokens_from_conventions(
            prose,
            r"The three result tokens \(([^)]+)\)",
        )
    )
    doc_kinds = set(
        _register_check_inline_tokens_from_conventions(
            prose,
            r"the three finding-kind tokens \(([^)]+)\)",
        )
    )
    doc_undecided = _register_check_undecided_reasons_from_conventions()
    doc_exit_codes = {
        int(token)
        for token in _register_check_inline_tokens_from_conventions(
            prose,
            r"the three exit codes\s*\(([^)]+)\)",
        )
    }
    doc_schema = set(
        _register_check_inline_tokens_from_conventions(
            prose,
            r"the schema token \(([^)]+)\)",
        )
    )

    missing_results = sorted(home_results - doc_results)
    extra_results = sorted(doc_results - home_results)
    assert not missing_results and not extra_results, (
        "CONVENTIONS.md §11 register-check result vocabulary drift — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_results, extra_results)
    )

    missing_kinds = sorted(home_kinds - doc_kinds)
    extra_kinds = sorted(doc_kinds - home_kinds)
    assert not missing_kinds and not extra_kinds, (
        "CONVENTIONS.md §11 register-check finding-kind vocabulary drift — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_kinds, extra_kinds)
    )

    missing_undecided = sorted(home_undecided - doc_undecided)
    extra_undecided = sorted(doc_undecided - home_undecided)
    assert not missing_undecided and not extra_undecided, (
        "CONVENTIONS.md §11 register-check undecided-reason vocabulary drift — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_undecided, extra_undecided)
    )

    missing_codes = sorted(set(home_exit.keys()) - doc_exit_codes)
    extra_codes = sorted(doc_exit_codes - set(home_exit.keys()))
    assert not missing_codes and not extra_codes, (
        "CONVENTIONS.md §11 register-check exit-code vocabulary drift — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_codes, extra_codes)
    )

    missing_schema = sorted(home_schema - doc_schema)
    extra_schema = sorted(doc_schema - home_schema)
    assert not missing_schema and not extra_schema, (
        "CONVENTIONS.md §11 register-check schema vocabulary drift — "
        "missing from doc: %r; present in doc but not in home: %r"
        % (missing_schema, extra_schema)
    )


def test_register_check_vocabulary_completeness():
    """Every register_check RESULT_*/KIND_*/UNDECIDED_* constant is in its frozenset."""
    import register_check

    derived_results = _register_check_string_constants_by_prefix("RESULT_")
    derived_kinds = _register_check_string_constants_by_prefix("KIND_")
    derived_undecided = _register_check_string_constants_by_prefix("UNDECIDED_")
    home_results = set(register_check.RESULTS)
    home_kinds = set(register_check.FINDING_KINDS)
    home_undecided = set(register_check.UNDECIDED_REASONS)
    missing_results = sorted(derived_results - home_results)
    extra_results = sorted(home_results - derived_results)
    missing_kinds = sorted(derived_kinds - home_kinds)
    extra_kinds = sorted(home_kinds - derived_kinds)
    missing_undecided = sorted(derived_undecided - home_undecided)
    extra_undecided = sorted(home_undecided - derived_undecided)
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
    assert not missing_undecided and not extra_undecided, (
        "register_check UNDECIDED_* constants drift from "
        "register_check.UNDECIDED_REASONS — "
        "missing from frozenset: %r; in frozenset but not derived: %r"
        % (missing_undecided, extra_undecided)
    )


# --- Cluster: R5 weight vocabulary + R7 park surface (pinned register literals) ---

# The epic register is the home of record for these sentences. lib/tests/ ships inside the
# plugin to projects that do not carry the register, so the literals are pinned here; the
# pin is validated against the home whenever the home is reachable, so a register edit in
# this repo turns the guard red instead of leaving two copies agreeing about the wrong text.
_EPIC_REGISTER_REL = os.path.normpath(
    os.path.join("..", "..", "docs", "superheroes",
                 "front-half-sdlc-core-6181ee", "register.md")
)

R5_WEIGHT_VOCABULARY = (
    "A weight call names `light` or `full`, states its measurables (gradable-line count "
    "for a spec draft; child count and register-entry count for a package read), names a "
    "round ceiling when it governs a read loop, and may be overridden in either direction "
    "by one stated sentence; the numeric bars are guidelines, never gates."
)

R7_PARK_SURFACE = (
    "A park lands the full park note — what was elicited or found so far, explicitly "
    "marked unapproved — on the owner's reading surface at park time: in the advisor's "
    "delivery message when the owner is present, else as the opening item of the "
    "advisor's next delivery message; a durable copy lands as a comment on the parked "
    "item's issue or PR, and the durable copy is for the record — it is never required "
    "owner reading."
)

_R5_PLUGIN_COPY_HOLDERS = (
    "skills/architect-discovery/SKILL.md",
    "skills/showrunner/SKILL.md",
)

_R7_PLUGIN_COPY_HOLDERS = (
    "skills/architect-discovery/SKILL.md",
    "skills/showrunner/SKILL.md",
    "skills/showrunner/reference/closure.md",
)

# §11.2: every known in-repo copy-holder outside the plugin for R5. A child doc that stops
# quoting an entry is a real failure, not a stale test — the register's Consumers line
# decides who must quote it.
_R5_IN_REPO_COPY_HOLDERS = (
    _EPIC_REGISTER_REL,
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c4-discovery.md")
    ),
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c6-epic-machinery.md")
    ),
)

# §11.2: every known in-repo copy-holder outside the plugin for R7. A child doc that stops
# quoting an entry is a real failure, not a stale test — the register's Consumers line
# decides who must quote it.
_R7_IN_REPO_COPY_HOLDERS = (
    _EPIC_REGISTER_REL,
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c4-discovery.md")
    ),
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c6-epic-machinery.md")
    ),
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c7-closure.md")
    ),
)


def _assert_literal_exactly_once(literal, rel, text=None):
    if text is None:
        text = _read(rel)
    count = text.count(literal)
    if count == 0:
        raise AssertionError(
            "%s: expected exactly one occurrence of pinned literal, found 0"
            % rel
        )
    if count > 1:
        raise AssertionError(
            "%s: expected exactly one occurrence of pinned literal, found %d"
            % (rel, count)
        )


def _assert_literal_exactly_once_if_reachable(literal, rel):
    path = os.path.normpath(os.path.join(PLUGIN, rel))
    if not os.path.isfile(path):
        pytest.skip(path)
    _assert_literal_exactly_once(literal, rel)


def _assert_literal_exactly_once_across_holders(literal, rels):
    """Check every holder; skip only if *no* holder was reachable, naming the unreachable ones."""
    unreachable = []
    for rel in rels:
        path = os.path.normpath(os.path.join(PLUGIN, rel))
        if not os.path.isfile(path):
            unreachable.append(path)
            continue
        _assert_literal_exactly_once(literal, rel)
    if len(unreachable) == len(rels):
        pytest.skip("no copy-holder reachable: %s" % ", ".join(unreachable))


def test_negative_assert_literal_exactly_once_absent():
    with pytest.raises(
        AssertionError,
        match=r"synthetic\.md: expected exactly one occurrence of pinned literal, found 0",
    ):
        _assert_literal_exactly_once(
            "probe literal",
            "synthetic.md",
            text="no probe here",
        )


def test_negative_assert_literal_exactly_once_duplicated():
    literal = "probe literal"
    duplicated = literal + " " + literal
    with pytest.raises(
        AssertionError,
        match=r"synthetic\.md: expected exactly one occurrence of pinned literal, found 2",
    ):
        _assert_literal_exactly_once(literal, "synthetic.md", text=duplicated)


def test_r5_pinned_literal_exactly_once_in_epic_register_when_reachable():
    """§11.2: pinned R5 literal is byte-exact in the epic register when the home is reachable."""
    _assert_literal_exactly_once_if_reachable(
        R5_WEIGHT_VOCABULARY, _EPIC_REGISTER_REL
    )


def test_r7_pinned_literal_exactly_once_in_epic_register_when_reachable():
    """§11.2: pinned R7 literal is byte-exact in the epic register when the home is reachable."""
    _assert_literal_exactly_once_if_reachable(R7_PARK_SURFACE, _EPIC_REGISTER_REL)


def test_r5_weight_vocabulary_exactly_once_in_plugin_copy_holders():
    """§11.2: R5 weight-call vocabulary is byte-identical in every enumerated plugin copy-holder."""
    for rel in _R5_PLUGIN_COPY_HOLDERS:
        _assert_literal_exactly_once(R5_WEIGHT_VOCABULARY, rel)


def test_r7_park_surface_exactly_once_in_plugin_copy_holders():
    """§11.2: R7 park-surface vocabulary is byte-identical in every enumerated plugin copy-holder."""
    for rel in _R7_PLUGIN_COPY_HOLDERS:
        _assert_literal_exactly_once(R7_PARK_SURFACE, rel)


def test_r5_weight_vocabulary_exactly_once_in_in_repo_copy_holders():
    """§11.2: R5 weight-call vocabulary is byte-identical in every enumerated in-repo copy-holder."""
    _assert_literal_exactly_once_across_holders(
        R5_WEIGHT_VOCABULARY, _R5_IN_REPO_COPY_HOLDERS
    )


def test_r7_park_surface_exactly_once_in_in_repo_copy_holders():
    """§11.2: R7 park-surface vocabulary is byte-identical in every enumerated in-repo copy-holder."""
    _assert_literal_exactly_once_across_holders(
        R7_PARK_SURFACE, _R7_IN_REPO_COPY_HOLDERS
    )


def _expect_assertion_error(fn, *, match):
    """Require fn() to raise AssertionError matching `match`.

    `pytest.raises(AssertionError)` is not enough for a bite-proof: a detector that
    regresses into `pytest.skip` raises `Skipped`, which derives from BaseException,
    so pytest.raises declines it and the whole test is reported SKIPPED — green. This
    helper catches BaseException and turns anything that is not a matching
    AssertionError into a failure, so a detector that stopped biting is always red.
    """
    try:
        fn()
    except AssertionError as exc:
        if not re.search(match, str(exc)):
            raise AssertionError(
                "detector raised AssertionError but message %r does not match %r"
                % (str(exc), match)
            ) from None
        return exc
    except BaseException as exc:  # noqa: BLE001 — Skipped is a BaseException, and that is the point
        raise AssertionError(
            "detector did not bite: expected AssertionError, got %s: %s"
            % (type(exc).__name__, exc)
        ) from None
    raise AssertionError("detector did not bite: no exception raised")


def test_negative_assert_literal_across_holders_checks_past_an_unreachable_one():
    _expect_assertion_error(
        lambda: _assert_literal_exactly_once_across_holders(
            "a literal no holder contains",
            ("does/not/exist.md", "skills/architect-discovery/SKILL.md"),
        ),
        match=r"skills/architect-discovery/SKILL\.md: expected exactly one occurrence",
    )


# --- Cluster: anchor invariant (issue-contract.md → the two charters) --------


_ANCHOR_BULLET_PREFIXES = (
    "- **Spec-section anchor.**",
    "- **Receipt anchor.**",
    "- **Ruling anchor.**",
)

_ANCHOR_CURSOR_CLAUSES = (
    "numbered greater than the anchor's",
    "the cursor test compares entry numbers, never dates",
    "Wording-class entries never stale an anchor",
)

_ANCHOR_INVERTED_FORMS = (
    "numbered less than",
    "earlier than the anchor's",
    "compare the amendment dates",
    "by date rather than by number",
    "wording-class entries stale an anchor",
    "use date comparison instead of",
    "compare dates instead of entry numbers",
)

_ANCHOR_EXPECTED_BULLET_LABELS = frozenset(
    {
        "Spec-section anchor.",
        "Receipt anchor.",
        "Ruling anchor.",
    }
)

_ANCHOR_BULLET_LABEL_RE = re.compile(r"^- \*\*([^*]+)\*\*")

_ANCHOR_SURFACES = (
    "skills/workhorse/SKILL.md",
    "skills/showrunner/SKILL.md",
    "skills/showrunner/reference/issue-contract.md",
    "skills/showrunner/reference/vet-receipt.md",
)


def _anchor_whitespace_normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def _anchor_extract_bullet(text, prefix, surface):
    """One top-level `- **...` bullet from prefix to blank line or sibling bullet."""
    lines = text.splitlines()
    matches = []
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            collected = [line]
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "":
                    break
                if re.match(r"^- \*\*", lines[j]):
                    break
                collected.append(lines[j])
            matches.append("\n".join(collected))
    assert len(matches) == 1, (
        "%s: prefix %r — expected exactly one bullet, found %d"
        % (surface, prefix, len(matches))
    )
    return _anchor_whitespace_normalize(matches[0])


def _anchor_resolution_section(rel):
    if rel == "skills/workhorse/SKILL.md":
        return _workhorse_intake_anchor_section(), rel
    if rel == "skills/showrunner/reference/issue-contract.md":
        return _issue_contract_section("## Anchor resolution"), rel
    raise ValueError("unexpected anchor resolution surface %r" % rel)


def _anchor_resolution_bullet_block(section_text, surface):
    """Fail-closed resolution-bullet block: first Spec-section bullet through pre-malformed."""
    m_start = re.search(
        r"^- \*\*Spec-section anchor\.\*\*",
        section_text,
        re.MULTILINE,
    )
    assert m_start, (
        "%s: resolution-bullet block start not found (moved or reworded?)" % surface
    )
    m_end = re.search(
        r"^A malformed Anchor",
        section_text[m_start.start():],
        re.MULTILINE,
    )
    assert m_end, (
        "%s: resolution-bullet block end marker not found (moved or reworded?)" % surface
    )
    return section_text[m_start.start(): m_start.start() + m_end.start()].strip()


def _anchor_enumerate_resolution_bullet_labels(block):
    labels = []
    for line in block.splitlines():
        m = _ANCHOR_BULLET_LABEL_RE.match(line)
        if m:
            labels.append(m.group(1))
    return labels


def _anchor_assert_resolution_bullets_complete(rel):
    section, surface = _anchor_resolution_section(rel)
    block = _anchor_resolution_bullet_block(section, surface)
    labels = _anchor_enumerate_resolution_bullet_labels(block)
    label_set = set(labels)
    unexpected = sorted(label_set - _ANCHOR_EXPECTED_BULLET_LABELS)
    missing = sorted(_ANCHOR_EXPECTED_BULLET_LABELS - label_set)
    assert len(labels) == 3, (
        "%s: expected exactly three anchor-resolution bullets, found %d; "
        "labels: %r; unexpected: %r"
        % (surface, len(labels), labels, unexpected)
    )
    assert not unexpected and not missing, (
        "%s: anchor-resolution bullet label set mismatch — unexpected: %r; "
        "missing: %r; found: %r"
        % (surface, unexpected, missing, labels)
    )
    for prefix in _ANCHOR_BULLET_PREFIXES:
        _anchor_extract_bullet(section, prefix, surface)


def _anchor_log_side_fails_closed_paragraph(rel):
    section, surface = _anchor_resolution_section(rel)
    m = re.search(
        r"\*\*The log side fails closed too\.\*\*.*?"
        r"(?=^\*\*(?:On any failure|Why the cursor))",
        section,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "%s: The log side fails closed too paragraph not found (moved or reworded?)"
        % surface
    )
    return m.group(0)


def _anchor_resolution_bullets(rel):
    section, surface = _anchor_resolution_section(rel)
    _anchor_assert_resolution_bullets_complete(rel)
    bullets = [
        _anchor_extract_bullet(section, prefix, surface)
        for prefix in _ANCHOR_BULLET_PREFIXES
    ]
    return bullets


def _workhorse_intake_anchor_section():
    text = _read("skills/workhorse/SKILL.md")
    m = re.search(
        r"(^\*\*Confirm the Anchor resolves before any spend\.\*\*.*?)"
        r"(?=^\*\*Launch-prompt discipline\.\*\*)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "workhorse/SKILL.md: anchor intake section not found (moved or reworded?)"
    )
    span = m.group(1)
    body = "\n".join(span.splitlines()[1:])
    assert body.strip(), "workhorse/SKILL.md: anchor intake section body is empty"
    return span


def _issue_contract_section(heading):
    text = _read("skills/showrunner/reference/issue-contract.md")
    m = re.search(
        r"^%s\s*\n(.*?)(?=^## |\Z)" % re.escape(heading),
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "issue-contract.md: section %r not found (moved or reworded?)" % heading
    )
    body = m.group(1)
    assert body.strip(), (
        "issue-contract.md: section %r body is empty (moved or reworded?)" % heading
    )
    return heading + "\n" + body


def _showrunner_record_anchor_at_filing_paragraph():
    """Duty-2 'Record the anchor at filing' paragraph — scoped to that paragraph only."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Record the anchor at filing\.\*\*.*?(?=\n   \*\*Notify in-flight)",
        text,
        re.DOTALL,
    )
    assert m, (
        "showrunner/SKILL.md: Record the anchor at filing paragraph not found "
        "(moved or reworded?)"
    )
    return m.group(0)


def _showrunner_superseded_ruling_notice_paragraph():
    """Duty-2 superseded-ruling notice paragraph — scoped to that paragraph only."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Notify in-flight builds when a ruling is superseded\.\*\*.*?"
        r"(?=\n   When an issue being filed)",
        text,
        re.DOTALL,
    )
    assert m, (
        "showrunner/SKILL.md: superseded-ruling notice paragraph not found "
        "(moved or reworded?)"
    )
    return m.group(0)


def _showrunner_repair_anchor_stop_paragraph():
    """Duty-3 repair-anchor-stop paragraph — scoped to that paragraph only."""
    text = _read("skills/showrunner/SKILL.md")
    m = re.search(
        r"\*\*Repair a builder's anchor stop\.\*\*.*?(?=\n   At an epic)",
        text,
        re.DOTALL,
    )
    assert m, (
        "showrunner/SKILL.md: Repair a builder's anchor stop paragraph not found "
        "(moved or reworded?)"
    )
    return m.group(0)


def _showrunner_anchor_coverage_bullet():
    text = _read("skills/showrunner/SKILL.md")
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("   - **The standing anchor-coverage row**"):
            start = i
            break
    assert start is not None, (
        "showrunner/SKILL.md: standing anchor-coverage row bullet not found "
        "(moved or reworded?)"
    )
    collected = [lines[start]]
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("   - "):
            break
        collected.append(lines[j])
    bullet = "\n".join(collected)
    assert bullet.strip(), (
        "showrunner/SKILL.md: standing anchor-coverage row bullet is empty"
    )
    return bullet


def test_anchor_resolution_bullets_match_between_home_and_workhorse():
    # axis: whitespace-normalized equality of the three resolution bullets across copies
    workhorse = _anchor_resolution_bullets("skills/workhorse/SKILL.md")
    home = _anchor_resolution_bullets(
        "skills/showrunner/reference/issue-contract.md"
    )
    for i, (w, h) in enumerate(zip(workhorse, home)):
        if w != h:
            pytest.fail(
                "anchor resolution bullet index %d differs — workhorse: %r; home: %r"
                % (i, w, h)
            )


def test_anchor_cursor_rule_clauses_present_in_both_copies():
    # axis: synchronized-deletion guard — clauses must appear in the Spec-section bullet
    workhorse_section, workhorse_surface = _anchor_resolution_section(
        "skills/workhorse/SKILL.md"
    )
    home_section, home_surface = _anchor_resolution_section(
        "skills/showrunner/reference/issue-contract.md"
    )
    workhorse_bullet = _anchor_extract_bullet(
        workhorse_section, "- **Spec-section anchor.**", workhorse_surface
    )
    home_bullet = _anchor_extract_bullet(
        home_section, "- **Spec-section anchor.**", home_surface
    )
    for clause in _ANCHOR_CURSOR_CLAUSES:
        clause_norm = _anchor_whitespace_normalize(clause)
        assert clause_norm in workhorse_bullet, (
            "workhorse Spec-section anchor bullet missing cursor clause %r "
            "(moved or reworded?)" % clause
        )
        assert clause_norm in home_bullet, (
            "issue-contract Spec-section anchor bullet missing cursor clause %r "
            "(moved or reworded?)" % clause
        )


def test_anchor_doctrine_forbids_inverted_cursor_forms():
    # axis: inverted cursor forms must be absent from all enumerated surfaces
    for rel in _ANCHOR_SURFACES:
        text_norm = _anchor_whitespace_normalize(_read(rel)).lower()
        for inverted in _ANCHOR_INVERTED_FORMS:
            assert inverted not in text_norm, (
                "%s contains inverted cursor form %r" % (rel, inverted)
            )


def test_anchor_stop_and_repair_is_two_sided():
    # axis: builder and advisor repair halves must both appear where required
    intake = _workhorse_intake_anchor_section()
    intake_norm = _anchor_whitespace_normalize(intake)
    assert _anchor_whitespace_normalize("stop before any spend") in intake_norm, (
        "workhorse intake missing stop-before-spend clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("You never repair the anchor yourself") in intake_norm, (
        "workhorse intake missing never-repair clause (moved or reworded?)"
    )

    repair_para = _showrunner_repair_anchor_stop_paragraph()
    repair_norm = _anchor_whitespace_normalize(repair_para)
    for phrase in (
        "re-anchor",
        "re-route",
        "park it to the owner",
        "A builder never repairs its own anchor",
    ):
        assert _anchor_whitespace_normalize(phrase) in repair_norm, (
            "showrunner repair-anchor-stop paragraph missing advisor repair phrase %r "
            "(moved or reworded?)" % phrase
        )

    home_resolution = _issue_contract_section("## Anchor resolution")
    home_norm = _anchor_whitespace_normalize(home_resolution)
    assert _anchor_whitespace_normalize("stops before any spend") in home_norm, (
        "issue-contract.md ## Anchor resolution missing stop-before-spend clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("builder never repairs its own anchor") in home_norm, (
        "issue-contract.md ## Anchor resolution missing never-repair clause "
        "(moved or reworded?)"
    )
    for phrase in ("re-anchor", "re-route", "park it to the owner"):
        assert _anchor_whitespace_normalize(phrase) in home_norm, (
            "issue-contract.md ## Anchor resolution missing %r "
            "(moved or reworded?)" % phrase
        )


def test_standing_anchor_coverage_row_is_standing_not_conditional():
    # axis: every-PR grading — conditional vet wording is the silent-omission failure
    bullet = _showrunner_anchor_coverage_bullet()
    bullet_norm = _anchor_whitespace_normalize(bullet)
    assert _anchor_whitespace_normalize("at **every** vet") in bullet_norm, (
        "showrunner duty-4 bullet missing at-every-vet clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("only anchor layer that inspects the diff") in bullet_norm, (
        "showrunner duty-4 bullet missing diff-inspection clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("reaches the owner in the owner half") in bullet_norm, (
        "showrunner duty-4 bullet missing owner-half delivery clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("not only in your receipt") in bullet_norm, (
        "showrunner duty-4 bullet missing not-only-receipt clause (moved or reworded?)"
    )

    home_section = _issue_contract_section("## The standing anchor-coverage vet row")
    home_norm = _anchor_whitespace_normalize(home_section)
    assert _anchor_whitespace_normalize("graded on every PR") in home_norm, (
        "issue-contract.md standing anchor-coverage section missing "
        "graded-on-every-PR clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("reaches the owner in the owner half") in home_norm, (
        "issue-contract.md standing anchor-coverage section missing "
        "owner-half delivery clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("not only in the advisor's own receipt") in home_norm, (
        "issue-contract.md standing anchor-coverage section missing "
        "not-only-receipt clause (moved or reworded?)"
    )


def test_anchor_recorded_at_filing_clause_in_showrunner_charter():
    # axis: anchor recorded at filing, never retrofitted
    filing_para = _showrunner_record_anchor_at_filing_paragraph()
    filing_norm = _anchor_whitespace_normalize(filing_para)
    assert _anchor_whitespace_normalize(
        "recorded **at filing time**, never added afterwards"
    ) in filing_norm, (
        "showrunner Record-the-anchor-at-filing paragraph missing at-filing-time clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("cannot be marked build-ready") in filing_norm, (
        "showrunner Record-the-anchor-at-filing paragraph missing cannot-be-build-ready "
        "clause (moved or reworded?)"
    )


def test_anchor_coverage_owner_half_clause_in_vet_receipt():
    # axis: vet-receipt owner-half delivery for the standing anchor-coverage row
    text = _read("skills/showrunner/reference/vet-receipt.md")
    norm = _anchor_whitespace_normalize(text)
    assert _anchor_whitespace_normalize("standing anchor-coverage row") in norm, (
        "vet-receipt.md missing standing anchor-coverage row name (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "so it is stated in the owner half and not left in the receipt alone"
    ) in norm, (
        "vet-receipt.md missing owner-half delivery clause (moved or reworded?)"
    )


def test_superseded_ruling_notice_duty_in_showrunner_charter():
    # axis: superseded-ruling notice duty and reverse-index doctrine
    notice_para = _showrunner_superseded_ruling_notice_paragraph()
    notice_norm = _anchor_whitespace_normalize(notice_para)
    assert _anchor_whitespace_normalize("The Anchor citation is the reverse index") in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing reverse-index clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("no rulings ledger") in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing no-rulings-ledger clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize("registers for embedded copies") in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing embedded-copy register clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "Record the notice where the build will see it"
    ) in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing durable-notice clause "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "on that build's issue or PR"
    ) in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing issue-or-PR notice surface "
        "(moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "never only in a channel message"
    ) in notice_norm, (
        "showrunner superseded-ruling notice paragraph missing not-only-channel clause "
        "(moved or reworded?)"
    )


def test_anchor_log_side_fails_closed():
    # axis: log-side fail-closed paragraph is a two-copy duplicate with four named conditions
    workhorse_para = _anchor_log_side_fails_closed_paragraph("skills/workhorse/SKILL.md")
    home_para = _anchor_log_side_fails_closed_paragraph(
        "skills/showrunner/reference/issue-contract.md"
    )
    workhorse_norm = _anchor_whitespace_normalize(workhorse_para)
    home_norm = _anchor_whitespace_normalize(home_para)
    assert workhorse_norm == home_norm, (
        "log-side fails-closed paragraph drift — workhorse: %r; home: %r"
        % (workhorse_para, home_para)
    )
    for clause in (
        "no Amendments log at all",
        "the log cannot be read",
        "missing its class or its touched-section list",
        "greater than the number of entries the log holds",
    ):
        clause_norm = _anchor_whitespace_normalize(clause)
        assert clause_norm in workhorse_norm, (
            "log-side fails-closed paragraph missing condition %r (moved or reworded?)"
            % clause
        )


def test_anchor_stop_terminal_and_resume_gate():
    # axis: stop terminal differs from register-check park; resume and repair gates pinned
    intake = _workhorse_intake_anchor_section()
    intake_norm = _anchor_whitespace_normalize(intake)
    assert _anchor_whitespace_normalize(
        "not the same terminal"
    ) in intake_norm, (
        "workhorse intake missing not-the-same-terminal clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "register-check parks"
    ) in intake_norm, (
        "workhorse intake missing register-check-parks clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "Post the report on the issue"
    ) in intake_norm, (
        "workhorse intake missing post-report-on-issue clause (moved or reworded?)"
    )
    assert _anchor_whitespace_normalize(
        "resumes only on the advisor's word"
    ) in intake_norm, (
        "workhorse intake missing resumes-only clause (moved or reworded?)"
    )

    repair_para = _showrunner_repair_anchor_stop_paragraph()
    repair_norm = _anchor_whitespace_normalize(repair_para)
    assert _anchor_whitespace_normalize(
        "graded end to end on the issue"
    ) in repair_norm, (
        "showrunner repair-anchor-stop paragraph missing graded-end-to-end clause "
        "(moved or reworded?)"
    )

    home_resolution = _issue_contract_section("## Anchor resolution")
    home_norm = _anchor_whitespace_normalize(home_resolution)
    assert _anchor_whitespace_normalize(
        "resumes **only** on the advisor's word"
    ) in home_norm, (
        "issue-contract ## Anchor resolution missing resumes-only clause "
        "(moved or reworded?)"
    )


# --- Sub-cluster: pre-doctrine on-ramp structure -----------------------------
# (home: skills/showrunner/reference/issue-contract.md § Pre-doctrine issues;
# copy-holder: skills/workhorse/SKILL.md anchor-intake repair template)
# The slot sequence and the build-ready completion tokens are NOT the prose's to declare
# — both are read out of lib/issue_contract.py, the runtime home, and the prose surfaces
# are checked against it. There is no level above that module in this chain.

_PRE_DOCTRINE_HEADING = "## Pre-doctrine issues"

_PRE_DOCTRINE_ORDERED_HEADINGS = (
    "## Anchor resolution",
    "## Pre-doctrine issues",
    "## The standing anchor-coverage vet row",
)

_PRE_DOCTRINE_ORDERED_CONTENTS_ROWS = (
    "- [Anchor resolution](#anchor-resolution)",
    "- [Pre-doctrine issues](#pre-doctrine-issues)",
    "- [The standing anchor-coverage vet row](#the-standing-anchor-coverage-vet-row)",
)

_PRE_DOCTRINE_PATTERN_HEADINGS = (
    "### Pattern 1 — the per-issue retrofit",
    "### Pattern 2 — the board-pass grandfathering",
)

_PRE_DOCTRINE_TEMPLATE_SLOT_HEADERS = (
    "**Anchor (ruling):**",
    "**What:**",
    "**DoD:**",
)

_PRE_DOCTRINE_ANNOTATION_FRAGMENTS = (
    "*Original filing (<filing-date>), preserved verbatim below; skeleton slots "
    "retrofitted",
    "during pre-doctrine repair (advisor edit, content unchanged).*",
)

_PRE_DOCTRINE_REGISTER_TOKEN_RE = re.compile(r"\bR\d+\b")

_WORKHORSE_REPAIR_TEMPLATE_SENTINEL = "**The stop-report carries its own repair.**"

_WORKHORSE_REPAIR_TEMPLATE_POINTER = (
    "`skills/showrunner/reference/issue-contract.md` § Pre-doctrine issues"
)

_WORKHORSE_REPAIR_FIELD_BULLET_RE = re.compile(r"^- \*\*([^*]+)\*\*", re.MULTILINE)

# The home template's fenced block. The slot ORDER this cluster asserts comes from the
# RUNTIME home — `issue_contract.SLOTS` — and the fence is checked against it; the fence
# is itself a copy of that sequence, so deriving the order from the fence alone would
# only move the tautological pin CONVENTIONS §11.3 prohibits, not end it. Nothing here
# re-types a slot name.
_PRE_DOCTRINE_TEMPLATE_FENCE_RE = re.compile(
    r"^```markdown\n(.*?)^```", re.MULTILINE | re.DOTALL
)

# The result keys the § Pre-doctrine issues guidance quotes out of the build-ready JSON.
# Only the KEY SELECTION is named here — each key is asserted present in a real
# `check_build_ready()` success payload, and its value spelling is read off that payload
# rather than re-typed (see `_pre_doctrine_completion_tokens_from_home`).
_PRE_DOCTRINE_QUOTED_RESULT_KEYS = ("ok", "reason")

# The two copy-holder fields that follow the derived slots, in order. Short durable
# tokens, not full bullet prose — rewording the bullet around them stays free.
_WORKHORSE_REPAIR_TRAILING_FIELD_TOKENS = ("separator", "original body")

_BLANK_LINE_RE = re.compile(r"^[ \t]*$", re.MULTILINE)


def _pre_doctrine_section():
    """The § Pre-doctrine issues section body, bounded by the next `## ` heading."""
    return _issue_contract_section(_PRE_DOCTRINE_HEADING)


def _issue_contract_heading_index(text, heading):
    m = re.search(r"^%s$" % re.escape(heading), text, re.MULTILINE)
    assert m, (
        "issue-contract.md: heading %r not found (moved or reworded?)" % heading
    )
    return m.start()


def _issue_contract_contents_block():
    """The `# Contents` list, bounded by the next `# ` heading."""
    text = _read("skills/showrunner/reference/issue-contract.md")
    m = re.search(r"^# Contents\s*\n(.*?)(?=^# )", text, re.MULTILINE | re.DOTALL)
    assert m, "issue-contract.md: # Contents list not found (moved or reworded?)"
    block = m.group(1)
    assert block.strip(), "issue-contract.md: # Contents list is empty"
    return block


def _workhorse_repair_template_block():
    """The stop-report repair-template paragraph plus its field bullets.

    Bounded structurally at both ends: the sentinel opens it, and it closes at the
    end of the field-bullet list (the first blank line after the last `- **…**`
    bullet). No ordinary prose sentence is a delimiter, so rewording the paragraph
    that follows the list does not break this reader.
    """
    span = _workhorse_intake_anchor_section()
    m_start = re.search(
        r"^\*\*The stop-report carries its own repair\.\*\*",
        span,
        re.MULTILINE,
    )
    assert m_start, (
        "workhorse/SKILL.md: repair-template block start not found in the "
        "anchor-intake span (moved or reworded?)"
    )
    tail = span[m_start.start():]
    m_first = _WORKHORSE_REPAIR_FIELD_BULLET_RE.search(tail)
    assert m_first, (
        "workhorse/SKILL.md: no repair-template field bullets found after the "
        "sentinel (bullet list removed or reshaped?)"
    )
    # The list runs unbroken to the first blank line after its first bullet; that
    # blank line is the structural end of the block.
    m_end = _BLANK_LINE_RE.search(tail, m_first.end())
    end = m_end.start() if m_end else len(tail)
    block = tail[:end].strip()
    assert block, "workhorse/SKILL.md: repair-template block is empty"
    return block


def _pre_doctrine_template_fence():
    """The single fenced retrofit template in § Pre-doctrine issues — the prose copy of
    the runtime slot sequence the workhorse field bullets copy in turn. Fails closed on
    a missing or duplicated fence."""
    section = _pre_doctrine_section()
    fences = _PRE_DOCTRINE_TEMPLATE_FENCE_RE.findall(section)
    assert len(fences) == 1, (
        "issue-contract.md § Pre-doctrine issues: expected exactly one ```markdown "
        "fenced retrofit template, found %d — the copy-holder drift pin reads the "
        "slot order out of that fence, so it cannot be missing or duplicated"
        % len(fences)
    )
    return fences[0]


def _pre_doctrine_template_slot_name_re(slots):
    """Slot-header reader built from the runtime slot names — the alternation is never
    re-typed here, so a rename in issue_contract moves this reader with it."""
    return re.compile(
        r"^\*\*(%s)\b[^*]*:\*\*" % "|".join(re.escape(slot) for slot in slots),
        re.MULTILINE,
    )


def _pre_doctrine_template_slot_order():
    """The ordered slot sequence the copy-holder pin checks against, taken from the
    RUNTIME home (`issue_contract.SLOTS`) and cross-checked against the home template's
    fence. Reading the order out of the fence alone would pass a synchronized reorder of
    the fence AND the copy-holder while both diverged from the runtime contract — the
    fence is a copy, and issue_contract.py is the end of the chain. Fails closed when a
    slot header is absent, declared more than once, or out of runtime order."""
    import issue_contract

    canonical = list(issue_contract.SLOTS)
    fence = _pre_doctrine_template_fence()
    slots = _pre_doctrine_template_slot_name_re(canonical).findall(fence)
    assert len(slots) == len(canonical), (
        "issue-contract.md § Pre-doctrine issues: expected %d slot headers in the "
        "fenced retrofit template — one per issue_contract.SLOTS entry %r — found %d: "
        "%r (slot removed or reshaped?)"
        % (len(canonical), canonical, len(slots), slots)
    )
    assert len(set(slots)) == len(slots), (
        "issue-contract.md § Pre-doctrine issues: a slot header is declared more "
        "than once in the fenced retrofit template: %r" % (slots,)
    )
    assert slots == canonical, (
        "issue-contract.md § Pre-doctrine issues: the fenced retrofit template's slot "
        "order %r no longer matches the runtime contract issue_contract.SLOTS %r — the "
        "fence is a copy of that runtime sequence, so a reorder in the fence (or a "
        "reorder in issue_contract.py the fence did not follow) has to move both"
        % (slots, canonical)
    )
    return canonical


def _pre_doctrine_conforming_body_from_home():
    """A minimal issue body the runtime build-ready check accepts, assembled out of the
    runtime slot names and anchor kinds rather than re-typed markdown."""
    import issue_contract

    # Any registered kind conforms; taking the registry's first sorted entry keeps this
    # derived from ANCHOR_KINDS instead of naming one kind by hand.
    kind = sorted(issue_contract.ANCHOR_KINDS)[0]
    return "\n".join(
        [
            "**%s (%s):** 2026-01-01 - owner decision - reachable record. "
            "Not superseded." % (issue_contract.SLOT_ANCHOR, kind),
            "",
            "**%s:** plain-language scope carried up from the original filing."
            % issue_contract.SLOT_WHAT,
            "",
            "**%s:**" % issue_contract.SLOT_DOD,
            "- an observable outcome a vet can grade from the handback alone.",
            "",
        ]
    )


def _pre_doctrine_completion_tokens_from_home(tmp_path):
    """The `key: value` completion tokens the guidance quotes, read off a REAL
    successful `issue_contract.check_build_ready()` result rather than hand-typed: each
    quoted key must be present in that payload, and the value is the payload's own JSON
    spelling. A runtime schema change — the key renamed or dropped, or a successful
    result no longer carrying a null reason — moves these tokens, so the section pin
    bites instead of leaving the shipped guidance stale."""
    import issue_contract

    body_path = tmp_path / "pre-doctrine-conforming-body.md"
    body_path.write_text(_pre_doctrine_conforming_body_from_home(), encoding="utf-8")
    result = issue_contract.check_build_ready(body_path.read_text(encoding="utf-8"))
    assert result.get("ok") is True, (
        "issue_contract.check_build_ready() refused the body this pin builds out of "
        "SLOTS + ANCHOR_KINDS (result: %r) — the § Pre-doctrine issues completion-token "
        "pin needs a real successful result to read its tokens off (runtime check "
        "tightened, or the derived body shape is no longer conforming?)" % (result,)
    )
    tokens = []
    for key in _PRE_DOCTRINE_QUOTED_RESULT_KEYS:
        assert key in result, (
            "issue_contract.check_build_ready() success result no longer carries the "
            "%r key (renamed or dropped?) — issue-contract.md § Pre-doctrine issues "
            "quotes it out of the JSON, so the shipped guidance has to move with it; "
            "result keys: %r" % (key, sorted(result))
        )
        tokens.append("%s: %s" % (key, json.dumps(result[key])))
    return tokens


def test_pre_doctrine_section_exists_exactly_once():
    # axis: the § Pre-doctrine issues heading is present exactly once
    text = _read("skills/showrunner/reference/issue-contract.md")
    headings = re.findall(
        r"^%s$" % re.escape(_PRE_DOCTRINE_HEADING), text, re.MULTILINE
    )
    assert len(headings) == 1, (
        "issue-contract.md: expected exactly one %r heading line, found %d "
        "(section removed, renamed, or duplicated?)"
        % (_PRE_DOCTRINE_HEADING, len(headings))
    )


def test_pre_doctrine_section_sits_between_resolution_and_coverage():
    # axis: section position — § Pre-doctrine issues is what terminates
    # § Anchor resolution for the anchor cluster's section bounder
    text = _read("skills/showrunner/reference/issue-contract.md")
    indexes = [
        _issue_contract_heading_index(text, heading)
        for heading in _PRE_DOCTRINE_ORDERED_HEADINGS
    ]
    resolution, pre_doctrine, coverage = indexes
    assert resolution < pre_doctrine, (
        "issue-contract.md: %r no longer sits after %r (section moved?) — the anchor "
        "cluster bounds %r at the next `## ` heading, so this order is load-bearing"
        % (
            _PRE_DOCTRINE_ORDERED_HEADINGS[1],
            _PRE_DOCTRINE_ORDERED_HEADINGS[0],
            _PRE_DOCTRINE_ORDERED_HEADINGS[0],
        )
    )
    assert pre_doctrine < coverage, (
        "issue-contract.md: %r no longer sits before %r (section moved?)"
        % (_PRE_DOCTRINE_ORDERED_HEADINGS[1], _PRE_DOCTRINE_ORDERED_HEADINGS[2])
    )


def test_pre_doctrine_contents_row_matches_section_order():
    # axis: the Contents row exists once and in the same order as the sections
    text = _read("skills/showrunner/reference/issue-contract.md")
    row = _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS[1]
    occurrences = re.findall(r"^%s$" % re.escape(row), text, re.MULTILINE)
    assert len(occurrences) == 1, (
        "issue-contract.md: expected exactly one Contents row %r, found %d "
        "(row removed, reworded, or duplicated?)" % (row, len(occurrences))
    )
    block = _issue_contract_contents_block()
    indexes = []
    for contents_row in _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS:
        m = re.search(r"^%s$" % re.escape(contents_row), block, re.MULTILINE)
        assert m, (
            "issue-contract.md: Contents row %r not found in the # Contents list "
            "(moved or reworded?)" % contents_row
        )
        indexes.append(m.start())
    assert indexes[0] < indexes[1], (
        "issue-contract.md: Contents row %r no longer sits after %r (row moved?)"
        % (
            _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS[1],
            _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS[0],
        )
    )
    assert indexes[1] < indexes[2], (
        "issue-contract.md: Contents row %r no longer sits before %r (row moved?)"
        % (
            _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS[1],
            _PRE_DOCTRINE_ORDERED_CONTENTS_ROWS[2],
        )
    )


def test_pre_doctrine_both_pattern_headings_present():
    # axis: the two repair recipes are named headings, one each
    section = _pre_doctrine_section()
    for heading in _PRE_DOCTRINE_PATTERN_HEADINGS:
        occurrences = re.findall(
            r"^%s$" % re.escape(heading), section, re.MULTILINE
        )
        assert len(occurrences) == 1, (
            "issue-contract.md § Pre-doctrine issues: expected exactly one %r "
            "heading, found %d (recipe removed, renamed, or duplicated?)"
            % (heading, len(occurrences))
        )


def test_pre_doctrine_template_carries_all_three_slot_headers():
    # axis: the copyable template carries all three skeleton slot headers
    section = _pre_doctrine_section()
    for slot_header in _PRE_DOCTRINE_TEMPLATE_SLOT_HEADERS:
        assert slot_header in section, (
            "issue-contract.md § Pre-doctrine issues: copyable template missing slot "
            "header %r (removed or reworded?)" % slot_header
        )


def test_pre_doctrine_dated_annotation_shape_pinned():
    # axis: the dated separator annotation keeps its verbatim-preservation shape
    section_norm = _anchor_whitespace_normalize(_pre_doctrine_section())
    for fragment in _PRE_DOCTRINE_ANNOTATION_FRAGMENTS:
        fragment_norm = _anchor_whitespace_normalize(fragment)
        assert fragment_norm in section_norm, (
            "issue-contract.md § Pre-doctrine issues: dated annotation missing "
            "fragment %r (removed or reworded?)" % fragment
        )


def test_pre_doctrine_completion_tokens_present(tmp_path):
    # axis: token presence only — both completion tokens survive in the section, each
    # DERIVED from a real check_build_ready() success payload rather than re-typed here,
    # so a runtime result-schema change moves the expectation. A substring check cannot
    # prove the surrounding prose reads them out of the JSON rather than the exit
    # status; that reading is prose review's call.
    section = _pre_doctrine_section()
    for token in _pre_doctrine_completion_tokens_from_home(tmp_path):
        assert token in section, (
            "issue-contract.md § Pre-doctrine issues: completion token %r is not "
            "present in the section — the token is read off a real "
            "issue_contract.check_build_ready() success result, so either the guidance "
            "moved (removed or softened back to 'green'?) or the runtime result shape "
            "changed and the guidance is now stale" % token
        )


def test_pre_doctrine_section_carries_no_register_token():
    # axis: no repo-internal register id leaks into consumer-facing guidance
    section = _pre_doctrine_section()
    leaked = _PRE_DOCTRINE_REGISTER_TOKEN_RE.findall(section)
    assert not leaked, (
        "issue-contract.md § Pre-doctrine issues: register token(s) %r leaked into "
        "consumer-facing guidance — a consuming project's advisor has no register, "
        "so the recipe names the ruling test by heading instead" % sorted(set(leaked))
    )


def test_workhorse_intake_repair_template_required_with_pointer():
    # axis: the stop-report repair requirement and its section-specific pointer
    span = _workhorse_intake_anchor_section()
    assert _WORKHORSE_REPAIR_TEMPLATE_SENTINEL in span, (
        "workhorse/SKILL.md anchor-intake span: missing repair-template sentinel %r "
        "(removed or reworded?)" % _WORKHORSE_REPAIR_TEMPLATE_SENTINEL
    )
    span_norm = _anchor_whitespace_normalize(span)
    pointer_norm = _anchor_whitespace_normalize(_WORKHORSE_REPAIR_TEMPLATE_POINTER)
    assert pointer_norm in span_norm, (
        "workhorse/SKILL.md anchor-intake span: missing pointer %r to where the "
        "missing-slot repair recipes live (removed or reworded?)"
        % _WORKHORSE_REPAIR_TEMPLATE_POINTER
    )


def test_workhorse_intake_repair_template_field_bullets_follow_home_slot_order():
    # axis: copy-holder ORDER — the workhorse field bullets carry the home
    # template's slot sequence, in that order, followed by the separator and
    # original-body fields. The expected sequence is the RUNTIME contract's
    # issue_contract.SLOTS — cross-checked against the fenced template in
    # issue-contract.md § Pre-doctrine issues — never hand-written here.
    slots = _pre_doctrine_template_slot_order()
    block = _workhorse_repair_template_block()
    labels = _WORKHORSE_REPAIR_FIELD_BULLET_RE.findall(block)
    expected_count = len(slots) + len(_WORKHORSE_REPAIR_TRAILING_FIELD_TOKENS)
    assert len(labels) == expected_count, (
        "workhorse/SKILL.md repair template: expected exactly %d field bullets "
        "(%d home slots + %d trailing fields), found %d; labels: %r"
        % (
            expected_count,
            len(slots),
            len(_WORKHORSE_REPAIR_TRAILING_FIELD_TOKENS),
            len(labels),
            labels,
        )
    )
    for index, slot in enumerate(slots):
        assert re.search(r"\b%s\b" % re.escape(slot), labels[index]), (
            "workhorse/SKILL.md repair template: field bullet %d is %r, which does "
            "not name the %r slot — issue_contract.SLOTS declares the slot order %r "
            "and every copy-holder must follow it"
            % (index + 1, labels[index], slot, slots)
        )
    for offset, token in enumerate(_WORKHORSE_REPAIR_TRAILING_FIELD_TOKENS):
        index = len(slots) + offset
        assert token in labels[index], (
            "workhorse/SKILL.md repair template: field bullet %d is %r, which does "
            "not carry the %r field (reordered, removed, or duplicated?); labels: %r"
            % (index + 1, labels[index], token, labels)
        )


# --- Cluster: four-route drift (register R6 → the two charters) ---------------

_ROUTING_REGISTER_REL = (
    "../../docs/superheroes/front-half-sdlc-core-6181ee/register.md"
)

_ROUTING_SHOWRUNNER_CHARTER = "skills/showrunner/SKILL.md"
_ROUTING_WORKHORSE_CHARTER = "skills/workhorse/SKILL.md"

# Holder-specific pin — charter wording denying a precedence procedure; not derived from R6.
_ROUTING_PRECEDENCE_DENIAL_PIN = "No precedence procedure exists and none ships"

_ROUTING_INVERTED_FORMS = (
    "run **discovery** yourself",
    "elicit with the owner",
    "judge the route yourself",
    "you run discovery when the route calls for it",
    "the builder runs discovery with the owner first",
)

# Copy-holder enumeration anchors — one row per hand-maintained route-name list outside the
# two charter bodies. root: "plugin" = PLUGIN-relative path; "repo" = repository root.
# Extraction normalizes per holder (strip backticks where present) before list compare.
_ROUTING_COPY_HOLDER_SPECS = (
    (
        "skills/showrunner/SKILL.md frontmatter description",
        "skills/showrunner/SKILL.md",
        "plugin",
        r"to one of four routes \(([^)]+)\)",
    ),
    (
        "skills/configure/reference/preflight.md §E",
        "skills/configure/reference/preflight.md",
        "plugin",
        r"## E — Board wiring for the issue being ripped",
    ),
    (
        "README.md Showrunner section",
        "README.md",
        "repo",
        r"## Showrunner — the advisor session",
    ),
    (
        "CONVENTIONS.md Showrunner cast bullet",
        "CONVENTIONS.md",
        "repo",
        r"- \*\*Showrunner\*\* — the advisor session",
    ),
    (
        "eval/skills/registry.json requiredPhrases",
        "eval/skills/registry.json",
        "repo",
        r'"superheroes/showrunner"',
    ),
)


def _routing_repo_root():
    return os.path.normpath(os.path.join(PLUGIN, "..", ".."))


def _routing_holder_path(root_kind, rel):
    if root_kind == "plugin":
        return os.path.join(PLUGIN, rel)
    return os.path.join(_routing_repo_root(), rel)


def _routing_names_from_paren_or_backticks(fragment):
    """Normalize holder fragments — backticks are stripped per holder, not uniform."""
    if "`" in fragment:
        names = re.findall(r"`([^`]+)`", fragment)
        if names:
            return names
    parts = [p.strip().strip("`") for p in fragment.split(",")]
    return [p for p in parts if p]


def _routing_names_from_copy_holder(label, root_kind, rel, anchor_pattern):
    path = _routing_holder_path(root_kind, rel)
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError as exc:
        pytest.fail(
            "%s: cannot read copy-holder at %s — %s" % (label, path, exc)
        )
    if label == "eval/skills/registry.json requiredPhrases":
        m = re.search(anchor_pattern, text)
        if not m:
            pytest.fail(
                "%s: anchor not found — %r" % (label, anchor_pattern)
            )
        try:
            registry = json.loads(text)
        except json.JSONDecodeError as exc:
            pytest.fail("%s: invalid JSON at %s — %s" % (label, path, exc))
        phrases = registry.get("requiredPhrases", {}).get(
            "superheroes/showrunner", []
        )
        route_phrase = next(
            (p for p in phrases if "four routes" in p),
            None,
        )
        if route_phrase is None:
            pytest.fail(
                "%s: requiredPhrases missing four-routes phrase for "
                "superheroes/showrunner" % label
            )
        pm = re.search(r"\(([^)]+)\)", route_phrase)
        if not pm:
            pytest.fail(
                "%s: four-routes phrase missing parenthesized enumeration: %r"
                % (label, route_phrase)
            )
        return _routing_names_from_paren_or_backticks(pm.group(1))
    if label == "skills/showrunner/SKILL.md frontmatter description":
        fm = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not fm:
            pytest.fail(
                "%s: YAML frontmatter block cannot be delimited at start of "
                "file" % label
            )
        frontmatter = fm.group(1)
        enum_pattern = r"to one of four routes \(([^)]+)\)"
        matches = list(re.finditer(enum_pattern, frontmatter))
        if len(matches) != 1:
            if not matches:
                pytest.fail(
                    "%s: anchor not found in frontmatter — %r"
                    % (label, enum_pattern)
                )
            pytest.fail(
                "%s: expected exactly one route enumeration in frontmatter, "
                "found %d" % (label, len(matches))
            )
        return _routing_names_from_paren_or_backticks(matches[0].group(1))
    m = re.search(anchor_pattern, text, re.MULTILINE)
    if not m:
        pytest.fail("%s: anchor not found — %r" % (label, anchor_pattern))
    if label == "skills/configure/reference/preflight.md §E":
        region = text[m.end(): m.end() + 400]
        om = re.search(
            r"one of ((?:`[^`]+`(?:,\s*)?)+)",
            region,
            re.DOTALL,
        )
        if not om:
            pytest.fail(
                "%s: route enumeration not found after §E anchor" % label
            )
        return _routing_names_from_paren_or_backticks(om.group(1))
    if label == "README.md Showrunner section":
        region = text[m.end(): m.end() + 600]
        phrase = "one of four intake routes"
        if phrase not in region:
            pytest.fail(
                "%s: anchor phrase %r not found in bounded region"
                % (label, phrase)
            )
        enum_pattern = re.escape(phrase) + r"\s*\(([^)]+)\)"
        matches = list(re.finditer(enum_pattern, region, re.DOTALL))
        if len(matches) != 1:
            pytest.fail(
                "%s: expected exactly one anchored enumeration after %r, "
                "found %d" % (label, phrase, len(matches))
            )
        return _routing_names_from_paren_or_backticks(matches[0].group(1))
    if label == "CONVENTIONS.md Showrunner cast bullet":
        region = text[m.start(): m.start() + 600]
        phrase = "one of four intake routes"
        if phrase not in region:
            pytest.fail(
                "%s: anchor phrase %r not found in bounded region"
                % (label, phrase)
            )
        enum_pattern = re.escape(phrase) + r"\s*\(([^)]+)\)"
        matches = list(re.finditer(enum_pattern, region, re.DOTALL))
        if len(matches) != 1:
            pytest.fail(
                "%s: expected exactly one anchored enumeration after %r, "
                "found %d" % (label, phrase, len(matches))
            )
        return _routing_names_from_paren_or_backticks(matches[0].group(1))
    pytest.fail("%s: no extraction rule for copy-holder" % label)


def _routing_register_path():
    return os.path.normpath(os.path.join(PLUGIN, _ROUTING_REGISTER_REL))


def _routing_normalize(text):
    """Compare byte-literal pins after stripping emphasis markup and collapsing whitespace."""
    stripped = text.replace("*", "").replace("_", "")
    return re.sub(r"\s+", " ", stripped).strip()


def _routing_inverted_normalize(text):
    """Markup-blind normalize for inverted-form absence census.

    Strips emphasis and backticks so a banned phrase is caught however it is emphasised."""
    stripped = text.replace("*", "").replace("_", "").replace("`", "")
    return re.sub(r"\s+", " ", stripped).strip()


def test_routing_normalize_preserves_backticks_inverted_normalize_strips_them():
    """Pin the backtick-sensitive vs backtick-blind split between routing normalizers."""
    sample = "use `resolve-write --doc spec` here"
    assert "`" in _routing_normalize(sample)
    assert "`" not in _routing_inverted_normalize(sample)
    assert _routing_normalize(sample.replace("`", "")) == _routing_inverted_normalize(sample)


def _routing_parse_r6_entry_text():
    """Fail-closed R6 quotable text — header line through the first blank line."""
    path = _routing_register_path()
    try:
        text = _read(_ROUTING_REGISTER_REL)
    except OSError:
        pytest.fail(
            "register R6 entry not found — cannot read register at %s" % path
        )
    m = re.search(r"^\*\*R6 — ", text, re.MULTILINE)
    if not m:
        pytest.fail(
            "register R6 entry not found — no **R6 — header in %s" % path
        )
    lines = text[m.start():].splitlines()
    entry_lines = [lines[0]]
    for line in lines[1:]:
        if line.strip() == "":
            break
        entry_lines.append(line)
    entry_text = "\n".join(entry_lines)
    if not entry_text.strip():
        pytest.fail(
            "register R6 entry not found — empty entry body in %s" % path
        )
    return entry_text


def _routing_route_names_from_r6(entry_text):
    m = re.search(
        r"The four intake routes are named (.*?), and their tests are",
        entry_text,
    )
    assert m, (
        "register R6: four-route name enumeration not found (moved or reworded?)"
    )
    names = re.findall(r"`([^`]+)`", m.group(1))
    assert len(names) == 4, (
        "register R6: expected exactly four route names, found %d: %r"
        % (len(names), names)
    )
    assert len(set(names)) == 4, (
        "register R6: route names must be distinct, found duplicates in %r"
        % names
    )
    return names


def _routing_route_tests_from_r6(entry_text):
    m_start = re.search(
        r"and their tests are FR-5's cases as amended: ",
        entry_text,
    )
    assert m_start, (
        "register R6: route-test segment start not found (moved or reworded?)"
    )
    tail = entry_text[m_start.end():]
    m_end = re.search(r"\bThese are JUDGMENT INPUTS", tail)
    assert m_end, (
        "register R6: route-test segment end not found (moved or reworded?)"
    )
    segment = tail[:m_end.start()]
    parts = segment.split("; ")
    assert len(parts) == 4, (
        "register R6: expected exactly four route tests, found %d: %r"
        % (len(parts), parts)
    )
    for part in parts:
        assert re.search(r"→ `[^`]+`", part), (
            "register R6: route test missing arrow-and-route-name: %r" % part
        )
    return parts


def _routing_judgment_sentence_from_r6(entry_text):
    m = re.search(
        r"(These are JUDGMENT INPUTS.*?recorded with the route and anchor at routing time)",
        entry_text,
        re.DOTALL,
    )
    assert m, (
        "register R6: judgment-input sentence not found (moved or reworded?)"
    )
    return m.group(1)


def _showrunner_routing_block():
    text = _read(_ROUTING_SHOWRUNNER_CHARTER)
    start_m = re.search(
        r"^\s*\*\*Route each issue to exactly one of four routes\.\*\*",
        text,
        re.MULTILINE,
    )
    assert start_m, (
        "showrunner/SKILL.md: routing block start not found (moved or reworded?)"
    )
    end_m = re.search(
        r"\*\*Only `build-ready` produces a builder launch",
        text[start_m.start():],
        re.MULTILINE,
    )
    assert end_m, (
        "showrunner/SKILL.md: routing block end not found (moved or reworded?)"
    )
    block = text[start_m.start(): start_m.start() + end_m.start()].strip()
    assert block.strip(), (
        "showrunner/SKILL.md: routing block is empty (moved or reworded?)"
    )
    return block


def _workhorse_intake_section():
    text = _read(_ROUTING_WORKHORSE_CHARTER)
    m = re.search(
        r"^## 1\. Intake — read the route and get the go-ahead\n(.*?)(?=^## 2\.|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "workhorse/SKILL.md: §1 Intake section not found (moved or reworded?)"
    )
    body = m.group(1)
    assert body.strip(), (
        "workhorse/SKILL.md: §1 Intake section body is empty (moved or reworded?)"
    )
    return body


def _workhorse_route_carry_sentence():
    section = _workhorse_intake_section()
    lines = section.splitlines()
    carry_lines = []
    started = False
    for line in lines:
        if line.startswith(
            "A routed issue carries exactly one of the advisor's four routes"
        ):
            started = True
            carry_lines.append(line)
        elif started:
            if line.strip() == "" or line.startswith("- "):
                break
            carry_lines.append(line)
    assert carry_lines, (
        "workhorse/SKILL.md: routed-issue route sentence not found "
        "(moved or reworded?)"
    )
    return "\n".join(carry_lines)


def _workhorse_route_bullet_names():
    section = _workhorse_intake_section()
    names = []
    for line in section.splitlines():
        m = re.match(r"^- \*\*`([^`]+)`\*\*", line)
        if m:
            names.append(m.group(1))
    assert len(names) == 4, (
        "workhorse/SKILL.md: expected exactly four §1 route bullets, found %d: %r"
        % (len(names), names)
    )
    return names


def _routing_charter_surfaces():
    return (
        _ROUTING_SHOWRUNNER_CHARTER,
        _ROUTING_WORKHORSE_CHARTER,
    )


def _retired_discovery_route_literal():
    """Retired route name — composed at runtime so this census file can scan itself."""
    return "-".join(("needs", "discovery"))


def _routing_census_paths():
    repo_root = _routing_repo_root()
    readme = os.path.join(repo_root, "README.md")
    conventions = os.path.join(repo_root, "CONVENTIONS.md")
    return [readme, conventions] + _collect_plugin_source_paths(PLUGIN)


def _scan_paths_for_literal(paths, literal):
    hits = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        rel = os.path.relpath(path, PLUGIN)
        if rel.startswith(".."):
            rel = os.path.relpath(path, os.path.normpath(os.path.join(PLUGIN, "..", "..")))
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                if literal in line:
                    hits.append((rel, lineno))
    return hits


def test_r6_route_spans_in_showrunner_routing_block():
    # axis: text agreement with register R6 — route tests and judgment-input sentence
    entry = _routing_parse_r6_entry_text()
    route_tests = _routing_route_tests_from_r6(entry)
    judgment = _routing_judgment_sentence_from_r6(entry)
    block = _showrunner_routing_block()
    block_norm = _routing_normalize(block)
    for span in route_tests:
        span_norm = _routing_normalize(span)
        assert span_norm in block_norm, (
            "showrunner routing block missing R6 route test span %r" % span
        )
    judgment_norm = _routing_normalize(judgment)
    assert judgment_norm in block_norm, (
        "showrunner routing block missing R6 judgment-input sentence %r" % judgment
    )
    _precedence_denial = "this register decides no precedence."
    _precedence_count = entry.count(_precedence_denial)
    assert _precedence_count == 1, (
        "register R6: expected exactly one occurrence of %r in home entry, "
        "found %d — charter pin below is no longer licensed"
        % (_precedence_denial, _precedence_count)
    )
    # Holder-specific pin — not home-derived; bounds the register-voice tail adaptation.
    # Home bound (decides no precedence) is checked first per CONVENTIONS §11.3.
    pin_norm = _routing_normalize(_ROUTING_PRECEDENCE_DENIAL_PIN)
    assert pin_norm in block_norm, (
        "showrunner routing block missing precedence-denial pin %r"
        % _ROUTING_PRECEDENCE_DENIAL_PIN
    )


def test_route_names_enumerated_in_order_in_both_charters():
    # axis: completeness and order of route-name enumeration — duplicate-sensitive list compare
    entry = _routing_parse_r6_entry_text()
    expected = _routing_route_names_from_r6(entry)
    showrunner_block = _showrunner_routing_block()
    m_names = re.search(
        r"The four intake routes are named.*?and their tests are",
        showrunner_block,
        re.DOTALL,
    )
    assert m_names, (
        "showrunner/SKILL.md: route-name sentence not found in routing block"
    )
    showrunner_names = re.findall(r"`([^`]+)`", m_names.group(0))
    assert showrunner_names == expected, (
        "showrunner route-name list drift — expected %r, found %r"
        % (expected, showrunner_names)
    )
    workhorse_sentence = _workhorse_route_carry_sentence()
    workhorse_names = re.findall(r"`([^`]+)`", workhorse_sentence)
    assert workhorse_names == expected, (
        "workhorse route-carry sentence list drift — expected %r, found %r"
        % (expected, workhorse_names)
    )
    workhorse_bullets = _workhorse_route_bullet_names()
    bullet_drift = [
        name
        for name in expected
        if workhorse_bullets.count(name) != 1
    ]
    assert not bullet_drift, (
        "workhorse §1 route-bullet list drift — each R6 name must appear once "
        "in bullets; problems for %r in %r"
        % (bullet_drift, workhorse_bullets)
    )


def test_route_names_enumerated_in_order_in_copy_holders():
    # axis: completeness and order of route-name enumeration in prose/registry copies
    entry = _routing_parse_r6_entry_text()
    expected = _routing_route_names_from_r6(entry)
    for label, rel, root_kind, anchor in _ROUTING_COPY_HOLDER_SPECS:
        found = _routing_names_from_copy_holder(label, root_kind, rel, anchor)
        assert found == expected, (
            "%s: route-name list drift — expected %r, found %r"
            % (label, expected, found)
        )


def test_census_excludes_pycache_but_catches_retired_route_literal(tmp_path):
    """Retired route name: __pycache__ carrying the literal is excluded; .py source is reported."""
    literal = _retired_discovery_route_literal()
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

    # _scan_paths_for_literal rel paths are PLUGIN-relative (..-heavy on tmp_path trees).
    hits = _scan_paths_for_literal(paths, literal)
    stale_hits = [
        (rel, lineno)
        for rel, lineno in hits
        if rel.endswith("stale_hit.py") or rel.endswith(os.path.join("lib", "stale_hit.py"))
    ]
    assert stale_hits, (
        "expected _scan_paths_for_literal to report stale_hit.py, got hits %r" % hits
    )
    assert stale_hits[0][1] == 1, (
        "expected literal on line 1 of stale_hit.py, got %r" % stale_hits
    )


def test_retired_discovery_route_name_census():
    # axis: absence of the retired route name across plugin source, README, CONVENTIONS
    # docs/ is out of scope — specs and child definition-docs quote the retired name as history.
    literal = _retired_discovery_route_literal()
    paths = _routing_census_paths()
    hits = _scan_paths_for_literal(paths, literal)
    assert not hits, (
        "retired route name %r found outside allowed history-only docs — hits: %r"
        % (literal, hits)
    )


def test_charters_forbid_inverted_routing_forms():
    """Removed routing behaviours must not creep back into either charter.

    Residual: the guard treats each charter as one whitespace-collapsed stream,
    so a forbidden phrase synthesized across a paragraph boundary (e.g. a line
    ending in ``run`` followed by a line beginning ``discovery yourself``)
    would be reported as a hit — a false positive — and that is accepted
    rather than closed with block-aware markdown parsing.
    """
    # axis: removed routing behaviours have not crept back into either charter
    inverted = list(_ROUTING_INVERTED_FORMS)
    inverted.append(_retired_discovery_route_literal())
    inverted_norm = [_routing_inverted_normalize(form) for form in inverted]
    hits = []
    for rel in _routing_charter_surfaces():
        text = _read(rel)
        text_norm = _routing_inverted_normalize(text)
        for form, form_norm in zip(inverted, inverted_norm):
            if form_norm.lower() in text_norm.lower():
                # Whole-text match is the failure; line number is diagnostic only.
                diag_line = None
                first_token = re.sub(r"\*+", "", form_norm.split()[0]).lower()
                for lineno, line in enumerate(text.splitlines(), start=1):
                    line_norm = _routing_inverted_normalize(line).lower()
                    if first_token in line_norm:
                        diag_line = lineno
                        break
                hits.append((rel, diag_line, form))
    assert not hits, (
        "inverted routing form(s) found in charter(s): %r" % hits
    )


# --- Cluster: package-read-audit vocabulary (package_read_audit → decomposition.md) ---
#
# Copy-holders enumerated (§11.2 caveat — every known copy must be listed here):
# - skills/showrunner/reference/decomposition.md § The audit trail (three check result tokens
#   and exit codes only)
# - CONVENTIONS.md §11.2 worked example 6 (enumeration of home + copy-holder)


_DECOMPOSITION_DOC = "skills/showrunner/reference/decomposition.md"


def _package_read_audit_audit_trail_section(doc):
    """### The audit trail in decomposition.md."""
    headings = re.findall(r"^### The audit trail\s*$", doc, re.MULTILINE)
    assert len(headings) == 1, (
        "decomposition.md: expected exactly one ### The audit trail heading, found %d"
        % len(headings)
    )
    m = re.search(
        r"^### The audit trail\s*\n(.*?)(?:\n### |\Z)",
        doc,
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        "decomposition.md: ### The audit trail section not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _package_read_audit_result_exit_pairs_from_doc(section):
    """Result tokens paired with exit codes from the audit-trail prose."""
    pairs = re.findall(
        r"\*\*`([^`]+)`\*\* \(exit (\d+)\)",
        section,
    )
    assert pairs, (
        "decomposition.md: no **`<token>`** (exit N) pairings found in "
        "### The audit trail (moved or reformatted?)"
    )
    return {token: int(exit_code) for token, exit_code in pairs}


def _package_read_audit_check_exit_mapping_from_home():
    import package_read_audit

    return {
        package_read_audit.RESULT_CONFORMING: package_read_audit.EXIT_CONFORMING,
        package_read_audit.RESULT_NONCONFORMING: package_read_audit.EXIT_NONCONFORMING,
        package_read_audit.RESULT_UNDECIDED: package_read_audit.EXIT_UNDECIDED,
    }


def _package_read_audit_non_result_vocabulary_from_home():
    """Refusal, nonconformity, undecided-reason and record-kind tokens minus check results."""
    import package_read_audit

    tokens = set()
    tokens |= set(package_read_audit.REFUSAL_REASONS)
    tokens |= set(package_read_audit.UNDECIDED_REASONS)
    tokens |= set(package_read_audit.NONCONFORMITY_KINDS)
    tokens |= set(package_read_audit.RECORD_KINDS)
    return tokens - set(package_read_audit.CHECK_RESULTS)


# Tokens excluded from the further-token sweep: ordinary English words that also
# appear as record-kind or reason literals — matching even token-shaped forms
# would false-positive on audit-trail prose ("per-round", "verification pass",
# "invocation's cause", "usage" in a CLI sense). pass/fail/light/full/verified/
# failed/engaged live in other module families (SYNC_RESULTS, WEIGHTS, OUTCOMES,
# CONTROL_PROBE_READS) and are outside this sweep entirely.
_PACKAGE_READ_AUDIT_ENGLISH_WORD_EXCLUSIONS = frozenset({
    "round",
    "verification",
    "invocation",
    "usage",
})


def _package_read_audit_token_shaped_occurrence(token, text):
    """Token-shaped occurrence: backticks or a standalone hyphenated identifier."""
    if re.search(r"`" + re.escape(token) + r"`", text):
        return True
    if "-" in token and re.search(
        r"(?<![\w-])" + re.escape(token) + r"(?![\w-])",
        text,
    ):
        return True
    return False


def _package_read_audit_worked_example_6_from_conventions():
    """Worked example 6 prose block from CONVENTIONS §11.2."""
    text = _read("../../CONVENTIONS.md")
    m = re.search(
        r"\*Worked example 6 — the package-read-audit vocabulary\.\* (.*?)\n\n",
        text,
        re.DOTALL,
    )
    assert m, (
        "CONVENTIONS.md §11: package-read-audit worked example 6 not found "
        "(moved or reworded?)"
    )
    return m.group(1)


def _package_read_audit_check_flags_from_home():
    """`check` subcommand flags from _main_check argparse registration."""
    text = _read("lib/package_read_audit.py")
    m = re.search(r"def _main_check\(argv\):(.*?)(?=\ndef |\Z)", text, re.DOTALL)
    assert m, (
        "package_read_audit.py: _main_check not found (moved or reworded?)"
    )
    flags = re.findall(r'parser\.add_argument\("(--[^"]+)"', m.group(1))
    assert flags, (
        "package_read_audit.py: _main_check has no parser.add_argument flags "
        "(moved or reworded?)"
    )
    return set(flags)


def _package_read_audit_check_flags_from_doc(section):
    """Flags named in the audit-trail fenced invocation and --invocation prose."""
    fences = re.findall(r"```bash\n(.*?)```", section, re.DOTALL)
    assert len(fences) == 1, (
        "decomposition.md: expected exactly one ```bash fence in "
        "### The audit trail, found %d"
        % len(fences)
    )
    fence = fences[0]
    assert " check " in fence or fence.strip().endswith(" check"), (
        "decomposition.md: fenced invocation does not name the check subcommand "
        "(moved or reformatted?)"
    )
    flags = set(re.findall(r"(--[\w-]+)", fence))
    assert re.search(r"`--invocation(?:\s+<[^>]+>)?`", section), (
        "decomposition.md: --invocation not named in ### The audit trail prose "
        "(moved or reformatted?)"
    )
    flags.add("--invocation")
    assert flags, (
        "decomposition.md: fenced invocation parsed to zero flags "
        "(regex drift or empty fence?)"
    )
    return flags


def test_package_read_audit_result_tokens_in_decomposition_doc():
    """§11: decomposition.md restates package_read_audit check results and exit codes."""
    import package_read_audit

    home_results = set(package_read_audit.CHECK_RESULTS)
    home_mapping = _package_read_audit_check_exit_mapping_from_home()
    doc = _read(_DECOMPOSITION_DOC)
    section = _package_read_audit_audit_trail_section(doc)
    doc_mapping = _package_read_audit_result_exit_pairs_from_doc(section)

    missing_tokens = sorted(home_results - set(doc_mapping.keys()))
    extra_tokens = sorted(set(doc_mapping.keys()) - home_results)
    wrong_exits = sorted(
        token
        for token in home_results
        if token in doc_mapping and doc_mapping[token] != home_mapping[token]
    )
    assert (
        not missing_tokens and not extra_tokens and not wrong_exits
    ), (
        "decomposition.md check result/exit drift from package_read_audit "
        "CHECK_RESULTS/EXIT_* — missing tokens: %r; extra tokens: %r; "
        "exit mismatches: %r"
        % (missing_tokens, extra_tokens, wrong_exits)
    )


def test_decomposition_doc_restates_no_further_tokens():
    """§11: decomposition.md does not restate non-result package_read_audit tokens."""
    sweep = _package_read_audit_non_result_vocabulary_from_home()
    sweep -= _PACKAGE_READ_AUDIT_ENGLISH_WORD_EXCLUSIONS
    doc = _read(_DECOMPOSITION_DOC)
    hits = sorted(
        token
        for token in sweep
        if _package_read_audit_token_shaped_occurrence(token, doc)
    )
    assert not hits, (
        "decomposition.md restates package_read_audit token(s) outside the "
        "enumerated check-result copy — add the doc to CONVENTIONS §11.2 "
        "worked example 6 or remove the token(s): %r"
        % hits
    )


def test_conventions_worked_example_6_enumerates_the_copy_holders():
    """§11: CONVENTIONS worked example 6 names the home module and copy-holder doc."""
    prose = _package_read_audit_worked_example_6_from_conventions()
    assert "plugins/superheroes/lib/package_read_audit.py" in prose, (
        "CONVENTIONS.md §11: worked example 6 missing authoritative home path "
        "plugins/superheroes/lib/package_read_audit.py"
    )
    assert "skills/showrunner/reference/decomposition.md" in prose, (
        "CONVENTIONS.md §11: worked example 6 missing enumerated copy-holder "
        "skills/showrunner/reference/decomposition.md"
    )


def test_decomposition_doc_invocation_matches_the_cli():
    """§11: decomposition.md check invocation flags match package_read_audit CLI."""
    home_flags = _package_read_audit_check_flags_from_home()
    doc = _read(_DECOMPOSITION_DOC)
    section = _package_read_audit_audit_trail_section(doc)
    doc_flags = _package_read_audit_check_flags_from_doc(section)
    missing_from_cli = sorted(doc_flags - home_flags)
    extra_in_doc = sorted(home_flags - doc_flags)
    assert not missing_from_cli and not extra_in_doc, (
        "decomposition.md check invocation drift from package_read_audit "
        "_main_check flags — doc names flags CLI lacks: %r; CLI accepts flags "
        "doc does not publish: %r"
        % (missing_from_cli, extra_in_doc)
    )


# --- Cluster: R8 closure receipt elements (pinned register literal) --------

R8_CLOSURE_RECEIPT_ELEMENTS = (
    "The closure receipt enumerates exactly: coverage map complete; all other children merged "
    "with green vets; amendments reconciled — meaning the Amendments log is valid against R4's "
    "format AND UFR-4's propagation is verified: every affected child carried the amended text "
    "or an explicit notice, and the coverage map still allocates every acceptance criterion; "
    "one end-to-end validation run against the current spec body with its result stated; "
    "aggregated Show-it items; delivered versus deferred/declined named; and NFR conformance "
    "checked across the delivery (owner reading load, plain language, guidelines never hardened "
    "into gates) — an absent element is named with why."
)

_R8_PLUGIN_COPY_HOLDERS = (
    "skills/showrunner/reference/closure.md",
)

# §11.2: every known in-repo copy-holder outside the plugin for R8. A child doc that stops
# quoting an entry is a real failure, not a stale test — the register's Consumers line
# decides who must quote it.
_R8_IN_REPO_COPY_HOLDERS = (
    _EPIC_REGISTER_REL,
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c6-epic-machinery.md")
    ),
    os.path.normpath(
        os.path.join("..", "..", "docs", "superheroes",
                     "front-half-sdlc-core-6181ee", "children", "c7-closure.md")
    ),
)


def test_r8_pinned_literal_exactly_once_in_epic_register_when_reachable():
    """§11.2: pinned R8 literal is byte-exact in the epic register when the home is reachable."""
    _assert_literal_exactly_once_if_reachable(
        R8_CLOSURE_RECEIPT_ELEMENTS, _EPIC_REGISTER_REL
    )


def test_r8_closure_receipt_elements_exactly_once_in_plugin_copy_holders():
    """§11.2: R8 closure-receipt element sentence is byte-identical in every plugin copy-holder."""
    for rel in _R8_PLUGIN_COPY_HOLDERS:
        _assert_literal_exactly_once(R8_CLOSURE_RECEIPT_ELEMENTS, rel)


def test_r8_closure_receipt_elements_exactly_once_in_in_repo_copy_holders():
    """§11.2: R8 closure-receipt element sentence is byte-identical in every in-repo copy-holder."""
    _assert_literal_exactly_once_across_holders(
        R8_CLOSURE_RECEIPT_ELEMENTS, _R8_IN_REPO_COPY_HOLDERS
    )


def test_grouping_payload_valid_delegates_to_payload_contracts_not_hand_copy():
    """§11: engine_adapter._grouping_payload_valid must delegate to payload_contracts P_SYNTHESIS."""
    text = _read("lib/engine_adapter.py")
    assert "payload_contracts.payload_fault" in text
    assert "payload_contracts.P_SYNTHESIS" in text
    for marker in _HANDWRITTEN_GROUPING_VALIDATION_MARKERS:
        assert marker not in text, (
            "hand-written P_SYNTHESIS grouping validation reappeared: %r" % marker
        )


_HANDWRITTEN_GROUPING_VALIDATION_MARKERS = (
    "for member in member_ids:",
    "if not isinstance(member_ids, list) or not member_ids:",
)


def test_grouping_contract_copy_census():
    """Census: P_SYNTHESIS grouping shape rule has exactly one home plus delegation in engine_adapter."""
    engine_text = _read("lib/engine_adapter.py")
    round_text = _read("lib/round_adapters.py")
    payload_text = _read("lib/payload_contracts.py")
    copies = []
    if ("member_ids-non-empty-strings" in payload_text
            and "member_ids-non-empty-strings" not in round_text):
        copies.append("payload_contracts-home")
    elif "member_ids-non-empty-strings" in round_text:
        copies.append("duplicate-home")
    else:
        copies.append("missing-home")
    for marker in _HANDWRITTEN_GROUPING_VALIDATION_MARKERS:
        if marker in engine_text:
            copies.append("engine_adapter-hand-copy:%s" % marker)
    if ("payload_contracts.payload_fault" in engine_text
            and "payload_contracts.P_SYNTHESIS" in engine_text):
        copies.append("engine_adapter-delegation")
    assert copies.count("payload_contracts-home") == 1, (
        "P_SYNTHESIS grouping rule home missing or duplicated: %r" % copies
    )
    assert "engine_adapter-delegation" in copies, (
        "engine_adapter must delegate grouping validation to payload_contracts: %r" % copies
    )
    hand_copies = [c for c in copies if c.startswith("engine_adapter-hand-copy:")]
    assert not hand_copies, (
        "hand-written P_SYNTHESIS grouping validation copies found: %r" % hand_copies
    )


def test_r8_in_repo_copy_holder_census_drift_missing_paths():
    """§11.2: every listed in-repo R8 copy-holder must exist when any sibling holder is reachable."""
    reachable = []
    missing = []
    for rel in _R8_IN_REPO_COPY_HOLDERS:
        path = os.path.normpath(os.path.join(PLUGIN, rel))
        if os.path.isfile(path):
            reachable.append(path)
        else:
            missing.append(path)
    if not reachable:
        pytest.skip("no copy-holder reachable: %s" % ", ".join(missing))
    assert not missing, (
        "R8 in-repo copy-holder census drift: missing path(s): %s"
        % ", ".join(missing)
    )


# --- Cluster: session-mode vocabulary (#1151) -----------------------------------


def test_session_mode_modes_match_review_base_guard():
    """§11: review_base_guard.SESSION_MODES derives from session_mode.MODES."""
    import review_base_guard
    import session_mode

    assert review_base_guard.SESSION_MODES == session_mode.MODES
    assert review_base_guard.SESSION_MODES == frozenset({"pr", "branch"})


def test_round_driver_no_fail_open_branch_default_for_session_mode():
    """Chokepoint census: round_driver must not default session mode to branch."""
    text = _read("lib/round_driver.py")
    assert 'or "branch"' not in text
    assert "or 'branch'" not in text


_REVIEW_CODE_SKILL_MODE_DOC = "skills/review-code/SKILL.md"


def _review_code_skill_shell_mode_assignments(doc_path=_REVIEW_CODE_SKILL_MODE_DOC):
    """Parse MODE=<value> from bash fences in review-code SKILL.md (session-mode pin)."""
    text = _read(doc_path)
    assignments = []
    for fence in re.findall(r"```bash\n(.*?)```", text, re.DOTALL):
        assignments.extend(re.findall(r"\bMODE=([^\s;]+)", fence))
    return assignments


def test_review_code_skill_shell_mode_assignments_match_session_mode_modes():
    """T1: shell-fence MODE= assignments equal session_mode.MODES exactly."""
    import session_mode

    assignments = _review_code_skill_shell_mode_assignments()
    assert len(assignments) >= 2, (
        "review-code SKILL.md: expected at least two MODE= assignments in bash fences, "
        "found %d (anti-vacuity)" % len(assignments)
    )
    assert set(assignments) == set(session_mode.MODES), (
        "review-code SKILL.md MODE= assignments %r must equal session_mode.MODES %r"
        % (sorted(set(assignments)), sorted(session_mode.MODES))
    )


def test_review_code_skill_shell_mode_assignments_anti_vacuity():
    """T2: shell-fence pin must find at least two MODE= assignments."""
    assignments = _review_code_skill_shell_mode_assignments()
    assert len(assignments) >= 2, (
        "review-code SKILL.md: MODE= parse found %d assignment(s); need >= 2"
        % len(assignments)
    )


def test_session_mode_guards_derive_through_resolve():
    """T3: check_base and _read_meta derive through session_mode.resolve."""
    import inspect

    import grounding_stage
    import review_base_guard

    check_base_source = inspect.getsource(review_base_guard.check_base)
    read_meta_source = inspect.getsource(grounding_stage._read_meta)
    assert "session_mode.resolve" in check_base_source
    assert "session_mode.resolve" in read_meta_source
    assert "not in SESSION_MODES" not in check_base_source
    assert "not in SESSION_MODES" not in read_meta_source


def test_grounding_stage_branch_disposition_uses_mode_branch_constant():
    """Branch-mode disposition compares against session_mode.MODE_BRANCH."""
    import inspect

    import grounding_stage

    for label, func in (
        ("stage", grounding_stage.stage),
        ("_trust_boundary", grounding_stage._trust_boundary),
    ):
        src = inspect.getsource(func)
        assert "session_mode.MODE_BRANCH" in src, (
            "grounding_stage.%s must compare against session_mode.MODE_BRANCH" % label
        )
        assert '== "branch"' not in src and "== 'branch'" not in src, (
            "grounding_stage.%s must not compare against bare branch literal" % label
        )
