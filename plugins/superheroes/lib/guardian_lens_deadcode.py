#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_lens_deadcode.py
"""Guardian dead-code lens — vulture (python) + knip (node): the noisiest lens by design.

Stdlib-only. This lens ships because the machinery around it — drift-over-baseline,
the model validation pass, the dispositions ledger, the report card — is built for
exactly this: a static reachability guess that is right most of the time and wrong
often enough that a naive report would burn advisor triage tokens (ratified #41
proposal §3.6). Two properties matter more than coverage:

  1. HONEST NON-COLLECTION. `knip` only means anything with the project's dependencies
     installed; `vulture` may not be installed at all. When a collector cannot run, this
     lens says `not-collected`/`partial` WITH THE REASON — never an empty candidate
     list, which the report would render as "no dead code" when the truth is "nobody
     looked". A `not-collected` ecosystem contributes nothing to `diff()`'s `resolved`,
     which would otherwise make an uninstalled tool look like somebody deleted the code.

  2. VALIDATION IS WHAT MAKES THIS USABLE. Most vulture hits on this repo are mock/stub
     signatures and pytest fixtures the project's own conventions sanction on purpose —
     `validation_guidance` is the kill list that keeps those out of a filed issue.

Ecosystem detection: python is present when a root manifest (`pyproject.toml` /
`requirements.txt`) exists OR when `.py` files exist outside vendor/build directories
(`node_modules`, `.venv`, `venv`, `dist`, `build`, `__pycache__`, `.git`) — vulture needs
no manifest, only source files. Node still requires `package.json` (knip needs the
manifest *and* an installed `node_modules`). A repo with neither `.py` files nor a node
manifest folds to `not-collected` rather than a silent "collected, zero findings".

Collector notes, grounded in real command-line runs (2026-07-21, not estimated):

  python — `vulture`, resolved from PATH through the guardian seam (the base seam rejects
  repo-local executables, so the venv-bin / project-interpreter ladder cannot resolve
  through it and is gone; an absent vulture degrades to not-collected quoting the install
  command). The single source operand is the ABSOLUTE repo root, never `"."` — a `"."`
  would resolve against the seam's neutral cwd and false-clean. `--min-confidence 60` is
  used EXPLICITLY: it is vulture's own default
  (confirmed empirically — an unflagged run and `--min-confidence 60` produced
  byte-identical output on this repo), made explicit so the threshold is visible in the
  invocation rather than an implicit default that could drift across vulture versions.
  Exit codes are vulture's own (`vulture.utils.ExitCode`): 0 = no dead code, 3 = dead
  code found — BOTH are a successful run; 1 (invalid input) and 2 (bad cmdline) are not.
  A full-repo scan of this repo (excluding `node_modules,.venv,venv,dist,build,
  __pycache__,.git`) measured ~0.78s wall and reported 37 raw hits aggregating to 30
  unique candidates, confirming the design's known seed
  (`plugins/superheroes/lib/repo_doctor.py:243`, `_compute_drift`'s unused
  `engine_plugin_ver` parameter, at 100% confidence) and also surfacing a REAL duplicate-
  id case in the wild: a pytest fixture parameter named `clean_registry`
  (`plugins/superheroes/lib/tests/test_guardian_lens.py`) is declared, unused in the
  test body, in 8 different test functions — one candidate id, aggregated, count 8,
  every line in the receipt. Dropping that instead of aggregating it would have been
  exactly the malformed-duplicate-id loss this lens exists to avoid.

  node — `knip`, resolved from PATH through the guardian seam (`knip --directory <abs
  repo> --reporter json`). PATH-only: the base seam rejects repo-local executables, so the
  old `node_modules/.bin/knip` preference and the pinned-`npx` network fallback are both
  gone — an unattended sweep never fetches a package from the registry. `node_modules`
  absence is checked BEFORE any invocation (a pure `os.path.isdir` on the absolute path,
  never a spawn) and reported `not-collected` with that exact reason — knip's own
  dependency-less behavior is not something this lens ever reports as a finding. Run
  read-only (no `--fix`, no write flag) against `/Users/zwrose/weekly-eats` (installed
  `node_modules`): exit 1 (knip's own "issues found" exit, matching `--max-issues` default
  0), ~1.6s wall, 55 file-groups scanned, 14 unused files, 33 unused exports. Empty stdout
  is treated as a broken run (not-collected), never a clean scan — a knip run always emits
  JSON. The argv that ran is recorded in the digest.

Candidate identity never carries a line number (`deadcode:vulture:<path>:<kind>:
<symbol>`, `deadcode:knip:<path>` for an unused file, `deadcode:knip:<path>:<export>`
for an unused export) because ids must survive line drift. That id is NOT automatically
unique — vulture's `clean_registry` case above is the proof — so every occurrence
sharing an id is AGGREGATED into one candidate (`metric` = occurrence count, every
line in the receipt) rather than left to collide, which the sweep would otherwise drop
as `malformed`.

`red_lines()` is always `[]` — dead code is a cost to future readers, never an absolute
red line.
"""
import json
import os
import re
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect as gc  # noqa: E402

