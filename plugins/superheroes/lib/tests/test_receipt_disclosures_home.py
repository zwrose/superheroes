"""By-construction proof that disclosure and record-path vocabularies have one home."""
import os

import pytest
import receipt_disclosures
import record_paths
import round_certification
import round_driver
import round_records
import session_contract
from test_round_records import _missing_env

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
    seats = receipt_disclosures._native_in_session_seats(journal)
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
    assert receipt_disclosures._native_in_session_seats(journal) == ["code-reviewer"]


def _recorded_event(seat, transport, *, phase="dispatch-panel", round_num=1, attempt=0,
                    occurrence=0, cmd="record-result"):
    event = {
        "cmd": cmd,
        "outcome": "recorded",
        "phase": phase,
        "round": round_num,
        "attempt": attempt,
        "occurrence": occurrence,
        "seat": seat,
    }
    if transport is not None:
        event[session_contract.SEAT_TRANSPORT_KEY] = transport
    return event


def test_native_in_session_disclosure_not_named_when_runner_replaces_native():
    journal = [
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE),
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_RUNNER),
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == []


def test_native_in_session_disclosure_named_when_runner_only_on_other_round():
    journal = [
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE, round_num=1),
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_RUNNER, round_num=2),
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == ["code-reviewer"]


def test_native_in_session_disclosure_record_missing_not_named():
    journal = [
        {
            "cmd": "record-missing",
            "outcome": "recorded",
            "seat": "code-reviewer",
            "phase": "dispatch-panel",
            "round": 1,
            "attempt": 0,
            "occurrence": 0,
        },
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == []


def test_native_in_session_disclosure_reappended_missing_cas_token_not_named():
    journal = [
        {
            "cmd": "advance",
            "outcome": "recorded",
            "reappended": True,
            "seat": "code-reviewer",
            "casToken": "seat-missing/1",
            "transport": "native-subagent",
        },
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == []


def test_native_in_session_disclosure_journal_stored_revision_missing_not_named():
    envelope = _missing_env(seat="code-reviewer")
    fields = round_records.recorded_row_fields(
        envelope, None, round_records.stored_cited_head_source(envelope))
    fields.update(round_driver._journal_transport_fields(envelope))
    assert fields["casToken"] == "seat-missing/1"
    event = {
        "cmd": "advance",
        "outcome": "recorded",
        "seat": "code-reviewer",
        **fields,
    }
    assert receipt_disclosures._native_in_session_seats([event]) == []


def test_native_in_session_disclosure_missing_then_recovered_named():
    journal = [
        {
            "cmd": "advance",
            "outcome": "recorded",
            "seat": "code-reviewer",
            "casToken": "seat-missing/1",
            "transport": "native-subagent",
            "phase": "dispatch-panel",
            "round": 1,
            "attempt": 0,
            "occurrence": 0,
        },
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE),
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == ["code-reviewer"]


def test_native_in_session_disclosure_record_missing_last_wins():
    journal = [
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE),
        _recorded_event("code-reviewer", None, cmd="record-missing"),
    ]
    assert receipt_disclosures._native_in_session_seats(journal) == []
    recovered = [
        _recorded_event("code-reviewer", None, cmd="record-missing"),
        _recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE),
    ]
    assert receipt_disclosures._native_in_session_seats(recovered) == ["code-reviewer"]


def test_latest_recorded_events_resolves_seatless_record_identity():
    journal = [
        {
            "cmd": "record-result",
            "outcome": "recorded",
            "phase": "dispatch-panel",
            "round": 1,
            "attempt": 0,
            session_contract.SEAT_TRANSPORT_KEY: session_contract.SEAT_TRANSPORT_NATIVE,
            "recordIdentity": {
                "phase": "dispatch-panel",
                "seat": "code-reviewer",
                "occurrence": 0,
                "attempt": 0,
            },
        },
    ]
    pairs = receipt_disclosures.latest_recorded_events(journal)
    assert len(pairs) == 1
    identity, _event = pairs[0]
    assert identity["seat"] == "code-reviewer"
    assert receipt_disclosures._native_in_session_seats(journal) == ["code-reviewer"]


def test_native_in_session_and_collect_seats_share_latest_recorded_events(monkeypatch):
    calls = []
    real_latest = receipt_disclosures.latest_recorded_events

    def recording_stub(journal):
        calls.append(journal)
        return real_latest(journal)

    monkeypatch.setattr(receipt_disclosures, "latest_recorded_events", recording_stub)
    journal = [_recorded_event("code-reviewer", session_contract.SEAT_TRANSPORT_NATIVE)]
    receipt_disclosures._native_in_session_seats(journal)
    round_certification._collect_seats({"state": {}, "journal": journal})
    assert len(calls) == 2
    assert calls[0] is journal
    assert calls[1] is journal


def test_session_contract_transport_literals_pinned():
    assert session_contract.SEAT_TRANSPORT_KEY == "transport"
    assert session_contract.SEAT_TRANSPORTS == (
        "runner",
        "native-subagent",
        "hand-landed",
        "orchestrator",
    )
    assert session_contract.SEAT_TRANSPORTS_DISCLOSED == ("native-subagent", "hand-landed")


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
