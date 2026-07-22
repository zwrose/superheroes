"""Duplication lens — jscpd detects, difflib measures. Never invokes real jscpd.

New contract (post #559/#560/#561): tool invocation routes through
``guardian_collect.run_tool`` and the injected ``ctx["run"]`` seam. jscpd's json reporter
is read off stdout (JSON object first, trailing summary ignored). Degradation is a
``not-collected`` / ``partial`` status return — never a raised ``LensDegraded``. The
previous digest is read as camelCase ``ctx["prevDigest"]``.
"""
import difflib
import json
import os
import subprocess

import pytest

import guardian_lens as gl
import guardian_lens_duplication as gld
from test_guardian_conformance import assert_lens_conformance

_FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures", "guardian", "jscpd-report.json",
)


def _load_fixture():
    with open(_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class _FakeJscpd:
    """Return crafted stdout through the ctx['run'] seam; never spawn a collector.

    Post-#564 the lens co-fires TWO tools: ``git ls-files -z`` (the tracked-file census)
    then ``jscpd`` over those files. This stub dispatches on argv[0]:

    - ``git`` — always succeeds (rc 0) with a NUL-separated ``ls-files -z`` payload. By
      default it walks the run's ``cwd`` for on-disk files (excluding ``.git``) so every
      file a test wrote is "tracked"; pass ``tracked=[...]`` to control the census
      explicitly (empty list ⇒ zero tracked). The ``raise_exc`` / ``returncode`` knobs are
      jscpd-only, so the jscpd-degradation scenarios still exercise jscpd itself.
    - anything else (``jscpd``) — the crafted report / stdout / returncode / raise, exactly
      as before, JSON object first then a trailing human summary the parser must ignore.
    """

    def __init__(self, report=None, *, stdout=None, returncode=0, raise_exc=None,
                 trailer=True, tracked=None):
        self.report = report
        self.stdout = stdout
        self.returncode = returncode
        self.raise_exc = raise_exc
        self.trailer = trailer
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
        self.calls.append((list(argv), dict(kwargs)))
        argv0 = argv[0] if argv else ""
        if argv0 == "git":
            return self._git_result(kwargs)
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.stdout is not None:
            text = self.stdout
        else:
            text = json.dumps(self.report)
            if self.trailer:
                text += "\nreport saved to /dev/stdout\n"
        rc = self.returncode

        class R:
            returncode = rc
            stdout = text
            stderr = "" if rc == 0 else "jscpd failed"
        return R()


def _ctx(tmp_path, run, *, config=None, prev_digest=None, cwd=None):
    return {
        "cwd": cwd or str(tmp_path),
        "run": run,
        "config": config,
        "prevDigest": prev_digest,
    }


def _collect(lens, tmp_path, run, **kwargs):
    return lens.collect(_ctx(tmp_path, run, **kwargs))


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


def _report(dups):
    return {
        "statistics": {"total": {}, "formats": {}, "detectionDate": "test"},
        "duplicates": dups,
    }


# --- conformance ------------------------------------------------------------------

def test_lens_instance_passes_conformance():
    """The shipped LENSES[0] instance must satisfy every honesty invariant."""
    assert_lens_conformance(gld.LENSES[0])


def test_module_exposes_lenses_tuple():
    assert gld.LENSES == (gld.LENS,)
    assert isinstance(gld.LENSES[0], gld.DuplicationLens)
    assert gld.LENSES[0].name == "duplication"


# --- fixture parsing --------------------------------------------------------------

def test_fixture_pairs_deduped_format_stripped_self_deferred(tmp_path):
    report = _load_fixture()
    names = set()
    for dup in report["duplicates"]:
        for key in ("firstFile", "secondFile"):
            raw = dup[key]["name"]
            names.add(raw.rsplit(":", 1)[0])
    for rel in names:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("line unique to %s\n" % rel, encoding="utf-8")

    shared = ["MEAS_%d" % i for i in range(12)]
    a = tmp_path / "plugins/superheroes/skills/audit-debt/SKILL.md"
    b = tmp_path / "plugins/superheroes/skills/review-code/SKILL.md"
    a.write_text("\n".join(["A_ONLY"] + shared + ["A_END"]) + "\n")
    b.write_text("\n".join(["B_ONLY"] + shared + ["B_END"]) + "\n")

    lens = gld.DuplicationLens()
    out = _collect(lens, tmp_path, _FakeJscpd(report))
    assert gl.classify_collect(out) == ("collected", None)

    ids = [c["id"] for c in out["candidates"]]
    assert len(ids) == len(set(ids)), "pairs must be deduped to one candidate each"

    for c in out["candidates"]:
        for f in c["files"]:
            assert ":" not in f.split("/")[-1] or f.endswith(".md"), (
                "format suffix must be stripped from candidate paths: %r" % f)
            assert not f.endswith(":bash") and not f.endswith(":markdown")

    assert out["diagnostics"]["selfClonesDeferred"] >= 1
    for c in out["candidates"]:
        assert c["files"][0] != c["files"][1]

    for c in out["candidates"]:
        a_path, b_path = c["files"]
        assert c["id"] == "duplication:%s|%s" % tuple(sorted([a_path, b_path]))
        assert "|" in c["id"] and "#" not in c["id"]


# --- stdout reading ---------------------------------------------------------------

def test_trailing_summary_after_json_is_ignored(tmp_path):
    """jscpd prints a human 'report saved' line after the JSON — raw_decode must ignore it."""
    shared = ["S_%d" % i for i in range(12)]
    _write_pair(tmp_path, "a.md", "b.md",
                ["A"] + shared + ["Z"], ["B"] + shared + ["Y"])
    report = _report([_clone_entry("a.md", "b.md", lines=12, fmt="markdown",
                                   start_a=2, end_a=13, start_b=2, end_b=13)])
    run = _FakeJscpd(report, trailer=True)  # appends trailing summary text
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    assert gl.classify_collect(out)[0] == "collected"
    assert len(out["candidates"]) == 1


# --- asymmetry: jscpd lines are provenance only -----------------------------------

def test_asymmetry_remeasured_not_jscpd_span(tmp_path):
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
    report = _report([
        _clone_entry("file_a.md", "file_b.md", lines=177,
                     start_a=219, end_a=395, start_b=123, end_b=126),
    ])
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    assert len(out["candidates"]) == 1
    cand = out["candidates"][0]
    assert cand["jscpdReportedLines"] == 177
    assert cand["longestBlockLines"] == known_shared
    assert cand["longestBlockLines"] != 177
    assert cand["sharedLines"] == known_shared
    assert cand["metric"] == known_shared


# --- autojunk pinning -------------------------------------------------------------

def test_autojunk_false_is_required(tmp_path):
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
    report = _report([_clone_entry("a.txt", "b.txt", lines=99, fmt="text")])
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["sharedLines"] == false_shared
    assert out["candidates"][0]["sharedLines"] != true_shared


# --- prevDigest camelCase read (regression) ---------------------------------------

def test_collect_reads_prev_digest_camelcase(tmp_path, monkeypatch):
    """collect() must read the baseline from camelCase ctx['prevDigest'] — a snake_case
    read (the pre-rebase bug) would lose the baseline and refire a known red line."""
    monkeypatch.setattr(gld, "_measure_pair", lambda a, b: (120, 120))
    (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("y\n", encoding="utf-8")
    report = _report([_clone_entry("a.py", "b.py", lines=120, tokens=50)])
    pid = gld._pair_id("a.py", "b.py")
    prev_camel = {"schemaVersion": 1, "pairs": {pid: {"longest": 120, "shared": 120}}}

    lens = gld.DuplicationLens()
    ctx = {
        "cwd": str(tmp_path),
        "run": _FakeJscpd(report),
        "prevDigest": prev_camel,
        # snake_case decoy: if collect wrongly read this, the pair would look fresh and
        # the red line would refire.
        "prev_digest": {"schemaVersion": 1, "pairs": {pid: {"longest": 1, "shared": 1}}},
    }
    out = lens.collect(ctx)
    assert lens._prev_digest is prev_camel
    # Known-at-120 pair (longest 120 >= threshold 100) is already in the camelCase
    # baseline and did not grow → no red line. The snake decoy (longest 1) would refire.
    assert lens.red_lines(out["candidates"]) == []


# --- diff -------------------------------------------------------------------------

def test_diff_new_worsened_resolved_and_none_prev():
    lens = gld.DuplicationLens()
    cur = {
        "schemaVersion": 1,
        "pairs": {
            "duplication:a|b": {"longest": 10, "shared": 20},
            "duplication:c|d": {"longest": 8, "shared": 15},
        },
    }
    prev = {
        "schemaVersion": 1,
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


def test_diff_returns_only_the_three_contract_keys():
    """M2: diff() returns ONLY new/worsened/resolved — driftSuppressedByCap is not a diff field."""
    lens = gld.DuplicationLens()
    cur = {
        "schemaVersion": 1,
        "pairs": {"duplication:a|b": {"longest": 10, "shared": 10}},
        "surfaceIds": ["duplication:a|b"],
    }
    d = lens.diff(None, cur)
    assert set(d.keys()) == {"new", "worsened", "resolved"}
    d2 = lens.diff({"pairs": {}}, cur)
    assert set(d2.keys()) == {"new", "worsened", "resolved"}


def test_diff_on_none_digest_emits_no_resolved():
    """Stopped-looking (digest None) must never emit resolved ids, even with a prior."""
    lens = gld.DuplicationLens()
    prev = {"schemaVersion": 1, "pairs": {"duplication:a|b": {"longest": 9, "shared": 9}}}
    d = lens.diff(prev, None)
    assert d == {"new": [], "worsened": [], "resolved": []}


# --- cap suppression is a DIAGNOSTIC, not a diff field (I8 / M2) -------------------

def test_cap_suppression_reported_in_diagnostics_not_diff(tmp_path, monkeypatch):
    """A new pair outside the presentation cap is counted in diagnostics.driftSuppressedByCap
    and filtered out of diff()['new'] — asserted via the reported diagnostic, not bypassed."""
    monkeypatch.setattr(gld, "TOP_N", 1)
    for name in ("a", "b", "c", "d"):
        (tmp_path / ("%s.py" % name)).write_text("%s\n" % name, encoding="utf-8")
    measures = {
        ("a.py", "b.py"): (10, 10),   # high shared → fills the cap of 1
        ("c.py", "d.py"): (8, 5),     # new, low shared → outside the cap
    }

    def fake_measure(path_a, path_b):
        key = tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    ab, cd = gld._pair_id("a.py", "b.py"), gld._pair_id("c.py", "d.py")
    report = _report([
        _clone_entry("a.py", "b.py", lines=10, tokens=90),
        _clone_entry("c.py", "d.py", lines=8, tokens=10),
    ])
    prev = {
        "schemaVersion": 1,
        "pairs": {ab: {"longest": 10, "shared": 10}},
        "surfaceIds": [ab],
    }
    lens = gld.DuplicationLens()
    out = _collect(lens, tmp_path, _FakeJscpd(report), prev_digest=prev)

    assert out["diagnostics"]["driftSuppressedByCap"] == 1
    assert out["digest"]["surfaceIds"] == [ab]
    d = lens.diff(prev, out["digest"])
    assert set(d["new"]) == set()  # cd suppressed by the cap
    assert cd not in d["new"]
    assert "driftSuppressedByCap" not in d


def test_first_baseline_reports_zero_drift_suppressed(tmp_path, monkeypatch):
    """M1: with no prior digest, driftSuppressedByCap must be 0 even with pairs outside the cap."""
    monkeypatch.setattr(gld, "TOP_N", 1)
    for name in ("a", "b", "c", "d"):
        (tmp_path / ("%s.py" % name)).write_text("%s\n" % name, encoding="utf-8")
    measures = {("a.py", "b.py"): (10, 10), ("c.py", "d.py"): (8, 5)}

    def fake_measure(path_a, path_b):
        key = tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = _report([
        _clone_entry("a.py", "b.py", lines=10, tokens=90),
        _clone_entry("c.py", "d.py", lines=8, tokens=10),
    ])
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report), prev_digest=None)
    # Non-vacuity: there IS a measured pair outside the presentation cap.
    assert out["diagnostics"]["candidatesBeforeCap"] > out["diagnostics"]["capApplied"]
    assert out["diagnostics"]["driftSuppressedByCap"] == 0


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
    assert rl[0]["kind"] in gl.RED_LINE_KINDS
    assert rl[0]["id"] == cand["id"]
    assert "100" in rl[0]["detail"]


def test_red_line_kind_sourced_from_authoritative_tuple():
    """I3: the emitted kind is the RED_LINE_KINDS member, not a divergent bare literal."""
    assert gld._RED_LINE_KIND == "large-fresh-clone"
    assert gld._RED_LINE_KIND in gl.RED_LINE_KINDS


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


# --- degradation paths (status returns, never raises) -----------------------------

def _seed_tracked(tmp_path, *names):
    """Write a couple of files so the git census is non-empty and jscpd is reached."""
    for name in (names or ("a.py", "b.py")):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("seed\n", encoding="utf-8")


def test_degrade_when_jscpd_missing_returns_not_collected(tmp_path):
    """Missing tool (run stub raises FileNotFoundError) → not-collected, never raises."""
    _seed_tracked(tmp_path)
    run = _FakeJscpd(raise_exc=FileNotFoundError("jscpd"))
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "not available" in reason


def test_degrade_on_nonzero_jscpd_exit(tmp_path):
    _seed_tracked(tmp_path)
    run = _FakeJscpd(_report([]), returncode=1)
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert reason


def test_degrade_on_empty_stdout(tmp_path):
    """Exit 0 but empty stdout → not-collected (no JSON to read), never a clean baseline."""
    _seed_tracked(tmp_path)
    run = _FakeJscpd(stdout="", returncode=0)
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "no JSON report" in reason


def test_degrade_on_unparseable_stdout(tmp_path):
    _seed_tracked(tmp_path)
    run = _FakeJscpd(stdout="{not valid json at all", returncode=0)
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "unparseable" in reason


def test_reporter_setup_failure_returns_not_collected_never_raises(tmp_path, monkeypatch):
    """F: a failure in the /dev/stdout reporter setup (mkdtemp / os.symlink) must convert
    to not-collected — collect() must NEVER raise out of the never-raises contract."""
    _seed_tracked(tmp_path)

    def boom(*a, **k):
        raise OSError("symlink not permitted")

    monkeypatch.setattr(gld.os, "symlink", boom)
    run = _FakeJscpd(_report([]))  # would collect cleanly if setup had succeeded
    out = _collect(gld.DuplicationLens(), tmp_path, run)  # must not raise
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "reporter setup failed" in reason


def test_degrade_on_report_missing_duplicates_list(tmp_path):
    """Valid JSON without list-valued duplicates must not erase the baseline."""
    _seed_tracked(tmp_path)
    out = _collect(gld.DuplicationLens(), tmp_path,
                   _FakeJscpd({"statistics": {}}))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "duplicates" in reason
    assert out["digest"] is None

    out2 = _collect(gld.DuplicationLens(), tmp_path,
                    _FakeJscpd({"duplicates": {"not": "a list"}}))
    status2, reason2 = gl.classify_collect(out2)
    assert status2 == "not-collected"
    assert "duplicates" in reason2


def test_degrade_on_reported_nonzero_parsed_zero(tmp_path):
    """jscpd summary reports clones but the duplicates array is empty → not-collected."""
    _seed_tracked(tmp_path)
    report = {
        "statistics": {"total": {"clones": 3, "duplicatedLines": 42}},
        "duplicates": [],
    }
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "normalization yielded zero candidates" in reason


def test_clean_zero_clone_report_collects_empty(tmp_path):
    """A genuine zero-clone report (summary 0, empty array) collects with no candidates."""
    _seed_tracked(tmp_path)
    report = {
        "statistics": {"total": {"clones": 0, "duplicatedLines": 0}},
        "duplicates": [],
    }
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    assert gl.classify_collect(out) == ("collected", None)
    assert out["candidates"] == []
    assert out["digest"]["pairs"] == {}


def test_degrade_on_malformed_duplicate_entry(tmp_path):
    """A duplicates entry with renamed/missing name fields must degrade, not skip."""
    _seed_tracked(tmp_path, "a.py", "b.py", "c.py", "d.py")
    report = {
        "duplicates": [
            {"firstFile": {"name": "a.py"}, "secondFile": {"name": "b.py"},
             "lines": 10, "tokens": 20},
            {"firstFile": {"fileName": "c.py"}, "secondFile": {"fileName": "d.py"},
             "lines": 10, "tokens": 20},
        ],
    }
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert "malformed" in reason
    assert "1 malformed" in reason
    assert "first offending index 1" in reason
    assert out["digest"] is None


# --- #564: git-tracked census confinement -----------------------------------------

def test_zero_tracked_short_circuits_not_collected_preserving_baseline(tmp_path):
    """Zero tracked files ⇒ not-collected (digest None) — NEVER a collected empty digest
    that would make diff() mark every prior pair `resolved` (a false 'all clones fixed').
    The prior baseline must survive."""
    # tracked=[] forces an empty census; the jscpd payload would collect cleanly if reached.
    run = _FakeJscpd(_report([]), tracked=[])
    pid = gld._pair_id("x.py", "y.py")
    prev = {"schemaVersion": 1, "pairs": {pid: {"longest": 40, "shared": 40}}}
    out = _collect(gld.DuplicationLens(), tmp_path, run, prev_digest=prev)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "zero tracked files" in reason
    # The baseline is NOT diffed to resolved — cur_digest is None hits diff()'s guard.
    d = gld.LENS.diff(prev, out.get("digest"))
    assert d["resolved"] == []
    # jscpd must never have been spawned with no operands (re-opening #564).
    assert not any(call[0] and call[0][0] == "jscpd" for call in run.calls)


def test_git_census_failure_degrades_not_collected(tmp_path):
    """A git ls-files failure must degrade (not-collected), never an empty tracked set that
    erases the baseline."""
    def run(argv, **kwargs):
        argv0 = argv[0] if argv else ""

        class R:
            returncode = 128 if argv0 == "git" else 0
            stdout = "" if argv0 == "git" else "{}"
            stderr = "fatal: not a git repository" if argv0 == "git" else ""
        return R()

    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "git ls-files failed" in reason


def test_arg_max_guard_degrades_never_scans_cwd(tmp_path, monkeypatch):
    """When the tracked-file operand payload exceeds the cap, degrade honestly — no silent
    cwd fallback, no truncation."""
    monkeypatch.setattr(gld, "MAX_TRACKED_OPERAND_BYTES", 5)
    _seed_tracked(tmp_path, "a.py", "b.py")  # 8 bytes of operands > 5-byte cap
    run = _FakeJscpd(_report([]))
    out = _collect(gld.DuplicationLens(), tmp_path, run)
    status, reason = gl.classify_collect(out)
    assert status == "not-collected"
    assert out["digest"] is None
    assert "across 2 files" in reason
    assert "5-byte cap" in reason
    # jscpd must NOT have been spawned (no cwd fallback).
    assert not any(call[0] and call[0][0] == "jscpd" for call in run.calls)


def test_diagnostics_report_census_provenance(tmp_path):
    """collect() reports censusSource + trackedFilesCensused in diagnostics."""
    shared = ["CENSUS_%d" % i for i in range(12)]
    _write_pair(tmp_path, "a.py", "b.py", shared, shared)
    report = _report([_clone_entry("a.py", "b.py", lines=12, fmt="python")])
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))
    assert gl.classify_collect(out)[0] == "collected"
    assert out["diagnostics"]["censusSource"] == "git ls-files"
    assert out["diagnostics"]["trackedFilesCensused"] == 2


