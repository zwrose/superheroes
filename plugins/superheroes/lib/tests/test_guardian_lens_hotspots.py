"""Hotspots lens — git churn × radon/lizard complexity. Never invokes real tools.

New contract (post #559/#560/#561): every tool call routes through
``guardian_collect.run_tool`` and the injected ``ctx["run"]`` seam (git churn, radon, and
lizard). Degradation is a ``not-collected`` / ``partial`` status return — never a raised
exception. The previous digest is read as camelCase ``ctx["prevDigest"]``.
"""
import csv
import json
import os
import textwrap
from types import SimpleNamespace

import pytest

import guardian_lens as gl
import guardian_lens_hotspots as hot
from test_guardian_conformance import assert_lens_conformance


# ---------------------------------------------------------------------------
# Multi-tool stub — one callable dispatches git / radon / lizard off argv.
# ---------------------------------------------------------------------------

class Tools:
    """Return crafted stdout through the ctx['run'] seam; never spawn a collector.

    Models run_tool's injected call: run(argv, capture_output=..., text=..., timeout=...,
    cwd=...). Dispatches on argv[0] and the git subcommand flags.
    """

    def __init__(self, *, shallow="false\n", log="", numstat="", lsfiles=(),
                 radon=None, lizard=None, fail_markers=None):
        self.shallow = shallow
        self.log = log
        self.numstat = numstat
        self.lsfiles = list(lsfiles)
        self.radon = radon
        self.lizard = lizard
        # fail_markers: {token: rc_or_Exception} — force a nonzero/raise for a call whose
        # argv contains token (exact element match).
        self.fail_markers = fail_markers or {}
        self.calls = []

    @staticmethod
    def _R(stdout, rc=0):
        return SimpleNamespace(stdout=stdout, stderr="" if rc == 0 else "err",
                               returncode=rc)

    def __call__(self, argv, **kwargs):
        argv = [str(a) for a in argv]
        self.calls.append(argv)
        for token, action in self.fail_markers.items():
            if token in argv:
                if isinstance(action, Exception):
                    raise action
                return self._R("", action)
        prog = os.path.basename(argv[0])
        if prog == "git":
            if "rev-parse" in argv:
                return self._R(self.shallow)
            if "--numstat" in argv:
                return self._R(self.numstat)
            if "log" in argv:
                return self._R(self.log)
            if "ls-files" in argv:
                return self._R("".join(p + "\0" for p in self.lsfiles))
        if prog == "radon":
            payload = self.radon
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            return self._R(payload if payload is not None else "")
        if prog == "lizard":
            return self._R(self.lizard if self.lizard is not None else "")
        return self._R("", 0)


def _ctx(cwd, run, *, config=None, prev_digest=None):
    return {"cwd": str(cwd), "run": run, "config": config, "prevDigest": prev_digest}


def _write(tmp_path, rel, lines):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(("x\n" * lines) if isinstance(lines, int) else lines, encoding="utf-8")
    return rel


# ---------------------------------------------------------------------------
# conformance + module shape
# ---------------------------------------------------------------------------

def test_lens_instance_passes_conformance():
    """The shipped LENSES[0] instance must satisfy every honesty invariant."""
    assert_lens_conformance(hot.LENSES[0])


def test_module_exposes_lenses_tuple():
    assert hot.LENSES == (hot.LENS,)
    assert isinstance(hot.LENSES[0], hot.HotspotsLens)
    assert hot.LENSES[0].name == "hotspots"


def test_conformance_clean_probe_collects_findings_probe_degrades(tmp_path):
    """Directly exercise the two conformance payloads through collect()."""
    case = hot.LENSES[0].conformance_cases()["reported-nonzero-parsed-zero"]

    def make_run(stdout):
        def run(argv, **kwargs):
            return SimpleNamespace(stdout=stdout, stderr="", returncode=case["exit"])
        return run

    clean = hot.HotspotsLens().collect(_ctx(tmp_path, make_run(case["clean_stdout"])))
    assert gl.classify_collect(clean) == ("collected", None)
    assert clean["candidates"] == []

    findings = hot.HotspotsLens().collect(_ctx(tmp_path, make_run(case["stdout"])))
    status, reason = gl.classify_collect(findings)
    assert status == "not-collected"
    assert findings["digest"] is None
    assert reason


# ---------------------------------------------------------------------------
# Fixture parsers
# ---------------------------------------------------------------------------

def test_parse_radon_json_error_entry_and_nesting():
    by_path, error_paths = hot.parse_radon_json(json.dumps({
        "a.py": [{"complexity": 46, "name": "render", "lineno": 34}],
        "bad.py": [{"error": "invalid syntax"}],
        "classy.py": [{
            "type": "class", "name": "C", "complexity": 5, "lineno": 1,
            "methods": [{"type": "method", "complexity": 120, "name": "explosive",
                         "lineno": 10}],
        }],
        "nest.py": [{
            "type": "function", "complexity": 5, "name": "outer", "lineno": 1,
            "closures": [{"type": "function", "complexity": 88, "name": "inner",
                          "lineno": 3, "closures": []}],
        }],
    }))
    assert by_path["a.py"]["maxFunctionCCN"] == 46
    assert by_path["a.py"]["worstFunction"]["name"] == "render"
    assert "bad.py" not in by_path
    assert "bad.py" in error_paths
    # class aggregate not scored; nested method is
    assert by_path["classy.py"]["maxFunctionCCN"] == 120
    assert by_path["classy.py"]["worstFunction"]["name"] == "explosive"
    # closure flattened
    assert by_path["nest.py"]["maxFunctionCCN"] == 88
    assert by_path["nest.py"]["worstFunction"]["name"] == "inner"


