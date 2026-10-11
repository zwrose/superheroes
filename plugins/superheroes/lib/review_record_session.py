#!/usr/bin/env python3
"""The full review lane's review record, written from the finished session directory.

Every fact in the account comes from the session's own files (loop-state.json, driver-journal.jsonl,
meta.json, the stored seat envelopes), except the few the driver never holds, which come from one
extras file. This module decides no status and posts nothing: it builds a review-account/1 and hands
it to review_record.write. A fact the session's files cannot establish takes the value that keeps the
record on the "not reviewed" side: an undecided outcome, a reviewer not run, or a refusal.

CLI:
  review_record_session.py write --session-dir DIR --extras FILE --repo-root DIR
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import dispatch_outcome  # noqa: E402
import receipt_disclosures  # noqa: E402
import record_paths  # noqa: E402
import review_record  # noqa: E402
import round_certification  # noqa: E402
import round_phases  # noqa: E402
import seat_map_receipts  # noqa: E402
import session_contract as sc  # noqa: E402
import verification  # noqa: E402

Refusal = review_record.Refusal
EXTRAS_SCHEMA = "review-session-extras/1"
UNREADABLE = "review-session-unreadable"
NOT_TERMINAL = "review-session-not-terminal"
UNSUPPORTED = "review-session-unsupported"
BAD_EXTRAS = "review-session-extras-invalid"
CARRIED = " (carried from the earlier review record)"
STILL_OPEN = "still open when the review loop ended"
_RAW_PHASES = (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_SCOPED)
_INGEST_CMDS = ("record-result", "record-missing", "advance")
_CAPPED = ("capped-with-open-critical", "capped-with-open-blocker")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _text(*vals):
    return next((v for v in vals if isinstance(v, str) and v), None)


def _read_json(path, what):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError, TypeError):
        raise Refusal(UNREADABLE, what)


def _journal(session_dir):
    if os.path.exists(os.path.join(session_dir, sc.JOURNAL_FAULT_FILE)):
        raise Refusal(UNREADABLE, sc.JOURNAL_FAULT_FILE)
    path = os.path.join(session_dir, sc.JOURNAL_FILE)
    if not os.path.exists(path):
        return []  # a session with no journal holds no recorded seat
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        raise Refusal(UNREADABLE, sc.JOURNAL_FILE)
    if not all(isinstance(r, dict) for r in rows):
        raise Refusal(UNREADABLE, sc.JOURNAL_FILE)
    return rows


def _check_extras(x):
    if not isinstance(x, dict) or x.get("schema") != EXTRAS_SCHEMA:
        raise Refusal(BAD_EXTRAS, "schema")
    if not (_int(x.get("pr")) and x["pr"] > 0):
        raise Refusal(BAD_EXTRAS, "pr")
    for k in ("runDirs", "goAheads", "makers", "checked"):
        if not isinstance(x.get(k, []), list):
            raise Refusal(BAD_EXTRAS, k)
    if not all(isinstance(d, str) and d for d in x.get("runDirs", [])):
        raise Refusal(BAD_EXTRAS, "runDirs")


def _slots(rows):
    """Active review slots, {(phase, round, seat, occurrence): (attempt, row)}: superseded attempts dropped, highest attempt kept."""
    gone = {(r.get("phase"), r.get("round"), r.get("attempt")) for r in rows if sc.journal_is_orders_superseded(r)}
    out = {}
    for r in rows:
        phase, seat, rnd, att = r.get("phase"), r.get("seat"), r.get("round"), r.get("attempt")
        if r.get("outcome") != "recorded" or not (isinstance(seat, str) and isinstance(phase, str)):
            continue  # a row naming no seat or phase names no reviewer
        if sc.run_kind_for_phase(phase) != sc.RUN_KIND_REVIEW or not (_int(rnd) and _int(att)):
            continue
        key = (phase, rnd, seat, r.get("occurrence", 0))
        if (phase, rnd, att) not in gone and (key not in out or att >= out[key][0]):
            out[key] = (att, r)
    return out


def _path(session_dir, key, attempt):
    phase, rnd, seat, occ = key
    try:
        return record_paths.store_path(session_dir, rnd, phase, record_paths.storage_key(seat, occ), attempt)
    except ValueError:
        return None


def _envelope(path):
    try:
        with open(path, encoding="utf-8") as fh:
            env = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None  # an unreadable envelope only loses the vendor and model it would have named
    return env if isinstance(env, dict) else None


def _payload_file(raw_dir, phase, rnd, seat, payload, taken):
    """The seat's findings payload as its own file in raw_dir: what the reviewer returned, without the runner's telemetry."""
    stem = f"{phase.removeprefix('dispatch-')}-{re.sub(r'[^A-Za-z0-9._-]', '-', seat)}-round-{rnd}"
    path, n = os.path.join(raw_dir, f"{stem}.json"), 1
    while path in taken:
        n += 1
        path = os.path.join(raw_dir, f"{stem}-{n}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    return path


def _bind(ran, run_dirs, engine_run):
    """{slot: run dir}: a directory binds to the one slot whose journaled runner nonce equals its engine record's."""
    hits = {}
    for d in run_dirs:
        try:
            rec = engine_run(d)[0]
        except Exception:
            continue
        nonce = rec.get("runnerNonce") if isinstance(rec, dict) else None
        slots = [k for k, (_, r) in ran.items() if nonce and (r.get("executionEvidence") or {}).get("runnerNonce") == nonce]
        if len(slots) == 1:
            hits.setdefault(slots[0], []).append(d)
    return {k: v[0] for k, v in hits.items() if len(v) == 1}


