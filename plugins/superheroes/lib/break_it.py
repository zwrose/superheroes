#!/usr/bin/env python3
"""Run a break-it test the test role wrote as text, in a throwaway copy, and check it was kept (#1800).

Stdlib only. A break-it test runs **only** inside a detached copy of the reviewed head: it never
touches the caller's tree, index or HEAD, and its process tree never outlives the call. The runner
itself writes only inside the copy. The copy links the reviewed checkout's installed, untracked
dependency directories (``DEPENDENCY_DIRS``); a test may write untracked cache files inside a linked
directory, such as vite's ``node_modules/.vite-temp``, but no tracked file of the reviewed checkout is
written, and a dependency tree that links back into the checkout's tracked files is never linked.
Every outcome is a record — ``failed``, ``passed`` or ``not-run`` with a reason —
and the caller decides from the record; nothing is raised."""
import hashlib
import json
import os
import posixpath
import re
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import uuid

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import break_it_key  # noqa: E402  (sibling leaf; the interpreter key name's one home)
from git_routing import GIT_ROUTING_VARS  # noqa: E402
import readout  # noqa: E402  (the band's fail-closed scrub seam)

SCHEMA = "break-it-run/1"
ROLE = "test-role"
TAXONOMY = "break-it-test"
RUN_FIELD = "breakItRun"
INTERPRETER_KEY = break_it_key.INTERPRETER_KEY
REDACTED_FIELD = "suggestionRedacted"
DEFAULT_TIMEOUT = 300
OUTPUT_TAIL_BYTES = 8192
OUTCOME_FAILED, OUTCOME_PASSED, OUTCOME_NOT_RUN = "failed", "passed", "not-run"
REASON_COMMAND_NOT_FOUND = "command-not-found"
REASON_MODULE_NOT_FOUND = "module-not-found"
REASON_DEPENDENCY_LINK_FAILED = "dependency-link-failed"
REASON_DEPENDENCY_LINK_UNSAFE = "dependency-link-unsafe"
DEPENDENCY_DIRS = ("node_modules",)
_JS_LAUNCHERS = frozenset(["npm", "npx", "pnpm", "yarn"])
_COMMAND_NOT_FOUND_EXIT = 127
_COMMAND_NOT_FOUND_RE = re.compile(r"command not found")
_MODULE_NOT_FOUND_RE = re.compile(
    r"ERR_MODULE_NOT_FOUND|Cannot find module|Cannot find package|ModuleNotFoundError|No module named")
KEPT, KEPT_MISSING, KEPT_CHANGED, KEPT_NOT_REGULAR, KEPT_FAILING, KEPT_UNRESOLVED = (
    "kept", "missing", "changed", "not-regular", "failing", "unresolved")


def setup_failure_reason(text, exit_code=None):
    """Why a run never executed the code under test, from its output and exit code: the one home of the
    setup-failure signature. ``command-not-found`` (exit 127, or ``command not found`` in the output) wins over
    ``module-not-found``; ``None`` when neither shows. Never raises; a non-str ``text`` reads as empty."""
    if not isinstance(text, str):
        text = ""
    if exit_code == _COMMAND_NOT_FOUND_EXIT or _COMMAND_NOT_FOUND_RE.search(text):
        return REASON_COMMAND_NOT_FOUND
    if _MODULE_NOT_FOUND_RE.search(text):
        return REASON_MODULE_NOT_FOUND
    return None


# The one hand-kept home of the block grammar. The test role's panel order renders it; parse_block
# reads its header, field prefixes and separator from it.
BLOCK_TEMPLATE = "\n".join([
    "break-it-test v1",
    "path: <the same repo-relative path as `file`>",
    "run: <one command, run from the repository root, that runs only this test file>",
    "---",
    "<the complete file content>",
])
RUN_RULES = (
    "The loop runs `run` without a shell, from a copy of the repository that holds its tracked "
    "files plus the reviewed checkout's installed `node_modules` when it has one: one command, "
    "optionally led by `NAME=value` settings, with no pipes, redirects, "
    "`;`, `&&`, `||`, backticks or `$(`. A command that needs anything else is not run. A `run` "
    "whose program is `python` or `python3` (or another Python interpreter path), or, when the "
    "project's `breakItInterpreter` calibration is set, `pytest` or `py.test` (run as "
    "`<launcher> -m pytest`), runs under the project's own interpreter launcher: the "
    "`breakItInterpreter` calibration when set, else the one its verify command uses. It is not run "
    "when that launcher cannot be found.")

_TEMPLATE_LINES = BLOCK_TEMPLATE.split("\n")
_HEADER = _TEMPLATE_LINES[0]
_PATH_PREFIX = _TEMPLATE_LINES[1].partition(" ")[0]
_RUN_PREFIX = _TEMPLATE_LINES[2].partition(" ")[0]
_SEPARATOR = _TEMPLATE_LINES[3]
_GIT_TIMEOUT = 120
_ENV_TOKEN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
_SHELL_TOKENS = frozenset(["|", "||", "&", "&&", ";", "<", ">", ">>", "2>", "&>"])
_SHELL_PROGRAMS = frozenset(["sh", "bash", "dash", "zsh", "ksh", "mksh", "fish", "busybox"])
_REGULAR_MODES = ("100644", "100755")
_PYTHON_PROGRAM = re.compile(r"^python(\d+(\.\d+)?)?$")
_SEPARATOR_CHARS = frozenset(";&|()\n")
_COMMAND_WORDS = frozenset(["if", "then", "else", "elif", "do", "while", "until", "!", "{"])
_UNSET = object()
_TOKEN_ENV = "BREAK_IT_RUN_TOKEN"
_DRAIN_JOIN = 5
_TERM_GRACE = 5
_REAPER = r"""
import ctypes, os, signal, subprocess, sys, time

PROC_ROOT = "/proc"
status_fd = int(sys.argv[1])
argv = sys.argv[2:]
try:
    ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)  # PR_SET_CHILD_SUBREAPER
except Exception:
    pass


def descendants():
    parent, state = {}, {}
    try:
        names = os.listdir(PROC_ROOT)
    except OSError:
        return []  # no /proc on this host: nothing to scan, the parent's token sweep is the net
    for name in names:
        if name.isdigit():
            try:
                with open("%s/%s/stat" % (PROC_ROOT, name)) as fh:
                    tail = fh.read().rsplit(")", 1)[1].split()
                parent[int(name)], state[int(name)] = int(tail[1]), tail[0]
            except (OSError, IndexError, ValueError):
                pass
    found, frontier = [], [os.getpid()]
    while frontier:
        nxt = [p for p, pp in parent.items() if pp in frontier and p not in found]
        found.extend(nxt)
        frontier = nxt
    return [p for p in found if state.get(p) != "Z"]


def sweep():
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        live = descendants()
        if not live:
            return
        for pid in live:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except OSError:
            pass
        time.sleep(0.02)


def on_term(signum, frame):
    sweep()
    os._exit(143)


signal.signal(signal.SIGTERM, on_term)
try:
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL)
except OSError:
    os.write(status_fd, b"E")
    os._exit(127)
code = child.wait()
sweep()
os._exit(code if code >= 0 else 128 - code)
"""


