"""Unit tests for the hotspots lens — never invoke radon/lizard/git-network."""
import csv
import json
import os
import subprocess
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import guardian_lens as gl
import guardian_lens_hotspots as hot
import guardian_tools as gt
from guardian_fixtures import git_commit, git_init_repo

FIXTURES = Path(__file__).parent / "fixtures" / "guardian"
RADON_FIXTURE = FIXTURES / "radon-cc.json"
LIZARD_FIXTURE = FIXTURES / "lizard.csv"


def _proc(stdout="", stderr="", returncode=0):
    return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)


def _git_init(repo):
    git_init_repo(repo)


def _commit(repo, relpath, content, msg="c"):
    path = Path(repo) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    subprocess.run(["git", "add", relpath], cwd=repo, check=True)
    git_commit(repo, msg)


# ---------------------------------------------------------------------------
# Fixture parsers
# ---------------------------------------------------------------------------

def test_parse_radon_json_fixture_and_error_entry():
    data = json.loads(RADON_FIXTURE.read_text())
    by_path, error_paths = hot.parse_radon_json(json.dumps(data))
    assert "plugins/superheroes/lib/guardian_report.py" in by_path
    gr = by_path["plugins/superheroes/lib/guardian_report.py"]
    assert gr["maxFunctionCCN"] == 46
    assert gr["worstFunction"]["name"] == "render"
    assert gr["worstFunction"]["line"] == 34

    core = by_path["plugins/superheroes/lib/core_md.py"]
    assert core["maxFunctionCCN"] == 45
    assert core["worstFunction"]["name"] == "migrate_on_read"

    # error entry → unmeasurable (absent from result) + listed in error_paths
    assert "plugins/superheroes/lib/broken_fake.py" not in by_path
    assert "plugins/superheroes/lib/broken_fake.py" in error_paths

    # class nesting: high-CCN method inside a class must be found; class aggregate is not
    # reported as worstFunction
    classy = by_path["plugins/superheroes/lib/classy_hot.py"]
    assert classy["maxFunctionCCN"] == 120
    assert classy["worstFunction"]["name"] == "explosive"
    assert classy["worstFunction"]["line"] == 10

    # inline error dict as sole content for a path
    err_only, err_paths = hot.parse_radon_json(json.dumps({
        "bad.py": [{"error": "invalid syntax"}],
        "ok.py": [{"complexity": 12, "name": "f", "lineno": 1}],
    }))
    assert "bad.py" not in err_only
    assert "bad.py" in err_paths
    assert err_only["ok.py"]["maxFunctionCCN"] == 12


def test_parse_radon_rejects_non_dict_shape():
    with pytest.raises(gl.LensDegraded) as exc:
        hot.parse_radon_json("[]")
    assert "contract mismatch" in exc.value.reason

    with pytest.raises(gl.LensDegraded):
        hot.parse_radon_json(json.dumps({"a.py": {"not": "a list"}}))


def test_parse_radon_flattens_nested_closures():
    nested, errs = hot.parse_radon_json(json.dumps({
        "nest.py": [{
            "type": "function",
            "complexity": 5,
            "name": "outer",
            "lineno": 1,
            "closures": [{
                "type": "function",
                "complexity": 88,
                "name": "inner",
                "lineno": 3,
                "closures": [],
            }],
        }],
    }))
    assert errs == []
    assert nested["nest.py"]["maxFunctionCCN"] == 88
    assert nested["nest.py"]["worstFunction"]["name"] == "inner"


def test_parse_lizard_csv_fixture_no_header_and_quoted_commas():
    text = LIZARD_FIXTURE.read_text()
    by_path = hot.parse_lizard_csv(text)
    panel = by_path["plugins/superheroes/lib/review_panel_shell.js"]
    assert panel["maxFunctionCCN"] == 82
    assert panel["worstFunction"]["name"] == "reviewPanel"

    # quoted commas in signature column — fixture tail row
    rows = list(csv.reader(text.splitlines()))
    quoted = [r for r in rows if len(r) >= 8 and r[7] == "foo"]
    assert quoted, "fixture must include the quoted-commas row"
    assert "a.js" in by_path
    assert by_path["a.js"]["maxFunctionCCN"] == 5

    # column order verified against fixture: col0=nloc, col1=CCN (not CCN at 0)
    first = rows[0]
    assert first[0] == "11" and first[1] == "8"


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
        assert "=>" not in p
        assert "{" not in p
    assert parsed["src/a.py"] == {"added": 10, "deleted": 2}


def test_relative_churn_skips_zero_line_files():
    assert hot.relative_churn(added=10, deleted=5, current_lines=0) is None
    assert hot.relative_churn(added=10, deleted=5, current_lines=100) == 0.15


# ---------------------------------------------------------------------------
# Size normalization (binding requirement a)
# ---------------------------------------------------------------------------

