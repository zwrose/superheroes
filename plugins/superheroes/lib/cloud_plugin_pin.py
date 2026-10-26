"""The plugin pin hook: the committed start-of-session script that keeps a project's cloud sessions on
the superheroes plugin commit its pin file names, and the one place that writes, rewrites and removes
it.

A plugin release must reach a project's cloud builds without anyone pasting new setup text. The
pasted setup text installs the plugin at one commit and the platform caches that; this SessionStart
hook, committed in the project's repository, installs the plugin at the commit named in a small
committed pin file, only when the installed plugin is at a different commit. The hook files in a
repository are exactly a function of the pin: with a pin, `.claude/settings.json` holds exactly one
hook object of ours, the script holds exactly `script_text()` and the pin file holds exactly
`pin_text(pin)`; with none, none of the three exists and no other part of the settings file changes.
`sync` is the single chokepoint that makes it so.

  cloud_plugin_pin.py {write,remove,status} [--cwd D] [--commit C]

The readers (`at_commit`, `in_tree`) answer a different question from `sync`: will a cloud session
starting on this tree run the right hook? They accept a registration the hook still runs under
(duplicates, another timeout), where `sync` rewrites it.

Standard library and the plugin's lib modules. Expected failures are refusals with a `reason` token,
never a raise.
"""
import argparse
import json
import os
import re
import shlex
import sys

import cloud_dependency_hook as hook
import cloud_pass

SCRIPT_REL = ".claude/hooks/superheroes-plugin-pin.sh"
PIN_REL = ".claude/superheroes-plugin-pin"
SETTINGS_REL = hook.SETTINGS_REL
HOOK_COMMAND = 'bash "$CLAUDE_PROJECT_DIR/%s"' % SCRIPT_REL
HOOK_TIMEOUT_SECONDS = 300
LOG_NAME = "superheroes-plugin-pin.log"
PIN_KEYS = ("source", "commit", "subdir", "version")

_VERSION_RE = re.compile(r"\d+\.\d+\.\d+", re.ASCII)
_PIN_HEADER = ("# The superheroes plugin the cloud sessions of this project install. Written by "
               "superheroes; a release moves it with one commit.")
_NONREGULAR = object()  # a link, folder or submodule where a file belongs


def _valid(pin):
    """True when `pin` is a dict of exactly the four keys, each a plain string of its kind."""
    from cloud_setup_text import _COMMIT_RE, _SOURCE_RE, _plain_relative
    return (isinstance(pin, dict) and set(pin) == set(PIN_KEYS)
            and all(isinstance(pin[k], str) for k in PIN_KEYS)
            and _SOURCE_RE.fullmatch(pin["source"]) is not None
            and _COMMIT_RE.fullmatch(pin["commit"]) is not None
            and _plain_relative(pin["subdir"]) and _VERSION_RE.fullmatch(pin["version"]) is not None)


def pin_text(pin):
    """The pin file's exact text. Raises ValueError on an invalid pin; callers validate first."""
    if not _valid(pin):
        raise ValueError("invalid plugin pin")
    return "\n".join([_PIN_HEADER] + ["%s=%s" % (k, pin[k]) for k in PIN_KEYS]) + "\n"


def parse_pin(text):
    """The pin as a dict of the four keys, or None. Strict: every line is blank, a comment or
    `key=value` with a known key, each key exactly once, every value plain."""
    if not isinstance(text, str):
        return None
    pin = {}
    for line in text.split("\n"):
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or key not in PIN_KEYS or key in pin:
            return None  # axis: a line that is not key=value, an unknown key or a repeat is an invalid pin
        pin[key] = value
    return pin if _valid(pin) else None


