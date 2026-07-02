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


# The skeleton summary: everything the loop needs IN MEMORY to run, bounded.
# Findings keep only their small identity/class/severity skeleton — the circuit breaker
# (file+title identity), recurrence (classKey/severity/carried), the round policy
# (per-dimension status/confidence/subjects/hasFindings), and the fix-context all stay
# functional. Since D3 this is also the DURABLE round-record form (persist-skeleton) —
# the unbounded evidence bodies never touch round-records.json at all; the dropped/deferred
# bodies land in the best-effort round-bodies dump, and the final round's bodies live in
# terminal-record.json. summarize_record is idempotent, so pre-D3 full-bodied files load
# (and re-persist) cleanly through the same path.
_SKELETON_FIELDS = ("file", "line", "title", "severity", "taxonomy", "dimension",
                    "classKey", "carried", "sourceRound")
_MAX_TITLE = 300


def _skeleton_finding(finding):
    if not isinstance(finding, dict):
        return {}
    out = {k: finding[k] for k in _SKELETON_FIELDS if k in finding}
    title = out.get("title")
    if isinstance(title, str) and len(title) > _MAX_TITLE:
        out["title"] = title[:_MAX_TITLE]
    return out


def _summarize_dimension(dim):
    if not isinstance(dim, dict):
        return {}
    findings = dim.get("findings") if isinstance(dim.get("findings"), list) else []
    out = {k: dim[k] for k in ("dimension", "status", "confidence", "round", "subjects",
                               "carriedFromRound", "escalated", "tier") if k in dim}
    out["findings"] = [_skeleton_finding(f) for f in findings]
    out["hasFindings"] = bool(findings) or bool(dim.get("hasFindings"))
    out["blockingCount"] = sum(1 for f in findings
                               if isinstance(f, dict) and f.get("severity") in BLOCKING)
    return out


def summarize_record(record):
    rec = record if isinstance(record, dict) else {}
    findings = rec.get("findings") if isinstance(rec.get("findings"), list) else []
    carried = rec.get("carriedFindings") if isinstance(rec.get("carriedFindings"), list) else []
    return {
        "schemaVersion": rec.get("schemaVersion"),
        "round": rec.get("round"),
        "kind": rec.get("kind"),
        "confirmationPending": bool(rec.get("confirmationPending")),
        "changedSubjects": rec.get("changedSubjects"),
        "coverageDecisions": rec.get("coverageDecisions") or [],
        "tokenUsage": rec.get("tokenUsage"),
        "findings": [_skeleton_finding(f) for f in findings],
        "carriedFindings": [_skeleton_finding(f) for f in carried],
        "dimensions": {name: _summarize_dimension(d)
                       for name, d in (rec.get("dimensions") or {}).items()},
    }


def persist_record(path, records, record, expected_hash=None, run_id=None, lease=None):
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        return {"ok": False, "reason": "stale"}
    if not state.get("ok") and expected_hash:
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
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


def persist_skeleton_record(path, record_json, record_hash, expected_hash=None,
                            run_id=None, lease=None):
    """Persist a round record whose DURABLE form is the bounded skeleton (D3). The record
    rides the courier pipe INLINE — safe because (a) it is the summarize_record skeleton
    (title<=300, identity/class/severity fields only), and (b) it self-verifies: the caller
    ships sha256(record_json) alongside, and a courier that mangles the JSON cannot also
    recompute its hash, so any transport corruption fails closed here instead of persisting
    silently altered content. summarize_record is re-applied Python-side so the on-disk
    contract (skeletons only, never evidence bodies) holds even if the JS twin drifts."""
    if content_hash(record_json) != (record_hash or ""):
        return {"ok": False, "reason": "record-corrupt"}
    try:
        record = json.loads(record_json)
    except ValueError as exc:
        return {"ok": False, "reason": "record-corrupt", "detail": str(exc)}
    if not isinstance(record, dict):
        return {"ok": False, "reason": "record-corrupt", "detail": "not a dict"}
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        return {"ok": False, "reason": "stale"}
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    return persist_record(path, state.get("records") or [], summarize_record(record),
                          expected_hash=expected_hash, run_id=run_id, lease=lease)


_MAX_DEFER_REASON = 500


def _skeleton_deferred(items):
    """Slim a fix report's deferred entries to identity/severity/reason (+ skeleton finding) —
    a deferred entry embedding its full finding body would smuggle evidence back into
    round-records.json through the update-round delta. The full bodies' durable home is the
    best-effort round-bodies dump."""
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            out.append(item)
            continue
        slim = {k: item[k] for k in ("identity", "id", "severity", "reason") if k in item}
        reason = slim.get("reason")
        if isinstance(reason, str) and len(reason) > _MAX_DEFER_REASON:
            slim["reason"] = reason[:_MAX_DEFER_REASON]
        if isinstance(item.get("finding"), dict):
            slim["finding"] = _skeleton_finding(item["finding"])
        out.append(slim)
    return out


