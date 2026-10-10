"""The setup text: the shell script an owner pastes into a cloud environment's setup-script field.

The cloud platform runs it once, as root, when it builds the environment's machine image. It fetches
the plugin at the exact commit the owner's machine runs, installs the two tools a build needs, and,
for a project that keeps its calibration outside the repository, writes that calibration onto the
cloud machine. The text holds no reviewer pass and no other secret: `compose` scans the complete
text it is about to return and refuses when the scan finds anything secret-shaped, and every caller
gets the text only through `compose`.

  cloud_setup_text.py write [--cwd D] [--root D] [--clipboard]

Standard library plus the plugin's own lib modules. Expected failures are refusals with a `reason`
token and one plain sentence, never a raise.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import cloud_pass
import cloud_setup
import config_dir
import core_md
import mode_registry
import project_config
import store_core

REVIEWER_CLI_PACKAGE = "@openai/codex"
DUPLICATION_CHECKER_PACKAGE = "jscpd@5.0.12"
SOURCE_DIR = "/opt/superheroes/plugin-src"
STAMP_FILE = "cloud-setup-stamp"
_CORE_MD = "config/core.md"
# The cloud platform runs nothing before a session starts except this cached script, so a setup
# made at one plugin version stays at that version until new setup text is pasted.
PICKS_UP_VERSION_BY_ITSELF = False

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_LOG = "$HOME/superheroes-cloud-setup.log"
_TOP_FILES = ("registry.json", "meta.json", "doc-policy.json")
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_SOURCE_RE = re.compile(r"https://[A-Za-z0-9][A-Za-z0-9._~:/-]*")
_PATH_RE = re.compile(r"[A-Za-z0-9._/-]+")
_STAMP_RE = re.compile(r"[A-Za-z0-9:._-]+")

# Axis: each entry bites on one secret-shaped form appearing anywhere in the final text.
_SECRET_SHAPES = (
    ("signed token", re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("provider key", re.compile(
        r"(?<![A-Za-z0-9])(?:(?:sk-|ghp_|gho_|ghu_|ghs_|github_pat_|xoxb-|xoxp-|xoxa-)"
        r"[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential assignment", re.compile(
        r"(?<![A-Za-z0-9_])(?:access_token|id_token|refresh_token|OPENAI_API_KEY|%s)"
        r"""["']?\s*[:=]\s*(?:"[^"\s]|'[^'\s]|[^\s"',;}])""" % re.escape(cloud_pass.PASS_ENV),
        re.IGNORECASE)),
    ("bearer credential", re.compile(r"Bearer \S{16,}")),
)


class _Refused(Exception):
    def __init__(self, reason, detail):
        Exception.__init__(self, reason)
        self.reason = reason
        self.detail = detail


def _refused(reason, detail):
    return {"action": "refused", "reason": reason, "detail": detail}


def _end_tag(index):
    return "SUPERHEROES_END_%d" % index


def _plain_relative(path):
    return (isinstance(path, str) and _PATH_RE.fullmatch(path) is not None
            and not path.startswith("/") and ".." not in path.split("/"))


def _plain_absolute(path):
    """An absolute path of plain characters, at least two segments deep (the script removes it)."""
    if not (isinstance(path, str) and _PATH_RE.fullmatch(path) and path.startswith("/")):
        return False
    segments = [s for s in path.split("/") if s]
    return len(segments) >= 2 and ".." not in segments and "." not in segments


def _plugin_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _plugin_version():
    try:
        with open(os.path.join(_plugin_root(), "version.txt"), encoding="utf-8") as fh:
            version = fh.read().strip()
    except (OSError, UnicodeError):
        version = ""
    if not version:
        raise _Refused("plugin-version-unreadable", "The plugin's version file is missing or empty.")
    return version


def _read_json(path):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read())
    except Exception:
        return None


