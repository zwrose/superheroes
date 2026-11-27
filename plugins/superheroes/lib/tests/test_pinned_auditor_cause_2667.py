from test_layer4a_auditor_seat_time_1272 import (
    _audits_emit_fixture,
    _blocking_finding,
    round_driver,
)


def test_missing_audit_evidence_explains_pinned_roster_exclusion(tmp_path):
    # axis: next records why a live independent vendor cannot audit when the roster excludes it
    session_dir, state, _target = _audits_emit_fixture(tmp_path, advance_used=True)
    config = state["config"]
    config["vendors"] = ["claude", "codex"]
    config["fixerVendor"] = "claude"
    state["seatMapReceipts"].append({
        "round": "1",
        "map": {
            "makerFamilies": ["anthropic"],
            "seats": {"code-reviewer": {"vendor": "cursor", "source": "pinned"}},
        },
    })
    state["fixBatch"] = [_blocking_finding("missing bounds guard", 2)]
    target, = round_driver._audit_targets(state, config, {})
    assert target["independence"] == "unseatable"
    state["_auditTargets"] = [target]
    round_driver.save_state(session_dir, state)

    action = round_driver.cmd_next(session_dir)
    assert action["ok"] and action["phase"] == round_driver.P_AUDITS, action
    records = round_driver.round_records
    path = records.store_path(session_dir, action["round"], action["phase"],
                              records.storage_key(target["id"], 0), action["attempt"])
    envelope, error = records.read_json(path)
    assert error is None, error
    assert envelope["reason"] == round_driver.UNFILLED_SEAT_REASON
    evidence = envelope["evidence"]
    assert "codex" in evidence and "excluded by the pinned roster" in evidence, evidence