_DUP_SNIPPET = "\n".join([
    "def compute_totals(items):",
    "    total = 0",
    "    for item in items:",
    "        total = total + item.value",
    "        if item.flag:",
    "            total = total + 1",
    "    average = total / max(len(items), 1)",
    "    result = total * 2 + average",
    "    return result, average, total",
]) + "\n"


def test_census_confines_jscpd_to_git_tracked_files_end_to_end(tmp_path):
    """End-to-end (#564): a real git repo with a genuine tracked clone PLUS an untracked
    checkouts/ dir holding byte-duplicates. Driving collect() with a run seam that shells
    out to REAL git and REAL jscpd, the census must confine jscpd to the tracked files:
    no candidate references the untracked junk, the census count equals the tracked count,
    and the genuine tracked clone is still detected (guards against over-confining)."""
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (tmp_path / "a.py").write_text(_DUP_SNIPPET, encoding="utf-8")
    (tmp_path / "b.py").write_text(_DUP_SNIPPET, encoding="utf-8")
    subprocess.run(["git", "add", "a.py", "b.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

    # Untracked junk: byte-duplicates of the tracked files + a nested .git internal.
    junk = tmp_path / "checkouts" / "junk"
    junk.mkdir(parents=True)
    (junk / "a.py").write_text(_DUP_SNIPPET, encoding="utf-8")
    (junk / "b.py").write_text(_DUP_SNIPPET, encoding="utf-8")
    hooks = tmp_path / "checkouts" / "junk" / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit.sample").write_text(_DUP_SNIPPET, encoding="utf-8")

    def run(argv, **kwargs):
        return subprocess.run(
            argv, capture_output=True, text=True,
            timeout=kwargs.get("timeout"), cwd=kwargs.get("cwd"))

    ctx = {"cwd": repo, "run": run, "config": None, "prevDigest": None}
    out = gld.DuplicationLens().collect(ctx)
    status, reason = gl.classify_collect(out)
    assert status == "collected", (status, reason, out.get("diagnostics"))

    # The genuine tracked clone IS detected (not over-confined).
    assert out["candidates"], out
    ids = {c["id"] for c in out["candidates"]}
    assert gld._pair_id("a.py", "b.py") in ids

    # NO candidate references the untracked junk dir (the #564 leak — asserted BEFORE the
    # diagnostics so a pre-fix lens fails on the actual confinement defect).
    for c in out["candidates"]:
        for f in c["files"]:
            assert "checkouts" not in f, (
                "untracked junk leaked into candidates: %r" % f)

    # Census confined to the two tracked files.
    assert out["diagnostics"]["censusSource"] == "git ls-files"
    assert out["diagnostics"]["trackedFilesCensused"] == 2


# --- cap + union ------------------------------------------------------------------

def test_top_n_cap_and_red_line_union():
    cands = []
    for i in range(30):
        cands.append({
            "id": "duplication:a%d|b%d" % (i, i),
            "files": ["a%d" % i, "b%d" % i],
            "longestBlockLines": 10,
            "sharedLines": 50 - i,
            "jscpdReportedLines": 10,
            "metric": 50 - i,
        })
    outlier = {
        "id": "duplication:out|lier",
        "files": ["out", "lier"],
        "longestBlockLines": 120,
        "sharedLines": 1,
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


def test_calibrated_clone_threshold_drives_red_lines_end_to_end(tmp_path):
    """Owner-calibrated cloneLines via config must change red_lines; default must not fire."""
    shared = ["CL_%d" % i for i in range(40)]
    _write_pair(tmp_path, "src/a.py", "src/b.py", shared, shared)
    report = _report([_clone_entry("src/a.py", "src/b.py", lines=40, tokens=80)])

    lens_cal = gld.DuplicationLens()
    out_cal = _collect(lens_cal, tmp_path, _FakeJscpd(report),
                       config={"thresholds": {"cloneLines": 30}}, prev_digest=None)
    assert out_cal["candidates"], out_cal
    assert out_cal["candidates"][0]["longestBlockLines"] >= 30
    assert out_cal["candidates"][0]["longestBlockLines"] < gl.RED_LINE_THRESHOLDS["cloneLines"]
    rl_cal = lens_cal.red_lines(out_cal["candidates"])
    assert len(rl_cal) == 1
    assert rl_cal[0]["kind"] == "large-fresh-clone"

    lens_def = gld.DuplicationLens()
    out_def = _collect(lens_def, tmp_path, _FakeJscpd(report), prev_digest=None)
    assert lens_def.red_lines(out_def["candidates"]) == []


def test_calibrated_clone_threshold_governs_union_past_top_n(tmp_path, monkeypatch):
    """Calibrated cloneLines must feed apply_cap's red-line union through collect()."""
    dups = []
    measures = {}
    for i in range(gld.TOP_N + 1):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=10, tokens=50 - i))
        measures[(a, b)] = (10, 50 - i)
    (tmp_path / "mid.py").write_text("m\n", encoding="utf-8")
    (tmp_path / "pair.py").write_text("p\n", encoding="utf-8")
    dups.append(_clone_entry("mid.py", "pair.py", lines=40, tokens=1))
    measures[("mid.py", "pair.py")] = (40, 1)
    mid_id = gld._pair_id("mid.py", "pair.py")

    def fake_measure(path_a, path_b):
        key = tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = _report(dups)

    lens_def = gld.DuplicationLens()
    out_def = _collect(lens_def, tmp_path, _FakeJscpd(report), prev_digest=None)
    assert mid_id not in {c["id"] for c in out_def["candidates"]}
    assert out_def["diagnostics"]["redLineUnionAdded"] == 0
    assert lens_def.red_lines(out_def["candidates"]) == []

    lens_cal = gld.DuplicationLens()
    out_cal = _collect(lens_cal, tmp_path, _FakeJscpd(report),
                       config={"thresholds": {"cloneLines": 30}}, prev_digest=None)
    assert mid_id in {c["id"] for c in out_cal["candidates"]}
    assert out_cal["diagnostics"]["redLineUnionAdded"] == 1
    assert any(r["id"] == mid_id for r in lens_cal.red_lines(out_cal["candidates"]))


def test_digest_persists_full_measured_set_not_just_cap(tmp_path, monkeypatch):
    """Digest must hold every measured pair — not only the capped presentation set."""
    n_measured = gld.TOP_N + 5
    dups = []
    measures = {}
    measured_ids = []
    for i in range(n_measured):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=10 + i))
        measures[(a, b)] = (10, 10 + i)
        measured_ids.append(gld._pair_id(a, b))

    def fake_measure(path_a, path_b):
        key = tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    report = _report(dups)
    out1 = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report), prev_digest=None)
    presented = out1["candidates"]
    digest_pairs = out1["digest"]["pairs"]
    presented_ids = {c["id"] for c in presented}

    assert out1["diagnostics"]["candidatesBeforeCap"] == n_measured
    assert len(presented) == gld.TOP_N
    assert len(digest_pairs) == n_measured > len(presented), (
        "digest must persist all %d measured pairs, not only the capped %d: got %d"
        % (n_measured, len(presented), len(digest_pairs))
    )
    for pid in measured_ids:
        assert pid in digest_pairs, "measured pair missing from digest: %s" % pid
    outside_cap = [pid for pid in measured_ids if pid not in presented_ids]
    assert outside_cap
    for pid in outside_cap:
        assert pid in digest_pairs
        assert pid not in out1["digest"]["surfaceIds"]

    boundary = gld._pair_id("a00.py", "b00.py")
    assert boundary in outside_cap
    boundary_prev = dict(digest_pairs[boundary])

    for i in range(n_measured):
        a, b = "a%02d.py" % i, "b%02d.py" % i
        if i == 0:
            measures[(a, b)] = (10, 10)
        else:
            measures[(a, b)] = (10, max(1, (10 + i) // 3))

    out2 = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report),
                    prev_digest=out1["digest"])
    assert boundary in {c["id"] for c in out2["candidates"]}
    assert out2["digest"]["pairs"][boundary]["shared"] == boundary_prev["shared"]
    assert out2["digest"]["pairs"][boundary]["longest"] == boundary_prev["longest"]
    d = gld.LENS.diff(out1["digest"], out2["digest"])
    assert boundary not in d["new"], d


