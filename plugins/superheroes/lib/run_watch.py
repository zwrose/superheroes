#!/usr/bin/env python3
import argparse
import calendar
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_state
import checkpoint
import control_plane
import docload
import journal
import ref_lock
import task_list

REVIEW_ROOT = "/tmp"


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clock(ts):
    if isinstance(ts, str) and len(ts) >= 19 and ts[10] == "T":
        return ts[11:19]
    return time.strftime("%H:%M:%S", time.gmtime())


def _parse_iso_epoch(ts):
    if not isinstance(ts, str):
        return None
    try:
        return calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return None


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _age(ts):
    epoch = _parse_iso_epoch(ts)
    if epoch is None:
        return "—"
    seconds = max(0, int(time.time() - epoch))
    if seconds < 60:
        return "%ds ago" % seconds
    minutes = seconds // 60
    if minutes < 60:
        return "%dm ago" % minutes
    hours = minutes // 60
    if hours < 48:
        return "%dh ago" % hours
    return "%dd ago" % (hours // 24)


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _phase_unknown():
    return {"available": False, "value": "unknown", "step": None, "total": len(checkpoint.CURRENT_PHASES)}


def _read_checkpoint(root, work_item):
    try:
        data = checkpoint.read(control_plane.paths(root, work_item)["checkpoint"])
    except Exception:
        return _phase_unknown(), {}, None
    if not isinstance(data, dict) or data.get("_incompatible"):
        return _phase_unknown(), {}, None

    phase = data.get("lastGoodPhase") or data.get("phase") or "unknown"
    step_index = data.get("lastGoodStep")
    step = None
    if isinstance(step_index, int) and not isinstance(step_index, bool):
        step = step_index + 1
    elif phase in checkpoint.CURRENT_PHASES:
        step = checkpoint.CURRENT_PHASES.index(phase) + 1
    phase_info = {
        "available": True,
        "value": phase,
        "step": step,
        "total": len(checkpoint.CURRENT_PHASES),
        "updated_at": data.get("updatedAt"),
        "pr": data.get("pr"),
    }
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    return phase_info, gates, data.get("updatedAt")


def _review_dir_for(work_item, phase):
    if not phase or phase == "unknown":
        pattern = os.path.join(REVIEW_ROOT, "showrunner-%s-*" % glob.escape(work_item))
        candidates = [p for p in glob.glob(pattern) if os.path.isdir(p)]
    else:
        prefix = "showrunner-%s-%s" % (work_item, phase)
        pattern = os.path.join(REVIEW_ROOT, glob.escape(prefix) + "*")
        candidates = []
        for path in glob.glob(pattern):
            if not os.path.isdir(path):
                continue
            base = os.path.basename(path)
            if base == prefix or base.startswith(prefix + "-"):
                candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _normalize_dimension(info):
    info = info if isinstance(info, dict) else {}
    findings = info.get("findings") if isinstance(info.get("findings"), list) else []
    titles = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        title = finding.get("title") or finding.get("taxonomy") or finding.get("file")
        if title:
            titles.append(str(title))
    blocking = info.get("blockingCount", info.get("blocking_count", 0))
    blocking = _safe_int(blocking)
    return {
        "status": str(info.get("status") or ("findings" if blocking else "unknown")),
        "tier": info.get("tier"),
        "blocking_count": blocking,
        "has_findings": bool(info.get("hasFindings")) if "hasFindings" in info else bool(findings),
        "finding_titles": titles,
    }


def _read_review(root, work_item, phase):
    try:
        run_dir = _review_dir_for(work_item, phase)
        if not run_dir:
            return {"available": False}
        records = _read_json(os.path.join(run_dir, "round-records.json"), [])
        telemetry = _read_json(os.path.join(run_dir, "review-telemetry.json"), {})
        terminal = _read_json(os.path.join(run_dir, "terminal-record.json"), {})
        last_round = {}
        if isinstance(records, list) and records and isinstance(records[-1], dict):
            last_round = records[-1]
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        terminal = terminal if isinstance(terminal, dict) else {}
        if not last_round and not telemetry and not terminal:
            return {"available": False, "run_dir": run_dir}
        dims = last_round.get("dimensions") if isinstance(last_round.get("dimensions"), dict) else {}
        return {
            "available": True,
            "run_dir": run_dir,
            "round": terminal.get("round") or last_round.get("round") or telemetry.get("roundCount"),
            "terminal": terminal.get("terminal") or telemetry.get("terminal"),
            "gate": terminal.get("gate"),
            "reason": terminal.get("reason"),
            "dimensions": {name: _normalize_dimension(info) for name, info in dims.items()},
        }
    except Exception:
        return {"available": False}


def _task_total(root, work_item):
    try:
        _fm, body = docload.load_doc(docload.tasks_doc_path(work_item, root))
        return len(task_list.parse(body))
    except Exception:
        return None


def _read_build(root, work_item):
    try:
        state = build_state.read_state(build_state.state_path(root, work_item))
        reviewed = state.get("reviewed") if isinstance(state.get("reviewed"), dict) else {}
        built = state.get("built") if isinstance(state.get("built"), dict) else {}
        return {
            "available": True,
            "reviewed": len(reviewed),
            "built": len(built),
            "total": _task_total(root, work_item),
            "final_review": state.get("final_review"),
        }
    except Exception:
        return {"available": False, "reviewed": 0, "built": 0, "total": None, "final_review": None}


def _last_event(events, *types):
    wanted = set(types)
    for event in reversed(events or []):
        if event.get("type") in wanted:
            return event
    return None


def _read_run(root, work_item, events):
    last_park = _last_event(events, "parked")
    try:
        store = control_plane.checkout_dir(root)
        if os.path.isdir(os.path.join(store, ".git")):
            _sha, lease = ref_lock.read_lease(store, work_item)
            if isinstance(lease, dict):
                ttl = lease.get("ttl") or ref_lock.DEFAULT_TTL
                stale = ref_lock.is_stale(lease, ttl)
                holder = "%s:%s" % (lease.get("host") or "?", lease.get("pid") or "?")
                return {
                    "state": "stale" if stale else "active",
                    "detail": "lease held, stale" if stale else "lease held, fresh",
                    "holder": holder,
                    "last_park": (last_park or {}).get("detail"),
                }
    except Exception:
        pass

    last = (events or [])[-1] if events else None
    state = "unknown"
    if isinstance(last, dict):
        typ = last.get("type")
        if typ == "run_completed":
            state = "completed"
        elif typ == "parked":
            state = "parked"
        elif typ in ("run_started", "resumed", "lease_acquired", "lease_reclaimed",
                     "step_entered", "step_completed", "gate", "ci_fix_attempt",
                     "phase_record", "external_dispatch", "notify"):
            state = "active"
        elif typ == "error":
            state = "error"
    return {"state": state, "detail": "from events" if state != "unknown" else None,
            "last_park": (last_park or {}).get("detail")}


def gather(root, work_item):
    root = os.path.abspath(root)
    phase_info, gates, checkpoint_updated = _read_checkpoint(root, work_item)
    paths = control_plane.paths(root, work_item)
    try:
        events = journal.read_events(paths["events"])
    except Exception:
        events = []
    latest_ts = checkpoint_updated
    if events:
        latest_ts = events[-1].get("ts") or latest_ts
    return {
        "work_item": work_item,
        "root": root,
        "phase": phase_info,
        "gates": gates,
        "review": _read_review(root, work_item, phase_info.get("value")),
        "build": _read_build(root, work_item),
        "run": _read_run(root, work_item, events),
        "events": events,
        "updated_at": latest_ts,
        "updated": _age(latest_ts),
        "clock": _clock(latest_ts or _now_iso()),
    }


def _gate_mark(value):
    if value == "passed":
        return "✓"
    if value in ("changes-requested", "failed", "blocked"):
        return "✗"
    return "–"


def _dimension_is_clean(dim):
    status = str((dim or {}).get("status") or "").lower()
    if _safe_int((dim or {}).get("blocking_count")) > 0:
        return False
    if status in ("clean", "passed", "pass", "ok", "skipped"):
        return True
    return not bool((dim or {}).get("has_findings"))


def _dimension_snapshot(name, dim):
    if _dimension_is_clean(dim):
        return "%s ✓" % name
    blocking = _safe_int((dim or {}).get("blocking_count"))
    if blocking:
        label = "blocking" if blocking == 1 else "blocking"
        return "%s ✗(%d %s)" % (name, blocking, label)
    return "%s ✗" % name


def _count(value, total):
    if total is None:
        return str(value)
    return "%s/%s" % (value, total)


def _final_review_label(final_review):
    if not isinstance(final_review, dict):
        return "pending"
    return "clean" if final_review.get("clean") is True else "dirty"


def render_snapshot(snapshot):
    snap = snapshot or {}
    phase = snap.get("phase") or {}
    gates = snap.get("gates") or {}
    phase_value = phase.get("value") or "unknown"
    step, total = phase.get("step"), phase.get("total")
    step_text = "  (step %s/%s)" % (step, total) if step and total else ""
    lines = [
        "showrunner · %s" % (snap.get("work_item") or "unknown"),
        "  phase   %s%s     gates  review %s  test %s" % (
            phase_value, step_text, _gate_mark(gates.get("review")), _gate_mark(gates.get("test"))),
    ]

    review = snap.get("review") or {}
    if not review.get("available"):
        lines.append("  review  — (no review yet)")
    else:
        dims = review.get("dimensions") if isinstance(review.get("dimensions"), dict) else {}
        parts = [_dimension_snapshot(name, dim) for name, dim in dims.items()]
        round_text = "round %s" % (review.get("round") or "?")
        suffix = "   → %s" % review.get("terminal") if review.get("terminal") else ""
        lines.append("  review  %s    %s%s" % (round_text, " · ".join(parts) if parts else "—", suffix))

    build = snap.get("build") or {}
    if not build.get("available"):
        lines.append("  build   —")
    else:
        total = build.get("total")
        lines.append("  build   tasks %s reviewed · %s built     final-review %s" % (
            _count(build.get("reviewed", 0), total),
            _count(build.get("built", 0), total),
            _final_review_label(build.get("final_review")),
        ))

    run = snap.get("run") or {}
    state = run.get("state") or "unknown"
    detail = run.get("detail")
    state_text = "%s (%s)" % (state, detail) if detail else state
    lines.append("  run     %s         last park  %s" % (state_text, run.get("last_park") or "—"))
    lines.append("  updated %s" % (snap.get("updated") or "—"))
    return "\n".join(lines)


def _diff_prefix(curr):
    return curr.get("clock") or _clock(curr.get("updated_at") or _now_iso())


def _blocking_line(prefix, round_no, name, dim):
    blocking = _safe_int((dim or {}).get("blocking_count"))
    title = ""
    titles = (dim or {}).get("finding_titles") or []
    if titles:
        title = " (%s)" % ", ".join(str(t) for t in titles[:3])
    return "%s  · round %s %s ✗ %d blocking%s" % (prefix, round_no or "?", name, blocking, title)


def diff(prev_snapshot, curr_snapshot):
    prev, curr = prev_snapshot or {}, curr_snapshot or {}
    prefix = _diff_prefix(curr)
    lines = []
    prev_review, curr_review = prev.get("review") or {}, curr.get("review") or {}
    if curr_review.get("available"):
        curr_round = curr_review.get("round")
        if curr_round and curr_round != prev_review.get("round"):
            lines.append("%s  → %s round %s started" % (
                prefix, (curr.get("phase") or {}).get("value") or "unknown", curr_round))
        prev_dims = prev_review.get("dimensions") if isinstance(prev_review.get("dimensions"), dict) else {}
        curr_dims = curr_review.get("dimensions") if isinstance(curr_review.get("dimensions"), dict) else {}
        for name, dim in curr_dims.items():
            prev_dim = prev_dims.get(name, {})
            if _safe_int((dim or {}).get("blocking_count")) > 0 and (
                    _safe_int((prev_dim or {}).get("blocking_count")) != _safe_int((dim or {}).get("blocking_count"))
                    or (prev_dim or {}).get("status") != (dim or {}).get("status")):
                lines.append(_blocking_line(prefix, curr_round, name, dim))
        terminal = curr_review.get("terminal")
        if terminal and terminal != prev_review.get("terminal"):
            lines.append("%s  → round %s verdict: %s" % (prefix, curr_round or "?", terminal))

    prev_build, curr_build = prev.get("build") or {}, curr.get("build") or {}
    if curr_build.get("available"):
        total = curr_build.get("total")
        for key, label in (("reviewed", "reviewed"), ("built", "built")):
            if curr_build.get(key) != prev_build.get(key):
                lines.append("%s  · build task %s %s" % (
                    prefix, _count(curr_build.get(key, 0), total), label))
    return lines


def _detail_suffix(evt):
    detail = (evt or {}).get("detail")
    return " · %s" % detail if detail else ""


def format_journal_event(evt):
    evt = evt or {}
    typ = evt.get("type") or "event"
    clock = _clock(evt.get("ts"))
    step = evt.get("step")
    detail = evt.get("detail")
    if typ == "run_started":
        return "%s  ▶ run started%s" % (clock, _detail_suffix(evt))
    if typ == "step_entered":
        return "%s  → %s" % (clock, step or detail or "step")
    if typ == "step_completed":
        return "%s  ✓ %s" % (clock, step or detail or "step completed")
    if typ == "gate":
        gate = detail or ((evt.get("payload") or {}).get("gate") if isinstance(evt.get("payload"), dict) else None)
        if gate == "passed":
            return "%s  ✓ %s gate passed" % (clock, step or "gate")
        return "%s  → %s gate %s" % (clock, step or "gate", gate or "recorded")
    if typ == "ci_fix_attempt":
        return "%s  ↻ ci fix attempt%s" % (clock, _detail_suffix(evt))
    if typ == "parked":
        return "%s  ‼ parked%s" % (clock, _detail_suffix(evt))
    if typ == "resumed":
        return "%s  ▶ resumed%s" % (clock, _detail_suffix(evt))
    if typ == "run_completed":
        return "%s  ✓ run completed%s" % (clock, _detail_suffix(evt))
    if typ in ("lease_acquired", "lease_reclaimed"):
        return "%s  · %s%s" % (clock, typ.replace("_", " "), _detail_suffix(evt))
    return "%s  · %s%s" % (clock, typ.replace("_", " "), _detail_suffix(evt))


def _dq(value):
    value = os.path.abspath(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def watch_command(lib_dir, root, work_item):
    script = os.path.join(os.path.abspath(lib_dir), "run_watch.py")
    return 'python3 %s --work-item %s --root %s --follow' % (
        _dq(script),
        str(work_item),
        _dq(root),
    )


def _print(text):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def main(argv):
    ap = argparse.ArgumentParser(description="Read-only live watch for a superheroes showrunner run")
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--root", default=os.getcwd())
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--print-command", action="store_true")
    args = ap.parse_args(argv[1:])
    lib_dir = os.path.dirname(os.path.abspath(__file__))

    if args.print_command:
        _print(watch_command(lib_dir, args.root, args.work_item))
        return 0

    prev = gather(args.root, args.work_item)
    _print(render_snapshot(prev))
    if not args.follow:
        return 0

    seen = max([_safe_int(e.get("seq")) for e in prev.get("events") or []] or [0])
    try:
        while True:
            time.sleep(max(0.1, args.interval))
            curr = gather(args.root, args.work_item)
            new_events = [e for e in curr.get("events") or [] if _safe_int(e.get("seq")) > seen]
            for event in sorted(new_events, key=lambda e: _safe_int(e.get("seq"))):
                _print(format_journal_event(event))
                seen = max(seen, _safe_int(event.get("seq")))
            for line in diff(prev, curr):
                _print(line)
            prev = curr
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
