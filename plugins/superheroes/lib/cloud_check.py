"""The cloud-builds setup sitting: the owner's instructions, the check that runs in the cloud, and
the judgment of that check on the owner's machine.

  cloud_check.py setup-message [--cwd D] [--root D] [--project-name N]
  cloud_check.py sign-in [--cwd D] [--root D] [--project-name N]
  cloud_check.py report [--cwd D] [--root D] [--nonce N]
  cloud_check.py judge --environment E --nonce N (--line TEXT | --line-file F) [--account A]
  cloud_check.py setup-text [--cwd D] [--root D] [--project-name N]

`report` runs inside the cloud session and prints one marked line saying what that session holds.
`judge` runs on the owner's machine, reads that line out of whatever text carries it, and writes
the setup record only when every part of the report agrees with this machine. Any other result
writes no record, and a project whose cloud-builds setting is on has it switched off through the
setting's one write path. A passed check never changes the setting.

Standard library plus the plugin's own lib modules. Every public function returns a plain dict and
never raises for an expected failure; an expected failure is a refusal with a `reason` token and one
plain sentence. No function here prints, logs or returns a reviewer pass.
"""
import argparse
import datetime
import json
import os
import re
import sys

import cloud_pass
import cloud_setup
import cloud_setup_text
import core_md
import engine_adapter
import mode_registry
import project_config

PASS_LIFETIME_DAYS = 10
MARKER = "SUPERHEROES-CLOUD-CHECK"
REPORT_SCHEMA = "cloud-check-report/1"
REPORT_FIELDS = ("schema", "nonce", "environment", "pluginVersion", "placedStamp", "stampFile",
                 "repoStamp", "confirmation")

_NONCE_RE = re.compile(r"[A-Za-z0-9]{8,64}")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

_SETUP_MESSAGE = (
    "**Setting up cloud builds for {project}.** You do these by hand, once. It takes about ten "
    "minutes.\n"
    "\n"
    "1. Make a cloud environment for this project on claude.ai, then copy its id from the "
    "environment's page and paste it here. My check and every build name this environment by that "
    "id, so your account's default never changes.\n"
    "2. Paste the setup text into it. I've written it below.\n"
    "3. Sign in once to the reviewer on your machine, with a sign-in kept apart from your main one. "
    "The pass is made from it. You only do this the first time on this account, and I'll walk you "
    "through it.\n"
    "4. Paste the reviewer pass into the environment. Run the pass command on your machine and it "
    "puts the pass on your clipboard.\n"
    "\n"
    "**Two things to know before you start.**\n"
    "\n"
    "The reviewer pass will sit in that environment's settings, and any session started in that "
    "environment can read it. It is a separate sign-in from your main one, it cannot renew itself, "
    "and it stops working after {days} days.\n"
    "\n"
    "Cloud builders do not get your personal instructions or permission rules. They follow this "
    "project's rules and the plugin's rules, and nothing else.\n"
    "\n"
    "Tell me when they're done and I'll run a short check.\n"
    "\n"
    "**Setup text** {header}\n"
    "\n"
    "A block to copy and paste. It holds no secret. The pass never goes in here. If this project "
    "needs its own tools in the cloud, such as a language runtime or a browser, add their install "
    "steps directly under the line that reads \"{marker}\"."
)

_SETUP_TEXT_MESSAGE = (
    "**Setup text** {header}\n"
    "\n"
    "Paste this over the whole setup-script field of the cloud environment. It holds no secret. "
    "The pass never goes in here."
)

_SIGN_IN_WALK = (
    "The reviewer needs its own sign-in on this machine, kept apart from your main one. Run this in "
    "a terminal and finish the sign-in in your browser:\n"
    "\n"
    "    {home_env}=\"{home}\" codex login\n"
    "\n"
    "Tell me when it's done and I'll check it."
)
_SIGN_IN_IN_PLACE = "The separate reviewer sign-in is in place."

_SAME_FIX = "paste the new setup text into the environment"
# part -> (sentence, fix), in the order the parts are reported
_PARTS = (
    ("environment",
     "The check ran in a different environment from the one whose id you gave me, or that "
     "environment has no pass block in it yet.",
     "check the id on the environment's page, run the pass command with that id and paste the "
     "block into the environment"),
    ("version", "The cloud's plugin is {cloud} and mine is {mine}.", _SAME_FIX),
    ("calibration", "The cloud's calibration doesn't match this machine's.", _SAME_FIX),
    ("reviewer", "The reviewer did not answer, so the pass is missing or was pasted wrong.",
     "paste a fresh pass into the environment"),
    ("record", "The check passed, but I could not write the setup record on this machine.",
     "tell me so I can look at the store"),
    ("setting", "I could not switch cloud builds off.", "switch them off in configure"),
)
_SWITCHED_OFF = " They were on for this project, so I've switched them off."

