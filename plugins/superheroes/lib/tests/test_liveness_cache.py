import json
import os

import pytest

import liveness_cache as lc
import mode_registry


def _good_liveness():
    return {
        "codex": {
            "live": True,
            "models": {
                "gpt-5.6-sol": {"ok": True, "detail": "READY"},
                "gpt-5.6-terra": {"ok": True, "detail": "READY"},
            },
            "cells": [
                {"model": "gpt-5.6-sol", "effort": "medium", "ok": True, "detail": "READY"},
                {"model": "gpt-5.6-terra", "effort": None, "ok": True, "detail": "READY"},
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }


def _good_needed():
    return {
        "codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]],
        "claude": [],
    }


# --- ttl_seconds ---


def test_ttl_seconds_default(monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    assert lc.ttl_seconds() == 600


def test_ttl_seconds_env_positive_override(monkeypatch):
    monkeypatch.setenv(lc._ENV_TTL, "120")
    assert lc.ttl_seconds() == 120


@pytest.mark.parametrize("val", ["abc", "0", "-5", ""])
def test_ttl_seconds_env_invalid_falls_back(monkeypatch, val):
    if val == "":
        monkeypatch.delenv(lc._ENV_TTL, raising=False)
    else:
        monkeypatch.setenv(lc._ENV_TTL, val)
    assert lc.ttl_seconds() == 600


# --- receipt_path ---


def test_receipt_path_under_state(monkeypatch, tmp_path):
    monkeypatch.setattr(mode_registry, "project_store_dir", lambda cwd, root=None: str(tmp_path))
    p = lc.receipt_path("/any/cwd")
    assert p == os.path.join(str(tmp_path), "state", "composition-liveness.json")
    assert p.endswith(os.path.join("state", "composition-liveness.json"))


# --- write / read round trip ---


def test_write_read_round_trip(tmp_path):
    path = str(tmp_path / "receipt.json")
    now = 1_000_000.0
    liveness = _good_liveness()
    needed = _good_needed()
    assert lc.write(liveness, needed, path=path, now=now) is True
    got = lc.read(path, now=now + 1)
    assert got is not None
    assert got["schemaVersion"] == lc.SCHEMA_VERSION
    assert got["probedAt"] == now
    assert got["liveness"] == liveness
    assert got["needed"]["codex"] == [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]]


def test_write_atomic_single_receipt_file(tmp_path):
    path = str(tmp_path / "state" / "composition-liveness.json")
    now = 500.0
    assert lc.write(_good_liveness(), _good_needed(), path=path, now=now) is True
    assert os.path.isfile(path)
    assert sorted(os.listdir(os.path.dirname(path))) == ["composition-liveness.json"]
    data = json.load(open(path))
    assert data["schemaVersion"] == lc.SCHEMA_VERSION
    assert "liveness" in data


# --- read MISS cases ---


def test_read_miss_missing_file(tmp_path):
    assert lc.read(str(tmp_path / "nope.json"), now=100.0) is None


def test_read_miss_bad_json(tmp_path):
    path = str(tmp_path / "bad.json")
    open(path, "wb").write(b"{not json")
    assert lc.read(path, now=100.0) is None


def test_read_miss_schema_version(tmp_path):
    path = str(tmp_path / "r.json")
    json.dump({"schemaVersion": 999, "probedAt": 0, "liveness": {}, "needed": {}}, open(path, "w"))
    assert lc.read(path, now=1000.0) is None


def test_read_rejects_pre_711_schema_v1_receipt(tmp_path, monkeypatch):
    # #711 bumped SCHEMA_VERSION; reverting the constant must not resurrect v1 receipts.
    assert lc.SCHEMA_VERSION > 1
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 5_000.0
    json.dump(
        {
            "schemaVersion": 1,
            "probedAt": now - 10,
            "liveness": _good_liveness(),
            "needed": _good_needed(),
        },
        open(path, "w"),
    )
    assert lc.read(path, now=now) is None


def test_read_rejects_v2_receipt_without_cells(tmp_path, monkeypatch):
    # axis: liveness structure — v2 receipts lacking per-cell evidence are rejected
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 5_000.0
    v2_liveness = {
        "codex": {
            "live": True,
            "models": {
                "gpt-5.6-sol": {"ok": True, "detail": "READY"},
                "gpt-5.6-terra": {"ok": True, "detail": "READY"},
            },
        },
        "claude": {"live": True, "models": {}},
    }
    json.dump(
        {
            "schemaVersion": 2,
            "probedAt": now - 10,
            "liveness": v2_liveness,
            "needed": _good_needed(),
        },
        open(path, "w"),
    )
    assert lc.read(path, now=now) is None


def test_read_rejects_v2_receipt_with_well_formed_cells(tmp_path, monkeypatch):
    # axis: SCHEMA_VERSION gate — stale v2 receipts rejected even when cell structure is valid
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 5_000.0
    v2_liveness = _good_liveness()
    json.dump(
        {
            "schemaVersion": 2,
            "probedAt": now - 10,
            "liveness": v2_liveness,
            "needed": _good_needed(),
        },
        open(path, "w"),
    )
    assert lc.read(path, now=now) is None


def test_read_miss_cells_not_list(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["cells"] = "not-a-list"
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_cell_ok_string(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["cells"][0]["ok"] = "true"
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_probed_at_future(tmp_path):
    path = str(tmp_path / "r.json")
    now = 2000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 1000)
    assert lc.read(path, now=now) is None


def test_read_miss_stale(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 10_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 601)
    assert lc.read(path, now=now) is None


def test_read_uses_reader_ttl_not_stored_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 20_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 601, ttl=100_000)
    assert lc.read(path, now=now) is None


def test_read_env_ttl_extends_stale_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv(lc._ENV_TTL, "100000")
    path = str(tmp_path / "r.json")
    now = 30_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 601)
    assert lc.read(path, now=now) is not None


def test_read_miss_json_nan_probed_at(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 4000.0
    with open(path, "wb") as fh:
        fh.write(
            ('{"schemaVersion": %d, "probedAt": NaN, "ttl": 600, '
             '"needed": {}, "liveness": {}}\n' % lc.SCHEMA_VERSION).encode("utf-8")
        )
    assert lc.read(path, now=now) is None


def test_is_timestamp_rejects_non_finite():
    assert lc._is_timestamp(float("nan")) is False
    assert lc._is_timestamp(float("inf")) is False


def test_write_skips_when_existing_receipt_is_newer(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    newer_liv = _good_liveness()
    older_liv = _good_liveness()
    older_liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = False
    assert lc.write(newer_liv, _good_needed(), path=path, now=2000.0) is True
    assert lc.write(older_liv, _good_needed(), path=path, now=1000.0) is True
    got = lc.read(path, now=2001.0)
    assert got is not None
    assert got["liveness"]["codex"]["models"]["gpt-5.6-sol"]["ok"] is True
    newest_liv = _good_liveness()
    newest_liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = False
    assert lc.write(newest_liv, _good_needed(), path=path, now=3000.0) is True
    got2 = lc.read(path, now=3001.0)
    assert got2 is not None
    assert got2["liveness"]["codex"]["models"]["gpt-5.6-sol"]["ok"] is False


def test_read_miss_model_ok_string(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = "false"
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_model_ok_int(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-sol"]["ok"] = 1
    lc.write(liv, _good_needed(), path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_miss_liveness_not_dict(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    payload = {
        "schemaVersion": lc.SCHEMA_VERSION,
        "probedAt": now - 10,
        "ttl": 600,
        "needed": {},
        "liveness": "nope",
    }
    json.dump(payload, open(path, "w"))
    assert lc.read(path, now=now) is None


def test_read_miss_model_entry_not_dict(tmp_path):
    path = str(tmp_path / "r.json")
    now = 3000.0
    liv = {"codex": {"live": True, "models": {"m": "bad"}}}
    lc.write(liv, {"codex": [["m", None]]}, path=path, now=now - 10)
    assert lc.read(path, now=now) is None


def test_read_hit_within_ttl(tmp_path, monkeypatch):
    monkeypatch.delenv(lc._ENV_TTL, raising=False)
    path = str(tmp_path / "r.json")
    now = 50_000.0
    lc.write(_good_liveness(), _good_needed(), path=path, now=now - 599)
    got = lc.read(path, now=now)
    assert got is not None
    assert got["liveness"]["codex"]["models"]["gpt-5.6-sol"]["ok"] is True


# --- covers ---


def test_covers_effort_exact_mismatch():
    need = {"codex": [["gpt-5.6-sol", "high"]]}
    rec = {"codex": [["gpt-5.6-sol", None]]}
    assert lc.covers(rec, need) is False
    rec_exact = {"codex": [["gpt-5.6-sol", "high"]]}
    assert lc.covers(rec_exact, need) is True


def test_covers_broad_receipt_narrow_need():
    rec = {"codex": [["a", None], ["b", "low"], ["c", None]]}
    need = {"codex": [["b", "low"]]}
    assert lc.covers(rec, need) is True
    rec_no_effort = {"codex": [["a", None], ["b", None], ["c", None]]}
    need_low = {"codex": [["b", "low"]]}
    assert lc.covers(rec_no_effort, need_low) is False


def test_covers_effort_mismatch_xhigh_vs_high():
    rec = {"codex": [["gpt-5.6-sol", "xhigh"]]}
    need = {"codex": [["gpt-5.6-sol", "high"]]}
    assert lc.covers(rec, need) is False


def test_covers_missing_vendor():
    assert lc.covers({}, {"codex": [["m", None]]}) is False


def test_covers_missing_model():
    rec = {"codex": [["a", None]]}
    need = {"codex": [["b", None]]}
    assert lc.covers(rec, need) is False


def test_covers_empty_need():
    assert lc.covers({"codex": [["a", None]]}, {}) is True


def test_covers_malformed():
    assert lc.covers(None, {"codex": []}) is False
    assert lc.covers({"codex": "x"}, {"codex": []}) is False


# --- live_vendors_from ---


def test_live_vendors_claude_always_present():
    live, notes = lc.live_vendors_from({}, {})
    assert live == ["claude"]
    assert notes == []


def test_live_vendors_all_ok():
    liv = _good_liveness()
    need = {"codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert live == ["claude", "codex"]
    assert notes == []


def test_live_vendors_one_model_not_ok():
    liv = _good_liveness()
    liv["codex"]["models"]["gpt-5.6-terra"]["ok"] = False
    liv["codex"]["cells"][1]["ok"] = False
    need = {"codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert live == ["claude"]
    assert len(notes) == 1
    assert notes[0]["constraint"] == "liveness-cell"
    assert notes[0]["model"] == "gpt-5.6-terra"
    assert "codex" in notes[0]["reason"]


def test_live_vendors_empty_model_list_not_live():
    live, notes = lc.live_vendors_from(_good_liveness(), {"codex": []})
    assert "codex" not in live
    assert len(notes) == 1
    assert notes[0]["vendor"] == "codex"
    assert notes[0]["model"] is None
    assert "no needed cell is reachable" in notes[0]["reason"]


def test_live_vendors_missing_vendor_in_liveness():
    need = {"cursor": [["grok", None]]}
    live, notes = lc.live_vendors_from(_good_liveness(), need)
    assert "cursor" not in live
    assert len(notes) == 1
    assert notes[0]["constraint"] == "liveness-cell"
    assert notes[0]["vendor"] == "cursor"
    assert notes[0]["model"] == "grok"


def test_live_vendors_ok_string_not_live():
    liv = {
        "codex": {
            "live": True,
            "models": {"m": {"ok": "true", "detail": ""}},
            "cells": [{"model": "m", "effort": None, "ok": "true", "detail": ""}],
        },
    }
    need = {"codex": [["m", None]]}
    live, notes = lc.live_vendors_from(liv, need)
    assert "codex" not in live
    assert notes
    assert notes[0]["constraint"] == "liveness-cell"


# --- write failure ---


def test_write_returns_false_when_dir_blocked(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    path = str(blocker / "state" / "composition-liveness.json")
    assert lc.write(_good_liveness(), _good_needed(), path=path, now=1.0) is False


def test_live_vendors_from_quorum_matches_composition_liveness_live_flags():
    needed = {
        "codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-terra", None]],
        "cursor": [["cursor-grok-4.6", "xhigh"]],
    }
    liveness = {
        "codex": {
            "live": True,
            "models": {
                "gpt-5.6-sol": {"ok": True, "detail": ""},
                "gpt-5.6-terra": {"ok": True, "detail": ""},
            },
            "cells": [
                {"model": "gpt-5.6-sol", "effort": "medium", "ok": True, "detail": ""},
                {"model": "gpt-5.6-terra", "effort": None, "ok": True, "detail": ""},
            ],
        },
        "cursor": {
            "live": False,
            "models": {"cursor-grok-4.6": {"ok": False, "detail": "down"}},
            "cells": [
                {"model": "cursor-grok-4.6", "effort": "xhigh", "ok": False, "detail": "down"},
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }
    live, notes = lc.live_vendors_from(liveness, needed)

    def _composition_style_live(vendor, entries):
        if not entries:
            return False
        info = liveness.get(vendor, {})
        models = info.get("models") if isinstance(info, dict) else None
        if not isinstance(models, dict):
            return False
        return all(
            isinstance(models.get(m), dict) and models[m].get("ok") is True
            for m, _ in entries
        )

    for vendor, entries in needed.items():
        if vendor == "claude":
            continue
        assert (vendor in live) == _composition_style_live(vendor, entries)
    assert "codex" in live
    assert "cursor" not in live
    assert any(n["constraint"] == "liveness-cell" and n["vendor"] == "cursor" for n in notes)


# --- live_from ---


def _aug15_liveness():
    """2026-08-15 incident shape: sol ok, terra timed out."""
    return {
        "codex": {
            "live": False,
            "models": {
                "gpt-5.6-sol": {"ok": True, "detail": "READY"},
                "gpt-5.6-terra": {"ok": False, "detail": "Command timed out after 120 seconds"},
            },
            "cells": [
                {"model": "gpt-5.6-sol", "effort": "xhigh", "ok": True, "detail": "READY"},
                {
                    "model": "gpt-5.6-terra",
                    "effort": "high",
                    "ok": False,
                    "detail": "Command timed out after 120 seconds",
                },
            ],
        },
        "claude": {"live": True, "models": {}, "cells": []},
    }


def test_live_from_aug15_sol_cell_live_terra_not():
    needed = {
        "codex": [["gpt-5.6-sol", "xhigh"], ["gpt-5.6-terra", "high"]],
    }
    live_vendors, live_cells, dead_notes = lc.live_from(_aug15_liveness(), needed)
    assert live_vendors == ["claude"]
    assert ["codex", "gpt-5.6-sol", "xhigh"] in live_cells
    assert ["codex", "gpt-5.6-terra", "high"] not in live_cells
    assert len(dead_notes) == 1
    assert dead_notes[0]["model"] == "gpt-5.6-terra"
    assert "timed out" in dead_notes[0]["reason"]


def test_live_from_dead_note_names_model_and_reason():
    needed = {"codex": [["gpt-5.6-terra", "high"]]}
    _, _, dead_notes = lc.live_from(_aug15_liveness(), needed)
    assert dead_notes[0]["constraint"] == "liveness-cell"
    assert dead_notes[0]["vendor"] == "codex"
    assert dead_notes[0]["model"] == "gpt-5.6-terra"
    assert dead_notes[0]["effort"] == "high"
    assert "120 seconds" in dead_notes[0]["reason"]


def test_bounded_reason_collapses_and_truncates():
    long = "word " * 60
    got = lc._bounded_reason(long)
    assert "  " not in got
    assert len(got) == 201
    assert got.endswith("\u2026")


def test_bounded_reason_no_detail():
    assert lc._bounded_reason(None) == "no probe evidence recorded"
    assert lc._bounded_reason("") == "no probe evidence recorded"


def _notes_name_vendor(notes, vendor):
    return any(n.get("vendor") == vendor for n in notes)


# axis: every vendor in needed but absent from live_vendors has at least one note naming it
@pytest.mark.parametrize(
    "liveness,needed",
    [
        # empty-entries: vendor needed but no reachable cell
        (
            _good_liveness(),
            {"codex": [], "cursor": []},
        ),
        # dead-cell: cell evidence says not live
        (
            _aug15_liveness(),
            {"codex": [["gpt-5.6-sol", "xhigh"], ["gpt-5.6-terra", "high"]]},
        ),
        # missing-vendor-evidence: vendor absent from liveness dict
        (
            _good_liveness(),
            {"cursor": [["grok", None]]},
        ),
        # malformed-entries: entries not a list/tuple
        (
            _good_liveness(),
            {"codex": "not-a-list"},
        ),
        # malformed-entry: entries is a list but an entry is not a model/effort pair
        (
            {
                "codex": {
                    "live": True,
                    "models": {"m": {"ok": True, "detail": "x"}},
                    "cells": [
                        {"model": "m", "effort": None, "ok": True, "detail": "x"},
                    ],
                },
                "claude": {"live": True, "models": {}, "cells": []},
            },
            {"codex": ["not-a-pair"]},
        ),
        # mixed: one live vendor, one empty-entries drop, one dead cell
        (
            {
                "codex": {
                    "live": True,
                    "models": {"gpt-5.6-sol": {"ok": True, "detail": ""}},
                    "cells": [
                        {"model": "gpt-5.6-sol", "effort": "xhigh", "ok": True, "detail": ""},
                    ],
                },
                "claude": {"live": True, "models": {}, "cells": []},
            },
            {
                "codex": [["gpt-5.6-sol", "xhigh"]],
                "cursor": [],
            },
        ),
    ],
)
def test_live_from_absent_vendors_always_have_disclosure_note(liveness, needed):
    live_vendors, _live_cells, dead_notes = lc.live_from(liveness, needed)
    for vendor in needed:
        if vendor == "claude":
            continue
        if vendor not in live_vendors:
            assert _notes_name_vendor(dead_notes, vendor), (
                "vendor %r left live set with no note" % vendor
            )


def test_live_from_fail_closed_absent_cell():
    liv = _good_liveness()
    needed = {"codex": [["gpt-5.6-sol", "medium"], ["missing-model", "high"]]}
    live_vendors, live_cells, dead_notes = lc.live_from(liv, needed)
    assert "codex" not in live_vendors
    assert any(n["model"] == "missing-model" for n in dead_notes)
    assert any("no probe evidence recorded" in n["reason"] for n in dead_notes)


def test_live_from_dead_note_redacts_absolute_paths():
    # axis: redaction boundary — absolute paths in probe detail never reach dead notes
    from types import SimpleNamespace

    import preflight_probe as pp

    secret_path = "/Users/someone/secret/project/file.py"
    detail_with_path = "failed at %s: timeout" % secret_path

    def _run(argv, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr=detail_with_path)

    needed = {"codex": [("gpt-5.6-sol", "xhigh")]}
    liveness = pp.composition_liveness(needed, run=_run)
    cell = liveness["codex"]["cells"][0]
    assert secret_path not in cell["detail"]
    assert pp._REDACTED_ABS_PATH in cell["detail"]

    _, _, dead_notes = lc.live_from(liveness, {"codex": [["gpt-5.6-sol", "xhigh"]]})
    assert secret_path not in dead_notes[0]["reason"]
    assert pp._REDACTED_ABS_PATH in dead_notes[0]["reason"]


# --- reconcile-after-loop disclosure (#1104 WO-B) ---


def _count_non_claude_needed_slots(needed):
    """Slots for census: one per positional entry, or 1 for unreachable vendor."""
    if not isinstance(needed, dict):
        return 0
    total = 0
    for vendor, entries in needed.items():
        if vendor == "claude":
            continue
        if not isinstance(entries, (list, tuple)) or len(entries) == 0:
            total += 1
        else:
            total += len(entries)
    return total


def test_live_from_novel_unhashable_effort_disclosed():
    """Bite-proof: unhashable effort passes if-arms but was silent via outer except."""
    needed = {"codex": [["gpt-m", {"effort": "high"}]]}
    live, live_cells, dead_notes = lc.live_from({}, needed)
    assert "codex" not in live
    assert live_cells == []
    assert len(dead_notes) == 1
    assert dead_notes[0]["vendor"] == "codex"
    assert dead_notes[0]["model"] is None
    assert "needed slot 0 has malformed cell entry" in dead_notes[0]["reason"]


def test_live_from_malformed_cell_unhashable_effort_returns():
    """Bite-proof: unhashable effort inside a cell must disclose, not raise."""
    liveness = {
        "codex": {
            "models": {},
            "cells": [{"model": "m", "effort": [], "ok": True}],
        },
    }
    needed = {"codex": [["m", None]]}
    live, live_cells, dead_notes = lc.live_from(liveness, needed)
    assert "codex" not in live
    assert live_cells == []
    assert len(dead_notes) == 1
    assert dead_notes[0]["vendor"] == "codex"


class _RaisingOnGet(dict):
    """Liveness dict whose .get raises — swallowed by _safe_vendor_info, not the outer loop."""

    def get(self, key, default=None):
        raise RuntimeError("loop died")


class _RaisingList(list):
    """cells list that raises on first iteration only (loop read, not reconcile)."""

    def __init__(self):
        super().__init__()
        self._read_attempts = 0

    def __iter__(self):
        self._read_attempts += 1
        if self._read_attempts == 1:
            raise RuntimeError("loop died")
        return iter(())


def _liveness_with_raising_cells():
    return {
        "codex": {
            "models": {},
            "cells": _RaisingList(),
        },
    }


class _RaisingOnSecondCellsIter(list):
    """cells list that raises on second iteration (reconcile read, not loop)."""

    def __init__(self):
        super().__init__()
        self._read_attempts = 0

    def __iter__(self):
        self._read_attempts += 1
        if self._read_attempts == 1:
            return iter(())
        raise RuntimeError("reconcile died")


class _RaisingLoopThenReconcile(list):
    """cells list that raises on first iter (loop) and again on second (reconcile)."""

    def __init__(self):
        super().__init__()
        self._read_attempts = 0

    def __iter__(self):
        self._read_attempts += 1
        if self._read_attempts == 1:
            raise RuntimeError("loop died")
        if self._read_attempts == 2:
            raise RuntimeError("reconcile died")
        return iter(())


def _liveness_with_raising_cells_on_reconcile():
    return {
        "codex": {
            "models": {},
            "cells": _RaisingOnSecondCellsIter(),
        },
    }


def _liveness_with_raising_loop_and_reconcile():
    return {
        "codex": {
            "models": {},
            "cells": _RaisingLoopThenReconcile(),
        },
    }


def test_live_from_reconcile_runs_when_loop_raises():
    """Reconcile still runs and discloses after a transient cell-evidence loop failure."""
    needed = {"codex": [["gpt-m", None]]}
    liveness = _RaisingOnGet()
    live, live_cells, dead_notes = lc.live_from(liveness, needed)
    assert "codex" not in live
    assert live_cells == []
    cell_notes = [n for n in dead_notes if n.get("constraint") == "liveness-cell"]
    assert len(cell_notes) == 1
    assert cell_notes[0]["vendor"] == "codex"
    assert cell_notes[0]["model"] == "gpt-m"


def test_live_from_loop_crash_emits_read_error_not_misattribution():
    # axis: a crashed liveness read is disclosed as read-error, not only as dead cells.
    needed = {"codex": [["gpt-m", None]]}
    liveness = _liveness_with_raising_cells()
    live, live_cells, dead_notes = lc.live_from(liveness, needed)
    assert "codex" not in live
    assert live_cells == []
    read_errors = [n for n in dead_notes if n.get("constraint") == "liveness-read-error"]
    assert len(read_errors) == 1
    assert "liveness read failed" in read_errors[0]["reason"]
    assert "loop died" in read_errors[0]["reason"]
    cell_notes = [n for n in dead_notes if n.get("constraint") == "liveness-cell"]
    assert len(cell_notes) == 1
    assert "not live per cached liveness" in cell_notes[0]["reason"]


def test_live_from_reconcile_crash_emits_read_error_not_propagation():
    # axis: a persistent reconcile read failure is disclosed and does not propagate.
    needed = {"codex": [["gpt-m", None]]}
    liveness = _liveness_with_raising_cells_on_reconcile()
    live, live_cells, dead_notes = lc.live_from(liveness, needed)
    assert "codex" not in live
    assert live_cells == []
    read_errors = [n for n in dead_notes if n.get("constraint") == "liveness-read-error"]
    assert len(read_errors) == 1
    assert "inventory reconcile" in read_errors[0]["reason"]
    assert "reconcile died" in read_errors[0]["reason"]


def test_live_from_loop_and_reconcile_crash_emit_distinguishable_read_errors():
    # axis: loop and reconcile failures each emit a distinct read-error note.
    needed = {"codex": [["gpt-m", None]]}
    liveness = _liveness_with_raising_loop_and_reconcile()
    live, live_cells, dead_notes = lc.live_from(liveness, needed)
    assert "codex" not in live
    assert live_cells == []
    read_errors = [n for n in dead_notes if n.get("constraint") == "liveness-read-error"]
    assert len(read_errors) == 2
    reasons = [n["reason"] for n in read_errors]
    assert sum("cell-evidence scan" in r for r in reasons) == 1
    assert sum("inventory reconcile" in r for r in reasons) == 1
    assert sum("loop died" in r for r in reasons) == 1
    assert sum("reconcile died" in r for r in reasons) == 1


def test_live_from_read_error_constraint_literal():
    # axis: read-error constraint string is pinned literally.
    needed = {"codex": [["gpt-m", None]]}
    _, _, dead_notes = lc.live_from(_liveness_with_raising_cells(), needed)
    constraints = {n["constraint"] for n in dead_notes}
    assert "liveness-read-error" in constraints


def test_live_from_normal_path_byte_identical():
    # axis: no-exception path output is unchanged.
    expected_live = ["claude", "codex"]
    expected_cells = [
        ["codex", "gpt-5.6-sol", "medium"],
        ["codex", "gpt-5.6-terra", None],
    ]
    live, live_cells, dead_notes = lc.live_from(_good_liveness(), _good_needed())
    assert (live, live_cells, dead_notes) == (expected_live, expected_cells, [])


@pytest.mark.parametrize(
    "liveness,needed",
    [
        (_good_liveness(), {"codex": [], "cursor": []}),
        (_aug15_liveness(), {"codex": [["gpt-5.6-sol", "xhigh"], ["gpt-5.6-terra", "high"]]}),
        (_good_liveness(), {"cursor": [["grok", None]]}),
        (_good_liveness(), {"codex": "not-a-list"}),
        (
            {
                "codex": {
                    "live": True,
                    "models": {"m": {"ok": True, "detail": "x"}},
                    "cells": [{"model": "m", "effort": None, "ok": True, "detail": "x"}],
                },
                "claude": {"live": True, "models": {}, "cells": []},
            },
            {"codex": ["not-a-pair"]},
        ),
        ({}, {"codex": [["gpt-m", {"effort": "high"}]]}),
        (
            {
                "codex": {
                    "models": {},
                    "cells": [{"model": "m", "effort": [], "ok": True}],
                },
            },
            {"codex": [["m", None]]},
        ),
        (
            _good_liveness(),
            {"codex": [["gpt-5.6-sol", "medium"], ["missing", "high"]]},
        ),
        (
            {
                "codex": {
                    "live": True,
                    "models": {"m": {"ok": "true", "detail": ""}},
                    "cells": [{"model": "m", "effort": None, "ok": "true", "detail": ""}],
                },
            },
            {"codex": [["m", None]]},
        ),
        (_good_liveness(), {"codex": [[{"a": 1}, None]]}),
        (
            {
                "codex": {
                    "models": {},
                    "cells": [
                        {"model": "m", "effort": None, "ok": True},
                        {"model": "m", "effort": "high", "ok": True},
                    ],
                },
            },
            {"codex": [["m", None], ["m", "high"]]},
        ),
        (
            {
                "codex": {
                    "live": True,
                    "models": {"m": {"ok": False, "detail": "down"}},
                    "cells": [{"model": "m", "effort": None, "ok": False, "detail": "down"}],
                },
            },
            {"codex": [["m", None]]},
        ),
        ("not-a-dict", {"codex": [["m", None]]}),
    ],
)
def test_live_from_census_every_needed_slot_live_or_disclosed(liveness, needed):
    """Every non-claude needed slot is either live or has a disclosure note."""
    live_vendors, live_cells, dead_notes = lc.live_from(liveness, needed)
    if not isinstance(needed, dict):
        assert live_vendors == ["claude"]
        assert live_cells == []
        assert dead_notes == []
        return
    expected_slots = _count_non_claude_needed_slots(needed)
    assert len(live_cells) + len(dead_notes) == expected_slots


def test_live_from_dead_note_reason_bounded():
    long_detail = "x" * 500
    liveness = {
        "codex": {
            "live": False,
            "models": {"m": {"ok": False, "detail": long_detail}},
            "cells": [{"model": "m", "effort": None, "ok": False, "detail": long_detail}],
        },
    }
    _, _, dead_notes = lc.live_from(liveness, {"codex": [["m", None]]})
    assert len(dead_notes) == 1
    reason = dead_notes[0]["reason"]
    assert len(reason) < 500
    assert "\u2026" in reason or len(lc._bounded_reason(long_detail)) <= 200


def test_live_from_edge_empty_or_non_list_entries():
    live, _, notes = lc.live_from(_good_liveness(), {"codex": []})
    assert "codex" not in live
    assert len(notes) == 1
    assert "no needed cell is reachable" in notes[0]["reason"]

    live2, _, notes2 = lc.live_from(_good_liveness(), {"codex": {"m": "high"}})
    assert "codex" not in live2
    assert len(notes2) == 1
    assert "no needed cell is reachable" in notes2[0]["reason"]


def test_live_from_edge_malformed_entry():
    live, _, notes = lc.live_from(_good_liveness(), {"codex": ["not-a-pair"]})
    assert "codex" not in live
    assert len(notes) == 1
    assert notes[0]["model"] is None
    assert "needed slot 0 has malformed cell entry" in notes[0]["reason"]


def test_live_from_edge_unhashable_entry_members():
    live, _, notes = lc.live_from(_good_liveness(), {"codex": [[{"a": 1}, None]]})
    assert "codex" not in live
    assert len(notes) == 1
    assert notes[0]["model"] is None
    assert "needed slot 0 model is not a string" in notes[0]["reason"]


def test_live_from_edge_malformed_liveness():
    need = {"codex": [["m", None]], "cursor": [["g", None]]}
    live, live_cells, notes = lc.live_from("not-a-dict", need)
    assert "codex" not in live
    assert "cursor" not in live
    assert live_cells == []
    assert len(notes) == 2


def test_live_from_edge_non_bool_ok():
    liv = {
        "codex": {
            "live": True,
            "models": {"m": {"ok": "true", "detail": ""}},
            "cells": [{"model": "m", "effort": None, "ok": "true", "detail": ""}],
        },
    }
    live, _, notes = lc.live_from(liv, {"codex": [["m", None]]})
    assert "codex" not in live
    assert len(notes) == 1


def test_live_from_edge_needed_not_dict():
    live, live_cells, notes = lc.live_from(_good_liveness(), "not-a-dict")
    assert live == ["claude"]
    assert live_cells == []
    assert notes == []


def test_live_from_edge_duplicate_model_effort_slots():
    """Duplicate (model, effort) in one vendor: multiset reconcile, deterministic."""
    liv = _good_liveness()
    need = {"codex": [["gpt-5.6-sol", "medium"], ["gpt-5.6-sol", "medium"]]}
    live, live_cells, notes = lc.live_from(liv, need)
    assert "codex" in live
    assert len(live_cells) == 2
    assert notes == []
