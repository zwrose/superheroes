#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_store.py
"""Guardian storage layout SSOT + snapshot & ledger I/O (read-only ledger in this order).

Stdlib-only. The single home for guardian artifact paths, schema keys, and snapshot CAS.
"""
import argparse
import json
import os
import re
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import core_md      # noqa: E402
import file_lock    # noqa: E402
import guardian_lens  # noqa: E402
import store_core   # noqa: E402

LAYOUT = {
    "report": "report.md",
    "snapshot": "latest.json",
    "ledger": "ledger.md",
    "vitals": "vitals.jsonl",
}
SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_KEYS = ("schemaVersion", "sweptSha", "vitals", "lenses")
LEDGER_SCHEMA_VERSION = 1
LEDGER_FENCE = "guardian-ledger"
LEDGER_MIN_FIELDS = ("id", "disposition")
SWEEP_LOCK = ".sweep.lock"
SWEEP_LOCK_TTL = 120

_LEDGER_BLOCK = re.compile(
    r"```json\s+" + re.escape(LEDGER_FENCE) + r"\s*\n(.*?)\n```", re.DOTALL)


class UnknownSnapshotVersion(Exception):
    pass


def guardian_layer_path(cwd, root=None):
    """Mode-aware path to guardian.md, co-located with core.md."""
    return core_md.layer_path(cwd, "guardian", root)


def guardian_dir(cwd, root=None):
    """The guardian artifact subdir beside core.md."""
    return os.path.join(os.path.dirname(core_md.core_path(cwd, root)), "guardian")


def report_path(cwd, root=None):
    return os.path.join(guardian_dir(cwd, root), LAYOUT["report"])


def snapshot_path(cwd, root=None):
    return os.path.join(guardian_dir(cwd, root), LAYOUT["snapshot"])


def ledger_path(cwd, root=None):
    return os.path.join(guardian_dir(cwd, root), LAYOUT["ledger"])


def vitals_path(cwd, root=None):
    return os.path.join(guardian_dir(cwd, root), LAYOUT["vitals"])


def sweep_lock_path(cwd, root=None):
    return os.path.join(guardian_dir(cwd, root), SWEEP_LOCK)


def snapshot_identity(snapshot):
    """Content-hash identity for CAS. None for a None snapshot.

    Hashes only the SNAPSHOT_KEYS projection so non-identity fields on disk
    (e.g. sweepId persisted beside the baseline) do not change the identity.
    Current snapshots contain exactly SNAPSHOT_KEYS, so existing identities
    are unchanged.
    """
    if snapshot is None:
        return None
    projected = {k: snapshot.get(k) for k in SNAPSHOT_KEYS}
    return store_core.short_hash(json.dumps(projected, sort_keys=True))


def read_snapshot(cwd, root=None):
    """Read latest.json → dict or None. Malformed → None + stderr breadcrumb.
    A schemaVersion newer than SNAPSHOT_SCHEMA_VERSION raises UnknownSnapshotVersion."""
    path = snapshot_path(cwd, root)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        return None
    except ValueError:
        sys.stderr.write("guardian_store: malformed snapshot JSON at %s\n" % path)
        return None
    if not isinstance(data, dict):
        sys.stderr.write("guardian_store: snapshot is not an object at %s\n" % path)
        return None
    ver = data.get("schemaVersion")
    if isinstance(ver, int) and not isinstance(ver, bool) and ver > SNAPSHOT_SCHEMA_VERSION:
        raise UnknownSnapshotVersion(
            "snapshot schemaVersion=%s is newer than %s"
            % (ver, SNAPSHOT_SCHEMA_VERSION))
    return data


def write_snapshot_cas(cwd, next_snapshot, expected_prev_identity, root=None):
    """Compare-and-swap write of latest.json under the sweep lock."""
    lock_path = sweep_lock_path(cwd, root)
    try:
        file_lock.acquire(lock_path, ttl=SWEEP_LOCK_TTL)
    except file_lock.LockHeld as exc:
        return {"ok": False, "reason": "raced", "lockHeld": exc.holder}
    try:
        current = read_snapshot(cwd, root)
        on_disk = snapshot_identity(current)
        if on_disk != expected_prev_identity:
            return {
                "ok": False,
                "reason": "raced",
                "onDisk": on_disk,
                "expected": expected_prev_identity,
            }
        path = snapshot_path(cwd, root)
        store_core.atomic_write(path, json.dumps(next_snapshot, indent=2) + "\n")
        return {"ok": True, "path": path}
    finally:
        file_lock.release(lock_path)


