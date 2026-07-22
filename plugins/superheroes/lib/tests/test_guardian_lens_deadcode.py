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
    """Dispatches on a substring of the joined argv. Unstubbed argv fails loudly."""

    def __init__(self, table):
        self.table = list(table)
        self.calls = []

    def __call__(self, argv, **kwargs):
        line = " ".join(argv)
        self.calls.append(line)
        for key, val in self.table:
            if key in line:
                if isinstance(val, BaseException):
                    raise val
                return _R(*val)
        return _R(127, "", "TEST-STUB-MISSING for %s" % line)

    def ran(self, key):
        return any(key in line for line in self.calls)


def _repo(tmp_path, files):
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return str(tmp_path)


def _py_repo(tmp_path, extra=None):
    files = {"pyproject.toml": "[project]\nname = \"x\"\n"}
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
    assert gld.LENS.collector_version == "1.0.0"
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
    repo = _py_repo(tmp_path)
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
    repo = _py_repo(tmp_path)
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
    repo = _py_repo(tmp_path)
    cid = "deadcode:vulture:plugins/superheroes/lib/foo.py:variable:bar"
    line10 = "plugins/superheroes/lib/foo.py:10: unused variable 'bar' (60% confidence)\n"
    line99 = "plugins/superheroes/lib/foo.py:99: unused variable 'bar' (60% confidence)\n"

    out1 = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, line10, ""))])))
    assert _by_id(out1["candidates"])[cid]["lines"] == [10]

    out2 = gld.LENS.collect(_ctx(repo, FakeRun([("vulture", (3, line99, ""))])))
    assert _by_id(out2["candidates"])[cid]["lines"] == [99]
    # Same id both times — moving the symbol's line never changes its identity.
    assert cid in _by_id(out1["candidates"]) and cid in _by_id(out2["candidates"])


def test_vulture_argv_operands_are_absolute(tmp_path):
    """R: neutral-cwd false-clean guard — the source operand must be the ABSOLUTE repo
    root, never a bare `"."` that would resolve against the seam's neutral cwd."""
    repo = _py_repo(tmp_path)
    run = FakeRun([("vulture", (0, "", ""))])
    out = gld.LENS.collect(_ctx(repo, run))
    argv = out["digest"]["ecosystems"]["python"]["argv"]
    assert argv[0] == "vulture"
    # The single source operand is argv[1]: absolute, and never ".".
    assert argv[1] == os.path.realpath(repo)
    assert os.path.isabs(argv[1]), argv
    assert "." not in argv[1:2]
    # PATH-only — no venv-bin / python-interpreter ladder in the resolution any more.
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
    repo = _node_repo(tmp_path)
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
    assert run.calls == []


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


# ------------------------------------------------------------------- mixed / combining

def test_both_ecosystems_collected(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\nname = \"x\"\n",
        "package.json": "{}\n",
        "node_modules/.gitkeep": "",
    })
    run = FakeRun([
        ("vulture", (3, VULTURE_EXCERPT, "")),
        ("knip", (1, KNIP_JSON, "")),
    ])
    out = gld.LENS.collect(_ctx(repo, run))
    assert out["status"] == "collected"
    assert out["digest"]["ecosystems"]["python"]["status"] == "collected"
    assert out["digest"]["ecosystems"]["node"]["status"] == "collected"
    tools = set(c["tool"] for c in out["candidates"])
    assert tools == {"vulture", "knip"}


def test_one_ecosystem_partial_carries_prev_forward_no_false_resolved(tmp_path):
    repo = _repo(tmp_path, {
        "pyproject.toml": "[project]\nname = \"x\"\n",
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
    ])
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
