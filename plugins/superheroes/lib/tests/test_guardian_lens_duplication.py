"""Duplication lens — jscpd detects, difflib measures. Never invokes real jscpd."""
import difflib
import json
import os

import pytest

import guardian_lens as gl
import guardian_lens_duplication as gld
import guardian_tools as gt

_FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "guardian", "jscpd-report.json",
)


def _load_fixture():
    with open(_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class _FakeJscpdRun:
    """Replay a canned jscpd report into --output; never spawn a real collector."""

    def __init__(self, report, returncode=0):
        self.report = report
        self.returncode = returncode
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), dict(kwargs)))
        if "--version" in argv:
            class R:
                returncode = 0
                stdout = "4.0.0\n"
                stderr = ""
            return R()
        out_dir = None
        for i, arg in enumerate(argv):
            if arg == "--output" and i + 1 < len(argv):
                out_dir = argv[i + 1]
                break
        if out_dir and self.returncode == 0:
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, "jscpd-report.json"), "w", encoding="utf-8") as fh:
                json.dump(self.report, fh)
        class R:
            returncode = self.returncode
            stdout = ""
            stderr = "jscpd failed" if self.returncode else ""
        return R()


def _write_pair(tmp_path, name_a, name_b, lines_a, lines_b):
    pa = tmp_path / name_a
    pb = tmp_path / name_b
    pa.parent.mkdir(parents=True, exist_ok=True)
    pb.parent.mkdir(parents=True, exist_ok=True)
    pa.write_text("\n".join(lines_a) + "\n", encoding="utf-8")
    pb.write_text("\n".join(lines_b) + "\n", encoding="utf-8")
    return str(pa), str(pb)


def _clone_entry(path_a, path_b, *, lines=177, start_a=219, end_a=395,
                 start_b=123, end_b=126, fmt="bash", tokens=54):
    return {
        "firstFile": {
            "end": end_a,
            "endLoc": {"column": 0, "line": end_a, "position": 0},
            "name": "%s:%s" % (path_a, fmt),
            "start": start_a,
            "startLoc": {"column": 0, "line": start_a, "position": 0},
        },
        "format": fmt,
        "fragment": "synthetic",
        "lines": lines,
        "secondFile": {
            "end": end_b,
            "endLoc": {"column": 0, "line": end_b, "position": 0},
            "name": "%s:%s" % (path_b, fmt),
            "start": start_b,
            "startLoc": {"column": 0, "line": start_b, "position": 0},
        },
        "tokens": tokens,
    }


# --- fixture parsing --------------------------------------------------------------

def test_fixture_pairs_deduped_format_stripped_self_deferred(tmp_path, monkeypatch):
    report = _load_fixture()
    # Materialize every path the fixture names so measurement can run.
    names = set()
    for dup in report["duplicates"]:
        for key in ("firstFile", "secondFile"):
            raw = dup[key]["name"]
            names.add(raw.rsplit(":", 1)[0])
    for rel in names:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        # Distinct enough content that cross-file shared blocks stay below threshold
        # except where we do not care — parsing assertions focus on ids / diagnostics.
        p.write_text("line unique to %s\n" % rel, encoding="utf-8")

    # Overwrite the asymmetric pair with a measurable shared block so a candidate emits.
    shared = ["MEAS_%d" % i for i in range(12)]
    a = tmp_path / "plugins/superheroes/skills/audit-debt/SKILL.md"
    b = tmp_path / "plugins/superheroes/skills/review-code/SKILL.md"
    a.write_text("\n".join(["A_ONLY"] + shared + ["A_END"]) + "\n")
    b.write_text("\n".join(["B_ONLY"] + shared + ["B_END"]) + "\n")

    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    run = _FakeJscpdRun(report)
    lens = gld.DuplicationLens()
    out = lens.collect({"cwd": str(tmp_path), "run": run})

    ids = [c["id"] for c in out["candidates"]]
    assert len(ids) == len(set(ids)), "pairs must be deduped to one candidate each"

    for c in out["candidates"]:
        for f in c["files"]:
            assert ":" not in f.split("/")[-1] or f.endswith(".md"), (
                "format suffix must be stripped from candidate paths: %r" % f)
            assert not f.endswith(":bash") and not f.endswith(":markdown")

    # Self-pair CONVENTIONS.md ↔ CONVENTIONS.md deferred
    assert out["diagnostics"]["selfClonesDeferred"] >= 1
    for c in out["candidates"]:
        assert c["files"][0] != c["files"][1]

    # Sorted id identity, no content hash
    for c in out["candidates"]:
        a_path, b_path = c["files"]
        assert c["id"] == "duplication:%s|%s" % tuple(sorted([a_path, b_path]))
        assert "|" in c["id"] and "#" not in c["id"]


