#!/usr/bin/env python3
"""Fenced JSON writes for Workhorse-visible readouts and mirrors."""
import argparse
import builtins
import hashlib
import json
import os
import tempfile

open = builtins.open


def content_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _current(path):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        return {"ok": True, "text": text, "hash": content_hash(text)}
    except FileNotFoundError:
        return {"ok": True, "text": "", "hash": content_hash("")}
    except OSError as exc:
        return {"ok": False, "reason": "unreadable", "detail": str(exc)}


def _atomic_replace(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fenced-json-", dir=directory, text=True)
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
        return {"ok": False, "reason": "replace-failed", "detail": str(exc)}


def write_record(path, payload, expected_hash=None, run_id=None, lease=None):
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if not expected_hash:
        return {"ok": False, "reason": "missing-expected-hash"}
    state = _current(path)
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("reason", "unreadable")}
    if state["hash"] != expected_hash:
        return {"ok": False, "reason": "stale"}
    record = dict(payload or {})
    record["runId"] = run_id
    if lease:
        record["lease"] = lease
    result = _atomic_replace(path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    if not result.get("ok"):
        return result
    return {"ok": True, "contentHash": content_hash(json.dumps(record, indent=2, sort_keys=True) + "\n")}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--payload-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    payload = json.loads(args.payload_json)
    result = write_record(args.path, payload, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
