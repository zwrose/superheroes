#!/usr/bin/env python3
"""Run a break-it test the test role wrote as text, in the session's own working copy, and check it was kept (#1800, #2210).

Stdlib only. A break-it test runs **only** from the root of the session's own working copy
(``repo_root``), and only when that tree is exactly the reviewed head: the working copy's HEAD must be
the head and no tracked file may be modified or staged, else the run is ``not-run`` and nothing is
written. The runner writes nowhere but the working copy (its own git directory included) and the
session folder: the test file it writes, the run's temporary and cache folders (``TMPDIR``, ``TMP``,
``TEMP`` and ``XDG_CACHE_HOME`` point at a per-run folder in the session folder, or in the git
directory's ``superheroes`` folder when no session folder is given) and nothing else. After the run, in
a ``finally``, it restores the working copy to what it was: the test file and the directories the write
made, the branch HEAD points at, HEAD, the local git config, the index, every tracked file and every
non-ignored untracked file the test added; a restore that fails is recorded ``working-copy-restore-failed``.
No other ref is rewound, deleted or created (a second worktree of the repository can change refs during the
run, and the restore cannot tell who changed one): each ref that still differs from the snapshot is left as it
is and named in the record's ``refsLeft``.
The one limit, stated plainly: a test that writes to an absolute path outside the working copy and the
session folder is not stopped (there is no OS sandbox). Its process tree never outlives the call: a process
the run left with its working directory in the working copy is stopped too, unless it started before the run
or is this process or one of its ancestors.
Every outcome is a record — ``failed``, ``passed`` or ``not-run`` with a reason —
and the caller decides from the record; nothing is raised."""
import hashlib
import json
import os
import pathlib
import posixpath
import re
import shlex
import signal
import stat
import subprocess
import sys
import threading
import time
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
    "The loop runs `run` without a shell, from the root of the session's own working copy, at the "
    "reviewed head: one command, "
    "optionally led by `NAME=value` settings, with no pipes, redirects, "
    "`;`, `&&`, `||`, backticks or `$(`. A command that needs anything else is not run. A `run` "
    "whose program is `python` or `python3` (or another Python interpreter path), or, when the "
    "project's `breakItInterpreter` calibration is set, `pytest` or `py.test` (run as "
    "`<launcher> -m pytest`), runs under the project's own interpreter launcher: the "
    "`breakItInterpreter` calibration when set, else the one its verify command uses. It is not run "
    "when that launcher cannot be found.")
CONTENT_RULES = (
    "The fixer writes the content byte for byte and commits it, and the review keeps the test only "
    "when the committed file is unchanged (a Python, JavaScript or TypeScript test may differ only in "
    "formatting and title, and a JavaScript or TypeScript comment counts). So the content must "
    "already be the file the project's own rules accept: every marker or directive comment those "
    "rules require on a test file (in CLAUDE.md, the calibration, or a check the project runs over "
    "its tests, which you can read in the repository) is written in its full required form, "
    "never as a bare marker the project would then have to extend.")

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
        # axis: a leading git routing assignment is refused, so the working copy's git can never be redirected — see bite-proof record wo_a_1800_break-it
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


def _record(head, block, outcome, reason=None, exit_code=None, output="", interpreter=None, restored=None,
            refs_left=None):
    """The run record. ``restored`` names what the run had to put back in the working copy, in restore order;
    ``refs_left`` the refs that differ from the snapshot after the restore and were left as they were."""
    block = block if isinstance(block, dict) else {}
    # axis: run output is subprocess text the test or the tested code wrote; it passes the fail-closed scrub before any record carries it
    output = readout.scrub(output)[0] if output else ""
    return {"schema": SCHEMA, "role": ROLE, "path": block.get("path"),
            "command": block.get("run"), "head": head, "sha256": block.get("sha256"),
            "content": block.get("content"),
            "outcome": outcome, "reason": reason, "exitCode": exit_code, "output": output,
            "interpreter": shlex.join(interpreter) if isinstance(interpreter, list) else interpreter,
            "restored": list(restored or []), "refsLeft": sorted(refs_left or [])}


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
    ``/bin/sleep``). So a detached worker running one escapes this net. The reaper and the session
    kill still apply.
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


def _ps_table():
    """``{pid: (ppid, start time text)}`` for every process, or an empty table when ``ps`` cannot be read."""
    try:
        out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,lstart="], capture_output=True,
                             timeout=_GIT_TIMEOUT, env=dict(os.environ, LC_ALL="C")).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    table = {}
    for line in out.decode("utf-8", errors="replace").splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2].strip())
    return table


class _DescendantWatch(threading.Thread):
    """Where the environment net cannot see a program's environment (macOS system programs), records the
    descendants of the run while its process chain is still intact, so a worker that detaches and outlives its
    parent is still stopped. A process is stopped only when its pid and start time both match what was recorded."""

    def __init__(self, root_pid):
        super().__init__(daemon=True)
        self.root_pid = root_pid
        self.seen = {}
        self._stop_event = threading.Event()

    def sample(self):
        table = _ps_table()
        family = {self.root_pid}
        grew = True
        while grew:
            grew = False
            for pid, (ppid, _) in table.items():
                if ppid in family and pid not in family:
                    family.add(pid)
                    grew = True
        for pid in family:
            if pid != self.root_pid and pid in table:
                self.seen.setdefault(pid, table[pid][1])

    def run(self):
        while not self._stop_event.is_set():
            self.sample()
            self._stop_event.wait(0.05)

    def stop_and_kill(self):
        self._stop_event.set()
        # axis: the sampling thread is finished before the final sample and the sweep, so no insertion races the iteration and no worker lands after it — see bite-proof record wo_e_2210_review_round2
        if self.is_alive() and threading.current_thread() is not self:
            self.join(_GIT_TIMEOUT + 5)
        self.sample()
        table = _ps_table()
        for pid, start in list(self.seen.items()):
            if pid != os.getpid() and pid in table and table[pid][1] == start:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