_PASSED = (
    "**The check passed.**\n"
    "\n"
    "- The cloud's plugin is {version}, the same as mine.\n"
    "- Its calibration matches this machine's.\n"
    "- The reviewer answered.\n"
    "\n"
)
_PASSED_OFF = "Cloud builds are ready for {project} and still switched off. " \
              "Say \"turn cloud builds on\" when you want them."
_PASSED_ON = "Cloud builds are ready for {project}, and they're already on."

_UNREAD = (
    "**The check did not report back.** I could not read a result from the check session.\n"
    "\n"
    "Cloud builds stay off.{switched} Say \"check again\" and I'll run it once more."
)


def _environment_ok(value):
    return (isinstance(value, str)
            and engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(value) is not None)


def _project(cwd, project_name):
    return project_name or cloud_setup_text._project_name(cwd)


def _compose(cwd, project_name, root, env, now):
    return cloud_setup_text.compose(cwd, now=now, project_name=project_name, root=root, env=env)


def _compose_refusal(result):
    return dict(result, message=result.get("detail") or "The setup text could not be written.")


def setup_message(cwd, *, project_name=None, root=None, env=None, now=None):
    """The owner's four hand steps, with the setup text beside them."""
    composed = _compose(cwd, project_name, root, env, now)
    if composed.get("action") != "written":
        return _compose_refusal(composed)
    message = _SETUP_MESSAGE.format(
        project=_project(cwd, project_name), header=composed["header"],
        marker=cloud_setup_text.TOOL_STEPS_MARKER, days=PASS_LIFETIME_DAYS)
    return {"action": "written", "message": message, "setupText": composed["text"],
            "header": composed["header"], "signedIn": sign_in(env)["signedIn"]}


def sign_in(env=None):
    """Whether the separate reviewer sign-in exists and is not the main one. Reads no token and
    opens no file."""
    env = os.environ if env is None else env
    separate = cloud_pass._separate_signin_path(env)
    try:
        # axis: the main sign-in never counts as the separate one
        present = os.path.isfile(separate) and \
            os.path.realpath(separate) != os.path.realpath(cloud_pass._default_signin_path(env))
    except Exception:
        present = False
    if present:
        return {"action": "checked", "signedIn": True, "message": _SIGN_IN_IN_PLACE}
    message = _SIGN_IN_WALK.format(home_env=cloud_pass._CODEX_HOME_ENV,
                                   home=os.path.dirname(separate))
    return {"action": "checked", "signedIn": False, "message": message}


def setup_text(cwd, *, project_name=None, root=None, env=None, now=None):
    """New setup text on request."""
    composed = _compose(cwd, project_name, root, env, now)
    if composed.get("action") != "written":
        return _compose_refusal(composed)
    return {"action": "written", "message": _SETUP_TEXT_MESSAGE.format(header=composed["header"]),
            "setupText": composed["text"], "header": composed["header"]}


def repo_calibration_stamp(cwd):
    """The stamp of the calibration the repository itself carries: every regular file under the
    repository's calibration directory, keyed by path relative to it, with the cloud-builds setting
    left out of the core file. `none` when the repository has no such directory."""
    core_rel = core_md.in_repo_core_rel_path()
    directory = os.path.join(core_md._repo_root(cwd), os.path.dirname(core_rel))
    if not os.path.isdir(directory):
        return "none"

    def fail(error):
        raise error

    files = {}
    for top, _dirs, names in os.walk(directory, onerror=fail):
        for name in names:
            path = os.path.join(top, name)
            if not os.path.isfile(path):
                continue
            rel = os.path.relpath(path, directory).replace(os.sep, "/")
            with open(path, "rb") as fh:
                data = fh.read()
            files[rel] = cloud_setup_text._without_setting(data) \
                if rel == os.path.basename(core_rel) else data
    return cloud_setup.calibration_stamp(files)


def _placed_stamp(cwd, root):
    return cloud_setup.calibration_stamp(cloud_setup_text.stamped_files(cwd, root))


def _or_none(fn, *args):
    try:
        return fn(*args)
    except Exception:
        return None


def _stamp_file(cwd, root):
    path = os.path.join(mode_registry.project_store_dir(cwd, root), cloud_setup_text.STAMP_FILE)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()