def test_measure_budget_ranks_before_measuring_and_carries_forward(tmp_path, monkeypatch):
    """MAX_PAIRS_MEASURED stops measurement; unmeasured pairs carry prior digest entries."""
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

    low_id = gld._pair_id("p3_a.py", "p3_b.py")
    high_id = gld._pair_id("p0_a.py", "p0_b.py")
    prev = {
        "schemaVersion": 1,
        "pairs": {
            low_id: {"longest": 8, "shared": 8},
            high_id: {"longest": 8, "shared": 8},
        },
    }
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                   prev_digest=prev)
    diag = out["diagnostics"]
    assert diag["pairsConsidered"] == 4
    assert diag["pairsMeasured"] == 2
    assert diag["pairsSkippedBudget"] == 2
    assert diag["budgetExhausted"] == "pairs"
    assert diag["pairsCarriedForward"] >= 1
    assert len(measure_calls) == 2
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
    assert low_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][low_id].get("carriedForward") is True
    assert out["digest"]["pairs"][low_id]["shared"] == 8


def test_unmeasured_without_prior_is_recorded_not_absent(tmp_path, monkeypatch):
    """A pair skipped by budget with no prior entry is persisted as unmeasured."""
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 1)

    dups = []
    for i, tokens in enumerate((200, 50)):
        a, b = "u%d_a.py" % i, "u%d_b.py" % i
        (tmp_path / a).write_text("x\n" * 8, encoding="utf-8")
        (tmp_path / b).write_text("x\n" * 8, encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=tokens))
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                   prev_digest=None)
    assert out["diagnostics"]["pairsMeasured"] == 1
    assert out["diagnostics"]["pairsUnmeasured"] == 1
    assert out["diagnostics"]["budgetExhausted"] == "pairs"
    low_id = gld._pair_id("u1_a.py", "u1_b.py")
    assert low_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][low_id] == {"unmeasured": True}

    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 10)
    out2 = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                    prev_digest=out["digest"])
    d = gld.LENS.diff(out["digest"], out2["digest"])
    assert low_id not in d["new"]
    assert low_id not in d["worsened"]


