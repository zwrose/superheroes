"""Which cloud environment the owner just picked with Claude Code's `/remote-env` picker.

  cloud_environment.py snapshot [--cwd D]
  cloud_environment.py pick [--before ID] [--confirmed ID] [--cwd D]
  cloud_environment.py compare --environment ID [--moving] [--cwd D]

Claude Code saves the pick as `remote.defaultEnvironmentId` in the user settings file of the
account it runs on. `snapshot` reads that value before the owner picks; `pick` reads it again and
returns the id only when it is a well-formed environment id and differs from the `--before` value.
A value that is missing or unchanged means no pick was made. On a retry after a failed check the
caller passes `--confirmed` (the id the first pick returned): an unchanged value equal to it is the
same environment kept, not a missing pick.

On a machine where several Claude accounts share one settings file, the second read is made right
after the pick, because another account's pick in between would be read as this one's. Standard
library plus `cloud_setup`, `config_dir` and `engine_adapter`. Every public function returns a plain
dict and never raises; nothing here prints, logs or writes a file except the one result line of the
command line.

`compare` runs just before a step uses an environment id and says whether it is the id about to be
used, so no step runs against an environment other than the one the owner picked. Once the account
has a setup record (written only after a passed check naming a picked id), the record's id matches
without reading the picker, because several accounts on one machine share the picker's one value,
and any other id is refused unless the owner is moving the account to another environment
(`--moving`). With no record, or on a move, the id is compared with the picker's current value.
"""
import argparse
import json
import os
import sys

import cloud_setup
import config_dir
import engine_adapter

SETTINGS_FILENAME = "settings.json"

_ASK_AGAIN = ("I can't see a new pick yet. In Claude Code on this account, run /remote-env, choose "
              "the environment you made for this project by its name, and tell me when it's done.")
_ALREADY_PICKED = ("Claude Code already had an environment picked, and it's still the same one. If "
                   "the environment shown as picked in /remote-env is the one you made for this "
                   "project, say it's that one and I'll use it. Otherwise pick this project's "
                   "environment and tell me.")
_PICKED = "Got it: I can see the environment you picked."
_UNREADABLE = ("I can't read this account's Claude Code settings, so I can't see which environment "
               "you picked. Check that Claude Code's settings file on this machine is readable, "
               "then tell me and I'll look again.")
_BEFORE_INVALID = "The value read before the pick is not an environment id."
_CONFIRMED_INVALID = "The environment confirmed earlier is not an environment id."
_KEPT = "Got it: I can see you kept the same environment."
_MISMATCHED = ("The environment picked in /remote-env is a different one from the one I was about "
               "to use. The sitting will use the picked one.")
_RECORDED_DIFFERS = ("The environment I was about to use is not the one this account's cloud setup "
                     "recorded. The sitting will use the recorded one. If you're moving this account "
                     "to another environment, tell me and pick it with /remote-env.")
_UNCHECKED = ("I can't confirm which environment is picked in /remote-env, so I'm stopping here. "
              "Check that Claude Code's settings file on this machine is readable and that an "
              "environment shows as picked in /remote-env, then tell me and I'll look again.")


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
    remote = data.get(engine_adapter.CLOUD_SETTINGS_SECTION)
    if not isinstance(remote, dict):
        return True, None
    value = remote.get(engine_adapter.CLOUD_SETTINGS_ENVIRONMENT_KEY)
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
                    "message": _ALREADY_PICKED if confirmed is None else _ASK_AGAIN}
        return {"action": "picked", "reason": None, "environment": value, "message": _PICKED}
    except Exception:
        return {"action": "not-picked", "reason": "settings-unreadable", "environment": None,
                "message": _UNREADABLE}


def _unchecked(reason):
    return {"action": "unchecked", "reason": reason, "environment": None, "message": _UNCHECKED}


def _recorded(env, cwd, root):
    """The environment this account's setup record names, or None when it has no valid record."""
    if cwd is None:
        return None
    account = cloud_setup.launching_account(env, cwd)
    if account is None:
        return None
    return cloud_setup.recorded_environment(cwd, account, root)


def compare(environment, env=None, cwd=None, root=None, moving=False):
    """Compare the id about to be used with the account's setup record, or, with no record or on a
    move (`moving`), with the one the picker holds now. Never raises."""
    try:
        if not _is_id(environment):
            return _unchecked("environment-invalid")
        recorded = None if moving else _recorded(env, cwd, root)
        # axis: only the id the account's setup record names matches without the picker — see bite-proof record c1918_recorded_environment.md
        if recorded is not None and environment == recorded:
            return {"action": "matched", "reason": "recorded", "environment": environment}
        # axis: a recorded account refuses any other id unless the owner is moving it — see bite-proof record c1918_recorded_environment.md
        if recorded is not None:
            return {"action": "mismatched", "reason": "recorded-differs", "environment": recorded,
                    "message": _RECORDED_DIFFERS}
        readable, current = _read(env, cwd)
        if not readable or current is None:
            return _unchecked("pick-unreadable")
        if environment == current:
            return {"action": "matched", "reason": None, "environment": current}
        return {"action": "mismatched", "reason": "picked-differs", "environment": current,
                "message": _MISMATCHED}
    except Exception:
        return _unchecked("compare-failed")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_environment.py")
    parser.add_argument("verb", choices=["snapshot", "pick", "compare"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--before", default=None)
    parser.add_argument("--confirmed", default=None)
    parser.add_argument("--environment", default=None)
    parser.add_argument("--moving", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    cwd = os.path.abspath(args.cwd or os.getcwd())
    if args.verb == "snapshot":
        result = snapshot(cwd=cwd)
    elif args.verb == "compare":
        result = compare(args.environment, cwd=cwd, moving=args.moving)
    else:
        result = pick(before=args.before, confirmed=args.confirmed, cwd=cwd)
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0 if result["action"] in ("read", "picked", "matched") else 1


if __name__ == "__main__":
    sys.exit(main())
