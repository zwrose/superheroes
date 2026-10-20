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
import base64
import fnmatch
import hashlib
import json
import os
import re
import shlex
import sys
import time
from datetime import datetime, timezone

import cloud_dependency_hook
import cloud_pass
import architect_config
import cloud_setup
import config_dir
import control_plane
import core_md
import mode_registry
import project_config
import size_count
import store_core

REVIEWER_CLI_PACKAGE = "@openai/codex"
DUPLICATION_CHECKER_PACKAGE = "jscpd@5.0.12"
SANDBOX_TOOL_PACKAGES = "bubblewrap socat"
SOURCE_DIR = "/opt/superheroes/plugin-src"
STAMP_FILE = "cloud-setup-stamp"
SETUP_COMMANDS_STAMP_KEY = "setup-commands"
SETUP_INPUTS_STAMP_KEY = "setup-inputs"
SETUP_HOOK_STAMP_KEY = "setup-dependency-hook"
SETUP_INPUT_STAMP_PREFIX = "setup-input/"
SETUP_INPUT_MISSING_STAMP_PREFIX = "setup-input-missing/"
REQUIREMENTS_PATTERN = "requirements*.txt"
TOOL_STEPS_MARKER = "# The project's own tool steps, if any, go below this line."
# The cloud platform runs nothing before a session starts except this cached script, so a setup
# made at one plugin version stays at that version until new setup text is pasted.
PICKS_UP_VERSION_BY_ITSELF = False

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_LOG = "$HOME/superheroes-cloud-setup.log"
_COMMIT_RE = re.compile(r"[0-9a-f]{40}")
_SOURCE_RE = re.compile(r"https://[A-Za-z0-9][A-Za-z0-9._~:/-]*")
_PATH_RE = re.compile(r"[A-Za-z0-9._/-]+")
_STAMP_RE = re.compile(r"[A-Za-z0-9:._-]+")

# the user-info runs to the last '@' inside one run of characters free of white space, '/', '?'
# and '#' after the '//'; it never crosses white space, so `--registry https://host:8443 @scope/pkg`
# (a URL followed by a separate argument) is not read as `host:8443 @`. The one exception is a word
# that IS the URL (the scheme starts the shell word, as a quoted URL does once split): there white
# space is part of a user name or password, and the user-info still stops at '/', '?' and '#'
_URL_USERINFO_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*)://([^\s/?#@:]*:[^\s/?#]*|[^\s/?#@:]*)@")
_URL_WORD_USERINFO_RE = re.compile(
    r"([A-Za-z][A-Za-z0-9+.-]*)://([^/?#@:\n]*:[^/?#\n]*|[^\s/?#@:]*)@")
_URL_REFERENCE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
_URL_HTTP_SCHEME_RE = re.compile(r"(?:.*\+)?https?", re.IGNORECASE)
_URL_QUOTES_RE = re.compile(r"""\\?["']""")

# the one home of the credential-name rule: a settings `env` key and a `NAME=value` shell word
CREDENTIAL_ENV_KEYS = {"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY",
                       "AWS_SESSION_TOKEN"}
CREDENTIAL_ENV_SUFFIXES = ("_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY", "_SECRET_KEY",
                           "_ACCESS_KEY")
ENV_REFERENCE_RE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
_ASSIGNMENT_WORD_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", re.DOTALL)


def is_credential_env_name(key):
    name = str(key).upper()
    return name in CREDENTIAL_ENV_KEYS or name.endswith(CREDENTIAL_ENV_SUFFIXES)


_SEPARATOR_CHARS = ";&|()\n"
_REDIRECT_CHARS = "<>"
# words that begin a command without being its name: the next word is still a command start
_KEYWORD_WORDS = {"{", "!", "if", "then", "else", "elif", "do", "while", "until", "time"}
# commands that pass their leading `NAME=value` words and options on to the command they run
_WRAPPER_COMMANDS = {"env", "sudo", "command", "exec", "nohup", "nice", "builtin"}
# commands whose every non-option argument that looks like `NAME=value` is an assignment
_DECLARE_COMMANDS = {"export", "declare", "typeset", "local", "readonly"}
# shells whose `-c` argument is a script of its own, scanned with the same rules
_SHELL_COMMANDS = {"bash", "sh", "dash", "zsh"}


def _shell_tokens(text):
    """`text` as a shell reads it, as ("word", segments) and ("sep", operator) tokens. A word's
    segments are (kind, text) pairs after quote removal: kind is "plain" or "dq" (a double-quoted
    part; both can hold a `$NAME` reference) or "lit" (single-quoted, ANSI-C decoded or
    backslash-escaped text, never a reference). A redirection operator is ("redir", operator)."""
    tokens = []
    segments = []
    buf = []
    kind = "plain"
    has_word = False
    i, n = 0, len(text)

    def flush_text():
        if buf:
            segments.append((kind, "".join(buf)))
            del buf[:]

    def end_word():
        nonlocal has_word
        flush_text()
        if has_word:
            tokens.append(("word", list(segments)))
        del segments[:]
        has_word = False

    while i < n:
        c = text[i]
        if c == "'" or (c == "$" and text[i + 1:i + 2] == "'"):
            ansi = c == "$"
            j = i + 2 if ansi else i + 1
            start = j
            while j < n and text[j] != "'":
                j += 2 if ansi and text[j] == "\\" else 1
            body = text[start:j]
            flush_text()
            segments.append(("lit", _ansi_c_decode("$'" + body + "'") if ansi else body))
            has_word = True
            i = j + 1
        elif c == '"':
            j = i + 1
            part = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n and text[j + 1] in '"\\$`\n':
                    if text[j + 1] == "$":
                        flush_text()
                        segments.append(("dq", "".join(part)))
                        part = []
                        segments.append(("lit", "$"))
                    elif text[j + 1] != "\n":
                        part.append(text[j + 1])
                    j += 2
                else:
                    part.append(text[j])
                    j += 1
            flush_text()
            segments.append(("dq", "".join(part)))
            has_word = True
            i = j + 1
        elif c == "\\" and i + 1 < n:
            if text[i + 1] != "\n":
                flush_text()
                segments.append(("lit" if text[i + 1] == "$" else "plain", text[i + 1]))
                has_word = True
            i += 2
        elif c in " \t\r":
            end_word()
            i += 1
        elif c in _SEPARATOR_CHARS or c in _REDIRECT_CHARS:
            digits = [t for k, t in segments if k == "plain"] + ["".join(buf)]
            if c in _REDIRECT_CHARS and has_word and "".join(digits).isdigit():
                buf.clear()
                del segments[:]
                has_word = False
            else:
                end_word()
            j = i + 1
            while j < n and text[j] == c and c != "(" and c != ")" and c != "\n":
                j += 1
            tokens.append(("redir" if c in _REDIRECT_CHARS else "sep", text[i:j]))
            i = j
        else:
            buf.append(c)
            has_word = True
            i += 1
    end_word()
    return tokens