def test_measure_time_budget_skips_remaining(tmp_path, monkeypatch):
    """MEASURE_TIME_BUDGET_SECONDS must stop measurement (not only the pairs cap)."""
    monkeypatch.setattr(gld, "MEASURE_TIME_BUDGET_SECONDS", 5)
    clock = {"t": 0.0}
    monkeypatch.setattr(gld.time, "monotonic", lambda: clock["t"])

    dups = []
    for i, tokens in enumerate((300, 200, 100)):
        a, b = "t%d_a.py" % i, "t%d_b.py" % i
        (tmp_path / a).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        (tmp_path / b).write_text(("shared_%d\n" % i) * 8, encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=8, tokens=tokens))

    real_measure = gld._measure_pair

    def slow_measure(path_a, path_b):
        clock["t"] += 10
        return real_measure(path_a, path_b)

    monkeypatch.setattr(gld, "_measure_pair", slow_measure)
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                   prev_digest=None)
    assert out["diagnostics"]["budgetExhausted"] == "time"
    assert out["diagnostics"]["pairsMeasured"] == 1
    assert out["diagnostics"]["pairsSkippedBudget"] >= 1
    assert out["diagnostics"]["pairsUnmeasured"] >= 1


def test_must_measure_pair_exempt_from_time_budget(tmp_path, monkeypatch):
    """I2: a pair whose jscpd lines reach the clone threshold is measured even after the
    time budget is exhausted — a red line must not be stranded behind the time cap."""
    monkeypatch.setattr(gld, "MEASURE_TIME_BUDGET_SECONDS", 5)
    clock = {"t": 0.0}
    monkeypatch.setattr(gld.time, "monotonic", lambda: clock["t"])

    measure_calls = []

    def fake_measure(path_a, path_b):
        clock["t"] += 10  # each measure blows the 5s budget for the next pair
        measure_calls.append(tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ])))
        return (10, 10)

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)

    # high-token pair first (measured, blows budget); low-token pair second but its
    # jscpd lines (150) reach the default threshold (100) → mandatory, measured anyway.
    (tmp_path / "hot_a.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "hot_b.py").write_text("y\n", encoding="utf-8")
    (tmp_path / "red_a.py").write_text("r\n", encoding="utf-8")
    (tmp_path / "red_b.py").write_text("s\n", encoding="utf-8")
    dups = [
        _clone_entry("hot_a.py", "hot_b.py", lines=10, tokens=300),
        _clone_entry("red_a.py", "red_b.py", lines=150, tokens=1),
    ]
    red_id = gld._pair_id("red_a.py", "red_b.py")
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                   prev_digest=None)
    assert out["diagnostics"]["budgetExhausted"] == "time"
    assert ("red_a.py", "red_b.py") in measure_calls
    assert ("hot_a.py", "hot_b.py") in measure_calls
    assert red_id in out["digest"]["pairs"]
    assert "longest" in out["digest"]["pairs"][red_id]
    assert not out["digest"]["pairs"][red_id].get("unmeasured")


