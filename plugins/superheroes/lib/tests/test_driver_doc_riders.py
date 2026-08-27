"""Drift guards for WO-E/1107 doc riders: driver-or-park valve + landing envelope fields.

Guards two owner-ruled riders:

1. The driver-or-park valve sentence mirrored at the driver's failure/stall guidance anchor
   (`round-driver.md` § Journal and receipt — where journal-fault and receipt-fault stops are
   documented). Home-first pin on the operative valve clause in `rubric/review-discipline.md`
   (CONVENTIONS §11.2 pattern 2 + §11.3 anti-tautology leg).

2. The full `seat-result/1` envelope field enumeration in `round-driver.md` § Landing shapes,
   pinned by construction: documented fields must match `round_records.SEAT_RESULT_FIELDS`, and an
   envelope built from that field list must pass `ingest_landing`.

Section extraction reuses `_file_section` and `_normalized` from `test_charter_boundary_sync`;
that reader is deliberately **fence-blind** (PR #727). The Landing shapes table lives inside
`## Emitted orders` with no fenced blocks in that slice today.

What the envelope ingest pin proves: a well-formed `seat-result/1` envelope whose fields match the
documented list is accepted at ingest with `NOT_EMITTED` anchors (no emission-time hash anchor).
What it does **not** prove: `seat-missing/1` ingest, anchor-hash matching, bare-payload host path,
or sweep/reconcile — those are covered elsewhere in `test_round_records.py`.
"""
import importlib.util
import os
import re

import pytest

from test_charter_boundary_sync import _file_section, _normalized

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))

_HOME = "rubric/review-discipline.md"
_ROUND_DRIVER = "skills/review-code/reference/round-driver.md"

_DRIVER_MANDATE_SECTION = (
    "## The driver mandate — the certified loop, its skips, and the flip"
)
_JOURNAL_SECTION = "## Journal and receipt"
_EMITTED_ORDERS_SECTION = "## Emitted orders"

_VALVE_HOME = (
    "the only valve is driver-or-park — never driver-or-improvise"
)
_VALVE_COPY = (
    "When the driver cannot continue — a refusal, a park, `journal-fault-unrecordable`, "
    "`receipt-fault`, or any other halt — park citing the blocker and never hand-drive the "
    "remainder; `rubric/review-discipline.md` is the home for the driver-or-park valve."
)

_SEAT_RESULT_TABLE_MARKER = "**`seat-result/1` envelope fields**"
_SEAT_MISSING_TABLE_MARKER = "The **`seat-missing/1`** shape is deliberately different"

SESSION = "s" * 32
PHASE = "dispatch-verifiers"
SEAT = "src/a/b.py:3"
OTHER_SEAT = "src/a/b.py:4"
ROSTER = [SEAT, OTHER_SEAT]


def _load_round_records():
    spec = importlib.util.spec_from_file_location(
        "round_records", os.path.join(_LIB, "round_records.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RR = _load_round_records()


def _read(rel):
    path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(path):
        raise AssertionError(f"surface file missing or unreadable: {rel}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section_text(rel, section):
    return _file_section(rel, section, _read)


def _documented_seat_result_fields():
    text = _read(_ROUND_DRIVER)
    start = text.find(_SEAT_RESULT_TABLE_MARKER)
    if start == -1:
        raise AssertionError(
            f"{_ROUND_DRIVER} missing seat-result envelope fields marker"
        )
    rest = text[start:]
    end = rest.find(_SEAT_MISSING_TABLE_MARKER)
    if end == -1:
        raise AssertionError(
            f"{_ROUND_DRIVER} missing seat-missing shape boundary after envelope table"
        )
    table_text = rest[:end]
    fields = re.findall(r"\| `(\w+)` \|", table_text)
    if not fields:
        raise AssertionError(
            f"{_ROUND_DRIVER} envelope fields table has no parseable rows"
        )
    return tuple(fields)


def _session(tmp_path, name="session"):
    sd = str(tmp_path / name)
    os.makedirs(sd, exist_ok=True)
    RR.atomic_write_json(
        os.path.join(sd, "meta.json"), {"sessionId": SESSION})
    return sd


def _build_envelope_from_fields(fields, payload=None):
    payload = payload if payload is not None else {"findings": ["f1"]}
    values = {
        "schema": RR.SEAT_RESULT_SCHEMA,
        "session": SESSION,
        "round": 1,
        "phase": PHASE,
        "seat": SEAT,
        "attempt": 1,
        "vendor": "claude",
        "model": "sonnet-5",
        "dispatchRef": "dispatch-abc",
        "orderSha256": RR.NOT_EMITTED,
        "manifestSha256": RR.NOT_EMITTED,
        "recordedAt": "2026-08-07T00:00:00",
        "payloadSha256": RR.payload_sha256(payload),
        "payload": payload,
    }
    return {field: values[field] for field in fields}


def test_valve_operative_clause_present_in_home():
    # axis: presence of the driver-or-park valve clause in review-discipline.md home section
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert _normalized(_VALVE_HOME) in home_section_text


def test_valve_sentence_present_in_journal_section_copy():
    # axis: presence of the valve guidance sentence in round-driver.md Journal section (copy)
    home_section_text = _section_text(_HOME, _DRIVER_MANDATE_SECTION)
    assert _normalized(_VALVE_HOME) in home_section_text
    journal_section_text = _section_text(_ROUND_DRIVER, _JOURNAL_SECTION)
    assert _normalized(_VALVE_COPY) in journal_section_text


def test_documented_seat_result_fields_match_authority():
    # axis: documented envelope field list matches round_records.SEAT_RESULT_FIELDS
    documented = _documented_seat_result_fields()
    assert documented == RR.SEAT_RESULT_FIELDS, (
        "documented fields %r != SEAT_RESULT_FIELDS %r"
        % (documented, RR.SEAT_RESULT_FIELDS)
    )


def test_seat_missing_doc_excludes_payload_sha256():
    # axis: seat-missing shape is documented without payloadSha256 (not conflated with seat-result)
    text = _read(_ROUND_DRIVER)
    start = text.find(_SEAT_MISSING_TABLE_MARKER)
    assert start != -1, "seat-missing boundary prose missing from round-driver.md"
    missing_slice = _normalized(text[start:start + 300])
    assert _normalized("carries no `payload` or `payloadSha256`") in missing_slice


def test_envelope_built_from_documented_fields_validates_at_ingest(tmp_path):
    # axis: envelope built exactly from the documented field list passes ingest_landing
    fields = _documented_seat_result_fields()
    assert fields == RR.SEAT_RESULT_FIELDS
    sd = _session(tmp_path)
    env = _build_envelope_from_fields(fields)
    path = RR.landing_path(sd, 1, PHASE, RR.storage_key(SEAT), 1)
    RR.atomic_write_json(path, env)
    out = RR.ingest_landing(
        sd, 1, PHASE, SEAT, 1, current_attempt=1, roster=ROSTER, anchor=None)
    assert out["ok"] is True, out
    assert out.get("reason") is None
