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


# The resume summary: everything the loop needs IN MEMORY to seed a resume, bounded.
# Findings keep only their small identity/class/severity skeleton — the circuit breaker
# (file+title identity), recurrence (classKey/severity/carried), the round policy
# (per-dimension status/confidence/subjects/hasFindings), and the fix-context all stay
# functional — while the unbounded evidence bodies and reviewer receipts stay on disk
# (the read twin of the compose-persist write-side fix; live 2026-07-02 defect class).
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


def _dim_result_path(run_dir, name, round_no):
    return os.path.join(run_dir, "dim-result-%s-r%s.json" % (name, round_no))


def compose_round_record(run_dir, round_no, kind, dimensions, changed_subjects,
                         coverage_decisions, token_usage, confirmation_pending=False):
    """Compose the round record Python-side from the per-dimension result FILES the loop
    staged in the run dir (dim-result-<name>-r<round>.json) plus small scalars. The record
    body never rides the courier pipe as an inline argument (live 2026-07-02: an LLM courier
    mangled the oversized inline JSON and every native review leg parked). Fail-closed:
    a missing/corrupt dimension file refuses the compose."""
    dim_results = {}
    for name in dimensions or []:
        path = _dim_result_path(run_dir, name, round_no)
        try:
            with open(path, encoding="utf-8") as fh:
                result = json.load(fh)
        except FileNotFoundError:
            return {"ok": False, "reason": "dim-result-missing:%s" % name}
        except (OSError, ValueError) as exc:
            return {"ok": False, "reason": "dim-result-unreadable:%s" % name, "detail": str(exc)}
        if not isinstance(result, dict):
            return {"ok": False, "reason": "dim-result-unreadable:%s" % name, "detail": "not a dict"}
        dim_results[name] = result
    record = record_from_dimension_results(
        round_no, kind, dim_results, changed_subjects, coverage_decisions, token_usage,
        confirmation_pending)
    return {"ok": True, "record": record}


def update_round_record(path, round_no, updates, expected_hash=None, run_id=None, lease=None):
    """Apply a SMALL delta (confirmationPending / changedSubjects / coverageDecisions / fix)
    to an already-persisted round's record — the post-fix update never re-ships the round
    body through the pipe. Same fenced-persist semantics as persist_record."""
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
    merged.update(updates or {})
    return persist_record(path, records, merged, expected_hash=expected_hash,
                          run_id=run_id, lease=lease)


def _strip_records(result):
    """The CLI answer for compose-persist/update-round: ok + contentHash only — echoing the
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
    persist_p = sub.add_parser("persist")
    persist_p.add_argument("--path", required=True)
    persist_p.add_argument("--dimensions", required=True)
    persist_p.add_argument("--record-json", required=True)
    persist_p.add_argument("--expected-hash")
    persist_p.add_argument("--run-id", required=True)
    persist_p.add_argument("--lease")
    compose_p = sub.add_parser("compose-persist")
    compose_p.add_argument("--path", required=True)
    compose_p.add_argument("--run-dir", required=True)
    compose_p.add_argument("--round", required=True, type=int)
    compose_p.add_argument("--kind", required=True)
    compose_p.add_argument("--dimensions", required=True)
    compose_p.add_argument("--changed-subjects-json", default="null")
    compose_p.add_argument("--coverage-decisions-json", default="[]")
    compose_p.add_argument("--token-usage-json", default="{}")
    compose_p.add_argument("--confirmation-pending", action="store_true")
    compose_p.add_argument("--expected-hash")
    compose_p.add_argument("--run-id", required=True)
    compose_p.add_argument("--lease")
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
    if args.cmd == "compose-persist":
        composed = compose_round_record(
            args.run_dir, args.round, args.kind, json.loads(args.dimensions),
            json.loads(args.changed_subjects_json), json.loads(args.coverage_decisions_json),
            json.loads(args.token_usage_json), args.confirmation_pending)
        if not composed.get("ok"):
            print(json.dumps(composed))
            return 1
        state = load_records_state(args.path, json.loads(args.dimensions))
        if args.expected_hash and state.get("contentHash") != args.expected_hash:
            print(json.dumps({"ok": False, "reason": "stale"}))
            return 1
        if not state.get("ok"):
            print(json.dumps({"ok": False, "reason": state.get("state") or "unreadable"}))
            return 1
        result = persist_record(args.path, state.get("records") or [], composed["record"],
                                expected_hash=args.expected_hash, run_id=args.run_id, lease=args.lease)
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
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
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
