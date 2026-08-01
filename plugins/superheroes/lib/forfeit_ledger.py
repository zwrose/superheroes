#!/usr/bin/env python3
"""Durable forfeit ledger and attribution decider (#747).

Every terminal dispatched run leaves a structured row outside the session that
produced it — telemetry, evidence pointers, and an attribution. A forfeit is
presumed self-inflicted until attributed. Unknown is a queue, not a bucket —
unattributed forfeit is pending work.

The ledger is a record, never a control input: nothing here decides what a
dispatch does.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import file_lock  # noqa: E402
import launch_ledger as ll  # noqa: E402
from dispatch_outcome import (  # noqa: E402
    ATTRIBUTION_CALLER_ERROR,
    ATTRIBUTION_ENGINE_SIDE,
    ATTRIBUTION_ENVIRONMENT,
    ATTRIBUTION_TRANSPORT,
    ATTRIBUTION_UNKNOWN,
    ATTRIBUTIONS,
    FORFEIT_REASONS,
    REASON_UNRUNNABLE,
    is_forfeit,
)

LEDGER_ROOT_ENV = "SUPERHEROES_FORFEIT_LEDGER_ROOT"
FORFEIT_LEDGER_ROOT_DIR = "superheroes-forfeit-ledger"
FORFEIT_LEDGER_FILE = "forfeit-ledger.jsonl"
SCHEMA = 1
ACTIVE_SILENCE_SECONDS = 60

_LOCK_SUFFIX = ".lock"
_DEFAULT_LOCK_TIMEOUT = 30.0
_COMPLETENESS_LEDGER_ONLY = "ledger-only"
_COMPLETENESS_CAVEAT = (
    "ledger-only: a run whose append failed is invisible to this summary"
)


def run_id_from_run_dir(run_dir):
    """Stable digest of a run directory's real path; never raises."""
    if not run_dir or not isinstance(run_dir, str):
        return None
    try:
        real = os.path.realpath(run_dir)
    except OSError:
        return None
    return hashlib.sha256(real.encode("utf-8")).hexdigest()


def _validate_resolved_root(repo_root, root, env):
    if not ll._has_git_entry(repo_root):
        return False
    if ll.repo_identity(repo_root) is None:
        return False
    return ll.validate_candidate_root(repo_root, root, env=env)


def _resolve_root(repo_root, env=None):
    """Resolve ledger root outside the repo; refuse in-repo paths. Never raises."""
    if env is None:
        env = os.environ
    if ll.repo_identity(repo_root) is None:
        return {"ok": False, "root": None, "reason": "ledger-repo-identity-unavailable"}

    override = env.get(LEDGER_ROOT_ENV)
    root = override if override else os.path.join(tempfile.gettempdir(), FORFEIT_LEDGER_ROOT_DIR)
    try:
        root = os.path.realpath(os.path.abspath(root))
    except OSError:
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    if not _validate_resolved_root(repo_root, root, env):
        return {"ok": False, "root": None, "reason": "ledger-root-unusable"}

    return {"ok": True, "root": root, "reason": None}


def ledger_path(repo_root, env=None):
    """Absolute path to this repo's ledger file, or None on failure. Never raises."""
    resolved = _resolve_root(repo_root, env=env)
    if not resolved["ok"]:
        return None
    repo_id = ll.repo_identity(repo_root)
    if repo_id is None:
        return None
    return os.path.join(resolved["root"], repo_id, FORFEIT_LEDGER_FILE)


def _lock_path(ledger_file):
    return ledger_file + _LOCK_SUFFIX


def _acquire_lock(lock_path, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            file_lock.acquire(lock_path)
            return True
        except file_lock.LockHeld:
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)
        except OSError:
            return False


def _release_lock(lock_path):
    try:
        file_lock.release(lock_path)
    except Exception:
        pass


def _parse_ledger_bytes(raw):
    """Parse ledger bytes; skip torn trailing write; flag interior corruption.

    axis: classification of damage — torn trailing skipped, interior corruption flagged.
    """
    records = []
    interior_corrupt = False
    if not raw:
        return records, interior_corrupt
    torn = raw[-1:] != b"\n"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return records, True
    lines = text.split("\n")
    if torn:
        lines.pop()
    for line in lines:
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except (ValueError, TypeError):
            interior_corrupt = True
            continue
        if not isinstance(parsed, dict):
            interior_corrupt = True
            continue
        records.append(parsed)
    return records, interior_corrupt


