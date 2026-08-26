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
import uuid
from datetime import datetime, timedelta, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import engine_pref  # noqa: E402
import heartbeat as hb  # noqa: E402
import launch_doctrine  # noqa: E402
import launch_ledger as ll  # noqa: E402
import model_registry  # noqa: E402
import pilot_calibration  # noqa: E402
import pilot_slot  # noqa: E402

SLOT_REF_ENV = "SUPERHEROES_SLOT_REF"
WORKTREES_ROOT_ENV = "SUPERHEROES_WORKTREES_ROOT"
WORKTREES_DIR_NAME = ".superheroes-worktrees"
CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
_DEFAULT_CONFIG_DIR_NAME = ".claude"
# The CLI's documented input for reasoning effort is CLAUDE_CODE_EFFORT_LEVEL, and an
# environment variable takes precedence over both the `--effort` flag and the `effortLevel`
# settings key. CLAUDE_EFFORT is NOT an input: the CLI writes its own resolved effort back
# into the environment under that name, so injecting it is a placebo the CLI overwrites.
# Demonstrated by a four-arm live probe (#1156, vet 178) — injecting CLAUDE_EFFORT=medium
# yields a child that resolves `high`, while CLAUDE_CODE_EFFORT_LEVEL=medium yields `medium`
# even when a stale CLAUDE_EFFORT=high rides along. `ps eww` cannot see this: it shows the
# exec-time environment, not the live resolution, so a spawn-plumbing check is not a receipt.
EFFORT_ENV = "CLAUDE_CODE_EFFORT_LEVEL"
EFFORT_REFLECTION_ENV = "CLAUDE_EFFORT"
# Owner ruling 2026-08-25 (in-channel, walk-3 sitting): every use of Opus 5 runs at effort
# `medium` — "opus 5 works better at medium overall". The launcher pins it at the spawn point
# so a builder can never run at whatever effort the launching session happened to carry;
# builders inherited `high` from an advisor session for a full arc before anyone noticed.
OPUS_TIER = "opus"
OPUS_DEFAULT_EFFORT = "medium"

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

_WORKTREE_GIT_TIMEOUT = 180
_WORKTREE_TAG_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

_WORKTREE_COLLISION_REMEDY = (
    "A build worktree already exists at this path (on disk, or registered with git and "
    "since removed). One worktree per build — the launcher never reuses or forces one, "
    "because a shared checkout is how one session's `git checkout` wiped a sibling's "
    "uncommitted work. Reap the stale worktree first (`git worktree remove <path>`, or "
    "`git worktree prune` when the directory is already gone), then relaunch."
)

_WORKHORSE_CMD = "/superheroes:workhorse"

# What a reader of a `started` record sees when its lane launched over a recorded surface
# overlap (#1054): which lanes it overlaps, and where the cost lands. Both citations are
# to rules those homes actually state — `base-moved` is the doctrine ruling that says to
# rebase when the base moves, and merge-train.md is what requires a remaining lane to stay
# branch-current. merge-train.md does NOT state a "landing order" rule, so this does not
# claim one.
_OVERLAP_EVIDENCE_SUFFIX = (
    "later lander rebases (base-moved ruling) and stays branch-current (merge-train.md)"
)

_SLOT_REMEDY = (
    "Provision this wave's pilot slots first (the advisor's duty — the builder never "
    "self-provisions), then give every lane named in `missing` its own reservation. "
    "The literal `this-launch` in `missing` names the launch being attempted — relaunch "
    "it with `--slot` and `--generation` on the command below. Any other id in `missing` "
    "is a live unslotted lane that must reach a terminal outcome before relaunch — there "
    "is no CLI transition today for a reserved-but-never-started lane. "
    "Relaunch each lane with: "
    "`launcher.py launch --repo-root <repo-root> --issue <n> --premise <FILE PATH> "
    "--checks <FILE PATH> --log-dir <dir> --slot <slot-id> --generation <int> "
    "[--boundary <FILE PATH>]`."
)

_CALIBRATION_UNRESOLVED_REMEDY_WITH_PATH = (
    "The launcher cannot tell whether this project declares pilot slots because pilot "
    "calibration returned cause `cause`. The launcher found a calibration file it could "
    "not read or use at `path` — this is not the project's active profile. Fix or "
    "remove that file, then relaunch."
)

_CALIBRATION_UNREADABLE_REMEDY_WITH_PATH = (
    "The launcher cannot tell whether this project declares pilot slots because pilot "
    "calibration returned cause `cause`. Fix or regenerate the calibration profile at "
    "`path`, then relaunch."
)

