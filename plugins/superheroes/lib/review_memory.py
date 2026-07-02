#!/usr/bin/env python3
"""Pure memory helpers for review-loop recurrence and v2 round records."""
import re
import argparse
import hashlib
import json
import os
import tempfile

BLOCKING = {"Critical", "Important"}
_WS = re.compile(r"\s+")


def _norm(value):
    return _WS.sub(" ", str(value or "").strip().lower())


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def class_key(finding):
    return "::".join([
        str(finding.get("dimension") or ""),
        str(finding.get("taxonomy") or ""),
        _norm(finding.get("title")),
    ])


def recurrent_classes(records, coverage_decisions=None):
    covered = {d.get("classKey") for d in (coverage_decisions or []) if isinstance(d, dict)}
    seen = {}
    for rec in records or []:
        rnd = rec.get("round")
        for finding in rec.get("findings") or []:
            if finding.get("carried"):
                continue
            if finding.get("severity") not in BLOCKING:
                continue
            key = finding.get("classKey") or class_key(finding)
            if key in covered:
                continue
            seen.setdefault(key, set()).add(rnd)
    out = []
    for key, rounds in sorted(seen.items()):
        if len(rounds) >= 2:
            out.append({"classKey": key, "rounds": sorted(rounds)})
    return out


def promote_record(record, dimensions):
    if record.get("schemaVersion") == 2:
        return record
    return {
        "schemaVersion": 2,
        "round": record.get("round"),
        "kind": "unknown",
        "dimensions": {d: {"dimension": d, "status": "unknown"} for d in (dimensions or [])},
        "findings": record.get("findings") or [],
        "changedSubjects": None,
        "coverageDecisions": [],
        "tokenUsage": {"available": False, "reason": "promoted from schema v1"},
        "confirmationPending": False,
    }


def _subject_from_reviewer(name):
    return {
        "test": "Test",
        "security": "Security",
        "code": "Code",
        "architecture": "Architecture",
        "failure": "Failure-Mode",
    }.get(str(name or "").split("-")[0].lower())


def _dimension_record(name, result, round_no):
    out = dict(result or {})
    out.setdefault("dimension", name)
    out.setdefault("round", round_no)
    raw_findings = out.get("findings") if isinstance(out.get("findings"), list) else []
    current = []
    carried = []
    is_carried = out.get("status") == "skipped" or out.get("carriedFromRound") is not None
    for finding in raw_findings:
        if not isinstance(finding, dict):
            continue
        item = dict(finding)
        item.setdefault("dimension", out.get("dimension") or name)
        if is_carried:
            item["carried"] = True
            item["sourceRound"] = out.get("carriedFromRound") or finding.get("sourceRound") or round_no
            carried.append(item)
        else:
            current.append(item)
    subjects = {f.get("dimension") for f in current + carried if f.get("dimension")}
    fallback = _subject_from_reviewer(name)
    if fallback:
        subjects.add(fallback)
    out["findings"] = current + carried
    out["currentFindings"] = current
    out["carriedFindings"] = carried
    out["hasFindings"] = bool(current or carried)
    out["subjects"] = sorted(subjects)
    return out, current, carried


def record_from_dimension_results(round_no, kind, dimensions, changed_subjects, coverage_decisions, token_usage, confirmation_pending=False):
    findings = []
    carried_findings = []
    dimension_records = {}
    for name, result in (dimensions or {}).items():
        dim_record, current, carried = _dimension_record(name, result, round_no)
        dimension_records[name] = dim_record
        findings.extend(current)
        carried_findings.extend(carried)
    return {
        "schemaVersion": 2,
        "round": round_no,
        "kind": kind,
        "dimensions": dimension_records,
        "findings": findings,
        "carriedFindings": carried_findings,
        "changedSubjects": changed_subjects,
        "coverageDecisions": coverage_decisions or [],
        "tokenUsage": token_usage or {"available": False, "reason": "missing"},
        "confirmationPending": bool(confirmation_pending),
    }


def load_records_state(path, dimensions):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return {"ok": True, "state": "missing", "records": [], "contentHash": content_hash("")}
    except OSError as exc:
        return {"ok": False, "state": "unreadable", "records": [], "reason": str(exc)}
    try:
        data = json.loads(text)
    except ValueError as exc:
        return {"ok": False, "state": "corrupt", "records": [], "contentHash": content_hash(text), "reason": str(exc)}
    if not isinstance(data, list):
        return {"ok": False, "state": "corrupt", "records": [], "contentHash": content_hash(text), "reason": "not a list"}
    return {"ok": True, "state": "loaded", "records": [promote_record(r, dimensions) for r in data], "contentHash": content_hash(text)}


def load_records(path, dimensions):
    return load_records_state(path, dimensions)["records"]


def persist_record(path, records, record, expected_hash=None, run_id=None, lease=None):
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        return {"ok": False, "reason": "stale"}
    if not state.get("ok") and expected_hash:
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".round-records-", dir=directory, text=True)
    if run_id:
        record = dict(record)
        record["runId"] = run_id
    if lease:
        record = dict(record)
        record["lease"] = lease
    merged = [r for r in (records or []) if r.get("round") != record.get("round")]
    merged.append(record)
    merged.sort(key=lambda r: r.get("round") or 0)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        text = json.dumps(merged, indent=2) + "\n"
        return {"ok": True, "records": merged, "contentHash": content_hash(text)}
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return {"ok": False, "reason": "write-failed", "detail": str(exc)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    load_p = sub.add_parser("load")
    load_p.add_argument("--path", required=True)
    load_p.add_argument("--dimensions", required=True)
    persist_p = sub.add_parser("persist")
    persist_p.add_argument("--path", required=True)
    persist_p.add_argument("--dimensions", required=True)
    persist_p.add_argument("--record-json", required=True)
    persist_p.add_argument("--expected-hash")
    persist_p.add_argument("--run-id", required=True)
    persist_p.add_argument("--lease")
    args = parser.parse_args(argv)
    dimensions = json.loads(args.dimensions)
    if args.cmd == "load":
        result = load_records_state(args.path, dimensions)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    state = load_records_state(args.path, dimensions)
    if not state.get("ok"):
        print(json.dumps(state))
        return 1
    result = persist_record(args.path, state.get("records") or [], json.loads(args.record_json), expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
