#!/usr/bin/env python3
"""Record visible, challengeable review coverage decisions."""
import argparse
import hashlib
import json
import os
import tempfile

SECTION = "## Review coverage decisions"


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path, text):
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".coverage-decisions-", dir=directory, text=True)
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


def _entry(decision):
    did = decision.get("id") or "RCD-unknown"
    kind = decision.get("kind") or "coverage"
    key = decision.get("classKey") or ""
    text = decision.get("text") or ""
    source = decision.get("sourceRound")
    payload = json.dumps(decision, sort_keys=True)
    return f"- **{did}** ({kind}; round {source}; class `{key}`): {text}\n  `review-coverage-decision-json:{payload}`\n"


def _with_fence(decision, run_id, lease=None):
    if not run_id:
        return None
    out = dict(decision)
    out["runId"] = run_id
    if lease:
        out["lease"] = lease
    return out


def record_doc_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    with open(path, encoding="utf-8") as fh:
        original = fh.read()
    if expected_hash and content_hash(original) != expected_hash:
        return {"ok": False, "reason": "stale"}
    entry = _entry(decision)
    if SECTION in original:
        updated = original.rstrip() + "\n" if entry in original else original.rstrip() + "\n" + entry
    else:
        updated = original.rstrip() + "\n\n" + SECTION + "\n\n" + entry
    result = _atomic_write(path, updated)
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


def record_code_decision(path, decision, expected_hash=None, run_id=None, lease=None):
    decision = _with_fence(decision, run_id, lease)
    if decision is None:
        return {"ok": False, "reason": "missing-run-id"}
    try:
        with open(path, encoding="utf-8") as fh:
            original = fh.read()
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = json.loads(original)
        if not isinstance(existing, list):
            existing = []
    except FileNotFoundError:
        original = ""
        if expected_hash and content_hash(original) != expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    except (OSError, ValueError):
        if expected_hash:
            return {"ok": False, "reason": "stale"}
        existing = []
    existing.append(decision)
    result = _atomic_write(path, json.dumps(existing, indent=2) + "\n")
    if not result["ok"]:
        return result
    return {"ok": True, "id": decision.get("id")}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["record-doc", "record-code"])
    parser.add_argument("--path", required=True)
    parser.add_argument("--decision-json", required=True)
    parser.add_argument("--expected-hash")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--lease")
    args = parser.parse_args(argv)
    decision = json.loads(args.decision_json)
    if args.cmd == "record-doc":
        result = record_doc_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    else:
        result = record_code_decision(args.path, decision, expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