def _ancestors(parents, pid):
    """The pids from ``pid`` up the ``{pid: ppid}`` table, ``pid`` included."""
    chain = set()
    while pid and pid not in chain:
        chain.add(pid)
        pid = parents.get(pid)
    return chain


def _proc_cwd_table():
    """``(processes, ancestors, note)`` read from ``/proc``: ``processes`` is ``[(pid, cwd, started, ppid, ident)]`` for
    every process whose working directory can be read, ``started`` an epoch time rounded up to the clock tick (so a
    process that began in the tick before the run reads as started in it), ``ppid`` its parent and ``ident`` the raw
    kernel start tick, which does not move between two readings the way ``started`` does; ``ancestors`` the pids of this process and
    its ancestors; ``note`` is ``None``. Inside a sandbox whose ``/proc`` is another PID namespace's (``/proc/self``
    is not this process), the pids it names are not this process's to signal, so the table is empty with a ``note``."""
    try:
        foreign = os.readlink("/proc/self") != str(os.getpid())
    except OSError:
        foreign = True
    if foreign:
        return [], set(), "working-directory net skipped: /proc names another PID namespace"
    ticks = os.sysconf("SC_CLK_TCK")
    with open("/proc/uptime") as fh:
        booted = time.time() - float(fh.read().split()[0])
    parents, processes = {}, []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            with open("/proc/%s/stat" % name) as fh:
                tail = fh.read().rsplit(")", 1)[1].split()
            parents[pid] = int(tail[1])
            started = booted + (int(tail[19]) + 1) / ticks
            processes.append((pid, os.readlink("/proc/%s/cwd" % name), started, parents[pid], int(tail[19])))
        except (OSError, IndexError, ValueError):
            pass
    return processes, _ancestors(parents, os.getpid()), None


def _lsof_cwds(text):
    """``{pid: cwd}`` from ``lsof -a -d cwd -Fpn`` output."""
    found, pid = {}, None
    for line in text.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            found[pid] = line[1:]
    return found


def _ps_start(text):
    """The epoch time, rounded up to the second, a ``ps -o lstart=`` text names, or ``None``."""
    try:
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y")) + 1
    except (ValueError, OverflowError):
        return None


def _lsof_cwd_table():
    """The same shape as ``_proc_cwd_table``, read with ``lsof -a -d cwd -Fpn`` and ``ps``, for a host without
    ``/proc``. ``note`` names why the table is empty when ``lsof`` or ``ps`` cannot be read."""
    try:
        out = subprocess.run(["lsof", "-a", "-d", "cwd", "-Fpn"], capture_output=True, timeout=_GIT_TIMEOUT).stdout
    except FileNotFoundError:
        return [], set(), "working-directory net skipped: lsof is absent"
    except (OSError, subprocess.TimeoutExpired):
        return [], set(), "working-directory net skipped: lsof could not be read"
    table = _ps_table()
    if not table:
        return [], set(), "working-directory net skipped: ps could not be read"
    cwds = _lsof_cwds(out.decode("utf-8", errors="replace"))
    processes = []
    for pid, cwd in cwds.items():
        started = _ps_start(table[pid][1]) if pid in table else None
        if started is not None:
            processes.append((pid, cwd, started, table[pid][0], table[pid][1]))
    return processes, _ancestors({pid: ppid for pid, (ppid, _) in table.items()}, os.getpid()), None


def _cwd_table():
    return _proc_cwd_table() if os.path.isdir("/proc/self") else _lsof_cwd_table()


def _process_ident(entry):
    """The stable start mark of a table entry ``(pid, cwd, started[, ppid[, ident]])``: its ``ident`` (the raw kernel
    start tick, or the ``ps`` start text), else its ``started`` time."""
    return entry[4] if len(entry) > 4 else entry[2]


def _known_processes(reader=None):
    """The ``(pid, ident)`` identity of every process the working-directory table names now, taken before a run
    launches so the net can tell a process that was already there from one the run started. ``ident`` is the
    entry's raw start mark when it has one (``_process_ident``), which is stable between two readings."""
    try:
        return set((entry[0], _process_ident(entry)) for entry in (reader or _cwd_table)()[0])
    except Exception:  # an unreadable table leaves the time test alone to decide
        return set()


def _belongs_to_run(pid, parent_of, run_pid):
    """True when the table shows ``pid`` is the run's: its parent chain reaches the run's reaper (``run_pid``), or it
    has itself been orphaned (its own parent is 0 or 1), which is how a worker that detached from the run reads once its
    parent is gone. A process whose parent is alive and not the run's was launched by something else and is not the
    run's, whatever that parent's own parent is."""
    if parent_of.get(pid) in (0, 1):
        return True
    seen = set()
    while pid not in seen:
        seen.add(pid)
        pid = parent_of.get(pid)
        if pid is None:
            return False
        if pid == run_pid:
            return True
    return False