def _reviewer(state, rnd, seat, stem, ran, same, env=None, ev=None, commit=None, run_dir=None):
    seat_map = seat_map_receipts.round_governing_map(state, rnd).get("seats")
    entry = (seat_map.get(seat) if isinstance(seat_map, dict) else None) or {}
    env, ev = env or {}, ev or {}
    out = {"name": f"{stem}{seat} (round {rnd})", "planned": True, "ran": ran,
           "vendor": _text(env.get("vendor"), entry.get("vendor")) or "unknown",
           "model": _text(env.get("model"), entry.get("model"), ev.get("engineModel")) or "unknown",
           "commit": commit, "runDir": run_dir}
    return dict(out, notIndependent=True) if seat in same else out


def _slot_ran(state, key, row, env):
    """Whether the slot's reviewer ran: ingestion alone does not say so, the stored result and the round's seat status do."""
    phase, rnd, seat, _ = key
    cmd = row.get("cmd")
    payload = env.get("payload") if isinstance(env, dict) else None
    if cmd == "record-missing" or dispatch_outcome.payload_did_not_run(payload) \
            or (isinstance(env, dict) and env.get("schema") == sc.SEAT_MISSING_SCHEMA):
        return False
    if cmd != "record-result" and payload is None:
        return False  # a swept or reappended slot with no readable result is a missing envelope
    rec = (state.get("rounds") or {}).get(str(rnd))
    status = rec.get("seatStatus") if isinstance(rec, dict) else None
    return not (phase == sc.PANEL_PHASE and isinstance(status, dict) and status.get(seat) == "missing")


def _reviewers(state, session_dir, rows, run_dirs, engine_run, raw_dir=None):
    slots = {k: v for k, v in _slots(rows).items() if v[1].get("cmd") in _INGEST_CMDS}
    envs = {k: _envelope(_path(session_dir, k, v[0])) for k, v in slots.items()}
    ran = {k: v for k, v in slots.items() if _slot_ran(state, k, v[1], envs[k])}
    bound = _bind(ran, run_dirs, engine_run)
    same = set(seat_map_receipts.same_family_seats(state, receipt_disclosures.author_family(state)))
    out, raw = [], []
    for key, (att, r) in slots.items():
        phase, rnd, seat, _ = key
        if key not in ran and any(k[0] == phase and k[2] == seat and k[1] > rnd for k in ran):
            continue  # a later round ran this seat: the earlier miss is recovered
        env = envs[key]
        stem = "" if phase == sc.PANEL_PHASE else phase.removeprefix("dispatch-") + " "
        out.append(_reviewer(state, rnd, seat, stem, key in ran, same, env,
                             r.get("executionEvidence") if isinstance(r.get("executionEvidence"), dict) else None,
                             _text(r.get("citedHead")), bound.get(key)))
        if key in ran and phase in _RAW_PHASES and raw_dir:
            if env is None or "payload" not in env:
                raise Refusal(UNREADABLE, f"{phase} {seat} round {rnd} findings")  # a ran seat's output must be retrievable
            raw.append(_payload_file(raw_dir, phase, rnd, seat, env["payload"], raw))
    return out, raw


