#!/usr/bin/env python3
"""The native implementer engine's run wrapper (#1947).

A cloud session on Linux whose calibration turns on ``localSockets`` cannot run the plugin's
sandboxed claude write dispatch: the Linux sandbox cannot serve a socket grant. In that one case the
implementer runs as a native subagent (``superheroes:implementer``) in its own isolated worktree,
bounded by the platform's auto mode and the plugin's install and network fence.

Five verbs, one JSON object on stdout each:

  route   --cwd W                       the one chokepoint: native, or the calibrated engine
  open    --run-dir D --order-path P --cwd W --base-sha S --deadline-seconds N
          [--expect-item X]... [--items-base-sha S] --seat JSON
                                        journal ``run-opened``, write ``agent-prompt.md`` and print
                                        the ``agent`` to dispatch, ``launchPrompt`` included
  enroll  --run-dir D                   run by the subagent, in its own worktree, as its first
                                        Bash command; checks the worktree, links the builder's
                                        installed dependency folders into it, writes nothing to the
                                        journal (the hook records the ``native-enrolled`` binding)
  wait    --run-dir D --max-wait S      poll for ``result.json`` or the deadline
  close   --run-dir D --worktree T --transcript F --into B [--forfeit deadline]
                                        grade the run and collect the subagent's change into B,
                                        enroll's untracked dependency links left out

Exit 0 on ``ok: true`` and on a non-forfeit terminal (``needs_context``, ``blocked``); exit 1 on a
refusal or a forfeit. Grading rests on git and on the harness's transcript and journal records.
"""
import argparse
import calendar
import contextlib
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import bite_proof_format  # noqa: E402  the record format an order that asks for one carries (#2082)
import cloud_pass  # noqa: E402  _is_cloud
import command_refusals  # noqa: E402  ORDER_TEXT — the one home of the refused-command stop rule (#2011)
import core_md  # noqa: E402  read_sandbox_access
import dispatch_outcome  # noqa: E402  REASON_FORFEITED
import engine_adapter  # noqa: E402  scrub_refusals — the band scrub seam for refusal text
import engine_dispatch  # noqa: E402  journal, git, host platform, declared-item check
import file_lock  # noqa: E402  the run-dir lock
import launch_ledger  # noqa: E402  scrub_env
import model_registry  # noqa: E402  CLAUDE_ALIAS_RESOLUTION
import preflight_probe  # noqa: E402  dispatch_calibration
import seat_bundle  # noqa: E402  the callable `dispatch_guard.py check --seat` runs
import store_core  # noqa: E402  repo root and git dirs

NATIVE_WHY = (
    "a cloud session on Linux whose calibration turns on localSockets, "
    "which the Linux sandbox cannot serve"
)
NATIVE_BOUNDS = (
    "no plugin sandbox: the implementer runs as a native subagent in its own isolated worktree, "
    "bounded by the platform's auto mode and the plugin's install and network fence "
    "(a command-prefix fence, not a sandbox), because " + NATIVE_WHY
)
NATIVE_EFFORT_NOTE = "the Agent tool takes no effort; the subagent runs at its default effort"
ROUTE_REASON_NATIVE = "cloud-local-sockets"
ROUTE_REASON_CALIBRATED = "calibrated"
REASON_DEPENDENCY_LINK_FAILED = "dependency-link-failed"
REASON_DEPENDENCY_LINK_UNSAFE = "dependency-link-unsafe"
DEPENDENCY_DIRS = ("node_modules",)

NATIVE_PREAMBLE = """\
You are a native implementer subagent for one scoped work order, running in your own isolated \
git worktree. Follow these rules before and while you carry out the order below.

1. Your first Bash command must be exactly:

   {ENROLL_COMMAND}

   If that command fails, or is denied, stop at once and report the failure. Do not continue and \
do not try another route into the worktree.
2. Work only in your own worktree. Do not commit. Leave your change in the working tree.
3. Install nothing and reach no network: no package installs, no curl or wget, no git push, \
fetch, pull or clone, no gh.
4. """ + command_refusals.FILE_WRITE_RULE + """
5. """ + command_refusals.ORDER_TEXT + """
6. When you finish, write your typed result to {RESULT_PATH} as one JSON object:
   {"status": "done" | "needs_context" | "blocked", "summary": "<text>", "refusals": [ ... ]}
   Include refusals, in the entry shape the rule above names, whenever you met a refused or \
denied command; an empty list or no refusals key means you met none. If your enroll command is \
refused or denied, still write this result with status "blocked" and that refusal before you stop.
   Use "done" only when the order is carried out; "needs_context" when you need information the \
order does not give; "blocked" when something outside your reach stops you.
7. Stop when the deadline given to the orchestrator passes; the fence refuses your commands after it.

The order follows, verbatim.

---

"""