def test_parse_radon_rejects_non_dict_shape_degraded():
    with pytest.raises(hot._Degraded) as exc:
        hot.parse_radon_json("[]")
    assert "contract mismatch" in str(exc.value)

    with pytest.raises(hot._Degraded):
        hot.parse_radon_json(json.dumps({"a.py": {"not": "a list"}}))


def test_parse_lizard_csv_columns():
    text = "30,82,10,0,30,reviewPanel@1-30@panel.js,panel.js,reviewPanel,sig,1,30\n"
    by_path = hot.parse_lizard_csv(text)
    assert by_path["panel.js"]["maxFunctionCCN"] == 82
    assert by_path["panel.js"]["worstFunction"]["name"] == "reviewPanel"


def test_numstat_parser_skips_binary_and_brace_rename_paths():
    sample = textwrap.dedent("""\
        10\t2\tsrc/a.py
        -\t-\tassets/logo.png
        5\t1\t{plugins/superheroes => .claude}/skills/X.md
        3\t0\tplugins/superheroes/skills/Y.md
        1\t1\tfoo => bar/renamed.py
    """)
    parsed = hot.parse_numstat(sample)
    paths = set(parsed)
    assert "src/a.py" in paths
    assert "plugins/superheroes/skills/Y.md" in paths
    assert "assets/logo.png" not in paths
    for p in paths:
        assert "=>" not in p and "{" not in p
    assert parsed["src/a.py"] == {"added": 10, "deleted": 2}


def test_relative_churn_skips_zero_line_files():
    assert hot.relative_churn(added=10, deleted=5, current_lines=0) is None
    assert hot.relative_churn(added=10, deleted=5, current_lines=100) == 0.15


# ---------------------------------------------------------------------------
# Size normalization
# ---------------------------------------------------------------------------

def test_size_normalization_ranks_relative_not_raw():
    window = {"historyTruncated": False, "requestedSince": "x",
              "observedSince": "x", "commitsObserved": 1}
    big = hot.build_candidate(
        path="big.py", added=400, deleted=100, current_lines=10000,
        max_ccn=20, worst={"name": "big_fn", "line": 1}, window=window)
    small = hot.build_candidate(
        path="small.py", added=30, deleted=10, current_lines=50,
        max_ccn=20, worst={"name": "small_fn", "line": 1}, window=window)
    assert big["rawChurn"] > small["rawChurn"]
    assert big["relativeChurn"] < small["relativeChurn"]
    assert small["hotspotScore"] > big["hotspotScore"]
    ranked = hot.rank_and_cap([big, small], top_n=25)
    assert ranked[0]["path"] == "small.py"
    assert ranked[0]["metric"] == ranked[0]["hotspotScore"]
    assert ranked[0]["rawChurn"] < ranked[1]["rawChurn"]


def test_abs_paths_always_returns_absolute(tmp_path):
    abs_repo = os.path.realpath(str(tmp_path))
    out = hot._abs_paths(abs_repo, ["a.py", "sub/b.py", os.path.join(abs_repo, "c.py")])
    assert all(os.path.isabs(p) for p in out)
    assert out[0] == os.path.join(abs_repo, "a.py")
    assert out[1] == os.path.join(abs_repo, "sub/b.py")
    assert out[2] == os.path.join(abs_repo, "c.py")


# ---------------------------------------------------------------------------
# git probes: tracked ∩ exists, window, and failure → not-collected
# ---------------------------------------------------------------------------

def test_tracked_existing_files_intersects_disk(tmp_path):
    _write(tmp_path, "keep.py", 5)
    run = Tools(lsfiles=["keep.py", "gone.py", "{a => b}/x.py"])
    tracked = hot.tracked_existing_files(_ctx(tmp_path, run), os.path.realpath(str(tmp_path)))
    assert "keep.py" in tracked
    assert "gone.py" not in tracked          # not on disk
    assert not any("=>" in t or "{" in t for t in tracked)  # brace-rename filtered


def test_tracked_existing_files_degrades_on_git_failure(tmp_path):
    run = Tools(lsfiles=["a.py"], fail_markers={"ls-files": 128})
    with pytest.raises(hot._Degraded) as exc:
        hot.tracked_existing_files(_ctx(tmp_path, run), str(tmp_path))
    assert "ls-files" in str(exc.value)


def test_observe_window_shallow_and_no_fetch(tmp_path):
    run = Tools(shallow="true\n", log="2026-01-01T00:00:00+00:00\n2026-02-01T00:00:00+00:00\n")
    window = hot.observe_window(_ctx(tmp_path, run), str(tmp_path), since="90 days")
    assert window["historyTruncated"] is True
    assert window["observedSince"] == "2026-01-01"
    assert window["commitsObserved"] == 2
    flat = " ".join(" ".join(a) for a in run.calls)
    assert "fetch" not in flat and "--unshallow" not in flat


def test_observe_window_degrades_on_unexpected_shallow_output(tmp_path):
    """`git rev-parse --is-shallow-repository` must report true/false; garbage degrades."""
    run = Tools(shallow="not-a-bool\n")
    with pytest.raises(hot._Degraded) as exc:
        hot.observe_window(_ctx(tmp_path, run), str(tmp_path))
    assert "unexpected output" in str(exc.value)

    run_empty = Tools(shallow="")
    with pytest.raises(hot._Degraded):
        hot.observe_window(_ctx(tmp_path, run_empty), str(tmp_path))