def _discover(cwd, env):
    """(source, commit, subdir) from the Claude config directory's plugin records."""
    def unknown(why):
        return _Refused("plugin-source-unknown", "The plugin's source cannot be found: %s." % why)

    cfg = config_dir.resolve(env=env, cwd=cwd)
    if not cfg:
        raise unknown("the Claude config directory cannot be resolved")
    base = os.path.join(cfg, "plugins")
    installed = _read_json(os.path.join(base, "installed_plugins.json"))
    markets = _read_json(os.path.join(base, "known_marketplaces.json"))
    if not (isinstance(installed, dict) and isinstance(markets, dict)
            and isinstance(installed.get("plugins"), dict)):
        raise unknown("a plugin record file is missing or unreadable")
    here = os.path.realpath(_plugin_root())
    key = record = None
    for name, entries in installed["plugins"].items():
        for entry in entries if isinstance(entries, list) else ():
            path = entry.get("installPath") if isinstance(entry, dict) else None
            if isinstance(path, str) and os.path.realpath(path) == here:
                key, record = name, entry
                break
        if record is not None:
            break
    if record is None or "@" not in key:
        raise unknown("no installed plugin matches this plugin's directory")
    plugin_name, market_name = key.rsplit("@", 1)
    commit = record.get("gitCommitSha")
    if not (isinstance(commit, str) and commit):
        raise unknown("no commit is recorded for the installed plugin")
    market = markets.get(market_name)
    source = market.get("source") if isinstance(market, dict) else None
    if not isinstance(source, dict):
        raise unknown("the plugin's marketplace is not recorded")
    if source.get("source") != "git":
        raise _Refused("plugin-source-unsupported",
                       "The plugin's marketplace is not a git source, which this setup text "
                       "cannot fetch from.")
    url = source.get("url")
    install = market.get("installLocation")
    listing = _read_json(os.path.join(install, ".claude-plugin", "marketplace.json")) \
        if isinstance(install, str) else None
    plugins = listing.get("plugins") if isinstance(listing, dict) else None
    subdir = next((p.get("source") for p in plugins if isinstance(p, dict)
                   and p.get("name") == plugin_name), None) if isinstance(plugins, list) else None
    if not (isinstance(url, str) and isinstance(subdir, str) and subdir):
        raise unknown("the marketplace does not say where the plugin lives")
    return url, commit, subdir[2:] if subdir.startswith("./") else subdir


def _store_files(store):
    """The calibration files that exist under `store`: relative path -> raw bytes."""
    wanted = list(_TOP_FILES)
    try:
        names = sorted(os.listdir(os.path.join(store, "config")))
    except FileNotFoundError:
        names = []
    except OSError:
        raise _Refused("calibration-unreadable", "The calibration's config directory cannot be read.")
    wanted += ["config/" + n for n in names if n.endswith(".md")]
    wanted.append("permission/rules.json")
    out = {}
    for rel in wanted:
        path = os.path.join(store, *rel.split("/"))
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            raise _Refused("calibration-unreadable", "A calibration file exists but cannot be read.")
        out[rel] = data if data.endswith(b"\n") else data + b"\n"
    return dict(sorted(out.items()))


def _calibration(cwd, root):
    """(placed, files). Raises _Refused for a storage mode that is not one of the two known."""
    unknown = _Refused("storage-mode-unknown", "The project's storage mode is not a known one.")
    try:
        mode = mode_registry.resolve(cwd, root, persist_backfill=False)["mode"]
    except mode_registry.UnknownSchemaVersion:
        raise unknown
    except Exception:
        raise _Refused("storage-mode-unknown", "The project's storage mode cannot be determined.")
    if mode == mode_registry.IN_REPO:
        return False, {}
    if mode != mode_registry.GLOBAL:
        raise unknown
    return True, _store_files(mode_registry.project_store_dir(cwd, root))


def calibration_files(cwd, root=None):
    """The calibration the setup text places: relative path -> bytes, sorted; empty when the
    repository itself carries it."""
    return _calibration(cwd, root)[1]


def _without_setting(data):
    """`data` with the cloud-builds setting out of its json block, re-rendered whether or not the
    key was there; `data` itself when it holds no readable setting."""
    try:
        text = data.decode("utf-8")
        obj = json.loads(core_md._json_block_inner_text(text))
        settings = obj.get("projectConfiguration")
        if isinstance(settings, dict):
            settings.pop(project_config.CLOUD_BUILDS_SLUG, None)
        body = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
        return core_md._splice_single_json_block(text, body).encode("utf-8")
    except Exception:
        return data


def _stamp_view(files):
    view = dict(files)
    if _CORE_MD in view:
        view[_CORE_MD] = _without_setting(view[_CORE_MD])
    return view


