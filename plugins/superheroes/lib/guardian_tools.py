#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_tools.py
"""Mandatory external-tool invocation seam for all Guardian lenses.

Stdlib-only and strictly read-only at sweep time: resolves what is ALREADY present,
invokes collectors through a hardened subprocess boundary, and degrades with messages
only — it acquires nothing.

Guarantees by construction:
  1. Neutral child cwd (never the swept repo).
  2. Absolute repo operands (repo-relative targets absolutized behind ``--``).
  3. Identity-based executable rejection (``os.path.samefile``, never string containment).
  4. Environment allowlist (code-loading vars stripped; PATH/NODE_PATH sanitized).
  5. No fetch at sweep time (degrade messages only — see ``missing_tool_reason``).
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# AUTHORITATIVE home for collector install guidance (§11: one home per cross-boundary
# fact). Every degrade message quotes this map; no other module restates a command.
#
# Keys are the ACTUAL argv[0] executable the lens resolves through PATH (never a
# conceptual label): the deps lens invokes `npm audit` (bin `npm`) and the ncu freshness
# tool by its explicit bin `npm-check-updates` (the `ncu` alias also ships, but the argv
# names `npm-check-updates`); the deadcode lens invokes `knip` (JS) and `vulture` (Python);
# `pip-audit` is the Python dependency-audit bin. npm ships with Node, so its guidance
# points at the Node install rather than a package-manager verb.
INSTALL_COMMANDS = {
    "jscpd": "npm install -g jscpd",
    "radon": "pip install radon",
    "lizard": "pip install lizard",
    "npm": "install Node.js, which bundles npm",
    "npm-check-updates": "npm install -g npm-check-updates",
    "knip": "npm install -g knip",
    "vulture": "pip install vulture",
    "pip-audit": "pip install pip-audit",
    "osv-scanner": (
        "brew install osv-scanner "
        "(or: go install github.com/google/osv-scanner/v2/cmd/osv-scanner@latest)"
    ),
}

# argv tail used to ask a resolved collector for its version.
VERSION_ARGS = {
    "jscpd": ("--version",),
    "radon": ("--version",),
    "lizard": ("--version",),
    "npm": ("--version",),
    "npm-check-updates": ("--version",),
    "knip": ("--version",),
    "vulture": ("--version",),
    "pip-audit": ("--version",),
    "osv-scanner": ("--version",),
}

VERSION_TIMEOUT = 10
COLLECT_TIMEOUT = 120
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
NODE_PATH_ENV = "NODE_PATH"

_VERSION_RE = re.compile(r"\d+(?:\.\d+)+[0-9A-Za-z.\-+]*")

# Rejection reason when which() lands on a repo-controlled or relative-PATH binary.
REJECTION_REPO_LOCAL = "repo-local executable ignored"

# Absolute PATH fallback when every inherited component was empty, relative, or
# repo-contained. Must never be "" — CPython treats an empty PATH as "search the
# child cwd", and that is only safe today because the child cwd is neutral.
_DEFAULT_SAFE_PATH_PARTS = ("/usr/bin", "/bin")

COLLECTOR_ENV_ALLOWPASS = frozenset({
    "PATH",
    "HOME", "USER", "LOGNAME", "USERNAME",
    "LANG", "LANGUAGE",
    "LC_ALL", "LC_CTYPE", "LC_MESSAGES", "LC_NUMERIC", "LC_TIME",
    "TZ",
    "TMPDIR", "TMP", "TEMP",
    "TERM", "COLORTERM",
    "SSL_CERT_FILE", "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "no_proxy",
    "SYSTEMROOT", "COMSPEC", "PATHEXT",
})

COLLECTOR_ENV_CODE_LOADING = frozenset({
    "NODE_OPTIONS",
    "NODE_REPL_EXTERNAL_MODULE",
    NODE_PATH_ENV,
    "PYTHONSTARTUP",
    "PYTHONPATH",
    "PYTHONHOME",
    "PERL5LIB",
    "RUBYLIB",
    "RUBYOPT",
    "BUN_OPTIONS",
})

_NEUTRAL_COLLECTOR_CWD = None
_NEUTRAL_COLLECTOR_CWD_LOCK = threading.Lock()

_NEUTRAL_TOOL_CONFIGS = {}
_NEUTRAL_TOOL_CONFIG_LOCK = threading.Lock()


def _git_toplevel(cwd):
    """Walk parents for a .git dir/file; fall back to realpath(cwd). Never spawns."""
    cur = os.path.realpath(cwd or ".")
    while True:
        git_entry = os.path.join(cur, ".git")
        if os.path.isdir(git_entry) or os.path.isfile(git_entry):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.realpath(cwd or ".")
        cur = parent


def _is_under(path, root):
    """True when path is root or a descendant of root (filesystem identity).

    Walks ancestors of the resolved path and compares each to root with
    os.path.samefile (st_dev/st_ino) — immune to casing, symlinks, and
    normalization differences that break lexical realpath containment.
    OSError from samefile (vanished/unreadable) fails closed: treat as under.
    """
    try:
        cur = os.path.realpath(path)
        root_real = os.path.realpath(root)
    except OSError:
        return True

    while True:
        try:
            if os.path.samefile(cur, root_real):
                return True
        except OSError:
            return True
        parent = os.path.dirname(cur)
        if parent == cur:
            return False
        cur = parent


def _is_confidently_under(path, root):
    """True only on a definite positive samefile match during the ancestor walk.

    Unlike ``_realpath_is_under`` / ``_is_under``, OSError and no-match both
    return False — operands must fail closed toward rejection.  Nonexistent
    leaves still resolve via the nearest existing ancestor (same as PATH logic).
    """
    try:
        root_real = os.path.realpath(root)
    except OSError:
        return False

    cur = path
    if not os.path.isabs(cur):
        try:
            cur = os.path.abspath(cur)
        except OSError:
            return False

    probe = cur
    while not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent

    walk = probe
    if os.path.exists(walk):
        try:
            walk = os.path.realpath(walk)
        except OSError:
            return False

    while True:
        try:
            if os.path.samefile(walk, root_real):
                return True
        except OSError:
            return False
        parent = os.path.dirname(walk)
        if parent == walk:
            return False
        if os.path.exists(parent):
            try:
                walk = os.path.realpath(parent)
            except OSError:
                return False
        else:
            walk = parent


def _realpath_is_under(path, root):
    """Identity containment for env/operand paths that may not exist on disk.

    Resolves the nearest existing ancestor, then samefile-walks from there up to
    ``/``. A nonexistent leaf outside the repo (e.g. ``/abs/toolchain``) must not
    fail closed — only a genuinely unreadable/vanished ancestor does.
    """
    try:
        root_real = os.path.realpath(root)
    except OSError:
        return True

    cur = path
    if not os.path.isabs(cur):
        try:
            cur = os.path.abspath(cur)
        except OSError:
            return True

    probe = cur
    while not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent

    walk = probe
    if os.path.exists(walk):
        try:
            walk = os.path.realpath(walk)
        except OSError:
            return True

    while True:
        try:
            if os.path.samefile(walk, root_real):
                return True
        except OSError:
            return True
        parent = os.path.dirname(walk)
        if parent == walk:
            return False
        if os.path.exists(parent):
            try:
                walk = os.path.realpath(parent)
            except OSError:
                return True
        else:
            walk = parent


def _path_entry_is_relative(entry):
    """Empty, '.', or any non-absolute PATH entry — cwd-relative, not machine PATH."""
    if entry == "" or entry == ".":
        return True
    return not os.path.isabs(entry)


def _resolved_via_relative_path_entry(tool, resolved_real, cwd):
    """True when which()'s result matches a relative/empty/'.' PATH entry expansion."""
    path_env = os.environ.get("PATH", "")
    for entry in path_env.split(os.pathsep):
        if not _path_entry_is_relative(entry):
            continue
        if entry in ("", "."):
            base = cwd
        else:
            base = entry if os.path.isabs(entry) else os.path.join(cwd, entry)
        candidate = os.path.join(base, tool)
        if os.path.realpath(candidate) == resolved_real:
            return True
    return False