def _kill_in_working_copy(root, since, reader=None, known=frozenset(), run_pid=None):
    """Kill every process that belongs to the run (``_belongs_to_run``: descended from ``run_pid``, or orphaned), whose
    working directory is ``root`` or lies beneath it, that started at or after ``since`` (an epoch time), was not
    already running when the run launched (``known``, the ``(pid, ident)`` pairs taken then, since a start time
    rounded up can read a process from the run's own second as new), and is neither this process nor one of its
    ancestors. A process launched independently in the checkout while the run goes, whose parent is alive and not the
    run's, is never touched. A second net beside the descendant watch,
    which samples and so misses a worker that starts and detaches between two samples. ``reader`` returns
    ``(processes, ancestors, note)`` as ``_cwd_table`` does; an entry without a parent is not shown to belong to the run
    and is left alone. Returns the note when the net could not run, else ``None``."""
    processes, ancestors, note = (reader or _cwd_table)()
    if note:
        return note
    real_root = os.path.realpath(root)
    inside = real_root.rstrip(os.sep) + os.sep
    parent_of = {entry[0]: entry[3] for entry in processes if len(entry) > 3}
    for entry in processes:
        pid, cwd, started = entry[:3]
        # axis: a process that started before the run, this process and its ancestors are never touched, so the session's own shell survives the net
        if pid == os.getpid() or pid in ancestors or started < since or (pid, _process_ident(entry)) in known:
            continue
        # axis: a process the table does not show to descend from the run or to be orphaned is never signalled, so independent work in the checkout survives
        if not _belongs_to_run(pid, parent_of, run_pid):
            continue
        if cwd == real_root or cwd.startswith(inside):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    return None


def _write_confined(root, rel, content, created=None):
    """Create ``rel`` inside ``root`` and nowhere else. None on success, else the not-run reason. Each directory
    the write makes is appended to ``created`` when it is given."""
    parts = rel.split("/")
    current = root
    for part in parts[:-1]:
        current = os.path.join(current, part)
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            os.mkdir(current)
            if created is not None:
                created.append(current)
            continue
        # axis: a symlinked ancestor is refused, never followed out of the root — see bite-proof record wo_a_1800_break-it
        if stat.S_ISLNK(mode):
            return "path-escapes"
        if not stat.S_ISDIR(mode):
            return "path-exists"
    target = os.path.join(root, *parts)
    real_root = os.path.realpath(root)
    real_parent = os.path.realpath(os.path.dirname(target))
    if real_parent != real_root and not real_parent.startswith(real_root + os.sep):
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


def _already_kept(root, rel, sha):
    """True when ``rel`` is already a regular file in ``root`` (no symlink on the way) whose bytes
    hash to ``sha`` — the test was kept in the change, so it is run as it stands."""
    parts = rel.split("/")
    current = root
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


def _declares_dependencies(root):
    """True when the root ``package.json`` of ``root`` (a regular file, read without following a symlink)
    declares a non-empty ``dependencies`` or ``devDependencies`` object."""
    target = os.path.join(root, "package.json")
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