_IMPORT_ROUTING_VARS = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE",
                        "NODE_PATH", "RUBYLIB", "PERL5LIB", "CLASSPATH")


def _names_root(value, root_real):
    """True when any absolute ``os.pathsep`` entry of ``value`` resolves to ``root_real`` or lies beneath it."""
    for entry in value.split(os.pathsep):
        if entry and os.path.isabs(entry):
            real = os.path.realpath(entry)
            if real == root_real or real.startswith(root_real.rstrip(os.sep) + os.sep):
                return True
    return False


def _clean_env(extra=None, root=None):
    """The ambient environment minus every git routing variable, the common import-routing variables
    and, given ``root``, every variable with a path entry that resolves to or beneath that path (an
    import path into the caller's checkout in any spelling), plus ``extra``."""
    root_real = os.path.realpath(root) if root else None
    env = {k: v for k, v in os.environ.items()
           if k not in GIT_ROUTING_VARS and k not in _IMPORT_ROUTING_VARS
           and not (root_real and _names_root(v, root_real))}
    env.update(extra or {})
    return env


def is_break_it(finding):
    return isinstance(finding, dict) and finding.get("taxonomy") == TAXONOMY


def _path_unsafe(path):
    if not isinstance(path, str) or not path or "\\" in path or "\0" in path:
        return True
    return any(seg in ("", ".", "..") for seg in path.split("/"))


def parse_block(text):
    """``({"path", "run", "content", "sha256"}, None)`` for a well-formed ``break-it-test v1``
    block, else ``(None, reason)``. The content after the ``---`` line is kept byte-exact. The
    grammar's one home is ``BLOCK_TEMPLATE``; the test role's panel order renders it and nothing
    else restates it."""
    if not isinstance(text, str):
        return None, "block-not-a-string"
    parts = text.split("\n", 4)
    # axis: the header is read from BLOCK_TEMPLATE, so the parser and the rendered grammar cannot drift apart
    if parts[0] != _HEADER:
        return None, "block-header-missing"
    path = (parts[1][len(_PATH_PREFIX):].strip()
            if len(parts) > 1 and parts[1].startswith(_PATH_PREFIX) else "")
    if not path:
        return None, "block-path-missing"
    run = (parts[2][len(_RUN_PREFIX):].strip()
           if len(parts) > 2 and parts[2].startswith(_RUN_PREFIX) else "")
    if not run:
        return None, "block-run-missing"
    if len(parts) < 4 or parts[3] != _SEPARATOR:
        return None, "block-separator-missing"
    # axis: an absolute, backslashed or dot-segment path is refused before anything is written — see bite-proof record wo_a_1800_break-it
    if _path_unsafe(path):
        return None, "path-unsafe"
    content = parts[4] if len(parts) == 5 else ""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {"path": path, "run": run, "content": content, "sha256": sha}, None


def parse_command(run):
    """``(argv, env, None)`` for a plain argv command with optional leading ``NAME=value`` entries,
    else ``(None, None, reason)``. Shell syntax, shell interpreters and the ``env`` program are
    refused: the command is never run by a shell."""
    if not isinstance(run, str) or not run.strip():
        return None, None, "run-empty"
    # axis: command substitution is refused on the raw text, before any tokenising — see bite-proof record wo_a_1800_break-it
    if "`" in run or "$(" in run:
        return None, None, "run-shell-syntax"
    try:
        tokens = shlex.split(run, posix=True)
    except ValueError:
        return None, None, "run-unparseable"
    for tok in tokens:
        # axis: a pipe, chain, redirect or terminator token is refused, not run as a literal arg — see bite-proof record wo_a_1800_break-it
        if (tok in _SHELL_TOKENS or tok.startswith((">", "<")) or tok.endswith((";", "|"))):
            return None, None, "run-shell-syntax"
    env = {}
    while tokens:
        m = _ENV_TOKEN.match(tokens[0])
        if not m:
            break
        # axis: a leading git routing assignment is refused, so the copy's git can never be redirected — see bite-proof record wo_a_1800_break-it
        if m.group(1) in GIT_ROUTING_VARS or m.group(1) == _TOKEN_ENV:
            return None, None, "run-env-refused"
        env[m.group(1)] = m.group(2)
        tokens.pop(0)
    if not tokens:
        return None, None, "run-empty"
    program = os.path.basename(tokens[0])
    # axis: the env program is refused outright (-u and -S reach a shell the leading NAME=value entries never need) — see bite-proof record wo_a_1800_break-it
    if program == "env":
        return None, None, "run-env-program"
    # axis: a shell interpreter is refused — its script argument is shell syntax — see bite-proof record wo_a_1800_break-it
    if program in _SHELL_PROGRAMS:
        return None, None, "run-shell-interpreter"
    return tokens, env, None


def _is_python_program(program):
    return bool(_PYTHON_PROGRAM.match(os.path.basename(program)))


_ENV_OPERAND_OPTIONS = frozenset(["-u", "--unset", "-C", "--chdir"])
_ENV_SPLIT_OPTIONS = ("-S", "--split-string")


def _env_split_words(tok, tokens, i):
    """The words an env ``-S``/``--split-string`` option at ``tokens[i]`` splices into the command,
    and how many tokens it consumed, or ``None`` when ``tok`` is no split-string option or its
    operand cannot be split."""
    if tok in _ENV_SPLIT_OPTIONS:
        if i + 1 >= len(tokens) or _is_separator(tokens[i + 1]):
            return None
        operand, used = tokens[i + 1], 2
    elif tok.startswith("--split-string="):
        operand, used = tok[len("--split-string="):], 1
    elif tok.startswith("-S"):
        operand, used = tok[2:], 1
    else:
        return None
    try:
        return shlex.split(operand), used
    except ValueError:
        return None


