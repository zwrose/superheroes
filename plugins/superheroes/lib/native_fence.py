"""The native implementer fence (#1947): the PreToolUse decision for a native run's subagent.

A native run (native_engine.py) hands a write order to the platform's `superheroes:implementer`
subagent in its own isolated worktree. There is no plugin sandbox around it, so this module is the
bound the plugin can put on it: a deadline, a closed-run stop, and a command-prefix fence against
installs and network commands. It is a command-prefix fence, not a sandbox.

`fence_decision(payload, now)` returns None (silent) or a deny-reason string. It acts only when
the payload's `agent_type` is exactly `superheroes:implementer` AND either the call is a native
run's enroll command or the payload's `agent_id` is enrolled in a native run (open or closed).
Every other payload — the builder, other agents, an un-enrolled implementer — is silent.

The run journal is read and written through engine_dispatch (`_journal_read_raw`,
`_journal_append`); the enrolled agent's index file lives under INDEX_ROOT.
"""
import datetime
import json
import os
import re
import shlex
import tempfile

IMPLEMENTER = "superheroes:implementer"
INDEX_ROOT_ENV = "SUPERHEROES_NATIVE_INDEX_ROOT"
INDEX_ROOT_NAME = "superheroes-native-agents"
INDEX_ROOT = os.path.join(tempfile.gettempdir(), INDEX_ROOT_NAME)

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
UNPARSEABLE = "unparseable"

_AGENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPERS = ("sudo", "env", "command", "exec", "time", "nohup")
_PIP_RE = re.compile(r"^pip[0-9.]*$")
_PYTHON_RE = re.compile(r"^(python[0-9.]*|pinned-python)$")

_INSTALLER_SUBS = {
    "npm": ("install", "i", "ci", "add", "update"),
    "pnpm": ("add", "install", "i", "update"),
    "gem": ("install",),
    "cargo": ("install",),
    "go": ("install", "get"),
    "conda": ("install",),
    "poetry": ("add", "install"),
}
_INSTALLER_ANY = ("uvx", "pipx", "brew", "apt", "apt-get", "dnf", "yum", "apk")
_NETWORK_ANY = ("curl", "wget", "ssh", "scp", "sftp", "nc", "ncat", "netcat", "telnet", "ftp",
                "gh")
_GIT_NETWORK_SUBS = ("push", "fetch", "pull", "clone", "ls-remote")
_GIT_OPTIONS_WITH_ARG = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")


def index_root():
    return os.environ.get(INDEX_ROOT_ENV) or INDEX_ROOT


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime(TIME_FORMAT)


def _parse_time(text):
    return datetime.datetime.strptime(text, TIME_FORMAT)


def _engine_dispatch():
    import engine_dispatch
    return engine_dispatch


# --- the command-prefix fence ------------------------------------------------------------------

def _heredoc_operator(command, i):
    """Parse the here-document operator at command[i:] (`<<` or `<<-`, then the delimiter word). Returns
    (end index, delimiter or None, strip_tabs, quoted). An unquoted delimiter means the body undergoes expansion."""
    n = len(command)
    j = i + 2
    strip_tabs = j < n and command[j] == "-"
    if strip_tabs:
        j += 1
    while j < n and command[j] in " \t":
        j += 1
    word, quote, quoted = [], None, False
    while j < n:
        ch = command[j]
        if quote:
            if ch == quote:
                quote = None
            else:
                word.append(ch)
        elif ch in "'\"":
            quote = ch
            quoted = True
        elif ch == "\\" and j + 1 < n:
            quoted = True
            j += 1
            word.append(command[j])
        elif ch in " \t\n;|&<>()":
            break
        else:
            word.append(ch)
        j += 1
    return j, "".join(word) or None, strip_tabs, quoted