def test_observe_window_degrades_on_git_failure(tmp_path):
    run = Tools(shallow="false\n", fail_markers={"--is-shallow-repository": 128})
    with pytest.raises(hot._Degraded) as exc:
        hot.observe_window(_ctx(tmp_path, run), str(tmp_path))
    assert "shallow" in str(exc.value)


def test_collect_churn_degrades_on_git_failure(tmp_path):
    run = Tools(fail_markers={"--numstat": 128})
    with pytest.raises(hot._Degraded) as exc:
        hot._collect_churn(_ctx(tmp_path, run), str(tmp_path), "90 days")
    assert "numstat" in str(exc.value)


def test_collect_degrades_not_collected_on_git_failure(tmp_path):
    """A git failure inside collect() surfaces as not-collected, never a raised exception."""
    _write(tmp_path, "a.py", 10)
    run = Tools(shallow="false\n", fail_markers={"ls-files": 128},
                numstat="10\t0\ta.py\n", lsfiles=["a.py"],
                radon={"a.py": [{"complexity": 15, "name": "f", "lineno": 1}]})
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "ls-files" in reason


# ---------------------------------------------------------------------------
# End-to-end collect
# ---------------------------------------------------------------------------

def _basic_tools(tmp_path, *, numstat, lsfiles, radon=None, lizard=None, log=None):
    return Tools(
        shallow="false\n",
        log=log if log is not None else "2026-05-01T00:00:00+00:00\n",
        numstat=numstat, lsfiles=lsfiles, radon=radon, lizard=lizard,
    )


def test_full_collect_ranks_by_relative_churn(tmp_path):
    _write(tmp_path, "big.py", 210)
    _write(tmp_path, "small.py", 21)
    run = _basic_tools(
        tmp_path,
        numstat="50\t0\tbig.py\n40\t0\tsmall.py\n",
        lsfiles=["big.py", "small.py"],
        radon={
            "big.py": [{"complexity": 12, "name": "big", "lineno": 1}],
            "small.py": [{"complexity": 12, "name": "small", "lineno": 1}],
        },
    )
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    assert gl.classify_collect(out)[0] == "collected"
    cands = out["candidates"]
    assert [c["path"] for c in cands] == ["small.py", "big.py"]
    by_path = {c["path"]: c for c in cands}
    assert by_path["small.py"]["rawChurn"] < by_path["big.py"]["rawChurn"]
    assert by_path["small.py"]["relativeChurn"] > by_path["big.py"]["relativeChurn"]
    assert by_path["small.py"]["hotspotScore"] > by_path["big.py"]["hotspotScore"]
    assert "historyTruncated" in cands[0]
    assert out["diagnostics"]["complexityCoverage"]["python"] == "collected"
    assert out["diagnostics"]["complexityCoverage"]["javascript"] == "not-collected"


def test_radon_abs_path_keys_normalized_to_relative(tmp_path):
    """radon returns absolute keys for absolute inputs; they must map back to repo-rel."""
    _write(tmp_path, "hot.py", 20)
    abs_repo = os.path.realpath(str(tmp_path))
    run = _basic_tools(
        tmp_path, numstat="20\t0\thot.py\n",
        lsfiles=["hot.py"],
        radon={os.path.join(abs_repo, "hot.py"): [
            {"complexity": 15, "name": "hot", "lineno": 1}]},
    )
    out = hot.HotspotsLens().collect({"cwd": abs_repo, "run": run})
    assert [c["path"] for c in out["candidates"]] == ["hot.py"]


def test_lizard_only_js_collects(tmp_path):
    _write(tmp_path, "hot.js", 20)
    run = _basic_tools(
        tmp_path, numstat="20\t0\thot.js\n",
        lsfiles=["hot.js"],
        lizard="20,15,10,0,20,hot@1-20@hot.js,hot.js,hot,sig,1,20\n",
    )
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    cov = out["diagnostics"]["complexityCoverage"]
    assert cov["javascript"] == "collected"
    assert cov["python"] == "not-collected"
    assert [c["path"] for c in out["candidates"]] == ["hot.js"]


def test_no_matching_files_collects_empty(tmp_path):
    """Churn on a non-py/js tracked file → no collectors, clean collected-empty."""
    _write(tmp_path, "README.md", "hi\n")
    run = _basic_tools(tmp_path, numstat="3\t0\tREADME.md\n", lsfiles=["README.md"])
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    assert gl.classify_collect(out)[0] == "collected"
    assert out["candidates"] == []
    cov = out["diagnostics"]["complexityCoverage"]
    assert cov["python"] == "not-collected" and cov["javascript"] == "not-collected"
    assert not any(os.path.basename(a[0]) in ("radon", "lizard") for a in run.calls)


# ---------------------------------------------------------------------------
# I4 fail-direction: not-collected vs partial
# ---------------------------------------------------------------------------

def test_both_needed_tools_fail_not_collected(tmp_path):
    _write(tmp_path, "a.py", 10)
    _write(tmp_path, "b.js", 10)
    run = _basic_tools(
        tmp_path, numstat="10\t0\ta.py\n10\t0\tb.js\n", lsfiles=["a.py", "b.js"],
        radon="", lizard="")  # both empty → both needed languages failed
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "python" in reason and "javascript" in reason