def script_text(plugin_dir=None, source_dir=None):
    """The hook script. Every embedded value is shell-quoted; every failure it handles exits 0.
    Production readers compare against the defaults; tests pass temp directories."""
    from cloud_setup_text import SOURCE_DIR, _plain_absolute
    plugin_dir = cloud_pass.CLOUD_PLUGIN_DIR if plugin_dir is None else plugin_dir
    source_dir = SOURCE_DIR if source_dir is None else source_dir
    if not (_plain_absolute(plugin_dir) and _plain_absolute(source_dir)):
        raise ValueError("the plugin and source directories must be plain absolute paths")
    q = shlex.quote
    lines = [
        "#!/bin/bash",
        "# Written by superheroes, which rewrites or removes it. Do not edit by hand.",
        "# In a cloud session it installs the superheroes plugin at the commit named in the pin file",
        "# when the installed plugin is not at that commit and version. Every failure it handles ends in",
        "# exit 0 with a one-line notice; a hook that cannot start, or that the session's hook timeout",
        "# cancels, is reported by the session itself.",
        "set +e +u",
        "LINK=%s" % q(plugin_dir),
        "SRC_DIR=%s" % q(source_dir),
        "PIN=%s" % q(PIN_REL),
        "",
        'if [ "${CLAUDE_CODE_REMOTE-}" != "true" ]; then',
        "  exit 0",
        "fi",
        "export LC_ALL=C GIT_TERMINAL_PROMPT=0",
        'cd "$(dirname "$0")/../.." 2>/dev/null || exit 0',
        "",
        "# The log lives inside .git. Command output goes there; the session sees only this script's",
        "# one-line notices.",
        'LOG=$(git rev-parse --git-path %s 2>/dev/null) && [ -n "$LOG" ] || LOG=/dev/null' % q(LOG_NAME),
        "",
        'INSTALLED=$(git -C "$LINK/" rev-parse HEAD 2>/dev/null) || INSTALLED=""',
        "skip() {",
        '  echo "superheroes: plugin pin not applied: $1; this session runs the plugin already '
        'installed (${INSTALLED:-none})."',
        "  exit 0",
        "}",
        "# The first line of a file, also when it has no final newline; empty when it cannot be read.",
        "first_line() {",
        '  local v=""',
        '  { IFS= read -r v < "$1"; } 2>/dev/null',
        "  printf '%s' \"$v\"",
        "}",
        "",
        "# The pin is read with the same strict rules as the Python reader: every line is blank, a",
        "# comment or key=value, and each of the four keys appears exactly once with a plain value.",
        "SOURCE_RE='^https://[A-Za-z0-9][A-Za-z0-9._~:/-]*$'",
        "PATH_RE='^[A-Za-z0-9._/-]+$'",
        "COMMIT_RE='^[0-9a-f]{40}$'",
        "VERSION_RE='^[0-9]+\\.[0-9]+\\.[0-9]+$'",
        '[ -f "$PIN" ] || skip "the pin file is missing"',
        "SEEN=' '",
        'while IFS= read -r line || [ -n "$line" ]; do',
        "  case \"$line\" in ''|'#'*) continue ;; esac",
        '  [[ "$line" =~ ^([a-z]+)=(.*)$ ]] || skip "the pin file has a line that is not key=value"',
        "  key=${BASH_REMATCH[1]}; value=${BASH_REMATCH[2]}",
        '  case "$SEEN" in *" $key "*) skip "the pin file repeats $key" ;; esac',
        '  SEEN="$SEEN$key "',
        '  case "$key" in',
        '    source) [[ "$value" =~ $SOURCE_RE ]] || skip "the pin source is not an https address"',
        "      SOURCE=$value ;;",
        '    commit) [[ "$value" =~ $COMMIT_RE ]] || skip "the pin commit is not a full lowercase sha"',
        "      COMMIT=$value ;;",
        '    subdir) [[ "$value" =~ $PATH_RE && "$value" != /* && "/$value/" != */../* ]] \\',
        '        || skip "the pin subdir is not a plain relative path"',
        "      SUBDIR=$value ;;",
        '    version) [[ "$value" =~ $VERSION_RE ]] || skip "the pin version is not x.y.z"',
        "      VERSION=$value ;;",
        '    *) skip "the pin file has an unknown key" ;;',
        "  esac",
        'done < "$PIN" 2>/dev/null',
        "for key in source commit subdir version; do",
        '  case "$SEEN" in *" $key "*) ;; *) skip "the pin file has no $key" ;; esac',
        "done",
        "",
        "# axis: a session already at the pinned commit and version fetches nothing",
        'if [ "$INSTALLED" = "$COMMIT" ] && [ "$(first_line "$LINK/version.txt")" = "$VERSION" ]; then',
        "  exit 0",
        "fi",
        "",
        "# The pinned tree is fetched into a new directory of its own, beside the setup text's, so two",
        "# sessions fetching at once never share or delete a tree; it is linked only once its commit and",
        "# version are the pin's. The fetch and the checkout are each bounded where timeout exists.",
        'TIMEOUT=""',
        'command -v timeout >/dev/null 2>&1 && TIMEOUT="timeout 120"',
        'DEST=""',
        "drop() {",
        '  [ -n "$DEST" ] && rm -rf "$DEST" >>"$LOG" 2>&1',
        '  skip "$1"',
        "}",
        # axis: each fetch writes, and on failure deletes, only a directory it made itself
        "if ! {",
        '  mkdir -p "$(dirname "$SRC_DIR")" && DEST=$(mktemp -d "$SRC_DIR-$COMMIT.XXXXXX") \\',
        '    && (cd "$DEST" && git init -q \\',
        '      && $TIMEOUT git fetch -q --depth 1 "$SOURCE" "$COMMIT" \\',
        "      && $TIMEOUT git checkout -q --detach FETCH_HEAD)",  # axis: the checkout is bounded too
        '} >>"$LOG" 2>&1; then',
        '  drop "the pinned commit could not be fetched"',
        "fi",
        "",
        # axis: a tree whose commit or version is not the pin's is never linked
        'GOT=$(git -C "$DEST" rev-parse HEAD 2>/dev/null) || GOT=""',
        '[ "$GOT" = "$COMMIT" ] || drop "the fetched plugin is not at the pinned commit"',
        'GOT_VERSION=$(first_line "$DEST/$SUBDIR/version.txt")',
        '[ "$GOT_VERSION" = "$VERSION" ] || drop "the fetched plugin is version ${GOT_VERSION:-unknown}, '
        'not the pinned $VERSION"',
        "",
        "# The link is replaced only by renaming a new link over it, so it is never absent: GNU mv -T and",
        "# BSD mv -h each rename onto the link itself rather than into the folder it points to. A mv with",
        "# neither leaves the old link in place.",
        # axis: the link is only ever renamed over, never removed and made again
        'TMPLINK="$LINK.pin-tmp.$$"',
        "swap() {",
        '  mkdir -p "$(dirname "$LINK")" && ln -sfn "$DEST/$SUBDIR" "$TMPLINK" || return 1',
        '  case "$(mv --version 2>/dev/null)" in',
        '    *"GNU coreutils"*) mv -Tf "$TMPLINK" "$LINK" ;;',
        '    *) mv -fh "$TMPLINK" "$LINK" ;;',
        "  esac",
        "}",
        'swap >>"$LOG" 2>&1 || { rm -f "$TMPLINK" >>"$LOG" 2>&1; drop "the plugin link could not be replaced"; }',
        'echo "superheroes: plugin $VERSION installed at the pinned commit ${COMMIT:0:12}."',
        "exit 0",
        "",
    ]
    return "\n".join(lines)


