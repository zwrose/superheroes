#!/usr/bin/env python3
"""Where a build runs: the routing decision and the reasons it can give.

Stdlib plus plugin imports only. Every reason any output prints is drawn from the one `REASONS`
table below. A build pointed at the cloud goes there only when nothing needs the owner's machine
and the cloud is ready; anything that cannot be read sends the build to the owner's machine.
`route` always returns a placement and never raises. `fix_text` gives the words that fix a
reason, and after a failed check it asks for the check to be run again."""
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import architect_config  # noqa: E402
import cloud_dependency_hook  # noqa: E402
import cloud_ready  # noqa: E402
import cloud_setup  # noqa: E402
import definition_doc  # noqa: E402
import mode_registry  # noqa: E402
import store_core  # noqa: E402

LOCAL_WORD = "local"
CLOUD_WORD = "cloud"

# The readiness check is the one home of the reasons it can give; route keeps only those.
NOT_READY_CODES = tuple(cloud_ready.REASON_FOR[name] for name in cloud_ready.CONDITION_ORDER)

_SETUP_TEXT_FIX = ('To fix it, paste the new setup text into the environment. '
                   'Say "setup text" and I\'ll write it.')

REASONS = {
    "local-word": {
        "words": 'You said "this one local".',
        "fix": None, "short": None, "wasnt": None,
    },
    "needs": {
        "words": "It needs {need}, which only your machine has.",
        "fix": None, "short": None, "wasnt": None,
    },
    "pass-lapsed": {
        "words": "The reviewer pass has lapsed.",
        "fix": ('To fix it, run the pass command on your machine, paste the new pass into the '
                'environment and say "check again".'),
        "short": 'Paste a fresh pass and say "check again" to fix it.',
        "wasnt": "the reviewer pass has lapsed.",
    },
    "no-pass": {
        "words": "There is no reviewer pass in the cloud environment.",
        "fix": ('To fix it, run the pass command on your machine, paste the pass into the '
                'environment and say "check again".'),
        "short": 'Paste a pass into the environment and say "check again" to fix it.',
        "wasnt": "there is no reviewer pass in the cloud environment.",
    },
    "no-setup": {
        "words": "This project has no cloud setup on this Claude account.",
        "fix": 'Say "set up cloud builds" and I\'ll walk you through it.',
        "short": 'Say "set up cloud builds" to fix it.',
        "wasnt": "this project has no cloud setup on this Claude account.",
    },
    "version": {
        "words": "The cloud's plugin is {cloud} and mine is {advisor}.",
        "fix": _SETUP_TEXT_FIX,
        "short": "Paste the new setup text to fix it.",
        "wasnt": "its plugin is {cloud} and mine is {advisor}.",
    },
    "calibration": {
        "words": "The cloud's calibration doesn't match this machine's.",
        "fix": _SETUP_TEXT_FIX,
        "short": "Paste the new setup text to fix it.",
        "wasnt": "its calibration doesn't match this machine's.",
    },
    "plugin-pin": {
        "words": ("The plugin pin on the branch this build starts from doesn't name the plugin I "
                  "run, or its pin hook is broken."),
        "fix": ("To fix it, run cloud_plugin_pin.py write on this machine (it pins the plugin I run), "
                "commit and push the files it names on the branch the build starts from, then launch "
                "again."),
        "short": "Commit a current plugin pin on the starting branch to fix it.",
        "wasnt": "the plugin pin on the branch it starts from doesn't name my plugin.",
    },
    "dependency-hook": {
        "words": ("The branch this build starts from doesn't carry the dependency hook, or a "
                  "setup file the build adopts can't be shown unchanged since the hook ran (it "
                  "changed, or it is a link), so the cloud could build it with out-of-date "
                  "dependencies."),
        "fix": ("To fix it, commit and push the dependency hook files configure wrote (the "
                "settings file and the hook script) on the branch the build starts from; if the "
                "build adopts a branch that changed a dependency file, bring that change into "
                "the branch it starts from first. A listed setup file that is a link or sits "
                "under a linked folder cannot be compared, so point both the setup command "
                "and configure's setup inputs at the regular file itself, with no link in "
                "between. Then launch again."),
        "short": ("Bring the dependency hook and any adopted setup-file change onto the "
                  "starting branch, and list setup files as regular files, to fix it."),
        "wasnt": ("the branch it starts from doesn't carry the dependency hook, or a setup file "
                  "it adopts can't be shown unchanged."),
    },
    "unreachable": {
        "words": "The cloud platform couldn't be reached.",
        "fix": "I'll try the cloud again at the next launch.",
        "short": "I'll try the cloud again at the next launch.",
        "wasnt": "the cloud platform couldn't be reached.",
    },
}

# The reasons any output can print are the keys of the one table above.
REASON_CODES = tuple(REASONS)

_UNKNOWN = "unknown"

_CHECK_AGAIN = "check again"
_CHECK_AGAIN_ONLY = 'Say "check again" and I\'ll run the check again.'
_CHECK_AGAIN_SUFFIX = ' Then say "check again".'

