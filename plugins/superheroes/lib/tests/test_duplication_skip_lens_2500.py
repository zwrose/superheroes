"""Duplication skip trees: the lens leaves calibrated frozen / generated trees out of both
sides of every pair, the sweep reads the calibration once and refuses to close a filed
record whose pair it never looked at, and the report names each skipped glob and its count.

The sweep's reading function is always monkeypatched here: this module covers the lens,
the sweep wiring and the report, never the real calibration reader.
"""
import os
import shutil
import subprocess

import pytest

import guardian_lens as gl
import guardian_lens_duplication as gld
import guardian_report as gr
import guardian_store as gs
import guardian_sweep as gsw
from guardian_fixtures import (
    FixtureLens, init_calibrated_repo, write_guardian_layer, write_ledger,
)
from test_guardian_lens_duplication import _FakeJscpd, _clone_entry, _report


def _store(tmp_path):
    return str(tmp_path / "store")


def _write(tmp_path, rel, text="seed\n"):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return str(p)


def _skip_ctx(tmp_path, run, globs, *, repo_root=None, cwd=None):
    return {
        "cwd": cwd or str(tmp_path),
        "run": run,
        "config": None,
        "prevDigest": None,
        "duplicationSkip": {
            "globs": globs, "reason": None, "detail": None,
            "repoRoot": repo_root or str(tmp_path),
        },
    }


def _frozen_and_src(tmp_path):
    """Two frozen files, two src files; the stub census walks the cwd for all four."""
    for rel in ("frozen/a.py", "frozen/b.py", "src/a.py", "src/b.py"):
        _write(tmp_path, rel)


# --- skip_matches / pair_touches_skip ----------------------------------------------

def test_skip_matches_returns_first_matching_glob_or_none():
    assert gld.skip_matches("frozen/x/y.py", ["src/*", "frozen/*", "frozen/x/*"]) == "frozen/*"
    assert gld.skip_matches("src/a.py", ["frozen/*"]) is None
    assert gld.skip_matches("src/a.py", []) is None
    # case-sensitive (fnmatchcase), and * crosses /
    assert gld.skip_matches("Frozen/a.py", ["frozen/*"]) is None


def test_pair_touches_skip_matches_either_side(tmp_path):
    cwd = str(tmp_path)
    pid = gld._pair_id("frozen/a.py", "src/b.py")
    assert gld.pair_touches_skip(pid, ["frozen/*"], cwd=cwd) is True
    pid2 = gld._pair_id("src/a.py", "zfrozen/b.py")
    assert gld.pair_touches_skip(pid2, ["zfrozen/*"], cwd=cwd) is True
    assert gld.pair_touches_skip(
        gld._pair_id("src/a.py", "src/b.py"), ["frozen/*"], cwd=cwd) is False


def test_pair_touches_skip_path_containing_pipe_still_matches(tmp_path):
    cwd = str(tmp_path)
    pid = gld._pair_id("src/a|b.py", "src/c.py")
    assert pid == "duplication:src/a|b.py|src/c.py"
    assert gld.pair_touches_skip(pid, ["src/a|b.py"], cwd=cwd) is True
    assert gld.pair_touches_skip(pid, ["src/c.py"], cwd=cwd) is True
    assert gld.pair_touches_skip(pid, ["nope/*"], cwd=cwd) is False


def test_pair_touches_skip_non_duplication_id_is_false(tmp_path):
    cwd = str(tmp_path)
    assert gld.pair_touches_skip("complexity:frozen/a.py|b.py", ["frozen/*"], cwd=cwd) is False
    assert gld.pair_touches_skip("", ["frozen/*"], cwd=cwd) is False
    assert gld.pair_touches_skip(None, ["frozen/*"], cwd=cwd) is False


def test_pair_touches_skip_converts_to_repo_root_relative(tmp_path):
    sub = tmp_path / "pkg"
    sub.mkdir()
    pid = gld._pair_id("generated/a.py", "y.py")
    assert gld.pair_touches_skip(
        pid, ["pkg/generated/*"], cwd=str(sub), repo_root=str(tmp_path)) is True
    # without the root the cwd-relative path is all there is
    assert gld.pair_touches_skip(pid, ["pkg/generated/*"], cwd=str(sub)) is False


# --- lens: filter ------------------------------------------------------------------