LENS_NAME = "deadcode"
COLLECTOR_VERSION = "1.0.0"
DIGEST_SCHEMA = 1

VULTURE_TIMEOUT = 60
# knip resolves its own reachability graph across the whole project; give it headroom.
KNIP_TIMEOUT = 120

VULTURE_MIN_CONFIDENCE = "60"
# `--exclude` patterns are unanchored substrings (vulture's own semantics) — this keeps
# vendored/build trees that happen to contain stray .py files out of the scan.
VULTURE_EXCLUDES = "node_modules,.venv,venv,dist,build,__pycache__,.git"
VULTURE_OK_EXIT = (0, 3)   # 0 = no dead code, 3 = dead code found — both are success.
KNIP_OK_EXIT = (0, 1)      # 0 = clean, 1 = issues found (knip's own --max-issues default 0).

_VULTURE_LINE = re.compile(
    r"^(?P<path>.+):(?P<line>\d+): unused (?P<kind>\w+) '(?P<symbol>.*)' "
    r"\((?P<confidence>\d+)% confidence\)$"
)

PYTHON_MANIFESTS = ("pyproject.toml", "requirements.txt")
NODE_MANIFESTS = ("package.json",)
# Directories skipped when probing for .py files (same set vulture excludes).
PY_SKIP_DIRS = frozenset(
    {"node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".git"})


# --------------------------------------------------------------------------- helpers

def _repo_root(ctx):
    """Repo top-level = the sweep's cwd (realpath).

    Mirrors the sibling `deps` / `hotspots` / `duplication` lenses: the base seam runs
    collectors from a neutral cwd, and the repo is the ``ctx["cwd"]`` the shell hands us —
    never re-derived via a ``git rev-parse`` spawn (that would route a git subprocess
    through the seam only to relocate a root we were already given). This lens spawns no
    git at all; every tool operand below is made absolute against this root so a
    neutral-cwd run can never false-clean by scanning the wrong tree.
    """
    cwd = (ctx or {}).get("cwd") or "."
    return os.path.realpath(cwd)


def _has_python_sources(repo):
    """True when at least one `.py` file exists outside vendor/build directories."""
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in PY_SKIP_DIRS]
        for name in files:
            if name.endswith(".py"):
                return True
    return False


def detect_ecosystems(repo):
    """[(ecosystem, manifest-relpath|None)] in a stable order.

    Python: a root manifest is a positive signal; `.py` files alone are enough (vulture
    needs no manifest). Node: `package.json` is required (knip needs it).
    """
    found = []
    python_manifest = None
    for rel in PYTHON_MANIFESTS:
        if os.path.isfile(os.path.join(repo, rel)):
            python_manifest = rel
            break
    if python_manifest is not None:
        found.append(("python", python_manifest))
    elif _has_python_sources(repo):
        found.append(("python", None))
    for rel in NODE_MANIFESTS:
        if os.path.isfile(os.path.join(repo, rel)):
            found.append(("node", rel))
            break
    return found


def _candidates_of(digest):
    cands = (digest or {}).get("candidates") if isinstance(digest, dict) else None
    if not isinstance(cands, dict):
        return {}
    return {k: v for k, v in cands.items() if isinstance(v, dict)}


def _metric_of(item):
    try:
        return float(item.get("metric"))
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _tool_failure_reason(tool, tried, res):
    """One human-readable line: what was tried, what run_tool said, and the first
    stderr line if there was one — never just a bare exit code."""
    detail = (res.get("reason") or "").strip()
    stderr_lines = (res.get("stderr") or "").strip().splitlines()
    reason = "%s not runnable (tried %s)" % (tool, tried)
    if detail:
        reason += ": %s" % detail
    if stderr_lines:
        reason += " — %s" % stderr_lines[0]
    return reason


def _carry_forward_prefix(prev_candidates, prefix, merged):
    """Copy every prev candidate whose id starts with `prefix` into `merged`, unchanged
    apart from a `carriedForward` marker, so `diff()` sees no false `resolved` for a
    section this sweep could not measure. Never overwrites a fresh entry."""
    carried = 0
    for cid, rec in prev_candidates.items():
        if cid.startswith(prefix) and cid not in merged:
            copy = dict(rec)
            copy["carriedForward"] = True
            merged[cid] = copy
            carried += 1
    return carried


# ----------------------------------------------------------------------- python (vulture)

def _vulture_argv(repo):
    """``vulture`` resolved from PATH through the guardian seam, scanning an ABSOLUTE root.

    PATH-only (the base seam rejects repo-local executables outright, so the old
    venv-bin / project-interpreter ladder cannot resolve through it — it is gone). The
    single source operand is the absolute repo root, never ``"."`` — a ``"."`` would
    resolve against the seam's neutral cwd and scan the wrong tree (a false-clean). An
    absent ``vulture`` degrades to not-collected quoting the install command, via the
    seam's tool-absent outcome.
    """
    argv = ["vulture", repo, "--min-confidence", VULTURE_MIN_CONFIDENCE,
            "--exclude", VULTURE_EXCLUDES]
    return (argv, "vulture on PATH via the guardian seam (absolute source root %s)" % repo)


def parse_vulture(stdout):
    """[hit, ...] or (None, reason) on output that does not look like vulture at all.

    A hit is {"path", "line", "kind", "symbol", "confidence"}. Lines vulture emits for
    OTHER issue types (`unreachable_code` — "unreachable code after 'return'",
    "unsatisfiable 'if' condition", etc.) do not match `unused <kind> '<name>'` and are
    deliberately out of scope for collector_version 1.0.0 (this lens tracks unused
    symbols, not unreachable control flow) — they are skipped, not treated as a parse
    failure. Only stdout that yields ZERO recognized lines (and is non-empty) is
    unparseable.
    """
    text = (stdout or "").strip()
    if not text:
        return ([], None)
    hits = []
    unrecognized = 0
    for line in text.splitlines():
        m = _VULTURE_LINE.match(line)
        if not m:
            unrecognized += 1
            continue
        hits.append({
            "path": m.group("path").replace("\\", "/"),
            "line": int(m.group("line")),
            "kind": m.group("kind"),
            "symbol": m.group("symbol"),
            "confidence": int(m.group("confidence")),
        })
    if not hits and unrecognized:
        return (None,
                "vulture output did not match the expected `path:line: unused <kind> "
                "'<symbol>' (NN%% confidence)` format (%d unrecognized line%s)"
                % (unrecognized, "" if unrecognized == 1 else "s"))
    return (hits, None)


def _vulture_receipt(kind, symbol, path, occ):
    lines = sorted(o["line"] for o in occ)
    n = len(occ)
    line_str = ", ".join(str(l) for l in lines)
    conf_str = "/".join(str(o["confidence"]) for o in sorted(occ, key=lambda o: o["line"]))
    return (
        "vulture: unused %s '%s' in %s — %d occurrence%s at line%s %s (confidence %s%%)"
        % (kind, symbol, path, n, "" if n == 1 else "s", "" if n == 1 else "s",
           line_str, conf_str)
    )


def aggregate_vulture(hits):
    """{id: candidate} — group hits sharing (path, kind, symbol) into one candidate.

    Ids never carry a line number, so two unused symbols with the same name in the
    same file (a real, observed case: a same-named pytest fixture parameter across
    several test functions) collide on id. Aggregating — rather than letting the sweep
    drop the duplicate as `malformed` — is what keeps that a real, countable finding.
    """
    groups = {}
    for h in hits:
        cid = "deadcode:vulture:%s:%s:%s" % (h["path"], h["kind"], h["symbol"])
        groups.setdefault(cid, []).append(h)
    out = {}
    for cid, occ in groups.items():
        first = occ[0]
        out[cid] = {
            "id": cid,
            "tool": "vulture",
            "kind": first["kind"],
            "path": first["path"],
            "symbol": first["symbol"],
            "metric": len(occ),
            "lines": sorted(o["line"] for o in occ),
            "receipt": _vulture_receipt(first["kind"], first["symbol"], first["path"], occ),
        }
    return out


def collect_python(ctx, repo):
    """(status, reason, {id: candidate}, argv, resolution) for the vulture collector."""
    argv, tried = _vulture_argv(repo)
    res = gc.run_tool(argv, ctx, timeout=VULTURE_TIMEOUT, cwd=repo,
                      ok_exits=VULTURE_OK_EXIT)
    if not res.get("ok"):
        return ("not-collected", _tool_failure_reason("vulture", tried, res), {},
                argv, tried)
    hits, err = parse_vulture(res.get("stdout"))
    if err is not None:
        return ("not-collected", err, {}, argv, tried)
    # Exit 3 means "dead code found" — empty/no-parsed output is a contradiction,
    # never a clean scan (R11).
    if res.get("exit") == 3 and not hits:
        return ("not-collected",
                "vulture exited 3 (dead code found) but stdout was empty / yielded no "
                "parseable hits — refusing to report a clean scan", {}, argv, tried)
    return ("collected", None, aggregate_vulture(hits), argv, tried)


# --------------------------------------------------------------------------- node (knip)

def _knip_argv(repo):
    """``knip`` resolved from PATH through the guardian seam, run against an ABSOLUTE dir.

    PATH-only (the base seam rejects repo-local executables, so the old
    ``node_modules/.bin/knip`` preference and the pinned-``npx`` network fallback are both
    gone — an unattended sweep never fetches a package from the registry). ``--directory``
    carries the absolute repo root so a neutral-cwd run scans the right project. An absent
    ``knip`` degrades to not-collected via the seam's tool-absent outcome.

    SECURITY / COST NOTE (D3, disclosed for owner/advisor ratification): knip LOADS AND
    EXECUTES the project's own ``knip.config.{js,ts}`` (or the ``knip`` key in
    ``package.json``) by design — it has no clean no-exec mode. On a repo whose knip config
    is attacker-controlled this is repo-controlled code execution during a sweep. This lens
    does NOT try to hack around it (a neutered config would silently mis-scan); the behavior
    is left as-is and surfaced here so a sandboxing follow-up can be scoped. The seam's
    other hardening (neutral cwd, sanitized env, no fetch, PATH-only) still applies.
    """
    argv = ["knip", "--directory", repo, "--reporter", "json"]
    return (argv, "knip on PATH via the guardian seam (--directory %s)" % repo)


def parse_knip(stdout):
    """issues-list or (None, reason). Requires the `{"issues": [...]}` shape observed
    from a real `knip --reporter json` run — anything else is unparseable.

    Empty stdout is NOT a clean scan: a knip run always emits a JSON document (a clean
    project is ``{"issues": []}``), so empty output is a broken run and degrades to
    not-collected rather than reading as "no dead code" — the same honesty stance the
    deps lens takes on empty ``npm audit`` JSON.
    """
    text = (stdout or "").strip()
    if not text:
        return (None, "knip produced empty output — a knip run always emits JSON; empty "
                      "stdout is a broken run, not a clean scan")
    try:
        data = json.loads(text)
    except ValueError as exc:
        return (None, "knip output was not valid JSON: %s" % exc)
    if not isinstance(data, dict) or not isinstance(data.get("issues"), list):
        return (None, "knip JSON did not have the expected {\"issues\": [...]} shape")
    return (data["issues"], None)


def _knip_receipt(kind, path, export, occ):
    n = len(occ)
    if kind == "file":
        return "knip: %s is reported as an unused file (no import graph reaches it)" % path
    lines = sorted(o["line"] for o in occ if isinstance(o.get("line"), int))
    line_str = ", ".join(str(l) for l in lines) if lines else "unknown"
    return (
        "knip: unused export '%s' in %s — %d occurrence%s at line%s %s"
        % (export, path, n, "" if n == 1 else "s", "" if n == 1 else "s", line_str)
    )


def _knip_inscope_signals(issues):
    """Count the IN-SCOPE (unused-file / unused-export) raw signals in knip's issues,
    regardless of whether each normalizes to a candidate.

    An entry contributes when it names a nonempty ``files`` list or a nonempty ``exports``
    list — the two categories this lens scopes to. Out-of-scope categories
    (types / dependencies / enumMembers / duplicates / unresolved / binaries / …) are NOT
    counted: knip legitimately exits 1 for those alone, and that is a genuine CLEAN scan
    *for the dead-code lens*. Counting the raw signal (not the normalized candidate) is
    what distinguishes "knip found unused files/exports we failed to normalize" (a
    contradiction — degrade) from "knip only flagged unused dependencies" (clean-collected).
    """
    n = 0
    for entry in issues or []:
        if not isinstance(entry, dict):
            continue
        files = entry.get("files")
        if isinstance(files, list) and files:
            n += len(files)
        exports = entry.get("exports")
        if isinstance(exports, list) and exports:
            n += len(exports)
    return n


def _knip_malformed_inscope(issues):
    """Count PRESENT-BUT-MALFORMED in-scope (``files`` / ``exports``) fields — a present
    key whose value is not a list, a shape ``aggregate_knip`` cannot normalize (H3).

    A malformed in-scope field is an in-scope signal knip EMITTED that this lens failed to
    parse. ``_knip_inscope_signals`` above counts only well-formed nonempty lists, so a
    present-but-non-list ``exports={"bad": "shape"}`` counts as ZERO there and — absent this
    detector — an exit-1 run carrying only that field (or that field beside a valid
    candidate) would read collected-clean, silently dropping the malformed signal. A
    genuinely ABSENT in-scope field (the out-of-scope-only exemption) is NOT malformed."""
    n = 0
    for entry in issues or []:
        if not isinstance(entry, dict):
            continue
        for key in ("files", "exports"):
            if key in entry and not isinstance(entry.get(key), list):
                n += 1
    return n


def aggregate_knip(issues):
    """{id: candidate} from knip's per-file issue entries — unused files + unused
    exports only (types/enumMembers/dependencies/etc. are out of scope for this lens)."""
    groups = {}
    for entry in issues or []:
        if not isinstance(entry, dict):
            continue
        path = entry.get("file")
        if not isinstance(path, str) or not path:
            continue
        for _f in entry.get("files") or []:
            cid = "deadcode:knip:%s" % path
            groups.setdefault(cid, {"kind": "file", "path": path, "export": None, "occ": []})
            groups[cid]["occ"].append({"line": None})
        for exp in entry.get("exports") or []:
            if not isinstance(exp, dict):
                continue
            name = exp.get("name")
            if not name:
                continue
            cid = "deadcode:knip:%s:%s" % (path, name)
            groups.setdefault(
                cid, {"kind": "export", "path": path, "export": name, "occ": []})
            groups[cid]["occ"].append({"line": exp.get("line")})

    out = {}
    for cid, g in groups.items():
        occ = g["occ"]
        lines = sorted(o["line"] for o in occ if isinstance(o.get("line"), int))
        out[cid] = {
            "id": cid,
            "tool": "knip",
            "kind": g["kind"],
            "path": g["path"],
            "export": g["export"],
            "metric": len(occ),
            "lines": lines,
            "receipt": _knip_receipt(g["kind"], g["path"], g["export"], occ),
        }
    return out


def collect_node(ctx, repo):
    """(status, reason, {id: candidate}, argv|None, resolution|None) for the knip collector.

    The ``node_modules`` gate is a pure ``os.path.isdir`` check on the ABSOLUTE repo path —
    never a spawn: knip's own dependency-less behavior must not be reported as a finding,
    and an uninstalled project degrades honestly BEFORE any invocation.
    """
    if not os.path.isdir(os.path.join(repo, "node_modules")):
        return ("not-collected",
                "no node_modules at repo root — knip requires the project's "
                "dependencies to be installed", {}, None, None)
    argv, tried = _knip_argv(repo)
    res = gc.run_tool(argv, ctx, timeout=KNIP_TIMEOUT, cwd=repo, ok_exits=KNIP_OK_EXIT)
    if not res.get("ok"):
        return ("not-collected", _tool_failure_reason("knip", tried, res), {}, argv, tried)
    issues, err = parse_knip(res.get("stdout"))
    if err is not None:
        return ("not-collected", err, {}, argv, tried)
    candidates = aggregate_knip(issues)
    # H3: a present-but-malformed in-scope field (e.g. `exports={"bad": "shape"}`) is an
    # in-scope signal knip emitted that we could not normalize. It must degrade even when a
    # VALID candidate sits beside it (which would otherwise mask it past the `not candidates`
    # gate below) — dropping it silently would read a contradiction as a clean scan. Gate on
    # the findings exit; a clean (exit 0) run carries no such contradiction.
    if res.get("exit") == 1:
        malformed = _knip_malformed_inscope(issues)
        if malformed:
            return ("not-collected",
                    "knip exited 1 (issues found) with %d present-but-malformed in-scope "
                    "files/exports field(s) that did not normalize — refusing to drop a "
                    "signalled-but-unparseable in-scope signal as a clean scan"
                    % malformed, {}, argv, tried)
    # Exit 1 means "issues found". A parsed-but-empty CANDIDATE set (not just an empty
    # raw `issues` list — the gate must check the NORMALIZED candidates, since
    # aggregate_knip drops out-of-scope entries) is the R2/R11 "findings-exit reported as
    # clean" defect — UNLESS knip's exit-1 was entirely out-of-scope for this lens.
    #   * empty `issues` list, OR in-scope file/export signals that normalized to zero
    #     → contradiction → degrade (refuse a clean scan).
    #   * nonempty `issues` carrying ONLY out-of-scope categories (unused dependencies /
    #     types / enumMembers / …) → a genuine clean dead-code scan → collected (empty).
    if res.get("exit") == 1 and not candidates:
        inscope = _knip_inscope_signals(issues)
        if inscope:
            return ("not-collected",
                    "knip exited 1 (issues found) with %d in-scope file/export signal(s) "
                    "that normalized to zero candidates — refusing to report a clean scan"
                    % inscope, {}, argv, tried)
        if not issues:
            return ("not-collected",
                    "knip exited 1 (issues found) but parsed to zero candidates — "
                    "refusing to report a clean scan", {}, argv, tried)
        # Exit 1 was entirely out-of-scope for the dead-code lens (e.g. unused
        # dependencies) — a genuine clean scan, not a contradiction.
        return ("collected", None, {}, argv, tried)
    return ("collected", None, candidates, argv, tried)


# ------------------------------------------------------------------------------- the lens

VALIDATION_GUIDANCE = """\
Each candidate is a symbol, file, or export a static tool could not prove is referenced
anywhere it could see. Most of what vulture and knip raise on this project is code every
convention here sanctions on purpose — reject a candidate whose kill list applies:
(1) TEST-CODE CONVENTIONS — mock/stub/fake signatures whose parameters exist only to
match an interface (a fake `run(argv, capture_output=True, ...)` that never reads
`capture_output`), pytest fixtures (including `@pytest.fixture(autouse=True)` helpers
never called by name), conftest.py helpers, a fixture parameter a test declares but its
body never reads, and a `parametrize` argument kept only for a readable test id;
(2) interface- or protocol-conformance parameters that must exist to match a required
signature even when the implementation ignores them; (3) framework entry points and
registered callbacks invoked by name or by string rather than by direct call (CLI
subcommand handlers, hooks, dispatch-table targets); (4) `__all__` exports and public API
surface meant for callers outside this repo/package; (5) dynamic access — `getattr`, dict
dispatch, `importlib`, string-keyed lookups a static tool cannot trace; (6) generated or
template/scaffold code (a `templates/` starter file with `{{placeholder}}` bodies is
never "dead", it is unfilled); (7) anything a declared repo convention (CLAUDE.md,
CONVENTIONS.md) sanctions by name. A hands-on vulture run against this repo confirmed
class (1) as the dominant false-positive source: of 30 aggregated candidates, several
were exactly a same-named pytest fixture parameter flagged across every test function
that declares it, and an autouse fixture definition flagged because pytest — not this
repo's code — is what calls it. Validate against the actual call site (the receipt's
lines, not just the symbol name) before ever writing a consequence, and reject an
aggregated candidate as a whole only when EVERY occurrence in its receipt is covered by
the kill list — a mixed candidate (some occurrences real, some conventions) needs a
consequence scoped to the real ones only.
"""

CONSEQUENCE_TEMPLATE = """\
Price dead code as CARRYING COST AND MISLEADING CONTEXT, never as a bug or a risk: every
future reader and every coding agent that touches this file has to read the dead symbol,
reason about whether it does something, and only then conclude it does not — that
reasoning tax is the cost, paid again on every future read.
  "`_compute_drift`'s `engine_plugin_ver` parameter (repo_doctor.py:243) is never read in
   the function body; every future reader has to trace the call site to learn that before
   they can trust what this function actually depends on."
Price effort from the receipt (delete an unused import: small; an unused parameter with
callers to update: small-to-medium; an unused function with no other callers: small
unless its name suggests a half-finished feature, in which case say so instead of
guessing). Never invent a severity tier — this lens carries no red line.
"""


class DeadCodeLens(object):
    """Unused symbols (vulture) + unused files/exports (knip) — validated hard, never
    silently degraded."""

    name = LENS_NAME
    collector_version = COLLECTOR_VERSION
    required_facts = ()
    validation_guidance = VALIDATION_GUIDANCE
    consequence_template = CONSEQUENCE_TEMPLATE
    # Measured 2026-07-21 at the command line, not estimated:
    #   this repo: vulture full-tree scan (excludes above) ~0.78s, 37 raw hits / 30
    #     aggregated candidates, confirming the known repo_doctor.py:243 seed.
    #   /Users/zwrose/weekly-eats (installed node_modules): knip --reporter json ~1.6s,
    #     exit 1 (issues found), 55 file-groups / 14 unused files / 33 unused exports.
    cost = {
        "collectorSeconds": 2.4,
        "note": "vulture ~0.78s full-repo scan (this repo); knip ~1.6s (weekly-eats, real "
                "installed node_modules). Both tools resolve from PATH through the "
                "guardian seam — no repo-local binary, no npx network fetch (an absent "
                "tool degrades to not-collected, never a silent clean). Python runs when a "
                "root manifest OR `.py` files are present; knip runs only when package.json "
                "and node_modules are both present.",
    }

    # -------------------------------------------------------------------------- collect

    def collect(self, ctx):
        ctx = ctx or {}
        repo = _repo_root(ctx)
        prev_candidates = _candidates_of(ctx.get("prevDigest"))
        detected = detect_ecosystems(repo)
        detected_names = [eco for eco, _rel in detected]

        if not detected:
            return dict(
                candidates=[], digest=None,
                **gc.not_collected(
                    "no python sources (.py files outside vendor/build dirs) and no "
                    "node manifest (package.json) at the repo root — dead-code "
                    "collection needs a declared or discoverable ecosystem; nothing "
                    "was scanned this sweep"))

        ecosystems = {}
        fresh = {}
        reasons = []
        any_collected = False

        for ecosystem, manifest_rel in detected:
            argv = None
            resolution = None
            if ecosystem == "python":
                status, reason, items, argv, resolution = collect_python(ctx, repo)
                tool = "vulture"
            else:
                status, reason, items, argv, resolution = collect_node(ctx, repo)
                tool = "knip"

            if status == "collected":
                any_collected = True
                fresh.update(items)
            else:
                reasons.append("%s: %s" % (ecosystem, reason))

            section = {
                "manifest": manifest_rel,
                "tool": tool,
                "status": status,
                "reason": reason,
                "candidateCount": len(items),
            }
            if argv is not None:
                section["argv"] = argv
            if resolution is not None:
                section["resolution"] = resolution
            ecosystems[ecosystem] = section

        merged = dict(fresh)
        prefixes = {"python": "deadcode:vulture:", "node": "deadcode:knip:"}
        for ecosystem, section in ecosystems.items():
            if section["status"] != "collected":
                _carry_forward_prefix(prev_candidates, prefixes[ecosystem], merged)

        digest = {
            "schema": DIGEST_SCHEMA,
            "collectorVersion": COLLECTOR_VERSION,
            "detected": detected_names,
            "ecosystems": ecosystems,
            "candidates": merged,
        }

        # not-collected returns digest None (the base conformance contract: a degraded
        # collect must not overwrite the tracked snapshot — see the deps lens and
        # guardian_conformance's digest-on-not-collected guard). partial keeps the digest
        # for the portions it did measure, carrying the unmeasured section forward.
        if not any_collected:
            return dict(candidates=[], digest=None,
                        **gc.not_collected("; ".join(reasons)))
        out = dict(candidates=list(fresh.values()), digest=digest)
        if reasons:
            out.update(gc.partial("; ".join(reasons)))
        else:
            out.update(gc.collected())
        return out

    # ----------------------------------------------------------------------------- diff

    def diff(self, prev_digest, cur_digest):
        # A degraded sweep returns digest=None (whole-lens not-collected). Nothing was
        # measured this run, so there is nothing to compare — claim no movement in either
        # direction. Reading prev candidates against an absent cur would emit every prior
        # finding as a false `resolved` (an uninstalled tool looking like a cleanup).
        if not isinstance(cur_digest, dict):
            return {"new": [], "worsened": [], "resolved": []}
        prev = _candidates_of(prev_digest)
        cur = _candidates_of(cur_digest)
        new = sorted(cid for cid in cur if cid not in prev)
        worsened = sorted(
            cid for cid in cur
            if cid in prev and _metric_of(cur[cid]) > _metric_of(prev[cid]))
        resolved = sorted(cid for cid in prev if cid not in cur)
        return {"new": new, "worsened": worsened, "resolved": resolved}

    # ------------------------------------------------------------------------ red lines

    def red_lines(self, candidates):
        """Dead code is a cost claim, never an absolute red line."""
        return []

    def degrade(self, reason):
        return {"lens": self.name, "degraded": True, "reason": reason}

    # ---------------------------------------------------------------------- conformance

    def conformance_fixture(self):
        """Minimal NODE-only workspace so collect() reaches the ``knip`` collector.

        ``package.json`` makes node the sole detected ecosystem, and a ``node_modules``
        directory (materialized by the sole file written under it) clears the
        dependency-installed gate so knip is invoked under the injected run stub. No
        ``.py`` files and no python manifest are written, so vulture never co-fires — the
        single injected stdout drives exactly one collector.

        This lens exercises the ``reported-nonzero-parsed-zero`` scenario through knip
        rather than vulture because vulture's genuine clean output IS empty stdout, which
        is indistinguishable from the harness-owned ``findings-empty-output`` scenario
        (exit 0 + empty) that the harness requires to DEGRADE; knip always emits JSON, so
        empty stdout is honestly a broken run. Same reason the deps lens picks node. The
        harness was NOT extended — a single injected stdout suffices (see the module diff's
        findings note).
        """
        return {
            "package.json": json.dumps({
                "name": "guardian-deadcode-conformance",
            }) + "\n",
            # Materializes the node_modules/ directory the knip gate checks (os.path.isdir),
            # without any real installed dependency.
            "node_modules/.package-lock.json": json.dumps({"name": "conformance"}) + "\n",
        }

    def conformance_cases(self):
        """Lens-supplied ``reported-nonzero-parsed-zero`` payload (see lens-contract.md).

        Under the node-only fixture the single injected stdout drives ``knip`` alone. knip
        signals findings via its EXIT CODE (1), not a count in its JSON, so both probes ship
        the same genuinely-shaped clean document ``{"issues": []}`` and are distinguished
        purely by exit — declaring knip's dual success exits (``exit=1`` findings,
        ``clean_exit=0`` clean):

        - ``clean_stdout`` = ``{"issues": []}`` at ``clean_exit=0`` → knip collected zero
          candidates cleanly → whole-lens ``collected``.
        - ``stdout`` = ``{"issues": []}`` at ``exit=1`` → knip signalled issues but parsed
          to zero candidates → the contradiction gate degrades knip to ``not-collected`` →
          whole-lens degrades. It must never read as ``collected``.
        """
        clean = json.dumps({"issues": []})
        return {
            "reported-nonzero-parsed-zero": {
                "stdout": clean,
                "clean_stdout": clean,
                "exit": 1,
                "clean_exit": 0,
                # knip (argv[0] "knip") is the sole collector under the node-only fixture
                # and the contradiction target. The per-tool map is declared for parity
                # with the multi-collector lenses; deleting the exit-1 gate makes the sole
                # knip run read clean → whole-lens collected → this case fails.
                "stdout_by_tool": {"knip": clean},
            },
        }

    def conformance_prev_digest(self):
        """A schema-valid prior digest carrying ONE recognizable knip sentinel, plus the
        same digest re-measured clean, for the conformance non-vacuity check.

        The harness first asserts ``diff(prev, cleared)`` RESOLVES the sentinel (so the
        findings-probe "resolved must be empty" is not vacuous), then asserts the degraded
        findings probe resolves nothing.
        """
        sentinel_id = "deadcode:knip:scripts/sentinel-unused.js"
        sentinel = {
            "id": sentinel_id, "tool": "knip", "kind": "file",
            "path": "scripts/sentinel-unused.js", "export": None,
            "metric": 1, "lines": [], "receipt": "knip: sentinel unused file",
        }

        def _digest(cands):
            return {
                "schema": DIGEST_SCHEMA,
                "collectorVersion": COLLECTOR_VERSION,
                "detected": ["node"],
                "ecosystems": {},
                "candidates": cands,
            }

        return {
            "prev": _digest({sentinel_id: sentinel}),
            "cleared": _digest({}),
            "sentinelIds": [sentinel_id],
        }


LENS = DeadCodeLens()
# Module-level roster the production loader registers (guardian_lens.PRODUCTION_LENS_MODULES).
LENSES = (LENS,)
