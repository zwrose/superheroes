"""guardian_lens_deadcode: vulture (python) unused symbols + knip (node) unused
files/exports.

No network, no real subprocess: every tool call is injected through ctx["run"]. The repo
root is the sweep's ctx["cwd"] (realpath) — this lens spawns no git at all. VULTURE_EXCERPT
and KNIP_JSON below are VERBATIM (trimmed) output captured at the command line on
2026-07-21:

  `vulture <abs repo> --min-confidence 60 --exclude node_modules,.venv,venv,dist,build,
  __pycache__,.git`: exit 3, 37 raw hits aggregating to 30 candidates. Confirms the design's
  known seed `plugins/superheroes/lib/repo_doctor.py:243` (`_compute_drift`'s unused
  `engine_plugin_ver` parameter, 100% confidence) and surfaces a real duplicate-id case: a
  same-named pytest fixture parameter `clean_registry` is flagged, unused in the test body,
  in 8 different test functions in `plugins/superheroes/lib/tests/test_guardian_lens.py`
  (excerpted to 2 of the 8 lines here).

  `knip --directory /Users/zwrose/weekly-eats --reporter json` run READ-ONLY (no --fix)
  against installed node_modules: exit 1, 55 file-groups, 14 unused files, 33 unused
  exports.

Every collector resolves from PATH through the guardian seam — no repo-local binary, no
npx network fetch — and every tool operand is made ABSOLUTE against the repo root so a
neutral-cwd run can never false-clean by scanning the wrong tree.
"""
import json
import os
import re

import guardian_census
import guardian_lens as gl
import guardian_lens_deadcode as gld
import pytest

# --------------------------------------------------------------------------- fixtures

# Verbatim excerpt (5 of the 37 real lines) from the vulture run described above.
VULTURE_EXCERPT = (
    "plugins/superheroes/lib/repo_doctor.py:243: unused variable 'engine_plugin_ver' "
    "(100% confidence)\n"
    "plugins/superheroes/lib/control_plane.py:135: unused function 'allowance_trail' "
    "(60% confidence)\n"
    "plugins/superheroes/lib/tests/test_engine_apply.py:7: unused import 'blocks_mod' "
    "(90% confidence)\n"
    "plugins/superheroes/lib/tests/test_guardian_lens.py:88: unused variable "
    "'clean_registry' (100% confidence)\n"
    "plugins/superheroes/lib/tests/test_guardian_lens.py:97: unused variable "
    "'clean_registry' (100% confidence)\n"
)

# Verbatim values (reformatted for readability) from the knip run described above: one
# whole-file-unused entry, one single-export entry, one multi-export entry.
KNIP_JSON = json.dumps({
    "issues": [
        {
            "file": "scripts/audit-store-invitations.cjs",
            "exports": [],
            "files": [{"name": "scripts/audit-store-invitations.cjs"}],
        },
        {
            "file": "scripts/docgen/lib.js",
            "exports": [{"name": "GENERATED_HEADER", "line": 50, "col": 14, "pos": 2101}],
            "files": [],
        },
        {
            "file": "scripts/lib/households-backfill-core.mjs",
            "exports": [
                {"name": "normalizeEmail", "line": 77, "col": 17, "pos": 3736},
                {"name": "householdMatchesPlacement", "line": 218, "col": 17, "pos": 9117},
            ],
            "files": [],
        },
    ],
})


# ----------------------------------------------------------------------------- harness

class _R(object):
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRun(object):
    """Dispatches on argv[0]. Unstubbed argv fails loudly.

    Post-#564 the lens co-fires ``git ls-files -z`` before vulture/knip. Pass
    ``tracked=[...]`` to control the census (``None`` = walk cwd on disk).
    """

    def __init__(self, table, tracked=None):
        self.table = list(table)
        self.tracked = tracked
        self.calls = []

    def _git_result(self, kwargs):
        if self.tracked is not None:
            names = list(self.tracked)
        else:
            cwd = kwargs.get("cwd") or "."
            names = []
            for root, dirs, files in os.walk(cwd):
                if ".git" in dirs:
                    dirs.remove(".git")
                for f in files:
                    names.append(os.path.relpath(os.path.join(root, f), cwd))
        text = "".join(n + "\0" for n in names)

        class R:
            returncode = 0
            stdout = text
            stderr = ""
        return R()

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append((argv, dict(kwargs)))
        if argv and argv[0] == "git":
            return self._git_result(kwargs)
        line = " ".join(argv)
        for key, val in self.table:
            if key in line:
                if isinstance(val, BaseException):
                    raise val
                return _R(*val)
        return _R(127, "", "TEST-STUB-MISSING for %s" % line)

    def ran(self, key):
        return any(c[0] and c[0][0] == key for c in self.calls)


def _repo(tmp_path, files):
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(tmp_path)


def _py_repo(tmp_path, extra=None):
    files = {"pyproject.toml": "[project]\nname = \"x\"\n", "lib/stub.py": "pass\n"}
    files.update(extra or {})
    return _repo(tmp_path, files)


def _vulture_excerpt_files():
    """On-disk paths matching VULTURE_EXCERPT so the tracked census admits vulture hits."""
    paths = set()
    for line in VULTURE_EXCERPT.strip().splitlines():
        paths.add(line.split(":")[0])
    return {p: "pass\n" for p in paths}


def _py_repo_with_excerpt(tmp_path, extra=None):
    files = _vulture_excerpt_files()
    files["pyproject.toml"] = "[project]\nname = \"x\"\n"
    files.update(extra or {})
    return _repo(tmp_path, files)


def _knip_tracked_files():
    """Paths referenced by KNIP_JSON that must be in the tracked census."""
    return [
        "package.json",
        "node_modules/.gitkeep",
        "scripts/audit-store-invitations.cjs",
        "scripts/docgen/lib.js",
        "scripts/lib/households-backfill-core.mjs",
    ]


