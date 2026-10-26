#!/usr/bin/env python3
"""What a launch says afterwards: the launch report, and the "Still on your machine" line kept for
later messages.

Stdlib plus plugin imports only. Every reason either one prints is drawn from the one `REASONS`
table in `launch_place`. Neither `render_report`, `still_check` nor `still_line` ever raises, and
nothing here writes: the line is worked out each time from the launch ledger and the cloud's
readiness at that moment. It is the first not-ready condition in the cloud check's order, among the
local fallbacks since the last build that went to the cloud and not yet fixed."""
import datetime
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cloud_ready  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text  # noqa: E402
import launch_ledger as ll  # noqa: E402
from launch_place import NOT_READY_CODES, REASONS, _fill, fix_text, reason_text, wasnt_text  # noqa: E402

_STILL_HEADER = "Still on your machine"
STILL_LEDGER_UNREADABLE = "still-ledger-unreadable"
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# The condition behind each reason, read back out of the readiness registry.
_CONDITION_FOR = {reason: name for name, reason in cloud_ready.REASON_FOR.items()}
# The reasons a condition this machine can read again clears.
_REREAD_REASONS = tuple(cloud_ready.REASON_FOR[name] for name in ("setup", "passLive", "pluginPin", "dependencyHook", "calibration"))
# The reason whose fact the cloud reports as a plugin version.
_VERSION_REASON = cloud_ready.REASON_FOR["version"]
# Where each reason stands in the cloud check's order: the lower the number, the sooner it is shown.
_RANK = {cloud_ready.REASON_FOR[name]: place for place, name in enumerate(cloud_ready.CONDITION_ORDER)}


# ---------------------------------------------------------------- what a ledger launch says about its place


def report_place_call(raw_reserved, folded_place):
    """The lane's place call: the reserved record's own when it agrees with the ledger's folded
    place, otherwise one synthesized from that place with no reason."""
    premise = raw_reserved.get("premise") if isinstance(raw_reserved, dict) else None
    call = premise.get("placeCall") if isinstance(premise, dict) else None
    if (
        isinstance(call, dict)
        and call.get("place") == folded_place
        and isinstance(call.get("pointedAtCloud"), bool)
    ):
        return call
    return {"place": folded_place, "pointedAtCloud": folded_place == ll.PLACE_CLOUD, "reason": None}


def decides_still(call):
    """True when the place call moves the "Still on your machine" line: a build in the cloud, or
    one the cloud was meant for that ran locally because it was not ready."""
    return call.get("place") == ll.PLACE_CLOUD or bool(
        call.get("place") == ll.PLACE_LOCAL and call.get("pointedAtCloud")
        and call.get("reason") in NOT_READY_CODES)


def started_indexes(records):
    """Each launch's ledger position of its latest started event. Launches reserve and spawn in
    separate steps, so the position a launch started at, not the one it reserved at, is the order
    in which the launches actually happened."""
    return {
        rec["launchId"]: idx for idx, rec in enumerate(records)
        if isinstance(rec, dict) and rec.get("event") == "started"
    }


