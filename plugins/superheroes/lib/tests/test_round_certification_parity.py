"""Certification receipt today-fields must match round_driver.build_receipt (#1271 C12 L2-G)."""
import json
import os

import pytest
import round_certification as RC
import round_driver as RD

from round_certification_fixtures import PARITY_FIXTURES, STATE_FILE

CERTIFICATION_EXTRA_KEYS = frozenset(
    ("terminalState", "terminalCause", "seats", "disclosures", "provenanceLabels")
)


def _load_state(session_dir):
    with open(os.path.join(session_dir, STATE_FILE), encoding="utf-8") as fh:
        return json.load(fh)


def _assert_receipt_parity(session_dir):
    state = _load_state(session_dir)
    driver_receipt = RD.build_receipt(state, session_dir)
    cert_receipt, refusal = RC.certify(session_dir)
    assert refusal is None, refusal
    assert cert_receipt is not None
    assert set(cert_receipt.keys()) >= set(driver_receipt.keys())
    for key in driver_receipt:
        assert cert_receipt[key] == driver_receipt[key], "mismatch on key %r" % key
    extra = set(cert_receipt.keys()) - set(driver_receipt.keys())
    assert extra == CERTIFICATION_EXTRA_KEYS, "unexpected extra keys: %s" % sorted(extra)
    ok, reason = RD.validate_receipt(cert_receipt)
    assert ok, reason


@pytest.mark.parametrize("label,builder", PARITY_FIXTURES, ids=[label for label, _ in PARITY_FIXTURES])
def test_certification_receipt_matches_driver_today_fields(tmp_path, label, builder):
    session_dir = builder(tmp_path)
    _assert_receipt_parity(session_dir)