def _node_repo_with_knip_fixture(tmp_path, extra=None, with_node_modules=True):
    files = {p: "export const x = 1;\n" for p in _knip_tracked_files() if p.endswith((".cjs", ".js", ".mjs"))}
    files["package.json"] = "{}\n"
    if with_node_modules:
        files["node_modules/.gitkeep"] = ""
    files.update(extra or {})
    return _repo(tmp_path, files)


def _node_repo(tmp_path, extra=None, with_node_modules=True):
    files = {"package.json": "{}\n"}
    if with_node_modules:
        files["node_modules/.gitkeep"] = ""
    files.update(extra or {})
    return _repo(tmp_path, files)


def _ctx(repo, run, prev=None):
    return {"cwd": repo, "root": None, "config": {}, "run": run, "prevDigest": prev}


def _by_id(candidates):
    return dict((c["id"], c) for c in candidates)


# ------------------------------------------------------------------------- the contract

def test_lens_satisfies_the_contract():
    ok, reasons = gl.validate_lens(gld.LENS)
    assert ok, reasons
    assert gld.LENS.name == "deadcode"
    assert gld.LENS.collector_version == "1.1.0"
    assert gld.LENS.required_facts == ()
    assert isinstance(gld.LENS.cost.get("collectorSeconds"), float)
    assert gld.LENS.cost.get("note")


def test_module_exports_lenses_tuple():
    assert gld.LENSES == (gld.LENS,)


def test_degrade_shape():
    assert gld.LENS.degrade("vulture missing") == {
        "lens": "deadcode", "degraded": True, "reason": "vulture missing"}


def test_red_lines_always_empty():
    """Dead code is a cost claim, never an absolute red line — regardless of metric."""
    assert gld.LENS.red_lines([{"id": "x", "metric": 999999}]) == []
    assert gld.LENS.red_lines([]) == []


def test_kill_list_named_in_validation_guidance():
    doc = gld.LENS.validation_guidance
    for phrase in ("fixture", "mock", "getattr", "__all__", "generated", "conftest"):
        assert phrase in doc, phrase


def test_consequence_prices_reading_cost_not_severity():
    doc = gld.LENS.consequence_template
    assert "cost" in doc.lower()
    assert "never" in doc.lower()


# --------------------------------------------------------------------- ecosystem gating

def test_neither_ecosystem_present_is_not_collected(tmp_path):
    """No .py files and no package.json — nothing to scan, never a silent clean."""
    repo = _repo(tmp_path, {"README.md": "hi\n"})
    out = gld.LENS.collect(_ctx(repo, FakeRun([])))
    assert out["status"] == "not-collected"
    assert "package.json" in out["reason"] or "python" in out["reason"].lower()
    assert out["candidates"] == []
    assert out["digest"] is None


def test_python_detected_by_py_files_without_manifest(tmp_path):
    """This repo's shape: hundreds of .py files, no root pyproject/requirements.

    Manifest-only detection would report not-collected and hide real dead code
    (including the design's confirmed seed in repo_doctor.py).
    """
    repo = _repo(tmp_path, {
        "lib/thing.py": "def unused(x):\n    return 1\n",
        "README.md": "hi\n",
    })
    assert gld.detect_ecosystems(os.path.realpath(repo)) == [("python", None)]
    run = FakeRun([("vulture", (3,
        "lib/thing.py:1: unused function 'unused' (100% confidence)\n", ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert out["digest"]["detected"] == ["python"]
    assert out["digest"]["ecosystems"]["python"]["manifest"] is None
    assert any("unused" in c["id"] for c in out["candidates"])


def test_py_files_inside_vendor_dirs_do_not_detect_python(tmp_path):
    repo = _repo(tmp_path, {
        "node_modules/pkg/x.py": "x = 1\n",
        ".venv/lib/y.py": "y = 1\n",
        "README.md": "hi\n",
    })
    assert gld.detect_ecosystems(os.path.realpath(repo)) == []


def test_detect_ecosystems_python_manifest(tmp_path):
    repo = _repo(tmp_path, {"requirements.txt": "x==1\n"})
    assert gld.detect_ecosystems(os.path.realpath(repo)) == [
        ("python", "requirements.txt")]


def test_detect_ecosystems_both(tmp_path):
    repo = _repo(tmp_path, {"pyproject.toml": "", "package.json": "{}"})
    assert gld.detect_ecosystems(os.path.realpath(repo)) == [
        ("python", "pyproject.toml"), ("node", "package.json")]


# --------------------------------------------------------------------- vulture (python)

def test_vulture_parse_real_output_kind_symbol_path(tmp_path):
    repo = _py_repo_with_excerpt(tmp_path)
    run = FakeRun([("vulture", (3, VULTURE_EXCERPT, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    cands = _by_id(out["candidates"])

    seed = "deadcode:vulture:plugins/superheroes/lib/repo_doctor.py:variable:engine_plugin_ver"
    assert seed in cands
    assert cands[seed]["metric"] == 1
    assert cands[seed]["lines"] == [243]
    assert cands[seed]["kind"] == "variable"
    assert cands[seed]["symbol"] == "engine_plugin_ver"
    assert cands[seed]["path"] == "plugins/superheroes/lib/repo_doctor.py"
    assert cands[seed]["tool"] == "vulture"
    assert "engine_plugin_ver" in cands[seed]["receipt"]

    fn_id = ("deadcode:vulture:plugins/superheroes/lib/control_plane.py:"
             "function:allowance_trail")
    assert cands[fn_id]["kind"] == "function"

    imp_id = ("deadcode:vulture:plugins/superheroes/lib/tests/test_engine_apply.py:"
              "import:blocks_mod")
    assert cands[imp_id]["kind"] == "import"


def test_duplicate_symbol_aggregates_not_dropped(tmp_path):
    """The real clean_registry case: same id at two lines in one file → one candidate,
    count 2, both lines in the receipt — never two colliding entries the sweep would
    drop as malformed."""
    repo = _py_repo_with_excerpt(tmp_path)
    run = FakeRun([("vulture", (3, VULTURE_EXCERPT, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    cands = _by_id(out["candidates"])

    dup_id = ("deadcode:vulture:plugins/superheroes/lib/tests/test_guardian_lens.py:"
              "variable:clean_registry")
    assert dup_id in cands
    assert cands[dup_id]["metric"] == 2
    assert cands[dup_id]["lines"] == [88, 97]
    assert "88" in cands[dup_id]["receipt"]
    assert "97" in cands[dup_id]["receipt"]
    # Exactly one candidate for this id in the surfaced list — nothing silently dropped,
    # nothing silently duplicated either.
    assert sum(1 for c in out["candidates"] if c["id"] == dup_id) == 1


def test_id_independent_of_line_number(tmp_path):
    repo = _py_repo(tmp_path, {"plugins/superheroes/lib/foo.py": "bar = 1\n"})
    cid = "deadcode:vulture:plugins/superheroes/lib/foo.py:variable:bar"
    line10 = "plugins/superheroes/lib/foo.py:10: unused variable 'bar' (60% confidence)\n"
    line99 = "plugins/superheroes/lib/foo.py:99: unused variable 'bar' (60% confidence)\n"

    out1 = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, line10, ""))])))
    assert _by_id(out1["candidates"])[cid]["lines"] == [10]

    out2 = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, line99, ""))])))
    assert _by_id(out2["candidates"])[cid]["lines"] == [99]
    # Same id both times — moving the symbol's line never changes its identity.
    assert cid in _by_id(out1["candidates"]) and cid in _by_id(out2["candidates"])


