#!/usr/bin/env python3
import argparse
import calendar
import glob
import json
import os
import re
import shlex
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import build_state
import checkpoint
import control_plane
import docload
import journal
import ref_lock
import review_memory
import task_list

REVIEW_ROOT = "/tmp"

# Plain-language labels for journal event types the live watch renders (CONVENTIONS §11 copy-holder;
# drift-guarded against journal.EVENT_TYPES in test_ssot_drift.py).
JOURNAL_EVENT_LABELS = {
    "run_started": "run started",
    "step_entered": "step entered",
    "step_completed": "step completed",
    "notify": "notify",
    "gate": "gate",
    "error": "error",
    "resumed": "resumed",
    "lease_acquired": "lease acquired",
    "lease_reclaimed": "lease reclaimed",
    "ci_fix_attempt": "ci fix attempt",
    "parked": "parked",
    "run_completed": "run completed",
    "phase_record": "phase record",
    "external_dispatch": "external dispatch",
    "phase_cost": "phase cost",
    "phases_skipped": "phases skipped",
    "permission_denied": "permission denied",
    "allowance_fired": "allowance fired",
    "final_review_handoff": "final review handoff",
    "routed_forward": "finding routed forward",
    "review_convergence": "review convergence",
    "handoff_provided": "handoff provided",
    # #402 Part B (merged from main): a courier answer carried a classifier-denial signature and
    # was declined terminally.
    "courier_declined": "courier declined",
    "manual_completion": "manually completed",
    "confinement_tripwire": "CONFINEMENT BREACH (engine wrote outside its worktree)",
}
KNOWN_JOURNAL_EVENT_TYPES = frozenset(JOURNAL_EVENT_LABELS)


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

    # #450: a TERMINAL `phase` marker (a hand-finished-after-park run) is authoritative — it
    # wins over the lastGoodPhase resume cursor, which stays truthfully frozen at where the
    # spine actually got to. So the record DISPLAYS "shipped-manual", not the stale parked phase.
    phase_marker = data.get("phase")
    if phase_marker in checkpoint.TERMINAL_PHASES:
        phase = phase_marker
    else:
        phase = data.get("lastGoodPhase") or phase_marker or "unknown"
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
    def _with_round_records(paths):
        return [p for p in paths
                if os.path.isfile(os.path.join(p, "round-records.json"))]

    if not phase or phase == "unknown":
        pattern = os.path.join(REVIEW_ROOT, "showrunner-%s-*" % glob.escape(work_item))
        candidates = _with_round_records([p for p in glob.glob(pattern) if os.path.isdir(p)])
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
        candidates = _with_round_records(candidates)
    if not candidates:
        review_prefix = "showrunner-%s-review-" % work_item
        pattern = os.path.join(REVIEW_ROOT, glob.escape(review_prefix) + "*")
        candidates = _with_round_records([p for p in glob.glob(pattern) if os.path.isdir(p)])
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def _phase_of_run_dir(run_dir, work_item):
    if not run_dir:
        return None
    rest = os.path.basename(run_dir)
    prefix = "showrunner-%s-" % work_item
    if not rest.startswith(prefix):
        return None
    rest = rest[len(prefix):]
    for phase in sorted(checkpoint.CURRENT_PHASES, key=len, reverse=True):
        if rest == phase or rest.startswith(phase + "-"):
            return phase
    return None


def _stale_review_phase(run_dir, work_item, phase):
    # When the active phase has no review dir of its own, _review_dir_for falls back to any
    # prior review dir. Flag that mismatch so the render can annotate the block as belonging
    # to an earlier phase instead of silently presenting stale review facts as current.
    if not phase or phase not in checkpoint.CURRENT_PHASES:
        return None
    dir_phase = _phase_of_run_dir(run_dir, work_item)
    return dir_phase if dir_phase and dir_phase != phase else None


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
        records_state = review_memory.load_records_state(
            os.path.join(run_dir, "round-records.json"), [])
        records = []
        if records_state.get("ok"):
            records = [review_memory.summarize_record(r)
                       for r in records_state.get("records") or []]
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
            "from_phase": _stale_review_phase(run_dir, work_item, phase),
            "round": terminal.get("round") or last_round.get("round") or telemetry.get("roundCount"),
            "terminal": terminal.get("terminal") or telemetry.get("terminal"),
            "gate": terminal.get("gate"),
            "reason": terminal.get("reason"),
            "dimensions": {name: _normalize_dimension(info) for name, info in dims.items()},
        }
    except Exception:
        return {"available": False}