def resolve(tool, cwd, run=None):
    """How (or whether) `tool` can be invoked here — never spawns a process.

    Resolution starts with PATH (shutil.which), then REJECTS any hit that:
      - is not absolute after normalizing against the PROCESS cwd, or
      - realpath-resolves inside the scanned repo (git toplevel when present), or
      - was reached via a relative / empty / "." PATH entry (resolved vs process cwd).
  """
    del run  # resolution never executes anything
    repo_root = _git_toplevel(cwd)
    process_cwd = os.path.realpath(os.getcwd())
    on_path = shutil.which(tool)
    if not on_path:
        return {"tool": tool, "found": False, "path": None, "source": None}

    if os.path.isabs(on_path):
        abs_hit = on_path
    else:
        abs_hit = os.path.join(process_cwd, on_path)
    abs_hit = os.path.abspath(abs_hit)
    if not os.path.isabs(abs_hit):
        return {
            "tool": tool,
            "found": False,
            "path": None,
            "source": None,
            "rejection": REJECTION_REPO_LOCAL,
        }
    resolved = os.path.realpath(abs_hit)
    if not os.path.isabs(resolved):
        return {
            "tool": tool,
            "found": False,
            "path": None,
            "source": None,
            "rejection": REJECTION_REPO_LOCAL,
        }
    if _is_under(resolved, repo_root):
        return {
            "tool": tool,
            "found": False,
            "path": None,
            "source": None,
            "rejection": REJECTION_REPO_LOCAL,
        }
    if _resolved_via_relative_path_entry(tool, resolved, process_cwd):
        return {
            "tool": tool,
            "found": False,
            "path": None,
            "source": None,
            "rejection": REJECTION_REPO_LOCAL,
        }
    return {"tool": tool, "found": True, "path": resolved, "source": "path"}