def _run_contained(argv, env, cwd, repo_root, token, timeout):
    """Run ``argv`` in ``cwd`` under the reaper, with the token sweep, keeping only the
    output tail. Returns ``(launch_failed, timed_out, returncode, output, setup)``, ``setup`` being the setup-failure
    reason the drain latched while the output went by, or ``None``. Every process a break-it run starts,
    the readiness probe included, goes through here."""
    status_r, status_w = os.pipe()
    known = _known_processes()
    started_at = time.time()
    try:
        # The test runs as the child of a small reaper in its own session: on Linux the reaper adopts every orphaned descendant (child subreaper) and kills the whole tree when the test ends or the reaper is terminated, however a worker detached or cleared its environment. The environment-token sweep below is the second net, and on other hosts the descendant watch the third. The last net is the working-directory sweep (`_kill_in_working_copy`): the working directory is the session's own checkout, so it stops only a process that started at or after this run and is neither this process nor an ancestor of it, which leaves the session's own shell alone.
        proc = subprocess.Popen([sys.executable, "-I", "-c", _REAPER, str(status_w)] + argv, cwd=cwd,
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
    # axis: off Linux a detached system program hides its environment, so the run's descendants are tracked by process chain while it is alive, in place of the removed working-directory sweep — see bite-proof record wo_a_2210_break_it_working_copy
    watch = None if os.path.isdir("/proc/self") else _DescendantWatch(proc.pid)
    try:
        if watch is not None:
            watch.start()
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
        if watch is not None:
            try:
                watch.stop_and_kill()
            except Exception:  # the working-directory net below still runs
                pass
        # axis: a worker that started and detached between two samples of the watch, or that hides its environment, is still stopped by where it runs and when it started — see bite-proof record wo_e_2210_review_round2
        try:
            net_note = _kill_in_working_copy(repo_root, started_at, known=known, run_pid=proc.pid)
        except Exception as exc:  # a net that cannot read the process table is disclosed, never raised
            net_note = "working-directory net skipped: %s" % str(exc)[-200:]
        proc.wait()
        launch_failed = os.read(status_r, 1) == b"E"
        os.close(status_r)
        if drain.is_alive():
            drain.join(_DRAIN_JOIN)
        try:
            proc.stdout.close()
        except OSError:
            pass
    output = drain.tail()
    if net_note:
        # the note rides inside the output bound: the tail gives up the room it takes
        room = max(OUTPUT_TAIL_BYTES - len(net_note.encode("utf-8")) - 1, 0)
        output = output.encode("utf-8")[-room:].decode("utf-8", errors="ignore") if room else ""
        output = (output + "\n" if output else "") + net_note
    return launch_failed, timed_out, proc.returncode, output, drain.setup


_PROBE_CODE = "import sys; sys.stdout.write(str(6 * 7) + 'ok')"
_PROBE_MARKER = "42ok"


_ROUTED_TMP_VARS = ("TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME")
_CHECKOUT_CONFIG = "config.worktree"  # git's per-checkout config file name


class _GitFailed(Exception):
    """A git call the working-copy run depends on failed."""


def _must(root, *args, ok=(0,)):
    """Run git in ``root`` through ``_git``; the completed process when its exit code is in ``ok``, else ``_GitFailed``."""
    try:
        done = _git(root, *args)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _GitFailed("git %s: %s" % (args[0], exc))
    if done.returncode not in ok:
        raise _GitFailed("git %s failed: %s" % (" ".join(args[:2]), _tail_text(done.stderr, True).strip()))
    return done


def _text(raw):
    return raw.decode("utf-8", errors="surrogateescape")


def _head_commit(root):
    """The commit HEAD resolves to, or the empty string when it resolves to none."""
    return _text(_must(root, "rev-parse", "--verify", "-q", "HEAD^{commit}", ok=(0, 1)).stdout).strip()


def _head_symref(root):
    """The ref HEAD points at, or the empty string when HEAD is detached."""
    return _text(_must(root, "symbolic-ref", "-q", "HEAD", ok=(0, 1)).stdout).strip()


def _tracked_status(root):
    """The porcelain status of the tracked files: empty when none is modified or staged."""
    return _must(root, "status", "--porcelain=v1", "-z", "--untracked-files=no").stdout


# ``git ls-files -v`` tags for assume-unchanged (h), skip-worktree (S) and both (s).
_HIDDEN_TAGS = frozenset("hsS")


def _hidden_flags(root):
    """``{path: tag}`` for the tracked paths whose index entry carries an assume-unchanged or skip-worktree flag:
    those flags hide a working-tree edit from ``git diff`` and ``git status``."""
    raw = _text(_must(root, "ls-files", "-v", "-z").stdout)
    return {entry[2:]: entry[0] for entry in raw.split("\0") if entry[:1] in _HIDDEN_TAGS and entry[1:2] == " "}


def _hidden_edits(root, commit, flags):
    """The flagged paths whose working-tree content differs from ``commit``: the edits the flags hide. A
    skip-worktree path that is absent is not an edit; any other absent path is."""
    edited = []
    for rel, tag in sorted(flags.items()):
        path = os.path.join(root, rel)
        if os.path.islink(path):
            now = os.readlink(path).encode("utf-8", errors="surrogateescape")
        elif os.path.isfile(path):
            now = _read_bytes(path)
        else:
            if not (tag in "sS" and not os.path.lexists(path)):
                edited.append(rel)
            continue
        done = _git(root, "--literal-pathspecs", "cat-file", "blob", "%s:%s" % (commit, rel))
        if done.returncode != 0 or done.stdout != now:
            edited.append(rel)
    return edited


def _precheck(root, head):
    """``(pinned commit, None, "")`` when the working copy is exactly ``head`` with no modified or staged tracked
    file, else ``(None, reason, detail)``. Reads only; nothing is written."""
    try:
        at = _text(_must(root, "rev-parse", "--verify", "HEAD^{commit}").stdout).strip()
        want = _text(_must(root, "rev-parse", "--verify", head + "^{commit}").stdout).strip()
        # axis: a working copy that is not at the reviewed head is never run, because the test would meet another tree — see bite-proof record wo_a_2210_break_it_working_copy
        if at != want:
            return None, "working-copy-not-at-head", "HEAD is %s, the reviewed head is %s" % (at, want)
        # axis: a modified or staged tracked file is never run over, because the restore could not tell the session's work from the run's — see bite-proof record wo_a_2210_break_it_working_copy
        if _tracked_status(root):
            return None, "working-copy-dirty", "a tracked file is modified or staged"
        # axis: a flagged file (assume-unchanged, skip-worktree) whose content differs from the head is never run over, because status and diff cannot show what the restore must undo; a clean flagged file is run, its flag kept
        edited = _hidden_edits(root, at, _hidden_flags(root))
        if edited:
            return None, "working-copy-dirty", "a tracked file hidden by an assume-unchanged or skip-worktree flag is modified: %s" % edited[0]
    except _GitFailed as exc:
        return None, "working-copy-unreadable", str(exc)
    return at, None, ""


def _remove_folder(path):
    """Remove the per-run folder and everything under it; a failure leaves what it could not remove."""
    for top, dirs, files in os.walk(path, topdown=False):
        for name in files + [d for d in dirs if os.path.islink(os.path.join(top, d))]:
            try:
                os.unlink(os.path.join(top, name))
            except OSError:
                pass
        try:
            os.rmdir(top)
        except OSError:
            pass


def _read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _config_paths(root):
    """The local git config file and the per-checkout one, as absolute paths."""
    paths = []
    for name in ("config", _CHECKOUT_CONFIG):
        found = _text(_must(root, "rev-parse", "--git-path", name).stdout).rstrip("\n")
        paths.append(os.path.join(root, found))
    return paths


def _refs(root):
    out = _text(_must(root, "for-each-ref", "--format=%(refname)%00%(objectname)").stdout)
    refs = {}
    for line in out.split("\n"):
        name, sep, oid = line.partition("\0")
        if sep:
            refs[name] = oid
    return refs


def _untracked(root):
    """The non-ignored untracked files, as repo-relative paths."""
    raw = _must(root, "ls-files", "--others", "--exclude-standard", "-z").stdout
    return set(_text(name) for name in raw.split(b"\0") if name)


_UNTRACKED_BACKUP_LIMIT = 16 * 1024 * 1024


def _backup_untracked(root, names):
    """``{rel: ("link", target) | ("file", bytes, mode)}`` for the existing untracked files, so a run that
    overwrites or deletes one can put it back. Raises ``OSError`` when the files are too large to hold, or when an
    entry is neither a regular file nor a symlink (a nested repository, listed with a trailing ``/``, or a special
    file): the restore cannot put such an entry back, so the run is refused rather than left unprotected."""
    backup, total = {}, 0
    for rel in sorted(names):
        path = os.path.join(root, rel)
        if os.path.islink(path):
            backup[rel] = ("link", os.readlink(path))
        elif not os.path.isfile(path):
            # axis: an existing untracked entry that is not a file or symlink (a nested repository) refuses the run, because its content cannot be put back
            raise OSError("existing untracked entry %s is not a regular file or symlink and cannot be protected" % rel)
        else:
            total += os.path.getsize(path)
            if total > _UNTRACKED_BACKUP_LIMIT:
                raise OSError("existing untracked files exceed %d bytes and cannot be protected" % _UNTRACKED_BACKUP_LIMIT)
            with open(path, "rb") as fh:
                backup[rel] = ("file", fh.read(), os.stat(path).st_mode & 0o7777)
    return backup


def _snapshot(root, pinned):
    """What the run must leave as it found it: HEAD, every ref, the local config bytes and the untracked files
    (names and, for each existing one, its content)."""
    untracked = _untracked(root)
    return {"pinned": pinned, "symref": _head_symref(root), "refs": _refs(root), "hidden": _hidden_flags(root),
            "config": {path: _read_bytes(path) for path in _config_paths(root)},
            "untracked": untracked, "untrackedBackup": _backup_untracked(root, untracked)}


def _restore_test_file(root, ctx):
    """Remove the test file the runner wrote and each directory its write made that is now empty."""
    target = ctx["target"]
    changed = False
    if target is not None and os.path.lexists(target):
        os.unlink(target)
        changed = True
    for directory in reversed(ctx["created"]):
        try:
            os.rmdir(directory)
        except OSError:
            pass
    return changed


def _restore_refs(root, snap):
    """Put back the one ref this run can own, the branch HEAD pointed at (none when HEAD was detached). Every
    other ref that differs from the snapshot is left as it is and named in ``snap["refsLeft"]``: a second
    worktree of the repository can change refs during the run, and the restore cannot tell which process changed one."""
    own = snap["symref"]
    # axis: only the branch HEAD points at is rewound; no other ref is ever moved, deleted or created, because the restore cannot tell this run's change from another worktree's — see bite-proof record wo_a_2210_break_it_working_copy
    put_back = bool(own) and own in snap["refs"] and _refs(root).get(own) != snap["refs"][own]
    if put_back:
        _must(root, "update-ref", own, snap["refs"][own])
    now = _refs(root)
    # axis: every other ref that differs from the snapshot is listed, not hidden, so the record shows what the restore left — see bite-proof record wo_a_2210_break_it_working_copy
    snap["refsLeft"] = sorted(ref for ref in set(now) | set(snap["refs"])
                              if ref != own and now.get(ref) != snap["refs"].get(ref))
    return put_back


def _restore_head(root, snap):
    # axis: HEAD is put back on its branch, or on the pinned commit when it was detached — see bite-proof record wo_a_2210_break_it_working_copy
    if _head_symref(root) == snap["symref"] and _head_commit(root) == snap["pinned"]:
        return False
    if snap["symref"]:
        _must(root, "symbolic-ref", "HEAD", snap["symref"])
    else:
        _must(root, "update-ref", "--no-deref", "HEAD", snap["pinned"])
    return True


def _restore_config(root, snap):
    changed = False
    for path, old in snap["config"].items():
        if _read_bytes(path) == old:
            continue
        changed = True
        if old is None:
            os.unlink(path)
        else:
            with open(path, "wb") as fh:
                fh.write(old)
    return changed


def _write_back(root, commit, rel):
    """Put ``rel`` back to its content in ``commit`` by writing the blob, since ``git checkout`` skips a skip-worktree
    path. A symlink in the commit is written as a symlink."""
    entry = _text(_must(root, "--literal-pathspecs", "ls-tree", "-z", commit, "--", rel).stdout)
    mode = entry.split(" ", 1)[0]
    blob = _must(root, "--literal-pathspecs", "cat-file", "blob", "%s:%s" % (commit, rel)).stdout
    path = os.path.join(root, rel)
    if os.path.islink(path) or (os.path.lexists(path) and mode == "120000"):
        os.unlink(path)
    if mode == "120000":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pathlib.Path(path).symlink_to(blob.decode("utf-8", errors="surrogateescape"))
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(blob)
    os.chmod(path, 0o755 if mode == "100755" else 0o644)


def _restore_index(root, snap):
    changed = False
    # axis: an assume-unchanged or skip-worktree flag the run set is cleared before tracked changes are looked for, because the flag hides the edit from diff and status
    before = snap.get("hidden", {})
    flags = _hidden_flags(root)
    # a flag the owner set before the run stays; only a flag the run set is cleared
    new = sorted(rel for rel in flags if rel not in before)
    if new:
        # one flag per call: git applies only the last of the two options when both are given
        for option in ("--no-assume-unchanged", "--no-skip-worktree"):
            _must(root, "--literal-pathspecs", "update-index", option, "--", *new)
        changed = True
    # a pre-existing flagged file the run edited is put back from the pinned commit, since status cannot show it
    hidden_edits = _hidden_edits(root, snap["pinned"], {rel: tag for rel, tag in flags.items() if rel in before})
    for rel in hidden_edits:
        _write_back(root, snap["pinned"], rel)
        changed = True
    if _must(root, "diff", "--cached", "--name-only", "-z").stdout:
        _must(root, "reset", "-q")
        changed = True
    return changed


def _restore_tracked(root, snap):
    names = [name for name in _must(root, "diff", "--name-only", "-z", snap["pinned"]).stdout.split(b"\0") if name]
    if not names:
        return False
    # axis: every tracked file that differs from the pinned commit, a deleted one included, is checked out again — see bite-proof record wo_a_2210_break_it_working_copy
    _must(root, "--literal-pathspecs", "checkout", "-q", snap["pinned"], "--", *[_text(name) for name in names])
    return True


def _restore_untracked(root, snap):
    added = sorted(_untracked(root) - snap["untracked"])
    problems = []
    for rel in added:
        path = os.path.join(root, rel)
        if rel.endswith("/") or (os.path.isdir(path) and not os.path.islink(path)):
            problems.append("%s is a directory the run added" % rel)
            continue
        # axis: a non-ignored untracked file the run added is removed, and any directory that leaves empty — see bite-proof record wo_a_2210_break_it_working_copy
        try:
            os.unlink(path)
        except FileNotFoundError:
            continue
        parent = os.path.dirname(path)
        while parent.startswith(root + os.sep):
            try:
                os.rmdir(parent)
            except OSError:
                break
            parent = os.path.dirname(parent)
    changed = bool(added)
    for rel, saved in snap.get("untrackedBackup", {}).items():
        path = os.path.join(root, rel)
        try:
            if saved[0] == "link":
                if os.path.islink(path) and os.readlink(path) == saved[1]:
                    continue
            elif os.path.isfile(path) and not os.path.islink(path) and _read_bytes(path) == saved[1] \
                    and os.stat(path).st_mode & 0o7777 == saved[2]:
                continue
            # axis: an untracked file that existed before the run is written back when the run overwrote, replaced or deleted it — see bite-proof record wo_e_2210_review_round2
            if os.path.islink(path) or os.path.isfile(path):
                os.unlink(path)
            elif os.path.isdir(path):
                problems.append("%s is a directory where the run found a file" % rel)
                continue
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if saved[0] == "link":
                pathlib.Path(path).symlink_to(saved[1])
            else:
                with open(path, "wb") as fh:
                    fh.write(saved[1])
                os.chmod(path, saved[2])
            changed = True
        except OSError as exc:
            problems.append("%s: %s" % (rel, exc))
    if problems:
        raise OSError("; ".join(problems))
    return changed


def _restore(root, snap, ctx):
    """Put the working copy back as the snapshot found it, then verify. Returns ``(restored step names,
    failures)``; a step that fails does not stop the ones after it."""
    restored, failures = [], []
    steps = (("test-file", _restore_test_file, ctx), ("refs", _restore_refs, snap), ("head", _restore_head, snap),
             ("config", _restore_config, snap), ("index", _restore_index, snap),
             ("tracked", _restore_tracked, snap), ("untracked", _restore_untracked, snap))
    for name, step, state in steps:
        try:
            if step(root, state):
                restored.append(name)
        except (_GitFailed, OSError) as exc:
            restored.append(name)
            failures.append("%s: %s" % (name, str(exc)[-OUTPUT_TAIL_BYTES:]))
    try:
        if _head_commit(root) != snap["pinned"]:
            failures.append("verify: HEAD does not resolve to %s" % snap["pinned"])
        if _tracked_status(root):
            failures.append("verify: a tracked file is still modified or staged")
    except _GitFailed as exc:
        failures.append("verify: %s" % exc)
    return restored, failures


def _scratch_folder(root, scratch):
    """``(folder base, None)`` for the per-run folders, or ``(None, reason)``: ``scratch`` when given and an existing
    directory, else the ``superheroes`` folder of the working copy's git directory."""
    if scratch is not None:
        try:
            scratch = os.path.abspath(os.fspath(scratch))
        except (TypeError, ValueError):
            return None, "scratch-unresolved"
        return (scratch, None) if os.path.isdir(scratch) else (None, "scratch-unresolved")
    # imported late: break_it's import closure is pinned (test_payload_contracts_layering)
    import store_core

    def run(cwd, *args):
        return store_core.run_git_result(cwd, *args, env=_clean_env())

    try:
        gitdir = store_core.get_worktree_gitdir(root, run=run)
    except store_core.RepoRootUnavailable as exc:
        raise _GitFailed("git-dir: %s" % exc)
    return os.path.join(gitdir, "superheroes"), None


def _run_in_working_copy(repo_root, head, block, argv, env, timeout, write, interpreter=None, scratch=None):
    def rec(outcome, reason=None, exit_code=None, output="", restored=None, refs_left=None):
        return _record(head, block, outcome, reason, exit_code, output, interpreter, restored, refs_left)

    root = os.path.abspath(repo_root)
    pinned, reason, detail = _precheck(root, head)
    if reason:
        return rec(OUTCOME_NOT_RUN, reason, output=detail)
    try:
        base, reason = _scratch_folder(root, scratch)
    except _GitFailed as exc:
        return rec(OUTCOME_NOT_RUN, "working-copy-unreadable", output=str(exc))
    if reason:
        return rec(OUTCOME_NOT_RUN, reason)
    try:
        snap = _snapshot(root, pinned)
    except (_GitFailed, OSError) as exc:
        return rec(OUTCOME_NOT_RUN, "working-copy-unreadable", output=str(exc)[-OUTPUT_TAIL_BYTES:])
    tmp = os.path.join(base, "break-it-tmp-" + uuid.uuid4().hex)
    ctx = {"target": None, "created": []}
    result = None
    try:
        try:
            result = _execute(root, rec, block, argv, env, timeout, write, interpreter, tmp, ctx)
        except Exception as exc:  # the restore below still runs; the caller decides from the record
            result = rec(OUTCOME_NOT_RUN, "run-error", output=str(exc)[-OUTPUT_TAIL_BYTES:])
    finally:
        # axis: the per-run folder and every change the run made to the working copy are undone on every exit path, an exception included — see bite-proof record wo_a_2210_break_it_working_copy
        _remove_folder(tmp)
        restored, failures = _restore(root, snap, ctx)
    if failures:
        return rec(OUTCOME_NOT_RUN, "working-copy-restore-failed", output="; ".join(failures)[-OUTPUT_TAIL_BYTES:],
                   restored=restored, refs_left=snap.get("refsLeft"))
    result["restored"] = restored
    result["refsLeft"] = sorted(snap.get("refsLeft") or [])
    return result


def _execute(root, rec, block, argv, env, timeout, write, interpreter, tmp, ctx):
    """Write the block into ``root``, run the interpreter probe and the test there, and return the record."""
    try:
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        os.mkdir(tmp)
    except OSError as exc:
        return rec(OUTCOME_NOT_RUN, "scratch-unresolved", output=str(exc)[-OUTPUT_TAIL_BYTES:])
    # axis: the run's temporary and cache folders are routed into the per-run folder, so nothing the test writes through them lands elsewhere — see bite-proof record wo_a_2210_break_it_working_copy
    env = dict(env, **{name: tmp for name in _ROUTED_TMP_VARS})
    # axis: Python bytecode is read from and written to a fresh folder in the per-run folder, so a stale ignored __pycache__ in the checkout never stands in for the reviewed source — see bite-proof record wo_a_2210_break_it_working_copy
    env["PYTHONPYCACHEPREFIX"] = os.path.join(tmp, "pycache")
    # axis: a target already in the working copy with the block's own bytes is the kept test; it runs as it stands, never `path-exists`
    if write and _already_kept(root, block["path"], block.get("sha256")):
        write = False
    if write:
        target = os.path.join(root, *block["path"].split("/"))
        if not os.path.lexists(target):
            ctx["target"] = target
        try:
            refusal = _write_confined(root, block["path"], block["content"], ctx["created"])
        except OSError:
            refusal = "write-failed"
        if refusal:
            return rec(OUTCOME_NOT_RUN, refusal)
    if interpreter:
        # axis: a launcher that cannot start reads not-run, never a failed test, and the probe runs contained like the test — see bite-proof record wo_5_1910_probe_containment
        failed, timed, status, tail, _ = _run_contained(
            (interpreter if isinstance(interpreter, list) else [interpreter]) + ["-c", _PROBE_CODE],
            env, root, root, uuid.uuid4().hex, timeout)
        # axis: only a launcher that really executes Python prints the computed marker; an echo-like program exits zero without it, so it reads unavailable, never passed
        if failed or timed or status != 0 or _PROBE_MARKER not in (tail or ""):
            return rec(OUTCOME_NOT_RUN, "interpreter-unavailable", output=tail or ("timed out" if timed else ""))
    # axis: a JavaScript launcher with dependencies declared and none installed is not launched, so npx never falls back to a global or cached runner and reads passed or failed without the project's dependencies
    if (os.path.basename(argv[0]) in _JS_LAUNCHERS and _declares_dependencies(root)
            and not os.path.lexists(os.path.join(root, "node_modules"))):
        return rec(OUTCOME_NOT_RUN, REASON_MODULE_NOT_FOUND,
                   output="the working copy holds package.json with dependencies but has no installed node_modules")
    token = uuid.uuid4().hex
    launch_failed, timed_out, code, output, setup = _run_contained(argv, env, root, root, token, timeout)
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


def run_one(repo_root, head, block, *, timeout=DEFAULT_TIMEOUT, write=True, interpreter=_UNSET, scratch=None):
    """Run one parsed block from the root of the session's own working copy, ``repo_root``, at ``head``, and put the
    working copy back as it was. Always returns a record. ``scratch`` is the session folder that holds the run's
    temporary folder; left ``None``, that folder is made in the working copy's git directory.
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
    try:
        return _run_in_working_copy(repo_root, head, block, argv, env, timeout, write, substituted, scratch)
    except Exception as exc:  # the caller decides from the record; nothing is raised
        return _record(head, block, OUTCOME_NOT_RUN, "run-error", output=str(exc)[-OUTPUT_TAIL_BYTES:],
                       interpreter=substituted)


def _not_run(head, block, reason):
    return _record(head, block, OUTCOME_NOT_RUN, reason)


def _safe_run(runner, repo_root, head, block, interpreter=_UNSET, scratch=None, **kwargs):
    if interpreter is not _UNSET:
        kwargs["interpreter"] = interpreter
    if scratch is not None:
        kwargs["scratch"] = scratch
    try:
        got = runner(repo_root, head, block, **kwargs)
    except Exception:  # the caller decides from the record; nothing is raised
        return _not_run(head, block, "runner-error")
    if not isinstance(got, dict) or got.get("outcome") not in (
            OUTCOME_FAILED, OUTCOME_PASSED, OUTCOME_NOT_RUN):
        return _not_run(head, block, "runner-error")
    return got


def intercept(findings, repo_root, head, *, runner=run_one, interpreter=_UNSET, scratch=None):
    """Run every break-it finding (each run is bounded by its timeout; how many to write is the test
    role's policy, stated in its agent file) and fold the results in. Returns ``(kept, runs, exempt_ids)``:
    ``kept`` is the findings (copies) with the passed break-it ones left out and the failed or
    not-run ones stamped with ``RUN_FIELD``; ``runs`` is one entry per break-it finding;
    ``exempt_ids`` holds ``id()`` of each stamped copy. ``scratch`` is the session folder that holds each run's
    temporary folder."""
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
            record = _safe_run(runner, repo_root, head, block, interpreter, scratch)
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
_SELECT_LONG = ("--testNamePattern", "--grep", "--filter", "--match", "--test-name-pattern", "--test-skip-pattern")


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
    # axis: a renamed test's command that filters by flag, selector or old title is refused, because the filter would select nothing in the moved test — see bite-proof record wo_a_2053_break_it_body
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


_JS_CONFIG_STEMS = ("vitest.config.", "vitest.workspace.", "vite.config.", "jest.config.")


def _js_collection_overrides(repo_root, head):
    """True when the repository at ``head`` may filter JS/TS tests by name through configuration: a root
    vitest.config.*, vitest.workspace.*, vite.config.* or jest.config.* (any content: none of them is parsed), or a
    root package.json that cannot be read or parsed as a JSON object or that carries a top-level ``jest`` or
    ``vitest`` key (fail closed)."""
    import json
    tree = _git(repo_root, "ls-tree", "-z", head)
    if tree.returncode != 0:
        return True
    for entry in tree.stdout.decode("utf-8", errors="replace").split("\0"):
        if not entry:
            continue
        meta, _, name = entry.partition("\t")
        if name.lower().startswith(_JS_CONFIG_STEMS):
            return True
        if name != "package.json":
            continue
        meta = meta.split()
        if len(meta) != 3 or meta[1] != "blob":
            return True
        blob = _git(repo_root, "cat-file", "blob", meta[2])
        if blob.returncode != 0:
            return True
        try:
            manifest = json.loads(blob.stdout.decode("utf-8"))
        except Exception:
            return True
        if not isinstance(manifest, dict) or "jest" in manifest or "vitest" in manifest:
            return True
    return False


def _carries_option_token(command):
    """True when the plain argv command ``command`` carries any option token (one starting with ``-``) after its
    leading ``NAME=value`` entries, or cannot be parsed as a plain command (fail closed)."""
    argv, _, refusal = parse_command(command)
    return bool(refusal) or any(tok.startswith("-") for tok in argv)


_DIRECT_RUNNERS = frozenset(("vitest", "jest"))
_RUNNER_LAUNCHERS = frozenset(("npx", "bunx"))
_EXEC_LAUNCHERS = frozenset(("pnpm", "yarn"))


def _calls_runner_directly(command):
    """True only when the plain argv command ``command`` calls vitest or jest directly: its first program token (after
    the leading VAR=value entries) is ``vitest`` or ``jest``, or is ``npx``, ``bunx``, ``pnpm exec`` or ``yarn exec``
    immediately followed by one of them. Every package-manager script form (``pnpm test``, ``npm run test``,
    ``pnpm vitest``) and every other program is not direct; package.json is never read. An unparseable command is not
    direct (fail closed)."""
    argv, _, refusal = parse_command(command)
    if refusal or not argv:
        return False
    if argv[0] in _DIRECT_RUNNERS:
        return True
    if argv[0] in _RUNNER_LAUNCHERS:
        return argv[1:2] != [] and argv[1] in _DIRECT_RUNNERS
    if argv[0] in _EXEC_LAUNCHERS:
        return argv[1:2] == ["exec"] and argv[2:3] != [] and argv[2] in _DIRECT_RUNNERS
    return False


def _body_search(repo_root, base, head, record, today, res, runner, interpreter, scratch=None):
    """The body search behind the three rows that read the test missing or changed: ``today`` unless the test is
    found, unchanged up to formatting and its title, once among the files the final diff carries."""
    # imported late: break_it's import closure is pinned (test_payload_contracts_layering)
    from break_it_body import js_collected, locate, pytest_collected, supported_suffixes
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
        # axis: a renamed JS/TS test is accepted only when the repository at the reviewed head has no root vitest/vite/jest config file and no package.json jest or vitest key (an unreadable package.json fails closed), because a configured testNamePattern could skip the new title while another test passes; the gate is the JS front's own (``JS_COLLECTION``) — see bite-proof record wo_b_2061_break_it_body_js
        if found["titles"] and js_collected(record["path"]) and _js_collection_overrides(repo_root, head):
            return res(KEPT_UNRESOLVED, "binding-conflict")
        # axis: a renamed JS/TS test's run command may carry no option token at all (nothing starting with `-`, after the leading VAR=value pairs), because --config, -c, --root, --dir, --project or --workspace can select a configuration the root listing above never reads, which could filter the new title out; an unrenamed moved test is unaffected — see bite-proof record wo_b_2061_break_it_body_js
        if found["titles"] and js_collected(record["path"]) and _carries_option_token(record["command"]):
            return res(KEPT_UNRESOLVED, "binding-conflict")
        # axis: a moved or retitled JS/TS test is accepted only when its command calls vitest or jest directly (`vitest`, `jest`, or `npx`/`bunx`/`pnpm exec`/`yarn exec` then one of them), because a package script (`pnpm test`, `npm test`, `node --test`) can carry a name filter that skips the test while another test passes and package.json is never read; a test found at its own path runs its original command unchanged (owner ruling 109 d (a)) — see bite-proof record wo_b_2061_break_it_body_js
        if (found["titles"] or found["path"] != record["path"]) and js_collected(record["path"]) and not _calls_runner_directly(record["command"]):
            return res(KEPT_UNRESOLVED, "binding-conflict")
    except (OSError, subprocess.TimeoutExpired):
        return res(KEPT_UNRESOLVED, "git-failed")
    command, refusal = _rewrite_command(record["command"], record["path"], found["path"], found["titles"])
    if refusal:
        return res(KEPT_UNRESOLVED, refusal)
    run = _safe_run(runner, repo_root, head,
                    {"path": found["path"], "run": command, "content": "", "sha256": record["sha256"]},
                    interpreter, scratch, write=False)
    if run["outcome"] == OUTCOME_PASSED:
        return res(KEPT, "body-match", run)
    return res(KEPT_FAILING, run.get("reason"), run)


def check_kept(repo_root, base, head, record, *, runner=run_one, interpreter=_UNSET, scratch=None):
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
        return _body_search(repo_root, base, head, record, today, res, runner, interpreter, scratch)

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
                     "sha256": record["sha256"]}, interpreter, scratch, write=False)
    if run["outcome"] == OUTCOME_PASSED:
        return res(KEPT, run=run)
    return res(KEPT_FAILING, run.get("reason"), run)
