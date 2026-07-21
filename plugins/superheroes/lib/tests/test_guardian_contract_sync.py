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


def _ledger_record_schema():
    return guardian_ledger.LEDGER_RECORD_FIELDS + (guardian_ledger.ADJUDICATED_IN,)


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
    assert guardian_ledger.ADJUDICATED_IN in _ledger_record_schema()


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
