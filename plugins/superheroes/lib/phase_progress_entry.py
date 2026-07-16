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


def _append_park(paths, park_reason=None, park_payload=None):
    # #130: fold the terminal `parked` marker into the park's journalOnly save leaf (no new leaf —
    # #118). A run that parks mid-phase exits via parkFromPhases, which journals nothing itself and
    # only some phases (review-code, ship) post a readout — so without this marker a workhorse/plan/
    # tasks park carries no terminal event and token_trend/run_watch would misclassify it as 'other'
    # rather than parked, dropping it from the tokens-per-park average. Tied to the fresh-record
    # branch (exactly-once, resume-safe); best-effort.
    # #397 FR-11: doc-review parks carry a structured payload (decision list) instead of bare detail.
    if park_reason is None and park_payload is None:
        return
    try:
        if park_payload is not None:
            journal.append(paths["events"], "parked", payload=park_payload, root=os.getcwd())
        else:
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


def _has_leg_record(path, payload, leg_idem, force=False):
    # #434: a relaunched review leg re-enters a PARKED phase, runs it again, and parks again with a
    # byte-identical payload (the #397 no-net-progress treadmill parks). Keying phase-record freshness
    # on payload-equality ALONE dedupes that second leg's phase_record/phase_cost/parked away — the run
    # journal ends up quieter than the allowance ledger (the 2nd/3rd legs fired allowance_fired events
    # but journaled no phase story). With a per-leg idem nonce — minted resume-continuing by the spine
    # (engine_dispatch's #350 primitive) and baked once into the save command — freshness becomes "a
    # phase_record already carries THIS leg's idem": a genuine re-entry (a fresh nonce) records, while a
    # courier retry of ONE save (the same baked nonce) still dedupes to a single line.
    #
    # `force` is the UNSEEDABLE-park fail-safe. When the spine could not read the journal to seed a
    # nonce (the seed-read courier leaf dropped stdout, etc.) it sets --leg-force on the PARK save: this
    # returns "not present" so the park ALWAYS records. That mirrors #350's actual fail-safe DIRECTION
    # (its unseedable dispatch omits --idem and therefore always writes — a tolerated over-count),
    # instead of silently reverting a relaunch park to payload-equality dedup, which would recreate the
    # exact #434 under-recording bug on a transient seed drop (a real premortem finding). leg_idem is
    # None WITHOUT force only on the legacy/direct-call path -> byte-unchanged payload-equality dedup.
    if force:
        return False
    if leg_idem is None:
        return any(record == payload for record in _phase_records(path))
    for event in journal.read_events(path):
        if event.get("type") == "phase_record" and event.get("idem") == leg_idem:
            return True
    return False


def _reflects_journal(paths, payload, leg_idem=None, force=False):
    # A forced park never "already reflects" (it must always apply), so the idempotent-apply reader must
    # report not-reflected too — else idempotent_apply short-circuits before _apply_journal runs.
    journal_ok = _has_leg_record(paths["events"], payload, leg_idem, force)
    return journal_ok, {"journal_confirmed": journal_ok}


def _apply_journal(paths, payload, cost=None, park_reason=None, park_payload=None, leg_idem=None, force=False):
    if not _has_leg_record(paths["events"], payload, leg_idem, force):
        # #434: stamp the per-leg idem on the phase_record (top-level, like #350's external_dispatch) so
        # journal.append itself dedupes a courier retry AND the freshness read above distinguishes legs;
        # the folded cost/park ride under this same fresh-record gate (exactly-once with the record).
        journal.append(paths["events"], "phase_record", payload=payload, root=os.getcwd(), idem=leg_idem)
        _append_cost(paths, cost)     # exactly-once with the record (crash-resume dedupes both)
        _append_park(paths, park_reason, park_payload)
    # Read-back confirmation must NOT re-force (the record is now present regardless of the seed) — a
    # forced apply that then re-forced the reader would always report unconfirmed. Confirm on presence.
    journal_ok = any(record == payload for record in _phase_records(paths["events"]))
    return journal_ok, {"journal_confirmed": journal_ok}


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
    # #397 FR-11: structured doc-review park payload (decision list) — preferred over bare detail.
    park_payload = None
    if getattr(args, "terminal_park_payload", None):
        try:
            park_payload = json.loads(args.terminal_park_payload)
        except ValueError:
            park_payload = None
    # #434: the per-leg idem nonce for a park-save (journal-only). Minted resume-continuing by the spine
    # and baked into this command, so a relaunched leg that parks again earns a fresh phase_record while
    # a courier retry of one save reuses the same nonce and dedupes. Only the journal-only (park) path
    # consumes it — a completed phase advances the checkpoint cursor, so a resume SKIPS it and it can
    # never double-record. None (unseedable / non-park) -> legacy payload-equality dedup.
    leg_idem = getattr(args, "leg_idem", None)
    # #434: the unseedable-park fail-safe. The spine sets --leg-force when it could not read the journal
    # to seed a per-leg nonce, so a park still ALWAYS records (fail-safe toward recording — the #350
    # direction) instead of silently reverting to payload-equality dedup and re-hiding the relaunch park.
    leg_force = bool(getattr(args, "leg_force", False)) and leg_idem is None
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
            lambda: _reflects_journal(paths, payload, leg_idem, leg_force),
            lambda: _apply_journal(paths, payload, cost, park_reason, park_payload, leg_idem, leg_force),
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
    s.add_argument("--terminal-park-payload", dest="terminal_park_payload", default=None,
                   help="#397 FR-11: structured `parked` event payload (doc-review decision list)")
    s.add_argument("--leg-idem", dest="leg_idem", default=None,
                   help="#434: per-leg idem nonce so a relaunched park earns its own phase_record/cost/park")
    s.add_argument("--leg-force", dest="leg_force", action="store_true",
                   help="#434: unseedable-park fail-safe — record unconditionally instead of payload-dedup")
    args = parser.parse_args(argv[1:])
    if args.cmd == "save":
        print(json.dumps(save(args), sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
