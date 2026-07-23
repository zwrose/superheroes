"""Tests for the Guardian coupling lens (#538) — adapted single-lens contract.

The lens is ONE tool-using lens ``glc.CouplingLens()`` (no constructor args) exported as
``LENS = CouplingLens(); LENSES = (LENS,)``. A single ``collect(ctx)`` covers BOTH
ecosystems: JS/TS via dependency-cruiser (spawned only through
``guardian_collect.run_tool`` → ``guardian_tools.invoke``) and Python via a stdlib AST
import census that NEVER spawns a tool. Outcome is main's 3-state model
(``collected`` / ``partial`` / ``not-collected``) via ``guardian_lens.classify_collect``;
the prior digest arrives as ``ctx["prevDigest"]`` (no store re-read).

To exercise one ecosystem, the fixture repo contains only that ecosystem's sources and
the single lens is driven; assertions read the merged outcome/digest. An absent
ecosystem is simply omitted from the digest (there is no "not-applicable with digest").

Everything that writes goes to a scratch ``root=`` store under ``tmp_path`` — never a
live store. Constants are IMPORTED from their lib homes, never restated (CONVENTIONS
§11.3).

The env/PATH/NODE_PATH/toolchain-pin invocation-hardening escape class is now owned by
``guardian_tools`` and covered by ``test_guardian_tools.py`` on main; the old adapters
env/invocation-stack tests (``_invoke`` / ``depcruise_env`` / ``run_depcruise`` /
``_sanitize_path_lookup`` / ``TOOLCHAIN_NODE_PATH`` / ``build_lenses``) are dropped here
because they target deleted symbols. Two tool-literal RCE regressions are re-ported
through the current seam (webpack-config via the real tool; import-linter contract_types
never spawned).
"""
import json
import os
import shutil
import subprocess

import pytest

import guardian_coupling_adapters as adapters
import guardian_ledger
import guardian_lens as gl
import guardian_lens_coupling as glc
import guardian_store as gs
import guardian_sweep as gsw
from guardian_fixtures import init_calibrated_repo, write_ledger


# ======================================================================================
# captured real tool output
# ======================================================================================

# Verbatim `depcruise --output-type json --no-config --ts-pre-compilation-deps ... src`
# on a scratch repo with dependency-cruiser 18.1.0 + typescript 5.9.3 resolvable.
# Trimmed only by dropping the `extensionsFound` array and the non-JS/TS transpiler rows.
REAL_DEPCRUISE_REPORT = json.dumps(json.loads(r"""
{
  "modules": [
    {"source": "src/features/a/main.js",
     "dependencies": [{"module": "../b/svc", "moduleSystem": "cjs", "dynamic": false,
       "dependencyTypes": ["local", "require"], "resolved": "src/features/b/svc.js",
       "coreModule": false, "followable": true, "couldNotResolve": false,
       "matchesDoNotFollow": false, "circular": false, "valid": true}],
     "dependents": [], "orphan": false, "valid": true},
    {"source": "src/features/b/svc.js", "dependencies": [],
     "dependents": ["src/features/a/main.js"], "orphan": false, "valid": true},
    {"source": "src/features/b/svc.ts", "dependencies": [],
     "dependents": ["src/features/c/main.ts"], "orphan": false, "valid": true},
    {"source": "src/features/b/types.d.ts", "dependencies": [],
     "dependents": ["src/features/c/main.ts"], "orphan": false, "valid": true},
    {"source": "src/features/c/main.ts",
     "dependencies": [
       {"module": "../b/svc", "moduleSystem": "es6", "dynamic": false,
        "dependencyTypes": ["local", "import"], "resolved": "src/features/b/svc.js",
        "coreModule": false, "followable": true, "couldNotResolve": false,
        "matchesDoNotFollow": false, "circular": false, "valid": true},
       {"module": "../b/types", "moduleSystem": "es6", "dynamic": false,
        "dependencyTypes": ["local", "type-only", "import"],
        "resolved": "src/features/b/types.d.ts", "coreModule": false,
        "followable": true, "couldNotResolve": false, "matchesDoNotFollow": false,
        "circular": false, "valid": true}],
     "dependents": [], "orphan": false, "valid": true}
  ],
  "summary": {
    "violations": [], "error": 0, "warn": 0, "info": 0, "ignore": 0,
    "totalCruised": 5, "totalDependenciesCruised": 3,
    "optionsUsed": {"args": "src", "outputType": "json"},
    "environment": {
      "version": "18.1.0",
      "nodeVersionSupported": "^22||^24||>=26",
      "nodeVersionFound": "v26.3.0",
      "osVersionFound": "arm64 darwin@25.5.0",
      "transpilersFound": [
        {"name": "javascript", "version": "*", "available": true,
         "currentVersion": "acorn@8.17.0"},
        {"name": "typescript", "version": ">=2.0.0 <7.0.0", "available": true,
         "currentVersion": "typescript@5.9.3"}
      ]
    }
  }
}
"""))

# ======================================================================================
# harness
# ======================================================================================

class _Completed(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_run(handler, tracked=None):
    """Injectable `run` — run_tool threads ctx['run']; tests never shell out.

    Post-#564 the lens co-fires ``git ls-files -z``. Pass ``tracked=[...]`` to pin the
    census; ``None`` walks the repo cwd on disk (every on-disk file is "tracked").
    """
    def _run(argv, **kwargs):
        if argv and argv[0] == "git":
            return _git_ls_files_result(kwargs, tracked=tracked)
        out = handler(list(argv), kwargs)
        if isinstance(out, BaseException):
            raise out
        if isinstance(out, _Completed):
            return out
        rc, stdout, stderr = out
        return _Completed(rc, stdout, stderr)
    return _run


def _git_ls_files_result(kwargs, tracked=None):
    cwd = kwargs.get("cwd") or "."
    if tracked is not None:
        names = list(tracked)
    else:
        names = []
        for root, dirs, files in os.walk(cwd):
            if ".git" in dirs:
                dirs.remove(".git")
            for fn in files:
                names.append(os.path.relpath(os.path.join(root, fn), cwd))
    text = "".join(n + "\0" for n in names)
    return _Completed(0, text, "")


def depcruise_run(report_json, returncode=0, side_effect=None):
    """A fake dependency-cruiser. Every invocation returns the same report."""
    def handler(argv, kwargs):
        if side_effect:
            side_effect(kwargs.get("cwd"))
        return (returncode, report_json, "")
    return make_run(handler)


def dc_report(edges=(), extra_sources=(), ts_available=True, ts_version="5.9.3",
              tool_version="18.1.0", violations=(), rule_set=None):
    """Build a dependency-cruiser report in the REAL schema (verified against capture)."""
    by_source = {}
    for src in extra_sources:
        by_source.setdefault(src, [])
    for edge in edges:
        src, dst = edge[0], edge[1]
        types = list(edge[2]) if len(edge) > 2 else ["local", "import"]
        rules = list(edge[3]) if len(edge) > 3 else []
        by_source.setdefault(src, []).append({
            "module": dst, "moduleSystem": "es6", "dynamic": False,
            "dependencyTypes": types, "resolved": dst, "coreModule": False,
            "followable": True, "couldNotResolve": False,
            "matchesDoNotFollow": False, "circular": False,
            "valid": not rules,
            "rules": [{"name": r, "severity": "error"} for r in rules],
        })
        by_source.setdefault(dst, [])
    modules = [{"source": s, "dependencies": d, "dependents": [], "orphan": False,
                "valid": True} for s, d in sorted(by_source.items())]
    summary = {
        "violations": [
            {"from": v[0], "to": v[1], "rule": {"name": v[2], "severity": "error"}}
            for v in violations
        ],
        "error": len(violations), "warn": 0, "info": 0, "ignore": 0,
        "totalCruised": len(modules), "totalDependenciesCruised": len(edges),
        "optionsUsed": {"args": "src", "outputType": "json"},
        "environment": {
            "version": tool_version,
            "transpilersFound": [
                {"name": "javascript", "version": "*", "available": True,
                 "currentVersion": "acorn@8.17.0"},
                {"name": "typescript", "version": ">=2.0.0 <7.0.0",
                 "available": bool(ts_available),
                 "currentVersion": ("typescript@" + ts_version) if ts_available else "-"},
            ],
        },
    }
    if rule_set is not None:
        summary["ruleSetUsed"] = rule_set
    return json.dumps({"modules": modules, "summary": summary})


DEFAULT_RULE_SET = {"forbidden": [{"name": "no-cross-feature",
                                   "from": {}, "to": {}, "severity": "error"}]}


def write(repo, rel, text="export const x = 1;\n"):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return rel


def lens():
    """The single adapted lens object (fresh instance; == the module singleton shape)."""
    return glc.CouplingLens()


def ctx(repo, tmp_path, run=None, prev=None):
    """Build a collect() ctx. `prev` is threaded as ctx['prevDigest'] (no store re-read)."""
    if run is None:
        run = make_run(lambda _argv, _kw: _Completed(127, "", "unexpected tool"))
    return {"cwd": repo, "root": store(tmp_path), "run": run, "prevDigest": prev}


def census_ctx(repo, tracked=None):
    return {"cwd": repo, "run": make_run(lambda _a, _k: _Completed(127, "", ""), tracked=tracked)}


def census_at(repo, ecosystem, tracked=None):
    got, err = glc.census(census_ctx(repo, tracked=tracked), repo, ecosystem)
    assert err is None, err
    return got


def store(tmp_path):
    return str(tmp_path / "scratch-store")


def st(out):
    """The classified collect status via the contract entry point."""
    status, _reason = gl.classify_collect(out)
    return status


def tree(root):
    """Snapshot every non-.git file as {relpath: bytes}.

    Path-only comparison cannot catch an in-place overwrite of an existing file;
    content hashing can. Callers asserting byte-identity must use this mapping.
    """
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            with open(path, "rb") as fh:
                out[rel] = fh.read()
    return out


# ======================================================================================
# 1. lens protocol compliance (single lens)
# ======================================================================================

def test_single_lens_passes_validate_lens():
    assert glc.LENSES == (glc.LENS,)
    assert len(glc.LENSES) == 1
    ok, reasons = gl.validate_lens(glc.LENS)
    assert ok is True, (glc.LENS.name, reasons)
    assert reasons == []
    assert glc.LENS.name == glc.LENS_NAME == "coupling"
    assert glc.LENS.collector_version == "1.1.0"


def test_production_roster_registers_only_the_single_coupling_lens():
    """§C: roster/registration target the ONE `coupling` lens (no js/py split)."""
    lenses = gl.registered_lenses()
    coupling = [l for l in lenses if getattr(l, "name", None) == glc.LENS_NAME]
    assert len(coupling) == 1, [getattr(l, "name", None) for l in lenses]
    ok, reasons = gl.validate_lens(coupling[0])
    assert ok is True, reasons
    # Contract methods are bound to the one object.
    for meth in ("collect", "diff", "red_lines", "degrade"):
        assert callable(getattr(glc.LENS, meth))


def test_required_facts_empty_so_the_sweep_never_pre_degrades_the_lens(tmp_path):
    """stack-tags is `absent` on this very repo, so requiring it would degrade the lens
    before collect() ever runs (guardian_sweep.collect → _unsatisfied_facts)."""
    assert glc.LENS.required_facts == ()
    repo = init_calibrated_repo(tmp_path)
    verdicts = gsw.verify_config(repo, root=store(tmp_path), needed_facts=set())
    statuses = {f["fact"]: f["status"] for f in verdicts["facts"]}
    assert statuses["stack-tags"] == "absent"
    unsatisfied = gsw._unsatisfied_facts(verdicts["facts"])
    assert not (set(glc.LENS.required_facts) & unsatisfied)


def test_red_lines_surface_nothing_while_check_the_check_is_deferred():
    """check-the-check is owner-deferred; coupling red_lines stay empty.

    Architectural walls reach the advisor only via drift-over-baseline when
    declared-vocabulary surfacing returns. dead-adopted-check is not a
    RED_LINE_KINDS member while that surface is deferred.
    """
    ordinary = [{"id": "coupling:depcruise:a->b", "metric": 99}]
    advisory = [{"id": "coupling:depcruise:check-the-check:adopted-check",
                 "advisory": True, "rule": "check-the-check"}]
    assert glc.LENS.red_lines(ordinary) == []
    assert glc.LENS.red_lines(advisory) == []
    assert glc.LENS.red_lines([]) == []
    assert gl.RED_LINE_KINDS == (
        "critical-vuln", "new-high-complexity", "large-fresh-clone")
    assert "dead-adopted-check" not in gl.RED_LINE_KINDS
    assert gsw._filter_red_lines([{"kind": "dead-adopted-check", "id": "x",
                                   "detail": "d"}]) == []


# ======================================================================================
# 2. adapters parsers against captured real tool output
# ======================================================================================

def test_parses_captured_real_depcruise_report():
    res = adapters.parse_depcruise_json(REAL_DEPCRUISE_REPORT, returncode=0)
    assert res["outcome"] == "ok"
    versions = adapters.depcruise_versions(res["payload"])
    assert versions["toolVersionResolved"] == "18.1.0"
    assert versions["typescriptVersionResolved"] == "5.9.3"
    assert versions["parseMode"] == "typescript"
    assert versions["pinHeld"] is True
    edges = adapters.depcruise_edges(res["payload"])
    pairs = {(e["from"], e["to"]) for e in edges}
    assert ("src/features/c/main.ts", "src/features/b/types.d.ts") in pairs
    type_only = [e for e in edges if glc.TYPE_ONLY_DEP_TYPE in e["types"]]
    assert len(type_only) == 1


def test_python_ast_census_records_no_declared_vocabulary_not_a_clean_claim(tmp_path):
    """A packaged Python tree with edges must not read as "checked and clean" — vocabulary
    is deferred, parseMode is ast-census-only, and candidates stay empty."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/api.py", "from mypkg import db\n")
    write(repo, "mypkg/db.py", "x = 1\n")
    out = lens().collect(ctx(repo, tmp_path))
    assert st(out) == "collected"
    assert out["candidates"] == []
    assert out["digest"]["versions"]["py"]["parseMode"] == "ast-census-only"
    assert out["digest"]["declaredVocabulary"]["declared"] is False
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert out["digest"]["declaredVocabulary"]["note"] == glc.VOCABULARY_DEFERRED_NOTE
    caps = {c["capability"] for c in out["digest"]["deferredCapabilities"]}
    assert "declared-vocabulary" in caps
    assert "check-the-check" in caps
    assert out["digest"]["counters"]["edges"] >= 1
    # Absent ecosystem is omitted, not recorded as not-applicable.
    assert "py" in out["digest"]["ecosystems"]
    assert "js" not in out["digest"]["ecosystems"]


# ======================================================================================
# 3. the closed collector-outcome table (adapters) + parse-driven collect
# ======================================================================================

def test_outcome_table_is_closed_and_defaults_to_degraded():
    assert adapters.classify("something-nobody-defined") == adapters.OUTCOMES["unknown"]
    assert adapters.classify("something-nobody-defined")[0] == adapters.DEGRADED
    for outcome, (klass, _reason) in adapters.OUTCOMES.items():
        assert klass in (adapters.OK, adapters.NOT_APPLICABLE, adapters.DEGRADED), outcome


@pytest.mark.parametrize("expected,returncode,text", [
    ("ok", 0, dc_report(edges=[("src/a/x.ts", "src/b/y.ts")])),
    ("ok-with-violations", 3,
     dc_report(edges=[("src/a/x.ts", "src/b/y.ts")],
               violations=[("src/a/x.ts", "src/b/y.ts", "no-cross-feature")])),
    ("nonzero-exit-partial-json", 3, '{"modules": [{"source": "src/a.ts"'),
    ("nonzero-exit-partial-json", 3, '{"modules": []}'),
    ("malformed-json", 0, "not json at all"),
    ("schema-changed", 0, '{"modules": "nope", "summary": {}}'),
    ("schema-changed", 0, '{"summary": {"environment": {}}}'),
    ("schema-changed", 0, '{"modules": [{"nope": 1}], "summary": {"environment": {}}}'),
    # Modules retain valid `source` but lose `dependencies` — must not read as a clean
    # graph (edges would silently vanish while the module census looks healthy).
    ("schema-changed", 0,
     '{"modules":[{"source":"src/a.ts"}],"summary":{"environment":{},"violations":[]}}'),
    ("truncated-output", 0, "x" * (adapters.MAX_OUTPUT_BYTES + 1)),
])
def test_outcome_table_parse_rows(expected, returncode, text):
    assert adapters.parse_depcruise_json(text, returncode=returncode)["outcome"] == expected


def test_nonzero_exit_with_complete_valid_json_is_a_success_row():
    """dependency-cruiser exits non-zero *because* rules were violated — that is data."""
    report = dc_report(edges=[("src/a/x.ts", "src/b/y.ts")],
                       violations=[("src/a/x.ts", "src/b/y.ts", "no-cross-feature")])
    res = adapters.parse_depcruise_json(report, returncode=7)
    assert adapters.is_ok(res["outcome"])


def test_no_declared_vocabulary_outcome_is_ok_not_degraded():
    """Synthetic Python census outcome stays a success row (data-only, not a failure)."""
    res = adapters.result("no-declared-vocabulary", payload={
        "analyzedFiles": None, "dependencies": None,
        "contracts": [], "violations": [], "toolVersionResolved": None})
    assert res["outcome"] == "no-declared-vocabulary"
    assert adapters.is_ok(res["outcome"])
    assert adapters.classify(res["outcome"])[0] == adapters.OK


@pytest.mark.parametrize("row", sorted(adapters.OUTCOMES))
def test_every_outcome_row_has_a_reason_or_is_a_success(row):
    klass, reason = adapters.OUTCOMES[row]
    if klass == adapters.DEGRADED:
        assert reason, "degraded row %r must carry a reason" % row


def test_tool_absent_degrades_collect_to_not_collected(tmp_path):
    """A JS-only repo where depcruise is unavailable → not-collected, digest None."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a/one.ts")
    run = make_run(lambda argv, kw: FileNotFoundError("depcruise"))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "not-collected"
    assert out["candidates"] == []
    assert out["digest"] is None
    assert isinstance(out["reason"], str) and out["reason"]
    # The js ecosystem's failure is named in the reason (tool not available).
    assert "not available" in out["reason"] or "depcruise" in out["reason"]