def test_only_needed_language_fails_not_collected(tmp_path):
    """radon empty for the only needed language (python) → not-collected, not partial."""
    _write(tmp_path, "a.py", 10)
    run = _basic_tools(tmp_path, numstat="10\t0\ta.py\n", lsfiles=["a.py"], radon="")
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "radon returned empty output" in reason


def test_one_language_collects_other_fails_is_partial_and_merges_prev(tmp_path):
    """Python collected, lizard empty with js files present → partial, baseline preserved
    for the js portion (no erasure, no false resolved)."""
    _write(tmp_path, "a.py", 20)
    _write(tmp_path, "b.js", 20)
    prev = {"schemaVersion": 1, "files": {"hotspots:b.js": {"score": 9.0, "ccn": 80}}}
    run = _basic_tools(
        tmp_path, numstat="20\t0\ta.py\n20\t0\tb.js\n", lsfiles=["a.py", "b.js"],
        radon={"a.py": [{"complexity": 15, "name": "f", "lineno": 1}]},
        lizard="")  # js needed, lizard empty → javascript failed
    lens = hot.HotspotsLens()
    out = lens.collect(_ctx(tmp_path, run, prev_digest=prev))
    status, reason = gl.classify_collect(out)
    assert status == "partial"
    assert "javascript" in reason
    # python candidate present; js prior carried forward (not erased).
    assert "hotspots:a.py" in {c["id"] for c in out["candidates"]}
    assert out["digest"]["files"]["hotspots:b.js"] == {"score": 9.0, "ccn": 80}
    # diff must not report the carried js file as resolved.
    d = lens.diff(prev, out["digest"])
    assert "hotspots:b.js" not in d["resolved"]


def test_lizard_empty_output_guard_for_needed_js(tmp_path):
    """Empty lizard output for tracked js is a failure (mirrors radon's empty guard)."""
    _write(tmp_path, "b.js", 10)
    run = _basic_tools(tmp_path, numstat="10\t0\tb.js\n", lsfiles=["b.js"], lizard="")
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "lizard returned empty output" in reason


# ---------------------------------------------------------------------------
# Honesty gate: churn reported but zero measurable surface
# ---------------------------------------------------------------------------

def test_churn_reported_zero_tracked_degrades(tmp_path):
    """git reports churn but ls-files yields zero tracked+existing files → not-collected."""
    run = _basic_tools(tmp_path, numstat="10\t2\tghost.py\n7\t3\tvanished.py\n",
                       lsfiles=[])  # nothing on disk / tracked
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "no measurable surface" in reason


# ---------------------------------------------------------------------------
# I5: per-language join anomaly
# ---------------------------------------------------------------------------

def test_join_anomaly_per_language_not_masked(tmp_path):
    """A JS join failure must degrade even though Python produced candidates."""
    coverage = {"python": "collected", "javascript": "collected"}
    churn = {"a.py": {"added": 10, "deleted": 0}, "b.js": {"added": 10, "deleted": 0}}
    complexity = {"a.py": {"maxFunctionCCN": 15, "worstFunction": {"name": "f", "line": 1}}}
    anomaly = hot._join_anomaly(
        coverage, py_paths=["a.py"], js_paths=["b.js"], churn=churn, complexity=complexity)
    assert anomaly is not None
    assert "javascript" in anomaly  # JS join failed
    assert "python" not in anomaly  # python joined cleanly


def test_join_anomaly_degrades_collect(tmp_path, monkeypatch):
    """Collected complexity that never joins churn∩tracked must degrade, not look clean."""
    _write(tmp_path, "hot.py", 20)
    run = _basic_tools(tmp_path, numstat="20\t0\thot.py\n",
                       lsfiles=["hot.py"],
                       radon={"hot.py": [{"complexity": 15, "name": "hot", "lineno": 1}]})
    real = hot._normalize_complexity_paths
    monkeypatch.setattr(hot, "_normalize_complexity_paths",
                        lambda cwd, cx: {"NOT_TRACKED.py": v for v in
                                         (real(cwd, cx) or {}).values()})
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "join anomaly" in reason


# ---------------------------------------------------------------------------
# diff + red lines
# ---------------------------------------------------------------------------

def test_diff_new_worsened_resolved_and_prev_none():
    cur = {"schemaVersion": 1, "files": {
        "hotspots:a.py": {"score": 2.0, "ccn": 12},
        "hotspots:b.py": {"score": 5.0, "ccn": 20},
    }}
    prev = {"schemaVersion": 1, "files": {
        "hotspots:b.py": {"score": 3.0, "ccn": 18},
        "hotspots:c.py": {"score": 1.0, "ccn": 10},
    }}
    d = hot.LENS.diff(prev, cur)
    assert set(d["new"]) == {"hotspots:a.py"}
    assert set(d["worsened"]) == {"hotspots:b.py"}
    assert set(d["resolved"]) == {"hotspots:c.py"}

    d0 = hot.LENS.diff(None, cur)
    assert set(d0["new"]) == {"hotspots:a.py", "hotspots:b.py"}
    assert d0["worsened"] == [] and d0["resolved"] == []

    d1 = hot.LENS.diff({"no": "files"}, cur)
    assert set(d1["new"]) == {"hotspots:a.py", "hotspots:b.py"}


