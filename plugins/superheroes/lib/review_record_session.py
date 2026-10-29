#!/usr/bin/env python3
"""The full review lane's review record, written from the finished session directory.

Every fact in the account comes from the session's own files (loop-state.json, driver-journal.jsonl,
meta.json, the stored seat envelopes), except the few the driver never holds, which come from one
extras file. This module decides no status and posts nothing: it builds a review-account/1 and hands
it to review_record.write. A fact the session's files cannot establish takes the value that keeps the
record on the "not reviewed" side: an undecided outcome, a reviewer not run, or a refusal.

CLI:
  review_record_session.py write --session-dir DIR --extras FILE --repo-root DIR [--abandoned REASON]

--abandoned writes the record of a session the orchestrator closed before the loop ended: it reads
not-reviewed, and says so.
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
import break_it  # noqa: E402
import countable_lines  # noqa: E402
import decision_kinds  # noqa: E402
import dispatch_outcome  # noqa: E402
import pr_body_stage  # noqa: E402
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
NOT_ABANDONABLE = "review-session-not-abandonable"
ABANDON_REASON_MISSING = "review-session-abandon-reason-missing"
BAD_EXTRAS = "review-session-extras-invalid"
CARRIED = " (carried from the earlier review record)"
STILL_OPEN = "still open when the review loop ended"
HAND_SUBMIT_NOTE = "the session was driven by hand submit; reviewers' raw outputs were not stored"
ABANDONED_CHECKED = "the review loop was abandoned before it ended: %s"
UNFOLDED_FINDINGS_CHECKED = "findings in seat results that were recorded but never folded are listed as open findings"
UNFOLDED_OPEN = "recorded by a reviewer but never taken into the loop before it was closed"
NO_SEAT_RESULT = "the session recorded no seat result or seat status"
UNFILLED = "unfilled"
_OWNER_SUPPLIED = "owner-supplied"
_LEGACY_JUDGMENT_PHASE = "present-judgment"  # reads `_policyApplied` rows an earlier version wrote
_HANDED_BACK = "handed-back"
_HANDED_BACK_AT_CAP = ("round-cap", "extra-audit-open")
_RAW_PHASES = (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_SCOPED)
_PRE_FIX_PHASES = (round_phases.P_PANEL, round_phases.P_GAPSWEEP, round_phases.P_VERIFIERS)
# synthesis only groups already-raised findings into root causes: it raises, confirms, audits and grades
# nothing, so it is not a reviewer of the change and the account does not list it
_UNLISTED_PHASES = (round_phases.P_SYNTHESIS,)
_INGEST_CMDS = ("record-result", "record-missing", "advance")
_FIXED, _SHOWN_WRONG, _CRAFT, _LEFT_FOR_OWNER, _RULING = review_findings_schema.OUTCOMES
# the finding parts a later row must not erase: the live row's value wins, else the ledger row's
_FINDING_PARTS = ("grade", "repeatOf", "breakItRuns", "kindOfMistake")


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
    for k in ("runDirs", "goAheads", "makers", "checked", "carriedChecks", "ownerRulings"):
        if not isinstance(x.get(k, []), list):
            raise Refusal(BAD_EXTRAS, k)
    if not all(isinstance(d, str) and d for d in x.get("runDirs", [])):
        raise Refusal(BAD_EXTRAS, "runDirs")
    if x.get("sheetAnswers") is not None and not isinstance(x["sheetAnswers"], dict):
        raise Refusal(BAD_EXTRAS, "sheetAnswers")
    if x.get("baseRef") is not None and not (isinstance(x["baseRef"], str) and x["baseRef"]):
        raise Refusal(BAD_EXTRAS, "baseRef")


def _slots(rows):
    """Active review slots, {(phase, round, seat, occurrence): (attempt, row)}: highest attempt kept."""
    out = {}
    for r in rows:
        phase, seat, rnd, att = r.get("phase"), r.get("seat"), r.get("round"), r.get("attempt")
        if r.get("outcome") != "recorded" or not (isinstance(seat, str) and isinstance(phase, str)):
            continue  # a row naming no seat or phase names no reviewer
        if sc.run_kind_for_phase(phase) != sc.RUN_KIND_REVIEW or not (_int(rnd) and _int(att)):
            continue
        key = (phase, rnd, seat, r.get("occurrence", 0))
        if key not in out or att >= out[key][0]:
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


# The `(round N)` suffix a persisted reviewer name carries: the one home of the format. `_reviewer` and
# `_unfilled_reviewer` write it through REVIEWER_ROUND_FORMAT; REVIEWER_ROUND_SUFFIX is the pattern that strips it
# (review_learning's tally).
REVIEWER_ROUND_FORMAT = " (round {rnd})"
REVIEWER_ROUND_SUFFIX = re.compile(r"\s*\(round \d+\)$")


def _step(rnd, phase):
    """Where in the loop a reviewer sat: two steps a round, a panel, gap-sweep or verifier read before the
    round's fix (even), every other review phase after it (odd)."""
    return 2 * rnd + (0 if phase in _PRE_FIX_PHASES else 1)


