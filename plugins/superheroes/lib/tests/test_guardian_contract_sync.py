"""§11 drift guard: Guardian SKILL + lens-contract prose stay in sync with lib homes.

Copy-holders (name every copy per CONVENTIONS §11):
  - plugins/superheroes/skills/guardian/SKILL.md — storage layout paths, ledger outcomes
  - plugins/superheroes/skills/guardian/reference/lens-contract.md — lens contract parts
  - CONVENTIONS.md — guardian artifact subtree, ledger record fields, vitals set
Authoritative homes:
  - guardian_store.LAYOUT
  - guardian_lens.LENS_CONTRACT_PARTS
  - guardian_lens.FACTS
  - guardian_ledger.LEDGER_RECORD_FIELDS
  - guardian_ledger.OUTCOMES_FOR / OUTCOMES_AGAINST
  - guardian_vitals.VITALS
  - guardian_vitals.DRIFT_THRESHOLDS
"""
import os

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


def test_skill_references_guardian_layout_paths():
    """Storage layout ↔ SKILL prose (fail-closed)."""
    layout = guardian_store.LAYOUT
    assert layout, "guardian_store.LAYOUT is empty — no authoritative home"
    skill = _read(_SKILL)
    checked = set()
    for key in layout:
        filename = layout[key]
        assert filename, "LAYOUT[%r] is empty" % key
        guardian_path = "guardian/" + filename
        assert guardian_path in skill or filename in skill, (
            "SKILL.md must reference %r (guardian/%s)" % (guardian_path, filename))
        checked.add(key)
    assert checked == set(layout.keys()), (
        "layout path loop must cover every LAYOUT key (checked %s, layout has %s)"
        % (sorted(checked), sorted(layout.keys())))


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
    """CONVENTIONS §2.1 prose ↔ vitals set + ledger record fields (fail-closed)."""
    text = _read(_CONVENTIONS)
    for vital in guardian_vitals.VITALS:
        assert vital in text, "CONVENTIONS.md missing vital %r" % vital
    for field in guardian_ledger.LEDGER_RECORD_FIELDS:
        assert field in text, "CONVENTIONS.md missing ledger record field %r" % field
    for outcome in guardian_ledger.OUTCOMES_FOR + guardian_ledger.OUTCOMES_AGAINST:
        assert outcome in text, "CONVENTIONS.md missing ledger outcome %r" % outcome


def test_skill_mentions_ledger_outcomes():
    """SKILL prose ↔ ledger outcome maps (fail-closed)."""
    skill = _read(_SKILL)
    for outcome in guardian_ledger.OUTCOMES_FOR + guardian_ledger.OUTCOMES_AGAINST:
        assert outcome in skill, "SKILL.md missing ledger outcome %r" % outcome