def _word_text(segments):
    return "".join(t for _, t in segments)


class _CredentialAssignment:
    """Pattern-like object (`.search(text)`) for a shell word `NAME=value` in assignment position
    where NAME is credential-named and the value is non-empty and not a bare `$NAME` / `${NAME}`
    reference. Assignment position is what bash or `env` treats as an assignment: the leading
    `NAME=value` words of a simple command (at the start of the text or after `;`, `&&`, `||`,
    `|`, `&`, `(`, `{`, `!` or a newline), and every `NAME=value` argument to `env`, `export`,
    `declare`, `typeset`, `local` or `readonly`. NAME and value are read after quote removal of the
    whole word (`$'...'` decoded), so quoting any part of the word cannot hide it. A word that is an
    argument to another command (`printf 'AWS_SECRET_ACCESS_KEY=%s\\n' "$KEY"`) is not checked."""

    @staticmethod
    def _is_literal(segments):
        # the value as quoted: single-quoted, ANSI-C or escaped text is a literal; only an unquoted
        # or double-quoted bare `$NAME` / `${NAME}` is the exempt reference
        parts = [(k, t) for k, t in segments if t]
        if not _word_text(parts).strip():
            return False
        if len(parts) == 1 and parts[0][0] in ("plain", "dq"):
            return not ENV_REFERENCE_RE.fullmatch(parts[0][1])
        return True

    @classmethod
    def _assignment_is_credential(cls, segments):
        full = _word_text(segments)
        name, eq, _ = full.partition("=")
        if name.endswith("+"):    # `NAME+=value` appends, and assigns just as `NAME=value` does
            name = name[:-1]
            skip_extra = 1
        else:
            skip_extra = 0
        if not eq or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or not is_credential_env_name(name):
            return False
        # drop the first len(name)+1 characters across segments, keeping each remainder's kind
        skip = len(name) + 1 + skip_extra
        value = []
        for kind, part in segments:
            if skip >= len(part):
                skip -= len(part)
                continue
            value.append((kind, part[skip:]))
            skip = 0
        return cls._is_literal(value)

    @classmethod
    def _search_command_text(cls, text, anywhere=False):
        at_start = True    # the next word may be an assignment or the command's name
        declare = False    # inside export / declare / ...: every non-option word is checked
        skip_redirect_target = False
        shell = None       # after a shell's name: "opts" reading its options, "optarg", "script"
        for kind, value in _shell_tokens(text):
            if kind == "sep":
                at_start, declare, shell = True, False, None
                continue
            if kind == "redir":
                skip_redirect_target = True
                continue
            if skip_redirect_target:
                skip_redirect_target = False
                continue
            word = _word_text(value)
            plain = len(value) == 1 and value[0][0] == "plain"
            if shell == "script":
                shell = None
                if cls._search_command_text(word, anywhere):
                    return True
                continue
            if shell == "optarg":
                shell = "opts"
                continue
            if shell == "opts":
                if word in ("-o", "+o", "-O", "+O"):
                    shell = "optarg"
                    continue
                if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", word):
                    shell = "script"
                    continue
                if word.startswith(("-", "+")):
                    continue
                shell = None
            if declare or at_start or anywhere:
                if word.startswith("-"):
                    continue
                if cls._assignment_is_credential(value):
                    return True
                if declare or re.match(r"[A-Za-z_][A-Za-z0-9_]*\+?=", word):
                    continue
                if plain and word in _KEYWORD_WORDS:
                    continue
                base = word.rsplit("/", 1)[-1]
                if base in _DECLARE_COMMANDS:
                    declare, at_start = True, False
                elif base in _WRAPPER_COMMANDS:
                    at_start = True
                elif base in _SHELL_COMMANDS:
                    shell, at_start = "opts", False
                else:
                    at_start = False
        return False

    def search(self, text):
        return self._search(text, False)

    def search_document(self, text):
        """Any `NAME=value` word counts, wherever it stands: for a file or a whole setup text,
        which is prose or markup as much as it is a command."""
        return self._search(text, True)

    def _search(self, text, anywhere):
        texts = [text]
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
        if anywhere:
            # prose and heredocs hold apostrophes that no shell would balance, so a line and a
            # white-space word are each read on their own
            texts += [piece for t in list(texts) for piece in t.splitlines() + t.split()]
        return any(self._search_command_text(t, anywhere) for t in texts)


