"""Which cloud environment the owner just picked with Claude Code's `/remote-env` picker.

  cloud_environment.py snapshot [--cwd D]
  cloud_environment.py pick [--before ID] [--confirmed ID] [--cwd D]

Claude Code saves the pick as `remote.defaultEnvironmentId` in the user settings file of the
account it runs on. `snapshot` reads that value before the owner picks; `pick` reads it again and
returns the id only when it is a well-formed environment id and differs from the `--before` value.
A value that is missing or unchanged means no pick was made. On a retry after a failed check the
caller passes `--confirmed` (the id the first pick returned): an unchanged value equal to it is the
same environment kept, not a missing pick.

On a machine where several Claude accounts share one settings file, the second read is made right
after the pick, because another account's pick in between would be read as this one's. Standard
library plus `config_dir` and `engine_adapter`. Every public function returns a plain dict and
never raises; nothing here prints, logs or writes a file except the one result line of the command
line.
"""
import argparse
import json
import os
import sys

import config_dir
import engine_adapter

SETTINGS_FILENAME = "settings.json"

_ASK_AGAIN = ("I can't see a new pick yet. In Claude Code on this account, run /remote-env, choose "
              "the environment you made for this project by its name, and tell me when it's done.")
_PICKED = "Got it: I can see the environment you picked."
_UNREADABLE = ("I can't read this account's Claude Code settings, so I can't see which environment "
               "you picked. Check that Claude Code's settings file on this machine is readable, "
               "then tell me and I'll look again.")
_BEFORE_INVALID = "The value read before the pick is not an environment id."
_CONFIRMED_INVALID = "The environment confirmed earlier is not an environment id."
_KEPT = "Got it: I can see you kept the same environment."


def _is_id(value):
    return (isinstance(value, str)
            and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(value) is not None)


def settings_path(env=None, cwd=None):
    """The account's Claude Code settings file, or None when no config directory resolves."""
    try:
        directory = config_dir.resolve(env, cwd)
        if directory is None:
            return None
        return os.path.join(directory, SETTINGS_FILENAME)
    except Exception:
        return None


def _read(env, cwd):
    """(readable, id): readable is False when the file exists but cannot be understood; id is the
    well-formed value or None when none is set."""
    path = settings_path(env, cwd)
    if path is None:
        return False, None
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return True, None
    except OSError:
        return False, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return False, None
    if not isinstance(data, dict):
        return False, None
    remote = data.get("remote")
    if not isinstance(remote, dict):
        return True, None
    value = remote.get("defaultEnvironmentId")
    if not _is_id(value):
        return True, None
    return True, value


def snapshot(env=None, cwd=None):
    """Read the current value. Never raises."""
    try:
        readable, value = _read(env, cwd)
        if not readable:
            return {"action": "refused", "reason": "settings-unreadable", "environment": None,
                    "message": _UNREADABLE}
        if value is None:
            return {"action": "read", "reason": "none-set", "environment": None}
        return {"action": "read", "reason": None, "environment": value}
    except Exception:
        return {"action": "refused", "reason": "settings-unreadable", "environment": None,
                "message": _UNREADABLE}


def pick(before=None, confirmed=None, env=None, cwd=None):
    """Read again and compare with `before`. Returns an id only for a new, well-formed value, or for
    an unchanged one equal to `confirmed` (the retry keeping its environment). Never raises."""
    try:
        if confirmed is not None and not _is_id(confirmed):
            return {"action": "refused", "reason": "confirmed-invalid", "environment": None,
                    "message": _CONFIRMED_INVALID}
        if before is not None and not _is_id(before):
            return {"action": "refused", "reason": "before-invalid", "environment": None,
                    "message": _BEFORE_INVALID}
        readable, value = _read(env, cwd)
        if not readable:
            return {"action": "not-picked", "reason": "settings-unreadable", "environment": None,
                    "message": _UNREADABLE}
        if value is None:
            return {"action": "not-picked", "reason": "pick-missing", "environment": None,
                    "message": _ASK_AGAIN}
        if value == before and confirmed is not None and value == confirmed:
            return {"action": "picked", "reason": "kept-confirmed", "environment": confirmed,
                    "message": _KEPT}
        if value == before:
            return {"action": "not-picked", "reason": "pick-unchanged", "environment": None,
                    "message": _ASK_AGAIN}
        return {"action": "picked", "reason": None, "environment": value, "message": _PICKED}
    except Exception:
        return {"action": "not-picked", "reason": "settings-unreadable", "environment": None,
                "message": _UNREADABLE}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_environment.py")
    parser.add_argument("verb", choices=["snapshot", "pick"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--before", default=None)
    parser.add_argument("--confirmed", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    cwd = os.path.abspath(args.cwd or os.getcwd())
    if args.verb == "snapshot":
        result = snapshot(cwd=cwd)
    else:
        result = pick(before=args.before, confirmed=args.confirmed, cwd=cwd)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if result["action"] in ("read", "picked") else 1


if __name__ == "__main__":
    sys.exit(main())
