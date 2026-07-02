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


def _apply(paths, work_item, step, phase, payload, side):
    if not any(record == payload for record in _phase_records(paths["events"])):
        journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd())
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


def _apply_journal(paths, payload):
    if not any(record == payload for record in _phase_records(paths["events"])):
        journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd())
    return _reflects_journal(paths, payload)


def save(args):
    try:
        payload = _payload(args.payload)
        side = json.loads(args.side) if args.side else {}
    except ValueError as e:
        return {"ok": False, "error": str(e)}
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
            lambda: _apply_journal(paths, payload),
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
        lambda: _apply(paths, args.work_item, step, args.phase, payload, side),
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
    args = parser.parse_args(argv[1:])
    if args.cmd == "save":
        print(json.dumps(save(args), sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
