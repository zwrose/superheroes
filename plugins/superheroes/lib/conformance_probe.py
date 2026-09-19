#!/usr/bin/env python3
"""Per-engine conformance probe (#1270 C11 layer 3)."""
import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import dispatch_outcome  # noqa: E402
import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import engine_result_channel  # noqa: E402
import model_registry  # noqa: E402
import preflight_probe  # noqa: E402
import readout  # noqa: E402
import seat_map  # noqa: E402
import store_core  # noqa: E402

SCHEMA = "conformance-probe/1"
PREFLIGHT_ENTRY_SCHEMA = "conformance-preflight-entry/1"
PROBE_ROLE = "reviewer-deep"
SLICE_MAX_WAIT = 300
BOUND_PAD_SECONDS = 60
DEFAULT_MAX_AGE_SECONDS = 86400  # a probe result is good for a day (owner-ruled 2026-09-19; was one hour)
DISPATCHABLE_ENGINES = tuple(
    e for e in engine_adapter.BUILD_ARGV_VENDORS if e in engine_result_channel._CHANNEL_BY_ENGINE)
_LEG_NAMES = ("resultProduction", "completionDetection", "progressTelemetry")
_PROBE_PROMPT = (
    "Verify exactly one claim and respond with exactly one JSON object.\n\n"
    "Claim: The working directory you were given contains at least one regular "
    "file at its top level (list it to check).\n\n"
    "You must open the directory listing (use a tool call).\n\n"
    "Return exactly one JSON object of the form "
    '`{"verdicts": [{"id": "conformance-probe-1", "verdict": "CONFIRMED" | "REFUTED", '
    '"reason": "<one sentence>", "severity": null, "evidence": "<the file name, or why none>"}], '
    '"investigated": ["<the path you listed>"]}` '
    "on the runner's declared result channel (the contract appended at the end of this prompt "
    "says whether that is a result file or your final response); no code fence. "
    "The reason field is required and must be a non-empty sentence; "
    "investigated lists the directory you listed. "
    'Use verdict `"CONFIRMED"` with evidence naming one such file when true, '
    'or verdict `"REFUTED"` when the listing is empty.\n\n'
    "When a result schema was supplied to you, it governs the outer shape; "
    "the verdict fields above are the same.\n")


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _now_utc():
    return datetime.now(timezone.utc)

def _parse_completed_at(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed
def _scrub_text(text):
    if not isinstance(text, str) or not text:
        return text
    scrubbed, _ok = readout.scrub(text)
    return scrubbed
def _scrubbed(value):
    return _scrub_text(str(value or ""))
def _scrub_obj(value):
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, list):
        return [_scrub_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrub_obj(v) for k, v in value.items()}
    return value
def _leg(ok, detail=None, evidence=None):
    return {"ok": bool(ok), "detail": detail, "evidence": evidence or {}}
def _all_legs_failed(detail, evidence=None):
    ev = evidence or {}
    return {name: _leg(False, detail, ev) for name in _LEG_NAMES}
def _failed_leg_names(legs):
    return [name for name in _LEG_NAMES if not legs.get(name, {}).get("ok")]

def _resolve_repo_root(repo_root):
    if repo_root is None:
        try:
            return store_core.repo_root(os.getcwd()), None
        except store_core.RepoRootUnavailable:
            return None, "repo-root-unresolvable"
    try:
        return os.path.realpath(repo_root), None
    except OSError:
        return None, "repo-root-unresolvable"

def _write_probe_prompt(prompt_path, repo_root=None):
    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write(_PROBE_PROMPT)
    return prompt_path

def _seat_for_engine(engine):
    cell = model_registry.matrix_config(PROBE_ROLE, engine)
    if cell is None or cell[0] is None:
        return None, "probe-cell-unresolvable"
    return {"vendor": engine, "model": cell[0], "effort": cell[1], "role": PROBE_ROLE}, None

def _dependent_from_calibration(rows, engine):
    if not rows:
        return None, "no calibrated role routes to %s" % engine
    if len(rows) == 1 and rows[0].get("role") == "*":
        read_error = rows[0].get("readError")
        if read_error:
            return None, "unknown — calibration unreadable: %s" % _scrub_text(read_error)
    roles = [row["role"] for row in rows
             if isinstance(row, dict) and row.get("engine") == engine and row.get("role") != "*"]
    if not roles:
        return [], "no calibrated role routes to %s" % engine
    return roles, "every full lane in the wave dispatches %s on %s" % (", ".join(roles), engine)