_ANSI_C_WORD_RE = re.compile(r"""\$'((?:[^'\\]|\\.)*)'""", re.DOTALL)


def _ansi_c_decode(text):
    """Bash renders `$'...'` as the literal text its backslash escapes spell; decode those so a
    quoted password is seen as the literal it is, not as the `$name` it resembles."""
    def decode(match):
        body = match.group(1)
        try:
            return body.encode("latin-1", "backslashreplace").decode("unicode_escape")
        except (UnicodeError, ValueError):
            return body
    return _ANSI_C_WORD_RE.sub(decode, text)


class _UrlCredential:
    """Pattern-like object (`.search(text)`) for a literal credential in `scheme://userinfo@host`.
    Each user-info is split on its first ':'; with a ':' it is refused unless the password part is
    exactly a bare `$NAME` or `${NAME}` (an empty or literal password is refused; the user part may
    be literal beside a reference password); without one it is refused unless it is a bare
    reference. A user-info with no ':' on a scheme that is not http/https (or a `+https` variant) is a user
    name and passes (`ssh://git@host`). Shell quotes and JSON escapes are stripped before the
    parse, so quoting a part cannot hide it."""

    @staticmethod
    def _refuses(text):
        matches = list(_URL_USERINFO_RE.finditer(text))
        # the scheme may follow an option or assignment prefix inside the word (`--index-url=`,
        # `X=`), or an opening quote; a scheme after white space belongs to a separate argument
        for whole in _URL_WORD_USERINFO_RE.finditer(text):
            prefix = text[:whole.start()]
            if not re.search(r"\s", prefix) or prefix.endswith(("'", '"')):
                matches.append(whole)
        for match in matches:
            scheme, userinfo = match.group(1), match.group(2)
            if not userinfo:
                continue
            user, colon, password = userinfo.partition(":")
            user, password = _URL_QUOTES_RE.sub("", user), _URL_QUOTES_RE.sub("", password)
            if colon:
                if not _URL_REFERENCE_RE.fullmatch(password):
                    return True
            elif not _URL_REFERENCE_RE.fullmatch(user) and _URL_HTTP_SCHEME_RE.fullmatch(scheme):
                return True
        return False

    @staticmethod
    def _words(text):
        # one shell word at a time, so a URL never borrows text from a neighbouring argument
        # without comments, a `#` word stays visible; with them, an apostrophe inside a comment
        # cannot make the parse fail and split a quoted URL at its spaces
        words = []
        for comments in (False, True):
            try:
                words += shlex.split(text, comments=comments)
            except ValueError:
                pass
        return words or text.split()

    def search(self, text):
        # shlex drops comments, so the raw white-space words are examined too
        words = list(dict.fromkeys(self._words(text) + text.split()))
        for word in words:
            for form in (word, word.replace("\\/", "/"), _ansi_c_decode(word)):
                if self._refuses(form) or self._refuses(_URL_QUOTES_RE.sub("", form)):
                    return True
        return False


# Axis: each entry bites on one secret-shaped form appearing anywhere in the final text.
_SECRET_SHAPES = (
    ("signed token", re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("provider key", re.compile(
        r"(?<![A-Za-z0-9])(?:(?:%s)[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16})"
        % "|".join(map(re.escape, cloud_setup._SECRET_PREFIXES)))),
    ("registry token", re.compile(
        r"(?<![A-Za-z0-9])npm_[A-Za-z0-9]{30,}"
        # _authToken, then the key's own closing quote, a ':' '=' separator, and an opening quote
        # (plain, or JSON-escaped as in the stored calibration); a value that is only a bare
        # environment reference ($NAME or ${NAME}) passes, anything else is a literal. A
        # whitespace-separated value counts only after a config-set verb in the same command
        # (`config set` or `npm set`, optional -options between), so prose and get/delete pass
        r"""|(?:_authToken|npmAuthToken)(?:\\?["'])?\s*[:=]\s*(?:\\?["'])?%(value)s"""
        r"""|(?<![A-Za-z0-9_-])(?:config|npm)\s+set(?:\s+-\S*)*\s+\S*?(?:_authToken|npmAuthToken)"""
        r"""(?:\\?["'])?\s+(?:\\?["'])?%(value)s"""
        % {"value": r"""(?!\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})(?=$|[\s"'\\,;})&|])|\s|\\?["'])\S"""})),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential assignment", re.compile(
        r"(?<![A-Za-z0-9_])(?:access_token|id_token|refresh_token|OPENAI_API_KEY|%s)"
        r"""["']?\s*[:=]\s*"""
        # a bare `$NAME` / `${NAME}` (optionally in matching quotes) is a reference, not a value
        r"""(?!(?:\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})"""
        r"""|\\?"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})(?:\\?\"|\\)"""
        r"""|'\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})')(?=$|[\s"',;}\\&|]))"""
        r"""(?:"[^"\s]|'[^'\s]|[^\s"',;}])""" % re.escape(cloud_pass.PASS_ENV),
        re.IGNORECASE)),
    ("url credential", _UrlCredential()),
    ("credential word assignment", _CredentialAssignment()),
    ("bearer credential", re.compile(
        # a token that is only a bare environment reference ($NAME or ${NAME}) passes
        r"""Bearer (?!\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})(?=$|[\s"'\\;,}&|]))"""
        r"\S{16,}")),
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
    kind, repo = source.get("source"), source.get("repo")
    if kind == "github" and isinstance(repo, str) and repo:
        url = "https://github.com/%s.git" % repo
    elif kind == "git":
        url = source.get("url")
    else:
        raise _Refused("plugin-source-unsupported",
                       "The plugin's marketplace is not a git source, which this setup text "
                       "cannot fetch from.")
    install = market.get("installLocation")
    listing = _read_json(os.path.join(install, ".claude-plugin", "marketplace.json")) \
        if isinstance(install, str) else None
    plugins = listing.get("plugins") if isinstance(listing, dict) else None
    subdir = next((p.get("source") for p in plugins if isinstance(p, dict)
                   and p.get("name") == plugin_name), None) if isinstance(plugins, list) else None
    if not (isinstance(url, str) and isinstance(subdir, str) and subdir):
        raise unknown("the marketplace does not say where the plugin lives")
    return url, commit, subdir[2:] if subdir.startswith("./") else subdir


