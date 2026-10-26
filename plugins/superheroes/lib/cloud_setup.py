#!/usr/bin/env python3
"""The one reader and the one write path for a project's cloud setup record.

Stdlib plus plugin imports only. A setup counts as ready for an account only when a fully valid
record naming exactly that account can be read; every other outcome reads as not ready. The
record holds identifiers, versions, a content stamp and dates, never a credential or a secret."""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import config_dir  # noqa: E402
import mode_registry  # noqa: E402

SCHEMA = "cloud-setup/1"
RECORD_FIELDS = (
    "schema",
    "account",
    "environment",
    "pluginVersion",
    "picksUpVersion",
    "calibrationStamp",
    "calibrationDate",
    "passLapses",
    "checkedAt",
)

REASON_MISSING = "cloud-setup-missing"
REASON_MALFORMED_VALUE = "malformed-value"
REASON_UNKNOWN_FIELD = "unknown-field"
REASON_SECRET_SHAPED = "secret-shaped-value"
REASON_STORE_LOCKED = "store-locked"
REASON_WRITE_FAILED = "write-failed"
REASON_ENVIRONMENT_MISMATCH = "environment-mismatch"

FAILED_CHECK_SCHEMA = "cloud-check-failed/1"
FAILED_CHECK_SUFFIX = ".failed-check.json"

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@:-]*$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_STAMP_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SIGNED_TOKEN_PATTERN = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.")
_SECRET_PREFIXES = (
    "sk-", "sess-", "rt_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_",
    "xoxa-", "xoxb-", "xoxp-", "xoxr-", "xoxs-",
)
_SECRET_MAX_LENGTH = 128
_ACCOUNT_FILE = ".claude.json"

_MESSAGES = {
    "on": (
        "Cloud builds are on for {project}. From the next launch, every build that can run "
        "in the cloud will.\n\n"
        'Say "this one local" at any launch to keep a build on your machine.'
    ),
    "off": (
        "Cloud builds are off for {project}. Builds run on your machine, as before.\n\n"
        "The cloud setup is kept, so switching back on needs no new setup."
    ),
    "refused": (
        "Cloud builds can't be switched on yet. This project has no cloud setup on this "
        'Claude account. Say "set up cloud builds" and I\'ll walk you through it.'
    ),
}

# part -> (what the check failed on, the short fix), for the paused wording; one home
PAUSED_PARTS = {
    "environment": ("the cloud environment", "pick this project's environment again with /remote-env and paste the pass block into it"),
    "version": ("the plugin version", "paste the new setup text into the environment"),
    "pin": ("the plugin pin", "commit a current plugin pin on the branch builds start from"),
    "hook": ("the dependency hook", "commit the dependency hook files on the branch builds start from"),
    "calibration": ("the calibration", "paste the new setup text into the environment"),
    "reviewer": ("the reviewer pass", "paste a fresh pass into the environment"),
    "identity": ("the git identity", "set the git identity variables in the environment"),
    "record": ("saving the result on this machine", "tell me so I can look at the store"),
    "unread": ("reporting back", None),
    "setting": ("an older check step", None),  # legacy part, written only by earlier plugin versions
}
PAUSED_RESUME = "They resume by themselves once the check passes."
# The report lines a launch that fell back because of a failed check ends with.
PAUSED_LINE_ON = ("Cloud builds are on but paused for this account until its setup check passes. "
                  + PAUSED_RESUME)
PAUSED_LINE_WORD = ("Cloud launches on this account are paused until its setup check passes. "
                    + PAUSED_RESUME)
_PAUSED_DAMAGED = ("last setup check failed.", 'Fix what it named, then say "check again".')
_PAUSED_NO_FIX = 'Say "check again" and I\'ll run it once more.'


def _named(names):
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def paused_parts(parts):
    """``(failed, fix)``: the failed-check sentence without its leading ``its ``, and the fix sentence,
    for a marker's ``failedParts`` (``[]`` or None for a damaged or unreadable marker). Known parts
    are named in ``PAUSED_PARTS`` order, unknown strings are skipped. Never raises."""
    try:
        given = [p for p in parts if isinstance(p, str)] if isinstance(parts, (list, tuple)) else []
        known = [p for p in PAUSED_PARTS if p in given]
        if not known:
            return _PAUSED_DAMAGED
        fixes = []
        for part in known:
            fix = PAUSED_PARTS[part][1]
            if fix is not None and fix not in fixes:
                fixes.append(fix)
        failed = "last setup check failed on %s." % _named([PAUSED_PARTS[p][0] for p in known])
        if not fixes:
            return failed, _PAUSED_NO_FIX
        return failed, "To fix it, %s, then say \"check again\"." % ", then ".join(fixes)
    except Exception:
        return _PAUSED_DAMAGED