def _stderr_failure_line(engine, legs, dependent_lanes):
    parts = ["%s:%s" % (n, (legs.get(n) or {}).get("detail") or "failed")
             for n in _LEG_NAMES if not (legs.get(n) or {}).get("ok")]
    return "CONFORMANCE PROBE FAILED engine=%s failed=%s dependent lanes: %s" % (
        engine, ",".join(parts), dependent_lanes)

def _preflight_check_entry(engine, channel, seat, wall_seconds, legs, run_dir, all_ok):
    cell = [seat["vendor"], seat["model"], seat.get("effort")]
    leg_summary = ",".join(
        "%s=%s" % (n, "ok" if legs[n]["ok"] else legs[n].get("detail") or "fail") for n in _LEG_NAMES)
    evidence = "%s channel=%s cell=%s wall=%.1fs legs=%s runDir=%s" % (
        engine, channel, "/".join(str(c) for c in cell if c is not None),
        wall_seconds, leg_summary, run_dir)
    if all_ok:
        return {"state": "pass", "reason": "%s conformance probe passed" % engine,
                "evidence": _scrub_text(evidence)}
    return {"state": "fail",
            "reason": "%s conformance probe failed: %s" % (engine, ",".join(_failed_leg_names(legs))),
            "evidence": _scrub_text(evidence)}

def _read_stderr_tail(run_dir_real, attempt):
    try:
        with open(os.path.join(run_dir_real, "attempt-%d.stderr" % attempt), "rb") as fh:
            data = fh.read()
        tail = data[-400:] if len(data) > 400 else data
        return _scrub_text(tail.decode("utf-8", errors="replace"))
    except OSError:
        return ""

def _effective_last_activity(ended, engagement):
    return ended.get("lastActivityAt")

def _grade_legs(terminal, state, bound_exceeded):
    attempts = state.get("attempts") or {}
    highest = max(attempts.keys()) if attempts else None
    ended = (attempts[highest] or {}).get("ended") if highest is not None else None
    engagement = terminal.get("engagement") if isinstance(terminal, dict) else {}
    if terminal.get("attempts") == 0:
        detail = terminal.get("detail") or terminal.get("reason") or "auth-or-config-refusal"
        auth = _leg(False, "auth-or-config-refusal",
                    {"reason": terminal.get("reason"), "detail": _scrubbed(detail)})
        return {name: auth for name in _LEG_NAMES}
    if not terminal.get("terminal"):
        rp = _leg(False, "result-did-not-validate", {"terminal": False})
    elif not terminal.get("ok"):
        rp = _leg(False, terminal.get("detail") or "result-did-not-validate",
                  {"reason": terminal.get("reason")})
    else:
        kind = terminal.get("resultKind")
        payload = terminal.get(kind)
        if kind not in engine_adapter.REVIEW_RESULT_KINDS or not isinstance(payload, list) or not payload:
            rp = _leg(False, "result-did-not-validate", {"resultKind": kind})
        else:
            rp = _leg(True, None, {"resultKind": kind, "count": len(payload)})
    if bound_exceeded:
        cd = _leg(False, "no-response-within-wait", {"boundExceeded": True})
    elif not ended:
        cd = _leg(False, "attempt-ended-missing", {})
    elif ended.get("timedOut"):
        cd = _leg(False, "no-response-within-wait", {"timedOut": True})
    elif not terminal.get("terminal"):
        cd = _leg(False, "no-response-within-wait", {"terminal": False})
    elif ended.get("refusal") is not None or ended.get("exit") not in (0, None):
        cd = _leg(False, "auth-or-config-refusal", {
            "refusal": _scrubbed(ended.get("refusal")) if ended.get("refusal") is not None else None,
            "exit": ended.get("exit"),
            "stderrTail": _read_stderr_tail(terminal.get("runDir") or "", ended.get("attempt", 1)),
        })
    else:
        cd = _leg(True, None, {"exit": ended.get("exit")})
    source = (engagement or {}).get("source")
    telemetry = (engagement or {}).get("telemetry")
    tool_calls = (engagement or {}).get("toolCalls")
    last_at = _effective_last_activity(ended or {}, engagement or {})
    tool_count_ok = isinstance(tool_calls, (int, float)) and not isinstance(tool_calls, bool) and tool_calls >= 1
    if (telemetry == "tool-calls" and source not in (None, "none") and last_at is not None
            and tool_count_ok):
        pt = _leg(True, None, {"source": source, "telemetry": telemetry,
                               "toolCalls": tool_calls, "lastActivityAt": last_at})
    else:
        pt = _leg(False, "telemetry-absent", {"source": source, "telemetry": telemetry,
                                              "toolCalls": tool_calls, "lastActivityAt": last_at})
    return {"resultProduction": rp, "completionDetection": cd, "progressTelemetry": pt}