def _has_ours(data):
    return any(isinstance(g, dict) and isinstance(g.get("hooks"), list)
               and any(hook._is_ours(h, script_rel=SCRIPT_REL) for h in g["hooks"])
               for g in hook._session_groups(data))


def _registered(data):
    try:
        return hook._registers_scope["registers"](data, HOOK_COMMAND)
    except Exception:
        return False


def _classify(script, settings, pin):
    """The reader result from the three files' contents: None when absent, _NONREGULAR for a link or
    folder, else bytes. Broken reasons come in the precedence the module's contract fixes."""
    data = None
    if isinstance(settings, bytes):
        try:
            data = json.loads(settings.decode("utf-8"))
        except ValueError:
            data = None
    if script is None and pin is None and not _has_ours(data):
        return {"state": "absent", "reason": None, "pin": None}
    broken = None
    if script is None:
        broken = "script-missing"  # axis: a pin or hook entry without the script starts no hook
    elif script != script_text().encode("utf-8"):
        broken = "script-differs"  # axis: bytes that differ from ours mean a stale or other hook runs
    elif not _registered(data):
        broken = "settings-not-registered"  # axis: settings that register no startup command never run the script
    elif pin is None:
        broken = "pin-missing"
    parsed = None
    if broken is None:
        try:
            parsed = parse_pin(pin.decode("utf-8")) if isinstance(pin, bytes) else None
        except UnicodeError:
            parsed = None
        broken = None if parsed else "pin-invalid"  # axis: a pin with any invalid field is never valid
    if broken:
        return {"state": "broken", "reason": broken, "pin": None}
    return {"state": "valid", "reason": None, "pin": parsed}


