#!/usr/bin/env python3
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint
import control_plane
import idempotent_write
import journal


def _payload(raw):
    try:
        return json.loads(raw)
    except ValueError:
        raise ValueError("malformed --payload JSON")


def _phase_records(path):
    records = []
    for event in journal.read_events(path):
        if event.get("type") == "phase_record":
            records.append(event.get("payload") or {})
    return records


def _reflects(paths, step, phase, payload):
    cp = checkpoint.read(paths["checkpoint"])
    if cp is None:
        cp = {}
    if cp.get("_incompatible"):
        return None, {"checkpoint": "incompatible", "reason": cp.get("reason")}
    records = _phase_records(paths["events"])
    journal_ok = any(record == payload for record in records)
    checkpoint_ok = cp.get("lastGoodStep") == step and cp.get("lastGoodPhase") == phase
    return journal_ok and checkpoint_ok, {
        "journal_confirmed": journal_ok,
        "checkpoint_confirmed": checkpoint_ok,
        "step": cp.get("lastGoodStep"),
        "phase": cp.get("lastGoodPhase"),
    }


def _append_cost(paths, cost):
    # #130: append the folded phase_cost telemetry event. Best-effort — a cost-write failure must
    # NEVER fail the phase-progress save (measurement only). Called ONLY inside the fresh-record
    # branch (tied to the phase_record's freshness), so a crash-resume that re-runs _apply — the
    # phase_record already present, the checkpoint stale — does NOT double-append the cost (which
    # cost_report.summarize would sum into an inflated run total).
    if not cost:
        return
    try:
        journal.append(paths["events"], "phase_cost", payload=cost, root=os.getcwd())
    except Exception:   # noqa: BLE001 — telemetry is best-effort; the phase save stands regardless
        pass


def _append_park(paths, park_reason):
    # #130: fold the terminal `parked` marker into the park's journalOnly save leaf (no new leaf —
    # #118). A run that parks mid-phase exits via parkFromPhases, which journals nothing itself and
    # only some phases (review-code, ship) post a readout — so without this marker a workhorse/plan/
    # tasks park carries no terminal event and token_trend/run_watch would misclassify it as 'other'
    # rather than parked, dropping it from the tokens-per-park average. Tied to the fresh-record
    # branch (exactly-once, resume-safe); best-effort.
    if park_reason is None:
        return
    try:
        journal.append(paths["events"], "parked", detail=str(park_reason), root=os.getcwd())
    except Exception:   # noqa: BLE001 — best-effort terminal marker
        pass


def _apply(paths, work_item, step, phase, payload, side, cost=None):
    if not any(record == payload for record in _phase_records(paths["events"])):
        journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd())
        _append_cost(paths, cost)   # exactly-once with the record (crash-resume dedupes both)
    cp = checkpoint.read(paths["checkpoint"]) or checkpoint.new(work_item, "")
    cp["lastGoodStep"] = step
    cp["lastGoodPhase"] = phase
    if "pr" in side:
        cp["pr"] = side["pr"]
    if side.get("ready") and isinstance(cp.get("pr"), dict):
        cp["pr"]["isDraft"] = False
    checkpoint.write(paths["checkpoint"], cp)
    reflects, detail = _reflects(paths, step, phase, payload)
    return reflects is True, detail


def _reflects_journal(paths, payload):
    journal_ok = any(record == payload for record in _phase_records(paths["events"]))
    return journal_ok, {"journal_confirmed": journal_ok}


def _apply_journal(paths, payload, cost=None, park_reason=None):
    if not any(record == payload for record in _phase_records(paths["events"])):
        journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd())
        _append_cost(paths, cost)     # exactly-once with the record (crash-resume dedupes both)
        _append_park(paths, park_reason)
    return _reflects_journal(paths, payload)


def save(args):
    try:
        payload = _payload(args.payload)
        side = json.loads(args.side) if args.side else {}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    # #130: the folded phase_cost payload (best-effort — a malformed value is dropped, never fatal).
    cost = None
    if getattr(args, "cost_payload", None):
        try:
            cost = json.loads(args.cost_payload)
        except ValueError:
            cost = None
    # #130: on a park (journal-only), the reason to fold into a `parked` terminal marker.
    park_reason = getattr(args, "terminal_park", None)
    paths = control_plane.paths(os.getcwd(), args.work_item)
    step = int(args.step)
    journal_only = bool(getattr(args, "journal_only", False))
    # --journal-only (#118 park tail): record the phase journal entry durably WITHOUT touching the
    # checkpoint cursor — a parked phase did not complete, so lastGoodStep must not advance (a
    # resume would otherwise skip the parked phase). Same idempotent-apply shape, journal-scoped.
    key = "phase:%s:step=%s:phase=%s:payload=%s" % (
        args.work_item,
        step,
        args.phase,
        json.dumps(payload, sort_keys=True),
    )
    if journal_only:
        result = idempotent_write.idempotent_apply(
            key + ":journal-only",
            lambda: _reflects_journal(paths, payload),
            lambda: _apply_journal(paths, payload, cost, park_reason),
        )
        detail = result.get("detail") or {}
        return {
            "ok": bool(result.get("ok")),
            "already": bool(result.get("already")),
            "applied": bool(result.get("applied")),
            "reason": result.get("reason"),
            "journal_confirmed": bool(detail.get("journal_confirmed")),
        }
    result = idempotent_write.idempotent_apply(
        key,
        lambda: _reflects(paths, step, args.phase, payload),
        lambda: _apply(paths, args.work_item, step, args.phase, payload, side, cost),
    )
    detail = result.get("detail") or {}
    return {
        "ok": bool(result.get("ok")),
        "already": bool(result.get("already")),
        "applied": bool(result.get("applied")),
        "reason": result.get("reason"),
        "journal_confirmed": bool(detail.get("journal_confirmed")),
        "checkpoint_confirmed": bool(detail.get("checkpoint_confirmed")),
        "step": detail.get("step"),
        "phase": detail.get("phase"),
    }


def main(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("save")
    s.add_argument("--work-item", required=True)
    s.add_argument("--step", required=True)
    s.add_argument("--phase", required=True)
    s.add_argument("--payload", required=True)
    s.add_argument("--json", dest="side", default=None)
    s.add_argument("--journal-only", dest="journal_only", action="store_true")
    s.add_argument("--cost-payload", dest="cost_payload", default=None,
                   help="#130: JSON phase_cost telemetry, folded into this save (best-effort)")
    s.add_argument("--terminal-park", dest="terminal_park", default=None,
                   help="#130: on a journal-only (park) save, the reason to fold into a `parked` marker")
    args = parser.parse_args(argv[1:])
    if args.cmd == "save":
        print(json.dumps(save(args), sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
