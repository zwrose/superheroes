#!/usr/bin/env python3
"""Headless builder launcher — preflight walk, premise stamp, composition, detached spawn.

Five CLI verbs over one core. Inspection verbs (preflight, compose) never spawn or write the
ledger. ``launch`` walks the checklist, validates the premise, and composes in one process before
reserve and spawn. Never raises to callers."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import functools
import json
import os
import platform
import pty
import re
import secrets
import select
import signal
import struct
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cloud_ready  # noqa: E402
import cloud_setup  # noqa: E402
import config_dir  # noqa: E402
import engine_adapter  # noqa: E402
import engine_dispatch  # noqa: E402
import engine_pref  # noqa: E402
import heartbeat as hb  # noqa: E402
import host_model  # noqa: E402
import launch_doctrine  # noqa: E402
import launch_ledger as ll  # noqa: E402
import launch_place  # noqa: E402
import launch_report  # noqa: E402
import model_registry  # noqa: E402
import pilot_calibration  # noqa: E402
import pilot_slot  # noqa: E402
import stack_check  # noqa: E402

SLOT_REF_ENV = "SUPERHEROES_SLOT_REF"
# The iPhone check is R1-R4 of the iPhone-check register: a launch that asks for it gets one
# fresh simulator phone, made just before the reservation and outside the ledger lock, and its
# builder is told that phone's ID and whether Device Hub is up. No launcher path quits Device
# Hub — quitting it shuts down every simulator on the Mac — or kills an app. The only simulator
# a launcher path removes is the phone its own launch just made, when the reservation refuses
# before writing the record. A launch naming `iphoneModels` gets one phone per named size, all
# handed over and all recorded.
IPHONE_ID_ENV = "SUPERHEROES_IPHONE_ID"
IPHONE_IDS_ENV = "SUPERHEROES_IPHONE_IDS"
DEVICE_HUB_ENV = "SUPERHEROES_DEVICE_HUB"
IPHONE_NONE = "none"
DEVICE_HUB_AVAILABLE = "available"
DEVICE_HUB_UNAVAILABLE = "unavailable"
IPHONE_DEVICE_TYPE = "com.apple.CoreSimulator.SimDeviceType.iPhone-17"
DEVICE_HUB_BUNDLE_ID = "com.apple.dt.Devices"
DEVICE_HUB_PROCESS = "DeviceHub"
# Creation runs before the reservation, outside the ledger lock, so this bounds only the launch itself.
_IPHONE_CREATE_TIMEOUT = 20
_DEVICE_HUB_CMD_TIMEOUT = 30
_DEVICE_HUB_POLL_SECONDS = 10
# The iPhone steps together never run longer than this; the launch deadline is extended by exactly the time they took.
_IPHONE_CEILING_SECONDS = ll.IPHONE_CEILING_SECONDS
# The shortest timeout the poll's last lookup gets once the poll deadline has passed.
_DEVICE_HUB_FINAL_LOOKUP_SECONDS = 1
WORKTREES_ROOT_ENV = "SUPERHEROES_WORKTREES_ROOT"
WORKTREES_DIR_NAME = ".superheroes-worktrees"
CONFIG_DIR_ENV = config_dir.CONFIG_DIR_ENV
_DEFAULT_CONFIG_DIR_NAME = config_dir.DEFAULT_CONFIG_DIR_NAME
_expand_home = config_dir._expand_home
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


def pin_effort(env, effort):
    """Pin ``effort`` in ``env`` for a child: overwrite the documented input and drop the stale
    reflection. A None effort is the inherit case and touches neither."""
    if effort is not None:
        env[EFFORT_ENV] = effort
        env.pop(EFFORT_REFLECTION_ENV, None)


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
_TOTAL_DEADLINE_SECONDS = ll.LAUNCH_DEADLINE_SECONDS

_VALID_STATES = frozenset({"pass", "fail", "na"})
_HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")

# Also bounds each step of the cloud base re-check, so the repair window reads the same number.
_WORKTREE_GIT_TIMEOUT = ll.REMOTE_BASE_STEP_TIMEOUT_SECONDS
_WORKTREE_TAG_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")

_WORKTREE_COLLISION_REMEDY = (
    "A build worktree already exists at this path (on disk, or registered with git and "
    "since removed). One worktree per build — the launcher never reuses or forces one, "
    "because a shared checkout is how one session's `git checkout` wiped a sibling's "
    "uncommitted work. Reap the stale worktree first (`git worktree remove <path>`, or "
    "`git worktree prune` when the directory is already gone), then relaunch."
)

_WORKHORSE_CMD = "/superheroes:workhorse"

# A cloud launch runs the platform command once and reads the session's identity from what it
# prints. The command needs a pseudo-terminal, so its output arrives wrapped in terminal control
# sequences, which are stripped before anything is matched.
PLACE_LOCAL = ll.PLACE_LOCAL
PLACE_CLOUD = ll.PLACE_CLOUD
_CLOUD_SPAWN_TIMEOUT_SECONDS = ll.CLOUD_SPAWN_TIMEOUT_SECONDS
_CLOUD_APPEND_TRIES = ll.STARTED_APPEND_TRIES
_CLOUD_APPEND_PAUSE_SECONDS = ll.STARTED_APPEND_PAUSE_SECONDS
_CLOUD_CREATED_PREFIX = "Created cloud session: "
# The two line patterns capture the whole token where the id sits; the id's grammar is decided
# once, by the ledger's own pattern (`ll._CLOUD_SESSION_ID_RE`), when the receipt is read.
_CLOUD_VIEW_RE = re.compile(r"View: (https://claude\.ai/code/([^?\s]*))")
_CLOUD_RESUME_RE = re.compile(r"Resume with: claude --teleport (\S+)")
_TERMINAL_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_TERMINAL_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_TERMINAL_ESC_RE = re.compile(r"\x1b(?:[()][0-9A-Za-z]|[78]|[@-Z\\-_=>])")
_TERMINAL_CONTROL_RE = re.compile(r"[\x00-\x09\x0b-\x1f]")
_CLOUD_UNCONFIRMED_REMEDY = (
    "The launch command may have created a cloud session that this launcher could not read the "
    "identity of. Look for a session with the name in `cloudSessionName` in the host's session "
    "listing. The lane is left live. When there is no such session, record the lane's outcome "
    "as `died`; when there is one, the lane is that session."
)
_CLOUD_UNCONFIRMED_APPEND_REMEDY = (
    "The launch command may have created a cloud session that this launcher could not read the "
    "identity of, and the `started` record could not be written (`startedAppend` holds why). The "
    "lane is live on its `reserved` record alone. Look for a session with the name in "
    "`cloudSessionName` in the host's session listing. A reported write failure does not prove the "
    "record is absent. Read the ledger first: when the lane already has its `started` record, end "
    "it normally with `record-outcome`; when it does not, restore it with `launcher.py "
    "repair-lane --pending-file <a file holding pendingStarted>`. The result carries the record "
    "a later repair needs in `pendingStarted`."
)
_CLOUD_STARTED_APPEND_REMEDY = (
    "A cloud session exists and is working: its identity is in `cloudSessionId`. The `started` "
    "record could not be written, and `startedAppend` holds why. The lane is left live on its "
    "`reserved` record alone. A reported write failure does not prove the record is absent. Read "
    "the ledger first: when the lane already has its `started` record, end it normally with "
    "`record-outcome`; when it does not, restore it with `launcher.py repair-lane "
    "--pending-file <a file holding pendingStarted>`. Keep the session's identity from this "
    "result and reach the session by it. The result carries the record a later repair needs in "
    "`pendingStarted`."
)

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
    "is a live unslotted lane that must reach a terminal outcome before relaunch — "
    "a reserved-but-never-started lane reaches one with `launcher.py repair-lane`. "
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


def _git_scrubbed(repo_root, *args, env=None, timeout=None):
    try:
        return subprocess.run(
            ["git", "-C", repo_root, *args],
            capture_output=True,
            text=True,
            env=ll.scrub_env(env),
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


def spawn_config_dir(env=None, cwd=None):
    """The absolute config root the spawned child will write its session transcript under.

    ``_spawn_attempt`` INJECTS this value into the child's environment under
    ``CLAUDE_CONFIG_DIR`` (#1246), and the ``reserved`` record carries the same call's
    answer — so the record is not a second, independently-derived guess at where the
    transcript lands, it is the root the child was actually spawned with. Recording it on
    the lane's ``reserved`` record is what lets a watcher running under a DIFFERENT Claude
    instance still resolve this lane's transcript (#1036). Injection rather than plain
    inheritance is what closes the auth-death class: a spawned ``claude -p`` child whose
    ``CLAUDE_CONFIG_DIR`` is unset dies "OAuth session expired", so a caller that forgot the
    export used to kill an unattended lane with a misleading auth error.

    An explicit caller-provided ``CLAUDE_CONFIG_DIR`` wins: the override branch below is
    read first, so the injection can never silently overwrite a deliberate export — it only
    supplies the default the caller did not set. The one normalization it does apply to an
    override is the ``.strip()`` below, which the ``reserved`` record has carried since
    #1036. Handing the child the RAW padded value instead would recreate exactly the
    record/child divergence #1036 exists to prevent — the watcher would search the stripped
    root while the child wrote to the padded one — and a padded export is in practice a
    quoting slip, where stripping is also what the caller meant.

    Every branch resolves through the SUPPLIED env and the child's own ``cwd`` — never the
    launcher's ambient environment or working directory — because a root derived from the
    launcher's context is a root the child does not write to. That includes a RELATIVE
    override, which resolves against the child's cwd (the build worktree); the child is
    handed that resolved ABSOLUTE form, which is the same directory it would have reached
    on its own and is byte-identical to the recorded value.

    Returns None when no absolute root can be derived; the caller then omits the field and
    injects nothing (the child keeps whatever it inherited), and a consumer reading a record
    without it falls back to its own env root (pre-#1036 behaviour). Recording a
    non-absolute value instead would refuse the whole record.
    """
    return config_dir.resolve(env=env, cwd=cwd)


_CTL_KERN = 1
_KERN_PROCARGS2 = 49

_INSTANCE_PIN_REMEDY = (
    "Relaunch with `--allow-foreign-instance` only when you deliberately intend the "
    "builder to run under a Claude instance other than this seat's own."
)


def _parse_kern_procargs2(data):
    """Parse a Darwin KERN_PROCARGS2 payload into exec path, argv, and env. Never raises."""
    try:
        if len(data) < 4:
            return None
        argc = struct.unpack("@I", data[:4])[0]
        pos = 4
        end = data.find(b"\x00", pos)
        if end == -1:
            return None
        exec_path = data[pos:end].decode("utf-8", errors="surrogateescape")
        pos = end + 1
        while pos < len(data) and data[pos] == 0:
            pos += 1
        argv = []
        for _ in range(argc):
            if pos >= len(data):
                return None
            end = data.find(b"\x00", pos)
            if end == -1:
                return None
            argv.append(data[pos:end].decode("utf-8", errors="surrogateescape"))
            pos = end + 1
        while pos < len(data) and data[pos] == 0:
            pos += 1
        env = {}
        while pos < len(data):
            end = data.find(b"\x00", pos)
            if end == -1:
                end = len(data)
            entry = data[pos:end].decode("utf-8", errors="surrogateescape")
            if "=" in entry:
                key, value = entry.split("=", 1)
                env[key] = value
            pos = end + 1
            if end >= len(data):
                break
        return {"exec_path": exec_path, "argv": argv, "env": env}
    except (struct.error, UnicodeDecodeError, ValueError):
        return None


def _read_kern_procargs2_darwin(pid):
    """Read KERN_PROCARGS2 for *pid* on Darwin. Returns bytes or None."""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c"))
    except (OSError, AttributeError):
        return None
    mib = (ctypes.c_int * 3)(_CTL_KERN, _KERN_PROCARGS2, pid)
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) != 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) != 0:
        return None
    return buf.raw[:size.value]


def _read_seat_snapshot_linux(pid):
    try:
        with open("/proc/%d/environ" % pid, "rb") as fh:
            env_data = fh.read()
        exec_path = os.readlink("/proc/%d/exe" % pid)
    except OSError:
        return None
    env = {}
    for entry in env_data.split(b"\x00"):
        if not entry:
            continue
        decoded = entry.decode("utf-8", errors="surrogateescape")
        if "=" in decoded:
            key, value = decoded.split("=", 1)
            env[key] = value
    return {"exec_path": exec_path, "argv": [], "env": env}


def _read_seat_snapshot(pid):
    """Structural seat-process snapshot. Returns dict or None. Never raises."""
    try:
        if platform.system() == "Darwin":
            payload = _read_kern_procargs2_darwin(pid)
            if payload is None:
                return None
            return _parse_kern_procargs2(payload)
        if platform.system() == "Linux":
            return _read_seat_snapshot_linux(pid)
        return None
    except OSError:
        return None


_CLAUDE_VERSIONED_BINARY_RE = re.compile(
    r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?",
)


# Structural classification of installer layouts — not an identity proof;
# the basename "claude" rule was never one either.
def _is_claude_code_runtime(snapshot):
    exec_path = snapshot.get("exec_path") if isinstance(snapshot, dict) else None
    if not isinstance(exec_path, str) or not exec_path:
        return False
    if os.path.basename(exec_path) == "claude":
        return True
    parent = os.path.basename(os.path.dirname(exec_path))
    grandparent = os.path.basename(os.path.dirname(os.path.dirname(exec_path)))
    if parent == "versions" and grandparent == "claude":
        return bool(_CLAUDE_VERSIONED_BINARY_RE.fullmatch(os.path.basename(exec_path)))
    return False


def _normalized_instance_path(path, home):
    if not isinstance(path, str) or not path.strip():
        return None
    expanded = _expand_home(path.strip(), {"HOME": home})
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    if not isinstance(home, str) or not home.strip():
        return None
    home_norm = os.path.normpath(os.path.expanduser(home.strip()))
    return os.path.normpath(os.path.join(home_norm, expanded))


def _claude_seat_pin_gate_applies(env=None):
    """Instance-pin gate applies only on Claude-hosted seats (CLAUDE_PID present)."""
    base = dict(env if env is not None else os.environ)
    pid_raw = base.get("CLAUDE_PID")
    return isinstance(pid_raw, str) and bool(pid_raw.strip())


def seat_config_dir(env=None):
    """The calling seat's own Claude instance root, from its process snapshot. Never raises."""
    base = dict(env if env is not None else os.environ)
    pid_raw = base.get("CLAUDE_PID")
    if not isinstance(pid_raw, str) or not pid_raw.strip():
        return {"instance": None, "reason": "seat-pid-absent"}
    try:
        pid = int(pid_raw.strip())
        if pid <= 0:
            return {"instance": None, "reason": "seat-pid-absent"}
    except ValueError:
        return {"instance": None, "reason": "seat-pid-absent"}

    try:
        snapshot = _read_seat_snapshot(pid)
    except OSError:
        snapshot = None
    if snapshot is None:
        return {"instance": None, "reason": "seat-snapshot-unreadable"}

    if not _is_claude_code_runtime(snapshot):
        return {"instance": None, "reason": "seat-not-claude"}

    seat_env = snapshot.get("env") or {}
    home = seat_env.get("HOME")
    if not isinstance(home, str) or not home.strip():
        return {"instance": None, "reason": "seat-snapshot-unreadable"}
    home_norm = os.path.normpath(os.path.expanduser(home.strip()))

    configured = seat_env.get("CLAUDE_CONFIG_DIR")
    if not isinstance(configured, str) or not configured.strip():
        instance = os.path.normpath(os.path.join(home_norm, _DEFAULT_CONFIG_DIR_NAME))
        return {"instance": instance, "reason": None}

    instance = _normalized_instance_path(configured, home_norm)
    if instance is None:
        return {"instance": None, "reason": "seat-snapshot-unreadable"}
    return {"instance": instance, "reason": None}


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
                "place": info.get("place"),
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
    place=None,
):
    """Refuse parallel unslotted launches on slot-calibrated projects. Never raises.

    A cloud lane has no pilot slot to hold: a cloud launch is never missing one, and a live
    cloud lane is never counted as an unslotted lane.
    """
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
    # axis: a cloud lane needs no slot — neither this launch nor a live lane of the batch is named when it is cloud.
    if (slot is None or generation is None) and place != PLACE_CLOUD:
        missing.append("this-launch")
    for launch_id, info in detail.items():
        if exclude_launch_id and launch_id == exclude_launch_id:
            continue
        if info.get("batchId") != batch_id:
            continue
        # A cloud lane holds no local pilot slot (its record forbids one).
        if info.get("place") == ll.PLACE_CLOUD:
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
    place=None,
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

        entry_out = {
            "id": check_id,
            "class": check_class,
            "state": state,
            "reason": reason,
            "evidence": entry.get("evidence", "") if isinstance(entry.get("evidence"), str) else "",
        }
        if state == "fail":
            out_checks.append(entry_out)
            return _fail("preflight-failed:%s" % check_id, checks=out_checks)

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
                place=place,
            )
            if slot_refusal is not None:
                return slot_refusal

        out_checks.append(entry_out)

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


