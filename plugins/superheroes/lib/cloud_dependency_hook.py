"""The cloud dependency hook: the committed start-of-session script that keeps a cloud session's
dependencies current, and the one place that writes, rewrites and removes it.

A project that lists cloud setup commands (configure item 17) can opt in to a SessionStart hook. In
a cloud session the hook re-runs those commands when the files they depend on changed since the
last successful run. The hook files in a repository are exactly a function of
`(commands, inputs, enabled)`: when enabled with at least one command, `.claude/settings.json` holds
exactly one hook object of ours and the script holds exactly `script_text(commands, inputs)`;
otherwise neither exists, and no other part of the settings file changes. `sync` is the single
chokepoint that makes it so.

  cloud_dependency_hook.py offer [--cwd D] [--root D]

`offer` prints the question configure asks before adding the hook; every other caller uses `sync`,
`fingerprint`, `script_text` and `offer_message`.

Standard library only. Expected failures are refusals with a `reason` token, never a raise.
"""
import argparse
import hashlib
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
import tempfile

SCRIPT_REL = ".claude/hooks/superheroes-cloud-dependencies.sh"
SETTINGS_REL = ".claude/settings.json"
HASH_NAME = "superheroes-cloud-setup-hash"
LOG_NAME = "superheroes-cloud-setup.log"
HOOK_TIMEOUT_SECONDS = 600
HOOK_COMMAND = 'bash "$CLAUDE_PROJECT_DIR/%s"' % SCRIPT_REL


