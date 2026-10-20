"""The cloud dependency hook: the committed start-of-session script that keeps a cloud session's
dependencies current, and the one place that writes, rewrites and removes it.

A project that lists cloud setup commands (configure item 17) can opt in to a SessionStart hook. In
a cloud session the hook re-runs those commands when the files they depend on changed since the
last successful run. The hook files in a repository are exactly a function of
`(commands, inputs, enabled)`: when enabled with at least one command, `.claude/settings.json` holds
exactly one hook object of ours and the script holds exactly `script_text(commands, inputs)`;
otherwise neither exists, and no other part of the settings file changes. `sync` is the single
chokepoint that makes it so.

The module has no command line; callers use `sync`, `fingerprint` and `script_text`.

Standard library only. Expected failures are refusals with a `reason` token, never a raise.
"""
import hashlib
import json
import os
import shlex
import tempfile

SCRIPT_REL = ".claude/hooks/superheroes-cloud-dependencies.sh"
SETTINGS_REL = ".claude/settings.json"
HASH_NAME = "superheroes-cloud-setup-hash"
LOG_NAME = "superheroes-cloud-setup.log"
HOOK_TIMEOUT_SECONDS = 600
HOOK_COMMAND = 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/superheroes-cloud-dependencies.sh"'


class _Refused(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)
        self.reason = reason


def fingerprint(commands, inputs):
    """The sha256 of the command list and the input list, so a changed list is a changed hash."""
    body = json.dumps({"commands": list(commands), "inputs": list(inputs)},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


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
        'if [ "$1" = "--record" ]; then',
        "  RECORD=1",
        '  if [ "$2" != "$FINGERPRINT" ]; then',
        '    echo "superheroes: dependency hook not recorded: the setup text and this hook list '
        'different setup commands or inputs"',
        "    exit 2",
        "  fi",
        'elif [ "$CLAUDE_CODE_REMOTE" != "true" ]; then',
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
        "# is missing).",
        "compute_hash() (",
        "  set -o pipefail",
        "  {",
        '    printf "fingerprint %s\\n" "$FINGERPRINT"',
        "    for f in %s; do" % quoted_inputs,
        '      if [ -f "$f" ]; then',
        '        printf "file %s %s\\n" "$f" "$(( $(wc -c < "$f") ))"',
        '        cat "$f" || exit 1',
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
        "def starts(e):",
        "    m = e.get('matcher')",
        "    if m is None or m in ('', '*'):",
        "        return True",
        "    try:",
        "        return isinstance(m, str) and re.fullmatch(m, 'startup') is not None",
        "    except Exception:",
        "        return False",
        "try:",
        "    with open(sys.argv[1], encoding='utf-8') as fh:",
        "        data = json.load(fh)",
        "    ok = isinstance(data, dict) and data.get('disableAllHooks') is not True",
        "    entries = data.get('hooks', {}).get('SessionStart', []) if ok else []",
        "    ok = ok and any(",
        "        isinstance(h, dict) and h.get('type') == 'command' and h.get('command') == sys.argv[2]",
        "        for e in entries if isinstance(e, dict) and starts(e) for h in (e.get('hooks') or []))",
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


def _is_ours(hook):
    return (isinstance(hook, dict) and isinstance(hook.get("command"), str)
            and SCRIPT_REL in hook["command"])


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


def _remove_ours(obj):
    """Takes every hook of ours out of `obj` (in place), dropping a group, list or key only when
    that removal emptied it. Returns the number removed."""
    removed = 0
    groups = _session_groups(obj)
    kept = []
    for group in groups:
        inner = group["hooks"]
        mine = [h for h in inner if _is_ours(h)]
        if not mine:
            kept.append(group)
            continue
        removed += len(mine)
        group["hooks"] = [h for h in inner if not _is_ours(h)]
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
        wanted = script_text(commands, inputs).encode("utf-8")
        if _read_bytes(script_path) != wanted or _mode_of(script_path, 0) != 0o755:
            write_script = wanted
        if settings is None:
            settings = {}
            was_missing = True
        else:
            was_missing = False
        mine = [h for g in _session_groups(settings) for h in g["hooks"] if _is_ours(h)]
        if was_missing or mine != [new_hook]:
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
