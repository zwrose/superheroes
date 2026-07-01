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
    return {
        "schemaVersion": 1,
        "terminal": terminal,
        "roundCount": len(rounds or []),
        "rounds": rounds or [],
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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    record = json.loads(args.payload_json)
    result = write_record(args.path, record, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
