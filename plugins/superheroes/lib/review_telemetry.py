#!/usr/bin/env python3
"""Local telemetry record for the shared review loop."""
import argparse
import hashlib
import json
import os
import tempfile


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".review-telemetry-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        return {"ok": True}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "write-failed", "detail": str(exc)}


def build_record(rounds, expected_leaves, usage, benchmark=False, terminal=None):
    expected = list(expected_leaves or [])
    usage = usage or {}
    missing = [leaf for leaf in expected if leaf not in usage]
    total = sum(int((usage.get(leaf) or {}).get("total") or 0) for leaf in expected if leaf in usage)
    complete = len(missing) == 0
    dimension_counts = {}
    for rec in rounds or []:
        for name, dim in (rec.get("dimensions") or {}).items():
            counts = dimension_counts.setdefault(name, {"run": 0, "skipped": 0, "cheap": 0, "deep": 0, "escalated": 0})
            status = dim.get("status")
            if status == "skipped":
                counts["skipped"] += 1
            elif status == "run":
                counts["run"] += 1
            tier = dim.get("tier")
            if tier == "reviewer":
                counts["cheap"] += 1
            elif tier == "reviewer-deep":
                counts["deep"] += 1
            if dim.get("escalated"):
                counts["escalated"] += 1
    # D3: no `rounds` embed — the round history's durable home is round-records.json (skeletons);
    # duplicating it here doubled the storage and nothing ever read telemetry rounds back
    # (the eval reads tokenUsage.total; the readout reads the summary scalars).
    return {
        "schemaVersion": 1,
        "terminal": terminal,
        "roundCount": len(rounds or []),
        "tokenUsage": {
            "complete": complete,
            "expectedLeaves": expected,
            "present": sorted([leaf for leaf in expected if leaf in usage]),
            "missing": missing,
            "total": total,
        },
        "dimensionCounts": dimension_counts,
        "benchmarkValid": bool(complete or not benchmark),
    }


def _current_hash(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return content_hash(fh.read())
    except FileNotFoundError:
        return content_hash("")


def write_record(path, record, expected_hash=None, run_id=None, lease=None):
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if expected_hash and _current_hash(path) != expected_hash:
        return {"ok": False, "reason": "stale"}
    record = dict(record)
    record["runId"] = run_id
    if lease:
        record["lease"] = lease
    return _atomic_write(path, json.dumps(record, indent=2) + "\n")


def _load_rounds(records_path):
    """Read the loop's round records from disk via review_memory's canonical reader.
    Missing file -> ok with [] (early terminals finalize before any round persisted);
    corrupt -> fail-closed."""
    import sys
    lib_dir = os.path.dirname(os.path.abspath(__file__))
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    import review_memory
    return review_memory.load_records_state(records_path, [])


def write_from_records(path, records_path, expected_leaves, usage, terminal=None,
                       benchmark=False, expected_hash=None, run_id=None, lease=None):
    """Compose + write the telemetry record with the per-round scalars (roundCount,
    dimensionCounts) derived from round-records.json ON DISK — round data never rides the
    courier pipe inline (live 2026-07-02: the inline --payload-json with every round embedded
    was courier-mangled). The written record is already the SMALL summary (D3: no rounds
    embed), and the same summary is returned so the caller can attach it to the verdict
    without re-reading."""
    state = _load_rounds(records_path)
    if not state.get("ok"):
        return {"ok": False, "reason": "records-" + (state.get("state") or "unreadable")}
    payload = build_record(state.get("records") or [], expected_leaves, usage,
                           benchmark=benchmark, terminal=terminal)
    result = write_record(path, payload, expected_hash=expected_hash, run_id=run_id, lease=lease)
    if not result.get("ok"):
        return result
    summary = dict(payload)
    summary["ok"] = True
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write", "write-from-records"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--payload-json")
    parser.add_argument("--records-path")
    parser.add_argument("--expected-leaves-json", default="[]")
    parser.add_argument("--usage-json", default="{}")
    parser.add_argument("--terminal")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    if args.cmd == "write-from-records":
        if not args.records_path:
            print(json.dumps({"ok": False, "reason": "missing-records-path"}))
            return 1
        result = write_from_records(
            args.path, args.records_path, json.loads(args.expected_leaves_json),
            json.loads(args.usage_json), terminal=args.terminal, benchmark=args.benchmark,
            expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    if args.payload_json is None:
        print(json.dumps({"ok": False, "reason": "missing-payload-json"}))
        return 1
    record = json.loads(args.payload_json)
    result = write_record(args.path, record, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