def _strip_comments(text):
    """``text`` with each unquoted shell comment removed up to (not including) its newline, so the
    newline stays a command boundary. An unquoted ``#`` starts a comment wherever it falls, as the
    resolver's lexer always treated it."""
    out = []
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'" and text[i + 1:i + 2] == "\n":
            # axis: a backslash-newline outside single quotes is a line continuation, joined out so it is never a command boundary
            i += 2
            continue
        if quote:
            if c == "\\" and quote == '"' and i + 1 < len(text):
                out.append(c)
                i += 1
                c = text[i]
            elif c == quote:
                quote = None
        elif c == "\\" and i + 1 < len(text):
            out.append(c)
            i += 1
            c = text[i]
        elif c in "'\"":
            quote = c
        elif c == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _is_separator(token):
    return bool(token) and all(c in _SEPARATOR_CHARS for c in token)


def _chain_chdir(current, operand):
    """The directory after one more ``env -C operand``: a relative operand composes onto the earlier
    one; an absolute operand is kept as it is."""
    return operand if current is None else posixpath.join(current, operand)


def _rebase_launcher(chdir, launcher):
    """``launcher`` (a relative path) as seen from the repository root after ``env -C chdir``: the
    normalised ``chdir/launcher`` (kept an explicit ``./`` path when it lands directly under the root, so
    it never reads as a bare PATH program), or ``None`` when ``chdir`` is absolute or the path climbs out of the root."""
    if os.path.isabs(chdir):
        return None
    rebased = posixpath.normpath(posixpath.join(chdir, launcher))
    if rebased == ".." or rebased.startswith("../") or posixpath.isabs(rebased):
        return None
    if "/" not in rebased:
        # axis: a launcher rebased onto the repository root stays an explicit path, never a bare name the runner would look up on PATH
        rebased = "./" + rebased
    return rebased


def project_interpreter(verify_command):
    """The Python launcher token the project's verify command runs, or ``None``. Reads the command
    text only and never executes anything. A launcher is the program at a command position when it
    is a ``python`` interpreter, or a path given a ``-m`` or ``.py`` argument (a launcher script
    such as ``scripts/pinned-python``); a bare generic runner such as ``uv run`` or ``make`` is not."""
    if not isinstance(verify_command, str) or verify_command.strip() in ("", "none"):
        return None
    try:
        # axis: an unquoted newline is a command boundary, so it is a separator token, never whitespace
        lexer = shlex.shlex(_strip_comments(verify_command), posix=True, punctuation_chars=";&|()<>\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        return None
    at_command = True
    after_env = False
    skip_operand = False
    env_chdir = None
    chdir_next = False
    i = -1
    while i + 1 < len(tokens):
        i += 1
        tok = tokens[i]
        if _is_separator(tok):
            at_command = True
            after_env = False
            skip_operand = False
            env_chdir = None
            chdir_next = False
            continue
        if not at_command:
            continue
        # axis: an absolute env wrapper is skipped (with its options and their operands) so the python it launches is the launcher, never the wrapper
        if skip_operand:
            skip_operand = False
            if chdir_next:
                chdir_next = False
                env_chdir = _chain_chdir(env_chdir, tok)
            continue
        if after_env and tok.startswith("-"):
            # axis: an env split-string operand is spliced back in as words, so the python it names is still the launcher
            split = _env_split_words(tok, tokens, i)
            if split is not None:
                words, used = split
                tokens[i:i + used] = words
                i -= 1
                continue
            # axis: env -C/--chdir moves the working directory the launcher path resolves from; a relative launcher after it is rebased onto that directory
            if tok in ("-C", "--chdir"):
                chdir_next = True
            elif tok.startswith("--chdir="):
                env_chdir = _chain_chdir(env_chdir, tok[len("--chdir="):])
            elif tok.startswith("-C"):
                env_chdir = _chain_chdir(env_chdir, tok[2:])
            skip_operand = tok in _ENV_OPERAND_OPTIONS or tok in _ENV_SPLIT_OPTIONS
            continue
        if os.path.basename(tok) == "env":
            after_env = True
            continue
        if tok in _COMMAND_WORDS or _ENV_TOKEN.match(tok):
            continue
        at_command = False
        if env_chdir is not None and not os.path.isabs(tok) and "/" in tok:
            tok = _rebase_launcher(env_chdir, tok)
            if tok is None:
                return None
        if _is_python_program(tok):
            return tok
        if "/" in tok:
            for arg in tokens[i + 1:]:
                if _is_separator(arg):
                    break
                if arg == "-m" or arg.endswith(".py"):
                    return tok
    return None


def launcher_argv(value):
    """The launcher prefix a ``breakItInterpreter`` value names: its shell words as a non-empty
    list, or ``None`` when it is not a string, does not split, is empty, or leads with an option.
    The one validator of the key; never raises."""
    if not isinstance(value, str):
        return None
    try:
        words = shlex.split(value, posix=True)
    except ValueError:
        return None
    if not words or not words[0] or words[0].startswith("-"):
        return None
    return words


def resolve_interpreter(config):
    """The launcher a break-it run of ``config``'s session uses: the ``breakItInterpreter`` prefix
    (a list) when that key is set, ``[]`` when it is set but invalid, else what the verify command
    names (``project_interpreter``: a string or ``None``). Executes nothing."""
    config = config if isinstance(config, dict) else {}
    value = config.get(INTERPRETER_KEY)
    if value is not None:
        # axis: a set key never falls back to the verify command's launcher; an invalid one is the empty prefix, which reads not-run — see bite-proof record wo_1_1961_break_it_interpreter_key
        return launcher_argv(value) or []
    return project_interpreter(config.get("verifyCommand"))


def _record(head, block, outcome, reason=None, exit_code=None, output="", interpreter=None):
    block = block if isinstance(block, dict) else {}
    # axis: run output is subprocess text the test or the tested code wrote; it passes the fail-closed scrub before any record carries it
    output = readout.scrub(output)[0] if output else ""
    return {"schema": SCHEMA, "role": ROLE, "path": block.get("path"),
            "command": block.get("run"), "head": head, "sha256": block.get("sha256"),
            "content": block.get("content"),
            "outcome": outcome, "reason": reason, "exitCode": exit_code, "output": output,
            "interpreter": shlex.join(interpreter) if isinstance(interpreter, list) else interpreter}


def _git(repo_root, *args):
    """Run git in its own session, so a timeout kills the whole group (filter and hook helpers too)."""
    cmd = ["git", "-C", repo_root] + list(args)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_clean_env(),
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=_GIT_TIMEOUT)
    except BaseException:
        _kill_group(proc.pid)
        proc.wait()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def _tail_text(raw, cut):
    """The last ``OUTPUT_TAIL_BYTES`` bytes of ``raw`` as text, never more once re-encoded."""
    if cut:
        while raw and 0x80 <= raw[0] <= 0xBF:
            raw = raw[1:]
    text = raw.decode("utf-8", errors="replace")
    total, start = 0, len(text)
    for i in range(len(text) - 1, -1, -1):
        total += len(text[i].encode("utf-8"))
        if total > OUTPUT_TAIL_BYTES:
            break
        start = i
    return text[start:]


