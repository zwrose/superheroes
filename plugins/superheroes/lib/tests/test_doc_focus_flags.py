"""Tests for `doc_focus_flags` — review-spec's deterministic, additive-only focus flags (#515).

Pins: the two triggers (migration, external-service), the both/neither cases, and that the
same input always yields the same output (determinism). The helper is additive-only — it
computes emphasis, it never narrows the script-owned dispatch — so these tests only assert the
flag/note payload it emits.
"""
import json
import os

import doc_focus_flags as dff

_HERE = os.path.dirname(os.path.abspath(__file__))


def test_migration_only():
    flags, note = dff.compute_flags(
        "When the operator runs the backfill, the system shall migrate old records.")
    assert flags == ["migration"]
    assert "rollback" in note and "data-safety" in note


def test_external_service_only():
    flags, note = dff.compute_flags(
        "The system shall call the payment webhook and reconcile via the upstream service.")
    assert flags == ["external-service"]
    assert "dependency-failure" in note and "degraded-mode" in note


def test_both_triggers_join_notes():
    flags, note = dff.compute_flags(
        "This work item performs a schema change and integrates a third-party API.")
    assert flags == ["migration", "external-service"]
    # both notes present, joined into one focus string, migration first (fixed order)
    assert "rollback" in note and "dependency-failure" in note
    assert note.index("rollback") < note.index("dependency-failure")


def test_neither_trigger_is_empty():
    flags, note = dff.compute_flags(
        "When the user taps Save, the system shall persist the note and show a confirmation.")
    assert flags == []
    assert note == ""


def test_word_boundary_avoids_false_trigger():
    # 'apiary' must not match the 'API' keyword (word-boundary-ish matching)
    flags, _ = dff.compute_flags("The system shall display the beekeeper's apiary layout.")
    assert flags == []


def test_case_insensitive():
    flags, _ = dff.compute_flags("A DATA MIGRATION runs on first deploy.")
    assert flags == ["migration"]


def test_determinism_same_input_same_output():
    text = "Migrate the ledger and call the external service webhook."
    first = dff.compute_flags(text)
    second = dff.compute_flags(text)
    assert first == second
    assert first[0] == ["migration", "external-service"]


def test_cli_emits_flags_and_focus_note(tmp_path, capsys):
    spec = tmp_path / "spec.md"
    spec.write_text("The system shall backfill data via a webhook.", encoding="utf-8")
    rc = dff.main(["--spec", str(spec)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["flags"] == ["migration", "external-service"]
    assert out["focusNote"]


def test_cli_missing_file_is_empty(tmp_path, capsys):
    rc = dff.main(["--spec", str(tmp_path / "nope.md")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out == {"flags": [], "focusNote": ""}