def _decide(own, by_key, rulings):
    """(outcome, reason, representative): undecided unless the ledger shows a disposition newer than the finding."""
    rep = sc.resolve_merged_into_entry(own, by_key)
    if not isinstance(rep, dict):
        return None, STILL_OPEN, None
    disp, seq, raised = rep.get("disposition"), rep.get(sc.DISPOSITION_SEQ_FIELD), own.get(sc.RAISED_SEQ_FIELD)
    if disp not in sc.DISPOSITIONS or not (_int(seq) and _int(raised) and seq > raised):  # a stale disposition decides nothing
        return None, STILL_OPEN, rep
    if disp == "fixed":
        return "fixed", f"fixed and audited in round {rep.get('dispositionRound')}", rep
    if disp == "refuted":
        why = _text(rep.get("refutedReason"))
        return ("left-for-owner" if (why or "").startswith("author-justified") else "shown-wrong"), why, rep
    why = _text(rep.get("outOfScopeReason"))
    ruling = rulings.get(sc.finding_identity_key(rep)) or {}
    prov = ruling.get("provenance") if ruling.get("ruling") == "out-of-scope" else None
    by, at = (_text(prov.get("ruledBy")), _text(prov.get("ruledAt"))) if isinstance(prov, dict) else (None, None)
    if by and at:  # only an attributed ruling settles an out-of-scope finding
        return "ruling", f"{why} (ruled by {by}, {at})", rep
    return "left-for-owner", why, rep


def _id(row, key):
    rid = row.get("id")
    return rid if isinstance(rid, str) and rid and not verification.is_staged_id(rid) else key


def _findings(state):
    owned = state.get(sc.DISPOSITION_LEDGER_OWNER_FIELD) == sc.DISPOSITION_LEDGER_OWNER_VALUE
    ledger, fault = sc.read_disposition_ledger(state, required=owned)  # an owned session's ledger is never optional
    if fault:
        raise Refusal(UNREADABLE, fault.token)
    live = state.get("findings") or []
    if not isinstance(live, list) or not all(isinstance(f, dict) for f in live):
        raise Refusal(UNREADABLE, "findings")
    by_key = {sc.finding_identity_key(r): r for r in ledger}
    content = dict(by_key, **{sc.finding_identity_key(f): f for f in live})
    log = state.get("rulingsLog") if isinstance(state.get("rulingsLog"), list) else []
    rulings = {r.get("findingKey"): r for r in log if isinstance(r, dict)}  # the latest ruling per key stands
    out = []
    for key, row in content.items():
        if row.get("summaryEntry"):
            continue
        outcome, reason, rep = (None, STILL_OPEN, None) if key not in by_key else _decide(by_key[key], by_key, rulings)
        if rep is not None and reason and sc.finding_identity_key(rep) != key:
            reason += f" (merged into {_id(rep, sc.finding_identity_key(rep))})"
        dim = row.get("dimension")
        out.append({"id": _id(row, key), "findingKey": key, "outcome": outcome, "reason": reason,
                    "reviewer": ", ".join(map(str, dim)) if isinstance(dim, list) else _text(dim),
                    **{k: row.get(k) for k in ("title", "severity", "file", "line", "consequence")},
                    "body": row.get("body", row.get("detail"))})
    return out


