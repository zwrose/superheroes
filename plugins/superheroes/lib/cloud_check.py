"""The cloud-builds setup sitting: the owner's instructions, the check that runs in the cloud, and
the judgment of that check on the owner's machine.

  cloud_check.py setup-message [--cwd D] [--root D] [--project-name N]
  cloud_check.py sign-in [--cwd D] [--root D] [--project-name N]
  cloud_check.py start --environment E [--cwd D] [--issue N]
  cloud_check.py report [--cwd D] [--root D] [--nonce N]
  cloud_check.py judge --environment E --nonce N (--line TEXT | --line-file F) [--account A]
  cloud_check.py setup-text [--cwd D] [--root D] [--project-name N]

`start` launches the check session on the owner's machine, always naming the environment id the
owner gave. `report` runs inside the cloud session and prints one marked line saying what that session holds.
`judge` runs on the owner's machine, reads that line out of whatever text carries it, and writes
the setup record only when every part of the report agrees with this machine. Any other result
writes no record and leaves the account's failed-check marker, which pauses cloud launches on that
account until a check passes. The cloud-builds setting is the owner's intent and is written only by
the owner's switch: no check, passed, failed or unread, ever writes it.

Standard library plus the plugin's own lib modules. Every public function returns a plain dict and
never raises for an expected failure; an expected failure is a refusal with a `reason` token and one
plain sentence. No function here prints, logs or returns a reviewer pass.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time

import cloud_dependency_hook
import cloud_pass
import cloud_plugin_pin
import cloud_setup
import cloud_setup_text
import core_md
import engine_adapter
import launch_doctrine
import mode_registry
import model_registry
import store_core

PASS_LIFETIME_DAYS = 10
MARKER = "SUPERHEROES-CLOUD-CHECK"
REPORT_SCHEMA = "cloud-check-report/1"
REPORT_FIELDS = ("schema", "nonce", "environment", "pluginVersion", "placedStamp", "stampFile",
                 "repoStamp", "confirmation")
IDENTITY_FIELD = "identity"
DIGEST_FIELD = "digest"
# The failed-check marker's reader lives in cloud_setup; these names stay importable from here.
FAILED_CHECK_SCHEMA = cloud_setup.FAILED_CHECK_SCHEMA
FAILED_CHECK_SUFFIX = cloud_setup.FAILED_CHECK_SUFFIX
failed_check_path = cloud_setup.failed_check_path
read_failed_check = cloud_setup.read_failed_check

_NONCE_RE = re.compile(r"[A-Za-z0-9]{8,64}")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")

_SETUP_MESSAGE = (
    "**Setting up cloud builds for {project}.** You do these by hand, once. It takes about ten "
    "minutes.\n"
    "\n"
    "1. Make a cloud environment for this project on claude.ai, then run /remote-env in Claude "
    "Code on this computer and pick it. I read which one you picked, so there's no id to copy, and "
    "every build names this environment itself. Once this account's first check passes, I keep the "
    "environment, so later checks need no pick unless you move this account to another one.\n"
    "2. Paste the setup text into it. I've written it below.\n"
    "3. Sign in once to the reviewer on your machine, with a sign-in kept apart from your main one. "
    "The pass is made from it. You only do this the first time on this machine, and I'll walk you "
    "through it.\n"
    "4. Paste the reviewer pass into the environment. Run the pass command on your machine and it "
    "puts the pass on your clipboard.\n"
    "\n"
    "**Two things to know before you start.**\n"
    "\n"
    "The reviewer pass will sit in that environment's settings, and any session started in that "
    "environment can read it. It is a separate sign-in from your main one, it cannot renew itself, "
    "and {expiry}.\n"
    "\n"
    "Cloud builders do not get your personal instructions or permission rules. They follow this "
    "project's rules and the plugin's rules, and nothing else.\n"
    "\n"
    "Tell me when they're done and I'll run a short check.\n"
    "\n"
    "**Setup text** {header}\n"
    "\n"
    "A block to copy and paste. It holds no secret. The pass never goes in here. If this project "
    "needs its own setup commands in the cloud, such as installing its dependencies, list them in "
    "configure (item 17, cloud setup commands) and write new setup text: a step added by hand "
    "under the line that reads \"{marker}\" is lost the next time setup text is pasted."
    " A credential never goes in a listed command: put it in the cloud environment's variables and "
    "reference it as $NAME. The setup text's secret scan catches obvious pastes and is not a "
    "guarantee."
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
    "    mkdir -p {home} && {home_env}={home} codex login\n"
    "\n"
    "Tell me when it's done and I'll check it."
)
_SIGN_IN_IS_MAIN = (
    "The reviewer home you set points at your main sign-in, so I can't use it. A pass has to come "
    "from a sign-in kept apart from your main one. Set {home_env} to a different folder, then "
    "I'll give you the sign-in command for it."
)
_EXPIRY_KNOWN = "it stops working on {date}"
_EXPIRY_UNKNOWN = "it stops working after {days} days; the exact date isn't known yet"
_SIGN_IN_IN_PLACE = "The separate reviewer sign-in is in place."

_SAME_FIX = cloud_setup.FIX_PASTE_SETUP
_PIN_FIX = ("run cloud_plugin_pin.py write on this machine, commit and push the files it names, then "
            "start a new check; if the pin already names my plugin, the cloud could not install it, "
            "and the hook's one-line message in the cloud session says why")
_PIN_MISMATCH = ("The cloud runs plugin {cloud} at commit {cloud_commit}; this project's pin names "
                 "{pin_version} at {pin_commit}, and mine is {mine}.")
_PIN_BROKEN = "This project's plugin pin hook is broken ({reason})."
# part -> (sentence, fix), in the order the parts are reported
_PARTS = (
    ("environment",
     "The check ran in a different environment from the one you picked with /remote-env, or that "
     "environment has no pass block in it yet.",
     "run /remote-env in Claude Code and pick this project's environment again, then run the pass "
     "command and paste the block into that environment"),
    ("version", "The cloud's plugin is {cloud} and mine is {mine}.", _SAME_FIX),
    ("pin", _PIN_MISMATCH, _PIN_FIX),
    # `%s` slots (not `.format` braces) are filled in `_failed_message` from `GAP_TEXT`: the gap
    # token and sentence in the first, the gap's fix in the second
    ("hook",
     "The dependency hook on the branch builds start from failed its check (`%s`): %s.", "%s"),
    ("calibration", "The cloud's calibration doesn't match this machine's.", _SAME_FIX),
    ("reviewer", "The reviewer did not answer, so the pass is missing or was pasted wrong.",
     cloud_setup.FIX_FRESH_PASS),
    ("identity",
     "The cloud session has no git identity to commit with, so a build there would stop at its "
     "first commit.",
     "set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to {name}, and GIT_AUTHOR_EMAIL and "
     "GIT_COMMITTER_EMAIL to {email}, in the environment's variables"),
    ("record", "The check passed, but I could not finish saving the result on this machine.",
     cloud_setup.FIX_RECORD),
)
_IDENTITY_UNREPORTED = "The cloud session did not report its git identity."
# The standing sentence of every check message: the failed-check marker is the paused state.
_PAUSED_STANDING = ("Cloud builds are paused for this account until the check passes. "
                    + cloud_setup.PAUSED_RESUME)
_NOT_PAUSED = ("I could not save the failed check on this machine, so cloud launches on this "
               "account are not paused. Say \"turn cloud builds off\" until the check passes.")
# said after the paused standing when this judgment's marker write failed but an earlier marker stays
_EARLIER_MARKER_STANDS = ("I could not record this check's own result, so the earlier failed "
                          "check's marker is the one that stands.")
# how many times the marker write tries a held store lock, and how long it waits between tries
_MARKER_ATTEMPTS = 5
_MARKER_WAIT = 0.2
_sleep = time.sleep

_PASSED = (
    "**The check passed.**\n"
    "\n"
    "- The cloud's plugin is {version}, the same as mine.\n"
    "- Its calibration matches this machine's.\n"
    "- The reviewer answered.\n"
    "- It has a git identity to commit with.\n"
    "\n"
)
_PASSED_OFF = "Cloud builds are ready for {project} and still switched off. " \
              "Say \"turn cloud builds on\" when you want them."
_PASSED_ON = ("Cloud builds are ready for {project} and on, so builds run in the cloud again from "
              "the next launch.")

_UNREAD = (
    "**The check did not report back.** I could not read a result from the check session.\n"
    "\n"
    "{standing} Say \"check again\" and I'll run it once more."
)

_CHECK_SESSION_PREFIX = "cloud-check-"
_CHECK_PROMPT = (
    "This is a short setup check. Edit nothing, commit nothing, push nothing, and invoke no "
    "skill.\n"
    "\n"
    "Run exactly this one command from the repository's root:\n"
    "\n"
    "python3 -B {plugin_dir}/lib/cloud_check.py report --nonce {nonce}\n"
    "\n"
    "It prints one line that starts with " + MARKER + ". If the command cannot run because that "
    "file does not exist, use this line instead, exactly as written:\n"
    "\n"
    "{fallback}\n"
    "\n"
    "Give that one line, alone and unchanged, as your final message."
)
_CHECK_POST = (
    "\n"
    "\n"
    "Also post that one line, alone inside a fenced code block, as one comment on issue #{issue} "
    "of this repository."
)
_ENVIRONMENT_NEEDED = ("I need to know which cloud environment to check. Run /remote-env in Claude "
                       "Code on this computer and pick this project's environment, then tell me, "
                       "and I'll read which one you picked.")
_NOT_STARTED = "The check session did not start: the cloud launch command could not be run."
_UNCONFIRMED = ("I could not confirm that the check session started. Look for a session named "
                "{name} in your session list; say \"check again\" and I'll start a new one.")
_STARTED = "The check session is running. I'll read its result in about a minute."


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
        marker=cloud_setup_text.TOOL_STEPS_MARKER, expiry=_expiry_phrase(env))
    return {"action": "written", "message": message, "setupText": composed["text"],
            "header": composed["header"], "signedIn": sign_in(env)["signedIn"]}


def _expiry_phrase(env):
    """When the pass will stop working: the separate sign-in's own expiry date when it can be read
    (the pass carries that same access token), else the ten-day figure with the unknown said."""
    env = os.environ if env is None else env
    try:
        separate = cloud_pass._separate_signin_path(env)
        if os.path.realpath(separate) != os.path.realpath(cloud_pass._default_signin_path(env)):
            date = cloud_pass._lapse_date(cloud_pass._read_object(separate))
            if date is not None:
                return _EXPIRY_KNOWN.format(date=date)
    except Exception:
        pass
    return _EXPIRY_UNKNOWN.format(days=PASS_LIFETIME_DAYS)


def sign_in(env=None):
    """Whether the separate reviewer sign-in exists and is not the main one. Reads no token and
    opens no file."""
    env = os.environ if env is None else env
    separate = cloud_pass._separate_signin_path(env)
    try:
        # axis: the main sign-in never counts as the separate one
        is_main = os.path.realpath(separate) == \
            os.path.realpath(cloud_pass._default_signin_path(env))
        present = os.path.isfile(separate) and not is_main
    except Exception:
        is_main, present = False, False
    if is_main:
        # axis: no login command ever targets the main sign-in's home
        return {"action": "checked", "signedIn": False,
                "message": _SIGN_IN_IS_MAIN.format(home_env=cloud_pass.SEPARATE_HOME_ENV)}
    if present:
        return {"action": "checked", "signedIn": True, "message": _SIGN_IN_IN_PLACE}
    message = _SIGN_IN_WALK.format(home_env=cloud_pass._CODEX_HOME_ENV,
                                   home=shlex.quote(os.path.dirname(separate)))
    return {"action": "checked", "signedIn": False, "message": message}


def setup_text(cwd, *, project_name=None, root=None, env=None, now=None):
    """New setup text on request."""
    composed = _compose(cwd, project_name, root, env, now)
    if composed.get("action") != "written":
        return _compose_refusal(composed)
    return {"action": "written", "message": _SETUP_TEXT_MESSAGE.format(header=composed["header"]),
            "setupText": composed["text"], "header": composed["header"]}


def repo_calibration_stamp(cwd):
    """The stamp of the calibration the repository itself carries: the calibration files directly
    under the repository's calibration directory (the `.md` layers, as the setup-text writer
    enumerates them in `cloud_setup_text._store_files`), keyed by name, with the cloud-builds
    setting left out of the core file. Subdirectories (the Guardian sweep outputs), lock files and
    editor or OS artifacts are not calibration and never change it. `none` when the repository has
    no such directory."""
    core_rel = core_md.in_repo_core_rel_path()
    directory = os.path.join(core_md._repo_root(cwd), os.path.dirname(core_rel))
    if not os.path.isdir(directory):
        return "none"
    files = {}
    # axis: only the calibration layers count; sweep outputs and machine artifacts never reach the stamp
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not name.endswith(".md") or not os.path.isfile(path):
            continue
        with open(path, "rb") as fh:
            data = fh.read()
        files[name] = cloud_setup_text._without_setting(data) \
            if name == os.path.basename(core_rel) else data
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


def _local_identity(cwd):
    """(name, email) of the identity git resolves in `cwd` on this machine, or None. Read only to
    fill in the fix line after the check has failed on the identity part; it decides nothing."""
    try:
        got = subprocess.run(["git", "-c", "user.useConfigOnly=true", "var", "GIT_AUTHOR_IDENT"],
                             cwd=cwd, capture_output=True, text=True, timeout=10)
        if got.returncode != 0:
            return None
        match = re.fullmatch(r"(.+?) <([^<>]+)> \d+ [+-]\d{4}", got.stdout.strip())
        if match is None or not match.group(1) or not match.group(2):
            return None
        return match.group(1), match.group(2)
    except Exception:
        return None


def _plugin_commit():
    """The commit of the plugin this session runs: a 40-hex string, or None when its directory is not
    a git checkout or git does not answer."""
    got = subprocess.run(["git", "-C", cloud_setup_text._plugin_root(), "rev-parse", "--verify", "HEAD"],
                         capture_output=True, text=True, timeout=10)
    commit = got.stdout.strip() if got.returncode == 0 else ""
    return commit if _COMMIT_RE.fullmatch(commit) else None


def report(env=None, cwd=None, root=None, nonce=None, confirm_fn=None, identity_fn=None):
    """What this cloud session holds, as the object the marked line carries. Never raises.
    `identity_fn(cwd)` is the test seam for the git identity check; it defaults to
    `launch_doctrine.git_identity`. `pluginCommit` is an optional field, not one a report must
    carry to be read."""
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
    try:
        identity = (identity_fn or launch_doctrine.git_identity)(cwd)
    except Exception:
        identity = {"author": False, "committer": False}
    return {
        "schema": REPORT_SCHEMA,
        "nonce": nonce if isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce) else None,
        "environment": environment,
        "pluginVersion": _or_none(cloud_setup_text._plugin_version),
        "pluginCommit": _or_none(_plugin_commit),
        "placedStamp": _or_none(_placed_stamp, cwd, root),
        "stampFile": _or_none(_stamp_file, cwd, root),
        "repoStamp": _or_none(repo_calibration_stamp, cwd),
        "confirmation": confirmation,
        IDENTITY_FIELD: identity,
    }


def _canonical(report_object):
    return json.dumps(report_object, sort_keys=True, separators=(",", ":"), default=str)


def report_digest(report_object):
    """A short digest of the report's canonical JSON, the digest field itself left out."""
    body = {k: v for k, v in report_object.items() if k != DIGEST_FIELD}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()[:32]


