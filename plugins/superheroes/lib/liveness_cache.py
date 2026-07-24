"""Short-TTL cache for composition liveness receipts (issue #610).

Fail-closed: the cache may only skip re-probing recent liveness; it must never turn
absence, failure, or corruption into a false \"live\". `write` stores `now` as the probe
START time (caller responsibility).
"""
import json
import math
import os
import tempfile

import mode_registry

SCHEMA_VERSION = 1
DEFAULT_TTL_SECONDS = 600
_ENV_TTL = "SUPERHEROES_LIVENESS_TTL_SECONDS"


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
    if not _liveness_structure_valid(raw["liveness"]):
        return None
    return raw


def covers(receipt_needed, needed):
    """True iff every (vendor, model) in needed appears in receipt_needed (effort ignored)."""
    try:
        if not isinstance(receipt_needed, dict) or not isinstance(needed, dict):
            return False
        if not needed:
            return True

        def _models_for_vendor(entries):
            models = set()
            if not isinstance(entries, (list, tuple)):
                raise ValueError("bad entries")
            for entry in entries:
                if not isinstance(entry, (list, tuple)) or len(entry) < 1:
                    raise ValueError("bad entry")
                models.add(entry[0])
            return models

        for vendor, need_entries in needed.items():
            if vendor not in receipt_needed:
                return False
            need_models = _models_for_vendor(need_entries)
            rec_models = _models_for_vendor(receipt_needed[vendor])
            if not need_models.issubset(rec_models):
                return False
        return True
    except Exception:
        return False


def live_vendors_from(liveness, needed):
    """Recompute live vendors from cached per-model oks; claude is always live."""
    live = []
    dead_notes = []
    try:
        if not isinstance(liveness, dict):
            liveness = {}
        if not isinstance(needed, dict):
            needed = {}

        for vendor, entries in needed.items():
            if vendor == "claude":
                continue
            if not isinstance(entries, (list, tuple)) or len(entries) == 0:
                dead_notes.append({
                    "constraint": "liveness-cache",
                    "reason": "%s not live per cached liveness" % vendor,
                })
                continue
            vendor_live = True
            info = liveness.get(vendor)
            if not isinstance(info, dict):
                vendor_live = False
            else:
                models = info.get("models")
                if not isinstance(models, dict):
                    vendor_live = False
                else:
                    for entry in entries:
                        if not isinstance(entry, (list, tuple)) or len(entry) < 1:
                            vendor_live = False
                            break
                        m = entry[0]
                        ent = models.get(m)
                        if not isinstance(ent, dict) or ent.get("ok") is not True:
                            vendor_live = False
                            break
            if vendor_live:
                live.append(vendor)
            else:
                dead_notes.append({
                    "constraint": "liveness-cache",
                    "reason": "%s not live per cached liveness" % vendor,
                })
    except Exception:
        pass
    if "claude" not in live:
        live.append("claude")
    return (sorted(live), dead_notes)
