"""Drift guard: the `rule` ruling file's `_provenance` validator and the durable-record refusal table
↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home:
  - round_driver.ROUND_PHASE_*_REFUSAL
  - round_driver._owner_artifact_provenance_well_formed
"""
import os
import re

import round_driver as RD

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")

_REFUSAL_TABLE_MARKER = "**Refusal tokens when paths interleave.**"
_REFUSAL_TABLE_END = "**Owner-artifact refusal causes**"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _parse_refusal_table_reasons(text):
    """Reason tokens from the durable-record refusal table in round-driver.md."""
    start = text.index(_REFUSAL_TABLE_MARKER)
    end = text.index(_REFUSAL_TABLE_END, start)
    chunk = text[start:end]
    return frozenset(re.findall(r"\| `([^`]+)` \|", chunk))


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


def _well_formed_provenance_artifact(**provenance_overrides):
    artifact = {
        "rulings": [{"id": "finding-1", "ruling": "out-of-scope", "reason": "later"}],
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