def report_line(report_object):
    """The one line `report` prints: the marker, one space, the object as compact sorted JSON,
    carrying a digest of everything else in it so a copy that altered any field is detectable."""
    carried = dict(report_object, **{DIGEST_FIELD: report_digest(report_object)})
    return MARKER + " " + _canonical(carried)


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
            found.append((_canonical(obj), obj))
    # axis: the launch prompt carries a fallback report; when the session transcript echoes it
    # beside a real report, the echo is not a competing result
    # axis: copies are compared as parsed objects, so JSON spacing never makes a faithful copy conflict
    fallback = _canonical(json.loads(_fallback_line(nonce)[len(MARKER) + 1:]))
    if any(body != fallback for body, _ in found):
        found = [(body, obj) for body, obj in found if body != fallback]
    if not found or any(body != found[0][0] for body, _ in found):
        return None
    return found[0][1]


def _readable(obj, nonce):
    confirmation = obj.get("confirmation") if isinstance(obj, dict) else None
    return (isinstance(obj, dict) and obj.get("schema") == REPORT_SCHEMA
            and all(field in obj for field in REPORT_FIELDS) and _nonce_is(obj, nonce)
            # axis: a report altered after it was made (any field) is not read
            and obj.get(DIGEST_FIELD) == report_digest(obj)
            and isinstance(confirmation, dict)
            and confirmation.get("schema") == cloud_pass.CONFIRMATION_SCHEMA
            and isinstance(confirmation.get("reviewerAnswered"), bool))


