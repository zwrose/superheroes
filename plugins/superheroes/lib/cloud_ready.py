#!/usr/bin/env python3
"""The readiness reader: whether the cloud can take a build right now.

Stdlib plus plugin imports only. The setting and the setup record come only from
`cloud_setup.read`; the calibration stamp comes only from the formula the cloud check uses. Seven
conditions are judged in a fixed order; the first one that fails names the reason. Anything that
cannot be read counts as not ready, never as ready, and `readiness` never raises."""
import datetime
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import cloud_check  # noqa: E402
import cloud_setup  # noqa: E402
import cloud_setup_text  # noqa: E402

CONDITION_ORDER = ("setup", "passPresent", "passLive", "version", "dependencyHook", "calibration",
                   "platform")
REASON_FOR = {"setup": "no-setup", "passPresent": "no-pass", "passLive": "pass-lapsed",
              "version": "version", "dependencyHook": "dependency-hook",
              "calibration": "calibration", "platform": "unreachable"}
REPORTED_KEYS = ("pluginVersion", "noPass", "unreachable")
# The one condition a failed check's part forces false; any other part, or a marker that cannot be
# read, forces the setup condition false.
FAILED_PART_CONDITION = {
    # axis: the reviewer part forces the pass-present condition false — see bite-proof record wo_c_place_call
    "reviewer": "passPresent",
    # axis: the version part forces the version condition false — see bite-proof record wo_c_place_call
    "version": "version",
    # axis: the calibration part forces the calibration condition false — see bite-proof record wo_c_place_call
    "calibration": "calibration",
}

_VERSION_RE = re.compile(r"\d+\.\d+\.\d+")


def valid_reported(reported):
    """True for None or a dict of only the known reported facts, each in its exact shape."""
    if reported is None:
        return True
    if not isinstance(reported, dict):
        return False
    for key, value in reported.items():
        if key not in REPORTED_KEYS:
            return False
        if key == "pluginVersion":
            if not (isinstance(value, str) and _VERSION_RE.fullmatch(value)):
                return False
        elif value is not True:
            return False
    return True


def _result(conditions, *, setting=False, account=None, environment=None, cloud_version=None,
            advisor_version=None, picks_up=None, checked_at=None, failed_check=None):
    # axis: the reason is the first false condition in the fixed order — see bite-proof record wo_a_place_call
    reason = next((REASON_FOR[name] for name in CONDITION_ORDER if not conditions[name]), None)
    return {
        "ready": reason is None,
        "reason": reason,
        "conditions": conditions,
        "setting": setting,
        "account": account,
        "environment": environment,
        "cloudVersion": cloud_version,
        "advisorVersion": advisor_version,
        "picksUpVersion": picks_up,
        "checkedAt": checked_at,
        "failedCheck": failed_check,
    }


def _all_false():
    return {name: False for name in CONDITION_ORDER}


def _advisor_version(given):
    if given is not None:
        return given if isinstance(given, str) and given else None
    try:
        version = cloud_setup_text._plugin_version()
    except Exception:
        return None
    return version if isinstance(version, str) and version else None


def _today(given):
    if isinstance(given, datetime.datetime):
        return given.date()
    if isinstance(given, datetime.date):
        return given
    return datetime.datetime.now(datetime.timezone.utc).date()


def _failed_check(cwd, account, root):
    """None when no failed-check marker is present, else the marker's failed parts: an empty list
    when the marker is damaged or its read raises."""
    try:
        marker = cloud_check.read_failed_check(cwd, account, root)
        if marker is None:
            return None
        parts = marker.get("failedParts")
        if marker.get("damaged") is True or not isinstance(parts, list):
            return []
        return list(parts)
    except Exception:
        return []


