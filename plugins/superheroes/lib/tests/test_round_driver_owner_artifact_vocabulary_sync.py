"""Drift guard: owner-artifact refusal + policyApplied source + gate-artifact vocabulary ↔ round_driver.py.

Copy-holder:
  - plugins/superheroes/skills/review-code/reference/round-driver.md
Authoritative home (derived at runtime — never retyped as literals in this test):
  - round_driver.OWNER_ARTIFACT_*_REFUSAL module constants
  - round_driver.POLICY_APPLIED_SOURCE_* module constants
  - round_driver.OWNER_PROVENANCE_FIELD_SHAPES
  - round_driver.JUDGMENT_DISPOSITIONS
  - round_driver.ROUND_ENTRY_KEY_FORMS, VERIFIER_FOLD_DISCLOSURE_CHANNELS,
    RESUMABLE_DISCLOSURE_CHANNELS for ``verifyPasses`` (membership only)

``verifyPasses`` is a verifier-fold disclosure channel: the verifier fold writes it
(``VERIFIER_FOLD_DISCLOSURE_CHANNELS``), resume restores it like every other disclosure
channel (``RESUMABLE_DISCLOSURE_CHANNELS``), and receipt-shape gating lives in
``ROUND_ENTRY_KEY_FORMS``. All three must hold for the doc's ``verifyPasses`` citation
to mean what it says.

Known residual: round-driver.md names ``receipt-interim/1`` in the checkpoint prose but not
``receipt-attested/1``, though ``ROUND_ENTRY_KEY_FORMS["verifyPasses"]["non_certified_schemas"]``
carries both — adding that prose is out of scope here.
"""
import json
import os
import re

import pytest

import round_driver as RD
from bite_support import patched_module
from clause_guard import check_clause, without_clause_in_section

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
_REF = os.path.join(_PLUGIN_ROOT, "skills", "review-code", "reference", "round-driver.md")
_REF_REL = "skills/review-code/reference/round-driver.md"
_CHECKPOINT_SECTION = "## checkpoint"
_CHECKPOINT_VERIFY_PASSES_CLAUSE = (
    "`build_receipt` (journal-derived `rounds`, `findings`, `decisions`, `seatMap`, `scriptRan`, "
    "`degraded`, `skippedBlockers` — including **per-pass verdict totals** on each round as "
    "`rounds[].verifyPasses`), then strips terminal-only keys (`certification`, `certificationShape`, "
    "`schemaVersion`, `verdict`), sets `schema` to `receipt-interim/1`, and adds a `stop` block "
    "(`reason`, `writtenAt`)."
)
_STALE_MIRROR_MSG = (
    "verifyPasses citation names a channel the code no longer registers, "
    "so the mirror is stale and the reference dangles"
)
_ROUND_ENTRY_KEY_FORMS_ENTRY = (
    '    "verifyPasses": {\n'
    '        "min_certified_version": 3,\n'
    '        "non_certified_schemas": (RECEIPT_ATTESTED_SCHEMA, RECEIPT_INTERIM_SCHEMA),\n'
    '    },\n'
)

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


def _rounds_bullet_line(text):
    rounds_lines = [
        line for line in text.splitlines() if line.startswith("- `rounds` — per-round")
    ]
    if len(rounds_lines) != 1:
        raise AssertionError(
            "expected exactly one per-round `rounds` enumeration bullet, found %d"
            % len(rounds_lines)
        )
    return rounds_lines[0]


def _assert_verify_passes_checkpoint_clause(text):
    # axis: ## checkpoint prose cites rounds[].verifyPasses at its anchored count.
    check_clause(text, _REF_REL, _CHECKPOINT_SECTION, _CHECKPOINT_VERIFY_PASSES_CLAUSE, 1)


def _assert_verify_passes_on_rounds_bullet(text):
    # axis: per-round `rounds` enumeration bullet names verifyPasses once.
    bullet = _rounds_bullet_line(text)
    count = bullet.count("verifyPasses")
    if count != 1:
        raise AssertionError(
            "round-driver.md per-round `rounds` bullet: the doc's %s" % _STALE_MIRROR_MSG
        )


def _assert_verify_passes_in_round_entry_key_forms(rd=None):
    # axis: verifyPasses is a receipt-shape-gated round-entry key in ROUND_ENTRY_KEY_FORMS.
    mod = rd if rd is not None else RD
    if "verifyPasses" not in mod.ROUND_ENTRY_KEY_FORMS:
        raise AssertionError(
            "round_driver.ROUND_ENTRY_KEY_FORMS: the doc's %s" % _STALE_MIRROR_MSG
        )


def _assert_verify_passes_in_verifier_fold_channels(rd=None):
    # axis: verifyPasses is written by the verifier fold disclosure channel registry.
    mod = rd if rd is not None else RD
    if "verifyPasses" not in mod.VERIFIER_FOLD_DISCLOSURE_CHANNELS:
        raise AssertionError(
            "round_driver.VERIFIER_FOLD_DISCLOSURE_CHANNELS: the doc's %s"
            % _STALE_MIRROR_MSG
        )


