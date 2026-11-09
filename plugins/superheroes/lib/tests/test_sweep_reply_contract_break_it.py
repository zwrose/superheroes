"""Sweep delivery guards reject absent or contradictory reply instructions."""

import pytest

import test_round_driver_order_channel as channel_checks
import test_round_orders as order_checks


@pytest.mark.parametrize("guard_name", ["render", "census"])
@pytest.mark.parametrize("mutation", ["empty", "writes-file"])
def test_sweep_reply_guards_reject_invalid_delivery(monkeypatch, guard_name, mutation):
    # axis: both delivery guards reject an empty reply block or an affirmative file-write instruction.
    checks = order_checks if guard_name == "render" else channel_checks

    def check():
        if guard_name == "render":
            checks.test_sweep_host_seat_order_replies_and_never_writes()
        else:
            checks.test_every_phase_renders_exactly_one_output_contract(checks.RD.P_SWEEP)

    check()
    original = checks.RO._SWEEP_HOST_REPLY_DELIVERY
    assert original.strip()
    if mutation == "empty":
        replacement = ""
    else:
        needle = "Write no file."
        assert original.count(needle) == 1
        replacement = original.replace(needle, "Write a file.", 1)

    monkeypatch.setattr(checks.RO, "_SWEEP_HOST_REPLY_DELIVERY", replacement)
    with pytest.raises(AssertionError):
        check()