def test_diff_returns_only_three_keys():
    cur = {"schemaVersion": 1, "files": {"hotspots:a.py": {"score": 1.0, "ccn": 12}},
           "surfaceIds": ["hotspots:a.py"]}
    assert set(hot.LENS.diff(None, cur).keys()) == {"new", "worsened", "resolved"}
    assert set(hot.LENS.diff({"files": {}}, cur).keys()) == {"new", "worsened", "resolved"}


def test_diff_on_none_digest_emits_no_resolved():
    """Stopped-looking (digest None) must never emit resolved ids, even with a prior."""
    prev = {"schemaVersion": 1, "files": {"hotspots:a.py": {"score": 9.0, "ccn": 90}}}
    assert hot.LENS.diff(prev, None) == {"new": [], "worsened": [], "resolved": []}


def test_red_line_only_when_ccn_new_or_grown():
    lens = hot.HotspotsLens()
    lens._prev_digest = {"files": {
        "hotspots:known.py": {"score": 10.0, "ccn": 100},
        "hotspots:grown.py": {"score": 8.0, "ccn": 90},
        "hotspots:unmeas.py": {"unmeasured": True},
    }}
    cands = [
        {"id": "hotspots:known.py", "maxFunctionCCN": 100, "path": "known.py"},
        {"id": "hotspots:grown.py", "maxFunctionCCN": 105, "path": "grown.py"},
        {"id": "hotspots:fresh.py", "maxFunctionCCN": 120, "path": "fresh.py"},
        {"id": "hotspots:low.py", "maxFunctionCCN": 50, "path": "low.py"},
        {"id": "hotspots:unmeas.py", "maxFunctionCCN": 130, "path": "unmeas.py"},
    ]
    rl = lens.red_lines(cands)
    ids = {r["id"] for r in rl}
    assert "hotspots:grown.py" in ids
    assert "hotspots:fresh.py" in ids
    assert "hotspots:known.py" not in ids   # unchanged at threshold
    assert "hotspots:low.py" not in ids      # below threshold
    assert "hotspots:unmeas.py" not in ids   # known-but-unmeasured, first real measure
    for r in rl:
        assert r["kind"] == "new-high-complexity"


def test_red_line_kind_sourced_from_authoritative_tuple():
    """I3: the emitted kind is the RED_LINE_KINDS member, not a divergent bare literal."""
    assert hot._RED_LINE_KIND == "new-high-complexity"
    assert hot._RED_LINE_KIND in gl.RED_LINE_KINDS


def test_calibrated_complexity_threshold_drives_red_lines_end_to_end(tmp_path):
    """Owner-calibrated complexity via config changes red_lines; default must not fire."""
    _write(tmp_path, "mid.py", 40)
    run = _basic_tools(tmp_path, numstat="40\t0\tmid.py\n", lsfiles=["mid.py"],
                       radon={"mid.py": [{"complexity": 60, "name": "mid", "lineno": 1}]})
    lens_cal = hot.HotspotsLens()
    out_cal = lens_cal.collect(_ctx(tmp_path, run,
                                    config={"thresholds": {"complexity": 50}}))
    assert out_cal["candidates"]
    assert out_cal["candidates"][0]["maxFunctionCCN"] == 60
    assert out_cal["candidates"][0]["maxFunctionCCN"] < gl.RED_LINE_THRESHOLDS["complexity"]
    assert [r["id"] for r in lens_cal.red_lines(out_cal["candidates"])] == ["hotspots:mid.py"]

    lens_def = hot.HotspotsLens()
    out_def = lens_def.collect(_ctx(tmp_path, _basic_tools(
        tmp_path, numstat="40\t0\tmid.py\n", lsfiles=["mid.py"],
        radon={"mid.py": [{"complexity": 60, "name": "mid", "lineno": 1}]})))
    assert lens_def.red_lines(out_def["candidates"]) == []


# ---------------------------------------------------------------------------
# TOP_N cap + red-line union
# ---------------------------------------------------------------------------

def test_top_n_cap_recorded_and_union():
    window = {"historyTruncated": False, "requestedSince": "a",
              "observedSince": "a", "commitsObserved": 1}
    cands = [hot.build_candidate(path="f%d.py" % i, added=9, deleted=0, current_lines=10,
                                 max_ccn=20, worst={"name": "f", "line": 1}, window=window)
             for i in range(30)]
    outlier = hot.build_candidate(path="outlier.py", added=1, deleted=0, current_lines=1000,
                                  max_ccn=120, worst={"name": "boom", "line": 1},
                                  window=window)
    cands.append(outlier)
    capped, diag = hot.apply_cap(cands, top_n=hot.TOP_N, always_include_ccn=100)
    assert "outlier.py" in [c["path"] for c in capped]
    assert diag["candidatesBeforeCap"] == 31
    assert diag["capApplied"] == hot.TOP_N
    assert diag["redLineUnionAdded"] == 1
    assert len(capped) == hot.TOP_N + 1


