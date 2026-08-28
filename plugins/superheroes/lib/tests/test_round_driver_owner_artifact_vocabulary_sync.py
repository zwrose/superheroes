"""Drift guard: owner-artifact refusal + policyApplied source + gate-artifact vocabulary ↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home (derived at runtime — never retyped as literals in this test):
  - round_driver.OWNER_ARTIFACT_*_REFUSAL module constants
  - round_driver.POLICY_APPLIED_SOURCE_* module constants
  - round_driver.OWNER_PROVENANCE_FIELD_SHAPES
  - round_driver.JUDGMENT_DISPOSITIONS
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
_OWNER_ARTIFACT_MARKER = "**Owner-artifact refusal causes**"
_SOURCE_MARKER = "**Policy-applied sources**"
_PROVENANCE_MARKER = "**Owner-gate `_provenance` required fields**"
_GATE_ARTIFACT_EXAMPLE_MARKER = (
    "Example `present-judgment` gate artifact (gate shape plus a filled-in `_provenance` block):"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_fenced_text_block(text, after_marker):
    """Return stripped non-empty lines from the first ```text block after *after_marker*."""
    idx = text.index(after_marker)
    chunk = text[idx:]
    match = re.search(r"```text\n(.*?)```", chunk, re.DOTALL)
    if not match:
        raise RuntimeError("no ```text block found after marker %r" % after_marker)
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


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


def _parse_provenance_field_shapes(text):
    """``field — shape`` pairs from the owner-gate ``_provenance`` fenced block."""
    marker_count = text.count(_PROVENANCE_MARKER)
    if marker_count != 1:
        raise RuntimeError(
            "expected exactly one owner-gate _provenance marker in round-driver.md, "
            "found %d" % marker_count
        )
    lines = _parse_fenced_text_block(text, _PROVENANCE_MARKER)
    pairs = {}
    for line in lines:
        field, shape = line.split(" — ", 1)
        field = field.strip()
        if field in pairs:
            raise RuntimeError(
                "duplicate provenance field %r in owner-gate _provenance block" % field
            )
        pairs[field] = shape.strip()
    return pairs


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


def test_owner_artifact_refusal_causes_match_docs():
    """round-driver.md owner-artifact refusal list ↔ OWNER_ARTIFACT_*_REFUSAL (both directions)."""
    text = _read(_REF)
    documented = set(_parse_fenced_text_block(text, _OWNER_ARTIFACT_MARKER))
    coded = set(_owner_artifact_refusal_causes())

    only_docs = documented - coded
    only_code = coded - documented
    assert not only_docs, (
        "round-driver.md lists owner-artifact refusals the driver cannot emit: %s"
        % sorted(only_docs))
    assert not only_code, (
        "driver emits owner-artifact refusals missing from round-driver.md: %s"
        % sorted(only_code))


def test_policy_applied_sources_match_docs():
    """round-driver.md policyApplied.source list ↔ POLICY_APPLIED_SOURCE_* (both directions)."""
    text = _read(_REF)
    documented = set(_parse_fenced_text_block(text, _SOURCE_MARKER))
    coded = set(_policy_applied_sources())

    only_docs = documented - coded
    only_code = coded - documented
    assert not only_docs, (
        "round-driver.md lists policyApplied sources the driver cannot emit: %s"
        % sorted(only_docs))
    assert not only_code, (
        "driver emits policyApplied sources missing from round-driver.md: %s"
        % sorted(only_code))


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


def test_owner_provenance_field_shapes_match_docs():
    """round-driver.md ``_provenance`` field shapes ↔ OWNER_PROVENANCE_FIELD_SHAPES (both directions)."""
    text = _read(_REF)
    documented = _parse_provenance_field_shapes(text)
    coded = dict(RD.OWNER_PROVENANCE_FIELD_SHAPES)

    only_docs = set(documented) - set(coded)
    only_code = set(coded) - set(documented)
    assert not only_docs, (
        "round-driver.md lists owner-gate _provenance fields the driver does not require: %s"
        % sorted(only_docs))
    assert not only_code, (
        "driver requires owner-gate _provenance fields missing from round-driver.md: %s"
        % sorted(only_code))

    shape_mismatches = {
        field: (documented[field], coded[field])
        for field in coded
        if documented.get(field) != coded[field]
    }
    assert not shape_mismatches, (
        "owner-gate _provenance field shape mismatch between docs and code: %s"
        % shape_mismatches)


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


def test_provenance_parser_raises_on_duplicate_field():
    """BP-R6 (#1194 FU2): a duplicated field line in the fenced block raises, never overwrites."""
    synthetic = (
        "prose before\n"
        + _PROVENANCE_MARKER
        + "\n\n```text\nruledBy — non-empty string\nruledBy — some other shape\n```\n"
    )
    try:
        _parse_provenance_field_shapes(synthetic)
    except RuntimeError as exc:
        assert "duplicate provenance field 'ruledBy'" in str(exc)
    else:
        raise AssertionError("duplicate provenance field did not raise — it was overwritten")


def test_rounds_enumeration_drift_pinned_to_disclosure_channel_registry():
    """#1202 FU5: round-driver.md's per-round `rounds` bullet names every registered disclosure
    channel. The registry is the code home (`RESUMABLE_DISCLOSURE_CHANNELS`); the doc line is the
    hand-maintained mirror — this pin turns a silently-stale mirror into a red test."""
    text = _read(_REF)
    rounds_lines = [line for line in text.splitlines()
                    if line.startswith("- `rounds` — per-round")]
    assert len(rounds_lines) == 1, "expected exactly one per-round `rounds` enumeration bullet"
    documented = set(re.findall(r"`([^`]+)`", rounds_lines[0]))
    registry = set(RD.RESUMABLE_DISCLOSURE_CHANNELS)
    missing = sorted(registry - documented)
    assert not missing, (
        "disclosure channels missing from round-driver.md's `rounds` enumeration: %s" % missing)