def _substitution_spans(body):
    """The command substitutions ($(...) with nesting, or backtick pairs) in an expanded here-document body, each
    as its own text span; the text around them is data and is dropped."""
    spans, i, n = [], 0, len(body)
    while i < n:
        if body.startswith("$(", i):
            depth, j = 0, i + 1
            while j < n:
                if body[j] == "(":
                    depth += 1
                elif body[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            spans.append(body[i:j + 1])
            i = j + 1
        elif body[i] == "`":
            j = body.find("`", i + 1)
            j = n - 1 if j < 0 else j
            spans.append(body[i:j + 1])
            i = j + 1
        else:
            i += 1
    return spans


def _split_segments(command):
    """Split on ; && || | & and newlines outside quotes, dropping comments. An unterminated quote stays in its segment
    (shlex then refuses it)."""
    segments, cur = [], []
    quote = None
    pending = []  # here-document (delimiter, strip_tabs) pairs whose bodies start after the next newline
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if quote:
            cur.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                cur.append(command[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch == "\\" and i + 1 < n:
            cur.append(ch)
            cur.append(command[i + 1])
            i += 1
        elif ch in "'\"":
            quote = ch
            cur.append(ch)
        elif ch == "#" and (
                not cur or (cur[-1] in " \t" and not (len(cur) > 1 and cur[-2] == "\\"))):
            # A comment outside quotes: Bash ignores it through the newline (the newline stays).
            while i + 1 < n and command[i + 1] != "\n":
                i += 1
        elif ch == "<" and command.startswith("<<<", i):
            cur.append("<<<")
            i += 2
        elif ch == "<" and command.startswith("<<", i):
            end, delim, strip_tabs, quoted = _heredoc_operator(command, i)
            cur.append(command[i:end])
            if delim:
                pending.append((delim, strip_tabs, quoted))
            i = end - 1
        elif ch in ";|&\n":
            segments.append("".join(cur))
            cur = []
            if ch in "|&" and i + 1 < n and command[i + 1] == ch:
                i += 1
            elif ch == "\n" and pending:
                # Skip each here-document body through its terminating delimiter line: the body is data.
                # An unquoted delimiter's body is expanded by the shell, so each command substitution in it
                # ($(...) or backticks) stays in the stream as its own segment while the surrounding body text
                # stays data. The fence reads only each segment's leading token, so command substitution and
                # subshells pass it: this keeps the substitution visible, it does not make it fail closed.
                pos = i + 1
                for delim, strip_tabs, quoted in pending:
                    start = pos
                    while pos < n:
                        nl = command.find("\n", pos)
                        line = command[pos:] if nl < 0 else command[pos:nl]
                        pos = n if nl < 0 else nl + 1
                        if (line.lstrip("\t") if strip_tabs else line) == delim:
                            break
                    if not quoted:
                        segments.extend(_substitution_spans(command[start:pos]))
                pending = []
                i = pos - 1
        else:
            cur.append(ch)
        i += 1
    segments.append("".join(cur))
    return segments


def _leading_tokens(tokens):
    """Drop leading NAME=value words and the wrappers (with their option flags)."""
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _ASSIGNMENT_RE.match(tok):
            i += 1
        elif os.path.basename(tok) in _WRAPPERS:
            wrapper = os.path.basename(tok)
            i += 1
            if wrapper != "command":
                while i < len(tokens) and tokens[i].startswith("-"):
                    i += 1
        else:
            break
    return tokens[i:]


def _subcommands(args):
    return [a for a in args if not a.startswith("-")]


def _git_subcommand(args):
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in _GIT_OPTIONS_WITH_ARG:
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            return tok
    return None


def _python_m_pip(args):
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "-m":
            return i + 1 < len(args) and _PIP_RE.match(args[i + 1]) is not None, args[i + 2:]
        if tok in ("-W", "-X"):
            i += 2
        elif tok.startswith("-"):
            i += 1
        else:
            break
    return False, []


def _segment_word(tokens):
    tokens = _leading_tokens(tokens)
    if not tokens:
        return None
    word = os.path.basename(tokens[0])
    args = tokens[1:]
    subs = _subcommands(args)
    first = subs[0] if subs else None

    if _PIP_RE.match(word):
        if first in ("install", "download"):
            return "%s %s" % (word, first)
    elif _PYTHON_RE.match(word):
        is_pip, rest = _python_m_pip(args)
        rest_subs = _subcommands(rest)
        if is_pip and rest_subs and rest_subs[0] in ("install", "download"):
            return "%s -m pip %s" % (word, rest_subs[0])
    elif word == "uv":
        if first == "pip" and len(subs) > 1 and subs[1] in ("install", "download"):
            return "uv pip %s" % subs[1]
        if first == "add":
            return "uv add"
        if first == "tool" and len(subs) > 1 and subs[1] == "install":
            return "uv tool install"
    elif word == "yarn":
        if first is None or first in ("add", "install"):
            return "yarn" if first is None else "yarn %s" % first
    elif word in _INSTALLER_SUBS:
        if first in _INSTALLER_SUBS[word]:
            return "%s %s" % (word, first)
    elif word == "git":
        sub = _git_subcommand(args)
        if sub in _GIT_NETWORK_SUBS:
            return "git %s" % sub
    elif word in _INSTALLER_ANY or word in _NETWORK_ANY:
        return word
    return None


def fence_word(command):
    """The fence word a Bash command matches, "unparseable" for a segment shlex cannot parse, or
    None. The first match in command order wins."""
    if not isinstance(command, str):
        return UNPARSEABLE
    for segment in _split_segments(command):
        if not segment.strip():
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            return UNPARSEABLE
        word = _segment_word(tokens)
        if word is not None:
            return word
    return None


# --- the enroll command ------------------------------------------------------------------------

def enroll_run_dir(command):
    """The absolute run dir D when `command` is exactly `python3 [-flags] .../native_engine.py
    enroll --run-dir D` (one segment, nothing chained, nothing after D); otherwise None."""
    if not isinstance(command, str):
        return None
    segments = [s for s in _split_segments(command) if s.strip()]
    if len(segments) != 1:
        return None
    try:
        tokens = _leading_tokens(shlex.split(segments[0]))
    except ValueError:
        return None
    if not tokens or not _PYTHON_RE.match(os.path.basename(tokens[0])):
        return None
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 1
    if i >= len(tokens) or os.path.basename(tokens[i]) != "native_engine.py":
        return None
    rest = tokens[i + 1:]
    if len(rest) == 3 and rest[0] == "enroll" and rest[1] == "--run-dir":
        run_dir = rest[2]
    elif len(rest) == 2 and rest[0] == "enroll" and rest[1].startswith("--run-dir="):
        run_dir = rest[1][len("--run-dir="):]
    else:
        return None
    if not run_dir.startswith("/") or "$" in run_dir or "`" in run_dir:
        return None
    return run_dir


# --- the run journal ---------------------------------------------------------------------------

def _run_state(run_dir):
    """(opened, enrolled, closed) for a run dir: the last native run-opened record or None, the
    first native-enrolled record or None, whether a run-closed record exists. An unreadable or
    interior-corrupt journal raises: the caller fails closed."""
    ed = _engine_dispatch()
    records, interior_corrupt, state, _classes = ed._journal_read_raw(os.path.realpath(run_dir))
    if state in ("absent", "empty"):
        return None, None, False
    if state != "ok" or interior_corrupt:
        raise ValueError("run journal unreadable (%s%s)" % (
            state, ", corrupt" if interior_corrupt else ""))
    opened = enrolled = None
    closed = False
    for rec in records:
        kind = rec.get("kind")
        if kind == "run-opened" and rec.get("engine") == "native":
            opened = rec
        elif kind == "native-enrolled" and enrolled is None:
            enrolled = rec
        elif kind == "run-closed":
            closed = True
    return opened, enrolled, closed


def _past_deadline(opened, now):
    return _parse_time(now) > _parse_time(opened["deadlineAt"])


def _index_path(agent_id):
    return os.path.join(index_root(), "%s.json" % agent_id)


def _write_index(agent_id, run_dir):
    root = index_root()
    os.makedirs(root, mode=0o700, exist_ok=True)
    path = _index_path(agent_id)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"runDir": run_dir}, fh)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _read_index(agent_id):
    """The enrolled agent's run dir, or None when the agent has no index entry."""
    if not isinstance(agent_id, str) or not _AGENT_ID_RE.match(agent_id):
        return None
    path = _index_path(agent_id)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    run_dir = data["runDir"]
    if not isinstance(run_dir, str) or not run_dir:
        raise ValueError("index entry has no runDir")
    return run_dir


def _enroll_decision(payload, run_dir, now):
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not _AGENT_ID_RE.match(agent_id):
        return "enroll refused: the payload carries no usable agent_id"
    opened, enrolled, closed = _run_state(run_dir)
    if opened is None:
        return "enroll refused: %s has no open native run" % run_dir
    if closed:
        return "enroll refused: the native run is closed; stop and report"
    if _past_deadline(opened, now):
        return ("enroll refused: the native run's deadline passed at %s; stop now and report"
                % opened["deadlineAt"])
    if enrolled is not None:
        return "enroll refused: the native run already has an enrolled agent"
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return "enroll refused: the payload carries no cwd to bind"
    record = {"kind": "native-enrolled", "agentId": agent_id,
              "worktree": os.path.realpath(cwd), "at": now}
    if not _engine_dispatch()._journal_append(os.path.realpath(run_dir), record):
        return "enroll refused: the run journal could not record the binding"
    _write_index(agent_id, os.path.realpath(run_dir))
    return None


# --- the decision ------------------------------------------------------------------------------

def fence_decision(payload, now=None):
    """None (silent) or a deny-reason string for one PreToolUse payload."""
    if payload.get("agent_type") != IMPLEMENTER:
        return None
    if now is None:
        now = utc_now()
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None

    if tool_name == "Bash":
        run_dir = enroll_run_dir(command)
        if run_dir is not None:
            return _enroll_decision(payload, run_dir, now)

    run_dir = _read_index(payload.get("agent_id"))
    if run_dir is None:
        return None

    opened, _enrolled, closed = _run_state(run_dir)
    if closed:
        return "the native run is closed; stop and report"
    if opened is None:
        raise ValueError("the enrolled run has no native run-opened record")
    if _past_deadline(opened, now):
        return ("the native run's deadline passed at %s; stop now and report" % opened["deadlineAt"])
    if tool_name == "Bash":
        word = fence_word(command)
        if word == UNPARSEABLE:
            return "installs and network commands are refused for a native implementer: " \
                   "unparseable command"
        if word is not None:
            return "installs and network commands are refused for a native implementer: %s" % word
    return None
