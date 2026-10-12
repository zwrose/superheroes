#!/usr/bin/env python3
"""What a launch says afterwards: the launch report, and the "Still on your machine" line kept for
later messages.

Stdlib plus plugin imports only. Every reason either one prints is drawn from the one `REASONS`
table in `launch_place`. None of `render_report`, `record_still`, `still_check`, `still_line`,
`clear_still`, `read_still_cursor` and `write_still_cursor` ever raises. The stored reason is the
first not-ready condition in the cloud check's order, and it is forgotten once a build goes to the
cloud or the condition behind it is fixed."""
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
from launch_place import NOT_READY_CODES, REASONS, _fill, _words, fix_text, reason_text  # noqa: E402

_STILL_SCHEMA = "cloud-still/1"
_CURSOR_SCHEMA = "cloud-still-cursor/1"
_STILL_HEADER = "Still on your machine"
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_UNREADABLE = object()
STILL_UNREADABLE = "still-state-unreadable"

# The condition behind each reason, read back out of the readiness registry.
_CONDITION_FOR = {reason: name for name, reason in cloud_ready.REASON_FOR.items()}
# The still-state clearing legs: a reason fixed by a condition this machine can read again.
_REREAD_REASONS = ("no-setup", "pass-lapsed", "calibration")


# ---------------------------------------------------------------- the launch report


def _label(lane):
    title = lane.get("title")
    if isinstance(title, str) and title.strip():
        return "#%s %s" % (lane["issue"], title.strip())
    return "#%s" % (lane["issue"],)


def _count(lanes):
    return "Launched %d build%s" % (len(lanes), "" if len(lanes) == 1 else "s")


def _fix_line(code, call):
    return _fill(fix_text(call), call.get("cloudVersion"), call.get("advisorVersion"))


def _recheck_first(calls):
    """The call that carries the failed check when any of these does, else the first: the fix for
    a reason must keep the recheck step whichever call came first."""
    return next((c for c in calls if c.get("failedCheck") is not None), calls[0])


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
    first = _recheck_first(calls)
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
            shared = [lane["placeCall"] for lane in local if lane["placeCall"].get("reason") == code]
            if shared:
                line = _fix_line(code, _recheck_first(shared))
                if line not in fixes:
                    fixes.append(line)
        return "\n".join(out + fixes)
    except Exception:
        return None


# ---------------------------------------------------------------- the line at the top of later messages


def _still_path(cwd, root):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "state", "cloud-still.json")


def _cursor_path(cwd, root):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "state", "cloud-still-cursor.json")


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


def _write_atomic(path, state):
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


def _write_still(path, state):
    _write_atomic(path, state)