def _parse_version(text):
    if not isinstance(text, str):
        return None
    m = _VERSION_RE.search(text)
    if m:
        return m.group(0)
    return None


def version(tool, cwd, run=None):
    """The resolved collector's reported version string, or None.

    Best-effort: an unresolved tool, a non-zero exit, a timeout, or unparseable output
    all yield None. Spawns from neutral cwd with sanitized env. `run` is injectable.
    """
    res = resolve(tool, cwd)
    if not res["found"]:
        return None
    runner = run or subprocess.run
    repo_real = os.path.realpath(cwd)
    child_cwd = neutral_collector_cwd(repo_real)
    child_env = sanitized_env(repo=repo_real)
    argv = [res["path"]] + list(VERSION_ARGS.get(tool, ("--version",)))
    try:
        proc = runner(
            argv, capture_output=True, text=True, cwd=child_cwd,
            timeout=VERSION_TIMEOUT, env=child_env)
    except Exception:
        return None
    if getattr(proc, "returncode", 1) != 0:
        return None
    return _parse_version(getattr(proc, "stdout", "") or "") or _parse_version(
        getattr(proc, "stderr", "") or "")


# *** BINDING OWNER CONSTRAINT ***
# The degrade message is a MESSAGE ONLY. Never auto-install, never fetch at sweep time
# (no `npx --yes`, no pip install), never add a configure knob, never retry after an
# install. Tool adoption is an owner act on a doctor-style recommendation
# (LEDGERS section 2 / the ratified #41 graduation path; owner-confirmed 2026-07-21).
def missing_tool_reason(tool, rejection=None):
    """The degrade reason for an absent (or rejected) collector — names the install
    command, runs none. When `rejection` is set, the reason names WHY it was refused.
    """
    cmd = INSTALL_COMMANDS.get(tool)
    if rejection:
        if not cmd:
            return (
                "%s ignored (%s) — no install command is recorded for it in "
                "guardian_tools.INSTALL_COMMANDS" % (tool, rejection)
            )
        return (
            "%s ignored (%s) — install it with `%s` to enable this lens"
            % (tool, rejection, cmd)
        )
    if not cmd:
        return ("%s not found on PATH — no install command is recorded for it in "
                "guardian_tools.INSTALL_COMMANDS" % tool)
    return "%s not found on PATH — install it with `%s` to enable this lens" % (tool, cmd)