_lapses_ok = cloud_setup._lapses_ok


def _pin_facts(cwd):
    """The plugin pin hook's reader result in the working tree; with no repository, absent."""
    try:
        return cloud_plugin_pin.in_tree(store_core.repo_root(cwd))
    except store_core.RepoRootUnavailable:
        return {"state": "absent", "reason": None, "pin": None}


def _hook_gap(cwd, root, commit=None, adopted=None):
    """The dependency hook's branch gap token at `commit` (the checkout's HEAD when None), or None
    when the hook is off or the commit carries it. Never raises: a repository root that cannot be
    found or any unexpected failure is `commit-unreadable`, and settings that cannot be read are
    `settings-unreadable`, so nothing unreadable passes."""
    try:
        return cloud_setup_text.branch_hook_gap(cwd, root, commit, adopted)
    except store_core.RepoRootUnavailable:
        return "commit-unreadable"  # axis: a repository root that cannot be found cannot show the commit carries the hook
    except cloud_setup_text._Refused:
        return "settings-unreadable"  # axis: setup settings that cannot be read are not the hook being off
    except Exception:
        return "commit-unreadable"  # axis: any other failure in the hook test is never read as a pass


def _judge_parts(obj, environment, cwd, root, today):
    """(results, local placed stamp or None, the pin hook's reader result, the hook gap token or
    None)."""
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
    identity = obj.get(IDENTITY_FIELD)
    # axis: the cloud session must resolve a configured author and committer identity
    identity_ok = (isinstance(identity, dict) and identity.get("author") is True
                   and identity.get("committer") is True)
    pin = _pin_facts(cwd)
    pin_ok = None
    if pin["state"] == "broken":
        pin_ok = False  # axis: a broken pin hook is never read as absent or valid
    elif pin["state"] == "valid":
        # axis: the cloud must run the commit the pin names, and the pin must name the plugin this machine runs
        pin_ok = (isinstance(obj.get("pluginCommit"), str)
                  and obj["pluginCommit"] == pin["pin"]["commit"]
                  and pin["pin"]["version"] == local_version)
    # axis: the commit a launch starts from (the checkout's HEAD) must carry the dependency hook when the project has it on
    gap = _hook_gap(cwd, root)
    return {
        "versionMatches": version_ok,
        "pinMatches": pin_ok,
        "dependencyHookMatches": gap is None,
        "calibrationMatches": computed and placed_ok and file_ok and repo_ok,
        "reviewerAnswered": reviewer,
        "environmentMatches": environment_ok,
        "identityPresent": identity_ok,
    }, local_placed, pin, gap


