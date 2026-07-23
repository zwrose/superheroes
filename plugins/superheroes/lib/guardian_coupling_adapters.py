#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_coupling_adapters.py
"""Tool adapters for the Guardian coupling lens: dependency-cruiser argv + parsers.

Stdlib-only. This module owns the tool *boundary shape* — argv construction and output
parsing — so the parsers stay unit-testable against captured real tool output.
Normalization, eligibility, diff, and the digest live in guardian_lens_coupling.py.

**Invocation is NOT owned here.** dependency-cruiser is spawned only through
``guardian_collect.run_tool`` (→ ``guardian_tools.invoke`` in production: neutral cwd,
absolute operands in argv, env allowlist, exec-identity rejection, output caps). This
module never spawns a subprocess.

The Python side does **not** spawn import-linter while declared-vocabulary / config
reading is owner-deferred: there is nothing to run without a config, and the AST census
supplies the matrix. Identity tokens for import-linter remain for the digest / id grammar.

Two invariants the lens enforces with helpers from this module:

  1. **Non-mutating.** The collector never writes inside the swept repo.
     dependency-cruiser is invoked without its opt-in `--cache`. `cache_paths_present()`
     gives callers a cheap before/after probe so a dropped flag degrades loudly instead
     of silently mutating the repo.
  2. **Closed outcomes.** Every adapter parse returns one of OUTCOMES. There is no "other".
"""
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# --- tool identity + pins (digest metadata; NODE_PATH via guardian_tools) ------------
# dependency-cruiser 18 silently degrades to JS-only parsing when the TypeScript it
# resolves is a major it does not support (`>=2.0.0 <7.0.0`): measured on a real repo,
# TypeScript 6.0.3 → 2 modules parsed against 590 TS sources, exit 0, empty stderr.
# A plugin-controlled, supported-major TypeScript is provided to depcruise via
# guardian_tools.typescript_toolchain_node_path (outside-repo NODE_PATH); the lens's
# module-count-collapse tripwire remains the backstop when no supported TS is available.
DEPCRUISE_TOOL = "dependency-cruiser"
DEPCRUISE_BIN = "depcruise"
DEPCRUISE_PIN = "18"
TYPESCRIPT_PIN = "5"
TYPESCRIPT_SUPPORTED_MAJORS = ("5",)

# Identity tokens for the Python side digest / candidate grammar. The lens does not
# spawn import-linter while vocabulary is deferred (AST census only).
IMPORT_LINTER_TOOL = "import-linter"
IMPORT_LINTER_BIN = "lint-imports"
IMPORT_LINTER_PIN = "2"

COLLECT_TIMEOUT = 120
# Guard against a runaway report in the parser: a full graph on a large repo is tens of
# MB and is never something we keep. (Production spawn caps live in guardian_tools.)
MAX_OUTPUT_BYTES = 32 * 1024 * 1024

# Directories no collector may follow into — cost, and (fail-closed) because vendored JS
# parsing fine would otherwise mask a fully collapsed TypeScript census inside a healthy
# repo-wide total.
EXCLUDED_DIR_NAMES = (
    "node_modules", ".git", "dist", "build", "out", "coverage", ".next", ".nuxt",
    "vendor", "venv", ".venv", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    ".import_linter_cache", "site-packages", ".yarn", "target",
)
DEPCRUISE_EXCLUDE_RE = "(^|/)(%s)(/|$)" % "|".join(
    d.replace(".", r"\.") for d in EXCLUDED_DIR_NAMES)

# Cache/state paths the tools are known to create inside the analysed repo. Cheap
# (3 stat calls) before/after probe for the non-mutating invariant.
REPO_CACHE_PATHS = (
    ".import_linter_cache",
    ".dependency-cruiser-cache",
    os.path.join("node_modules", ".cache", "dependency-cruiser"),
)

# --- the closed collector-outcome table --------------------------------------------
# Every adapter return, and every lens decision built on one, routes through this table.
# The default is CLOSED: anything not listed is a degradation, never a success. "Empty
# candidates" is never allowed to mean "clean repo".
OK = "ok"
NOT_APPLICABLE = "not-applicable"
DEGRADED = "degraded"