def read(repo_root, env=None):
    """Return (rows, interior_corrupt). Never raises."""
    path = ledger_path(repo_root, env=env)
    if path is None:
        return [], False
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return [], False
    return _parse_ledger_bytes(raw)


def _append_raw(path, row):
    """Append one JSON line with flush+fsync. False on failure; never raises."""
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        line = json.dumps(row, separators=(",", ":")) + "\n"
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        return True
    except (OSError, TypeError, ValueError):
        return False


def append(repo_root, row, env=None, lock_timeout=_DEFAULT_LOCK_TIMEOUT):
    """Append one row under lock; idempotent per runId. Never raises.

    axis: failure containment — OSError returns written=False, never reaches callers.

    Returns {"written": bool, "deduped": bool, "path": str|None, "why": str|None}.
    """
    failure = {"written": False, "deduped": False, "path": None, "why": None}
    if not isinstance(row, dict):
        failure["why"] = "row-not-a-dict"
        return failure

    path = ledger_path(repo_root, env=env)
    if path is None:
        failure["why"] = "ledger-path-unavailable"
        return failure

    run_id = row.get("runId")
    if not run_id:
        run_dir = row.get("runDir")
        run_id = run_id_from_run_dir(run_dir) if run_dir else None
        if run_id:
            row = dict(row)
            row["runId"] = run_id
    if not run_id:
        failure["why"] = "run-id-unavailable"
        return failure

    lock_path = _lock_path(path)
    if not _acquire_lock(lock_path, lock_timeout):
        failure["why"] = "lock-unavailable"
        return failure

    try:
        existing, _ = read(repo_root, env=env)
        for prior in existing:
            if prior.get("runId") == run_id:
                return {
                    "written": True,
                    "deduped": True,
                    "path": path,
                    "why": None,
                }

        # axis: refusal to double-count a continuation — skip when runId already present.
        if not _append_raw(path, row):
            failure["why"] = "ledger-append-failed"
            failure["path"] = path
            return failure
        return {"written": True, "deduped": False, "path": path, "why": None}
    finally:
        _release_lock(lock_path)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def classify_attempt(attempt, row):
    """Return attribution for one attempt. Pure; never raises."""
    if not isinstance(attempt, dict):
        return {
            "class": ATTRIBUTION_UNKNOWN,
            "why": "attempt record missing or not a dict",
        }

    signal_source = attempt.get("signalSource")
    if signal_source == "engine":
        sig = attempt.get("signal")
        return {
            "class": ATTRIBUTION_ENGINE_SIDE,
            "why": "engine delivered signal %s (signalSource engine)" % sig,
        }

    exit_code = attempt.get("exit")
    timed_out = attempt.get("timedOut")
    if exit_code is not None and exit_code != 0:
        if not timed_out and signal_source != "runner-timeout":
            return {
                "class": ATTRIBUTION_ENGINE_SIDE,
                "why": "exit %s without runner timeout attribution" % exit_code,
            }

    silence = attempt.get("silenceSeconds")
    if timed_out and _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
        cap = attempt.get("capSeconds")
        return {
            "class": ATTRIBUTION_ENVIRONMENT,
            "why": "timed out with silenceSeconds=%s under capSeconds=%s" % (silence, cap),
        }

    stages = row.get("stages") if isinstance(row.get("stages"), dict) else {}
    stdout_bytes = attempt.get("stdoutBytes")
    if (
        not timed_out
        and exit_code == 0
        and _is_number(stdout_bytes)
        and stdout_bytes > 0
        and stages.get("delivered") is False
    ):
        return {
            "class": ATTRIBUTION_TRANSPORT,
            "why": "exit 0 with stdout but stages.delivered is False",
        }

    parts = []
    if timed_out:
        parts.append("timedOut=True")
    if silence is not None:
        parts.append("silenceSeconds=%s" % silence)
    if exit_code is not None:
        parts.append("exit=%s" % exit_code)
    if not parts:
        parts.append("insufficient attempt telemetry")
    return {
        "class": ATTRIBUTION_UNKNOWN,
        "why": "would need timeout silence, engine signal, or transport shape; saw %s"
        % ", ".join(parts),
    }


def _matches_caller_error(row):
    return (
        row.get("reason") == REASON_UNRUNNABLE
        and row.get("attemptCount") == 0
    )