_CALIBRATION_UNREADABLE_REMEDY_NO_PATH = (
    "The launcher cannot tell whether this project declares pilot slots because pilot "
    "calibration returned cause `cause`. No profile path is available — check the repo "
    "root and the test-pilot store for a readable calibration layer or profile, then "
    "relaunch."
)

_SLOT_CALIBRATION_POLICY = {
    pilot_calibration.CAUSE_DECLARED: "continue",
    pilot_calibration.CAUSE_NO_CALIBRATION: "pass",
    pilot_calibration.CAUSE_NO_PILOT_BLOCK: "pass",
    pilot_calibration.CAUSE_CREDENTIAL_SET_EMPTY: "pass",
    pilot_calibration.CAUSE_REPO_ROOT_INVALID: "refuse",
    pilot_calibration.CAUSE_RESOLVER_FAILED: "refuse",
    pilot_calibration.CAUSE_CALIBRATION_UNRESOLVED: "refuse",
    pilot_calibration.CAUSE_CALIBRATION_UNREADABLE: "refuse",
    pilot_calibration.CAUSE_NO_CONFIG_BLOCK: "refuse",
    pilot_calibration.CAUSE_CONFIG_UNPARSEABLE: "refuse",
    pilot_calibration.CAUSE_PILOT_BLOCK_MALFORMED: "refuse",
    pilot_calibration.CAUSE_CREDENTIAL_SET_MALFORMED: "refuse",
}

# A refusal returned before parallelism is computed can never be evidence that the
# batch is parallel — only post-determination gate refusals belong here.
_GATE_REFUSAL_REASONS = frozenset({
    "preflight-slot-reservation-required",
    "preflight-slot-calibration-unreadable",
})


def _calibration_unreadable_remedy(cause, path):
    if path:
        template = (
            _CALIBRATION_UNRESOLVED_REMEDY_WITH_PATH
            if cause == pilot_calibration.CAUSE_CALIBRATION_UNRESOLVED
            else _CALIBRATION_UNREADABLE_REMEDY_WITH_PATH
        )
        return template.replace(
            "`cause`", repr(cause)).replace("`path`", repr(path))
    return _CALIBRATION_UNREADABLE_REMEDY_NO_PATH.replace(
        "`cause`", repr(cause))


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


def worktree_root(env=None):
    """Where build worktrees live. ``SUPERHEROES_WORKTREES_ROOT`` wins; else ~/. Never raises."""
    base = dict(env if env is not None else os.environ)
    configured = base.get(WORKTREES_ROOT_ENV)
    if isinstance(configured, str) and configured.strip():
        return os.path.abspath(os.path.expanduser(configured.strip()))
    home = base.get("HOME")
    if not isinstance(home, str) or not home.strip():
        home = os.path.expanduser("~")
    if not os.path.isabs(home):
        return None
    return os.path.join(home, WORKTREES_DIR_NAME)


def _expand_home(path, env):
    """expanduser against the SUPPLIED env's HOME, not the ambient process env.

    The child inherits the env passed here, so expanding `~` through the launcher's own
    HOME would record a root the child never uses.
    """
    if not path.startswith("~"):
        return path
    home = env.get("HOME")
    if not isinstance(home, str) or not home:
        return os.path.expanduser(path)
    if path == "~" or path.startswith("~" + os.sep):
        return home + path[1:]
    return os.path.expanduser(path)


def spawn_config_dir(env=None, cwd=None):
    """The absolute config root the spawned child will write its session transcript under.

    ``_scrub_env`` does not strip ``CLAUDE_CONFIG_DIR``, so the child inherits exactly what
    is read here — that inheritance is what makes this value a true record of where the
    lane's transcript lands rather than a second, independently-derived guess. Recording it
    on the lane's ``reserved`` record is what lets a watcher running under a DIFFERENT
    Claude instance still resolve this lane's transcript (#1036).

    Every branch resolves through the SUPPLIED env and the child's own ``cwd`` — never the
    launcher's ambient environment or working directory — because a root derived from the
    launcher's context is a root the child does not write to. That includes a RELATIVE
    override, which the child resolves against its cwd (the build worktree).

    Returns None when no absolute root can be derived; the caller then omits the field, and
    a consumer reading a record without it falls back to its own env root (pre-#1036
    behaviour). Recording a non-absolute value instead would refuse the whole record.
    """
    base = dict(env if env is not None else os.environ)
    configured = base.get(CONFIG_DIR_ENV)
    if isinstance(configured, str) and configured.strip():
        path = _expand_home(configured.strip(), base)
        if os.path.isabs(path):
            return path
        if isinstance(cwd, str) and os.path.isabs(cwd):
            return os.path.normpath(os.path.join(cwd, path))
        return None
    home = base.get("HOME")
    if not isinstance(home, str) or not home.strip():
        home = os.path.expanduser("~")
    if not os.path.isabs(home):
        return None
    return os.path.join(home, _DEFAULT_CONFIG_DIR_NAME)