def launch_day(info):
    """The UTC date the launch started; None when the ledger carries no usable time."""
    stamp = info.get("startedTs", info.get("reservedTs"))
    try:
        return datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).date()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


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
    a reason must keep the recheck step whichever call came first. A failed check that left no
    recheck words (a calibration part on a dependency-hook call) does not count: a later call
    whose fix asks for the check again wins."""
    def asks(c):
        return "check again" in (fix_text(c) or "")
    failed = [c for c in calls if c.get("failedCheck") is not None]
    return next((c for c in failed if asks(c)), failed[0] if failed else calls[0])


def _summary(lanes):
    """The all-on-your-machine form, or None when the lanes do not share one reason."""
    calls = [lane["placeCall"] for lane in lanes]
    if not all(c["place"] == ll.PLACE_LOCAL and c["pointedAtCloud"] for c in calls):
        return None
    codes = {c.get("reason") for c in calls}
    if len(codes) != 1 or not codes <= set(NOT_READY_CODES):
        return None
    if len({reason_text(c) for c in calls}) != 1:
        return None
    first = _recheck_first(calls)
    code = first["reason"]
    wasnt = wasnt_text(first)
    return "%s, all on your machine. The cloud wasn't ready: %s\n%s" % (
        _count(lanes), wasnt, _fix_line(code, first))


def yields_report(calls):
    """True when any of these place calls leaves a launch report: cloud builds were on or used.
    The one predicate behind a report, so a caller that decides before it renders cannot drift
    from the renderer. Never raises; a call it cannot read yields no report."""
    try:
        return any(c["pointedAtCloud"] or c["place"] == ll.PLACE_CLOUD for c in calls)
    except Exception:
        return False


def _paused_line(lanes):
    """The one status line for a build the cloud was meant for that fell back because its account's
    setup check failed, or None. The reason and fix lines name the failed part; this says only that
    the account is paused: `PAUSED_LINE_ON` when the setting pointed it, else `PAUSED_LINE_WORD`."""
    paused = [lane["placeCall"] for lane in lanes
              if lane["placeCall"]["place"] != ll.PLACE_CLOUD
              and lane["placeCall"].get("pointedAtCloud") is True
              and lane["placeCall"].get("failedCheck") is not None]
    if not paused:
        return None
    return (cloud_setup.PAUSED_LINE_ON if any(c.get("by") == "setting" for c in paused)
            else cloud_setup.PAUSED_LINE_WORD)


def render_report(lanes):
    """The launch report for these lanes, in launch order; None when cloud builds were neither on
    nor used. Never names a reason that is not in the table. A build the cloud was meant for that
    fell back because of a failed check ends the report with the paused line."""
    try:
        if not lanes:
            return None
        calls = [lane["placeCall"] for lane in lanes]
        if not yields_report(calls):
            return None
        paused = _paused_line(lanes)
        summary = _summary(lanes)
        if summary is not None:
            return summary if paused is None else summary + "\n" + paused
        out = ["%s." % _count(lanes)]
        cloud = [_label(lane) for lane in lanes if lane["placeCall"]["place"] == ll.PLACE_CLOUD]
        local = [lane for lane in lanes if lane["placeCall"]["place"] != ll.PLACE_CLOUD]
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
                # one fix line per (reason, hook gap) pair, the recheck-carrying call's: every call
                # but a dependency-hook one has no hook gap, so those reasons print one line each;
                # a gap read back from a ledger record that is not a string groups as no gap. A
                # no-setup call's fix depends on the parts that failed, so those calls group by
                # (hook gap, failed parts) and a lane paused on other parts keeps its own fix line
                groups = {}
                for call in shared:
                    gap = call.get("hookGap")
                    key = gap if isinstance(gap, str) else None
                    # axis: lanes paused on different failed parts each keep their own fix line
                    if code == cloud_ready.REASON_FOR["setup"] and isinstance(call.get("failedCheck"), list):
                        key = (key, tuple(call["failedCheck"]))
                    groups.setdefault(key, []).append(call)
                for group in groups.values():
                    line = _fix_line(code, _recheck_first(group))
                    if line not in fixes:
                        fixes.append(line)
        return "\n".join(out + fixes + ([] if paused is None else [paused]))
    except Exception:
        return None


# ---------------------------------------------------------------- the line at the top of later messages


def _configuration_is_whole(path):
    """True when the profile's projectConfiguration is absent or a mapping. The profile reader gives
    any other value as an empty mapping, which the config reader then gives as the setting's default."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    import core_md

    block = json.loads(core_md._JSON_BLOCK.search(text).group(1))
    return block.get(core_md.PROJECT_CONFIGURATION_KEY) is None or isinstance(
        block[core_md.PROJECT_CONFIGURATION_KEY], dict)


