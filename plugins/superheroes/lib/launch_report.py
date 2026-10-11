#!/usr/bin/env python3
"""What a launch says afterwards: the launch report, and the "Still on your machine" line kept for
later messages.

Stdlib plus plugin imports only. Every reason either one prints is drawn from the one `REASONS`
table in `launch_place`. None of `render_report`, `record_still`, `still_line` and `clear_still`
ever raises. The stored reason is the first not-ready condition in the cloud check's order, and it
is forgotten once a build goes to the cloud or the condition behind it is fixed."""
import datetime
import json
import os
import re
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cloud_ready  # noqa: E402
import mode_registry  # noqa: E402
from launch_place import NOT_READY_CODES, REASONS, _fill, _words, reason_text  # noqa: E402

_STILL_SCHEMA = "cloud-still/1"
_STILL_HEADER = "Still on your machine"
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# The still-state clearing legs: a reason fixed by a condition this machine can read again.
_REREAD_CONDITION = {"no-setup": "setup", "pass-lapsed": "passLive", "calibration": "calibration"}


# ---------------------------------------------------------------- the launch report


def _label(lane):
    title = lane.get("title")
    if isinstance(title, str) and title.strip():
        return "#%s %s" % (lane["issue"], title.strip())
    return "#%s" % (lane["issue"],)


def _count(lanes):
    return "Launched %d build%s" % (len(lanes), "" if len(lanes) == 1 else "s")


def _fix_line(code, call):
    return _fill(REASONS[code]["fix"], call.get("cloudVersion"), call.get("advisorVersion"))


def _summary(lanes):
    """The all-on-your-machine form, or None when the lanes do not share one reason."""
    calls = [lane["placeCall"] for lane in lanes]
    if not all(c["place"] == "local" and c["pointedAtCloud"] for c in calls):
        return None
    codes = {c.get("reason") for c in calls}
    if len(codes) != 1 or not codes <= set(NOT_READY_CODES):
        return None
    if len({reason_text(c) for c in calls}) != 1:
        return None
    first = calls[0]
    code = first["reason"]
    wasnt = _fill(REASONS[code]["wasnt"], first.get("cloudVersion"), first.get("advisorVersion"))
    return "%s, all on your machine. The cloud wasn't ready: %s\n%s" % (
        _count(lanes), wasnt, _fix_line(code, first))


def render_report(lanes):
    """The launch report for these lanes, in launch order; None when cloud builds were neither on
    nor used. Never names a reason that is not in the table."""
    try:
        if not lanes:
            return None
        calls = [lane["placeCall"] for lane in lanes]
        if not any(c["pointedAtCloud"] or c["place"] == "cloud" for c in calls):
            return None
        summary = _summary(lanes)
        if summary is not None:
            return summary
        out = ["%s." % _count(lanes)]
        cloud = [_label(lane) for lane in lanes if lane["placeCall"]["place"] == "cloud"]
        local = [lane for lane in lanes if lane["placeCall"]["place"] != "cloud"]
        if cloud:
            out.append("In the cloud: %s." % ", ".join(cloud))
        if local:
            out.append("On your machine:")
            for lane in local:
                words = reason_text(lane["placeCall"])
                out.append("- %s. %s" % (_label(lane), words) if words else "- %s." % _label(lane))
        fixes = []
        for name in cloud_ready.CONDITION_ORDER:
            code = cloud_ready.REASON_FOR[name]
            for lane in local:
                call = lane["placeCall"]
                if call.get("reason") == code:
                    line = _fix_line(code, call)
                    if line not in fixes:
                        fixes.append(line)
                    break
        return "\n".join(out + fixes)
    except Exception:
        return None


# ---------------------------------------------------------------- the line at the top of later messages


def _still_path(cwd, root):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "state", "cloud-still.json")


def _today(given):
    if isinstance(given, datetime.datetime):
        return given.date()
    if isinstance(given, datetime.date):
        return given
    return datetime.datetime.now(datetime.timezone.utc).date()