_PHONE_SIMULATOR = "the phone simulator"
_CANON_AND_SPECS = "this project's Canon and specs"
_CANON_ONLY = "this project's Canon"
_SPECS_ONLY = "this project's specs"


# ---------------------------------------------------------------- what only the owner's machine has


def _canon_outside(cwd, root):
    try:
        top = store_core.repo_root(cwd)
        got = definition_doc.resolve_canon(root=top, cwd=cwd, store_root=root)
        return got["home"] != "repo"
    except Exception:
        # axis: a Canon location that cannot be read counts as outside the repository — see bite-proof record wo_a_place_call
        return True


def _specs_outside(cwd, root):
    """True unless the doc policy and the project store say the specs are in the repository; the
    storage mode does not decide it. Read strictly: a policy that is missing, malformed or too new counts as
    outside, and nothing is created, written or backfilled."""
    try:
        with open(architect_config.policy_path(cwd, root), encoding="utf-8") as fh:
            policy = json.load(fh)
        if not isinstance(policy, dict):
            return True
        if "schemaVersion" in policy:
            version = policy["schemaVersion"]
            if type(version) is not int or version > architect_config.SCHEMA_VERSION:
                return True
        # axis: the specs are in the repository only when the policy says committed — see bite-proof record wo_a_place_call
        if policy.get("visibility") != architect_config.COMMITTED:
            return True
        location = policy.get("location")
        if not isinstance(location, str) or architect_config._safe_location(location) != location:
            return True
        docs = os.path.join(mode_registry.project_store_dir(cwd, root), "docs")
        # axis: the specs are in the repository only when the project store holds none — see bite-proof record wo_a_place_call
        if os.path.isdir(docs):
            for name in os.listdir(docs):
                if os.path.isfile(os.path.join(docs, name, "spec.md")):
                    return True
        return False
    except Exception:
        return True


def machine_needs(cwd, premise, *, root=None):
    """What only the owner's machine has, for this build: the advisor's judgment from the order,
    the phone simulator, and a Canon or specs kept outside the repository.
    De-duplicated, in that order. Read-only."""
    found = []

    def add(need):
        if need not in found:
            found.append(need)

    judged = premise.get("needs")
    for need in judged if isinstance(judged, (list, tuple)) else ():
        if isinstance(need, str) and need.strip():
            add(need)
    if premise.get("iphoneCheck") is True:
        add(_PHONE_SIMULATOR)
    try:
        canon = _canon_outside(cwd, root)
        specs = _specs_outside(cwd, root)
    except Exception:
        canon = specs = True
    if canon and specs:
        add(_CANON_AND_SPECS)
    elif canon:
        add(_CANON_ONLY)
    elif specs:
        add(_SPECS_ONLY)
    return found


def _join_needs(needs):
    if len(needs) <= 1:
        return "".join(needs)
    return ", ".join(needs[:-1]) + " and " + needs[-1]


# ---------------------------------------------------------------- the routing decision


def _placement(place, pointed, by, reason, need, cloud_version, advisor_version, environment,
               reported, failed_check=None, hook_gap=None):
    return {"place": place, "pointedAtCloud": pointed, "by": by, "reason": reason, "need": need,
            "cloudVersion": cloud_version, "advisorVersion": advisor_version,
            "environment": environment, "reported": reported, "failedCheck": failed_check,
            "hookGap": hook_gap}


def route(cwd, premise, launch_word=None, *, readiness_fn=None, needs_fn=None, root=None,
          env=None):
    """Where one build runs: the placement, with the reason it ran on the owner's machine when
    the setting or the launch word pointed it at the cloud. Always returns; never raises."""
    if launch_word not in (None, LOCAL_WORD, CLOUD_WORD):
        raise ValueError("launch word must be None, %r or %r: %r" % (LOCAL_WORD, CLOUD_WORD, launch_word))
    reported = None
    pointed = False
    by = None
    cloud_version = advisor_version = failed_check = hook_gap = None
    try:
        reported = premise.get("reportedCloud")
        if readiness_fn is not None:
            now = readiness_fn(cwd, reported=reported, root=root, env=env)
        else:
            base = premise.get("baseCommit")
            adopts = premise.get("adoptsHead")
            # the session starts on baseCommit; an adopted head is checked out only after SessionStart
            now = cloud_ready.readiness(
                cwd, reported=reported, root=root, env=env,
                commit=base if isinstance(base, str) and base else None,
                adopted=adopts if isinstance(adopts, str) and adopts else None)
        setting = now.get("setting") is True
        cloud_version = now.get("cloudVersion")
        advisor_version = now.get("advisorVersion")
        failed_check = now.get("failedCheck")
        hook_gap = now.get("dependencyHookGap")
        if launch_word == CLOUD_WORD:
            by = "word"
        elif launch_word is None and setting:
            by = "setting"
        pointed = by is not None

        def local(reason, need=None):
            return _placement(
                "local", pointed, by, reason, need, cloud_version, advisor_version, None, reported,
                failed_check, hook_gap if reason == "dependency-hook" else None)

        wants = needs_fn or machine_needs
        # axis: a launch word of local wins over a need, so the owner's word is the reason given — see bite-proof record wo_a_place_call
        if launch_word == LOCAL_WORD:
            by = "setting" if setting else None
            pointed = by is not None
            return local("local-word" if setting else None)
        needs = wants(cwd, premise, root=root)
        # axis: a need of the owner's machine wins over a cloud word — see bite-proof record wo_a_place_call
        if needs:
            if pointed:
                return local("needs", _join_needs(needs))
            return local(None)
        if not pointed:
            return local(None)
        if now.get("ready") is True and now.get("reason") is None:
            return _placement(
                "cloud", pointed, by, None, None, cloud_version, advisor_version,
                now.get("environment"), reported, failed_check)
        reason = now.get("reason")
        reason = reason if reason in NOT_READY_CODES else "no-setup"
        account = now.get("account")
        if reason == "no-setup" and failed_check is None and isinstance(account, str):
            # an account whose first check failed has a marker and no setup record: readiness
            # returns before it reads the marker, so the marker is read here
            failed_check = cloud_ready._failed_check(cwd, account, root)
        return local(reason)
    except Exception:
        return _placement(
            "local", pointed, by, "no-setup" if pointed else None, None, cloud_version,
            advisor_version, None, reported, failed_check)