def test_modules_without_dependencies_list_degrade_through_collect(tmp_path):
    """Schema drift that keeps module sources but drops dependencies must not look clean."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a.ts")
    drifted = json.dumps({
        "modules": [{"source": "src/a.ts"}],
        "summary": {"environment": {}, "violations": []},
    })
    assert adapters.parse_depcruise_json(drifted, returncode=0)["outcome"] == "schema-changed"
    out = lens().collect(ctx(repo, tmp_path, run=depcruise_run(drifted)))
    assert st(out) == "not-collected"
    assert out["digest"] is None
    assert adapters.OUTCOMES["schema-changed"][1] in out["reason"]


# ======================================================================================
# 4. the non-mutating invariant
# ======================================================================================

def test_depcruise_argv_opts_out_of_caching_and_vendored_trees():
    argv = adapters.depcruise_argv(["src"])
    assert "--cache" not in argv
    assert "--output-type" in argv and "json" in argv
    assert "--no-config" in argv
    assert "--config" not in argv
    assert "--" in argv
    assert argv[argv.index("--") + 1] == "./src"
    for flag in ("--exclude", "--do-not-follow"):
        assert argv[argv.index(flag) + 1] == adapters.DEPCRUISE_EXCLUDE_RE
    assert "node_modules" in adapters.DEPCRUISE_EXCLUDE_RE


@pytest.mark.parametrize("ecosystem", ["js", "py"])
def test_collect_leaves_the_swept_repo_byte_identical(tmp_path, ecosystem):
    repo = init_calibrated_repo(tmp_path)
    if ecosystem == "js":
        write(repo, "src/a/one.ts", "export const sentinel = 'js-byte-identical';\n")
        run = depcruise_run(dc_report(extra_sources=["src/a/one.ts"]))
    else:
        write(repo, "pkg/__init__.py", "")
        write(repo, "pkg/one.py", "sentinel = 'py-byte-identical'\n")
        # Python side never spawns; run must not be called.
        run = make_run(
            lambda a, k: (_ for _ in ()).throw(
                AssertionError("Python side must not spawn while vocabulary deferred")))
    before = tree(repo)
    assert before, "byte-identity snapshot must cover at least one file"
    # Sentinel contents must be present so an in-place rewrite of either source fails.
    if ecosystem == "js":
        assert b"js-byte-identical" in before["src/a/one.ts"]
    else:
        assert b"py-byte-identical" in before["pkg/one.py"]
    lens().collect(ctx(repo, tmp_path, run=run))
    assert tree(repo) == before
    assert adapters.cache_paths_present(repo) == []


def test_a_collector_that_writes_in_the_repo_degrades_loudly(tmp_path):
    """The lens probes for known cache paths before/after; a tool that writes inside the
    swept repo degrades loudly (the cache-path before/after probe still lives in the lens).
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a.ts")
    repo_real = os.path.realpath(repo)

    def handler(argv, kwargs):
        os.makedirs(os.path.join(repo_real, ".dependency-cruiser-cache"), exist_ok=True)
        return (0, dc_report(extra_sources=["src/a.ts"]), "")

    out = lens().collect(ctx(repo, tmp_path, run=make_run(handler)))
    assert st(out) == "not-collected"
    assert ".dependency-cruiser-cache" in out["reason"]
    assert adapters.OUTCOMES["repo-write"][1] in out["reason"]