def _default_safe_path():
    parts = [p for p in _DEFAULT_SAFE_PATH_PARTS if os.path.isdir(p)]
    if not parts:
        parts = list(_DEFAULT_SAFE_PATH_PARTS)
    return os.pathsep.join(parts)


def _sanitize_path_lookup(value, repo=None):
    """Drop empty, relative, and swept-repo PATH components — never absolutize."""
    cleaned = []
    repo_real = os.path.realpath(repo) if repo else None
    for part in value.split(os.pathsep):
        if part == "":
            continue
        if not os.path.isabs(part):
            continue
        if repo_real and _realpath_is_under(part, repo_real):
            continue
        cleaned.append(part)
    if not cleaned:
        return _default_safe_path()
    return os.pathsep.join(cleaned)


def _node_path_entries_outside_repo(value, repo=None):
    """Keep absolute NODE_PATH entries outside the swept repo."""
    repo_real = os.path.realpath(repo) if repo else None
    kept = []
    for part in value.split(os.pathsep):
        if not part or not os.path.isabs(part):
            continue
        if repo_real and _realpath_is_under(part, repo_real):
            continue
        kept.append(part)
    return os.pathsep.join(kept)


def sanitized_env(base_env=None, repo=None, extra_node_path=None):
    """Build the collector subprocess env — the single inheritance boundary."""
    source = base_env if base_env is not None else os.environ
    repo_real = os.path.realpath(repo) if repo else None
    env = {}
    for key in COLLECTOR_ENV_ALLOWPASS:
        if key in source and source[key] is not None:
            env[key] = source[key]
    for key in COLLECTOR_ENV_CODE_LOADING:
        if key != NODE_PATH_ENV:
            env.pop(key, None)

    if "PATH" in env and env["PATH"] is not None:
        env["PATH"] = _sanitize_path_lookup(env["PATH"], repo=repo_real)

    prior_raw = source.get(NODE_PATH_ENV) if NODE_PATH_ENV in source else None
    if prior_raw:
        cleaned_prior = _node_path_entries_outside_repo(prior_raw, repo=repo_real)
        if cleaned_prior:
            env[NODE_PATH_ENV] = cleaned_prior

    if extra_node_path:
        if not os.path.isabs(extra_node_path):
            raise ValueError(
                "extra_node_path must be absolute, got %r" % (extra_node_path,))
        if repo_real and _realpath_is_under(extra_node_path, repo_real):
            raise ValueError(
                "extra_node_path must not resolve inside the swept repo, got %r"
                % (extra_node_path,))
        prior = env.get(NODE_PATH_ENV)
        env[NODE_PATH_ENV] = (
            extra_node_path + os.pathsep + prior if prior else extra_node_path)
    return env


def safe_repo_operand(path):
    """Normalize a repo-derived path so it cannot be parsed as a CLI option."""
    if not isinstance(path, str) or path == "":
        raise ValueError("repo operand must be a non-empty str, got %r" % (path,))
    if os.path.isabs(path):
        if path.startswith("-"):
            raise ValueError(
                "repo operand must not begin with '-' after normalization: %r" % path)
        return path
    if path.startswith("./") or path.startswith("../"):
        normalized = path
    elif path == ".":
        normalized = "./"
    else:
        normalized = "./" + path
    if normalized.startswith("-"):
        raise ValueError(
            "repo operand must not begin with '-' after normalization: %r" % path)
    return normalized


