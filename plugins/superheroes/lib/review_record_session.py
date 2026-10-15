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

import audits as audits_mod  # noqa: E402
import circuit_breaker  # noqa: E402
import decision_kinds  # noqa: E402
import dispatch_outcome  # noqa: E402
import receipt_disclosures  # noqa: E402
import record_paths  # noqa: E402
import review_findings_schema  # noqa: E402
import review_record  # noqa: E402
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
HAND_SUBMIT_NOTE = "the session was driven by hand submit; reviewers' raw outputs were not stored"
UNFILLED = "unfilled"
_OWNER_SUPPLIED = "owner-supplied"
_RAW_PHASES = (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_SCOPED)
_PRE_FIX_PHASES = (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_VERIFIERS)
# synthesis only groups already-raised findings into root causes: it raises, confirms, audits and grades
# nothing, so it is not a reviewer of the change and the account does not list it
_UNLISTED_PHASES = (round_phases.P_SYNTHESIS,)
_INGEST_CMDS = ("record-result", "record-missing", "advance")
_FIXED, _SHOWN_WRONG, _CRAFT, _LEFT_FOR_OWNER, _RULING = review_findings_schema.OUTCOMES


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
    if x.get("sheetAnswers") is not None and not isinstance(x["sheetAnswers"], dict):
        raise Refusal(BAD_EXTRAS, "sheetAnswers")
    if x.get("baseRef") is not None and not (isinstance(x["baseRef"], str) and x["baseRef"]):
        raise Refusal(BAD_EXTRAS, "baseRef")


def _historical_orders_superseded(row):
    """True for a row an earlier plugin version journaled when a re-emit replaced a round's orders.
    That version is gone, but its finished sessions are still read here: an attempt it superseded is
    no reviewer, even when no replacement was ever recorded."""
    return row.get("cmd") == "re-emit" and row.get("outcome") == "orders-superseded"


def _slots(rows):
    """Active review slots, {(phase, round, seat, occurrence): (attempt, row)}: attempts an earlier
    version's re-emit superseded dropped, highest remaining attempt kept."""
    gone = {(r.get("phase"), r.get("round"), r.get("attempt")) for r in rows if _historical_orders_superseded(r)}
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


def _step(rnd, phase):
    """Where in the loop a reviewer sat: two steps a round, a panel, gap-sweep or verifier read before the
    round's fix (even), every other review phase after it (odd)."""
    return 2 * rnd + (0 if phase in _PRE_FIX_PHASES else 1)


def _reviewer(state, rnd, seat, stem, ran, env=None, ev=None, commit=None, run_dir=None, phase=None):
    seat_map = seat_map_receipts.round_governing_map(state, rnd).get("seats")
    entry = (seat_map.get(seat) if isinstance(seat_map, dict) else None) or {}
    env, ev = env or {}, ev or {}
    return {"name": f"{stem}{seat} (round {rnd})", "planned": True, "ran": ran,
            "vendor": _text(env.get("vendor"), entry.get("vendor")) or "unknown",
            "model": _text(env.get("model"), entry.get("model"), ev.get("engineModel")) or "unknown",
            "commit": commit, "runDir": run_dir, "step": _step(rnd, phase) if phase else None}


def _unfilled_reviewer(rnd, seat):
    """A seat the round's map left unfilled: planned, never run, no vendor or model to name."""
    return {"name": f"{seat} (round {rnd})", "planned": True, "ran": False, "vendor": UNFILLED,
            "model": UNFILLED, "commit": None, "runDir": None}


def _panel_rounds_with_status(state):
    """{round: seatStatus} for each round that recorded a seat status, in round order."""
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    return {int(n): rec["seatStatus"] for n, rec in sorted(rounds.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else -1)
            if str(n).isdigit() and isinstance(rec, dict) and isinstance(rec.get("seatStatus"), dict)}