def _payload(engine, channel, seat, repo_root, started_at, completed_at, wall, run_dir,
             legs, dependent_roles, dependent_lanes, wave=None):
    all_ok = all(legs[n]["ok"] for n in _LEG_NAMES)
    out = {
        "schema": SCHEMA, "ok": all_ok, "engine": engine, "channel": channel, "seat": seat,
        "probedCell": [seat["vendor"], seat["model"], seat.get("effort")],
        "repoRoot": repo_root, "startedAt": started_at, "completedAt": completed_at,
        "wallSeconds": wall, "runDir": run_dir, "legs": legs,
        "failed": _failed_leg_names(legs), "dependentRoles": dependent_roles,
        "dependentLanes": dependent_lanes,
        "preflightCheck": _preflight_check_entry(engine, channel, seat, wall, legs, run_dir, all_ok),
    }
    if wave:
        out["wave"] = wave
    return out

def _refuse(engine, detail, repo_root, seat=None, channel=None):
    seat = seat or {"vendor": engine, "model": None, "effort": None, "role": PROBE_ROLE}
    if channel is None and engine in DISPATCHABLE_ENGINES:
        channel = engine_result_channel.channel_for(engine)
    legs = _all_legs_failed(detail)
    dep_roles, dep_lanes = _dependent_from_calibration(
        preflight_probe.dispatch_calibration(cwd=repo_root or os.getcwd()), engine)
    now = _utc_now_iso()
    payload = _scrub_obj(_payload(engine, channel, seat, repo_root, now, now, 0.0, "", legs, dep_roles, dep_lanes))
    return payload, 1, _stderr_failure_line(engine, legs, dep_lanes)

def probe(engine, repo_root=None, run_dir=None, timeout=None, run_engine=None, build_view=None,
          wave=None):
    """Run the conformance probe for `engine`. Returns (payload, exit code, stderr line). Never raises."""
    started_at, t0 = _utc_now_iso(), time.monotonic()
    timeout = timeout if timeout is not None else engine_dispatch.RETRY_MIN_TIMEOUT
    if engine not in DISPATCHABLE_ENGINES:
        payload, code, stderr_line = _refuse(engine, "engine-not-dispatchable", None)
        payload["repoRoot"] = None
        return payload, code, stderr_line
    repo_real, repo_err = _resolve_repo_root(repo_root)
    if repo_err:
        return _refuse(engine, repo_err, None)
    seat, cell_err = _seat_for_engine(engine)
    if cell_err:
        return _refuse(engine, cell_err, repo_real, seat=seat)
    run_dir_given = run_dir is not None
    if run_dir is None:
        try:
            parent = tempfile.mkdtemp(prefix="conformance-probe-")
            run_dir = os.path.join(parent, "run")
        except OSError as exc:
            return _refuse(engine, "run-dir-setup-failed:%s" % type(exc).__name__, repo_real, seat=seat)
    run_dir_real = os.path.realpath(run_dir)
    try:
        records, _ = engine_dispatch._journal_read(run_dir_real)
        if engine_dispatch._journal_state(records).get("folded") is not None:
            return _refuse(engine, "run-dir-reused", repo_real, seat=seat)
    except OSError:
        pass
    if run_dir_given:
        prompt_path = os.path.join(
            os.path.dirname(run_dir_real),
            os.path.basename(run_dir_real) + ".probe-prompt.md",
        )
    else:
        prompt_path = os.path.join(os.path.dirname(run_dir_real), "probe-prompt.md")
    try:
        _write_probe_prompt(prompt_path, repo_real)
    except OSError:
        return _refuse(engine, "prompt-write-failed", repo_real, seat=seat)
    channel = engine_result_channel.channel_for(engine)
    order_id = "conformance-probe:%s:%s" % (engine, uuid.uuid4().hex)
    deadline = time.monotonic() + timeout + BOUND_PAD_SECONDS
    terminal, bound_exceeded = {"ok": False, "terminal": False, "attempts": 0}, False
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            dispatch_kw = {
                "seat": seat, "prompt_path": prompt_path, "repo_root": repo_real,
                "run_dir": run_dir, "max_wait": min(SLICE_MAX_WAIT, int(remaining)),
                "order_id": order_id,
                "expected_result_kind": "verdicts", "timeout": timeout, "run_engine": run_engine,
            }
            if build_view is not None:
                dispatch_kw["build_view"] = build_view
            terminal = engine_dispatch.dispatch_review(**dispatch_kw)
        except Exception as exc:
            terminal = {"ok": False, "terminal": True, "reason": dispatch_outcome.REASON_UNRUNNABLE,
                        "detail": "internal-%s" % type(exc).__name__,
                        "attempts": 0, "forfeited": False, "runDir": run_dir_real}
            break
        if terminal.get("terminal"):
            break
    if not terminal.get("terminal"):
        bound_exceeded = True
        try:
            engine_dispatch.dispatch_abandon(run_dir)
        except Exception:
            pass
        terminal = dict(terminal, terminal=True, ok=False)
    records, _ = engine_dispatch._journal_read(run_dir_real)
    legs = _grade_legs(terminal, engine_dispatch._journal_state(records), bound_exceeded)
    wall = time.monotonic() - t0
    dep_roles, dep_lanes = _dependent_from_calibration(
        preflight_probe.dispatch_calibration(cwd=repo_real), engine)
    payload = _scrub_obj(_payload(
        engine, channel, seat, repo_real, started_at, _utc_now_iso(), round(wall, 1),
        run_dir_real, legs, dep_roles, dep_lanes, wave=wave))
    all_ok = payload["ok"]
    return payload, (0 if all_ok else 1), (_stderr_failure_line(engine, legs, dep_lanes) if not all_ok else None)

