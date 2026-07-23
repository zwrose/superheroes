"""§11 drift guard: Guardian SKILL + lens-contract prose stay in sync with lib homes.

Copy-holders (name every copy per CONVENTIONS §11):
  - plugins/superheroes/skills/guardian/SKILL.md — storage layout paths, ledger outcomes
  - plugins/superheroes/skills/guardian/reference/lens-contract.md — lens contract parts
  - CONVENTIONS.md — guardian artifact subtree, ledger record fields, vitals set
Authoritative homes:
  - guardian_store.LAYOUT
  - guardian_lens.LENS_CONTRACT_PARTS
  - guardian_lens.FACTS
  - guardian_ledger.LEDGER_RECORD_FIELDS + guardian_ledger.ADJUDICATED_IN
  - guardian_ledger.OUTCOMES_FOR / OUTCOMES_AGAINST
  - guardian_vitals.VITALS
  - guardian_vitals.DRIFT_THRESHOLDS
"""
import importlib
import os
import re

import guardian_ledger
import guardian_lens
import guardian_store
import guardian_vitals

_PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_REPO = os.path.abspath(os.path.join(_PLUGIN, "..", ".."))
_SKILL = os.path.join(_PLUGIN, "skills", "guardian", "SKILL.md")
_LENS_CONTRACT = os.path.join(_PLUGIN, "skills", "guardian", "reference", "lens-contract.md")
_CONVENTIONS = os.path.join(_REPO, "CONVENTIONS.md")
_LEDGER_MODULE = os.path.join(_PLUGIN, "lib", "guardian_ledger.py")

_REGISTERED_LENSES_MARKER = re.compile(
    r"<!--\s*guardian:registered-lenses:start\s*-->(.*?)<!--\s*guardian:registered-lenses:end\s*-->",
    re.DOTALL,
)
_BACKTICKED = re.compile(r"`([^`]+)`")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _one(matches, label, shape):
    assert len(matches) == 1, (
        "%s: expected exactly one %s, found %d (rename or reformat broke the parser)"
        % (label, shape, len(matches)))
    return matches[0]


def _parse_skill_layout_paths(skill_text):
    """Parse guardian/ artifact paths from the SKILL storage table."""
    anchor = _one(
        re.findall(r"\| `guardian\.md` \|", skill_text),
        "SKILL.md", "`guardian.md` table anchor")
    assert anchor, "SKILL.md storage table anchor missing"
    paths = re.findall(r"`(guardian/[^`]+)`", skill_text)
    assert paths, "SKILL.md: no `guardian/...` paths parsed from storage table"
    return tuple(sorted(set(paths)))


def _parse_conventions_backtick_list(text, anchor_re, label):
    block = _one(re.findall(anchor_re, text, re.DOTALL), label, "backtick list anchor")
    items = re.findall(r"`([^`]+)`", block)
    assert items, "%s: anchor matched but no backtick tokens parsed" % label
    return tuple(items)


_OUTCOME_TOKEN = r"(?:`[^`]+`(?:\s*,\s*(?:and\s+)?|\s+and\s+)*)+"


def _parse_ledger_extension_field():
    """Parse the documented schema-extension field from guardian_ledger.py prose."""
    text = _read(_LEDGER_MODULE)
    documented = _one(
        re.findall(r"\*\*Schema extension — `([^`]+)`\.\*\*", text),
        "guardian_ledger.py", "schema-extension anchor")
    return documented


def _skill_registered_lens_names():
    """Backticked lens names between the SKILL rollout markers, in order (with dupes)."""
    skill = _read(_SKILL)
    m = _REGISTERED_LENSES_MARKER.search(skill)
    assert m, (
        "SKILL.md is missing the guardian:registered-lenses start/end markers — the "
        "roster sync guard cannot locate the registered-lens enumeration")
    return _BACKTICKED.findall(m.group(1))


def _production_lens_names():
    """Flatten guardian_lens.PRODUCTION_LENS_NAMES to the set of expected lens names."""
    names = []
    for exported in guardian_lens.PRODUCTION_LENS_NAMES.values():
        names.extend(exported)
    return names