def _matches_engine_side(row):
    for attempt in row.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        if attempt.get("signalSource") == "engine":
            return True
        exit_code = attempt.get("exit")
        if exit_code is not None and exit_code != 0:
            if not attempt.get("timedOut") and attempt.get("signalSource") != "runner-timeout":
                return True
    return False


def _matches_environment(row):
    for attempt in row.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        if attempt.get("timedOut"):
            silence = attempt.get("silenceSeconds")
            if _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
                return True
    return False


def _matches_transport(row):
    attempts = row.get("attempts") or []
    if not attempts:
        return False
    stages = row.get("stages") if isinstance(row.get("stages"), dict) else {}
    if stages.get("delivered") is not False:
        return False
    for attempt in attempts:
        if not isinstance(attempt, dict):
            return False
        if attempt.get("timedOut"):
            return False
        if attempt.get("exit") != 0:
            return False
    return any(
        _is_number(att.get("stdoutBytes")) and att.get("stdoutBytes") > 0
        for att in attempts
        if isinstance(att, dict)
    )


def _run_level_attribution(row):
    """Derive run-level class by stated precedence. Pure."""
    if _matches_caller_error(row):
        detail = row.get("detail") or "unrunnable before spawn"
        return {
            "class": ATTRIBUTION_CALLER_ERROR,
            "why": "unrunnable before any engine spawned: %s" % detail,
        }
    if _matches_engine_side(row):
        return {
            "class": ATTRIBUTION_ENGINE_SIDE,
            "why": "engine-side signal or exit on at least one attempt",
        }
    if _matches_environment(row):
        for attempt in row.get("attempts") or []:
            if not isinstance(attempt, dict):
                continue
            if attempt.get("timedOut"):
                silence = attempt.get("silenceSeconds")
                if _is_number(silence) and silence <= ACTIVE_SILENCE_SECONDS:
                    cap = attempt.get("capSeconds")
                    return {
                        "class": ATTRIBUTION_ENVIRONMENT,
                        "why": "timed out with silenceSeconds=%s under capSeconds=%s"
                        % (silence, cap),
                    }
        return {
            "class": ATTRIBUTION_ENVIRONMENT,
            "why": "runner cap fired while output was still moving",
        }
    if _matches_transport(row):
        return {
            "class": ATTRIBUTION_TRANSPORT,
            "why": "every attempt exit 0 with stdout but stages.delivered is False",
        }
    return {
        "class": ATTRIBUTION_UNKNOWN,
        "why": "no precedence rule matched; need more telemetry",
    }


def classify(row):
    """Classify each attempt, then the run. Mutates attempts with attribution. Pure.

    axis: which cause wins when attempts disagree — precedence order sets mixed when they differ.
    """
    if not isinstance(row, dict):
        return {
            "class": ATTRIBUTION_UNKNOWN,
            "why": "row missing or not a dict",
        }

    attempts = row.get("attempts")
    if attempts is None:
        attempts = []
    attempt_classes = []
    for attempt in attempts:
        if isinstance(attempt, dict):
            att = classify_attempt(attempt, row)
            attempt["attribution"] = att
            attempt_classes.append(att["class"])

    run_attr = _run_level_attribution(row)
    unique_classes = set(attempt_classes)
    if len(unique_classes) > 1:
        causes = []
        for attempt in attempts:
            if isinstance(attempt, dict) and "attribution" in attempt:
                att = attempt["attribution"]
                causes.append("%s (%s)" % (att["class"], att["why"]))
        run_attr = dict(run_attr)
        run_attr["mixed"] = True
        run_attr["why"] = (
            "mixed causes: %s; run-level precedence chose %s"
            % ("; ".join(causes), run_attr["class"])
        )
    return run_attr


def build_row(
    *,
    at=None,
    run_dir=None,
    order_id=None,
    engine=None,
    engine_model=None,
    run_kind=None,
    reason=None,
    detail=None,
    attempt_count=None,
    attempts=None,
    stages=None,
    engagement=None,
    evidence=None,
    ok=None,
):
    """Assemble one ledger row from runner inputs. Pure; no I/O."""
    if at is None:
        at = time.time()
    if attempts is None:
        attempts = []
    if stages is None:
        stages = {"engaged": None, "delivered": None}
    if evidence is None:
        evidence = {
            "stdoutPaths": [],
            "stderrPaths": [],
            "journalPath": None,
            "promptPath": None,
        }

    row = {
        "at": at,
        "schema": SCHEMA,
        "runDir": run_dir,
        "runId": run_id_from_run_dir(run_dir) if run_dir else None,
        "orderId": order_id,
        "engine": engine,
        "engineModel": engine_model,
        "runKind": run_kind,
        "reason": reason,
        "detail": detail,
        "attemptCount": attempt_count,
        "attempts": [dict(a) for a in attempts if isinstance(a, dict)],
        "stages": dict(stages) if isinstance(stages, dict) else stages,
        "engagement": engagement,
        "evidence": dict(evidence) if isinstance(evidence, dict) else evidence,
        "salvage": None,
        "ok": ok if ok is not None else (reason is None),
    }
    row["attribution"] = classify(row)
    return row