def test_size_normalization_ranks_relative_not_raw():
    """Big file, huge raw churn, low relative → below small file, high relative."""
    # big: 10000 lines, raw churn 500 → relative 0.05; CCN 20 → score 1.0
    # small: 50 lines, raw churn 40 → relative 0.8; CCN 20 → score 16.0
    big = hot.build_candidate(
        path="big.py",
        added=400, deleted=100, current_lines=10000,
        max_ccn=20, worst={"name": "big_fn", "line": 1},
        window={"historyTruncated": False, "requestedSince": "x",
                "observedSince": "x", "commitsObserved": 1},
    )
    small = hot.build_candidate(
        path="small.py",
        added=30, deleted=10, current_lines=50,
        max_ccn=20, worst={"name": "small_fn", "line": 1},
        window={"historyTruncated": False, "requestedSince": "x",
                "observedSince": "x", "commitsObserved": 1},
    )
    assert big["rawChurn"] > small["rawChurn"]
    assert big["relativeChurn"] < small["relativeChurn"]
    assert small["hotspotScore"] > big["hotspotScore"]
    ranked = hot.rank_and_cap([big, small], top_n=25)
    assert ranked[0]["path"] == "small.py"
    assert ranked[0]["metric"] == ranked[0]["hotspotScore"]
    # raw churn is provenance only — not the ranking key
    assert ranked[0]["rawChurn"] < ranked[1]["rawChurn"]


# ---------------------------------------------------------------------------
# Tracked ∩ exists intersection
# ---------------------------------------------------------------------------

def test_deleted_and_untracked_excluded_via_intersection(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "keep.py", "x\n" * 20, "add keep")
    _commit(repo, "gone.py", "y\n" * 20, "add gone")
    (repo / "gone.py").unlink()
    (repo / "untracked.py").write_text("z\n" * 20)
    # still in index history but deleted from disk; untracked never in ls-files

    tracked = hot.tracked_existing_files(str(repo), run=subprocess.run)
    assert "keep.py" in tracked
    assert "gone.py" not in tracked
    assert "untracked.py" not in tracked


# ---------------------------------------------------------------------------
# Shallow guard (binding requirement b)
# ---------------------------------------------------------------------------

def test_shallow_guard_reports_window_and_never_fetches(tmp_path, monkeypatch):
    repo = tmp_path / "shallow"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "a.py", "print(1)\n", "one")

    recorded = []
    real_run = subprocess.run

    def selective_run(argv, **kwargs):
        recorded.append(list(argv))
        joined = " ".join(str(a) for a in argv)
        assert "fetch" not in joined
        assert "--unshallow" not in joined
        if "rev-parse" in argv and "--is-shallow-repository" in argv:
            return _proc(stdout="true\n")
        return real_run(argv, **kwargs)

    earliest = real_run(
        ["git", "log", "--format=%cI", "--reverse"],
        cwd=str(repo), capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()[0][:10]

    window = hot.observe_window(str(repo), since="90 days", run=selective_run)
    assert window["historyTruncated"] is True
    assert window["observedSince"] == earliest
    assert window["commitsObserved"] == 1
    flat = " ".join(" ".join(map(str, a)) for a in recorded)
    assert "fetch" not in flat
    assert "--unshallow" not in flat


# ---------------------------------------------------------------------------
# Coverage rules
# ---------------------------------------------------------------------------

def test_both_tools_missing_raises_lens_degraded(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "a.py", "def f():\n  return 1\n", "c")

    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": False, "path": None, "source": None,
    })
    with pytest.raises(gl.LensDegraded) as exc:
        hot.LENS.collect({"cwd": str(repo), "run": subprocess.run})
    reason = exc.value.reason
    assert "pip install radon" in reason
    assert "pip install lizard" in reason