def test_vulture_argv_operands_are_tracked_py_files(tmp_path):
    """R: vulture receives tracked .py file operands via ``--``, never the repo dir."""
    repo = _py_repo(tmp_path)
    run = FakeRun([("vulture", (0, "", ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    vulture_calls = [c[0] for c in run.calls if c[0] and c[0][0] == "vulture"]
    assert len(vulture_calls) == 1
    argv = vulture_calls[0]
    assert argv[0] == "vulture"
    assert "--" in argv
    operand_idx = argv.index("--") + 1
    operands = argv[operand_idx:]
    assert operands, argv
    assert all(arg.endswith(".py") for arg in operands), argv
    assert "vulture on PATH" in out["digest"]["ecosystems"]["python"]["resolution"]


def test_vulture_clean_run_is_collected_zero_candidates(tmp_path):
    repo = _py_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (0, "", ""))])))
    assert out["status"] == "collected"
    assert out["candidates"] == []


def test_vulture_findings_exit_with_empty_output_is_not_collected(tmp_path):
    """The R2/R11 honesty gate: exit 3 (dead code found) + empty stdout is a
    contradiction, not a clean scan. Reverting the exit-3 gate in collect_python makes
    this collect() read `collected` with zero candidates — this test bites."""
    repo = _py_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, "", ""))])))
    assert out["status"] == "not-collected"
    reason = out["reason"] or ""
    assert "empty" in reason.lower() or "contradiction" in reason.lower() or (
        "exit" in reason.lower() and "3" in reason)
    assert out["candidates"] == []
    assert out["digest"] is None


def test_vulture_contradiction_with_prev_finding_degrades_no_false_resolved(tmp_path):
    """The escaped defect made concrete: a findings-exit run that parses to zero, carrying
    a prev_digest with a prior finding, must DEGRADE (digest=None) AND diff() must emit no
    `resolved` — an uninstalled/contradictory tool must never look like a cleanup. Revert
    the exit-3 gate and both the degrade and the empty-resolved assertions bite."""
    repo = _py_repo(tmp_path)
    prev_id = "deadcode:vulture:lib/old.py:function:gone"
    prev_digest = {
        "schema": gld.DIGEST_SCHEMA,
        "candidates": {prev_id: {"id": prev_id, "tool": "vulture", "kind": "function",
                                 "path": "lib/old.py", "symbol": "gone",
                                 "metric": 1, "lines": [10], "receipt": "..."}},
    }
    out = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, "", ""))]), prev=prev_digest))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    d = gld.LENS.diff(prev_digest, out["digest"])
    assert d["resolved"] == []


def test_vulture_missing_not_collected(tmp_path):
    """Real scenario: vulture absent from PATH — the seam's tool-absent outcome degrades
    to not-collected naming the tool, never an empty clean scan."""
    repo = _py_repo(tmp_path)
    run = FakeRun([("vulture", (1, "", "No module named vulture"))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "vulture" in out["reason"]
    assert "No module named vulture" in out["reason"]
    assert out["candidates"] == []


def test_vulture_unparseable_output_not_collected_never_empty_clean(tmp_path):
    repo = _py_repo(tmp_path)
    garbage = "this is not vulture output at all\nneither is this line\n"
    out = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, garbage, ""))])))
    assert out["status"] == "not-collected"
    assert "did not match" in out["reason"]
    assert out["candidates"] == []


# ------------------------------------------------------------------------- knip (node)

def test_knip_parse_real_output_files_and_exports(tmp_path):
    repo = _node_repo_with_knip_fixture(tmp_path)
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    cands = _by_id(out["candidates"])

    file_id = "deadcode:knip:scripts/audit-store-invitations.cjs"
    assert cands[file_id]["kind"] == "file"
    assert cands[file_id]["metric"] == 1
    assert cands[file_id]["tool"] == "knip"

    export_id = "deadcode:knip:scripts/docgen/lib.js:GENERATED_HEADER"
    assert cands[export_id]["kind"] == "export"
    assert cands[export_id]["export"] == "GENERATED_HEADER"
    assert cands[export_id]["lines"] == [50]
    assert cands[export_id]["metric"] == 1

    multi_id = "deadcode:knip:scripts/lib/households-backfill-core.mjs:normalizeEmail"
    assert cands[multi_id]["kind"] == "export"
    assert cands[multi_id]["path"] == "scripts/lib/households-backfill-core.mjs"