def test_calibrated_complexity_governs_union_past_top_n(tmp_path, monkeypatch):
    """Calibrated complexity feeds apply_cap's red-line union through collect()."""
    monkeypatch.setattr(hot, "TOP_N", 3)
    radon = {}
    numstat_lines = []
    lsfiles = []
    for i in range(hot.TOP_N + 1):
        name = "hot%02d.py" % i
        _write(tmp_path, name, 10)
        numstat_lines.append("9\t0\t%s" % name)
        radon[name] = [{"complexity": 20, "name": "f", "lineno": 1}]
        lsfiles.append(name)
    _write(tmp_path, "mid.py", 1000)
    numstat_lines.append("1\t0\tmid.py")
    radon["mid.py"] = [{"complexity": 60, "name": "m", "lineno": 1}]
    lsfiles.append("mid.py")
    numstat = "\n".join(numstat_lines) + "\n"

    def make_run():
        return _basic_tools(tmp_path, numstat=numstat, lsfiles=lsfiles, radon=radon)

    lens_def = hot.HotspotsLens()
    out_def = lens_def.collect(_ctx(tmp_path, make_run()))
    assert "mid.py" not in [c["path"] for c in out_def["candidates"]]
    assert out_def["diagnostics"]["redLineUnionAdded"] == 0
    assert lens_def.red_lines(out_def["candidates"]) == []

    lens_cal = hot.HotspotsLens()
    out_cal = lens_cal.collect(_ctx(tmp_path, make_run(),
                                    config={"thresholds": {"complexity": 50}}))
    assert "mid.py" in [c["path"] for c in out_cal["candidates"]]
    assert out_cal["diagnostics"]["redLineUnionAdded"] >= 1
    assert any(r["id"] == "hotspots:mid.py"
               for r in lens_cal.red_lines(out_cal["candidates"]))


# ---------------------------------------------------------------------------
# I9: cap filtering + suppression diagnostics
# ---------------------------------------------------------------------------

def test_cap_suppression_reported_in_diagnostics_not_diff(tmp_path, monkeypatch):
    """A new hotspot outside the presentation cap is counted in driftSuppressedByCap and
    filtered out of diff()['new'] — asserted via the reported diagnostic."""
    monkeypatch.setattr(hot, "TOP_N", 1)
    _write(tmp_path, "a.py", 20)   # high score → fills cap
    _write(tmp_path, "c.py", 20)   # new, lower score → outside cap
    run = _basic_tools(
        tmp_path, numstat="20\t0\ta.py\n5\t0\tc.py\n", lsfiles=["a.py", "c.py"],
        radon={"a.py": [{"complexity": 20, "name": "f", "lineno": 1}],
               "c.py": [{"complexity": 12, "name": "g", "lineno": 1}]})
    prev = {"schemaVersion": 1,
            "files": {"hotspots:a.py": {"score": 20.0, "ccn": 20}},
            "surfaceIds": ["hotspots:a.py"]}
    lens = hot.HotspotsLens()
    out = lens.collect(_ctx(tmp_path, run, prev_digest=prev))
    assert out["diagnostics"]["driftSuppressedByCap"] == 1
    assert out["digest"]["surfaceIds"] == ["hotspots:a.py"]
    d = lens.diff(prev, out["digest"])
    assert "hotspots:c.py" not in d["new"]   # suppressed by the cap
    assert "driftSuppressedByCap" not in d


def test_digest_persists_full_measured_set_not_just_cap(tmp_path, monkeypatch):
    """Digest must hold every measured file — not only the capped presentation set.

    Then the second sweep moves an unchanged outside-cap file across the top-N boundary;
    it must not appear as `new`.
    """
    monkeypatch.setattr(hot, "TOP_N", 25)
    n = hot.TOP_N + 5
    radon = {}
    numstat_lines = []
    lsfiles = []
    measured_ids = []
    for i in range(n):
        name = "f%02d.py" % i
        _write(tmp_path, name, 10)
        numstat_lines.append("10\t0\t%s" % name)
        radon[name] = [{"complexity": 10 + i, "name": "f", "lineno": 1}]
        lsfiles.append(name)
        measured_ids.append("hotspots:%s" % name)
    numstat = "\n".join(numstat_lines) + "\n"
    run = _basic_tools(tmp_path, numstat=numstat, lsfiles=lsfiles, radon=radon)
    out1 = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    presented = out1["candidates"]
    digest_files = out1["digest"]["files"]
    presented_ids = {c["id"] for c in presented}
    assert out1["diagnostics"]["candidatesBeforeCap"] == n
    assert len(presented) == hot.TOP_N
    assert len(digest_files) == n > len(presented)
    for fid in measured_ids:
        assert fid in digest_files
    outside_cap = [fid for fid in measured_ids if fid not in presented_ids]
    assert outside_cap
    for fid in outside_cap:
        assert fid not in out1["digest"]["surfaceIds"]

    boundary = "hotspots:f04.py"
    assert boundary in outside_cap
    boundary_prev = dict(digest_files[boundary])

    # Reshuffle: drop CCN of former top so f04 enters without changing its own metric.
    radon2 = {}
    for i in range(n):
        name = "f%02d.py" % i
        ccn = 14 if i == 4 else max(10, (10 + i) // 2)
        radon2[name] = [{"complexity": ccn, "name": "f", "lineno": 1}]
    run2 = _basic_tools(tmp_path, numstat=numstat, lsfiles=lsfiles, radon=radon2)
    out2 = hot.HotspotsLens().collect(_ctx(tmp_path, run2, prev_digest=out1["digest"]))
    assert boundary in {c["id"] for c in out2["candidates"]}
    assert out2["digest"]["files"][boundary]["ccn"] == boundary_prev["ccn"]
    assert out2["digest"]["files"][boundary]["score"] == boundary_prev["score"]
    d = hot.LENS.diff(out1["digest"], out2["digest"])
    assert boundary not in d["new"], d


# ---------------------------------------------------------------------------
# I10: unmeasured hotspot recovery (radon per-file error carry / unmeasured)
# ---------------------------------------------------------------------------

def test_radon_error_carries_prior_digest_entry(tmp_path):
    """A radon per-file error must not erase a prior hotspot from the digest."""
    _write(tmp_path, "hot.py", 20)
    _write(tmp_path, "ok.py", 20)
    prev = {"files": {"hotspots:hot.py": {"score": 3.5, "ccn": 15}}}
    run = _basic_tools(
        tmp_path, numstat="20\t0\thot.py\n20\t0\tok.py\n",
        lsfiles=["hot.py", "ok.py"],
        radon={"hot.py": [{"error": "invalid syntax"}],
               "ok.py": [{"complexity": 12, "name": "ok", "lineno": 1}]})
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run, prev_digest=prev))
    assert gl.classify_collect(out)[0] == "collected"
    assert out["digest"]["files"]["hotspots:hot.py"] == {"score": 3.5, "ccn": 15}
    assert any(e.get("path") == "hot.py" for e in out["diagnostics"]["collectorErrors"])
    assert "hotspots:hot.py" not in {c["id"] for c in out["candidates"]}