def test_skill_references_guardian_layout_paths():
    """Storage layout ↔ SKILL prose (fail-closed, exact equality both directions)."""
    home_paths = tuple(
        sorted("guardian/" + guardian_store.LAYOUT[key] for key in guardian_store.LAYOUT))
    assert home_paths, "guardian_store.LAYOUT is empty — no authoritative home"
    skill = _read(_SKILL)
    documented = _parse_skill_layout_paths(skill)
    assert documented == home_paths, (
        "SKILL.md layout paths drifted from guardian_store.LAYOUT\n"
        "  documented only: %s\n  home only: %s"
        % (sorted(set(documented) - set(home_paths)),
           sorted(set(home_paths) - set(documented))))


def test_lens_contract_covers_all_parts():
    """Lens contract parts ↔ reference prose (§11.3 corollary — RHS traces to lib home)."""
    parts = guardian_lens.LENS_CONTRACT_PARTS
    assert parts, "guardian_lens.LENS_CONTRACT_PARTS is empty — no authoritative home"
    text = _read(_LENS_CONTRACT)
    for part in parts:
        assert part in text, "lens-contract.md missing contract part slug %r" % part
    assert set(parts) == {"collector", "baseline-diff", "validation", "consequence", "cost"}, (
        "LENS_CONTRACT_PARTS membership changed — update this golden set AND lens-contract.md "
        "(a silent removal would stop validate_lens requiring the dropped part)"
    )


def test_lens_contract_covers_all_facts():
    """FACTS ↔ reference prose (fail-closed)."""
    facts = guardian_lens.FACTS
    assert facts, "guardian_lens.FACTS is empty — no authoritative home"
    text = _read(_LENS_CONTRACT)
    for fact in facts:
        assert fact in text, "lens-contract.md missing FACTS member %r" % fact
    assert set(facts) == {"verify-command", "recorded-coverage", "stack-tags", "paths"}, (
        "FACTS membership changed — update this golden set AND lens-contract.md"
    )


def test_vitals_and_drift_thresholds_agree():
    """VITALS ↔ DRIFT_THRESHOLDS (authoritative homes must match in both directions)."""
    vitals = guardian_vitals.VITALS
    thresholds = guardian_vitals.DRIFT_THRESHOLDS
    missing = [v for v in vitals if v not in thresholds]
    assert not missing, "DRIFT_THRESHOLDS missing vitals: %s" % missing
    extra = [k for k in thresholds if k not in vitals]
    assert not extra, "DRIFT_THRESHOLDS has keys not in VITALS: %s" % extra


def test_conventions_mentions_vitals_and_ledger_fields():
    """CONVENTIONS §2.1 prose ↔ vitals set + ledger record fields (exact equality)."""
    text = _read(_CONVENTIONS)
    documented_vitals = _parse_conventions_backtick_list(
        text,
        r"tracked each sweep \(([^;]+);",
        "CONVENTIONS.md vitals list")
    assert tuple(guardian_vitals.VITALS) == documented_vitals, (
        "CONVENTIONS.md vitals list drifted from guardian_vitals.VITALS\n"
        "  documented only: %s\n  home only: %s"
        % (sorted(set(documented_vitals) - set(guardian_vitals.VITALS)),
           sorted(set(guardian_vitals.VITALS) - set(documented_vitals))))
    documented_fields = _parse_conventions_backtick_list(
        text,
        r"LEDGER_RECORD_FIELDS`\)\s+carries ([^.]+)\.",
        "CONVENTIONS.md ledger record fields")
    assert tuple(guardian_ledger.LEDGER_RECORD_FIELDS) == documented_fields, (
        "CONVENTIONS.md ledger fields drifted from guardian_ledger.LEDGER_RECORD_FIELDS\n"
        "  documented only: %s\n  home only: %s"
        % (sorted(set(documented_fields) - set(guardian_ledger.LEDGER_RECORD_FIELDS)),
           sorted(set(guardian_ledger.LEDGER_RECORD_FIELDS) - set(documented_fields))))
    documented_for = _parse_conventions_backtick_list(
        text,
        r"(" + _OUTCOME_TOKEN + r") count for;",
        "CONVENTIONS.md outcomes-for list")
    documented_against = _parse_conventions_backtick_list(
        text,
        r"(" + _OUTCOME_TOKEN + r") count\s+against",
        "CONVENTIONS.md outcomes-against list")
    assert tuple(guardian_ledger.OUTCOMES_FOR) == documented_for, (
        "CONVENTIONS.md OUTCOMES_FOR drifted from guardian_ledger.OUTCOMES_FOR")
    assert tuple(guardian_ledger.OUTCOMES_AGAINST) == documented_against, (
        "CONVENTIONS.md OUTCOMES_AGAINST drifted from guardian_ledger.OUTCOMES_AGAINST")
    documented_extension = _parse_ledger_extension_field()
    assert documented_extension == guardian_ledger.ADJUDICATED_IN, (
        "guardian_ledger.py schema-extension prose drifted from ADJUDICATED_IN\n"
        "  documented only: %r\n  home only: %r"
        % (documented_extension, guardian_ledger.ADJUDICATED_IN))