def test_executable_depcruise_config_is_ignored_not_passed_to_collector(tmp_path):
    """Repo config reading is owner-deferred — configs are never passed as --config.

    Presence of a config must not degrade as a special case and must not reach the
    collector argv. Collect still runs (data-gatherer) with --no-config.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a.ts")
    # .dependency-cruiser.js is itself a .js source; include it in the fake report so
    # the census/collapse tripwire does not fire and obscure the config-ignore claim.
    write(repo, ".dependency-cruiser.js",
          "module.exports = { forbidden: [{ name: 'x', from: {}, to: {} }] };\n")
    calls = []

    def handler(argv, kwargs):
        calls.append(list(argv))
        return (0, dc_report(extra_sources=["src/a.ts", ".dependency-cruiser.js"]), "")

    out = lens().collect(ctx(repo, tmp_path, run=make_run(handler)))
    assert st(out) == "collected"
    assert out["candidates"] == []
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert calls, "data-gatherer must still invoke depcruise"
    for argv in calls:
        assert "--config" not in argv
        assert "--no-config" in argv
        assert "--" in argv


# ======================================================================================
# OWNER-REQUIRED RCE regressions — permanent standing proof (re-ported through the seam)
# ======================================================================================
# Confirmed remote-code-execution escapes were found during review. These tests failing
# are an EMERGENCY: a read-only Guardian sweep must never execute code from the repo it
# sweeps. Each keeps a positive control proving the payload is still live (gated on the
# real tool). The other four env/invocation-stack RCE regressions
# (`..._config_dir_trap_...`, `..._node_options_...`, `..._path_never_absolutized_...`,
# `..._node_path_inside_repo_...`) are DROPPED here: that escape class is now owned by
# `guardian_tools` (neutral cwd, sanitized env, repo-local rejection) and covered by
# `test_guardian_tools.py`.

RCE_MARKER_NAME = "GUARDIAN_RCE_REGRESSION_MARKER"


def _resolve_collector_bin(name):
    """Locate a collector binary for positive-control gates.

    `shutil.which` alone misses --user installs whose scripts dir is off PATH.
    """
    found = shutil.which(name)
    if found:
        return found
    if name != adapters.IMPORT_LINTER_BIN:
        return None
    try:
        from importlib.metadata import distribution
        dist = distribution("import-linter")
        for f in dist.files or ():
            rel = str(f).replace("\\", "/")
            if rel.endswith("/lint-imports") or f.name == "lint-imports":
                path = os.path.realpath(str(dist.locate_file(f)))
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
    except Exception:
        return None
    return None


def _assert_hardened_depcruise_argv(argv):
    """Structural: `--no-config`, `--` end-of-options, no bare `--config` flag, safe operands."""
    assert "--no-config" in argv
    assert "--" in argv, "end-of-options separator missing — --config-dir trap reopens"
    sep = argv.index("--")
    before = argv[:sep]
    assert "--config" not in before, (
        "--config flag before end-of-options — trap reopens: %r" % before)
    operands = argv[sep + 1:]
    assert operands, "repo operands missing after --"
    for op in operands:
        assert not op.startswith("-"), op
        # collect-path operands are absolute under the swept repo
        assert os.path.isabs(op), op


def test_rce_regression_depcruise_webpack_config_never_executes_through_the_seam(tmp_path):
    """EMERGENCY regression — Escape 1: dependency-cruiser `webpackConfig` RCE.

    A declarative `.dependency-cruiser.json` can set `options.webpackConfig.fileName`
    to a repo `webpack.config.js` whose top level runs code. The lens passes no repo
    config (`--no-config`, absolute operands) so the config is never discovered/executed;
    the marker must not appear and the repo's vocabulary is never surfaced.
    """
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    write(repo, "src/a.js", "export const a = 1;\n")
    write(repo, "webpack.config.js",
          "require('fs').writeFileSync(%r, 'webpack-config-executed\\n');\n"
          "module.exports = {};\n" % RCE_MARKER_NAME)
    write(repo, ".dependency-cruiser.json", json.dumps({
        "forbidden": [{"name": "no-cross", "from": {}, "to": {}}],
        "options": {"webpackConfig": {"fileName": "webpack.config.js"}},
    }))
    assert not os.path.exists(marker)

    # Structural (always runs, non-vacuous): argv is hardened; the config never reaches it.
    captured = []

    def handler(argv, kwargs):
        captured.append(list(argv))
        return (0, dc_report(extra_sources=["src/a.js", "webpack.config.js"]), "")

    out = lens().collect({"cwd": repo, "root": root, "run": make_run(handler),
                          "prevDigest": None})
    assert not os.path.exists(marker), (
        "EMERGENCY: lens collect executed repo webpack.config.js "
        "(marker %r appeared)" % marker)
    assert captured, "collector must have been invoked"
    for argv in captured:
        _assert_hardened_depcruise_argv(argv)
    assert st(out) == "collected"
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert out["candidates"] == []

    # Real tool THROUGH THE SEAM (no injected run → guardian_tools.invoke): --no-config
    # means the repo config is never discovered, so the payload stays inert.
    depcruise = _resolve_collector_bin(adapters.DEPCRUISE_BIN)
    if depcruise is None:
        pytest.skip("dependency-cruiser not installed (real-seam run + positive control gated)")
    lens().collect({"cwd": repo, "root": root, "prevDigest": None})
    assert not os.path.exists(marker), (
        "EMERGENCY: real-seam collect executed repo webpack.config.js "
        "(marker %r appeared)" % marker)

    # Positive control OUTSIDE the lens path: the payload IS live when a config is passed.
    assert not os.path.exists(marker)
    subprocess.run(
        [depcruise, "--config", ".dependency-cruiser.json",
         "--output-type", "json", "src"],
        cwd=repo, capture_output=True, text=True, timeout=60, check=False)
    assert os.path.isfile(marker), (
        "positive control failed: unsanitized depcruise did not execute "
        "webpack.config.js — payload is dead, test proves nothing")


def test_rce_regression_import_linter_contract_types_never_imports_repo_code(tmp_path):
    """EMERGENCY regression — Escape 2: import-linter `contract_types` RCE.

    A repo config registering `contract_types = pwn: app.payload.Attack` causes
    import-linter to import that module. The Python path is an AST census that NEVER
    spawns lint-imports; the marker must not appear, candidates stay empty, and the
    deferral note is present.
    """
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    marker = os.path.join(repo, RCE_MARKER_NAME)
    write(repo, "app/__init__.py", "")
    write(repo, "app/payload.py",
          "open(%r, 'w').write('contract-types-executed\\n')\n"
          "class Attack:\n    pass\n" % RCE_MARKER_NAME)
    write(repo, "setup.cfg",
          "[importlinter]\n"
          "root_package = app\n"
          "contract_types =\n"
          "    pwn: app.payload.Attack\n"
          "\n"
          "[importlinter:contract:p]\n"
          "name = Pwn\n"
          "type = pwn\n"
          "modules =\n"
          "    app\n")
    assert not os.path.exists(marker)

    calls = []

    def handler(argv, kwargs):
        calls.append(list(argv))
        raise AssertionError("collector must not run when vocabulary is deferred")

    out = lens().collect({"cwd": repo, "root": root, "run": make_run(handler),
                          "prevDigest": None})
    assert not os.path.exists(marker), (
        "EMERGENCY: lens collect imported repo contract_types payload "
        "(marker %r appeared)" % marker)
    assert calls == [], "Python side must not invoke lint-imports while deferred"
    assert st(out) == "collected"
    assert out["candidates"] == []
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert out["digest"]["declaredVocabulary"]["note"] == glc.VOCABULARY_DEFERRED_NOTE
    assert out["digest"]["declaredVocabulary"]["declared"] is False

    # Positive control OUTSIDE the lens path: invoking the tool with the unsanitized repo
    # config imports app.payload and creates the marker (proves the payload is live).
    lint_imports = _resolve_collector_bin(adapters.IMPORT_LINTER_BIN)
    if lint_imports is None:
        pytest.skip("import-linter not installed (positive control gated)")
    assert not os.path.exists(marker)
    subprocess.run(
        [lint_imports, "--config", "setup.cfg", "--no-cache"],
        cwd=repo, capture_output=True, text=True, timeout=60, check=False)
    assert os.path.isfile(marker), (
        "positive control failed: unsanitized lint-imports did not import "
        "app.payload — payload is dead, test proves nothing")


# ======================================================================================
# 5. the findings bar
# ======================================================================================

def _bar_repo(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    for rel in ("src/features/checkout/pay.ts", "src/features/catalog/list.ts",
                "src/features/catalog/list.d.ts", "src/features/catalog/list.test.ts",
                "src/lib/fetcher.ts", "src/generated/api.ts"):
        write(repo, rel)
    return repo


BAR_EDGES = [
    # eligible feature→feature edge
    ("src/features/checkout/pay.ts", "src/features/catalog/list.ts"),
    # .d.ts / declaration-only
    ("src/features/checkout/pay.ts", "src/features/catalog/list.d.ts"),
    # type-only import
    ("src/features/checkout/pay.ts", "src/features/catalog/list.ts",
     ["local", "type-only", "import"]),
    # test plumbing
    ("src/features/catalog/list.test.ts", "src/features/checkout/pay.ts"),
    # lib wrapper target
    ("src/features/checkout/pay.ts", "src/lib/fetcher.ts"),
    # generated
    ("src/features/checkout/pay.ts", "src/generated/api.ts"),
]
BAR_VIOLATIONS = [(e[0], e[1], "no-cross-feature") for e in BAR_EDGES]


def test_dts_test_and_wrapper_edges_are_digest_data_never_candidates(tmp_path):
    """Vocabulary deferred ⇒ surface nothing; excluded edges remain digest DATA."""
    repo = _bar_repo(tmp_path)
    run = depcruise_run(dc_report(edges=BAR_EDGES, violations=BAR_VIOLATIONS,
                                  rule_set=DEFAULT_RULE_SET))
    out = lens().collect(ctx(repo, tmp_path, run=run))

    assert out["candidates"] == []
    vocab = out["digest"]["declaredVocabulary"]
    assert vocab["declared"] is False
    assert vocab["deferred"] is True
    assert vocab["note"] == glc.VOCABULARY_DEFERRED_NOTE
    excluded = out["digest"]["excludedByReason"]
    assert excluded[glc.EXCLUSION_DECLARATION] >= 1
    assert excluded[glc.EXCLUSION_TYPE_ONLY] >= 1
    assert excluded[glc.EXCLUSION_TEST_PLUMBING] >= 1
    assert excluded[glc.EXCLUSION_WRAPPER] >= 1
    assert excluded[glc.EXCLUSION_GENERATED] >= 1
    # every excluded edge is still DATA — it is in the matrix and the counters
    assert out["digest"]["counters"]["edges"] == len(BAR_EDGES)
    assert out["digest"]["counters"]["excludedByBar"] == len(BAR_EDGES) - 1
    assert out["digest"]["counters"]["eligible"] == 1
    assert out["digest"]["counters"]["surfaced"] == 0
    assert sum(out["digest"]["matrix"].values()) == len(BAR_EDGES)


@pytest.mark.parametrize("frm,to,types,reason", [
    ("src/f/a.ts", "src/f2/b.d.ts", [], glc.EXCLUSION_DECLARATION),
    ("src/f/a.ts", "src/f2/b.ts", ["type-only"], glc.EXCLUSION_TYPE_ONLY),
    ("src/f/a.test.ts", "src/f2/b.ts", [], glc.EXCLUSION_TEST_PLUMBING),
    ("src/f/a.ts", "src/__tests__/b.ts", [], glc.EXCLUSION_TEST_PLUMBING),
    ("src/f/a.ts", "src/generated/b.ts", [], glc.EXCLUSION_GENERATED),
    ("src/f/a.ts", "src/lib/b.ts", [], glc.EXCLUSION_WRAPPER),
    ("src/f/a.ts", "src/f2/utils.ts", [], glc.EXCLUSION_WRAPPER),
    ("pkg/db/a.py", "pkg/db/b.py", [], glc.EXCLUSION_INTRA_CLUSTER),
    ("src/f/a.ts", "src/f2/b.ts", [], None),
])
def test_eligibility_filter_rows(frm, to, types, reason):
    fc = glc.cluster_key(frm, glc.ROOT_WORKSPACE)
    tc = glc.cluster_key(to, glc.ROOT_WORKSPACE)
    assert glc.exclusion_reason(frm, to, types, fc, tc) == reason


def test_every_exclusion_the_filter_can_emit_is_a_documented_reason(tmp_path):
    repo = _bar_repo(tmp_path)
    run = depcruise_run(dc_report(edges=BAR_EDGES, violations=BAR_VIOLATIONS,
                                  rule_set=DEFAULT_RULE_SET))
    digest = lens().collect(ctx(repo, tmp_path, run=run))["digest"]
    assert set(digest["excludedByReason"]) <= set(glc.EXCLUSION_REASONS)
    assert len(set(glc.EXCLUSION_REASONS)) == len(glc.EXCLUSION_REASONS)


def test_no_declared_boundary_vocabulary_surfaces_nothing(tmp_path):
    """Binding conservative fallback: guessing walls from folder names is exactly the
    plausible-but-wrong rule derivation this project rejected.

    Owner-deferred vocabulary must be reported as deferred — not as "the repo declared
    nothing" after a check we did not perform.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/features/checkout/pay.ts")
    write(repo, "src/features/catalog/list.ts")
    edges = [("src/features/checkout/pay.ts", "src/features/catalog/list.ts")]
    run = depcruise_run(dc_report(edges=edges))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert out["candidates"] == []
    vocab = out["digest"]["declaredVocabulary"]
    assert vocab["declared"] is False
    assert vocab["deferred"] is True
    assert vocab["note"] == glc.VOCABULARY_DEFERRED_NOTE
    assert out["digest"]["counters"]["edges"] == 1  # still collected as DATA


def test_deferred_vocabulary_never_surfaces_candidates_even_with_tool_violations(tmp_path):
    """Violations in a collector report are not findings while vocabulary is deferred.

    Surfacing from tool-reported rule hits without reading declared config would re-open
    the removed surface by another door.
    """
    repo = _bar_repo(tmp_path)
    run = depcruise_run(dc_report(edges=BAR_EDGES, violations=BAR_VIOLATIONS,
                                  rule_set=DEFAULT_RULE_SET))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert out["candidates"] == []
    assert out["digest"]["eligible"] == {}
    assert out["digest"]["counters"]["surfaced"] == 0
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert out["digest"]["checkTheCheck"]["status"] == glc.CHECK_DEFERRED
    assert out["digest"]["checkTheCheck"]["detail"] == glc.CHECK_THE_CHECK_DEFERRED_NOTE


# ======================================================================================
# 6. the orphan-id leak (driven through the REAL sweep)
# ======================================================================================

class _NaiveDiffLens(glc.CouplingLens):
    """Control: what a matrix-keyed diff would do. Proves the leak is real, not theory."""

    def diff(self, prev_digest, cur_digest):
        prev = ((prev_digest or {}).get("matrix") or {})
        cur = ((cur_digest or {}).get("matrix") or {})
        new = [glc.make_id(glc.TOOL_TOKEN_JS, *cell.split(glc.EDGE_ARROW))
               for cell in sorted(cur) if cell not in prev]
        return {"new": new, "worsened": [], "resolved": []}


def _leak_setup(tmp_path, the_lens):
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    write(repo, "src/features/checkout/pay.ts")
    write(repo, "src/lib/fetcher.ts")
    # baseline sweep: no edges at all
    baseline = the_lens.collect({"cwd": repo, "root": root, "prevDigest": None,
                                 "run": depcruise_run(dc_report(rule_set=DEFAULT_RULE_SET))})
    gs.write_snapshot_cas(repo, {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION,
        "sweptSha": "baseline",
        "vitals": {},
        "lenses": {the_lens.name: {"collectorVersion": the_lens.collector_version,
                                   "digest": baseline["digest"]}},
    }, None, root=root)
    # this sweep: a brand-new edge that the bar excludes (a lib-wrapper target)
    edges = [("src/features/checkout/pay.ts", "src/lib/fetcher.ts")]
    run = depcruise_run(dc_report(
        edges=edges, violations=[(edges[0][0], edges[0][1], "no-cross-feature")],
        rule_set=DEFAULT_RULE_SET))
    return repo, root, run


def test_digest_only_edge_cannot_surface_through_the_real_sweep(tmp_path):
    the_lens = lens()
    repo, root, run = _leak_setup(tmp_path, the_lens)
    bundle = gsw.collect(repo, lenses=[the_lens], root=root, run=run)
    assert bundle["surfaced"] == []
    assert bundle["funnel"]["malformed"] == []