def _panel_head(state, rnd, setup=None, phase=sc.PANEL_PHASE):
    """The head the round's `phase` orders were emitted at (latest attempt). Round 1's panel carries no emission
    head: it ran before any fix, at the session-setup head (`setup` is the meta's). None when none is recorded."""
    anchors = state.get("_ordersAnchors")
    best = None
    for key, anchor in (anchors.items() if isinstance(anchors, dict) else ()):
        parts = str(key).split(":")
        if len(parts) == 3 and parts[0] == str(rnd) and parts[1] == phase and parts[2].isdigit() \
                and isinstance(anchor, dict) and isinstance(anchor.get("headSha"), str) and anchor["headSha"]:
            if best is None or int(parts[2]) > best[0]:
                best = (int(parts[2]), anchor["headSha"])
    if best:
        return best[1]
    if phase != sc.PANEL_PHASE or str(rnd) != "1":
        return None
    cfg = state.get("config")
    return _text(cfg.get("headSha") if isinstance(cfg, dict) else None, setup)


def _audit_key(a):
    return a.get("identity") or a.get("id")


def _audit_silent(a):
    """An audit entry the round recorded as silence: no result came back, so no auditor ran for that target."""
    return isinstance(a, dict) and a.get("reason") == audits_mod.NO_AUDIT_RESULT_REASON


def _audit_reviewers(state, rnd, audits, later=frozenset()):
    """One reviewer per auditor vendor whose authenticated audit result the round persisted, at the audits' emission head,
    and one unrun reviewer for a target the round recorded as silent that no later round `later` audited. Any other
    entry, a not-discharged ruling included, is an auditor that ran."""
    head = _panel_head(state, rnd, phase=round_phases.P_AUDITS)
    vendors = sorted({a["auditor"] for a in audits if isinstance(a, dict) and isinstance(a.get("auditor"), str) and a["auditor"]})
    out = [_reviewer(state, rnd, f"auditor {v}", "audits ", True, {"vendor": v, "model": "unknown"},
                     commit=head, phase=round_phases.P_AUDITS) for v in vendors] if head else []
    silent = any(_audit_silent(a) and _audit_key(a) not in later for a in audits)
    return out + ([_reviewer(state, rnd, "auditor", "audits ", False, commit=head, phase=round_phases.P_AUDITS)] if silent else [])