def _setting_read_off(cwd, root):
    """True only when the cloud-builds setting was read cleanly and is off. The readiness reader
    gives an unreadable setting as off, so a setting-directed reminder is not dropped on its word.
    The config reader also gives a profile it could not read or parse as the defaults, so only an
    absent profile or one that read back whole counts as read."""
    try:
        import core_md
        import project_config

        # the path is resolved once, without writing the mode record; gate_config_profile_is_absent
        # would resolve it again with the default, which can write that record
        path = core_md.core_path(cwd, root, persist_backfill=False)
        if core_md.read(cwd, root, persist_backfill=False) is None:
            if core_md._classify_core_md_at_path(path).status != core_md.CONFIG_ABSENT:
                return False
        elif not _configuration_is_whole(path):
            return False
        got = project_config.get_item(
            cwd, project_config.CLOUD_BUILDS_SLUG, root=root, persist_backfill=False)
        return got.get("effective") is False and got.get("malformed") is not True
    except Exception:
        return False


def _fixed(candidate, now, cwd=None, root=None):
    reason = candidate["reason"]
    reported = candidate.get("reported") or {}
    # a setting the reader could not read is not a setting switched off
    if candidate["by"] == "setting" and now.get("setting") is not True and _setting_read_off(cwd, root):
        return True
    conditions = now.get("conditions") or {}
    if reason == cloud_ready.REASON_FOR["dependencyHook"]:
        # axis: a dependency-hook fallback is fixed only when readiness reads the hook now and the check routing runs, on the checkout's current HEAD against the launch's adopted head, finds no gap — see bite-proof record i2021_branch_hook
        return conditions.get("dependencyHook") is True and cloud_setup_text.branch_hook_gap(
            cwd, root, None, candidate.get("adoptsHead")) is None
    if reason in _REREAD_REASONS:
        return conditions.get(_CONDITION_FOR[reason]) is True
    if reason == _VERSION_REASON and reported.get("pluginVersion") is None:
        return conditions.get(_CONDITION_FOR[reason]) is True
    if candidate.get("failedCheck") is not None:
        # axis: a fallback that came from a failed check is fixed once a passing check has cleared the marker and its condition reads true now, on the same day too
        return now.get("failedCheck") is None and conditions.get(_CONDITION_FOR[reason]) is True
    checked = now.get("checkedAt")
    observed = candidate.get("observedOn")
    # a launch with no start date has no day for a later check to follow
    if not (isinstance(checked, str) and _DATE_RE.fullmatch(checked)) or observed is None:
        return False
    try:
        # axis: a reported fact is fixed only by a check made on a later day — see bite-proof record wo_a_launch_report
        later = datetime.date.fromisoformat(checked) > datetime.date.fromisoformat(observed)
        # axis: a reported fact clears only when the reader reads ready now — see bite-proof record wo_a_launch_report
        return later and now.get("ready") is True
    except ValueError:
        return False


def _candidate(call, info, premise=None):
    """What the line needs from one local fallback, kept to the shapes it can print. `premise` is the
    reserved record's premise: the base and adopted commits routing checked the hook on."""
    premise = premise if isinstance(premise, dict) else {}
    base = premise.get("baseCommit")
    adopts = premise.get("adoptsHead")
    reported = call.get("reported")
    failed = call.get("failedCheck")
    day = launch_day(info)
    return {
        "reason": call["reason"],
        "by": call.get("by"),
        "cloudVersion": call["cloudVersion"] if isinstance(call.get("cloudVersion"), str) else None,
        "advisorVersion": call["advisorVersion"] if isinstance(call.get("advisorVersion"), str) else None,
        "reported": reported if cloud_ready.valid_reported(reported) else None,
        "failedCheck": failed if isinstance(failed, list) and all(isinstance(p, str) for p in failed) else None,
        "observedOn": None if day is None else day.isoformat(),
        "baseCommit": base if isinstance(base, str) and base else None,
        "adoptsHead": adopts if isinstance(adopts, str) and adopts else None,
    }