def append_repo_operands(argv, operands):
    """Append ``--`` then safely-prefixed repo-derived operands. Empty → unchanged."""
    if not operands:
        return list(argv)
    safe = [safe_repo_operand(o) for o in operands]
    return list(argv) + ["--"] + safe


def absolute_repo_operands(repo, targets):
    """Turn repo-relative targets into absolute paths under `repo`."""
    if not repo or not os.path.isabs(repo):
        raise ValueError("repo must be an absolute path, got %r" % (repo,))
    repo_real = os.path.realpath(repo)
    out = []
    for target in targets:
        if not isinstance(target, str) or target == "":
            raise ValueError("repo operand must be a non-empty str, got %r" % (target,))
        if os.path.isabs(target):
            abs_target = os.path.realpath(target)
        else:
            abs_target = os.path.realpath(os.path.join(repo_real, target))
        if not _is_confidently_under(abs_target, repo_real):
            raise ValueError(
                "cruise target %r resolves outside the swept repo %r"
                % (target, repo_real))
        out.append(abs_target)
    return out


def neutral_collector_cwd(repo):
    """A process-lifetime scratch directory that is not the swept repo."""
    global _NEUTRAL_COLLECTOR_CWD
    repo_real = os.path.realpath(repo)
    tmp_base = tempfile.gettempdir()
    if _realpath_is_under(tmp_base, repo_real):
        raise RuntimeError(
            "temp base %r resolves inside the swept repo %r — cannot create a "
            "neutral collector cwd" % (tmp_base, repo_real))
    with _NEUTRAL_COLLECTOR_CWD_LOCK:
        if _NEUTRAL_COLLECTOR_CWD is None or not os.path.isdir(_NEUTRAL_COLLECTOR_CWD):
            _NEUTRAL_COLLECTOR_CWD = tempfile.mkdtemp(
                prefix="superheroes-guardian-collector-")
        result = _NEUTRAL_COLLECTOR_CWD
    if _realpath_is_under(result, repo_real):
        raise RuntimeError(
            "neutral collector cwd %r resolves inside the swept repo %r"
            % (result, repo_real))
    return result


def _sanitize_tool_config_name(name):
    """Reduce a tool label to a single safe filename component."""
    if not isinstance(name, str) or name == "":
        raise ValueError("tool config name must be a non-empty str, got %r" % (name,))
    if "\0" in name:
        raise ValueError("tool config name must not contain null bytes, got %r" % (name,))
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    if safe in ("", ".", ".."):
        safe = "_"
    return safe


def neutral_tool_config(repo, name):
    """Absolute path to an empty, process-lifetime config file that is NOT in the swept repo."""
    global _NEUTRAL_TOOL_CONFIGS
    repo_real = os.path.realpath(repo)
    tmp_base = tempfile.gettempdir()
    if _realpath_is_under(tmp_base, repo_real):
        raise RuntimeError(
            "temp base %r resolves inside the swept repo %r — cannot create a "
            "neutral tool config" % (tmp_base, repo_real))
    safe_name = _sanitize_tool_config_name(name)
    with _NEUTRAL_TOOL_CONFIG_LOCK:
        path = _NEUTRAL_TOOL_CONFIGS.get(safe_name)
        if path is None:
            fd, path = tempfile.mkstemp(
                prefix="superheroes-guardian-tool-config-%s-" % safe_name,
                suffix=".toml",
                dir=tmp_base)
            os.close(fd)
            _NEUTRAL_TOOL_CONFIGS[safe_name] = path
        elif not os.path.isfile(path):
            with open(path, "wb"):
                pass
        result = _NEUTRAL_TOOL_CONFIGS[safe_name]
    if _realpath_is_under(result, repo_real):
        raise RuntimeError(
            "neutral tool config %r resolves inside the swept repo %r"
            % (result, repo_real))
    return result


def _read_pipe_bounded(pipe, limit):
    if pipe is None:
        return "", False
    chunks = []
    total = 0
    while True:
        to_read = min(65536, max(limit - total + 1, 1))
        chunk = pipe.read(to_read)
        if not chunk:
            return "".join(chunks), False
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            return "".join(chunks), True