def _reviewer(state, rnd, seat, stem, ran, env=None, ev=None, commit=None, run_dir=None, phase=None):
    seat_map = seat_map_receipts.round_governing_map(state, rnd).get("seats")
    entry = (seat_map.get(seat) if isinstance(seat_map, dict) else None) or {}
    env, ev = env or {}, ev or {}
    return {"name": f"{stem}{seat}{REVIEWER_ROUND_FORMAT.format(rnd=rnd)}", "planned": True, "ran": ran,
            "vendor": _text(env.get("vendor"), entry.get("vendor")) or "unknown",
            "model": _text(env.get("model"), entry.get("model"), ev.get("engineModel")) or "unknown",
            "commit": commit, "runDir": run_dir, "step": _step(rnd, phase) if phase else None}


def _unfilled_reviewer(rnd, seat):
    """A seat the round's map left unfilled: planned, never run, no vendor or model to name."""
    return {"name": f"{seat}{REVIEWER_ROUND_FORMAT.format(rnd=rnd)}", "planned": True, "ran": False, "vendor": UNFILLED,
            "model": UNFILLED, "commit": None, "runDir": None}


def _panel_rounds_with_status(state):
    """{round: seatStatus} for each round that recorded a seat status, in round order."""
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    return {int(n): rec["seatStatus"] for n, rec in sorted(rounds.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else -1)
            if str(n).isdigit() and isinstance(rec, dict) and isinstance(rec.get("seatStatus"), dict)}


def _panel_head(state, rnd, setup=None, phase=sc.PANEL_PHASE, field="headSha"):
    """The head the round's `phase` orders were emitted at (latest attempt). Round 1's panel carries no emission
    head: it ran before any fix, at the session-setup head (`setup` is the meta's). None when none is recorded."""
    anchors = state.get("_ordersAnchors")
    best = None
    for key, anchor in (anchors.items() if isinstance(anchors, dict) else ()):
        parts = str(key).split(":")
        if len(parts) == 3 and parts[0] == str(rnd) and parts[1] == phase and parts[2].isdigit() \
                and isinstance(anchor, dict) and isinstance(anchor.get(field), str) and anchor[field]:
            if best is None or int(parts[2]) > best[0]:
                best = (int(parts[2]), anchor[field])
    if best:
        return best[1]
    if phase != sc.PANEL_PHASE or str(rnd) != "1":
        return None
    cfg = state.get("config")
    return _text(cfg.get("headSha") if isinstance(cfg, dict) else None, setup)


def _audit_key(a):
    """The per-location audit target id: the transport key. The line-less `identity` is shared by same-title siblings."""
    return a.get("id") or a.get("identity")


def _audit_silent(a):
    """An audit entry the round recorded as silence: no result came back, so no auditor ran for that target."""
    return isinstance(a, dict) and a.get("reason") == audits_mod.NO_AUDIT_RESULT_REASON


def _audit_reviewers(state, rnd, audits, later=frozenset()):
    """One reviewer per auditor vendor whose authenticated audit result the round persisted, at the audits' emission head,
    and one unrun reviewer for a target the round recorded as silent that no later round `later` audited. Any other
    entry, a not-discharged ruling included, is an auditor that ran."""
    head = _panel_head(state, rnd, phase=round_phases.P_AUDITS)
    vendors = sorted({a["auditor"] for a in audits if isinstance(a, dict) and isinstance(a.get("auditor"), str) and a["auditor"]})
    unnamed = ["unknown"] if any(isinstance(a, dict) and not _audit_silent(a) and not a.get("auditor") for a in audits) else []
    out = [_reviewer(state, rnd, f"auditor {v}", "audits ", bool(head), {"vendor": v, "model": "unknown"},
                     commit=head, phase=round_phases.P_AUDITS) for v in vendors + unnamed]  # no recoverable head: stays a missing review
    silent = any(_audit_silent(a) and _audit_key(a) not in later for a in audits)
    return out + ([_reviewer(state, rnd, "auditor", "audits ", False, commit=head, phase=round_phases.P_AUDITS)] if silent else [])


_VERIFY_COUNTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED", "unverified", "ambiguous")


def _nothing_to_verify(state, rnd):
    """Whether the round's verifier phase had no staged finding: `verifyPasses` is a non-empty list and every entry is a dict whose
    verdict and unanswered counts are all present zeros. Anything else, a missing or malformed record included, had something to verify."""
    passes = (state["rounds"].get(str(rnd)) or {}).get("verifyPasses")
    return isinstance(passes, list) and bool(passes) and all(
        isinstance(p, dict) and all(_int(p.get(k)) and p[k] == 0 for k in _VERIFY_COUNTS) for p in passes)