def _status_reviewers(state, setup=None):
    """Reviewer rows for a session driven by hand submit, which journals no seat: each panel round's seat
    status says which seats ran, and the reviewers' raw outputs were not stored."""
    status = _panel_rounds_with_status(state)
    # axis: a hand-submit session with no seat status in any round holds nothing that says a reviewer ran — see bite-proof record c7l3_wo2_session_writer
    if not any(status.values()):
        raise Refusal(UNSUPPORTED, "the session recorded no seat result or seat status")
    out, ran_in = [], {}
    for rnd, seats in status.items():
        for seat, value in seats.items():
            if value == "run":
                ran_in.setdefault(seat, []).append(rnd)
    for rnd, seats in status.items():
        unfilled = receipt_disclosures.unfilled_seats(seat_map_receipts.round_governing_map(state, rnd)) \
            & set(round_phases.DIMENSIONS)
        for seat in sorted(seats):
            if seat in unfilled:
                continue  # listed below as an unfilled seat
            commit = _panel_head(state, rnd, setup)
            ran = seats[seat] == "run" and commit is not None  # any other value, or a panel with no recoverable head, is never credited
            fell = next((f.get("ran") for f in ((state["rounds"].get(str(rnd)) or {}).get("fellOpen") or ()) if isinstance(f, dict)
                         and f.get("seat") == seat and isinstance(f.get("ran"), str) and f["ran"]), None) if ran else None
            if not ran and any(r > rnd for r in ran_in.get(seat, ())):
                continue  # a later round ran this seat: the earlier miss is recovered
            out.append(_reviewer(state, rnd, seat, "", ran, {"vendor": fell, "model": "unknown"} if fell else None,
                                 commit=commit, phase=sc.PANEL_PHASE))
        out += [_unfilled_reviewer(rnd, seat) for seat in sorted(unfilled)
                if not any(r > rnd for r in ran_in.get(seat, ()))]
    by_round = {int(n): rec["audits"] for n, rec in state["rounds"].items()
                if str(n).isdigit() and isinstance(rec, dict) and isinstance(rec.get("audits"), list)}
    for rnd, audits in by_round.items():
        later = {_audit_key(a) for r, rows in by_round.items() if r > rnd for a in rows if isinstance(a, dict) and not _audit_silent(a)}
        out += _audit_reviewers(state, rnd, audits, later)
    return out


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
    slots = {k: v for k, v in _slots(rows).items() if v[1].get("cmd") in _INGEST_CMDS
             and k[0] not in _UNLISTED_PHASES}
    envs = {k: _envelope(_path(session_dir, k, v[0])) for k, v in slots.items()}
    ran = {k: v for k, v in slots.items() if _slot_ran(state, k, v[1], envs[k])}
    bound = _bind(ran, run_dirs, engine_run)
    unfilled = {}  # panel round -> the seats its governing map leaves unfilled
    for rnd in sorted({k[1] for k in slots if k[0] == sc.PANEL_PHASE}
                      | {int(n) for n, rec in (state.get("rounds") or {}).items()
                         if str(n).isdigit() and isinstance(rec, dict) and "seatStatus" in rec}):
        names = receipt_disclosures.unfilled_seats(seat_map_receipts.round_governing_map(state, rnd)) & set(round_phases.DIMENSIONS)
        if names:
            unfilled[rnd] = sorted(names)
    out, raw = [], []
    for key, (att, r) in slots.items():
        phase, rnd, seat, _ = key
        if phase == sc.PANEL_PHASE and seat in unfilled.get(rnd, ()):
            continue  # listed below as an unfilled seat, whether or not a slot was journaled for it
        env = envs[key]
        body = env.get("payload") if isinstance(env, dict) else None
        if key in ran and phase in _RAW_PHASES and raw_dir and body is None and not (isinstance(env, dict) and "payload" in env):
            raise Refusal(UNREADABLE, f"{phase} {seat} round {rnd} findings")  # a ran seat's output must be retrievable
        if phase in _RAW_PHASES and raw_dir and (key in ran or (isinstance(body, dict) and body.get("findings"))):
            raw.append(_payload_file(raw_dir, phase, rnd, seat, body, raw))  # findings from a missing seat stay retrievable
        if key not in ran and any(k[0] == phase and k[2] == seat and k[1] > rnd for k in ran):
            continue  # a later round ran this seat: the earlier miss is recovered
        stem = "" if phase == sc.PANEL_PHASE else phase.removeprefix("dispatch-") + " "
        out.append(_reviewer(state, rnd, seat, stem, key in ran, env,
                             r.get("executionEvidence") if isinstance(r.get("executionEvidence"), dict) else None,
                             _text(r.get("citedHead")), bound.get(key), phase))
    out += [_unfilled_reviewer(rnd, seat) for rnd, names in unfilled.items() for seat in names
            if not any(k[0] == sc.PANEL_PHASE and k[2] == seat and k[1] > rnd for k in ran)]  # a later run recovers it
    return out, raw


def _group(rep, by_key):
    """The representative and every ledger row merged into it."""
    return [r for r in by_key.values() if r is rep or sc.resolve_merged_into_entry(r, by_key) is rep]


def _latest_ruling(rep, by_key, rulings):
    """The newest ruling logged against the representative or against any finding merged into it, else {}."""
    # axis: a ruling logged against a finding merged into the representative settles the representative too — see bite-proof record c7l3_wo2_session_writer
    keys = [sc.finding_identity_key(r) for r in _group(rep, by_key)] + [rep.get("id")]
    found = [rulings[k] for k in keys if isinstance(k, str) and isinstance(rulings.get(k), dict)]
    return max(found, key=lambda r: r["seq"] if _int(r.get("seq")) else -1) if found else {}


def _decided_by(rep, outcome):
    """The cited decision the settled ledger row carries (the driver's settle puts it there); an older ledger
    without it leaves the finding as settled."""
    held = sc.decided_by_of(rep)
    return held if outcome is not None and isinstance(held, dict) else None