def _expected_probe_cell(engine):
    cell = model_registry.matrix_config(PROBE_ROLE, engine)
    if cell is None or cell[0] is None:
        return None
    return [engine, cell[0], cell[1]]

def _validate_probe_record(raw, path_hint=""):
    if not isinstance(raw, dict):
        return "probe-result-malformed:%s" % path_hint
    if raw.get("schema") != SCHEMA:
        return "probe-result-malformed:%s" % path_hint
    if not isinstance(raw.get("ok"), bool):
        return "probe-result-malformed:%s" % path_hint
    eng = raw.get("engine")
    if eng not in DISPATCHABLE_ENGINES:
        return "probe-result-malformed:%s" % path_hint
    if not isinstance(raw.get("channel"), str):
        return "probe-result-malformed:%s" % path_hint
    if raw.get("channel") != engine_result_channel.channel_for(eng):
        # A record taken on a channel the engine no longer dispatches on proves nothing about the
        # channel it does dispatch on (a pre-3c cursor record on the marker channel, inside the
        # day-long window, would otherwise pass the preflight for the typed-file channel).
        return "probe-channel-mismatch:%s" % eng
    seat = raw.get("seat")
    if not isinstance(seat, dict) or seat.get("vendor") != eng:
        return "probe-result-malformed:%s" % path_hint
    probed = raw.get("probedCell")
    if not isinstance(probed, list) or len(probed) < 2:
        return "probe-result-malformed:%s" % path_hint
    if not isinstance(raw.get("repoRoot"), str):
        return "probe-result-malformed:%s" % path_hint
    for fld in ("startedAt", "completedAt"):
        if not isinstance(raw.get(fld), str):
            return "probe-result-malformed:%s" % path_hint
    completed_parsed = _parse_completed_at(raw.get("completedAt"))
    if completed_parsed is None and isinstance(raw.get("completedAt"), str) and raw.get("completedAt").strip():
        text = raw.get("completedAt").strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            naive_check = datetime.fromisoformat(text)
            if naive_check.tzinfo is None:
                return "probe-result-malformed:%s" % path_hint
        except ValueError:
            pass
    if not isinstance(raw.get("wallSeconds"), (int, float)):
        return "probe-result-malformed:%s" % path_hint
    if not isinstance(raw.get("runDir"), str):
        return "probe-result-malformed:%s" % path_hint
    legs = raw.get("legs")
    if not isinstance(legs, dict):
        return "probe-result-malformed:%s" % path_hint
    for name in _LEG_NAMES:
        leg = legs.get(name)
        if not isinstance(leg, dict) or not isinstance(leg.get("ok"), bool):
            return "probe-result-malformed:%s" % path_hint
    computed_ok = all(legs[n]["ok"] for n in _LEG_NAMES)
    computed_failed = _failed_leg_names(legs)
    if raw.get("ok") != computed_ok:
        return "probe-result-malformed:%s" % path_hint
    failed = raw.get("failed")
    if not isinstance(failed, list) or sorted(failed) != sorted(computed_failed):
        return "probe-result-malformed:%s" % path_hint
    if not isinstance(raw.get("preflightCheck"), dict):
        return "probe-result-malformed:%s" % path_hint
    return None