def _status_reviewers(state, setup=None, rows=()):
    """Reviewer rows for a session driven by hand submit, which journals no seat: each panel round's seat
    status says which seats ran, and the reviewers' raw outputs were not stored."""
    status = _panel_rounds_with_status(state)
    # axis: a hand-submit session with no seat status in any round holds nothing that says a reviewer ran — see bite-proof record c7l3_wo2_session_writer
    if not any(status.values()):
        raise Refusal(UNSUPPORTED, NO_SEAT_RESULT)
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
            if ran and not fell and seat in ((state["rounds"].get(str(rnd)) or {}).get("fellOpenProvenanceMissing") or ()):
                fell = "unknown"  # the session could not establish which vendor ran: never credit the configured one
            out.append(_reviewer(state, rnd, seat, "", ran, {"vendor": fell, "model": "unknown"} if fell else None,
                                 commit=commit, phase=sc.PANEL_PHASE))
        out += [_unfilled_reviewer(rnd, seat) for seat in sorted(unfilled)
                if not any(r > rnd for r in ran_in.get(seat, ()))]
    by_round = {int(n): rec["audits"] for n, rec in state["rounds"].items()
                if str(n).isdigit() and isinstance(rec, dict) and isinstance(rec.get("audits"), list)}
    for rnd, audits in by_round.items():
        later = {_audit_key(a) for r, rows in by_round.items() if r > rnd for a in rows if isinstance(a, dict) and not _audit_silent(a)}
        out += _audit_reviewers(state, rnd, audits, later)
    for rnd, phase in sorted({(r["round"], r["phase"]) for r in rows if r.get("cmd") == "submit" and r.get("outcome") == "accepted"
                              and _int(r.get("round")) and r.get("phase") in (round_phases.P_VERIFIERS, *_RAW_PHASES[1:])}):
        # axis: a hand-accepted verifier phase with no staged finding is not a planned reviewer — see bite-proof record wo_6_1910_empty_verifier
        if phase == round_phases.P_VERIFIERS and _nothing_to_verify(state, rnd):
            continue
        prov = [p.get("ran") for p in ((state["rounds"].get(str(rnd)) or {}).get("verifierProvenance") or ()) if isinstance(p, dict)
                and p.get("outcome") == "verdicts-folded"] if phase == round_phases.P_VERIFIERS else []  # a hand-accepted verifier, gap sweep or scoped finder journals no seat: one row a phase; a verifier whose verdicts were ignored or empty never ran
        head = _panel_head(state, rnd, setup, phase)
        out.append(_reviewer(state, rnd, "reviewer", phase.removeprefix("dispatch-") + " ", bool(head) and (bool(prov) or phase != round_phases.P_VERIFIERS),
                             {"vendor": _text(*prov, _panel_head(state, rnd, None, phase, "vendor")) or "unknown", "model": "unknown"}, commit=head, phase=phase))
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
        row = _reviewer(state, rnd, seat, stem, key in ran, env,
                        r.get("executionEvidence") if isinstance(r.get("executionEvidence"), dict) else None,
                        _text(r.get("citedHead")), bound.get(key), phase)
        if phase == sc.PANEL_PHASE and key in ran:
            # axis: a panel reviewer that ran and reported no well-formed read list counts as having read nothing, never as unreported — see bite-proof record c1l5_wo_b_read_parts
            reported = body.get("readParts") if isinstance(body, dict) else None
            row["readParts"] = reported if review_record._items_fault(reported, review_record._part_fault) is None else []
        out.append(row)
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


def _decide(own, by_key, rulings, exempt=None):
    """(outcome, reason, representative): undecided unless the ledger shows a disposition newer than the finding.

    `exempt` maps a finding key to the driver's `ruled-out-of-scope` break-it row: a fixed finding named there
    was ruled out of scope and only cleared by the audit, so it reads as the ruling, never as fixed."""
    rep = sc.resolve_merged_into_entry(own, by_key)
    if not isinstance(rep, dict):
        return None, STILL_OPEN, None
    disp, seq, raised = rep.get("disposition"), rep.get(sc.DISPOSITION_SEQ_FIELD), own.get(sc.RAISED_SEQ_FIELD)
    if disp not in sc.DISPOSITIONS or not (_int(seq) and _int(raised) and seq > raised):  # a stale disposition decides nothing
        return None, STILL_OPEN, rep
    held = (exempt or {}).get(sc.finding_identity_key(rep))
    # axis: a fixed finding the driver ruled out of scope is the ruling in the record, never "fixed and audited" — see bite-proof record wo_a_2072_ruled_exempt
    if disp == "fixed" and isinstance(held, dict):
        return _RULING, f"ruled out of scope: {held.get('reason')} (ruled by {held.get('ruledBy')}, {held.get('ruledAt')})", rep
    if disp == "fixed":
        receipt = rep.get("dispositionReceipt")
        if isinstance(receipt, dict) and receipt.get("kind") == sc.FULL_PANEL_NOT_RERAISED:
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


MERGED_INTO_FORMAT = " (merged into {})"  # the one mark a merged member row's reason ends with
_MERGED_INTO = re.compile(r"\(merged into (.*)\)$")  # built from MERGED_INTO_FORMAT above; keep the two together


def merged_into(reason):
    """The representative id a merged member row's reason names (the mark `MERGED_INTO_FORMAT` writes), or None."""
    # the carry path appends CARRIED after the mark each later review; the mark's own end is what remains
    found = _MERGED_INTO.search(reason.replace(CARRIED, "")) if isinstance(reason, str) else None
    return found.group(1) if found else None


