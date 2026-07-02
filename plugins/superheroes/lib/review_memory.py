#!/usr/bin/env python3
"""Pure memory helpers for review-loop recurrence and v2 round records."""
import re
import argparse
import glob
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


def _sent_hash_ok(raw, want, staged=False):
    """True when the transported text matches the sender's sha256. For a STAGED file,
    tolerate exactly one trailing newline: the bundle's leaf-bash writeFile is a heredoc
    (`cat > p <<EOF`), which puts body+'\\n' on disk — one byte the sender's hash never
    covered. Inline args get no tolerance; any other alteration still fails."""
    if not want:
        return False
    if content_hash(raw) == want:
        return True
    return bool(staged) and raw.endswith("\n") and content_hash(raw[:-1]) == want


def _with_write_stamp(record, run_id, lease):
    out = dict(record)
    if run_id:
        out["runId"] = run_id
    if lease:
        out["lease"] = lease
    return out


def persist_skeleton_record(path, record_json, record_hash, expected_hash=None,
                            run_id=None, lease=None, dimensions=None, round_no=None,
                            staged=False):
    """Persist a round record whose DURABLE form is the bounded skeleton (D3). The record
    rides the courier pipe inline (or as a staged file past the safe inline size) and
    self-verifies: the caller ships sha256 of the exact text alongside, and a courier that
    mangles the JSON cannot also recompute its hash, so transport corruption fails closed
    here instead of persisting silently altered content. --round cross-checks freshness (a
    replayed earlier arg pair carries the wrong round). summarize_record is re-applied
    Python-side so the on-disk contract (skeletons only, never evidence bodies) holds even
    if the JS twin drifts. A stale expected-hash re-probes for the record itself: when a
    prior attempt PERSISTED and only its answer was lost in transport, the retry answers
    ok idempotently instead of killing the run as write-failed."""
    if not _sent_hash_ok(record_json, record_hash or "", staged=staged):
        return {"ok": False, "reason": "record-corrupt"}
    try:
        record = json.loads(record_json)
    except ValueError as exc:
        return {"ok": False, "reason": "record-corrupt", "detail": str(exc)}
    if not isinstance(record, dict):
        return {"ok": False, "reason": "record-corrupt", "detail": "not a dict"}
    if round_no is not None and record.get("round") != round_no:
        return {"ok": False, "reason": "record-corrupt", "detail": "round mismatch"}
    skeleton = summarize_record(record)
    state = load_records_state(path, dimensions or [])
    if expected_hash and state.get("contentHash") != expected_hash:
        if state.get("ok"):
            stamped = _with_write_stamp(skeleton, run_id, lease)
            target = next((r for r in state.get("records") or []
                           if r.get("round") == skeleton.get("round")), None)
            if target == stamped:
                return {"ok": True, "contentHash": state.get("contentHash"), "idempotent": True}
        return {"ok": False, "reason": "stale"}
    if not state.get("ok"):
        return {"ok": False, "reason": state.get("state") or "unreadable"}
    return persist_record(path, state.get("records") or [], skeleton,
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
    smuggle back in. Same fenced-persist semantics as persist_record, with the same
    idempotent stale-probe as persist-skeleton (a prior applied delta whose answer was
    lost in transport answers ok on the retry)."""
    state = load_records_state(path, [])
    if expected_hash and state.get("contentHash") != expected_hash:
        if state.get("ok"):
            target = next((r for r in state.get("records") or []
                           if r.get("round") == round_no), None)
            if target is not None:
                merged = _with_write_stamp(dict(target), run_id, lease)
                merged.update(_sanitize_updates(updates))
                if merged == target:
                    return {"ok": True, "contentHash": state.get("contentHash"), "idempotent": True}
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


def _terminal_fields_from_records(records_path):
    """Compose the readout's fixes / deferred / coverageDecisions from the DURABLE round records
    on disk. These are the unbounded synthesis outputs — a verdict carrying every fix + deferred
    reason + coverage decision inline is exactly the blob that outgrows the courier (live
    2026-07-02: the terminal-record write parked payload-stage-failed). They ride round-records.json
    (Python-written, never the courier), so finalize re-derives them here instead of pushing them
    through. Missing/unreadable/corrupt -> empty lists (an early terminal has no rounds yet; the
    loop that could not read its own records already parked upstream)."""
    state = load_records_state(records_path, [])
    records = state.get("records") or []
    fixes, deferred, coverage = [], [], []
    seen_cov = set()
    for rec in sorted(records, key=lambda r: r.get("round") or 0):
        if not isinstance(rec, dict):
            continue
        fix = rec.get("fix") if isinstance(rec.get("fix"), dict) else {}
        fixes.extend(fix.get("fixes") or [])
        deferred.extend(fix.get("deferred") or [])
        for cd in rec.get("coverageDecisions") or []:
            key = cd.get("id") if isinstance(cd, dict) else cd
            if key in seen_cov:
                continue
            seen_cov.add(key)
            coverage.append(cd)
    return fixes, deferred, coverage


def _terminal_telemetry(telemetry_path):
    """Read the SMALL telemetry summary from review-telemetry.json (written Python-side just before
    finalize). runId/lease are transport stamps, not readout content, so they are stripped.
    Missing/unreadable -> None (the caller keeps whatever small telemetry the verdict carried)."""
    if not telemetry_path:
        return None
    try:
        with open(telemetry_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {k: v for k, v in data.items() if k not in ("runId", "lease")}


# The evidence-bodied fields + transport stamps a terminal record must never carry: findings hold
# full evidence bodies and NO terminal-record consumer reads them (the readout renders
# terminal/reason/telemetry/fixes/deferred/drops/coverage); runId/lease are re-stamped below.
_TERMINAL_STRIP = ("findings", "carriedFindings", "runId", "lease")


def compose_terminal_record(path, verdict_json, verdict_hash=None, records_path=None,
                            telemetry_path=None, run_id=None, lease=None):
    """Compose + atomically OVERWRITE the loop's terminal record from state already on disk
    (#136 compose-persist pattern). Only the small verdict scalars (terminal/reason/round/gate/
    drops/…) ride inline and self-verify: the caller ships sha256(verdict_json) and a courier that
    mangles the scalars cannot also recompute the hash, so transport corruption fails closed here
    instead of persisting silently altered content. The unbounded synthesis outputs (fixes/
    deferred/coverageDecisions) come from round-records.json and the telemetry summary from
    review-telemetry.json — never through the courier. Overwrite is finalize's job: the record is
    durable for crash-resume, not append-only, so a stale prior-run record is replaced."""
    if not run_id:
        return {"ok": False, "reason": "missing-run-id"}
    if verdict_hash is not None and not _sent_hash_ok(verdict_json, verdict_hash):
        return {"ok": False, "reason": "verdict-corrupt"}
    try:
        verdict = json.loads(verdict_json)
    except ValueError as exc:
        return {"ok": False, "reason": "verdict-corrupt", "detail": str(exc)}
    if not isinstance(verdict, dict):
        return {"ok": False, "reason": "verdict-corrupt", "detail": "not a dict"}
    record = {k: v for k, v in verdict.items() if k not in _TERMINAL_STRIP}
    if records_path:
        record["fixes"], record["deferred"], record["coverageDecisions"] = \
            _terminal_fields_from_records(records_path)
    else:
        record.setdefault("fixes", [])
        record.setdefault("deferred", [])
        record.setdefault("coverageDecisions", [])
    telemetry = _terminal_telemetry(telemetry_path)
    if telemetry is not None:
        record["telemetry"] = telemetry
    record["runId"] = run_id
    if lease:
        record["lease"] = lease
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    directory = os.path.dirname(os.path.abspath(path)) or "."
    tmp = None
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".terminal-record-", dir=directory, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError as exc:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return {"ok": False, "reason": "write-failed", "detail": str(exc)}
    return {"ok": True, "contentHash": content_hash(text)}


def sweep_stale_staging(run_dir):
    """Loop-entry hygiene: run dirs (/tmp/showrunner-<wi>-<phase>) are shared across runs of
    the same work-item+phase, so a DEAD run's transient staging artifacts (per-dim files from
    pre-D3 bundles, staged skeletons/updates, fenced .payload files) must not confuse a fresh
    round. Durable loop state that crash-resume actually READS (round-records.json,
    deferred-set.json, round-bodies-*, last-extras.json, terminal-record.json) is deliberately
    preserved. round-state.json is swept too: it is a WRITE-ONLY per-run diagnostic (saved by
    saveRoundStateBestEffort, never read back for resume), so a dead run's copy is pure
    cross-run contamination — live 2026-07-02 run 7's stale round-state.json survived into run 8
    in the shared /tmp dir, the same class that poisoned run 6. Best-effort: a failed unlink
    never blocks the load."""
    swept = 0
    for pattern in ("dim-result-*.json", "round-skeleton-*.json", "round-updates-*.json",
                    "*.payload", "round-state.json"):
        for path in glob.glob(os.path.join(run_dir, pattern)):
            try:
                os.unlink(path)
                swept += 1
            except OSError:
                pass
    return swept


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
    loads_p.add_argument("--sweep-stale-staging", action="store_true",
                         help="unlink a dead run's transient staging artifacts in the records "
                              "file's directory before loading (durable loop state preserved)")
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
    skel_p.add_argument("--round", type=int,
                        help="freshness cross-check: refuse when the verified record's round "
                             "differs (a replayed earlier arg pair passes the hash but not this)")
    skel_p.add_argument("--dimensions", default="[]",
                        help="reviewer set for schema-v1 promotion on load")
    skel_p.add_argument("--expected-hash")
    skel_p.add_argument("--run-id", required=True)
    skel_p.add_argument("--lease")
    update_p = sub.add_parser("update-round")
    update_p.add_argument("--path", required=True)
    update_p.add_argument("--round", required=True, type=int)
    update_p.add_argument("--updates-json")
    update_p.add_argument("--updates-path",
                          help="read the delta from this staged FILE instead — used when the "
                               "delta outgrows a safe inline courier arg")
    update_p.add_argument("--updates-hash",
                          help="sha256 of the updates text exactly as sent/staged; verified "
                               "when present (pre-D3 bundles omit it)")
    update_p.add_argument("--expected-hash")
    update_p.add_argument("--run-id", required=True)
    update_p.add_argument("--lease")
    term_p = sub.add_parser("compose-terminal")
    term_p.add_argument("--path", required=True)
    term_p.add_argument("--records-path",
                        help="round-records.json — the durable home of fixes/deferred/coverage; "
                             "composed Python-side so the unbounded synthesis outputs never ride "
                             "the courier")
    term_p.add_argument("--telemetry-path",
                        help="review-telemetry.json — the small telemetry summary read from disk")
    term_p.add_argument("--verdict-json", required=True,
                        help="the small verdict scalars inline (terminal/reason/round/gate/drops/…), "
                             "self-verified by --verdict-hash; findings are stripped")
    term_p.add_argument("--verdict-hash",
                        help="sha256 of --verdict-json exactly as sent — the transport self-check")
    term_p.add_argument("--run-id", required=True)
    term_p.add_argument("--lease")
    hash_p = sub.add_parser("hash")
    hash_p.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    if args.cmd == "compose-terminal":
        result = compose_terminal_record(args.path, args.verdict_json,
                                         verdict_hash=args.verdict_hash,
                                         records_path=args.records_path,
                                         telemetry_path=args.telemetry_path,
                                         run_id=args.run_id, lease=args.lease)
        print(json.dumps(result))
        return 0 if result.get("ok") else 1
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
        staged = bool(args.record_path)
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
                                         run_id=args.run_id, lease=args.lease,
                                         dimensions=json.loads(args.dimensions),
                                         round_no=args.round, staged=staged)
        if result.get("ok") and args.record_path:
            try:
                os.unlink(args.record_path)
            except OSError:
                pass
        print(json.dumps(_strip_records(result)))
        return 0 if result.get("ok") else 1
    if args.cmd == "update-round":
        staged = bool(args.updates_path)
        if args.updates_path:
            try:
                with open(args.updates_path, encoding="utf-8") as fh:
                    updates_json = fh.read()
            except OSError as exc:
                print(json.dumps({"ok": False, "reason": "updates-corrupt", "detail": str(exc)}))
                return 1
        elif args.updates_json is not None:
            updates_json = args.updates_json
        else:
            print(json.dumps({"ok": False, "reason": "missing-updates"}))
            return 1
        if args.updates_hash and not _sent_hash_ok(updates_json, args.updates_hash, staged=staged):
            print(json.dumps({"ok": False, "reason": "updates-corrupt"}))
            return 1
        try:
            updates = json.loads(updates_json)
        except ValueError as exc:
            print(json.dumps({"ok": False, "reason": "updates-corrupt", "detail": str(exc)}))
            return 1
        result = update_round_record(args.path, args.round, updates,
                                     expected_hash=args.expected_hash, run_id=args.run_id,
                                     lease=args.lease)
        if result.get("ok") and args.updates_path:
            try:
                os.unlink(args.updates_path)
            except OSError:
                pass
        print(json.dumps(_strip_records(result)))
        return 0 if result.get("ok") else 1
    dimensions = json.loads(args.dimensions)
    if args.cmd == "load-summary":
        if args.sweep_stale_staging:
            sweep_stale_staging(os.path.dirname(os.path.abspath(args.path)))
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