def read_still_cursor(cwd, *, root=None):
    """The ledger position of the last launch applied to the reminder: -1 when none has been, None
    when the cursor file cannot be read or is not in the shape written. Never raises."""
    try:
        with open(_cursor_path(cwd, root), encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return -1
    except Exception:
        return None
    if not isinstance(data, dict) or set(data) != {"schema", "applied"}:
        return None
    applied = data["applied"]
    if data["schema"] != _CURSOR_SCHEMA or isinstance(applied, bool) or not isinstance(applied, int) \
            or applied < -1:
        return None
    return applied


def write_still_cursor(cwd, applied, *, root=None):
    """Record the ledger position of the last launch applied; True when it was written. Never raises."""
    try:
        _write_atomic(_cursor_path(cwd, root), {"schema": _CURSOR_SCHEMA, "applied": applied})
        return True
    except Exception:
        return False


def record_still(cwd, place_calls, *, root=None, today=None, keep_higher_stored=False):
    """After a launch: keep the one reason the cloud was not used, or forget it once a build went
    to the cloud. With keep_higher_stored, a stored reminder that ranks above the new reason stays
    (unchanged), and one that cannot be read is neither replaced nor removed (refused). Never raises."""
    try:
        path = _still_path(cwd, root)
        if any(c.get("place") == "cloud" for c in place_calls):
            # axis: a build that went to the cloud clears the stored reason even beside a local not-ready fallback — see bite-proof record wo_a_launch_report
            return {"action": _remove(path)["action"], "reason": None}
        stuck = [c for c in place_calls if c.get("place") == "local" and c.get("pointedAtCloud")
                 and c.get("reason") in NOT_READY_CODES]
        if stuck:
            rank = [cloud_ready.REASON_FOR[name] for name in cloud_ready.CONDITION_ORDER]
            best = min(rank.index(c["reason"]) for c in stuck)
            tied = [c for c in stuck if rank.index(c["reason"]) == best]
            call = _recheck_first(tied)
            if keep_higher_stored:
                stored = _read_still(path)
                if stored is _UNREADABLE:
                    return {"action": "refused", "reason": STILL_UNREADABLE}
                # axis: a new fallback never displaces a higher-ranked unresolved reminder — see bite-proof record wo_a_launch_report
                if stored and rank.index(stored["reason"]) < best:
                    return {"action": "unchanged", "reason": None}
            # a launch the owner pointed at the cloud by word stays unresolved when the setting is off
            by = "word" if any(c.get("by") == "word" for c in tied) else call.get("by")
            # a builder-reported version on any tied call keeps the later-day clearing, whichever call came first
            reported = next((c["reported"] for c in tied if isinstance(c.get("reported"), dict)
                             and c["reported"].get("pluginVersion") is not None), call.get("reported"))
            state = {
                "schema": _STILL_SCHEMA, "reason": call["reason"], "by": by,
                "cloudVersion": call.get("cloudVersion"),
                "advisorVersion": call.get("advisorVersion"),
                "reported": reported,
                "observedOn": _today(today).isoformat(),
            }
            if call.get("failedCheck") is not None:
                state["failedCheck"] = call["failedCheck"]
            _write_still(path, state)
            return {"action": "written", "reason": call["reason"]}
        return {"action": "unchanged", "reason": None}
    except Exception:
        return {"action": "refused", "reason": "write-failed"}


def _read_still(path):
    """The stored state; None when it is absent, False when it is not in the exact shape written,
    and _UNREADABLE when the file could not be read at all."""
    try:
        with open(path, encoding="utf-8") as fh:
            state = json.load(fh)
    except FileNotFoundError:
        return None
    except OSError:
        return _UNREADABLE
    except (ValueError, RecursionError):
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
    failed = state.get("failedCheck")
    if failed is not None and not (
            isinstance(failed, list) and all(isinstance(part, str) for part in failed)):
        return False
    observed = state.get("observedOn")
    if not (isinstance(observed, str) and _DATE_RE.fullmatch(observed)):
        return False
    try:
        datetime.date.fromisoformat(observed)
    except ValueError:
        return False
    return state


def _setting_read_off(cwd, root):
    """True only when the cloud-builds setting was read cleanly and is off. The readiness reader
    gives an unreadable setting as off, so a setting-directed reminder is not dropped on its word.
    The config reader also gives a profile it could not read or parse as the defaults, so only an
    absent profile or one that read back whole counts as read."""
    try:
        import core_md
        import project_config

        if core_md.read(cwd, root) is None and not core_md.gate_config_profile_is_absent(cwd, root):
            return False
        got = project_config.get_item(cwd, project_config.CLOUD_BUILDS_SLUG, root=root)
        return got.get("effective") is False and got.get("malformed") is not True
    except Exception:
        return False


def _fixed(state, now, cwd=None, root=None):
    reason = state["reason"]
    reported = state.get("reported") or {}
    # a setting the reader could not read is not a setting switched off
    if state["by"] == "setting" and now.get("setting") is not True and _setting_read_off(cwd, root):
        return True
    conditions = now.get("conditions") or {}
    if reason in _REREAD_REASONS:
        return conditions.get(_CONDITION_FOR[reason]) is True
    if reason == "version" and reported.get("pluginVersion") is None:
        return conditions.get(_CONDITION_FOR[reason]) is True
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


def still_check(cwd, *, root=None, today=None, readiness_fn=None):
    """The line to repeat at the top of a later message (None when there is none) and the refusal
    when the stored state could not be read; an unreadable file is left in place, not cleared.
    Clears the stored reason once it is fixed. Never raises."""
    try:
        path = _still_path(cwd, root)
        state = _read_still(path)
        if state is None:
            return {"line": None, "refused": None}
        if state is _UNREADABLE:
            return {"line": None, "refused": STILL_UNREADABLE}
        if state is False:
            _remove(path)
            return {"line": None, "refused": None}
        try:
            now = (readiness_fn or cloud_ready.readiness)(cwd, reported=None, root=root)
            fixed = _fixed(state, now, cwd, root)
        except Exception:
            fixed = False
        if fixed:
            _remove(path)
            return {"line": None, "refused": None}
        code = state["reason"]
        words = _words(code, state.get("cloudVersion"), state.get("advisorVersion"))
        failed = state.get("failedCheck")
        # after a failed check the reminder carries the recheck step, as the launch report does
        fix = REASONS[code]["short"] if failed is None else fix_text(
            {"reason": code, "failedCheck": failed})
        return {"line": "%s\n%s %s" % (_STILL_HEADER, words, fix), "refused": None}
    except Exception:
        return {"line": None, "refused": None}


def still_line(cwd, *, root=None, today=None, readiness_fn=None):
    """The line to repeat at the top of a later message, or None. Never raises."""
    return still_check(cwd, root=root, today=today, readiness_fn=readiness_fn)["line"]


def clear_still(cwd, *, root=None):
    """Forget the stored reason. Never raises."""
    try:
        return _remove(_still_path(cwd, root))
    except Exception:
        return {"action": "refused"}