def _id(row, key):
    rid = row.get("id")
    return rid if isinstance(rid, str) and rid and not verification.is_staged_id(rid) else key


def _finding_parts(row, older):
    """{part: value} for each finding part: the row's own when it has the key, else the older (ledger) row's, else absent."""
    out = {}
    for k in _FINDING_PARTS:
        for src in (row, older):
            if isinstance(src, dict) and k in src:
                out[k] = src[k]
                break
    return out


def _findings(state):
    """The account's findings list."""
    return _findings_and_merges(state)[0]


def _findings_and_merges(state):
    """(the account's findings, a map of each merged member row's findingKey to its representative's findingKey).

    The map is the ledger's own resolved merge, the one `_decide` follows; a member whose merge does not
    resolve is not in it."""
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
            and p.get("phase") == _LEGACY_JUDGMENT_PHASE else None  # the owner-supplied source string; the driver is not importable here
        prov = act.get("_provenance") if isinstance(act, dict) else None
        if isinstance(prov, dict) and _text(prov.get("ruledBy")) and _text(prov.get("ruledAt")):
            for d in act.get("dispositions") if isinstance(act.get("dispositions"), list) else []:
                if isinstance(d, dict) and d.get("disposition") == "skip" and isinstance(d.get("id"), str):
                    rulings.setdefault(d["id"], {"ruling": "out-of-scope", "provenance": prov})
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    exempt = {r["findingKey"]: r for rec in rounds.values() if isinstance(rec, dict)
              for r in (rec.get("breakItKept") if isinstance(rec.get("breakItKept"), list) else [])
              if isinstance(r, dict) and r.get("outcome") == "ruled-out-of-scope" and isinstance(r.get("findingKey"), str)}
    out, merged = [], {}
    for key, row in content.items():
        if row.get("summaryEntry"):
            continue
        outcome, reason, rep = (None, STILL_OPEN, None) if key not in by_key else _decide(by_key[key], by_key, rulings, exempt)
        if rep is not None and sc.finding_identity_key(rep) != key:
            merged[key] = sc.finding_identity_key(rep)
        if rep is not None and reason and sc.finding_identity_key(rep) != key:
            reason += MERGED_INTO_FORMAT.format(_id(rep, sc.finding_identity_key(rep)))
        dim = row.get("dimension")
        # axis: a live row without a finding part keeps the ledger row's, so a newer row never erases an older row's part — see bite-proof record c1l1_wo_b_session_seam
        held = _finding_parts(row, by_key.get(key))
        out.append({"id": _id(row, key), "findingKey": key, "outcome": outcome, "reason": reason,
                    "decidedBy": _decided_by(rep, outcome) if rep is not None else None,
                    "reviewer": ", ".join(map(str, dim)) if isinstance(dim, list) else _text(dim),
                    **{k: row.get(k) for k in ("title", "severity", "file", "line", "consequence")},
                    "body": row.get("body", row.get("detail")), **held})
    return out, merged


def _original_maker_families(state, fix_round):
    """Maker families named by the maps submitted no later than the first fix's round (a round's map is
    folded before that round's fix); the seeded and legacy maps (non-numeric round) count."""
    early = [e for e in seat_map_receipts.receipts(state)
             if not str(e.get("round")).isdigit() or int(str(e["round"])) <= fix_round]
    return receipt_disclosures.accumulated_maker_families({**state, "seatMapReceipts": early, "seatMap": None})


def _ceiling(cfg):
    """The round ceiling an earlier driver version applied to a session it wrote: the stored one when it is a
    number, the default it used when none was stored; None when the stored one is unusable."""
    named = cfg.get("maxRoundsAbsolute")
    if _int(named):
        return named
    return 10 if named is None else None  # reads state an earlier version wrote: its flat default ceiling


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


def _rerun_checks(rounds):
    """Every re-run check the rounds recorded, in round order; the containing round names each one."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        checks = rounds[n].get("rerunChecks") if isinstance(rounds[n], dict) else None
        # a malformed entry passes through unchanged: the writer's validation is the refusing layer
        out += [dict(e, round=int(n)) if isinstance(e, dict) else e for e in checks] if isinstance(checks, list) else []
    return out


def _synthesis_rounds(rows):
    """The sorted distinct rounds in which the synthesis step recorded a result (`recorded`, or a hand submit's
    `accepted`); a seat recorded missing is no result."""
    # axis: a record-missing synthesis row is no result and adds no round — see bite-proof record c1l1_wo_b_session_seam
    # axis: a hand submit journals "accepted" and counts as "recorded" does — see bite-proof record c1l1_wo_b_session_seam
    return sorted({r["round"] for r in rows if r.get("outcome") in ("recorded", "accepted")
                   and r.get("phase") == round_phases.P_SYNTHESIS
                   and r.get("cmd") != "record-missing" and _int(r.get("round"))})


def _line_key(value):
    """A finding's line as a comparable key: the coerced int when it coerces, else its repr."""
    ok, line = sc.coerce_line(value)
    return line if ok else repr(value)