def stamped_files(cwd, root=None):
    """What the stamp covers: the placed calibration with the cloud-builds setting left out, so
    switching cloud builds on or off never changes the stamp."""
    return _stamp_view(calibration_files(cwd, root))


def _project_name(cwd):
    try:
        remote = store_core.get_remote(cwd)
        return remote.split("/")[-1] if remote else os.path.basename(store_core.repo_root(cwd))
    except Exception:
        return os.path.basename(os.path.abspath(cwd))


def _utc_date(now):
    moment = now if isinstance(now, datetime) else datetime.fromtimestamp(
        time.time() if now is None else now, timezone.utc)
    return moment.astimezone(timezone.utc).date()


def _scan(text):
    """The name of the first secret-shaped form in `text`, else None."""
    return next((name for name, pattern in _SECRET_SHAPES if pattern.search(text)), None)


def _script(head, source, commit, subdir, source_dir, plugin_dir, files, key, stamp):
    parent = os.path.dirname(plugin_dir.rstrip("/"))
    out = [
        "#!/bin/bash",
        "# " + head,
        "# Setup text for a cloud environment: paste it over the whole setup-script field.",
        "# It holds no reviewer pass and no other secret.",
        'LOG="%s"' % _LOG,
        'SRC="%s"' % source_dir,
        'LINK="%s"' % plugin_dir,
        "",
        "# Fetch the plugin at the commit the owner's machine runs.",
        "(",
        '  rm -rf "$SRC" && mkdir -p "$SRC" && cd "$SRC" && git init -q . \\',
        '    && git fetch -q --depth 1 "%s" %s \\' % (source, commit),
        '    && git checkout -q --detach FETCH_HEAD && mkdir -p "%s" \\' % parent,
        '    && ln -sfn "$SRC/%s" "$LINK" \\' % subdir,
        '    && echo "plugin ok $(cat "$SRC/%s/version.txt")" || echo "plugin FAILED"' % subdir,
        ') >> "$LOG" 2>&1 &',
        "",
        "# Install the reviewer tool and the duplication checker.",
        "(",
        '  npm install -g "%s" && echo "reviewer cli ok" || echo "reviewer cli FAILED"'
        % REVIEWER_CLI_PACKAGE,
        '  npm install -g "%s" && echo "duplication checker ok" || echo "duplication checker FAILED"'
        % DUPLICATION_CHECKER_PACKAGE,
        ') >> "$LOG" 2>&1 &',
        "wait",
    ]
    if files:
        out += ["", "# Place the project's calibration.",
                'DEST="$HOME/.claude/superheroes/projects/%s"' % key,
                'mkdir -p "$DEST"', "wrote=0"]
        for index, (rel, data) in enumerate(files.items(), 1):
            tag = _end_tag(index)
            out += ['mkdir -p "$(dirname "$DEST/%s")"' % rel,
                    """cat > "$DEST/%s" <<'%s'""" % (rel, tag)]
            out += [data.decode("utf-8")[:-1], tag, '[ "$?" = 0 ] && wrote=$((wrote + 1))']
        out += ["printf '%%s\\n' '%s' > \"$DEST/%s\"" % (stamp, STAMP_FILE),
                'echo "calibration: $wrote of %d files written" >> "$LOG"' % len(files)]
    out += ["", "# The project's own tool steps, if any, go below this line.",
            'echo "setup end" >> "$LOG"', "exit 0", ""]
    return "\n".join(out)