def test_knip_argv_operands_are_absolute_and_path_only(tmp_path):
    """R: neutral-cwd false-clean guard + PATH-only — knip runs with `--directory <abs
    repo>` and is never a repo-local `node_modules/.bin/knip` nor a pinned npx fetch."""
    repo = _node_repo(tmp_path)
    run = FakeRun([("knip", (0, json.dumps({"issues": []}), ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    argv = out["digest"]["ecosystems"]["node"]["argv"]
    assert argv[0] == "knip"
    assert "--directory" in argv
    dir_operand = argv[argv.index("--directory") + 1]
    assert dir_operand == os.path.realpath(repo)
    assert os.path.isabs(dir_operand), argv
    assert "--reporter" in argv and "json" in argv
    # No npx, no node_modules/.bin path anywhere in the invocation.
    joined = " ".join(argv)
    assert "npx" not in joined
    assert os.path.join("node_modules", ".bin") not in joined
    assert "knip on PATH" in out["digest"]["ecosystems"]["node"]["resolution"]


def test_node_modules_missing_not_collected_never_empty_clean(tmp_path):
    repo = _node_repo(tmp_path, with_node_modules=False)
    run = FakeRun([])  # knip must never even be invoked
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "node_modules" in out["reason"]
    assert out["candidates"] == []
    assert not run.ran("knip")


def test_knip_clean_run_is_collected_zero_candidates(tmp_path):
    repo = _node_repo(tmp_path)
    empty = json.dumps({"issues": []})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (0, empty, ""))])))
    assert out["status"] == "collected"
    assert out["candidates"] == []


def test_knip_empty_stdout_is_not_collected_not_clean(tmp_path):
    """Empty stdout from knip is a broken run, never a clean scan — knip always emits
    JSON. Caught in parse_knip before any exit-code reasoning."""
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (0, "", ""))])))
    assert out["status"] == "not-collected"
    assert "empty" in (out["reason"] or "").lower()
    assert out["candidates"] == []


def test_knip_findings_exit_with_zero_candidates_is_not_collected(tmp_path):
    """The R2/R11 honesty gate: exit 1 (issues found) + a well-formed but EMPTY
    `{"issues": []}` is a contradiction, not a clean scan. Reverting the exit-1 gate in
    collect_node makes this read `collected` with zero candidates — this test bites."""
    repo = _node_repo(tmp_path)
    empty = json.dumps({"issues": []})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, empty, ""))])))
    assert out["status"] == "not-collected"
    reason = out["reason"] or ""
    assert "zero" in reason.lower() or "contradiction" in reason.lower() or (
        "exit" in reason.lower() and "1" in reason)
    assert out["candidates"] == []
    assert out["digest"] is None


def test_knip_contradiction_with_prev_finding_degrades_no_false_resolved(tmp_path):
    """Findings-exit + parsed-zero, carrying a prev finding: must DEGRADE (digest=None) and
    diff() must emit no `resolved`. Revert the exit-1 gate and both assertions bite."""
    repo = _node_repo(tmp_path)
    prev_id = "deadcode:knip:scripts/old-file.js"
    prev_digest = {
        "schema": gld.DIGEST_SCHEMA,
        "candidates": {prev_id: {"id": prev_id, "tool": "knip", "kind": "file",
                                 "path": "scripts/old-file.js", "export": None,
                                 "metric": 1, "lines": [], "receipt": "..."}},
    }
    empty = json.dumps({"issues": []})
    out = gld.LENS.collect(
        _ctx(repo, FakeRun([("knip", (1, empty, ""))]), prev=prev_digest))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    d = gld.LENS.diff(prev_digest, out["digest"])
    assert d["resolved"] == []


def test_knip_inscope_signals_normalizing_to_zero_degrade(tmp_path):
    """A1(a): exit 1 whose `issues` carry IN-SCOPE file/export signals that normalize to
    ZERO candidates (an export entry with no `name`) is a contradiction — degrade, never
    collected-zero. The gate must check the NORMALIZED candidates, not the raw `issues`
    list. Reverting A1 (gate on `not issues`) reads the nonempty raw list as findings-
    present and returns `collected` with zero candidates → both assertions bite."""
    repo = _node_repo(tmp_path)
    prev_id = "deadcode:knip:scripts/old-file.js"
    prev_digest = {
        "schema": gld.DIGEST_SCHEMA,
        "candidates": {prev_id: {"id": prev_id, "tool": "knip", "kind": "file",
                                 "path": "scripts/old-file.js", "export": None,
                                 "metric": 1, "lines": [], "receipt": "..."}},
    }
    # exports present (in-scope signal) but the export has no name → normalizes to zero.
    issues = json.dumps({"issues": [
        {"file": "src/x.ts", "files": [], "exports": [{"line": 3, "col": 5}]}]})
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "x.ts").write_text("export const x = 1;\n")
    out = gld.LENS.collect(
        _ctx(repo, FakeRun([("knip", (1, issues, ""))]), prev=prev_digest))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert out["candidates"] == []
    reason = out["reason"] or ""
    assert "in-scope" in reason and "zero" in reason.lower()
    d = gld.LENS.diff(prev_digest, out["digest"])
    assert d["resolved"] == []


def test_knip_out_of_scope_exit1_stays_collected_empty(tmp_path):
    """A1(b) nuance — do NOT over-degrade: knip also exits 1 for OUT-OF-SCOPE categories
    (unused dependencies / types / enumMembers). With no in-scope file/export signal that
    is a genuine CLEAN dead-code scan and must stay `collected` (empty), never degrade. A
    naive `not candidates` gate (no out-of-scope exemption) would over-degrade this — the
    assertion bites against that mutation."""
    repo = _node_repo(tmp_path)
    issues = json.dumps({"issues": [
        {"file": "package.json",
         "dependencies": [{"name": "left-pad"}],
         "files": [], "exports": []}]})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, issues, ""))])))
    assert out["status"] == "collected"
    assert out["candidates"] == []
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"