def _fallbacks(records, launches):
    """The local fallbacks since the last build that went to the cloud, oldest start first. A launch
    counts once it has started. One whose cloud session is unconfirmed may not exist, so it is
    neither a cloud build nor a fallback."""
    started_at = started_indexes(records)
    reserved = {
        rec["launchId"]: rec for rec in records
        if isinstance(rec, dict) and rec.get("event") == "reserved"
    }
    deciding = []
    for launch_id, info in launches.items():
        # axis: an unconfirmed cloud launch does not clear the line — see bite-proof record wo_a_launch_report
        if not info["started"] or info.get("cloudSessionUnconfirmed"):
            continue
        raw = reserved.get(launch_id)
        call = report_place_call(raw, info["place"])
        if decides_still(call):
            premise = raw.get("premise") if isinstance(raw, dict) else None
            deciding.append((started_at.get(launch_id, info["reservedIndex"]), call, info, premise))
    deciding.sort(key=lambda entry: entry[0])
    # axis: only the fallbacks after the last confirmed cloud launch count — see bite-proof record wo_a_launch_report
    last_cloud = max((at for at, (_pos, call, _info, _premise) in enumerate(deciding)
                      if call.get("place") == ll.PLACE_CLOUD), default=-1)
    return [_candidate(call, info, premise) for _pos, call, info, premise in deciding[last_cloud + 1:]]


def _still_fixed(candidate, now, cwd, root):
    """True when this fallback's reason reads fixed now. Readiness that could not be read fixes nothing."""
    if now is None:
        return False
    try:
        return _fixed(candidate, now, cwd, root)
    except Exception:
        return False


def still_check(repo_root, *, root=None, readiness_fn=None):
    """The line to repeat at the top of a later message (None when there is none), and the refusal
    when the launch ledger could not be read. Nothing is saved: the line is worked out from the
    ledger and from the cloud's readiness now. Never raises."""
    try:
        try:
            read = ll.read(repo_root, create=False)
        except Exception:
            # a reader that breaks leaves the ledger's state unknown: refuse, never read it as no reminder
            return {"line": None, "refused": STILL_LEDGER_UNREADABLE}
        if read["state"] == "missing":
            return {"line": None, "refused": None}
        if read["state"] != "ok":
            return {"line": None, "refused": STILL_LEDGER_UNREADABLE}
        folded = ll.fold(read["records"])
        if not folded["ok"]:
            return {"line": None, "refused": STILL_LEDGER_UNREADABLE}
        candidates = _fallbacks(read["records"], folded["launches"])
        if not candidates:
            return {"line": None, "refused": None}
        try:
            now = (readiness_fn or cloud_ready.readiness)(
                repo_root, reported=None, root=root, persist_backfill=False)
        except Exception:
            now = None
        # axis: a fixed candidate is skipped, so the next one still standing shows — see bite-proof record wo_a_launch_report
        standing = [c for c in candidates if not _still_fixed(c, now, repo_root, root)]
        if not standing:
            return {"line": None, "refused": None}
        # the reason first in the cloud check's order; of equals, the one that carries the recheck
        # step, then the latest started (the list runs oldest first, so it is walked from the end)
        shown = min(reversed(standing), key=lambda c: (_RANK[c["reason"]], c["failedCheck"] is None))
        code = shown["reason"]
        failed = shown["failedCheck"]
        words = reason_text({"reason": code, "failedCheck": failed,
                             "cloudVersion": shown["cloudVersion"],
                             "advisorVersion": shown["advisorVersion"]})
        # after a failed check the line carries the recheck step, as the launch report does
        fix = REASONS[code]["short"] if failed is None else fix_text(
            {"reason": code, "failedCheck": failed})
        return {"line": "%s\n%s %s" % (_STILL_HEADER, words, fix), "refused": None}
    except Exception:
        return {"line": None, "refused": None}


def still_line(repo_root, *, root=None, readiness_fn=None):
    """The line to repeat at the top of a later message, or None. Never raises."""
    return still_check(repo_root, root=root, readiness_fn=readiness_fn)["line"]