def test_skill_mentions_ledger_outcomes():
    """SKILL prose ↔ ledger outcome maps (exact equality both directions)."""
    skill = _read(_SKILL)
    documented_for = _parse_conventions_backtick_list(
        skill,
        r"(" + _OUTCOME_TOKEN + r") count for;",
        "SKILL.md outcomes-for list")
    documented_against = _parse_conventions_backtick_list(
        skill,
        r"(" + _OUTCOME_TOKEN + r") count against",
        "SKILL.md outcomes-against list")
    assert tuple(guardian_ledger.OUTCOMES_FOR) == documented_for, (
        "SKILL.md OUTCOMES_FOR drifted from guardian_ledger.OUTCOMES_FOR\n"
        "  documented only: %s\n  home only: %s"
        % (sorted(set(documented_for) - set(guardian_ledger.OUTCOMES_FOR)),
           sorted(set(guardian_ledger.OUTCOMES_FOR) - set(documented_for))))
    assert tuple(guardian_ledger.OUTCOMES_AGAINST) == documented_against, (
        "SKILL.md OUTCOMES_AGAINST drifted from guardian_ledger.OUTCOMES_AGAINST\n"
        "  documented only: %s\n  home only: %s"
        % (sorted(set(documented_against) - set(guardian_ledger.OUTCOMES_AGAINST)),
           sorted(set(guardian_ledger.OUTCOMES_AGAINST) - set(documented_against))))


def test_conventions_vitals_guard_fails_on_home_mutation(monkeypatch):
    """Mutation check: a changed authoritative vital must fail the §11 guard."""
    original = guardian_vitals.VITALS
    monkeypatch.setattr(
        guardian_vitals, "VITALS",
        original + ("__mutation_probe__",))
    try:
        import pytest
        with pytest.raises(AssertionError, match="drifted"):
            test_conventions_mentions_vitals_and_ledger_fields()
    finally:
        monkeypatch.setattr(guardian_vitals, "VITALS", original)


def test_adjudicated_in_guard_fails_on_home_mutation(monkeypatch):
    """Mutation check: a renamed ADJUDICATED_IN must fail the §11 guard."""
    original = guardian_ledger.ADJUDICATED_IN
    monkeypatch.setattr(guardian_ledger, "ADJUDICATED_IN", "__mutation_probe__")
    try:
        import pytest
        with pytest.raises(AssertionError, match="drifted"):
            test_conventions_mentions_vitals_and_ledger_fields()
    finally:
        monkeypatch.setattr(guardian_ledger, "ADJUDICATED_IN", original)


def test_lens_contract_requires_guardian_tools_invocation_seam():
    """Tool invocation ↔ reference prose (§11 copy-holder — RHS traces to lib home)."""
    text = _read(_LENS_CONTRACT)
    assert "## Tool invocation" in text
    assert "guardian_tools.invoke" in text
    assert "guardian_tools.resolve" in text
    assert "guardian_tools.version" in text
    assert "contract violation" in text.lower()
    assert "guardian_tools.INSTALL_COMMANDS" in text
    import guardian_tools
    assert guardian_tools.INSTALL_COMMANDS, (
        "guardian_tools.INSTALL_COMMANDS is the authoritative install-command home"
    )