# --- asymmetry: jscpd lines are provenance only -----------------------------------

def test_asymmetry_remeasured_not_jscpd_span(tmp_path, monkeypatch):
    """jscpd reports 177 for 219-395 / 123-126; difflib must supply the real number."""
    fixture = _load_fixture()
    asym = next(
        d for d in fixture["duplicates"]
        if d["firstFile"]["start"] == 219 and d["firstFile"]["end"] == 395
        and d["secondFile"]["start"] == 123 and d["secondFile"]["end"] == 126
    )
    assert asym["lines"] == 177

    known_shared = 12
    shared = ["KNOWN_SHARED_%d" % i for i in range(known_shared)]
    _write_pair(
        tmp_path, "file_a.md", "file_b.md",
        ["ONLY_A"] + shared + ["END_A"],
        ["ONLY_B"] + shared + ["END_B"],
    )
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [
            _clone_entry("file_a.md", "file_b.md", lines=177,
                         start_a=219, end_a=395, start_b=123, end_b=126),
        ],
    }
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    lens = gld.DuplicationLens()
    out = lens.collect({"cwd": str(tmp_path), "run": _FakeJscpdRun(report)})
    assert len(out["candidates"]) == 1
    cand = out["candidates"][0]
    assert cand["jscpdReportedLines"] == 177
    assert cand["longestBlockLines"] == known_shared
    assert cand["longestBlockLines"] != 177
    assert cand["sharedLines"] == known_shared
    assert cand["metric"] == known_shared


# --- autojunk pinning -------------------------------------------------------------

def test_autojunk_false_is_required(tmp_path, monkeypatch):
    """Default autojunk=True changes the answer; the lens must pin autojunk=False."""
    shared_unique = ["SHARED_LINE_%d" % i for i in range(20)]
    shared_with_blanks = ["", "### Heading", "", "Matching status line exactly.", ""]
    blanks_pad = [""] * 180
    unique_a = ["ONLY_A_%d" % i for i in range(50)]
    unique_b = ["ONLY_B_%d" % i for i in range(50)]
    lines_a = blanks_pad + unique_a + shared_unique + shared_with_blanks + ["TAIL_A"]
    lines_b = (
        blanks_pad[:100] + unique_b + shared_unique + shared_with_blanks
        + ["TAIL_B"] + blanks_pad[100:]
    )
    assert len(lines_b) >= 200
    false_shared = sum(
        n for _i, _j, n in difflib.SequenceMatcher(
            None, lines_a, lines_b, autojunk=False).get_matching_blocks()
        if n >= gld.MIN_BLOCK_LINES)
    true_shared = sum(
        n for _i, _j, n in difflib.SequenceMatcher(
            None, lines_a, lines_b, autojunk=True).get_matching_blocks()
        if n >= gld.MIN_BLOCK_LINES)
    assert false_shared != true_shared, "fixture must exercise autojunk disagreement"

    _write_pair(tmp_path, "a.txt", "b.txt", lines_a, lines_b)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [_clone_entry("a.txt", "b.txt", lines=99, fmt="text")],
    }
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    out = gld.DuplicationLens().collect({"cwd": str(tmp_path), "run": _FakeJscpdRun(report)})
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["sharedLines"] == false_shared
    assert out["candidates"][0]["sharedLines"] != true_shared


# --- diff -------------------------------------------------------------------------