LAUNCH_PROMPT = (
    "Read the file {PROMPT_PATH} in full with the Read tool before doing anything else, "
    "then follow it exactly: it is your whole work order."
)

GIT_TIMEOUT = 60
DEADLINE_MIN_SECONDS = 60
DEADLINE_MAX_SECONDS = 7200
WAIT_MAX_SECONDS = 540
_SHA40 = re.compile(r"[0-9a-f]{40}")
_TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_LOCK_NAME = ".native.lock"
_PROMPT_NAME = "agent-prompt.md"
_RESULT_NAME = "result.json"
_PATCH_NAME = "native-collect.patch"
_STATUSES = ("done", "needs_context", "blocked")
_SUBAGENT_TYPE = "superheroes:implementer"

# Injectable seams: tests advance the clock and never sleep for real.
_SLEEP = time.sleep


def _now():
    return time.time()


def _stamp(epoch):
    return time.strftime(_TIME_FORMAT, time.gmtime(epoch))


def _parse_stamp(text):
    try:
        return calendar.timegm(time.strptime(text, _TIME_FORMAT))
    except (TypeError, ValueError):
        return None


def _refusal(reason, **extra):
    out = {"ok": False, "terminal": True, "reason": reason}
    out.update(extra)
    return out


# --- git -----------------------------------------------------------------------------------


# Every git subprocess this module causes runs under `_neutral_git`: the owner's global and system
# git config never reaches it (#1949). The env pair does not reach the repository's own or the
# worktree's config, and `engine_dispatch._git_scrubbed` strips GIT_CONFIG_GLOBAL from its child, so
# `_git` builds its own child environment (the pair restored) and also pins each setting the engine's porcelain parsing depends on.
_NEUTRAL_ENV = (("GIT_CONFIG_GLOBAL", os.devnull), ("GIT_CONFIG_NOSYSTEM", "1"))
_NEUTRAL_CONFIG = (
    "diff.noprefix=false", "diff.context=3", "apply.whitespace=nowarn",
    "status.showUntrackedFiles=all", "diff.submodule=short", "status.submoduleSummary=false",
    "color.ui=false", "core.quotePath=false", "diff.external=", "diff.renames=false",
)


def _neutral_child_env():
    """A child environment scrubbed of the routing variables, the neutral pair put back after."""
    env = launch_ledger.scrub_env(
        keys=engine_dispatch._GIT_ROUTING_VARS, roots=(engine_dispatch.JOURNAL_ROOT_ENV,))
    env.update(_NEUTRAL_ENV)
    return env


