"""Compose probes and records the non-panel cells and the host family (#1851, review C5 L4).

Every probe in this file is a fake: no vendor CLI, no network. The registry's real verifier and
reviewer-deep cells coincide with the panel's own cells, so the probing tests give the codex and
cursor verifier cells a distinct model id (a patched `matrix_config("verifier", ...)`) — a dead
non-panel cell and a dead panel cell are then separate things to assert on."""
import json
import os
import sys
import time
from types import SimpleNamespace

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import liveness_cache  # noqa: E402
import model_registry as MR  # noqa: E402
import preflight_probe as pp  # noqa: E402
import seat_map as SM  # noqa: E402
import seat_map_receipts as SMR  # noqa: E402

CODEX_VERIFIER = ("codex-nonpanel-verifier", "high")
CURSOR_VERIFIER = ("cursor-nonpanel-verifier", "xhigh")
CODEX_VERIFIER_TRIPLE = ["codex", *CODEX_VERIFIER]
CURSOR_VERIFIER_TRIPLE = ["cursor", *CURSOR_VERIFIER]
COMPOSE_BASE = [
    "x", "compose",
    "--configured-engines", "claude,codex,cursor",
    "--implementation-engine", "cursor",
    "--host-model", "claude-opus-5",
    "--pr-number", "1851",
]


def _real_cell(role, vendor):
    cell = MR.matrix_config(role, vendor)
    return None if cell is None else [vendor, *cell]


@pytest.fixture
def probe_env(tmp_path, monkeypatch):
    """Patch the probe seams: distinct verifier cells, a fake per-cell probe that records every
    (vendor, model, effort) it is asked about and fails the ones in `env.dead`, and a private cache."""
    env = SimpleNamespace(
        dead=set(),
        probed=[],
        floor=None,
        cache=str(tmp_path / "state" / "composition-liveness.json"),
        extra_needed_seen=[],
    )
    real_matrix = MR.matrix_config

    def matrix(role, vendor):
        if role == "verifier" and vendor == "codex":
            return CODEX_VERIFIER
        if role == "verifier" and vendor == "cursor":
            return CURSOR_VERIFIER
        return real_matrix(role, vendor)

    def no_op_argv(engine, model, effort=None):
        return (engine, model, effort or "")

    def engine_probe(tool, argv, run, stdin_text):
        engine, model, effort = argv
        cell = (engine, model, effort or None)
        env.probed.append(cell)
        ok = cell not in env.dead
        return {"tool": tool, "ok": ok, "exit": 0 if ok else 1, "detail": "" if ok else "dead cell"}

    real_live = pp.live_vendors_for_composition

    def spying_live(*args, **kwargs):
        env.extra_needed_seen.append(kwargs)
        return real_live(*args, **kwargs)

    monkeypatch.setattr(MR, "matrix_config", matrix)
    monkeypatch.setattr(pp, "model_no_op_argv", no_op_argv)
    monkeypatch.setattr(pp, "_engine_probe_in_scratch_repo", engine_probe)
    monkeypatch.setattr(pp, "codex_cli_floor_probe", lambda run=None: env.floor)
    monkeypatch.setattr(pp, "live_vendors_for_composition", spying_live)
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: env.cache)
    return env


def _compose(capsys, extra=(), base=COMPOSE_BASE):
    rc = SM.main(list(base) + list(extra))
    assert rc == 0
    return json.loads(capsys.readouterr().out)


def _panel_view(receipt):
    return {
        "liveVendors": receipt["liveVendors"],
        "liveCells": receipt["liveCells"],
        "liveCellsSource": receipt["liveCellsSource"],
        "degradations": receipt["degradations"],
    }


# --- edge 1: verifier cell dead, panel cells live -------------------------------------------


