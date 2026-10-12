#!/usr/bin/env python3
"""Run a break-it test the test role wrote as text, in a throwaway copy, and check it was kept (#1800).

Stdlib only. A break-it test runs **only** inside a detached copy of the reviewed head: it never
touches the caller's tree, index or HEAD, never writes outside the copy, and its process tree never
outlives the call. Every outcome is a record — ``failed``, ``passed`` or ``not-run`` with a reason —
and the caller decides from the record; nothing is raised."""
import hashlib
import os
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

from git_routing import GIT_ROUTING_VARS  # noqa: E402
import readout  # noqa: E402  (the band's fail-closed scrub seam)

SCHEMA = "break-it-run/1"
ROLE = "test-role"
TAXONOMY = "break-it-test"
RUN_FIELD = "breakItRun"
REDACTED_FIELD = "suggestionRedacted"
DEFAULT_TIMEOUT = 300
OUTPUT_TAIL_BYTES = 8192
OUTCOME_FAILED, OUTCOME_PASSED, OUTCOME_NOT_RUN = "failed", "passed", "not-run"
KEPT, KEPT_MISSING, KEPT_CHANGED, KEPT_NOT_REGULAR, KEPT_FAILING, KEPT_UNRESOLVED = (
    "kept", "missing", "changed", "not-regular", "failing", "unresolved")

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
    "files only: one command, optionally led by `NAME=value` settings, with no pipes, redirects, "
    "`;`, `&&`, `||`, backticks or `$(`. A command that needs anything else is not run.")

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


def _record(head, block, outcome, reason=None, exit_code=None, output=""):
    block = block if isinstance(block, dict) else {}
    # axis: run output is subprocess text the test or the tested code wrote; it passes the fail-closed scrub before any record carries it
    output = readout.scrub(output)[0] if output else ""
    return {"schema": SCHEMA, "role": ROLE, "path": block.get("path"),
            "command": block.get("run"), "head": head, "sha256": block.get("sha256"),
            "outcome": outcome, "reason": reason, "exitCode": exit_code, "output": output}


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

    def run(self):
        try:
            while True:
                chunk = os.read(self.stream.fileno(), 65536)
                if not chunk:
                    return
                self.buf += chunk
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
    """Pids of processes whose environment carries ``token`` (inherited through any session)."""
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


def _run_in_copy(repo_root, d, copy, head, block, argv, env, timeout, write):
    def rec(outcome, reason=None, exit_code=None, output=""):
        return _record(head, block, outcome, reason, exit_code, output)

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
    token = uuid.uuid4().hex
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
        return rec(OUTCOME_NOT_RUN, "command-not-found")
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
    output = drain.tail()
    if launch_failed and not timed_out:
        return rec(OUTCOME_NOT_RUN, "command-not-found")
    if timed_out:
        return rec(OUTCOME_NOT_RUN, "timeout", output=output)
    code = proc.returncode
    return rec(OUTCOME_PASSED if code == 0 else OUTCOME_FAILED, exit_code=code, output=output)


def run_one(repo_root, head, block, *, timeout=DEFAULT_TIMEOUT, write=True):
    """Run one parsed block in a throwaway detached copy of ``head``. Always returns a record."""
    block = dict(block) if isinstance(block, dict) else {}
    argv, env, refusal = parse_command(block.get("run"))
    if refusal:
        return _record(head, block, OUTCOME_NOT_RUN, refusal)
    if (not isinstance(head, str) or not head or head.startswith("-")
            or not isinstance(repo_root, str) or not repo_root):
        return _record(head, block, OUTCOME_NOT_RUN, "head-unresolved")
    if write and (not isinstance(block.get("content"), str) or _path_unsafe(block.get("path"))):
        return _record(head, block, OUTCOME_NOT_RUN, "path-unsafe")
    d = tempfile.mkdtemp(prefix="break-it-")
    copy = os.path.join(d, "copy")
    try:
        result = _run_in_copy(repo_root, d, copy, head, block, argv, env, timeout, write)
    except Exception as exc:  # the caller decides from the record; nothing is raised
        result = _record(head, block, OUTCOME_NOT_RUN, "run-error", output=str(exc)[-OUTPUT_TAIL_BYTES:])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return result


def _not_run(head, block, reason):
    return _record(head, block, OUTCOME_NOT_RUN, reason)


def _safe_run(runner, repo_root, head, block, **kwargs):
    try:
        got = runner(repo_root, head, block, **kwargs)
    except Exception:  # the caller decides from the record; nothing is raised
        return _not_run(head, block, "runner-error")
    if not isinstance(got, dict) or got.get("outcome") not in (
            OUTCOME_FAILED, OUTCOME_PASSED, OUTCOME_NOT_RUN):
        return _not_run(head, block, "runner-error")
    return got


def intercept(findings, repo_root, head, *, runner=run_one):
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
            record = _safe_run(runner, repo_root, head, block)
        runs.append(dict(record, title=copy.get("title"), file=copy.get("file")))
        # axis: a passing break-it test means the change held, so the finding is dropped — see bite-proof record wo_a_1800_break-it
        if record["outcome"] == OUTCOME_PASSED:
            continue
        copy[RUN_FIELD] = record
        kept.append(copy)
        # axis: only a well-formed block on its own file at line 1 buys the scope exemption; a malformed one keeps ordinary scope checking
        if block and block["path"] == copy.get("file") and copy.get("line") == 1:
            exempt_ids.add(id(copy))
    return kept, runs, exempt_ids


def check_kept(repo_root, base, head, record, *, runner=run_one):
    """Whether the break-it test the loop ran is still in the final change, unchanged and passing.
    Returns ``{"path", "outcome", "reason", "run"}``; ``outcome`` is one of the ``KEPT*`` values."""
    record = record if isinstance(record, dict) else {}
    path = record.get("path")

    def res(outcome, reason=None, run=None):
        return {"path": path, "outcome": outcome, "reason": reason, "run": run}

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
            return res(KEPT_MISSING, "not-in-head")
        meta = entry.partition("\t")[0].split()
        if len(meta) != 3 or meta[0] not in _REGULAR_MODES or meta[1] != "blob":
            return res(KEPT_NOT_REGULAR, "not-a-regular-file")
        diff = _git(repo_root, "diff", "--name-only", base + "..." + head, "--", path)
        if diff.returncode != 0:
            return res(KEPT_UNRESOLVED, "diff-failed")
        # axis: a file the final diff does not carry is missing, even when head holds a file at that path — see bite-proof record wo_a_1800_break-it
        if not diff.stdout.strip():
            return res(KEPT_MISSING, "not-in-diff")
        blob = _git(repo_root, "cat-file", "blob", meta[2])
        if blob.returncode != 0:
            return res(KEPT_UNRESOLVED, "cat-file-failed")
    except (OSError, subprocess.TimeoutExpired):
        return res(KEPT_UNRESOLVED, "git-failed")
    # axis: the committed bytes must hash to the sha256 the loop ran, else the test was changed — see bite-proof record wo_a_1800_break-it
    if hashlib.sha256(blob.stdout).hexdigest() != record["sha256"]:
        return res(KEPT_CHANGED, "sha256-differs")
    run = _safe_run(runner, repo_root, head,
                    {"path": path, "run": record["command"], "content": "",
                     "sha256": record["sha256"]}, write=False)
    if run["outcome"] == OUTCOME_PASSED:
        return res(KEPT, run=run)
    return res(KEPT_FAILING, run.get("reason"), run)
