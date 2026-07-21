"""§11 drift guard: Guardian SKILL + lens-contract prose stay in sync with lib homes.

Copy-holders (name every copy per CONVENTIONS §11):
  - plugins/superheroes/skills/guardian/SKILL.md — storage layout paths
  - plugins/superheroes/skills/guardian/reference/lens-contract.md — lens contract parts
Authoritative homes:
  - guardian_store.LAYOUT
  - guardian_lens.LENS_CONTRACT_PARTS
"""
import os

import guardian_lens
import guardian_store

_PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_SKILL = os.path.join(_PLUGIN, "skills", "guardian", "SKILL.md")
_LENS_CONTRACT = os.path.join(_PLUGIN, "skills", "guardian", "reference", "lens-contract.md")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def test_skill_references_guardian_layout_paths():
    """Storage layout ↔ SKILL prose (fail-closed)."""
    layout = guardian_store.LAYOUT
    assert layout, "guardian_store.LAYOUT is empty — no authoritative home"
    skill = _read(_SKILL)
    for key in ("report", "snapshot", "ledger"):
        assert key in layout, "LAYOUT missing key %r" % key
        filename = layout[key]
        assert filename, "LAYOUT[%r] is empty" % key
        guardian_path = "guardian/" + filename
        assert guardian_path in skill or filename in skill, (
            "SKILL.md must reference %r (guardian/%s)" % (guardian_path, filename))


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