def test_dead_verifier_cell_leaves_the_panel_verdict_untouched(probe_env, capsys, tmp_path, monkeypatch):
    clean = _compose(capsys)
    assert CODEX_VERIFIER_TRIPLE in clean["nonPanelLiveCells"]

    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: str(tmp_path / "b.json"))
    probe_env.dead.add(("codex", CODEX_VERIFIER[0], CODEX_VERIFIER[1]))
    degraded = _compose(capsys)

    assert "codex" in degraded["liveVendors"]
    assert _panel_view(degraded) == _panel_view(clean)
    assert CODEX_VERIFIER_TRIPLE not in degraded["nonPanelLiveCells"]
    assert CURSOR_VERIFIER_TRIPLE in degraded["nonPanelLiveCells"]
    assert _real_cell("reviewer-deep", "codex") in degraded["nonPanelLiveCells"]
    assert degraded["nonPanelLiveCellsSource"] == "probed"
    assert not [d for d in degraded["degradations"] if CODEX_VERIFIER[0] in json.dumps(d)]


# --- edge 2: panel cell dead, verifier cell live ---------------------------------------------


def test_dead_panel_cell_drops_the_vendor_but_records_the_live_verifier_cell(probe_env, capsys):
    deep_model, deep_effort = MR.matrix_config("reviewer-deep", "codex")
    probe_env.dead.add(("codex", deep_model, deep_effort))
    receipt = _compose(capsys)

    assert "codex" not in receipt["liveVendors"]
    assert CODEX_VERIFIER_TRIPLE in receipt["nonPanelLiveCells"]
    assert ["codex", deep_model, deep_effort] not in receipt["nonPanelLiveCells"]


# --- edge 3: pinned compose still probes the non-panel cells ---------------------------------


def test_pinned_compose_still_probes_the_nonpanel_cells(probe_env, capsys):
    receipt = _compose(capsys, ["--pins", '{"security-reviewer":{"vendor":"codex"}}'])

    assert receipt["livenessPinScoped"] is True
    kwargs = probe_env.extra_needed_seen[0]
    panel_codex = [list(c) for c in kwargs["needed_override"]["codex"]]
    assert list(CODEX_VERIFIER) not in panel_codex
    assert list(CODEX_VERIFIER) in [list(c) for c in kwargs["extra_needed"]["codex"]]
    assert ("codex", *CODEX_VERIFIER) in probe_env.probed
    assert CODEX_VERIFIER_TRIPLE in receipt["nonPanelLiveCells"]
    assert CURSOR_VERIFIER_TRIPLE in receipt["nonPanelLiveCells"]


# --- edge 4: cache coverage includes the non-panel set ---------------------------------------


def test_cache_whose_needed_covers_both_sets_is_reused_without_a_reprobe(probe_env, capsys):
    first = _compose(capsys)
    assert probe_env.probed
    probe_env.probed.clear()
    second = _compose(capsys)

    assert probe_env.probed == []
    assert second["nonPanelLiveCells"] == first["nonPanelLiveCells"]
    assert second["nonPanelLiveCellsSource"] == "probed"
    assert _panel_view(second)["liveCells"] == _panel_view(first)["liveCells"]


def test_cache_written_before_l4_without_the_nonpanel_cells_is_reprobed(probe_env, capsys):
    panel_needed = pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"])
    stale_liveness = {
        vendor: {
            "live": True,
            "models": {m: {"ok": True, "detail": ""} for m, _e in cells},
            "cells": [{"model": m, "effort": e, "ok": True, "detail": ""} for m, e in cells],
        }
        for vendor, cells in panel_needed.items()
    }
    stale_liveness["claude"] = {"live": True, "models": {}, "cells": []}
    assert liveness_cache.write(stale_liveness, panel_needed, path=probe_env.cache, now=time.time() - 5)

    receipt = _compose(capsys)

    assert ("codex", *CODEX_VERIFIER) in probe_env.probed
    assert CODEX_VERIFIER_TRIPLE in receipt["nonPanelLiveCells"]
    rewritten = liveness_cache.read(probe_env.cache, now=time.time())
    assert liveness_cache.covers(
        rewritten["needed"], pp.needed_configs_for(SM.NONPANEL_CELL_ROLES, ["codex", "cursor"]))