def _file_key(value):
    """A finding's file as a comparable, hashable key: a string as itself, any other JSON value as a tagged repr."""
    return value if isinstance(value, str) else ("non-string", repr(value))


def _drop_key(rnd, title, file, line):
    """The key a compile drop and the finding it dropped share: round, title, file and line. A file that is not a
    string was recorded without its line, so for it the line is left out of the key."""
    # axis: a drop with no string file lost its line when recorded, so it is matched on round, title and file alone — see bite-proof record c1l1_wo_b_session_seam
    return (rnd, title, _file_key(file), _line_key(line) if isinstance(file, str) else None)


def _normalized(finding):
    """A copy of a stored reviewer finding with its line normalized as `mechanical_compile` does: a numeric-string
    line coerced to its int. A supplied findingKey is kept (an existing test pins that it matches a listed row)."""
    out = dict(finding)
    ok, line = sc.coerce_line(finding.get("line"))
    if ok:
        out["line"] = line
    return out


def _passed_break_it(rounds):
    """``{(round, title, file)}`` of each break-it run whose test passed. Under the current rules a passed run
    keeps its finding (the run judges nothing), so such a proposal is listed; a session that began under the
    earlier rules has passed proposals the intercept dropped before compile, which are in neither the listed
    findings nor the compile drops, and this settles them."""
    out = set()
    for n in rounds:
        runs = rounds[n].get("breakItRuns") if str(n).isdigit() and isinstance(rounds[n], dict) else None
        for r in runs if isinstance(runs, list) else []:
            if isinstance(r, dict) and r.get("outcome") == "passed" and isinstance(r.get("title"), str):
                out.add((int(n), r["title"], _file_key(r.get("file"))))
    return out


def _audit_candidates(payload):
    """The new-issue candidates a stored fix-audit result claims: only a `discharged-but-new-issue` ruling carries them."""
    if not (isinstance(payload, dict) and payload.get("ruling") == "discharged-but-new-issue"):
        return []
    raised = payload.get("newIssues")
    return [c for c in raised if isinstance(c, dict)] if isinstance(raised, list) else []


def _raised_reports(session_dir, rows, pending, pending_round):
    """``[(phase, round, seat, [finding])]``: each stored reviewer report, the stored fix-audit results' new-issue
    candidates, and the candidates an audit fold left pending in the state (`_newIssues`, folded only by the scoped step)."""
    out = []
    for key, (att, _) in _slots(rows).items():
        phase, rnd, seat, _ = key
        if phase not in _RAW_PHASES and phase != round_phases.P_AUDITS:
            continue
        env = _envelope(_path(session_dir, key, att))
        payload = env.get("payload") if isinstance(env, dict) else None
        if phase == round_phases.P_AUDITS:
            out.append((phase, rnd, seat, _audit_candidates(payload)))
            continue
        raised = payload.get("findings") if isinstance(payload, dict) else None
        out.append((phase, rnd, seat, raised if isinstance(raised, list) else []))
    if isinstance(pending, list) and pending:
        out.append((round_phases.P_AUDITS, pending_round, "auditor", [c for c in pending if isinstance(c, dict)]))
    return out


def _unfolded(session_dir, rows, rounds, findings, settled_rounds=None, settled_kinds=None, pending=None,
              pending_round=None):
    """One open finding row for each finding a reviewer recorded in a stored seat result that the loop never took in.

    A finding the account already lists, one an earlier seat stored the same, one the round's compile dropped
    (it stays under `refused`; matched by round, title, file and line, so a same-titled finding at another line
    stays; a drop whose file is not a string lost its line, so it is matched by round, title and file), and a break-it proposal whose test passed (the intercept dropped it before compile; only the test role's
    own panel proposal is settled that way) add nothing. A listed finding already settled in a round before the
    report's own round is reopened (`settled_rounds` maps a finding key to the round that settled it)."""
    settled_rounds = settled_rounds or {}
    settled_kinds = settled_kinds or {}  # a finding key to the kind of its recorded settlement
    listed = {f["findingKey"] for f in findings}
    by_listed = {f["findingKey"]: f for f in findings}
    dropped = {_drop_key(d["round"], d["title"], d["file"], d["line"]) for d in _refused(rounds)}
    passed = _passed_break_it(rounds)
    out = []
    for phase, rnd, seat, raised in _raised_reports(session_dir, rows, pending, pending_round):
        for f in raised:
            if not (isinstance(f, dict) and isinstance(f.get("title"), str) and f["title"].strip()):
                continue
            fkey = sc.finding_identity_key(_normalized(f))
            # axis: a finding the round's compile dropped stays under refused and is not listed a second time — see bite-proof record c1l1_wo_b_session_seam
            # axis: a break-it proposal whose test passed was dropped before compile and is no defect; kept for a session that began under the earlier rules, since the current intercept drops nothing — see bite-proof record c1l1_wo_b_session_seam
            # axis: that rule covers only the test role's own panel proposal (panel phase, test-role seat, break-it taxonomy) — see bite-proof record c1l1_wo_b_session_seam
            settled = phase == round_phases.P_PANEL and seat == break_it.ROLE and break_it.is_break_it(f) \
                and (rnd, f["title"], _file_key(f.get("file"))) in passed
            if _drop_key(rnd, f["title"], f.get("file"), f.get("line")) in dropped or settled:
                continue
            if fkey in listed:
                held = by_listed.get(fkey)
                # a report from a round after the one that settled the listed finding was never folded (a folded
                # re-report would have reopened the ledger row): the defect came back, so the row reads open again
                # the scoped finder is the one report phase that runs after a round's fix audit, so in the settling
                # round itself only its report postdates the settlement; the one exception is a refutation, which the
                # loop records after the scoped report is folded, so a same-round refuted row answers that report;
                # so does a same-round owner skip (out-of-scope): only a fix audit's `fixed` is reopened by it;
                # an audit's own new-issue candidate (stored or pending) is unprocessed whatever its identity, so
                # it too reopens the `fixed` row its own audit fold recorded
                if isinstance(held, dict) and held.get("outcome") is not None and _int(rnd) \
                        and _int(settled_rounds.get(fkey)) \
                        and (rnd > settled_rounds[fkey] or (rnd == settled_rounds[fkey]
                                                            and phase in (round_phases.P_SCOPED, round_phases.P_AUDITS)
                                                            and settled_kinds.get(fkey) == "fixed")):
                    held.update({"outcome": None, "reason": UNFOLDED_OPEN, "decidedBy": None})
                continue
            listed.add(fkey)
            fid = f.get("id")
            out.append({"id": fid if isinstance(fid, str) and fid.strip() else fkey, "findingKey": fkey, "title": f["title"],
                        "severity": f.get("severity"), "file": f.get("file"), "line": f.get("line"),
                        "consequence": f.get("consequence"), "body": f.get("body", f.get("detail")), "reviewer": seat,
                        "outcome": None, "reason": UNFOLDED_OPEN, "decidedBy": None})
    return out