class _Refused(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def fingerprint(commands, inputs):
    """The sha256 of the command list and the input list, so a changed list is a changed hash."""
    body = json.dumps({"commands": list(commands), "inputs": list(inputs)},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


# Whether a SessionStart group runs at startup, and whether a settings document registers the hook.
# One source, two users: `_STARTS_LINES` and `_REGISTERS_LINES` are embedded in the script text's
# record-mode check and run here by the Python reader, so the script and the reader cannot drift.
_STARTS_LINES = [
    "def starts(e):",
    "    m = e.get('matcher')",
    "    if m is None or m in ('', '*'):",
    "        return True",
    # axis: Claude evaluates matchers as JavaScript regular expressions, and Python's regex
    # dialect differs from that (`start++up` compiles here, not there), so only the plain form is
    # trusted: a `|`-separated list of literal words, one of which is `startup`; anything with
    # another metacharacter is treated as not covering startup
    "    if not isinstance(m, str) or not re.fullmatch(r'[A-Za-z0-9_-]+(\\|[A-Za-z0-9_-]+)*', m):",
    "        return False",
    "    return 'startup' in m.split('|')",
]
# The whole registration rule: hooks not all disabled, and an enabled startup SessionStart group
# holding the command. It calls `starts`, so the two line lists run in one scope.
_REGISTERS_LINES = [
    "def registers(data, command):",
    "    ok = isinstance(data, dict) and data.get('disableAllHooks') is not True",
    "    entries = data.get('hooks', {}).get('SessionStart', []) if ok else []",
    "    return bool(ok and any(",
    "        isinstance(h, dict) and h.get('type') == 'command' and h.get('command') == command",
    "        for e in entries if isinstance(e, dict) and starts(e) for h in (e.get('hooks') or [])))",
]
_registers_scope = {"re": re}
exec("\n".join([*_STARTS_LINES, *_REGISTERS_LINES]), _registers_scope)
_group_starts = _registers_scope["starts"]


_GIT_TIMEOUT_SECONDS = 30
_REGULAR_MODES = ("100644", "100755")


def _registers(data):
    """True when settings document `data` registers the hook the way the script's record mode
    accepts: hooks not all disabled, and an enabled startup SessionStart group holding our command."""
    try:
        return _registers_scope["registers"](data, HOOK_COMMAND)
    except Exception:
        return False


def _git_out(repo_root, *args):
    """The stdout bytes of one bounded git read, or None when it could not run or exited non-zero."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}
    try:
        done = subprocess.run(["git", "-C", str(repo_root), *args], capture_output=True, env=env,
                              timeout=_GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return done.stdout if done.returncode == 0 else None


def _resolve(repo_root, commit):
    if not isinstance(commit, str) or not commit or commit.startswith("-"):
        return None  # never handed to git, where a leading dash reads as an option
    out = _git_out(repo_root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % commit)
    text = out.decode("utf-8", "replace").strip() if out is not None else ""
    return text or None


def _entry(repo_root, resolved, path):
    """(mode, type, oid) of `path` in the tree at `resolved`, None when absent, False when unreadable."""
    out = _git_out(repo_root, "ls-tree", "-z", resolved, "--", path)
    if out is None:
        return False
    for raw in out.split(b"\0"):
        if not raw:
            continue
        meta, _, name = raw.decode("utf-8", "replace").partition("\t")
        fields = meta.split(" ")
        if name == path and len(fields) == 3:
            return tuple(fields)
    return None


def _regular(entry):
    return bool(entry) and entry[0] in _REGULAR_MODES and entry[1] == "blob"


def _blob(repo_root, entry):
    """The bytes of the blob an entry names, None when they cannot be read."""
    return _git_out(repo_root, "cat-file", "blob", entry[2])


def _ancestor_gap(repo_root, commits, norm):
    """A reason token when a proper ancestor directory of `norm` is unreadable or is anything but a
    tree at any of `commits` (absent is fine), else None."""
    parts = norm.split("/")[:-1]
    for depth in range(1, len(parts) + 1):
        prefix = "/".join(parts[:depth])
        if not prefix:
            continue
        for commit in commits:
            entry = _entry(repo_root, commit, prefix)
            if entry is False:
                return "commit-unreadable"  # axis: an ancestor that cannot be listed leaves the input unshown
            if entry and entry[1] != "tree":
                return "adopted-input-not-a-file"  # axis: an input under a symlink, file or submodule is read through it, which a tree lookup cannot traverse
    return None


def branch_gap(repo_root, commit, commands, inputs, adopted=None):
    """None when the tree at `commit` carries this hook (the script exactly as `script_text` writes
    it, and settings that register it as record mode accepts) and, with `adopted`, every path in
    `inputs` is identical at `adopted`; else a reason token: commit-unreadable, script-missing,
    script-differs, settings-not-registered, adopted-inputs-differ or adopted-input-not-a-file (an input
    that is a link, a folder or a submodule, or sits under a linked folder). Never raises."""
    resolved = _resolve(repo_root, commit)
    if resolved is None:
        return "commit-unreadable"  # axis: a commit that does not resolve cannot be shown to carry the hook
    script = _entry(repo_root, resolved, SCRIPT_REL)
    settings = _entry(repo_root, resolved, SETTINGS_REL)
    if script is False or settings is False:
        return "commit-unreadable"  # axis: a tree that cannot be listed is not shown to carry the hook
    if script is None:
        return "script-missing"  # axis: a commit without the script starts a session with no hook
    if not _regular(script):
        return "script-differs"  # axis: a symlink or directory at the script path is not the script configure wrote
    wanted = script_text(commands, inputs).encode("utf-8")
    if _blob(repo_root, script) != wanted:
        return "script-differs"  # axis: script bytes that differ from configure's mean a stale or other hook runs
    body = _blob(repo_root, settings) if _regular(settings) else None
    try:
        data = json.loads(body.decode("utf-8")) if body is not None else None
    except ValueError:
        data = None
    if not _registers(data):
        return "settings-not-registered"  # axis: settings that do not register an enabled startup command never run the script
    if adopted is not None:
        base = _resolve(repo_root, adopted)
        if base is None:
            return "commit-unreadable"  # axis: an adopted head that does not resolve cannot be compared
        for path in inputs:
            norm = posixpath.normpath(path)
            ours = _entry(repo_root, resolved, norm)
            theirs = _entry(repo_root, base, norm)
            if ours is False or theirs is False:
                return "commit-unreadable"  # axis: an input that cannot be listed cannot be compared
            if ours is None or theirs is None:
                gap = _ancestor_gap(repo_root, (resolved, base), norm)
                if gap:
                    return gap
            if ours is None and theirs is None:
                continue
            if (ours and not _regular(ours)) or (theirs and not _regular(theirs)):
                return "adopted-input-not-a-file"  # axis: a symlink, tree or submodule input is read through its target, so equal entries prove nothing
            if not (ours and theirs and ours[2] == theirs[2]):
                return "adopted-inputs-differ"  # axis: an input changed by the adopted branch is not refreshed by the hook already started
    return None


_REWRITE_FIX = ("set configure's item 17, 18 or 19 again (any set rewrites the hook files), then commit "
                "and push the settings file and the hook script on the branch builds start from")
# gap token -> (sentence, fix), lowercase fragments with no trailing period: the one home of the
# owner-facing words for a `branch_gap` token, plus `settings-unreadable`, which only callers give
GAP_TEXT = {
    "commit-unreadable": (
        "its commit could not be read on this machine, so it cannot be shown to carry the hook",
        "make sure this machine's checkout of the project can read that branch's commit (fetch it if "
        "it is missing)"),
    "script-missing": ("it has no dependency hook script", _REWRITE_FIX),
    "script-differs": (
        "its dependency hook script is not the one configure writes now (an older plugin's, or "
        "edited by hand)", _REWRITE_FIX),
    "settings-not-registered": (
        "its settings file does not register the dependency hook to run at session start",
        _REWRITE_FIX),
    "adopted-inputs-differ": (
        "a setup file the build adopts changed since the hook ran",
        "bring the adopted branch's dependency-file change into the branch the build starts from "
        "first"),
    "adopted-input-not-a-file": (
        "a setup file the build adopts is a link or sits under a linked folder, so it cannot be "
        "compared",
        "point both the setup command and configure's setup inputs at the regular file itself, with "
        "no link in between"),
    "settings-unreadable": (
        "this project's setup settings (configure items 17 to 19) could not be read",
        "set configure's items 17 to 19 again so they can be read"),
}


# a settings `env` key that names a credential, and the one value that is allowed there: a bare
# `$NAME` / `${NAME}` reference
_CREDENTIAL_ENV_KEYS = {"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY",
                        "AWS_SESSION_TOKEN"}
_CREDENTIAL_ENV_SUFFIXES = ("_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY", "_SECRET_KEY",
                            "_ACCESS_KEY")
_BARE_REFERENCE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")


def _credential_env_name(key):
    name = str(key).upper()
    return name in _CREDENTIAL_ENV_KEYS or name.endswith(_CREDENTIAL_ENV_SUFFIXES)


def _env_carries_credential(settings):
    """True when the settings `env` block gives a credential-named key a populated value that is
    not a bare `$NAME` / `${NAME}` reference (the content scan cannot know an opaque value)."""
    env = settings.get("env") if isinstance(settings, dict) else None
    if not isinstance(env, dict):
        return False
    for key, value in env.items():
        if not _credential_env_name(key):
            continue
        if value is None or value == "":
            continue
        if isinstance(value, str) and _BARE_REFERENCE_RE.fullmatch(value.strip()):
            continue
        return True
    return False


def _settings_secret_shaped(settings):
    """True when the settings about to be written carry a credential: the shared whole-text scan
    finds a shape in the serialized file, or the `env` block holds a credential-named literal."""
    from cloud_setup_text import _scan  # lazy: that module imports this one back
    text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
    return bool(_scan(text)) or _env_carries_credential(settings)


def _skipped(reason):
    # record mode exits 2 when it declines, so the setup text logs that the record failed
    return 'echo "superheroes: dependency hook skipped: %s"; exit $((RECORD * 2))' % reason


def script_text(commands, inputs):
    """The hook script. Every embedded value is shell-quoted; nothing in it fails the session."""
    quoted_inputs = " ".join(shlex.quote(i) for i in inputs)
    quoted_commands = " ".join(shlex.quote(c) for c in commands)
    lines = [
        "#!/bin/bash",
        "# Written by superheroes configure, which rewrites or removes it. Do not edit by hand.",
        "# In a cloud session it re-runs the project's setup commands when the files they depend on",
        "# changed since the last successful run. It never fails the session.",
        "FINGERPRINT=%s" % shlex.quote(fingerprint(commands, inputs)),
        "",
        "# Record mode is checked before the cloud guard: the cloud's setup script may run without",
        "# CLAUDE_CODE_REMOTE. It exits 2 when it declines to record; every other path exits 0.",
        'RECORD=0',
        'if [ "${1-}" = "--record" ]; then',
        "  RECORD=1",
        '  if [ "${2-}" != "$FINGERPRINT" ]; then',
        '    echo "superheroes: dependency hook not recorded: the setup text and this hook list '
        'different setup commands or inputs"',
        "    exit 2",
        "  fi",
        'elif [ "${CLAUDE_CODE_REMOTE-}" != "true" ]; then',
        "  exit 0",
        "fi",
        "",
        "# The repository root, from this script's own path.",
        'cd "$(dirname "$0")/../.." || exit $((RECORD * 2))',
        "",
        "# The state and the log live inside .git, never in the working tree.",
        'STATE=$(git rev-parse --git-path %s 2>/dev/null) && [ -n "$STATE" ] \\' % HASH_NAME,
        '  || { %s; }' % _skipped("git could not name its state file"),
        'LOG=$(git rev-parse --git-path %s 2>/dev/null) && [ -n "$LOG" ] \\' % LOG_NAME,
        '  || { %s; }' % _skipped("git could not name its log file"),
        "",
        'if command -v sha256sum >/dev/null 2>&1; then HASHER="sha256sum"',
        'elif command -v shasum >/dev/null 2>&1; then HASHER="shasum -a 256"',
        "else %s" % _skipped("no sha256 tool"),
        "fi",
        "",
        "# The hash covers the fingerprint and, in list order, each input's size and bytes (or that it",
        "# is missing). An input that exists but is not a regular file fails the hash, so it is never",
        "# hashed as missing.",
        "compute_hash() (",
        "  set -o pipefail",
        "  {",
        '    printf "fingerprint %s\\n" "$FINGERPRINT"',
        "    for f in %s; do" % quoted_inputs,
        '      if [ -f "$f" ]; then',
        '        printf "file %s %s\\n" "$f" "$(( $(wc -c < "$f") ))"',
        '        cat -- "$f" || exit 1',
        '      elif [ -e "$f" ] || [ -L "$f" ]; then',
        "        exit 1",
        "      else",
        '        printf "missing %s\\n" "$f"',
        "      fi",
        "    done",
        "  } | $HASHER | { read -r first _; printf \"%s\" \"$first\"; }",
        ")",
        'HASH=$(compute_hash 2>/dev/null) || HASH=""',
        'if [ -z "$HASH" ]; then %s' % _skipped("an input could not be read"),
        "fi",
        "",
        'if [ "$RECORD" = 1 ]; then',
        # axis: a hook the clone's settings do not register as an enabled SessionStart command never runs, so it is never recorded
        "  python3 - %s %s <<'PY' 2>/dev/null" % (shlex.quote(SETTINGS_REL), shlex.quote(HOOK_COMMAND)),
        "import json, re, sys",
        *_STARTS_LINES,
        *_REGISTERS_LINES,
        "try:",
        "    with open(sys.argv[1], encoding='utf-8') as fh:",
        "        data = json.load(fh)",
        "    ok = registers(data, sys.argv[2])",
        "except Exception:",
        "    ok = False",
        "sys.exit(0 if ok else 1)",
        "PY",
        '  [ $? -eq 0 ] \\',
        '    || { echo "superheroes: dependency hook not recorded: not registered as a SessionStart '
        'hook in .claude/settings.json"; exit 2; }',
        '  printf "%s\\n" "$HASH" > "$STATE" 2>/dev/null \\',
        '    || { echo "superheroes: dependency hook not recorded: the state file could not be '
        'written"; exit 2; }',
        "  exit 0",
        "fi",
        "",
        'PREVIOUS=""',
        '[ -f "$STATE" ] && read -r PREVIOUS < "$STATE"',
        # axis: an unchanged hash runs nothing; a changed or never-recorded hash runs the commands
        'if [ "$HASH" = "$PREVIOUS" ]; then',
        "  exit 0",
        "fi",
        "",
        "# The recorded success hash goes before any command runs, so a failed run leaves none and",
        "# the next session runs the commands again, even if the inputs return to an earlier state.",
        'rm -f "$STATE" 2>/dev/null',
        'if [ -e "$STATE" ]; then',
        '  echo "superheroes: dependency hook skipped: the previous record could not be cleared"',
        "  exit 0",
        "fi",
        "",
        "n=0",
        "for cmd in %s; do" % quoted_commands,
        "  n=$((n + 1))",
        '  if ! bash -o pipefail -c "$cmd" </dev/null >>"$LOG" 2>&1; then',
        '    echo "superheroes: cloud setup command $n failed, so dependencies may be out of date; '
        'the next session tries again (log: $LOG)"',
        "    exit 0",
        "  fi",
        "done",
        "",
        'printf "%s\\n" "$HASH" > "$STATE" 2>/dev/null \\',
        '  || echo "superheroes: dependency hook could not record this run; the next session '
        'runs the setup commands again"',
        "exit 0",
        "",
    ]
    return "\n".join(lines)


def offer_message(commands, inputs):
    """What the owner is told before being asked to add the hook."""
    count = len(commands)
    files = ", ".join(inputs) if inputs else "no files are listed yet"
    return (
        "The dependency hook is optional, and you choose it per project. It adds two files to this "
        "project's repository: one new start-of-session entry in .claude/settings.json, and a small "
        "script. You commit and push them, because cloud sessions start from the pushed repository. "
        "In a cloud session it checks the listed files (%s) and re-runs your %d listed setup "
        "command%s only when they changed, so a session with nothing changed starts in a few "
        "seconds. A command that fails never stops the session: it prints one line, and the next "
        "session tries again. Without the hook, a change to those files makes the cloud check "
        "report the setup text out of date and ask you to paste it again.\n\n"
        "Add the dependency hook?" % (files, count, "" if count == 1 else "s"))


def _is_ours(hook, script_rel=SCRIPT_REL):
    return (isinstance(hook, dict) and isinstance(hook.get("command"), str)
            and _invokes_script(hook["command"], script_rel=script_rel))


def _invokes_script(command, script_rel=SCRIPT_REL):
    """True when `command` runs the managed script: the script path is the program, or the argument
    of a bare bash/sh. A command that only mentions the path (an argument to another tool, a longer
    filename such as `...sh.backup`) is not ours. `script_rel` names another managed script (the
    plugin pin hook shares this editor)."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if tokens and os.path.basename(tokens[0]) in ("bash", "sh"):
        tokens = tokens[1:]
    if not tokens:
        return False
    target = tokens[0].replace("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR")
    return target == script_rel or target.endswith("/" + script_rel)


def _load_settings(path):
    """The parsed settings object, or None when there is no file; _Refused when it cannot be read
    as the shape the hook edits."""
    if not os.path.lexists(path):
        return None
    try:
        with open(path, "rb") as fh:
            obj = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        raise _Refused("settings-unreadable")
    if not isinstance(obj, dict):
        raise _Refused("settings-unreadable")
    hooks = obj.get("hooks")
    if "hooks" in obj and not isinstance(hooks, dict):
        raise _Refused("settings-unreadable")
    if "hooks" in obj and "SessionStart" in hooks:
        groups = hooks["SessionStart"]
        if not isinstance(groups, list):
            raise _Refused("settings-unreadable")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise _Refused("settings-unreadable")
    return obj


def _session_groups(obj):
    hooks = obj.get("hooks") if isinstance(obj, dict) else None
    groups = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    return groups if isinstance(groups, list) else []


def _remove_ours(obj, script_rel=SCRIPT_REL):
    """Takes every hook of ours out of `obj` (in place), dropping a group, list or key only when
    that removal emptied it. Returns the number removed."""
    removed = 0
    groups = _session_groups(obj)
    kept = []
    for group in groups:
        inner = group["hooks"]
        mine = [h for h in inner if _is_ours(h, script_rel=script_rel)]
        if not mine:
            kept.append(group)
            continue
        removed += len(mine)
        group["hooks"] = [h for h in inner if not _is_ours(h, script_rel=script_rel)]
        if group["hooks"]:
            kept.append(group)
    if removed:
        hooks = obj["hooks"]
        if kept:
            hooks["SessionStart"] = kept
        else:
            del hooks["SessionStart"]
            if not hooks:
                del obj["hooks"]
    return removed


def _atomic_write(path, data, mode):
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def _mode_of(path, default):
    try:
        return os.stat(path).st_mode & 0o7777
    except OSError:
        return default


def _valid_list(value):
    return isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value)


def _sync(repo_root, commands, inputs, enabled, changed):
    desired = enabled is True and bool(commands)
    script_path = os.path.join(repo_root, *SCRIPT_REL.split("/"))
    settings_path = os.path.join(repo_root, *SETTINGS_REL.split("/"))
    if desired and not (_valid_list(commands) and _valid_list(inputs)):
        raise _Refused("invalid-arguments")
    settings = _load_settings(settings_path)
    new_hook = {"type": "command", "command": HOOK_COMMAND, "timeout": HOOK_TIMEOUT_SECONDS}

    # every change is computed here, before anything is written
    write_script = None
    delete_script = False
    write_settings = None
    delete_settings = False
    if desired:
        if isinstance(settings, dict) and settings.get("disableAllHooks") is True:
            # the hook could not run, and record mode rejects these settings; nothing is written
            raise _Refused("settings-hooks-disabled")
        wanted = script_text(commands, inputs).encode("utf-8")
        if _read_bytes(script_path) != wanted or _mode_of(script_path, 0) != 0o755:
            write_script = wanted
        if settings is None:
            settings = {}
            was_missing = True
        else:
            was_missing = False
        mine = [h for g in _session_groups(settings) for h in g["hooks"] if _is_ours(h)]
        # in place also needs the group holding it to run at startup, as record mode requires
        starts = all(_group_starts(g) for g in _session_groups(settings)
                     if any(_is_ours(h) for h in g["hooks"]))
        if was_missing or mine != [new_hook] or not starts:
            _remove_ours(settings)
            hooks = settings.setdefault("hooks", {})
            hooks.setdefault("SessionStart", []).append({"hooks": [new_hook]})
            write_settings = settings
    else:
        if settings is not None and _remove_ours(settings):
            if settings == {}:
                delete_settings = True
            else:
                write_settings = settings
        delete_script = os.path.lexists(script_path)

    if not os.path.isdir(repo_root) and (write_script is not None or write_settings is not None):
        raise OSError("the repository root does not exist")
    # the settings the hook relies on are scanned even when the existing entry is reused
    checked = write_settings if write_settings is not None else (settings if desired else None)
    if checked is not None:
        if _settings_secret_shaped(checked):
            # nothing is written, the script included: the owner is told to commit this file
            raise _Refused("settings-secret-shaped")
    if write_script is not None:
        _atomic_write(script_path, write_script, 0o755)
        changed.add(SCRIPT_REL)
    if write_settings is not None:
        data = (json.dumps(write_settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        _atomic_write(settings_path, data, _mode_of(settings_path, 0o644))
        changed.add(SETTINGS_REL)
    if delete_settings:
        os.remove(settings_path)
        changed.add(SETTINGS_REL)
    if delete_script:
        os.remove(script_path)
        changed.add(SCRIPT_REL)
    if not changed:
        return "noop"
    return "written" if desired else "removed"


def sync(repo_root, commands, inputs, enabled):
    """Makes the hook files match `(commands, inputs, enabled)`; see the module docstring.
    Returns {"action": "written" | "removed" | "noop" | "refused", "reason": token or None,
    "changed": [repo-relative paths written or deleted, sorted]}."""
    changed = set()
    try:
        action = _sync(repo_root, commands, inputs, enabled, changed)
        reason = None
    except _Refused as refusal:
        action, reason = "refused", refusal.reason
    except OSError:
        action, reason = "refused", "hook-files-unwritable"
    return {"action": action, "reason": reason, "changed": sorted(changed)}


def _offer_refusal(reason, detail):
    sys.stderr.write(json.dumps({"action": "refused", "reason": reason, "detail": detail}) + "\n")
    return 1


def _offer(cwd, root):
    """The offer for the project at `cwd`, printed as one json line; 1 when there is none to make."""
    import project_config
    import store_core
    commands_item = project_config.get_item(
        cwd, project_config.CLOUD_SETUP_COMMANDS_SLUG, root=root, persist_backfill=False)
    commands = commands_item.get("raw")
    if not (_valid_list(commands) and commands):
        return _offer_refusal("no-setup-commands", "The project lists no cloud setup commands "
                              "(configure item 17), so there is nothing for a hook to keep current.")
    inputs_item = project_config.get_item(
        cwd, project_config.CLOUD_SETUP_INPUTS_SLUG, root=root, persist_backfill=False)
    stored = inputs_item.get("raw")
    if stored is None:
        try:
            repo_root = store_core.repo_root(cwd)
        except store_core.RepoRootUnavailable:
            return _offer_refusal("repo-root-unavailable", "The repository root cannot be found, "
                                  "so the files the setup depends on cannot be detected.")
        # axis: the offered list follows item 18's validator, as item 17's fill does
        inputs, source = project_config._detected_inputs(repo_root), "detected"
    elif _valid_list(stored) and project_config.validate_item_value(
            project_config._item_by_slug(project_config.CLOUD_SETUP_INPUTS_SLUG), list(stored)) is None:
        inputs, source = list(stored), "stored"
    else:
        return _offer_refusal("setup-inputs-malformed", "The project's setup inputs (configure "
                              "item 18) are not a list of paths.")
    sys.stdout.write(json.dumps({
        "action": "offer", "message": offer_message(commands, inputs), "commands": len(commands),
        "inputs": inputs, "inputsSource": source}) + "\n")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_dependency_hook.py")
    parser.add_argument("verb", choices=["offer"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return _offer(args.cwd or os.getcwd(), args.root)


if __name__ == "__main__":
    sys.exit(main())