def test_the_leak_this_guards_is_real_not_theoretical(tmp_path):
    """guardian_sweep fabricates `{"id": cid}` for a diff id with no candidate."""
    naive = _NaiveDiffLens()
    repo, root, run = _leak_setup(tmp_path, naive)
    bundle = gsw.collect(repo, lenses=[naive], root=root, run=run)
    assert [s["id"] for s in bundle["surfaced"]] == [
        "coupling:depcruise:src/features/checkout->src/lib"]
    assert set(bundle["surfaced"][0]) == {"id", "lens", "driftReason"}  # a bare placeholder


def test_diff_returns_only_ids_in_the_current_eligible_index():
    prev = {"eligible": {"coupling:depcruise:a->b": 2}, "matrix": {"a->b": 2}}
    cur = {"eligible": {"coupling:depcruise:a->b": 5},
           "matrix": {"a->b": 5, "x->y": 9, "p->q": 1}}
    d = lens().diff(prev, cur)
    assert d["new"] == []
    assert d["worsened"] == ["coupling:depcruise:a->b"]
    assert d["resolved"] == []
    for key in ("new", "worsened"):
        for cid in d[key]:
            assert cid in cur["eligible"]


def test_diff_new_and_resolved_and_degraded_digests():
    the_lens = lens()
    assert the_lens.diff(None, None) == {"new": [], "worsened": [], "resolved": []}
    d = the_lens.diff({"eligible": {"a": 1}}, {"eligible": {"b": 2}})
    assert d == {"new": ["b"], "worsened": [], "resolved": ["a"]}
    # equal metric is not movement
    assert the_lens.diff({"eligible": {"a": 3}}, {"eligible": {"a": 3}})["worsened"] == []


# ======================================================================================
# 7. the collapse tripwires
# ======================================================================================

def test_module_count_collapse_degrades_with_a_naming_reason(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    for i in range(20):
        write(repo, "src/app/mod%d.ts" % i)
    # dependency-cruiser 18 on an unsupported TypeScript: exit 0, empty stderr, ~nothing
    # parsed. Measured on a real repo: 2 modules against 590 TS sources.
    run = depcruise_run(dc_report(extra_sources=["src/app/mod0.ts"], ts_available=False))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "not-collected"
    assert "collapse" in out["reason"]
    assert "1 parsed of 20 sources" in out["reason"]
    assert "javascript-only" in out["reason"]
    assert out["digest"] is None


def test_per_language_collapse_hidden_inside_a_healthy_total_is_still_caught(tmp_path):
    """A total-vs-total census can be fooled: plenty of JS parses while every TS file
    collapses. Measured shape — a pinned real run parsed 3,324 vendored .js modules."""
    repo = init_calibrated_repo(tmp_path)
    for i in range(30):
        write(repo, "src/legacy/mod%d.js" % i)
    for i in range(20):
        write(repo, "src/app/mod%d.ts" % i)
    parsed = ["src/legacy/mod%d.js" % i for i in range(30)]
    run = depcruise_run(dc_report(extra_sources=parsed, ts_available=False))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "not-collected"
    assert "./ts 0 parsed of 20 sources" in out["reason"]
    # ... and the total (30 of 50) would have looked perfectly healthy
    assert 30 > 50 * glc.COLLAPSE_RATIO


def test_per_workspace_collapse_hidden_inside_a_healthy_total_is_still_caught(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "package.json", '{"name":"root"}\n')
    write(repo, "packages/web/package.json", '{"name":"web"}\n')
    for i in range(30):
        write(repo, "src/mod%d.ts" % i)
    for i in range(20):
        write(repo, "packages/web/src/mod%d.ts" % i)
    parsed = ["src/mod%d.ts" % i for i in range(30)]
    run = depcruise_run(dc_report(extra_sources=parsed))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "not-collected"
    assert "packages/web/ts 0 parsed of 20 sources" in out["reason"]
    # a collapse confined to some workspaces is its own closed-table row
    assert adapters.OUTCOMES["workspace-collapse"][1] in out["reason"]


def test_collapse_rows_route_through_the_closed_outcome_table():
    confined = {"sources": {".": {"ts": 30}, "packages/web": {"ts": 20}}}
    hits = [{"workspace": "packages/web", "language": "ts", "sources": 20, "parsed": 0}]
    assert glc.collapse_outcome(confined, hits) == "workspace-collapse"
    everywhere = {"sources": {".": {"ts": 30}}}
    hits = [{"workspace": ".", "language": "ts", "sources": 30, "parsed": 0}]
    assert glc.collapse_outcome(everywhere, hits) == "module-count-collapse"
    for row in ("workspace-collapse", "module-count-collapse"):
        assert adapters.classify(row)[0] == adapters.DEGRADED


def test_prior_digest_cliff_degrades_via_prev_digest_in_ctx(tmp_path):
    """Prior comes from ctx['prevDigest'] (no store re-read)."""
    repo = init_calibrated_repo(tmp_path)
    for i in range(40):
        write(repo, "src/app/mod%d.ts" % i)
    prev = {"ecosystems": {"js": {"modulesParsed": 980, "sourcesCensused": 40}},
            "counters": {"modulesParsed": 980, "sourcesCensused": 40}}
    parsed = ["src/app/mod%d.ts" % i for i in range(38)]
    run = depcruise_run(dc_report(extra_sources=parsed))
    out = lens().collect(ctx(repo, tmp_path, run=run, prev=prev))
    assert st(out) == "not-collected"
    assert "cliff" in out["reason"]
    assert "980" in out["reason"]


def test_prior_digest_cliff_degrades_through_the_sweep(tmp_path):
    """End-to-end: the sweep threads the prior snapshot digest as ctx['prevDigest']."""
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    for i in range(40):
        write(repo, "src/app/mod%d.ts" % i)
    the_lens = lens()
    prior = {"ecosystems": {"js": {"modulesParsed": 980, "sourcesCensused": 40}},
             "counters": {"modulesParsed": 980, "sourcesCensused": 40}}
    gs.write_snapshot_cas(repo, {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION, "sweptSha": "s", "vitals": {},
        "lenses": {the_lens.name: {"collectorVersion": the_lens.collector_version,
                                   "digest": prior}},
    }, None, root=root)
    parsed = ["src/app/mod%d.ts" % i for i in range(38)]
    run = depcruise_run(dc_report(extra_sources=parsed))
    bundle = gsw.collect(repo, lenses=[the_lens], root=root, run=run)
    degraded = {d["lens"]: d for d in bundle["funnel"]["degradedLenses"]}
    assert the_lens.name in degraded
    assert "cliff" in degraded[the_lens.name]["reason"]


def test_a_genuine_repo_shrink_is_not_a_cliff():
    """A real shrink drops SOURCES too; a broken collector drops only parsed modules."""
    prior = {"counters": {"modulesParsed": 980, "sourcesCensused": 1000}}
    assert glc.detect_cliff(prior, parsed_total=30, sources_total=32) is None
    assert glc.detect_cliff(prior, parsed_total=30, sources_total=990) is not None
    assert glc.detect_cliff(None, 1, 1) is None


def test_collapse_needs_a_meaningful_source_count():
    # Zero parsed against any on-disk sources is always a collapse — even below
    # COLLAPSE_MIN_SOURCES. The threshold applies only to nonzero ratio judgments.
    below = {"sources": {".": {"ts": glc.COLLAPSE_MIN_SOURCES - 1}}}
    assert glc.detect_collapse(below, {".": {"ts": 0}})
    # A nonzero partial parse below the threshold is not a ratio collapse.
    assert glc.detect_collapse(below, {".": {"ts": 1}}) == []
    # At/above the threshold, a ratio hit (parsed <= sources * COLLAPSE_RATIO) collapses.
    at = {"sources": {".": {"ts": max(glc.COLLAPSE_MIN_SOURCES, 10)}}}
    assert glc.detect_collapse(at, {".": {"ts": 1}})
    assert glc.detect_collapse(at, {".": {"ts": 0}})


def test_healthy_parse_does_not_degrade(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    sources = ["src/app/mod%d.ts" % i for i in range(20)]
    for rel in sources:
        write(repo, rel)
    run = depcruise_run(dc_report(extra_sources=sources))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "collected"
    assert out["digest"]["counters"]["modulesParsed"] == 20


# ======================================================================================
# 8. ecosystem presence / partial / Python honesty
# ======================================================================================

def test_flat_layout_python_only_reports_not_analyzable_honestly(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "lib/one.py", "x = 1\n")
    write(repo, "lib/two.py", "import os\n")
    out = lens().collect(ctx(repo, tmp_path))
    assert st(out) == "not-collected"
    assert "not analyzable" in out["reason"]
    assert "flat layout" in out["reason"]
    assert out["candidates"] == []
    assert out["digest"] is None


def test_a_repo_with_no_python_omits_the_python_ecosystem(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/app/main.ts")
    out = lens().collect(ctx(repo, tmp_path,
                             run=depcruise_run(dc_report(extra_sources=["src/app/main.ts"]))))
    assert st(out) == "collected"
    assert "js" in out["digest"]["ecosystems"]
    assert "py" not in out["digest"]["ecosystems"]


def test_a_repo_with_no_javascript_omits_the_js_ecosystem(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/mod.py", "x = 1\n")
    out = lens().collect(ctx(repo, tmp_path))
    assert st(out) == "collected"
    assert "py" in out["digest"]["ecosystems"]
    assert "js" not in out["digest"]["ecosystems"]


def test_a_repo_with_neither_ecosystem_is_not_collected(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "README.md", "# nothing to measure\n")
    out = lens().collect(ctx(repo, tmp_path))
    assert st(out) == "not-collected"
    assert out["digest"] is None
    assert "no JS/TS or Python sources" in out["reason"]


def test_a_flat_python_side_degrades_to_partial_without_erasing_js(tmp_path):
    """One ecosystem degrading while the other collects → PARTIAL (reason names the
    degraded side); the healthy side's data survives in the merged digest."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "lib/one.py", "x = 1\n")  # flat python (no __init__)
    write(repo, "src/app/main.ts")
    run = depcruise_run(dc_report(extra_sources=["src/app/main.ts"]))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "partial"
    assert "not analyzable" in out["reason"] or "flat layout" in out["reason"]
    assert out["digest"] is not None
    assert out["digest"]["ecosystems"]["js"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["py"]["status"] == "not-collected"


def test_packaged_python_collects_data_only_while_vocabulary_is_deferred(tmp_path):
    """Even with a packaged tree and a broken-looking contract on disk, surfaces nothing.

    Deferred must be honest — not conflated with "checked and clean." The Python side
    never spawns lint-imports.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/api/__init__.py", "")
    write(repo, "mypkg/db/__init__.py", "")
    write(repo, "mypkg/api/handlers.py", "from mypkg.db import conn\n")
    write(repo, "mypkg/db/conn.py", "conn = 1\n")
    write(repo, "mypkg/db/bad.py", "from mypkg.api import handlers\n")
    write(repo, "setup.cfg", "[importlinter]\nroot_package = mypkg\n")
    calls = []

    def handler(argv, kwargs):
        calls.append(list(argv))
        raise AssertionError("Python side must not spawn while vocabulary deferred")

    out = lens().collect(ctx(repo, tmp_path, run=make_run(handler)))
    assert calls == [], "Python side must not invoke lint-imports while deferred"
    assert out["candidates"] == []
    vocab = out["digest"]["declaredVocabulary"]
    assert vocab["declared"] is False
    assert vocab["deferred"] is True
    assert vocab["note"] == glc.VOCABULARY_DEFERRED_NOTE
    assert out["digest"]["checkTheCheck"]["status"] == glc.CHECK_DEFERRED
    assert out["digest"]["versions"]["py"]["parseMode"] == "ast-census-only"
    assert out["digest"]["counters"]["edges"] >= 1


def test_python_side_never_invokes_import_linter_while_vocabulary_deferred(tmp_path):
    """Zero-analyzed collapse via import-linter is unreachable: the tool is not invoked.

    AST census supplies the matrix; a missing/zero import-linter run is not a clean
    claim — vocabulary deferral is recorded explicitly.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    for i in range(8):
        write(repo, "mypkg/mod%d.py" % i, "x = 1\n")
    write(repo, "setup.cfg", "[importlinter]\nroot_package = mypkg\n")
    calls = []
    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda a, k: calls.append(a) or (0, "", ""))))
    assert calls == []
    assert st(out) == "collected"
    assert out["candidates"] == []
    assert out["digest"]["declaredVocabulary"]["deferred"] is True
    assert out["digest"]["versions"]["py"]["parseMode"] == "ast-census-only"
    assert out["digest"]["counters"]["modulesParsed"] == 9


def test_python_ast_census_leaves_the_repo_byte_identical(tmp_path):
    """Python collect is AST-only while vocabulary is deferred — never mutates the repo."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/api.py", "from pkg import db  # ast-census-byte-identical\n")
    write(repo, "pkg/db.py", "x = 1  # ast-census-byte-identical\n")
    write(repo, "setup.cfg", "[importlinter]\nroot_package = pkg\n\n"
                             "[importlinter:contract:l]\nname = L\ntype = layers\n"
                             "layers =\n    pkg.api\n    pkg.db\n")
    before = tree(repo)
    assert b"ast-census-byte-identical" in before["pkg/api.py"]
    assert b"ast-census-byte-identical" in before["pkg/db.py"]
    assert b"root_package = pkg" in before["setup.cfg"]
    calls = []
    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda a, k: calls.append(a) or (0, "", ""))))
    assert calls == [], "Python side must not spawn while vocabulary is deferred"
    assert tree(repo) == before
    assert adapters.cache_paths_present(repo) == []
    assert out["digest"]["versions"]["py"]["parseMode"] == "ast-census-only"