def _wider_rounds(rounds):
    """``[{round, why}]`` for every round whose recorded focus is wider, in round order."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        focus = rounds[n].get("focus") if isinstance(rounds[n], dict) else None
        if isinstance(focus, dict) and focus.get("on") == "wider":
            out.append({"round": int(n), "why": focus.get("why")})
    return out


def _command_refusals(rounds):
    """``[{..., round}]``: every refusal a round's fixer reported, in round order. A round with no
    ``fix`` dict, or a ``fix`` without a ``refusals`` list (a session written before the key), yields
    nothing; the writer's validation is the refusing layer for a malformed entry."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        fix = rounds[n].get("fix") if isinstance(rounds[n], dict) else None
        refusals = fix.get("refusals") if isinstance(fix, dict) else None
        if isinstance(refusals, list):
            out += [dict(entry, round=int(n)) if isinstance(entry, dict) else entry for entry in refusals]
    return out


def account_from_session(session_dir, extras, readers=None, raw_dir=None, abandoned=None):
    _check_extras(extras)
    if abandoned is not None and not (isinstance(abandoned, str) and abandoned.strip()):
        raise Refusal(ABANDON_REASON_MISSING, "--abandoned needs a reason")
    if not os.path.isdir(session_dir):
        raise Refusal(UNREADABLE, "session dir")
    state = _read_json(os.path.join(session_dir, sc.STATE_FILE), sc.STATE_FILE)
    if not isinstance(state, dict):
        raise Refusal(UNREADABLE, sc.STATE_FILE)
    if abandoned is not None and state.get("terminal"):
        raise Refusal(NOT_ABANDONABLE, "the review loop ended; write its record without --abandoned")
    if abandoned is None and not state.get("terminal"):
        raise Refusal(NOT_TERMINAL, "the review loop has not ended")
    meta = _read_json(os.path.join(session_dir, sc.META_FILE), "meta.json sessionId")
    if not (isinstance(meta, dict) and _text(meta.get("sessionId"))):
        raise Refusal(UNREADABLE, "meta.json sessionId")
    rows = _journal(session_dir)
    if abandoned is None and state["terminal"] not in decision_kinds.CERTIFIED_VERDICTS:
        raise Refusal(UNSUPPORTED, "the session ended on a terminal that is not a certified verdict")
    by_hand = not any(r.get("outcome") == "recorded" and isinstance(r.get("seat"), str) for r in rows)
    cfg = state.get("config") if isinstance(state.get("config"), dict) else {}
    rounds = state.get("rounds") if isinstance(state.get("rounds"), dict) else {}
    decisions = [d for d in state.get("decisions") or [] if isinstance(d, dict)]
    findings, merged = _findings_and_merges(state)
    if abandoned is not None:  # the loop never took these in: each is listed open rather than only in a raw file
        # axis: in an abandoned session a finding recorded in a stored seat result but never folded is listed open — see bite-proof record c1l1_wo_b_session_seam
        ledger, _ = sc.read_disposition_ledger(state, required=False)
        by_key = {sc.finding_identity_key(r): r for r in ledger or [] if isinstance(r, dict)}
        settled_rounds = {k: sc.resolve_merged_into_entry(r, by_key).get("dispositionRound") for k, r in by_key.items()
                          if isinstance(sc.resolve_merged_into_entry(r, by_key), dict)}
        settled_kinds = {k: sc.resolve_merged_into_entry(r, by_key).get("disposition") for k, r in by_key.items()
                         if isinstance(sc.resolve_merged_into_entry(r, by_key), dict)}
        pending = state.get("_newIssues")
        findings += _unfolded(session_dir, rows, rounds, findings, settled_rounds, settled_kinds, pending,
                              state.get("round") if _int(state.get("round")) else None)
    if by_hand:  # a hand submit journals no seat: the rounds' seat status is the only record of who ran
        try:
            reviewers, raw = _status_reviewers(state, meta.get("headSha"), rows), []
        except Refusal as refusal:
            # an abandoned session may have run no seat yet: it lists no reviewer, and any other refusal still stands
            if abandoned is None or refusal.args[:2] != (UNSUPPORTED, NO_SEAT_RESULT):
                raise
            reviewers, raw = [], []
    else:
        reviewers, raw = _reviewers(state, session_dir, rows, extras.get("runDirs", []),
                                    review_record._readers(readers)["engine_run"], raw_dir)
    checked = list(extras.get("checked", [])) + ([HAND_SUBMIT_NOTE] if by_hand else [])
    pr_body_line = pr_body_stage.record_line(session_dir)
    if pr_body_line is not None:
        checked.append(pr_body_line)
    checked += _verify_via_checked(rounds)
    if abandoned is not None:
        checked += [ABANDONED_CHECKED % abandoned.strip(), UNFOLDED_FINDINGS_CHECKED]
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
    if abandoned is not None:
        cause, capped = {}, False  # no terminal to map
    else:
        cause = decision_kinds.map_terminal_cause(state["terminal"], last.get("kind")) or {}
        if state["terminal"] == _HANDED_BACK:
            # a hand-back stops at the cap only for the round cap and the extra audit; the others end early
            capped = last.get("kind") in _HANDED_BACK_AT_CAP
        else:
            capped = decision_kinds.map_verdict_to_terminal_state(state["terminal"]) == "cap" or cause.get("reason") == "budget"
    ceiling = cause.get("reason") == "budget"  # a round-ceiling stop, not a stop at the configured round cap
    rerun, synthesis = _rerun_checks(rounds), _synthesis_rounds(rows)
    extra = state.get("extraAudit")
    # the copies the proof still covers in the head diff the reviewers were last given: none whose section changed
    proven_copies = countable_lines.still_proven(
        state.get("provenCopies") or [], state.get("headDiff") or state.get("reviewedDiff"))
    # the extra audit round is labelled, never counted: it is a round of `rounds` the cap did not allow
    # axis: the extra audit round does not count toward rounds.count — see bite-proof record c1l4b_wo_a
    counted = len(rounds) - (1 if isinstance(extra, dict) and str(extra.get("round")) in rounds else 0)
    return {"schema": review_record.ACCOUNT_SCHEMA, "pr": extras["pr"], "repo": extras.get("repo"), "lane": "full",
            "laneReason": extras.get("laneReason"), "ci": extras.get("ci"), "sessionId": meta["sessionId"],
            "finalCommit": _text(meta.get(sc.FIX_FOLD_HEAD_KEY), cfg.get(sc.FIX_FOLD_HEAD_KEY), meta.get("headSha"),
                                 cfg.get("headSha")),
            "rounds": {"count": counted, "cap": _ceiling(cfg) if ceiling else cfg["maxRounds"] if _int(cfg.get("maxRounds")) else None,
                       "capKind": review_record.CAP_KINDS[1] if ceiling else review_record.CAP_KINDS[0], "stoppedAtCap": capped,
                       **({"wider": wider} if wider else {}),
                       **({"extraAudit": {"why": extra.get("why")}} if isinstance(extra, dict) else {})},
            **({"rerunChecks": rerun} if rerun else {}), **({"synthesisRounds": synthesis} if synthesis else {}),
            **{k: state[k] for k in ("outsideThisPR", "unreadShare") if k in state},
            **({"provenCopies": proven_copies} if proven_copies else {}),
            "reviewers": reviewers, "makers": makers, "findings": findings, "rawFindingsFiles": raw,
            "refused": _refused(rounds), "commandRefusals": _command_refusals(rounds), "sheetAnswers": extras.get("sheetAnswers"), "baseRef": extras.get("baseRef") or (cfg["baseRef"] if isinstance(cfg.get("baseRef"), str) else None),
            "goAheads": extras.get("goAheads", []), "carriedChecks": extras.get("carriedChecks", []),
            "ownerRulings": _owner_rulings(extras.get("ownerRulings", []), findings, merged), "checked": checked,
            **({"abandoned": {"reason": abandoned.strip()}} if abandoned is not None else {})}


