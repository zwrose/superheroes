"""Short-TTL cache for composition liveness receipts (issue #610).

Fail-closed: the cache may only skip re-probing recent liveness; it must never turn
absence, failure, or corruption into a false \"live\". `write` stores `now` as the probe
START time (caller responsibility).
"""
import json
import math
import os
import tempfile
from collections import Counter

import mode_registry

# Bump when probe configuration semantics change so legacy receipts cannot be
# reused (#711: effort is now enforced per (model, effort) pair; v1 receipts
# recorded effort the old probe never actually dispatched; #795: v2 receipts
# carry no per-cell evidence and are refused rather than read as vendor-level truth).
SCHEMA_VERSION = 3
DEFAULT_TTL_SECONDS = 600
_ENV_TTL = "SUPERHEROES_LIVENESS_TTL_SECONDS"

# probed = per-cell probe evidence (fresh or TTL-cached); synthesized = derived from a
# vendor-level rollup, never probed per cell; unprobed = no probe evidence of any kind exists
# and the cells carry no verification weight. `unprobed` has had no live producer since the
# cache-only receipt-only path was reaped (#1138); it stays in the vocabulary because seat maps
# are persisted and re-read, and a map written by an older plugin version must keep reading as
# unusable evidence in `seat_map._resolvable_families_for_seat`.
LIVE_CELLS_SOURCE_PROBED = "probed"
LIVE_CELLS_SOURCE_SYNTHESIZED = "synthesized"
LIVE_CELLS_SOURCE_UNPROBED = "unprobed"
LIVE_CELLS_SOURCES = (
    LIVE_CELLS_SOURCE_PROBED,
    LIVE_CELLS_SOURCE_SYNTHESIZED,
    LIVE_CELLS_SOURCE_UNPROBED,
)


def ttl_seconds():
    """Reader TTL in seconds; env override when a positive int, else default. Never raises."""
    try:
        raw = os.environ.get(_ENV_TTL)
        if raw is None:
            return DEFAULT_TTL_SECONDS
        val = int(raw)
        if val > 0:
            return val
    except (TypeError, ValueError):
        pass
    return DEFAULT_TTL_SECONDS


def receipt_path(cwd=None, root=None):
    return os.path.join(
        mode_registry.project_store_dir(cwd, root),
        "state",
        "composition-liveness.json",
    )


def _normalize_needed(needed):
    out = {}
    if not isinstance(needed, dict):
        return out
    for vendor, entries in needed.items():
        norm = []
        if isinstance(entries, (list, tuple)):
            for entry in entries:
                if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                    model = entry[0]
                    effort = entry[1] if len(entry) > 1 else None
                    norm.append([model, effort])
        out[vendor] = norm
    return out


def _reject_constant(_tok):
    raise ValueError("non-finite JSON constant")