# ---------------------------------------------------------------- the reasons as words


def _version_slot(value):
    return value if isinstance(value, str) and value.strip() else _UNKNOWN


def _fill(template, cloud_version, advisor_version, need=None):
    return (template.replace("{cloud}", _version_slot(cloud_version))
            .replace("{advisor}", _version_slot(advisor_version))
            .replace("{need}", need if isinstance(need, str) and need.strip() else "something"))


def _words(code, cloud_version, advisor_version, need=None):
    return _fill(REASONS[code]["words"], cloud_version, advisor_version, need)


def _hook_gap_text(place_call):
    """(gap token, sentence, fix) for a dependency-hook placement that names a known gap, else None."""
    if place_call.get("reason") != "dependency-hook":
        return None
    gap = place_call.get("hookGap")
    if not isinstance(gap, str) or gap not in cloud_dependency_hook.GAP_TEXT:
        return None
    sentence, fix = cloud_dependency_hook.GAP_TEXT[gap]
    return gap, sentence, fix


def _paused_no_setup(place_call):
    """(failed, fix) from the one paused wording when this is a no-setup placement whose account has
    a failed-check marker (`failedCheck` a list), else None."""
    failed = place_call.get("failedCheck")
    if place_call.get("reason") == "no-setup" and isinstance(failed, list):
        return cloud_setup.paused_parts(failed)
    return None


def reason_text(place_call):
    """The board's words for the reason on this placement, or None when it has none."""
    try:
        code = place_call.get("reason")
        if code not in REASONS:
            return None
        paused = _paused_no_setup(place_call)
        if paused is not None:
            return "This account's " + paused[0]
        found = _hook_gap_text(place_call)
        if found is not None:
            return ("The dependency hook on the branch this build starts from failed its check "
                    "(`%s`): %s, so the cloud could build it with out-of-date dependencies."
                    % (found[0], found[1]))
        return _words(code, place_call.get("cloudVersion"), place_call.get("advisorVersion"),
                      place_call.get("need"))
    except Exception:
        return None


def fix_text(place_call):
    """The words that fix this placement's reason, or None when it has none. After a failed
    check they ask for the check to be run again."""
    try:
        code = place_call.get("reason")
        if code not in REASONS:
            return None
        paused = _paused_no_setup(place_call)
        if paused is not None:
            return paused[1]
        fix = REASONS[code]["fix"]
        if code == "dependency-hook":
            found = _hook_gap_text(place_call)
            if found is not None:
                fix = "To fix it, %s. Then launch again." % found[2]
            failed = place_call.get("failedCheck")
            # axis: after a failed hook part the fix ends by asking for the check to be run again
            return fix + _CHECK_AGAIN_SUFFIX if isinstance(failed, list) and "hook" in failed else fix
        if fix is None or place_call.get("failedCheck") is None:
            return fix
        # axis: after a failed check the fix ends by asking for the check to be run again — see bite-proof record wo_c_place_call
        if code == "no-setup":
            return _CHECK_AGAIN_ONLY
        if code in ("version", "plugin-pin", "calibration", "no-pass"):
            return fix if _CHECK_AGAIN in fix else fix + _CHECK_AGAIN_SUFFIX
        return fix
    except Exception:
        return None


def wasnt_text(place_call):
    """The "the cloud wasn't ready: ..." clause for this placement's reason, or None when the
    reason is not one in the table."""
    try:
        code = place_call.get("reason")
        if code not in REASONS:
            return None
        paused = _paused_no_setup(place_call)
        if paused is not None:
            return "this account's " + paused[0]
        found = _hook_gap_text(place_call)
        if found is not None:
            return ("the dependency hook on the branch it starts from failed its check (`%s`): %s."
                    % (found[0], found[1]))
        return _fill(REASONS[code]["wasnt"], place_call.get("cloudVersion"),
                     place_call.get("advisorVersion"))
    except Exception:
        return None