def _assert_verify_passes_in_resumable_channels(rd=None):
    # axis: verifyPasses is restorable across resume via RESUMABLE_DISCLOSURE_CHANNELS.
    mod = rd if rd is not None else RD
    if "verifyPasses" not in mod.RESUMABLE_DISCLOSURE_CHANNELS:
        raise AssertionError(
            "round_driver.RESUMABLE_DISCLOSURE_CHANNELS: the doc's %s" % _STALE_MIRROR_MSG
        )


def _without_verify_passes_on_rounds_bullet(text):
    bullet = _rounds_bullet_line(text)
    if "verifyPasses" not in bullet:
        raise AssertionError(
            "mutation setup: verifyPasses missing from per-round `rounds` bullet"
        )
    new_bullet = bullet.replace("`verifyPasses`, ", "", 1)
    if new_bullet.count("verifyPasses") != 0:
        raise AssertionError(
            "mutation setup: verifyPasses still present after removal from per-round bullet"
        )
    return text.replace(bullet, new_bullet, 1)


def test_verify_passes_checkpoint_prose_pinned():
    """#1219 FC-1: checkpoint interim-receipt prose cites rounds[].verifyPasses."""
    text = _read(_REF)
    _assert_verify_passes_checkpoint_clause(text)


def test_verify_passes_rounds_bullet_pinned():
    """#1219 FC-2: per-round `rounds` enumeration bullet names verifyPasses once."""
    text = _read(_REF)
    _assert_verify_passes_on_rounds_bullet(text)


def test_verify_passes_round_entry_key_forms_membership_pinned():
    """#1219 FC-3: verifyPasses is a key of ROUND_ENTRY_KEY_FORMS (membership only)."""
    _assert_verify_passes_in_round_entry_key_forms()


def test_verify_passes_verifier_fold_channel_membership_pinned():
    """#1219 FC-4: verifyPasses is a member of VERIFIER_FOLD_DISCLOSURE_CHANNELS."""
    _assert_verify_passes_in_verifier_fold_channels()


def test_verify_passes_resumable_channel_membership_pinned():
    """#1219 FC-5: verifyPasses is a member of RESUMABLE_DISCLOSURE_CHANNELS."""
    _assert_verify_passes_in_resumable_channels()


def test_negative_verify_passes_checkpoint_clause_missing():
    """#1219 FC-1 negative: deleting the anchored checkpoint sentence raises."""
    text = _read(_REF)
    mutated = without_clause_in_section(
        text, _REF_REL, _CHECKPOINT_SECTION, _CHECKPOINT_VERIFY_PASSES_CLAUSE,
    )
    with pytest.raises(AssertionError, match=_CHECKPOINT_SECTION):
        _assert_verify_passes_checkpoint_clause(mutated)


def test_negative_verify_passes_checkpoint_clause_missing_while_bullet_stands():
    """#1219 FC-1 isolation: checkpoint deletion still raises when the rounds bullet stands."""
    text = _read(_REF)
    mutated = without_clause_in_section(
        text, _REF_REL, _CHECKPOINT_SECTION, _CHECKPOINT_VERIFY_PASSES_CLAUSE,
    )
    _assert_verify_passes_on_rounds_bullet(mutated)
    with pytest.raises(AssertionError, match=_CHECKPOINT_SECTION):
        _assert_verify_passes_checkpoint_clause(mutated)


def test_negative_verify_passes_missing_from_rounds_bullet():
    """#1219 FC-2 negative: removing verifyPasses from the per-round bullet raises."""
    text = _read(_REF)
    mutated = _without_verify_passes_on_rounds_bullet(text)
    _assert_verify_passes_checkpoint_clause(mutated)
    with pytest.raises(AssertionError, match=_STALE_MIRROR_MSG):
        _assert_verify_passes_on_rounds_bullet(mutated)


def test_negative_verify_passes_missing_from_round_entry_key_forms():
    """#1219 FC-3 negative: dropping verifyPasses from ROUND_ENTRY_KEY_FORMS raises."""
    patched = patched_module(RD, [(_ROUND_ENTRY_KEY_FORMS_ENTRY, "")])
    with pytest.raises(AssertionError, match=_STALE_MIRROR_MSG):
        _assert_verify_passes_in_round_entry_key_forms(patched)


def test_negative_verify_passes_missing_from_verifier_fold_channels():
    """#1219 FC-4 negative: dropping verifyPasses from VERIFIER_FOLD_DISCLOSURE_CHANNELS raises."""
    patched = patched_module(
        RD,
        [('VERIFIER_FOLD_DISCLOSURE_CHANNELS = ("verifyPasses",)',
          'VERIFIER_FOLD_DISCLOSURE_CHANNELS = ()')],
    )
    with pytest.raises(AssertionError, match=_STALE_MIRROR_MSG):
        _assert_verify_passes_in_verifier_fold_channels(patched)


def test_negative_verify_passes_missing_from_resumable_channels():
    """#1219 FC-5 negative: dropping verifyPasses from RESUMABLE_DISCLOSURE_CHANNELS raises."""
    patched = patched_module(RD, [('    "verifyPasses": _dict_list,', "")])
    with pytest.raises(AssertionError, match=_STALE_MIRROR_MSG):
        _assert_verify_passes_in_resumable_channels(patched)


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