def test_radon_error_without_prior_is_unmeasured_and_recovers(tmp_path):
    """A per-file radon error with no prior digest entry is recorded unmeasured; a later
    successful measure of that file must not read as `new` drift."""
    _write(tmp_path, "hot.py", 20)
    _write(tmp_path, "ok.py", 20)
    run1 = _basic_tools(
        tmp_path, numstat="20\t0\thot.py\n20\t0\tok.py\n", lsfiles=["hot.py", "ok.py"],
        radon={"hot.py": [{"error": "invalid syntax"}],
               "ok.py": [{"complexity": 12, "name": "ok", "lineno": 1}]})
    out1 = hot.HotspotsLens().collect(_ctx(tmp_path, run1))
    rec = out1["digest"]["files"]["hotspots:hot.py"]
    assert rec.get("unmeasured") is True and rec.get("error") is True

    # Recovery sweep: radon now measures hot.py → not `new` (was known-but-unmeasured).
    run2 = _basic_tools(
        tmp_path, numstat="20\t0\thot.py\n20\t0\tok.py\n", lsfiles=["hot.py", "ok.py"],
        radon={"hot.py": [{"complexity": 40, "name": "hot", "lineno": 1}],
               "ok.py": [{"complexity": 12, "name": "ok", "lineno": 1}]})
    lens2 = hot.HotspotsLens()
    out2 = lens2.collect(_ctx(tmp_path, run2, prev_digest=out1["digest"]))
    d = lens2.diff(out1["digest"], out2["digest"])
    assert "hotspots:hot.py" not in d["new"]
    # A known-but-unmeasured file's first real measure is not a red line either.
    assert not any(r["id"] == "hotspots:hot.py" for r in lens2.red_lines(out2["candidates"]))


# ---------------------------------------------------------------------------
# I11: radon error-threshold branch boundary
# ---------------------------------------------------------------------------

def test_radon_error_threshold_boundary(tmp_path, monkeypatch):
    """At the per-file error threshold the (only needed) language fails → not-collected;
    just below it, collection succeeds with the errors recorded."""
    monkeypatch.setattr(hot, "PER_FILE_ERROR_DEGRADE_THRESHOLD", 3)
    for i in range(4):
        _write(tmp_path, "f%d.py" % i, 20)
    lsfiles = ["f%d.py" % i for i in range(4)]
    numstat = "".join("20\t0\tf%d.py\n" % i for i in range(4))

    # Exactly 3 errors (>= threshold) with the 4th good → python fails → not-collected.
    radon_at = {"f0.py": [{"error": "e"}], "f1.py": [{"error": "e"}],
                "f2.py": [{"error": "e"}],
                "f3.py": [{"complexity": 12, "name": "f", "lineno": 1}]}
    out_at = hot.HotspotsLens().collect(_ctx(
        tmp_path, _basic_tools(tmp_path, numstat=numstat, lsfiles=lsfiles, radon=radon_at)))
    status, reason = gl.classify_collect(out_at)
    assert status == "not-collected"
    assert "exceeded threshold (3 >= 3)" in reason

    # 2 errors (< threshold, not all files) → collected with the errors recorded.
    radon_below = {"f0.py": [{"error": "e"}], "f1.py": [{"error": "e"}],
                   "f2.py": [{"complexity": 12, "name": "f", "lineno": 1}],
                   "f3.py": [{"complexity": 14, "name": "g", "lineno": 1}]}
    out_below = hot.HotspotsLens().collect(_ctx(
        tmp_path, _basic_tools(tmp_path, numstat=numstat, lsfiles=lsfiles,
                               radon=radon_below)))
    assert gl.classify_collect(out_below)[0] == "collected"
    assert len(out_below["diagnostics"]["collectorErrors"]) == 2


def test_radon_all_files_error_degrades(tmp_path):
    """When every tracked file of the only needed language errors, the lens degrades."""
    _write(tmp_path, "hot.py", 20)
    run = _basic_tools(tmp_path, numstat="20\t0\thot.py\n", lsfiles=["hot.py"],
                       radon={"hot.py": [{"error": "invalid syntax"}]})
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "all" in reason.lower() or "per-file" in reason


# ---------------------------------------------------------------------------
# prevDigest camelCase regression
# ---------------------------------------------------------------------------