def paused_failure(parts):
    """The clause naming what a failed check failed on and its fix, as one string. Never raises."""
    failed, fix = paused_parts(parts)
    return "its " + failed + " " + fix


def switch_message(kind, project_name, parts=None):
    """The approved words for switching cloud builds ``on``, ``off``, the ``refused`` switch-on, or
    ``on-paused``: switched on while this account's last setup check failed (``parts`` is the marker's
    failed parts, or None for a damaged one)."""
    if kind == "on-paused":
        return ("Cloud builds are on for %s, but paused for this account: " % project_name
                + paused_failure(parts) + " " + PAUSED_RESUME)
    if kind not in _MESSAGES:
        raise ValueError("unknown message kind: %r" % (kind,))
    return _MESSAGES[kind].format(project=project_name)


def calibration_stamp(files):
    """``none`` for no files, else a SHA-256 stamp over each sorted path and its content."""
    if not isinstance(files, dict):
        raise TypeError("files must be a mapping of relative path to bytes")
    for path, content in files.items():
        if not isinstance(path, str):
            raise TypeError("file path must be str")
        if not isinstance(content, bytes):
            raise TypeError("file content must be bytes")
    if not files:
        return "none"
    digest = hashlib.sha256()
    for path in sorted(files):
        content = files[path]
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _id_ok(value):
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and _ID_PATTERN.fullmatch(value) is not None
    )


def launching_account(env=None, cwd=None):
    """The launching Claude account id, or None when it cannot be read. Never raises."""
    try:
        base = dict(env if env is not None else os.environ)
        directory = config_dir.resolve(base, cwd)
        if directory is None:
            return None
        configured = base.get(config_dir.CONFIG_DIR_ENV)
        if isinstance(configured, str) and configured.strip():
            path = os.path.join(directory, _ACCOUNT_FILE)
        else:
            path = os.path.join(os.path.dirname(directory), _ACCOUNT_FILE)
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, dict):
            return None
        oauth = raw.get("oauthAccount")
        if not isinstance(oauth, dict):
            return None
        account = oauth.get("accountUuid")
        if not _id_ok(account):
            return None
        return account
    except Exception:
        return None


def record_path(cwd, account, root=None):
    """Where the setup record for ``account`` lives in the project's store."""
    name = hashlib.sha256(account.encode("utf-8")).hexdigest()[:16]
    return os.path.join(
        mode_registry.project_store_dir(cwd, root), "state", "cloud-setup", name + ".json")


def _secret_shaped(value):
    # axis: a secret-shaped string is refused before any field shape is read — see bite-proof record wo_a_cloud-setup_secret-shape
    if len(value) > _SECRET_MAX_LENGTH:
        return True
    if "{" in value or '"' in value or "-----BEGIN" in value:
        return True
    if value.lower().startswith("bearer "):
        return True
    if value.startswith(_SECRET_PREFIXES):
        return True
    return _SIGNED_TOKEN_PATTERN.match(value) is not None


def _date_ok(value):
    if not isinstance(value, str) or _DATE_PATTERN.fullmatch(value) is None:
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _lapses_ok(lapses, today):
    # axis: the date's format is the record owner's rule, not a second copy
    if not _date_ok(lapses):
        return False
    try:
        return datetime.date.fromisoformat(lapses) >= today
    except ValueError:
        return False


def _field_ok(field, value):
    if field == "schema":
        return value == SCHEMA
    if field in ("account", "environment"):
        return _id_ok(value)
    if field == "pluginVersion":
        return isinstance(value, str) and _VERSION_PATTERN.fullmatch(value) is not None
    if field == "picksUpVersion":
        return type(value) is bool
    if field == "calibrationStamp":
        return isinstance(value, str) and (
            value == "none" or _STAMP_PATTERN.fullmatch(value) is not None)
    return _date_ok(value)


def _validate(record):
    """None when ``record`` is a fully valid setup record, else ``{"reason", "field"}``."""
    if not isinstance(record, dict):
        return {"reason": REASON_MALFORMED_VALUE, "field": None}
    for key in record:
        if key not in RECORD_FIELDS:
            return {"reason": REASON_UNKNOWN_FIELD, "field": key}
    for field in RECORD_FIELDS:
        if field not in record:
            return {"reason": REASON_MALFORMED_VALUE, "field": field}
    for field in RECORD_FIELDS:
        value = record[field]
        if isinstance(value, str) and _secret_shaped(value):
            return {"reason": REASON_SECRET_SHAPED, "field": field}
    for field in RECORD_FIELDS:
        if not _field_ok(field, record[field]):
            return {"reason": REASON_MALFORMED_VALUE, "field": field}
    return None