# ======================================================================================
# 9. identity stability
# ======================================================================================

def test_id_survives_a_line_level_change():
    """Identity is cluster-scoped; line edits inside files do not change clusters."""
    before = glc.make_id(
        glc.TOOL_TOKEN_JS,
        glc.cluster_key("src/checkout/pay.ts", glc.ROOT_WORKSPACE),
        glc.cluster_key("src/catalog/list.ts", glc.ROOT_WORKSPACE),
        rule="no-cross-feature")
    after = glc.make_id(
        glc.TOOL_TOKEN_JS,
        glc.cluster_key("src/checkout/pay.ts", glc.ROOT_WORKSPACE),
        glc.cluster_key("src/catalog/list.ts", glc.ROOT_WORKSPACE),
        rule="no-cross-feature")
    assert before == after == (
        "coupling:depcruise:no-cross-feature:src/checkout->src/catalog")


def test_rename_boundary_behaves_as_documented():
    """PRESERVED: a file rename inside the cluster. NOT PRESERVED: the cluster moved."""
    base = glc.make_id(
        glc.TOOL_TOKEN_JS,
        glc.cluster_key("src/checkout/pay.ts", glc.ROOT_WORKSPACE),
        glc.cluster_key("src/catalog/list.ts", glc.ROOT_WORKSPACE),
        rule="no-cross-feature")
    renamed_file = glc.make_id(
        glc.TOOL_TOKEN_JS,
        glc.cluster_key("src/checkout/checkout_page.ts", glc.ROOT_WORKSPACE),
        glc.cluster_key("src/catalog/list.ts", glc.ROOT_WORKSPACE),
        rule="no-cross-feature")
    assert renamed_file == base

    moved_cluster = glc.make_id(
        glc.TOOL_TOKEN_JS,
        glc.cluster_key("src/checkout/pay.ts", glc.ROOT_WORKSPACE),
        glc.cluster_key("src/products/list.ts", glc.ROOT_WORKSPACE),
        rule="no-cross-feature")
    assert moved_cluster != base


def test_ids_follow_the_documented_grammar_and_normalization():
    # Grammar literal lives in ID_GRAMMAR; docs are drift-guarded in
    # test_guardian_contract_sync.test_id_grammar_doc_copies_match_lib_home_and_make_id.
    assert glc.ID_GRAMMAR
    assert "<tool>" in glc.ID_GRAMMAR and "<rule>" in glc.ID_GRAMMAR
    cid = glc.make_id(glc.TOOL_TOKEN_JS, "src/a", "src/b", rule="no-cross-feature")
    lens_token, tool_token, rule, location = cid.split(glc.ID_SEP)
    assert lens_token == glc.LENS_FAMILY
    assert tool_token == glc.TOOL_TOKEN_JS
    assert rule == "no-cross-feature"
    assert location == "src/a" + glc.EDGE_ARROW + "src/b"
    # Rule is part of identity when present; omitting it yields the legacy 3-segment form.
    bare = glc.make_id(glc.TOOL_TOKEN_JS, "src/a", "src/b")
    assert bare == glc.ID_SEP.join(
        (glc.LENS_FAMILY, glc.TOOL_TOKEN_JS, "src/a" + glc.EDGE_ARROW + "src/b"))
    # separator + case normalization are stated and applied. NOTE: on the POSIX test
    # host `/` is the only path separator; a literal backslash is DATA, preserved for
    # identity (see test_backslash_dir_name_stays_distinct_from_nested_dir_on_posix),
    # so the normalization case uses forward slashes.
    assert glc.cluster_key("SRC/Features/Checkout/Pay.ts", glc.ROOT_WORKSPACE) == \
        "src/features/checkout"
    # workspace-qualified: the same inner path in two workspaces is two identities
    assert glc.cluster_key("packages/web/src/a/x.ts", "packages/web") != \
        glc.cluster_key("packages/api/src/a/x.ts", "packages/api")


def test_wall_key_is_a_deterministic_seam_for_recurrence():
    a = glc.make_wall_key(glc.TOOL_TOKEN_JS, "no-cross-feature", "src/a", "src/b")
    b = glc.make_wall_key(glc.TOOL_TOKEN_JS, "no-cross-feature", "src/a", "src/b")
    assert a == b
    assert a != glc.make_wall_key(glc.TOOL_TOKEN_JS, "other-rule", "src/a", "src/b")


# ======================================================================================
# 10. metric drives ledger re-raise
# ======================================================================================

def test_metric_is_a_scalar_number():
    """Eligible-index metrics must be numeric scalars (ledger materially_worsened)."""
    metric = 3
    assert isinstance(metric, (int, float))
    assert not isinstance(metric, bool)
    cand = {
        "id": "coupling:depcruise:no-cross-feature:src/checkout->src/catalog",
        "metric": metric,
    }
    assert guardian_ledger.materially_worsened(
        cand, {"disposition": "declined", "metricAtDisposition": 3}) is False


def test_metric_drives_materially_worsened():
    """Without a numeric metric a declined wall stays suppressed forever as coupling
    grows (guardian_ledger.materially_worsened)."""
    cid = "coupling:depcruise:no-cross-feature:src/checkout->src/catalog"
    rec = {"disposition": "declined", "metricAtDisposition": 4}
    assert guardian_ledger.materially_worsened({"id": cid, "metric": 4}, rec) is False
    assert guardian_ledger.materially_worsened({"id": cid, "metric": 6}, rec) is True


def test_deferred_vocabulary_cannot_resurface_declined_walls_via_collect(tmp_path):
    """While vocabulary is deferred, collect surfaces nothing — declined walls stay quiet.

    That is honest deferral, not silent suppression of a finding we claimed to check.
    """
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    write(repo, "src/catalog/list.ts")
    the_lens = lens()
    cid = "coupling:depcruise:no-cross-feature:src/checkout->src/catalog"
    write_ledger(tmp_path, [{"id": cid, "disposition": "declined", "issue": None,
                             "metricAtDisposition": 2}], root=root)
    baseline_digest = {"eligible": {cid: 2}, "counters": {"modulesParsed": 3,
                                                          "sourcesCensused": 3}}
    gs.write_snapshot_cas(repo, {
        "schemaVersion": gs.SNAPSHOT_SCHEMA_VERSION, "sweptSha": "s", "vitals": {},
        "lenses": {the_lens.name: {"collectorVersion": the_lens.collector_version,
                                   "digest": baseline_digest}},
    }, None, root=root)

    edges, viols = [], []
    for i in range(5):
        src = "src/checkout/pay%d.ts" % i
        write(repo, src)
        edges.append((src, "src/catalog/list.ts"))
        viols.append((src, "src/catalog/list.ts", "no-cross-feature"))
    bundle = gsw.collect(
        repo, lenses=[the_lens], root=root,
        run=depcruise_run(dc_report(edges=edges, violations=viols,
                                    rule_set=DEFAULT_RULE_SET)))
    assert bundle["surfaced"] == []
    # Prove the lens collected data and recorded the deferral honestly.
    digest = bundle["nextSnapshot"]["lenses"][the_lens.name]["digest"]
    assert digest["declaredVocabulary"]["deferred"] is True
    assert digest["counters"]["edges"] == 5
    assert digest["counters"]["surfaced"] == 0


# ======================================================================================
# 11. the digest
# ======================================================================================

