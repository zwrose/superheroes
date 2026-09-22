"""By-construction proof that disclosure and record-path vocabularies have one home."""
import os

import receipt_disclosures
import record_paths
import round_certification
import round_driver
import round_records
import session_contract

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_receipt_disclosures_exports_match_driver_and_writer():
    for name in receipt_disclosures.__all__:
        assert getattr(round_driver, name) is getattr(receipt_disclosures, name), name
        if hasattr(round_certification, name):
            assert getattr(round_certification, name) is getattr(receipt_disclosures, name), name


def test_record_paths_exports_match_records_and_writer():
    for name in record_paths.__all__:
        assert getattr(round_records, name) is getattr(record_paths, name), name
        if hasattr(round_certification, name):
            assert getattr(round_certification, name) is getattr(record_paths, name), name


def test_native_in_session_disclosure_names_synthesis_with_stamped_vendor():
    journal = [
        {
            "outcome": "recorded",
            "phase": "dispatch-synthesis",
            "round": 1,
            "attempt": 0,
            "seat": "synthesis",
            "vendor": "claude",
        },
    ]
    assert receipt_disclosures._native_in_session_seats({}, journal) == ["synthesis"]
    degraded, _ = receipt_disclosures.build_degraded_prose(
        {}, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    assert any(line.startswith("unprobed native seat(s) synthesis") for line in degraded)


def test_native_in_session_disclosure_ignores_non_claude_stamped_vendor():
    journal = [
        {
            "outcome": "recorded",
            "phase": "dispatch-fixer",
            "round": 1,
            "attempt": 0,
            "seat": "fixer",
            "vendor": "cursor",
        },
    ]
    assert receipt_disclosures._native_in_session_seats({}, journal) == []
    degraded, _ = receipt_disclosures.build_degraded_prose(
        {}, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    assert not any(line.startswith("unprobed native seat(s)") for line in degraded)


def test_native_in_session_disclosure_line_when_claude_seat_has_no_evidence():
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": {"seats": {"code-reviewer": {"vendor": "claude"}}}},
        ],
    }
    journal = [{"outcome": "recorded", "seat": "code-reviewer"}]
    degraded, _ = receipt_disclosures.build_degraded_prose(
        state, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    expected = (
        "unprobed native seat(s) code-reviewer: native in-session seats run on the host model "
        "and are declared live, never probed — their engagement rests on the seat's own record"
    )
    assert expected in degraded


def test_native_in_session_disclosure_absent_when_claude_seat_has_evidence():
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": {"seats": {"code-reviewer": {"vendor": "claude"}}}},
        ],
    }
    journal = [
        {
            "outcome": "recorded",
            "seat": "code-reviewer",
            "executionEvidence": {"runnerNonce": "n"},
        }
    ]
    degraded, _ = receipt_disclosures.build_degraded_prose(
        state, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    assert not any(line.startswith("unprobed native seat(s)") for line in degraded)


def test_native_in_session_disclosure_uses_round_governing_map_not_latest():
    """Round 1 claude seat stays native even when round 2 map seats the same seat on codex."""
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": {"seats": {"code-reviewer": {"vendor": "claude"}}}},
            {"round": "2", "map": {"seats": {"code-reviewer": {"vendor": "codex"}}}},
        ],
    }
    journal = [{"outcome": "recorded", "seat": "code-reviewer", "round": 1}]
    degraded, _ = receipt_disclosures.build_degraded_prose(
        state, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    assert any(line.startswith("unprobed native seat(s) code-reviewer") for line in degraded)


def test_native_in_session_disclosure_inverse_map_change():
    """Round 2 claude without evidence is native; round 1 codex with evidence is not."""
    state = {
        "seatMapReceipts": [
            {"round": "1", "map": {"seats": {"code-reviewer": {"vendor": "codex"}}}},
            {"round": "2", "map": {"seats": {"code-reviewer": {"vendor": "claude"}}}},
        ],
    }
    journal = [
        {
            "outcome": "recorded",
            "seat": "code-reviewer",
            "round": 1,
            "executionEvidence": {"runnerNonce": "n"},
        },
        {"outcome": "recorded", "seat": "code-reviewer", "round": 2},
    ]
    degraded, _ = receipt_disclosures.build_degraded_prose(
        state, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
    )
    native_lines = [line for line in degraded if line.startswith("unprobed native seat(s)")]
    assert len(native_lines) == 1
    assert "code-reviewer" in native_lines[0]
    assert receipt_disclosures._native_in_session_seats(state, journal[:1]) == []


def test_no_pending_registration_disclosure_strings():
    for name in ("receipt_disclosures.py", "round_certification.py"):
        path = os.path.join(_LIB, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        assert "pending registration" not in text
        assert "pending-registration" not in text


def test_session_contract_exports_match_driver_records_and_writer():
    driver_names = {
        "STATE_FILE",
        "JOURNAL_FILE",
        "JOURNAL_FAULT_FILE",
        "HEAD_CONTENT_BLOBS_FILE",
        "FIX_FOLD_HEAD_KEY",
    }
    records_names = {"META_FILE", "SEAT_MISSING_SCHEMA", "canonical", "payload_sha256"}
    writer_names = set(session_contract.__all__)
    for name in session_contract.__all__:
        home = getattr(session_contract, name)
        if name in driver_names:
            assert getattr(round_driver, name) is home, name
        if name in records_names:
            assert getattr(round_records, name) is home, name
        if name in writer_names and hasattr(round_certification, name):
            assert getattr(round_certification, name) is home, name
    sample = {"id": "v0", "title": "probe", "file": "a.py", "line": 1}
    assert round_driver._finding_identity_key(sample) == session_contract.finding_identity_key(sample)
    assert round_certification._finding_identity_key is session_contract.finding_identity_key
