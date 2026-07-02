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


def write_record(path, payload, expected_hash=None, run_id=None, lease=None,
                 allow_overwrite=False):
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if not allow_overwrite:
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
    parser.add_argument("--payload-json")
    parser.add_argument("--payload-path",
                        help="read the payload from this staged FILE (and unlink it on success) "
                             "instead of an inline arg — a large payload must never ride the "
                             "courier pipe inline (it gets mangled; live 2026-07-02)")
    parser.add_argument("--payload-hash",
                        help="sha256 of the staged payload file's exact text — verified here "
                             "BEFORE the write, folding the courier-side hash read-back leaf "
                             "into this one (a mangled staged write fails closed as "
                             "payload-corrupt instead of persisting silently altered content)")
    parser.add_argument("--expected-hash")
    parser.add_argument("--allow-overwrite", action="store_true",
                        help="skip the expected-hash CAS: unconditionally replace the artifact "
                             "(single-writer, lease-guarded run artifacts like terminal-record)")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    if args.payload_path:
        try:
            with open(args.payload_path, encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(json.dumps({"ok": False, "reason": "payload-unreadable", "detail": str(exc)}))
            return 1
        if args.payload_hash and content_hash(raw) != args.payload_hash:
            print(json.dumps({"ok": False, "reason": "payload-corrupt"}))
            return 1
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            print(json.dumps({"ok": False, "reason": "payload-unreadable", "detail": str(exc)}))
            return 1
    elif args.payload_json is not None:
        payload = json.loads(args.payload_json)
    else:
        print(json.dumps({"ok": False, "reason": "missing-payload"}))
        return 1
    result = write_record(args.path, payload, expected_hash=args.expected_hash, run_id=args.run_id,
                          lease=args.lease, allow_overwrite=args.allow_overwrite)
    if result.get("ok") and args.payload_path:
        try:
            os.unlink(args.payload_path)
        except OSError:
            pass
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