def test_one_tool_missing_partial_coverage(tmp_path, monkeypatch):
    """Radon present, lizard absent, only Python files — lizard is not required."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "def f():\n" + ("  x = 1\n" * 30)
    _commit(repo, "hot.py", body, "c1")
    _commit(repo, "hot.py", body + "  y = 2\n", "c2")

    def resolve(tool, cwd, run=None):
        if tool == "radon":
            return {"tool": tool, "found": True, "path": "/fake/radon", "source": "path"}
        return {"tool": tool, "found": False, "path": None, "source": None}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "9.9.9")

    radon_out = json.dumps({
        "hot.py": [{"complexity": 15, "name": "f", "lineno": 1, "endline": 30, "rank": "C"}],
    })

    def fake_run(argv, **kwargs):
        if argv and (str(argv[0]).endswith("radon") or argv[0] == "/fake/radon"):
            # Simulate absolute-path keys radon returns when given abs inputs
            cwd = kwargs.get("cwd")
            repo_s = str(repo)
            payload = radon_out
            if cwd and os.path.realpath(cwd) != os.path.realpath(repo_s):
                abs_hot = os.path.join(repo_s, "hot.py")
                payload = json.dumps({
                    abs_hot: [{"complexity": 15, "name": "f", "lineno": 1}],
                })
            return _proc(stdout=payload)
        return subprocess.run(argv, **kwargs)

    out = hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    diag = out["diagnostics"]
    cov = diag["complexityCoverage"]
    assert cov["python"] == "collected"
    assert cov["javascript"] == "missing-tool"
    assert "lizard" in str(diag.get("coverageGaps") or diag)
    assert [c["path"] for c in out["candidates"]] == ["hot.py"]
    assert out["digest"]["toolVersions"]["radon"] == "9.9.9"
    assert out["digest"]["toolVersions"]["lizard"] is None


def test_lizard_only_partial_coverage(tmp_path, monkeypatch):
    """Lizard present, radon absent, only JS files — radon is not required."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "function hot() {\n" + ("  var x = 1;\n" * 30) + "}\n"
    _commit(repo, "hot.js", body, "c1")
    _commit(repo, "hot.js", body + "var y = 2;\n", "c2")

    def resolve(tool, cwd, run=None):
        if tool == "lizard":
            return {"tool": tool, "found": True, "path": "/fake/lizard", "source": "path"}
        return {"tool": tool, "found": False, "path": None, "source": None}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.17.0")

    # lizard csv: nloc,CCN,...,file,name,...,start,end
    lizard_csv = "30,15,10,0,30,hot@1-30@hot.js,hot.js,hot,function hot(),1,30\n"

    def fake_run(argv, **kwargs):
        if argv and (str(argv[0]).endswith("lizard") or argv[0] == "/fake/lizard"):
            cwd = kwargs.get("cwd")
            repo_s = str(repo)
            text = lizard_csv
            if cwd and os.path.realpath(cwd) != os.path.realpath(repo_s):
                abs_hot = os.path.join(repo_s, "hot.js")
                text = "30,15,10,0,30,hot@1-30@%s,%s,hot,function hot(),1,30\n" % (
                    abs_hot, abs_hot)
            return _proc(stdout=text)
        return subprocess.run(argv, **kwargs)

    out = hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    cov = out["diagnostics"]["complexityCoverage"]
    assert cov["javascript"] == "collected"
    assert cov["python"] == "missing-tool"
    assert [c["path"] for c in out["candidates"]] == ["hot.js"]