def atomic_write_bytes(path, data, tmp_prefix=".guardian-store."):
    """Binary atomic write — round-trips bytes exactly (no newline translation)."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("atomic_write_bytes requires bytes")
    d = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=tmp_prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def find_ledger_fences(text):
    """All guardian-ledger fenced-block matches in document order."""
    if not text:
        return []
    return list(_LEDGER_BLOCK.finditer(text))


def ledger_fence_identity(text):
    """Content-hash identity of the sole guardian-ledger fence. None if absent/ambiguous.

    Mirrors `snapshot_identity`: callers capture this at the read that produced the
    records, then pass it to the writer for compare-and-swap."""
    matches = find_ledger_fences(text)
    if len(matches) != 1:
        return None
    return store_core.short_hash(matches[0].group(0))


def _parse_ledger_block(text):
    """Extract the guardian-ledger fenced JSON block from ledger.md text.

    Exactly one fence is required. Zero → no-block/empty; more than one → ambiguous.
    Never silently prefers the first of several competing blocks."""
    if not text:
        return None, "empty"
    matches = find_ledger_fences(text)
    if not matches:
        return None, "no-block"
    if len(matches) > 1:
        return None, "ambiguous"
    try:
        return json.loads(matches[0].group(1)), None
    except ValueError:
        return None, "bad-json"


def read_ledger(cwd, root=None):
    """Read-only parse of ledger.md → {records, byId, status, note}.

    Malformed, newer, unreadable, or partially-valid ledgers NEVER suppress via
    missing data alone — status reflects the failure. An unreadable ledger is
    opaque, not empty: `records: []` never means "safe to rewrite as blank."

    Only a genuinely absent path returns status `absent`. Every other read
    failure is `unreadable`. Invalid records (failing the shared writer
    validator) are excluded from `records`/`byId` and surface as `partial`.

    `schemaVersion` must be a non-bool int exactly equal to LEDGER_SCHEMA_VERSION
    for status `ok`; a greater int is `newer`; anything else is `malformed`.

    Total type validation: a block that is not a dict is malformed (never
    AttributeError); a record whose id is not a non-empty str is skipped (never
    TypeError on byId); duplicate ids are ambiguous and never suppress."""
    # Lazy import: guardian_ledger imports this module at load time.
    import guardian_ledger as gled  # noqa: E402

    path = ledger_path(cwd, root)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        # Only a genuinely non-existent path is absent. If the path still
        # lexists (permissions race, dangling weirdness), treat as unreadable.
        if os.path.lexists(path):
            return {
                "records": [],
                "byId": {},
                "status": "unreadable",
                "note": "ledger path exists but could not be read (FileNotFoundError)",
                "fenceIdentity": None,
            }
        return {
            "records": [], "byId": {}, "status": "absent", "note": None,
            "fenceIdentity": None,
        }
    except OSError as exc:
        return {
            "records": [],
            "byId": {},
            "status": "unreadable",
            "note": "ledger exists but could not be read (%s)" % type(exc).__name__,
            "fenceIdentity": None,
        }

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "records": [],
            "byId": {},
            "status": "unreadable",
            "note": "ledger exists but is not valid UTF-8",
            "fenceIdentity": None,
        }

    fence_identity = ledger_fence_identity(text)
    block, err = _parse_ledger_block(text)
    if err == "ambiguous":
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger has multiple %s fenced blocks (ambiguous)" % LEDGER_FENCE,
            "fenceIdentity": None,
        }
    if err == "bad-json":
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger JSON block is malformed",
            "fenceIdentity": fence_identity,
        }
    if err in ("empty", "no-block"):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger has no %s fenced block" % LEDGER_FENCE,
            "fenceIdentity": None,
        }

    # Hand-edited ledgers can parse to a list/string/number — never .get on those.
    if not isinstance(block, dict):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger block is not an object (got %s)" % type(block).__name__,
            "fenceIdentity": fence_identity,
        }

    ver = block.get("schemaVersion")
    # ok requires a non-bool int exactly equal to LEDGER_SCHEMA_VERSION. Missing,
    # string, bool, zero, negative, or any other shape is malformed; only a future
    # int is newer. (bool is a subclass of int — reject it explicitly.)
    if isinstance(ver, int) and not isinstance(ver, bool) and ver > LEDGER_SCHEMA_VERSION:
        return {
            "records": [],
            "byId": {},
            "status": "newer",
            "note": "ledger schemaVersion=%s is newer than %s"
                     % (ver, LEDGER_SCHEMA_VERSION),
            "fenceIdentity": fence_identity,
        }
    if not (isinstance(ver, int) and not isinstance(ver, bool)
            and ver == LEDGER_SCHEMA_VERSION):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger schemaVersion must be int %s (got %r)"
                     % (LEDGER_SCHEMA_VERSION, ver),
            "fenceIdentity": fence_identity,
        }

    raw_records = block.get("records")
    if not isinstance(raw_records, list):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger records is not a list",
            "fenceIdentity": fence_identity,
        }

    if "sweeps" in block and not isinstance(block.get("sweeps"), list):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger sweeps is not a list",
            "fenceIdentity": fence_identity,
        }

    records = []
    by_id = {}
    duplicates = set()
    skipped_invalid = 0
    bad_sweeps = 0
    for rec in raw_records:
        if not isinstance(rec, dict):
            skipped_invalid += 1
            continue
        if not all(rec.get(f) is not None for f in LEDGER_MIN_FIELDS):
            skipped_invalid += 1
            continue
        if rec.get("disposition") not in guardian_lens.FINDING_STATES:
            skipped_invalid += 1
            continue
        rid = rec.get("id")
        # Unhashable / empty ids must never reach byId (TypeError: unhashable type).
        if not isinstance(rid, str) or not rid.strip():
            skipped_invalid += 1
            continue
        ok, _reasons = gled.validate_record(rec)
        if not ok:
            # Preserve on disk (caller must not rewrite); exclude from byId so a
            # typo cannot mute detection. Partial ledgers disable suppression in
            # collect so a dropped invalid sibling cannot make a collision look unique.
            skipped_invalid += 1
            continue
        records.append(rec)
        if rid in duplicates:
            continue
        if rid in by_id:
            duplicates.add(rid)
            by_id.pop(rid, None)
            continue
        by_id[rid] = rec

    raw_sweeps = block.get("sweeps")
    if isinstance(raw_sweeps, list):
        for entry in raw_sweeps:
            if not isinstance(entry, dict):
                bad_sweeps += 1

    notes = []
    if duplicates:
        notes.append(
            "duplicate ids make suppression ambiguous (not suppressing): %s"
            % ", ".join(sorted(duplicates)))
    if skipped_invalid:
        notes.append(
            "skipped %d invalid or incomplete record(s) (excluded from byId; "
            "on-disk bytes must not be rewritten)" % skipped_invalid)
    if bad_sweeps:
        notes.append(
            "skipped %d invalid sweeps entr%s (on-disk bytes must not be rewritten)"
            % (bad_sweeps, "y" if bad_sweeps == 1 else "ies"))
    status = "ok"
    if skipped_invalid or duplicates or bad_sweeps:
        status = "partial"
    return {
        "records": records,
        "byId": by_id,
        "status": status,
        "note": "; ".join(notes) if notes else None,
        "fenceIdentity": fence_identity,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="guardian storage layout + I/O")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("paths", help="resolved guardian artifact paths")
    pp.add_argument("--cwd", default=".")
    pp.add_argument("--root", default=None)
    rs = sub.add_parser("read-snapshot")
    rs.add_argument("--cwd", default=".")
    rs.add_argument("--root", default=None)
    rl = sub.add_parser("read-ledger")
    rl.add_argument("--cwd", default=".")
    rl.add_argument("--root", default=None)
    args = ap.parse_args(argv)
    cwd = args.cwd
    root = args.root
    try:
        if args.cmd == "paths":
            out = {
                "report": report_path(cwd, root),
                "snapshot": snapshot_path(cwd, root),
                "ledger": ledger_path(cwd, root),
                "layer": guardian_layer_path(cwd, root),
                "guardianDir": guardian_dir(cwd, root),
            }
        elif args.cmd == "read-snapshot":
            out = read_snapshot(cwd, root)
        else:
            out = read_ledger(cwd, root)
    except Exception as exc:
        out = {"error": str(exc)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