class _TailDrain(threading.Thread):
    """Reads a pipe to its end, keeping only the last ``OUTPUT_TAIL_BYTES`` bytes."""

    def __init__(self, stream):
        super().__init__(daemon=True)
        self.stream = stream
        self.buf = b""
        self.cut = False
        self.setup = None

    def run(self):
        try:
            while True:
                chunk = os.read(self.stream.fileno(), 65536)
                if not chunk:
                    return
                self.buf += chunk
                # axis: a setup-failure signature printed early in a long output is latched before the tail trim drops it — see bite-proof record wo_1_1981_not_executed
                if self.setup != REASON_COMMAND_NOT_FOUND:
                    found = setup_failure_reason(self.buf.decode("utf-8", errors="replace"))
                    if found is not None:
                        self.setup = found
                # axis: the stored output never exceeds OUTPUT_TAIL_BYTES while the test runs — see bite-proof record wo_a_1800_break-it
                if len(self.buf) > OUTPUT_TAIL_BYTES:
                    self.buf = self.buf[-OUTPUT_TAIL_BYTES:]
                    self.cut = True
        except (OSError, ValueError):
            return

    def tail(self):
        return _tail_text(self.buf, self.cut)


def _kill_group(pid, sig=signal.SIGKILL):
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _tagged_pids(token):
    """Pids of processes whose environment carries ``token`` (inherited through any session).

    On macOS, ``ps -E`` cannot read the environment of Apple's system programs (such as
    ``/bin/sleep``). So a detached worker running one, after it has left the copy's directory,
    escapes this net. The session kill and the in-copy working-directory net still apply.
    """
    needle = (_TOKEN_ENV + "=" + token).encode()
    found = []
    if os.path.isdir("/proc/self"):
        for name in os.listdir("/proc"):
            if name.isdigit():
                try:
                    with open("/proc/%s/environ" % name, "rb") as fh:
                        if needle in fh.read().split(b"\0"):
                            found.append(int(name))
                except OSError:
                    pass
        return found
    try:
        out = subprocess.run(["ps", "-Eww", "-A", "-o", "pid=,command="], capture_output=True,
                             timeout=_GIT_TIMEOUT).stdout
    except (OSError, subprocess.TimeoutExpired):
        return found
    for line in out.splitlines():
        if needle in line.split():
            try:
                found.append(int(line.split(None, 1)[0]))
            except (ValueError, IndexError):
                pass
    return found


def _kill_tagged(token):
    """Kill every process the run started, even one that left the command's session."""
    for pid in _tagged_pids(token):
        if pid != os.getpid():
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _kill_in_dir(copy):
    """Third net, independent of session and environment: kill any process whose working directory
    lies inside ``copy`` (``/proc/<pid>/cwd`` on Linux, ``lsof`` elsewhere when it is installed)."""
    root = os.path.realpath(copy)
    pids = []
    if os.path.isdir("/proc/self"):
        for name in os.listdir("/proc"):
            try:
                cwd = os.readlink("/proc/%s/cwd" % name) if name.isdigit() else ""
            except OSError:
                continue
            if cwd == root or cwd.startswith(root + os.sep):
                pids.append(int(name))
    elif shutil.which("lsof"):
        try:
            out = subprocess.run(["lsof", "-t", "+D", root], capture_output=True, timeout=30).stdout
            pids = [int(w) for w in out.split() if w.isdigit()]
        except (OSError, subprocess.TimeoutExpired):
            pass
    for pid in pids:
        if pid != os.getpid():
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _write_confined(copy, rel, content):
    """Create ``rel`` inside ``copy`` and nowhere else. None on success, else the not-run reason."""
    parts = rel.split("/")
    current = copy
    for part in parts[:-1]:
        current = os.path.join(current, part)
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            os.mkdir(current)
            continue
        # axis: a symlinked ancestor inside the copy is refused, never followed out of it — see bite-proof record wo_a_1800_break-it
        if stat.S_ISLNK(mode):
            return "path-escapes"
        if not stat.S_ISDIR(mode):
            return "path-exists"
    target = os.path.join(copy, *parts)
    real_copy = os.path.realpath(copy)
    real_parent = os.path.realpath(os.path.dirname(target))
    if real_parent != real_copy and not real_parent.startswith(real_copy + os.sep):
        return "path-escapes"
    try:
        # axis: O_EXCL refuses to overwrite a file the head already tracks — see bite-proof record wo_a_1800_break-it
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        return "path-exists"
    except OSError:
        return "write-failed"
    with os.fdopen(fd, "wb") as fh:
        fh.write(content.encode("utf-8"))
    return None


def _already_kept(copy, rel, sha):
    """True when ``rel`` is already a regular file in ``copy`` (no symlink on the way) whose bytes
    hash to ``sha`` — the test was kept in the change, so it is run as it stands."""
    parts = rel.split("/")
    current = copy
    try:
        for part in parts[:-1]:
            current = os.path.join(current, part)
            if not stat.S_ISDIR(os.lstat(current).st_mode):
                return False
        target = os.path.join(current, parts[-1])
        if not stat.S_ISREG(os.lstat(target).st_mode):
            return False
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            data = fh.read()
    except OSError:
        return False
    return hashlib.sha256(data).hexdigest() == sha