def test_digest_is_kb_scale_and_carries_resolved_versions(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    edges = []
    for i in range(400):
        src = "src/f%d/a.ts" % i
        dst = "src/g%d/b.ts" % i
        write(repo, src)
        write(repo, dst)
        edges.append((src, dst))
    run = depcruise_run(dc_report(edges=edges))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    digest = out["digest"]
    size = len(json.dumps(digest))
    assert size < glc.DIGEST_MAX_BYTES, size
    assert digest["versions"]["js"]["toolVersionResolved"] == "18.1.0"
    assert digest["versions"]["js"]["typescriptVersionResolved"] == "5.9.3"
    assert digest["versions"]["js"]["toolVersionPinned"] == adapters.DEPCRUISE_PIN
    assert digest["versions"]["js"]["typescriptVersionPinned"] == adapters.TYPESCRIPT_PIN
    assert digest["versions"]["js"]["parseMode"] == "typescript"
    assert digest["matrixTruncated"] is True
    assert len(digest["matrix"]) == glc.MAX_MATRIX_CELLS


def test_matrix_hash_covers_the_full_matrix_not_the_truncated_one():
    """Truncation must not hide drift: identical top cells, different low-ranked tails.

    A mutant that hashed only `_truncate_matrix(matrix)[0]` would still pass a test
    that merely compares two small matrices — both fit under MAX_MATRIX_CELLS. Crossing
    the boundary with a shared top and divergent tails kills that mutant.
    """
    n = glc.MAX_MATRIX_CELLS
    top = {"cell-%03d->x" % i: 100 for i in range(n)}
    a = dict(top)
    a["tail-a->z"] = 1
    b = dict(top)
    b["tail-b->z"] = 1
    stored_a, trunc_a = glc._truncate_matrix(a)
    stored_b, trunc_b = glc._truncate_matrix(b)
    assert trunc_a is True and trunc_b is True
    assert stored_a == stored_b
    assert glc.matrix_hash(a) != glc.matrix_hash(b)


def test_digest_counters_make_the_drift_metrics_derivable(tmp_path):
    repo = _bar_repo(tmp_path)
    run = depcruise_run(dc_report(edges=BAR_EDGES, violations=BAR_VIOLATIONS,
                                  rule_set=DEFAULT_RULE_SET))
    digest = lens().collect(ctx(repo, tmp_path, run=run))["digest"]
    counters = digest["counters"]
    for key in ("edges", "eligible", "surfaced", "excludedByBar", "modulesParsed",
                "sourcesCensused"):
        assert isinstance(counters[key], int), key
    assert counters["edges"] == counters["eligible"] + counters["excludedByBar"]
    assert counters["surfaced"] == 0  # vocabulary deferred
    assert digest["matrixHash"]
    assert digest["perWorkspace"]["."]["sources"]
    assert digest["declaredVocabulary"]["deferred"] is True


def test_digest_drift_bearing_fields_carry_no_absolute_machine_paths(tmp_path):
    """The identity / drift-bearing digest fields must be repo-relative and portable.

    Rewritten for the adapted contract: like every guardian lens (deps, deadcode), the
    per-ecosystem `argv` is provenance and carries the absolute repo operand
    run_tool/guardian_tools requires — that field is excluded here. What MUST stay
    path-clean is everything drift compares across machines/checkouts: the matrix (whose
    keys feed matrixHash), the eligible index, counters, and perWorkspace. A machine path
    leaking into any of those would make the same repo diff differently per checkout.
    """
    repo = _bar_repo(tmp_path)
    run = depcruise_run(dc_report(edges=BAR_EDGES, violations=BAR_VIOLATIONS,
                                  rule_set=DEFAULT_RULE_SET))
    digest = lens().collect(ctx(repo, tmp_path, run=run))["digest"]
    # Sanity: the provenance argv IS where the absolute operand lives (non-vacuous — proves
    # the exclusion below is load-bearing, not hiding a clean-everywhere result).
    assert str(tmp_path) in json.dumps(digest["ecosystems"]["js"]["argv"])
    drift_bearing = {k: v for k, v in digest.items() if k != "ecosystems"}
    drift_bearing["ecosystems"] = {
        eco: {k: v for k, v in section.items() if k != "argv"}
        for eco, section in digest["ecosystems"].items()
    }
    assert str(tmp_path) not in json.dumps(drift_bearing)
    # matrixHash is computed over the full (pre-truncation) matrix keys — those are the
    # repo-relative clusters, never an absolute path.
    for cell in digest["matrix"]:
        assert str(tmp_path) not in cell


def test_digest_round_trips_through_a_real_finalize(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = store(tmp_path)
    write(repo, "src/app/main.ts")
    the_lens = lens()
    run = depcruise_run(dc_report(extra_sources=["src/app/main.ts"]))
    bundle = gsw.collect(repo, lenses=[the_lens], root=root, run=run)
    assert gsw.finalize(repo, bundle, [], root=root)["ok"] is True
    snap = gs.read_snapshot(repo, root=root)
    assert snap["lenses"][the_lens.name]["digest"]["schemaVersion"] == \
        glc.DIGEST_SCHEMA_VERSION


# ======================================================================================
# 12. check-the-check — owner-deferred
# ======================================================================================

def test_check_the_check_is_recorded_as_deferred_not_as_a_live_or_dead_verdict(tmp_path):
    """Digest must say deferred — never CHECK_ALIVE / dead statuses we did not compute."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/app/main.ts")
    write(repo, ".dependency-cruiser.json", json.dumps({
        "forbidden": [{"name": "no-cross-feature"}],
    }))
    run = depcruise_run(dc_report(extra_sources=["src/app/main.ts"],
                                  rule_set={"forbidden": []}))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    check = out["digest"]["checkTheCheck"]
    assert check == glc.deferred_check_the_check()
    assert check["status"] == glc.CHECK_DEFERRED
    assert check["detail"] == glc.CHECK_THE_CHECK_DEFERRED_NOTE
    assert [c for c in out["candidates"] if c.get("advisory")] == []
    assert out["candidates"] == []


def test_adopted_config_on_disk_does_not_produce_dead_check_candidates(tmp_path):
    """Configs on disk are invisible to the deferred lens — no dead-check advisories."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/app/main.ts")
    write(repo, ".dependency-cruiser.json", json.dumps({"forbidden": []}))
    write(repo, "dependency-cruiser-known-violations.json",
          json.dumps([{"from": "a", "to": "b", "rule": "no-cross-feature"}] * 12))
    run = depcruise_run(dc_report(extra_sources=["src/app/main.ts"],
                                  rule_set=DEFAULT_RULE_SET))
    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert out["digest"]["checkTheCheck"]["status"] == glc.CHECK_DEFERRED
    assert out["digest"]["checkTheCheck"]["unenforced"] == 0
    assert out["candidates"] == []


def test_check_the_check_never_runs_or_enforces_anything(tmp_path):
    """Advisory-only doctrine — and while deferred, no second invocation at all."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/app/main.ts")
    write(repo, ".dependency-cruiser.json", json.dumps({
        "forbidden": [{"name": "no-cross-feature"}],
    }))
    spawned = []
    run = make_run(lambda argv, kw: spawned.append(argv) or (
        0, dc_report(extra_sources=["src/app/main.ts"], rule_set=DEFAULT_RULE_SET), ""))
    lens().collect(ctx(repo, tmp_path, run=run))
    assert len(spawned) == 1  # one read-only cruise, nothing else
    assert all("--fix" not in a and "--write" not in a for a in spawned[0])
    assert "--config" not in spawned[0]
    assert "--no-config" in spawned[0]


# ======================================================================================
# 13. census (lens-owned ecosystem detection)
# ======================================================================================

def test_census_is_recursive_and_finds_nested_workspaces(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "packages/web/package.json", "{}")
    write(repo, "packages/web/src/a.ts")
    write(repo, "packages/api/package.json", "{}")
    write(repo, "packages/api/src/b.js")
    got = census_at(repo, "js")
    assert set(got["workspaces"]) == {".", "packages/web", "packages/api"}
    assert got["sources"]["packages/web"] == {"ts": 1}
    assert got["sources"]["packages/api"] == {"js": 1}
    # the sweep's root-only manifest detection would have found nothing here
    assert gsw._present_root_manifests(repo) == set()


def test_census_never_walks_into_vendored_trees(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a.ts")
    write(repo, "node_modules/leftpad/index.js")
    write(repo, "dist/bundle.js")
    got = census_at(repo, "js")
    assert got["total"] == 1
    assert "node_modules" in adapters.EXCLUDED_DIR_NAMES


def test_declaration_files_are_censused_as_typescript(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/types.d.ts")
    assert census_at(repo, "js")["sources"]["."] == {"ts": 1}


# ======================================================================================
# 14. Python census carried findings (§E) — locked to the correct behavior
# ======================================================================================

def test_python_src_layout_package_resolves_against_its_import_name(tmp_path):
    """§E item 1: a `src/`-layout package imports as `mypkg.api`, not `src.mypkg.api`.

    Verified LIVE-and-handled (`_src_layout_strip` / `_module_path_aliases`). Locks it:
    an edge api→db must resolve even though the files sit under `src/`.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/mypkg/__init__.py", "")
    write(repo, "src/mypkg/api.py", "from mypkg import db\n")
    write(repo, "src/mypkg/db.py", "x = 1\n")
    edges = glc._python_edges(repo, census_at(repo, "py"))
    pairs = {(e["from"], e["to"]) for e in edges["edges"]}
    assert ("src/mypkg/api.py", "src/mypkg/db.py") in pairs, pairs
    assert edges["parseFailures"] == []
    # Full collect agrees (data collected, no candidates).
    out = lens().collect(ctx(repo, tmp_path))
    assert st(out) == "collected"
    assert out["digest"]["counters"]["edges"] >= 1


def test_imported_symbols_do_not_inflate_the_edge_count(tmp_path):
    """§E item 2: two symbols imported from one module = ONE dependency edge, not three.

    `_imported_modules` emits symbol-qualified names but `_resolve_module` longest-prefix
    matches them onto the real module and `_python_edges` dedupes (seen_edges). LIVE-and-
    handled; locked so a regression that counts symbols as edges fails here.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/api.py", "alpha = 1\nbeta = 2\n")
    write(repo, "mypkg/consumer.py", "from mypkg.api import alpha, beta\n")
    edges = glc._python_edges(repo, census_at(repo, "py"))
    consumer_edges = [e for e in edges["edges"]
                      if e["from"] == "mypkg/consumer.py"]
    assert len(consumer_edges) == 1, consumer_edges
    assert consumer_edges[0]["to"] == "mypkg/api.py"


def test_census_preserves_on_disk_case_for_case_sensitive_filesystems(tmp_path):
    """§E item 3: identity lower-casing must not break filesystem access.

    `census` keeps ORIGINAL case for the path it opens (`_rel_posix`), lowering only at
    identity sites (`_norm_rel`). LIVE-and-handled; a regression that lower-cased the
    census path would fail to open a mixed-case file on a case-sensitive filesystem.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "MyPkg/__init__.py", "")
    write(repo, "MyPkg/Api.py", "from MyPkg import Db\n")
    write(repo, "MyPkg/Db.py", "x = 1\n")
    census = census_at(repo, "py")
    censused = {rel for _ws, rel, _lang in census["files"]}
    assert "MyPkg/Api.py" in censused  # original case preserved
    edges = glc._python_edges(repo, census)
    assert edges["parseFailures"] == [], edges["parseFailures"]
    assert edges["nonRegular"] == []
    pairs = {(e["from"], e["to"]) for e in edges["edges"]}
    assert ("MyPkg/Api.py", "MyPkg/Db.py") in pairs, pairs
    # identity/cluster keys are still lower-cased
    assert glc.cluster_key("MyPkg/Api.py", glc.ROOT_WORKSPACE) == "mypkg"


# ======================================================================================
# 15. Python census I/O safety (symlink / FIFO / per-file + aggregate byte caps)
# ======================================================================================

def test_python_census_dev_zero_symlink_and_fifo_degrade_without_hanging(tmp_path):
    """`/dev/zero` symlink (and FIFO when available) must degrade, not hang/OOM.

    Bounded: collect must finish under a hard wall-clock cap. Do not open the special
    file; degrade honestly when non-regular sources are found.
    """
    import concurrent.futures

    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/ok.py", "x = 1\n")
    zero_link = os.path.join(repo, "mypkg", "zero.py")
    try:
        os.symlink("/dev/zero", zero_link)
    except OSError as exc:
        pytest.skip("cannot create /dev/zero symlink: %s" % exc)
    assert os.path.islink(zero_link)

    fifo_path = os.path.join(repo, "mypkg", "fifo.py")
    fifo_ok = False
    try:
        os.mkfifo(fifo_path)
        fifo_ok = True
    except (OSError, AttributeError):
        pass  # platform may lack FIFOs — symlink case still covers the hang class

    def _collect():
        return lens().collect(ctx(
            repo, tmp_path,
            run=make_run(lambda a, k: (_ for _ in ()).throw(
                AssertionError("Python side must not spawn")))))

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_collect)
        try:
            out = fut.result(timeout=5)
        except concurrent.futures.TimeoutError:
            pytest.fail(
                "Python census hung (>5s) on /dev/zero symlink"
                + (" and FIFO" if fifo_ok else "")
                + " — open() was not refused")
    assert st(out) == "not-collected", out
    assert out["digest"] is None
    assert "non-regular" in out["reason"] or "symlink" in out["reason"]
    # Sanity: the choke-point still collapses any path text in the reason.
    assert "\n" not in out["reason"]