def _drain_pipe_discard(pipe):
    if pipe is None:
        return
    try:
        while True:
            chunk = pipe.read(65536)
            if not chunk:
                return
    except (OSError, ValueError):
        return


def _result_dict(outcome, tool, argv, cwd, returncode=None, stdout="", stderr="",
                 truncated=False, reason=None, parsed=None):
    out = {
        "outcome": outcome,
        "tool": tool,
        "argv": list(argv) if argv is not None else None,
        "cwd": cwd,
        "returncode": returncode,
        "stdout": stdout or "",
        "stderr": stderr or "",
        "truncated": truncated,
    }
    if reason is not None:
        out["reason"] = reason
    if parsed is not None:
        out["parsed"] = parsed
    return out


def _route_captured(tool, argv, cwd, stdout, stderr, rc, parse):
    stdout = stdout or ""
    stderr = stderr or ""
    if len(stdout) > MAX_OUTPUT_BYTES:
        return _result_dict(
            "truncated-output", tool, argv, cwd, returncode=rc,
            stdout=stdout, stderr=stderr, truncated=True)
    if not stdout.strip():
        if rc != 0:
            return _result_dict(
                "nonzero-exit", tool, argv, cwd, returncode=rc,
                stdout=stdout, stderr=stderr)
        return _result_dict(
            "empty-output", tool, argv, cwd, returncode=rc,
            stdout=stdout, stderr=stderr)
    outcome = "ok" if rc == 0 else "nonzero-exit"
    parsed = None
    if parse is not None:
        parsed = parse(stdout, returncode=rc)
    return _result_dict(
        outcome, tool, argv, cwd, returncode=rc,
        stdout=stdout, stderr=stderr, parsed=parsed)


def _kill_process_tree(proc, child_pgid):
    """Kill the collector and any descendants (e.g. node worker fan-out)."""
    if child_pgid is not None:
        try:
            os.killpg(child_pgid, signal.SIGKILL)
        except (OSError, AttributeError, ProcessLookupError):
            try:
                proc.kill()
            except OSError:
                pass
    else:
        try:
            proc.kill()
        except OSError:
            pass