def _core_rel():
    """The core file's path under a store, from the modules that own its names."""
    return mode_registry.CONFIG_DIRNAME + "/" + core_md.CORE_FILENAME


def _policy_name(cwd, root):
    return os.path.basename(architect_config.policy_path(cwd, root))


def _store_files(store, top):
    """The calibration files that exist under `store`: relative path -> raw bytes. `top` names the
    files directly under the store, read by the caller from their owners."""
    wanted = list(top)
    config_dir_name = mode_registry.CONFIG_DIRNAME
    try:
        names = sorted(os.listdir(os.path.join(store, config_dir_name)))
    except FileNotFoundError:
        names = []
    except OSError:
        raise _Refused("calibration-unreadable", "The calibration's config directory cannot be read.")
    wanted += [config_dir_name + "/" + n for n in names if n.endswith(".md")]
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
        # doc-policy.json is machine-local for every project, so it is placed even here.
        policy = architect_config.policy_path(cwd, root)
        found = _store_files(os.path.dirname(policy), (os.path.basename(policy),))
        return False, {k: v for k, v in found.items() if k == os.path.basename(policy)}
    if mode != mode_registry.GLOBAL:
        raise unknown
    top = (mode_registry.REGISTRY_FILENAME, mode_registry.META_FILENAME, _policy_name(cwd, root))
    return True, _store_files(mode_registry.project_store_dir(cwd, root), top)


def calibration_files(cwd, root=None):
    """The calibration the setup text places: relative path -> bytes, sorted; for a project whose
    repository carries its calibration, only the machine-local doc-policy.json (when it exists)."""
    return _calibration(cwd, root)[1]


def _without_setting(data, slug=None):
    """`data` with the cloud-builds setting (or the setting `slug` names) out of its json block,
    re-rendered whether or not the key was there; `data` itself when it holds no readable
    setting."""
    try:
        text = data.decode("utf-8")
        obj = json.loads(core_md._json_block_inner_text(text))
        settings = obj.get("projectConfiguration")
        if isinstance(settings, dict):
            settings.pop(slug or project_config.CLOUD_BUILDS_SLUG, None)
            if not settings:
                del obj["projectConfiguration"]
        body = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
        return core_md._splice_single_json_block(text, body).encode("utf-8")
    except Exception:
        return data


def _refuse_malformed_container(cwd, root, reason="setup-commands-unreadable",
                                what="setup commands"):
    """Refuses a core whose raw projectConfiguration is present but not an object: parse_core reads
    that as an empty setting, which would drop the owner's commands without a word."""
    try:
        path = core_md.core_path(cwd, root, persist_backfill=False)
        with open(path, encoding="utf-8") as fh:
            match = core_md._JSON_BLOCK.search(fh.read())
        block = json.loads(match.group(1)) if match else None
    except Exception:
        return
    # axis: a projectConfiguration that is not an object is refused, never read as absent commands
    if isinstance(block, dict) and core_md.PROJECT_CONFIGURATION_KEY in block and not isinstance(
            block[core_md.PROJECT_CONFIGURATION_KEY], dict):
        raise _Refused(reason, "The project's calibration holds its configuration in a form that "
                       "cannot be read for %s." % what)


def _setup_commands(cwd, root):
    """The project's ordered setup commands (configure item 17): a list of strings, possibly empty.
    A project with no readable core, or no such setting, has none."""
    return _stored_setup_commands(cwd, root) or []


def _stored_setup_commands(cwd, root):
    """The stored list of setup commands, or None when the project does not store the setting at
    all (so an empty list that was stored is told apart from a setting never set). A setting that
    is there but invalid is refused, because the text would otherwise quietly leave out what the
    owner listed."""
    return _stored_setting(
        cwd, root, project_config.CLOUD_SETUP_COMMANDS_SLUG, "setup commands",
        "setup-commands-unreadable",
        ("setup-commands-malformed", "The project's setup commands are stored in a form that is "
         "not a list of one-line commands."))


def _stored_setup_inputs(cwd, root, commands):
    """The stored list of files the setup depends on (item 18), or None when never stored. A
    project with no setup commands has no inputs, and its item 18 is not even read."""
    if not commands:
        return None
    return _stored_setting(
        cwd, root, project_config.CLOUD_SETUP_INPUTS_SLUG, "setup inputs",
        "setup-inputs-unreadable",
        ("setup-inputs-malformed", "The project's setup inputs are stored in a form that is not a "
         "list of plain repository paths."))


def _dependency_hook_on(cwd, root, commands):
    """Whether the project opted in to the dependency hook (item 19): only an exact true. A project
    with no setup commands has no hook, and its item 19 is not even read."""
    if not commands:
        return False
    return _stored_setting(
        cwd, root, project_config.CLOUD_DEPENDENCY_HOOK_SLUG, "dependency hook setting",
        "setup-commands-unreadable", None) is True


