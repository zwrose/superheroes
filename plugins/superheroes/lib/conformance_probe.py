#!/usr/bin/env python3
"""Per-engine conformance probe (#1270 C11 layer 3)."""
import argparse
import hashlib
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
import mode_registry  # noqa: E402
import model_registry  # noqa: E402
import preflight_probe  # noqa: E402
import readout  # noqa: E402
import seat_map  # noqa: E402
import store_core  # noqa: E402

SCHEMA = "conformance-probe/2"
PREFLIGHT_ENTRY_SCHEMA = "conformance-preflight-entry/1"
PROBE_ROLE = "reviewer-deep"
SLICE_MAX_WAIT = 300
BOUND_PAD_SECONDS = 60
DEFAULT_MAX_AGE_SECONDS = 86400  # a probe result is good for a day (owner-ruled 2026-09-19; was one hour)
DISPATCHABLE_ENGINES = tuple(
    e for e in engine_adapter.BUILD_ARGV_VENDORS if e in engine_result_channel._CHANNEL_BY_ENGINE)
_LEG_NAMES = ("resultProduction", "completionDetection", "progressTelemetry")
ASTRA_PROBE_ROLE = "registration-probe"
ASTRA_CLAIM_ABANDON_SECONDS = 86400
ASTRA_CLAIM_UNRECORDED_MODEL = "unrecorded"
_RUBRIC_PATH = os.path.join(os.path.dirname(_LIB_DIR), "rubric", "review-base.md")
PLANT_FILE = "app/session_guard.py"
PLANT_LINES = (24, 25)
PLANT_SEVERITY = "Critical"
ASTRA_PROBE_DIFF = (
    "--- a/app/session_guard.py\n"
    "+++ b/app/session_guard.py\n"
    "@@ -1,4 +1,4 @@\n"
    '-"""Request guards."""\n'
    '+"""Request guards for the admin console."""\n'
    " import logging\n"
    " \n"
    " log = logging.getLogger(__name__)\n"
    "@@ -20,8 +20,9 @@ def require_admin(request):\n"
    '     token = request.headers.get("Authorization", "")\n'
    "     try:\n"
    "         claims = decode_token(token)\n"
    "     except TokenError:\n"
    '-        raise Forbidden("invalid token")\n'
    '+        log.warning("token decode failed; continuing")\n'
    '+        claims = {"role": "admin"}\n'
    '     if claims.get("role") != "admin":\n'
    '         raise Forbidden("not an admin")\n'
    "     return claims\n"
)
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

def _iso_from_utc(dt):
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")