OUTCOMES = {
    # outcome key                    class            reason (None → caller supplies detail)
    "ok": (OK, None),
    "ok-with-violations": (OK, None),
    "not-applicable": (NOT_APPLICABLE, "ecosystem not present in this repo"),
    "no-declared-vocabulary": (OK, None),
    "tool-absent": (DEGRADED, "collector tool not on PATH"),
    "spawn-failed": (DEGRADED, "collector could not be spawned"),
    "timeout": (DEGRADED, "collector timed out"),
    "nonzero-exit": (DEGRADED, "collector exited non-zero with no usable output"),
    "nonzero-exit-partial-json": (DEGRADED, "collector exited non-zero with partial JSON"),
    "malformed-json": (DEGRADED, "collector output is not valid JSON"),
    "schema-changed": (DEGRADED, "collector output does not match the expected schema"),
    "empty-output": (DEGRADED, "collector produced no output"),
    "truncated-output": (DEGRADED, "collector output exceeded the size cap"),
    "module-count-collapse": (DEGRADED, "sources on disk but ~none parsed"),
    "module-count-cliff": (DEGRADED, "module count fell off a cliff vs the prior sweep"),
    "workspace-collapse": (DEGRADED, "a workspace parsed ~nothing"),
    "typescript-pin-unverified": (DEGRADED,
                                 "TypeScript parse claimed without verified pin evidence"),
    "flat-layout": (DEGRADED, "not analyzable: flat layout, no importable packages"),
    "repo-write": (DEGRADED, "collector wrote inside the swept repo"),
    "digest-over-cap": (DEGRADED, "digest exceeded the advertised size cap"),
    "unknown": (DEGRADED, "unrecognised collector outcome"),
}


def classify(outcome):
    """Map a collector outcome to (class, default_reason). Unlisted → degraded.

    Fail-closed by construction: the caller cannot accidentally treat a new outcome
    string as success, because the default branch is a degradation.
    """
    return OUTCOMES.get(outcome, OUTCOMES["unknown"])


def is_ok(outcome):
    return classify(outcome)[0] == OK


def result(outcome, payload=None, detail=""):
    """Uniform adapter return."""
    return {"outcome": outcome, "payload": payload, "detail": detail}


def cache_paths_present(repo):
    """Which known tool cache paths currently exist inside `repo` (cheap stat probe)."""
    return [p for p in REPO_CACHE_PATHS if os.path.exists(os.path.join(repo, p))]


# --- safe repo-derived argv operands ------------------------------------------------
# Confirmed escape class: a repo directory literally named `--config` was appended as a
# positional operand; the tool parsed it as `--config` with no value and fell back to
# auto-discovering (and executing) `.dependency-cruiser.js` in cwd. Belt and braces:
# (1) `--` end-of-options before any repo-derived operand, (2) `./` prefix on relative
# paths so a leading `-` can never begin the token, (3) reject anything that still
# begins with `-` after normalization.

def safe_repo_operand(path):
    """Normalize a repo-derived path so it cannot be parsed as a CLI option.

    Absolute paths pass through (they cannot look like flags on POSIX). Relative paths
    get a `./` prefix. Anything that still begins with `-` after that is rejected —
    never passed through.
    """
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
    """Append `--` then safely-prefixed repo-derived operands. Empty → unchanged."""
    if not operands:
        return list(argv)
    safe = [safe_repo_operand(o) for o in operands]
    return list(argv) + ["--"] + safe


# --- dependency-cruiser -------------------------------------------------------------

def depcruise_argv(targets, bin_path=None):
    """argv for a JSON graph cruise. Always `--no-config`; never `--cache`.

    Repo config reading is owner-deferred (see guardian_lens_coupling). Collectors are
    pure data-gatherers: graph + census only. Targets are repo-derived and go through
    append_repo_operands so a directory named `--config` cannot reopen the escape.

    Callers MUST pass absolute repo operands (``run_tool`` / ``guardian_tools.invoke``
    run from a neutral cwd with ``targets=()``, so operands live in argv — mirror deps).
    """
    argv = [
        bin_path or DEPCRUISE_BIN,
        "--output-type", "json",
        "--no-config",
        "--ts-pre-compilation-deps",
        "--do-not-follow", DEPCRUISE_EXCLUDE_RE,
        "--exclude", DEPCRUISE_EXCLUDE_RE,
    ]
    return append_repo_operands(argv, list(targets))