def _decide(own, by_key, rulings):
    """(outcome, reason, representative): undecided unless the ledger shows a disposition newer than the finding."""
    rep = sc.resolve_merged_into_entry(own, by_key)
    if not isinstance(rep, dict):
        return None, STILL_OPEN, None
    disp, seq, raised = rep.get("disposition"), rep.get(sc.DISPOSITION_SEQ_FIELD), own.get(sc.RAISED_SEQ_FIELD)
    if disp not in sc.DISPOSITIONS or not (_int(seq) and _int(raised) and seq > raised):  # a stale disposition decides nothing
        return None, STILL_OPEN, rep
    if disp == "fixed":
        receipt = rep.get("dispositionReceipt")
        if isinstance(receipt, dict) and receipt.get("kind") == "full-panel-not-reraised":
            return _FIXED, f"fixed; the full panel in round {receipt.get('panelRound')} did not raise it again", rep
        return _FIXED, f"fixed and audited in round {rep.get('dispositionRound')}", rep
    if disp == "refuted":
        why = _text(rep.get("refutedReason"))
        return (_LEFT_FOR_OWNER if (why or "").startswith("author-justified") else _SHOWN_WRONG), why, rep
    if disp in (_CRAFT, _LEFT_FOR_OWNER, _RULING):  # the end-of-loop settle names its outcome and reason
        return disp, _text(rep.get("settledReason")), rep
    why = _text(rep.get("outOfScopeReason"))
    ruling = _latest_ruling(rep, by_key, rulings)
    prov = ruling.get("provenance") if ruling.get("ruling") == "out-of-scope" else None
    by, at = (_text(prov.get("ruledBy")), _text(prov.get("ruledAt"))) if isinstance(prov, dict) else (None, None)
    if by and at:  # only an attributed ruling settles an out-of-scope finding
        return _RULING, f"{why} (ruled by {by}, {at})", rep
    return _LEFT_FOR_OWNER, why, rep


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
    rulings = {r["findingKey"]: r for r in log if isinstance(r, dict) and isinstance(r.get("findingKey"), str)}  # the latest ruling per key stands
    for p in state.get("_policyApplied") if isinstance(state.get("_policyApplied"), list) else []:
        act = p.get("action") if isinstance(p, dict) and p.get("source") == _OWNER_SUPPLIED \
            and p.get("phase") == round_phases.P_JUDGMENT else None  # the owner-supplied source string; the driver is not importable here
        prov = act.get("_provenance") if isinstance(act, dict) else None
        if isinstance(prov, dict) and _text(prov.get("ruledBy")) and _text(prov.get("ruledAt")):
            for d in act.get("dispositions") if isinstance(act.get("dispositions"), list) else []:
                if isinstance(d, dict) and d.get("disposition") == "skip" and isinstance(d.get("id"), str):
                    rulings.setdefault(d["id"], {"ruling": "out-of-scope", "provenance": prov})
    out = []
    for key, row in content.items():
        if row.get("summaryEntry"):
            continue
        outcome, reason, rep = (None, STILL_OPEN, None) if key not in by_key else _decide(by_key[key], by_key, rulings)
        if rep is not None and reason and sc.finding_identity_key(rep) != key:
            reason += f" (merged into {_id(rep, sc.finding_identity_key(rep))})"
        dim = row.get("dimension")
        out.append({"id": _id(row, key), "findingKey": key, "outcome": outcome, "reason": reason,
                    "decidedBy": _decided_by(rep, outcome) if rep is not None else None,
                    "reviewer": ", ".join(map(str, dim)) if isinstance(dim, list) else _text(dim),
                    **{k: row.get(k) for k in ("title", "severity", "file", "line", "consequence")},
                    "body": row.get("body", row.get("detail"))})
    return out


def _original_maker_families(state, fix_round):
    """Maker families named by the maps submitted no later than the first fix's round (a round's map is
    folded before that round's fix); the seeded and legacy maps (non-numeric round) count."""
    early = [e for e in seat_map_receipts.receipts(state)
             if not str(e.get("round")).isdigit() or int(str(e["round"])) <= fix_round]
    return receipt_disclosures.accumulated_maker_families({**state, "seatMapReceipts": early, "seatMap": None})


def _ceiling(cfg):
    """The round ceiling the driver applied: the configured one when it is a number, else the one it resolves
    from the configuration; None when no usable ceiling resolves."""
    named = cfg.get("maxRoundsAbsolute")
    if _int(named):
        return named
    found, refusal = circuit_breaker.resolve_round_ceiling(cfg.get("maxRounds"), named)
    return found if refusal is None and _int(found) else None


