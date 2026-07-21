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
    """Content-hash identity for CAS. None for a None snapshot."""
    if snapshot is None:
        return None
    return store_core.short_hash(json.dumps(snapshot, sort_keys=True))


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


def _parse_ledger_block(text):
    """Extract the guardian-ledger fenced JSON block from ledger.md text."""
    if not text:
        return None, "empty"
    m = _LEDGER_BLOCK.search(text)
    if not m:
        return None, "no-block"
    try:
        return json.loads(m.group(1)), None
    except ValueError:
        return None, "bad-json"


def read_ledger(cwd, root=None):
    """Read-only parse of ledger.md → {records, byId, status, note}.

    Malformed or newer-version ledgers NEVER suppress findings — status reflects
    the failure but records/byId are empty so callers surface everything."""
    path = ledger_path(cwd, root)
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return {"records": [], "byId": {}, "status": "absent", "note": None}

    block, err = _parse_ledger_block(text)
    if err == "bad-json":
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger JSON block is malformed",
        }
    if err in ("empty", "no-block"):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger has no %s fenced block" % LEDGER_FENCE,
        }

    ver = block.get("schemaVersion")
    if isinstance(ver, int) and not isinstance(ver, bool) and ver > LEDGER_SCHEMA_VERSION:
        return {
            "records": [],
            "byId": {},
            "status": "newer",
            "note": "ledger schemaVersion=%s is newer than %s"
                     % (ver, LEDGER_SCHEMA_VERSION),
        }

    raw_records = block.get("records")
    if not isinstance(raw_records, list):
        return {
            "records": [],
            "byId": {},
            "status": "malformed",
            "note": "ledger records is not a list",
        }

    records = []
    by_id = {}
    for rec in raw_records:
        if not isinstance(rec, dict):
            continue
        if not all(rec.get(f) is not None for f in LEDGER_MIN_FIELDS):
            continue
        if rec.get("disposition") not in guardian_lens.FINDING_STATES:
            continue
        records.append(rec)
        by_id[rec["id"]] = rec

    return {"records": records, "byId": by_id, "status": "ok", "note": None}


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
