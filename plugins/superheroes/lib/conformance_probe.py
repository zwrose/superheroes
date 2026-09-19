#!/usr/bin/env python3
"""Per-engine conformance probe (#1270 C11 layer 3): one real review dispatch per dispatchable
engine, grading result production, completion detection, and progress telemetry separately."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
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

SCHEMA = "conformance-probe/1"
PREFLIGHT_ENTRY_SCHEMA = "conformance-preflight-entry/1"
PROBE_ROLE = "reviewer-deep"
SLICE_MAX_WAIT = 300
BOUND_PAD_SECONDS = 60
DEFAULT_MAX_AGE_SECONDS = 3600

DISPATCHABLE_ENGINES = tuple(
    e for e in engine_adapter.BUILD_ARGV_VENDORS
    if e in engine_result_channel._CHANNEL_BY_ENGINE
)

_LEG_NAMES = ("resultProduction", "completionDetection", "progressTelemetry")


def _utc_now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_completed_at(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _scrub_text(text):
    if not isinstance(text, str) or not text:
        return text
    scrubbed, _ok = readout.scrub(text)
    return scrubbed


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


def _engine_not_dispatchable_detail(engine):
    accepted = ", ".join(DISPATCHABLE_ENGINES)
    base = "accepted engines: %s" % accepted
    if engine == "claude":
        return "%s; the CLI-Claude engine child owns that adapter branch" % base
    return base


def _resolve_repo_root(repo_root):
    if repo_root is None:
        try:
            proc = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None, "repo-root-unresolvable"
        if proc.returncode != 0:
            return None, "repo-root-unresolvable"
        repo_root = proc.stdout.strip()
    try:
        return os.path.realpath(repo_root), None
    except OSError:
        return None, "repo-root-unresolvable"


def _probe_prompt_text(target_file):
    return (
        "Verify exactly one claim and respond with exactly one JSON object.\n\n"
        "Claim: `%s` defines `channel_for` and it raises `UnknownEngineError` "
        "for an unregistered engine name.\n\n"
        "You must open the named file (use a tool call to read it).\n\n"
        "Respond with a single JSON object of the form "
        '`{"result": {"resultKind": "verdicts", "verdicts": [...]}}` '
        'containing exactly one verdict with id `"conformance-probe-1"`.\n'
        % target_file
    )


def _write_probe_prompt(prompt_path, repo_root):
    target = os.path.join(
        repo_root, "plugins", "superheroes", "lib", "engine_result_channel.py")
    text = _probe_prompt_text(target)
    with open(prompt_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return prompt_path


def _seat_for_engine(engine):
    cell = seat_map.matrix_config(PROBE_ROLE, engine)
    if cell is None:
        return None, "probe-cell-unresolvable"
    model, effort = cell
    if model is None:
        return None, "probe-cell-unresolvable"
    seat = {
        "vendor": engine,
        "model": model,
        "effort": effort,
        "role": PROBE_ROLE,
    }
    return seat, None


def _dependent_from_calibration(rows, engine):
    if not rows:
        return None, "no calibrated role routes to %s" % engine
    if len(rows) == 1 and rows[0].get("role") == "*":
        read_error = rows[0].get("readError")
        if read_error:
            return None, "unknown — calibration unreadable: %s" % _scrub_text(read_error)
    roles = [
        row["role"] for row in rows
        if isinstance(row, dict) and row.get("engine") == engine and row.get("role") != "*"
    ]
    if not roles:
        return [], "no calibrated role routes to %s" % engine
    role_text = ", ".join(roles)
    return roles, "every full lane in the wave dispatches %s on %s" % (role_text, engine)


def _stderr_failure_line(engine, legs, dependent_lanes):
    parts = []
    for name in _LEG_NAMES:
        leg = legs.get(name) or {}
        if not leg.get("ok"):
            detail = leg.get("detail") or "failed"
            parts.append("%s:%s" % (name, detail))
    failed = ",".join(parts)
    return (
        "CONFORMANCE PROBE FAILED engine=%s failed=%s dependent lanes: %s"
        % (engine, failed, dependent_lanes)
    )


def _preflight_check_entry(engine, channel, seat, wall_seconds, legs, run_dir, all_ok):
    cell = [seat["vendor"], seat["model"], seat.get("effort")]
    leg_summary = ",".join(
        "%s=%s" % (n, "ok" if legs[n]["ok"] else legs[n].get("detail") or "fail")
        for n in _LEG_NAMES
    )
    evidence = "%s channel=%s cell=%s wall=%.1fs legs=%s runDir=%s" % (
        engine, channel, "/".join(str(c) for c in cell if c is not None),
        wall_seconds, leg_summary, run_dir,
    )
    if all_ok:
        return {
            "state": "pass",
            "reason": "%s conformance probe passed" % engine,
            "evidence": _scrub_text(evidence),
        }
    failed = _failed_leg_names(legs)
    return {
        "state": "fail",
        "reason": "%s conformance probe failed: %s" % (engine, ",".join(failed)),
        "evidence": _scrub_text(evidence),
    }


def _read_stderr_tail(run_dir_real, attempt):
    path = os.path.join(run_dir_real, "attempt-%d.stderr" % attempt)
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        tail = data[-400:] if len(data) > 400 else data
        text = tail.decode("utf-8", errors="replace")
        return _scrub_text(text)
    except OSError:
        return ""


def _effective_last_activity(ended, engagement):
    last_at = ended.get("lastActivityAt")
    if last_at is not None:
        return last_at
    if ended.get("activitySource") == "injected-seam":
        if engagement.get("telemetry") == "tool-calls":
            return ended.get("at")
    return None


def _grade_result_production(terminal):
    if not terminal.get("terminal"):
        return _leg(False, "result-did-not-validate", {"terminal": False})
    if terminal.get("attempts") == 0:
        detail = terminal.get("detail") or terminal.get("reason") or "auth-or-config-refusal"
        return _leg(
            False, "auth-or-config-refusal",
            {"reason": terminal.get("reason"), "detail": _scrub_text(str(detail))},
        )
    if not terminal.get("ok"):
        detail = terminal.get("detail") or "result-did-not-validate"
        return _leg(False, detail, {"reason": terminal.get("reason")})
    kind = terminal.get("resultKind")
    if kind not in engine_adapter.REVIEW_RESULT_KINDS:
        return _leg(False, "result-did-not-validate", {"resultKind": kind})
    payload = terminal.get(kind)
    if not isinstance(payload, list) or not payload:
        return _leg(False, "result-did-not-validate", {"resultKind": kind})
    return _leg(True, None, {"resultKind": kind, "count": len(payload)})


def _grade_completion(terminal, ended, bound_exceeded):
    if terminal.get("attempts") == 0:
        detail = terminal.get("detail") or terminal.get("reason")
        return _leg(
            False, "auth-or-config-refusal",
            {"reason": terminal.get("reason"), "detail": _scrub_text(str(detail or ""))},
        )
    if bound_exceeded:
        return _leg(False, "no-response-within-wait", {"boundExceeded": True})
    if not ended:
        return _leg(False, "attempt-ended-missing", {})
    if ended.get("timedOut"):
        return _leg(False, "no-response-within-wait", {"timedOut": True})
    if not terminal.get("terminal"):
        return _leg(False, "no-response-within-wait", {"terminal": False})
    refusal = ended.get("refusal")
    exit_code = ended.get("exit")
    if refusal is not None or (exit_code not in (0, None)):
        attempt = ended.get("attempt", 1)
        run_dir_real = terminal.get("runDir") or ""
        evidence = {
            "refusal": _scrub_text(str(refusal)) if refusal is not None else None,
            "exit": exit_code,
            "stderrTail": _read_stderr_tail(run_dir_real, attempt),
        }
        return _leg(False, "auth-or-config-refusal", evidence)
    return _leg(True, None, {"exit": exit_code})


def _grade_telemetry(terminal, ended, engagement):
    if terminal.get("attempts") == 0:
        detail = terminal.get("detail") or terminal.get("reason")
        return _leg(
            False, "auth-or-config-refusal",
            {"reason": terminal.get("reason"), "detail": _scrub_text(str(detail or ""))},
        )
    source = (engagement or {}).get("source")
    telemetry = (engagement or {}).get("telemetry")
    tool_calls = (engagement or {}).get("toolCalls")
    last_at = _effective_last_activity(ended or {}, engagement or {})
    if telemetry == "tool-calls" and source not in (None, "none") and last_at is not None:
        return _leg(True, None, {
            "source": source, "telemetry": telemetry,
            "toolCalls": tool_calls, "lastActivityAt": last_at,
        })
    return _leg(False, "telemetry-absent", {
        "source": source, "telemetry": telemetry,
        "toolCalls": tool_calls, "lastActivityAt": last_at,
    })


def _grade_legs(terminal, state, bound_exceeded):
    attempts = state.get("attempts") or {}
    highest = max(attempts.keys()) if attempts else None
    ended = None
    if highest is not None:
        ended = (attempts[highest] or {}).get("ended")
    engagement = terminal.get("engagement") if isinstance(terminal, dict) else {}
    return {
        "resultProduction": _grade_result_production(terminal),
        "completionDetection": _grade_completion(terminal, ended, bound_exceeded),
        "progressTelemetry": _grade_telemetry(terminal, ended, engagement),
    }


def _refusal_payload(engine, detail, repo_root=None, seat=None, channel=None):
    seat = seat or {"vendor": engine, "model": None, "effort": None, "role": PROBE_ROLE}
    channel = channel or (engine_result_channel.channel_for(engine) if engine in DISPATCHABLE_ENGINES else None)
    legs = _all_legs_failed(detail)
    dependent_roles, dependent_lanes = _dependent_from_calibration(
        preflight_probe.dispatch_calibration(cwd=repo_root or os.getcwd()),
        engine,
    )
    now = _utc_now_iso()
    payload = {
        "schema": SCHEMA,
        "ok": False,
        "engine": engine,
        "channel": channel,
        "seat": seat,
        "probedCell": [seat["vendor"], seat.get("model"), seat.get("effort")],
        "repoRoot": repo_root,
        "startedAt": now,
        "completedAt": now,
        "wallSeconds": 0.0,
        "runDir": "",
        "legs": legs,
        "failed": _failed_leg_names(legs),
        "dependentRoles": dependent_roles,
        "dependentLanes": dependent_lanes,
        "preflightCheck": _preflight_check_entry(
            engine, channel, seat, 0.0, legs, "", False),
    }
    return _scrub_obj(payload)


def probe(engine, repo_root=None, run_dir=None, timeout=None, run_engine=None, build_view=None):
    """Run the conformance probe for `engine`. Returns (payload dict, exit code). Never raises."""
    started_at = _utc_now_iso()
    t0 = time.monotonic()
    timeout = timeout if timeout is not None else engine_dispatch.RETRY_MIN_TIMEOUT

    if engine not in DISPATCHABLE_ENGINES:
        detail = "engine-not-dispatchable"
        payload = _refusal_payload(engine, detail)
        payload["repoRoot"] = None
        _, dep_lanes = _dependent_from_calibration(
            preflight_probe.dispatch_calibration(), engine)
        return payload, 1, _stderr_failure_line(engine, payload["legs"], dep_lanes)

    repo_real, repo_err = _resolve_repo_root(repo_root)
    if repo_err:
        payload = _refusal_payload(engine, repo_err, repo_root=None)
        _, dep_lanes = _dependent_from_calibration(
            preflight_probe.dispatch_calibration(cwd=repo_real or os.getcwd()), engine)
        return payload, 1, _stderr_failure_line(engine, payload["legs"], dep_lanes)

    seat, cell_err = _seat_for_engine(engine)
    if cell_err:
        payload = _refusal_payload(engine, cell_err, repo_root=repo_real, seat=seat)
        _, dep_lanes = _dependent_from_calibration(
            preflight_probe.dispatch_calibration(cwd=repo_real), engine)
        return payload, 1, _stderr_failure_line(engine, payload["legs"], dep_lanes)

    if run_dir is None:
        run_dir = tempfile.mkdtemp(prefix="conformance-probe-")
    run_dir_real = os.path.realpath(run_dir)
    parent = os.path.dirname(run_dir_real)
    prompt_path = os.path.join(parent, "probe-prompt.md")
    try:
        _write_probe_prompt(prompt_path, repo_real)
    except OSError as exc:
        payload = _refusal_payload(engine, "repo-root-unresolvable", repo_root=repo_real, seat=seat)
        return payload, 1, _stderr_failure_line(engine, payload["legs"], "")

    channel = engine_result_channel.channel_for(engine)
    bound = timeout + BOUND_PAD_SECONDS
    deadline = time.monotonic() + bound
    terminal = {"ok": False, "terminal": False, "attempts": 0}
    bound_exceeded = False

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        slice_wait = min(SLICE_MAX_WAIT, int(remaining))
        try:
            dispatch_kw = {
                "seat": seat,
                "prompt_path": prompt_path,
                "repo_root": repo_real,
                "run_dir": run_dir,
                "max_wait": slice_wait,
                "order_id": "conformance-probe:%s" % engine,
                "expected_result_kind": "verdicts",
                "timeout": timeout,
                "run_engine": run_engine,
            }
            if build_view is not None:
                dispatch_kw["build_view"] = build_view
            terminal = engine_dispatch.dispatch_review(**dispatch_kw)
        except Exception as exc:
            terminal = {
                "ok": False, "terminal": True, "reason": dispatch_outcome.REASON_UNRUNNABLE,
                "detail": "internal-%s" % type(exc).__name__,
                "attempts": 0, "forfeited": False, "runDir": run_dir_real,
            }
            break
        if terminal.get("terminal"):
            break

    if not terminal.get("terminal"):
        bound_exceeded = True
        try:
            engine_dispatch.dispatch_abandon(run_dir)
        except Exception:
            pass
        terminal = dict(terminal)
        terminal["terminal"] = True
        terminal["ok"] = False

    records, _ = engine_dispatch._journal_read(run_dir_real)
    state = engine_dispatch._journal_state(records)
    legs = _grade_legs(terminal, state, bound_exceeded)
    all_ok = all(legs[n]["ok"] for n in _LEG_NAMES)
    wall = time.monotonic() - t0
    completed_at = _utc_now_iso()

    cal_rows = preflight_probe.dispatch_calibration(cwd=repo_real)
    dependent_roles, dependent_lanes = _dependent_from_calibration(cal_rows, engine)

    payload = {
        "schema": SCHEMA,
        "ok": all_ok,
        "engine": engine,
        "channel": channel,
        "seat": seat,
        "probedCell": [seat["vendor"], seat["model"], seat.get("effort")],
        "repoRoot": repo_real,
        "startedAt": started_at,
        "completedAt": completed_at,
        "wallSeconds": round(wall, 1),
        "runDir": run_dir_real,
        "legs": legs,
        "failed": _failed_leg_names(legs),
        "dependentRoles": dependent_roles,
        "dependentLanes": dependent_lanes,
        "preflightCheck": _preflight_check_entry(
            engine, channel, seat, wall, legs, run_dir_real, all_ok),
    }
    payload = _scrub_obj(payload)
    stderr_line = None
    if not all_ok:
        stderr_line = _stderr_failure_line(engine, legs, dependent_lanes)
    return payload, (0 if all_ok else 1), stderr_line


def _required_probe_engines(repo_root, calibration_rows=None):
    rows = calibration_rows
    if rows is None:
        rows = preflight_probe.dispatch_calibration(cwd=repo_root)
    if len(rows) == 1 and rows[0].get("role") == "*" and rows[0].get("readError"):
        return None, "calibration-unreadable"
    engines = {
        row["engine"] for row in rows
        if isinstance(row, dict) and row.get("engine") in DISPATCHABLE_ENGINES
    }
    return sorted(engines), None


def _author_family_from_calibration(rows):
    impl = next((r for r in rows if r.get("role") == "implementer"), None)
    if not impl:
        return None, "author-family-unresolved"
    vendor = impl.get("engine")
    model = impl.get("model")
    if not vendor or not model:
        return None, "author-family-unresolved"
    resolved = model_registry.resolve_dispatch("implementer", vendor, model)
    if not resolved.get("ok"):
        return None, "author-family-unresolved"
    model_id = resolved.get("model_id")
    family = model_registry.model_family(vendor, model_id)
    if not family:
        return None, "author-family-unresolved"
    return family, None


def preflight_entry(
    repo_root,
    result_paths,
    launch_without=(),
    owner_words=(),
    max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
    calibration_rows=None,
):
    """Build the engine-auth preflight entry from probe results. Returns (payload, exit_code)."""
    try:
        repo_real = os.path.realpath(repo_root)
    except OSError:
        return {"ok": False, "reason": "repo-root-unresolvable"}, 1

    launch_pairs = list(launch_without or [])
    words = list(owner_words or [])
    if len(launch_pairs) != len(words):
        if len(launch_pairs) > len(words):
            return {"ok": False, "reason": "owner-word-missing"}, 1

    results_by_engine = {}
    extra_engines = []
    for path in result_paths:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {"ok": False, "reason": "probe-result-malformed:%s" % path}, 1
        if raw.get("schema") != SCHEMA:
            return {"ok": False, "reason": "probe-result-malformed:%s" % path}, 1
        eng = raw.get("engine")
        if eng in results_by_engine:
            return {"ok": False, "reason": "probe-duplicate:%s" % eng}, 1
        results_by_engine[eng] = (path, raw)

    cal_rows = calibration_rows
    if cal_rows is None:
        cal_rows = preflight_probe.dispatch_calibration(cwd=repo_real)
    required, cal_err = _required_probe_engines(repo_real, cal_rows)
    if cal_err:
        return {"ok": False, "reason": cal_err}, 1

    for eng in required:
        if eng not in results_by_engine:
            return {"ok": False, "reason": "probe-missing:%s" % eng}, 1

    for eng in results_by_engine:
        if eng not in required:
            extra_engines.append(eng)

    now = datetime.now(timezone.utc)
    failed = []
    passing = []
    for eng in required:
        _path, res = results_by_engine[eng]
        if os.path.realpath(res.get("repoRoot") or "") != repo_real:
            return {"ok": False, "reason": "probe-foreign-repo:%s" % eng}, 1
        completed = _parse_completed_at(res.get("completedAt"))
        if completed is None:
            return {"ok": False, "reason": "probe-stale:%s" % eng}, 1
        age = (now - completed).total_seconds()
        if age > max_age_seconds:
            return {"ok": False, "reason": "probe-stale:%s" % eng}, 1
        if res.get("ok"):
            passing.append(eng)
        else:
            failed.append(eng)

    owner_map = {}
    for eng, word in zip(launch_pairs, words):
        if not isinstance(word, str) or not word.strip():
            return {"ok": False, "reason": "owner-word-blank"}, 1
        if eng not in failed:
            return {"ok": False, "reason": "launch-without-not-failed:%s" % eng}, 1
        owner_map[eng] = word.strip()

    uncovered_failed = [e for e in failed if e not in owner_map]

    if not failed:
        evidence = "; ".join(
            "%s: %s" % (e, results_by_engine[e][1].get("preflightCheck", {}).get("evidence", ""))
            for e in required
        )
        entry = {
            "state": "pass",
            "reason": "conformance probes passed: %s" % ",".join(required),
            "evidence": _scrub_text(evidence),
        }
        return {
            "schema": PREFLIGHT_ENTRY_SCHEMA,
            "ok": True,
            "reason": None,
            "engine-auth": entry,
            "required": required,
            "failed": [],
            "seatMap": None,
        }, 0

    if uncovered_failed:
        legs = []
        for eng in uncovered_failed:
            res = results_by_engine[eng][1]
            legs.append("%s (%s)" % (eng, ",".join(res.get("failed") or [])))
        evidence = "; ".join(
            results_by_engine[e][1].get("preflightCheck", {}).get("evidence", "")
            for e in required
        )
        entry = {
            "state": "fail",
            "reason": (
                "conformance probe failed: %s — hold; nothing launches without the owner's word"
                % "; ".join(legs)
            ),
            "evidence": _scrub_text(evidence),
        }
        return {
            "schema": PREFLIGHT_ENTRY_SCHEMA,
            "ok": True,
            "reason": None,
            "engine-auth": entry,
            "required": required,
            "failed": failed,
            "seatMap": None,
        }, 0

    author_family, fam_err = _author_family_from_calibration(cal_rows)
    if fam_err:
        return {"ok": False, "reason": fam_err}, 1

    live_cells = []
    for eng in passing:
        res = results_by_engine[eng][1]
        cell = res.get("probedCell")
        if isinstance(cell, list) and len(cell) >= 2:
            live_cells.append(tuple(cell[:3]) if len(cell) >= 3 else (cell[0], cell[1], None))

    live_vendors = sorted(set(passing) | {"claude"})
    try:
        sm = seat_map.build(
            None,
            live_vendors,
            author_family,
            None,
            0,
            live_cells=live_cells,
            live_cells_source="probed",
        )
    except Exception as exc:
        return {"ok": False, "reason": "seat-map-failed:%s" % type(exc).__name__}, 1

    same_family = [
        d for d in (sm.get("degradations") or [])
        if isinstance(d, dict) and d.get("constraint") == "same-family"
    ]
    impl_row = next((r for r in cal_rows if r.get("role") == "implementer"), {})
    impl_on = impl_row.get("engine")

    if same_family:
        seats = ", ".join(sorted({d.get("seat", "?") for d in same_family}))
        entry = {
            "state": "fail",
            "reason": (
                "conformance probe failed: %s; launched without it on the owner's word — "
                "full lanes PARK: %s would seat the maker family %s"
                % (",".join(failed), seats, author_family)
            ),
            "evidence": _scrub_text("; ".join(
                results_by_engine[e][1].get("preflightCheck", {}).get("evidence", "")
                for e in required
            )),
        }
        return {
            "schema": PREFLIGHT_ENTRY_SCHEMA,
            "ok": True,
            "reason": None,
            "engine-auth": entry,
            "required": required,
            "failed": failed,
            "seatMap": sm,
        }, 0

    words_text = "; ".join("%s: %s" % (e, owner_map[e]) for e in sorted(owner_map))
    other_deg = sorted({
        d.get("constraint") for d in (sm.get("degradations") or [])
        if isinstance(d, dict) and d.get("constraint") != "same-family"
    })
    sub_parts = []
    for seat_name, seat_val in sorted((sm.get("seats") or {}).items()):
        sub_parts.append(
            "%s: %s/%s/%s" % (
                seat_name, seat_val.get("family"), seat_val.get("vendor"), seat_val.get("model"),
            )
        )
    entry = {
        "state": "pass",
        "reason": (
            "conformance probe failed: %s; launching without it on the owner's word: %s"
            % (",".join(failed), words_text)
        ),
        "evidence": _scrub_text(
            "substitutes — %s; other degradations: %s; implementer calibrated on %s: %s"
            % ("; ".join(sub_parts), ",".join(other_deg) or "none", impl_on, "yes" if impl_on in passing else "no")
        ),
    }
    return {
        "schema": PREFLIGHT_ENTRY_SCHEMA,
        "ok": True,
        "reason": None,
        "engine-auth": entry,
        "required": required,
        "failed": failed,
        "seatMap": sm,
    }, 0


def main(argv):
    ap = argparse.ArgumentParser(prog="conformance_probe")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run one engine conformance probe")
    run_p.add_argument("--engine", required=True)
    run_p.add_argument("--repo-root", default=None)
    run_p.add_argument("--run-dir", default=None)
    run_p.add_argument("--timeout", type=int, default=None)

    pe = sub.add_parser("preflight-entry", help="aggregate probe results into engine-auth entry")
    pe.add_argument("--repo-root", required=True)
    pe.add_argument("--result", action="append", required=True, dest="results")
    pe.add_argument("--launch-without", action="append", default=[], dest="launch_without")
    pe.add_argument("--owner-word", action="append", default=[], dest="owner_words")
    pe.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)

    args = ap.parse_args(argv[1:])

    if args.cmd == "run":
        payload, code, stderr_line = probe(
            args.engine,
            repo_root=args.repo_root,
            run_dir=args.run_dir,
            timeout=args.timeout,
        )
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        if stderr_line:
            sys.stderr.write(stderr_line + "\n")
        return code

    if args.cmd == "preflight-entry":
        payload, code = preflight_entry(
            args.repo_root,
            args.results,
            launch_without=args.launch_without,
            owner_words=args.owner_words,
            max_age_seconds=args.max_age_seconds,
        )
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