def _repo_tag(repo_root):
    """A readable, filesystem-safe stem for the repo the build belongs to."""
    tag = _WORKTREE_TAG_UNSAFE.sub("-", os.path.basename(os.path.abspath(repo_root)))
    return tag.strip("-") or "repo"


def build_worktree_path(repo_root, issue, launch_id, env=None):
    """The path this launch's build worktree gets. One per launch, never shared.

    The launch id's suffix is what makes the name unique per launch: an adoption launch
    for an issue whose prior lane still has a worktree on disk gets its own path rather
    than colliding with — or reusing — the dead build's checkout.
    """
    root = worktree_root(env=env)
    if not root:
        return None
    suffix = launch_id.rsplit("-", 1)[-1] if isinstance(launch_id, str) else ""
    if not suffix:
        return None
    return os.path.join(root, _repo_tag(repo_root), "issue-%s-%s" % (issue, suffix))


def _registered_worktree_paths(repo_root, env=None):
    """Realpaths git currently registers as worktrees, or None when unreadable."""
    proc = _git_scrubbed(
        repo_root, "worktree", "list", "--porcelain",
        env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if proc is None or proc.returncode != 0:
        return None
    paths = set()
    for line in (proc.stdout or "").splitlines():
        if line.startswith("worktree "):
            paths.add(os.path.realpath(line[len("worktree "):].strip()))
    return paths


def create_build_worktree(repo_root, path, base_commit, env=None):
    """Create the build worktree at *path*, detached at *base_commit*. Never raises.

    Fail-closed on every uncertainty: a path that already exists on disk, a path git
    still registers, an unreadable worktree list, or a failed `git worktree add` all
    refuse rather than hand a builder a checkout someone else may be holding.
    """
    if os.path.lexists(path):
        return _fail("launch-worktree-collision", path=path, remedy=_WORKTREE_COLLISION_REMEDY)
    registered = _registered_worktree_paths(repo_root, env=env)
    if registered is None:
        return _fail("launch-worktree-list-failed", path=path)
    if os.path.realpath(path) in registered:
        return _fail("launch-worktree-collision", path=path, remedy=_WORKTREE_COLLISION_REMEDY)
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    except OSError:
        return _fail("launch-worktree-root-create-failed", path=path)
    proc = _git_scrubbed(
        repo_root, "worktree", "add", "--detach", path, base_commit,
        env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if proc is None or proc.returncode != 0:
        return _fail("launch-worktree-create-failed", path=path)
    if not os.path.isdir(path):
        return _fail("launch-worktree-create-failed", path=path)
    return {"ok": True, "reason": None, "path": path}


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


def _preflight_extra(preflight_result):
    extra = {}
    if "missing" in preflight_result:
        extra["missing"] = preflight_result["missing"]
    if "remedy" in preflight_result:
        extra["remedy"] = preflight_result["remedy"]
    if "path" in preflight_result:
        extra["path"] = preflight_result["path"]
    if "cause" in preflight_result:
        extra["cause"] = preflight_result["cause"]
    return extra


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


def _resolve_effort(effort, tier):
    """Resolve the child's reasoning effort + where it came from. Never raises.

    Three outcomes, and the third is the one that matters: an explicit `--effort` is the
    deliberate exception (a flag, not an env accident); a resolved `opus` tier is pinned to
    `medium` by the owner ruling above; every other tier resolves to None, which the spawn
    point reads as "leave the ambient effort variables alone" — the ruling names Opus 5 only.
    """
    if effort is not None:
        resolved, source = effort, "explicit"
    elif tier == OPUS_TIER:
        resolved, source = OPUS_DEFAULT_EFFORT, "opus-policy"
    else:
        return {"ok": True, "effort": None, "source": "inherited"}
    # One gate for BOTH branches, deliberately: the policy default is no more exempt from the
    # registry than a caller's --effort. Were `medium` ever dropped from the claude enum, an
    # opus launch must refuse before spawn rather than spawn at an effort the vendor rejects.
    if resolved not in model_registry.effort_enum("claude"):
        return _fail("effort-not-registry-known")
    return {"ok": True, "effort": resolved, "source": source}


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


def _terminal_reason_from_fold(info, records):
    if not info.get("terminal"):
        return None
    if info.get("terminalKind") == "outcome":
        return info.get("outcome")
    if info.get("terminalKind") == "refused":
        idx = info.get("terminalIndex")
        if idx is not None and 0 <= idx < len(records):
            rec = records[idx]
            if isinstance(rec, dict):
                return rec.get("reason")
    return None


def _gate_parallel_detail(ledger_state):
    """Lanes that count toward parallelism at the post-reserve slot gate."""
    live_detail = ledger_state.get("detail") or {}
    all_detail = ledger_state.get("allDetail") or {}
    out = dict(live_detail)
    for launch_id, info in all_detail.items():
        if launch_id in out:
            continue
        reason = info.get("terminalReason")
        if reason in _GATE_REFUSAL_REASONS:
            out[launch_id] = info
    return out


def _ledger_live_state(repo_root, env=None):
    lp = ll.ledger_path(repo_root, env=env)
    if not lp["ok"]:
        return {
            "ok": False,
            "reason": lp["reason"],
            "live": [],
            "unreadable": True,
            "unavailable": False,
            "detail": {},
            "allDetail": {},
            "declarations": {},
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
            "detail": {},
            "allDetail": {},
            "declarations": {},
        }
    detail = {}
    all_detail = {}
    declarations = {}
    if state == "ok":
        folded = ll.fold(read_result["records"])
        if not folded["ok"]:
            return {
                "ok": False,
                "reason": folded["reason"],
                "live": [],
                "unreadable": True,
                "unavailable": False,
                "detail": {},
                "allDetail": {},
                "declarations": {},
            }
        declarations = folded["batchDeclarations"]
        records = read_result["records"]
        for launch_id, info in folded["launches"].items():
            entry = {
                "batchId": info["batchId"],
                "slot": info.get("slot"),
                "generation": info.get("generation"),
                "terminalReason": _terminal_reason_from_fold(info, records),
            }
            all_detail[launch_id] = entry
            if not info.get("terminal"):
                detail[launch_id] = entry
    live = ll.live_launches(read_result["records"])
    return {
        "ok": True,
        "reason": None,
        "live": live,
        "unreadable": False,
        "unavailable": False,
        "detail": detail,
        "allDetail": all_detail if state == "ok" else {},
        "declarations": declarations,
    }


def _slot_reservation_gate(
    repo_root,
    batch_id,
    slot,
    generation,
    ledger_state,
    exclude_launch_id=None,
    *,
    fail_on_unreadable=False,
    parallel_detail=None,
):
    """Refuse parallel unslotted launches on slot-calibrated projects. Never raises."""
    # axis: parallel slot-calibrated launch with unslotted lane(s) — refuse, not presence
    # disclosure: preflight predicate + launch_build post-reserve re-check; not inside reserve's lock — undeclared-batch races may both pass preflight, re-check refuses at least one before spawn
    if not isinstance(batch_id, str) or not batch_id.strip():
        return None
    if not ledger_state.get("ok") or ledger_state.get("unreadable"):
        if fail_on_unreadable:
            return _fail("post-reserve-ledger-unreadable")
        return None

    declarations = ledger_state.get("declarations") or {}
    detail = ledger_state.get("detail") or {}
    parallel_source = parallel_detail if parallel_detail is not None else detail
    batch_decls = declarations.get(batch_id, [])
    max_expected = 0
    for rec in batch_decls:
        expected = rec.get("expectedLaunches")
        if (
            isinstance(expected, int)
            and not isinstance(expected, bool)
            and expected > max_expected
        ):
            max_expected = expected

    has_reservation_in_batch = False
    for launch_id, info in parallel_source.items():
        if exclude_launch_id and launch_id == exclude_launch_id:
            continue
        if info.get("batchId") == batch_id:
            has_reservation_in_batch = True
            break

    parallel = max_expected > 1 or has_reservation_in_batch
    if not parallel:
        return None

    missing = []
    if slot is None or generation is None:
        missing.append("this-launch")
    for launch_id, info in detail.items():
        if exclude_launch_id and launch_id == exclude_launch_id:
            continue
        if info.get("batchId") != batch_id:
            continue
        if info.get("slot") is None:
            missing.append(launch_id)

    if not missing:
        return None

    slot_info = pilot_calibration.declares_slots(repo_root)
    cause = slot_info.get("cause")
    policy = _SLOT_CALIBRATION_POLICY.get(cause)
    expected_state = pilot_calibration.CAUSE_STATE_MAP.get(cause)
    if (
        policy is None
        or expected_state is None
        or slot_info.get("state") != expected_state
        or slot_info.get("state")
        not in (
            pilot_calibration.STATE_DECLARED,
            pilot_calibration.STATE_ABSENT,
            pilot_calibration.STATE_CANNOT_TELL,
        )
    ):
        return _fail(
            "preflight-slot-calibration-unreadable",
            path=slot_info.get("path"),
            cause=cause,
            remedy=_calibration_unreadable_remedy(cause, slot_info.get("path")),
        )
    if policy == "pass":
        return None
    if policy == "refuse":
        return _fail(
            "preflight-slot-calibration-unreadable",
            path=slot_info.get("path"),
            cause=cause,
            remedy=_calibration_unreadable_remedy(cause, slot_info.get("path")),
        )

    return _fail(
        "preflight-slot-reservation-required",
        missing=missing,
        remedy=_SLOT_REMEDY,
    )


def walk_preflight(
    checks_input,
    repo_root,
    env=None,
    doctrine_loader=None,
    *,
    batch_id=None,
    slot=None,
    generation=None,
):
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
            slot_refusal = _slot_reservation_gate(
                repo_root,
                batch_id,
                slot,
                generation,
                ledger_state,
            )
            if slot_refusal is not None:
                return slot_refusal

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


def compose_launch(repo_root, issue, premise, model=None, doctrine_loader=None, effort=None):
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
    effort_result = _resolve_effort(effort, token)
    if not effort_result["ok"]:
        return effort_result
    session_id = str(uuid.uuid4())
    # The same argv is reused if launch_build retries, so the session id is reused
    # too. That is safe because the only retrying path is spawn-oserror, where
    # Popen raised and no child ever started — every other failure is terminal
    # with no re-spawn.
    argv = ["claude", "--model", token, "--session-id", session_id, "-p", prompt]
    return {
        "ok": True,
        "reason": None,
        "prompt": prompt,
        "argv": argv,
        "sessionId": session_id,
        "model": token,
        "modelResolution": {
            "tier": resolution["tier"],
            "source": resolution["source"],
            "reason": resolution["reason"],
        },
        # None means "inherit" — the spawn point leaves the effort variables untouched. The source
        # is always a word, so the ledger records WHY a lane ran at the effort it ran at.
        "effort": effort_result["effort"],
        "effortSource": effort_result["source"],
        "doctrine": doctrine,
    }


def _default_spawn(argv, cwd, out_fh, err_fh, child_env):
    return subprocess.Popen(
        argv,
        cwd=cwd,
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


def _accounted_fail(reserve_result, reason, launch_id, **extra):
    """A pre-spawn refusal carries the disclosure its accounting reservation recorded.

    These branches refuse before any child spawns, but `_try_reserve_for_refusal` has
    already written a `reserved` record — which may carry `surfaceOverlap` (#1054). A
    result that omits the warning hides an overlap the ledger is holding.
    """
    warnings = list((reserve_result or {}).get("warnings") or [])
    return _fail(reason, launchId=launch_id, warnings=warnings, **extra)


def _overlap_evidence(warnings):
    """Disclosure text for a launch that reserved over live lanes; None when it did not."""
    ids = []
    for warning in warnings or []:
        if not isinstance(warning, str):
            continue
        prefix, sep, live_id = warning.partition(":")
        if prefix != "surface-overlap" or not sep or not live_id.strip():
            continue
        ids.append(live_id.strip())
    if not ids:
        return None
    return "overlaps %s; %s" % (", ".join(ids), _OVERLAP_EVIDENCE_SUFFIX)


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
    slot=None,
    generation=None,
    cwd=None,
    evidence=None,
    effort=None,
):
    """Spawn one attempt in the build worktree; return dict with ok, proc, reason.

    Every spawn this launcher makes passes through here, so the own-worktree invariant is
    asserted here rather than at each caller: a child whose cwd is the primary checkout is
    refused, never spawned. The resolved effort is pinned here for the same reason — this
    is the one place a builder child is born, so a pinned effort cannot be routed around.
    """
    spawn = spawn_fn or _default_spawn
    if not isinstance(cwd, str) or not cwd.strip():
        return {"ok": False, "reason": "spawn-cwd-missing", "proc": None}
    if os.path.realpath(cwd) == os.path.realpath(repo_root):
        return {"ok": False, "reason": "spawn-cwd-is-repo-root", "proc": None}
    child_env = _scrub_env(env)
    child_env[hb.LAUNCH_ID_ENV] = launch_id
    if slot is not None and generation is not None:
        child_env[SLOT_REF_ENV] = pilot_slot.format_slot_ref(slot, generation)
    else:
        child_env.pop(SLOT_REF_ENV, None)
    resolved = ll.resolve_root(repo_root, env=env)
    if resolved["ok"]:
        child_env[hb.HEARTBEAT_ROOT_ENV] = resolved["root"]
    child_env["BASH_MAX_TIMEOUT_MS"] = str(bash_max_timeout_ms)
    # Assignment, not defaulting: the launching session's ambient effort variables are already
    # in `child_env` via `_scrub_env`, so a pinned effort must overwrite the documented input or
    # the accident this closes survives. The stale CLAUDE_EFFORT *reflection* is dropped rather
    # than written: the CLI overwrites it from its own resolution anyway, so writing it would buy
    # nothing while destroying the one honest observable — a child's reflection is evidence of
    # what the CLI resolved only for as long as we do not forge it, and a forged one is exactly
    # the placebo receipt vet 178 caught. A None effort is the inherit case and touches neither.
    if effort is not None:
        child_env[EFFORT_ENV] = effort
        child_env.pop(EFFORT_REFLECTION_ENV, None)
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
        proc = spawn(argv, cwd, out_fh, err_fh, child_env)
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
    if isinstance(evidence, str) and evidence.strip():
        started["evidence"] = evidence
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
            started_repair=dict(
                {
                    "attempt": attempt,
                    "pid": proc.pid,
                    "logPath": log_path,
                    "errPath": err_path,
                },
                **({"evidence": started["evidence"]} if "evidence" in started else {})
            ),
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
    *,
    slot=None,
    generation=None,
    boundary=None,
    effort=None,
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

    batch_id = premise.get("batchId") if isinstance(premise, dict) else None
    if not isinstance(batch_id, str) or not batch_id.strip():
        batch_id = None

    preflight_result = walk_preflight(
        checks_input,
        repo_root,
        env=env,
        doctrine_loader=doctrine_loader,
        batch_id=batch_id,
        slot=slot,
        generation=generation,
    )
    if not preflight_result["ok"]:
        stage = "preflight"
        reason = preflight_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, premise, preflight_result, None, env,
            slot=slot, generation=generation, boundary=boundary,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _accounted_fail(
                    reserve_result,
                    _terminalization_reason(term, reason),
                    launch_id,
                    **_preflight_extra(preflight_result),
                )
        return _accounted_fail(
            reserve_result,
            reason,
            launch_id,
            **_preflight_extra(preflight_result),
        )

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
            slot=slot, generation=generation, boundary=boundary,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _accounted_fail(
                    reserve_result, _terminalization_reason(term, reason), launch_id,
                )
        return _accounted_fail(reserve_result, reason, launch_id)

    compose_result = compose_launch(
        repo_root, issue, premise_result["premise"], model=model, doctrine_loader=doctrine_loader,
        effort=effort,
    )
    if not compose_result["ok"]:
        stage = "compose" if compose_result["reason"] != "model-not-registry-known" else "model"
        if compose_result["reason"] == "model-default-unavailable":
            stage = "model"
        if compose_result["reason"] == "effort-not-registry-known":
            stage = "model"
        reason = compose_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, premise_result["premise"],
            preflight_result, compose_result, env,
            slot=slot, generation=generation, boundary=boundary,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
            if not term["ok"]:
                return _accounted_fail(
                    reserve_result, _terminalization_reason(term, reason), launch_id,
                )
        return _accounted_fail(reserve_result, reason, launch_id)

    stamped = premise_result["premise"]
    doctrine = compose_result["doctrine"]
    argv = compose_result["argv"]

    worktree_path = build_worktree_path(repo_root, issue, launch_id, env=env)
    if not worktree_path:
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, stamped, preflight_result, compose_result, env,
            slot=slot, generation=generation, boundary=boundary,
        )
        if reserve_result.get("reserved"):
            term = _terminalize(
                repo_root, launch_id, False, "launch-worktree-path-unresolvable",
                stage="worktree", env=env,
            )
            if not term["ok"]:
                return _accounted_fail(
                    reserve_result,
                    _terminalization_reason(term, "launch-worktree-path-unresolvable"),
                    launch_id,
                )
        return _accounted_fail(
            reserve_result, "launch-worktree-path-unresolvable", launch_id,
        )

    worktree_result = create_build_worktree(
        repo_root, worktree_path, stamped["baseCommit"], env=env,
    )
    if not worktree_result["ok"]:
        refusal_reason = worktree_result["reason"]
        reserve_result = _try_reserve_for_refusal(
            repo_root, launch_id, issue, stamped, preflight_result, compose_result, env,
            slot=slot, generation=generation, boundary=boundary,
        )
        extra = {"path": worktree_result["path"]}
        if "remedy" in worktree_result:
            extra["remedy"] = worktree_result["remedy"]
        if reserve_result.get("reserved"):
            term = _terminalize(
                repo_root,
                launch_id,
                False,
                refusal_reason,
                stage="worktree",
                env=env,
            )
            if not term["ok"]:
                return _accounted_fail(
                    reserve_result,
                    _terminalization_reason(term, refusal_reason),
                    launch_id,
                    **extra,
                )
        return _accounted_fail(reserve_result, refusal_reason, launch_id, **extra)

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
        # Effort provenance sits beside the model's: "" is the inherit case, which is exactly
        # what a reader needs to tell an unpinned lane from one pinned to the same value.
        "effort": compose_result["effort"] or "",
        "effortSource": compose_result["effortSource"],
        "worktree": worktree_path,
        "sessionId": compose_result["sessionId"],
    }
    config_dir = spawn_config_dir(env=env, cwd=worktree_path)
    if config_dir is not None:
        reserved["configDir"] = config_dir
    if slot is not None:
        reserved["slot"] = slot
    if generation is not None:
        reserved["generation"] = generation
    if boundary is not None:
        reserved["boundary"] = boundary
    reserve_result = ll.reserve(repo_root, reserved, env=env)
    if not reserve_result["ok"]:
        extra = {}
        proc = _git_scrubbed(
            repo_root, "worktree", "remove", worktree_path,
            env=env, timeout=_WORKTREE_GIT_TIMEOUT,
        )
        if proc is None or proc.returncode != 0:
            extra["orphanedWorktree"] = worktree_path
        return _fail(reserve_result["reason"], launchId=launch_id, **extra)

    # The lanes this launch's surfaces overlapped are a recorded, disclosed warning rather
    # than a refusal (#1054). Stamped on the `started` record so a ledger reader sees the
    # accepted overlap and where the cost lands, without the advisor's context.
    warnings = list(reserve_result.get("warnings") or [])
    overlap_evidence = _overlap_evidence(warnings)

    def _post_reserve_fail(reason, **extra):
        """Every return past the reservation carries the overlap disclosure.

        The reservation is where the overlap becomes a fact, so a caller reading a
        LATER failure still needs it — a lane that spawned and then died over an
        accepted overlap is exactly when the advisor wants to know. Routing the
        post-reserve failures through one helper is what keeps a future failure path
        from silently omitting it.
        """
        return _fail(reason, launchId=launch_id, warnings=warnings, **extra)

    ledger_recheck = _ledger_live_state(repo_root, env=env)
    slot_refusal = _slot_reservation_gate(
        repo_root,
        batch_id,
        slot,
        generation,
        ledger_recheck,
        exclude_launch_id=launch_id,
        fail_on_unreadable=True,
        parallel_detail=_gate_parallel_detail(ledger_recheck),
    )
    if slot_refusal is not None:
        refusal_reason = slot_refusal["reason"]
        term = _terminalize(
            repo_root,
            launch_id,
            False,
            refusal_reason,
            stage="preflight",
            env=env,
        )
        reason = _terminalization_reason(term, refusal_reason)
        return _post_reserve_fail(
            reason,
            **_preflight_extra(slot_refusal),
        )

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
        return _post_reserve_fail(reason)
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
            return _post_reserve_fail(reason)

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
            slot=slot,
            generation=generation,
            cwd=worktree_path,
            evidence=overlap_evidence,
            effort=compose_result["effort"],
        )
        if spawn_result.get("refused"):
            return _post_reserve_fail(spawn_result["reason"])
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
                return _post_reserve_fail(reason)
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
                return _post_reserve_fail(reason)
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
                return _post_reserve_fail(reason)
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
                return _post_reserve_fail(reason)
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
            return _post_reserve_fail(reason)

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
            return _post_reserve_fail(reason)
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
                "effort": compose_result["effort"],
                "effortSource": compose_result["effortSource"],
                "worktree": worktree_path,
                "warnings": warnings,
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
            return _post_reserve_fail(reason)
        reason = _terminalization_reason(term, "settle-nonzero-exit")
        return _post_reserve_fail(reason)