def test_diff_new_worsened_resolved_and_none_prev():
    lens = gld.DuplicationLens()
    cur = {
        "schemaVersion": 1,
        "toolVersions": {"jscpd": "4.0.0"},
        "pairs": {
            "duplication:a|b": {"longest": 10, "shared": 20},
            "duplication:c|d": {"longest": 8, "shared": 15},
        },
    }
    prev = {
        "schemaVersion": 1,
        "toolVersions": {"jscpd": "4.0.0"},
        "pairs": {
            "duplication:a|b": {"longest": 10, "shared": 12},
            "duplication:e|f": {"longest": 9, "shared": 9},
        },
    }
    d = lens.diff(prev, cur)
    assert set(d["new"]) == {"duplication:c|d"}
    assert set(d["worsened"]) == {"duplication:a|b"}
    assert set(d["resolved"]) == {"duplication:e|f"}

    d_none = lens.diff(None, cur)
    assert set(d_none["new"]) == set(cur["pairs"])
    assert d_none["worsened"] == []
    assert d_none["resolved"] == []

    d_bad = lens.diff("not-a-digest", cur)
    assert set(d_bad["new"]) == set(cur["pairs"])

    # unmeasured → measured is not `new`; unmeasured never counts as resolved
    prev_u = {
        "schemaVersion": 1,
        "pairs": {
            "duplication:a|b": {"unmeasured": True},
            "duplication:gone|x": {"unmeasured": True},
        },
    }
    cur_u = {
        "schemaVersion": 1,
        "pairs": {
            "duplication:a|b": {"longest": 20, "shared": 20},
        },
    }
    d_u = lens.diff(prev_u, cur_u)
    assert "duplication:a|b" not in d_u["new"]
    assert "duplication:a|b" not in d_u["worsened"]
    assert "duplication:gone|x" not in d_u["resolved"]


def test_diff_filters_to_surface_ids_and_counts_suppressed():
    """Full digest drift outside the presentation cap must not return those ids."""
    lens = gld.DuplicationLens()
    prev = {
        "schemaVersion": 1,
        "pairs": {
            "duplication:a|b": {"longest": 10, "shared": 10},
        },
        "surfaceIds": ["duplication:a|b"],
    }
    cur = {
        "schemaVersion": 1,
        "pairs": {
            "duplication:a|b": {"longest": 10, "shared": 10},
            "duplication:c|d": {"longest": 8, "shared": 8},  # new, outside surface
            "duplication:e|f": {"longest": 12, "shared": 12},  # new, on surface
        },
        "surfaceIds": ["duplication:a|b", "duplication:e|f"],
    }
    d = lens.diff(prev, cur)
    assert set(d["new"]) == {"duplication:e|f"}
    assert "duplication:c|d" not in d["new"]
    assert d["driftSuppressedByCap"] == 1


# --- red lines --------------------------------------------------------------------

def test_red_line_fires_on_remeasured_large_fresh_clone():
    lens = gld.DuplicationLens()
    lens._prev_digest = None
    cand = {
        "id": "duplication:a|b",
        "files": ["a", "b"],
        "longestBlockLines": 100,
        "sharedLines": 100,
        "jscpdReportedLines": 50,
        "metric": 100,
    }
    rl = lens.red_lines([cand])
    assert len(rl) == 1
    assert rl[0]["kind"] == "large-fresh-clone"
    assert rl[0]["id"] == cand["id"]
    assert "100" in rl[0]["detail"]


def test_red_line_does_not_fire_on_jscpd_177_with_small_remeasure():
    lens = gld.DuplicationLens()
    lens._prev_digest = None
    cand = {
        "id": "duplication:a|b",
        "files": ["a", "b"],
        "longestBlockLines": 12,
        "sharedLines": 12,
        "jscpdReportedLines": 177,
        "metric": 12,
    }
    assert lens.red_lines([cand]) == []


def test_red_line_does_not_refire_unchanged_known_pair():
    lens = gld.DuplicationLens()
    pid = "duplication:a|b"
    lens._prev_digest = {
        "schemaVersion": 1,
        "toolVersions": {"jscpd": "4.0.0"},
        "pairs": {pid: {"longest": 120, "shared": 120}},
    }
    cand = {
        "id": pid,
        "files": ["a", "b"],
        "longestBlockLines": 120,
        "sharedLines": 120,
        "jscpdReportedLines": 200,
        "metric": 120,
    }
    assert lens.red_lines([cand]) == []


def test_red_line_fires_when_longest_grows():
    lens = gld.DuplicationLens()
    pid = "duplication:a|b"
    lens._prev_digest = {
        "schemaVersion": 1,
        "pairs": {pid: {"longest": 100, "shared": 100}},
    }
    cand = {
        "id": pid,
        "files": ["a", "b"],
        "longestBlockLines": 110,
        "sharedLines": 110,
        "jscpdReportedLines": 50,
        "metric": 110,
    }
    rl = lens.red_lines([cand])
    assert len(rl) == 1
    assert rl[0]["kind"] == "large-fresh-clone"


# --- degrade ----------------------------------------------------------------------