def report(env=None, cwd=None, root=None, nonce=None, confirm_fn=None):
    """What this cloud session holds, as the object the marked line carries. Never raises."""
    env = os.environ if env is None else env
    cwd = os.getcwd() if cwd is None else cwd
    environment = env.get(cloud_pass.ENVIRONMENT_ENV)
    if not _environment_ok(environment):
        environment = None
    try:
        confirmation = (cloud_pass.confirm if confirm_fn is None else confirm_fn)(env)
    except Exception:
        confirmation = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": False,
                        "passLapses": None, "reason": "confirm-raised"}
    return {
        "schema": REPORT_SCHEMA,
        "nonce": nonce if isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce) else None,
        "environment": environment,
        "pluginVersion": _or_none(cloud_setup_text._plugin_version),
        "placedStamp": _or_none(_placed_stamp, cwd, root),
        "stampFile": _or_none(_stamp_file, cwd, root),
        "repoStamp": _or_none(repo_calibration_stamp, cwd),
        "confirmation": confirmation,
    }


def report_line(report_object):
    """The one line `report` prints: the marker, one space, the object as compact sorted JSON."""
    return MARKER + " " + json.dumps(report_object, sort_keys=True, separators=(",", ":"),
                                     default=str)


def _nonce_is(obj, nonce):
    # axis: a report answers only the check that was started with this nonce
    return isinstance(obj, dict) and obj.get("nonce") == nonce


def _find_report(text, nonce):
    """The one report object that carries `nonce`, or None when there is none or two disagree."""
    found = []
    for line in text.splitlines():
        line = line.lstrip(" >`").rstrip("` ")
        if not line.startswith(MARKER + " {"):
            continue
        body = line[len(MARKER) + 1:]
        try:
            obj = json.loads(body)
        except Exception:
            continue
        if _nonce_is(obj, nonce):
            found.append((body, obj))
    if not found or any(body != found[0][0] for body, _ in found):
        return None
    return found[0][1]


def _readable(obj, nonce):
    confirmation = obj.get("confirmation") if isinstance(obj, dict) else None
    return (isinstance(obj, dict) and obj.get("schema") == REPORT_SCHEMA
            and all(field in obj for field in REPORT_FIELDS) and _nonce_is(obj, nonce)
            and isinstance(confirmation, dict)
            and confirmation.get("schema") == cloud_pass.CONFIRMATION_SCHEMA
            and isinstance(confirmation.get("reviewerAnswered"), bool))


def _lapses_ok(lapses, today):
    if not (isinstance(lapses, str) and _DATE_RE.fullmatch(lapses)):
        return False
    try:
        return datetime.date.fromisoformat(lapses) >= today
    except ValueError:
        return False


def _judge_parts(obj, environment, cwd, root, today):
    """(results, local placed stamp or None)."""
    local_version = _or_none(cloud_setup_text._plugin_version)
    local_placed = _or_none(_placed_stamp, cwd, root)
    local_repo = _or_none(repo_calibration_stamp, cwd)
    confirmation = obj["confirmation"]
    # axis: the pass is accepted only when the reviewer answered and the pass has not lapsed
    reviewer = confirmation["reviewerAnswered"] is True and _lapses_ok(
        confirmation.get("passLapses"), today)
    # axis: the check must have run in the environment whose id the owner gave
    environment_ok = obj["environment"] == environment
    # axis: the cloud's plugin must be the version this machine runs
    version_ok = isinstance(obj["pluginVersion"], str) and obj["pluginVersion"] == local_version
    computed = local_placed is not None and local_repo is not None
    # axis: the placed calibration the cloud holds must be the one this machine would place
    placed_ok = obj["placedStamp"] == local_placed
    # axis: the stamp file is absent exactly when nothing was placed, else it equals the local stamp
    file_ok = obj["stampFile"] is None if local_placed == "none" else obj["stampFile"] == local_placed
    # axis: the calibration the repository carries must match this machine's
    repo_ok = obj["repoStamp"] == local_repo
    return {
        "versionMatches": version_ok,
        "calibrationMatches": computed and placed_ok and file_ok and repo_ok,
        "reviewerAnswered": reviewer,
        "environmentMatches": environment_ok,
    }, local_placed


def _switch_off(cwd, account, root, project_name, set_fn):
    """(was on, switched off). A refused or raising write is not switched off."""
    if cloud_setup.read(cwd, account, root)["setting"] is not True:
        return False, False
    set_fn = project_config.set_item if set_fn is None else set_fn
    try:
        got = set_fn(cwd, project_config.CLOUD_BUILDS_SLUG, False, root=root,
                     project_name=project_name)
    except Exception:
        return True, False
    return True, isinstance(got, dict) and got.get("action") in ("written", "noop")