def _fail_closed(cwd, who, root, environment, failed, now):
    """(failed parts, marker written). The failed-check marker is the paused state; this writes it
    and nothing else, and never touches the cloud-builds setting."""
    failed = list(failed)
    marked = who is not None and _write_failed_check(cwd, who, root, environment, failed, now)
    return failed, marked


def _utc_stamp(now):
    moment = now if isinstance(now, datetime.datetime) else datetime.datetime.fromtimestamp(
        time.time() if now is None else now, datetime.timezone.utc)
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_stamp(stamp):
    return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")


def _write_failed_check(cwd, account, root, environment, failed_parts, now):
    """True only when the marker was written. A store lock held by another writer is tried again,
    `_MARKER_ATTEMPTS` times in all with `_MARKER_WAIT` seconds between; an OSError or any other
    exception is not retried and is False."""
    for attempt in range(_MARKER_ATTEMPTS):
        outcome = _write_failed_check_once(cwd, account, root, environment, failed_parts, now)
        if outcome is not None:
            return outcome
        # axis: a store lock held by another writer is waited out a few times before the marker is given up
        if attempt + 1 < _MARKER_ATTEMPTS:
            _sleep(_MARKER_WAIT)
    return False


def _write_failed_check_once(cwd, account, root, environment, failed_parts, now):
    """One try: True when written, None when the store lock was held, False on any failure."""
    try:
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return None
            marker = {"schema": FAILED_CHECK_SCHEMA, "account": account, "environment": environment,
                      "failedAt": _utc_stamp(now),
                      "failedParts": list(failed_parts)}
            path = failed_check_path(cwd, account, root)
            directory = os.path.dirname(path)
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".cloud-check-failed-", dir=directory, text=True)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(json.dumps(marker, sort_keys=True, indent=2) + "\n")
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
            return True
    except Exception:
        return False