def test_python_census_per_file_byte_cap_degrades_not_silent_truncate(tmp_path, monkeypatch):
    """Oversized regular .py must degrade — never silently truncate the census."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    # Tiny cap so the fixture stays small; production cap is PY_SOURCE_MAX_BYTES.
    monkeypatch.setattr(glc, "PY_SOURCE_MAX_BYTES", 64)
    monkeypatch.setattr(glc, "PY_CENSUS_MAX_BYTES", 10 * 1024)
    write(repo, "mypkg/big.py", "x = %r\n" % ("a" * 200))
    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda a, k: (_ for _ in ()).throw(
            AssertionError("Python side must not spawn")))))
    assert st(out) == "not-collected"
    assert "cap" in out["reason"].lower() or "bytes" in out["reason"]
    assert "per-file cap" in out["reason"]
    assert out["digest"] is None


def test_python_census_aggregate_byte_cap_degrades_not_silent_truncate(tmp_path, monkeypatch):
    """§A carried gap: the AGGREGATE PY_CENSUS_MAX_BYTES cap must also degrade.

    Several files each UNDER the per-file cap whose running total crosses the aggregate
    cap must degrade honestly — a truncated census feeds the collapse tripwire.
    """
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    # Per-file cap comfortably above each file; aggregate cap below their sum.
    monkeypatch.setattr(glc, "PY_SOURCE_MAX_BYTES", 500)
    monkeypatch.setattr(glc, "PY_CENSUS_MAX_BYTES", 600)
    write(repo, "mypkg/big1.py", "x = %r\n" % ("a" * 400))
    write(repo, "mypkg/big2.py", "y = %r\n" % ("b" * 400))
    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda a, k: (_ for _ in ()).throw(
            AssertionError("Python side must not spawn")))))
    assert st(out) == "not-collected"
    assert "aggregate" in out["reason"]
    assert out["digest"] is None


# ======================================================================================
# 16. model-text injection / identity vs display clamp (security seat)
# ======================================================================================

def test_repo_derived_directory_name_cannot_forge_markdown_headings_in_report(tmp_path):
    """Hostile directory name with newlines + `## ` must not introduce report headings.

    Repo-controlled names flow into degraded reasons → funnel → report.md. Without
    `_safe_repo_text`, a committed dirname forges markdown structure the validating
    model and a human read.
    """
    import guardian_report as gr

    repo = init_calibrated_repo(tmp_path)
    # Newline + markdown heading inside a directory name (filesystem-permitting).
    hostile = "pkg\n## forged-heading"
    try:
        os.makedirs(os.path.join(repo, hostile), exist_ok=True)
    except OSError:
        pytest.skip("filesystem rejected dirname with newline/markdown")
    write(repo, os.path.join(hostile, "__init__.py"), "")
    write(repo, os.path.join(hostile, "mod.py"), "x = 1\n")
    # Symlink source forces a degraded collect whose reason embeds the dirname.
    try:
        os.symlink("/dev/zero", os.path.join(repo, hostile, "evil.py"))
    except OSError:
        pytest.skip("symlink to /dev/zero unavailable")

    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda a, k: (_ for _ in ()).throw(
            AssertionError("Python side must not spawn")))))
    assert st(out) == "not-collected"
    reason = out["reason"]
    assert "\n" not in reason
    assert "## " not in reason
    assert "#" not in reason  # neutralised at the choke point
    # Rendered report must not gain a forged heading from the dirname.
    bundle = {
        "committed": "uncommitted",
        "funnel": {
            "raised": {},
            "malformed": [],
            "killedByDrift": [],
            "killedByLedger": [],
            "trackedFiled": [],
            "degradedLenses": [{"lens": glc.LENS_NAME, "reason": reason}],
        },
        "vitalsDelta": {},
        "ledgerStatus": [],
    }
    report = gr.render(bundle, [], {"byId": {}})
    # Stock headings only — no forged "## forged-heading" line.
    heading_lines = [ln for ln in report.splitlines() if ln.startswith("## ")]
    assert "## forged-heading" not in heading_lines
    assert all(not ln.startswith("## forged") for ln in report.splitlines())
    assert hostile not in report
    assert "\n## forged-heading" not in report


def test_identity_encoding_keeps_injection_char_matrix_keys_distinct():
    """Lossy _safe_repo_text must not collapse identity keys or mask matrixHash drift.

    Clusters that differ only in an injection-significant char (``#`` vs ``*``, plus a
    ``<script>``-bearing segment) must survive as distinct matrix / eligible keys, and
    changing one colliding cell's weight must change matrixHash.
    """
    the_lens = glc.LENS
    rows_base = [
        {"fromCluster": "a#", "toCluster": "b", "exclusion": None},
        {"fromCluster": "a*", "toCluster": "b", "exclusion": None},
        {"fromCluster": "pkg/<script>", "toCluster": "other", "exclusion": None},
    ]
    # Two edges on a#->b, one on a*->b, one on the script segment.
    rows = [
        rows_base[0], rows_base[0],
        rows_base[1],
        rows_base[2],
    ]
    candidates = [
        {
            "id": glc.make_id(glc.TOOL_TOKEN_JS, "a#", "b", rule="wall"),
            "fromCluster": "a#", "toCluster": "b", "rule": "wall",
            "wallKey": glc.make_wall_key(glc.TOOL_TOKEN_JS, "wall", "a#", "b"),
            "metric": 2, "paths": [],
        },
        {
            "id": glc.make_id(glc.TOOL_TOKEN_JS, "a*", "b", rule="wall"),
            "fromCluster": "a*", "toCluster": "b", "rule": "wall",
            "wallKey": glc.make_wall_key(glc.TOOL_TOKEN_JS, "wall", "a*", "b"),
            "metric": 1, "paths": [],
        },
        {
            "id": glc.make_id(
                glc.TOOL_TOKEN_JS, "pkg/<script>", "other", rule="wall"),
            "fromCluster": "pkg/<script>", "toCluster": "other", "rule": "wall",
            "wallKey": glc.make_wall_key(
                glc.TOOL_TOKEN_JS, "wall", "pkg/<script>", "other"),
            "metric": 1, "paths": [],
        },
    ]
    vocab = glc.deferred_vocabulary()
    check = glc.deferred_check_the_check()
    census = {"workspaces": ["."]}

    def _digest(edge_rows):
        return the_lens._build_digest(
            ecosystems={}, rows=edge_rows, candidates=candidates,
            vocabulary=vocab, check=check, versions={},
            per_workspace={}, parsed_total=0, sources_total=0,
            js_census=census, py_census=None)

    digest = _digest(rows)
    key_hash = glc._encode_identity_key("a#->b")
    key_star = glc._encode_identity_key("a*->b")
    key_script = glc._encode_identity_key("pkg/<script>->other")
    assert key_hash != key_star
    assert key_hash in digest["matrix"]
    assert key_star in digest["matrix"]
    assert key_script in digest["matrix"]
    assert digest["matrix"][key_hash] == 2
    assert digest["matrix"][key_star] == 1
    # Pre-fix collapse would leave a single a_->b cell; three distinct keys required.
    assert len(digest["matrix"]) == 3

    ids = list(digest["eligible"].keys())
    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert all("<" not in i and "#" not in i and "*" not in i for i in ids)

    # Change only the a#->b weight; hash must move. Changing a* instead must also move,
    # and the two resulting hashes must differ from each other (collision would mask one).
    rows_bump_hash = [
        rows_base[0], rows_base[0], rows_base[0],  # weight 3
        rows_base[1],
        rows_base[2],
    ]
    rows_bump_star = [
        rows_base[0], rows_base[0],
        rows_base[1], rows_base[1],  # weight 2
        rows_base[2],
    ]
    h0 = digest["matrixHash"]
    h_hash = _digest(rows_bump_hash)["matrixHash"]
    h_star = _digest(rows_bump_star)["matrixHash"]
    assert h_hash != h0
    assert h_star != h0
    assert h_hash != h_star


def test_safe_repo_text_neutralizes_html_tags_but_preserves_edge_arrow():
    """HTML tags in repo-derived free text must not survive; a->b reasons must.

    ``_safe_repo_text`` previously left ``<>`` alone so EDGE_ARROW survived, which also
    let ``<script>`` / ``<img ...>`` through into reasons/digest display fields.
    """
    hostile_script = "pkg/<script>alert(1)</script>/mod"
    hostile_img = 'dir/<img src=x onerror=alert(1)>/file'
    safe_script = glc._safe_repo_text(hostile_script)
    safe_img = glc._safe_repo_text(hostile_img)
    assert "<script>" not in safe_script
    assert "</script>" not in safe_script
    assert "<img" not in safe_img
    assert "onerror=" in safe_img or "onerror" in safe_img  # text may remain
    assert "<" not in safe_script
    assert ">" not in safe_script
    assert "<" not in safe_img
    assert ">" not in safe_img
    # Arrow grammar preserved for normal edge reasons / matrix display fragments.
    assert glc._safe_repo_text("a->b") == "a->b"
    assert glc._safe_repo_text("features/a->features/b: crosses wall") == (
        "features/a->features/b: crosses wall")
    # Digest free-text path that embeds a hostile name must also be neutralized.
    reason = glc._safe_repo_text(
        "coupling py: refused non-regular — pkg/<script>evil.py")
    assert "<script>" not in reason
    assert "<" not in reason and ">" not in reason
    assert glc.EDGE_ARROW in glc._safe_repo_text("src/a->src/b")


# ======================================================================================
# 17. B6 identity-collapse regressions (F3 arrow-in-name, F4 lossy truncation, F2 dedup)
# ======================================================================================

def test_arrow_in_cluster_name_does_not_collapse_distinct_matrix_cells():
    """F3: a literal ``->`` inside a cluster/dir name must not collapse two DISTINCT
    edges into one matrix cell or hide matrixHash drift.

    A directory named ``a->b`` is a legal POSIX filename in the adversarial-repo threat
    model. ``x -> (a->b)`` and ``(x->a) -> b`` are different edges; building a raw
    ``x->a->b`` key and splitting it later is ambiguous and merges them into one cell,
    so a real cross-wall edge change leaves matrixHash unchanged (drift masked).
    Driven through the real classification path (build_matrix + _build_digest).
    """
    the_lens = glc.LENS
    e1 = {"fromCluster": "x", "toCluster": "a->b", "exclusion": None}
    e2 = {"fromCluster": "x->a", "toCluster": "b", "exclusion": None}
    vocab = glc.deferred_vocabulary()
    check = glc.deferred_check_the_check()
    census = {"workspaces": ["."]}

    def _digest(edge_rows):
        return the_lens._build_digest(
            ecosystems={}, rows=edge_rows, candidates=[],
            vocabulary=vocab, check=check, versions={},
            per_workspace={}, parsed_total=0, sources_total=0,
            js_census=census, py_census=None)

    base = _digest([e1, e2])
    # Expected keys computed from the encode-then-join contract (no raw pre-join split).
    k1 = (glc._encode_identity_fragment("x") + glc.EDGE_ARROW
          + glc._encode_identity_fragment("a->b"))
    k2 = (glc._encode_identity_fragment("x->a") + glc.EDGE_ARROW
          + glc._encode_identity_fragment("b"))
    assert k1 != k2
    # Two DISTINCT cells — the pre-fix split-on-arrow collapses them into one.
    assert len(base["matrix"]) == 2, base["matrix"]
    assert k1 in base["matrix"] and k2 in base["matrix"]
    assert base["matrix"][k1] == 1 and base["matrix"][k2] == 1
    # The `>` inside a cluster name is encoded to %3E, so the `->` separator is
    # unambiguous: each key splits into exactly two cluster fragments (the pre-fix raw
    # key `x->a->b` splits into three).
    for key in base["matrix"]:
        assert len(key.split(glc.EDGE_ARROW)) == 2, key
        assert "%3E" in key  # a name-borne `>` survived only as its encoded form
    # Drift: bumping ONLY the x->(a->b) edge must move matrixHash, and it must differ
    # from bumping the other colliding edge instead — a collapse would mask one of them.
    h0 = base["matrixHash"]
    h1 = _digest([e1, e1, e2])["matrixHash"]
    h2 = _digest([e1, e2, e2])["matrixHash"]
    assert h1 != h0
    assert h2 != h0
    assert h1 != h2


def test_encode_identity_fragment_truncation_stays_distinct_for_long_shared_prefixes():
    """F4: two distinct fragments that both exceed the identity ``max_len`` and share a
    long prefix must stay DISTINCT after ``_encode_identity_fragment``.

    A plain ``prefix + "..."`` truncation is LOSSY on an identity — distinct long ids
    with a shared prefix collapse to one key and mask coupling drift / candidate identity.
    """
    max_len = glc.REPO_TEXT_MAX * 2
    prefix = "p" * (max_len + 1)  # already over the cap on its own
    a = prefix + "AAAA"
    b = prefix + "BBBB"
    assert len(a) > max_len and len(b) > max_len
    ea = glc._encode_identity_fragment(a)
    eb = glc._encode_identity_fragment(b)
    # Distinct despite the shared 501+ char prefix.
    assert ea != eb
    # Still bounded (identity fragments are capped).
    assert len(ea) <= max_len and len(eb) <= max_len
    # Deterministic: same input encodes the same way across calls.
    assert glc._encode_identity_fragment(a) == ea


def test_duplicate_parsed_paths_do_not_inflate_the_parsed_census(tmp_path):
    """F2: a parsed-modules list that repeats the same module path must not inflate the
    ``_parsed_census`` count / the cliff's parsed total.

    A tool that lists a module twice must count once — a duplicate could weaken the
    collapse/cliff tripwires by faking a higher parsed count than modules on disk.
    """
    repo = init_calibrated_repo(tmp_path)
    src_census = {"workspaces": [glc.ROOT_WORKSPACE]}
    # 3 listed entries, only 2 DISTINCT normalized paths.
    parsed_paths = ["src/a/x.ts", "src/a/x.ts", "src/b/y.ts"]
    census = glc._parsed_census(repo, parsed_paths, src_census, glc.JS_EXT_LANG)
    total = sum(sum(by_lang.values()) for by_lang in census.values())
    assert total == 2, census
    # The dedup seam feeding len(parsed_paths) at the tripwire sites agrees.
    assert len(glc._dedup_norm_paths(repo, parsed_paths)) == 2


# ======================================================================================
# 18. Identity-collision CLASS closed by construction (#538 follow-up)
#     Every STRUCTURAL char (`->`, `:`, `~`) escaped in the encoding; `_posix` preserves
#     a POSIX backslash; parsed-path dedup preserves case. Each test below FAILS on the
#     pre-fix code and PASSES after.
# ======================================================================================

def test_escape_set_covers_every_structural_identity_char():
    """GUARD: every structural character used to BUILD identities must be in the escape
    set, so no future separator/marker can silently reopen the collision class.

    Structural chars: EDGE_ARROW (`->`, i.e. `>`), ID_SEP (`:`), and the truncation
    marker (`~`). If any can appear literally inside an encoded fragment, two distinct
    inputs can alias one identity.
    """
    structural_chars = ("-", ">", ":", "~")
    for ch in structural_chars:
        # A structural char that participates in a separator/marker (`>`,`:`,`~`) must be
        # escaped away by _encode_identity_fragment; `-` alone is not a separator (only the
        # two-char `->` is) so it need not be escaped.
        encoded = glc._encode_identity_fragment("x" + ch + "y")
        if ch in (">", ":", "~"):
            assert ch not in encoded, (ch, encoded)
    # Direct on the compiled alphabet: the separator/marker chars are all matched.
    assert glc._IDENTITY_ESCAPE_RE.search(">")
    assert glc._IDENTITY_ESCAPE_RE.search(":")
    assert glc._IDENTITY_ESCAPE_RE.search("~")
    # And ID_SEP / the truncation marker are exactly the chars we assert are covered.
    assert glc.ID_SEP == ":"
    assert glc._IDENTITY_TRUNC_MARKER == "~"


def test_id_sep_char_in_a_fragment_cannot_alias_the_field_separator():
    """`:` (ID_SEP) inside a cluster/rule must NOT alias the id field boundary.

    Pre-fix `:` was not escaped, so make_id(tool,"b","c",rule="r:a") and
    make_id(tool,"a:b","c",rule="r") both minted `coupling:depcruise:r:a:b->c`.
    """
    i1 = glc.make_id(glc.TOOL_TOKEN_JS, "b", "c", rule="r:a")
    i2 = glc.make_id(glc.TOOL_TOKEN_JS, "a:b", "c", rule="r")
    assert i1 != i2, (i1, i2)
    # Same aliasing on the wall-key seam.
    w1 = glc.make_wall_key(glc.TOOL_TOKEN_JS, "r:a", "b", "c")
    w2 = glc.make_wall_key(glc.TOOL_TOKEN_JS, "r", "a:b", "c")
    assert w1 != w2, (w1, w2)
    # The literal `:` survives only as its encoded form inside a fragment.
    assert "%3A" in i1 and "%3A" in i2


def test_truncation_marker_char_in_a_fragment_cannot_alias_a_truncated_form():
    """`~` (the truncation marker) inside a fragment must NOT alias the truncated form
    of a different, longer fragment.

    Pre-fix `~` was not escaped: A's distinctness-preserving truncation is
    ``A[:keep] + "~" + short_hash(A)``; a DIFFERENT fragment B constructed to end with
    that exact ``~<hash>`` tail encoded to the identical string — a collision. Escaping
    `~` makes the marker unambiguous (any literal `~` becomes %7E).
    """
    max_len = glc.REPO_TEXT_MAX * 2
    a = "a" * 200 + "/" + "b" * 200            # 401 chars > max_len (400) -> truncated
    assert len(a) > max_len
    # Reconstruct A's pre-fix truncated tail to craft the colliding B.
    digest_a = glc.store_core.short_hash(a)    # a needs no escaping, so encoded == a
    keep = max_len - len(glc._IDENTITY_TRUNC_MARKER) - len(digest_a)
    b = a[:keep] + glc._IDENTITY_TRUNC_MARKER + digest_a  # a literal `~<hashA>` tail
    assert a != b
    ea = glc._encode_identity_fragment(a)
    eb = glc._encode_identity_fragment(b)
    assert ea != eb, (ea, eb)                  # pre-fix: eb == ea (collision)
    # Both stay bounded; the only bare `~` in either is the marker the encoder inserted
    # (B's literal `~` is escaped to %7E before truncation, so it cannot be that marker).
    assert len(ea) <= max_len and len(eb) <= max_len
    assert ea.count(glc._IDENTITY_TRUNC_MARKER) == 1
    assert eb.count(glc._IDENTITY_TRUNC_MARKER) == 1


def test_backslash_dir_name_stays_distinct_from_nested_dir_on_posix():
    """`_posix` must preserve a POSIX literal backslash so `a\\b` (one dir) stays distinct
    from `a/b` (nested) — distinct cluster keys, matrix keys, and matrixHash.

    Pre-fix `_posix` folded `\\`->`/` unconditionally, collapsing a directory literally
    named ``a\\b`` into nested ``a/b`` BEFORE identity encoding could escape it.
    """
    if os.sep != "/":
        pytest.skip("backslash-is-literal only holds on a POSIX host")
    fc_lit = glc.cluster_key("a\\b/mod.ts", glc.ROOT_WORKSPACE)    # literal-backslash dir
    fc_nested = glc.cluster_key("a/b/mod.ts", glc.ROOT_WORKSPACE)  # nested a/b
    assert fc_lit != fc_nested, (fc_lit, fc_nested)   # pre-fix: both "a/b"
    k_lit = glc._edge_key(fc_lit, "z")
    k_nested = glc._edge_key(fc_nested, "z")
    assert k_lit != k_nested, (k_lit, k_nested)
    m_lit = glc.build_matrix([{"fromCluster": fc_lit, "toCluster": "z"}])
    m_nested = glc.build_matrix([{"fromCluster": fc_nested, "toCluster": "z"}])
    assert glc.matrix_hash(m_lit) != glc.matrix_hash(m_nested)
    # The literal backslash reached identity encoding and became %5C.
    assert "%5C" in k_lit and "%5C" not in k_nested


def test_case_only_differing_parsed_paths_count_distinctly(tmp_path):
    """Parsed-path dedup must PRESERVE case so case-only-differing modules on a
    case-sensitive FS are counted distinctly — else the parsed census undercounts vs the
    source census and manufactures a FALSE cliff/collapse degrade.

    Pre-fix the dedup keyed on the lower-cased `_norm_rel`, collapsing all four modules
    to one.
    """
    repo = init_calibrated_repo(tmp_path)
    parsed_paths = ["src/AA.ts", "src/Aa.ts", "src/aA.ts", "src/aa.ts"]
    assert len(glc._dedup_norm_paths(repo, parsed_paths)) == 4
    src_census = {"workspaces": [glc.ROOT_WORKSPACE]}
    census = glc._parsed_census(repo, parsed_paths, src_census, glc.JS_EXT_LANG)
    total = sum(sum(by_lang.values()) for by_lang in census.values())
    assert total == 4, census


# ======================================================================================
# #564: git-tracked census confinement + vitals()
# ======================================================================================

def _vitals_digest(cross_cluster_edges=3, edges=None, ecosystems=None, outcome="ok",
                   matrix_truncated=False):
    if edges is None:
        edges = cross_cluster_edges + 2
    return {
        "outcome": outcome,
        "counters": {
            "edges": edges,
            "crossClusterEdges": cross_cluster_edges,
        },
        "ecosystems": ecosystems if ecosystems is not None else {
            "js": {"status": "collected"},
        },
        "matrixTruncated": matrix_truncated,
    }


def test_untracked_js_edge_does_not_change_counters_or_vital(tmp_path):
    """#564: depcruise output referencing an untracked file must not inflate edges."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "package.json", "{}")
    write(repo, "src/tracked.ts", "import './tracked-b';\n")
    write(repo, "src/tracked-b.ts", "export const x = 1;\n")
    write(repo, "src/untracked.ts", "import './tracked-b';\n")
    tracked = ["package.json", "src/tracked.ts", "src/tracked-b.ts"]
    report = dc_report(edges=[("src/tracked.ts", "src/tracked-b.ts")])
    baseline = lens().collect(ctx(
        repo, tmp_path, run=make_run(
            lambda argv, kw: (0, report, ""), tracked=tracked)))
    report2 = dc_report(edges=[
        ("src/tracked.ts", "src/tracked-b.ts"),
        ("src/untracked.ts", "src/tracked-b.ts"),
    ])
    filtered = lens().collect(ctx(
        repo, tmp_path, run=make_run(
            lambda argv, kw: (0, report2, ""), tracked=tracked)))
    assert st(baseline) == "collected", baseline.get("reason")
    assert st(filtered) == "collected", filtered.get("reason")
    assert baseline["digest"]["counters"]["edges"] == (
        filtered["digest"]["counters"]["edges"])
    assert filtered["digest"]["ecosystems"]["js"]["untrackedFiltered"] >= 1
    val_b, _ = glc.LENS.vitals(baseline["digest"])["couplingEdges"]
    val_f, _ = glc.LENS.vitals(filtered["digest"])["couplingEdges"]
    assert val_b == val_f