def test_stub_jscpd_input_config_never_lists_a_skipped_file(tmp_path):
    _frozen_and_src(tmp_path)
    src_a = str(tmp_path / "src" / "a.py")
    src_b = str(tmp_path / "src" / "b.py")
    report = _report([_clone_entry(src_a, src_b, lines=12, fmt="python")])
    run = _FakeJscpd(report)
    out = gld.DuplicationLens().collect(_skip_ctx(tmp_path, run, ["frozen/*"]))
    assert gl.classify_collect(out)[0] == "collected", out
    assert len(run.configs) == 1
    listed = run.configs[0]["path"]
    rels = sorted(os.path.relpath(p, str(tmp_path)) for p in listed)
    assert rels == ["src/a.py", "src/b.py"]
    assert out["skippedTrees"] == {"globs": [{"glob": "frozen/*", "files": 2}], "files": 2}
    assert out["digest"]["skipGlobs"] == ["frozen/*"]


def test_each_file_counts_once_under_first_matching_glob_in_order(tmp_path):
    _frozen_and_src(tmp_path)
    run = _FakeJscpd(_report([]))
    globs = ["frozen/a*", "frozen/*", "never/*"]
    out = gld.DuplicationLens().collect(_skip_ctx(tmp_path, run, globs))
    assert out["skippedTrees"] == {
        "globs": [
            {"glob": "frozen/a*", "files": 1},
            {"glob": "frozen/*", "files": 1},
            {"glob": "never/*", "files": 0},
        ],
        "files": 2,
    }
    assert out["digest"]["skipGlobs"] == sorted(globs)


def test_subdirectory_cwd_matches_globs_from_the_repo_root(tmp_path):
    # Repo root is tmp_path; the lens runs from pkg/ and sees cwd-relative paths.
    _write(tmp_path, "pkg/generated/x.py")
    _write(tmp_path, "pkg/y.py")
    _write(tmp_path, "pkg/z.py")
    sub = str(tmp_path / "pkg")
    run = _FakeJscpd(_report([]))
    ctx = _skip_ctx(tmp_path, run, ["pkg/generated/*"], repo_root=str(tmp_path), cwd=sub)
    out = gld.DuplicationLens().collect(ctx)
    assert gl.classify_collect(out)[0] == "collected", out
    assert out["skippedTrees"] == {
        "globs": [{"glob": "pkg/generated/*", "files": 1}], "files": 1}
    rels = sorted(os.path.relpath(p, os.path.realpath(sub))
                  for p in run.configs[0]["path"])
    assert rels == ["y.py", "z.py"]


def test_every_tracked_file_skipped_is_not_collected_never_empty_digest(tmp_path):
    _write(tmp_path, "frozen/a.py")
    _write(tmp_path, "frozen/b.py")
    run = _FakeJscpd(_report([]))
    out = gld.DuplicationLens().collect(_skip_ctx(tmp_path, run, ["frozen/*"]))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert reason == "every tracked file matched a duplication skip glob (2 files skipped)"
    assert out["digest"] is None
    assert out["candidates"] == []
    assert out["skippedTrees"] == {"globs": [{"glob": "frozen/*", "files": 2}], "files": 2}
    # jscpd is never spawned with an empty path list
    assert [c for c in run.calls if c[0][0] == "jscpd"] == []


def test_stub_jscpd_reporting_a_skipped_file_anyway_is_not_collected(tmp_path):
    _frozen_and_src(tmp_path)
    report = _report([
        _clone_entry("frozen/a.py", "src/a.py", lines=12, fmt="python"),
    ], sources=2)
    run = _FakeJscpd(report)
    out = gld.DuplicationLens().collect(_skip_ctx(tmp_path, run, ["frozen/*"]))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "outside the tracked-file census" in reason
    assert "frozen/a.py" in reason
    assert out["skippedTrees"]["files"] == 2


@pytest.mark.parametrize("skip", [
    None,
    {"globs": [], "reason": None, "detail": None, "repoRoot": None},
    {"globs": [], "reason": "duplication-skip-unreadable", "detail": "x", "repoRoot": None},
    {"globs": "frozen/*", "reason": None, "detail": None, "repoRoot": None},
    {"globs": ["frozen/*", 7], "reason": None, "detail": None, "repoRoot": None},
    "frozen/*",
])
def test_no_usable_globs_behaves_as_today(tmp_path, skip):
    _frozen_and_src(tmp_path)
    run = _FakeJscpd(_report([]))
    ctx = {"cwd": str(tmp_path), "run": run, "config": None, "prevDigest": None}
    if skip is not None:
        ctx["duplicationSkip"] = skip
    out = gld.DuplicationLens().collect(ctx)
    assert gl.classify_collect(out)[0] == "collected", out
    assert out["skippedTrees"] == {"globs": [], "files": 0}
    assert out["digest"]["skipGlobs"] == []
    assert len(run.configs[0]["path"]) == 4