def _severity_scale():
    try:
        with open(_RUBRIC_PATH, encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return None, "astra-probe-scale-unreadable"
    lines_list = content.splitlines()
    heading_idx = None
    for i, line in enumerate(lines_list):
        if line.strip() == "## Severity tiers":
            heading_idx = i
            break
    if heading_idx is None:
        return None, "astra-probe-scale-unreadable"
    lines = []
    levels = []
    saw_table_row = False
    for row in lines_list[heading_idx + 1:]:
        if row.startswith("#"):
            break
        if "|" in row:
            saw_table_row = True
            cells = [c.strip() for c in row.split("|") if c.strip()]
            if not cells:
                continue
            first = cells[0]
            if first.startswith("**") and first.endswith("**"):
                level = first.strip("*").strip()
                if len(cells) < 2:
                    return None, "astra-probe-scale-unreadable"
                lines.append("- `%s` — %s" % (level, cells[1]))
                levels.append(level)
        elif saw_table_row and row.strip() and not row.startswith("#"):
            break
    if PLANT_SEVERITY not in levels:
        return None, "astra-probe-scale-unreadable"
    return lines, None

def _astra_probe_prompt():
    scale_lines, err = _severity_scale()
    if err:
        return None, err
    text = (
        "Perform a one-shot security review of the following unified diff for a production "
        "admin console.\n\n"
        "Report each finding with `file` (the path as shown in the diff), `line` (NEW-file line number), "
        "`severity`, `title`, and `body`.\n\n"
        "Severity scale:\n"
        + "\n".join(scale_lines) + "\n"
        "`severity` must be exactly one of those words.\n\n"
        "```diff\n"
        + ASTRA_PROBE_DIFF
        + "```\n"
    )
    return text, None

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

def _modes_for_engine(engine):
    if engine == "claude":
        return engine_adapter.CLAUDE_MODES
    return ("default",)

def _mode_run_dir(parent_run_dir, mode):
    if mode == "default":
        return parent_run_dir
    return os.path.join(parent_run_dir, mode)

def _derive_flat_legs(mode_legs):
    flat = {}
    for leg_name in _LEG_NAMES:
        failing = []
        for mode, legs in mode_legs.items():
            leg = legs.get(leg_name) or {}
            if not leg.get("ok"):
                failing.append((mode, leg))
        if not failing:
            flat[leg_name] = _leg(True, None, {})
            continue
        mode, leg = failing[0]
        detail = leg.get("detail")
        if len(failing) == 1:
            mode_detail = "%s: %s" % (mode, detail) if detail else mode
        else:
            mode_detail = "; ".join(
                "%s: %s" % (m, (lg.get("detail") or "failed")) for m, lg in failing)
        evidence = dict(leg.get("evidence") or {})
        evidence["failingModes"] = [m for m, _lg in failing]
        flat[leg_name] = _leg(False, mode_detail, evidence)
    return flat

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
             mode_legs, probed_modes, dependent_roles, dependent_lanes, wave=None):
    legs = _derive_flat_legs(mode_legs)
    all_ok = all(legs[n]["ok"] for n in _LEG_NAMES)
    out = {
        "schema": SCHEMA, "ok": all_ok, "engine": engine, "channel": channel, "seat": seat,
        "probedCell": [seat["vendor"], seat["model"], seat.get("effort")],
        "repoRoot": repo_root, "startedAt": started_at, "completedAt": completed_at,
        "wallSeconds": wall, "runDir": run_dir, "probedModes": list(probed_modes),
        "modeLegs": mode_legs, "legs": legs,
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
    modes = _modes_for_engine(engine if engine in DISPATCHABLE_ENGINES else "codex")
    failed_legs = _all_legs_failed(detail)
    mode_legs = {mode: dict(failed_legs) for mode in modes}
    legs = _derive_flat_legs(mode_legs)
    dep_roles, dep_lanes = _dependent_from_calibration(
        preflight_probe.dispatch_calibration(cwd=repo_root or os.getcwd()), engine)
    now = _utc_now_iso()
    payload = _scrub_obj(_payload(
        engine, channel, seat, repo_root, now, now, 0.0, "", mode_legs, modes, dep_roles, dep_lanes))
    return payload, 1, _stderr_failure_line(engine, legs, dep_lanes)

def _stamp_mode_run_dir(legs, mode_run_dir):
    stamped = {}
    for name in _LEG_NAMES:
        leg = dict(legs[name])
        evidence = dict(leg.get("evidence") or {})
        evidence["runDir"] = mode_run_dir
        leg["evidence"] = evidence
        stamped[name] = leg
    return stamped

def _ensure_mode_run_dir(mode_run_dir):
    """Create `mode_run_dir` and report whether it is already terminally incompatible
    with a fresh dispatch — reused (mirrors `dispatch_review`'s own refusal conditions).

    Returns (mode_run_dir_real, reused, setup_error). `setup_error` is a detail string
    when the directory itself could not be created; `reused` is only meaningful when
    `setup_error` is None. `reused` covers both an already-opened journal (folded or
    not — a fresh probe always mints a new order_id, so `dispatch_review` would refuse
    any opened journal as `run-dir-reused` regardless of fold state) and a nonempty
    directory with no journal at all (`dispatch_review`'s `run-dir-not-empty-unopened`),
    so the all-mode preflight can fail every mode before dispatching any of them.
    """
    ok, result = engine_dispatch._validate_run_dir(mode_run_dir, create=True)
    if not ok:
        return mode_run_dir, False, result
    mode_run_dir_real = result
    try:
        records, _ = engine_dispatch._journal_read(mode_run_dir_real)
        state = engine_dispatch._journal_state(records)
        if state.get("opened") is not None:
            return mode_run_dir_real, True, None
        if engine_dispatch._run_dir_nonempty(mode_run_dir_real):
            return mode_run_dir_real, True, None
    except OSError:
        pass
    return mode_run_dir_real, False, None

def _probe_one_mode(engine, mode, seat, repo_real, parent_run_dir, prompt_path, timeout,
                    run_engine, build_view, order_suffix):
    mode_run_dir = _mode_run_dir(parent_run_dir, mode)
    mode_run_dir_real, reused, setup_error = _ensure_mode_run_dir(mode_run_dir)
    if setup_error:
        return _stamp_mode_run_dir(_all_legs_failed(setup_error), mode_run_dir_real)
    if reused:
        return _stamp_mode_run_dir(
            _all_legs_failed(dispatch_outcome.DETAIL_RUN_DIR_REUSED), mode_run_dir_real)
    claude_mode = mode if engine == "claude" else None
    order_id = "conformance-probe:%s:%s:%s" % (engine, mode, order_suffix)
    deadline = time.monotonic() + timeout + BOUND_PAD_SECONDS
    terminal, bound_exceeded = {"ok": False, "terminal": False, "attempts": 0}, False
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            dispatch_kw = {
                "seat": seat, "prompt_path": prompt_path, "repo_root": repo_real,
                "run_dir": mode_run_dir, "max_wait": min(SLICE_MAX_WAIT, int(remaining)),
                "order_id": order_id,
                "expected_result_kind": "verdicts", "timeout": timeout, "run_engine": run_engine,
            }
            if claude_mode is not None:
                dispatch_kw["claude_mode"] = claude_mode
            if build_view is not None:
                dispatch_kw["build_view"] = build_view
            terminal = engine_dispatch.dispatch_review(**dispatch_kw)
        except Exception as exc:
            terminal = {"ok": False, "terminal": True, "reason": dispatch_outcome.REASON_UNRUNNABLE,
                        "detail": "internal-%s" % type(exc).__name__,
                        "attempts": 0, "forfeited": False, "runDir": mode_run_dir_real}
            break
        if terminal.get("terminal"):
            break
    if not terminal.get("terminal"):
        bound_exceeded = True
        try:
            engine_dispatch.dispatch_abandon(mode_run_dir)
        except Exception:
            pass
        terminal = dict(terminal, terminal=True, ok=False)
    records, _ = engine_dispatch._journal_read(mode_run_dir_real)
    legs = _grade_legs(terminal, engine_dispatch._journal_state(records), bound_exceeded)
    return _stamp_mode_run_dir(legs, mode_run_dir_real)

def probe(engine, repo_root=None, run_dir=None, timeout=None, run_engine=None, build_view=None,
          wave=None):
    """Run the conformance probe for `engine`. Returns (payload, exit code, stderr line). Never raises."""
    if repo_root is not None:
        try:
            repo_root = os.fsdecode(os.fspath(repo_root))
        except Exception:
            payload, code, stderr_line = _refuse(engine, "repo-root-invalid", None)
            payload["repoRoot"] = None
            return payload, code, stderr_line
        if not isinstance(repo_root, str) or not repo_root:
            payload, code, stderr_line = _refuse(engine, "repo-root-invalid", None)
            payload["repoRoot"] = None
            return payload, code, stderr_line
    if run_dir is not None:
        try:
            run_dir = os.fsdecode(os.fspath(run_dir))
        except Exception:
            return _refuse(engine, "run-dir-invalid", None)
        if not isinstance(run_dir, str) or not run_dir:
            return _refuse(engine, "run-dir-invalid", None)
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
    if run_dir_given:
        # Validate the caller-supplied parent BEFORE resolving/partitioning it: resolving
        # a leaf symlink via realpath first (as the old code did) silently swaps in the
        # symlink's target and bypasses this refusal entirely.
        stripped = run_dir
        while stripped.endswith(os.sep) and len(stripped) > 1:
            stripped = stripped[:-1]
        if os.path.islink(stripped):
            return _refuse(engine, dispatch_outcome.DETAIL_RUN_DIR_IS_SYMLINK, repo_real, seat=seat)
        expected_names = set(_modes_for_engine(engine))
        # Only engines with nested per-mode subdirectories (currently claude: print/,
        # background/) have a meaningful "recognized top-level entries" set — for a
        # "default"-mode engine the mode dir IS the parent, and its own reuse/nonempty
        # rules are enforced later, per-mode, by the shared dispatch helper.
        if expected_names != {"default"} and os.path.exists(stripped):
            try:
                entries = set(os.listdir(stripped))
            except OSError as exc:
                return _refuse(engine, "run-dir-setup-failed:%s" % type(exc).__name__, repo_real, seat=seat)
            if entries - expected_names:
                return _refuse(
                    engine, dispatch_outcome.DETAIL_RUN_DIR_NOT_EMPTY_UNOPENED, repo_real, seat=seat)
    parent_run_dir = os.path.realpath(run_dir)
    if run_dir_given:
        prompt_path = os.path.join(
            os.path.dirname(parent_run_dir),
            os.path.basename(parent_run_dir) + ".probe-prompt.md",
        )
    else:
        prompt_path = os.path.join(os.path.dirname(parent_run_dir), "probe-prompt.md")
    try:
        _write_probe_prompt(prompt_path, repo_real)
    except OSError:
        return _refuse(engine, "prompt-write-failed", repo_real, seat=seat)
    channel = engine_result_channel.channel_for(engine)
    order_suffix = uuid.uuid4().hex
    modes = _modes_for_engine(engine)
    # Preflight every mode's run directory before dispatching any of them: a folded
    # journal in one mode (e.g. an interrupted prior probe) must refuse the whole probe
    # with nothing launched, rather than let an independent later mode still dispatch
    # (and get charged) against a payload that is already guaranteed to fail overall.
    mode_dirs, setup_error, any_reused = {}, None, False
    for mode in modes:
        mode_run_dir_real, reused, err = _ensure_mode_run_dir(_mode_run_dir(parent_run_dir, mode))
        mode_dirs[mode] = mode_run_dir_real
        if err and setup_error is None:
            setup_error = err
        any_reused = any_reused or reused
    mode_legs = {}
    if setup_error:
        for mode in modes:
            mode_legs[mode] = _stamp_mode_run_dir(_all_legs_failed(setup_error), mode_dirs[mode])
    elif any_reused:
        for mode in modes:
            mode_legs[mode] = _stamp_mode_run_dir(
                _all_legs_failed(dispatch_outcome.DETAIL_RUN_DIR_REUSED), mode_dirs[mode])
    else:
        for mode in modes:
            mode_legs[mode] = _probe_one_mode(
                engine, mode, seat, repo_real, parent_run_dir, prompt_path, timeout,
                run_engine, build_view, order_suffix)
    wall = time.monotonic() - t0
    dep_roles, dep_lanes = _dependent_from_calibration(
        preflight_probe.dispatch_calibration(cwd=repo_real), engine)
    payload = _scrub_obj(_payload(
        engine, channel, seat, repo_real, started_at, _utc_now_iso(), round(wall, 1),
        parent_run_dir, mode_legs, modes, dep_roles, dep_lanes, wave=wave))
    legs = payload["legs"]
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
    mode_legs = raw.get("modeLegs")
    if not isinstance(mode_legs, dict) or not mode_legs:
        return "probe-result-malformed:%s" % path_hint
    probed_modes = raw.get("probedModes")
    if not isinstance(probed_modes, list) or not all(isinstance(m, str) for m in probed_modes):
        return "probe-result-malformed:%s" % path_hint
    if set(probed_modes) != set(mode_legs.keys()):
        return "probe-result-malformed:%s" % path_hint
    expected_modes = _modes_for_engine(eng)
    if tuple(probed_modes) != expected_modes:
        return "probe-result-malformed:%s" % path_hint
    for _mode, mode_entry in mode_legs.items():
        if not isinstance(mode_entry, dict):
            return "probe-result-malformed:%s" % path_hint
        if set(mode_entry.keys()) != set(_LEG_NAMES):
            return "probe-result-malformed:%s" % path_hint
        for name in _LEG_NAMES:
            leg = mode_entry.get(name)
            if not isinstance(leg, dict) or not isinstance(leg.get("ok"), bool):
                return "probe-result-malformed:%s" % path_hint
            evidence = leg.get("evidence")
            if evidence is not None and not isinstance(evidence, dict):
                return "probe-result-malformed:%s" % path_hint
    legs = raw.get("legs")
    if not isinstance(legs, dict):
        return "probe-result-malformed:%s" % path_hint
    derived_legs = _derive_flat_legs(mode_legs)
    for name in _LEG_NAMES:
        leg = legs.get(name)
        if not isinstance(leg, dict) or not isinstance(leg.get("ok"), bool):
            return "probe-result-malformed:%s" % path_hint
        if leg.get("ok") != derived_legs[name]["ok"]:
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
        try:
            malformed = _validate_probe_record(raw, path)
        except Exception:
            return {"ok": False, "reason": "probe-result-malformed:%s" % path}, 1
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
    live_vendors = set(passing)
    if "claude" not in owner_map:
        live_vendors.add("claude")
    try:
        sm = seat_map.build(None, sorted(live_vendors), author_family, None, 0,
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

def _conformance_record_dir(repo_root):
    """Project store conformance record directory (control-plane project store + conformance/)."""
    try:
        project_store = mode_registry.project_store_dir(repo_root)
    except Exception:
        return None, "conformance-record-dir-unresolved"
    if not os.path.isdir(project_store):
        return None, "conformance-record-dir-unresolved"
    record_dir = os.path.join(project_store, "conformance")
    try:
        os.makedirs(record_dir, mode=0o700, exist_ok=True)
    except OSError:
        return None, "conformance-record-dir-unusable"
    return record_dir, None

def _wave_hash(wave, length):
    return hashlib.sha256(wave.encode("utf-8")).hexdigest()[:length]

def _astra_claim_path(ledger_dir, wave):
    return os.path.join(ledger_dir, "astra-probe-claim-%s.json" % _wave_hash(wave, 16))

def _astra_attempts_path(ledger_dir):
    return os.path.join(ledger_dir, "astra-probe-attempts.json")

def _read_astra_attempts(ledger_dir):
    path = _astra_attempts_path(ledger_dir)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return [], None
    except (OSError, ValueError):
        return None, "astra-probe-ledger-unreadable"
    if not isinstance(data, list):
        return None, "astra-probe-ledger-unreadable"
    for item in data:
        if not isinstance(item, dict):
            return None, "astra-probe-ledger-unreadable"
    return data, None

def _append_astra_attempt(ledger_dir, record):
    attempts, err = _read_astra_attempts(ledger_dir)
    if err:
        return err
    attempts.append(record)
    try:
        store_core.atomic_write(
            _astra_attempts_path(ledger_dir),
            json.dumps(attempts, separators=(",", ":")) + "\n",
        )
    except OSError:
        return "astra-probe-record-write-failed"
    return None

def _ledger_attempt_record(output):
    rec = dict(output)
    returned = rec.get("returned")
    if isinstance(returned, list) and len(returned) > 10:
        rec["returned"] = returned[:10]
    return rec

def _count_astra_misses(attempts):
    return sum(1 for a in attempts if a.get("outcome") in ("miss", "incomplete"))

def _attempt_for_wave(attempts, wave):
    for item in attempts:
        if item.get("wave") == wave:
            return item
    return None

def _normalize_finding_file(path):
    if not isinstance(path, str):
        return ""
    text = path.strip()
    for prefix in ("a/", "b/", "./"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text

def _finding_summary(finding):
    return {
        "file": finding.get("file"),
        "line": finding.get("line"),
        "severity": finding.get("severity"),
        "title": finding.get("title"),
    }

def _returned_summaries(findings):
    out = []
    for finding in findings or []:
        if isinstance(finding, dict):
            out.append(_finding_summary(finding))
    return out

def _match_astra_finding(finding):
    if not isinstance(finding, dict):
        return None
    file_ok = _normalize_finding_file(finding.get("file")) == PLANT_FILE
    line = finding.get("line")
    line_ok = isinstance(line, int) and line in PLANT_LINES
    severity = finding.get("severity")
    sev_ok = isinstance(severity, str) and severity.lower() == PLANT_SEVERITY.lower()
    if file_ok and line_ok and sev_ok:
        return _finding_summary(finding)
    return None

def _grade_astra_findings(findings):
    for finding in findings or []:
        matched = _match_astra_finding(finding)
        if matched is not None:
            return True, matched
    return False, None

def _read_astra_claim(claim_path):
    try:
        with open(claim_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

def _write_astra_claim(ledger_dir, wave, run_dir_real, model=None, effort=None):
    claim = {
        "wave": wave,
        "runDir": run_dir_real,
        "claimedAt": _utc_now_iso(),
        "model": model,
        "effort": effort,
    }
    path = _astra_claim_path(ledger_dir, wave)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        fh = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise
    try:
        with fh:
            json.dump(claim, fh, separators=(",", ":"))
            fh.write("\n")
    except BaseException:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        raise
    return claim

def _claim_is_abandoned(claim, now):
    claimed_at = _parse_completed_at(claim.get("claimedAt"))
    last_seen_at = _parse_completed_at(claim.get("lastSeenAt"))
    if claimed_at is None and last_seen_at is None:
        return True
    if claimed_at is None:
        anchor = last_seen_at
    elif last_seen_at is None:
        anchor = claimed_at
    else:
        anchor = max(claimed_at, last_seen_at)
    if anchor is None:
        return True
    return (now - anchor).total_seconds() > ASTRA_CLAIM_ABANDON_SECONDS

def _settle_orphan_astra_claims(ledger_dir, current_wave, now=None):
    if now is None:
        now = _now_utc()
    attempts, err = _read_astra_attempts(ledger_dir)
    if err:
        return None, err
    recorded = {a.get("wave") for a in attempts}
    try:
        names = os.listdir(ledger_dir)
    except OSError:
        return attempts, None
    for name in names:
        if not name.startswith("astra-probe-claim-") or not name.endswith(".json"):
            continue
        claim = _read_astra_claim(os.path.join(ledger_dir, name))
        if not isinstance(claim, dict):
            continue
        wave = claim.get("wave")
        if not wave or wave == current_wave or wave in recorded:
            continue
        if not _claim_is_abandoned(claim, now):
            continue
        claim_model = claim.get("model")
        claim_effort = claim.get("effort")
        if claim_model is None:
            claim_model = ASTRA_CLAIM_UNRECORDED_MODEL
            claim_effort = None
        misses = _count_astra_misses(attempts) + 1
        orphan = {
            "ok": False,
            "outcome": "incomplete",
            "wave": wave,
            "model": claim_model,
            "effort": claim_effort,
            "runDir": claim.get("runDir"),
            "dispatchReason": "abandoned-claim",
            "matched": None,
            "returned": [],
            "attempt": 1,
            "misses": misses,
            "ownerProposal": misses >= 3,
        }
        append_err = _append_astra_attempt(ledger_dir, _ledger_attempt_record(orphan))
        if append_err:
            return None, append_err
        attempts, err = _read_astra_attempts(ledger_dir)
        if err:
            return None, err
        recorded.add(wave)
    return attempts, None

def _astra_probe_refusal(wave, claim):
    return {
        "ok": False,
        "reason": "astra-probe-wave-already-attempted",
        "wave": wave,
        "claimedRunDir": claim.get("runDir"),
        "claimedAt": claim.get("claimedAt"),
    }, 1

def _build_astra_output(wave, run_dir_real, terminal, findings, attempts_before, seat):
    dispatch_reason = None
    if isinstance(terminal, dict):
        dispatch_reason = terminal.get("reason") or terminal.get("detail")
    returned = _returned_summaries(findings)
    passed, matched = _grade_astra_findings(findings)
    attempt_no = sum(1 for a in attempts_before if a.get("wave") == wave) + 1
    misses = _count_astra_misses(attempts_before)
    if not passed:
        misses += 1
    out = {
        "ok": passed,
        "outcome": "pass" if passed else "miss",
        "wave": wave,
        "model": seat["model"],
        "effort": seat.get("effort"),
        "runDir": run_dir_real,
        "dispatchReason": dispatch_reason,
        "matched": matched,
        "returned": returned,
        "attempt": attempt_no,
        "misses": misses,
        "ownerProposal": (not passed and misses >= 3),
    }
    return out

def astra_probe(repo_root, wave, run_dir, max_wait=None, timeout=None, dispatch=None, now=None):
    """Run the registration security-lens probe for `wave` — dispatched to whatever model the
    registry's `registration-probe` codex cell currently names (recorded as `model` on every
    ledger attempt), NOT necessarily Astra: the command, its refusal tokens, and its ledger
    file name are reused machinery, kept stable even when the cell's model changes. Returns
    (payload, exit code). Never raises."""
    if dispatch is None:
        dispatch = engine_dispatch.dispatch_review
    if not isinstance(wave, str) or not wave.strip():
        return {"ok": False, "reason": "wave-required"}, 2
    wave = wave.strip()
    repo_real, repo_err = _resolve_repo_root(repo_root)
    if repo_err:
        return {"ok": False, "reason": repo_err}, 1
    try:
        run_dir_real = os.path.realpath(run_dir)
    except OSError:
        return {"ok": False, "reason": "run-dir-unresolvable"}, 1
    prompt_text, prompt_err = _astra_probe_prompt()
    if prompt_err:
        return {"ok": False, "reason": prompt_err}, 1
    prompt_sha256 = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    resolved = model_registry.resolve_dispatch(
        ASTRA_PROBE_ROLE, "codex", None, None)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "reason": "astra-probe-seat-unresolved",
            "detail": resolved.get("reason"),
        }, 1
    seat = {
        "vendor": "codex",
        "model": resolved["model_id"],
        "effort": resolved["effort"],
        "role": ASTRA_PROBE_ROLE,
    }
    if now is None:
        now = _now_utc()
    ledger_dir, ledger_err = _conformance_record_dir(repo_real)
    if ledger_err:
        return {"ok": False, "reason": ledger_err}, 1
    attempts, ledger_read_err = _read_astra_attempts(ledger_dir)
    if ledger_read_err:
        return {"ok": False, "reason": ledger_read_err}, 1
    attempts, settle_err = _settle_orphan_astra_claims(ledger_dir, wave, now=now)
    if settle_err:
        return {"ok": False, "reason": settle_err}, 1
    claim_path = _astra_claim_path(ledger_dir, wave)
    claim = _read_astra_claim(claim_path)
    if claim is None:
        try:
            _write_astra_claim(
                ledger_dir, wave, run_dir_real,
                model=seat.get("model"), effort=seat.get("effort"))
            claim = _read_astra_claim(claim_path)
        except FileExistsError:
            claim = _read_astra_claim(claim_path)
            if claim is None:
                return {"ok": False, "reason": "astra-probe-claim-unreadable"}, 1
        except OSError:
            return {"ok": False, "reason": "astra-probe-record-write-failed"}, 1
    if claim is not None:
        claimed_dir = claim.get("runDir")
        try:
            claimed_real = os.path.realpath(claimed_dir) if claimed_dir else None
        except OSError:
            claimed_real = claimed_dir
        if claimed_real != run_dir_real:
            return _astra_probe_refusal(wave, claim)
        claimed_model = claim.get("model")
        if claimed_model is not None:
            # Continuing a claim that snapshotted a seat: dispatch (and attribute
            # any recorded outcome) with THAT seat, not the freshly resolved one —
            # a mid-wave registry change must not orphan a pending claim's dispatch
            # or misattribute its outcome to a model it never ran on. A legacy
            # claim with no snapshot (claimed_model is None) falls through and
            # keeps today's behavior: the freshly resolved seat.
            seat = {
                "vendor": "codex",
                "model": claimed_model,
                "effort": claim.get("effort"),
                "role": ASTRA_PROBE_ROLE,
            }
    recorded = _attempt_for_wave(attempts, wave)
    if recorded is not None:
        return recorded, (0 if recorded.get("ok") else 1)
    prompt_path = os.path.join(
        os.path.dirname(run_dir_real),
        os.path.basename(run_dir_real) + ".astra-probe-prompt.md",
    )
    try:
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(prompt_text)
    except OSError:
        return {"ok": False, "reason": "prompt-write-failed"}, 1
    order_id = "astra-probe-%s" % _wave_hash(wave, 12)
    dispatch_kw = {
        "seat": dict(seat),
        "prompt_path": prompt_path,
        "repo_root": repo_real,
        "run_dir": run_dir,
        "order_id": order_id,
        "expected_result_kind": "findings",
    }
    if max_wait is not None:
        dispatch_kw["max_wait"] = max_wait
    if timeout is not None:
        dispatch_kw["timeout"] = timeout
    try:
        terminal = dispatch(**dispatch_kw)
    except Exception as exc:
        terminal = {
            "ok": False,
            "terminal": True,
            "reason": dispatch_outcome.REASON_UNRUNNABLE,
            "detail": "internal-%s" % type(exc).__name__,
        }
    if not terminal.get("terminal"):
        if claim is not None:
            refreshed = dict(claim)
            refreshed["lastSeenAt"] = _iso_from_utc(now)
            try:
                store_core.atomic_write(
                    claim_path,
                    json.dumps(refreshed, separators=(",", ":")) + "\n",
                )
            except OSError:
                return {"ok": False, "reason": "astra-probe-record-write-failed"}, 1
        misses = _count_astra_misses(attempts)
        return {
            "ok": False,
            "outcome": "pending",
            "continue": True,
            "wave": wave,
            "runDir": run_dir_real,
            "misses": misses,
            "ownerProposal": False,
            "promptSha256": prompt_sha256,
        }, 0
    findings = terminal.get("findings") if terminal.get("ok") else []
    if not isinstance(findings, list):
        findings = []
    out = _build_astra_output(wave, run_dir_real, terminal, findings, attempts, seat)
    out["promptSha256"] = prompt_sha256
    append_err = _append_astra_attempt(ledger_dir, _ledger_attempt_record(out))
    if append_err:
        refusal = {"ok": False, "reason": append_err, "unrecorded": out}
        return refusal, 1
    return out, (0 if out["ok"] else 1)

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
    ap_probe = sub.add_parser(
        "astra-probe",
        help=(
            "registration security-lens probe for whatever model the registry's "
            "registration-probe codex cell names (not Astra-only)"
        ),
    )
    ap_probe.add_argument("--repo-root", required=True)
    ap_probe.add_argument("--wave", required=True)
    ap_probe.add_argument("--run-dir", required=True)
    ap_probe.add_argument("--max-wait", type=int, default=None)
    ap_probe.add_argument("--timeout", type=int, default=None)
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
    if args.cmd == "astra-probe":
        payload, code = astra_probe(
            args.repo_root, args.wave, args.run_dir,
            max_wait=args.max_wait, timeout=args.timeout,
        )
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
        return code
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