def _try_reserve_for_refusal(
    repo_root, launch_id, issue, premise, preflight_result, compose_result, env,
    *, slot=None, generation=None, boundary=None,
):
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
    effort_token = ""
    effort_source = ""
    if compose_result and compose_result.get("ok"):
        argv = compose_result.get("argv") or []
        model_token = compose_result.get("model") or ""
        resolution = compose_result.get("modelResolution") or {}
        model_source = resolution.get("source", "")
        reason = resolution.get("reason")
        model_reason = reason if reason is not None else ""
        effort_token = compose_result.get("effort") or ""
        effort_source = compose_result.get("effortSource") or ""
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
        "effort": effort_token,
        "effortSource": effort_source,
    }
    if slot is not None:
        reserved["slot"] = slot
    if generation is not None:
        reserved["generation"] = generation
    if boundary is not None:
        reserved["boundary"] = boundary
    result = ll.reserve(repo_root, reserved, env=env)
    # This accounting reservation can itself land on a live lane's surfaces, so it carries
    # the same disclosure a normal reservation does (#1054). Dropping it here is how the
    # pre-spawn refusal paths used to return a result that hid an overlap the ledger had
    # already recorded on the reserved record.
    return {"reserved": result["ok"], "warnings": list(result.get("warnings") or [])}