def _scan_entries(directory):
    """The paths of every entry of ``directory`` and of each ``@``-prefixed scope directory beneath it."""
    found = []
    for name in sorted(os.listdir(directory)):
        entry = os.path.join(directory, name)
        found.append(entry)
        if name.startswith("@") and os.path.isdir(entry) and not os.path.islink(entry):
            found.extend(os.path.join(entry, sub) for sub in sorted(os.listdir(entry)))
    return found


def _link_dependencies(repo_root, copy):
    """Link the reviewed checkout's installed dependency directories into ``copy``. None on success or when
    there is nothing to do, else the not-run reason."""
    root_real = os.path.realpath(repo_root)
    for name in DEPENDENCY_DIRS:
        source = os.path.join(os.path.abspath(repo_root), name)
        target = os.path.join(copy, name)
        # axis: a dependency directory the head tracks is already in the copy and is never replaced by a link
        if os.path.lexists(target) or not os.path.isdir(source):
            continue
        src_real = os.path.realpath(source)
        try:
            for entry in _scan_entries(source):
                if not os.path.islink(entry):
                    continue
                real = os.path.realpath(entry)
                inside_root = real == root_real or real.startswith(root_real.rstrip(os.sep) + os.sep)
                inside_src = real == src_real or real.startswith(src_real.rstrip(os.sep) + os.sep)
                # axis: a package that links back into the reviewed checkout's tracked tree is never linked, so a test cannot write a tracked file through it
                if inside_root and not inside_src:
                    return REASON_DEPENDENCY_LINK_UNSAFE
            os.symlink(source, target, target_is_directory=True)
        except OSError:
            # axis: a scan or link that fails reads not-run, never a run without the dependencies
            return REASON_DEPENDENCY_LINK_FAILED
    return None


def _declares_dependencies(copy):
    """True when the copy's root ``package.json`` (a regular file, read without following a symlink)
    declares a non-empty ``dependencies`` or ``devDependencies`` object."""
    target = os.path.join(copy, "package.json")
    try:
        if not stat.S_ISREG(os.lstat(target).st_mode):
            return False
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            data = json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    return any(isinstance(data.get(key), dict) and data[key] for key in ("dependencies", "devDependencies"))


def _run_contained(argv, env, copy, repo_root, token, timeout):
    """Run ``argv`` in ``copy`` under the reaper, with the token and working-directory sweeps, keeping only the
    output tail. Returns ``(launch_failed, timed_out, returncode, output, setup)``, ``setup`` being the setup-failure
    reason the drain latched while the output went by, or ``None``. Every process a break-it run starts,
    the readiness probe included, goes through here."""
    status_r, status_w = os.pipe()
    try:
        # The test runs as the child of a small reaper in its own session: on Linux the reaper adopts every orphaned descendant (child subreaper) and kills the whole tree when the test ends or the reaper is terminated, however a worker detached or cleared its environment. The environment-token sweep and the working-directory sweep below are the second and third nets, the only ones on other hosts, where a worker that both leaves the copy's directory tree and clears its environment is still not contained.
        proc = subprocess.Popen([sys.executable, "-I", "-c", _REAPER, str(status_w)] + argv, cwd=copy,
                                env=_clean_env(dict(env, **{_TOKEN_ENV: token}), repo_root),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, start_new_session=True,
                                pass_fds=(status_w,))
    except (FileNotFoundError, PermissionError):
        os.close(status_r)
        os.close(status_w)
        return True, False, None, "", None
    os.close(status_w)
    drain = _TailDrain(proc.stdout)
    timed_out = False
    try:
        drain.start()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        # axis: every exit path, an exception included, lets the reaper sweep its descendants before the group is killed — see bite-proof record wo_a_1800_break-it
        if proc.poll() is None:
            _kill_group(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=_TERM_GRACE)
            except subprocess.TimeoutExpired:
                pass
        # axis: the whole process tree dies after every exit, detached workers included, so none outlives the call — see bite-proof record wo_a_1800_break-it
        _kill_group(proc.pid)
        _kill_tagged(token)
        _kill_in_dir(copy)
        proc.wait()
        launch_failed = os.read(status_r, 1) == b"E"
        os.close(status_r)
        if drain.is_alive():
            drain.join(_DRAIN_JOIN)
        try:
            proc.stdout.close()
        except OSError:
            pass
    return launch_failed, timed_out, proc.returncode, drain.tail(), drain.setup


_PROBE_CODE = "import sys; sys.stdout.write(str(6 * 7) + 'ok')"
_PROBE_MARKER = "42ok"


