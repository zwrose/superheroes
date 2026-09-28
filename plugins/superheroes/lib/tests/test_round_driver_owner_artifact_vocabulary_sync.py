"""Drift guard: gate-artifact example + durable-record refusal table ↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home:
  - round_driver.JUDGMENT_DISPOSITIONS
  - round_driver.ROUND_PHASE_*_REFUSAL
  - round_driver._owner_artifact_provenance_well_formed
  - round_driver.OWNER_ARTIFACT_*_REFUSAL
  - round_driver.POLICY_APPLIED_SOURCE_*
"""
import json
import os
import re

import round_driver as RD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")

_REFUSAL_TABLE_MARKER = "**Refusal tokens when paths interleave.**"
_REFUSAL_TABLE_END = "**Owner-artifact refusal causes**"
_POLICY_APPLIED_SOURCE_NARRATIVE_START = (
    "resolution is journalled under one of two owner-gate sources"
)
_POLICY_APPLIED_SOURCE_NARRATIVE_END = "**Owner-gate `_provenance` required fields**"
_GATE_ARTIFACT_EXAMPLE_MARKER = (
    "Example `present-judgment` gate artifact (gate shape plus a filled-in `_provenance` block):"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_fenced_json_block(text, after_marker):
    """Return the parsed object from the first ```json block after *after_marker*."""
    idx = text.index(after_marker)
    chunk = text[idx:]
    match = re.search(r"```json\n(.*?)```", chunk, re.DOTALL)
    if not match:
        raise RuntimeError("no ```json block found after marker %r" % after_marker)
    return json.loads(match.group(1))


def _parse_gate_artifact_example_dispositions(text):
    """Disposition values from the worked ``present-judgment`` gate-artifact JSON example."""
    artifact = _parse_fenced_json_block(text, _GATE_ARTIFACT_EXAMPLE_MARKER)
    dispositions = artifact.get("dispositions")
    if not isinstance(dispositions, list):
        raise RuntimeError("gate-artifact example missing dispositions list")
    values = []
    for entry in dispositions:
        if not isinstance(entry, dict):
            raise RuntimeError("gate-artifact example dispositions entry is not an object")
        value = entry.get("disposition")
        if not isinstance(value, str):
            raise RuntimeError("gate-artifact example disposition value is not a string")
        values.append(value)
    return frozenset(values)


def _parse_refusal_table_reasons(text):
    """Reason tokens from the durable-record refusal table in round-driver.md."""
    start = text.index(_REFUSAL_TABLE_MARKER)
    end = text.index(_REFUSAL_TABLE_END, start)
    chunk = text[start:end]
    return frozenset(re.findall(r"\| `([^`]+)` \|", chunk))


def _owner_artifact_refusal_causes():
    """Every ``OWNER_ARTIFACT_*_REFUSAL`` string constant on ``round_driver``."""
    return frozenset(
        val for name, val in vars(RD).items()
        if name.startswith("OWNER_ARTIFACT_") and name.endswith("_REFUSAL")
        and isinstance(val, str)
    )


def _policy_applied_sources():
    """Every ``POLICY_APPLIED_SOURCE_*`` string constant on ``round_driver``."""
    return frozenset(
        val for name, val in vars(RD).items()
        if name.startswith("POLICY_APPLIED_SOURCE_") and isinstance(val, str)
    )


def _round_phase_refusal_causes():
    """Every ``ROUND_PHASE_*_REFUSAL`` string constant on ``round_driver``."""
    return frozenset(
        val for name, val in vars(RD).items()
        if name.startswith("ROUND_PHASE_") and name.endswith("_REFUSAL")
        and isinstance(val, str)
    )


def _round_phase_refusal_tokens_in_table(text):
    """Round-phase refusal tokens from the durable-record refusal table (excludes shared rows)."""
    table_tokens = set(_parse_refusal_table_reasons(text))
    return {token for token in table_tokens if token.startswith("round-phase-")}


def _policy_applied_source_narrative_chunk(text):
    """Owner-gate ``policyApplied.source`` assignment prose (operative copy, not later echoes)."""
    start = text.index(_POLICY_APPLIED_SOURCE_NARRATIVE_START)
    end = text.index(_POLICY_APPLIED_SOURCE_NARRATIVE_END, start)
    return text[start:end]


def _assert_driver_constants_present(chunk, label, tokens):
    missing = sorted(token for token in tokens if token not in chunk)
    assert not missing, "%s missing from %s: %s" % (label, _REF, missing)


def test_gate_artifact_example_dispositions_match_judgment_vocabulary():
    """Worked gate-artifact JSON example dispositions ↔ JUDGMENT_DISPOSITIONS."""
    text = _read(_REF)
    documented = set(_parse_gate_artifact_example_dispositions(text))
    coded = set(RD.JUDGMENT_DISPOSITIONS)

    invalid = documented - coded
    assert not invalid, (
        "round-driver.md gate-artifact example uses judgment dispositions the driver does not "
        "recognize: %s" % sorted(invalid))


def test_gate_artifact_example_provenance_is_not_submittable():
    """Worked gate-artifact JSON example must not pass _owner_artifact_provenance_well_formed."""
    text = _read(_REF)
    artifact = _parse_fenced_json_block(text, _GATE_ARTIFACT_EXAMPLE_MARKER)
    assert not RD._owner_artifact_provenance_well_formed(artifact)


def _well_formed_provenance_artifact(**provenance_overrides):
    artifact = {
        "dispositions": [{"id": "finding-1", "disposition": "fix-as-suggested"}],
        "_provenance": {
            "ruledBy": "owner",
            "ruledAt": "2026-08-26T00:00:00Z",
            "records": ["gate-ruling.json"],
        },
    }
    if provenance_overrides:
        artifact["_provenance"] = dict(artifact["_provenance"], **provenance_overrides)
    return artifact


def test_owner_artifact_provenance_well_formed_accepts_complete_block():
    assert RD._owner_artifact_provenance_well_formed(_well_formed_provenance_artifact())


def test_owner_artifact_provenance_well_formed_rejects_blank_ruled_by():
    artifact = _well_formed_provenance_artifact(ruledBy="")
    assert not RD._owner_artifact_provenance_well_formed(artifact)


def test_owner_artifact_provenance_well_formed_rejects_blank_ruled_at():
    artifact = _well_formed_provenance_artifact(ruledAt="   ")
    assert not RD._owner_artifact_provenance_well_formed(artifact)


def test_owner_artifact_provenance_well_formed_rejects_empty_records():
    artifact = _well_formed_provenance_artifact(records=[])
    assert not RD._owner_artifact_provenance_well_formed(artifact)


def test_owner_artifact_provenance_well_formed_rejects_blank_record_entry():
    artifact = _well_formed_provenance_artifact(records=["gate-ruling.json", ""])
    assert not RD._owner_artifact_provenance_well_formed(artifact)


def test_owner_artifact_refusal_tokens_present_in_round_driver_doc():
    """Refusal table ↔ OWNER_ARTIFACT_*_REFUSAL constants (identifier presence, not fenced lists)."""
    text = _read(_REF)
    table_reasons = _parse_refusal_table_reasons(text)
    _assert_driver_constants_present(
        table_reasons,
        "OWNER_ARTIFACT_*_REFUSAL",
        _owner_artifact_refusal_causes(),
    )


def test_policy_applied_source_tokens_present_in_round_driver_doc():
    """Owner-gate journal prose ↔ POLICY_APPLIED_SOURCE_* constants (identifier presence)."""
    text = _read(_REF)
    narrative = _policy_applied_source_narrative_chunk(text)
    _assert_driver_constants_present(
        narrative,
        "POLICY_APPLIED_SOURCE_*",
        _policy_applied_sources(),
    )


def test_round_phase_refusal_causes_match_docs():
    """round-driver.md durable-record refusal table ↔ ROUND_PHASE_*_REFUSAL (both directions)."""
    text = _read(_REF)
    documented_round_phase = _round_phase_refusal_tokens_in_table(text)
    coded = set(_round_phase_refusal_causes())

    only_code = coded - documented_round_phase
    only_docs = documented_round_phase - coded
    assert not only_code, (
        "ROUND_PHASE_*_REFUSAL constants missing from round-driver.md refusal table: %s"
        % sorted(only_code))
    assert not only_docs, (
        "round-driver.md refusal table lists round-phase tokens the driver cannot emit: %s"
        % sorted(only_docs))