def _remove_failed_check(cwd, account, root, started=None):
    """True only when no marker remains because of this call: removed, or already missing. With
    `started` (the judgment's start stamp), a marker whose failedAt is equal or later was written
    by an overlapping judgment that failed: it stays and this returns False. An absent or damaged
    marker, or one stamped strictly earlier, is removed."""
    try:
        with mode_registry.config_lock(cwd, root) as got:
            if not got:
                return False
            if started is not None:
                marker = read_failed_check(cwd, account, root)
                try:
                    newer = (marker is not None and not marker.get("damaged")
                             and _parse_stamp(marker.get("failedAt")) >= _parse_stamp(started))
                except Exception:
                    newer = False
                if newer:
                    return False
            try:
                os.unlink(failed_check_path(cwd, account, root))
            except FileNotFoundError:
                pass
            return True
    except Exception:
        return False


def _short_commit(commit):
    return commit[:12] if isinstance(commit, str) and _COMMIT_RE.fullmatch(commit) else "unknown"


def _standing(cwd, who, root, marked):
    """The standing sentence of a failed or unread message, decided once per judgment from what is
    on disk after it: paused when this judgment's marker landed, paused with the earlier marker
    named when the write failed but a marker for the account remains, else not paused. A read that
    raises, or no account, counts as no marker."""
    if marked:
        return _PAUSED_STANDING
    try:
        remains = who is not None and read_failed_check(cwd, who, root) is not None
    except Exception:
        remains = False
    return _PAUSED_STANDING + " " + _EARLIER_MARKER_STANDS if remains else _NOT_PAUSED