def _active_phase_from_events(events, checkpoint_updated):
    checkpoint_epoch = _parse_iso_epoch(checkpoint_updated) or 0
    for event in reversed(events or []):
        if not isinstance(event, dict):
            continue
        event_epoch = _parse_iso_epoch(event.get("ts")) or 0
        if event_epoch and checkpoint_epoch and event_epoch < checkpoint_epoch:
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        phase = payload.get("phase")
        if isinstance(phase, str) and phase in checkpoint.CURRENT_PHASES:
            return phase
        step = event.get("step")
        if isinstance(step, str) and step in checkpoint.CURRENT_PHASES:
            return step
    return None


def _with_active_phase(phase_info, events, checkpoint_updated):
    active = _active_phase_from_events(events, checkpoint_updated)
    if not active:
        return phase_info
    out = dict(phase_info)
    out["value"] = active
    out["available"] = True
    out["step"] = checkpoint.CURRENT_PHASES.index(active) + 1
    return out


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
        if isinstance(event, dict) and event.get("type") in wanted:
            return event
    return None


def _park_cause(park_event):
    # #446: a park's cause is its bare `detail` OR, for a folded structured payload (assumption
    # parks, doc-review parks), payload.reason. Both the timeline and the run-summary read it here so
    # the summary's `last park` never goes blank for a payload-bearing park.
    if not isinstance(park_event, dict):
        return None
    detail = park_event.get("detail")
    if detail:
        return detail
    payload = park_event.get("payload") if isinstance(park_event.get("payload"), dict) else {}
    return payload.get("reason")


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
                    "last_park": _park_cause(last_park),
                }
    except Exception:
        pass

    last = (events or [])[-1] if events else None
    state = "unknown"
    detail = None
    if isinstance(last, dict):
        typ = last.get("type")
        if typ == "run_completed":
            state = "completed"
        elif typ == "manual_completion":
            # #450: a parked run finished BY HAND outside the spine — a genuine terminal
            # completion, distinguished from an automated run_completed so the record is
            # honest about HOW it shipped (not merely that it did).
            state = "completed"
            detail = "manual"
        elif typ == "parked":
            state = "parked"
        elif typ in ("run_started", "resumed", "lease_acquired", "lease_reclaimed",
                     "step_entered", "step_completed", "gate", "ci_fix_attempt",
                     "phase_record", "external_dispatch", "notify", "phases_skipped",
                     "routed_forward", "review_convergence", "handoff_provided"):
            state = "active"
        elif typ == "error":
            state = "error"
    return {"state": state,
            "detail": detail or ("from events" if state != "unknown" else None),
            "last_park": _park_cause(last_park)}


def gather(root, work_item):
    root = os.path.abspath(root)
    phase_info, gates, checkpoint_updated = _read_checkpoint(root, work_item)
    paths = control_plane.paths(root, work_item)
    try:
        # journal.read_events yields whatever each line parses to; a valid-JSON but
        # non-object line (a bare number, a list) would slip past its parse guard and
        # crash every downstream `.get()`. Filter to dicts here so the fail-soft contract
        # holds — a corrupt events line degrades the run line, it does not crash the watch.
        events = [e for e in journal.read_events(paths["events"]) if isinstance(e, dict)]
    except Exception:
        events = []
    phase_info = _with_active_phase(phase_info, events, checkpoint_updated)
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
    if status in ("clean", "passed", "pass", "ok"):
        return True
    return not bool((dim or {}).get("has_findings"))


