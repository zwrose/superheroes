import os
import re

import round_certification as RC
import round_driver as RD
import round_records as RR

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_certified_verdicts_match_driver():
    assert set(RC.CERTIFIED_VERDICTS) == set(RD.CERTIFIED_VERDICTS)


def test_attested_verdict_matches_driver():
    assert RC.ATTESTED_VERDICT == RD.ATTESTED_VERDICT


def test_seat_provenance_matches_records():
    assert set(RC.SEAT_PROVENANCE) == set(RR.SEAT_PROVENANCE)


def test_execution_evidence_read_values_match_records():
    assert RC.EXECUTION_EVIDENCE_READ_VALUES == RR.EXECUTION_EVIDENCE_READ_VALUES


def test_base_guard_checked_matches_driver():
    assert RC.BASE_GUARD_CHECKED == RD.BASE_GUARD_CHECKED


def test_supported_state_versions_match_driver():
    assert RC.SUPPORTED_STATE_VERSIONS == RD.SUPPORTED_STATE_VERSIONS


def test_decision_keys_match_driver_census():
    driver_path = os.path.join(_LIB, "round_driver.py")
    with open(driver_path, encoding="utf-8") as fh:
        source = fh.read()
    driver_keys = set(re.findall(r'_decision\(state,\s*"([^"]+)"', source))
    assert set(RC._DECISION_KEYS) == driver_keys


def test_execution_evidence_telemetry_values_match_records():
    assert RC.EXECUTION_EVIDENCE_TELEMETRY_VALUES == RR.EXECUTION_EVIDENCE_TELEMETRY_VALUES