_ADOPTS_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


def valid_adopts_branch(value):
    """Whether `value` is a branch name a successor launch may adopt: a string of at most 200
    characters starting with a letter or digit, with no `..` or `//`, ending in none of `/`, `.`
    or `.lock`."""
    return (
        isinstance(value, str)
        and _ADOPTS_BRANCH_RE.fullmatch(value) is not None
        and ".." not in value
        and "//" not in value
        and not value.endswith(("/", ".", ".lock"))
    )


_ADOPTS_HEAD_RE = re.compile(r"[0-9a-f]{40}")
ADOPTS_PREFIX = "Adopts branch:"
_ADOPTS_LINE_RE = re.compile(r"^Adopts branch: (\S+) at ([0-9a-f]{40})$")


def valid_adopts_head(value):
    """Whether `value` is a full 40-hex lowercase sha, the pushed head a successor adopts."""
    return isinstance(value, str) and _ADOPTS_HEAD_RE.fullmatch(value) is not None


def adopts_line(branch, head):
    """The one prompt line that names an adopted branch and its pushed head. The composer writes
    it and the cloud builder's parser reads it back: this is the only home of the format."""
    return "%s %s at %s" % (ADOPTS_PREFIX, branch, head)


def parse_adopts_line(line):
    """(branch, head) from one `Adopts branch:` line, or None when the line is not well formed
    (no ` at <40-hex>` part, a branch outside the name shape, a head not 40 lowercase hex)."""
    match = _ADOPTS_LINE_RE.match(line)
    if match is None or not valid_adopts_branch(match.group(1)):
        return None
    return match.group(1), match.group(2)


def adopts_premise_reason(premise):
    """The refusal token for a premise's adoption pair, or None when it is sound. `adoptsBranch`
    must be a valid branch name, and it and `adoptsHead` (a full lowercase sha) come together:
    either one without the other refuses with the head token."""
    if not isinstance(premise, dict):
        return None
    has_branch = "adoptsBranch" in premise
    if has_branch and not valid_adopts_branch(premise["adoptsBranch"]):
        return "premise-adopts-branch-invalid"
    if has_branch != ("adoptsHead" in premise):
        return "premise-adopts-head-invalid"
    if has_branch and not valid_adopts_head(premise["adoptsHead"]):
        return "premise-adopts-head-invalid"
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

    has_stack = "stack" in premise
    has_layer = "layerPosition" in premise
    has_layers_planned = "layersPlanned" in premise
    # axis: stack and layerPosition must both be present or both absent
    if has_stack != has_layer:
        return _fail("premise-stack-fields-incomplete")
    # axis: layersPlanned requires stack and layerPosition
    if has_layers_planned and not has_stack:
        return _fail("premise-stack-layers-planned-incomplete")
    if has_stack:
        stack_val = premise["stack"]
        layer_val = premise["layerPosition"]
        # axis: stack and layerPosition must be positive ints (bool is not an int here)
        if (
            not ll.is_positive_premise_int(stack_val)
            or not ll.is_positive_premise_int(layer_val)
        ):
            return _fail("premise-stack-field-invalid")
        if has_layers_planned:
            layers_planned_val = premise["layersPlanned"]
            # axis: layersPlanned must be a positive int (bool is not an int here)
            if not ll.is_positive_premise_int(layers_planned_val):
                return _fail("premise-stack-layers-planned-invalid")
            # axis: layersPlanned must be at least layerPosition
            if layers_planned_val < layer_val:
                return _fail("premise-stack-layers-planned-under-position")

    if "adopts" in premise:
        # axis: adopts names the pull request an adoption takes over at its own stack
        # position, so it means nothing without the stack pair
        if not has_stack:
            return _fail("premise-adopts-without-stack")
        # axis: adopts must be a positive int pull-request number (bool is not an int here)
        if not ll.is_positive_premise_int(premise["adopts"]):
            return _fail("premise-adopts-invalid")
        # axis: the bottom layer is never gated, so an adopts there would be checked by
        # nothing; a bottom-layer adoption needs no adopts at all
        if premise["layerPosition"] == 1:
            return _fail("premise-adopts-bottom-layer")

    if "dependency" in premise:
        dependency_val = premise["dependency"]
        # axis: dependency must be a positive int (bool is not an int here)
        if not ll.is_positive_premise_int(dependency_val):
            return _fail("premise-dependency-invalid")

    if "iphoneCheck" in premise:
        # axis: iphoneCheck must be a real bool (1 and "yes" are not); False and absent both
        # mean the check is off
        if not isinstance(premise["iphoneCheck"], bool):
            return _fail("premise-iphone-check-invalid")

    if "iphoneModels" in premise:
        models_val = premise["iphoneModels"]
        # axis: iphoneModels names the phone sizes to make — a non-empty list of distinct, unpadded,
        # non-blank strings beside iphoneCheck true; anything else would make a phone the lane did
        # not ask for or none at all, and a size named without the check would never be made
        if (
            not isinstance(models_val, list)
            or not models_val
            or not all(isinstance(m, str) and m.strip() and m == m.strip() for m in models_val)
            or len(set(models_val)) != len(models_val)
            or premise.get("iphoneCheck") is not True
        ):
            return _fail("premise-iphone-models-invalid")

    if "needs" in premise:
        needs_val = premise["needs"]
        # axis: needs is the advisor's list of what only the owner's machine has — a list of non-empty strings, else the routing step would read it as nothing — see bite-proof record wo_b_place_call
        if not isinstance(needs_val, list) or not all(
            isinstance(n, str) and n.strip() for n in needs_val
        ):
            return _fail("premise-needs-invalid")

    if "reportedCloud" in premise:
        # axis: reportedCloud is a fact the cloud reported — only the known keys in their exact shapes — see bite-proof record wo_b_place_call
        if not cloud_ready.valid_reported(premise["reportedCloud"]):
            return _fail("premise-reported-cloud-invalid")

    # axis: adoptsBranch names the pushed branch a successor launch adopts — a string in the branch-name shape, else the builder would be told to check out a name git reads as an option or a path — and adoptsHead, its pushed head, travels with it as a full lowercase sha, else the builder could not tell a moved branch from the one handed over — see bite-proof record adopt_branch
    adopts_reason = adopts_premise_reason(premise)
    if adopts_reason is not None:
        return _fail(adopts_reason)

    stamped = dict(premise)
    stamped["baseCommit"] = resolved
    stamped["standingExclusions"] = dict(STANDING_EXCLUSIONS)
    return {
        "ok": True,
        "reason": None,
        "premise": stamped,
        "resolvedBaseCommit": resolved,
    }


def plugin_version():
    """The `version` of the running plugin's manifest, or None. Never raises."""
    manifest = os.path.join(os.path.dirname(_LIB_DIR), ".claude-plugin", "plugin.json")
    try:
        with open(manifest, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    if isinstance(version, str) and version.strip():
        return version
    return None


def compose_launch(
    repo_root, issue, premise, model=None, doctrine_loader=None, effort=None,
    place=None, cloud_environment=None, session_name=None,
):
    """Compose prompt and argv. Never raises."""
    import launch_lines  # the one home of the launch line labels (cloud_builder parses them back)
    if place not in (None, PLACE_LOCAL, PLACE_CLOUD):
        return _fail("launch-place-invalid")
    cloud = place == PLACE_CLOUD
    loader = doctrine_loader or launch_doctrine.load
    doctrine = loader()
    if not doctrine.get("ok"):
        return _fail(doctrine.get("reason") or "doctrine-unreadable")

    rulings_block = doctrine.get("rulingsBlock") or ""
    own_line = launch_doctrine.ruling_line(doctrine, "own-worktree")
    if not own_line:
        return _fail("compose-ruling-zero-absent")

    adopts = None
    adopts_reason = adopts_premise_reason(premise)
    if adopts_reason is not None:
        return _fail(adopts_reason)
    if isinstance(premise, dict) and "adoptsBranch" in premise:
        adopts = adopts_line(premise["adoptsBranch"], premise["adoptsHead"])
    version = None
    if cloud:
        version = plugin_version()
        if version is None:
            return _fail("compose-plugin-version-unreadable")
        base = premise.get("baseCommit") if isinstance(premise, dict) else None
        if not isinstance(base, str) or not base.strip():
            return _fail("premise-missing-field:baseCommit")
        # Cloud intake reads the base back as a full lowercase 40-hex sha; a value it would refuse
        # is refused here, as given (never stripped or case-folded).
        # axis: the cloud prompt carries only a full lowercase 40-hex base commit — see bite-proof record c8a_wo2.md
        if not valid_adopts_head(base):
            return _fail("premise-base-commit-invalid")
        # axis: the cloud prompt names the cloud environment on its own line — see bite-proof record wo_c_place_call
        environment_line = launch_lines.format_line(launch_lines.ENVIRONMENT, cloud_environment)
        # axis: the cloud prompt names the base commit on its own line — see bite-proof record wo_c_place_call
        base_line = launch_lines.format_line(launch_lines.BASE, base)
        if adopts is not None:
            # axis: the cloud prompt names the adopted branch on its own line right after the base commit — see bite-proof record adopt_branch
            base_line += "\n" + adopts
        place_line = launch_lines.format_line(launch_lines.PLACE, "cloud session")
        version_line = launch_lines.format_line(launch_lines.VERSION, version)
        # axis: every cloud prompt carries the doctrine's standing push permission, between the base lines and the rulings
        cloud_launch_line = doctrine.get("cloudLaunchLine")
        if not isinstance(cloud_launch_line, str) or not cloud_launch_line.strip():
            return _fail("compose-cloud-launch-line-absent")
        prompt = "%s\n\nIssue: #%s\n\n%s\n%s\n%s\n%s\n\n%s\n\n%s" % (
            _WORKHORSE_CMD, issue, place_line, version_line, environment_line, base_line,
            cloud_launch_line, rulings_block,
        )
    elif adopts is not None:
        local_base = premise.get("baseCommit")
        if not isinstance(local_base, str) or not local_base.strip():
            return _fail("premise-missing-field:baseCommit")
        # A local adopt launch never reaches cloud intake, so its base keeps the non-empty check.
        prompt = "%s\n\nIssue: #%s\n\n%s\n%s\n\n%s" % (
            _WORKHORSE_CMD, issue, adopts, launch_lines.format_line(launch_lines.BASE, local_base),
            rulings_block,
        )
    else:
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
    if cloud:
        # A cloud lane has no session id of its own to mint: the platform names the session.
        session_id = None
        built = engine_adapter.claude_cloud_builder_argv(
            token, effort_result["effort"], prompt, cloud_environment, session_name,
        )
    else:
        session_id = str(uuid.uuid4())
        # The same argv is reused if launch_build retries, so the session id is reused
        # too. That is safe because the only retrying path is spawn-oserror, where
        # Popen raised and no child ever started — every other failure is terminal
        # with no re-spawn.
        built = engine_adapter.claude_builder_argv(token, session_id, prompt)
    if built.get("reason") is not None:
        if "detail" in built:
            return _fail(built["reason"], detail=built["detail"])
        return _fail(built["reason"])
    argv = built["argv"]
    composed = {
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
    if cloud:
        composed["place"] = PLACE_CLOUD
        composed["pluginVersion"] = version
        composed["cloudEnvironment"] = cloud_environment
        composed["cloudSessionName"] = session_name
    return composed


# WORKAROUND: headless builders must survive parent session exit via detached spawn
# delete-when: a re-run of the background-session trial observes its "detached spawn"
# condition met; the condition is restated in the keep-or-retire record's marker inventory
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


class _LauncherTerminated(Exception):
    """The launcher was sent SIGTERM or SIGINT while a cloud launch command was running."""


def _make_terminate_handler(state):
    """A SIGTERM/SIGINT handler that records the signal in `state["pending"]` and never raises.

    A raise from a handler lands wherever the launcher happens to be: before the child is in hand
    it would lose the only handle on its process group, and inside the cleanup it would cut the
    group kill short. So the handler only records, and the read loop is what acts on the record.
    """
    def handler(signum, frame):
        state["pending"] = True
    return handler


def _drain_pty(master, chunks, budget=0.5):
    """Append what is still buffered in the pty master to ``chunks``, for at most ``budget`` seconds.

    Stops on no data ready, an empty read, an OSError (EIO once the child has gone, or a closed
    descriptor) or the budget elapsing. Never raises.
    """
    try:
        deadline = time.monotonic() + budget
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.05)
            if not ready:
                break
            data = os.read(master, 65536)
            if not data:
                break
            chunks.append(data)
    except Exception:
        pass


def default_cloud_spawn(argv, cwd, log_path, child_env, timeout):
    """Run the cloud launch command once under a pseudo-terminal and return what it printed.

    The command refuses to run without a terminal, so its stdin, stdout and stderr are the slave
    end of a pseudo-terminal and the output is read off the master end. The child is its own
    session leader, so its process group is its pid: on every path out once it has started
    (exit, timeout, a failed read, any exception) that whole group is sent SIGKILL and the command
    is reaped, so no process the launch started outlives the call. Both descriptors are always
    closed. Raises OSError when the command could not be started (the terminal could not be
    opened, or the command could not be launched). Once it has run, nothing raises: a log that
    cannot be written is not an error, and any other failure is returned as `readError` (the
    exception's class name) beside the output captured so far.
    """
    master, slave = pty.openpty()
    term_state = {"pending": False}
    previous_term = None
    previous_int = None
    try:
        # axis: a launcher cancelled at any point from child creation through cleanup still ends the
        # group it started — the handler is installed before the child exists and only records the
        # SIGTERM; the waits below check the record between short slices, and the cleanup, which no
        # handler can interrupt, runs its group kill and reap to the end.
        try:
            previous_term = signal.signal(
                signal.SIGTERM, _make_terminate_handler(term_state),
            )
        except (ValueError, OSError):
            previous_term = None  # not the main thread: no handler can be installed here
        # axis: Ctrl-C is a cancellation like SIGTERM — recorded, never raised, so the captured
        # output is still logged and the caller still writes the started record.
        try:
            previous_int = signal.signal(
                signal.SIGINT, _make_terminate_handler(term_state),
            )
        except (ValueError, OSError):
            previous_int = None
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                stdin=slave,
                stdout=slave,
                stderr=slave,
                start_new_session=True,
                close_fds=True,
                env=child_env,
            )
        finally:
            try:
                os.close(slave)
            except OSError:
                pass
        # axis: the lane is not ended — once Popen has returned nothing below raises, because the
        # caller reads a raise as "the command never started" and would end a lane whose session
        # may exist; a failure comes back as `readError` beside the output captured so far.
        chunks = []
        timed_out = False
        read_error = None
        try:
            try:
                deadline = time.monotonic() + timeout
                while True:
                    if term_state["pending"]:
                        _drain_pty(master, chunks)
                        raise _LauncherTerminated()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    ready, _, _ = select.select([master], [], [], min(remaining, 0.25))
                    if ready:
                        try:
                            data = os.read(master, 65536)
                        except OSError:
                            break
                        if not data:
                            break
                        chunks.append(data)
                    elif proc.poll() is not None:
                        break
                if not timed_out:
                    wait_until = max(deadline, time.monotonic() + 0.1)
                    while True:
                        if term_state["pending"]:
                            _drain_pty(master, chunks)
                            raise _LauncherTerminated()
                        remaining = wait_until - time.monotonic()
                        if remaining <= 0:
                            timed_out = True
                            break
                        try:
                            proc.wait(timeout=min(remaining, 0.25))
                            break
                        except subprocess.TimeoutExpired:
                            continue
            except Exception as exc:
                read_error = type(exc).__name__
        finally:
            # axis: no process the launch started outlives it — the signal goes to the process group
            # the Popen this function holds leads (its pid), on every path out, never to a caller's.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            except Exception as exc:
                read_error = read_error or type(exc).__name__
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
            except Exception as exc:
                read_error = read_error or type(exc).__name__
        if term_state["pending"]:
            # A SIGTERM that landed after the waits ended (during the cleanup) is still reported.
            read_error = read_error or _LauncherTerminated.__name__
        raw = b"".join(chunks)
        try:
            with open(log_path, "wb") as fh:
                fh.write(raw)
        except OSError:
            pass
        result = {
            "pid": proc.pid,
            "rc": proc.returncode,
            "timedOut": timed_out,
            "output": raw.decode("utf-8", errors="replace"),
        }
        if read_error is not None:
            result["readError"] = read_error
        return result
    finally:
        if previous_term is not None:
            try:
                signal.signal(signal.SIGTERM, previous_term)
            except (ValueError, OSError):
                pass
        if previous_int is not None:
            try:
                signal.signal(signal.SIGINT, previous_int)
            except (ValueError, OSError):
                pass
        try:
            os.close(master)
        except OSError:
            pass