def _required_probe_engines(repo_root, calibration_rows=None):
    rows = calibration_rows if calibration_rows is not None else preflight_probe.dispatch_calibration(cwd=repo_root)
    if len(rows) == 1 and rows[0].get("role") == "*" and rows[0].get("readError"):
        return None, "calibration-unreadable"
    return sorted(DISPATCHABLE_ENGINES), None

def _author_family_from_calibration(rows):
    impl = next((r for r in rows if r.get("role") == "implementer"), None)
    if not impl or not impl.get("engine") or not impl.get("model"):
        return None, "author-family-unresolved"
    resolved = model_registry.resolve_dispatch("implementer", impl["engine"], impl["model"])
    if not resolved.get("ok"):
        return None, "author-family-unresolved"
    family = model_registry.model_family(impl["engine"], resolved.get("model_id"))
    return (family, None) if family else (None, "author-family-unresolved")

def _evidence_join(required, results_by_engine):
    return "; ".join(results_by_engine[e][1].get("preflightCheck", {}).get("evidence", "") for e in required)

def _entry_result(entry, required, failed, sm, wave=None):
    out = {"schema": PREFLIGHT_ENTRY_SCHEMA, "ok": True, "reason": None,
           "engine-auth": entry, "required": required, "failed": failed, "seatMap": sm,
           "waveBinding": wave if wave else "none"}
    return out, 0

