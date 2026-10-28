#!/usr/bin/env python3
"""Staleness + degraded-path self-check for a review-crew project profile.

Each review skill runs this at Setup. It re-detects the live signals the way
review-init does (see review-init/SKILL.md Step 1), compares them to the
profile's provenance block, and reports *material drift* as JSON.

FAIL SOFT: this must NEVER crash the orchestrator. Any unreadable/unparseable
profile, or any internal exception, becomes a soft-fail result and exit 0. It
never raises and never returns a nonzero exit code from a real check.

CLI:
    python3 repo_doctor.py <profile-path> <plugin-version> <rubric-version> [--root <dir>]

Output (stdout, JSON):
    { "ok": true, "readable": true, "drift": [...], "unchecked": [...],
      "signal_hash": "<hex or ''>", "nudge_acked": <bool>,
      "message": "<one-line nudge or null>" }

Material drift is ANY of:
  - profile rubric-version < the engine's <rubric-version> arg;
  - profile schema < SUPPORTED_SCHEMA (this script supports schema 1);
  - >= DEP_THRESHOLD added top-level deps (set-diff of live vs profile; only
    ADDED deps count);
  - a new top-level source dir not reflected in the profile's recorded src-dirs;
  - the verify command no longer resolves (its program is absent on PATH, or for a
    word with a `/`, under root). The program is the first word in command position
    that is not a shell keyword, builtin or `VAR=value`; when no word can be read as
    one, the check lands in "unchecked" — reported in the message, never as drift;
  - the verify command names a concrete path (a test dir / script) that no
    longer exists under root — a suite that moved or was removed without the
    command being updated;
  - the profile's default-branch no longer resolves (git rev-parse --verify).
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core_md  # noqa: E402  (sibling, pure read)

# Highest profile schema this script understands. A profile with schema lower
# than this is behind and counts as material drift (the engine grew newer
# fields). Bump in lockstep with the review-init profile template `schema:`.
SUPPORTED_SCHEMA = 1

# Number of ADDED top-level deps that constitutes material drift.
DEP_THRESHOLD = 3

# Source dirs review-init probes for (Step 1: ls -d src lib app).
SRC_DIR_CANDIDATES = ("src", "lib", "app")

_INT = re.compile(r"-?\d+")


def _parse_provenance(text):
    """Parse the provenance block. Returns a dict or raises on a clearly
    non-profile file. Keys: schema, plugin, rubric-version, nudge-ack (dict),
    dep-set (list), default-branch, forge, src-dirs (list or None)."""
    if "schema:" not in text:
        raise ValueError("no provenance block")

    out = {
        "schema": None,
        "plugin": None,
        "rubric-version": None,
        "nudge-ack": {},
        "dep-set": [],
        "default-branch": None,
        "forge": None,
        "src-dirs": None,
        "verify-command": None,
    }

    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("schema:"):
            out["schema"] = _to_int(line.split(":", 1)[1])
        elif line.startswith("plugin:"):
            out["plugin"] = line.split(":", 1)[1].strip()
        elif line.startswith("rubric-version:"):
            out["rubric-version"] = _to_int(line.split(":", 1)[1])
        elif line.startswith("nudge-ack:"):
            out["nudge-ack"] = _parse_ack_map(line.split(":", 1)[1])
        elif line.startswith("dep-set:"):
            out["dep-set"] = _parse_list(line.split(":", 1)[1])
        elif line.startswith("default-branch:"):
            out["default-branch"] = line.split(":", 1)[1].strip() or None
        elif line.startswith("forge:"):
            out["forge"] = line.split(":", 1)[1].strip() or None
        elif line.startswith("src-dirs:"):
            out["src-dirs"] = _parse_list(line.split(":", 1)[1])
        elif line.startswith("command:"):
            # the ## Verify command line (first one wins)
            if out["verify-command"] is None:
                out["verify-command"] = line.split(":", 1)[1].strip() or None

    if out["schema"] is None:
        raise ValueError("provenance block missing schema")
    return out


def _to_int(s):
    m = _INT.search(s)
    return int(m.group(0)) if m else None


def _parse_list(s):
    """Parse a YAML-ish inline list `[a, b@2, c]` → ['a', 'b@2', 'c']."""
    s = s.strip()
    if s.startswith("["):
        s = s[1:]
    if s.endswith("]"):
        s = s[:-1]
    items = [tok.strip() for tok in s.split(",")]
    return [t for t in items if t]


def _parse_ack_map(s):
    """Parse the nudge-ack map. Accepts `{}` and the keys-as-strings forms the
    profile might carry (`{'<hash>': true, ...}` or `{<hash>: true}`). We only
    need the SET of acked signal-hashes, so collect every hex-ish key."""
    keys = {}
    s = s.strip()
    if not s or s == "{}":
        return {}
    inner = s
    if inner.startswith("{"):
        inner = inner[1:]
    if inner.endswith("}"):
        inner = inner[:-1]
    for pair in inner.split(","):
        if ":" not in pair:
            continue
        k = pair.split(":", 1)[0].strip().strip("'\"")
        if k:
            keys[k] = True
    return keys


def _norm_dep(name):
    """Compare deps by base name (drop any @major suffix review-init records)."""
    return name.split("@", 1)[0].strip()


def _detect_live_deps(root):
    """Live top-level dependency names, the way review-init reads them.

    Reads package.json dependencies + devDependencies (JS) only. Other ecosystems
    (pyproject.toml / Cargo.toml / go.mod) are not yet covered, so the dep-drift
    signal is JS-only in v1 (polyglot dep-sets are a v1.1 concern per the spec); the
    other five drift signals remain stack-neutral. Returns a set of base names.
    Missing/unparseable manifests → empty set (no false drift)."""
    deps = set()
    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg) as fh:
                data = json.load(fh)
            for key in ("dependencies", "devDependencies"):
                for name in (data.get(key) or {}):
                    deps.add(_norm_dep(name))
        except Exception:
            pass
    return deps


def _detect_live_src_dirs(root):
    return {d for d in SRC_DIR_CANDIDATES if os.path.isdir(os.path.join(root, d))}


# Words that open, join or close a shell construct: the next word is still in command position.
_SHELL_KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until",
                   "!", "{", "}"}
# Builtins (and `for`/`select` headers): their own words are arguments, so the whole simple
# command up to the next control operator is skipped.
# Every bash builtin (`compgen -b`, bash 5.2) except the prefixes below.
_SHELL_BUILTINS = {".", ":", "[", "alias", "bg", "bind", "break", "builtin", "caller", "cd",
                   "compgen", "complete", "compopt", "continue", "declare", "dirs", "disown",
                   "echo", "enable", "eval", "exit", "export", "false", "fc", "fg", "getopts",
                   "hash", "help", "history", "jobs", "kill", "let", "local", "logout",
                   "mapfile", "popd", "printf", "pushd", "pwd", "read", "readarray", "readonly",
                   "return", "set", "shift", "shopt", "source", "suspend", "test", "times",
                   "trap", "true", "type", "typeset", "ulimit", "umask", "unalias", "unset",
                   "wait", "for", "select"}
# Prefixes whose operand, after their options, is the program they run (`command -v` only
# queries, so it is skipped). The pairs are the options that take an argument.
_SHELL_PREFIXES = {"command", "exec", "time"}
_PREFIX_OPTION_ARGS = {("exec", "-a"), ("time", "-o"), ("time", "-f")}
# A program word that only the shell can read: an expansion, a glob, quoting or an escape.
_SHELL_ONLY = set("*?$(){}[]|<>&;`~\"'\\")
_SHELL_UNPARSED = {"case", "function", "coproc"}
# Builtins that change where a later program resolves.
_RESOLUTION_CHANGERS = {"cd", "pushd", "popd", "source", "."}
_CONTROL_OPS = {";", "&&", "||", "|", "&", "(", ")", ";;", "|&", ";&"}
_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def _verify_program(verify_command):
    """(program, unchecked, unsure) for the verify command (#2088). `program` is the first word
    in command position that names a program, skipping shell keywords, builtins with their
    arguments, and `VAR=value` prefixes. `unchecked` is a reason when no such word can be read
    (shell syntax this check does not parse, or a program only the shell can expand). `unsure`
    names what can change which word is the program or where it resolves — a quote or escape
    anywhere, or an assignment or `cd`-like builtin before it — so an unresolved program reads
    unchecked, never stale: the walk is a partial shell reader and must fail safe."""
    if not verify_command:
        return None, None, None
    unsure = None
    if any(c in verify_command for c in "\"'\\"):
        unsure = "the command quotes or escapes a word"
    try:
        # Non-POSIX mode keeps quotes on their words, so a quoted `";"` is never an operator.
        lex = shlex.shlex(verify_command, posix=False, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError as exc:
        return None, "unparseable (%s)" % exc, None
    skipping = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if tok in _CONTROL_OPS:
            skipping = False
        elif tok.startswith("#"):
            # A comment runs to the end of its line, operators in it included.
            unsure = unsure or "the command has a comment"
            if not skipping:
                return None, "a comment stands where the program should be", None
        elif skipping:
            if _ASSIGNMENT.match(tok):  # `export PATH=…`
                unsure = unsure or "an assignment comes before it"
        elif tok in _SHELL_UNPARSED:
            return None, "starts a `%s` construct" % tok, None
        elif tok in _SHELL_KEYWORDS:
            continue
        elif _ASSIGNMENT.match(tok):
            unsure = unsure or "an assignment comes before it"
        elif tok == "[[":
            # `&&`/`||` inside `[[ … ]]` are operands, not control operators.
            if "]]" not in tokens[i:]:
                return None, "an unclosed `[[`", None
            i = tokens.index("]]", i) + 1
            skipping = True
        elif tok in _SHELL_PREFIXES:
            while i < len(tokens) and tokens[i].startswith("-"):
                skipping = skipping or (tok == "command" and "v" in tokens[i].lower())
                i += 2 if (tok, tokens[i]) in _PREFIX_OPTION_ARGS else 1
        elif tok in _SHELL_BUILTINS:
            skipping = True
            if tok in _RESOLUTION_CHANGERS:
                unsure = unsure or "`%s` comes before it" % tok
        elif tok.isdigit() and i < len(tokens) and tokens[i][:1] in ("<", ">"):
            continue  # the file descriptor of `2>file`
        elif tok[0] in "<>":
            i += 1  # a redirection and its target
        elif any(c in _SHELL_ONLY for c in tok):
            return None, "program %r is read only by the shell" % tok, None
        else:
            return tok, None, unsure
    return None, "no word names a program", None


# Shell metacharacters that make a token impossible to resolve statically
# (globs, variable/command substitution, redirection). Tokens carrying any of
# these are skipped — we only flag concrete, checkable paths.
_UNRESOLVABLE = set("*?$(){}[]|<>&;`~")


def _path_word(tok):
    """The path a token names, or None. A token counts when it names a file or directory in
    the repo: it contains a `/`, is not a flag (`-q`, `--run`), and carries no shell
    metacharacter we cannot resolve statically (globs, `$vars`, subshells). Surrounding quotes
    are stripped and a trailing `/` is dropped so it can be `os.path`-checked against root."""
    t = tok.strip().strip("'\"")
    if not t or t.startswith("-") or "/" not in t or any(c in _UNRESOLVABLE for c in t):
        return None
    return t.rstrip("/") or None


# Words that open or close a construct whose body may not run (#2146); `elif`/`else` sit
# inside an `if`, so its depth covers them.
_CONDITIONAL_OPEN = {"if", "while", "until", "for", "select", "(", "{"}
_CONDITIONAL_CLOSE = {"fi", "done", ")", "}"}
_LIST_SEPARATORS = {";", "&", ";;", ";&"}


def _verify_path_args(verify_command):
    """(sure, unsure): the concrete path-like arguments in the verify command (`_path_word`).

    Used to catch a verify command that still references a test path that has since moved or
    been removed. A path is `sure` only when the command certainly runs it from the project
    root (#2146): one inside an `if`/`while`/`for` construct, a subshell or a group, in an
    and-or list (either side of `&&` or `||`), after a `cd`-like builtin, or in a comment is
    `unsure`. Shapes the walk does not model (`case`, functions, here-documents, unbalanced
    constructs, text that does not tokenize) make every path `unsure`: the walk is a partial
    shell reader, so it fails safe."""
    if not verify_command:
        return [], []
    try:
        lex = shlex.shlex(verify_command, posix=False, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        tokens = list(lex)
    except ValueError:
        return [], [p for p in map(_path_word, verify_command.split()) if p]
    if any(t in _SHELL_UNPARSED or t.startswith("<<") for t in tokens):
        return [], [p for p in map(_path_word, tokens) if p]
    # Split into lists at the separators; a list holding `&&` or `||` is an and-or list.
    lists, cur = [], []
    for tok in tokens:
        if tok in _LIST_SEPARATORS:
            lists.append(cur)
            cur = []
        else:
            cur.append(tok)
    lists.append(cur)
    sure, unsure = [], []
    depth, tainted, skip, balanced = 0, False, False, True
    for lst in lists:
        and_or = "&&" in lst or "||" in lst
        for tok in lst:
            if skip:  # a redirection's target
                skip = False
            elif tok.startswith("#"):
                tainted = True  # a comment runs to the end of its line
            elif tok in _CONDITIONAL_OPEN:
                depth += 1
            elif tok in _CONDITIONAL_CLOSE:
                depth -= 1
                balanced = balanced and depth >= 0
            elif tok in _RESOLUTION_CHANGERS:
                tainted = True
            elif tok[0] in "<>":
                skip = True
            else:
                p = _path_word(tok)
                if p:
                    (unsure if tainted or and_or or depth > 0 else sure).append(p)
    if depth or not balanced:
        return [], sure + unsure
    return sure, unsure


def _missing_verify_paths(verify_command, root):
    """(missing, unsure): the path args in the verify command that do not exist under root,
    split into those the command certainly runs and those it may not (`_verify_path_args`)."""
    sure, unsure = _verify_path_args(verify_command)
    return ([p for p in sure if not os.path.exists(os.path.join(root, p))],
            [p for p in unsure if not os.path.exists(os.path.join(root, p))])


def _binary_resolves(binary, root, env):
    """True if the binary is on PATH, or, for a word with a `/`, is an executable file at that
    path under root. Package-manager wrappers (npm/pnpm/yarn/make/python3) are treated as
    resolvable iff the wrapper itself is on PATH — we cannot cheaply resolve their
    subcommands here."""
    if not binary:
        # No verify command recorded → nothing to resolve, not a degradation.
        return True
    if "/" in binary:
        return shutil.which(os.path.join(root, binary)) is not None
    path = env.get("PATH")
    return shutil.which(binary, path=path) is not None


def _branch_resolves(root, branch, env):
    """True if `git rev-parse --verify <branch>` succeeds under root."""
    if not branch:
        return True
    try:
        r = subprocess.run(
            ["git", "-C", root, "rev-parse", "--verify", "--quiet", branch],
            capture_output=True, env=env, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        # No git / timeout: cannot confirm a failure, so do not invent drift.
        return True


def _compute_drift(prof, engine_plugin_ver, engine_rubric_ver, root, env, unchecked=None):
    """Material drift, as a list. A check that could not run appends its reason to
    `unchecked` (when given) instead of reporting drift."""
    drift = []

    # 1. rubric-version behind the engine.
    pr = prof["rubric-version"]
    if pr is not None and engine_rubric_ver is not None and pr < engine_rubric_ver:
        drift.append(
            "rubric-version advanced %d→%d" % (pr, engine_rubric_ver)
        )

    # 2. schema behind what this script supports.
    sc = prof["schema"]
    if sc is not None and sc < SUPPORTED_SCHEMA:
        drift.append(
            "schema behind: profile schema %d < supported %d"
            % (sc, SUPPORTED_SCHEMA)
        )

    # 3. >= DEP_THRESHOLD ADDED top-level deps (skip when no baseline was recorded).
    dep_set = prof.get("dep-set")
    if dep_set is not None:
        profile_deps = {_norm_dep(d) for d in dep_set}
        live_deps = _detect_live_deps(root)
        if live_deps:  # only judge when we could actually read a manifest
            added = live_deps - profile_deps
            if len(added) >= DEP_THRESHOLD:
                drift.append(
                    "%d added top-level deps since last profile" % len(added)
                )

    # 4. new top-level source dir not reflected in the recorded src-dirs.
    recorded = prof["src-dirs"]
    if recorded is not None:
        recorded_set = {d.strip() for d in recorded}
        live_src = _detect_live_src_dirs(root)
        new_dirs = sorted(live_src - recorded_set)
        if new_dirs:
            drift.append("new top-level source dir: %s" % ", ".join(new_dirs))

    # 5. verify command no longer resolves.
    binary, why, unsure = _verify_program(prof["verify-command"])
    if not why and not _binary_resolves(binary, root, env):
        if not unsure:
            drift.append("verify command no longer resolves: %s" % binary)
        else:
            why = "%s does not resolve here, but %s" % (binary, unsure)
    if why and unchecked is not None:
        unchecked.append("verify command could not be checked: %s" % why)

    # 6. verify command names a concrete path that no longer exists.
    # axis: only a path the command certainly runs from the root is missing; one it may not
    # run is a note, never drift (#2146).
    missing, unsure = _missing_verify_paths(prof["verify-command"], root)
    if missing:
        drift.append(
            "verify command references missing path(s): %s"
            % ", ".join(sorted(missing))
        )
    if unsure and unchecked is not None:
        unchecked.append(
            "verify command path(s) could not be checked: %s (a branch that may not run, "
            "or a directory change, comes before them)" % ", ".join(sorted(set(unsure)))
        )

    # 7. default-branch no longer resolves.
    branch = prof["default-branch"]
    if not _branch_resolves(root, branch, env):
        drift.append("default-branch no longer resolves: %s" % branch)

    return drift


def _hash_drift(drift):
    if not drift:
        return ""
    joined = "\n".join(sorted(drift))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _message(drift, unchecked, acked):
    """The one-line nudge: drift first, then any check that could not run. Drift the owner
    already acknowledged is left out when a note still has to be shown."""
    parts = []
    if drift and not (acked and unchecked):
        parts.append("review-crew profile drift: " + "; ".join(drift)
                     + " — consider re-running review-init")
    if unchecked:
        parts.append("review-crew profile note: " + "; ".join(unchecked))
    return " · ".join(parts) or None


def _soft_fail():
    return {
        "ok": False,
        "readable": False,
        "drift": [],
        "unchecked": [],
        "signal_hash": "",
        "nudge_acked": False,
        "message": "profile unreadable — re-run superheroes:configure",
    }


def _parse_layer_provenance(text):
    """Parse provenance fields from a unified layer's §2.2 comment."""
    out = {"nudge-ack": {}, "rubric-version": None}
    m = re.search(r"<!--\s*[\w-]+:", text or "")
    prov = ""
    if m:
        end = text.find("-->", m.start())
        if end != -1:
            prov = text[m.start():end + 3]
    if not prov:
        prov = text or ""
    m_rv = re.search(r"rubric-version=(\d+)", prov)
    if m_rv:
        out["rubric-version"] = int(m_rv.group(1))
    m_na = re.search(r"nudge-ack=(\{[^}]*\})", prov)
    if m_na:
        out["nudge-ack"] = _parse_ack_map(m_na.group(1))
    return out


def _core_verify(root):
    """(core.md verifyCommand or None, refusal message or None). The named #1331 refusal is
    reported, never swallowed into "no verify command"; any other read failure stays fail-open."""
    try:
        rec = core_md.read(root)
    except core_md.VerifyCommandMalformed as exc:
        return None, str(exc)
    except Exception:
        return None, None
    return (rec.get("verifyCommand") if rec else None) or None, None


def _doctor_unified(root, plugin_ver, rubric_ver, env, layer_text):
    """Staleness check for unified layout (core.md + layer) without legacy provenance."""
    prov = _parse_layer_provenance(layer_text)
    layer_rubric = prov.get("rubric-version")
    prof = {
        "schema": SUPPORTED_SCHEMA,
        "plugin": plugin_ver,
        "rubric-version": layer_rubric if layer_rubric is not None else rubric_ver,
        "nudge-ack": prov.get("nudge-ack") or {},
        "dep-set": None,  # unified layers carry no dep baseline — skip dep drift
        "default-branch": None,
        "forge": None,
        "src-dirs": None,
        "verify-command": None,
    }
    prof["verify-command"], refusal = _core_verify(root)
    unchecked = []
    drift = _compute_drift(prof, plugin_ver, rubric_ver, root, env, unchecked)
    signal_hash = _hash_drift(drift)
    nudge_acked = bool(signal_hash) and signal_hash in prof["nudge-ack"]
    return {
        "ok": refusal is None,
        "readable": True,
        "drift": drift,
        "unchecked": unchecked,
        "signal_hash": signal_hash,
        "nudge_acked": nudge_acked and not unchecked,
        "message": refusal or _message(drift, unchecked, nudge_acked),
    }


def _is_unified_layer(text):
    return bool(re.search(r"<!--\s*review-crew:", text or ""))


def doctor(profile_path, plugin_ver, rubric_ver, root, env):
    """Core check. Returns the result dict. Catches everything → soft-fail. The verify command
    prefers core_md.read(root).verifyCommand (a PURE read — never migrates, never writes), so the
    2am staleness probe stays read-only; else the profile's recorded command. Reading from `root`
    (the project under inspection) ensures the core.md override is scoped to the correct project,
    not the caller's working directory."""
    try:
        with open(profile_path) as fh:
            text = fh.read()
    except Exception:
        return _soft_fail()

    if _is_unified_layer(text):
        return _doctor_unified(root, plugin_ver, rubric_ver, env, text)

    if "schema:" not in text:
        return _soft_fail()

    try:
        prof = _parse_provenance(text)
    except Exception:
        return _soft_fail()

    try:
        core_verify, refusal = _core_verify(root)
        if core_verify is not None:
            prof["verify-command"] = core_verify
        unchecked = []
        drift = _compute_drift(prof, plugin_ver, rubric_ver, root, env, unchecked)
        signal_hash = _hash_drift(drift)
        nudge_acked = bool(signal_hash) and signal_hash in prof["nudge-ack"]
        return {
            "ok": refusal is None,
            "readable": True,
            "drift": drift,
            "unchecked": unchecked,
            "signal_hash": signal_hash,
            "nudge_acked": nudge_acked and not unchecked,
            "message": refusal or _message(drift, unchecked, nudge_acked),
        }
    except Exception:
        # Internal failure mid-check → degrade to a readable-but-soft result so
        # the orchestrator is never blocked.
        return {
            "ok": False,
            "readable": True,
            "drift": [],
            "unchecked": [],
            "signal_hash": "",
            "nudge_acked": False,
            "message": "profile self-check failed — proceeding without staleness data",
        }


def main(argv, env=None):
    if env is None:
        env = os.environ
    try:
        args = argv[1:]
        root = "."
        positional = []
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--root":
                root = args[i + 1] if i + 1 < len(args) else "."
                i += 2
                continue
            positional.append(a)
            i += 1

        if len(positional) < 3:
            sys.stderr.write(
                "Usage: repo_doctor.py <profile-path> <plugin-version> "
                "<rubric-version> [--root <dir>]\n"
            )
            # Usage error is the one case we report nonzero (no profile given),
            # but per spec we still must not crash the orchestrator; emit a
            # soft-fail JSON and exit 0.
            sys.stdout.write(json.dumps(_soft_fail()) + "\n")
            return 0

        profile_path, plugin_ver, rubric_raw = positional[0], positional[1], positional[2]
        rubric_ver = _to_int(rubric_raw)

        result = doctor(profile_path, plugin_ver, rubric_ver, root, env)
    except Exception:
        result = _soft_fail()

    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