def _refusal(finding):
    out = {"action": "refused", "reason": finding["reason"]}
    if finding["field"] is not None:
        out["field"] = finding["field"]
    return out


def _load(cwd, account, root):
    if not _id_ok(account):
        return "unreadable", None
    try:
        with open(record_path(cwd, account, root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        return "none", None
    except (OSError, ValueError, RecursionError):
        return "unreadable", None
    # axis: a record that fails validation never reads as ready — see bite-proof record wo_a_cloud-setup_record-validation
    if _validate(raw) is not None:
        return "unreadable", None
    # axis: a record for another account never reads as ready — see bite-proof record wo_a_cloud-setup_account-equality
    if raw["account"] != account:
        return "unreadable", None
    return "ready", raw


def read(cwd, account, root=None, *, persist_backfill=True):
    """The cloud-builds setting and the setup record's state for ``account``. Never raises."""
    setting = False
    try:
        import project_config

        keyword = {} if persist_backfill else {"persist_backfill": False}
        got = project_config.get_item(cwd, project_config.CLOUD_BUILDS_SLUG, root=root, **keyword)
        setting = got.get("effective") is True
    except Exception:
        setting = False
    try:
        state, record = _load(cwd, account, root)
    except Exception:
        state, record = "unreadable", None
    return {
        "setting": setting,
        "state": state,
        "ready": state == "ready",
        "record": record,
    }


def recorded_environment(cwd, account, root=None):
    """The environment a ready setup record for ``account`` names, or None. Never raises; writes
    nothing."""
    try:
        state, record = _load(cwd, account, root)
    except Exception:
        return None
    return record["environment"] if state == "ready" else None


def failed_check_path(cwd, account, root=None):
    """Where the failed-check marker for ``account`` lives: the setup record's path, beside it."""
    return record_path(cwd, account, root)[:-len(".json")] + FAILED_CHECK_SUFFIX


def read_failed_check(cwd, account, root=None):
    """The failed-check marker for ``account``: None when there is none, the marker when it reads,
    else the damaged shape. Never raises."""
    damaged = {"schema": FAILED_CHECK_SCHEMA, "failedAt": None, "failedParts": [],
               "environment": None, "damaged": True}
    try:
        path = failed_check_path(cwd, account, root)
        if not os.path.lexists(path):
            return None
        with open(path, encoding="utf-8") as fh:
            got = json.load(fh)
        # axis: a marker that exists but cannot be read is present and damaged, never absent
        if isinstance(got, dict) and got.get("schema") == FAILED_CHECK_SCHEMA:
            return got
    except Exception:
        pass
    return damaged


def _write(cwd, account, root, build):
    """The only writer: under the lock, ``build(current)`` gives ``(record, refusal)``."""
    try:
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return {"action": "refused", "reason": REASON_STORE_LOCKED}
            _state, current = _load(cwd, account, root)
            built, refusal = build(current)
            if refusal is not None:
                return refusal
            finding = _validate(built)
            if finding is not None:
                return _refusal(finding)
            if built == current:
                return {"action": "noop"}
            path = record_path(cwd, account, root)
            directory = os.path.dirname(path)
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".cloud-setup-", dir=directory, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(built, sort_keys=True, indent=2) + "\n")
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
            return {"action": "written"}
    except OSError:
        return {"action": "refused", "reason": REASON_WRITE_FAILED}


def record_check(cwd, *, account, environment, plugin_version, picks_up_version,
                 calibration_stamp, calibration_date, pass_lapses, checked_at, root=None):
    """Validate and write the whole setup record."""
    record = {
        "schema": SCHEMA,
        "account": account,
        "environment": environment,
        "pluginVersion": plugin_version,
        "picksUpVersion": picks_up_version,
        "calibrationStamp": calibration_stamp,
        "calibrationDate": calibration_date,
        "passLapses": pass_lapses,
        "checkedAt": checked_at,
    }
    finding = _validate(record)
    if finding is not None:
        return _refusal(finding)
    return _write(cwd, account, root, lambda current: (record, None))


def confirm_pass(cwd, account, lapses, *, environment=None, root=None):
    """Move only the lapse date of the ready record for ``account``."""
    if not _id_ok(account):
        return {"action": "refused", "reason": REASON_MISSING}

    def build(current):
        if current is None:
            return None, {"action": "refused", "reason": REASON_MISSING}
        # axis: a pass is confirmed only for the environment the record names — see bite-proof record wo_a_cloud-setup_environment-compare
        if environment is not None and environment != current["environment"]:
            return None, {"action": "refused", "reason": REASON_ENVIRONMENT_MISMATCH}
        return dict(current, passLapses=lapses), None

    return _write(cwd, account, root, build)


_CHECK_AGAIN = "cloud builds stay off until a check passes. Run the setup check again."
_PAUSED_ON = ("cloud builds are paused for this account until a check passes, and resume by "
              "themselves once one does. Run the setup check again.")
_SETTING_UNREAD = "I could not read whether cloud builds are on. Run the setup check again."
_RENEW = ("Run the pass command and paste the new pass into the environment. "
          "Sign the reviewer in again if the date does not move.")


def _lapse_line(days, lapses, next_pass_days, live):
    """(mark, line) for a pass with ``days`` left until it lapses on ``lapses``. ``live`` is the readiness
    rule's answer (a lapse date equal to today is still live), so gardening and launch readiness agree."""
    when = "%d %s" % (lapses.day, lapses.strftime("%b"))
    if not live:
        return "Renew now", "Cloud reviewer pass: lapsed %s. %s" % (when, _RENEW)
    # axis: a pass that will not last to the next gardening pass is marked Renew now — see bite-proof record c8b_setup_and_gardening
    if days <= 0:
        return "Renew now", "Cloud reviewer pass: lapses today, %s. It won't last to the next gardening pass. %s" % (
            when, _RENEW)
    if days <= next_pass_days:
        return "Renew now", "Cloud reviewer pass: %d %s left, lapses %s. It won't last to the next gardening pass. %s" % (
            days, "day" if days == 1 else "days", when, _RENEW)
    return None, "Cloud reviewer pass: %d days left, lapses %s. Nothing to do." % (days, when)


def _cloud_builds_setting(cwd, root):
    """The project's cloud-builds setting as it stands: True or False only when the profile was read and the
    item is well formed, else None. No profile file means cloud builds are off, since the setting lives in the
    profile. A profile file that exists but cannot be read is unknown, and `read` reports both as unparseable,
    so the core file's presence tells them apart. Never raises."""
    try:
        import core_md
        import project_config

        got = project_config.read(cwd, root, persist_backfill=False)
        if not isinstance(got, dict):
            return None
        unparseable = got.get("profileUnparseable")
        # axis: a corrupt profile is an unreadable setting, a missing one is off — see bite-proof record c8c_wo_d.md
        if unparseable is True:
            return None if os.path.lexists(core_md.core_path(cwd, root, persist_backfill=False)) else False
        if unparseable is not False:
            return None
        item = next((i for i in got["items"] if i["slug"] == project_config.CLOUD_BUILDS_SLUG), None)
        if not isinstance(item, dict) or item.get("malformed"):
            return None
        effective = item["effective"]
    except Exception:
        return None
    return effective if isinstance(effective, bool) else None


def _check_again(setting):
    """(sentence, joins with "so") saying what the owner does next, true to the current setting."""
    # axis: the line says cloud builds stay off only while the owner's setting is off; with the setting on it says the account is paused and resumes by itself
    if setting is False:
        return _CHECK_AGAIN, True
    if setting is True:
        return _PAUSED_ON, True
    return _SETTING_UNREAD, False


def gardening_lines(cwd, next_pass_days, today=None, root=None):
    """The reviewer-pass line for the gardening pass, one per setup record in the project's store, so it
    is read for whichever Claude account the builders run on. No records, no lines. Each line is
    ``{"account", "mark", "line"}``; a record that cannot be read gives the unreadable line."""
    directory = os.path.dirname(record_path(cwd, "x", root))
    # a failed-check marker sits beside its record and is not a record
    try:
        names = sorted(n for n in os.listdir(directory)
                       if n.endswith(".json") and not n.endswith(FAILED_CHECK_SUFFIX))
    except FileNotFoundError:
        return []
    except OSError:
        return [{"account": None, "mark": None, "line": "Cloud reviewer pass: the setup record could not be read."}]
    if today is None:
        today = datetime.datetime.now(datetime.timezone.utc).date()
    elif isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    lines = []
    for name in names:
        account, record, repair = None, None, None
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                found = json.load(fh)["account"]
            # axis: an account read from a record file is validated before it builds a marker path
            if not _id_ok(found):
                raise ValueError("account")
            account = found
            # axis: a failed or unreadable check marker makes the saved lapse date stale, as cloud_parked reads it
            marker = read_failed_check(cwd, account, root)
            if marker is not None:
                again, joins_with_so = _check_again(_cloud_builds_setting(cwd, root))
                failed_parts = marker.get("failedParts")
                # axis: a marker whose failedParts is not a list of strings is damaged, never iterated as valid
                well_formed = (isinstance(failed_parts, list)
                               and all(isinstance(p, str) for p in failed_parts))
                if marker.get("damaged") or not well_formed or not failed_parts or "reviewer" in failed_parts:
                    lines.append({"account": account, "mark": "Renew now", "line":
                                  "Cloud reviewer pass: the last reviewer check failed, so the pass must be renewed. "
                                  + _RENEW + " " + again[0].upper() + again[1:]})
                    continue
                repair = ("Cloud reviewer pass: the last cloud check failed on %s%s%s"
                          % (", ".join(failed_parts), ", so " if joins_with_so else ". ", again))
            got = read(cwd, account, root)
            record = got["record"] if got["state"] == "ready" else None
        except Exception:
            record = None
        if record is None:
            # a non-reviewer check failure with no readable record keeps its repair line alone
            lines.append({"account": account, "mark": None,
                          "line": repair or "Cloud reviewer pass: the setup record could not be read."})
            continue
        lapses = datetime.date.fromisoformat(record["passLapses"])
        mark, line = _lapse_line((lapses - today).days, lapses, next_pass_days,
                                 _lapses_ok(record["passLapses"], today))
        if repair is not None:
            # a non-reviewer check failure keeps the independent expiry warning beside its repair line
            mark, line = (None, repair) if mark is None else (mark, repair + " " + line)
        lines.append({"account": account, "mark": mark, "line": line})
    return lines


def _bool_arg(text):
    if text == "true":
        return True
    if text == "false":
        return False
    return text


def main(argv):
    ap = argparse.ArgumentParser(prog="cloud_setup")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("read")
    rp.add_argument("--account", default=None)

    cp = sub.add_parser("record-check")
    cp.add_argument("--account", default=None)
    cp.add_argument("--environment", default=None)
    cp.add_argument("--plugin-version", default=None)
    cp.add_argument("--picks-up-version", default=None)
    cp.add_argument("--calibration-stamp", default=None)
    cp.add_argument("--calibration-date", default=None)
    cp.add_argument("--pass-lapses", default=None)
    cp.add_argument("--checked-at", default=None)

    pp = sub.add_parser("confirm-pass")
    pp.add_argument("--account", default=None)
    pp.add_argument("--lapses", default=None)
    pp.add_argument("--environment", default=None)

    acp = sub.add_parser("account")

    gp = sub.add_parser("gardening")
    gp.add_argument("--today", default=None)
    gp.add_argument("--next-pass-days", type=int, default=None)

    for each in (rp, cp, pp, acp, gp):
        each.add_argument("--cwd", default=".")
        each.add_argument("--root", default=None)

    args = ap.parse_args(argv)
    cwd = os.path.abspath(args.cwd)

    if args.cmd == "gardening":
        if args.next_pass_days is None or args.next_pass_days <= 0:
            sys.stdout.write(json.dumps({"reason": "next-pass-days-invalid"}, indent=2) + "\n")
            return 1
        if args.today is not None and not _date_ok(args.today):
            sys.stdout.write(json.dumps({"reason": "today-invalid"}, indent=2) + "\n")
            return 1
        out = {"lines": gardening_lines(
            args.cwd, today=args.today, next_pass_days=args.next_pass_days, root=args.root)}
    elif args.cmd == "account":
        out = {"account": launching_account(cwd=cwd)}
    else:
        account = args.account
        if account is None:
            account = launching_account(cwd=cwd)
        if args.cmd == "read":
            out = read(args.cwd, account, root=args.root)
        elif args.cmd == "record-check":
            out = record_check(
                args.cwd,
                account=account,
                environment=args.environment,
                plugin_version=args.plugin_version,
                picks_up_version=_bool_arg(args.picks_up_version),
                calibration_stamp=args.calibration_stamp,
                calibration_date=args.calibration_date,
                pass_lapses=args.pass_lapses,
                checked_at=args.checked_at,
                root=args.root,
            )
        else:
            out = confirm_pass(
                args.cwd, account, args.lapses, environment=args.environment, root=args.root)

    sys.stdout.write(json.dumps(out, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