def _run_in_copy(repo_root, d, copy, head, block, argv, env, timeout, write, interpreter=None):
    def rec(outcome, reason=None, exit_code=None, output=""):
        return _record(head, block, outcome, reason, exit_code, output, interpreter)

    try:
        # axis: the copy is an independent clone, so config, refs and tags the test writes stay inside it — see bite-proof record wo_a_1800_break-it
        added = _git(repo_root, "clone", "--quiet", "--no-checkout", "--shared", "--no-tags",
                     "--", os.path.abspath(repo_root), copy)
        if added.returncode == 0:
            added = _git(copy, "remote", "remove", "origin")
        if added.returncode == 0:
            added = _git(copy, "checkout", "--quiet", "--detach", head, "--")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return rec(OUTCOME_NOT_RUN, "copy-failed", output=str(exc)[-OUTPUT_TAIL_BYTES:])
    if added.returncode != 0:
        return rec(OUTCOME_NOT_RUN, "copy-failed",
                   output=_tail_text(added.stderr, True))
    # axis: the dependencies are linked before the block is written, so a block path under a linked directory meets a symlinked ancestor and is refused `path-escapes`
    unlinked = _link_dependencies(repo_root, copy)
    if unlinked:
        return rec(OUTCOME_NOT_RUN, unlinked)
    # axis: a target already in the copy with the block's own bytes is the kept test; it runs as it stands, never `path-exists`
    if write and _already_kept(copy, block["path"], block.get("sha256")):
        write = False
    if write:
        try:
            refusal = _write_confined(copy, block["path"], block["content"])
        except OSError:
            refusal = "write-failed"
        if refusal:
            return rec(OUTCOME_NOT_RUN, refusal)
    if interpreter:
        # axis: a launcher that cannot start reads not-run, never a failed test, and the probe runs contained like the test — see bite-proof record wo_5_1910_probe_containment
        failed, timed, status, tail, _ = _run_contained(
            (interpreter if isinstance(interpreter, list) else [interpreter]) + ["-c", _PROBE_CODE],
            env, copy, repo_root, uuid.uuid4().hex, timeout)
        # axis: only a launcher that really executes Python prints the computed marker; an echo-like program exits zero without it, so it reads unavailable, never passed
        if failed or timed or status != 0 or _PROBE_MARKER not in (tail or ""):
            return rec(OUTCOME_NOT_RUN, "interpreter-unavailable", output=tail or ("timed out" if timed else ""))
    # axis: a JavaScript launcher with dependencies declared and none installed is not launched, so npx never falls back to a global or cached runner and reads passed or failed without the project's dependencies
    if (os.path.basename(argv[0]) in _JS_LAUNCHERS and _declares_dependencies(copy)
            and not os.path.lexists(os.path.join(copy, "node_modules"))):
        return rec(OUTCOME_NOT_RUN, REASON_MODULE_NOT_FOUND,
                   output="the copy holds package.json with dependencies but the reviewed checkout has no installed node_modules")
    token = uuid.uuid4().hex
    launch_failed, timed_out, code, output, setup = _run_contained(argv, env, copy, repo_root, token, timeout)
    if launch_failed and not timed_out:
        return rec(OUTCOME_NOT_RUN, REASON_COMMAND_NOT_FOUND)
    if timed_out:
        return rec(OUTCOME_NOT_RUN, "timeout", output=output)
    tail_reason = setup_failure_reason(output, code)
    reason = REASON_COMMAND_NOT_FOUND if REASON_COMMAND_NOT_FOUND in (setup, tail_reason) else (setup or tail_reason)
    # axis: a run whose output shows a missing command or module, or that exits 127, reads not-run, never failed or passed — see bite-proof record wo_1_1981_not_executed
    if reason:
        return rec(OUTCOME_NOT_RUN, reason, exit_code=code, output=output)
    return rec(OUTCOME_PASSED if code == 0 else OUTCOME_FAILED, exit_code=code, output=output)


def run_one(repo_root, head, block, *, timeout=DEFAULT_TIMEOUT, write=True, interpreter=_UNSET):
    """Run one parsed block in a throwaway detached copy of ``head``. Always returns a record.
    Given ``interpreter`` (the project's launcher, or ``None`` when it could not be resolved), a
    command whose program is a Python interpreter runs under that launcher, and is not run when
    there is none or it does not start. A ``list`` is the calibrated launcher prefix: it also runs a
    ``pytest`` program as ``prefix -m pytest``, and the empty list (an invalid key) is not run.
    Left ``_UNSET``, the command runs as written."""
    block = dict(block) if isinstance(block, dict) else {}
    argv, env, refusal = parse_command(block.get("run"))
    if refusal:
        return _record(head, block, OUTCOME_NOT_RUN, refusal)
    substituted = None
    if isinstance(interpreter, list):
        is_pytest = os.path.basename(argv[0]) in ("pytest", "py.test")
        if _is_python_program(argv[0]) or is_pytest:
            # axis: a calibrated key that is set but invalid reads not-run, never the verify command's launcher or a PATH python — see bite-proof record wo_1_1961_break_it_interpreter_key
            if not interpreter:
                return _record(head, block, OUTCOME_NOT_RUN, "interpreter-key-invalid")
            # axis: a python or pytest run executes under the calibrated launcher prefix, the pytest one as `-m pytest` — see bite-proof record wo_1_1961_break_it_interpreter_key
            substituted = interpreter
            argv = interpreter + (["-m", "pytest"] if is_pytest else []) + argv[1:]
    elif interpreter is not _UNSET and _is_python_program(argv[0]):
        # axis: no launcher means not-run, never a PATH python the project does not use — see bite-proof record wo_3_1910_break_it_interpreter
        if not interpreter:
            return _record(head, block, OUTCOME_NOT_RUN, "interpreter-unresolved")
        # axis: a python run executes under the supplied launcher — see bite-proof record wo_3_1910_break_it_interpreter
        substituted = interpreter
        argv = [interpreter] + argv[1:]
    if (not isinstance(head, str) or not head or head.startswith("-")
            or not isinstance(repo_root, str) or not repo_root):
        return _record(head, block, OUTCOME_NOT_RUN, "head-unresolved")
    if write and (not isinstance(block.get("content"), str) or _path_unsafe(block.get("path"))):
        return _record(head, block, OUTCOME_NOT_RUN, "path-unsafe")
    d = tempfile.mkdtemp(prefix="break-it-")
    copy = os.path.join(d, "copy")
    try:
        result = _run_in_copy(repo_root, d, copy, head, block, argv, env, timeout, write, substituted)
    except Exception as exc:  # the caller decides from the record; nothing is raised
        result = _record(head, block, OUTCOME_NOT_RUN, "run-error", output=str(exc)[-OUTPUT_TAIL_BYTES:],
                         interpreter=substituted)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return result


def _not_run(head, block, reason):
    return _record(head, block, OUTCOME_NOT_RUN, reason)


def _safe_run(runner, repo_root, head, block, interpreter=_UNSET, **kwargs):
    if interpreter is not _UNSET:
        kwargs["interpreter"] = interpreter
    try:
        got = runner(repo_root, head, block, **kwargs)
    except Exception:  # the caller decides from the record; nothing is raised
        return _not_run(head, block, "runner-error")
    if not isinstance(got, dict) or got.get("outcome") not in (
            OUTCOME_FAILED, OUTCOME_PASSED, OUTCOME_NOT_RUN):
        return _not_run(head, block, "runner-error")
    return got