def strip_terminal_sequences(text):
    """The text with terminal control sequences and control bytes other than the newline removed."""
    text = _TERMINAL_OSC_RE.sub("", text)
    text = _TERMINAL_CSI_RE.sub("", text)
    text = _TERMINAL_ESC_RE.sub("", text)
    return _TERMINAL_CONTROL_RE.sub("", text)


def read_cloud_receipt(text, session_name):
    """The `(session_id, session_url)` of a coherent creation receipt in `text`, else None.

    Coherent: a `Created cloud session: <name>` line whose name is `session_name`, then a `View:`
    line or a `Resume with: claude --teleport` line (or both) that yields a session id the ledger
    accepts, and equal ids when both do. The creation text may follow other text on its line. The
    identity lines of a creation line are the complete lines between it and the next creation
    line (or the end of the output); a trailing piece with no newline after it is not complete
    and yields nothing. The id is read from those lines only; a `session_` token elsewhere is not
    one.
    """
    # The last element is the piece after the final newline: a line the output was cut inside.
    lines = [line.strip() for line in text.split("\n")[:-1]]
    created = [i for i, line in enumerate(lines) if _CLOUD_CREATED_PREFIX in line]
    for position, index in enumerate(created):
        line = lines[index]
        announced = line[line.find(_CLOUD_CREATED_PREFIX) + len(_CLOUD_CREATED_PREFIX):]
        # axis: whose session it is — the announced name must equal the name this launch requested.
        if announced.strip() != session_name:
            continue
        # axis: whose receipt it is — identity lines belong to the nearest creation line before them.
        end = created[position + 1] if position + 1 < len(created) else len(lines)
        block = lines[index + 1:end]
        view = next((m for m in map(_CLOUD_VIEW_RE.match, block) if m), None)
        resume = next((m for m in map(_CLOUD_RESUME_RE.match, block) if m), None)
        if view is None and resume is None:
            continue
        view_id = view.group(2) if view is not None else None
        resume_id = resume.group(1) if resume is not None else None
        # axis: one grammar — the ledger's pattern alone decides what a session id is.
        if any(
            token is not None and not ll._CLOUD_SESSION_ID_RE.fullmatch(token)
            for token in (view_id, resume_id)
        ):
            continue
        if view_id is not None and resume_id is not None and view_id != resume_id:
            continue
        return (view_id or resume_id), (view.group(1) if view is not None else None)
    return None


def _pause_between_appends():
    time.sleep(_CLOUD_APPEND_PAUSE_SECONDS)


def _started_already_landed(repo_root, launch_id, env):
    """True when the ledger, read afresh, already holds the lane's `started` record.

    A reported write failure does not prove the record is absent (the line can land and its sync
    fail). A read that fails, or a ledger that does not fold, proves nothing, so it answers False.
    """
    read_result = ll.read(repo_root, env=env)
    if read_result["state"] not in ("ok", "missing"):
        return False
    folded = ll.fold(read_result["records"])
    if not folded["ok"]:
        return False
    lane = folded["launches"].get(launch_id)
    return bool(lane and lane.get("started"))


def _append_started(repo_root, record, env):
    """Append a cloud lane's `started` record, trying up to three times; the last result.

    The append takes a lock, and a brief contention for it is the ordinary cause of a failure, so
    one failure must not strand a lane whose command has already run. After each failure the
    ledger is read again: a lane whose `started` record is already visible is never appended a
    second time, and its failure stands (a visible record is not proof it is durable, and a retried
    sync cannot prove it either), so the pending record is kept for the repair verb.
    """
    for attempt in range(_CLOUD_APPEND_TRIES):
        result = _append_under_lock(repo_root, record, env=env)
        if result["ok"]:
            return result
        # axis: a failed append is not taken as proof the record is absent — the ledger is re-read.
        if _started_already_landed(repo_root, record.get("launchId"), env):
            # axis: a reported storage error stands — a record seen again, or a second sync, does not prove it reached storage (a failed writeback can leave a clean cached page), so the failure and the pending repair stay, and no second append is made.
            return result
        if attempt + 1 < _CLOUD_APPEND_TRIES:
            _pause_between_appends()
    return result


def _run_cloud_spawn(
    repo_root, launch_id, argv, session_name, log_path, err_path, child_env, timeout,
    spawn_fn, evidence, env, post_reserve_fail, success_base,
):
    """Run the cloud launch command once, record the lane's `started`, and shape the result.

    Exactly one outcome applies, in this order: the command never ran (terminalized); a coherent
    creation receipt was read (started, success); no coherent receipt (started with the
    unconfirmed marker, lane left live). Once the command has run, no path ends the lane: a
    session may exist, and only its owner's `record-outcome` ends the lane. Never raises for a
    command that ran.
    """
    spawn = spawn_fn or default_cloud_spawn
    try:
        with open(err_path, "ab"):
            pass
    except OSError:
        term = _terminalize(repo_root, launch_id, False, "log-open-failed", stage="spawn", env=env)
        return post_reserve_fail(_terminalization_reason(term, "log-open-failed"))

    try:
        spawned = spawn(argv, repo_root, log_path, child_env, timeout)
    except OSError:
        term = _terminalize(repo_root, launch_id, False, "spawn-oserror", stage="spawn", env=env)
        return post_reserve_fail(_terminalization_reason(term, "spawn-oserror"))
    if not isinstance(spawned, dict):
        # The command may have run and made a session, so the lane is left live.
        return post_reserve_fail(
            "cloud-spawn-result-invalid", cloudSessionName=session_name, logPath=log_path,
        )

    pid = spawned.get("pid")
    output = spawned.get("output")
    text = strip_terminal_sequences(output) if isinstance(output, str) else ""
    # axis: where the id is read from — only a coherent creation receipt, never a token elsewhere.
    receipt = read_cloud_receipt(text, session_name)

    started = {
        "event": "started",
        "launchId": launch_id,
        "ts": time.time(),
        "schema": ll.SCHEMA,
        "attempt": 1,
        "pid": pid,
        "logPath": log_path,
        "errPath": err_path,
        "cloudSessionName": session_name,
    }
    if isinstance(evidence, str) and evidence.strip():
        started["evidence"] = evidence

    if receipt is not None:
        session_id, session_url = receipt
        started["cloudSessionId"] = session_id
        if session_url is not None:
            started["cloudSessionUrl"] = session_url
        append_result = _append_started(repo_root, started, env)
        if not append_result["ok"]:
            # axis: a session exists and is working — the lane stays live on its `reserved` record.
            return post_reserve_fail(
                "cloud-started-append-failed",
                cloudSessionId=session_id,
                cloudSessionName=session_name,
                cloudSessionUrl=session_url,
                logPath=log_path,
                startedAppend=append_result["reason"],
                pendingStarted=dict(started),
                remedy=_CLOUD_STARTED_APPEND_REMEDY,
            )
        success = dict(success_base)
        success.update({
            "cloudSessionId": session_id,
            "cloudSessionName": session_name,
            "cloudSessionUrl": session_url,
            "pid": pid,
            "logPath": log_path,
            "errPath": err_path,
            "attempt": 1,
        })
        return success

    # axis: an uncertain creation keeps the lane live — whatever the exit code or timeout, a session may exist, so nothing is terminalized.
    started["cloudSessionUnconfirmed"] = True
    append_result = _append_started(repo_root, started, env)
    extra = {}
    remedy = _CLOUD_UNCONFIRMED_REMEDY
    if not append_result["ok"]:
        extra["startedAppend"] = append_result["reason"]
        extra["pendingStarted"] = dict(started)
        remedy = _CLOUD_UNCONFIRMED_APPEND_REMEDY
    return post_reserve_fail(
        "cloud-session-unconfirmed",
        cloudSessionName=session_name,
        logPath=log_path,
        remedy=remedy,
        **extra,
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


def _settle_uncertain_reservation(repo_root, launch_id, reason, stage, env):
    """End a reservation whose append reported failure and whose read-back could not say.

    One terminal write: `terminal` when the landed record is now ended, `absent` when the
    line never landed, `uncertain` when the settle could not read or write the ledger.
    """
    term = _terminalize(repo_root, launch_id, False, reason, stage=stage, env=env)
    if term["ok"]:
        return "terminal"
    if term["reason"] == "terminal-unknown-launch":
        return "absent"
    return "uncertain"


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


def _default_iphone_run(argv, timeout):
    """The one runner every simulator and Device Hub command goes through."""
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _resolve_iphone_models(models, run, budget_seconds):
    """Resolve each named phone size to its simulator device type; never raises.

    Returns {"ok": True, "types": [(name, identifier), ...]} in `models` order, or
    {"ok": False, "reason": ..., "unknownModels": [...]}. The inventory is the output of
    `simctl list devicetypes -j`, read as {"devicetypes": [{"name", "identifier"}, ...]}. A size
    matches by exact name, and only an entry whose identifier is a device-type identifier.
    """
    unreadable = {"ok": False, "reason": "iphone-models-unreadable", "unknownModels": []}
    if budget_seconds <= 0:
        return unreadable
    try:
        proc = run(
            ["xcrun", "simctl", "list", "devicetypes", "-j"],
            min(_IPHONE_CREATE_TIMEOUT, budget_seconds),
        )
        if proc.returncode != 0:
            return unreadable
        data = json.loads(proc.stdout)
        entries = data.get("devicetypes") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return unreadable
        by_name = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name, identifier = entry.get("name"), entry.get("identifier")
            if (
                isinstance(name, str)
                and isinstance(identifier, str)
                and ".SimDeviceType." in identifier
            ):
                by_name.setdefault(name, identifier)
        unknown = [m for m in models if m not in by_name]
        if unknown:
            return {"ok": False, "reason": "iphone-model-unknown", "unknownModels": unknown}
        return {"ok": True, "types": [(m, by_name[m]) for m in models]}
    except Exception:
        return unreadable


def _create_iphone(launch_id, run, budget_seconds, device_type=IPHONE_DEVICE_TYPE, name=None):
    """Create this launch's phone; return {"iphoneId": udid}, or {} on any failure.

    Called just before the reservation, outside the ledger lock, and never raises: a phone
    that could not be made is a launch without a phone, not a failed launch. The command
    never runs longer than `budget_seconds`, and with none left it is not run at all.
    """
    if budget_seconds <= 0:
        return {}
    try:
        proc = run(
            [
                "xcrun", "simctl", "create",
                name if name is not None else "superheroes-%s" % launch_id,
                device_type,
            ],
            min(_IPHONE_CREATE_TIMEOUT, budget_seconds),
        )
        if proc.returncode != 0:
            return {}
        udid = (proc.stdout or "").strip()
        if not ll.is_iphone_id(udid):
            return {}
        return {"iphoneId": udid}
    except Exception:
        return {}


def _delete_own_iphone(udid, run):
    """Delete the phone this launch made; True on exit 0, False otherwise. Never raises."""
    try:
        return run(["xcrun", "simctl", "delete", udid], _IPHONE_CREATE_TIMEOUT).returncode == 0
    except Exception:
        return False


def _ensure_device_hub(run, poll_seconds, budget_seconds):
    """Return DEVICE_HUB_AVAILABLE or DEVICE_HUB_UNAVAILABLE; never raises.

    A Device Hub that is not up is opened, never restarted: the only commands issued are a
    process lookup and an open request. All of it is bounded by `budget_seconds`.
    """
    pgrep_argv = ["pgrep", "-x", DEVICE_HUB_PROCESS]
    end = time.monotonic() + budget_seconds

    def left():
        return end - time.monotonic()

    try:
        if left() <= 0:
            return DEVICE_HUB_UNAVAILABLE
        if run(pgrep_argv, min(_DEVICE_HUB_CMD_TIMEOUT, left())).returncode == 0:
            return DEVICE_HUB_AVAILABLE
        if left() <= 0:
            return DEVICE_HUB_UNAVAILABLE
        # `-g` opens it without bringing it to the foreground, so the owner's front window
        # does not change (UFR-9).
        opened = run(
            ["open", "-g", "-b", DEVICE_HUB_BUNDLE_ID],
            min(_DEVICE_HUB_CMD_TIMEOUT, left()),
        )
        if opened.returncode != 0:
            return DEVICE_HUB_UNAVAILABLE
        poll_deadline = min(time.monotonic() + poll_seconds, end)
        while True:
            time.sleep(max(0.0, min(0.5, poll_deadline - time.monotonic())))
            if left() <= 0:
                return DEVICE_HUB_UNAVAILABLE
            # The last lookup is always made, at or after the poll deadline, so a late wake
            # cannot end the poll without one.
            looked = run(
                pgrep_argv,
                min(
                    _DEVICE_HUB_CMD_TIMEOUT,
                    max(poll_deadline - time.monotonic(), _DEVICE_HUB_FINAL_LOOKUP_SECONDS),
                    left(),
                ),
            )
            if looked.returncode == 0 and time.monotonic() <= end:
                return DEVICE_HUB_AVAILABLE
            if time.monotonic() >= poll_deadline:
                return DEVICE_HUB_UNAVAILABLE
    except Exception:
        return DEVICE_HUB_UNAVAILABLE


# WORKAROUND: launcher refuses spawn when cwd is the primary checkout (own-worktree)
# delete-when: a re-run of the background-session trial observes its
# "launcher-enforced own-worktree half" condition met; the condition is restated in the
# keep-or-retire record's marker inventory
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
    iphone_env=None,
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
    child_env = ll.scrub_env(env)
    for name in host_model.SESSION_ENV_VARS:
        child_env.pop(name, None)   # a child session derives its own host model; a parent's (or its transcript) must never stand in (#2110)
    child_env[hb.LAUNCH_ID_ENV] = launch_id
    if slot is not None and generation is not None:
        child_env[SLOT_REF_ENV] = pilot_slot.format_slot_ref(slot, generation)
    else:
        child_env.pop(SLOT_REF_ENV, None)
    # The scrub is unconditional, so a launch issued from inside an iPhone lane can never hand
    # its own phone to a lane that has none; only the launcher's own iphone_env sets them.
    child_env.pop(IPHONE_ID_ENV, None)
    child_env.pop(IPHONE_IDS_ENV, None)
    child_env.pop(DEVICE_HUB_ENV, None)
    if isinstance(iphone_env, dict):
        child_env.update(iphone_env)
    resolved = ll.resolve_root(repo_root, env=env)
    if resolved["ok"]:
        child_env[hb.HEARTBEAT_ROOT_ENV] = resolved["root"]
    # The config root is PINNED here rather than left to inheritance (#1246). A spawned
    # `claude -p` child with no CLAUDE_CONFIG_DIR dies "OAuth session expired" — an error
    # that reads as an auth failure and is really an unset variable — so a caller who forgot
    # the export killed an unattended lane. Pinning it at the one place a child is born is
    # what makes the export impossible to forget, exactly as the effort pin below does.
    # This is NOT an override: `spawn_config_dir` reads a caller-provided value first, so a
    # deliberate export wins and only the default is supplied. It is also the SAME call the
    # `reserved` record makes, on the same `env` and the same `cwd` (the record passes the
    # worktree path this spawn runs in) — so the recorded configDir and the injected value
    # agree by construction, not by two sites happening to derive the same answer. None means
    # no absolute root could be derived: inject nothing and leave the inherited value alone,
    # matching the record, which omits the field on exactly that branch.
    config_dir = spawn_config_dir(env=env, cwd=cwd)
    if config_dir is not None:
        child_env[CONFIG_DIR_ENV] = config_dir
    child_env["BASH_MAX_TIMEOUT_MS"] = str(bash_max_timeout_ms)
    # Assignment, not defaulting: the launching session's ambient effort variables are already
    # in `child_env` via `ll.scrub_env`, so a pinned effort must overwrite the documented input or
    # the accident this closes survives. The stale CLAUDE_EFFORT *reflection* is dropped rather
    # than written: the CLI overwrites it from its own resolution anyway, so writing it would buy
    # nothing while destroying the one honest observable — a child's reflection is evidence of
    # what the CLI resolved only for as long as we do not forge it, and a forged one is exactly
    # the placebo receipt vet 178 caught. A None effort is the inherit case and touches neither.
    pin_effort(child_env, effort)
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
    # axis: the child's birth identity is recorded at spawn so a reused pid is told from the lane's child.
    # Empty on any failed read; the spawn never depends on it.
    started.update(ll.read_birth_identity(proc.pid))
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
                **({"evidence": started["evidence"]} if "evidence" in started else {}),
                **{field: started[field] for field in ll._BIRTH_IDENTITY_FIELDS if field in started}
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


def _lookup_stack_entry_pr(
    repo_root, resolved_base_commit, env=None, gh_run=None, deadline=None,
):
    """Resolve the open PR whose head is the resolved base commit. Never raises."""
    if gh_run is None:
        gh_run = subprocess.run
    scrubbed = ll.scrub_env(env)
    if deadline is not None and time.monotonic() >= deadline:
        return {"ok": False, "reason": "stack-read-unavailable"}
    slug_deadline = None
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "reason": "stack-read-unavailable"}
        slug_deadline = remaining
    repo_name, slug_refusal = stack_check.resolve_repo_slug(
        repo_root, deadline=slug_deadline, run=gh_run, env=scrubbed,
    )
    if slug_refusal is not None:
        detail = slug_refusal.get("detail") or slug_refusal.get("reason")
        out = {"ok": False, "reason": "stack-read-unavailable"}
        if detail:
            out["detail"] = detail
        return out
    if deadline is not None and time.monotonic() >= deadline:
        return {"ok": False, "reason": "stack-read-unavailable"}
    pr_timeout = 120
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "reason": "stack-read-unavailable"}
        pr_timeout = min(120, remaining)
    pr_list, pr_refusal = stack_check.list_open_prs(
        ("number", "headRefOid", "state"),
        run=gh_run,
        timeout=pr_timeout,
        deadline_at=deadline,
        run_kwargs=dict(cwd=repo_root, env=scrubbed),
    )
    if pr_refusal is not None:
        out = {"ok": False, "reason": "stack-read-unavailable"}
        if pr_refusal.get("detail"):
            out["detail"] = pr_refusal["detail"]
        return out
    candidates = []
    for pr in pr_list:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        if pr.get("state") != "OPEN":
            continue
        if not stack_check.same_commit(pr.get("headRefOid"), resolved_base_commit):
            continue
        if not isinstance(number, int) or isinstance(number, bool):
            continue
        candidates.append(number)
    # axis: zero open PRs carry this head — base is not a layer head
    if not candidates:
        return {"ok": False, "reason": "base-not-layer-head"}
    # axis: ambiguous or unreadable entry PR lookup
    if len(candidates) > 1:
        return {"ok": False, "reason": "stack-read-unavailable"}
    return {"ok": True, "pr": candidates[0], "repo": repo_name}