def _verify_via_checked(rounds):
    """One `checked` line per round whose pass rested on a CI run in place of the local verify command."""
    out = []
    for n in sorted((n for n in rounds if str(n).isdigit()), key=int):
        via = rounds[n].get("verifyVia") if isinstance(rounds[n], dict) else None
        # axis: the review record names the verify used — see bite-proof record wo_b_2072_ci_verify
        if isinstance(via, dict) and via.get("via") == "ci-exact-head":
            out.append("Verify in round %s: CI workflow %s run %s on %s passed, in place of the local "
                       "verify command (%s)" % (n, via.get("workflow"), via.get("runId"),
                                                str(via.get("headSha"))[:7], via.get("reason")))
    return out


def _owner_rulings(entries, findings, merged):
    """The extras' ownerRulings, plus one entry per merged member of each finding an entry names.

    `merged` is `_findings_and_merges`' map of each member row's findingKey to its representative's findingKey, from the
    ledger's resolved merge, never from a reason's text or a display id (ids repeat across rounds). An entry
    names a row as the writer reads it (`review_record._ruling_hits`: raw findingKey, stored key or id); the
    ruling on the representative covers the members, unless an entry already names that member. A member whose
    merge did not resolve is not in `merged` and gets no entry. The writer validates the entries; one that is
    not a dict, or names no row here, is passed through unchanged. Rows carried from an earlier record are never
    expanded: the session names each one it means."""
    out = list(entries)
    for e in entries:
        key = e.get("key") if isinstance(e, dict) else None
        for i in review_record._ruling_hits(findings, key):
            rep = findings[i]
            for row in findings:
                # axis: a ruling on a merged group's representative covers its members — see bite-proof record wo_a_1958_owner_ruling
                if row is rep or merged.get(row["findingKey"]) != rep["findingKey"]:
                    continue
                if any(isinstance(o, dict) and review_record._ruling_hits([row], o.get("key")) for o in out):
                    continue
                out.append({"key": row["findingKey"], "url": e.get("url"), "words": e.get("words")})
    return out