def intercept(findings, repo_root, head, *, runner=run_one, interpreter=_UNSET):
    """Run every break-it finding (each run is bounded by its timeout; how many to write is the test
    role's policy, stated in its agent file) and fold the results in. Returns ``(kept, runs, exempt_ids)``:
    ``kept`` is the findings (copies) with the passed break-it ones left out and the failed or
    not-run ones stamped with ``RUN_FIELD``; ``runs`` is one entry per break-it finding;
    ``exempt_ids`` holds ``id()`` of each stamped copy."""
    kept, runs, exempt_ids = [], [], set()
    for finding in findings or []:
        if not isinstance(finding, dict):
            kept.append(finding)
            continue
        copy = dict(finding)
        # axis: a seat-supplied RUN_FIELD stamp is never trusted, on any finding — see bite-proof record wo_a_1800_break-it
        copy.pop(RUN_FIELD, None)
        if not is_break_it(copy):
            kept.append(copy)
            continue
        block, refusal = parse_block(copy.get("suggestion"))
        # axis: the transport scrubs suggestions as prose; a test whose bytes it changed is never run in altered form, but its parsed block is kept so the finding still earns the scope exemption and reaches the verifier
        redacted = not refusal and copy.get(REDACTED_FIELD) is True
        if redacted:
            refusal = "suggestion-redacted"
        if refusal:
            record = _not_run(head, None if redacted else block, refusal)
        elif block["path"] != copy.get("file"):
            record = _not_run(head, block, "path-mismatch")
        else:
            record = _safe_run(runner, repo_root, head, block, interpreter)
        runs.append(dict(record, title=copy.get("title"), file=copy.get("file")))
        # axis: a passing break-it test means the change held, so the finding is dropped — see bite-proof record wo_a_1800_break-it
        if record["outcome"] == OUTCOME_PASSED:
            continue
        copy[RUN_FIELD] = record
        kept.append(copy)
        # axis: only a well-formed block on its own file at line 1 buys the scope exemption; a malformed one keeps ordinary scope checking
        if block and block["path"] == copy.get("file") and _coerce_line(copy.get("line")) == (True, 1):
            exempt_ids.add(id(copy))
    return kept, runs, exempt_ids


def _coerce_line(value):
    # imported late: engine_adapter's pinned import closure must not gain session_contract
    from session_contract import coerce_line
    return coerce_line(value)


_SELECT_SHORT = ("-k", "-t", "-g")
_SELECT_LONG = ("--testNamePattern", "--grep", "--filter", "--match")


def _names_path(tok, path):
    """True when the argv token ``tok`` is ``path`` (or ``path::...``) in any equivalent repo-relative spelling."""
    head = tok.partition("::")[0]
    return bool(head) and not head.startswith("-") and posixpath.normpath(head) == posixpath.normpath(path)


def _selects_tests(tok, titles, old_path):
    """True when the argv token ``tok`` filters which tests run: by a flag, a ``::`` selector or an old title. The
    token naming ``old_path`` is judged by its ``::`` selector alone, so a path that contains a title is no filter."""
    if _names_path(tok, old_path):
        # axis: the path token is judged by the `::` rule alone, so a test file named after its own test still renames — see bite-proof record wo_a_2053_break_it_body
        return "::" in tok
    return (tok in _SELECT_SHORT or tok in _SELECT_LONG
            or any(tok.startswith(flag + "=") for flag in _SELECT_LONG)
            or any(tok.startswith(flag) and not tok.startswith("--") for flag in _SELECT_SHORT)
            or "::" in tok or any(old in tok for old, _ in titles))


def _carries_options(name):
    """True when the environment variable ``name`` carries runner options (``PYTEST_ADDOPTS``, ``*_ADDOPTS``,
    ``*_OPTIONS``); every other variable is plain data."""
    return name == "PYTEST_ADDOPTS" or name.endswith("_ADDOPTS") or name.endswith("_OPTIONS")


def _env_selects(value, titles, old_path):
    """True when an option-carrying environment value, read as a command line, carries a test selector (or cannot be read)."""
    try:
        parts = shlex.split(value)
    except ValueError:
        return True
    return any(_selects_tests(part, titles, old_path) for part in parts)


def _rewrite_command(command, old_path, new_path, titles):
    """``(command, None)`` to run for the test found at ``new_path``, or ``(None, reason)`` when the command cannot
    be pointed at it: ``command-unmapped`` (not a plain command, or no token names ``old_path``) or
    ``command-selects-tests`` (a renamed test whose command filters by name)."""
    argv, env, refusal = parse_command(command)
    if refusal:
        return None, "command-unmapped"
    # axis: a renamed test's command that filters by flag, selector or old title is refused, because the filter would select nothing in the moved copy — see bite-proof record wo_a_2053_break_it_body
    if titles and any(_selects_tests(tok, titles, old_path) for tok in argv):
        return None, "command-selects-tests"
    # axis: a selector the environment carries (PYTEST_ADDOPTS=-k ...) filters like one in argv, so it is refused the same way — see bite-proof record wo_a_2053_break_it_body
    if titles and any(_env_selects(value, titles, old_path) for name, value in env.items() if _carries_options(name)):
        return None, "command-selects-tests"
    # axis: a test found at its own path runs the command exactly as the loop ran it — see bite-proof record wo_a_2053_break_it_body
    if new_path == old_path:
        return command, None
    moved, replaced = [], False
    for tok in argv:
        if tok == old_path or tok.startswith(old_path + "::"):
            tok, replaced = new_path, True
        moved.append(tok)
    if not replaced:
        return None, "command-unmapped"
    return " ".join([shlex.quote("%s=%s" % pair) for pair in env.items()] + [shlex.join(moved)]), None


_COLLECTION_SETTINGS = ("python_functions", "python_classes", "python_files", "addopts")


def _collection_overrides(repo_root, head):
    """True when the repository at ``head`` may declare a pytest collection override: a root pytest.ini,
    pyproject.toml ([tool.pytest.ini_options]), setup.cfg ([tool:pytest]) or tox.ini ([pytest]) that sets
    python_functions, python_classes, python_files or addopts (any value: addopts can carry a ``-k`` selector that
    deselects the new name, and it is not parsed), or one that cannot be read or parsed (fail closed)."""
    import configparser
    sections = (("pytest.ini", "pytest"), ("setup.cfg", "tool:pytest"), ("tox.ini", "pytest"), ("pyproject.toml", None))
    for name, section in sections:
        tree = _git(repo_root, "ls-tree", "-z", head, "--", name)
        if tree.returncode != 0:
            return True
        meta = tree.stdout.decode("utf-8", errors="replace").split("\0", 1)[0].partition("\t")[0].split()
        if not meta:
            continue
        if len(meta) != 3 or meta[1] != "blob":
            return True
        blob = _git(repo_root, "cat-file", "blob", meta[2])
        if blob.returncode != 0:
            return True
        try:
            text = blob.stdout.decode("utf-8")
            if section is None:
                import tomllib
                table = tomllib.loads(text).get("tool", {}).get("pytest", {}).get("ini_options", {})
                if not isinstance(table, dict) or any(key in table for key in _COLLECTION_SETTINGS):
                    return True
            else:
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read_string(text)
                if parser.has_section(section) and any(parser.has_option(section, key) for key in _COLLECTION_SETTINGS):
                    return True
        except Exception:
            return True
    return False