def test_knip_present_but_malformed_inscope_field_degrades_not_collected_clean(tmp_path):
    """H3: a PRESENT-BUT-MALFORMED in-scope field (`exports={"bad": "shape"}` — present key,
    non-list) beside an out-of-scope dependency is an in-scope signal knip emitted that this
    lens could not normalize. It must degrade (carry), never read collected-clean.

    Fail-before: `_knip_inscope_signals` counts only well-formed nonempty lists, so the
    malformed field counts as ZERO, the out-of-scope-only exemption fires, and the run reads
    `collected` empty — silently dropping the malformed signal (and, with a prev finding,
    resolving it). Removing the H3 malformed detector makes both assertions bite."""
    repo = _node_repo(tmp_path)
    prev_id = "deadcode:knip:src/x.ts:staleExport"
    prev_digest = {
        "schema": gld.DIGEST_SCHEMA,
        "candidates": {prev_id: {"id": prev_id, "tool": "knip", "kind": "export",
                                 "path": "src/x.ts", "export": "staleExport",
                                 "metric": 1, "lines": [], "receipt": "..."}},
    }
    issues = json.dumps({"issues": [
        {"file": "src/x.ts", "exports": {"bad": "shape"}},          # malformed in-scope
        {"file": "package.json", "dependencies": [{"name": "left-pad"}]},  # out-of-scope
    ]})
    out = gld.LENS.collect(
        _ctx(repo, FakeRun([("knip", (1, issues, ""))]), prev=prev_digest))
    assert out["status"] != "collected"
    node = out["digest"]["ecosystems"]["node"] if out.get("digest") else None
    if node is not None:
        assert node["status"] == "not-collected"
    reason = out["reason"] or ""
    assert "malformed" in reason.lower()
    # the malformed in-scope signal is carried forward, never resolved
    d = gld.LENS.diff(prev_digest, out.get("digest"))
    assert d["resolved"] == []


def test_knip_malformed_inscope_masked_by_valid_candidate_still_degrades(tmp_path):
    """H3 masking case: a VALID unused-file candidate beside a malformed in-scope field.
    The valid candidate keeps `candidates` truthy so the `not candidates` gate never fires;
    the malformed detector must degrade anyway rather than let the sibling mask it."""
    repo = _node_repo(tmp_path)
    issues = json.dumps({"issues": [
        {"file": "scripts/dead.js", "files": ["scripts/dead.js"]},  # valid candidate
        {"file": "src/x.ts", "exports": {"bad": "shape"}},          # malformed in-scope
    ]})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, issues, ""))])))
    assert out["status"] != "collected"
    assert "malformed" in (out["reason"] or "").lower()


def test_knip_only_unused_dependencies_no_inscope_keys_stays_collected(tmp_path):
    """H3 guardrail: exit 1 with ONLY unused-dependencies and NO files/exports keys at all
    (genuinely absent in-scope fields) stays collected-empty — the malformed detector must
    not fire on absent fields (the out-of-scope-only exemption is preserved)."""
    repo = _node_repo(tmp_path)
    issues = json.dumps({"issues": [
        {"file": "package.json", "dependencies": [{"name": "left-pad"}]}]})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, issues, ""))])))
    assert out["status"] == "collected"
    assert out["candidates"] == []
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"


def test_knip_unparseable_output_not_collected_never_empty_clean(tmp_path):
    repo = _node_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, "not json at all", ""))])))
    assert out["status"] == "not-collected"
    assert "knip" in out["reason"]
    assert out["candidates"] == []


def test_knip_wrong_json_shape_not_collected(tmp_path):
    repo = _node_repo(tmp_path)
    wrong = json.dumps({"nope": []})
    out = gld.LENS.collect(_ctx(repo, FakeRun([("knip", (1, wrong, ""))])))
    assert out["status"] == "not-collected"
    assert "issues" in out["reason"]
    assert out["candidates"] == []


# ------------------------------------------------------- knip executable-config gate (#548)

def test_knip_executable_config_js_refused_knip_never_invoked(tmp_path):
    """#548 precedent applied: an executable `knip.config.js` (a Node module knip would
    LOAD AND RUN) is refused during the read-only sweep. The node section degrades with the
    executable-config reason and knip is NEVER spawned — the spy records zero knip calls.
    Revert the gate (always-run) and both the reason and the never-invoked assertion bite."""
    repo = _node_repo(tmp_path, extra={"knip.config.js": "module.exports = {};\n"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])  # a spy: any knip spawn would be recorded
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    reason = out["reason"] or ""
    assert "executable" in reason.lower()
    assert "knip.config.js" in reason
    assert out["candidates"] == []
    assert out["digest"] is None
    # knip must never have been invoked — a filesystem classification, not a spawn.
    assert not run.ran("knip")
    assert not any(c[0] and c[0][0] == "knip" for c in run.calls)