def test_probe_writes_one_cache_receipt_covering_both_sets(probe_env, capsys):
    _compose(capsys)
    rec = liveness_cache.read(probe_env.cache, now=time.time())
    assert liveness_cache.covers(
        rec["needed"], pp.needed_configs_for(("reviewer-deep", "reviewer"), ["codex", "cursor"]))
    assert liveness_cache.covers(
        rec["needed"], pp.needed_configs_for(SM.NONPANEL_CELL_ROLES, ["codex", "cursor"]))


# --- edge 5: --live-vendors is synthesized ---------------------------------------------------


def _expected_cells(vendors):
    out = set()
    for vendor in vendors:
        for role in SM.NONPANEL_CELL_ROLES:
            cell = MR.matrix_config(role, vendor)
            if cell is not None:
                out.add((vendor, cell[0], cell[1]))
    return sorted([list(c) for c in out], key=lambda c: (c[0], c[1], c[2] or ""))


def test_live_vendors_path_synthesizes_both_cells_per_listed_vendor(capsys):
    receipt = _compose(
        capsys, base=["x", "compose", "--live-vendors", "claude,codex,cursor",
                      "--implementation-engine", "cursor", "--host-model", "claude-opus-5",
                      "--pr-number", "1851"])

    assert receipt["nonPanelLiveCellsSource"] == "synthesized"
    assert receipt["nonPanelLiveCells"] == _expected_cells(["codex", "cursor"])
    for vendor in ("codex", "cursor"):
        for role in ("verifier", "reviewer-deep"):
            assert _real_cell(role, vendor) in receipt["nonPanelLiveCells"]
        # the receipt carries exactly the cells the registry lists: codex's synthesis cell (the same
        # triple as its verifier cell), and none for cursor, whose synthesis row is empty
        synthesis = _real_cell("synthesis", vendor)
        if MR.matrix_config("synthesis", vendor) is None:
            assert synthesis is None
        else:
            assert synthesis in receipt["nonPanelLiveCells"]


def test_live_vendors_path_lists_only_the_listed_vendors(capsys):
    receipt = _compose(
        capsys, base=["x", "compose", "--live-vendors", "claude,codex",
                      "--implementation-engine", "cursor", "--host-model", "claude-opus-5",
                      "--pr-number", "1851"])

    assert receipt["nonPanelLiveCellsSource"] == "synthesized"
    assert receipt["nonPanelLiveCells"] == _expected_cells(["codex"])


# --- edge 6: refusal / probe error -> unprobed ----------------------------------------------


def test_codex_floor_refusal_keeps_the_other_vendors_probed_cells(probe_env, capsys):
    # axis: a codex refusal kills only codex's cells; cursor's successfully probed cells stay live
    probe_env.floor = {"tool": "codex cli floor", "ok": False, "exit": 0, "detail": "codex-cli-too-old: test"}
    receipt = _compose(capsys)

    assert receipt["nonPanelLiveCellsSource"] == "probed"
    assert not [c for c in receipt["nonPanelLiveCells"] if c[0] == "codex"]
    assert "codex" not in receipt["liveVendors"]
    assert CURSOR_VERIFIER_TRIPLE in receipt["nonPanelLiveCells"]
    assert _real_cell("reviewer-deep", "cursor") in receipt["nonPanelLiveCells"]