def test_degrade_when_jscpd_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": False, "path": None, "source": None,
    })
    lens = gld.DuplicationLens()
    with pytest.raises(gl.LensDegraded) as excinfo:
        lens.collect({"cwd": str(tmp_path), "run": _FakeJscpdRun({})})
    assert "npm install -g jscpd" in excinfo.value.reason


def test_degrade_on_nonzero_jscpd_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    lens = gld.DuplicationLens()
    with pytest.raises(gl.LensDegraded):
        lens.collect({"cwd": str(tmp_path), "run": _FakeJscpdRun({}, returncode=1)})


def test_degrade_on_report_missing_duplicates_list(tmp_path, monkeypatch):
    """Valid JSON without list-valued duplicates must not erase the baseline."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    lens = gld.DuplicationLens()
    # Missing key
    with pytest.raises(gl.LensDegraded) as exc:
        lens.collect({
            "cwd": str(tmp_path),
            "run": _FakeJscpdRun({"statistics": {}}),
        })
    assert "duplicates" in exc.value.reason
    # Present but not a list
    with pytest.raises(gl.LensDegraded) as exc2:
        lens.collect({
            "cwd": str(tmp_path),
            "run": _FakeJscpdRun({"duplicates": {"not": "a list"}}),
        })
    assert "duplicates" in exc2.value.reason


def test_top_n_cap_and_red_line_union():
    cands = []
    for i in range(30):
        cands.append({
            "id": "duplication:a%d|b%d" % (i, i),
            "files": ["a%d" % i, "b%d" % i],
            "longestBlockLines": 10,
            "sharedLines": 50 - i,  # descending shared
            "jscpdReportedLines": 10,
            "metric": 50 - i,
        })
    outlier = {
        "id": "duplication:out|lier",
        "files": ["out", "lier"],
        "longestBlockLines": 120,
        "sharedLines": 1,  # low shared → outside top-N
        "jscpdReportedLines": 120,
        "metric": 1,
    }
    cands.append(outlier)
    capped, diag = gld.apply_cap(
        cands, top_n=gld.TOP_N, always_include_clone_lines=100,
    )
    ids = [c["id"] for c in capped]
    assert outlier["id"] in ids
    assert diag["candidatesBeforeCap"] == 31
    assert diag["capApplied"] == gld.TOP_N
    assert diag["redLineUnionAdded"] == 1


def test_calibrated_clone_threshold_drives_red_lines_end_to_end(tmp_path, monkeypatch):
    """Owner-calibrated cloneLines via config must change red_lines; default must not fire.

    Candidate longestBlockLines sits below the default (100) but at/above a lowered
    calibrated threshold. Drive collect() then red_lines() — do not assert private fields.
    """
    shared = ["CL_%d" % i for i in range(40)]
    _write_pair(tmp_path, "src/a.py", "src/b.py", shared, shared)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [_clone_entry("src/a.py", "src/b.py", lines=40, tokens=80)],
    }
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")

    lens_cal = gld.DuplicationLens()
    out_cal = lens_cal.collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "config": {"thresholds": {"cloneLines": 30}},
        "prev_digest": None,
    })
    assert out_cal["candidates"], out_cal
    assert out_cal["candidates"][0]["longestBlockLines"] >= 30
    assert out_cal["candidates"][0]["longestBlockLines"] < gl.RED_LINE_THRESHOLDS["cloneLines"]
    rl_cal = lens_cal.red_lines(out_cal["candidates"])
    assert len(rl_cal) == 1
    assert rl_cal[0]["kind"] == "large-fresh-clone"

    lens_def = gld.DuplicationLens()
    out_def = lens_def.collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": None,
    })
    assert lens_def.red_lines(out_def["candidates"]) == []


def test_calibrated_clone_threshold_governs_union_past_top_n(tmp_path, monkeypatch):
    """Calibrated cloneLines must feed apply_cap's red-line union through collect()."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")

    dups = []
    measures = {}
    for i in range(gld.TOP_N + 1):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=10, tokens=50 - i))
        # High shared → fills top-N; longest stays below default red-line (100).
        measures[(a, b)] = (10, 50 - i)
    (tmp_path / "mid.py").write_text("m\n", encoding="utf-8")
    (tmp_path / "pair.py").write_text("p\n", encoding="utf-8")
    dups.append(_clone_entry("mid.py", "pair.py", lines=40, tokens=1))
    # High longest (40), lowest shared — outside top-N by shared, in via union at 30.
    measures[("mid.py", "pair.py")] = (40, 1)
    mid_id = gld._pair_id("mid.py", "pair.py")

    def fake_measure(path_a, path_b):
        rel_a = os.path.relpath(path_a, str(tmp_path))
        rel_b = os.path.relpath(path_b, str(tmp_path))
        key = tuple(sorted([rel_a, rel_b]))
        # measures keys are unsorted path pairs as written
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }

    lens_def = gld.DuplicationLens()
    out_def = lens_def.collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": None,
    })
    assert mid_id not in {c["id"] for c in out_def["candidates"]}
    assert out_def["diagnostics"]["redLineUnionAdded"] == 0
    assert lens_def.red_lines(out_def["candidates"]) == []

    lens_cal = gld.DuplicationLens()
    out_cal = lens_cal.collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "config": {"thresholds": {"cloneLines": 30}},
        "prev_digest": None,
    })
    assert mid_id in {c["id"] for c in out_cal["candidates"]}
    assert out_cal["diagnostics"]["redLineUnionAdded"] == 1
    assert any(r["id"] == mid_id for r in lens_cal.red_lines(out_cal["candidates"]))