# --- lens: real jscpd ----------------------------------------------------------------

def _py_body(tag):
    chunks = []
    for i in range(14):
        chunks.append(
            "def %s_fn_%d(x):\n    y = x * %d + %d\n    return y - %d\n" % (tag, i, i, i + 1, i))
    return "\n".join(chunks)


def _git_env():
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _real_repo_with_two_pairs(tmp_path):
    repo = str(tmp_path)
    env = _git_env()
    subprocess.run(["git", "-c", "init.defaultBranch=main", "init", "-q"],
                   cwd=repo, check=True, env=env)
    frozen_body = _py_body("frozen")
    src_body = _py_body("live")
    _write(tmp_path, "frozen/a.py", frozen_body)
    _write(tmp_path, "frozen/b.py", frozen_body)
    _write(tmp_path, "src/a.py", src_body)
    _write(tmp_path, "src/b.py", src_body)
    subprocess.run(["git", "add", "frozen", "src"], cwd=repo, check=True, env=env)
    return repo, env


def _real_run(env):
    def run(argv, **kwargs):
        return subprocess.run(
            argv, capture_output=True, text=True,
            timeout=kwargs.get("timeout"), cwd=kwargs.get("cwd"), env=env)
    return run


@pytest.mark.skipif(not shutil.which("jscpd"), reason="jscpd not installed")
def test_real_jscpd_skipped_tree_reaches_neither_side_of_any_pair(tmp_path):
    repo, env = _real_repo_with_two_pairs(tmp_path)
    ctx = {
        "cwd": repo, "run": _real_run(env), "config": None, "prevDigest": None,
        "duplicationSkip": {
            "globs": ["frozen/*"], "reason": None, "detail": None, "repoRoot": repo},
    }
    out = gld.DuplicationLens().collect(ctx)
    status, reason = gl.classify_collect(out)
    assert status == "collected", (status, reason, out.get("diagnostics"))
    ids = {c["id"] for c in out["candidates"]}
    assert gld._pair_id("src/a.py", "src/b.py") in ids
    assert not [i for i in ids if "frozen/" in i], ids
    for c in out["candidates"]:
        assert not [f for f in c["files"] if f.startswith("frozen/")]
    assert out["skippedTrees"] == {"globs": [{"glob": "frozen/*", "files": 2}], "files": 2}


@pytest.mark.skipif(not shutil.which("jscpd"), reason="jscpd not installed")
def test_real_jscpd_control_without_skip_reports_both_pairs(tmp_path):
    repo, env = _real_repo_with_two_pairs(tmp_path)
    ctx = {"cwd": repo, "run": _real_run(env), "config": None, "prevDigest": None}
    out = gld.DuplicationLens().collect(ctx)
    status, reason = gl.classify_collect(out)
    assert status == "collected", (status, reason, out.get("diagnostics"))
    ids = {c["id"] for c in out["candidates"]}
    assert gld._pair_id("src/a.py", "src/b.py") in ids
    assert gld._pair_id("frozen/a.py", "frozen/b.py") in ids
    assert out["skippedTrees"] == {"globs": [], "files": 0}


# --- sweep ---------------------------------------------------------------------------

class _DupLens(FixtureLens):
    """A lens named ``duplication`` that returns a chosen result and records its ctx."""

    def __init__(self, result, **kwargs):
        super().__init__(name="duplication", **kwargs)
        self._result = result
        self.last_ctx = None

    def collect(self, ctx):
        self.last_ctx = ctx
        return dict(self._result)


_FILED_PID = "duplication:frozen/a.py|src/a.py"
_SKIPPED = {"globs": [{"glob": "frozen/*", "files": 2}], "files": 2}