def preflight_entry(repo_root, result_paths, launch_without=(), owner_words=(),
                    max_age_seconds=DEFAULT_MAX_AGE_SECONDS, calibration_rows=None, wave=None):
    """Build the engine-auth preflight entry from probe results. Returns (payload, exit_code)."""
    try:
        repo_real = os.path.realpath(repo_root)
    except OSError:
        return {"ok": False, "reason": "repo-root-unresolvable"}, 1
    launch_pairs, words = list(launch_without or []), list(owner_words or [])
    if len(launch_pairs) != len(words) and len(launch_pairs) > len(words):
        return {"ok": False, "reason": "owner-word-missing"}, 1
    results_by_engine = {}
    for path in result_paths:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {"ok": False, "reason": "probe-result-malformed:%s" % path}, 1
        malformed = _validate_probe_record(raw, path)
        if malformed:
            return {"ok": False, "reason": malformed}, 1
        eng = raw.get("engine")
        if eng in results_by_engine:
            return {"ok": False, "reason": "probe-duplicate:%s" % eng}, 1
        results_by_engine[eng] = (path, raw)
    cal_rows = calibration_rows if calibration_rows is not None else preflight_probe.dispatch_calibration(cwd=repo_real)
    required, cal_err = _required_probe_engines(repo_real, cal_rows)
    if cal_err:
        return {"ok": False, "reason": cal_err}, 1
    for eng in required:
        if eng not in results_by_engine:
            return {"ok": False, "reason": "probe-missing:%s" % eng}, 1
    now = _now_utc()
    failed, passing = [], []
    for eng in required:
        _path, res = results_by_engine[eng]
        if os.path.realpath(res.get("repoRoot") or "") != repo_real:
            return {"ok": False, "reason": "probe-foreign-repo:%s" % eng}, 1
        completed = _parse_completed_at(res.get("completedAt"))
        age = (now - completed).total_seconds() if completed is not None else None
        if completed is None or age < 0 or age > max_age_seconds:
            return {"ok": False, "reason": "probe-stale:%s" % eng}, 1
        if wave is not None:
            result_wave = res.get("wave")
            if not result_wave or result_wave != wave:
                return {"ok": False, "reason": "probe-wave-mismatch:%s" % eng}, 1
        expected_cell = _expected_probe_cell(eng)
        probed_cell = res.get("probedCell")
        if expected_cell is None or list(probed_cell[:len(expected_cell)]) != expected_cell:
            return {"ok": False, "reason": "probe-cell-mismatch:%s" % eng}, 1
        (passing if res.get("ok") else failed).append(eng)
    owner_map = {}
    for eng, word in zip(launch_pairs, words):
        if not isinstance(word, str) or not word.strip():
            return {"ok": False, "reason": "owner-word-blank"}, 1
        if eng not in failed:
            return {"ok": False, "reason": "launch-without-not-failed:%s" % eng}, 1
        owner_map[eng] = word.strip()
    ev_join = _scrub_text(_evidence_join(required, results_by_engine))
    if not failed:
        return _entry_result({"state": "pass", "reason": "conformance probes passed: %s" % ",".join(required),
                              "evidence": ev_join}, required, [], None, wave=wave)
    uncovered = [e for e in failed if e not in owner_map]
    if uncovered:
        legs = ["%s (%s)" % (e, ",".join(results_by_engine[e][1].get("failed") or [])) for e in uncovered]
        return _entry_result({
            "state": "fail",
            "reason": "conformance probe failed: %s — hold; nothing launches without the owner's word" % "; ".join(legs),
            "evidence": ev_join,
        }, required, failed, None, wave=wave)
    author_family, fam_err = _author_family_from_calibration(cal_rows)
    if fam_err:
        return {"ok": False, "reason": fam_err}, 1
    live_cells = []
    for eng in passing:
        cell = results_by_engine[eng][1].get("probedCell")
        if isinstance(cell, list) and len(cell) >= 2:
            live_cells.append(tuple(cell[:3]) if len(cell) >= 3 else (cell[0], cell[1], None))
    try:
        sm = seat_map.build(None, sorted(set(passing) | {"claude"}), author_family, None, 0,
                            live_cells=live_cells, live_cells_source="probed")
    except Exception as exc:
        return {"ok": False, "reason": "seat-map-failed:%s" % type(exc).__name__}, 1
    same_family = [d for d in (sm.get("degradations") or [])
                   if isinstance(d, dict) and d.get("constraint") == "same-family"]
    impl_on = next((r.get("engine") for r in cal_rows if r.get("role") == "implementer"), None)
    if same_family:
        seats = ", ".join(sorted({d.get("seat", "?") for d in same_family}))
        return _entry_result({
            "state": "fail",
            "reason": "conformance probe failed: %s; launched without it on the owner's word — "
                      "full lanes PARK: %s would seat the maker family %s"
                      % (",".join(failed), seats, author_family),
            "evidence": ev_join,
        }, required, failed, sm, wave=wave)
    other_deg = sorted({d.get("constraint") for d in (sm.get("degradations") or [])
                        if isinstance(d, dict) and d.get("constraint") != "same-family"})
    sub_parts = ["%s: %s/%s/%s" % (n, v.get("family"), v.get("vendor"), v.get("model"))
                 for n, v in sorted((sm.get("seats") or {}).items())]
    words_text = "; ".join("%s: %s" % (e, owner_map[e]) for e in sorted(owner_map))
    return _entry_result({
        "state": "pass",
        "reason": "conformance probe failed: %s; launching without it on the owner's word: %s"
                  % (",".join(failed), words_text),
        "evidence": _scrub_text("substitutes — %s; other degradations: %s; implementer calibrated on %s: %s"
                                % ("; ".join(sub_parts), ",".join(other_deg) or "none", impl_on,
                                   "yes" if impl_on in passing else "no")),
    }, required, failed, sm, wave=wave)

def main(argv):
    ap = argparse.ArgumentParser(prog="conformance_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run_p = sub.add_parser("run", help="run one engine conformance probe")
    run_p.add_argument("--engine", required=True)
    run_p.add_argument("--repo-root", default=None)
    run_p.add_argument("--run-dir", default=None)
    run_p.add_argument("--timeout", type=int, default=None)
    run_p.add_argument("--wave", default=None)
    pe = sub.add_parser("preflight-entry", help="aggregate probe results into engine-auth entry")
    pe.add_argument("--repo-root", required=True)
    pe.add_argument("--result", action="append", required=True, dest="results")
    pe.add_argument("--launch-without", action="append", default=[], dest="launch_without")
    pe.add_argument("--owner-word", action="append", default=[], dest="owner_words")
    pe.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    pe.add_argument("--wave", default=None)
    args = ap.parse_args(argv[1:])
    if args.cmd == "run":
        payload, code, stderr_line = probe(args.engine, repo_root=args.repo_root,
                                           run_dir=args.run_dir, timeout=args.timeout,
                                           wave=args.wave)
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        if stderr_line:
            sys.stderr.write(stderr_line + "\n")
        return code
    if args.cmd == "preflight-entry":
        payload, code = preflight_entry(args.repo_root, args.results,
                                        launch_without=args.launch_without,
                                        owner_words=args.owner_words,
                                        max_age_seconds=args.max_age_seconds,
                                        wave=args.wave)
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        return code
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