def test_lens_contract_covers_conformance_scenarios():
    """REQUIRED_CONFORMANCE_SCENARIOS ↔ reference prose (§11 drift guard)."""
    scenarios = guardian_lens.REQUIRED_CONFORMANCE_SCENARIOS
    assert scenarios, (
        "guardian_lens.REQUIRED_CONFORMANCE_SCENARIOS is empty — no authoritative home")
    text = _read(_LENS_CONTRACT)
    for scenario in scenarios:
        assert scenario in text, (
            "lens-contract.md missing conformance scenario %r" % scenario)
    assert set(scenarios) == {
        "missing-tool",
        "timeout",
        "nonzero-exit",
        "findings-empty-output",
        "unparseable",
        "reported-nonzero-parsed-zero",
    }, (
        "REQUIRED_CONFORMANCE_SCENARIOS membership changed — update this golden set "
        "AND lens-contract.md"
    )


def test_lens_contract_covers_lens_supplied_conformance_scenarios():
    """LENS_SUPPLIED_CONFORMANCE_SCENARIOS ↔ reference prose (§11 drift guard)."""
    lens_supplied = guardian_lens.LENS_SUPPLIED_CONFORMANCE_SCENARIOS
    assert lens_supplied, (
        "guardian_lens.LENS_SUPPLIED_CONFORMANCE_SCENARIOS is empty — no authoritative home")
    text = _read(_LENS_CONTRACT)
    for scenario in lens_supplied:
        assert scenario in text, (
            "lens-contract.md missing conformance scenario %r" % scenario)
        assert "lens-supplied" in text, (
            "lens-contract.md must describe %r as lens-supplied" % scenario)
    assert set(lens_supplied) == {"reported-nonzero-parsed-zero"}, (
        "LENS_SUPPLIED_CONFORMANCE_SCENARIOS membership changed — update this golden "
        "set AND lens-contract.md"
    )


def test_lens_contract_covers_conformance_case_fields():
    """CONFORMANCE_CASE_FIELDS ↔ reference prose (§11 drift guard)."""
    fields = guardian_lens.CONFORMANCE_CASE_FIELDS
    assert fields, (
        "guardian_lens.CONFORMANCE_CASE_FIELDS is empty — no authoritative home")
    text = _read(_LENS_CONTRACT)
    for field in fields:
        assert field in text, (
            "lens-contract.md missing conformance case field %r" % field)
    assert set(fields) == {"stdout", "clean_stdout", "exit"}, (
        "CONFORMANCE_CASE_FIELDS membership changed — update this golden set "
        "AND lens-contract.md"
    )


def test_lens_contract_covers_optional_conformance_case_fields():
    """CONFORMANCE_CASE_OPTIONAL_FIELDS ↔ reference prose (§11 drift guard)."""
    optional = guardian_lens.CONFORMANCE_CASE_OPTIONAL_FIELDS
    assert optional, (
        "guardian_lens.CONFORMANCE_CASE_OPTIONAL_FIELDS is empty — no authoritative home")
    text = _read(_LENS_CONTRACT)
    for field in optional:
        assert field in text, (
            "lens-contract.md missing optional conformance case field %r" % field)
    assert set(optional) == {
        "clean_exit", "config", "prev_digest",
        "stdout_by_tool", "clean_stdout_by_tool",
    }, (
        "CONFORMANCE_CASE_OPTIONAL_FIELDS membership changed — update this golden set "
        "AND lens-contract.md"
    )


def test_lens_contract_covers_permanent_boundary_key():
    """PERMANENT_BOUNDARY_KEY ↔ reference prose (§11 drift guard)."""
    key = guardian_lens.PERMANENT_BOUNDARY_KEY
    assert key == "permanentBoundary"
    text = _read(_LENS_CONTRACT)
    assert key in text, "lens-contract.md missing permanentBoundary key"
    assert "non-empty string `reason`" in text, (
        "lens-contract.md must document the reason requirement for permanent-boundary partials")


def test_permanent_boundary_rejects_partial_without_reason():
    """Fail-before: a partial with permanentBoundary but no reason must not seed a baseline."""
    assert guardian_lens.permanent_boundary({
        "status": "partial",
        guardian_lens.PERMANENT_BOUNDARY_KEY: True,
    }) is False
    assert guardian_lens.permanent_boundary({
        "status": "partial",
        guardian_lens.PERMANENT_BOUNDARY_KEY: True,
        "reason": "",
    }) is False