def _apply_stack_gate(
    stamped_premise,
    resolved_base_commit,
    repo_root,
    env,
    pr_lookup,
    membership_reader,
    deadline=None,
):
    """Run the layer gate when the premise names a stack; GitHub-side and argument-side failures return a refusal dict and raise nothing, while a violated internal pair-slot invariant in membership_reader raises AssertionError."""
    stack_num = stamped_premise["stack"]
    layer_pos = stamped_premise["layerPosition"]
    if layer_pos == 1:
        return {
            "ok": True,
            "stackGate": {"applied": False, "reason": "bottom-layer"},
        }
    if deadline is not None and time.monotonic() >= deadline:
        return {"ok": False, "reason": "stack-read-unavailable"}
    lookup = pr_lookup(repo_root, resolved_base_commit, env=env, deadline=deadline)
    if not lookup["ok"]:
        out = {"ok": False, "reason": lookup["reason"]}
        if "detail" in lookup:
            out["detail"] = lookup["detail"]
        return out
    entry_pr = lookup["pr"]
    repo_name = lookup["repo"]
    membership_deadline = None
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "reason": "stack-read-unavailable"}
        membership_deadline = remaining
    membership = membership_reader(
        pr=entry_pr,
        repo=repo_name,
        expect_stack=stack_num,
        deadline=membership_deadline,
    )
    if not membership["ok"]:
        reason = membership.get("reason")
        # axis: entry PR is not linked to a stack
        if reason == stack_check.REASON_NOT_LINKED:
            return {"ok": False, "reason": "base-not-layer-head"}
        # axis: membership read found stack order inconsistent with premise
        if reason == stack_check.REASON_ORDER_MISMATCH:
            out = {"ok": False, "reason": "order-mismatch"}
            if "detail" in membership:
                out["detail"] = membership["detail"]
            return out
        return {
            "ok": False,
            "reason": "stack-read-unavailable",
            "detail": reason,
        }
    queried = membership["queried"]
    members = membership.get("members", [])
    adopts = stamped_premise.get("adopts")
    occupant_adopted = False
    # axis: claimed layer position is already occupied in the stack
    for member in members:
        position = member.get("position")
        if (
            isinstance(position, int)
            and not isinstance(position, bool)
            and position == layer_pos
        ):
            # bite-axis: an adoption re-occupies its own position only when the premise names
            # that exact occupant and the occupant sits on the layer below's branch; any other
            # occupant, or no adopts at all, is a new layer landing on a taken position
            if (
                adopts is None
                or member.get("number") != adopts
                or member.get("baseRefName") != queried.get("headRefName")
            ):
                return {"ok": False, "reason": "layer-position-occupied"}
            # axis: the adoption pair names the branch and head the occupant actually holds — the launch continues the pair's branch, so a pair that differs from the occupant would record the stack pull request as taken over while the builder works a different branch
            if "adoptsBranch" in stamped_premise and (
                member.get("headRefName") != stamped_premise["adoptsBranch"]
                or member.get("headRefOid") != stamped_premise["adoptsHead"]
            ):
                return {"ok": False, "reason": "adopts-branch-mismatch"}
            occupant_adopted = True
    # axis: an adoption premise whose position holds no pull request has nothing to adopt
    if adopts is not None and not occupant_adopted:
        return {"ok": False, "reason": "adopts-occupant-missing"}
    # axis: queried position must equal layerPosition - 1
    if queried["position"] != layer_pos - 1:
        return {"ok": False, "reason": "base-not-layer-head"}
    # axis: queried headRefOid must equal resolved base commit
    if not stack_check.same_commit(queried["headRefOid"], resolved_base_commit):
        return {"ok": False, "reason": "base-not-layer-head"}
    stack_gate = {
        "applied": True,
        "stack": stack_num,
        "layerPosition": layer_pos,
        "entryPr": entry_pr,
        "layerBelowHead": resolved_base_commit,
    }
    if occupant_adopted:
        stack_gate["adopts"] = adopts
    return {"ok": True, "stackGate": stack_gate}


def _apply_dependency_gate(
    stamped_premise,
    resolved_base_commit,
    repo_root,
    env,
    pr_vet_reader,
    deadline=None,
):
    """Run the dependency gate when the premise names a dependency; GitHub-side and argument-side failures return a refusal dict and raise nothing."""
    dependency = stamped_premise["dependency"]
    if deadline is not None and time.monotonic() >= deadline:
        return {"ok": False, "reason": "dependency-read-unavailable"}
    scrubbed = ll.scrub_env(env)
    slug_deadline = None
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "reason": "dependency-read-unavailable"}
        slug_deadline = remaining
    repo_name, slug_refusal = stack_check.resolve_repo_slug(
        repo_root, deadline=slug_deadline, env=scrubbed,
    )
    if slug_refusal is not None:
        detail = slug_refusal.get("detail") or slug_refusal.get("reason")
        out = {"ok": False, "reason": "dependency-read-unavailable"}
        if detail:
            out["detail"] = detail
        return out
    if deadline is not None and time.monotonic() >= deadline:
        return {"ok": False, "reason": "dependency-read-unavailable"}
    read_deadline = None
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "reason": "dependency-read-unavailable"}
        read_deadline = remaining
    pr_state, read_refusal = pr_vet_reader(
        dependency,
        repo_name,
        deadline=read_deadline,
        env=scrubbed,
    )
    if read_refusal is not None:
        detail = read_refusal.get("detail") or read_refusal.get("reason")
        out = {"ok": False, "reason": "dependency-read-unavailable"}
        if detail:
            out["detail"] = detail
        return out
    if pr_state is None:
        return {"ok": False, "reason": "dependency-read-unavailable"}
    pr_lifecycle = pr_state["state"]
    # axis: merged dependency is not gated — trunk base is what merged deps are for
    if pr_lifecycle == "MERGED":
        return {
            "ok": True,
            "dependencyGate": {"applied": False, "reason": "dependency-not-open"},
        }
    # axis: closed-unmerged dependency is stale — the premise cannot resolve by itself
    if pr_lifecycle == "CLOSED":
        return {
            "ok": False,
            "reason": "dependency-closed-unmerged",
            "detail": str(dependency),
        }
    # Allowlist guarantees OPEN/MERGED/CLOSED only; any other value refuses.
    if pr_lifecycle != "OPEN":
        return {
            "ok": False,
            "reason": "dependency-read-unavailable",
            "detail": pr_lifecycle,
        }
    # axis: draft dependency is work in flight — verdict is not consulted
    if pr_state.get("isDraft"):
        return {
            "ok": True,
            "dependencyGate": {"applied": False, "reason": "dependency-not-ready"},
        }
    verdict, vet_refusal = stack_check.read_vet_verdict(
        pr_state["body"], pr_state["headRefOid"],
    )
    if vet_refusal is not None:
        out = {"ok": False, "reason": "dependency-read-unavailable"}
        detail = vet_refusal.get("detail") or vet_refusal.get("reason")
        if detail:
            out["detail"] = detail
        return out
    # axis: unreadable verdict is never treated as absent — only explicit not-ready passes
    if verdict != stack_check.VERDICT_READY:
        return {
            "ok": True,
            "dependencyGate": {"applied": False, "reason": "dependency-not-ready"},
        }
    head_sha = pr_state["headRefOid"]
    # axis: READY dependency requires base exactly equal to dependency head
    if stack_check.same_commit(resolved_base_commit, head_sha):
        return {
            "ok": True,
            "dependencyGate": {
                "applied": True,
                "dependency": dependency,
                "dependencyHead": head_sha,
                "verdict": verdict,
            },
        }
    return {
        "ok": False,
        "reason": "dependency-open-ready-pr",
        "detail": head_sha,
    }


def _place_refusal(
    launch_id, place, slot, generation, boundary, premise, cloud_environment, issue,
):
    """The refusal a launch earns for its place before any reservation exists, or None.

    Every refusal here is returned before the ledger is touched, so none of them carries an
    overlap disclosure or leaves a lane behind. Never raises.
    """
    if place not in (None, PLACE_LOCAL, PLACE_CLOUD):
        return _fail("launch-place-invalid", launchId=launch_id)
    if place != PLACE_CLOUD:
        return None
    if slot is not None or generation is not None or boundary is not None:
        return _fail("launch-cloud-with-slot", launchId=launch_id)
    if isinstance(premise, dict) and premise.get("iphoneCheck") is True:
        return _fail("launch-cloud-with-iphone-check", launchId=launch_id)
    if plugin_version() is None:
        return _fail("launch-cloud-plugin-version-unreadable", launchId=launch_id)
    if not isinstance(cloud_environment, str) or not (
        engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(cloud_environment)
    ):
        return _fail("launch-cloud-environment-invalid", launchId=launch_id)
    # axis: refused before any write — a cloud lane is looked up by its issue, so it must be a number.
    if not ll.valid_lane_issue(issue):
        return _fail("launch-cloud-issue-invalid", launchId=launch_id)
    return None


# GitHub's answer when the repository has no such commit: HTTP 422 with this message. Any other
# failure (a missing or private repository, a refused login, a dropped connection) leaves the
# question open.
_BASE_ABSENT_MARKER = "no commit found for sha"