def test_liveness_read_error_on_the_nonpanel_set_is_unprobed(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("reconcile exploded")

    monkeypatch.setattr(pp, "codex_cli_floor_probe", lambda run=None: None)
    monkeypatch.setattr(liveness_cache, "_reconcile_inventory", boom)
    report: dict = {}
    pp.live_vendors_for_composition(
        ["cursor"],
        run=lambda argv, **kw: SimpleNamespace(returncode=0, stdout="READY", stderr=""),
        extra_needed=pp.needed_configs_for(SM.NONPANEL_CELL_ROLES, ["cursor"]),
        extra_report=report,
    )

    assert report == {"liveCells": [], "source": "unprobed"}


def test_compose_without_a_filled_report_is_unprobed_never_omitted(tmp_path, monkeypatch, capsys):
    def fell_open(*_args, **_kwargs):
        return (["claude"], [], {}, [], "probed", {"servedFromCache": False, "probedAt": None, "remainingTtl": None})

    monkeypatch.setattr(pp, "live_vendors_for_composition", fell_open)
    receipt = _compose(capsys)

    assert receipt["nonPanelLiveCells"] == []
    assert receipt["nonPanelLiveCellsSource"] == "unprobed"
    assert "hostFamily" in receipt


# --- edge 7: host family ----------------------------------------------------------------------


def _host_family_receipt(capsys, host_args):
    return _compose(
        capsys, base=["x", "compose", "--live-vendors", "claude,codex,cursor",
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
        capsys, base=["x", "compose", "--live-vendors", "claude,codex,cursor",
                      "--author-family", "openai",
                      "--pr-number", "1851"])

    assert receipt["hostFamily"] is None
    assert receipt["nonPanelLiveCellsSource"] == "synthesized"


# --- edge 8: receipt projection --------------------------------------------------------------


def _seat_map(**extra):
    base = {"seats": {"generalist-reviewer": {"vendor": "claude", "family": "anthropic", "tier": "reviewer-deep"}}}
    base.update(extra)
    return base


def _state(*maps):
    return {"seatMapReceipts": [{"round": str(i + 1), "map": m} for i, m in enumerate(maps)]}


def test_projection_merges_the_nonpanel_source_to_the_least_trusted():
    probed = _seat_map(nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE])
    unprobed = _seat_map(nonPanelLiveCellsSource="unprobed", nonPanelLiveCells=[])

    assert SMR.emit_receipt_seat_map(_state(probed, unprobed))["nonPanelLiveCellsSource"] == "unprobed"
    assert SMR.emit_receipt_seat_map(_state(unprobed, probed))["nonPanelLiveCellsSource"] == "unprobed"
    synthesized = _seat_map(nonPanelLiveCellsSource="synthesized", nonPanelLiveCells=[])
    assert SMR.emit_receipt_seat_map(_state(probed, synthesized))["nonPanelLiveCellsSource"] == "synthesized"


@pytest.mark.parametrize("bad", [["probed"], {"a": 1}, 7, None])
def test_projection_malformed_nonpanel_source_merges_to_unprobed(bad):
    probed = _seat_map(nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE])
    malformed = _seat_map(nonPanelLiveCellsSource=bad, nonPanelLiveCells=[])

    assert SMR.emit_receipt_seat_map(_state(malformed))["nonPanelLiveCellsSource"] == "unprobed"
    assert SMR.emit_receipt_seat_map(_state(probed, malformed))["nonPanelLiveCellsSource"] == "unprobed"


def test_projection_unions_the_nonpanel_cells():
    first = _seat_map(nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE])
    second = _seat_map(nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CURSOR_VERIFIER_TRIPLE])

    merged = SMR.emit_receipt_seat_map(_state(first, second))["nonPanelLiveCells"]

    assert CODEX_VERIFIER_TRIPLE in merged and CURSOR_VERIFIER_TRIPLE in merged


def test_projection_host_family_survives_only_on_agreement():
    anthropic = _seat_map(hostFamily="anthropic")
    openai = _seat_map(hostFamily="openai")
    unknown = _seat_map(hostFamily=None)

    assert SMR.emit_receipt_seat_map(_state(anthropic, anthropic))["hostFamily"] == "anthropic"
    assert SMR.emit_receipt_seat_map(_state(anthropic, openai))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(openai, anthropic))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(anthropic, unknown))["hostFamily"] is None
    assert SMR.emit_receipt_seat_map(_state(unknown, anthropic))["hostFamily"] is None