def test_lens_contract_covers_tool_free_conformance_scenarios():
    """TOOL_FREE_CONFORMANCE_SCENARIOS ↔ reference prose (§11 drift guard)."""
    scenarios = guardian_lens.TOOL_FREE_CONFORMANCE_SCENARIOS
    assert scenarios, (
        "guardian_lens.TOOL_FREE_CONFORMANCE_SCENARIOS is empty — no authoritative home")
    text = _read(_LENS_CONTRACT)
    for scenario in scenarios:
        assert scenario in text, (
            "lens-contract.md missing tool-free conformance scenario %r" % scenario)
    assert "uses_external_tools" in text, (
        "lens-contract.md must document the uses_external_tools opt-in")
    assert set(scenarios) == {
        "unreadable-input", "all-inputs-unavailable", "partial-carry-forward",
    }, (
        "TOOL_FREE_CONFORMANCE_SCENARIOS membership changed — update this golden set "
        "AND lens-contract.md"
    )


# --- production roster ↔ SKILL rollout sync (fail-closed, duplicate-sensitive) -----

def test_skill_rollout_roster_matches_production_lens_names():
    """Every PRODUCTION_LENS_NAMES entry is named in the SKILL rollout markers and vice
    versa — no drift, no duplicates. Protects each later lens registration."""
    skill_names = _skill_registered_lens_names()
    prod_names = _production_lens_names()

    assert skill_names, "no registered-lens names found between the SKILL rollout markers"
    assert len(skill_names) == len(set(skill_names)), (
        "duplicate lens name in the SKILL rollout markers: %s" % skill_names)
    assert len(prod_names) == len(set(prod_names)), (
        "duplicate lens name in PRODUCTION_LENS_NAMES: %s" % prod_names)
    assert set(skill_names) == set(prod_names), (
        "SKILL rollout roster %s drifted from PRODUCTION_LENS_NAMES %s — a lens registered "
        "in one but not the other" % (sorted(skill_names), sorted(prod_names)))


def test_skill_rollout_roster_guard_is_not_vacuous():
    """The guard must fail closed when a name is present on only one side."""
    prod_names = set(_production_lens_names())
    skill_names = set(_skill_registered_lens_names())
    # Baseline agreement (proven by the sibling test) — perturb each side and assert drift.
    assert skill_names == prod_names
    assert (skill_names | {"phantom-lens"}) != prod_names
    assert skill_names != (prod_names | {"phantom-lens"})


def test_production_lens_modules_and_names_are_in_sync():
    """C2: the runtime module roster (PRODUCTION_LENS_MODULES) and the name map
    (PRODUCTION_LENS_NAMES) must have IDENTICAL module-key sets — dropping a module from
    the loaded tuple while keeping its name mapping (or vice versa) must fail closed. The
    sibling roster test compares only PRODUCTION_LENS_NAMES against the SKILL prose, so it
    would not notice a module silently missing from the loaded tuple."""
    modules = guardian_lens.PRODUCTION_LENS_MODULES
    names = guardian_lens.PRODUCTION_LENS_NAMES
    assert len(modules) == len(set(modules)), (
        "duplicate module in PRODUCTION_LENS_MODULES: %s" % (modules,))
    assert set(modules) == set(names.keys()), (
        "PRODUCTION_LENS_MODULES %s drifted from PRODUCTION_LENS_NAMES keys %s — a module "
        "registered in one but not the other"
        % (sorted(modules), sorted(names.keys())))


def test_production_lens_modules_sync_guard_is_not_vacuous():
    """The C2 guard must fail closed when a module is on only one side."""
    modules = set(guardian_lens.PRODUCTION_LENS_MODULES)
    name_keys = set(guardian_lens.PRODUCTION_LENS_NAMES.keys())
    assert modules == name_keys
    assert (modules | {"guardian_lens_phantom"}) != name_keys
    assert modules != (name_keys | {"guardian_lens_phantom"})


def _module_exported_lens_names(module_name):
    """The set of lens names a rostered module actually EXPORTS via its module-level
    LENSES tuple."""
    module = importlib.import_module(module_name)
    exported = tuple(getattr(module, "LENSES", ()) or ())
    return {getattr(lens, "name", None) for lens in exported}