def in_tree(repo_root):
    """The reader result for the working tree: absent, valid or broken. A link or folder at one of
    the paths counts as present and broken."""
    contents = []
    for rel in (SCRIPT_REL, SETTINGS_REL, PIN_REL):
        path = os.path.join(repo_root, *rel.split("/"))
        if not os.path.lexists(path):
            contents.append(None)
        elif os.path.islink(path) or not os.path.isfile(path):
            contents.append(_NONREGULAR)
        else:
            body = hook._read_bytes(path)
            contents.append(_NONREGULAR if body is None else body)
    return _classify(*contents)


def _read_commit(repo_root, resolved):
    """The three files' contents at `resolved`, or None when the tree cannot be read."""
    contents = []
    for rel in (SCRIPT_REL, SETTINGS_REL, PIN_REL):
        entry = hook._entry(repo_root, resolved, rel)
        if entry is False:
            return None
        if entry is None:
            contents.append(None)
        elif not hook._regular(entry):
            contents.append(_NONREGULAR)
        else:
            body = hook._blob(repo_root, entry)
            if body is None:
                return None
            contents.append(body)
    return contents


def at_commit(repo_root, commit):
    """{"state": "absent" | "valid" | "broken", "reason": token or None, "pin": dict or None} for the
    tree at `commit`. Never raises. A commit that does not resolve or list falls back to the working
    tree: absent there is absent, anything else is broken with `commit-unreadable`."""
    try:
        resolved = hook._resolve(repo_root, commit)
        contents = _read_commit(repo_root, resolved) if resolved else None
        if contents is not None:
            return _classify(*contents)
        if in_tree(repo_root)["state"] == "absent":
            return {"state": "absent", "reason": None, "pin": None}
        # axis: hook files in the working tree and a commit that cannot be read are never absent
        return {"state": "broken", "reason": "commit-unreadable", "pin": None}
    except Exception:
        return {"state": "broken", "reason": "commit-unreadable", "pin": None}


def _secret_shaped(texts, settings):
    """True when a text to be written carries a secret shape, or the settings relied on a credential."""
    from cloud_setup_text import _scan
    return any(_scan(t) for t in texts) or (
        settings is not None and hook._settings_secret_shaped(settings))