def _invoke_subprocess_bounded(tool, argv, cwd, timeout, env, parse):
    popen_kwargs = {
        "cwd": cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "env": env,
    }
    child_pgid = None
    try:
        popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(argv, **popen_kwargs)
        child_pgid = proc.pid
    except TypeError:
        popen_kwargs.pop("start_new_session", None)
        try:
            proc = subprocess.Popen(argv, **popen_kwargs)
        except FileNotFoundError:
            return _result_dict(
                "spawn-failed", tool, argv, cwd,
                reason="executable not found: %s" % (argv[0] if argv else tool))
        except OSError as exc:
            return _result_dict(
                "spawn-failed", tool, argv, cwd,
                reason="%s: %s" % (argv[0] if argv else tool, exc))
    except FileNotFoundError:
        return _result_dict(
            "spawn-failed", tool, argv, cwd,
            reason="executable not found: %s" % (argv[0] if argv else tool))
    except OSError as exc:
        return _result_dict(
            "spawn-failed", tool, argv, cwd,
            reason="%s: %s" % (argv[0] if argv else tool, exc))

    stdout_box = [""]
    stderr_box = [""]
    truncated = [False]

    def _drain_stdout():
        text, trunc = _read_pipe_bounded(proc.stdout, MAX_OUTPUT_BYTES)
        stdout_box[0] = text
        if trunc:
            truncated[0] = True
            _kill_process_tree(proc, child_pgid)
            _drain_pipe_discard(proc.stdout)

    def _drain_stderr():
        text, trunc = _read_pipe_bounded(proc.stderr, 64 * 1024)
        stderr_box[0] = text
        if trunc:
            _drain_pipe_discard(proc.stderr)

    readers = [
        threading.Thread(target=_drain_stdout),
        threading.Thread(target=_drain_stderr),
    ]
    for t in readers:
        t.daemon = True
        t.start()
    outcome = None
    try:
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc, child_pgid)
            outcome = _result_dict(
                "timeout", tool, argv, cwd,
                reason="%s after %ss" % (argv[0], timeout))
        except (OSError, subprocess.SubprocessError) as exc:
            _kill_process_tree(proc, child_pgid)
            outcome = _result_dict(
                "spawn-failed", tool, argv, cwd,
                reason="%s: %s" % (argv[0], exc))
        else:
            for t in readers:
                t.join(timeout=5)
            if any(t.is_alive() for t in readers):
                _kill_process_tree(proc, child_pgid)
                for t in readers:
                    t.join(timeout=5)
            if any(t.is_alive() for t in readers):
                outcome = _result_dict(
                    "capture-incomplete", tool, argv, cwd,
                    returncode=proc.returncode,
                    reason="collector output not fully drained within bound "
                           "(a surviving descendant may hold the pipe)")
            elif truncated[0]:
                outcome = _result_dict(
                    "truncated-output", tool, argv, cwd,
                    returncode=proc.returncode, stdout=stdout_box[0],
                    stderr=stderr_box[0], truncated=True)
            else:
                rc = proc.returncode if proc.returncode is not None else 0
                outcome = _route_captured(
                    tool, argv, cwd, stdout_box[0], stderr_box[0], rc, parse)
    finally:
        for t in readers:
            t.join(timeout=5)
        for pipe in (proc.stdout, proc.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    pass
    return outcome


def _invoke(run, tool, argv, cwd, timeout, env, parse):
    run = run or subprocess.run
    if run is subprocess.run:
        return _invoke_subprocess_bounded(tool, argv, cwd, timeout, env, parse)
    try:
        r = run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
    except FileNotFoundError:
        return _result_dict(
            "spawn-failed", tool, argv, cwd,
            reason="executable not found: %s" % (argv[0] if argv else tool))
    except subprocess.TimeoutExpired:
        return _result_dict(
            "timeout", tool, argv, cwd,
            reason="%s after %ss" % (argv[0], timeout))
    except (OSError, subprocess.SubprocessError) as exc:
        return _result_dict(
            "spawn-failed", tool, argv, cwd,
            reason="%s: %s" % (argv[0], exc))
    return _route_captured(
        tool, argv, cwd,
        getattr(r, "stdout", "") or "",
        getattr(r, "stderr", "") or "",
        getattr(r, "returncode", 0),
        parse,
    )


def invoke(tool, fixed_args, repo, targets, *, run=None, cwd=None,
           timeout=COLLECT_TIMEOUT, env=None, parse=None, extra_node_path=None):
    """The single external-tool invocation seam for Guardian lenses."""
    if not repo or not os.path.isabs(repo):
        raise ValueError("repo must be an absolute path, got %r" % (repo,))
    repo_abs = os.path.realpath(repo)

    res = resolve(tool, repo)
    if not res["found"]:
        return _result_dict(
            "tool-absent", tool, None, None,
            reason=missing_tool_reason(tool, res.get("rejection")))
    if _is_under(res["path"], repo_abs):
        return _result_dict(
            "tool-absent", tool, None, None,
            reason=missing_tool_reason(tool, REJECTION_REPO_LOCAL))

    argv = append_repo_operands(
        [res["path"]] + list(fixed_args),
        absolute_repo_operands(repo_abs, list(targets)))

    child_cwd = cwd or neutral_collector_cwd(repo_abs)
    if _realpath_is_under(child_cwd, repo_abs):
        raise ValueError(
            "collector cwd must not be inside the swept repo, got %r" % (child_cwd,))

    child_env = sanitized_env(env, repo=repo_abs, extra_node_path=extra_node_path)
    return _invoke(run, tool, argv, child_cwd, timeout, child_env, parse)