@contextlib.contextmanager
def _neutral_git():
    """Run git, and the callees that spawn it, under neutral configuration.

    Hides the ambient routing variables, then points the global config at the null device and
    switches the system config off in ``os.environ`` for the duration. The previous values (or their
    absence) come back afterwards, on an exception too; the context nests. ``engine_dispatch.
    _git_scrubbed`` (which the declared-item check spawns git through) would drop the neutral pair
    from its child, so it is swapped for a runner that keeps it, and put back after."""
    saved = {key: os.environ.get(key) for key, _ in _NEUTRAL_ENV}
    saved_runner = engine_dispatch._git_scrubbed

    def neutral_scrubbed(cwd, *args, timeout=None):
        overrides = [part for setting in _NEUTRAL_CONFIG for part in ("-c", setting)]
        return subprocess.run(
            ["git", "-C", cwd, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=",
             *overrides, *args],
            capture_output=True, text=True, env=_neutral_child_env(), timeout=timeout)

    try:
        with engine_dispatch._git_routing_scrubbed_environ():
            os.environ.update(_NEUTRAL_ENV)  # after the scrub: GIT_CONFIG_GLOBAL is a routing var
            engine_dispatch._git_scrubbed = neutral_scrubbed
            yield
    finally:
        engine_dispatch._git_scrubbed = saved_runner
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _git(cwd, *args):
    """(returncode, stdout, stderr); returncode -1 when git cannot run or times out.

    The child environment is scrubbed of the routing variables first and the neutral pair is put
    back after: ``engine_dispatch._git_scrubbed`` would drop ``GIT_CONFIG_GLOBAL`` with them and
    leave git reading the owner's global config (a global ``core.excludesFile`` hides a new file
    from ``add -A``)."""
    overrides = [part for setting in _NEUTRAL_CONFIG for part in ("-c", setting)]
    try:
        with _neutral_git():
            env = _neutral_child_env()
            proc = subprocess.run(
                ["git", "-C", cwd, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=",
                 *overrides, *args],
                capture_output=True, text=True, env=env, timeout=GIT_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        return -1, "", ""
    return proc.returncode, proc.stdout or "", proc.stderr or ""


# --- route ---------------------------------------------------------------------------------


_CALIBRATION_ERROR = object()


def _calibrated_implementer(cwd):
    """The calibrated implementer engine, or None; a calibration read error is ``_CALIBRATION_ERROR``."""
    rows = preflight_probe.dispatch_calibration(cwd=cwd)
    rows = rows if isinstance(rows, list) else []
    if any(isinstance(row, dict) and row.get("readError") for row in rows):
        return _CALIBRATION_ERROR
    for row in rows:
        if isinstance(row, dict) and row.get("role") == "implementer" and row.get("engine"):
            return row["engine"]
    return None


def route(cwd):
    """native exactly when cloud, linux, a calibration that turns localSockets on and a claude
    implementer; any other calibrated engine keeps its own dispatch path."""
    with _neutral_git():  # both reads name cwd's repository
        calibrated = _calibrated_implementer(cwd)
        cloud_linux = (cloud_pass._is_cloud(os.environ)
                       and engine_dispatch._host_platform() == "linux")
        read = core_md.read_sandbox_access(cwd) if cloud_linux else None
    if cloud_linux:
        access = read.get("access")
        if not isinstance(access, dict):
            if read.get("reason") == core_md.SANDBOX_ACCESS_REASON_MALFORMED:
                return {"ok": False, "reason": "sandbox-access-malformed"}
            return {"ok": False, "reason": "sandbox-access-unreadable"}
        if calibrated is _CALIBRATION_ERROR:
            return {"ok": False, "reason": "calibration-unreadable"}
        if access.get("localSockets") is True and calibrated == "claude":
            return {"ok": True, "engine": "native", "reason": ROUTE_REASON_NATIVE,
                    "why": NATIVE_WHY}
    if calibrated and calibrated is not _CALIBRATION_ERROR:
        return {"ok": True, "engine": calibrated, "reason": ROUTE_REASON_CALIBRATED}
    return {"ok": False, "reason": "calibration-unreadable"}


def _cmd_route(args):
    return route(args.cwd)


# --- journal state -------------------------------------------------------------------------


def _state(run_dir_real):
    """The native run's journal facts: opened, enrolled, collecting, closed (each a record or None)."""
    records, interior_corrupt = engine_dispatch._journal_read_raw(run_dir_real)[:2]
    state = {"opened": None, "enrolled": None, "collecting": None, "closed": None,
             "corrupt": bool(interior_corrupt)}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        kind = rec.get("kind")
        if kind == "run-opened" and rec.get("engine") == "native":
            state["opened"] = state["opened"] or rec
        elif kind == "native-enrolled":
            state["enrolled"] = state["enrolled"] or rec
        elif kind == "native-collecting":
            state["collecting"] = state["collecting"] or rec
        elif kind == "run-closed":
            state["closed"] = state["closed"] or rec
    return state


def _deadline_epoch(opened):
    return _parse_stamp(opened.get("deadlineAt"))


# --- open ----------------------------------------------------------------------------------


def _item_invalid(item):
    if not isinstance(item, str) or not item or item.startswith("/") or os.path.isabs(item):
        return True
    return ".." in item.replace("\\", "/").split("/")


def _run_dir_not_empty(run_dir):
    if os.path.lexists(run_dir) and not os.path.isdir(run_dir):
        return True
    return os.path.isdir(run_dir) and bool(os.listdir(run_dir))


def _cmd_open(args):
    routed = route(args.cwd)
    if not (routed.get("ok") and routed.get("engine") == "native"):
        return _refusal("native-engine-not-routed", routeReason=routed.get("reason"))
    run_dir = os.path.abspath(args.run_dir)
    if _run_dir_not_empty(run_dir):
        return _refusal("run-dir-not-empty")
    if not _SHA40.fullmatch(args.base_sha or ""):
        return _refusal("base-sha-invalid")
    items_base_sha = args.items_base_sha
    if items_base_sha is not None:
        if not _SHA40.fullmatch(items_base_sha):
            return _refusal("items-base-sha-invalid")
        if _git(os.path.realpath(args.cwd), "merge-base", "--is-ancestor",
                items_base_sha, args.base_sha)[0] != 0:
            return _refusal("items-base-sha-not-ancestor")
    if not DEADLINE_MIN_SECONDS <= args.deadline_seconds <= DEADLINE_MAX_SECONDS:
        return _refusal("deadline-invalid")
    expected = args.expect_item or None
    if expected is not None:
        if any(_item_invalid(item) for item in expected):
            return _refusal("expect-item-invalid")
        normalized = []
        for item in expected:
            ok, detail = engine_dispatch._normalize_expected_item(item)
            if not ok:
                return _refusal("expect-item-invalid")
            normalized.append(detail)
        expected = normalized
    resolved = seat_bundle.resolve_entry(args.seat, verb="guard-check")
    if not resolved.get("ok"):
        return _refusal(resolved.get("entryReason"), detail=resolved.get("detail"))
    verdict = resolved["allowlistVerdict"]
    if resolved.get("vendor") != "claude" or resolved.get("role") != "implementer":
        return _refusal("native-seat-invalid")
    token = verdict.get("dispatch_token")
    served = model_registry.CLAUDE_ALIAS_RESOLUTION["resolved"].get(token)
    if not served:
        return _refusal("native-seat-invalid", detail="no served model for %r" % (token,))
    try:
        with open(args.order_path, "rb") as fh:
            order = fh.read()
    except OSError:
        return _refusal("order-unreadable")
    bite_proof_block, bite_proof_reason = bite_proof_format.block_for(
        order.decode("utf-8", errors="ignore"))
    # axis: an order naming a bite-proof reaches the subagent with the rubric's record format, or no run opens — see bite-proof record wo_2082_format
    if bite_proof_reason:
        return _refusal(bite_proof_reason)

    try:
        os.makedirs(run_dir, exist_ok=True)
    except OSError:
        return _refusal("run-dir-unwritable")
    run_dir = os.path.realpath(run_dir)
    lock = os.path.join(run_dir, _LOCK_NAME)
    try:
        file_lock.acquire_with_reason(lock)
    except file_lock.LockHeld:
        return _refusal("run-dir-locked")
    prompt_path = os.path.join(run_dir, _PROMPT_NAME)
    try:
        if engine_dispatch._journal_read_raw(run_dir)[2] != "absent":
            return _refusal("run-dir-journal-exists")
        pointer_path = os.path.join(run_dir, "journal-root.txt")
        try:  # survive the loss of a command-scoped journal-root override
            with open(pointer_path, "w", encoding="utf-8") as fh:
                fh.write(engine_dispatch._journal_root_for_run_dir(run_dir) + "\n")
        except OSError:
            return _refusal("journal-write-failed")
        opened_at = int(_now())
        enroll = "python3 -B %s enroll --run-dir %s" % (
            shlex.quote(os.path.join(_LIB_DIR, "native_engine.py")), shlex.quote(run_dir))
        preamble = (NATIVE_PREAMBLE.replace("{ENROLL_COMMAND}", enroll)
                    .replace("{RESULT_PATH}", os.path.join(run_dir, _RESULT_NAME)))
        try:
            with open(prompt_path, "wb") as fh:
                fh.write(preamble.encode("utf-8") + order)
                if bite_proof_block:
                    fh.write(b"\n\n" + bite_proof_block.encode("utf-8") + b"\n")
        except OSError:
            return _refusal("prompt-write-failed")
        record = {
            "kind": "run-opened",
            "engine": "native",
            "runKind": "write",
            "cwd": os.path.realpath(args.cwd),
            "baseSha": args.base_sha,
            "expectedItems": expected,
            "orderSha256": hashlib.sha256(order).hexdigest(),
            "openedAt": _stamp(opened_at),
            "deadlineAt": _stamp(opened_at + args.deadline_seconds),
            "deadlineSeconds": args.deadline_seconds,
            "resolvedSeat": {"model_id": verdict.get("model_id"),
                             "effort": verdict.get("effort"), "dispatchToken": token},
            "effectiveEffort": None,
            "effortNote": NATIVE_EFFORT_NOTE,
            "expectedServedModel": served,
            "bounds": NATIVE_BOUNDS,
            "routeReason": ROUTE_REASON_NATIVE,
        }
        if items_base_sha is not None:
            record["itemsBaseSha"] = items_base_sha
        if not engine_dispatch._journal_append(run_dir, record):
            os.unlink(prompt_path)
            os.unlink(pointer_path)
            return _refusal("journal-write-failed")
    finally:
        file_lock.release(lock)
    return {
        "ok": True, "terminal": False, "runDir": run_dir, "deadlineAt": record["deadlineAt"],
        "agent": {"subagent_type": _SUBAGENT_TYPE, "model": token, "isolation": "worktree",
                  "run_in_background": True, "promptPath": prompt_path,
                  "launchPrompt": LAUNCH_PROMPT.replace("{PROMPT_PATH}", prompt_path)},
    }


# --- enroll --------------------------------------------------------------------------------


def _enroll_refusal(reason):
    return {"ok": False, "reason": reason}


def _scan_entries(directory):
    """The paths of every entry of ``directory`` and of each ``@``-prefixed scope directory and the ``.bin``
    directory beneath it."""
    found = []
    for name in sorted(os.listdir(directory)):
        entry = os.path.join(directory, name)
        found.append(entry)
        # axis: a ``.bin`` entry that links back into the reviewed checkout's tracked tree is scanned like a package link, so it is never linked
        if (name.startswith("@") or name == ".bin") and os.path.isdir(entry) and not os.path.islink(entry):
            found.extend(os.path.join(entry, sub) for sub in sorted(os.listdir(entry)))
    return found


def _link_dependencies(repo_root, copy):
    """Link the reviewed checkout's installed dependency directories into ``copy``. None on success or when
    there is nothing to do, else the not-run reason."""
    root_real = os.path.realpath(repo_root)
    for name in DEPENDENCY_DIRS:
        source = os.path.join(os.path.abspath(repo_root), name)
        target = os.path.join(copy, name)
        # axis: a dependency directory the head tracks is already in the copy and is never replaced by a link
        if os.path.lexists(target) or not os.path.isdir(source):
            continue
        src_real = os.path.realpath(source)
        # axis: a dependency folder that is itself a link into another part of the reviewed checkout is never linked, so a test cannot write a tracked file through it
        if (src_real == root_real or src_real.startswith(root_real.rstrip(os.sep) + os.sep)) and src_real != os.path.join(root_real, name):
            return REASON_DEPENDENCY_LINK_UNSAFE
        try:
            for entry in _scan_entries(source):
                if not os.path.islink(entry):
                    continue
                real = os.path.realpath(entry)
                inside_root = real == root_real or real.startswith(root_real.rstrip(os.sep) + os.sep)
                inside_src = real == src_real or real.startswith(src_real.rstrip(os.sep) + os.sep)
                # axis: a package that links back into the reviewed checkout's tracked tree is never linked, so a test cannot write a tracked file through it
                if inside_root and not inside_src:
                    return REASON_DEPENDENCY_LINK_UNSAFE
            os.symlink(source, target, target_is_directory=True)
        except OSError:
            # axis: a scan or link that fails reads not-run, never a run without the dependencies
            return REASON_DEPENDENCY_LINK_FAILED
    return None


def _enroll_dependencies(top, builder_top):
    """Link the builder's installed dependency folders into ``top`` through the one guarded helper,
    ``_link_dependencies``. Returns the ``dependencies`` object: ``linked`` names exactly the links that
    exist, and ``note`` the helper's reason, or why nothing was linked."""
    installed = {name: os.path.isdir(os.path.join(builder_top, name)) for name in DEPENDENCY_DIRS}
    present = {name: os.path.lexists(os.path.join(top, name)) for name in DEPENDENCY_DIRS}
    reason = _link_dependencies(builder_top, top)
    linked = [name for name in DEPENDENCY_DIRS
              if os.path.islink(os.path.join(top, name)) and not present[name]]
    dependencies = {"linked": linked}
    if reason:
        dependencies["note"] = reason
    elif not linked:
        some = [name for name in installed if installed[name]]
        dependencies["note"] = "already-present" if some and all(present[n] for n in some) else "none-installed"
    return dependencies


def _cmd_enroll(args):
    run_dir = os.path.realpath(args.run_dir)
    state = _state(run_dir)
    opened = state["opened"]
    if opened is None or state["closed"] is not None:
        return _enroll_refusal("native-run-not-open")
    deadline = _deadline_epoch(opened)
    if deadline is None or _now() > deadline:
        return _enroll_refusal("native-deadline")
    here = os.getcwd()
    rc, out, _ = _git(here, "status", "--porcelain", "--untracked-files=all")
    if rc != 0 or out.strip():
        return _enroll_refusal("native-worktree-dirty")
    try:
        with _neutral_git():  # same worktree `_git` sees
            top = store_core.repo_root(here)
            git_dir = store_core.get_worktree_gitdir(top)
            common_dir = store_core.get_gitdir(top)
    except Exception:  # fail closed: a resolver failure leaves isolation unproven
        return _enroll_refusal("native-worktree-not-isolated")
    if not all(isinstance(p, str) and p for p in (top, git_dir, common_dir)):
        return _enroll_refusal("native-worktree-not-isolated")
    top = os.path.realpath(top)
    try:
        with _neutral_git():
            builder_top = store_core.repo_root(opened.get("cwd") or "")
    except Exception:  # fail closed: the builder's root unresolved leaves isolation unproven
        return _enroll_refusal("native-worktree-not-isolated")
    if not isinstance(builder_top, str) or not builder_top:
        return _enroll_refusal("native-worktree-not-isolated")
    if git_dir == common_dir or top == os.path.realpath(builder_top):
        return _enroll_refusal("native-worktree-not-isolated")
    base = opened.get("baseSha")
    rc, _, _ = _git(top, "checkout", "--detach", base)
    head_rc, head, _ = _git(top, "rev-parse", "HEAD")
    if rc != 0 or head_rc != 0 or head.strip() != base:
        return _enroll_refusal("native-base-checkout-failed")
    return {"ok": True, "head": base, "dependencies": _enroll_dependencies(top, builder_top)}


# --- wait ----------------------------------------------------------------------------------


def _cmd_wait(args):
    if not 0 <= args.max_wait <= WAIT_MAX_SECONDS:
        return _refusal("max-wait-invalid")
    run_dir = os.path.realpath(args.run_dir)
    opened = _state(run_dir)["opened"]
    deadline = _deadline_epoch(opened) if opened else None
    if deadline is None:
        return _refusal("native-run-not-open")
    result_path = os.path.join(run_dir, _RESULT_NAME)
    start = _now()
    while True:
        now = _now()
        present = os.path.exists(result_path)
        passed = now > deadline
        if present or passed or now - start >= args.max_wait:
            return {"ok": True, "resultPresent": present, "deadlinePassed": passed,
                    "secondsLeft": max(0, int(deadline - now))}
        _SLEEP(1)


# --- close ---------------------------------------------------------------------------------


def _transcript_models(path):
    """Every ``message.model`` of an assistant record; unparseable lines are skipped."""
    models = []
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return models
    for line in lines:
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(rec, dict) or rec.get("type") != "assistant":
            continue
        message = rec.get("message")
        model = message.get("model") if isinstance(message, dict) else None
        if isinstance(model, str) and model:
            models.append(model)
    return models


def _read_result(run_dir):
    try:
        with open(os.path.join(run_dir, _RESULT_NAME), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("status") not in _STATUSES:
        return None
    if "summary" in data and not isinstance(data["summary"], str):
        return None
    # axis: a result whose refusals list fails command_refusals.refusals_fault is unreadable (native-result-invalid on the done path).
    if "refusals" in data and command_refusals.refusals_fault(data["refusals"]) is not None:
        return None
    return data


def _result_refusals(run_dir):
    """The valid non-empty refusals list in ``result.json``, else ``None``; best-effort, never raises."""
    try:
        with open(os.path.join(run_dir, _RESULT_NAME), encoding="utf-8") as fh:
            data = json.load(fh)
        refusals = data.get("refusals") if isinstance(data, dict) else None
        if refusals and command_refusals.refusals_fault(refusals) is None:
            return engine_adapter.scrub_refusals(refusals)
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _worktree_listed(into, target):
    rc, out, _ = _git(into, "worktree", "list", "--porcelain")
    if rc != 0:
        return False
    for line in out.splitlines():
        if line.startswith("worktree ") and os.path.realpath(line[len("worktree "):]) == target:
            return True
    return False


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _staged_entry(cwd, path):
    """The index entry (mode, object id, stage) of ``path``; "" when absent, None on a git failure.
    Compared by object id and mode, so a symlink is never followed."""
    rc, out, _ = _git(cwd, "ls-files", "-s", "-z", "--", ":(literal)" + path)
    if rc != 0:
        return None
    for record in out.split("\0"):
        head, _, name = record.partition("\t")
        if name == path:  # exactly the declared file, never a sibling the pathspec matched
            return head
    return ""


def _in_tree(cwd, rev, path):
    """True when ``path`` is a file in ``rev``'s tree."""
    return _git(cwd, "cat-file", "-e", "%s:%s" % (rev, path))[0] == 0


class _Close(object):
    """One close attempt under the run-dir lock; every outcome goes through ``_finish``."""

    def __init__(self, run_dir, opened, state):
        self.run_dir = run_dir
        self.opened = opened
        self.state = state
        self.served = None
        self.refusals = None

    def _result(self, **fields):
        out = {"engine": "native", "bounds": NATIVE_BOUNDS, "servedModel": self.served}
        # axis: every terminal close result carries the agent's valid refusals, forfeit paths included.
        if self.refusals:
            out["refusals"] = self.refusals
        out.update(fields)
        return out

    def _finish(self, result):
        record = dict(result, kind="run-closed", closedAt=_stamp(_now()))
        if not engine_dispatch._journal_append(self.run_dir, record):
            return self._result(ok=False, terminal=True, reason="journal-write-failed")
        return result

    def _forfeit(self, token, **extra):
        return self._finish(self._result(
            ok=False, terminal=True, reason=dispatch_outcome.REASON_FORFEITED,
            forfeited=True, detail=token, **extra))

    def run(self, args):
        opened = self.opened
        self.refusals = _result_refusals(self.run_dir)
        if self.state["collecting"] is not None:
            return self._forfeit("native-collect-interrupted")
        deadline = _deadline_epoch(opened)
        if args.forfeit == "deadline" or deadline is None or _now() > deadline:
            return self._forfeit("native-deadline")
        enrolled = self.state["enrolled"]
        if enrolled is None:
            return self._forfeit("native-not-enrolled")
        target = os.path.realpath(args.worktree)
        into = os.path.realpath(args.into)
        try:
            with _neutral_git():  # same root `_git` will use
                top = store_core.repo_root(into)
        except Exception:
            return self._forfeit("native-collect-failed")
        if not top:
            return self._forfeit("native-collect-failed")
        into = os.path.realpath(top)  # patch paths are root-relative
        agent_id = enrolled.get("agentId")
        if (target != os.path.realpath(enrolled.get("worktree") or "")
                or not isinstance(agent_id, str) or not agent_id
                or agent_id not in os.path.basename(args.transcript)):
            return self._forfeit("native-binding-mismatch")
        if not _worktree_listed(into, target) or target == into:
            return self._forfeit("native-worktree-not-isolated")
        base = opened.get("baseSha")
        if _git(target, "merge-base", "--is-ancestor", base, "HEAD")[0] != 0:
            return self._forfeit("native-base-mismatch")
        models = _transcript_models(args.transcript)
        if not models:
            return self._forfeit("native-model-unread")
        if any(model != opened.get("expectedServedModel") for model in models):
            return self._forfeit("native-model-mismatch")
        self.served = models[0]
        result = _read_result(self.run_dir)
        if result is None:
            return self._forfeit("native-result-invalid")
        if result["status"] != "done":
            return self._finish(self._result(
                ok=False, terminal=True, reason=result["status"], forfeited=False))
        return self._collect(target, into, base)

    def _collect(self, target, into, base):
        items_base = self.opened.get("itemsBaseSha") or base
        with _neutral_git():
            item_check = engine_dispatch._item_delivery_check(
                target,
                {"expectedItems": self.opened.get("expectedItems"), "baseSha": items_base,
                 "baselineDirty": {}},
                timeout=GIT_TIMEOUT)
        extra = {} if item_check is None else {"itemCheck": item_check}
        if item_check is not None:
            if item_check.get("evidenceUnavailable"):
                return self._forfeit(
                    "item-evidence-unavailable:%s" % item_check.get("evidenceCause"), **extra)
            if item_check.get("missing"):
                return self._forfeit("items-undelivered", **extra)
        patch_path = os.path.join(self.run_dir, _PATCH_NAME)
        for name in DEPENDENCY_DIRS:
            link = os.path.join(target, name)
            # axis: only enroll's own untracked link to the builder's folder is dropped; a path the base tracks, or a link resolving elsewhere, is collected as it stands
            if (os.path.islink(link)
                    and os.path.realpath(link) == os.path.realpath(os.path.join(into, name))
                    and not _in_tree(target, base, name)):
                try:
                    os.unlink(link)
                except OSError:
                    return self._forfeit("native-collect-failed", **extra)
        if _git(target, "add", "-A")[0] != 0:
            return self._forfeit("native-collect-failed", **extra)
        rc, names, _ = _git(target, "diff", "--cached", "--name-only", "-z",
                            "--ignore-submodules=none", base)
        if rc != 0:
            return self._forfeit("native-collect-failed", **extra)
        files = sorted(name for name in names.split("\0") if name)
        if _git(
                target, "diff", "--cached", "--binary", "--unified=3", "--src-prefix=a/",
                "--dst-prefix=b/", "--no-color", "--no-ext-diff", "--no-textconv",
                "--ignore-submodules=none", "--submodule=short", "--output=" + patch_path, base)[0] != 0:
            return self._forfeit("native-collect-failed", **extra)
        patch_sha = _sha256_file(patch_path)
        if not engine_dispatch._journal_append(
                self.run_dir, {"kind": "native-collecting", "patchSha256": patch_sha,
                               "at": _stamp(_now())}):
            return self._result(ok=False, terminal=True, reason="journal-write-failed")
        if files and _git(into, "apply", "--index", "--whitespace=nowarn", patch_path)[0] != 0:
            return self._forfeit("native-collect-failed", **extra)
        for item in self.opened.get("expectedItems") or []:
            mine = _staged_entry(into, item)
            theirs = _staged_entry(target, item)
            if mine is None or theirs is None:
                return self._forfeit("native-collect-incomplete", **extra)
            if mine == "" and theirs == "" and _in_tree(target, items_base, item):
                continue  # a declared deletion (or rename source), applied on both sides
            if mine == "" or mine != theirs:
                return self._forfeit("native-collect-incomplete", **extra)
        return self._finish(self._result(
            ok=True, terminal=True, signal="ok", itemCheck=item_check,
            collected={"files": files, "patchSha256": patch_sha}))


def _replay(closed):
    return {k: v for k, v in closed.items() if k not in ("kind", "closedAt")}


def _cmd_close(args):
    run_dir = os.path.realpath(args.run_dir)
    lock = os.path.join(run_dir, _LOCK_NAME)
    if not os.path.isdir(run_dir):
        return _refusal("native-run-not-open")
    try:
        file_lock.acquire_with_reason(lock, reclaim_dead_holder=True)
    except file_lock.LockHeld:
        return _refusal("run-dir-locked")
    try:
        state = _state(run_dir)
        if state["opened"] is None:
            return _refusal("native-run-not-open")
        if state["closed"] is not None:
            return _replay(state["closed"])
        if state["corrupt"]:
            return _refusal("native-journal-corrupt")
        return _Close(run_dir, state["opened"], state).run(args)
    finally:
        file_lock.release(lock)


# --- CLI -----------------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(description="Native implementer engine run wrapper")
    sub = parser.add_subparsers(dest="verb", required=True)

    p = sub.add_parser("route", help="Name the engine an implementer run takes")
    p.add_argument("--cwd", required=True)
    p.set_defaults(func=_cmd_route)

    p = sub.add_parser("open", help="Open a native run and write the agent prompt")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--order-path", required=True)
    p.add_argument("--cwd", required=True)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--deadline-seconds", required=True, type=int)
    p.add_argument("--expect-item", action="append")
    p.add_argument("--items-base-sha")
    p.add_argument("--seat", required=True)
    p.set_defaults(func=_cmd_open)

    p = sub.add_parser("enroll", help="Subagent: check its worktree and pin the base")
    p.add_argument("--run-dir", required=True)
    p.set_defaults(func=_cmd_enroll)

    p = sub.add_parser("wait", help="Poll for result.json or the deadline")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--max-wait", required=True, type=int)
    p.set_defaults(func=_cmd_wait)

    p = sub.add_parser("close", help="Grade the run and collect its change")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--worktree", required=True)
    p.add_argument("--transcript", required=True)
    p.add_argument("--into", required=True)
    p.add_argument("--forfeit", choices=("deadline",))
    p.set_defaults(func=_cmd_close)
    return parser


def _exit_code(result):
    if result.get("ok") is True:
        return 0
    if result.get("terminal") is True and result.get("forfeited") is False:
        return 0
    return 1


def main(argv=None):
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    result = args.func(args)
    print(json.dumps(result))
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