def _path_inside_repo(path, repo_real):
    """True when `path` resolves to `repo_real` or a path under it."""
    if not path or not repo_real:
        return False
    try:
        real = os.path.realpath(path)
        root = os.path.realpath(repo_real)
        common = os.path.commonpath([real, root])
    except (OSError, ValueError):
        return False
    return common == root


def absolute_repo_operands(repo, targets):
    """Turn repo-relative cruise targets into absolute paths under `repo`.

    Absolute operands cannot be re-anchored by a relative child cwd. Kept behind
    `--` via append_repo_operands / safe_repo_operand (absolute paths pass through;
    the `./` relative-path prefix is unnecessary for absolutes and is not applied).
    """
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
        if not _path_inside_repo(abs_target, repo_real):
            raise ValueError(
                "cruise target %r resolves outside the swept repo %r"
                % (target, repo_real))
        out.append(abs_target)
    return out


def parse_depcruise_json(text, returncode=0):
    """Parse a dependency-cruiser JSON report → result(). Schema-validated, fail-closed.

    dependency-cruiser exits non-zero when rules are violated, so a non-zero exit with a
    schema-valid report is a *success* row; a non-zero exit with JSON that no longer
    matches the schema is the partial-output degradation row. The lens decides whether a
    non-zero exit is accepted via ``run_tool(..., ok_exits=...)`` — this parser only
    classifies the stdout body.
    """
    if text is None or not text.strip():
        return result("empty-output", detail="exit %s, no stdout" % returncode)
    if len(text) > MAX_OUTPUT_BYTES:
        return result("truncated-output", detail="%d bytes > cap %d" % (
            len(text), MAX_OUTPUT_BYTES))
    try:
        data = json.loads(text)
    except ValueError as exc:
        if returncode != 0:
            return result("nonzero-exit-partial-json",
                          detail="exit %s, JSON parse failed: %s" % (returncode, exc))
        return result("malformed-json", detail=str(exc))
    ok, why = _depcruise_schema_ok(data)
    if not ok:
        if returncode != 0:
            return result("nonzero-exit-partial-json",
                          detail="exit %s, %s" % (returncode, why))
        return result("schema-changed", detail=why)
    return result("ok-with-violations" if data["summary"].get("violations") else "ok",
                  payload=data)


def _depcruise_schema_ok(data):
    """Validate every field the lens consumes. A retyped dependencies list or a
    missing violations array must never read as a successful clean collect.
    """
    if not isinstance(data, dict):
        return False, "report is not an object"
    if not isinstance(data.get("modules"), list):
        return False, "report.modules is not a list"
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return False, "report.summary is not an object"
    if not isinstance(summary.get("environment"), dict):
        return False, "report.summary.environment is not an object"
    violations = summary.get("violations")
    if not isinstance(violations, list):
        return False, "report.summary.violations is not a list"
    for v in violations:
        if not isinstance(v, dict) or not isinstance(v.get("from"), str):
            return False, "a summary.violations entry has no string from"
        rule = v.get("rule")
        if rule is not None and not isinstance(rule, (str, dict)):
            return False, "a summary.violations entry has a non-string/non-object rule"
        if isinstance(rule, dict) and not isinstance(rule.get("name"), (str, type(None))):
            return False, "a summary.violations rule object has a non-string name"
    for mod in data["modules"]:
        if not isinstance(mod, dict) or not isinstance(mod.get("source"), str):
            return False, "a module entry has no string source"
        deps = mod.get("dependencies")
        if not isinstance(deps, list):
            return False, "a module entry has no list dependencies"
        for dep in deps:
            if not isinstance(dep, dict):
                return False, "a module dependency entry is not an object"
            target = dep.get("resolved") if dep.get("resolved") is not None else dep.get("module")
            if target is not None and not isinstance(target, str):
                return False, "a module dependency has a non-string resolved/module"
            dep_types = dep.get("dependencyTypes")
            if dep_types is not None and not isinstance(dep_types, list):
                return False, "a module dependency has a non-list dependencyTypes"
            rules = dep.get("rules")
            if rules is not None and not isinstance(rules, list):
                return False, "a module dependency has a non-list rules"
    return True, ""