def test_projection_leaves_the_keys_absent_when_no_receipt_carries_them():
    projected = SMR.emit_receipt_seat_map(_state(_seat_map(), _seat_map()))

    for key in ("hostFamily", "nonPanelLiveCells", "nonPanelLiveCellsSource"):
        assert key not in projected


def test_projection_ignores_legacy_receipts_beside_a_carrying_one():
    legacy = _seat_map()
    carrying = _seat_map(
        hostFamily="anthropic", nonPanelLiveCellsSource="probed", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE])

    projected = SMR.emit_receipt_seat_map(_state(carrying, legacy))

    assert projected["hostFamily"] == "anthropic"
    assert projected["nonPanelLiveCellsSource"] == "probed"
    assert projected["nonPanelLiveCells"] == [CODEX_VERIFIER_TRIPLE]


def test_the_three_keys_never_fall_into_the_last_wins_loop():
    for key in ("hostFamily", "nonPanelLiveCells", "nonPanelLiveCellsSource"):
        assert key in SMR._EVIDENCE_MAP_KEYS
    assert "nonPanelLiveCells" in SMR._LIST_EVIDENCE_MAP_KEYS


# --- edge 9: claude is never probed, never required ------------------------------------------


def test_claude_is_never_probed_and_has_no_nonpanel_triple(probe_env, capsys):
    receipt = _compose(capsys)

    assert all(vendor != "claude" for vendor, _m, _e in probe_env.probed)
    assert all(cell[0] != "claude" for cell in receipt["nonPanelLiveCells"])
    assert "claude" in receipt["liveVendors"]


def test_claude_only_live_vendors_records_an_empty_synthesized_set(capsys):
    receipt = _compose(
        capsys, base=["x", "compose", "--live-vendors", "claude",
                      "--implementation-engine", "claude", "--host-model", "claude-opus-5",
                      "--pr-number", "1851"])

    assert receipt["nonPanelLiveCells"] == []
    assert receipt["nonPanelLiveCellsSource"] == "synthesized"


# --- the compose-liveness CLI prints the cells (J5) -------------------------------------------


def test_cli_compose_liveness_prints_the_nonpanel_cells(probe_env, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pp, "review_cross_vendor_engines", lambda prefs, which=None: ["codex", "cursor"])
    monkeypatch.setattr(pp.core_md, "read", lambda *a, **k: {"enginePreferences": {}})

    rc = pp.main(["preflight_probe.py", "compose-liveness", "--cwd", str(tmp_path)])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert CODEX_VERIFIER_TRIPLE in payload["nonPanelLiveCells"]
    assert CURSOR_VERIFIER_TRIPLE in payload["nonPanelLiveCells"]
    assert payload["nonPanelLiveCellsSource"] == "probed"
    assert "liveCells" in payload


# --- to_receipt carries what compose stamps ---------------------------------------------------


def test_to_receipt_carries_the_three_keys_only_when_the_map_has_them():
    sm = SM.build(SM.PANEL_ROSTER, ["claude"], "openai", 1)
    assert not {"hostFamily", "nonPanelLiveCells", "nonPanelLiveCellsSource"} & set(SM.to_receipt(sm))

    sm.update(hostFamily="openai", nonPanelLiveCells=[CODEX_VERIFIER_TRIPLE], nonPanelLiveCellsSource="probed")
    receipt = SM.to_receipt(sm)
    assert receipt["hostFamily"] == "openai"
    assert receipt["nonPanelLiveCells"] == [CODEX_VERIFIER_TRIPLE]
    assert receipt["nonPanelLiveCellsSource"] == "probed"