def _refused(rounds):
    """The findings a reviewer raised that the round's compile dropped, in round order."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        drops = rounds[n].get("compileDrops") if isinstance(rounds[n], dict) else None
        for d in drops if isinstance(drops, list) else []:
            if isinstance(d, dict) and _text(d.get("title")) and _text(d.get("reason")):
                out.append({"file": d.get("file"), "line": d.get("line"), "title": d["title"],
                            "reason": d["reason"], "round": int(n)})
    return out


def _wider_rounds(rounds):
    """``[{round, why}]`` for every round whose recorded focus is wider, in round order."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        focus = rounds[n].get("focus") if isinstance(rounds[n], dict) else None
        if isinstance(focus, dict) and focus.get("on") == "wider":
            out.append({"round": int(n), "why": focus.get("why")})
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
    if state["terminal"] not in decision_kinds.CERTIFIED_VERDICTS:
        raise Refusal(UNSUPPORTED, "the session ended on a terminal that is not a certified verdict")
    by_hand = not any(r.get("outcome") == "recorded" and isinstance(r.get("seat"), str) for r in rows)
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    decisions = [d for d in state.get("decisions") or [] if isinstance(d, dict)]
    findings = _findings(state)
    if by_hand:  # a hand submit journals no seat: the rounds' seat status is the only record of who ran
        reviewers, raw = _status_reviewers(state, meta.get("headSha")), []
    else:
        reviewers, raw = _reviewers(state, session_dir, rows, extras.get("runDirs", []),
                                    review_record._readers(readers)["engine_run"], raw_dir)
    checked = list(extras.get("checked", [])) + ([HAND_SUBMIT_NOTE] if by_hand else [])
    makers, fam = list(extras.get("makers", [])), receipt_disclosures.author_family(state)
    baseline = receipt_disclosures.accumulated_maker_families(state)
    # a family a seat map already named a maker faced the whole review: the loop fixer's delayed fromStep must not
    # shadow that baseline entry, or the original maker would drop out of the early panels' independence check
    # ...but a family first named by a map submitted after the first fix was introduced by that fix, not a maker
    # of the original change: the cumulative union stays the baseline for later auditor selection, while only
    # the maps submitted up to the first fix decide whether the fixer's family faced the whole review
    fixed = [int(n) for n, r in rounds.items() if isinstance(r, dict) and "fix" in r and str(n).isdigit()]
    original = _original_maker_families(state, min(fixed)) if fixed else baseline
    if fam and fam not in original and any(isinstance(r, dict) and "fix" in r for r in rounds.values()) \
            and not any(isinstance(m, dict) and m.get("family") == fam for m in makers):
        makers.append({"family": fam, "source": "review loop fixer",
                       **({"fromStep": 2 * min(fixed) + 1} if fixed else {})})
    for family in sorted(baseline):
        if not any(isinstance(m, dict) and m.get("family") == family for m in makers):
            makers.append({"family": family, "source": "seat map maker list"})
    wider = _wider_rounds(rounds)
    last = decisions[-1] if decisions else {}
    cause = decision_kinds.map_terminal_cause(state["terminal"], last.get("kind")) or {}
    capped = decision_kinds.map_verdict_to_terminal_state(state["terminal"]) == "cap" or cause.get("reason") == "budget"
    ceiling = cause.get("reason") == "budget"  # a round-ceiling stop, not a stop at the configured round cap
    return {"schema": review_record.ACCOUNT_SCHEMA, "pr": extras["pr"], "repo": extras.get("repo"), "lane": "full",
            "laneReason": extras.get("laneReason"), "ci": extras.get("ci"), "sessionId": meta["sessionId"],
            "finalCommit": _text(meta.get(sc.FIX_FOLD_HEAD_KEY), cfg.get(sc.FIX_FOLD_HEAD_KEY), meta.get("headSha"),
                                 cfg.get("headSha")),
            "rounds": {"count": len(rounds), "cap": _ceiling(cfg) if ceiling else cfg["maxRounds"] if _int(cfg.get("maxRounds")) else None,
                       "capKind": review_record.CAP_KINDS[1] if ceiling else review_record.CAP_KINDS[0], "stoppedAtCap": capped,
                       **({"wider": wider} if wider else {})},
            "reviewers": reviewers, "makers": makers, "findings": findings, "rawFindingsFiles": raw,
            "refused": _refused(rounds), "sheetAnswers": extras.get("sheetAnswers"), "baseRef": extras.get("baseRef") or (cfg["baseRef"] if isinstance(cfg.get("baseRef"), str) else None),
            "goAheads": extras.get("goAheads", []), "checked": checked}


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