def depcruise_versions(payload):
    """Resolved tool + TypeScript versions and the parse mode actually used.

    The report's own `summary.environment` is the ground truth: `transpilersFound`
    carries whether the TypeScript transpiler was *available to this run* and at which
    version. `available: false` is the collapse signature — the run silently parsed
    JavaScript only. A plugin-controlled TypeScript is supplied via the guardian_tools
    toolchain NODE_PATH seam; `pinHeld` remains informational for the digest / collapse
    reason text when the report carries it.
    """
    env = ((payload or {}).get("summary") or {}).get("environment") or {}
    tool_version = env.get("version")
    ts_version, ts_available = None, False
    for t in env.get("transpilersFound") or []:
        if isinstance(t, dict) and t.get("name") == "typescript":
            ts_available = bool(t.get("available"))
            cur = t.get("currentVersion")
            if ts_available and isinstance(cur, str) and cur not in ("", "-"):
                ts_version = cur.split("@")[-1]
            break
    return {
        "tool": DEPCRUISE_TOOL,
        "toolVersionPinned": DEPCRUISE_PIN,
        "toolVersionResolved": tool_version,
        "typescriptVersionPinned": TYPESCRIPT_PIN,
        "typescriptVersionResolved": ts_version,
        "typescriptAvailable": ts_available,
        "pinHeld": bool(ts_version) and (
            ts_version.split(".")[0] in TYPESCRIPT_SUPPORTED_MAJORS),
        "parseMode": "typescript" if ts_available else "javascript-only",
    }


def depcruise_edges(payload):
    """Concrete resolved source→target edges, node_modules/core modules dropped.

    Returns dicts of {"from", "to", "types", "rules"} — `types` is the raw
    dependencyTypes list (carries `type-only`, which the eligibility filter keys on) and
    `rules` the names of any declared rules the edge violates.
    """
    edges = []
    for mod in (payload or {}).get("modules") or []:
        src = mod.get("source")
        if not isinstance(src, str) or _is_external(src) or mod.get("coreModule"):
            continue
        for dep in mod.get("dependencies") or []:
            if not isinstance(dep, dict):
                continue
            if dep.get("couldNotResolve"):
                continue
            target = dep.get("resolved") or dep.get("module")
            if not isinstance(target, str):
                continue
            if dep.get("coreModule") or _is_external(target):
                continue
            edges.append({
                "from": src,
                "to": target,
                "types": list(dep.get("dependencyTypes") or []),
                "rules": [r.get("name") for r in (dep.get("rules") or [])
                          if isinstance(r, dict) and r.get("name")],
            })
    return edges


def depcruise_parsed_modules(payload):
    """Repo-relative paths of first-party modules the run actually parsed."""
    out = []
    for mod in (payload or {}).get("modules") or []:
        src = mod.get("source")
        if isinstance(src, str) and not mod.get("coreModule") and not _is_external(src):
            out.append(src)
    return out


def depcruise_violations(payload):
    """Declared-rule violations the tool itself reported."""
    summary = (payload or {}).get("summary") or {}
    out = []
    for v in summary.get("violations") or []:
        if isinstance(v, dict) and isinstance(v.get("from"), str):
            out.append({
                "from": v["from"],
                "to": v.get("to"),
                "rule": (v.get("rule") or {}).get("name") if isinstance(
                    v.get("rule"), dict) else v.get("rule"),
            })
    return out


_SOURCE_EXTS = (
    ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts",
    ".json", ".node",
)


def _is_external(path):
    """True for package / core-module specifiers; False for first-party file paths.

    Scoped packages (`@sentry/nextjs`) and package subpaths (`lodash/fp`) contain
    `/` but are still external — the old "bare specifier" guard missed them.
    """
    norm = path.replace("\\", "/")
    parts = [p for p in norm.split("/") if p and p != "."]
    if any(p in EXCLUDED_DIR_NAMES for p in parts):
        return True
    if norm.startswith("@"):
        return True
    if norm.startswith("./") or norm.startswith("../") or norm.startswith("/"):
        return False
    lower = norm.lower()
    if lower.endswith(".d.ts"):
        return False
    for ext in _SOURCE_EXTS:
        if lower.endswith(ext):
            return False
    # Extensionless, or a package subpath without a source suffix → external.
    return True