def test_must_measure_set_is_bounded(monkeypatch):
    """I2: the must-measure set is capped by MAX_MUST_MEASURE so it cannot defeat the time bound."""
    monkeypatch.setattr(gld, "MAX_MUST_MEASURE", 2)
    pair_jscpd = {}
    for i in range(5):
        pid = "duplication:a%d|b%d" % (i, i)
        # All at/above the clone threshold — every one is "must measure" by lines.
        pair_jscpd[pid] = ("a%d" % i, "b%d" % i, 150, 10 + i)
    plan = gld._plan_measurement(pair_jscpd, red_threshold=100)
    assert len(plan["must_measure"]) == 2


def test_oversize_pair_skipped_and_carried(tmp_path, monkeypatch):
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
    report = _report([
        _clone_entry("small_a.py", "small_b.py", lines=8, tokens=10),
        _clone_entry("big_a.py", "big_b.py", lines=8, tokens=10),
    ])
    prev = {"schemaVersion": 1, "pairs": {big_id: {"longest": 8, "shared": 8}}}
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report), prev_digest=prev)
    assert out["diagnostics"]["pairsSkippedOversize"] >= 1
    assert big_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][big_id].get("carriedForward") is True
    assert small_id in out["digest"]["pairs"]
    assert "longest" in out["digest"]["pairs"][small_id]
    assert not out["digest"]["pairs"][small_id].get("unmeasured")
    assert not out["digest"]["pairs"][small_id].get("carriedForward")