def _earlier(account, extras, repo_root, readers):
    """The latest earlier record's findings, or [] when there is none.

    Any refusal other than "no earlier record", and any malformed findings list, reads as none: the
    writer makes its own refusal, so there is one place that refuses.
    """
    repo = extras.get("repo") or review_record._readers(readers)["repo_name"](repo_root)
    prior = review_record.read(account["pr"], repo, readers)
    earlier = prior.get("findings") if prior.get("ok") else None
    if not isinstance(earlier, list) or not all(isinstance(f, dict) for f in earlier):
        return []
    return earlier


def _fill(account, earlier):
    """Give each account finding the parts the earlier record held for it and the session's row lacks.

    A `grade`, `repeatOf` or `kindOfMistake` the row lacks is the earlier one; the earlier `breakItRuns` come first,
    followed by each of the row's runs not already among them. The earlier runs come from the posted record, which the
    writer scrubbed, so each of the row's runs is compared in its scrubbed form and appended in that form: a run
    the scrub changes is carried once, as the writer will post it."""
    held = {review_record._key(f): f for f in earlier}
    for f in account["findings"]:
        old = held.get(review_record._key(f))
        if old is None:
            continue
        for part in ("grade", "repeatOf", "kindOfMistake"):
            if part not in f and part in old:
                f[part] = old[part]
        # axis: the earlier record's break-it runs stay ahead of this session's new ones, none twice — see bite-proof record c1l1_wo_b_session_seam
        # a present non-list value is left as supplied, so the writer refuses it as review-account-invalid
        if isinstance(old.get("breakItRuns"), list) and isinstance(f.get("breakItRuns", []), list):
            mine = f.get("breakItRuns", [])
            runs = list(old["breakItRuns"])
            for run in mine:
                # axis: a current run is compared and appended as the writer will post it (scrubbed), so a run the scrub changed is carried once and not appended again on every rewrite — see bite-proof record c1l1_wo_b_session_seam
                shown = review_record._scrubbed(run) if isinstance(run, dict) else run
                if shown not in runs:
                    runs.append(shown)
            f["breakItRuns"] = runs


def _carried(account, earlier):
    """The latest earlier record's findings this session did not raise, as that record stored them."""
    present = {review_record._key(f) for f in account["findings"]}
    out = []
    for f in earlier:
        if review_record._key(f) in present:
            continue
        reason = f.get("reason")
        fresh = isinstance(reason, str) and reason and not reason.endswith(CARRIED)
        out.append(dict(f, reason=reason + CARRIED if fresh else reason))
    return out


def write_from_session(session_dir, extras_path, repo_root, readers=None, abandoned=None):
    tmp = []

    def go():
        tmp.append(tempfile.mkdtemp(prefix="review-record-"))
        try:
            with open(extras_path, encoding="utf-8") as fh:
                extras = json.load(fh)
        except (OSError, ValueError, TypeError):
            raise Refusal(BAD_EXTRAS, "extras file")
        account = account_from_session(session_dir, extras, readers, tmp[0], abandoned)
        earlier = _earlier(account, extras, repo_root, readers)
        _fill(account, earlier)
        account["findings"] += _carried(account, earlier)
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
    w.add_argument("--abandoned", default=None)
    args = p.parse_args(argv)
    result = write_from_session(args.session_dir, args.extras, args.repo_root, abandoned=args.abandoned)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