def _failed_message(parts, standing, cloud_version, local_version, identity=None,
                    identity_reported=True, pin=None, cloud_commit=None, hook_gap=None):
    # a hook part with no known gap token still reads as the fail-closed one, never as a blank
    gap_sentence, gap_fix = cloud_dependency_hook.GAP_TEXT[
        hook_gap if hook_gap in cloud_dependency_hook.GAP_TEXT else "commit-unreadable"]
    pinned = (pin or {}).get("pin") or {}
    pin_values = {
        "cloud": "unknown" if cloud_version is None else cloud_version,
        "cloud_commit": _short_commit(cloud_commit),
        "pin_version": pinned.get("version") or "unknown",
        "pin_commit": _short_commit(pinned.get("commit")),
    }
    sentences = []
    for name, sentence, _fix in _PARTS:
        if name not in parts:
            continue
        if name == "identity" and not identity_reported:
            # an unreported identity is named only when it is the one part that failed
            if parts == ["identity"]:
                sentences.append(_IDENTITY_UNREPORTED)
            continue
        if name == "pin" and (pin or {}).get("state") == "broken":
            sentences.append(_PIN_BROKEN.format(reason=pin["reason"]))
            continue
        if name == "hook":
            sentences.append(sentence % (hook_gap if hook_gap in cloud_dependency_hook.GAP_TEXT
                                         else "commit-unreadable", gap_sentence))
            continue
        sentences.append(sentence.format(
            **dict({"cloud": "not installed" if cloud_version is None else cloud_version,
                    "mine": "unknown" if local_version is None else local_version},
                   **pin_values if name == "pin" else {})))
    count = "one part" if len(sentences) == 1 else "%d parts" % len(sentences)
    fixes = []
    for name, _sentence, fix in _PARTS:
        if name == "identity" and name in parts:
            if not identity_reported:
                fix = _SAME_FIX if parts == ["identity"] else None
            else:
                # only this one fix is a template; the name and email are values, never formatted
                fix = fix.format(
                    name="your name" if identity is None else "`%s`" % identity[0],
                    email="your email" if identity is None else "`%s`" % identity[1])
        if name == "hook":
            fix = fix % gap_fix
        if name in parts and fix is not None and fix not in fixes:
            fixes.append(fix)
    return ("**The check failed on %s.** %s\n\n%s To fix it, %s and say \"check again\"."
            % (count, " ".join(sentences), standing, ", then ".join(fixes)))