def test_measurement_union_past_pairs_budget(tmp_path, monkeypatch):
    """A low-token pair with jscpd lines at the clone threshold must still be measured."""
    monkeypatch.setattr(gld, "MAX_PAIRS_MEASURED", 2)

    dups = []
    measures = {}
    for i in range(4):
        a, b = "m%d_a.py" % i, "m%d_b.py" % i
        (tmp_path / a).write_text("x\n", encoding="utf-8")
        (tmp_path / b).write_text("y\n", encoding="utf-8")
        dups.append(_clone_entry(a, b, lines=10, tokens=400 - i))
        measures[(a, b)] = (10, 10)

    (tmp_path / "big_a.py").write_text("b\n", encoding="utf-8")
    (tmp_path / "big_b.py").write_text("c\n", encoding="utf-8")
    dups.append(_clone_entry("big_a.py", "big_b.py", lines=30, tokens=1))
    measures[("big_a.py", "big_b.py")] = (30, 5)
    big_id = gld._pair_id("big_a.py", "big_b.py")

    def fake_measure(path_a, path_b):
        key = tuple(sorted([
            os.path.relpath(path_a, str(tmp_path)),
            os.path.relpath(path_b, str(tmp_path)),
        ]))
        for (pa, pb), val in measures.items():
            if tuple(sorted([pa, pb])) == key:
                return val
        return None

    monkeypatch.setattr(gld, "_measure_pair", fake_measure)
    out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(_report(dups)),
                   config={"thresholds": {"cloneLines": 30}}, prev_digest=None)
    assert out["diagnostics"]["measurementUnionAdded"] >= 1
    assert big_id in out["digest"]["pairs"]
    assert out["digest"]["pairs"][big_id].get("longest") == 30
    assert not out["digest"]["pairs"][big_id].get("unmeasured")
    assert big_id in {c["id"] for c in out["candidates"]}