def _dimension_snapshot(name, dim):
    # Blocking always wins — even a carried/skipped dimension that still holds a blocking
    # finding must read as ✗, never as a reassuring ✓ or a neutral dash.
    blocking = _safe_int((dim or {}).get("blocking_count"))
    if blocking:
        return "%s ✗(%d blocking)" % (name, blocking)
    if str((dim or {}).get("status") or "").lower() == "skipped":
        return "%s –" % name          # not run this round — distinct from a genuine ✓
    if _dimension_is_clean(dim):
        return "%s ✓" % name
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
        stale = "  (from %s)" % review["from_phase"] if review.get("from_phase") else ""
        suffix = "   → %s" % review.get("terminal") if review.get("terminal") else ""
        lines.append("  review  %s%s    %s%s" % (
            round_text, stale, " · ".join(parts) if parts else "—", suffix))

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
            blocker_changed = (
                _safe_int((prev_dim or {}).get("blocking_count")) != _safe_int((dim or {}).get("blocking_count"))
                or (prev_dim or {}).get("status") != (dim or {}).get("status")
                or (prev_dim or {}).get("finding_titles") != (dim or {}).get("finding_titles")
                or curr_round != prev_review.get("round")
            )
            if _safe_int((dim or {}).get("blocking_count")) > 0 and blocker_changed:
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


def _step_label(step, detail=None):
    # A phase-name string renders as the phase; a numeric index renders as "step N"
    # (the journal's step-index base is not guaranteed, so don't guess a phase name and
    # risk mislabeling); otherwise fall back to the event detail.
    if isinstance(step, str) and step in checkpoint.CURRENT_PHASES:
        return step
    if isinstance(step, bool):
        step = None
    if isinstance(step, int):
        return "step %d" % step
    if isinstance(step, str) and step.strip().lstrip("-+").isdigit():
        return "step %s" % step.strip()
    if isinstance(step, str) and step:
        return step
    return detail or "step"