def test_digest_persists_full_measured_set_not_just_cap(tmp_path, monkeypatch):
    """Digest must hold every measured pair — not only the capped presentation set.

    Drives DuplicationLens.collect() on a fixture with more measured pairs than
    TOP_N. A regression that persists only capped/presented ids must fail the
    count and membership asserts below. The second sweep then moves an unchanged
    outside-cap pair across the top-N boundary; it must not appear as `new`.
    """
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")

    n_measured = gld.TOP_N + 5  # strictly more measured pairs than the presentation cap
    dups = []
    measures = {}
    measured_ids = []
    for i in range(n_measured):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=10 + i))
        # sharedLines = 10+i → highest index ranks first; a00 lowest (outside top-N)
        measures[(a, b)] = (10, 10 + i)
        measured_ids.append(gld._pair_id(a, b))

    def fake_measure(path_a, path_b):
        rel_a = os.path.relpath(path_a, str(tmp_path))
        rel_b = os.path.relpath(path_b, str(tmp_path))
        key = tuple(sorted([rel_a, rel_b]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }
    out1 = gld.DuplicationLens().collect({
        "cwd": str(tmp_path), "run": _FakeJscpdRun(report), "prev_digest": None,
    })
    presented = out1["candidates"]
    digest_pairs = out1["digest"]["pairs"]
    presented_ids = {c["id"] for c in presented}

    assert out1["diagnostics"]["candidatesBeforeCap"] == n_measured
    assert len(presented) == gld.TOP_N
    # Direct capped-digest regression check: full measured set in digest, larger than presentation.
    assert len(digest_pairs) == n_measured > len(presented), (
        "digest must persist all %d measured pairs, not only the capped %d: got %d"
        % (n_measured, len(presented), len(digest_pairs))
    )
    for pid in measured_ids:
        assert pid in digest_pairs, "measured pair missing from digest: %s" % pid
    outside_cap = [pid for pid in measured_ids if pid not in presented_ids]
    assert outside_cap, "fixture must leave measured pairs outside the presentation cap"
    for pid in outside_cap:
        assert pid in digest_pairs
        assert pid not in out1["digest"]["surfaceIds"]

    # Boundary pair: lowest shared on sweep 1 (outside cap); metric stays fixed on sweep 2.
    boundary = gld._pair_id("a00.py", "b00.py")
    assert boundary in outside_cap
    boundary_prev = dict(digest_pairs[boundary])

    # Reshuffle: drop others' shared so boundary enters top-N without changing its own metric.
    for i in range(n_measured):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        if i == 0:
            measures[(a, b)] = (10, 10)  # unchanged
        else:
            measures[(a, b)] = (10, max(1, (10 + i) // 3))

    out2 = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": out1["digest"],
    })
    assert boundary in {c["id"] for c in out2["candidates"]}, (
        "second sweep must move boundary across the top-N cap (otherwise assert is vacuous)"
    )
    assert out2["digest"]["pairs"][boundary]["shared"] == boundary_prev["shared"]
    assert out2["digest"]["pairs"][boundary]["longest"] == boundary_prev["longest"]
    d = gld.LENS.diff(out1["digest"], out2["digest"])
    assert boundary not in d["new"], d


def test_degrade_on_malformed_duplicate_entry(tmp_path, monkeypatch):
    """A duplicates entry with renamed/missing name fields must degrade, not skip.

    One good + one name-renamed entry → LensDegraded (baseline preserved by shell),
    not a successful digest with only the good pair measured.
    """
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    lens = gld.DuplicationLens()
    report = {
        "duplicates": [
            {
                "firstFile": {"name": "a.py"},
                "secondFile": {"name": "b.py"},
                "lines": 10,
                "tokens": 20,
            },
            {
                # jscpd-upgrade rename: usable paths live under fileName, not name
                "firstFile": {"fileName": "c.py"},
                "secondFile": {"fileName": "d.py"},
                "lines": 10,
                "tokens": 20,
            },
        ],
    }
    with pytest.raises(gl.LensDegraded) as exc:
        lens.collect({"cwd": str(tmp_path), "run": _FakeJscpdRun(report)})
    reason = exc.value.reason
    assert "malformed" in reason
    assert "1 malformed" in reason
    assert "first offending index 1" in reason


def test_measure_budget_ranks_before_measuring_and_carries_forward(tmp_path, monkeypatch):
    """MAX_PAIRS_MEASURED stops measurement; unmeasured pairs carry prior digest entries."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 2)

    dups = []
    measure_calls = []
    for i, tokens in enumerate((300, 200, 100, 50)):
        a, b = "p%d_a.py" % i, "p%d_b.py" % i
        (tmp_path / a).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        (tmp_path / b).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=tokens))

    real_measure = gld._measure_pair

    def counting_measure(path_a, path_b):
        measure_calls.append((path_a, path_b))
        return real_measure(path_a, path_b)

    monkeypatch.setattr(gld, "_measure_pair", counting_measure)

    low_id = gld._pair_id("p3_a.py", "p3_b.py")  # lowest tokens — last in rank
    high_id = gld._pair_id("p0_a.py", "p0_b.py")
    prev = {
        "schemaVersion": 1,
        "pairs": {
            low_id: {"longest": 8, "shared": 8},
            high_id: {"longest": 8, "shared": 8},
        },
    }
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }
    lens = gld.DuplicationLens()
    out = lens.collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": prev,
    })
    diag = out["diagnostics"]
    assert diag["pairsConsidered"] == 4
    assert diag["pairsMeasured"] == 2
    assert diag["pairsSkippedBudget"] == 2
    assert diag["budgetExhausted"] == "pairs"
    assert diag["pairsCarriedForward"] >= 1
    assert len(measure_calls) == 2
    # Highest-token pairs measured first
    measured_rels = [
        tuple(sorted([
            os.path.relpath(a, str(tmp_path)),
            os.path.relpath(b, str(tmp_path)),
        ]))
        for a, b in measure_calls
    ]
    assert ("p0_a.py", "p0_b.py") in measured_rels
    assert ("p1_a.py", "p1_b.py") in measured_rels
    assert ("p3_a.py", "p3_b.py") not in measured_rels
    # Unmeasured-but-present low_id carried forward — must not vanish
    assert low_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][low_id].get("carriedForward") is True
    assert out["digest"]["pairs"][low_id]["shared"] == 8


def test_unmeasured_without_prior_is_recorded_not_absent(tmp_path, monkeypatch):
    """A pair skipped by budget with no prior entry is persisted as unmeasured."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 1)

    dups = []
    for i, tokens in enumerate((200, 50)):
        a, b = "u%d_a.py" % i, "u%d_b.py" % i
        (tmp_path / a).write_text("x\n" * 8, encoding="utf-8")
        (tmp_path / b).write_text("x\n" * 8, encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=tokens))
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }
    out = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": None,
    })
    assert out["diagnostics"]["pairsMeasured"] == 1
    assert out["diagnostics"]["pairsUnmeasured"] == 1
    assert out["diagnostics"]["budgetExhausted"] == "pairs"
    low_id = gld._pair_id("u1_a.py", "u1_b.py")
    assert low_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][low_id] == {"unmeasured": True}

    # Next sweep measuring it must not invent `new` drift.
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 10)
    out2 = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": out["digest"],
    })
    d = gld.LENS.diff(out["digest"], out2["digest"])
    assert low_id not in d["new"]
    assert low_id not in d["worsened"]