# --- side-effect-free -------------------------------------------------------------

def test_collect_writes_nothing_inside_repo(tmp_path):
    (tmp_path / ".git").mkdir()
    shared = ["X_%d" % i for i in range(8)]
    _write_pair(tmp_path, "src/a.py", "src/b.py", shared, shared)
    before = []
    for root, dirs, files in os.walk(tmp_path):
        for name in dirs + files:
            before.append(os.path.relpath(os.path.join(root, name), tmp_path))
    before.sort()

    report = _report([_clone_entry("src/a.py", "src/b.py", lines=8, fmt="python")])
    _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report))

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
    assert gld.LENS.collector_version == "2.1.0"
    assert gld.LENS.collector_version != "1.0.0"
    assert gld.LENS.required_facts == ()
    assert gld.LENS.consequence_template is gld.CONSEQUENCE_TEMPLATE
    assert gld.LENS.validation_guidance is gld.VALIDATION_GUIDANCE


def test_collector_version_bumped_with_digest_shape_change():
    """Shipped collector_version must not stay at 1.0.0 after the digest-shape change."""
    assert gld.DuplicationLens.collector_version != "1.0.0"
    assert gld.DuplicationLens.collector_version == gld.LENS.collector_version
    src_path = gld.__file__
    with open(src_path, encoding="utf-8") as fh:
        src = fh.read()
    assert '"surfaceIds"' in src or "'surfaceIds'" in src
    assert '"unmeasured"' in src or "'unmeasured'" in src
    assert 'collector_version = "2.1.0"' in src