def _remove(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        return {"action": "unchanged"}
    except OSError:
        return {"action": "refused"}
    return {"action": "cleared"}


def _write_still(path, state):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".cloud-still-", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, sort_keys=True, indent=2) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def record_still(cwd, place_calls, *, root=None, today=None):
    """After a launch: keep the one reason the cloud was not used, or forget it once a build went
    to the cloud. Never raises."""
    try:
        path = _still_path(cwd, root)
        if any(c.get("place") == "cloud" for c in place_calls):
            # axis: a build that went to the cloud clears the stored reason even beside a local not-ready fallback — see bite-proof record wo_a_launch_report
            return {"action": _remove(path)["action"], "reason": None}
        stuck = [c for c in place_calls if c.get("place") == "local" and c.get("pointedAtCloud")
                 and c.get("reason") in NOT_READY_CODES]
        if stuck:
            rank = [cloud_ready.REASON_FOR[name] for name in cloud_ready.CONDITION_ORDER]
            call = min(stuck, key=lambda c: rank.index(c["reason"]))
            _write_still(path, {
                "schema": _STILL_SCHEMA, "reason": call["reason"], "by": call.get("by"),
                "cloudVersion": call.get("cloudVersion"),
                "advisorVersion": call.get("advisorVersion"),
                "reported": call.get("reported"),
                "observedOn": _today(today).isoformat(),
            })
            return {"action": "written", "reason": call["reason"]}
        return {"action": "unchanged", "reason": None}
    except Exception:
        return {"action": "refused", "reason": "write-failed"}


def _read_still(path):
    """The stored state, or None when it is absent or not in the exact shape written."""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError):
        return False
    if not isinstance(state, dict) or state.get("schema") != _STILL_SCHEMA:
        return False
    if state.get("reason") not in NOT_READY_CODES or state.get("by") not in ("setting", "word"):
        return False
    for key in ("cloudVersion", "advisorVersion"):
        if state.get(key) is not None and not isinstance(state[key], str):
            return False
    if not cloud_ready.valid_reported(state.get("reported")):
        return False
    observed = state.get("observedOn")
    if not (isinstance(observed, str) and _DATE_RE.fullmatch(observed)):
        return False
    try:
        datetime.date.fromisoformat(observed)
    except ValueError:
        return False
    return state


def _fixed(state, now):
    reason = state["reason"]
    reported = state.get("reported") or {}
    if state["by"] == "setting" and now.get("setting") is not True:
        return True
    conditions = now.get("conditions") or {}
    if reason in _REREAD_CONDITION:
        return conditions.get(_REREAD_CONDITION[reason]) is True
    if reason == "version" and reported.get("pluginVersion") is None:
        return conditions.get("version") is True
    checked = now.get("checkedAt")
    if not (isinstance(checked, str) and _DATE_RE.fullmatch(checked)):
        return False
    try:
        # axis: a reported fact is fixed only by a check made on a later day — see bite-proof record wo_a_launch_report
        later = datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(state["observedOn"])
        # axis: a reported fact clears only when the reader reads ready now — see bite-proof record wo_a_launch_report
        return later and now.get("ready") is True
    except ValueError:
        return False


def still_line(cwd, *, root=None, today=None, readiness_fn=None):
    """The line to repeat at the top of a later message, or None; clears the stored reason once
    it is fixed. Never raises."""
    try:
        path = _still_path(cwd, root)
        state = _read_still(path)
        if state is None:
            return None
        if state is False:
            _remove(path)
            return None
        try:
            now = (readiness_fn or cloud_ready.readiness)(cwd, reported=None, root=root)
            fixed = _fixed(state, now)
        except Exception:
            fixed = False
        if fixed:
            _remove(path)
            return None
        code = state["reason"]
        words = _words(code, state.get("cloudVersion"), state.get("advisorVersion"))
        return "%s\n%s %s" % (_STILL_HEADER, words, REASONS[code]["short"])
    except Exception:
        return None


def clear_still(cwd, *, root=None):
    """Forget the stored reason. Never raises."""
    try:
        return _remove(_still_path(cwd, root))
    except Exception:
        return {"action": "refused"}
