#!/usr/bin/env python3
"""Headless builder launcher — preflight walk, premise stamp, composition, detached spawn.

Five CLI verbs over one core. Inspection verbs (preflight, compose) never spawn or write the
ledger. ``launch`` walks the checklist, validates the premise, and composes in one process before
reserve and spawn. Never raises to callers."""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import engine_pref  # noqa: E402
import heartbeat as hb  # noqa: E402
import launch_doctrine  # noqa: E402
import launch_ledger as ll  # noqa: E402
import model_registry  # noqa: E402

STANDING_EXCLUSIONS = {"releasePRsExcluded": True, "forcePush": "never"}

_SETTLE_SECONDS = 20
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (5, 15, 45)
_TOTAL_DEADLINE_SECONDS = 300

_GIT_SCRUB_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
)

_VALID_STATES = frozenset({"pass", "fail", "na"})
_HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")

_WORKHORSE_CMD = "/superheroes:workhorse"


def _scrub_env(env=None):
    base = dict(env if env is not None else os.environ)
    for key in _GIT_SCRUB_VARS:
        base.pop(key, None)
    base.pop(ll.LEDGER_ROOT_ENV, None)
    return base


def _git_scrubbed(repo_root, *args, env=None, timeout=None):
    try:
        return subprocess.run(
            ["git", "-C", repo_root, *args],
            capture_output=True,
            text=True,
            env=_scrub_env(env),
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _append_under_lock(repo_root, record, env=None):
    return ll.append_under_lock(repo_root, record, env=env)


def _parse_json_object(text, duplicate_reason):
    """Parse a JSON object; refuse duplicate keys with *duplicate_reason*."""

    def _reject_dupes(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError(duplicate_reason)
            seen[key] = value
        return seen

    try:
        data = json.loads(text, object_pairs_hook=_reject_dupes)
    except ValueError as exc:
        if str(exc) == duplicate_reason:
            return None, duplicate_reason
        return None, None
    except TypeError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    return data, None


def _read_json_file(path, duplicate_reason="json-duplicate-key"):
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None, None
    return _parse_json_object(text, duplicate_reason)


def _fail(reason, **extra):
    out = {"ok": False, "reason": reason}
    out.update(extra)
    return out


def _claude_dispatch_tokens():
    return model_registry.claude_dispatch_tokens()


def _resolve_model(model, repo_root):
    """Resolve the launch model token + where it came from. Never raises."""
    tokens = _claude_dispatch_tokens()
    if not tokens:
        return _fail("model-default-unavailable")
    if model is not None:
        if model not in tokens:
            return _fail("model-not-registry-known")
        return {
            "ok": True,
            "token": model,
            "tokens": tokens,
            "resolution": {"tier": model, "source": "explicit", "reason": None},
        }
    loaded = engine_pref.load_builder_dispatch_tier(repo_root)
    tier = loaded["tier"]
    if tier in tokens:
        return {
            "ok": True,
            "token": tier,
            "tokens": tokens,
            "resolution": {
                "tier": tier,
                "source": loaded["source"],
                "reason": loaded["reason"],
            },
        }
    fallback = engine_pref.BUILDER_DISPATCH_TIER_DEFAULT
    if fallback not in tokens:
        return _fail("model-default-unavailable")
    return {
        "ok": True,
        "token": fallback,
        "tokens": tokens,
        "resolution": {
            "tier": fallback,
            "source": "invalid-config-default",
            "reason": "model-not-registry-known:%s" % tier,
        },
    }


def _parse_iso8601(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ledger_live_state(repo_root, env=None):
    lp = ll.ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {
            "ok": False,
            "reason": lp["reason"],
            "live": [],
            "unreadable": True,
            "unavailable": False,
        }
    read_result = ll.read(repo_root, env=env)
    state = read_result["state"]
    if state not in ("ok", "missing"):
        return {
            "ok": False,
            "reason": "ledger-%s" % state,
            "live": [],
            "unreadable": True,
            "unavailable": False,
        }
    if state == "ok":
        folded = ll.fold(read_result["records"])
        if not folded["ok"]:
            return {
                "ok": False,
                "reason": folded["reason"],
                "live": [],
                "unreadable": True,
                "unavailable": False,
            }
    live = ll.live_launches(read_result["records"])
    return {
        "ok": True,
        "reason": None,
        "live": live,
        "unreadable": False,
        "unavailable": False,
    }


def walk_preflight(checks_input, repo_root, env=None, doctrine_loader=None):
    """Walk preflight checks. Never raises."""
    loader = doctrine_loader or launch_doctrine.load
    doctrine = loader()
    if not doctrine.get("ok"):
        return _fail(doctrine.get("reason") or "doctrine-unreadable")

    if not isinstance(checks_input, dict):
        return _fail("preflight-malformed-input")

    for owned in launch_doctrine.LAUNCHER_OWNED_CHECKS:
        if owned in checks_input:
            return _fail("preflight-launcher-owned-check:%s" % owned)

    known_ids = {cid for cid, _cls in launch_doctrine.PREFLIGHT_CHECKS}
    for key in checks_input:
        if key not in known_ids:
            return _fail("preflight-unknown-check:%s" % key)

    ledger_state = _ledger_live_state(repo_root, env=env)

    out_checks = []
    for check_id, check_class in launch_doctrine.PREFLIGHT_CHECKS:
        if check_id == "standing-rulings":
            out_checks.append({
                "id": check_id,
                "class": check_class,
                "state": "pass",
                "reason": "",
                "evidence": doctrine["digest"],
            })
            continue

        if check_id not in checks_input:
            return _fail("preflight-missing-check:%s" % check_id)

        entry = checks_input[check_id]
        if not isinstance(entry, dict):
            return _fail("preflight-malformed-input")

        state = entry.get("state")
        if state not in _VALID_STATES:
            return _fail("preflight-bad-state:%s" % check_id)

        reason = entry.get("reason")
        if state == "na":
            if not isinstance(reason, str) or not reason.strip():
                return _fail("preflight-na-without-reason:%s" % check_id)
        else:
            reason = reason if isinstance(reason, str) else ""

        if check_class == "always" and state == "na":
            return _fail("preflight-always-check-na:%s" % check_id)

        if state == "fail":
            return _fail("preflight-failed:%s" % check_id)

        if check_id == "disjoint-surfaces":
            if state == "na":
                if (
                    ledger_state.get("unreadable")
                    or ledger_state.get("unavailable")
                    or ledger_state["live"]
                ):
                    return _fail("preflight-disjointness-required")
            elif ledger_state.get("unreadable"):
                return _fail("preflight-ledger-unreadable")

        out_checks.append({
            "id": check_id,
            "class": check_class,
            "state": state,
            "reason": reason,
            "evidence": entry.get("evidence", "") if isinstance(entry.get("evidence"), str) else "",
        })

    return {"ok": True, "reason": None, "checks": out_checks, "go": True, "doctrine": doctrine}


def _validate_grant_scope(grant):
    if not isinstance(grant, dict):
        return _fail("premise-grant-fuzzy")
    applicable = grant.get("applicable")
    if applicable is False:
        reason = grant.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return _fail("premise-not-applicable-without-reason:grantScope")
        return {"ok": True, "applicable": False}
    if applicable is not True:
        return _fail("premise-grant-fuzzy")
    kind = grant.get("kind")
    if kind == "prs":
        prs = grant.get("prs")
        if not isinstance(prs, list) or not prs or not all(
            isinstance(p, int) and not isinstance(p, bool) for p in prs
        ):
            return _fail("premise-grant-kind")
        return {"ok": True, "applicable": True}
    if kind == "timeBox":
        until = grant.get("until")
        if _parse_iso8601(until) is None:
            return _fail("premise-grant-kind")
        return {"ok": True, "applicable": True}
    if kind == "count":
        count = grant.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            return _fail("premise-grant-kind")
        return {"ok": True, "applicable": True}
    if isinstance(kind, str):
        return _fail("premise-grant-kind")
    return _fail("premise-grant-fuzzy")


def _validate_owner_capability(owner, max_run_minutes):
    if not isinstance(owner, dict):
        return _fail("premise-missing-field:ownerCapability")
    applicable = owner.get("applicable")
    if applicable is False:
        reason = owner.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            return _fail("premise-not-applicable-without-reason:ownerCapability")
        return {"ok": True, "applicable": False}
    if applicable is not True:
        return _fail("premise-missing-field:ownerCapability")
    if "cleared" not in owner:
        return _fail("premise-owner-capability-cleared-missing")
    cleared = owner.get("cleared")
    if isinstance(cleared, str):
        return _fail("premise-owner-capability-cleared-fuzzy")
    if not isinstance(cleared, list):
        return _fail("premise-owner-capability-cleared-fuzzy")
    if not cleared:
        return _fail("premise-owner-capability-cleared-empty")
    for item in cleared:
        if not isinstance(item, str) or not item.strip():
            return _fail("premise-owner-capability-cleared-item-empty")
    expires = owner.get("expiresAt")
    if expires is None:
        return _fail("premise-owner-capability-expiry-missing")
    dt = _parse_iso8601(expires)
    if dt is None:
        return _fail("premise-owner-capability-expiry-unparseable")
    horizon = datetime.now(timezone.utc) + timedelta(minutes=max_run_minutes)
    if dt < horizon:
        return _fail("premise-owner-capability-expires-before-horizon")
    return {"ok": True, "applicable": True}


def _cross_check_preflight(premise_checks, preflight_checks):
    """premise_checks: grant/owner applicable flags; preflight_checks: walk output list."""
    if preflight_checks is None:
        return None
    by_id = {c["id"]: c["state"] for c in preflight_checks}
    grant_applicable = premise_checks.get("grant_applicable")
    owner_applicable = premise_checks.get("owner_applicable")
    if grant_applicable is not None:
        actual = by_id.get("grant-state")
        if not grant_applicable:
            if actual != "na":
                return "premise-check-mismatch:grant-state"
        elif actual == "na":
            return "premise-check-mismatch:grant-state"
    if owner_applicable is not None:
        actual = by_id.get("owner-capability")
        if not owner_applicable:
            if actual != "na":
                return "premise-check-mismatch:owner-capability"
        elif actual == "na":
            return "premise-check-mismatch:owner-capability"
    return None


def validate_premise(premise, repo_root, preflight_checks=None, env=None, issue=None):
    """Validate premise stamp per contract C7. Never raises.

    ``maxRunMinutes`` is a premise horizon used to validate
    ``ownerCapability.expiresAt`` — not an enforced runtime limit.
    """
    if not isinstance(premise, dict):
        return _fail("premise-missing-field:baseCommit")

    required = (
        "baseCommit", "surfaces", "batchId", "issue",
        "maxRunMinutes", "bashMaxTimeoutMs", "grantScope", "ownerCapability",
    )
    for field in required:
        if field not in premise:
            return _fail("premise-missing-field:%s" % field)

    base = premise["baseCommit"]
    if not isinstance(base, str) or not base.strip():
        return _fail("premise-missing-field:baseCommit")
    proc = _git_scrubbed(repo_root, "rev-parse", "--verify", "%s^{commit}" % base.strip(), env=env)
    if proc is None or proc.returncode != 0:
        return _fail("premise-base-commit-unresolved")
    resolved = (proc.stdout or "").strip()
    if not _HEX40.match(resolved):
        return _fail("premise-base-commit-unresolved")

    surfaces = premise["surfaces"]
    if not isinstance(surfaces, list) or not surfaces or not all(
        isinstance(s, str) and s.strip() for s in surfaces
    ):
        return _fail("premise-surfaces-empty")

    if not isinstance(premise["batchId"], str) or not premise["batchId"].strip():
        return _fail("premise-missing-field:batchId")
    if not isinstance(premise["issue"], int) or isinstance(premise["issue"], bool):
        return _fail("premise-missing-field:issue")
    if issue is not None and premise["issue"] != issue:
        return _fail("premise-issue-mismatch")

    max_run = premise["maxRunMinutes"]
    if not isinstance(max_run, int) or isinstance(max_run, bool) or max_run < 1:
        return _fail("premise-max-run-minutes")

    bash_timeout = premise["bashMaxTimeoutMs"]
    if not isinstance(bash_timeout, int) or isinstance(bash_timeout, bool) or bash_timeout < 1:
        return _fail("premise-bash-max-timeout")

    grant_result = _validate_grant_scope(premise["grantScope"])
    if not grant_result["ok"]:
        return grant_result

    owner_result = _validate_owner_capability(premise["ownerCapability"], max_run)
    if not owner_result["ok"]:
        return owner_result

    mismatch = _cross_check_preflight(
        {
            "grant_applicable": grant_result["applicable"],
            "owner_applicable": owner_result["applicable"],
        },
        preflight_checks,
    )
    if mismatch:
        return _fail(mismatch)

    stamped = dict(premise)
    stamped["baseCommit"] = resolved
    stamped["standingExclusions"] = dict(STANDING_EXCLUSIONS)
    return {
        "ok": True,
        "reason": None,
        "premise": stamped,
        "resolvedBaseCommit": resolved,
    }


def compose_launch(repo_root, issue, premise, model=None, doctrine_loader=None):
    """Compose prompt and argv. Never raises."""
    loader = doctrine_loader or launch_doctrine.load
    doctrine = loader()
    if not doctrine.get("ok"):
        return _fail(doctrine.get("reason") or "doctrine-unreadable")

    rulings_block = doctrine.get("rulingsBlock") or ""
    own_line = launch_doctrine.ruling_line(doctrine, "own-worktree")
    if not own_line:
        return _fail("compose-ruling-zero-absent")

    prompt = "%s\n\nIssue: #%s\n\n%s" % (_WORKHORSE_CMD, issue, rulings_block)
    if own_line not in prompt:
        return _fail("compose-ruling-zero-absent")

    model_result = _resolve_model(model, repo_root)
    if not model_result["ok"]:
        return model_result

    token = model_result["token"]
    resolution = model_result["resolution"]
    argv = ["claude", "--model", token, "-p", prompt]
    return {
        "ok": True,
        "reason": None,
        "prompt": prompt,
        "argv": argv,
        "model": token,
        "modelResolution": {
            "tier": resolution["tier"],
            "source": resolution["source"],
            "reason": resolution["reason"],
        },
        "doctrine": doctrine,
    }


def _default_spawn(argv, repo_root, out_fh, err_fh, child_env):
    return subprocess.Popen(
        argv,
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        stdout=out_fh,
        stderr=err_fh,
        start_new_session=True,
        close_fds=True,
        env=child_env,
    )


def _terminalization_reason(term_result, fallback_reason):
    if term_result.get("ok"):
        return fallback_reason
    tr = term_result.get("reason") or "unknown"
    return "terminalization-failed:%s" % tr


def _terminalize(
    repo_root,
    launch_id,
    child_ever_spawned,
    reason,
    evidence=None,
    proc=None,
    stage=None,
    env=None,
    started_repair=None,
):
    """The ONLY writer of a terminal ledger event for a launch. Never raises."""
    result = ll.terminalize(
        repo_root,
        launch_id,
        child_ever_spawned=child_ever_spawned,
        reason=reason,
        evidence=evidence,
        stage=stage,
        proc=proc,
        started_repair=started_repair,
        env=env,
    )
    return {"ok": bool(result.get("ok")), "reason": result.get("reason")}


def _spawn_attempt(
    repo_root,
    launch_id,
    attempt,
    argv,
    log_path,
    err_path,
    bash_max_timeout_ms,
    env=None,
    spawn_fn=None,
):
    """Spawn one attempt; return dict with ok, proc, reason."""
    spawn = spawn_fn or _default_spawn
    child_env = _scrub_env(env)
    child_env[hb.LAUNCH_ID_ENV] = launch_id
    resolved = ll.resolve_root(repo_root, env=env)
    if resolved["ok"]:
        child_env[hb.HEARTBEAT_ROOT_ENV] = resolved["root"]
    child_env["BASH_MAX_TIMEOUT_MS"] = str(bash_max_timeout_ms)
    try:
        out_fh = open(log_path, "ab")
    except OSError:
        return {"ok": False, "reason": "log-open-failed", "proc": None}
    try:
        err_fh = open(err_path, "ab")
    except OSError:
        out_fh.close()
        return {"ok": False, "reason": "log-open-failed", "proc": None}

    try:
        proc = spawn(argv, repo_root, out_fh, err_fh, child_env)
    except OSError:
        out_fh.close()
        err_fh.close()
        return {"ok": False, "reason": "spawn-oserror", "proc": None, "oserror": True}
    out_fh.close()
    err_fh.close()

    started = {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": attempt,
        "pid": proc.pid,
        "logPath": log_path,
        "errPath": err_path,
    }
    append_result = _append_under_lock(repo_root, started, env=env)
    if not append_result["ok"]:
        term = _terminalize(
            repo_root,
            launch_id,
            True,
            append_result["reason"],
            evidence="started-append-failed",
            proc=proc,
            env=env,
            started_repair={
                "attempt": attempt,
                "pid": proc.pid,
                "logPath": log_path,
                "errPath": err_path,
            },
        )
        fail_reason = _terminalization_reason(term, append_result["reason"])
        return {"ok": False, "reason": fail_reason, "proc": None, "refused": True}

    return {"ok": True, "proc": proc}


def _observe_settle(proc, settle_seconds, deadline=None):
    settle_deadline = time.monotonic() + settle_seconds
    while time.monotonic() < settle_deadline:
        if deadline is not None and time.monotonic() >= deadline:
            return "deadline"
        rc = proc.poll()
        if rc is not None:
            return rc
        time.sleep(0.1)
    if deadline is not None and time.monotonic() >= deadline:
        return "deadline"
    rc = proc.poll()
    return rc


def launch_build(
    repo_root,
    issue,
    premise,
    checks_input,
    log_dir,
    model=None,
    env=None,
    doctrine_loader=None,
    spawn_fn=None,
    settle_seconds=None,
    max_attempts=None,
    backoff_seconds=None,
    total_deadline_seconds=None,
):
    """Full launch flow: preflight, premise, compose, reserve, spawn, settle/retry."""
    settle_seconds = _SETTLE_SECONDS if settle_seconds is None else settle_seconds
    max_attempts = _MAX_ATTEMPTS if max_attempts is None else max_attempts
    backoff_seconds = _BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds
    total_deadline_seconds = (
        _TOTAL_DEADLINE_SECONDS if total_deadline_seconds is None else total_deadline_seconds
    )

    launch_id = "launch-%s" % secrets.token_hex(8)
    deadline = time.monotonic() + total_deadline_seconds

    preflight_result = walk_preflight(
        checks_input, repo_root, env=env, doctrine_loader=doctrine_loader,
    )
    if not preflight_result["ok"]:
        stage = "preflight"
        reason = preflight_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, premise, preflight_result, None, env,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _fail(_terminalization_reason(term, reason), launchId=launch_id)
        return _fail(reason, launchId=launch_id)

    premise_result = validate_premise(
        premise,
        repo_root,
        preflight_checks=preflight_result["checks"],
        env=env,
        issue=issue,
    )
    if not premise_result["ok"]:
        stage = "premise"
        reason = premise_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, premise, preflight_result, None, env,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _fail(_terminalization_reason(term, reason), launchId=launch_id)
        return _fail(reason, launchId=launch_id)

    compose_result = compose_launch(
        repo_root, issue, premise_result["premise"], model=model, doctrine_loader=doctrine_loader,
    )
    if not compose_result["ok"]:
        stage = "compose" if compose_result["reason"] != "model-not-registry-known" else "model"
        if compose_result["reason"] == "model-default-unavailable":
            stage = "model"
        reason = compose_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, premise_result["premise"],
            preflight_result, compose_result, env,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _fail(_terminalization_reason(term, reason), launchId=launch_id)
        return _fail(reason, launchId=launch_id)

    stamped = premise_result["premise"]
    doctrine = compose_result["doctrine"]
    argv = compose_result["argv"]

    resolution = compose_result["modelResolution"]
    model_reason = resolution["reason"]
    reserved = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": stamped["batchId"],
        "repoId": ll.repo_identity(repo_root) or "",
        "issue": issue,
        "surfaces": stamped["surfaces"],
        "premise": stamped,
        "preflight": {"checks": preflight_result["checks"]},
        "argv": argv,
        "doctrineDigest": doctrine["digest"],
        "model": compose_result["model"],
        "modelSource": resolution["source"],
        "modelReason": model_reason if model_reason is not None else "",
    }
    reserve_result = ll.reserve(repo_root, reserved, env=env)
    if not reserve_result["ok"]:
        return _fail(reserve_result["reason"], launchId=launch_id)

    try:
        os.makedirs(log_dir, mode=0o700, exist_ok=True)
    except OSError:
        term = _terminalize(
            repo_root,
            launch_id,
            False,
            "log-dir-create-failed",
            stage="log-dir",
            env=env,
        )
        reason = _terminalization_reason(term, "log-dir-create-failed")
        return _fail(reason, launchId=launch_id)
    log_path = os.path.join(log_dir, "%s.stdout" % launch_id)
    err_path = os.path.join(log_dir, "%s.stderr" % launch_id)

    attempt = 1
    child_ever_spawned = False
    while attempt <= max_attempts:
        if time.monotonic() >= deadline:
            term = _terminalize(
                repo_root,
                launch_id,
                child_ever_spawned,
                "deadline",
                evidence="deadline" if child_ever_spawned else None,
                stage="retry-deadline-exceeded" if not child_ever_spawned else None,
                env=env,
            )
            reason = _terminalization_reason(term, "retry-deadline-exceeded")
            return _fail(reason, launchId=launch_id)

        spawn_result = _spawn_attempt(
            repo_root,
            launch_id,
            attempt,
            argv,
            log_path,
            err_path,
            stamped["bashMaxTimeoutMs"],
            env=env,
            spawn_fn=spawn_fn,
        )
        if spawn_result.get("refused"):
            return _fail(spawn_result["reason"], launchId=launch_id)
        if spawn_result.get("oserror"):
            if attempt >= max_attempts:
                term = _terminalize(
                    repo_root,
                    launch_id,
                    False,
                    "spawn-oserror-exhausted",
                    stage="spawn",
                    env=env,
                )
                reason = _terminalization_reason(term, "spawn-oserror-exhausted")
                return _fail(reason, launchId=launch_id)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                term = _terminalize(
                    repo_root,
                    launch_id,
                    False,
                    "deadline",
                    stage="retry-deadline-exceeded",
                    env=env,
                )
                reason = _terminalization_reason(term, "retry-deadline-exceeded")
                return _fail(reason, launchId=launch_id)
            delay_idx = min(attempt - 1, len(backoff_seconds) - 1)
            delay = min(backoff_seconds[delay_idx], remaining)
            if delay >= remaining:
                term = _terminalize(
                    repo_root,
                    launch_id,
                    False,
                    "deadline",
                    stage="retry-deadline-exceeded",
                    env=env,
                )
                reason = _terminalization_reason(term, "retry-deadline-exceeded")
                return _fail(reason, launchId=launch_id)
            retry_record = {
                "event": "retry",
                "launchId": launch_id,
                "ts": time.time(),
                "schema": ll.SCHEMA,
                "attempt": attempt,
                "reason": "spawn-oserror",
                "delaySeconds": delay,
            }
            retry_append = _append_under_lock(repo_root, retry_record, env=env)
            if not retry_append["ok"]:
                term = _terminalize(
                    repo_root,
                    launch_id,
                    False,
                    retry_append["reason"],
                    stage="retry-append-failed",
                    env=env,
                )
                reason = _terminalization_reason(term, retry_append["reason"])
                return _fail(reason, launchId=launch_id)
            if delay > 0:
                time.sleep(delay)
            attempt += 1
            continue
        if not spawn_result["ok"]:
            term = _terminalize(
                repo_root,
                launch_id,
                False,
                spawn_result["reason"],
                stage="spawn",
                env=env,
            )
            reason = _terminalization_reason(term, spawn_result["reason"])
            return _fail(reason, launchId=launch_id)

        child_ever_spawned = True
        proc = spawn_result["proc"]
        rc = _observe_settle(proc, settle_seconds, deadline=deadline)
        if rc == "deadline":
            term = _terminalize(
                repo_root,
                launch_id,
                True,
                "retry-deadline-exceeded",
                evidence="deadline",
                proc=proc,
                env=env,
            )
            reason = _terminalization_reason(term, "retry-deadline-exceeded")
            return _fail(reason, launchId=launch_id)
        if rc is None:
            return {
                "ok": True,
                "reason": None,
                "launchId": launch_id,
                "pid": proc.pid,
                "logPath": log_path,
                "errPath": err_path,
                "attempt": attempt,
                "model": compose_result["model"],
                "modelResolution": compose_result["modelResolution"],
            }

        evidence = "exit-zero" if rc == 0 else "nonzero-exit:%s" % rc
        term = _terminalize(
            repo_root,
            launch_id,
            True,
            evidence,
            evidence=evidence,
            proc=proc,
            env=env,
        )
        if rc == 0:
            reason = _terminalization_reason(term, "settle-exit-zero-uncertain")
            return _fail(reason, launchId=launch_id)
        reason = _terminalization_reason(term, "settle-nonzero-exit")
        return _fail(reason, launchId=launch_id)


def _try_reserve_for_refusal(repo_root, launch_id, issue, premise, preflight_result, compose_result, env):
    """Best-effort reserve so refusal is accounted. Returns {reserved: bool}."""
    if not isinstance(premise, dict):
        return {"reserved": False}
    surfaces = premise.get("surfaces")
    batch_id = premise.get("batchId")
    if not surfaces or not batch_id:
        return {"reserved": False}
    doctrine = (preflight_result or {}).get("doctrine") or launch_doctrine.load()
    digest = doctrine.get("digest") if isinstance(doctrine, dict) else None
    if not digest:
        loaded = launch_doctrine.load()
        digest = loaded.get("digest") or ""
    checks = (preflight_result or {}).get("checks") or []
    argv = []
    model_token = ""
    model_source = ""
    model_reason = ""
    if compose_result and compose_result.get("ok"):
        argv = compose_result.get("argv") or []
        model_token = compose_result.get("model") or ""
        resolution = compose_result.get("modelResolution") or {}
        model_source = resolution.get("source", "")
        reason = resolution.get("reason")
        model_reason = reason if reason is not None else ""
    reserved = {
        "event": "reserved",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "batchId": batch_id,
        "repoId": ll.repo_identity(repo_root) or "",
        "issue": issue if isinstance(issue, int) else premise.get("issue", 0),
        "surfaces": surfaces,
        "premise": premise,
        "preflight": {"checks": checks},
        "argv": argv,
        "doctrineDigest": digest,
        "model": model_token,
        "modelSource": model_source,
        "modelReason": model_reason,
    }
    result = ll.reserve(repo_root, reserved, env=env)
    return {"reserved": result["ok"]}


def record_outcome(repo_root, launch_id, outcome, evidence, env=None):
    """Thin pass-through to launch_ledger.record_outcome."""
    return ll.record_outcome(repo_root, launch_id, outcome, evidence, env=env)


def amend(repo_root, launch_id, kind, value, note, env=None):
    """Thin pass-through to launch_ledger.amend."""
    return ll.amend(repo_root, launch_id, kind, value, note, env=env)


def declare_batch(repo_root, batch_id, expected_launches, env=None):
    """Thin pass-through to launch_ledger.declare_batch."""
    return ll.declare_batch(repo_root, batch_id, expected_launches, env=env)


def count_batch(repo_root, batch_id, env=None):
    """Thin pass-through to launch_ledger.count."""
    return ll.count(repo_root, batch_id, env=env)


def _cli_preflight(args):
    checks, dup_reason = _read_json_file(args.checks, duplicate_reason="preflight-duplicate-key")
    if dup_reason:
        return _fail(dup_reason)
    if checks is None:
        return _fail("preflight-malformed-input")
    return walk_preflight(checks, args.repo_root)


def _cli_compose(args):
    premise, dup_reason = _read_json_file(args.premise, duplicate_reason="premise-duplicate-key")
    if dup_reason:
        return _fail(dup_reason)
    if premise is None:
        return _fail("premise-missing-field:baseCommit")
    premise_result = validate_premise(premise, args.repo_root, issue=args.issue)
    if not premise_result["ok"]:
        return premise_result
    return compose_launch(
        args.repo_root, args.issue, premise_result["premise"], model=args.model,
    )


def _cli_launch(args):
    checks, dup_reason = _read_json_file(args.checks, duplicate_reason="preflight-duplicate-key")
    if dup_reason:
        return _fail(dup_reason)
    if checks is None:
        return _fail("preflight-malformed-input")
    premise, dup_reason = _read_json_file(args.premise, duplicate_reason="premise-duplicate-key")
    if dup_reason:
        return _fail(dup_reason)
    if premise is None:
        return _fail("premise-missing-field:baseCommit")
    return launch_build(
        args.repo_root,
        args.issue,
        premise,
        checks,
        args.log_dir,
        model=args.model,
    )


def _cli_record_outcome(args):
    return record_outcome(args.repo_root, args.launch_id, args.outcome, args.evidence)


def _cli_amend(args):
    if args.kind not in ll.CALLER_WRITABLE_AMENDMENT_KINDS:
        return _fail("amend-kind-not-caller-writable:%s" % args.kind)
    return amend(args.repo_root, args.launch_id, args.kind, args.value, args.note)


def _cli_count(args):
    return count_batch(args.repo_root, args.batch)


def _cli_declare_batch(args):
    expected = args.expected
    if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
        return _fail("batch-expected-invalid")
    return declare_batch(args.repo_root, args.batch, expected)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="launcher")
    sub = parser.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("preflight")
    pf.add_argument("--repo-root", required=True)
    pf.add_argument("--checks", required=True)
    pf.add_argument("--premise", required=False)
    pf.add_argument("--batch", required=False)
    pf.set_defaults(func=_cli_preflight)

    comp = sub.add_parser("compose")
    comp.add_argument("--repo-root", required=True)
    comp.add_argument("--issue", type=int, required=True)
    comp.add_argument("--premise", required=True)
    comp.add_argument("--model", default=None)
    comp.set_defaults(func=_cli_compose)

    la = sub.add_parser("launch")
    la.add_argument("--repo-root", required=True)
    la.add_argument("--issue", type=int, required=True)
    la.add_argument("--premise", required=True)
    la.add_argument("--checks", required=True)
    la.add_argument("--log-dir", required=True)
    la.add_argument("--model", default=None)
    la.set_defaults(func=_cli_launch)

    ro = sub.add_parser("record-outcome")
    ro.add_argument("--repo-root", required=True)
    ro.add_argument("--launch-id", required=True)
    ro.add_argument("--outcome", required=True)
    ro.add_argument("--evidence", required=True)
    ro.set_defaults(func=_cli_record_outcome)

    am = sub.add_parser("amend")
    am.add_argument("--repo-root", required=True)
    am.add_argument("--launch-id", required=True)
    am.add_argument("--kind", required=True)
    am.add_argument("--value", required=True)
    am.add_argument("--note", required=True)
    am.set_defaults(func=_cli_amend)

    ct = sub.add_parser("count")
    ct.add_argument("--repo-root", required=True)
    ct.add_argument("--batch", required=True)
    ct.set_defaults(func=_cli_count)

    db = sub.add_parser("declare-batch")
    db.add_argument("--repo-root", required=True)
    db.add_argument("--batch", required=True)
    db.add_argument("--expected", type=int, required=True)
    db.set_defaults(func=_cli_declare_batch)

    args = parser.parse_args(argv)
    result = args.func(args)
    print(json.dumps(result))
    if not result.get("ok"):
        return 1
    if args.command == "count" and result.get("indeterminate"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