def _is_timestamp(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _bounded_reason(detail):
    if not detail or not isinstance(detail, str):
        return "no probe evidence recorded"
    collapsed = " ".join(detail.split())
    if len(collapsed) <= 200:
        return collapsed
    return collapsed[:200] + "\u2026"


def _liveness_structure_valid(liveness):
    if not isinstance(liveness, dict):
        return False
    for _vendor, info in liveness.items():
        if not isinstance(info, dict):
            return False
        models = info.get("models")
        if not isinstance(models, dict):
            return False
        for _model, entry in models.items():
            if not isinstance(entry, dict):
                return False
            if type(entry.get("ok")) is not bool:
                return False
        cells = info.get("cells")
        # axis: malformed per-cell evidence is refused (non-list cells)
        if not isinstance(cells, list):
            return False
        for cell in cells:
            if not isinstance(cell, dict):
                return False
            if not isinstance(cell.get("model"), str):
                return False
            # axis: malformed per-cell evidence is refused (non-bool ok)
            if type(cell.get("ok")) is not bool:
                return False
            effort = cell.get("effort")
            if effort is not None and not isinstance(effort, str):
                return False
    return True


def _read_newest_wins_existing(path, now):
    """Load a fresh receipt for newest-wins compare; None if missing/invalid/stale."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh, parse_constant=_reject_constant)
        if not isinstance(raw, dict):
            return None
        probed_at = raw.get("probedAt")
        if not _is_timestamp(probed_at):
            return None
        return read(path, now=max(float(now), float(probed_at)))
    except Exception:
        return None


def write(liveness, needed, *, path, now, ttl=None):
    """Atomically write a liveness receipt. Returns True on success, False on any failure.

    Best-effort newest-probedAt-wins: if a fresh receipt already exists with probedAt at least
    as new as this probe's start (``now``), the write is skipped and True is returned so an
    older probe cannot clobber a newer one. A residual TOCTOU window remains; it is bounded by
    the short TTL and downstream dispatch fall-open behavior.
    """
    try:
        existing = _read_newest_wins_existing(path, now)
        if existing is not None:
            existing_at = existing.get("probedAt")
            if _is_timestamp(existing_at) and float(existing_at) >= float(now):
                return True
        payload = {
            "schemaVersion": SCHEMA_VERSION,
            "probedAt": float(now),
            "ttl": int(ttl) if ttl is not None else DEFAULT_TTL_SECONDS,
            "needed": _normalize_needed(needed),
            "liveness": liveness,
        }
        text = json.dumps(payload, sort_keys=True) + "\n"
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".composition-liveness-", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
            tmp = None
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        return True
    except Exception:
        return False


def read(path, *, now):
    """Return a validated receipt dict, or None on any problem. Never raises."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh, parse_constant=_reject_constant)
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("schemaVersion") != SCHEMA_VERSION:
        return None
    probed_at = raw.get("probedAt")
    if not _is_timestamp(probed_at):
        return None
    if probed_at > now:
        return None
    if (now - probed_at) >= ttl_seconds():
        return None
    if not isinstance(raw.get("liveness"), dict):
        return None
    if not isinstance(raw.get("needed"), dict):
        return None
    # axis: refusal of a receipt lacking per-cell evidence
    if not _liveness_structure_valid(raw["liveness"]):
        return None
    return raw


def covers(receipt_needed, needed):
    """True iff every (vendor, model, effort) in needed appears in receipt_needed."""
    try:
        if not isinstance(receipt_needed, dict) or not isinstance(needed, dict):
            return False
        if not needed:
            return True

        def _pairs_for_vendor(entries):
            pairs = set()
            if not isinstance(entries, (list, tuple)):
                raise ValueError("bad entries")
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) < 1:
                    raise ValueError("bad entry")
                model = entry[0]
                effort = entry[1] if len(entry) > 1 else None
                pairs.add((model, effort))
            return pairs

        for vendor, need_entries in needed.items():
            if vendor not in receipt_needed:
                return False
            need_pairs = _pairs_for_vendor(need_entries)
            rec_pairs = _pairs_for_vendor(receipt_needed[vendor])
            if not need_pairs.issubset(rec_pairs):
                return False
        return True
    except Exception:
        return False


_UNKEYABLE = object()


def _slot_key_from_cell(cell):
    """Return (model, effort) or _UNKEYABLE. Never raises."""
    if not isinstance(cell, dict):
        return _UNKEYABLE
    model = cell.get("model")
    if not isinstance(model, str):
        return _UNKEYABLE
    effort = cell.get("effort")
    try:
        hash((model, effort))
    except TypeError:
        return _UNKEYABLE
    return (model, effort)


def _cells_by_key(info):
    out = {}
    if not isinstance(info, dict):
        return out
    try:
        cells = info.get("cells")
    except Exception:
        return out
    if not isinstance(cells, list):
        return out
    for cell in cells:
        key = _slot_key_from_cell(cell)
        if key is _UNKEYABLE:
            continue
        out[key] = cell
    return out


def _dead_cell_note(vendor, model, effort, detail):
    return {
        "constraint": "liveness-cell",
        "vendor": vendor,
        "model": model,
        "effort": effort,
        "reason": "%s/%s (%s) not live per cached liveness: %s"
        % (vendor, model, effort, _bounded_reason(detail)),
    }


def _liveness_read_error_note(detail, stage=None):
    if stage == "cell-evidence":
        prefix = "liveness read failed during cell-evidence scan"
    elif stage == "reconcile":
        prefix = "liveness read failed during inventory reconcile"
    else:
        prefix = "liveness read failed"
    return {
        "constraint": "liveness-read-error",
        "reason": "%s: %s" % (prefix, _bounded_reason(detail)),
    }


def _slot_key_from_entry(entry):
    """Return (model, effort) or _UNKEYABLE. Never raises."""
    if not isinstance(entry, (list, tuple)) or len(entry) < 1:
        return _UNKEYABLE
    model = entry[0]
    if not isinstance(model, str):
        return _UNKEYABLE
    effort = entry[1] if len(entry) > 1 else None
    try:
        hash((model, effort))
    except TypeError:
        return _UNKEYABLE
    return (model, effort)


def _build_needed_inventory(needed):
    """Per-vendor positional slot inventory from needed. Never raises."""
    inventory = {}
    if not isinstance(needed, dict):
        return inventory
    for vendor, entries in needed.items():
        if vendor == "claude":
            continue
        if not isinstance(entries, (list, tuple)) or len(entries) == 0:
            inventory[vendor] = None
            continue
        inventory[vendor] = [
            (i, entry, _slot_key_from_entry(entry))
            for i, entry in enumerate(entries)
        ]
    return inventory