def _stored_setting(cwd, root, slug, what, unreadable, malformed):
    """The stored value of the project-configuration item `slug` (named `what` in a refusal), or
    None when it is not stored. A calibration that cannot be read for it is refused with the
    `unreadable` reason, and a stored value that fails the item's own validation with the
    `malformed` reason and sentence (with no `malformed`, a stored value is returned as it is)."""
    try:
        facts = core_md.read(cwd, root, persist_backfill=False)
    except Exception:
        raise _Refused(unreadable, "The project's %s cannot be read from its calibration." % what)
    if facts is None:
        # core_md.read answers None for a file it cannot open as well as for an absent one; a core
        # that is there but unreadable would otherwise drop the owner's commands without a word
        path = core_md.core_path(cwd, root, persist_backfill=False)
        if os.path.isfile(path):
            try:
                with open(path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                raise _Refused(unreadable, "The project's %s cannot be read from its "
                               "calibration." % what)
            # axis: a core that names the setting but cannot be parsed would drop the owner's
            # commands without a word, so it is refused; a core that never names it has none
            if slug.encode("utf-8") in raw:
                raise _Refused(unreadable, "The project's calibration names %s but cannot be "
                               "parsed to read them." % what)
    else:
        _refuse_malformed_container(cwd, root, unreadable, what)
    settings = facts.get("projectConfiguration") if facts is not None else None
    if not isinstance(settings, dict) or slug not in settings:
        return None
    item = project_config._item_by_slug(slug)
    # axis: a stored value that is not a valid list is refused, never read as an empty list
    if malformed is not None and project_config.validate_item_value(
            item, settings[slug]) is not None:
        raise _Refused(*malformed)
    return settings[slug]


def detect_inputs(repo_root):
    """The sorted names of the lockfiles and requirements files directly in `repo_root`; it never
    looks deeper, and a missing root (or one that is not a directory) has none. A root that exists
    but cannot be read raises `OSError`: "could not look" is not "found none"."""
    try:
        entries = list(os.scandir(repo_root))
    except (FileNotFoundError, NotADirectoryError):
        return []
    names = []
    for entry in entries:
        try:
            regular = entry.is_file(follow_symlinks=False)
        except OSError:
            continue
        if regular and (entry.name in size_count.LOCKFILE_NAMES
                        or fnmatch.fnmatchcase(entry.name, REQUIREMENTS_PATTERN)):
            names.append(entry.name)
    return sorted(names)


def _input_view(repo_root, inputs):
    """The stamp entries for the files the setup depends on: the list itself, each existing file's
    bytes, and an empty marker for each one that does not exist."""
    view = {SETUP_INPUTS_STAMP_KEY: (json.dumps(list(inputs), ensure_ascii=False)
                                     + "\n").encode("utf-8")}
    for rel in inputs:
        path = os.path.join(repo_root, *rel.split("/"))
        try:
            os.lstat(path)
        except (FileNotFoundError, NotADirectoryError):
            view[SETUP_INPUT_MISSING_STAMP_PREFIX + rel] = b""
            continue
        except OSError:
            raise _Refused("setup-inputs-unreadable", "A file the setup depends on (%s) is not a "
                           "readable file." % rel)
        try:
            if not os.path.isfile(path):
                raise OSError("not a regular file")
            with open(path, "rb") as fh:
                view[SETUP_INPUT_STAMP_PREFIX + rel] = fh.read()
        except OSError:
            raise _Refused("setup-inputs-unreadable", "A file the setup depends on (%s) is not a "
                           "readable file." % rel)
    return view


def _expectations_from_view(view, inputs):
    """(path, sha256 hex or None) for each setup input as the text is composed, read from an
    already-taken input view so the stamp and the checks in the text describe the same bytes:
    None marks a file that does not exist. The generated script checks the clone against these."""
    return [(rel, hashlib.sha256(view[SETUP_INPUT_STAMP_PREFIX + rel]).hexdigest()
             if SETUP_INPUT_STAMP_PREFIX + rel in view else None) for rel in inputs]


def _stamp_view(files, commands=(), inputs_view=None):
    view = dict(files)
    core = _core_rel()
    if core in view:
        view[core] = _without_setting(view[core])
        # axis: without setup commands items 18 and 19 are unused, so they never move the stamp
        if not commands:
            for unused in (project_config.CLOUD_SETUP_INPUTS_SLUG,
                           project_config.CLOUD_DEPENDENCY_HOOK_SLUG):
                view[core] = _without_setting(view[core], unused)
    # axis: the stamp moves whenever the command list does, in both storage modes
    if commands:
        view[SETUP_COMMANDS_STAMP_KEY] = (
            json.dumps(list(commands), ensure_ascii=False) + "\n").encode("utf-8")
        if inputs_view:
            view.update(inputs_view)
    return view


def _inputs_view_for(cwd, commands, inputs):
    """The input files' stamp entries, read once; None unless commands are listed and item 18 is
    stored."""
    # axis: the input files join the stamp only with commands and stored inputs
    if not (commands and inputs is not None):
        return None
    try:
        repo_root = store_core.repo_root(cwd)
    except store_core.RepoRootUnavailable:
        raise _Refused("setup-inputs-unreadable", "The repository root cannot be found, so the "
                       "files the setup depends on cannot be read.")
    return _input_view(repo_root, inputs)


def _hook_view(inputs):
    """The stamp entries with the dependency hook on: the hook flag and the input list (when
    stored), never the input files' contents."""
    # axis: with commands and the hook on, the input list (when stored) and the hook flag stay in
    # the stamp, because they change the generated text; only the files' contents leave it
    view = {SETUP_HOOK_STAMP_KEY: b"on\n"}
    if inputs is not None:
        view[SETUP_INPUTS_STAMP_KEY] = (
            json.dumps(list(inputs), ensure_ascii=False) + "\n").encode("utf-8")
    return view


def _view_for(cwd, files, commands, inputs, hook_on):
    """The stamp's view of `files`, built for both callers (`stamped_files` and `_compose`): the
    files the setup depends on join it exactly when commands are listed, item 18 is stored and the
    dependency hook is not on (with the hook on it keeps dependencies current, so a change to those
    files needs no new paste)."""
    if commands and hook_on:
        return _stamp_view(files, commands, _hook_view(inputs))
    # axis: the input files join the stamp only with commands, stored inputs and no hook
    return _stamp_view(files, commands, _inputs_view_for(cwd, commands, inputs))


def stamped_files(cwd, root=None):
    """What the stamp covers: the placed calibration with the cloud-builds setting left out, so
    switching cloud builds on or off never changes the stamp, and the project's setup commands
    when it lists any, with the files they depend on unless the dependency hook is on."""
    commands = _setup_commands(cwd, root)
    return _view_for(cwd, calibration_files(cwd, root), commands,
                     _stored_setup_inputs(cwd, root, commands),
                     _dependency_hook_on(cwd, root, commands))


def _project_name(cwd):
    try:
        remote = store_core.get_remote(cwd)
        return remote.split("/")[-1] if remote else os.path.basename(store_core.repo_root(cwd))
    except Exception:
        return os.path.basename(os.path.abspath(cwd))


_CLONE_DIR_RE = re.compile(r"[A-Za-z0-9._-]+")


def _clone_dir(cwd):
    """The directory a cloud clone of this repository is named: the last path component of its
    remote, when that is plain enough for the shell; else None."""
    try:
        remote = store_core.get_remote(cwd)
        name = remote.split("/")[-1] if remote else None
    except Exception:
        return None
    if name and _CLONE_DIR_RE.fullmatch(name) and name not in (".", ".."):
        return name
    return None


def _utc_date(now):
    moment = now if isinstance(now, datetime) else datetime.fromtimestamp(
        time.time() if now is None else now, timezone.utc)
    return moment.astimezone(timezone.utc).date()


_ENCODED_RUN_RE = re.compile(r"[A-Za-z0-9+/_-]{40,}={0,2}")


def _plain_shape(text, document=False):
    # a command text is read with assignment position (see `_CredentialAssignment`); a document is not
    def hit(pattern):
        search = getattr(pattern, "search_document", None) if document else None
        return (search or pattern.search)(text)
    return next((name for name, pattern in _SECRET_SHAPES if hit(pattern)), None)


def _encoded_shape(text):
    """A base64 run (standard or URL-safe alphabet, any label or none) that decodes to text
    carrying a secret-shaped form, such as an encoded reviewer pass."""
    for match in _ENCODED_RUN_RE.finditer(re.sub(r"[*`~]", "", text)):
        run = match.group(0).strip("_").rstrip("=").replace("-", "+").replace("_", "/")
        run += "=" * (-len(run) % 4)
        try:
            decoded = base64.b64decode(run).decode("utf-8")
        except Exception:
            continue
        if _plain_shape(decoded) is not None:
            return "encoded credential"
    return None


_EMPTY_QUOTES_RE = re.compile(r"""\\"\\"|''|\"\"""")


def _without_empty_quotes(text):
    """`text` with adjacent empty shell quote pairs removed (also JSON-escaped), so shell
    concatenation cannot split a literal from its key."""
    while True:
        shorter = _EMPTY_QUOTES_RE.sub("", text)
        if shorter == text:
            return text
        text = shorter


def _scan(text, document=False):
    """The name of the first secret-shaped form in `text`, else None. The shapes are matched on a
    normalized copy too, with empty quote pairs removed. `text` is one setup command unless
    `document` is true (a file or a whole setup text)."""
    return (_plain_shape(text, document) or _plain_shape(_without_empty_quotes(text), document)
            or _encoded_shape(text))


def _for_line(commands):
    """The loop header that lists the setup commands, each shell-quoted."""
    return "  for cmd in %s; do" % " ".join(shlex.quote(c) for c in commands)


def _input_check_lines(expected):
    """The step that compares each listed input in the clone with the content the text was
    written for (its sha256, or `missing`), logging one line per input that differs and leaving
    `ok` at 0 so no stamp is published."""
    if not expected:
        return []
    out = [
        "  check_input() {",
        # axis: only an absent component is missing (the Python reader's rule: not-found or
        # not-a-directory); a symlink that does not resolve, or a directory that cannot be
        # searched, is unreadable and never matches the expected `missing`
        '    got=""; probe="$DIR"; IFS=/ read -r -a parts <<< "$1"',
        '    for part in "${parts[@]}"; do',
        '      probe="$probe/$part"',
        '      if [ -L "$probe" ] && [ ! -e "$probe" ]; then got=unreadable; break',
        '      elif [ ! -e "$probe" ]; then got=missing; break; fi',
        '      if [ -d "$probe" ] && [ ! -x "$probe" ]; then got=unreadable; break; fi',
        "    done",
        '    if [ -n "$got" ]; then :',
        '    elif [ -f "$DIR/$1" ]; then',
        '      got=$( (sha256sum "$DIR/$1" || shasum -a 256 "$DIR/$1") 2>/dev/null | cut -d" " -f1)',
        "    else got=unreadable; fi",
        '    if [ "$got" != "$2" ]; then',
        '      echo "setup input $1 differs from the setup text: expected $2, found ${got:-unreadable}"',
        "      ok=0",
        "    fi",
        "  }",
        '  if [ -n "$DIR" ]; then',
    ]
    for rel, digest in expected:
        out.append("    check_input %s %s" % (shlex.quote(rel), digest or "missing"))
    out.append("  fi")
    return out


def _commands_block(commands, clone, stamp=None, count=0, expected=(), record=None):
    """The step that runs the project's setup commands, one at a time, in its clone. With a stamp
    to publish, it publishes it last, and only when the calibration was written and every command
    ran and succeeded. With a `record` fingerprint (the dependency hook is on), a finished run also
    tells the clone's hook script, so the hook starts from this run; a missing script or a failed
    record withholds the stamp and fails the setup, because the stamp stops covering the inputs."""
    return [
        "",
        "# Run the project's own setup commands (configure item 17), one at a time, in the order "
        "listed,",
        "# in its clone: the working directory, or the clone beside it. The first failure skips "
        "the rest.",
        "(",
        '  DIR=""',
        '  if [ -e "$PWD/.git" ]; then DIR="$PWD"',
        *(['  elif [ -e "$PWD/$CLONE/.git" ]; then DIR="$PWD/$CLONE"'] if clone is not None else []),
        "  fi",
        "  n=0",
        '  failed=""',
        "  ok=1",
        *_input_check_lines(expected),
        _for_line(commands),
        "    n=$((n + 1))",
        '    if [ -z "$DIR" ]; then ok=0; echo "setup command $n skipped: no clone in $PWD%s"'
        % (" or $PWD/$CLONE" if clone is not None else ""),
        # axis: inputs that differ from the ones the text was written for run no command
        *(['    elif [ "$ok" = 0 ] && [ -z "$failed" ]; then '
           'echo "setup command $n skipped: setup inputs differ from the setup text"']
          if expected else []),
        # axis: after a failure every later command is skipped, never run
        '    elif [ -n "$failed" ]; then echo "setup command $n skipped: setup command $failed FAILED"',
        '    elif (cd "$DIR" && bash -o pipefail -c "$cmd" </dev/null); then echo "setup command $n ok"',
        '    else echo "setup command $n FAILED"; failed=$n; ok=0',
        "    fi",
        "  done",
        *([
            # axis: the hook is told of the run only when every command succeeded; with the hook
            # on the stamp no longer covers the inputs, so a missing script or a failed record
            # means the setup did not finish (no stamp, non-zero exit)
            '  if [ "$ok" = 1 ]; then',
            '    if [ -f "$DIR/%s" ]; then' % cloud_dependency_hook.SCRIPT_REL,
            # axis: the script's own record mode declines (exit 2) when the clone's settings do not register it as an enabled SessionStart hook, so that withholds the stamp as a failed record does
            '      if (cd "$DIR" && bash %s --record %s); then echo "dependency hook recorded"'
            % (cloud_dependency_hook.SCRIPT_REL, record),
            '      else echo "dependency hook record FAILED"; ok=0; fi',
            '    else echo "dependency hook not in the clone: commit and push it"; ok=0; fi',
            "  fi",
        ] if record is not None else []),
        *([
            # axis: the stamp is the receipt for a finished setup, so a failed or skipped command
            # leaves none
            '  if [ "$ok" = 1 ] && [ "$wrote" = %d ]; then' % count,
            "    printf '%%s\\n' '%s' > \"$DEST/%s\" || { echo \"setup stamp write FAILED\"; ok=0; }"
            % (stamp, STAMP_FILE),
            '  else echo "setup stamp withheld: setup did not finish" ; ok=0 ; fi',
        ] if stamp is not None else []),
        # axis: the subshell's own status is whether every listed command ran and succeeded
        '  [ "$ok" = 1 ]',
        ') >> "$LOG" 2>&1',
        # a listed command's failure ends the script non-zero: an unfinished setup must not be
        # cached by the platform as a finished one
        "setup_rc=$?",
    ]


def _script(head, source, commit, subdir, source_dir, plugin_dir, files, dest, stamp, clone,
            commands, cleared=False, expected=(), record=None):
    parent = os.path.dirname(plugin_dir.rstrip("/"))
    out = [
        "#!/bin/bash",
        "# " + head,
        "# Setup text for a cloud environment: paste it over the whole setup-script field.",
        "# It holds no reviewer pass and no other secret.",
        'LOG="%s"' % _LOG,
        'SRC="%s"' % source_dir,
        'LINK="%s"' % plugin_dir,
        *(['CLONE="%s"' % clone] if clone is not None else []),
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
        "",
        "# Install the two packages the write sandbox needs.",
        "(",
        '  apt-get install -y %s || { apt-get update && apt-get install -y %s; } \\'
        % (SANDBOX_TOOL_PACKAGES, SANDBOX_TOOL_PACKAGES),
        '    && echo "sandbox tools ok" || echo "sandbox tools FAILED"',
        ') >> "$LOG" 2>&1 &',
        "",
        "# Install the project's pinned Python, when it has a .python-version file: in the working",
        "# directory, or in the clone beside it. uv reads the file itself, from that directory, with",
        "# UV_PYTHON cleared so an inherited value cannot override it.",
        "(",
        '  DIR=""',
        '  if [ -f "$PWD/.python-version" ]; then DIR="$PWD"',
        *(['  elif [ -f "$PWD/$CLONE/.python-version" ]; then DIR="$PWD/$CLONE"']
          if clone is not None else []),
        "  fi",
        '  if [ -z "$DIR" ]; then',
        '    echo "pinned python: no .python-version in $PWD%s"'
        % (" or $PWD/$CLONE" if clone is not None else ""),
        "  else",
        "    if grep -qvE '^[[:space:]]*(#|$)' \"$DIR/.python-version\""
        ' && (cd "$DIR" && env -u UV_PYTHON uv python install); then'
        ' echo "pinned python ok"',
        '    else echo "pinned python FAILED"; fi',
        "  fi",
        ') >> "$LOG" 2>&1 &',
        "wait",
    ]
    if files or stamp is not None:
        out += ["", "# Place the project's calibration.",
                'DEST="%s"' % dest, 'rm -f "$DEST/%s"' % STAMP_FILE,
                'mkdir -p "$DEST"', "wrote=0"]
        for index, (rel, data) in enumerate(files.items(), 1):
            tag = _end_tag(index)
            out += ['mkdir -p "$(dirname "$DEST/%s")"' % rel,
                    """cat > "$DEST/%s" <<'%s'""" % (rel, tag)]
            out += [data.decode("utf-8")[:-1], tag, '[ "$?" = 0 ] && wrote=$((wrote + 1))']
        # axis: with setup commands the stamp is published after they succeed, not here
        if not commands:
            out += ['if [ "$wrote" = %d ]; then' % len(files),
                    "  printf '%%s\\n' '%s' > \"$DEST/%s\"" % (stamp, STAMP_FILE),
                    'else echo "calibration FAILED: only $wrote of %d files written" >> "$LOG"; fi'
                    % len(files)]
        else:
            out += ['if [ "$wrote" != %d ]; then' % len(files),
                    '  echo "calibration FAILED: only $wrote of %d files written" >> "$LOG"; fi'
                    % len(files)]
        out += ['echo "calibration: $wrote of %d files written" >> "$LOG"' % len(files)]
    elif cleared:
        # axis: a list stored as empty removes the stamp an earlier list placed, which an unset
        # list never had to
        out += ["", "# The project lists no setup commands: retire the stamp an earlier list left.",
                'DEST="%s"' % dest, 'rm -f "$DEST/%s"' % STAMP_FILE]
    # axis: only a non-empty list adds a step, so no list leaves the text as it was
    if commands:
        out += _commands_block(commands, clone, stamp if (files or stamp is not None) else None,
                               len(files), expected, record)
    out += ["", TOOL_STEPS_MARKER,
            'echo "setup end" >> "$LOG"', 'exit "$setup_rc"' if commands else "exit 0", ""]
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
    stored = _stored_setup_commands(cwd, root)
    commands = stored or []
    inputs = _stored_setup_inputs(cwd, root, commands)
    hook_on = _dependency_hook_on(cwd, root, commands)
    # axis: a list stored as empty, in a project that places no files, still has a stamp to retire
    cleared = stored is not None and not stored and not files
    if placed and not files:
        raise _Refused("calibration-missing", "The project keeps its calibration outside the "
                       "repository but none of its calibration files exists.")
    key = mode_registry.config_key(cwd) if placed else None
    bad = [rel for rel in files if not _plain_relative(rel)]
    if placed and not _plain_relative(key):
        bad.append(key)
    dest = mode_registry.project_store_dir(
        cwd, control_plane.DEFAULT_STORE_ROOT.replace("~", "$HOME", 1)
    ) if files or commands or cleared else None
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
    inputs_view = None
    if files or commands:
        try:
            # axis: the inputs are read once; the stamp and the checks in the text share the bytes
            if not hook_on:
                inputs_view = _inputs_view_for(cwd, commands, inputs)
            stamp = (cloud_setup.calibration_stamp if stamp_fn is None else stamp_fn)(
                _stamp_view(files, commands, _hook_view(inputs)
                            if commands and hook_on else inputs_view))
        except _Refused:
            raise
        except Exception:
            stamp = None
        if not (isinstance(stamp, str) and _STAMP_RE.fullmatch(stamp)):
            raise _Refused("stamp-unavailable", "The calibration's stamp is not available.")
    if placed:
        moment = _utc_date(now)
        date = moment.strftime("%Y-%m-%d")
        part = "calibration from %d %s" % (moment.day, _MONTHS[moment.month - 1])
    else:
        part = "calibration in the repository"
    name = " ".join((project_name or _project_name(cwd)).splitlines())
    head = "%s · plugin %s · %s" % (name, version, part)
    expected = ()
    # axis: with the hook on the inputs are not in the stamp, so the text does not check them
    if commands and inputs and not hook_on:
        if inputs_view is None:
            inputs_view = _inputs_view_for(cwd, commands, inputs)
        expected = _expectations_from_view(inputs_view, inputs)
    text = _script(head, source, commit, subdir, source_dir, plugin_dir, files, dest, stamp,
                   _clone_dir(cwd), commands, cleared, expected,
                   cloud_dependency_hook.fingerprint(commands, inputs or []) if hook_on else None)
    # axis: the command list is scanned as written (as `set` scans it), never as the quoted
    # word list, whose quote concatenation reads as a literal; the rest of the script is scanned
    # in full
    scanned = text
    if commands:
        scanned = scanned.replace(_for_line(commands), "  for cmd in ; do", 1)
        # the placed core carries the commands' other copy, JSON-escaped; it is left out of the
        # whole-text scan the same way (the text written is unchanged)
        core = _core_rel()
        if core in files:
            scanned = scanned.replace(
                files[core].decode("utf-8"),
                _without_setting(files[core], project_config.CLOUD_SETUP_COMMANDS_SLUG).decode(
                    "utf-8"), 1)
    shape = next((_scan(c) for c in commands if _scan(c)), None) or _scan(scanned, True)
    if shape:
        where = next((rel for rel, data in files.items()
                      if _scan(data.decode("utf-8"), True)), None)
        raise _Refused("secret-shaped-content", "Something shaped like a %s is in the setup text%s; "
                       "it was not returned." % (shape, " (in %s)" % where if where else ""))
    calibration = {"placed": placed, "files": list(files), "date": date, "stamp": stamp}
    if commands:
        calibration["setupCommands"] = len(commands)
        if hook_on:
            calibration["dependencyHook"] = True
    return {"action": "written", "reason": None, "text": text, "header": head,
            "pluginVersion": version, "pluginCommit": commit, "calibration": calibration,
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
