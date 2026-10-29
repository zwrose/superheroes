"""Compose records the host family, and the receipt projection keeps it only on agreement (#1851, review C5 L4).

Every compose in this file runs on the `--live-vendors` path: no vendor CLI, no probe, no network.

Bite-proof record: plugins/superheroes/lib/tests/bite_proofs/wo_r_1851_host_family.md"""
import json
import os
import sys

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import model_registry as MR  # noqa: E402
import seat_map as SM  # noqa: E402
import seat_map_receipts as SMR  # noqa: E402


def _compose(capsys, base):
    rc = SM.main(list(base))
    assert rc == 0
    return json.loads(capsys.readouterr().out)


# --- compose: the host family -----------------------------------------------------------------


def _host_family_receipt(capsys, host_args):
    return _compose(
        capsys, ["x", "compose", "--live-vendors", "claude,codex,cursor",
                 "--implementation-engine", "cursor", "--pr-number", "1851", *host_args])


@pytest.mark.parametrize(
    "host_args, expected",
    [
        (["--host-model", "gpt-5.6-sol"], "openai"),
        (["--host-model", "claude-opus-5"], "anthropic"),
        (["--host-model", ""], None),
        (["--host-model", "no-such-model-1851"], None),
        ([], None),
    ],
)
def test_host_family_is_the_registry_family_of_the_host_model(capsys, host_args, expected):
    receipt = _host_family_receipt(capsys, host_args)

    assert "hostFamily" in receipt
    assert receipt["hostFamily"] == expected
    assert receipt["hostFamily"] == MR.host_family(host_args[1] if host_args else "")


def test_host_family_does_not_move_the_family_fields_or_degradations(capsys):
    known = _host_family_receipt(capsys, ["--host-model", "gpt-5.6-sol"])
    assert known["authorFamily"] == "xai"
    assert not [d for d in known["degradations"] if d["constraint"] == "host-model-unknown"]

    unknown = _host_family_receipt(capsys, ["--host-model", ""])
    assert len([d for d in unknown["degradations"] if d["constraint"] == "host-model-unknown"]) == 1


def test_author_flag_path_records_a_null_host_family(capsys):
    receipt = _compose(
        capsys, ["x", "compose", "--live-vendors", "claude,codex,cursor",
                 "--author-family", "openai",
                 "--pr-number", "1851"])

    assert receipt["hostFamily"] is None


# --- receipt projection -----------------------------------------------------------------------


def _seat_map(**extra):
    base = {"seats": {"generalist-reviewer": {"vendor": "claude", "family": "anthropic", "tier": "reviewer-deep"}}}
    base.update(extra)
    return base


def _state(*maps):
    return {"seatMapReceipts": [{"round": str(i + 1), "map": m} for i, m in enumerate(maps)]}


def test_projection_host_family_survives_only_on_agreement():
    anthropic = _seat_map(hostFamily="anthropic")
    openai = _seat_map(hostFamily="openai")
    unknown = _seat_map(hostFamily=None)

    assert SMR.emit_receipt_seat_map(_state(anthropic, anthropic))["hostFamily"] == "anthropic"
    assert SMR.emit_receipt_seat_map(_state(anthropic, openai))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(openai, anthropic))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(anthropic, unknown))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(unknown, anthropic))["hostFamily"] is None


def test_projection_leaves_the_key_absent_when_no_receipt_carries_it():
    projected = SMR.emit_receipt_seat_map(_state(_seat_map(), _seat_map()))

    assert "hostFamily" not in projected


def test_projection_ignores_legacy_receipts_beside_a_carrying_one():
    legacy = _seat_map()
    carrying = _seat_map(hostFamily="anthropic")

    assert SMR.emit_receipt_seat_map(_state(carrying, legacy))["hostFamily"] == "anthropic"
    assert SMR.emit_receipt_seat_map(_state(legacy, carrying))["hostFamily"] == "anthropic"


def test_the_host_family_key_never_falls_into_the_last_wins_loop():
    assert "hostFamily" in SMR._EVIDENCE_MAP_KEYS


# --- to_receipt carries what compose stamps ---------------------------------------------------


def test_to_receipt_carries_the_host_family_only_when_the_map_has_it():
    sm = SM.build(SM.PANEL_ROSTER, ["claude"], "openai", 1)
    assert "hostFamily" not in SM.to_receipt(sm)

    sm.update(hostFamily="openai")
    assert SM.to_receipt(sm)["hostFamily"] == "openai"
    sm.update(hostFamily=None)
    assert SM.to_receipt(sm)["hostFamily"] is None