def _cell_is_live(cells_by_key, key):
    """Total per-cell read: True only when evidence exists with ok is True."""
    if key is _UNKEYABLE:
        return False
    cell = cells_by_key.get(key)
    if not isinstance(cell, dict):
        return False
    return cell.get("ok") is True


def _cell_detail(cells_by_key, key):
    if key is _UNKEYABLE:
        return None
    cell = cells_by_key.get(key)
    if not isinstance(cell, dict):
        return None
    return cell.get("detail")


def _safe_vendor_info(liveness, vendor):
    """Total read of per-vendor liveness info. Never raises."""
    try:
        if isinstance(liveness, dict):
            return liveness.get(vendor)
    except Exception:
        pass
    return None


def _unreachable_vendor_note(vendor):
    return {
        "constraint": "liveness-cell",
        "vendor": vendor,
        "model": None,
        "effort": None,
        "reason": "%s not live: no needed cell is reachable for it" % vendor,
    }


def _unkeyable_slot_note(vendor, slot_index):
    return {
        "constraint": "liveness-cell",
        "vendor": vendor,
        "model": None,
        "effort": None,
        "reason": "%s not live: needed slot %d has malformed cell entry" % (vendor, slot_index),
    }


def _non_string_model_note(vendor, slot_index):
    return {
        "constraint": "liveness-cell",
        "vendor": vendor,
        "model": None,
        "effort": None,
        "reason": "%s not live: needed slot %d model is not a string" % (vendor, slot_index),
    }


def _live_cell_sort_key(cell):
    if not isinstance(cell, (list, tuple)) or len(cell) < 3:
        return ("", "", (False, ""))
    vendor, model, effort = cell[0], cell[1], cell[2]
    return (
        vendor,
        model,
        (effort is not None, str(effort) if effort is not None else ""),
    )


def _reconcile_inventory(inventory, live_cells, liveness, dead_notes, live):
    """Emit dead-cell notes for every inventory gap; append live vendors."""
    available = Counter(tuple(cell) for cell in live_cells)
    for vendor, slots in inventory.items():
        if slots is None:
            dead_notes.append(_unreachable_vendor_note(vendor))
            continue
        info = _safe_vendor_info(liveness, vendor)
        cells_by_key = _cells_by_key(info)
        vendor_live = True
        for slot_index, entry, key in slots:
            if key is _UNKEYABLE:
                vendor_live = False
                if (
                    isinstance(entry, (list, tuple))
                    and len(entry) >= 1
                    and not isinstance(entry[0], str)
                ):
                    dead_notes.append(_non_string_model_note(vendor, slot_index))
                else:
                    dead_notes.append(_unkeyable_slot_note(vendor, slot_index))
                continue
            model, effort = key
            cell_key = (vendor, model, effort)
            if available[cell_key] > 0:
                available[cell_key] -= 1
                continue
            vendor_live = False
            dead_notes.append(
                _dead_cell_note(vendor, model, effort, _cell_detail(cells_by_key, key))
            )
        if vendor_live:
            live.append(vendor)


def live_from(liveness, needed):
    """-> (live_vendors, live_cells, dead_notes). The ONE place a liveness verdict is read."""
    live = []
    live_cells = []
    dead_notes = []
    if not isinstance(liveness, dict):
        liveness = {}
    if not isinstance(needed, dict):
        needed = {}

    inventory = _build_needed_inventory(needed)

    loop_error = None
    reconcile_error = None
    try:
        for vendor, slots in inventory.items():
            if slots is None:
                continue
            info = _safe_vendor_info(liveness, vendor)
            cells_by_key = _cells_by_key(info)
            for _slot_index, _entry, key in slots:
                if key is _UNKEYABLE:
                    continue
                if _cell_is_live(cells_by_key, key):
                    model, effort = key
                    live_cells.append([vendor, model, effort])
    except Exception as exc:
        loop_error = exc
    if loop_error is not None:
        dead_notes.append(_liveness_read_error_note(str(loop_error), stage="cell-evidence"))
    try:
        _reconcile_inventory(inventory, live_cells, liveness, dead_notes, live)
    except Exception as exc:
        reconcile_error = exc
    if reconcile_error is not None:
        dead_notes.append(_liveness_read_error_note(str(reconcile_error), stage="reconcile"))

    if "claude" not in live:
        live.append("claude")
    live_cells.sort(key=_live_cell_sort_key)
    return (sorted(live), live_cells, dead_notes)


def live_vendors_from(liveness, needed):
    """Recompute live vendors from cached per-model oks; claude is always live."""
    live, _cells, dead_notes = live_from(liveness, needed)
    return (live, dead_notes)