# The forms of a GitHub remote address: scp-like ssh, ssh URL, https URL; ``.git`` optional.
_GITHUB_REMOTE_RE = re.compile(
    r"^(?:git@github\.com:|ssh://git@github\.com/|https://github\.com/)"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


def _gh_commit_lookup(owner, repo, sha, env, timeout):
    """Ask GitHub's commits endpoint for ``sha`` with ``gh``; the completed process, or None when
    ``gh`` could not run or timed out. Tests replace it."""
    try:
        return subprocess.run(
            ["gh", "api", "repos/%s/%s/commits/%s" % (owner, repo, sha), "--jq", ".sha"],
            capture_output=True,
            text=True,
            env=ll.scrub_env(env),
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _base_on_remote(repo_root, base, env):
    """Whether the commit ``base`` is on the remote, asked of GitHub afresh: True, False, or
    None when the remote could not be asked.

    The launching checkout's ``origin`` address names the owner and repository, and the launcher
    asks GitHub's commits endpoint through ``gh`` whether that commit exists there: the host the
    cloud session clones from, and no local tracking ref can be stale. True only when the call
    succeeds and answers with the same commit; False only when GitHub says it has no such commit
    (HTTP 422). Everything else is None: an origin that is not on github.com or is missing, no
    ``gh``, a timeout, a missing or private repository, a refused login, a dropped connection.
    """
    url = _git_scrubbed(
        repo_root, "remote", "get-url", "origin", env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if url is None or url.returncode != 0:
        return None
    matched = _GITHUB_REMOTE_RE.match(url.stdout.strip())
    if matched is None:
        return None
    asked = _gh_commit_lookup(
        matched.group("owner"), matched.group("repo"), base, env, _WORKTREE_GIT_TIMEOUT,
    )
    if asked is None:
        return None
    if asked.returncode == 0:
        return True if (asked.stdout or "").strip() == base else None
    said = (asked.stderr or "").lower()
    if _BASE_ABSENT_MARKER in said and "http 422" in said:
        return False
    return None


# The round-trip to the remote; tests replace it.
_base_on_remote_fn = _base_on_remote


def _cloud_base_refusal(repo_root, stamped, env):
    """The refusal reason when the base commit the launch names is not on the remote, else None.

    The cloud command takes no revision, and the platform starts the session from the launching
    checkout's commit, not from the prompt's ``Base commit:`` line. So the base must be on the
    remote (this function) and the checkout must be on the base (``_cloud_checkout_refusal``).
    Run before reservation and again right before the cloud command: reservation can wait on the
    ledger lock. The check fails closed: a remote that could not be asked refuses.
    """
    # axis: the named base is on the remote, read fresh from the server and never from local tracking refs — see bite-proof record wo_c_place_call
    found = _base_on_remote_fn(repo_root, stamped["baseCommit"], env)
    # axis: a remote that could not be asked refuses — see bite-proof record wo_c_place_call
    if found is None:
        return "launch-cloud-base-remote-unchecked"
    # axis: a base the remote lacks refuses — see bite-proof record wo_c_place_call
    if found is not True:
        return "launch-cloud-base-not-on-remote"
    return None


def _remote_branch_head(repo_root, branch, env):
    """The tip of ``refs/heads/<branch>`` on ``origin``, asked of the remote afresh, as a pair.

    ``(sha, None)`` when the remote answers with exactly that one ref. ``(None, "absent")`` when
    git says no such ref exists (``--exit-code`` exits 2). ``(None, "unchecked")`` for everything
    else: git could not run, a timeout, any other exit code, no line, several lines, or a line
    that does not parse or names another ref. Tests replace it through ``_remote_branch_head_fn``.
    """
    ask_env = dict(os.environ if env is None else env)
    ask_env["GIT_TERMINAL_PROMPT"] = "0"
    ref = "refs/heads/%s" % branch
    asked = _git_scrubbed(
        repo_root, "ls-remote", "--exit-code", "origin", ref,
        env=ask_env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if asked is None:
        return None, "unchecked"
    if asked.returncode == 2:
        return None, "absent"
    if asked.returncode != 0:
        return None, "unchecked"
    lines = (asked.stdout or "").splitlines()
    if len(lines) != 1:
        return None, "unchecked"
    sha, tab, named = lines[0].partition("\t")
    if tab != "\t" or named != ref or not _HEX40.match(sha):
        return None, "unchecked"
    return sha, None


# The round-trip to the remote for a branch tip; tests replace it.
_remote_branch_head_fn = _remote_branch_head


def _read_checkout(repo_root, env):
    """The launching checkout's ``(branch, head)``, each None when it could not be read.

    The branch is read on both sides of the HEAD read, so one result never combines two branches.
    """
    branch = None
    head = None
    named = _git_scrubbed(
        repo_root, "symbolic-ref", "--quiet", "HEAD", env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if named is not None and named.returncode == 0:
        prefix = "refs/heads/"
        said = (named.stdout or "").strip()
        if said.startswith(prefix) and len(said) > len(prefix):
            branch = said[len(prefix):]
    read = _git_scrubbed(
        repo_root, "rev-parse", "--verify", "HEAD^{commit}", env=env,
        timeout=_WORKTREE_GIT_TIMEOUT,
    )
    if read is not None and read.returncode == 0:
        said = (read.stdout or "").strip()
        if _HEX40.match(said):
            head = said
    named = _git_scrubbed(
        repo_root, "symbolic-ref", "--quiet", "HEAD", env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    branch_after = None
    if named is not None and named.returncode == 0:
        said = (named.stdout or "").strip()
        prefix = "refs/heads/"
        if said.startswith(prefix) and len(said) > len(prefix):
            branch_after = said[len(prefix):]
    # axis: a branch read after HEAD that is unreadable or names another branch makes the whole read unreadable — see bite-proof record i1900_cloud_checkout
    if branch_after != branch:
        return None, head
    return branch, head


def _cloud_checkout_refusal(repo_root, base, env):
    """None when the launching checkout is on a named branch whose local HEAD and whose tip on
    ``origin`` are both ``base``; else ``(reason, detail)``. It only reads the checkout.

    The platform starts the session from the checkout's commit, and we cannot tell whether it
    reads the local commit or the branch's tip on the remote, so both must be the base. Anything
    that cannot be read refuses. The checkout is read again after the remote answers, because the
    owner may switch while the lookup is pending.
    """
    branch, head = _read_checkout(repo_root, env)
    detail = {
        "checkout": repo_root,
        "checkoutBranch": branch,
        "checkoutHead": head,
        "baseCommit": base,
    }
    # axis: a branch or HEAD that could not be read refuses, a detached HEAD included — see bite-proof record i1900_cloud_checkout
    if branch is None or head is None:
        return "launch-cloud-checkout-unreadable", detail
    # axis: a checkout whose HEAD is not the base refuses, and the remote is not asked — see bite-proof record i1900_cloud_checkout
    if head != base:
        return "launch-cloud-checkout-off-base", detail
    tip, why = _remote_branch_head_fn(repo_root, branch, env)
    detail["remoteBranchHead"] = tip
    # axis: a remote branch tip that could not be read refuses — see bite-proof record i1900_cloud_checkout
    if why == "unchecked":
        return "launch-cloud-checkout-remote-unchecked", detail
    # axis: a branch the remote lacks refuses — see bite-proof record i1900_cloud_checkout
    if why == "absent":
        return "launch-cloud-checkout-branch-not-on-remote", detail
    # axis: a remote branch tip that is not the base refuses — see bite-proof record i1900_cloud_checkout
    if tip != base:
        return "launch-cloud-checkout-off-base", detail
    again_branch, again_head = _read_checkout(repo_root, env)
    detail["checkoutBranch"] = again_branch
    detail["checkoutHead"] = again_head
    # axis: a checkout that cannot be read again after the remote answered refuses — see bite-proof record i1900_cloud_checkout
    if again_branch is None or again_head is None:
        return "launch-cloud-checkout-unreadable", detail
    # axis: a checkout that moved to another branch or commit while the remote lookup was pending refuses — see bite-proof record i1900_cloud_checkout
    if again_branch != branch or again_head != base:
        return "launch-cloud-checkout-off-base", detail
    return None


def _cloud_start_refusal(repo_root, stamped, env):
    """None, or ``(reason, extra)``: why a cloud launch must not run the cloud command now.

    The base-on-remote refusals come first, with their tokens and their local fallback
    unchanged; then the checkout check, whose refusals carry the checkout's facts in ``extra``.
    """
    reason = _cloud_base_refusal(repo_root, stamped, env)
    if reason is not None:
        return reason, {}
    return _cloud_checkout_refusal(repo_root, stamped["baseCommit"], env)


_ADOPT_HEAD_NOT_ON_BASE = "premise-adopts-head-not-on-base"
_ADOPT_REMEDY_UNDECIDABLE = (
    "Ancestry could not be decided in the launching checkout: fetch the adopted branch so its "
    "head is present, and run git fetch --unshallow when the checkout is shallow, then launch "
    "again. If it still does not descend from baseCommit: "
)
_ADOPT_REMEDY_STACKED = (
    "Bring the adopted branch current with the layer below first: merge the layer below's head "
    "into it and push, then launch again with the same baseCommit. A layer above the bottom "
    "keeps the layer below's head as its base."
)
_ADOPT_REMEDY_BOTTOM = (
    "Bring the adopted branch current with its base first: merge the base into it and push, then "
    "launch again with the same baseCommit. Or set baseCommit to the adopted head and launch "
    "with --repo-root set to a worktree on the adopted branch at that head."
)


def _adopted_head_refusal(repo_root, stamped, env):
    """None when the premise adopts nothing or its ``adoptsHead`` descends from ``baseCommit``;
    else ``(reason, detail)``. It only reads the launching checkout.

    The adopted head must resolve to a commit here, and ``merge-base --is-ancestor`` must exit 0
    for the resolved base (a head equal to the base passes). Exit 1 is ``not-descendant`` only when
    the checkout is positively known not to be shallow; a git that could not run, a head not
    present here, a shallow checkout (its history may be cut short of the base), an unreadable
    shallow state, any other exit, or a base that is not a full sha is ``undecidable``. Both
    refuse, and the ``remedy`` names the fix.
    """
    if "adoptsHead" not in stamped:
        return None
    head = stamped["adoptsHead"]
    base = stamped.get("baseCommit")
    position = stamped.get("layerPosition")
    stacked = isinstance(position, int) and not isinstance(position, bool) and position >= 2
    remedy = _ADOPT_REMEDY_STACKED if stacked else _ADOPT_REMEDY_BOTTOM

    def refusal(ancestry):
        text = remedy if ancestry == "not-descendant" else _ADOPT_REMEDY_UNDECIDABLE + remedy
        return _ADOPT_HEAD_NOT_ON_BASE, {
            "adoptsHead": head, "baseCommit": base, "ancestry": ancestry, "remedy": text,
        }

    # axis: a base that is absent or not a full sha refuses undecidable and git is not run — see bite-proof record i2002_adopt_head_on_base
    if not isinstance(base, str) or not _HEX40.match(base):
        return refusal("undecidable")
    resolved = _git_scrubbed(
        repo_root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % head,
        env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    # axis: an adopted head git could not read refuses undecidable — see bite-proof record i2002_adopt_head_on_base
    if resolved is None:
        return refusal("undecidable")
    # axis: an adopted head that is not a commit in the launching checkout refuses undecidable — see bite-proof record i2002_adopt_head_on_base
    if resolved.returncode != 0:
        return refusal("undecidable")
    asked = _git_scrubbed(
        repo_root, "merge-base", "--is-ancestor", base, head,
        env=env, timeout=_WORKTREE_GIT_TIMEOUT,
    )
    # axis: an ancestry read that could not run refuses undecidable — see bite-proof record i2002_adopt_head_on_base
    if asked is None:
        return refusal("undecidable")
    if asked.returncode == 0:
        return None
    if asked.returncode == 1:
        shallow = _git_scrubbed(
            repo_root, "rev-parse", "--is-shallow-repository",
            env=env, timeout=_WORKTREE_GIT_TIMEOUT,
        )
        # axis: a shallow state git could not read refuses undecidable — see bite-proof record i2002_adopt_head_on_base
        if shallow is None:
            return refusal("undecidable")
        # axis: a shallow-state read that exits non-zero refuses undecidable — see bite-proof record i2002_adopt_head_on_base
        if shallow.returncode != 0:
            return refusal("undecidable")
        answer = (shallow.stdout or "").strip()
        # axis: a head that does not descend from the base in a checkout known not shallow refuses not-descendant — see bite-proof record i2002_adopt_head_on_base
        if answer == "false":
            return refusal("not-descendant")
        # axis: a shallow checkout, or any other shallow answer, refuses undecidable since the ancestry may cross the boundary — see bite-proof record i2002_adopt_head_on_base
        return refusal("undecidable")
    # axis: any ancestry exit other than 0 or 1 refuses undecidable — see bite-proof record i2002_adopt_head_on_base
    return refusal("undecidable")


_ADOPT_ORIGINAL_SESSION_LIVE = "adopt-original-session-live"
_ADOPT_ORIGINAL_SESSION_UNREAD = "adopt-original-session-unread"
_ADOPT_ORIGINAL_REMEDY_LIVE = (
    "The adopted branch's original cloud builder is still live. Send the fix order to that "
    "session (through the relay when it runs on another account) instead of launching a new "
    "lane. Launch a new fix leg only once that session is archived or gone from the listing, "
    "its status bucket reads failed, or cloud_recover assess has recorded it stopped on a "
    "handover."
)
_ADOPT_ORIGINAL_REMEDY_UNREAD = (
    "Record the builders' account's cloud session listing at launch time (one list_sessions "
    "page read with no cursor and has_more false; a get_session result covers only a session it "
    "returns, never one that is gone) and pass it with --cloud-sessions-file; a listing that "
    "cannot be read, or that does not cover every earlier session, refuses."
)
_LISTING_STRING_FIELDS = ("title", "session_status", "status_bucket", "environment_id")
# The owner machine clock that stamped startedTs and the host clock that stamped created_at can disagree.
_ADOPT_ABSENCE_SKEW_SECONDS = 600


def _listing_value(text):
    """The JSON value in *text*; ``ValueError`` on bad JSON or a duplicate key at any depth."""

    def _reject_dupes(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ValueError("json-duplicate-key")
            seen[key] = value
        return seen

    try:
        return json.loads(text, object_pairs_hook=_reject_dupes)
    except (TypeError, RecursionError) as exc:
        raise ValueError("json-unreadable") from exc


def _listing_row_ok(row):
    if not isinstance(row, dict) or not isinstance(row.get("id"), str):
        return False
    if any(k in row and not isinstance(row[k], str) for k in _LISTING_STRING_FIELDS):
        return False
    return "archived" not in row or isinstance(row["archived"], bool)


def _listing_rows(parsed):
    """``(rows, pages, result_count)`` of a parsed listing, or ``None`` when its shape is not a recorded host shape.

    A JSON array is a list of results, anything else is one result; a result that is only a
    ``ccr`` wrapper is unwrapped. A result is a list page (``data`` list, ``has_more`` a bool when
    present) or a session object. ``pages`` are the list-page results, ``rows`` every session row,
    ``result_count`` the number of results the listing held.
    """
    results = parsed if isinstance(parsed, list) else [parsed]
    if not results:
        return None
    rows = []
    pages = []
    for result in results:
        if isinstance(result, dict) and set(result) == {"ccr"}:
            result = result["ccr"]
        if not isinstance(result, dict):
            return None
        if "data" in result:
            if not isinstance(result["data"], list):
                return None
            if "has_more" in result and not isinstance(result["has_more"], bool):
                return None
            pages.append(result)
            found = result["data"]
        else:
            found = [result]
        if not all(_listing_row_ok(row) for row in found):
            return None
        rows.extend(found)
    return rows, pages, len(results)


def _listing_created_ts(row):
    """Epoch seconds of a row's ISO-8601 UTC ``created_at``, or ``None`` when absent or not that."""
    raw = row.get("created_at")
    if not isinstance(raw, str):
        return None
    try:
        stamp = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        return None
    return stamp.timestamp()


def _page_created_by_environment(pages):
    """``{environment_id: newest created epoch}`` of the one complete page when its rows prove the page's span, else ``None``.

    Every row needs a parseable UTC ``created_at`` and the rows must run newest-created first
    (non-increasing); an empty page, an unparseable stamp or a page out of order proves nothing.
    A row with no ``environment_id`` is left out of the map, so it never proves a lane's absence.
    """
    rows = pages[0]["data"]
    stamps = [_listing_created_ts(row) for row in rows]
    if not stamps or any(t is None for t in stamps):
        return None
    if any(later > earlier for earlier, later in zip(stamps, stamps[1:])):
        return None
    newest = {}
    for row, stamp in zip(rows, stamps):
        env_id = row.get("environment_id")
        if isinstance(env_id, str) and stamp > newest.get(env_id, float("-inf")):
            newest[env_id] = stamp
    return newest


def _original_session_refusal(repo_root, issue, stamped, sessions_file, env):
    """None, or ``(reason, detail)``: an adoption must not launch beside a live original builder.

    A premise that carries ``adoptsBranch`` is checked against the cloud lanes the ledger holds for
    the issue that started a session. A lane is exempt when its latest outcome is ``refusal`` (it
    built nothing) or ``cloud_recover assess`` recorded it stopped on a handover. For the others the
    recorded host listing (``sessions_file``) must show the lane's session archived, failed or
    gone: a row that is none of those is live, and a listing that cannot be read, or that does not
    cover a session it does not show, refuses ``adopt-original-session-unread``.
    """
    if "adoptsBranch" not in stamped:
        return None

    def unread(failed, **more):
        return _ADOPT_ORIGINAL_SESSION_UNREAD, dict(
            more, failedRead=failed, remedy=_ADOPT_ORIGINAL_REMEDY_UNREAD,
        )

    got = ll.read(repo_root, env=env)
    folded = ll.fold(got["records"]) if got["state"] in ("ok", "missing") else None
    # axis: a ledger that cannot be read or folded refuses unread, since the earlier lanes are unknown — see bite-proof record i2119_original_session
    if folded is None or not folded.get("ok"):
        return unread("ledger")
    import cloud_recover

    candidates = {
        launch_id: info for launch_id, info in folded["launches"].items()
        if info["place"] == ll.PLACE_CLOUD and str(info["issue"]) == str(issue)
        and info.get("cloudSessionName") is not None
        and cloud_recover._latest_outcome(info) != "refusal"
    }
    if candidates:
        stopped, readable = cloud_recover.handover_stopped_ids(repo_root, env)
        # axis: a recover state that cannot be read refuses unread while a lane still needs it — see bite-proof record i2119_original_session
        if not readable:
            return unread("recover-state")
        candidates = {
            launch_id: info for launch_id, info in candidates.items() if launch_id not in stopped
        }
    if not candidates:
        return None
    # axis: an adoption over a lane that started a session with no listing given refuses unread — see bite-proof record i2119_original_session
    if sessions_file is None:
        return unread("listing-not-given")
    try:
        with open(sessions_file, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return unread("listing-file")
    except UnicodeDecodeError:
        return unread("listing-json")
    try:
        parsed = _listing_value(text)
    except ValueError:
        return unread("listing-json")
    listing = _listing_rows(parsed)
    # axis: a listing that is not a recorded host shape refuses unread — see bite-proof record i2119_original_session
    if listing is None:
        return unread("listing-shape")
    rows, pages, result_count = listing
    complete = result_count == 1 and len(pages) == 1 and pages[0].get("has_more") is False
    # axis: a has_more-false page proves absence only when its rows are ordered and parseable, so a cursor-read last page cannot pass — see bite-proof record i2119_original_session
    created_by_env = _page_created_by_environment(pages) if complete else None
    live = []
    unproven = []
    for launch_id, info in candidates.items():
        if info.get("cloudSessionId") is not None:
            matched = [row for row in rows if row["id"] == info["cloudSessionId"]]
        else:
            matched = [row for row in rows if row.get("title") == info["cloudSessionName"]]
        if not matched:
            started_ts = info.get("startedTs")
            lane_env = info.get("cloudEnvironment")
            newest = (
                created_by_env.get(lane_env)
                if created_by_env is not None and isinstance(lane_env, str) else None
            )
            # axis: absence needs a row of the lane's own cloud environment created at or after the lane started plus the clock-skew allowance, and a lane with no started time or no environment proves nothing, and a lane whose session id was never confirmed is matched by title only, so absence never proves it gone — see bite-proof record i2119_original_session
            if (
                newest is None or not isinstance(started_ts, (int, float))
                or isinstance(started_ts, bool)
                or newest < started_ts + _ADOPT_ABSENCE_SKEW_SECONDS
                or info.get("cloudSessionId") is None
            ):
                unproven.append(launch_id)
            continue
        # a row is not live only when it is archived or failed; any other row, an unknown status included, is live
        showing = [
            row for row in matched
            if row.get("archived") is not True
            and "ARCHIVED" not in row.get("session_status", "")
            and "FAILED" not in row.get("status_bucket", "")
        ]
        if showing:
            live.append({
                "launchId": launch_id,
                "cloudSessionName": info["cloudSessionName"],
                "cloudSessionId": info.get("cloudSessionId"),
                "sessionStatus": showing[0].get("session_status"),
                "statusBucket": showing[0].get("status_bucket"),
            })
    # axis: a candidate whose session the listing shows live refuses, and one it shows archived or failed does not — see bite-proof record i2119_original_session
    if live:
        return _ADOPT_ORIGINAL_SESSION_LIVE, {
            "originalSessions": live, "remedy": _ADOPT_ORIGINAL_REMEDY_LIVE,
        }
    # axis: a candidate absent from a listing that is not one complete page spanning its start is unproven, never gone — see bite-proof record i2119_original_session
    if unproven:
        return unread("listing-incomplete", launchIds=unproven)
    return None


def _refuse_unreserved(
    ctx, reason, stage, premise, preflight_result, compose_result=None, **extra
):
    """Account one refusal that falls before the launch's real reservation.

    A refused launch is still a launch the ledger must show: reserve a record for it, terminalize
    it with `reason` at `stage`, and return the accounted failure. A terminalization failure
    replaces the reason and keeps `extra`. `ctx` is the launch's shared context, built once in
    `launch_build`; every such refusal goes through here so none can return a bare failure.
    """
    reserve_result = _try_reserve_for_refusal(
        ctx["repo_root"], ctx["launch_id"], ctx["issue"], premise, preflight_result,
        compose_result, ctx["env"],
        slot=ctx["slot"], generation=ctx["generation"], boundary=ctx["boundary"],
        seat_instance=ctx["seat_instance"],
        foreign_instance_allowed=ctx["foreign_override"],
        **ctx["place_fields"],
    )
    if reserve_result.get("reserved"):
        term = _terminalize(
            ctx["repo_root"], ctx["launch_id"], False, reason, stage=stage, env=ctx["env"],
        )
        if not term["ok"]:
            return _accounted_fail(
                reserve_result,
                _terminalization_reason(term, reason),
                ctx["launch_id"],
                **extra,
            )
    return _accounted_fail(reserve_result, reason, ctx["launch_id"], **extra)


def _check_premises(
    ctx,
    premise,
    checks_input,
    *,
    model,
    effort,
    doctrine_loader,
    batch_id,
    gate_place,
    cloud,
    cloud_environment,
    cloud_session_name,
    worktree_path,
    deadline,
    pr_vet_reader,
    pr_lookup,
    membership_reader,
    run,
    cloud_sessions_file=None,
):
    """Validate every premise a launch rests on, before anything is reserved or made.

    Walks preflight, validates the premise, applies the dependency and stack gates, checks that an
    adopted head descends from the base and that no earlier cloud builder of an adopted branch is
    still live (`cloud_sessions_file` is the recorded session listing), composes the launch, resolves any named phone sizes
    through `run`, and checks the cloud base (cloud) or the worktree path (local), in that order.
    Returns `{"refusal": <accounted failure>}` on the first
    refusal, else `{"refusal": None}` with the `preflight`, `premise` (stamped), `compose`,
    `stackGate` and `dependencyGate` results, plus `iphoneTypes` (the resolved sizes, empty when
    none are named) and `iphoneSpent` (seconds the size lookup took).
    """
    repo_root = ctx["repo_root"]
    env = ctx["env"]
    if membership_reader is None:
        membership_reader = stack_check.read_membership
    if pr_lookup is None:
        pr_lookup = _lookup_stack_entry_pr
    if pr_vet_reader is None:
        pr_vet_reader = stack_check.read_pr_vet_state

    preflight_result = walk_preflight(
        checks_input,
        repo_root,
        env=env,
        doctrine_loader=doctrine_loader,
        batch_id=batch_id,
        slot=ctx["slot"],
        generation=ctx["generation"],
        place=gate_place,
    )
    if not preflight_result["ok"]:
        return {"refusal": _refuse_unreserved(
            ctx, preflight_result["reason"], "preflight", premise, preflight_result,
            **_preflight_extra(preflight_result),
        )}

    premise_result = validate_premise(
        premise,
        repo_root,
        preflight_checks=preflight_result["checks"],
        env=env,
        issue=ctx["issue"],
    )
    if not premise_result["ok"]:
        return {"refusal": _refuse_unreserved(
            ctx, premise_result["reason"], "premise", premise, preflight_result,
        )}

    stamped_premise = premise_result["premise"]
    resolved_base = premise_result["resolvedBaseCommit"]
    dependency_gate = None
    if "dependency" in stamped_premise:
        gate_result = _apply_dependency_gate(
            stamped_premise,
            resolved_base,
            repo_root,
            env,
            pr_vet_reader,
            deadline=deadline,
        )
        if not gate_result["ok"]:
            extra = {}
            if "detail" in gate_result:
                extra["detail"] = gate_result["detail"]
            return {"refusal": _refuse_unreserved(
                ctx, gate_result["reason"], "dependency", stamped_premise, preflight_result,
                **extra,
            )}
        dependency_gate = gate_result["dependencyGate"]
    stack_gate = None
    if "stack" in stamped_premise:
        gate_result = _apply_stack_gate(
            stamped_premise,
            resolved_base,
            repo_root,
            env,
            pr_lookup,
            membership_reader,
            deadline=deadline,
        )
        if not gate_result["ok"]:
            extra = {}
            if "detail" in gate_result:
                extra["detail"] = gate_result["detail"]
            return {"refusal": _refuse_unreserved(
                ctx, gate_result["reason"], "stack", stamped_premise, preflight_result,
                **extra,
            )}
        stack_gate = gate_result["stackGate"]

    # An adopted head must descend from the resolved base, here and now, before anything is spent.
    # After the stack gate, so a pair off the adopted occupant keeps `adopts-branch-mismatch`.
    refusal = _adopted_head_refusal(repo_root, stamped_premise, env)
    if refusal is not None:
        reason, detail = refusal
        return {"refusal": _refuse_unreserved(
            ctx, reason, "premise", stamped_premise, preflight_result, **detail,
        )}

    # An adoption never launches beside an earlier cloud builder of the issue that is still live,
    # nor when the recorded session listing cannot say; local and cloud launches alike.
    refusal = _original_session_refusal(
        repo_root, ctx["issue"], stamped_premise, cloud_sessions_file, env,
    )
    if refusal is not None:
        reason, detail = refusal
        return {"refusal": _refuse_unreserved(
            ctx, reason, "original-session", stamped_premise, preflight_result, **detail,
        )}

    compose_cloud = (
        {
            "place": PLACE_CLOUD,
            "cloud_environment": cloud_environment,
            "session_name": cloud_session_name,
        }
        if cloud else {}
    )
    compose_result = compose_launch(
        repo_root, ctx["issue"], stamped_premise, model=model, doctrine_loader=doctrine_loader,
        effort=effort, **compose_cloud,
    )
    if not compose_result["ok"]:
        stage = "compose" if compose_result["reason"] != "model-not-registry-known" else "model"
        if compose_result["reason"] == "model-default-unavailable":
            stage = "model"
        if compose_result["reason"] == "effort-not-registry-known":
            stage = "model"
        return {"refusal": _refuse_unreserved(
            ctx, compose_result["reason"], stage, premise_result["premise"], preflight_result,
            compose_result,
        )}

    stamped = stamped_premise
    # The named sizes are looked up before anything is created, so an unknown or unreadable size
    # refuses with no worktree, no phone and no child.
    iphone_types = []
    iphone_spent = 0.0
    if stamped.get("iphoneCheck") is True and isinstance(stamped.get("iphoneModels"), list):
        step_started = time.monotonic()
        resolved_models = _resolve_iphone_models(
            stamped["iphoneModels"], run, _IPHONE_CEILING_SECONDS
        )
        iphone_spent = time.monotonic() - step_started
        if not resolved_models["ok"]:
            extra = {}
            if resolved_models.get("unknownModels"):
                extra["unknownModels"] = resolved_models["unknownModels"]
            return {"refusal": _refuse_unreserved(
                ctx, resolved_models["reason"], "iphone-models", stamped, preflight_result,
                compose_result, **extra,
            )}
        iphone_types = resolved_models["types"]

    if cloud:
        # The cloud command takes no revision and the platform starts the session from the
        # launching checkout's commit, so the remote must have the base and the checkout must be
        # on it. The launcher pushes nothing and never changes the checkout to make it so.
        refusal = _cloud_start_refusal(repo_root, stamped, env)
        if refusal is not None:
            refusal_reason, refusal_extra = refusal
            return {"refusal": _refuse_unreserved(
                ctx, refusal_reason, "cloud-base", stamped, preflight_result, compose_result,
                **refusal_extra,
            )}

    if not cloud and not worktree_path:
        return {"refusal": _refuse_unreserved(
            ctx, "launch-worktree-path-unresolvable", "worktree", stamped, preflight_result,
            compose_result,
        )}

    return {
        "refusal": None,
        "preflight": preflight_result,
        "premise": stamped_premise,
        "compose": compose_result,
        "stackGate": stack_gate,
        "dependencyGate": dependency_gate,
        "iphoneTypes": iphone_types,
        "iphoneSpent": iphone_spent,
    }


def _reserved_record(
    repo_root,
    launch_id,
    issue,
    stamped,
    preflight_result,
    compose_result,
    *,
    cloud,
    cloud_environment,
    plugin_ver,
    worktree_path,
    env,
    seat_instance,
    foreign_override,
    slot,
    generation,
    boundary,
):
    """Build the `reserved` ledger record for a launch, and the config dir its child runs under.

    Returns `(reserved, config_dir)`; the caller keeps `config_dir` for the cloud child's
    environment.
    """
    argv = compose_result["argv"]
    doctrine = compose_result["doctrine"]
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
    }
    if cloud:
        reserved["place"] = PLACE_CLOUD
        reserved["cloudEnvironment"] = cloud_environment
        reserved["pluginVersion"] = plugin_ver
        # The launching account's id, so a later reader decides "the advisor's account" by id,
        # not by config-dir path. Omitted when the account cannot be read.
        account_id = cloud_setup.launching_account(env, cwd=repo_root)
        if isinstance(account_id, str) and account_id:
            reserved["accountId"] = account_id
    else:
        reserved["worktree"] = worktree_path
        reserved["sessionId"] = compose_result["sessionId"]
    config_dir = spawn_config_dir(env=env, cwd=repo_root if cloud else worktree_path)
    if config_dir is not None:
        reserved["configDir"] = config_dir
    if seat_instance is not None:
        reserved["seatInstance"] = seat_instance
    if foreign_override:
        reserved["foreignInstanceAllowed"] = True
    if slot is not None:
        reserved["slot"] = slot
    if generation is not None:
        reserved["generation"] = generation
    if boundary is not None:
        reserved["boundary"] = boundary
    return reserved, config_dir


def _attach_gates(result, stack_gate, dependency_gate):
    """Record the stack and dependency gate results on a successful launch `result`."""
    if stack_gate is not None:
        result["stackGate"] = stack_gate
    if dependency_gate is not None:
        result["dependencyGate"] = dependency_gate
    return result


def _premise_batch_id(premise):
    """The premise's batch id: a non-empty string, else None."""
    batch_id = premise.get("batchId") if isinstance(premise, dict) else None
    if not isinstance(batch_id, str) or not batch_id.strip():
        batch_id = None
    return batch_id


def _launch_timing(
    settle_seconds, max_attempts, backoff_seconds, total_deadline_seconds,
    device_hub_poll_seconds,
):
    """Resolve the launch's timing knobs to their defaults.

    Returns `(settle_seconds, max_attempts, backoff_seconds, total_deadline_seconds,
    device_hub_poll_seconds)`.
    """
    settle_seconds = _SETTLE_SECONDS if settle_seconds is None else settle_seconds
    max_attempts = _MAX_ATTEMPTS if max_attempts is None else max_attempts
    backoff_seconds = _BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds
    total_deadline_seconds = (
        _TOTAL_DEADLINE_SECONDS if total_deadline_seconds is None else total_deadline_seconds
    )
    poll_seconds = (
        _DEVICE_HUB_POLL_SECONDS if device_hub_poll_seconds is None else device_hub_poll_seconds
    )
    return settle_seconds, max_attempts, backoff_seconds, total_deadline_seconds, poll_seconds


def _cloud_child_env(env, config_dir, effort):
    """The environment a cloud launch command runs under."""
    # The launch command carries none of the launch-id, slot, iPhone or heartbeat variables:
    # the session it makes runs elsewhere and has no use for this machine's lane plumbing.
    cloud_env = ll.scrub_env(env)
    for name in (
        hb.LAUNCH_ID_ENV, hb.HEARTBEAT_ROOT_ENV, SLOT_REF_ENV, IPHONE_ID_ENV, IPHONE_IDS_ENV,
        DEVICE_HUB_ENV,
    ):
        cloud_env.pop(name, None)
    if config_dir is not None:
        cloud_env[CONFIG_DIR_ENV] = config_dir
    # The same rule as the local spawn: the variable outranks the `--effort` flag, so a
    # resolved effort overwrites the ambient value and drops the stale reflection; a None
    # effort touches neither.
    pin_effort(cloud_env, effort)
    return cloud_env


def _holds_launch_ownership(func):
    """Run `func` (a launch) holding its per-launch ownership lock from before it reserves.

    The lock (`ll.acquire_launch_ownership`) is taken before any `reserved` record is written and
    released only when the launch returns, on every path (success, refusal, exception), so a live
    holder is positive evidence the launch is still running: the never-started repair refuses on
    it. The decorator mints the launch id and hands it to `func` as `_launch_id`.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        launch_id = "launch-%s" % secrets.token_hex(8)
        # repo_root and env are the first and seventh parameters of `launch_build`.
        repo_root = args[0] if args else kwargs.get("repo_root")
        env = args[6] if len(args) > 6 else kwargs.get("env")
        ownership = ll.acquire_launch_ownership(repo_root, launch_id, env=env)
        if not ownership["ok"]:
            return _fail("launch-ownership-unavailable:%s" % ownership["reason"],
                         launchId=launch_id)
        try:
            return func(*args, _launch_id=launch_id, **kwargs)
        finally:
            ll.release_launch_ownership(ownership["path"])
    return wrapper


@_holds_launch_ownership
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
    allow_foreign_instance=False,
    membership_reader=None,
    pr_lookup=None,
    pr_vet_reader=None,
    iphone_run=None,
    device_hub_poll_seconds=None,
    place=None,
    cloud_environment=None,
    cloud_spawn_fn=None,
    cloud_spawn_timeout=None,
    cloud_sessions_file=None,
    _launch_id=None,
):
    """Full launch flow: preflight, premise, compose, reserve, spawn, settle/retry.

    With ``place="cloud"`` the builder is started in a cloud session instead: the platform command
    runs once, the session's identity is read from its output, the lane is recorded and the call
    returns. No worktree is made, no local child is left, and nothing is pushed.

    Every premise the launch rests on is checked by `_check_premises` before anything is made.
    `cloud_sessions_file` is the recorded host session listing an adoption launch is checked against.
    """
    settle_seconds, max_attempts, backoff_seconds, total_deadline_seconds, poll_seconds = (
        _launch_timing(
            settle_seconds, max_attempts, backoff_seconds, total_deadline_seconds,
            device_hub_poll_seconds,
        )
    )

    run = iphone_run or _default_iphone_run

    launch_id = _launch_id or "launch-%s" % secrets.token_hex(8)
    deadline = time.monotonic() + total_deadline_seconds

    batch_id = _premise_batch_id(premise)

    # Pre-reservation refusals: nothing is written to the ledger for any of these.
    place_refusal = _place_refusal(
        launch_id, place, slot, generation, boundary, premise, cloud_environment, issue,
    )
    if place_refusal is not None:
        return place_refusal
    cloud = place == PLACE_CLOUD
    plugin_ver = plugin_version() if cloud else None
    cloud_session_name = ll.cloud_session_name(issue, launch_id) if cloud else None
    # A cloud launch makes no worktree: the config root resolves against the launching checkout.
    worktree_path = None if cloud else build_worktree_path(repo_root, issue, launch_id, env=env)
    requested = spawn_config_dir(env=env, cwd=repo_root if cloud else worktree_path)
    gate_place = PLACE_CLOUD if cloud else None
    place_fields = (
        {"place": PLACE_CLOUD, "cloud_environment": cloud_environment, "plugin_version": plugin_ver}
        if cloud else {}
    )
    foreign_override = False
    if _claude_seat_pin_gate_applies(env=env):
        seat = seat_config_dir(env=env)
        if seat["instance"] is None:
            if not allow_foreign_instance:
                return _fail(  # pre-reservation: instance pin gate before any reservation
                    "launch-seat-instance-undetermined",
                    seatInstance=None,
                    seatReason=seat["reason"],
                    requestedInstance=requested,
                    launchId=launch_id,
                    remedy=_INSTANCE_PIN_REMEDY,
                )
            foreign_override = True
        elif requested is not None:
            seat_norm = os.path.normpath(os.path.expanduser(seat["instance"]))
            requested_norm = os.path.normpath(os.path.expanduser(requested))
            if seat_norm != requested_norm:
                if not allow_foreign_instance:
                    return _fail(  # pre-reservation: instance pin gate before any reservation
                        "launch-foreign-instance-pin",
                        seatInstance=seat["instance"],
                        requestedInstance=requested,
                        launchId=launch_id,
                        remedy=_INSTANCE_PIN_REMEDY,
                    )
                foreign_override = True
    else:
        seat = {"instance": None, "reason": "seat-pid-absent"}

    ctx = {
        "repo_root": repo_root,
        "launch_id": launch_id,
        "issue": issue,
        "env": env,
        "slot": slot,
        "generation": generation,
        "boundary": boundary,
        "seat_instance": seat["instance"],
        "foreign_override": foreign_override,
        "place_fields": place_fields,
    }

    checked = _check_premises(
        ctx, premise, checks_input,
        model=model, effort=effort, doctrine_loader=doctrine_loader, batch_id=batch_id,
        gate_place=gate_place, cloud=cloud, cloud_environment=cloud_environment,
        cloud_session_name=cloud_session_name, worktree_path=worktree_path,
        deadline=deadline, pr_vet_reader=pr_vet_reader, pr_lookup=pr_lookup,
        membership_reader=membership_reader, run=run, cloud_sessions_file=cloud_sessions_file,
    )
    if checked["refusal"] is not None:
        return checked["refusal"]
    preflight_result = checked["preflight"]
    stamped = checked["premise"]
    compose_result = checked["compose"]
    stack_gate = checked["stackGate"]
    dependency_gate = checked["dependencyGate"]
    iphone_check = stamped.get("iphoneCheck") is True
    iphone_info = {"id": None, "deviceHub": None} if iphone_check else None
    models_named = iphone_check and isinstance(stamped.get("iphoneModels"), list)
    if models_named:
        iphone_info["ids"] = []
    # The size lookup ran inside the premise checks; its time counts against the iPhone ceiling
    # and extends the deadline, as every iPhone step does.
    iphone_spent = checked["iphoneSpent"]
    deadline += iphone_spent
    iphone_types = checked["iphoneTypes"]
    doctrine = compose_result["doctrine"]
    argv = compose_result["argv"]

    # A cloud lane has no worktree to make.
    worktree_result = (
        {"ok": True, "reason": None, "path": None}
        if cloud
        else create_build_worktree(repo_root, worktree_path, stamped["baseCommit"], env=env)
    )
    if not worktree_result["ok"]:
        extra = {"path": worktree_result["path"]}
        if "remedy" in worktree_result:
            extra["remedy"] = worktree_result["remedy"]
        return _refuse_unreserved(
            ctx, worktree_result["reason"], "worktree", stamped, preflight_result,
            compose_result, **extra,
        )

    reserved, config_dir = _reserved_record(
        repo_root, launch_id, issue, stamped, preflight_result, compose_result,
        cloud=cloud, cloud_environment=cloud_environment, plugin_ver=plugin_ver,
        worktree_path=worktree_path, env=env, seat_instance=seat["instance"],
        foreign_override=foreign_override, slot=slot, generation=generation,
        boundary=boundary,
    )
    # The phone is made here, outside the ledger lock: a slow simulator creation must never hold
    # other launches' reservations. Its id rides on the reserved record.
    made_iphone_ids = []
    if iphone_check:
        step_started = time.monotonic()
        if models_named:
            # One phone per named size, in premise order. A create that fails is skipped; the
            # others still go.
            for number, (_model, device_type) in enumerate(iphone_types, 1):
                made = _create_iphone(
                    launch_id,
                    run,
                    _IPHONE_CEILING_SECONDS - iphone_spent - (time.monotonic() - step_started),
                    device_type=device_type,
                    name="superheroes-%s-%d" % (launch_id, number),
                ).get("iphoneId")
                if made:
                    made_iphone_ids.append(made)
        else:
            made = _create_iphone(
                launch_id, run, _IPHONE_CEILING_SECONDS - iphone_spent
            ).get("iphoneId")
            if made:
                made_iphone_ids.append(made)
        took = time.monotonic() - step_started
        iphone_spent += took
        deadline += took
    made_iphone_id = made_iphone_ids[0] if made_iphone_ids else None
    if made_iphone_id:
        reserved["iphoneId"] = made_iphone_id
        if models_named:
            reserved["iphoneIds"] = list(made_iphone_ids)
    reserve_result = ll.reserve(repo_root, reserved, env=env)
    if not reserve_result["ok"]:
        extra = {}
        read_back = None
        if reserve_result.get("reason") == "ledger-append-failed":
            # The append reported failure: the read-back says whether the line landed. An
            # undecided or missing read-back (fail closed) is settled by one terminal write.
            read_back = reserve_result.get("appendReadBack")
            if read_back != "not-landed":
                read_back = _settle_uncertain_reservation(
                    repo_root, launch_id, "ledger-append-failed", "reserve", env,
                )
            extra["appendReadBack"] = read_back
        if made_iphone_id:
            if read_back == "uncertain":
                # The settle could not read or write the ledger, so a record may name these
                # phones: they are reported, never removed.
                phone_outcomes = [{"id": udid, "recorded": "uncertain"} for udid in made_iphone_ids]
            elif read_back == "terminal":
                # The landed record is now terminal and names these phones: the reap owns them.
                phone_outcomes = [{"id": udid, "recorded": True} for udid in made_iphone_ids]
            else:
                # No record names these phones (the refusal returned before the append, or the
                # line did not land): they are this launch's own and nothing else can reap them.
                phone_outcomes = [
                    {"id": udid, "recorded": False, "deleted": _delete_own_iphone(udid, run)}
                    for udid in made_iphone_ids
                ]
            extra["iphone"] = phone_outcomes[0]
            if models_named:
                extra["iphones"] = phone_outcomes
        if not cloud:
            if read_back == "uncertain":
                # A live reservation may name this worktree: keep it until the lane is readable.
                extra["keptWorktree"] = worktree_path
                extra["remedy"] = (
                    "First make the ledger read cleanly again: `repair-lane` refuses an unreadable "
                    "ledger. Then, after confirming no builder runs for this launch, end the lane "
                    "with `launcher.py repair-lane --repo-root %s --launch-id %s "
                    "--evidence \"<what failed and what was checked>\" "
                    "--no-builder \"<what was checked to show no builder exists>\"`. "
                    "Only once the lane reads terminal (or absent) can the worktree at %s be removed."
                    % (repo_root, launch_id, worktree_path)
                )
            else:
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
    if iphone_info is not None:
        iphone_info["id"] = made_iphone_id
        if models_named:
            iphone_info["ids"] = list(made_iphone_ids)

    def _post_reserve_fail(reason, **extra):
        """Every return past the reservation carries the overlap disclosure.

        The reservation is where the overlap becomes a fact, so a caller reading a
        LATER failure still needs it — a lane that spawned and then died over an
        accepted overlap is exactly when the advisor wants to know. Routing the
        post-reserve failures through one helper is what keeps a future failure path
        from silently omitting it.
        """
        if iphone_info is not None:
            extra["iphone"] = dict(iphone_info)
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
        place=gate_place,
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

    if cloud:
        cloud_env = _cloud_child_env(env, config_dir, compose_result["effort"])
        success_base = {
            "ok": True,
            "reason": None,
            "launchId": launch_id,
            "place": PLACE_CLOUD,
            "model": compose_result["model"],
            "modelResolution": compose_result["modelResolution"],
            "effort": compose_result["effort"],
            "effortSource": compose_result["effortSource"],
            "warnings": warnings,
        }
        # axis: reservation may have waited on the ledger lock, so the base is re-checked
        # right before the command; a base the remote lost terminalizes the unstarted lane.
        drift = _cloud_start_refusal(repo_root, stamped, env)
        if drift is not None:
            drift_reason, drift_extra = drift
            term = _terminalize(
                repo_root, launch_id, False, drift_reason, stage="cloud-base", env=env,
            )
            return _post_reserve_fail(_terminalization_reason(term, drift_reason), **drift_extra)
        cloud_result = _run_cloud_spawn(
            repo_root,
            launch_id,
            argv,
            cloud_session_name,
            log_path,
            err_path,
            cloud_env,
            _CLOUD_SPAWN_TIMEOUT_SECONDS if cloud_spawn_timeout is None else cloud_spawn_timeout,
            cloud_spawn_fn,
            overlap_evidence,
            env,
            _post_reserve_fail,
            success_base,
        )
        if cloud_result.get("ok"):
            _attach_gates(cloud_result, stack_gate, dependency_gate)
        return cloud_result

    # A phone or Device Hub that is not there never fails the launch: the builder is told what
    # is true and the lane spawns regardless.
    if iphone_check:
        step_started = time.monotonic()
        iphone_info["deviceHub"] = _ensure_device_hub(
            run, poll_seconds, _IPHONE_CEILING_SECONDS - iphone_spent
        )
        took = time.monotonic() - step_started
        iphone_spent += took
        deadline += took
        iphone_env = {
            IPHONE_ID_ENV: iphone_info["id"] or IPHONE_NONE,
            DEVICE_HUB_ENV: iphone_info["deviceHub"],
        }
        if models_named and made_iphone_ids:
            iphone_env[IPHONE_IDS_ENV] = ",".join(made_iphone_ids)
    else:
        iphone_env = None

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
            iphone_env=iphone_env,
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
            success = {
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
            _attach_gates(success, stack_gate, dependency_gate)
            if iphone_check:
                success["iphone"] = dict(iphone_info)
            return success

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
    seat_instance=None, foreign_instance_allowed=False,
    place=None, cloud_environment=None, plugin_version=None,
):
    """Best-effort reserve so refusal is accounted. Returns {reserved: bool}.

    A refused cloud launch is still a cloud lane, so its record carries the place fields.
    """
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
    if seat_instance is not None:
        reserved["seatInstance"] = seat_instance
    if foreign_instance_allowed:
        reserved["foreignInstanceAllowed"] = True
    # axis: a refused cloud launch is a cloud lane — the refusal's record carries the place fields.
    if place == PLACE_CLOUD:
        reserved["place"] = PLACE_CLOUD
        reserved["cloudEnvironment"] = cloud_environment
        reserved["pluginVersion"] = plugin_version
        account_id = cloud_setup.launching_account(env, cwd=repo_root)
        if isinstance(account_id, str) and account_id:
            reserved["accountId"] = account_id
    result = ll.reserve(repo_root, reserved, env=env)
    if result.get("reason") == "ledger-append-failed" and result.get("appendReadBack") == "landed":
        # The line is in the ledger and this path never spawns: the caller ends it with the
        # refusal's own reason and stage, so the diagnostic is not replaced by the append failure.
        return {"reserved": True, "warnings": []}
    if result.get("reason") == "ledger-append-failed" and result.get("appendReadBack") != "not-landed":
        # Undecided or missing read-back (fail closed): one terminal write settles the record,
        # so the caller has nothing left to end.
        settled = _settle_uncertain_reservation(
            repo_root, launch_id, "ledger-append-failed", "reserve", env,
        )
        return {"reserved": False, "warnings": [], "appendReadBack": settled}
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


def canary(repo_root, launch_id, env=None):
    """Report builder engagement from the lane's own session transcript tool calls."""
    read = ll.read(repo_root, env=env)
    if read["state"] != "ok":
        return _fail("canary-ledger-unreadable:%s" % read["state"])
    folded = ll.fold(read["records"])
    if not folded["ok"]:
        return _fail("canary-ledger-fold-refused:%s" % folded["reason"])
    lane = folded["launches"].get(launch_id)
    if lane is None:
        return _fail("canary-lane-unknown")
    # axis: a cloud lane is not read as a lane with a missing transcript — it has no local transcript at all.
    if lane.get("place") == PLACE_CLOUD:
        return _fail("canary-cloud-lane")
    session_id = lane.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        return _fail("canary-session-id-absent")
    config_dir = lane.get("configDir")
    if not isinstance(config_dir, str) or not config_dir:
        return _fail("canary-config-dir-absent")
    rows, paths, size, truncated = engine_dispatch.read_session_transcript_rows(
        config_dir, session_id,
    )
    if len(paths) == 0:
        return _fail("canary-transcript-missing")
    if len(paths) > 1:
        return _fail("canary-transcript-ambiguous")
    tool_calls = engine_adapter.claude_transcript_tool_calls(rows)
    if tool_calls is None:
        return _fail("canary-transcript-unreadable")
    if truncated and tool_calls == 0:
        return _fail("canary-transcript-truncated")
    return {
        "ok": True,
        "reason": None,
        "launchId": launch_id,
        "sessionId": session_id,
        "configDir": config_dir,
        "transcriptPath": paths[0],
        "toolCalls": tool_calls,
        "truncated": truncated,
        "engaged": tool_calls > 0,
    }


def _issue_title(repo_root, issue):
    """The issue's title from `gh`, or None; never raises."""
    try:
        done = subprocess.run(
            ["gh", "api", "repos/{owner}/{repo}/issues/%s" % issue, "--jq", ".title"],
            cwd=repo_root, capture_output=True, text=True, timeout=15,
        )
        title = done.stdout.strip()
        if done.returncode == 0 and title:
            return title
    except Exception:
        pass
    return None


def _report_title(title_fn, repo_root, issue):
    try:
        title = title_fn(repo_root, issue)
    except Exception:
        return None
    return title if isinstance(title, str) and title else None


def launch_report_for_batch(repo_root, batch_id, *, title_fn=None, env=None):
    """The launch report for one batch, built from the ledger's started launches."""
    read = ll.read(repo_root, env=env, create=False)
    if read["state"] == "missing":
        return {"ok": True, "report": None, "lanes": 0}
    if read["state"] != "ok":
        return _fail("report-ledger-%s" % read["state"])
    folded = ll.fold(read["records"])
    if not folded["ok"]:
        return _fail("report-ledger-fold:%s" % folded["reason"])
    batch = [
        (launch_id, info) for launch_id, info in folded["launches"].items()
        if info.get("batchId") == batch_id
    ]
    first_index = {}
    last_started = {}
    for launch_id, info in batch:
        issue = info["issue"]
        first_index[issue] = min(first_index.get(issue, info["reservedIndex"]), info["reservedIndex"])
        # an unconfirmed cloud session may not exist, so it is neither reported nor a cloud build
        if info["started"] and not info.get("cloudSessionUnconfirmed") and (
            issue not in last_started or info["reservedIndex"] > last_started[issue][1]["reservedIndex"]
        ):
            last_started[issue] = (launch_id, info)
    reserved = {
        rec["launchId"]: rec for rec in read["records"]
        if isinstance(rec, dict) and rec.get("event") == "reserved"
    }
    lookup = title_fn or _issue_title
    calls = []
    for issue in sorted(last_started, key=lambda i: first_index[i]):
        launch_id, info = last_started[issue]
        calls.append((issue, launch_report.report_place_call(reserved.get(launch_id), info["place"])))
    # titles are looked up only for a report that will render, by the renderer's own predicate
    wanted = launch_report.yields_report([call for _issue, call in calls])
    lanes = [
        {"issue": issue, "title": _report_title(lookup, repo_root, issue) if wanted else None,
         "placeCall": call}
        for issue, call in calls
    ]
    return {
        "ok": True,
        "report": launch_report.render_report(lanes),
        "lanes": len(lanes),
    }


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
        place=getattr(args, "place", None),
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
    cloud_kwargs = {}
    if getattr(args, "place", None) == PLACE_CLOUD:
        cloud_kwargs = {
            "place": PLACE_CLOUD,
            "cloud_environment": getattr(args, "cloud_environment", None),
            "session_name": "issue-%s-preview" % args.issue,
        }
    return compose_launch(
        args.repo_root, args.issue, premise_result["premise"], model=args.model,
        effort=args.effort, **cloud_kwargs,
    )


# The results of a cloud attempt that mean the launcher ended it before any session could exist:
# the command never ran and the lane was terminalized first, so a terminalization failure
# (a ``terminalization-failed:`` reason) is never one of them. Each maps to the placing reason the
# local fallback records. A remote that could not be asked is the platform being out of reach;
# a base the remote lacks is something only the owner's machine has. No other result is one.
# The four ``launch-cloud-checkout-*`` refusals also mean no session exists, but they are
# deliberately left out: they are a stop for the owner (the checkout is theirs to put on the base),
# not a reason to build elsewhere.
_CLOUD_NEVER_STARTED_REASONS = {
    "spawn-oserror": ("unreachable", None),
    "log-open-failed": ("unreachable", None),
    "launch-cloud-base-remote-unchecked": ("unreachable", None),
    "launch-cloud-base-not-on-remote": ("needs", "its base commit"),
}


def _premise_with_resolved_base(repo_root, premise):
    """A copy of ``premise`` whose ``baseCommit`` is the one commit it names now, or ``premise``
    itself when it names no commit that resolves (``validate_premise`` then refuses it)."""
    base = premise.get("baseCommit") if isinstance(premise, dict) else None
    if not isinstance(base, str) or not base.strip():
        return premise
    proc = _git_scrubbed(repo_root, "rev-parse", "--verify", "%s^{commit}" % base.strip())
    resolved = (proc.stdout or "").strip() if proc is not None and proc.returncode == 0 else ""
    if not _HEX40.match(resolved):
        return premise
    return dict(premise, baseCommit=resolved)


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

    # axis: the placeCall is the launcher's own word on where the build runs — a premise file that brings one is refused — see bite-proof record wo_b_place_call
    if isinstance(premise, dict) and "placeCall" in premise:
        return _fail("premise-place-call-caller-set")
    # axis: the cloud environment comes from the setup record the routing step read — see bite-proof record wo_b_place_call
    if getattr(args, "cloud_environment", None) is not None:
        return _fail("launch-cloud-environment-routed")

    # axis: a premise's base names one commit for the cloud attempt and the local fallback alike, so a ref that moves between the two never changes what the fallback builds — see bite-proof record wo_d_place_call
    premise = _premise_with_resolved_base(args.repo_root, premise)

    # axis: every launch is routed once, before it starts — see bite-proof record wo_b_place_call
    place_call = launch_place.route(
        args.repo_root, premise if isinstance(premise, dict) else {}, getattr(args, "place", None),
    )

    def launch(stamped_call, **where):
        stamped = dict(premise, placeCall=stamped_call) if isinstance(premise, dict) else premise
        return launch_build(
            args.repo_root,
            args.issue,
            stamped,
            checks,
            args.log_dir,
            model=args.model,
            effort=args.effort,
            allow_foreign_instance=args.allow_foreign_instance,
            cloud_sessions_file=getattr(args, "cloud_sessions_file", None),
            **where,
        )

    def launch_local(stamped_call):
        # The slot, generation and boundary are the fallback resources: only a local launch uses them.
        return launch(
            stamped_call, slot=args.slot, generation=args.generation, boundary=boundary,
        )

    if place_call["place"] != PLACE_CLOUD:
        result = launch_local(place_call)
        result["placeCall"] = place_call
        return result

    # axis: a cloud launch gets no slot, generation or boundary — the cloud has none to give — see bite-proof record wo_b_place_call
    result = launch(
        place_call, place=PLACE_CLOUD, cloud_environment=place_call["environment"],
    )
    # axis: fall back only on the results that mean no session could exist; any other result may have a live lane, and a second builder must never start — see bite-proof record wo_b_place_call
    # The four launch-cloud-checkout-* refusals also mean no session exists, but they are left out of the map on purpose: they stop for the owner, whose checkout it is, and never build elsewhere.
    if not result.get("ok") and result.get("reason") in _CLOUD_NEVER_STARTED_REASONS:
        # axis: a cloud attempt the launcher ended is the platform being unreachable, or the build needing a commit only this machine has — see bite-proof record wo_b_place_call
        fallback_reason, fallback_need = _CLOUD_NEVER_STARTED_REASONS[result["reason"]]
        fallback_call = dict(
            place_call, place=PLACE_LOCAL, reason=fallback_reason, need=fallback_need,
            environment=None,
        )
        local = launch_local(fallback_call)
        local["placeCall"] = fallback_call
        local["cloudAttempt"] = result
        local["fellBack"] = True
        return local
    result["placeCall"] = place_call
    if args.slot is not None or args.generation is not None or boundary is not None:
        result["fallbackResourcesUnused"] = {"slot": args.slot, "generation": args.generation}
    return result


def _cli_record_outcome(args):
    return record_outcome(
        args.repo_root, args.launch_id, args.outcome, args.evidence,
        await_exit=args.await_exit,
    )


def _cli_repair_lane(args):
    pending = None
    if args.pending_file is not None:
        try:
            with open(args.pending_file, encoding="utf-8") as fh:
                pending = json.load(fh)
        except (OSError, ValueError):
            return _fail("pending-file-unreadable")
        if pending is None:
            # A file holding JSON `null` decodes to the same None as an omitted file; an
            # explicit file that carries no record must refuse, not fall to terminalization.
            return _fail(ll.REPAIR_PENDING_STARTED_INVALID)
    return ll.repair_never_started(
        args.repo_root, args.launch_id, pending_started=pending, evidence=args.evidence,
        no_builder_evidence=args.no_builder,
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


def _cli_canary(args):
    return canary(args.repo_root, args.launch_id)


def _cli_report(args):
    return launch_report_for_batch(args.repo_root, args.batch)


def _cli_still(args):
    got = launch_report.still_check(args.repo_root)
    if got["refused"] is not None:
        return _fail(got["refused"])
    return {"ok": True, "line": got["line"]}


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
    pf.add_argument("--place", choices=[PLACE_LOCAL, PLACE_CLOUD], default=None)
    pf.set_defaults(func=_cli_preflight)

    comp = sub.add_parser("compose")
    comp.add_argument("--repo-root", required=True)
    comp.add_argument("--issue", type=int, required=True)
    comp.add_argument("--premise", required=True)
    comp.add_argument("--model", default=None)
    comp.add_argument("--effort", default=None)
    comp.add_argument("--place", choices=[PLACE_LOCAL, PLACE_CLOUD], default=None)
    comp.add_argument("--cloud-environment", default=None)
    comp.set_defaults(func=_cli_compose)

    la = sub.add_parser("launch")
    la.add_argument("--repo-root", required=True)
    la.add_argument("--issue", type=int, required=True)
    la.add_argument(
        "--premise", required=True,
        help=("the build premise as JSON; its `needs` list names everything only the owner's "
              "machine has (a locally seeded browser context, a slot, a local-only file), and a "
              "build with no `needs` is free to be placed in the cloud"),
    )
    la.add_argument("--checks", required=True)
    la.add_argument("--log-dir", required=True)
    la.add_argument("--model", default=None)
    la.add_argument("--effort", default=None)
    la.add_argument("--slot", default=None)
    la.add_argument("--generation", type=int, default=None)
    la.add_argument("--boundary", default=None)
    la.add_argument(
        "--place", choices=[PLACE_LOCAL, PLACE_CLOUD], default=None,
        help="the owner's launch word; the launcher decides where each build runs",
    )
    la.add_argument(
        "--cloud-environment", default=None,
        help="refused on launch: the environment comes from the cloud setup record",
    )
    la.add_argument(
        "--cloud-sessions-file", default=None,
        help=("the builders' account's cloud session listing (a list_sessions or get_session "
              "result, or a JSON array of them), read at launch time; an adoption launch needs "
              "it when an earlier cloud lane for the issue started a session"),
    )
    la.add_argument(
        "--allow-foreign-instance",
        action="store_true",
        help="allow launching when CLAUDE_CONFIG_DIR is not this seat's own instance",
    )
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

    rl = sub.add_parser("repair-lane")
    rl.add_argument("--repo-root", required=True)
    rl.add_argument("--launch-id", required=True)
    rl.add_argument(
        "--pending-file", default=None,
        help="a file holding the `pendingStarted` record of a lane whose `started` was not written; "
             "without it the lane's terminal event is recorded from --evidence",
    )
    rl.add_argument("--evidence", default=None)
    rl.add_argument(
        "--no-builder", default=None,
        help="one line naming what was checked to show no builder exists (the cloud session "
             "listing, or the worktree); required to record the lane's terminal event",
    )
    rl.set_defaults(func=_cli_repair_lane)

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

    rp = sub.add_parser("report")
    rp.add_argument("--repo-root", required=True)
    rp.add_argument("--batch", required=True)
    rp.set_defaults(func=_cli_report)

    st = sub.add_parser("still")
    st.add_argument("--repo-root", required=True)
    st.set_defaults(func=_cli_still)

    db = sub.add_parser("declare-batch")
    db.add_argument("--repo-root", required=True)
    db.add_argument("--batch", required=True)
    db.add_argument("--expected", type=int, required=True)
    db.set_defaults(func=_cli_declare_batch)

    cn = sub.add_parser("canary")
    cn.add_argument("--repo-root", required=True)
    cn.add_argument("--launch-id", required=True)
    cn.set_defaults(func=_cli_canary)

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