def summarize(rows, *, window_seconds=None, now=None):
    """Standing accounting over ledger rows. Pure.

    axis: the denominator includes successes — rates use every terminal row in the window.
    """
    if now is None:
        now = time.time()
    if window_seconds is None:
        window = {"seconds": None, "from": None, "to": now}
        filtered = list(rows)
    else:
        cutoff = now - window_seconds
        window = {"seconds": window_seconds, "from": cutoff, "to": now}
        filtered = [
            r for r in rows
            if isinstance(r, dict) and _is_number(r.get("at")) and r["at"] >= cutoff
        ]

    total = len(filtered)
    by_reason = {}
    by_attribution = {key: 0 for key in sorted(ATTRIBUTIONS)}
    by_engine = {}
    salvage_count = 0
    forfeit_count = 0

    for row in filtered:
        if not isinstance(row, dict):
            continue
        reason = row.get("reason")
        by_reason[reason] = by_reason.get(reason, 0) + 1
        if is_forfeit(reason):
            forfeit_count += 1
        attr = row.get("attribution")
        if isinstance(attr, dict):
            cls = attr.get("class")
            if cls in by_attribution:
                by_attribution[cls] += 1
        engine = row.get("engine")
        if engine is not None:
            by_engine[engine] = by_engine.get(engine, 0) + 1
        salvage = row.get("salvage")
        if isinstance(salvage, dict) and salvage.get("detected"):
            salvage_count += 1

    salvage_rate = salvage_count / total if total > 0 else None
    forfeit_rate = forfeit_count / total if total > 0 else None

    return {
        "window": window,
        "total": total,
        "byReason": by_reason,
        "byAttribution": by_attribution,
        "byEngine": by_engine,
        "forfeit": {"count": forfeit_count, "rate": forfeit_rate},
        "salvage": {"count": salvage_count, "rate": salvage_rate},
        "unattributed": by_attribution.get(ATTRIBUTION_UNKNOWN, 0),
        "completeness": _COMPLETENESS_LEDGER_ONLY,
        "completenessCaveat": _COMPLETENESS_CAVEAT,
    }


def _format_human_summary(summary):
    window = summary["window"]
    if window["seconds"] is None:
        window_line = "window: all rows (to %s)" % window["to"]
    else:
        window_line = "window: %ss from %s to %s" % (
            window["seconds"], window["from"], window["to"],
        )
    lines = [window_line, "total: %d" % summary["total"]]
    for cls in sorted(ATTRIBUTIONS):
        lines.append("%s: %d" % (cls, summary["byAttribution"][cls]))
    forfeit = summary.get("forfeit", {})
    lines.append(
        "forfeit: count=%d rate=%s" % (
            forfeit.get("count", 0),
            forfeit.get("rate"),
        )
    )
    salvage = summary["salvage"]
    lines.append(
        "salvage: count=%d rate=%s" % (salvage["count"], salvage["rate"])
    )
    lines.append("unattributed: %d" % summary["unattributed"])
    lines.append("completeness: %s" % summary["completeness"])
    return "\n".join(lines)


def _cmd_report(args):
    rows, interior_corrupt = read(args.repo_root)
    if interior_corrupt and not rows:
        print("ledger unreadable: interior corruption", file=sys.stderr)
        return 1
    summary = summarize(rows, window_seconds=args.window_seconds)
    if args.json:
        print(json.dumps(summary, separators=(",", ":"), sort_keys=True))
    else:
        print(_format_human_summary(summary))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Forfeit ledger report")
    sub = parser.add_subparsers(dest="command")
    report = sub.add_parser("report")
    report.add_argument("--repo-root", required=True)
    report.add_argument("--window-seconds", type=float, default=None)
    report.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "report":
        return _cmd_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