def test_degrade_helper_shape():
    out = gld.LENS.degrade("missing tool")
    assert out == {"lens": "duplication", "degraded": True, "reason": "missing tool"}


# --- Relative cwd forms must agree (symmetry with hotspots) ------------------------

@pytest.mark.parametrize("cwd_form", [".", "./", "ABS", "ABS/"])
def test_collect_cwd_forms_agree(tmp_path, cwd_form):
    """Relative and absolute cwd forms must yield the same candidate set."""
    shared = ["DUP_%d" % i for i in range(12)]
    _write_pair(tmp_path, "src/a.py", "src/b.py",
                ["A_ONLY"] + shared + ["A_END"],
                ["B_ONLY"] + shared + ["B_END"])
    report = _report([
        _clone_entry("src/a.py", "src/b.py", lines=12, fmt="python",
                     start_a=2, end_a=13, start_b=2, end_b=13),
    ])

    abs_repo = os.path.realpath(str(tmp_path))
    baseline = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report), cwd=abs_repo)
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
        out = _collect(gld.DuplicationLens(), tmp_path, _FakeJscpd(report), cwd=cwd_arg)
    finally:
        os.chdir(old)

    assert [c["id"] for c in out["candidates"]] == base_ids
    assert out["diagnostics"]["candidatesBeforeCap"] == (
        baseline["diagnostics"]["candidatesBeforeCap"])