def judge(cwd, line, *, environment, nonce, account=None, root=None, env=None, now=None,
          project_name=None, record_fn=None):
    """Read the report line out of `line` and decide. The setup record is written only when the
    environment, the plugin version, the calibration and the reviewer's answer all agree with this
    machine; for a project that commits the plugin pin hook the plugin version is judged as the pin:
    the cloud's reported commit must equal the pin's commit and the pin's version this machine's,
    and a broken hook fails the check. Every other result writes no record and leaves a
    failed-check marker beside the record, which pauses cloud launches on this account (a passing
    check writes the record first, then removes the marker; a marker that cannot be removed fails
    the check as `record` with `recordWritten` true and stays). The cloud-builds setting is the
    owner's intent and is written only by the owner's switch: no result here writes it, so
    `settingSwitchedOff` is always False. The record is never touched by a failed or unread
    result."""
    name = _project(cwd, project_name)
    started = _utc_stamp(now)  # the judgment's start moment, taken once, whole seconds UTC
    today = cloud_setup_text._utc_date(now)
    who = account if account is not None else cloud_setup.launching_account(env, cwd)
    obj = None
    if (_environment_ok(environment) and isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce)
            and isinstance(line, str)):
        found = _find_report(line, nonce)
        obj = found if _readable(found, nonce) else None
    if obj is None:
        # axis: an unread report writes the marker and never the setting
        # axis: an unread report leaves a marker a later reader can see, and never touches the record
        failed, marked = _fail_closed(cwd, who, root, environment, ["unread"], now)
        return {"action": "unread", "results": dict.fromkeys(
                    ("versionMatches", "pinMatches", "dependencyHookMatches",
                     "calibrationMatches", "reviewerAnswered", "environmentMatches",
                     "identityPresent")),
                "dependencyHookGap": None,
                "failedParts": failed, "recordWritten": False, "settingSwitchedOff": False,
                "markerWritten": marked,
                # axis: the unread message says the account is paused exactly when a marker for it is on disk after the judgment, an earlier one included, never the not-paused sentence beside a marker that still pauses
                "message": _UNREAD.format(standing=_standing(cwd, who, root, marked))}

    results, local_placed, pin, gap = _judge_parts(obj, environment, cwd, root, today)
    identity_reported = isinstance(obj.get(IDENTITY_FIELD), dict)
    # axis: a valid pin hook's pin part replaces the version part
    failed = [part for part, key in (("environment", "environmentMatches"),
                                     ("version", "versionMatches"),
                                     ("pin", "pinMatches"),
                                     ("hook", "dependencyHookMatches"),
                                     ("calibration", "calibrationMatches"),
                                     ("reviewer", "reviewerAnswered"),
                                     ("identity", "identityPresent"))
              if not results[key] and not (part == "version" and pin["state"] == "valid")
              and not (part == "pin" and results[key] is None)]
    written = False
    if not failed:
        done = False
        try:
            # axis: a passing check writes the record first and clears the failed-check marker only
            # after the write succeeded, so an interruption between the two leaves a stale marker
            # (not ready, the fail-closed direction) and never a lost one
            if who is not None:
                # axis: a refused or raising record write is never reported as a pass
                got = (cloud_setup.record_check if record_fn is None else record_fn)(
                    cwd, account=who, environment=environment, plugin_version=obj["pluginVersion"],
                    picks_up_version=cloud_setup_text.PICKS_UP_VERSION_BY_ITSELF,
                    calibration_stamp=local_placed, calibration_date=today.isoformat(),
                    pass_lapses=obj["confirmation"]["passLapses"], checked_at=today.isoformat(),
                    root=root)
                written = isinstance(got, dict) and got.get("action") in ("written", "noop")
                # axis: a marker that cannot be removed fails the check and stays in place; one
                # axis: stamped at or after this judgment's start came from an overlapping failure
                done = written and _remove_failed_check(cwd, who, root, started)
        except Exception:
            done = False
        if not done:
            failed.append("record")

    if failed:
        # axis: a failed check writes the marker and never the setting
        # axis: a failed check leaves a marker a later reader can see, and never touches the record
        failed, marked = _fail_closed(cwd, who, root, environment, failed, now)
        # axis: the message says the account is paused exactly when a marker for it is on disk after the judgment, an earlier one included, and the not-paused sentence only when none is, never both
        standing = _standing(cwd, who, root, marked)
        return {"action": "failed", "results": results, "dependencyHookGap": gap,
                "failedParts": failed, "recordWritten": written, "settingSwitchedOff": False,
                "markerWritten": marked,
                "message": _failed_message(
                    failed, standing, obj["pluginVersion"], _or_none(cloud_setup_text._plugin_version),
                    identity_reported=identity_reported, pin=pin,
                    cloud_commit=obj.get("pluginCommit"), hook_gap=gap,
                    # axis: an identity the session never reported is not a missing one
                    **({"identity": _local_identity(cwd)}
                       if "identity" in failed and identity_reported else {}))}
    on = cloud_setup.read(cwd, who, root)["setting"] is True
    ending = (_PASSED_ON if on else _PASSED_OFF).format(project=name)
    return {"action": "passed", "results": results, "dependencyHookGap": None,
            "failedParts": [], "recordWritten": True,
            "settingSwitchedOff": False, "markerWritten": False,
            "message": _PASSED.format(version=obj["pluginVersion"]) + ending}


def _refusal(reason, message, **more):
    return dict({"action": "refused", "reason": reason, "message": message}, **more)


def _issue_number(issue):
    """The issue as a positive integer, or None when it is not one."""
    if isinstance(issue, bool):
        return None
    if isinstance(issue, int):
        return issue if issue > 0 else None
    if isinstance(issue, str) and re.fullmatch(r"[0-9]+", issue):
        return int(issue) or None
    return None