def test_required_collector_nonzero_degrades(tmp_path, monkeypatch):
    """Python files present + radon non-zero → LensDegraded (baseline preserved)."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "a.py", "def f():\n  return 1\n", "c")

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            return _proc(stdout="", returncode=2)
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    with pytest.raises(gl.LensDegraded) as exc:
        hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    assert "radon exited non-zero" in exc.value.reason


def test_no_matching_files_is_not_collected(tmp_path, monkeypatch):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "README.md", "hi\n", "c")

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0.0")

    called_collectors = []

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]) or "lizard" in str(argv[0]):
            called_collectors.append(argv[0])
            if "radon" in str(argv[0]):
                return _proc(stdout="{}")
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out = hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    cov = out["diagnostics"]["complexityCoverage"]
    assert cov["python"] == "not-collected"
    assert cov["javascript"] == "not-collected"
    assert called_collectors == []


def test_radon_repo_config_cannot_write_inside_repo(tmp_path, monkeypatch):
    """Repo-local radon.cfg must not redirect writes into the scanned tree."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "def f():\n" + ("  x = 1\n" * 30)
    _commit(repo, "hot.py", body, "c1")
    _commit(repo, "hot.py", body + "  y = 2\n", "c2")
    (repo / "radon.cfg").write_text("[cc]\noutput_file = POISON.txt\n")

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    radon_calls = []

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            radon_calls.append((list(argv), dict(kwargs)))
            cwd = kwargs.get("cwd")
            # If the collector were run with the repo as cwd, a config-driven
            # output_file would land here — simulate that poison write.
            if cwd and os.path.realpath(cwd) == os.path.realpath(str(repo)):
                (repo / "POISON.txt").write_text("owned\n")
            abs_hot = os.path.join(str(repo), "hot.py")
            return _proc(stdout=json.dumps({
                abs_hot: [{"complexity": 15, "name": "f", "lineno": 1}],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out = hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    assert not (repo / "POISON.txt").exists()
    assert radon_calls, "radon must have been invoked"
    for argv, kwargs in radon_calls:
        assert os.path.realpath(kwargs["cwd"]) != os.path.realpath(str(repo))
        # absolute input paths after the radon cc -s -j flags
        path_args = [a for a in argv[4:] if isinstance(a, str)]
        assert path_args and all(os.path.isabs(p) for p in path_args)
    assert any(c["path"] == "hot.py" for c in out["candidates"])


# ---------------------------------------------------------------------------
# TOP_N cap recorded
# ---------------------------------------------------------------------------

def test_top_n_cap_recorded_in_diagnostics():
    window = {"historyTruncated": False, "requestedSince": "a",
              "observedSince": "a", "commitsObserved": 1}
    cands = [
        hot.build_candidate(
            path="f%d.py" % i, added=10, deleted=0, current_lines=10,
            max_ccn=10 + i, worst={"name": "f", "line": 1}, window=window,
        )
        for i in range(30)
    ]
    capped, diag = hot.apply_cap(cands, top_n=hot.TOP_N)
    assert diag["candidatesBeforeCap"] == 30
    assert diag["capApplied"] == hot.TOP_N
    assert len(capped) == hot.TOP_N
    assert diag["candidatesBeforeCap"] > diag["capApplied"]
    assert diag["redLineUnionAdded"] == 0


def test_top_n_unions_absolute_complexity_outlier():
    """A low-churn CCN>=100 file outside top-N must still be returned for red lines."""
    window = {"historyTruncated": False, "requestedSince": "a",
              "observedSince": "a", "commitsObserved": 1}
    cands = []
    for i in range(30):
        # High relative churn via tiny files — fills top-N
        cands.append(hot.build_candidate(
            path="hot%d.py" % i, added=9, deleted=0, current_lines=10,
            max_ccn=20, worst={"name": "f", "line": 1}, window=window,
        ))
    # Low relative churn, absolute CCN red-line outlier
    outlier = hot.build_candidate(
        path="outlier.py", added=1, deleted=0, current_lines=1000,
        max_ccn=120, worst={"name": "boom", "line": 1}, window=window,
    )
    cands.append(outlier)
    capped, diag = hot.apply_cap(
        cands, top_n=hot.TOP_N, always_include_ccn=100,
    )
    paths = [c["path"] for c in capped]
    assert "outlier.py" in paths
    assert diag["candidatesBeforeCap"] == 31
    assert diag["capApplied"] == hot.TOP_N
    assert diag["redLineUnionAdded"] == 1
    assert len(capped) == hot.TOP_N + 1


# ---------------------------------------------------------------------------
# diff + red lines
# ---------------------------------------------------------------------------

def test_diff_new_worsened_resolved_and_prev_none():
    cur = {
        "schemaVersion": 1,
        "files": {
            "hotspots:a.py": {"score": 2.0, "ccn": 12},
            "hotspots:b.py": {"score": 5.0, "ccn": 20},
        },
    }
    prev = {
        "schemaVersion": 1,
        "files": {
            "hotspots:b.py": {"score": 3.0, "ccn": 18},
            "hotspots:c.py": {"score": 1.0, "ccn": 10},
        },
    }
    d = hot.LENS.diff(prev, cur)
    assert set(d["new"]) == {"hotspots:a.py"}
    assert set(d["worsened"]) == {"hotspots:b.py"}
    assert set(d["resolved"]) == {"hotspots:c.py"}

    d0 = hot.LENS.diff(None, cur)
    assert set(d0["new"]) == {"hotspots:a.py", "hotspots:b.py"}
    assert d0["worsened"] == []
    assert d0["resolved"] == []

    # malformed prev
    d1 = hot.LENS.diff({"no": "files"}, cur)
    assert set(d1["new"]) == {"hotspots:a.py", "hotspots:b.py"}


def test_red_line_only_when_ccn_new_or_grown():
    lens = hot.HotspotsLens()
    # Ordering dependency: collect caches prev; we set it directly for the unit test.
    lens._prev_digest = {
        "files": {
            "hotspots:known.py": {"score": 10.0, "ccn": 100},
            "hotspots:grown.py": {"score": 8.0, "ccn": 90},
        },
    }
    cands = [
        {"id": "hotspots:known.py", "maxFunctionCCN": 100, "path": "known.py"},
        {"id": "hotspots:grown.py", "maxFunctionCCN": 105, "path": "grown.py"},
        {"id": "hotspots:fresh.py", "maxFunctionCCN": 120, "path": "fresh.py"},
        {"id": "hotspots:low.py", "maxFunctionCCN": 50, "path": "low.py"},
    ]
    rl = lens.red_lines(cands)
    ids = {r["id"] for r in rl}
    assert "hotspots:grown.py" in ids
    assert "hotspots:fresh.py" in ids
    assert "hotspots:known.py" not in ids  # unchanged at threshold — not new/grown
    assert "hotspots:low.py" not in ids
    for r in rl:
        assert r["kind"] == "new-high-complexity"


def test_calibrated_complexity_threshold_drives_red_lines_end_to_end(tmp_path, monkeypatch):
    """Owner-calibrated complexity via config must change red_lines; default must not fire.

    Candidate CCN sits below the default (100) but at/above a lowered calibrated
    threshold. Drive collect() then red_lines() — do not assert private fields.
    """
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "def mid():\n" + ("  x = 1\n" * 40)
    _commit(repo, "mid.py", body, "c1")
    _commit(repo, "mid.py", body + "  y = 2\n", "c2")

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")
    abs_repo = os.path.realpath(str(repo))

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            abs_mid = os.path.join(abs_repo, "mid.py")
            return _proc(stdout=json.dumps({
                abs_mid: [{"complexity": 60, "name": "mid", "lineno": 1}],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    lens_cal = hot.HotspotsLens()
    out_cal = lens_cal.collect({
        "cwd": abs_repo,
        "run": fake_run,
        "config": {"thresholds": {"complexity": 50}},
        "prev_digest": None,
    })
    assert out_cal["candidates"]
    assert out_cal["candidates"][0]["maxFunctionCCN"] == 60
    assert out_cal["candidates"][0]["maxFunctionCCN"] < gl.RED_LINE_THRESHOLDS["complexity"]
    rl_cal = lens_cal.red_lines(out_cal["candidates"])
    assert [r["id"] for r in rl_cal] == ["hotspots:mid.py"]

    lens_def = hot.HotspotsLens()
    out_def = lens_def.collect({
        "cwd": abs_repo,
        "run": fake_run,
        "prev_digest": None,
    })
    assert lens_def.red_lines(out_def["candidates"]) == []


def test_collect_caches_prev_digest_from_ctx(tmp_path, monkeypatch):
    """Hotspots takes prev_digest from ctx — lenses do not read the store."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": False, "path": None, "source": None,
    })
    digest = {"files": {"hotspots:x.py": {"score": 1.0, "ccn": 10}}}
    lens = hot.HotspotsLens()
    with pytest.raises(gl.LensDegraded):
        lens.collect({"cwd": str(repo), "prev_digest": digest, "run": subprocess.run})
    assert lens._prev_digest == digest

    lens2 = hot.HotspotsLens()
    with pytest.raises(gl.LensDegraded):
        lens2.collect({"cwd": str(repo), "run": subprocess.run})
    assert lens2._prev_digest is None


# ---------------------------------------------------------------------------
# consequence / validation guidance — measured evidence only
# ---------------------------------------------------------------------------

def test_consequence_template_measured_evidence_only():
    low = hot.CONSEQUENCE_TEMPLATE.lower() + " " + hot.VALIDATION_GUIDANCE.lower()
    assert "churn" in low
    assert "complexity" in low or "ccn" in low
    assert "truncat" in low or "observed window" in low
    # Templates may name "severity tiers" only to forbid them — require the ban.
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


def test_full_collect_ranks_by_relative_churn(tmp_path, monkeypatch):
    """End-to-end collect with fake tools: size-normalization still wins."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    big = "def big():\n" + ("  pass\n" * 200)
    small = "def small():\n" + ("  pass\n" * 20)
    _commit(repo, "big.py", big, "add big")
    _commit(repo, "small.py", small, "add small")
    # churn: big gets +200 lines (still large file), small gets rewritten heavily
    big2 = big + ("  x=1\n" * 50)  # +50 on 200+ → modest relative
    small2 = "def small():\n" + ("  x=1\n" * 40)  # rewrite-ish on small file
    (repo / "big.py").write_text(big2)
    (repo / "small.py").write_text(small2)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    git_commit(repo, "churn")

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            # Return absolute-path keys as real radon does when given abs inputs
            payload = {
                os.path.join(str(repo), "big.py"): [
                    {"complexity": 12, "name": "big", "lineno": 1},
                ],
                os.path.join(str(repo), "small.py"): [
                    {"complexity": 12, "name": "small", "lineno": 1},
                ],
            }
            return _proc(stdout=json.dumps(payload))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out = hot.LENS.collect({"cwd": str(repo), "run": fake_run})
    cands = out["candidates"]
    assert [c["path"] for c in cands] == ["small.py", "big.py"]
    by_path = {c["path"]: c for c in cands}
    assert by_path["small.py"]["rawChurn"] < by_path["big.py"]["rawChurn"]
    assert by_path["small.py"]["relativeChurn"] > by_path["big.py"]["relativeChurn"]
    assert by_path["small.py"]["hotspotScore"] > by_path["big.py"]["hotspotScore"]
    assert "historyTruncated" in cands[0]
    assert "capApplied" in out["diagnostics"]
    assert "candidatesBeforeCap" in out["diagnostics"]
    assert "redLineUnionAdded" in out["diagnostics"]


# ---------------------------------------------------------------------------
# Relative cwd forms must agree (FIX-2 — silent-zero under `--cwd .`)
# ---------------------------------------------------------------------------

def _hotspots_fixture_repo(tmp_path):
    """Repo with known churn + complexity so relative vs absolute cwd can be compared."""
    repo = tmp_path / "cwd_forms"
    repo.mkdir()
    _git_init(repo)
    body = "def hot():\n" + ("  x = 1\n" * 30)
    _commit(repo, "hot.py", body, "c1")
    _commit(repo, "hot.py", body + "  y = 2\n", "c2")
    return repo


def _hotspots_fake_tools(monkeypatch, repo):
    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    repo_s = os.path.realpath(str(repo))

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            abs_hot = os.path.join(repo_s, "hot.py")
            return _proc(stdout=json.dumps({
                abs_hot: [{"complexity": 15, "name": "hot", "lineno": 1}],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    return fake_run


def test_abs_paths_always_returns_absolute(tmp_path):
    repo = str(tmp_path / "r")
    os.makedirs(repo)
    abs_repo = os.path.realpath(repo)
    out = hot._abs_paths(abs_repo, ["a.py", "sub/b.py", os.path.join(abs_repo, "c.py")])
    assert all(os.path.isabs(p) for p in out)
    assert out[0] == os.path.join(abs_repo, "a.py")
    assert out[1] == os.path.join(abs_repo, "sub/b.py")
    assert out[2] == os.path.join(abs_repo, "c.py")

    # Relative cwd must still yield absolute results (defensive against callers).
    old = os.getcwd()
    try:
        os.chdir(abs_repo)
        rel_out = hot._abs_paths(".", ["hot.py"])
        assert all(os.path.isabs(p) for p in rel_out)
        assert os.path.realpath(rel_out[0]) == os.path.join(abs_repo, "hot.py")
    finally:
        os.chdir(old)


@pytest.mark.parametrize("cwd_form", [".", "./", "ABS", "ABS/"])
def test_collect_cwd_forms_agree(tmp_path, monkeypatch, cwd_form):
    """Relative and absolute cwd forms must yield the same candidate set."""
    repo = _hotspots_fixture_repo(tmp_path)
    fake_run = _hotspots_fake_tools(monkeypatch, repo)
    abs_repo = os.path.realpath(str(repo))

    baseline = hot.HotspotsLens().collect({"cwd": abs_repo, "run": fake_run})
    base_ids = [c["id"] for c in baseline["candidates"]]
    assert base_ids == ["hotspots:hot.py"], baseline

    if cwd_form in (".", "./"):
        cwd_arg = cwd_form
        chdir = True
    elif cwd_form == "ABS":
        cwd_arg = abs_repo
        chdir = False
    else:
        cwd_arg = abs_repo + os.sep
        chdir = False

    old = os.getcwd()
    try:
        if chdir:
            os.chdir(abs_repo)
        out = hot.HotspotsLens().collect({"cwd": cwd_arg, "run": fake_run})
    finally:
        os.chdir(old)

    assert [c["id"] for c in out["candidates"]] == base_ids
    assert out["diagnostics"]["candidatesBeforeCap"] == baseline["diagnostics"]["candidatesBeforeCap"]
    assert out["diagnostics"].get("joinAnomaly") is None


def test_join_anomaly_when_complexity_keys_miss_tracked(tmp_path, monkeypatch):
    """Collected complexity that never joins churn∩tracked must degrade, not look clean."""
    repo = _hotspots_fixture_repo(tmp_path)
    fake_run = _hotspots_fake_tools(monkeypatch, repo)
    abs_repo = os.path.realpath(str(repo))

    # Force a path-key mismatch after a successful "collected" run.
    real_normalize = hot._normalize_complexity_paths

    def broken_normalize(cwd, complexity):
        out = real_normalize(cwd, complexity)
        return {"./NOT_A_TRACKED_PATH.py": v for v in out.values()} or {
            "./NOT_A_TRACKED_PATH.py": {
                "maxFunctionCCN": 15,
                "worstFunction": {"name": "x", "line": 1},
            },
        }

    monkeypatch.setattr(hot, "_normalize_complexity_paths", broken_normalize)
    with pytest.raises(gl.LensDegraded) as exc:
        hot.HotspotsLens().collect({"cwd": abs_repo, "run": fake_run})
    assert "join anomaly" in exc.value.reason


def test_digest_persists_full_measured_set_not_just_cap(tmp_path, monkeypatch):
    """Digest must hold every measured file — not only the capped presentation set.

    Drives HotspotsLens.collect() on a fixture with more measured files than TOP_N.
    A regression that persists only capped/presented ids must fail the count and
    membership asserts below. The second sweep then moves an unchanged outside-cap
    file across the top-N boundary; it must not appear as `new`.
    """
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    abs_repo = os.path.realpath(str(repo))

    n_measured = hot.TOP_N + 5  # strictly more measured files than the presentation cap
    radon_payload = {}
    measured_ids = []
    for i in range(n_measured):
        name = "f%02d.py" % i
        body = "def f():\n" + ("  x = 1\n" * 10)
        _commit(repo, name, body, "add %s" % name)
        # Higher CCN → higher score with equal churn; lowest indices fall outside top-N.
        radon_payload[os.path.join(abs_repo, name)] = [
            {"complexity": 10 + i, "name": "f", "lineno": 1},
        ]
        measured_ids.append("hotspots:%s" % name)

    def fake_churn(ctx, since):
        return {("f%02d.py" % i): {"added": 10, "deleted": 0} for i in range(n_measured)}

    monkeypatch.setattr(hot, "_collect_churn", fake_churn)

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            return _proc(stdout=json.dumps(radon_payload))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out1 = hot.HotspotsLens().collect({
        "cwd": abs_repo, "run": fake_run, "prev_digest": None,
    })
    presented = out1["candidates"]
    digest_files = out1["digest"]["files"]
    presented_ids = {c["id"] for c in presented}

    assert out1["diagnostics"]["candidatesBeforeCap"] == n_measured
    assert len(presented) == hot.TOP_N
    # Direct capped-digest regression check: full measured set in digest, larger than presentation.
    assert len(digest_files) == n_measured > len(presented), (
        "digest must persist all %d measured files, not only the capped %d: got %d"
        % (n_measured, len(presented), len(digest_files))
    )
    for fid in measured_ids:
        assert fid in digest_files, "measured file missing from digest: %s" % fid
    outside_cap = [fid for fid in measured_ids if fid not in presented_ids]
    assert outside_cap, "fixture must leave measured files outside the presentation cap"
    for fid in outside_cap:
        assert fid in digest_files
        assert fid not in out1["digest"]["surfaceIds"]

    # f04 has CCN 14; top-N by score are the highest CCNs — f04 is outside on sweep 1.
    boundary = "hotspots:f04.py"
    assert boundary in outside_cap
    boundary_prev = dict(digest_files[boundary])

    # Reshuffle: drop CCN of former top so f04 enters without changing its own metric.
    radon_payload2 = {}
    for i in range(n_measured):
        name = "f%02d.py" % i
        ccn = 14 if i == 4 else max(10, (10 + i) // 2)
        radon_payload2[os.path.join(abs_repo, name)] = [
            {"complexity": ccn, "name": "f", "lineno": 1},
        ]

    def fake_run2(argv, **kwargs):
        if "radon" in str(argv[0]):
            return _proc(stdout=json.dumps(radon_payload2))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out2 = hot.HotspotsLens().collect({
        "cwd": abs_repo, "run": fake_run2, "prev_digest": out1["digest"],
    })
    assert boundary in {c["id"] for c in out2["candidates"]}, (
        "second sweep must move boundary across the top-N cap (otherwise assert is vacuous)"
    )
    assert out2["digest"]["files"][boundary]["ccn"] == boundary_prev["ccn"]
    assert out2["digest"]["files"][boundary]["score"] == boundary_prev["score"]
    d = hot.LENS.diff(out1["digest"], out2["digest"])
    assert boundary not in d["new"], d


def test_git_failure_degrades_instead_of_empty_baseline(tmp_path):
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    _commit(repo, "a.py", "x\n", "c")

    def failing_run(argv, **kwargs):
        if "ls-files" in argv:
            return _proc(stdout="", returncode=128)
        return subprocess.run(argv, **kwargs)

    with pytest.raises(gl.LensDegraded) as exc:
        hot.tracked_existing_files(str(repo), run=failing_run)
    assert "ls-files" in exc.value.reason

    def fail_log(argv, **kwargs):
        if "log" in argv and "--numstat" in argv:
            return _proc(stdout="", returncode=128)
        return subprocess.run(argv, **kwargs)

    with pytest.raises(gl.LensDegraded) as exc2:
        hot._collect_churn({"cwd": str(repo), "run": fail_log}, "90 days")
    assert "numstat" in exc2.value.reason

    def fail_shallow(argv, **kwargs):
        if "--is-shallow-repository" in argv:
            return _proc(stdout="", returncode=128)
        return subprocess.run(argv, **kwargs)

    with pytest.raises(gl.LensDegraded) as exc3:
        hot.observe_window(str(repo), run=fail_shallow)
    assert "shallow" in exc3.value.reason


def test_radon_error_carries_prior_digest_entry(tmp_path, monkeypatch):
    """A radon per-file error must not erase a prior hotspot from the digest.

    Uses two tracked files so a single error is not 'all files of a language'.
    """
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "def hot():\n" + ("  x = 1\n" * 30)
    _commit(repo, "hot.py", body, "c1")
    _commit(repo, "hot.py", body + "  y = 2\n", "c2")
    _commit(repo, "ok.py", body, "c3")
    abs_repo = os.path.realpath(str(repo))
    prev = {
        "files": {
            "hotspots:hot.py": {"score": 3.5, "ccn": 15},
        },
    }

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            abs_hot = os.path.join(abs_repo, "hot.py")
            abs_ok = os.path.join(abs_repo, "ok.py")
            return _proc(stdout=json.dumps({
                abs_hot: [{"error": "invalid syntax"}],
                abs_ok: [{"complexity": 12, "name": "ok", "lineno": 1}],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out = hot.HotspotsLens().collect({
        "cwd": abs_repo, "run": fake_run, "prev_digest": prev,
    })
    assert "hotspots:hot.py" in out["digest"]["files"]
    assert out["digest"]["files"]["hotspots:hot.py"]["ccn"] == 15
    assert out["digest"]["files"]["hotspots:hot.py"]["score"] == 3.5
    assert any(e.get("path") == "hot.py" for e in out["diagnostics"]["collectorErrors"])
    assert "hotspots:hot.py" not in {c["id"] for c in out["candidates"]}


def test_radon_error_without_prior_is_unmeasured(tmp_path, monkeypatch):
    """A per-file radon error with no prior digest entry must be recorded, not omitted."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    body = "def hot():\n" + ("  x = 1\n" * 30)
    _commit(repo, "hot.py", body, "c1")
    _commit(repo, "ok.py", body, "c2")
    abs_repo = os.path.realpath(str(repo))

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            return _proc(stdout=json.dumps({
                os.path.join(abs_repo, "hot.py"): [{"error": "invalid syntax"}],
                os.path.join(abs_repo, "ok.py"): [
                    {"complexity": 12, "name": "ok", "lineno": 1},
                ],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    out = hot.HotspotsLens().collect({
        "cwd": abs_repo, "run": fake_run, "prev_digest": None,
    })
    rec = out["digest"]["files"]["hotspots:hot.py"]
    assert rec.get("unmeasured") is True
    assert rec.get("error") is True


def test_radon_errors_all_files_degrade(tmp_path, monkeypatch):
    """When every tracked file of a language errors, the lens must degrade."""
    repo = _hotspots_fixture_repo(tmp_path)
    abs_repo = os.path.realpath(str(repo))

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            abs_hot = os.path.join(abs_repo, "hot.py")
            return _proc(stdout=json.dumps({
                abs_hot: [{"error": "invalid syntax"}],
            }))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    with pytest.raises(gl.LensDegraded) as exc:
        hot.HotspotsLens().collect({
            "cwd": abs_repo, "run": fake_run, "prev_digest": None,
        })
    assert "all" in exc.value.reason.lower() or "per-file" in exc.value.reason


def test_calibrated_complexity_threshold_governs_union_past_top_n(tmp_path, monkeypatch):
    """Calibrated complexity must feed apply_cap's red-line union through collect()."""
    repo = tmp_path / "r"
    repo.mkdir()
    _git_init(repo)
    abs_repo = os.path.realpath(str(repo))

    radon_payload = {}
    for i in range(hot.TOP_N + 1):
        name = "hot%02d.py" % i
        # Small files: high relative churn from the stubbed numstat below.
        body = "def f():\n" + ("  x = 1\n" * 10)
        _commit(repo, name, body, "add %s" % name)
        radon_payload[os.path.join(abs_repo, name)] = [
            {"complexity": 20, "name": "f", "lineno": 1},
        ]
    # Large mid file + tiny stubbed churn → score loses to fillers; CCN 60 for union.
    mid_body = "def m():\n" + ("  x = 1\n" * 1000)
    _commit(repo, "mid.py", mid_body, "add mid")
    radon_payload[os.path.join(abs_repo, "mid.py")] = [
        {"complexity": 60, "name": "m", "lineno": 1},
    ]

    def fake_churn(ctx, since):
        out = {}
        for i in range(hot.TOP_N + 1):
            out["hot%02d.py" % i] = {"added": 9, "deleted": 0}
        out["mid.py"] = {"added": 1, "deleted": 0}
        return out

    monkeypatch.setattr(hot, "_collect_churn", fake_churn)

    def resolve(tool, cwd, run=None):
        return {"tool": tool, "found": True, "path": "/fake/%s" % tool, "source": "path"}

    monkeypatch.setattr(gt, "resolve", resolve)
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "1.0")

    def fake_run(argv, **kwargs):
        if "radon" in str(argv[0]):
            return _proc(stdout=json.dumps(radon_payload))
        if "lizard" in str(argv[0]):
            return _proc(stdout="")
        return subprocess.run(argv, **kwargs)

    lens_def = hot.HotspotsLens()
    out_def = lens_def.collect({
        "cwd": abs_repo, "run": fake_run, "prev_digest": None,
    })
    assert "mid.py" not in [c["path"] for c in out_def["candidates"]], [
        (c["path"], c.get("hotspotScore"), c.get("maxFunctionCCN"), c.get("relativeChurn"))
        for c in out_def["candidates"]
    ]
    assert out_def["diagnostics"]["redLineUnionAdded"] == 0
    assert lens_def.red_lines(out_def["candidates"]) == []

    lens_cal = hot.HotspotsLens()
    out_cal = lens_cal.collect({
        "cwd": abs_repo,
        "run": fake_run,
        "config": {"thresholds": {"complexity": 50}},
        "prev_digest": None,
    })
    assert "mid.py" in [c["path"] for c in out_cal["candidates"]]
    assert out_cal["diagnostics"]["redLineUnionAdded"] >= 1
    assert any(r["id"] == "hotspots:mid.py" for r in lens_cal.red_lines(out_cal["candidates"]))