def test_tracked_symlink_to_untracked_target_excluded_from_py_census(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/a.py", "x = 1\n")
    (tmp_path / "untracked_target.py").write_text("y = 1\n")
    os.symlink("untracked_target.py", str(tmp_path / "link.py"))
    got, err = glc.census(
        census_ctx(repo, tracked=["mypkg/__init__.py", "mypkg/a.py", "link.py"]),
        repo, "py")
    assert err is None
    censused = {rel for _ws, rel, _lang in got["files"]}
    assert "mypkg/a.py" in censused
    assert "link.py" not in censused
    assert "untracked_target.py" not in censused


def test_git_census_failure_degrades_coupling_not_collected(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    write(repo, "src/a.ts")

    def run(argv, **kwargs):
        if argv and argv[0] == "git":
            return _Completed(128, "", "fatal: not a git repository")
        return _Completed(0, dc_report(edges=[("src/a.ts", "src/b.ts")]), "")

    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "not-collected"
    assert out["digest"] is None
    assert "git ls-files failed" in (out.get("reason") or "")


def test_coupling_vitals_complete_on_good_digest():
    val, reason = glc.LENS.vitals(_vitals_digest(7))["couplingEdges"]
    assert val == 7.0
    assert reason is None


def test_coupling_vitals_partial_when_ecosystem_incomplete():
    digest = _vitals_digest(5, ecosystems={"js": {"status": "collected"},
                                              "py": {"status": "not-collected"}})
    val, reason = glc.LENS.vitals(digest)["couplingEdges"]
    assert val == 5.0
    assert reason and "py" in reason


def test_coupling_vitals_not_collected_on_bad_outcome():
    digest = _vitals_digest(5)
    digest["outcome"] = "degraded"
    val, reason = glc.LENS.vitals(digest)["couplingEdges"]
    assert val is None
    assert reason


def test_coupling_vitals_not_collected_on_malformed_digest():
    val, reason = glc.LENS.vitals(None)["couplingEdges"]
    assert val is None and reason


def test_coupling_vitals_not_collected_on_non_numeric_edges():
    digest = _vitals_digest(3)
    digest["counters"]["crossClusterEdges"] = "many"
    val, reason = glc.LENS.vitals(digest)["couplingEdges"]
    assert val is None and "numeric" in reason


def test_coupling_vitals_counts_cross_cluster_edges_only():
    """couplingEdges vital reads crossClusterEdges, not total edge rows."""
    the_lens = lens()
    vocab = glc.deferred_vocabulary()
    check = glc.deferred_check_the_check()
    census = {"workspaces": ["."]}
    intra = {
        "from": "pkg/a.py", "to": "pkg/b.py",
        "fromCluster": "pkg", "toCluster": "pkg",
        "exclusion": glc.EXCLUSION_INTRA_CLUSTER,
    }
    cross = {
        "from": "pkg/a.py", "to": "other/c.py",
        "fromCluster": "pkg", "toCluster": "other",
        "exclusion": None,
    }

    def _digest(rows):
        return the_lens._build_digest(
            ecosystems={}, rows=rows, candidates=[], vocabulary=vocab, check=check,
            versions={}, per_workspace={}, parsed_total=0, sources_total=0,
            js_census=census, py_census=None)

    digest_cross_only = _digest([cross])
    digest_with_intra = _digest([cross, intra, intra])
    assert digest_cross_only["counters"]["edges"] == 1
    assert digest_cross_only["counters"]["crossClusterEdges"] == 1
    assert digest_with_intra["counters"]["edges"] == 3
    assert digest_with_intra["counters"]["crossClusterEdges"] == 1
    val_only, _ = glc.LENS.vitals(digest_cross_only)["couplingEdges"]
    val_with_intra, _ = glc.LENS.vitals(digest_with_intra)["couplingEdges"]
    assert val_only == 1.0
    assert val_with_intra == 1.0


def test_one_ecosystem_census_failure_yields_partial_with_other_measurement(tmp_path):
    """When one ecosystem's census fails, the other ecosystem still publishes partial."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "mypkg/__init__.py", "")
    write(repo, "mypkg/a.py", "x = 1\n")
    tracked = ["mypkg/__init__.py", "mypkg/a.py"]
    git_calls = [0]

    def run(argv, **kwargs):
        if argv and argv[0] == "git":
            git_calls[0] += 1
            if git_calls[0] == 1:
                return _Completed(128, "", "transient failure")
            return _git_ls_files_result(kwargs, tracked=tracked)
        raise AssertionError("unexpected tool: %s" % argv)

    out = lens().collect(ctx(repo, tmp_path, run=run))
    assert st(out) == "partial"
    assert out["digest"] is not None
    assert out["digest"]["ecosystems"]["py"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["js"]["status"] == "not-collected"
    assert "git ls-files failed" in (out.get("reason") or "")


def test_untracked_symlink_does_not_degrade_python_census(tmp_path):
    """An untracked symlink on disk is outside the tracked population — not a degrade."""
    repo = init_calibrated_repo(tmp_path)
    write(repo, "pkg/__init__.py", "")
    write(repo, "pkg/a.py", "x = 1\n")
    os.symlink("a.py", str(tmp_path / "pkg" / "link.py"))
    got, err = glc.census(
        census_ctx(repo, tracked=["pkg/__init__.py", "pkg/a.py"]),
        repo, "py")
    assert err is None
    assert got["skippedNonRegular"] == []
    out = lens().collect(ctx(
        repo, tmp_path,
        run=make_run(lambda _a, _k: _Completed(127, "", ""),
                     tracked=["pkg/__init__.py", "pkg/a.py"])))
    assert st(out) == "collected"
    assert out["digest"]["ecosystems"]["py"]["status"] == "collected"


def test_coupling_vitals_reports_edges_when_matrix_truncated():
    digest = _vitals_digest(42, matrix_truncated=True)
    val, reason = glc.LENS.vitals(digest)["couplingEdges"]
    assert val == 42.0
    assert reason is None