def _compose(cwd, now, stamp_fn, plugin_source, plugin_commit, plugin_subdir, project_name, root,
             env, source_dir, plugin_dir):
    plugin_dir = cloud_pass.CLOUD_PLUGIN_DIR if plugin_dir is None else plugin_dir
    version = _plugin_version()
    invalid = _Refused("plugin-source-invalid", "The plugin source, commit or directory is not in "
                       "the plain form the setup text accepts.")
    given = (plugin_source, plugin_commit, plugin_subdir)
    if (any(v is None for v in given) and any(v is not None for v in given)) \
            or not (_plain_absolute(source_dir) and _plain_absolute(plugin_dir)):
        raise invalid
    source, commit, subdir = given if plugin_source is not None else _discover(cwd, env)
    if not (isinstance(source, str) and _SOURCE_RE.fullmatch(source)
            and isinstance(commit, str) and _COMMIT_RE.fullmatch(commit)
            and _plain_relative(subdir)):
        raise invalid
    placed, files = _calibration(cwd, root)
    if placed and not files:
        raise _Refused("calibration-missing", "The project keeps its calibration outside the "
                       "repository but none of its calibration files exists.")
    key = mode_registry.config_key(cwd) if placed else None
    bad = [rel for rel in files if not _plain_relative(rel)]
    if placed and not _plain_relative(key):
        bad.append(key)
    tags = {rel: _end_tag(i) for i, rel in enumerate(files, 1)}
    for rel, data in files.items():
        try:
            body = data.decode("utf-8")
        except UnicodeDecodeError:
            bad.append(rel)
            continue
        if "\x00" in body or tags[rel] in body.split("\n"):
            bad.append(rel)
    if bad:
        raise _Refused("calibration-unplaceable", "A calibration file cannot be written safely "
                       "into the script (not text, an unsafe path, or a line that ends its "
                       "here-document).")
    stamp = date = None
    if placed:
        try:
            stamp = (cloud_setup.calibration_stamp if stamp_fn is None else stamp_fn)(
                _stamp_view(files))
        except Exception:
            stamp = None
        if not (isinstance(stamp, str) and _STAMP_RE.fullmatch(stamp)):
            raise _Refused("stamp-unavailable", "The calibration's stamp is not available.")
        moment = _utc_date(now)
        date = moment.strftime("%Y-%m-%d")
        part = "calibration from %d %s" % (moment.day, _MONTHS[moment.month - 1])
    else:
        part = "calibration in the repository"
    name = " ".join((project_name or _project_name(cwd)).splitlines())
    head = "%s · plugin %s · %s" % (name, version, part)
    text = _script(head, source, commit, subdir, source_dir, plugin_dir, files, key, stamp)
    shape = _scan(text)
    if shape:
        where = next((rel for rel, data in files.items()
                      if _scan(data.decode("utf-8"))), None)
        raise _Refused("secret-shaped-content", "Something shaped like a %s is in the setup text%s; "
                       "it was not returned." % (shape, " (in %s)" % where if where else ""))
    return {"action": "written", "reason": None, "text": text, "header": head,
            "pluginVersion": version, "pluginCommit": commit,
            "calibration": {"placed": placed, "files": list(files), "date": date, "stamp": stamp},
            "picksUpVersionByItself": PICKS_UP_VERSION_BY_ITSELF}


def compose(cwd, *, now=None, stamp_fn=None, plugin_source=None, plugin_commit=None,
            plugin_subdir=None, project_name=None, root=None, env=None, source_dir=SOURCE_DIR,
            plugin_dir=None):
    """The setup text and what it carries, or a refusal with no `text` key."""
    try:
        return _compose(cwd, now, stamp_fn, plugin_source, plugin_commit, plugin_subdir,
                        project_name, root, env, source_dir, plugin_dir)
    except _Refused as refusal:
        return _refused(refusal.reason, refusal.detail)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cloud_setup_text.py")
    parser.add_argument("verb", choices=["write"])
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--root", default=None)
    parser.add_argument("--plugin-source", default=None)
    parser.add_argument("--plugin-commit", default=None)
    parser.add_argument("--plugin-subdir", default=None)
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--clipboard", action="store_true")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    result = compose(args.cwd or os.getcwd(), plugin_source=args.plugin_source,
                     plugin_commit=args.plugin_commit, plugin_subdir=args.plugin_subdir,
                     project_name=args.project_name, root=args.root)
    if result["action"] == "written" and args.clipboard:
        try:
            cloud_pass.copy_to_clipboard(result["text"])
        except LookupError:
            result = _refused("no-clipboard", "No clipboard command is on the path.")
        except Exception:
            result = _refused("clipboard-failed", "The clipboard command failed.")
    if result["action"] == "refused":
        sys.stderr.write(json.dumps(result) + "\n")
        return 1
    if args.clipboard:
        sys.stdout.write(json.dumps({k: v for k, v in result.items() if k != "text"}) + "\n")
    else:
        sys.stdout.write(result["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