def _filed_duplication_repo(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    root = _store(tmp_path)
    write_guardian_layer(tmp_path, {"vitals": False})
    write_ledger(tmp_path, [{
        "id": _FILED_PID,
        "disposition": "filed",
        "date": "2026-07-01",
        "issue": "#123",
        "metricAtDisposition": {"metric": 5},
        "reason": None,
        "reraiseWhen": None,
        "adjudicatedIn": "s0",
    }], root=root)
    return repo, root


def _skip_read(repo, globs, reason=None, detail=None):
    return lambda cwd, root: {
        "globs": list(globs), "reason": reason, "detail": detail, "repoRoot": repo}


@pytest.mark.parametrize("globs, closes", [
    (["frozen/*"], False),   # the pair touches a skipped tree: stays filed
    (["other/*"], True),     # control: a pair no glob touches is closed as before
])
def test_filed_duplication_record_in_skipped_tree_is_never_closed(
        tmp_path, monkeypatch, globs, closes):
    repo, root = _filed_duplication_repo(tmp_path)
    monkeypatch.setattr(gsw, "_read_duplication_skip", _skip_read(repo, globs))
    monkeypatch.setattr(gsw, "_resolve_issue_state", lambda *a, **k: "closed")
    lens = _DupLens({"candidates": [], "digest": {"v": 2}, "skippedTrees": _SKIPPED})

    bundle = gsw.collect(repo, lenses=[lens], root=root)

    obs = bundle["filedObservations"][_FILED_PID]
    assert obs["present"] is False
    assert obs["issueState"] == "closed"
    assert bool(obs.get("skipped")) is (not closes)
    records = gs.read_ledger(repo, root=root)["records"]
    new_records, advances = gsw._close_filed_records(
        records, bundle["filedObservations"], "sweep-2500")
    by_id = {r["id"]: r for r in new_records}
    if closes:
        assert by_id[_FILED_PID]["disposition"] == "verified-fixed"
        assert len(advances) == 1
    else:
        assert by_id[_FILED_PID]["disposition"] == "filed"
        assert advances == []


def test_bundle_carries_the_read_and_the_lens_skipped_trees(tmp_path, monkeypatch):
    repo, root = _filed_duplication_repo(tmp_path)
    monkeypatch.setattr(gsw, "_read_duplication_skip", _skip_read(repo, ["frozen/*"]))
    monkeypatch.setattr(gsw, "_resolve_issue_state", lambda *a, **k: "open")
    lens = _DupLens({"candidates": [], "digest": {"v": 2}, "skippedTrees": _SKIPPED})
    other = FixtureLens(name="other-lens", emit_normal=True)

    bundle = gsw.collect(repo, lenses=[lens, other], root=root)

    assert bundle["skippedTrees"] == {
        "read": {"globs": ["frozen/*"], "reason": None, "detail": None},
        "lenses": {"duplication": _SKIPPED},
    }
    # every lens ctx carries the one read
    assert lens.last_ctx["duplicationSkip"]["globs"] == ["frozen/*"]
    assert lens.last_ctx["duplicationSkip"]["repoRoot"] == repo


def test_not_collected_lens_still_reports_its_skipped_trees(tmp_path, monkeypatch):
    repo, root = _filed_duplication_repo(tmp_path)
    monkeypatch.setattr(gsw, "_read_duplication_skip", _skip_read(repo, ["frozen/*"]))
    monkeypatch.setattr(gsw, "_resolve_issue_state", lambda *a, **k: "closed")
    lens = _DupLens({
        "candidates": [], "digest": None, "skippedTrees": _SKIPPED,
        "status": "not-collected",
        "reason": "every tracked file matched a duplication skip glob (2 files skipped)",
    })
    bundle = gsw.collect(repo, lenses=[lens], root=root)
    assert bundle["skippedTrees"]["lenses"] == {"duplication": _SKIPPED}
    # a lens that never collected observes nothing, so nothing can close
    assert _FILED_PID not in bundle["filedObservations"]


def test_read_failure_is_recorded_in_the_bundle(tmp_path, monkeypatch):
    repo = init_calibrated_repo(tmp_path)
    monkeypatch.setattr(
        gsw, "_read_duplication_skip",
        _skip_read(repo, [], "duplication-skip-unreadable", "OSError: nope"))
    bundle = gsw.collect(repo, lenses=[FixtureLens(emit_normal=True)])
    assert bundle["skippedTrees"] == {
        "read": {"globs": [], "reason": "duplication-skip-unreadable",
                 "detail": "OSError: nope"},
        "lenses": {},
    }


def test_sweep_reader_returns_the_readers_globs_with_repo_root(tmp_path, monkeypatch):
    import project_config
    repo = init_calibrated_repo(tmp_path)
    monkeypatch.setattr(
        project_config, "read_duplication_skip",
        lambda cwd, root=None: {"globs": ["frozen/*"], "reason": None, "detail": None},
        raising=False)
    got = gsw._read_duplication_skip(repo, None)
    assert got == {"globs": ["frozen/*"], "reason": None, "detail": None,
                   "repoRoot": gsw._repo_root(repo)}


def test_sweep_reader_that_raises_skips_nothing_and_says_so(tmp_path, monkeypatch):
    import project_config

    def boom(cwd, root=None):
        raise RuntimeError("boom")

    repo = init_calibrated_repo(tmp_path)
    monkeypatch.setattr(project_config, "read_duplication_skip", boom, raising=False)
    got = gsw._read_duplication_skip(repo, None)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-unreadable"
    assert "RuntimeError" in got["detail"] and "boom" in got["detail"]
    assert got["repoRoot"] == gsw._repo_root(repo)


@pytest.mark.parametrize("bad", [
    {"globs": "frozen/*", "reason": None, "detail": None},
    {"globs": ["frozen/*", 3], "reason": None, "detail": None},
    {"reason": None, "detail": None},
    None,
])
def test_sweep_reader_result_that_is_not_a_glob_list_skips_nothing(
        tmp_path, monkeypatch, bad):
    import project_config
    repo = init_calibrated_repo(tmp_path)
    monkeypatch.setattr(
        project_config, "read_duplication_skip", lambda cwd, root=None: bad, raising=False)
    got = gsw._read_duplication_skip(repo, None)
    assert got["globs"] == []
    assert got["reason"] == "duplication-skip-unreadable"


def test_sweep_reader_unresolvable_repo_root_is_none(tmp_path, monkeypatch):
    import project_config

    def no_root(cwd):
        raise RuntimeError("no repo")

    monkeypatch.setattr(gsw, "_repo_root", no_root)
    monkeypatch.setattr(
        project_config, "read_duplication_skip",
        lambda cwd, root=None: {"globs": [], "reason": None, "detail": None},
        raising=False)
    got = gsw._read_duplication_skip(str(tmp_path), None)
    assert got["repoRoot"] is None
    assert got["globs"] == []


# --- report ----------------------------------------------------------------------------

def _section(md):
    start = md.index(gr.HEADER_SKIPPED)
    end = md.index(gr.HEADER_FUNNEL)
    assert start < end
    return md[start:end]


def _render(skipped, **extra):
    bundle = {}
    if skipped is not None:
        bundle["skippedTrees"] = skipped
    bundle.update(extra)
    return gr.render(bundle, [], {"byId": {}})


def test_report_lists_each_glob_with_its_count_and_a_total():
    md = _render({
        "read": {"globs": ["frozen/*", "gen/*"], "reason": None, "detail": None},
        "lenses": {"duplication": {
            "globs": [{"glob": "frozen/*", "files": 2}, {"glob": "gen/*", "files": 0}],
            "files": 2}},
    })
    lines = _section(md).splitlines()
    assert lines[0] == "## Skipped trees"
    assert "- `frozen/*`: 2 file(s) skipped by the duplication lens" in lines
    assert "- `gen/*`: 0 file(s) skipped by the duplication lens" in lines
    assert lines.index("- `frozen/*`: 2 file(s) skipped by the duplication lens") < \
        lines.index("- `gen/*`: 0 file(s) skipped by the duplication lens")
    assert "- 2 file(s) skipped in all" in lines
    assert "_None._" not in lines


def test_report_without_duplication_entry_says_count_not_measured_and_omits_total():
    md = _render({
        "read": {"globs": ["frozen/*"], "reason": None, "detail": None},
        "lenses": {},
    })
    lines = _section(md).splitlines()
    assert ("- `frozen/*`: file count not measured "
            "(the duplication lens did not reach its census)") in lines
    assert not [ln for ln in lines if "skipped in all" in ln]


def test_report_states_an_unreadable_value_with_reason_and_detail():
    md = _render({
        "read": {"globs": [], "reason": "duplication-skip-unreadable",
                 "detail": "RuntimeError: boom"},
        "lenses": {},
    })
    lines = _section(md).splitlines()
    assert ("- nothing skipped: the duplication skip trees could not be read "
            "(duplication-skip-unreadable): RuntimeError: boom") in lines
    assert "_None._" not in lines


def test_report_unreadable_value_without_detail_has_no_colon_tail():
    md = _render({
        "read": {"globs": [], "reason": "duplication-skip-malformed", "detail": None},
        "lenses": {},
    })
    lines = _section(md).splitlines()
    assert ("- nothing skipped: the duplication skip trees could not be read "
            "(duplication-skip-malformed)") in lines


@pytest.mark.parametrize("skipped", [
    None,
    {"read": {"globs": [], "reason": None, "detail": None}, "lenses": {}},
])
def test_report_with_nothing_skipped_says_none(skipped):
    lines = _section(_render(skipped)).splitlines()
    assert lines[0] == "## Skipped trees"
    assert "_None._" in lines


def test_skipped_trees_section_sits_after_report_card_and_before_funnel():
    md = _render(None)
    assert md.index(gr.HEADER_REPORT_CARD) < md.index(gr.HEADER_SKIPPED) \
        < md.index(gr.HEADER_FUNNEL)