def _sync(repo_root, pin, changed):
    desired = pin is not None
    if desired and not _valid(pin):
        raise hook._Refused("invalid-pin")
    script_path = os.path.join(repo_root, *SCRIPT_REL.split("/"))
    pin_path = os.path.join(repo_root, *PIN_REL.split("/"))
    settings_path = os.path.join(repo_root, *SETTINGS_REL.split("/"))
    settings = hook._load_settings(settings_path)
    new_hook = {"type": "command", "command": HOOK_COMMAND, "timeout": HOOK_TIMEOUT_SECONDS}

    # every change is computed here, before anything is written
    writes = {}
    deletes = []
    write_settings = None
    delete_settings = False
    texts = []
    if desired:
        if isinstance(settings, dict) and settings.get("disableAllHooks") is True:
            # axis: the hook could not run under these settings; nothing is written
            raise hook._Refused("settings-hooks-disabled")
        texts = [script_text(), pin_text(pin)]
        for path, text, mode in ((script_path, texts[0], 0o755), (pin_path, texts[1], 0o644)):
            data = text.encode("utf-8")
            if (hook._read_bytes(path) != data or hook._mode_of(path, 0) != mode
                    or os.path.islink(path)):
                writes[path] = (data, mode)
        was_missing = settings is None
        settings = {} if was_missing else settings
        mine = [h for g in hook._session_groups(settings) for h in g["hooks"]
                if hook._is_ours(h, script_rel=SCRIPT_REL)]
        starts = all(hook._group_starts(g) for g in hook._session_groups(settings)
                     if any(hook._is_ours(h, script_rel=SCRIPT_REL) for h in g["hooks"]))
        if (was_missing or mine != [new_hook] or not starts
                or os.path.islink(settings_path)):
            hook._remove_ours(settings, script_rel=SCRIPT_REL)
            settings.setdefault("hooks", {}).setdefault("SessionStart", []).append(
                {"hooks": [new_hook]})
            write_settings = settings
    else:
        if settings is not None and hook._remove_ours(settings, script_rel=SCRIPT_REL):
            delete_settings = settings == {}
            write_settings = None if delete_settings else settings
        deletes = [p for p in (script_path, pin_path) if os.path.lexists(p)]

    if not os.path.isdir(repo_root) and (writes or write_settings is not None):
        raise OSError("the repository root does not exist")
    # the settings the hook relies on are scanned even when the existing entry is reused
    checked = write_settings if write_settings is not None else (settings if desired else None)
    if _secret_shaped(texts, checked):  # axis: nothing is written, the script and pin included
        raise hook._Refused("secret-shaped")
    for path, (data, mode) in writes.items():
        hook._atomic_write(path, data, mode)
        changed.add(os.path.relpath(path, repo_root).replace(os.sep, "/"))
    if write_settings is not None:
        data = (json.dumps(write_settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        hook._atomic_write(settings_path, data, hook._mode_of(settings_path, 0o644))
        changed.add(SETTINGS_REL)
    if delete_settings:
        os.remove(settings_path)
        changed.add(SETTINGS_REL)
    for path in deletes:
        os.remove(path)
        changed.add(os.path.relpath(path, repo_root).replace(os.sep, "/"))
    if not changed:
        return "noop"
    return "written" if desired else "removed"


def sync(repo_root, pin):
    """Makes the hook files match `pin` (a dict to write, None to remove); see the module docstring.
    Returns {"action": "written" | "removed" | "noop" | "refused", "reason": token or None,
    "changed": [repo-relative paths written or deleted, sorted]}."""
    changed = set()
    try:
        action = _sync(repo_root, pin, changed)
        reason = None
    except hook._Refused as refusal:
        action, reason = "refused", refusal.reason
    except OSError:
        action, reason = "refused", "hook-files-unwritable"
    return {"action": action, "reason": reason, "changed": sorted(changed)}


def installed_pin(cwd, env=None):
    """(pin, None) for the plugin this machine runs, or (None, a refusal dict)."""
    import cloud_setup_text
    try:
        source, commit, subdir = cloud_setup_text._discover(cwd, env)
        version = cloud_setup_text._plugin_version()
    except cloud_setup_text._Refused as refusal:
        return None, {"action": "refused", "reason": refusal.reason, "detail": refusal.detail}
    return {"source": source, "commit": commit, "subdir": subdir, "version": version}, None


def _run(verb, cwd, commit):
    import store_core
    try:
        root = store_core.repo_root(cwd)
    except store_core.RepoRootUnavailable as exc:
        return {"action": "refused", "reason": "repo-root-unavailable", "detail": str(exc),
                "changed": []}
    if verb == "status":
        return at_commit(root, commit or "HEAD")
    if verb == "remove":
        return {**sync(root, None), "detail": None}
    pin, refusal = installed_pin(cwd)
    if refusal:
        return {**refusal, "changed": []}
    result = {**sync(root, pin), "detail": None, "pin": pin}
    if result["action"] == "written":
        result["message"] = ("Commit and push %s: cloud sessions start from the pushed repository, "
                             "so the pin takes effect once it is there." % ", ".join(result["changed"]))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_plugin_pin.py")
    parser.add_argument("verb", choices=["write", "remove", "status"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    result = _run(args.verb, args.cwd or os.getcwd(), args.commit)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("action") == "refused" else 0


if __name__ == "__main__":
    sys.exit(main())