def _failed_message(parts, switched, cloud_version, local_version):
    sentences = []
    for name, sentence, _fix in _PARTS:
        if name in parts:
            sentences.append(sentence.format(
                cloud="not installed" if cloud_version is None else cloud_version,
                mine="unknown" if local_version is None else local_version))
    count = "one part" if len(parts) == 1 else "%d parts" % len(parts)
    fixes = []
    for name, _sentence, fix in _PARTS:
        if name in parts and fix not in fixes:
            fixes.append(fix)
    return ("**The check failed on %s.** %s\n\nCloud builds stay off.%s To fix it, %s and say "
            "\"check again\"." % (count, " ".join(sentences), _SWITCHED_OFF if switched else "",
                                  ", then ".join(fixes)))


def judge(cwd, line, *, environment, nonce, account=None, root=None, env=None, now=None,
          project_name=None, set_fn=None, record_fn=None):
    """Read the report line out of `line` and decide. The setup record is written only when the
    environment, the plugin version, the calibration and the reviewer's answer all agree with this
    machine; every other result writes none and switches an on cloud-builds setting off."""
    name = _project(cwd, project_name)
    today = cloud_setup_text._utc_date(now)
    obj = None
    if (_environment_ok(environment) and isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce)
            and isinstance(line, str)):
        found = _find_report(line, nonce)
        obj = found if _readable(found, nonce) else None
    if obj is None:
        was_on, off = _switch_off(cwd, account, root, name, set_fn)
        failed = ["unread"] + (["setting"] if was_on and not off else [])
        return {"action": "unread", "results": dict.fromkeys(
                    ("versionMatches", "calibrationMatches", "reviewerAnswered",
                     "environmentMatches")),
                "failedParts": failed, "recordWritten": False, "settingSwitchedOff": off,
                "message": _UNREAD.format(switched=_SWITCHED_OFF if off else "")}

    results, local_placed = _judge_parts(obj, environment, cwd, root, today)
    failed = [part for part, key in (("environment", "environmentMatches"),
                                     ("version", "versionMatches"),
                                     ("calibration", "calibrationMatches"),
                                     ("reviewer", "reviewerAnswered")) if not results[key]]
    written = False
    who = None
    if not failed:
        who = account if account is not None else cloud_setup.launching_account(env, cwd)
        try:
            if who is not None:
                # axis: a refused or raising record write is never reported as a pass
                got = (cloud_setup.record_check if record_fn is None else record_fn)(
                    cwd, account=who, environment=environment, plugin_version=obj["pluginVersion"],
                    picks_up_version=cloud_setup_text.PICKS_UP_VERSION_BY_ITSELF,
                    calibration_stamp=local_placed, calibration_date=today.isoformat(),
                    pass_lapses=obj["confirmation"]["passLapses"], checked_at=today.isoformat(),
                    root=root)
                written = isinstance(got, dict) and got.get("action") == "written"
        except Exception:
            written = False
        if not written:
            failed.append("record")

    if failed:
        # axis: a failed check leaves cloud builds off
        was_on, off = _switch_off(cwd, account, root, name, set_fn)
        if was_on and not off:
            failed.append("setting")
        return {"action": "failed", "results": results, "failedParts": failed,
                "recordWritten": written, "settingSwitchedOff": off,
                "message": _failed_message(failed, off, obj["pluginVersion"],
                                           _or_none(cloud_setup_text._plugin_version))}
    on = cloud_setup.read(cwd, who, root)["setting"] is True
    ending = (_PASSED_ON if on else _PASSED_OFF).format(project=name)
    return {"action": "passed", "results": results, "failedParts": [], "recordWritten": True,
            "settingSwitchedOff": False,
            "message": _PASSED.format(version=obj["pluginVersion"]) + ending}


def _print(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 1 if result.get("action") in ("refused", "failed", "unread") else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_check.py")
    parser.add_argument("verb", choices=["setup-message", "sign-in", "report", "judge",
                                         "setup-text"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--nonce", default=None)
    parser.add_argument("--environment", default=None)
    parser.add_argument("--account", default=None)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--line", default=None)
    source.add_argument("--line-file", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    cwd = args.cwd or os.getcwd()
    if args.verb == "report":
        sys.stdout.write(report_line(report(cwd=cwd, root=args.root, nonce=args.nonce)) + "\n")
        return 0
    if args.verb == "sign-in":
        return _print(sign_in())
    if args.verb == "setup-message":
        return _print(setup_message(cwd, project_name=args.project_name, root=args.root))
    if args.verb == "setup-text":
        return _print(setup_text(cwd, project_name=args.project_name, root=args.root))
    text = args.line
    if args.line_file is not None:
        try:
            with open(args.line_file, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeError):
            text = None
    return _print(judge(cwd, text, environment=args.environment, nonce=args.nonce,
                        account=args.account, root=args.root, project_name=args.project_name))


if __name__ == "__main__":
    sys.exit(main())
