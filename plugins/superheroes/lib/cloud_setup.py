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
REASON_CHECK_FAILED = "cloud-check-failed"

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
    "check-failed": (
        "Cloud builds can't be switched on yet: the last check of this project's cloud setup "
        'failed. Fix what it named, then say "check again".'
    ),
}


def switch_message(kind, project_name):
    """The approved words for switching cloud builds ``on``, ``off``, the ``refused`` switch-on, or the
    ``check-failed`` switch-on refused because the last check of the setup failed."""
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


def read(cwd, account, root=None):
    """The cloud-builds setting and the setup record's state for ``account``. Never raises."""
    setting = False
    try:
        import project_config

        got = project_config.get_item(cwd, project_config.CLOUD_BUILDS_SLUG, root=root)
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


def _lapse_line(days, lapses, next_pass_days):
    """(mark, line) for a pass with ``days`` left until it lapses on ``lapses``."""
    when = "%d %s" % (lapses.day, lapses.strftime("%b"))
    renew = "Run the pass command and paste the new pass into the environment."
    # axis: a pass that will not last to the next gardening pass is marked Renew now — see bite-proof record c8_cloud_cleanup
    if days <= 0:
        return "Renew now", "Cloud reviewer pass: lapsed %s. %s" % (when, renew)
    if days <= next_pass_days:
        return "Renew now", "Cloud reviewer pass: %d %s left, lapses %s. It won't last to the next gardening pass. %s" % (
            days, "day" if days == 1 else "days", when, renew)
    return None, "Cloud reviewer pass: %d days left, lapses %s. Nothing to do." % (days, when)


def gardening_lines(cwd, next_pass_days, today=None, root=None):
    """The reviewer-pass line for the gardening pass, one per setup record in the project's store, so it
    is read for whichever Claude account the builders run on. No records, no lines. Each line is
    ``{"account", "mark", "line"}``; a record that cannot be read gives the unreadable line."""
    directory = os.path.dirname(record_path(cwd, "x", root))
    # a failed-check marker sits beside its record and is not a record
    try:
        names = sorted(n for n in os.listdir(directory)
                       if n.endswith(".json") and not n.endswith(".failed-check.json"))
    except FileNotFoundError:
        return []
    except OSError:
        return [{"account": None, "mark": None, "line": "Cloud reviewer pass: the setup record could not be read."}]
    if today is None:
        today = datetime.date.today()
    elif isinstance(today, str):
        today = datetime.date.fromisoformat(today)
    lines = []
    for name in names:
        account, record = None, None
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                account = json.load(fh)["account"]
            import cloud_check  # lazy: cloud_check imports this module
            # axis: a failed or unreadable check marker makes the saved lapse date stale, as cloud_parked reads it
            if cloud_check.read_failed_check(cwd, account, root) is not None:
                lines.append({"account": account, "mark": "Renew now", "line":
                              "Cloud reviewer pass: the last reviewer check failed, so the pass must be renewed. "
                              "Run the pass command and paste the new pass into the environment."})
                continue
            got = read(cwd, account, root)
            record = got["record"] if got["state"] == "ready" else None
        except Exception:
            record = None
        if record is None:
            lines.append({"account": account if isinstance(account, str) else None, "mark": None,
                          "line": "Cloud reviewer pass: the setup record could not be read."})
            continue
        lapses = datetime.date.fromisoformat(record["passLapses"])
        mark, line = _lapse_line((lapses - today).days, lapses, next_pass_days)
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