def test_collect_reads_prev_digest_camelcase(tmp_path):
    """collect() must read the baseline from camelCase ctx['prevDigest'] — a snake_case
    read (the pre-rebase bug) would lose the baseline and refire a known red line."""
    _write(tmp_path, "hot.py", 20)
    run = _basic_tools(tmp_path, numstat="20\t0\thot.py\n", lsfiles=["hot.py"],
                       radon={"hot.py": [{"complexity": 120, "name": "hot", "lineno": 1}]})
    prev_camel = {"schemaVersion": 1,
                  "files": {"hotspots:hot.py": {"score": 999.0, "ccn": 120}}}
    ctx = {
        "cwd": str(tmp_path),
        "run": run,
        "prevDigest": prev_camel,
        # snake_case decoy: if collect wrongly read this, the CCN-120 file would look
        # fresh and the red line would refire.
        "prev_digest": {"schemaVersion": 1,
                        "files": {"hotspots:hot.py": {"score": 1.0, "ccn": 1}}},
    }
    lens = hot.HotspotsLens()
    out = lens.collect(ctx)
    assert lens._prev_digest is prev_camel
    # Known-at-120 file did not grow → no red line. The snake decoy (ccn 1) would refire.
    assert lens.red_lines(out["candidates"]) == []


# ---------------------------------------------------------------------------
# M3: hotspotsWindow config branch removed (dead) — window stays the default
# ---------------------------------------------------------------------------

def test_hotspots_window_config_branch_removed(tmp_path):
    """read_config never populates hotspotsWindow; a config carrying it must NOT change
    the window — it stays the 90-day default."""
    _write(tmp_path, "hot.py", 20)
    run = _basic_tools(tmp_path, numstat="20\t0\thot.py\n", lsfiles=["hot.py"],
                       radon={"hot.py": [{"complexity": 15, "name": "hot", "lineno": 1}]})
    out = hot.HotspotsLens().collect(_ctx(tmp_path, run,
                                          config={"hotspotsWindow": "7 days"}))
    assert out["digest"]["window"]["sinceSpec"] == hot.DEFAULT_WINDOW
    # The --since flag passed to git carried the default, not the config value.
    since_flags = [a for call in run.calls for a in call if a.startswith("--since=")]
    assert since_flags
    assert all(f == "--since=90 days" for f in since_flags)


# ---------------------------------------------------------------------------
# cwd forms agree
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cwd_form", [".", "./", "ABS", "ABS/"])
def test_collect_cwd_forms_agree(tmp_path, cwd_form):
    _write(tmp_path, "hot.py", 20)
    abs_repo = os.path.realpath(str(tmp_path))

    def make_run():
        return _basic_tools(tmp_path, numstat="20\t0\thot.py\n", lsfiles=["hot.py"],
                            radon={"hot.py": [{"complexity": 15, "name": "hot",
                                               "lineno": 1}]})

    baseline = hot.HotspotsLens().collect({"cwd": abs_repo, "run": make_run()})
    base_ids = [c["id"] for c in baseline["candidates"]]
    assert base_ids == ["hotspots:hot.py"], baseline

    if cwd_form in (".", "./"):
        cwd_arg, chdir = cwd_form, True
    elif cwd_form == "ABS":
        cwd_arg, chdir = abs_repo, False
    else:
        cwd_arg, chdir = abs_repo + os.sep, False

    old = os.getcwd()
    try:
        if chdir:
            os.chdir(abs_repo)
        out = hot.HotspotsLens().collect({"cwd": cwd_arg, "run": make_run()})
    finally:
        os.chdir(old)
    assert [c["id"] for c in out["candidates"]] == base_ids
    assert out["diagnostics"].get("joinAnomaly") is None


# ---------------------------------------------------------------------------
# vocabulary + protocol shape
# ---------------------------------------------------------------------------

def test_consequence_template_measured_evidence_only():
    low = hot.CONSEQUENCE_TEMPLATE.lower() + " " + hot.VALIDATION_GUIDANCE.lower()
    assert "churn" in low
    assert "complexity" in low or "ccn" in low
    assert "truncat" in low or "observed window" in low
    assert "never" in hot.CONSEQUENCE_TEMPLATE.lower()
    assert "rule-catalog" in low or "severity tier" in low
    for w in ("sonar", "blocker", "critical vulnerability"):
        assert w not in low


def test_lens_protocol_shape():
    ok, reasons = gl.validate_lens(hot.LENS)
    assert ok, reasons
    assert hot.LENS.name == "hotspots"
    assert hot.LENS.collector_version == "2.0.0"
    assert hot.LENS.collector_version != "1.0.0"
    assert hot.LENS.required_facts == ()


def test_collector_version_bumped_with_digest_shape_change():
    assert hot.HotspotsLens.collector_version != "1.0.0"
    with open(hot.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert '"surfaceIds"' in src or "'surfaceIds'" in src
    assert 'collector_version = "2.0.0"' in src


def test_degrade_helper_shape():
    assert hot.LENS.degrade("missing tool") == {
        "lens": "hotspots", "degraded": True, "reason": "missing tool"}


def test_no_subprocess_import_in_module():
    """The lens module must not import subprocess (routes every spawn via run_tool)."""
    with open(hot.__file__, encoding="utf-8") as fh:
        src = fh.read()
    assert "import subprocess" not in src
    assert "guardian_collect" in src