def test_measure_time_budget_skips_remaining(tmp_path, monkeypatch):
    """MEASURE_TIME_BUDGET_SECONDS must stop measurement (not only the pairs cap)."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    monkeypatch.setattr(gld, "MEASURE_TIME_BUDGET_SECONDS", 5)

    clock = {"t": 0.0}

    def fake_monotonic():
        return clock["t"]

    monkeypatch.setattr(gld.time, "monotonic", fake_monotonic)

    dups = []
    for i, tokens in enumerate((300, 200, 100)):
        a, b = "t%d_a.py" % i, "t%d_b.py" % i
        (tmp_path / a).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        (tmp_path / b).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=tokens))

    real_measure = gld._measure_pair

    def slow_measure(path_a, path_b):
        clock["t"] += 10  # each measure blows the 5s budget for the next pair
        return real_measure(path_a, path_b)

    monkeypatch.setattr(gld, "_measure_pair", slow_measure)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }
    out = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": None,
    })
    assert out["diagnostics"]["budgetExhausted"] == "time"
    assert out["diagnostics"]["pairsMeasured"] == 1
    assert out["diagnostics"]["pairsSkippedBudget"] >= 1
    assert out["diagnostics"]["pairsUnmeasured"] >= 1


def test_oversize_pair_skipped_and_carried(tmp_path, monkeypatch):
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    monkeypatch.setattr(gld, "MAX_MEASURE_FILE_BYTES", 100)

    _write_pair(
        tmp_path, "small_a.py", "small_b.py",
        ["S_%d" % i for i in range(8)],
        ["S_%d" % i for i in range(8)],
    )
    big = "X" * 200
    (tmp_path / "big_a.py").write_text(big, encoding="utf-8")
    (tmp_path / "big_b.py").write_text(big, encoding="utf-8")
    big_id = gld._pair_id("big_a.py", "big_b.py")
    small_id = gld._pair_id("small_a.py", "small_b.py")
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [
            _clone_entry("small_a.py", "small_b.py", lines=8, tokens=10),
            _clone_entry("big_a.py", "big_b.py", lines=8, tokens=10),
        ],
    }
    prev = {
        "schemaVersion": 1,
        "pairs": {big_id: {"longest": 8, "shared": 8}},
    }
    out = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "prev_digest": prev,
    })
    assert out["diagnostics"]["pairsSkippedOversize"] >= 1
    assert big_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][big_id].get("carriedForward") is True
    # Positive control: the small pair must still be measured.
    assert small_id in out["digest"]["pairs"]
    assert "longest" in out["digest"]["pairs"][small_id]
    assert not out["digest"]["pairs"][small_id].get("unmeasured")
    assert not out["digest"]["pairs"][small_id].get("carriedForward")


def test_measurement_union_past_pairs_budget(tmp_path, monkeypatch):
    """A low-token pair with jscpd lines at the clone threshold must still be measured."""
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 2)

    dups = []
    measures = {}
    for i in range(4):
        a, b = "m%d_a.py" % i, "m%d_b.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        # High tokens fill the budget; lines stay below default threshold.
        dups.append(_clone_entry(a, b, lines=10, tokens=400 - i))
        measures[(a, b)] = (10, 10)

    (tmp_path / "big_a.py").write_text("b\n", encoding="utf-8")
    (tmp_path / "big_b.py").write_text("c\n", encoding="utf-8")
    # Lowest tokens (would sit past budget) but jscpd lines hit calibrated threshold.
    dups.append(_clone_entry("big_a.py", "big_b.py", lines=30, tokens=1))
    measures[("big_a.py", "big_b.py")] = (30, 5)
    big_id = gld._pair_id("big_a.py", "big_b.py")

    def fake_measure(path_a, path_b):
        rel_a = os.path.relpath(path_a, str(tmp_path))
        rel_b = os.path.relpath(path_b, str(tmp_path))
        key = tuple(sorted([rel_a, rel_b]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }
    out = gld.DuplicationLens().collect({
        "cwd": str(tmp_path),
        "run": _FakeJscpdRun(report),
        "config": {"thresholds": {"cloneLines": 30}},
        "prev_digest": None,
    })
    assert out["diagnostics"]["measurementUnionAdded"] >= 1
    assert big_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][big_id].get("longest") == 30
    assert not out["digest"]["pairs"][big_id].get("unmeasured")
    assert big_id in {c["id"] for c in out["candidates"]}


# --- side-effect-free -------------------------------------------------------------

def test_collect_writes_nothing_inside_repo(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    shared = ["X_%d" % i for i in range(8)]
    _write_pair(tmp_path, "src/a.py", "src/b.py", shared, shared)
    before = []
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            before.append(os.path.relpath(os.path.join(root, name), tmp_path))
    before.sort()

    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [_clone_entry("src/a.py", "src/b.py", lines=8, fmt="python")],
    }
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")
    gld.DuplicationLens().collect({"cwd": str(tmp_path), "run": _FakeJscpdRun(report)})

    after = []
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            after.append(os.path.relpath(os.path.join(root, name), tmp_path))
    after.sort()
    assert after == before


# --- pricing vocabulary -----------------------------------------------------------

_BANNED = ("bug", "defect", "fault", "crash", "vulnerability", "error-prone")


def test_pricing_vocabulary_change_cost_only():
    """Consequence speaks of change cost / consistency risk — never bug/defect risk."""
    for text in (gld.CONSEQUENCE_TEMPLATE, gld.VALIDATION_GUIDANCE):
        lower = text.lower()
        assert "change cost" in lower or "change-cost" in lower or "consistency" in lower
        assert "every future edit" in lower or "all copies" in lower or "n copies" in lower \
            or "copies" in lower
        for banned in _BANNED:
            assert banned not in lower, "banned %r in %r" % (banned, text)


def test_lens_contract_shape():
    ok, reasons = gl.validate_lens(gld.LENS)
    assert ok, reasons
    assert gld.LENS.name == "duplication"
    assert gld.LENS.collector_version == "2.0.0"
    assert gld.LENS.collector_version != "1.0.0"
    assert gld.LENS.required_facts == ()
    assert gld.LENS.consequence_template is gld.CONSEQUENCE_TEMPLATE
    assert gld.LENS.validation_guidance is gld.VALIDATION_GUIDANCE


def test_collector_version_bumped_with_digest_shape_change():
    """Shipped collector_version must not stay at 1.0.0 after the digest-shape change."""
    assert gld.DuplicationLens.collector_version != "1.0.0"
    assert gld.DuplicationLens.collector_version == gld.LENS.collector_version
    # Shape markers that made 1.0.0 incompatible: surfaceIds + unmeasured entries.
    src_path = gld.__file__
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    assert '"surfaceIds"' in src or "'surfaceIds'" in src
    assert '"unmeasured"' in src or "'unmeasured'" in src
    assert 'collector_version = "2.0.0"' in src


def test_degrade_helper_shape():
    out = gld.LENS.degrade("missing tool")
    assert out == {"lens": "duplication", "degraded": True, "reason": "missing tool"}


# --- Relative cwd forms must agree (FIX-2 symmetry with hotspots) ------------------

@pytest.mark.parametrize("cwd_form", [".", "./", "ABS", "ABS/"])
def test_collect_cwd_forms_agree(tmp_path, monkeypatch, cwd_form):
    """Relative and absolute cwd forms must yield the same candidate set."""
    shared = ["DUP_%d" % i for i in range(12)]
    _write_pair(tmp_path, "src/a.py", "src/b.py",
                ["A_ONLY"] + shared + ["A_END"],
                ["B_ONLY"] + shared + ["B_END"])
    report = {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": [
            _clone_entry("src/a.py", "src/b.py", lines=12, fmt="python",
                         start_a=2, end_a=13, start_b=2, end_b=13),
        ],
    }
    monkeypatch.setattr(gt, "resolve", lambda tool, cwd, run=None: {
        "tool": tool, "found": True, "path": "/fake/jscpd", "source": "path",
    })
    monkeypatch.setattr(gt, "version", lambda tool, cwd, run=None: "4.0.0")

    abs_repo = os.path.realpath(str(tmp_path))
    baseline = gld.DuplicationLens().collect({
        "cwd": abs_repo, "run": _FakeJscpdRun(report),
    })
    base_ids = [c["id"] for c in baseline["candidates"]]
    assert base_ids, "fixture must produce at least one candidate"

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
        out = gld.DuplicationLens().collect({
            "cwd": cwd_arg, "run": _FakeJscpdRun(report),
        })
    finally:
        os.chdir(old)

    assert [c["id"] for c in out["candidates"]] == base_ids
    assert out["diagnostics"]["candidatesBeforeCap"] == (
        baseline["diagnostics"]["candidatesBeforeCap"])