def account_from_session(session_dir, extras, readers=None, raw_dir=None):
    _check_extras(extras)
    if not os.path.isdir(session_dir):
        raise Refusal(UNREADABLE, "session dir")
    state = _read_json(os.path.join(session_dir, sc.STATE_FILE), sc.STATE_FILE)
    if not isinstance(state, dict):
        raise Refusal(UNREADABLE, sc.STATE_FILE)
    if not state.get("terminal"):
        raise Refusal(NOT_TERMINAL, "the review loop has not ended")
    meta = _read_json(os.path.join(session_dir, sc.META_FILE), "meta.json sessionId")
    if not (isinstance(meta, dict) and _text(meta.get("sessionId"))):
        raise Refusal(UNREADABLE, "meta.json sessionId")
    rows = _journal(session_dir)
    if state["terminal"] not in round_certification.CERTIFIED_VERDICTS:
        raise Refusal(UNSUPPORTED, "the session ended on a terminal that is not a certified verdict")
    if not any(r.get("outcome") == "recorded" and isinstance(r.get("seat"), str) for r in rows):
        raise Refusal(UNSUPPORTED, "the session recorded no seat result")
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    decisions = [d for d in state.get("decisions") or [] if isinstance(d, dict)]
    findings = _findings(state)
    reviewers, raw = _reviewers(state, session_dir, rows, extras.get("runDirs", []),
                                review_record._readers(readers)["engine_run"], raw_dir)
    makers, fam = list(extras.get("makers", [])), receipt_disclosures.author_family(state)
    if fam and any(isinstance(r, dict) and "fix" in r for r in rounds.values()) \
            and not any(isinstance(m, dict) and m.get("family") == fam for m in makers):
        makers.append({"family": fam, "source": "review loop fixer"})
    last = decisions[-1] if decisions else {}
    capped = state["terminal"] in _CAPPED or (state["terminal"] == "halted" and last.get("kind") == "round-ceiling")
    return {"schema": review_record.ACCOUNT_SCHEMA, "pr": extras["pr"], "repo": extras.get("repo"), "lane": "full",
            "laneReason": extras.get("laneReason"), "ci": extras.get("ci"), "sessionId": meta["sessionId"],
            "finalCommit": _text(meta.get(sc.FIX_FOLD_HEAD_KEY), cfg.get(sc.FIX_FOLD_HEAD_KEY), meta.get("headSha"),
                                 cfg.get("headSha")),
            "rounds": {"count": len(rounds), "cap": cfg["maxRounds"] if _int(cfg.get("maxRounds")) else None,
                       "stoppedAtCap": capped},
            "reviewers": reviewers, "makers": makers, "findings": findings, "rawFindingsFiles": raw,
            "goAheads": extras.get("goAheads", []), "checked": extras.get("checked", [])}


def _carried(account, extras, repo_root, readers):
    """The latest earlier record's findings this session did not raise, as that record stored them.

    Any refusal other than "no earlier record", and any malformed findings list, carries nothing: the
    writer makes its own refusal, so there is one place that refuses.
    """
    repo = extras.get("repo") or review_record._readers(readers)["repo_name"](repo_root)
    prior = review_record.read(account["pr"], repo, readers)
    earlier = prior.get("findings") if prior.get("ok") else None
    if not isinstance(earlier, list) or not all(isinstance(f, dict) for f in earlier):
        return []
    present = {review_record._key(f) for f in account["findings"]}
    out = []
    for f in earlier:
        if review_record._key(f) in present:
            continue
        reason = f.get("reason")
        out.append(dict(f, reason=reason + CARRIED if isinstance(reason, str) and reason else reason))
    return out


def write_from_session(session_dir, extras_path, repo_root, readers=None):
    tmp = []

    def go():
        tmp.append(tempfile.mkdtemp(prefix="review-record-"))
        try:
            with open(extras_path, encoding="utf-8") as fh:
                extras = json.load(fh)
        except (OSError, ValueError, TypeError):
            raise Refusal(BAD_EXTRAS, "extras file")
        account = account_from_session(session_dir, extras, readers, tmp[0])
        account["findings"] += _carried(account, extras, repo_root, readers)
        path = os.path.join(tmp[0], "review-account.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(account, fh)
        return review_record.write(path, repo_root, readers)
    try:
        return review_record._guarded(go)
    finally:
        for path in tmp:
            shutil.rmtree(path, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(prog="review_record_session")
    w = p.add_subparsers(dest="command", required=True).add_parser("write")
    w.add_argument("--session-dir", required=True, dest="session_dir")
    w.add_argument("--extras", required=True)
    w.add_argument("--repo-root", required=True, dest="repo_root")
    args = p.parse_args(argv)
    result = write_from_session(args.session_dir, args.extras, args.repo_root)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