def _fallback_line(nonce):
    """The line a session that cannot run `report` gives instead: a report that judges as failed."""
    obj = dict.fromkeys(REPORT_FIELDS)
    obj["pluginCommit"] = None
    obj["schema"] = REPORT_SCHEMA
    obj["nonce"] = nonce
    obj["confirmation"] = {"schema": cloud_pass.CONFIRMATION_SCHEMA, "reviewerAnswered": False,
                           "passLapses": None, "reason": "plugin-missing"}
    obj[IDENTITY_FIELD] = None
    return report_line(obj)


def _check_prompt(nonce, issue):
    prompt = _CHECK_PROMPT.format(plugin_dir=cloud_pass.CLOUD_PLUGIN_DIR, nonce=nonce,
                                  fallback=_fallback_line(nonce))
    return prompt + (_CHECK_POST.format(issue=issue) if issue is not None else "")


def _repo_root(cwd, env=None):
    try:
        return store_core.repo_root(cwd, env=env)
    except Exception:
        return os.path.abspath(cwd)


def start(cwd, *, environment, issue=None, env=None, spawn_fn=None, timeout=120, nonce=None):
    """Start the check session in the environment whose id the owner gave. Never raises for an
    expected failure; nothing is spawned unless every refusal below has been passed."""
    # axis: every check session names the environment id the owner gave, and only a well-formed one
    if not _environment_ok(environment):
        return _refusal("check-environment-invalid", _ENVIRONMENT_NEEDED)
    number = None
    if issue is not None:
        number = _issue_number(issue)
        if number is None:
            return _refusal("check-issue-invalid",
                            "The issue number must be a positive whole number.")
    if nonce is None:
        nonce = secrets.token_hex(8)
    elif not (isinstance(nonce, str) and _NONCE_RE.fullmatch(nonce)):
        return _refusal("check-nonce-invalid",
                        "The check's nonce must be 8 to 64 letters and digits.")
    name = _CHECK_SESSION_PREFIX + nonce[:8]
    cell = model_registry.resolve_dispatch("mechanical", "claude", None)
    if cell.get("ok") is not True:
        return _refusal("check-model-unresolved",
                        "I could not choose the model the check session runs at.",
                        detail=cell.get("detail") or cell.get("reason"))
    built = engine_adapter.claude_cloud_builder_argv(
        cell["dispatch_token"], cell["effort"], _check_prompt(nonce, number), environment, name,
        permission_mode=None,  # the owner's auto-mode ruling covers builders; the check's model may lack it
        disallowed_tools=None)  # the question-dialog ruling covers builders; the check asks nothing
    if built.get("reason") is not None or not built.get("argv"):
        return _refusal("check-launch-refused", "The check session could not be launched.",
                        detail=built.get("reason"))
    import launcher
    child_env = launcher.ll.scrub_env(env)
    launcher.pin_effort(child_env, cell["effort"])
    spawn = spawn_fn or launcher.default_cloud_spawn
    try:
        log_path = os.path.join(tempfile.mkdtemp(prefix="cloud-check-"), "launch.log")
        spawned = spawn(built["argv"], _repo_root(cwd, child_env), log_path, child_env, timeout)
    except OSError:
        return _refusal("check-session-not-started", _NOT_STARTED)
    output = spawned.get("output") if isinstance(spawned, dict) else None
    # axis: a session is reported started only on a receipt for this launch's own session name
    got = launcher.read_cloud_receipt(
        launcher.strip_terminal_sequences(output if isinstance(output, str) else ""), name)
    if got is None:
        return _refusal("check-session-unconfirmed", _UNCONFIRMED.format(name=name),
                        sessionName=name)
    session_id, session_url = got
    return {"action": "started", "reason": None, "environment": environment, "nonce": nonce,
            "sessionName": name, "sessionId": session_id, "sessionUrl": session_url,
            "issue": number, "message": _STARTED}


def _print(result):
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 1 if result.get("action") in ("refused", "failed", "unread") else 0


def main(argv=None, spawn_fn=None):
    parser = argparse.ArgumentParser(prog="cloud_check.py")
    parser.add_argument("verb", choices=["setup-message", "sign-in", "report", "judge",
                                         "setup-text", "start"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--nonce", default=None)
    parser.add_argument("--environment", default=None)
    parser.add_argument("--account", default=None)
    parser.add_argument("--issue", default=None)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--line", default=None)
    source.add_argument("--line-file", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    cwd = args.cwd or os.getcwd()
    if args.verb == "report":
        sys.stdout.write(report_line(report(cwd=cwd, root=args.root, nonce=args.nonce)) + "\n")
        return 0
    if args.verb == "start":
        return _print(start(cwd, environment=args.environment, issue=args.issue, spawn_fn=spawn_fn))
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
