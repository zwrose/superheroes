"""By-construction proof that disclosure and record-path vocabularies have one home."""
import os

import pytest
import receipt_disclosures
import record_paths
import round_certification
import round_driver
import round_records
import session_contract

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DISCLOSURE_LINE_PREFIX = (
    "unprobed native seat(s) %s: seats with no runner execution record — run in-session on "
    "the host model, fallen open to it, or landed by hand — are declared live, never "
    "probed; their engagement rests on the seat's own record"
)


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


@pytest.mark.parametrize(
    "transport,named",
    [
        (session_contract.SEAT_TRANSPORT_NATIVE, True),
        (session_contract.SEAT_TRANSPORT_HAND_LANDED, True),
        (None, True),
        (session_contract.SEAT_TRANSPORT_RUNNER, False),
        (session_contract.SEAT_TRANSPORT_ORCHESTRATOR, False),
    ],
    ids=["native-subagent", "hand-landed", "missing", "runner", "orchestrator"],
)
def test_native_in_session_disclosure_transport_param(transport, named):
    event = {"outcome": "recorded", "seat": "code-reviewer"}
    if transport is not None:
        event[session_contract.SEAT_TRANSPORT_KEY] = transport
    journal = [event]
    seats = receipt_disclosures._native_in_session_seats({}, journal)
    if named:
        assert seats == ["code-reviewer"]
        degraded, _ = receipt_disclosures.build_degraded_prose(
            {}, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
        )
        assert _DISCLOSURE_LINE_PREFIX % "code-reviewer" in degraded
    else:
        assert seats == []
        degraded, _ = receipt_disclosures.build_degraded_prose(
            {}, receipt_disclosures.RECEIPT_FORM_CERTIFIED, journal=journal,
        )
        assert not any(line.startswith("unprobed native seat(s)") for line in degraded)


def test_native_in_session_disclosure_named_when_runner_then_native():
    journal = [
        {
            "outcome": "recorded",
            "seat": "code-reviewer",
            session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_RUNNER,
        },
        {
            "outcome": "recorded",
            "seat": "code-reviewer",
            session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_NATIVE,
        },
    ]
    assert receipt_disclosures._native_in_session_seats({}, journal) == ["code-reviewer"]


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