def test_knip_executable_config_dotfile_ts_refused_knip_never_invoked(tmp_path):
    """Second executable variant — a `.knip.ts` dotfile (fail-closed superset). Same
    refusal, knip never spawned."""
    repo = _node_repo(tmp_path, extra={".knip.ts": "export default {};\n"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "executable" in (out["reason"] or "").lower()
    assert ".knip.ts" in out["reason"]
    assert not run.ran("knip")


def test_knip_executable_config_refused_even_when_declarative_also_present(tmp_path):
    """Presence of ANY executable config ⇒ refuse, even if a declarative one also exists
    (knip may pick the executable one; fail closed)."""
    repo = _node_repo(tmp_path, extra={
        "knip.json": json.dumps({"entry": ["src/index.ts"]}),
        "knip.config.ts": "export default {};\n",
    })
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "executable" in (out["reason"] or "").lower()
    assert "knip.config.ts" in out["reason"]
    assert not run.ran("knip")


def test_knip_executable_config_refused_before_node_modules_gate(tmp_path):
    """ORDERING: with NO node_modules AND an executable config, the code-execution refusal
    is the reason surfaced (not the node_modules-missing reason) — the execution risk is the
    one worth reporting. knip still never runs."""
    repo = _node_repo(tmp_path, with_node_modules=False,
                      extra={"knip.config.js": "module.exports = {};\n"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "executable" in (out["reason"] or "").lower()
    assert "node_modules" not in (out["reason"] or "")
    assert not run.ran("knip")


def test_knip_declarative_json_config_runs(tmp_path):
    """A declarative `knip.json` (DATA — parsed, not executed) is safe: knip runs and the
    section collects/aggregates exactly as today."""
    repo = _node_repo_with_knip_fixture(
        tmp_path, extra={"knip.json": json.dumps({"entry": ["src/index.ts"]})})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert run.ran("knip")
    cands = _by_id(out["candidates"])
    assert "deadcode:knip:scripts/audit-store-invitations.cjs" in cands


def test_knip_declarative_jsonc_dotfile_config_runs(tmp_path):
    """A declarative `.knip.jsonc` dotfile is also DATA — knip runs."""
    repo = _node_repo(tmp_path, extra={".knip.jsonc": "{\n  // comment\n  \"entry\": []\n}\n"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert run.ran("knip")


def test_knip_package_json_knip_key_runs(tmp_path):
    """A `knip` key in package.json is declarative (DATA) — knip runs as today."""
    repo = _node_repo(tmp_path, extra={
        "package.json": json.dumps({"name": "x", "knip": {"entry": ["src/index.ts"]}}) + "\n",
    })
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert run.ran("knip")


def test_knip_no_config_runs_default_scan(tmp_path):
    """No knip config at all → knip's default scan (parses source, executes nothing) runs
    as today."""
    repo = _node_repo(tmp_path)  # package.json + node_modules, no knip config
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert run.ran("knip")


def test_knip_unrecognized_extension_config_refused_fail_closed(tmp_path):
    """Fail-direction: a knip-config-shaped file with an extension we do NOT recognize as
    declarative (`knip.config.xyz`) is uncertain ⇒ treat as executable and refuse. knip
    never runs."""
    repo = _node_repo(tmp_path, extra={"knip.config.xyz": "whatever\n"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "executable" in (out["reason"] or "").lower()
    assert "knip.config.xyz" in out["reason"]
    assert not run.ran("knip")


def test_knip_unparseable_package_json_refused_fail_closed(tmp_path):
    """Fail-direction: a package.json that cannot be parsed cannot be classified (its
    `knip` key is unreadable) ⇒ refuse. knip never runs."""
    repo = _node_repo(tmp_path, extra={"package.json": "{ this is not json"})
    run = FakeRun([("knip", (1, KNIP_JSON, ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert "executable" in (out["reason"] or "").lower()
    assert "package.json" in out["reason"]
    assert not run.ran("knip")


def test_classify_knip_config_unit(tmp_path):
    """Direct classification table — declarative/no-config safe; executable/unknown/
    unparseable refused."""
    # no config → safe
    safe, name = gld._classify_knip_config(_node_repo(tmp_path / "a"))
    assert safe and name is None
    # declarative only → safe
    safe, name = gld._classify_knip_config(
        _node_repo(tmp_path / "b", extra={"knip.json": "{}"}))
    assert safe and name is None
    # executable → refuse, names the file
    safe, name = gld._classify_knip_config(
        _node_repo(tmp_path / "c", extra={"knip.config.mjs": "export default {}\n"}))
    assert not safe and name == "knip.config.mjs"


# ------------------------------------------------------------------- mixed / combining

def test_both_ecosystems_collected(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\nname = \"x\"\n",
        "lib/stub.py": "pass\n",
        "package.json": "{}\n",
        "node_modules/.gitkeep": "",
        "scripts/audit-store-invitations.cjs": "export const x = 1;\n",
        "scripts/docgen/lib.js": "export const x = 1;\n",
        "scripts/lib/households-backfill-core.mjs": "export const x = 1;\n",
    })
    run = FakeRun([
        ("vulture", (3, VULTURE_EXCERPT, "")),
        ("knip", (1, KNIP_JSON, "")),
    ], tracked=_knip_tracked_files() + [
        "pyproject.toml", "lib/stub.py",
        "plugins/superheroes/lib/repo_doctor.py",
        "plugins/superheroes/lib/control_plane.py",
        "plugins/superheroes/lib/tests/test_engine_apply.py",
        "plugins/superheroes/lib/tests/test_guardian_lens.py",
    ])
    for p in [
        "plugins/superheroes/lib/repo_doctor.py",
        "plugins/superheroes/lib/control_plane.py",
        "plugins/superheroes/lib/tests/test_engine_apply.py",
        "plugins/superheroes/lib/tests/test_guardian_lens.py",
    ]:
        fp = tmp_path / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("pass\n")
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected"
    assert out["digest"]["ecosystems"]["python"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"
    tools = set(c["tool"] for c in out["candidates"])
    assert tools == {"vulture", "knip"}


def test_one_ecosystem_partial_carries_prev_forward_no_false_resolved(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\nname = \"x\"\n",
        "lib/stub.py": "pass\n",
        "package.json": "{}\n",
        "node_modules/.gitkeep": "",
    })
    prev_node_id = "deadcode:knip:scripts/old-file.js"
    prev_digest = {
        "schema": gld.DIGEST_SCHEMA,
        "candidates": {
            prev_node_id: {
                "id": prev_node_id, "tool": "knip", "kind": "file",
                "path": "scripts/old-file.js", "export": None,
                "metric": 1, "lines": [], "receipt": "knip: unused file",
            },
        },
    }
    run = FakeRun([
        ("vulture", (3, VULTURE_EXCERPT, "")),
        ("knip", (127, "", "TEST-STUB-MISSING")),
    ], tracked=[
        "pyproject.toml", "lib/stub.py", "package.json", "node_modules/.gitkeep",
        "plugins/superheroes/lib/repo_doctor.py",
        "plugins/superheroes/lib/control_plane.py",
        "plugins/superheroes/lib/tests/test_engine_apply.py",
        "plugins/superheroes/lib/tests/test_guardian_lens.py",
    ])
    for p in [
        "plugins/superheroes/lib/repo_doctor.py",
        "plugins/superheroes/lib/control_plane.py",
        "plugins/superheroes/lib/tests/test_engine_apply.py",
        "plugins/superheroes/lib/tests/test_guardian_lens.py",
    ]:
        fp = tmp_path / p
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text("pass\n")
    out = gld.LENS.collect(_ctx(repo, run, prev=prev_digest))
    assert out["status"] == "partial"
    assert "knip" in out["reason"]

    surfaced_ids = [c["id"] for c in out["candidates"]]
    assert any("repo_doctor.py" in i for i in surfaced_ids)
    # Carried-forward candidate never surfaces as a freshly-collected finding this sweep...
    assert prev_node_id not in surfaced_ids
    # ...but IS present in the digest so the next diff() sees no false "resolved".
    assert prev_node_id in out["digest"]["candidates"]
    assert out["digest"]["candidates"][prev_node_id]["carriedForward"] is True

    d = gld.LENS.diff(prev_digest, out["digest"])
    assert prev_node_id not in d["resolved"]


# ------------------------------------------------------------------------------- diff

def test_diff_new_worsened_resolved():
    prev_digest = {"candidates": {
        "a": {"id": "a", "metric": 1},
        "b": {"id": "b", "metric": 3},
    }}
    cur_digest = {"candidates": {
        "b": {"id": "b", "metric": 5},
        "c": {"id": "c", "metric": 1},
    }}
    d = gld.LENS.diff(prev_digest, cur_digest)
    assert d["new"] == ["c"]
    assert d["worsened"] == ["b"]
    assert d["resolved"] == ["a"]


def test_diff_equal_metric_is_neither_new_nor_worsened():
    prev_digest = {"candidates": {"a": {"id": "a", "metric": 2}}}
    cur_digest = {"candidates": {"a": {"id": "a", "metric": 2}}}
    d = gld.LENS.diff(prev_digest, cur_digest)
    assert d == {"new": [], "worsened": [], "resolved": []}


def test_diff_none_cur_never_resolves_prev_findings():
    """A degraded sweep (digest=None) must claim no movement — never resolve a prior
    finding it did not re-measure."""
    prev_digest = {"candidates": {"a": {"id": "a", "metric": 1}}}
    assert gld.LENS.diff(prev_digest, None) == {"new": [], "worsened": [], "resolved": []}


def test_diff_handles_none_and_malformed_digests():
    assert gld.LENS.diff(None, None) == {"new": [], "worsened": [], "resolved": []}
    assert gld.LENS.diff("not-a-dict", {"candidates": {"a": {"id": "a", "metric": 1}}}) == {
        "new": ["a"], "worsened": [], "resolved": []}


# ---------------------------------------------------------------------- low-level parse

def test_parse_vulture_real_excerpt_shape():
    hits, err = gld.parse_vulture(VULTURE_EXCERPT)
    assert err is None
    assert len(hits) == 5
    seed = [h for h in hits if h["symbol"] == "engine_plugin_ver"][0]
    assert seed["kind"] == "variable"
    assert seed["line"] == 243
    assert seed["confidence"] == 100
    assert seed["path"] == "plugins/superheroes/lib/repo_doctor.py"


def test_parse_vulture_empty_stdout_is_clean_not_error():
    hits, err = gld.parse_vulture("")
    assert hits == [] and err is None


def test_parse_vulture_garbage_is_unparseable():
    hits, err = gld.parse_vulture("this is not vulture output\nneither is this")
    assert hits is None
    assert "did not match" in err


def test_parse_knip_real_json_shape():
    issues, err = gld.parse_knip(KNIP_JSON)
    assert err is None
    assert len(issues) == 3


def test_parse_knip_empty_stdout_is_unparseable_not_clean():
    """knip always emits JSON — empty stdout is a broken run, not `{"issues": []}`."""
    issues, err = gld.parse_knip("")
    assert issues is None
    assert "empty" in err.lower()


def test_parse_knip_clean_json_is_empty_not_error():
    issues, err = gld.parse_knip(json.dumps({"issues": []}))
    assert issues == [] and err is None


def test_parse_knip_bad_json_is_unparseable():
    issues, err = gld.parse_knip("{not json")
    assert issues is None
    assert "not valid JSON" in err


def test_parse_knip_wrong_shape_is_unparseable():
    issues, err = gld.parse_knip(json.dumps({"nope": []}))
    assert issues is None
    assert "issues" in err


# ------------------------------------------------------------------------- conformance

def test_lens_passes_the_conformance_harness():
    """The full per-lens honesty harness — the same gate CI runs over every registered
    lens — must pass for deadcode (node/knip conformance path)."""
    from test_guardian_conformance import assert_lens_conformance
    assert_lens_conformance(gld.LENS)


def test_conformance_fixture_is_node_only():
    """The fixture detects node alone (so a single injected stdout drives exactly knip)."""
    fixture = gld.LENS.conformance_fixture()
    assert "package.json" in fixture
    assert any(rel.startswith("node_modules/") for rel in fixture)
    assert not any(rel.endswith(".py") for rel in fixture)
    assert "pyproject.toml" not in fixture and "requirements.txt" not in fixture


def test_conformance_case_declares_knip_dual_exits():
    case = gld.LENS.conformance_cases()["reported-nonzero-parsed-zero"]
    assert case["exit"] == 1        # knip findings exit
    assert case["clean_exit"] == 0  # knip clean exit
    assert "git" in case["stdout_by_tool"]
    assert "git" in case.get("clean_stdout_by_tool", {})


# --- #564: git-tracked census confinement -----------------------------------------

def test_untracked_twin_does_not_change_python_candidates(tmp_path):
    """#564: an untracked near-duplicate must not alter vulture candidates."""
    repo = _py_repo(tmp_path, {"lib/tracked.py": "def unused():\n    pass\n"})
    untracked_body = "def unused():\n    pass\n"
    (tmp_path / "lib" / "untracked_twin.py").write_text(untracked_body)
    hit = "lib/tracked.py:1: unused function 'unused' (100% confidence)\n"
    run = FakeRun([("vulture", (3, hit, ""))], tracked=["lib/tracked.py"])
    baseline = gld.LENS.collect(_ctx(repo, run))
    assert baseline["status"] == "collected", baseline.get("reason")
    assert len(baseline["candidates"]) == 1
    edges_before = baseline["digest"]["ecosystems"]["python"].get("untrackedFiltered", 0)

    run2 = FakeRun([("vulture", (3, hit, ""))], tracked=["lib/tracked.py"])
    with_twin = gld.LENS.collect(_ctx(repo, run2))
    assert with_twin["status"] == "collected"
    assert len(with_twin["candidates"]) == len(baseline["candidates"])
    assert with_twin["digest"]["ecosystems"]["python"].get("untrackedFiltered", 0) == (
        edges_before)


def test_untracked_twin_does_not_change_knip_candidates(tmp_path):
    """#564: knip in-scope signals on untracked files must not affect candidates."""
    repo = _node_repo(tmp_path)
    tracked_issue = json.dumps({"issues": [{
        "file": "src/tracked.js",
        "files": [{"name": "src/tracked.js"}],
        "exports": [],
    }]})
    untracked_issue = json.dumps({"issues": [
        {"file": "src/tracked.js", "files": [{"name": "src/tracked.js"}], "exports": []},
        {"file": "src/untracked.js", "files": [{"name": "src/untracked.js"}], "exports": []},
    ]})
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "tracked.js").write_text("export const x = 1;\n")
    (tmp_path / "src" / "untracked.js").write_text("export const y = 1;\n")
    tracked = ["package.json", "node_modules/.gitkeep", "src/tracked.js"]
    baseline = gld.LENS.collect(_ctx(
        repo, FakeRun([("knip", (1, tracked_issue, ""))], tracked=tracked)))
    assert baseline["status"] == "collected", baseline.get("reason")
    assert len(baseline["candidates"]) == 1

    filtered = gld.LENS.collect(_ctx(
        repo, FakeRun([("knip", (1, untracked_issue, ""))], tracked=tracked)))
    assert filtered["status"] == "collected"
    assert len(filtered["candidates"]) == len(baseline["candidates"])
    assert filtered["digest"]["ecosystems"]["node"]["untrackedFiltered"] == 1


def test_tracked_symlink_to_untracked_target_excluded_from_vulture_operands(tmp_path):
    repo = _py_repo(tmp_path, {"a.py": "x = 1\n"})
    (tmp_path / "untracked_target.py").write_text("y = 1\n")
    os.symlink("untracked_target.py", str(tmp_path / "link.py"))
    run = FakeRun([("vulture", (0, "", ""))], tracked=["a.py", "link.py"])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    vulture_calls = [c[0] for c in run.calls if c[0] and c[0][0] == "vulture"]
    assert len(vulture_calls) == 1
    argv = vulture_calls[0]
    joined = " ".join(argv)
    assert "link.py" not in joined
    assert "untracked_target.py" not in joined
    assert any("a.py" in arg for arg in argv)


def test_git_census_failure_degrades_python_not_collected(tmp_path):
    def run(argv, **kwargs):
        if argv and argv[0] == "git":
            class R:
                returncode = 128
                stdout = ""
                stderr = "fatal: not a git repository"
            return R()
        return _R(0, "", "")

    repo = _py_repo(tmp_path)
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert "git ls-files failed" in (out["reason"] or "")


def test_arg_max_guard_degrades_never_scans_repo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(guardian_census, "MAX_TRACKED_OPERAND_BYTES", 5)
    repo = _py_repo(tmp_path, {"a.py": "x\n", "b.py": "y\n"})
    run = FakeRun([("vulture", (0, "", ""))], tracked=["a.py", "b.py"])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "not-collected"
    assert out["digest"] is None
    assert "across 2 files" in (out["reason"] or "")
    assert not any(c[0] and c[0][0] == "vulture" for c in run.calls)


def test_vulture_exit3_all_untracked_hits_collected_not_contradiction(tmp_path):
    """Exit 3 with hits that filter to zero (all untracked) is collected, not degraded."""
    repo = _py_repo(tmp_path)
    hit = "lib/untracked.py:1: unused function 'f' (100% confidence)\n"
    run = FakeRun([("vulture", (3, hit, ""))], tracked=["lib/stub.py"])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert out["candidates"] == []
    assert out["digest"]["ecosystems"]["python"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["python"]["untrackedFiltered"] == 1


def test_knip_exit1_all_untracked_hits_collected_not_contradiction(tmp_path):
    """Exit 1 with in-scope signals that filter to zero (all untracked) is collected."""
    repo = _node_repo(tmp_path)
    untracked_only = json.dumps({"issues": [
        {"file": "src/untracked.js", "files": [{"name": "src/untracked.js"}], "exports": []},
    ]})
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "untracked.js").write_text("export const y = 1;\n")
    tracked = ["package.json", "node_modules/.gitkeep", "src/tracked.js"]
    run = FakeRun([("knip", (1, untracked_only, ""))], tracked=tracked)
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert out["candidates"] == []
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["node"]["untrackedFiltered"] == 1


def test_knip_filtered_untracked_does_not_trip_contradiction_gate(tmp_path):
    """Post-filter in-scope counting: untracked knip signals must not degrade."""
    repo = _node_repo(tmp_path)
    issues = json.dumps({"issues": [
        {"file": "src/untracked.js", "files": [{"name": "src/untracked.js"}], "exports": []},
    ]})
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "untracked.js").write_text("export const z = 1;\n")
    run = FakeRun([("knip", (1, issues, ""))], tracked=["package.json", "node_modules/.gitkeep"])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected", out.get("reason")
    assert out["candidates"] == []
    assert out["digest"]["ecosystems"]["node"]["untrackedFiltered"] == 1