def _readiness(cwd, account, advisor_version, reported, today, root, env, stamp_fn, seen,
               *, persist_backfill=True, commit=None, adopted=None):
    if account is None:
        account = cloud_setup.launching_account(env, cwd)
    advisor = _advisor_version(advisor_version)
    keyword = {} if persist_backfill else {"persist_backfill": False}
    got = cloud_setup.read(cwd, account, root, **keyword)
    setting = got.get("setting") is True
    seen["setting"] = setting
    seen["account"] = account if isinstance(account, str) else None
    fallback = dict(setting=setting, account=seen["account"], advisor_version=advisor)
    # axis: a reported fact in an unknown shape never reads as ready — see bite-proof record wo_a_place_call
    if not valid_reported(reported):
        return _result(_all_false(), **fallback)
    reported = reported or {}
    setup = got.get("ready") is True and isinstance(got.get("record"), dict)
    conditions = _all_false()
    # axis: no setup forces every later condition false — see bite-proof record wo_a_place_call
    if not setup:
        return _result(conditions, **fallback)
    record = got["record"] if isinstance(got.get("record"), dict) else {}
    # axis: any failed-check marker present means the latest check failed, so the setup is not ready — see bite-proof record wo_c_place_call
    failed = _failed_check(cwd, account, root)
    forced = set()
    if failed is not None:
        # axis: any other failed part, or a marker that cannot be read, forces the setup condition false — see bite-proof record wo_c_place_call
        if not failed or any(part not in FAILED_PART_CONDITION for part in failed):
            return _result(conditions, failed_check=failed, **fallback)
        forced = {FAILED_PART_CONDITION[part] for part in failed}
    conditions["setup"] = setup
    conditions["passPresent"] = reported.get("noPass") is not True
    # axis: the pass is live only while its recorded lapse date is not before today — see bite-proof record wo_a_place_call
    conditions["passLive"] = cloud_check._lapses_ok(record.get("passLapses"), _today(today))
    # axis: a version the cloud reported stands in place of the record's — see bite-proof record wo_a_place_call
    if reported.get("pluginVersion") is not None:
        cloud_version = reported["pluginVersion"]
        conditions["version"] = advisor is not None and cloud_version == advisor
    else:
        cloud_version = record.get("pluginVersion")
        conditions["version"] = advisor is not None and (
            cloud_version == advisor or record.get("picksUpVersion") is True)
        # axis: a failed version check leaves the old record in place, so its version is not the cloud's current one — see bite-proof record wo_d_place_call
        if failed is not None and "version" in failed:
            cloud_version = None
    try:
        # axis: with the hook on, the commit the session starts on must carry it; unreadable is not ready
        conditions["dependencyHook"] = cloud_setup_text.branch_hook_gap(
            cwd, root, commit, adopted) is None
    except Exception:
        conditions["dependencyHook"] = False
    try:
        # axis: the calibration matches only when the placed stamp equals the recorded one — see bite-proof record wo_a_place_call
        conditions["calibration"] = (stamp_fn or cloud_check._placed_stamp)(cwd, root) == record.get(
            "calibrationStamp")
    except Exception:
        conditions["calibration"] = False
    conditions["platform"] = reported.get("unreachable") is not True
    for name in forced:
        conditions[name] = False
    return _result(
        conditions, setting=setting, account=seen["account"], environment=record.get("environment"),
        cloud_version=cloud_version, advisor_version=advisor,
        picks_up=record.get("picksUpVersion"), checked_at=record.get("checkedAt"),
        failed_check=failed)


def readiness(cwd, *, account=None, advisor_version=None, reported=None, today=None,
              root=None, env=None, stamp_fn=None, persist_backfill=True, commit=None,
              adopted=None):
    """Whether the cloud can take a build now, with every condition and the facts behind them.
    Never raises; any unexpected failure reads as not ready.

    The result's keys are ready, reason, conditions, setting, account, environment, cloudVersion,
    advisorVersion, picksUpVersion, checkedAt and failedCheck. `failedCheck` is None unless the
    setup is on record and the latest check for the account failed; then it is the failed parts
    the check left (an empty list when that note cannot be read). A failed check forces its parts'
    conditions false: the reviewer part the pass, the version part the version, the calibration
    part the calibration, and any other part, or a marker that cannot be read, the setup.

    `commit` is the commit the cloud session starts on (the checkout's HEAD when None); with the
    dependency hook on, it must carry the hook. `adopted` is, for a launch that adopts a branch, the
    adopted head, whose setup inputs must match those at `commit`."""
    seen = {"setting": False, "account": None}
    try:
        return _readiness(
            cwd, account, advisor_version, reported, today, root, env, stamp_fn, seen,
            persist_backfill=persist_backfill, commit=commit, adopted=adopted)
    except Exception:
        return _result(_all_false(), setting=seen["setting"], account=seen["account"])