def test_module_exports_equal_declared_production_names():
    """H7: each rostered module's EXPORTED lens-name set must EQUAL its declared
    PRODUCTION_LENS_NAMES tuple — not merely be a superset. The loader fails closed on a
    MISSING expected name; an EXTRA undeclared export (a module shipping a lens no roster
    entry accounts for) would otherwise register silently. Set-equality rejects both."""
    for module_name, declared in guardian_lens.PRODUCTION_LENS_NAMES.items():
        exported = _module_exported_lens_names(module_name)
        assert None not in exported, (
            "module %r exports a lens object with no .name" % module_name)
        assert exported == set(declared), (
            "module %r exports lens names %s but PRODUCTION_LENS_NAMES declares %s — an "
            "undeclared surplus or a missing export"
            % (module_name, sorted(exported), sorted(declared)))


def test_module_export_equality_guard_is_not_vacuous():
    """The H7 guard must fail closed on an undeclared surplus export, not only a miss."""
    module_name = guardian_lens.PRODUCTION_LENS_MODULES[0]
    declared = set(guardian_lens.PRODUCTION_LENS_NAMES[module_name])
    exported = _module_exported_lens_names(module_name)
    assert exported == declared  # baseline agreement (proven by the sibling test)
    # An extra undeclared export and a missing export must both break equality.
    assert (exported | {"phantom-lens"}) != declared
    assert exported != (declared | {"phantom-lens"})


def _registered_production_lens_names():
    guardian_lens.load_production_lenses()
    return {lens.name for lens in guardian_lens.REGISTRY}


def _vitals_owning_lens_names():
    guardian_lens.load_production_lenses()
    return {
        lens.name for lens in guardian_lens.REGISTRY
        if callable(getattr(lens, "vitals", None))
    }


def test_vital_lens_sources_match_production_lenses():
    """VITAL_LENS_SOURCES ↔ registered production lenses (§11 drift guard, both directions).

    Every declared owner must resolve to a real registered lens name; every production lens
    that publishes vitals must be declared as an owner — a rename or orphan mapping fails."""
    registered = _registered_production_lens_names()
    assert registered, "no production lenses registered — guard is vacuous"
    vitals_owners = _vitals_owning_lens_names()
    covered_owners = set()
    for lens_names in guardian_vitals.VITAL_LENS_SOURCES.values():
        hits = [name for name in lens_names if name in registered]
        assert hits, (
            "VITAL_LENS_SOURCES declares owner(s) %s but none resolve to a registered "
            "production lens (registered: %s)"
            % (lens_names, sorted(registered)))
        covered_owners.update(hits)
    missing_owners = vitals_owners - covered_owners
    assert not missing_owners, (
        "production lens(es) with vitals() are not declared in VITAL_LENS_SOURCES: %s"
        % sorted(missing_owners))


def test_every_production_lens_declares_explicit_first_baseline_precision():
    """FIRST_BASELINE_PRECISIONS ↔ production lens declarations (§11 drift guard)."""
    guardian_lens.load_production_lenses(force=True)
    for lens in guardian_lens.REGISTRY:
        name = getattr(lens, "name", None)
        if isinstance(lens, guardian_lens._UnavailableLens):
            continue
        if isinstance(name, str) and name.startswith("module:"):
            continue
        assert "first_baseline_precision" in dir(lens), (
            "production lens %r must declare first_baseline_precision explicitly"
            % name)
        val = getattr(lens, "first_baseline_precision", None)
        assert val in guardian_lens.FIRST_BASELINE_PRECISIONS, (
            "production lens %r first_baseline_precision=%r not in %s"
            % (name, val, guardian_lens.FIRST_BASELINE_PRECISIONS))


def test_vital_lens_sources_guard_is_not_vacuous():
    """The VITAL_LENS_SOURCES guard must fail closed when a side drifts."""
    registered = _registered_production_lens_names()
    vitals_owners = _vitals_owning_lens_names()
    covered = set()
    for names in guardian_vitals.VITAL_LENS_SOURCES.values():
        covered.update(n for n in names if n in registered)
    assert vitals_owners <= covered
    assert covered == vitals_owners
    assert (vitals_owners | {"phantom-lens"}) != covered