def _sanitize_updates(updates):
    up = dict(updates or {})
    fix = up.get("fix")
    if isinstance(fix, dict) and "deferred" in fix:
        fix = dict(fix)
        fix["deferred"] = _skeleton_deferred(fix.get("deferred"))
        up["fix"] = fix
    return up


def update_round_record(path, round_no, updates, expected_hash=None, run_id=None, lease=None):
    """Apply a SMALL delta (confirmationPending / changedSubjects / coverageDecisions / fix)
    to an already-persisted round's record — the post-fix update never re-ships the round
    body through the pipe, and its deferred entries are re-slimmed here so bodies can't
    smuggle back in. Same fenced-persist semantics as persist_record."""
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        return {"ok": False, "reason": "stale"}
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    records = state.get("records") or []
    target = next((r for r in records if r.get("round") == round_no), None)
    if target is None:
        return {"ok": False, "reason": "round-missing"}
    merged = dict(target)
    merged.update(_sanitize_updates(updates))
    return persist_record(path, records, merged, expected_hash=expected_hash,
                          run_id=run_id, lease=lease)


def _strip_records(result):
    """The CLI answer for persist-skeleton/update-round: ok + contentHash only — echoing the
    merged records back through the courier stdout would be the same mega-payload defect."""
    return {k: v for k, v in result.items() if k != "records"}


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    load_p = sub.add_parser("load")
    load_p.add_argument("--path", required=True)
    load_p.add_argument("--dimensions", required=True)
    loads_p = sub.add_parser("load-summary")
    loads_p.add_argument("--path", required=True)
    loads_p.add_argument("--dimensions", required=True)
    loads_p.add_argument("--extras-path",
                         help="also read this small side file (last-extras.json) and answer it "
                              "as 'extras' — folds the loop's two entry reads into one leaf")
    skel_p = sub.add_parser("persist-skeleton")
    skel_p.add_argument("--path", required=True)
    skel_p.add_argument("--record-json",
                        help="the skeleton record inline (the typical, small case)")
    skel_p.add_argument("--record-path",
                        help="read the skeleton from this staged FILE instead — used when a "
                             "many-finding round outgrows a safe inline courier arg")
    skel_p.add_argument("--record-hash", required=True,
                        help="sha256 of the record text exactly as sent/staged — the transport "
                             "self-check that lets the write verify itself in one leaf")
    skel_p.add_argument("--expected-hash")
    skel_p.add_argument("--run-id", required=True)
    skel_p.add_argument("--lease")
    update_p = sub.add_parser("update-round")
    update_p.add_argument("--path", required=True)
    update_p.add_argument("--round", required=True, type=int)
    update_p.add_argument("--updates-json", required=True)
    update_p.add_argument("--expected-hash")
    update_p.add_argument("--run-id", required=True)
    update_p.add_argument("--lease")
    hash_p = sub.add_parser("hash")
    hash_p.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "hash":
        try:
            with open(args.path, encoding="utf-8") as fh:
                text = fh.read()
        except FileNotFoundError:
            text = ""
        except OSError as exc:
            print(json.dumps({"ok": False, "reason": "unreadable", "detail": str(exc)}))
            return 1
        print(json.dumps({"ok": True, "contentHash": content_hash(text)}))
        return 0
    if args.cmd == "persist-skeleton":
        if args.record_path:
            try:
                with open(args.record_path, encoding="utf-8") as fh:
                    record_json = fh.read()
            except OSError as exc:
                print(json.dumps({"ok": False, "reason": "record-corrupt", "detail": str(exc)}))
                return 1
        elif args.record_json is not None:
            record_json = args.record_json
        else:
            print(json.dumps({"ok": False, "reason": "missing-record"}))
            return 1
        result = persist_skeleton_record(args.path, record_json, args.record_hash,
                                         expected_hash=args.expected_hash,
                                         run_id=args.run_id, lease=args.lease)
        print(json.dumps(_strip_records(result)))
        return 0 if result.get("ok") else 1
    if args.cmd == "update-round":
        result = update_round_record(args.path, args.round, json.loads(args.updates_json),
                                     expected_hash=args.expected_hash, run_id=args.run_id,
                                     lease=args.lease)
        print(json.dumps(_strip_records(result)))
        return 0 if result.get("ok") else 1
    dimensions = json.loads(args.dimensions)
    if args.cmd == "load-summary":
        result = load_records_state(args.path, dimensions)
        result["records"] = [summarize_record(r) for r in result.get("records") or []]
        if args.extras_path:
            try:
                with open(args.extras_path, encoding="utf-8") as fh:
                    result["extras"] = json.load(fh)
            except (OSError, ValueError):
                result["extras"] = None
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
    result = load_records_state(args.path, dimensions)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
