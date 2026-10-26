"""A slow liveness probe no longer reads as a dead review vendor (#2168).

A composition probe that outruns its timeout counts the vendor live, discloses the cell as a
`liveness-timeout` degradation, and is never cached; a probe that fails outright still reads
dead. Every probe here is a fake: no vendor CLI, no network."""
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import liveness_cache  # noqa: E402
import model_registry as MR  # noqa: E402
import preflight_probe as pp  # noqa: E402
import seat_map as SM  # noqa: E402

_CODEX_CELL = MR.ladder("codex")[0]
_CODEX_VERSION_STDOUT = "codex-cli %s\n" % MR.codex_min_cli()[0]
COMPOSE_BASE = [
    "x", "compose",
    "--configured-engines", "claude,codex",
    "--implementation-engine", "claude",
    "--host-model", "claude-opus-5",
    "--pr-number", "2168",
]


def _run_answering(cell_reply):
    """A fake run: at-floor `codex --version`, and `cell_reply(argv)` for every cell probe."""
    def _run(argv, **kwargs):
        if list(argv) == ["codex", "--version"]:
            return SimpleNamespace(returncode=0, stdout=_CODEX_VERSION_STDOUT, stderr="")
        return cell_reply(argv, kwargs)
    return _run


def _timeout(argv, kwargs):
    raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs.get("timeout"))


def _fails(argv, kwargs):
    return SimpleNamespace(returncode=1, stdout="", stderr="401 Unauthorized")


def _not_installed(argv, kwargs):
    raise FileNotFoundError("[Errno 2] No such file or directory: 'codex'")


# --- probe_command ---------------------------------------------------------------------------


def test_probe_command_marks_a_timeout_and_only_a_timeout():
    seen = {}

    def _run(argv, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(cmd=argv, timeout=kwargs["timeout"])

    timed = pp.probe_command("t", ["t"], run=_run)
    assert seen["timeout"] == pp.PROBE_TIMEOUT_SECONDS
    assert timed["ok"] is False and timed["timedOut"] is True

    failed = pp.probe_command("t", ["t"], run=lambda argv, **kw: _not_installed(argv, kw))
    assert failed["ok"] is False and "timedOut" not in failed


# --- composition_liveness --------------------------------------------------------------------


def test_timed_out_cell_reads_live_and_unproven():
    model, effort = _CODEX_CELL
    result = pp.composition_liveness({"codex": [(model, effort)]}, run=_run_answering(_timeout))
    cell = result["codex"]["cells"][0]
    assert result["codex"]["live"] is True
    assert cell["ok"] is True and cell["timedOut"] is True
    assert "timed out after %ds" % pp.PROBE_TIMEOUT_SECONDS in cell["detail"]


@pytest.mark.parametrize("reply", [_fails, _not_installed], ids=["non-zero-exit", "not-installed"])
def test_failed_cell_still_reads_dead(reply):
    model, effort = _CODEX_CELL
    result = pp.composition_liveness({"codex": [(model, effort)]}, run=_run_answering(reply))
    cell = result["codex"]["cells"][0]
    assert result["codex"]["live"] is False
    assert cell["ok"] is False and "timedOut" not in cell


# --- live_vendors_for_composition ------------------------------------------------------------


def test_timeout_keeps_vendor_live_discloses_it_and_is_never_cached(tmp_path):
    cache = str(tmp_path / "composition-liveness.json")
    live, live_cells, _liv, notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"], run=_run_answering(_timeout), cache_path=cache, now=1000.0)
    assert "codex" in live
    assert any(c[0] == "codex" for c in live_cells)
    timeout_notes = [n for n in notes if n.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]
    assert timeout_notes
    assert all(n["vendor"] == "codex" and "timed out" in n["reason"] for n in timeout_notes)
    assert len({(n["model"], n["effort"]) for n in timeout_notes}) == len(timeout_notes)
    assert not [n for n in notes if n.get("constraint") == "liveness-cell"]
    assert not os.path.exists(cache)


def test_timeout_confined_to_the_nonpanel_set_is_disclosed_once():
    panel_cell = _CODEX_CELL
    extra_cell = next(c for c in MR.ladder("codex") if c[0] != panel_cell[0])

    def _reply(argv, kwargs):
        if argv[argv.index("-m") + 1] == extra_cell[0]:
            return _timeout(argv, kwargs)
        return SimpleNamespace(returncode=0, stdout="READY", stderr="")

    report = {}
    live, _cells, _liv, notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"], run=_run_answering(_reply),
        needed_override={"codex": [panel_cell]},
        extra_needed={"codex": [panel_cell, extra_cell]},
        extra_report=report)
    assert "codex" in live
    assert ["codex", *extra_cell] in report["liveCells"]
    timeout_notes = [n for n in notes if n.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]
    assert [(n["model"], n["effort"]) for n in timeout_notes] == [tuple(extra_cell)]

    shared = pp.live_vendors_for_composition(
        ["codex"], run=_run_answering(_timeout),
        needed_override={"codex": [panel_cell]},
        extra_needed={"codex": [panel_cell]})[3]
    assert len([n for n in shared if n.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]) == 1


def test_outright_failure_still_excludes_vendor_and_caches(tmp_path):
    cache = str(tmp_path / "composition-liveness.json")
    live, _cells, _liv, notes, _src, _prov = pp.live_vendors_for_composition(
        ["codex"], run=_run_answering(_fails), cache_path=cache, now=1000.0)
    assert "codex" not in live
    assert [n for n in notes if n.get("constraint") == "liveness-cell" and n["vendor"] == "codex"]
    assert not [n for n in notes if n.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]
    assert liveness_cache.read(cache, now=1000.0) is not None


# --- the seat map, end to end through compose ------------------------------------------------


@pytest.fixture
def compose_with(tmp_path, monkeypatch):
    """Compose a seat map whose every codex cell probe answers with `reply`, through the real
    probe_command, with a private liveness cache."""
    cache = str(tmp_path / "state" / "composition-liveness.json")
    monkeypatch.setattr(liveness_cache, "receipt_path", lambda cwd=None, root=None: cache)
    monkeypatch.setattr(pp, "codex_cli_floor_probe", lambda run=None: None)

    def _compose(reply, capsys):
        def engine_probe(tool, argv, run, stdin_text):
            return pp.probe_command(tool, argv, run=_run_answering(reply), stdin_text=stdin_text)

        monkeypatch.setattr(pp, "_engine_probe_in_scratch_repo", engine_probe)
        assert SM.main(list(COMPOSE_BASE)) == 0
        return json.loads(capsys.readouterr().out)

    return _compose


def _codex_seats(receipt):
    return [s for s in receipt["seats"].values() if s.get("vendor") == "codex"]


def test_seat_map_seats_a_timed_out_vendor_and_names_the_timeout(compose_with, capsys):
    receipt = compose_with(_timeout, capsys)
    assert "codex" in receipt["liveVendors"]
    assert _codex_seats(receipt)
    timeout_degs = [d for d in receipt["degradations"]
                    if d.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]
    assert timeout_degs
    assert all("timed out after %ds" % pp.PROBE_TIMEOUT_SECONDS in d["reason"] for d in timeout_degs)


def test_seat_map_leaves_an_outright_failed_vendor_unseated(compose_with, capsys):
    receipt = compose_with(_fails, capsys)
    assert "codex" not in receipt["liveVendors"]
    assert not _codex_seats(receipt)
    assert not [d for d in receipt["degradations"]
                if d.get("constraint") == liveness_cache.LIVENESS_TIMEOUT_CONSTRAINT]