def format_journal_event(evt):
    evt = evt or {}
    typ = evt.get("type")
    typ = typ if isinstance(typ, str) and typ else "event"
    clock = _clock(evt.get("ts"))
    step = evt.get("step")
    detail = evt.get("detail")
    if typ == "run_started":
        return "%s  ▶ run started%s" % (clock, _detail_suffix(evt))
    if typ == "step_entered":
        return "%s  → %s" % (clock, _step_label(step, detail))
    if typ == "step_completed":
        return "%s  ✓ %s" % (clock, _step_label(step, detail))
    if typ == "gate":
        gate = detail or ((evt.get("payload") or {}).get("gate") if isinstance(evt.get("payload"), dict) else None)
        if gate == "passed":
            return "%s  ✓ %s gate passed" % (clock, step or "gate")
        return "%s  → %s gate %s" % (clock, step or "gate", gate or "recorded")
    if typ == "ci_fix_attempt":
        return "%s  ↻ ci fix attempt%s" % (clock, _detail_suffix(evt))
    if typ == "parked":
        # #446: a park that folded a structured payload (assumption parks, doc-review parks) carries
        # its cause in payload.reason rather than a bare `detail` — surface it so the live readout
        # names why the run parked instead of a mute `‼ parked`.
        cause = _park_cause(evt)
        return "%s  ‼ parked%s" % (clock, (" · %s" % cause) if cause else "")
    if typ == "resumed":
        return "%s  ▶ resumed%s" % (clock, _detail_suffix(evt))
    if typ == "run_completed":
        return "%s  ✓ run completed%s" % (clock, _detail_suffix(evt))
    if typ == "manual_completion":
        # #450: a hand-finished-after-park receipt. Surface the PR (and any note) so the
        # timeline names WHERE the work landed instead of ending on a mute park.
        payload = evt.get("payload") if isinstance(evt.get("payload"), dict) else {}
        pr = payload.get("pr")
        note = payload.get("note")
        pr_txt = (" · PR %s" % pr) if pr not in (None, "") else ""
        note_txt = (" — %s" % note) if note else ""
        return "%s  ✓ manually completed%s%s" % (clock, pr_txt, note_txt)
    if typ == "phases_skipped":
        # #25: surface the quick route's skipped front-half phases in the live readout — never silent.
        payload = evt.get("payload") if isinstance(evt.get("payload"), dict) else {}
        route = payload.get("route") or "quick"
        skipped = payload.get("skipped")
        names = ", ".join(skipped) if isinstance(skipped, list) and skipped else "front-half phases"
        return "%s  ⏭ %s route — skipped %s" % (clock, route, names)
    if typ == "routed_forward":
        # #397 FR-4: a tasks-review non-blocking finding routed to the journal, never into build.
        payload = evt.get("payload") if isinstance(evt.get("payload"), dict) else {}
        doc = payload.get("doc") or "doc"
        return "%s  → %s %s" % (clock, doc, JOURNAL_EVENT_LABELS[typ])
    if typ == "review_convergence":
        # #397 FR-15: per-review convergence record at every doc-review terminal.
        payload = evt.get("payload") if isinstance(evt.get("payload"), dict) else {}
        doc = payload.get("doc") or "doc"
        outcome = payload.get("outcome") or "recorded"
        return "%s  · %s %s — %s" % (clock, doc, JOURNAL_EVENT_LABELS[typ], outcome)
    if typ == "handoff_provided":
        # #397 FR-3: tasks phase receipt that the plan hand-off was provided (or unreadable).
        payload = evt.get("payload") if isinstance(evt.get("payload"), dict) else {}
        doc = payload.get("doc") or "plan"
        return "%s  · %s hand-off %s" % (clock, doc, JOURNAL_EVENT_LABELS[typ])
    if typ in ("lease_acquired", "lease_reclaimed"):
        return "%s  · %s%s" % (clock, typ.replace("_", " "), _detail_suffix(evt))
    label = JOURNAL_EVENT_LABELS.get(typ)
    if label:
        return "%s  · %s%s" % (clock, label, _detail_suffix(evt))
    return "%s  · %s%s" % (clock, typ.replace("_", " "), _detail_suffix(evt))


def _poll_lines(prev, curr, seen):
    """Pure tail step: given the previous and current snapshots and the highest event seq
    already shown, return (lines, new_seen) — the journal-cadence lines for events past
    `seen` followed by the snapshot-diff content lines, plus the advanced cursor. Each
    event is emitted at most once; a poll with nothing new returns no lines."""
    lines = []
    new_events = [e for e in curr.get("events") or []
                  if isinstance(e, dict) and _safe_int(e.get("seq")) > seen]
    for event in sorted(new_events, key=lambda e: _safe_int(e.get("seq"))):
        lines.append(format_journal_event(event))
        seen = max(seen, _safe_int(event.get("seq")))
    lines.extend(diff(prev, curr))
    return lines, seen


def _dq(value):
    value = os.path.abspath(value)
    if any(ch in value for ch in "$`!\\"):
        return shlex.quote(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


_SAFE_ARG = re.compile(r"\A[A-Za-z0-9._/-]+\Z")


def _arg(value):
    # Quote anything that isn't an unambiguously safe token, so the printed command stays
    # paste-safe even if a work-item ever carries a shell metacharacter (; & | * ( ) < > …).
    text = str(value)
    if text and _SAFE_ARG.match(text):
        return text
    return shlex.quote(text)


def watch_command(lib_dir, root, work_item):
    script = os.path.join(os.path.abspath(lib_dir), "run_watch.py")
    return 'python3 %s --work-item %s --root %s --follow' % (
        _dq(script),
        _arg(work_item),
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

    seen = max([_safe_int(e.get("seq")) for e in prev.get("events") or []
                if isinstance(e, dict)] or [0])
    try:
        while True:
            time.sleep(max(0.1, args.interval))
            curr = gather(args.root, args.work_item)
            lines, seen = _poll_lines(prev, curr, seen)
            for line in lines:
                _print(line)
            prev = curr
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