def _body_search(repo_root, base, head, record, today, res, runner, interpreter):
    """The body search behind the three rows that read the test missing or changed: ``today`` unless the test is
    found, unchanged up to formatting and its title, once among the files the final diff carries."""
    # imported late: break_it's import closure is pinned (test_payload_contracts_layering)
    from break_it_body import locate, pytest_collected, supported_suffixes
    suffixes = supported_suffixes()
    if posixpath.splitext(record["path"].lower())[1] not in suffixes:
        return today
    try:
        diff = _git(repo_root, "diff", "--name-only", "-z", base + "..." + head)
        if diff.returncode != 0:
            return res(KEPT_UNRESOLVED, "diff-failed")
        candidates = []
        for name in diff.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
            if not name or posixpath.splitext(name.lower())[1] not in suffixes or _path_unsafe(name):
                continue
            tree = _git(repo_root, "ls-tree", "-z", head, "--", name)
            if tree.returncode != 0:
                return res(KEPT_UNRESOLVED, "ls-tree-failed")
            meta = tree.stdout.decode("utf-8", errors="replace").split("\0", 1)[0].partition("\t")[0].split()
            if len(meta) != 3 or meta[0] not in _REGULAR_MODES or meta[1] != "blob":
                continue
            blob = _git(repo_root, "cat-file", "blob", meta[2])
            if blob.returncode != 0:
                return res(KEPT_UNRESOLVED, "cat-file-failed")
            try:
                text = blob.stdout.decode("utf-8")
            except UnicodeDecodeError:
                text = None
            candidates.append((name, text))
    except (OSError, subprocess.TimeoutExpired):
        return res(KEPT_UNRESOLVED, "git-failed")
    found = locate(record["content"], record["path"], candidates)
    if found["status"] in ("unsupported", "none"):
        return today
    if found["status"] != "found":
        return res(KEPT_UNRESOLVED, found["reason"])
    # axis: a renamed pytest test is accepted only when the repository at the reviewed head declares no pytest collection override, because a custom python_functions could leave the new name uncollected (or an addopts -k selector deselect it) while the host still passes; pytest configuration says nothing about a vitest or jest run, so only a test read by a pytest-collected front is gated — see bite-proof records wo_a_2053_break_it_body and wo_b_2061_break_it_body_js
    try:
        if found["titles"] and pytest_collected(record["path"]) and _collection_overrides(repo_root, head):
            return res(KEPT_UNRESOLVED, "binding-conflict")
    except (OSError, subprocess.TimeoutExpired):
        return res(KEPT_UNRESOLVED, "git-failed")
    command, refusal = _rewrite_command(record["command"], record["path"], found["path"], found["titles"])
    if refusal:
        return res(KEPT_UNRESOLVED, refusal)
    run = _safe_run(runner, repo_root, head,
                    {"path": found["path"], "run": command, "content": "", "sha256": record["sha256"]},
                    interpreter, write=False)
    if run["outcome"] == OUTCOME_PASSED:
        return res(KEPT, "body-match", run)
    return res(KEPT_FAILING, run.get("reason"), run)


def check_kept(repo_root, base, head, record, *, runner=run_one, interpreter=_UNSET):
    """Whether the break-it test the loop ran is still in the final change, unchanged and passing.
    Returns ``{"path", "outcome", "reason", "run"}``; ``outcome`` is one of the ``KEPT*`` values."""
    record = record if isinstance(record, dict) else {}
    path = record.get("path")

    def res(outcome, reason=None, run=None):
        return {"path": path, "outcome": outcome, "reason": reason, "run": run}

    def searched(today):
        # axis: a record without content never searches, so it keeps the byte-exact check — see bite-proof record wo_a_2053_break_it_body
        if not isinstance(record.get("content"), str):
            return today
        return _body_search(repo_root, base, head, record, today, res, runner, interpreter)

    for value in (repo_root, base, head, path, record.get("command"), record.get("sha256")):
        if not isinstance(value, str) or not value:
            return res(KEPT_UNRESOLVED, "input-missing")
    if base.startswith("-") or head.startswith("-") or _path_unsafe(path):
        return res(KEPT_UNRESOLVED, "input-unsafe")
    try:
        tree = _git(repo_root, "ls-tree", "-z", head, "--", path)
        if tree.returncode != 0:
            return res(KEPT_UNRESOLVED, "ls-tree-failed")
        entry = tree.stdout.decode("utf-8", errors="replace").split("\0", 1)[0]
        if not entry:
            return searched(res(KEPT_MISSING, "not-in-head"))
        meta = entry.partition("\t")[0].split()
        if len(meta) != 3 or meta[0] not in _REGULAR_MODES or meta[1] != "blob":
            return res(KEPT_NOT_REGULAR, "not-a-regular-file")
        diff = _git(repo_root, "diff", "--name-only", base + "..." + head, "--", path)
        if diff.returncode != 0:
            return res(KEPT_UNRESOLVED, "diff-failed")
        # axis: a file the final diff does not carry is missing, even when head holds a file at that path — see bite-proof record wo_a_1800_break-it
        if not diff.stdout.strip():
            return searched(res(KEPT_MISSING, "not-in-diff"))
        blob = _git(repo_root, "cat-file", "blob", meta[2])
        if blob.returncode != 0:
            return res(KEPT_UNRESOLVED, "cat-file-failed")
    except (OSError, subprocess.TimeoutExpired):
        return res(KEPT_UNRESOLVED, "git-failed")
    # axis: the committed bytes must hash to the sha256 the loop ran, else the test was changed — see bite-proof record wo_a_1800_break-it
    if hashlib.sha256(blob.stdout).hexdigest() != record["sha256"]:
        return searched(res(KEPT_CHANGED, "sha256-differs"))
    run = _safe_run(runner, repo_root, head,
                    {"path": path, "run": record["command"], "content": "",
                     "sha256": record["sha256"]}, interpreter, write=False)
    if run["outcome"] == OUTCOME_PASSED:
        return res(KEPT, run=run)
    return res(KEPT_FAILING, run.get("reason"), run)