def record_outcome(repo_root, launch_id, outcome, evidence, env=None, await_exit=0):
    """Thin pass-through to launch_ledger.record_outcome."""
    return ll.record_outcome(
        repo_root, launch_id, outcome, evidence, env=env, await_exit=await_exit,
    )


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
    return walk_preflight(
        checks,
        args.repo_root,
        batch_id=args.batch,
        slot=args.slot,
        generation=args.generation,
    )


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
        effort=args.effort,
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

    boundary = None
    if args.boundary is not None:
        if args.slot is None or args.generation is None:
            return _fail("launch-boundary-without-slot-generation")
        boundary_data, boundary_dup = _read_json_file(
            args.boundary, duplicate_reason="boundary-duplicate-key",
        )
        if boundary_dup:
            return _fail(boundary_dup)
        if boundary_data is None:
            return _fail("launch-boundary-unreadable")
        boundary = boundary_data

    return launch_build(
        args.repo_root,
        args.issue,
        premise,
        checks,
        args.log_dir,
        model=args.model,
        slot=args.slot,
        generation=args.generation,
        boundary=boundary,
        effort=args.effort,
    )


def _cli_record_outcome(args):
    return record_outcome(
        args.repo_root, args.launch_id, args.outcome, args.evidence,
        await_exit=args.await_exit,
    )


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
    pf.add_argument("--slot", default=None)
    pf.add_argument("--generation", type=int, default=None)
    pf.set_defaults(func=_cli_preflight)

    comp = sub.add_parser("compose")
    comp.add_argument("--repo-root", required=True)
    comp.add_argument("--issue", type=int, required=True)
    comp.add_argument("--premise", required=True)
    comp.add_argument("--model", default=None)
    comp.add_argument("--effort", default=None)
    comp.set_defaults(func=_cli_compose)

    la = sub.add_parser("launch")
    la.add_argument("--repo-root", required=True)
    la.add_argument("--issue", type=int, required=True)
    la.add_argument("--premise", required=True)
    la.add_argument("--checks", required=True)
    la.add_argument("--log-dir", required=True)
    la.add_argument("--model", default=None)
    la.add_argument("--effort", default=None)
    la.add_argument("--slot", default=None)
    la.add_argument("--generation", type=int, default=None)
    la.add_argument("--boundary", default=None)
    la.set_defaults(func=_cli_launch)

    ro = sub.add_parser("record-outcome")
    ro.add_argument("--repo-root", required=True)
    ro.add_argument("--launch-id", required=True)
    ro.add_argument("--outcome", required=True)
    ro.add_argument("--evidence", required=True)
    ro.add_argument(
        "--await-exit", type=float, default=0.0,
        help="seconds to keep re-attempting while the lane's child is still alive "
             "(0..1800, default 0 = refuse immediately as before; foreground callers "
             "under a 10-minute tool cap stay <=540 — longer waits are background calls)",
    )
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
    if args.command == "record-outcome" and result.get("recorded") in (
        "amendment", "amendment-existing",
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
