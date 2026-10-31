"""Seat independence — loop record and driver seed (#1272 WO-2)."""
import receipt_disclosures
import round_driver as RD

HEAD = "diff --git a/a.py\n"


def test_driver_seed_single_vendor_cross_family_fixer_is_independent():
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude"], "fixerVendor": "cursor"}))[
            "independenceDegraded"
        ]
        is False
    )
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude"], "fixerVendor": "claude"}))[
            "independenceDegraded"
        ]
        is True
    )
    assert RD.new_state(RD._default_config({"vendors": ["claude"]}))["independenceDegraded"] is True
    assert (
        RD.new_state(RD._default_config({"vendors": ["codex", "cursor"]}))["independenceDegraded"]
        is False
    )


def test_fixer_round_record_carries_declared_vendor():
    state = RD.new_state(RD._default_config({"fixerVendor": "cursor"}))
    RD._fold_panel(
        state,
        state["config"],
        {"seats": {dim: {"findings": []} for dim in RD.DIMENSIONS}},
    )
    RD._fold_apply_fixes(state, state["config"], {"fixes": [], "headDiff": HEAD})
    # re-pinned (#1272 layer 2d): the fixer fold now advances the round; the vendor is recorded on the fold's own round
    assert state["rounds"]["1"]["fixerVendor"] == state["config"]["fixerVendor"]


def test_duplicate_vendor_entries_do_not_read_independent():
    assert (
        RD.new_state(RD._default_config({"vendors": ["claude", "claude"]}))["independenceDegraded"]
        is True
    )
    assert receipt_disclosures.live_vendors({"vendors": ["codex", "codex", "cursor"]}) == [
        "codex",
        "cursor",
    ]


def test_auditor_vendor_and_seed_share_one_rule():
    configs = [
        {"vendors": ["claude"], "fixerVendor": "cursor"},
        {"vendors": ["claude"], "fixerVendor": "claude"},
        {"vendors": ["codex", "cursor"], "fixerVendor": "cursor"},
    ]
    for cfg in configs:
        full_cfg = RD._default_config(cfg)
        fixer = full_cfg.get("fixerVendor")
        expected = (
            "independent"
            if receipt_disclosures.independent_auditor_available(full_cfg)[0]
            else "unseatable"
        )
        assert RD._auditor_vendor(full_cfg, fixer)[1] == expected
