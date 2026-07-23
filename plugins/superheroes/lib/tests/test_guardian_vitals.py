import json
import os
import subprocess

import pytest

import core_md as cm
import guardian_store as gs
import guardian_vitals as gv
import guardian_lens_duplication as gld
import mode_registry as mr
import store_core as sc
from guardian_fixtures import init_calibrated_repo


# --- local helpers (this module only; guardian_fixtures.py is shared and not edited) ---

def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _plain_repo(tmp_path, files):
    """Git repo containing exactly `files` ({relpath: str|bytes}). Only str/bytes given
    here are tracked, so expected LOC/file/TODO counts are exact and hand-checkable."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel, content in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=guardian@test.local", "-c", "user.name=guardian-test",
         "commit", "-q", "-m", "init")
    return str(repo)


class RecordingRun:
    """subprocess.run stand-in that records every argv/command it is asked to spawn."""

    def __init__(self, stdout="", returncode=0):
        self.calls = []
        self._stdout = stdout
        self._returncode = returncode

    def __call__(self, cmd, **kwargs):
        self.calls.append({"cmd": cmd, "kwargs": kwargs})
        return subprocess.CompletedProcess(cmd, self._returncode, self._stdout, "")


_REAL_RUN = subprocess.run   # captured before any monkeypatching, so watchers can't recurse


def _passthrough_run(cmd, **kwargs):
    return _REAL_RUN(cmd, **kwargs)


# --- 1. VITALS <-> DRIFT_THRESHOLDS consistency (fail-closed, CONVENTIONS §11) ---

def test_every_vital_has_a_threshold():
    missing = [v for v in gv.VITALS if v not in gv.DRIFT_THRESHOLDS]
    assert missing == []


def test_every_threshold_names_a_known_vital():
    extra = [k for k in gv.DRIFT_THRESHOLDS if k not in gv.VITALS]
    assert extra == []


def test_threshold_kinds_are_known_and_limits_present():
    for name, spec in gv.DRIFT_THRESHOLDS.items():
        assert spec["kind"] in gv.THRESHOLD_KINDS, name
        if spec["kind"] in ("relative", "absolute"):
            assert isinstance(spec.get("limit"), (int, float)), name


def test_vitals_is_not_a_lens():
    """§3.7: vitals is a shared component, never a judgment lens."""
    import guardian_lens as gl
    assert not any(getattr(l, "name", None) == "vitals" for l in gl.REGISTRY)
    ok, _reasons = gl.validate_lens(gv)
    assert ok is False


# --- 2. LOC / file / TODO collection against a real temp git repo ---

_TRACKED = {
    "src/a.py": "# TODO: refactor\nprint(1)\nprint(2)\n",              # 3 lines, 1 marker
    "docs/notes.md": "FIXMEs remain here\nPREFIXME is not a marker\nTODO TODO\n",
                                                                       # 3 lines, 3 markers
    "bin/blob.dat": b"\x00\x01\x02\x00binary TODO\n",                  # binary: skipped
    ".gitignore": "ignored.py\n",                                      # 1 line, 0 markers
}


def _repo_with_noise(tmp_path):
    repo = _plain_repo(tmp_path, dict(_TRACKED))
    # untracked + gitignored files carry markers and lines that must NOT be counted
    (tmp_path / "repo" / "untracked.py").write_text("# TODO untracked\nx = 1\n")
    (tmp_path / "repo" / "ignored.py").write_text("# TODO ignored\ny = 2\n")
    return repo


def test_loc_file_todo_exact_counts(tmp_path):
    repo = _repo_with_noise(tmp_path)
    out = gv.collect(repo)
    assert out["vitals"]["fileCount"] == 4          # tracked files only
    assert out["vitals"]["locTotal"] == 7           # 3 + 3 + 1 (binary contributes none)
    assert out["vitals"]["todoCount"] == 4          # occurrences, not files
    for name in ("locTotal", "fileCount", "todoCount"):
        assert name not in out["notCollected"]
        assert out["sources"][name]


def test_todo_source_says_occurrences_not_files(tmp_path):
    repo = _repo_with_noise(tmp_path)
    out = gv.collect(repo)
    assert "occurrence" in out["sources"]["todoCount"]


def test_prefixme_is_not_a_marker():
    assert gv.count_markers("PREFIXME PRETODO") == 0
    assert gv.count_markers("FIXMEs TODO: x") == 2


def test_binary_file_does_not_crash_and_is_reported_skipped(tmp_path):
    repo = _repo_with_noise(tmp_path)
    out = gv.collect(repo)
    assert "binary" in out["sources"]["locTotal"]


def test_not_a_git_repo_is_not_collected(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("x = 1\n")
    out = gv.collect(str(plain))
    for name in ("locTotal", "fileCount", "todoCount"):
        assert out["vitals"][name] is None
        assert out["notCollected"][name]
        assert "git" in out["notCollected"][name]


# --- 3. parse_verify_output ---

def test_parse_verify_output_simple_summary():
    out = gv.parse_verify_output("===== 1703 passed in 62.10s =====")
    assert out["suiteTestCount"] == 1703
    assert out["suiteSkipped"] == 0
    assert out["suiteRuntimeSeconds"] == 62.10


def test_parse_verify_output_with_skips_and_deselects():
    text = "=== 1700 passed, 2 failed, 1 skipped, 5 deselected in 61.00s ==="
    out = gv.parse_verify_output(text)
    assert out["suiteTestCount"] == 1703          # deselected tests never ran
    assert out["suiteSkipped"] == 1
    assert out["suiteRuntimeSeconds"] == 61.0


def test_parse_verify_output_minutes_form():
    out = gv.parse_verify_output("=== 10 passed in 2m 3.50s ===")
    assert out["suiteRuntimeSeconds"] == pytest.approx(123.5)


def test_parse_verify_output_uses_last_summary_line():
    text = "collected 5 items\n1 passed in 0.10s\n=== 4 passed, 1 skipped in 9.00s ===\n"
    out = gv.parse_verify_output(text)
    assert out["suiteTestCount"] == 5
    assert out["suiteSkipped"] == 1
    assert out["suiteRuntimeSeconds"] == 9.0


def test_parse_verify_output_garbage_is_all_none():
    out = gv.parse_verify_output("wharrgarbl no summary here")
    assert out == {"suiteTestCount": None, "suiteSkipped": None,
                   "suiteRuntimeSeconds": None}


def test_parse_verify_output_rejects_non_pytest_error_lookalikes():
    """Coverage gap: '0 errors' / '2 failed' outside a pytest summary must stay None."""
    cases = [
        "typecheck complete: 0 errors in 3.0s",
        "eslint: 2 failed checks in 1.5s",
        "compiler finished with 0 errors",
    ]
    for text in cases:
        out = gv.parse_verify_output(text)
        assert out == {
            "suiteTestCount": None,
            "suiteSkipped": None,
            "suiteRuntimeSeconds": None,
        }, text


def test_parse_verify_output_none_text_is_all_none():
    assert gv.parse_verify_output(None) == {
        "suiteTestCount": None, "suiteSkipped": None, "suiteRuntimeSeconds": None}


# --- 4. not-collected honesty ---

_SUITE = ("suiteRuntimeSeconds", "suiteTestCount", "suiteSkipped")


def _assert_not_collected(out, names, needle=None):
    for name in names:
        assert out["vitals"][name] is None, name
        reason = out["notCollected"].get(name)
        assert isinstance(reason, str) and reason.strip(), name
        if needle:
            assert needle in reason, (name, reason)


def test_no_verify_result_suite_vitals_not_collected(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo)
    _assert_not_collected(out, _SUITE, "not run this sweep")


def test_failed_verify_is_not_collected_with_reason(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, verify_result={
        "status": "failed", "receipt": "pytest -q → exit 1",
        "stdout": "3 passed, 1 failed in 4.00s", "durationSeconds": 4.0})
    _assert_not_collected(out, _SUITE, "failed")


def test_verify_absent_is_not_collected_with_reason(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, verify_result={
        "status": "absent", "receipt": "no verifyCommand in core.md"})
    _assert_not_collected(out, _SUITE)


def test_over_budget_is_not_collected_with_reason(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, budget_seconds=10, verify_result={
        "status": "ok", "receipt": "pytest -q → exit 0",
        "stdout": "5 passed in 30.00s", "durationSeconds": 30.0})
    _assert_not_collected(out, _SUITE, "exceeded time budget")


def test_unparseable_verify_stdout_is_not_collected(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, verify_result={
        "status": "ok", "receipt": "make test → exit 0",
        "stdout": "all good, no numbers here"})
    _assert_not_collected(out, ("suiteTestCount", "suiteSkipped"))


def test_successful_verify_collects_suite_vitals(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, budget_seconds=120, verify_result={
        "status": "ok", "receipt": "pytest -q → exit 0",
        "stdout": "=== 1703 passed, 1 skipped in 62.10s ===",
        "durationSeconds": 63.2})
    # a skipped test is still a test in the suite: 1703 passed + 1 skipped
    assert out["vitals"]["suiteTestCount"] == 1704
    assert out["vitals"]["suiteSkipped"] == 1
    # Pytest summary duration wins when parseable (excludes harness/startup noise).
    assert out["vitals"]["suiteRuntimeSeconds"] == 62.10
    assert "test-summary line" in out["sources"]["suiteRuntimeSeconds"]
    for name in _SUITE:
        assert name not in out["notCollected"]


def test_wall_clock_fallback_when_summary_has_no_duration(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, verify_result={
        "status": "ok", "stdout": "12 passed", "durationSeconds": 7.5})
    assert out["vitals"]["suiteRuntimeSeconds"] == 7.5
    assert "wall clock" in out["sources"]["suiteRuntimeSeconds"]


def test_missing_lens_digest_is_not_collected_with_reason(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results={})
    _assert_not_collected(out, ("duplicationPercent", "majorsBehind", "vulnCount"))
    assert "duplication" in out["notCollected"]["duplicationPercent"]


def test_digest_missing_vital_field_is_not_collected(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})

    class DupLens:
        name = "duplication"

        def vitals(self, digest):
            return gld.LENS.vitals(digest)

    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": DupLens(),
            "status": "collected",
            "digest": {"pairs": {}},
            "reason": None,
            "fresh": True,
        },
    })
    _assert_not_collected(out, ("duplicationPercent",), "duplicationPercent")
    assert out["vitals"]["duplicationPercent"] is None
    assert out["vitals"]["duplicationPercent"] != 0


def test_digest_values_are_read_from_lens_vitals(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})

    class DupLens:
        name = "duplication"

        def vitals(self, digest):
            return {"duplicationPercent": (4.5, None)}

    class DepsLens:
        name = "deps"

        def vitals(self, digest):
            return {"majorsBehind": (7, None), "vulnCount": (2, None)}

    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": DupLens(), "status": "collected", "digest": {},
            "reason": None, "fresh": True,
        },
        "deps": {
            "lens": DepsLens(), "status": "collected", "digest": {},
            "reason": None, "fresh": True,
        },
    })
    assert out["vitals"]["duplicationPercent"] == 4.5
    assert out["vitals"]["majorsBehind"] == 7
    assert out["vitals"]["vulnCount"] == 2
    assert "duplication" in out["sources"]["duplicationPercent"]
    assert out["completeness"]["duplicationPercent"]["state"] == "complete"


def test_non_numeric_vital_tuple_is_not_collected(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})

    class DupLens:
        name = "duplication"

        def vitals(self, digest):
            return {"duplicationPercent": ("lots", None)}

    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": DupLens(), "status": "collected", "digest": {},
            "reason": None, "fresh": True,
        },
    })
    _assert_not_collected(out, ("duplicationPercent",))


def test_not_collected_helper_shape():
    assert gv.not_collected("no dice") == {"status": "not-collected", "reason": "no dice"}


def test_every_vital_is_either_collected_or_explained(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo)
    assert set(out["vitals"]) == set(gv.VITALS)
    for name in gv.VITALS:
        if out["vitals"][name] is None:
            assert out["notCollected"][name].strip()
        else:
            assert name not in out["notCollected"]


# --- 5. no subprocess runs the suite (anti-double-run guard) ---

_READ_ONLY_GIT = ("rev-parse", "ls-files")
_VERIFY_CMD = "run-the-whole-suite --please"


def test_collect_never_spawns_the_verify_command(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    rec = RecordingRun(stdout="")
    gv.collect(repo, run=rec, verify_result={
        "status": "ok", "receipt": "%s → exit 0" % _VERIFY_CMD,
        "stdout": "5 passed in 1.00s", "durationSeconds": 1.0,
        "command": _VERIFY_CMD})
    assert rec.calls, "collect should have gone through the injected runner for git"
    for call in rec.calls:
        cmd = call["cmd"]
        assert isinstance(cmd, list), cmd                     # never a shell string
        assert cmd[0] == "git", cmd
        assert call["kwargs"].get("shell") is not True, cmd
        assert any(sub in cmd for sub in _READ_ONLY_GIT), cmd
        assert _VERIFY_CMD not in " ".join(str(p) for p in cmd), cmd


def test_collect_with_verify_result_spawns_nothing_but_git(tmp_path, monkeypatch):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    seen = []

    def _guard(cmd, **kwargs):
        seen.append(cmd)
        return _passthrough_run(cmd, **kwargs)

    monkeypatch.setattr(gv.subprocess, "run", _guard)
    gv.collect(repo, verify_result={"status": "ok", "stdout": "1 passed in 0.10s"})
    assert seen, "expected the git probes to run through subprocess"
    assert all(isinstance(c, list) and c[0] == "git" for c in seen), seen


# --- 6. threshold crossings ---

def test_relative_crosses_at_boundary_and_not_below():
    at = gv.crossings({"locTotal": 1000}, {"locTotal": 1200})     # +20% == limit
    assert [c["vital"] for c in at] == ["locTotal"]
    below = gv.crossings({"locTotal": 1000}, {"locTotal": 1199})  # +19.9%
    assert below == []


def test_absolute_crosses_at_boundary_and_not_below():
    at = gv.crossings({"duplicationPercent": 3.0}, {"duplicationPercent": 5.0})
    assert [c["vital"] for c in at] == ["duplicationPercent"]
    below = gv.crossings({"duplicationPercent": 3.0}, {"duplicationPercent": 4.9})
    assert below == []


def test_any_increase_crosses_on_one_and_not_on_flat():
    up = gv.crossings({"vulnCount": 0}, {"vulnCount": 1})
    assert [c["vital"] for c in up] == ["vulnCount"]
    flat = gv.crossings({"vulnCount": 3}, {"vulnCount": 3})
    assert flat == []


def test_kind_none_never_crosses():
    assert gv.DRIFT_THRESHOLDS["suiteTestCount"]["kind"] == "none"
    assert gv.crossings({"suiteTestCount": 10}, {"suiteTestCount": 10_000}) == []


def test_improvements_never_cross_but_appear_in_delta():
    prev = {"locTotal": 1000, "vulnCount": 5, "suiteRuntimeSeconds": 100.0}
    cur = {"locTotal": 500, "vulnCount": 0, "suiteRuntimeSeconds": 10.0}
    assert gv.crossings(prev, cur) == []
    d = gv.delta(prev, cur)
    assert d["locTotal"]["change"] == -500
    assert d["vulnCount"]["change"] == -5


def test_first_sweep_is_quiet():
    assert gv.crossings(None, {"locTotal": 10_000, "vulnCount": 9}) == []
    assert gv.crossings({}, {"locTotal": 10_000, "vulnCount": 9}) == []


def test_not_collected_side_never_crosses():
    assert gv.crossings({"locTotal": 100}, {"locTotal": None}) == []
    assert gv.crossings({"locTotal": None}, {"locTotal": 100_000}) == []


def test_zero_base_relative_does_not_raise_and_does_not_cross():
    assert gv.crossings({"locTotal": 0}, {"locTotal": 500}) == []
    assert gv.delta({"locTotal": 0}, {"locTotal": 500})["locTotal"]["pct"] is None


def test_booleans_are_not_numbers():
    assert gv.crossings({"vulnCount": False}, {"vulnCount": True}) == []
    assert gv.delta({"vulnCount": False}, {"vulnCount": True}) == {}


def test_threshold_overrides_are_honored():
    loose = {"vulnCount": {"kind": "absolute", "limit": 10}}
    assert gv.crossings({"vulnCount": 0}, {"vulnCount": 3}, thresholds=loose) == []
    assert gv.crossings({"vulnCount": 0}, {"vulnCount": 3}) != []


def test_invalid_threshold_override_retains_default_and_notes():
    notes = []
    crossings = gv.crossings(
        {"vulnCount": 0}, {"vulnCount": 1},
        thresholds={"vulnCount": {"kind": "absolute", "limit": "two"}},
        notes_out=notes)
    assert crossings, "default any-increase must still fire"
    assert crossings[0]["threshold"] == gv.DRIFT_THRESHOLDS["vulnCount"]
    assert notes and "vulnCount" in notes[0]

    notes2 = []
    crossings2 = gv.crossings(
        {"suiteRuntimeSeconds": 10}, {"suiteRuntimeSeconds": 20},
        thresholds={"suiteRuntimeSeconds": {"kind": "relative", "limit": "40%"}},
        notes_out=notes2)
    assert crossings2, "invalid relative limit must not disable the default 40% crossing"
    assert notes2 and "suiteRuntimeSeconds" in notes2[0]


def test_crossing_entry_fields():
    (c,) = gv.crossings({"suiteRuntimeSeconds": 62.0}, {"suiteRuntimeSeconds": 87.4})
    assert c["vital"] == "suiteRuntimeSeconds"
    assert c["prev"] == 62.0 and c["cur"] == 87.4
    assert c["change"] == pytest.approx(25.4)
    assert c["threshold"] == gv.DRIFT_THRESHOLDS["suiteRuntimeSeconds"]


def test_delta_shape():
    d = gv.delta({"locTotal": 100}, {"locTotal": 125})
    assert d["locTotal"] == {"prev": 100, "cur": 125, "change": 25, "pct": 0.25}


# --- 7. crossing sentences are plain language ---

_JARGON = ("severity", "critical", "violation", "must ", "error-prone", "rule ",
           "warning", "blocker")


def test_sentences_name_both_numbers_and_avoid_jargon():
    cases = [
        ({"suiteRuntimeSeconds": 62.0}, {"suiteRuntimeSeconds": 87.4}, ["62", "87.4"]),
        ({"vulnCount": 0}, {"vulnCount": 2}, ["2"]),
        ({"locTotal": 1000}, {"locTotal": 1300}, ["1000", "1300"]),
        ({"todoCount": 100}, {"todoCount": 200}, ["100", "200"]),
        ({"duplicationPercent": 1.0}, {"duplicationPercent": 6.0}, ["1", "6"]),
        ({"majorsBehind": 1}, {"majorsBehind": 9}, ["1", "9"]),
        ({"fileCount": 100}, {"fileCount": 200}, ["100", "200"]),
        ({"suiteSkipped": 1}, {"suiteSkipped": 4}, ["1", "4"]),
    ]
    for prev, cur, needles in cases:
        (c,) = gv.crossings(prev, cur)
        sentence = c["sentence"]
        assert sentence
        for n in needles:
            assert n in sentence, (c["vital"], sentence)
        low = sentence.lower()
        for word in _JARGON:
            assert word not in low, (c["vital"], sentence)
        assert "since the last sweep" in low


def test_suite_slower_sentence_reads_like_the_design_line():
    (c,) = gv.crossings({"suiteRuntimeSeconds": 62.0}, {"suiteRuntimeSeconds": 87.4})
    assert "slower" in c["sentence"]
    assert "41%" in c["sentence"]


def test_new_vulnerability_sentence_is_singular_at_one():
    (c,) = gv.crossings({"vulnCount": 0}, {"vulnCount": 1})
    assert "1 new vulnerability since the last sweep" in c["sentence"]
    (c2,) = gv.crossings({"vulnCount": 0}, {"vulnCount": 2})
    assert "2 new vulnerabilities since the last sweep" in c2["sentence"]


# --- 8. append-only trend file ---

def _trend_text(repo, root=None):
    with open(gs.vitals_path(repo, root), encoding="utf-8") as fh:
        return fh.read()


def test_two_sweeps_two_records_earlier_bytes_unchanged(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    r1 = gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1", swept_sha="aaa",
                            now="2026-07-21")
    assert r1["ok"] is True
    first = _trend_text(repo)
    r2 = gv.append_unlocked(repo, {"locTotal": 20}, sweep_id="s2", swept_sha="bbb",
                            now="2026-07-22")
    assert r2["ok"] is True
    after = _trend_text(repo)
    assert after.startswith(first)
    recs = gv.read_trend(repo)["records"]
    assert [r["sweepId"] for r in recs] == ["s1", "s2"]
    assert [r["vitals"]["locTotal"] for r in recs] == [10, 20]
    assert [r["date"] for r in recs] == ["2026-07-21", "2026-07-22"]


def test_duplicate_sweep_id_is_skipped(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1", now="2026-07-21")
    before = _trend_text(repo)
    out = gv.append_unlocked(repo, {"locTotal": 99}, sweep_id="s1", now="2026-07-21")
    assert out["ok"] is True
    assert out["skipped"] == "duplicate-sweepId"
    assert _trend_text(repo) == before
    assert len(gv.read_trend(repo)["records"]) == 1


def test_same_sha_two_sweep_ids_makes_two_records(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1", swept_sha="same",
                       now="2026-07-21")
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s2", swept_sha="same",
                       now="2026-07-21")
    recs = gv.read_trend(repo)["records"]
    assert len(recs) == 2
    assert {r["sweptSha"] for r in recs} == {"same"}


def test_torn_trailing_line_is_recovered_reported_and_kept(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1", now="2026-07-21")
    path = gs.vitals_path(repo)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"date": "2026-07-22", "sweepId": "s2", "vita')  # crash mid-append
    torn = _trend_text(repo)
    out = gv.append_unlocked(repo, {"locTotal": 20}, sweep_id="s2", now="2026-07-22")
    assert out["ok"] is True
    assert out["recovered"] == "torn-trailing-line"
    text = _trend_text(repo)
    assert text.startswith(torn), "the damaged line must stay as evidence"
    read = gv.read_trend(repo)
    assert [r["sweepId"] for r in read["records"]] == ["s1", "s2"]
    assert read["malformed"] == 1
    assert len([l for l in text.splitlines() if '"sweepId": "s2"' in l and
                l.rstrip().endswith("}")]) == 1


def test_append_is_never_a_rewrite(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 1}, sweep_id="s1", now="2026-07-21")
    path = gs.vitals_path(repo)
    first_bytes = open(path, "rb").read()
    for i in range(2, 5):
        gv.append_unlocked(repo, {"locTotal": i}, sweep_id="s%d" % i, now="2026-07-21")
    assert open(path, "rb").read().startswith(first_bytes)
    assert len(gv.read_trend(repo)["records"]) == 4


def test_append_records_only_known_vitals(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    out = gv.append_unlocked(repo, {"locTotal": 5, "bogus": 1}, sweep_id="s1",
                             now="2026-07-21")
    assert out["droppedKeys"] == ["bogus"]
    rec = gv.read_trend(repo)["records"][0]
    assert rec["vitals"] == {"locTotal": 5}


def test_append_io_failure_returns_not_ok_instead_of_raising(tmp_path):
    """Real I/O failure (a directory sitting where the file belongs), not a stubbed one."""
    repo = init_calibrated_repo(tmp_path)
    os.makedirs(gs.vitals_path(repo))
    out = gv.append_unlocked(repo, {"locTotal": 1}, sweep_id="s1", now="2026-07-21")
    assert out["ok"] is False
    assert isinstance(out["reason"], str) and out["reason"].strip()


def test_append_takes_the_sweep_lock_and_unlocked_does_not(tmp_path):
    import file_lock
    repo = init_calibrated_repo(tmp_path)
    lock = gs.sweep_lock_path(repo)
    file_lock.acquire(lock, ttl=gs.SWEEP_LOCK_TTL)
    try:
        held = gv.append(repo, {"locTotal": 1}, sweep_id="s1", now="2026-07-21")
        assert held["ok"] is False
        assert held["reason"] == "raced"
        # the unlocked entry point is what finalize calls while holding the lock
        inner = gv.append_unlocked(repo, {"locTotal": 1}, sweep_id="s1",
                                   now="2026-07-21")
        assert inner["ok"] is True
    finally:
        file_lock.release(lock)
    assert os.path.exists(gs.vitals_path(repo))


def test_append_releases_the_lock(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    assert gv.append(repo, {"locTotal": 1}, sweep_id="s1", now="2026-07-21")["ok"]
    assert gv.append(repo, {"locTotal": 2}, sweep_id="s2", now="2026-07-21")["ok"]
    assert not os.path.exists(gs.sweep_lock_path(repo))


_MUTATING_GIT = ("add", "commit", "push", "tag", "checkout", "reset", "rm", "mv")


def test_append_never_commits_or_mutates_the_repo(tmp_path, monkeypatch):
    """The appender may resolve its path (which reads git), but never writes through git."""
    repo = init_calibrated_repo(tmp_path)
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    seen = []

    def _watch(cmd, **kwargs):
        seen.append(cmd)
        return _passthrough_run(cmd, **kwargs)

    monkeypatch.setattr(gv.subprocess, "run", _watch)
    assert gv.append_unlocked(repo, {"locTotal": 1}, sweep_id="s1",
                              now="2026-07-21")["ok"] is True
    for cmd in seen:
        parts = [str(p) for p in (cmd if isinstance(cmd, list) else [cmd])]
        assert not (set(parts) & set(_MUTATING_GIT)), parts
    after = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                           capture_output=True, text=True).stdout.strip()
    assert after == head


# --- 8b. provenance line (CONVENTIONS §2.2, JSONL-compatible reading) ---

def test_fresh_file_starts_with_json_provenance(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 1}, sweep_id="s1", now="2026-07-21")
    first = _trend_text(repo).splitlines()[0]
    prov = json.loads(first)
    assert prov["schemaVersion"] == gv.TREND_SCHEMA_VERSION
    assert prov["file"] == gv.TREND_FILE_ID
    assert prov["created"] == "2026-07-21"


def test_provenance_written_exactly_once(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    for i in range(1, 4):
        gv.append_unlocked(repo, {"locTotal": i}, sweep_id="s%d" % i, now="2026-07-21")
    text = _trend_text(repo)
    assert text.count('"%s"' % gv.TREND_FILE_ID) == 1
    read = gv.read_trend(repo)
    assert len(read["records"]) == 3
    assert read["provenance"]["file"] == gv.TREND_FILE_ID
    assert all("sweepId" in r for r in read["records"])


def test_read_trend_absent(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    out = gv.read_trend(repo)
    assert out["status"] == "absent"
    assert out["records"] == []
    assert out["provenance"] is None


def test_read_trend_requires_first_line_provenance(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.vitals_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(
        json.dumps({"date": "2026-07-21", "sweepId": "s1", "vitals": {}}) + "\n")
    out = gv.read_trend(repo)
    assert out["status"] == "malformed"
    assert out["records"] == []


def test_read_trend_newer_provenance_is_opaque(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.vitals_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(
        json.dumps({"schemaVersion": 99, "file": "guardian-vitals",
                    "created": "2026-07-21"}) + "\n"
        + json.dumps({"date": "2026-07-21", "sweepId": "s1", "vitals": {"locTotal": 1}})
        + "\n")
    out = gv.read_trend(repo)
    assert out["status"] == "newer"
    assert out["records"] == []
    assert out["provenance"] is None


def test_read_trend_malformed_provenance_schema_version(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.vitals_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(
        json.dumps({"schemaVersion": "1", "file": "guardian-vitals",
                    "created": "2026-07-21"}) + "\n")
    out = gv.read_trend(repo)
    assert out["status"] == "malformed"
    assert out["records"] == []


def test_append_unlocked_refuses_newer_trend_schema(tmp_path):
    """Rollback must not append v1 records into a future-schema trend."""
    repo = init_calibrated_repo(tmp_path)
    path = gs.vitals_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    before = (
        json.dumps({"schemaVersion": 99, "file": "guardian-vitals",
                    "created": "2026-07-21"}) + "\n"
        + json.dumps({"date": "2026-07-21", "sweepId": "old", "vitals": {"locTotal": 1}})
        + "\n"
    )
    open(path, "w", encoding="utf-8").write(before)
    out = gv.append_unlocked(repo, {"locTotal": 2}, sweep_id="s2", now="2026-07-22")
    assert out["ok"] is False
    assert out.get("status") == "newer" or "newer" in out.get("reason", "")
    assert open(path, encoding="utf-8").read() == before


def test_append_unlocked_refuses_missing_provenance(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    path = gs.vitals_path(repo)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    before = json.dumps({"date": "2026-07-21", "sweepId": "s1",
                         "vitals": {"locTotal": 1}}) + "\n"
    open(path, "w", encoding="utf-8").write(before)
    out = gv.append_unlocked(repo, {"locTotal": 2}, sweep_id="s2", now="2026-07-22")
    assert out["ok"] is False
    assert open(path, encoding="utf-8").read() == before


def test_read_trend_limit_tails(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    for i in range(1, 6):
        gv.append_unlocked(repo, {"locTotal": i}, sweep_id="s%d" % i, now="2026-07-21")
    tail = gv.read_trend(repo, limit=2)["records"]
    assert [r["sweepId"] for r in tail] == ["s4", "s5"]


# --- 9. real-seam test (CONVENTIONS §12.2): real file, real reader, real argv ---

def test_real_seam_append_then_read_through_cli(tmp_path, capsys):
    repo = init_calibrated_repo(tmp_path)
    assert gv.append(repo, {"locTotal": 42, "vulnCount": 0}, sweep_id="sweep-1",
                     swept_sha="deadbeef", now="2026-07-21")["ok"] is True
    assert gv.main(["read", "--cwd", repo]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert out["records"][0]["sweepId"] == "sweep-1"
    assert out["records"][0]["vitals"]["locTotal"] == 42
    assert out["records"][0]["sweptSha"] == "deadbeef"


def test_real_seam_collect_cli_on_a_real_repo(tmp_path, capsys):
    repo = _plain_repo(tmp_path, {"a.py": "# TODO one\nx = 1\n"})
    assert gv.main(["collect", "--cwd", repo]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["vitals"]["fileCount"] == 1
    assert out["vitals"]["locTotal"] == 2
    assert out["vitals"]["todoCount"] == 1
    assert out["notCollected"]["vulnCount"]


def test_cli_subprocess_round_trip(tmp_path):
    """Real argv through a real python process — no in-process import shortcuts."""
    repo = init_calibrated_repo(tmp_path)
    gv.append(repo, {"locTotal": 7}, sweep_id="s1", now="2026-07-21")
    mod = os.path.abspath(gv.__file__)
    r = subprocess.run(["python3", mod, "read", "--cwd", repo],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["records"][0]["vitals"]["locTotal"] == 7


# --- 10. both storage modes ---

def test_trend_round_trip_in_repo_mode(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    assert gv.append(repo, {"locTotal": 3}, sweep_id="s1", now="2026-07-21")["ok"]
    path = gs.vitals_path(repo)
    assert path == os.path.join(repo, ".claude", "superheroes", "guardian",
                                gs.LAYOUT["vitals"])
    assert os.path.isfile(path)
    assert gv.read_trend(repo)["records"][0]["vitals"]["locTotal"] == 3


def test_trend_round_trip_global_mode(tmp_path):
    repo = init_calibrated_repo(tmp_path, remote="git@github.com:o/r.git")
    root = str(tmp_path / "store")
    store = mr.ensure_project_store(repo, root=root)
    cfg = os.path.join(store, "config")
    os.makedirs(cfg, exist_ok=True)
    sc.atomic_write(os.path.join(cfg, "core.md"), cm.render_core(
        {"verifyCommand": "true", "stackTags": [], "threatModel": "t", "patterns": ""},
        "confirmed", "2026-01-01", "2026-01-01"))
    mr.write_registry(repo, mr.GLOBAL, "rk", root=root, now="2026-06-21T00:00:00Z")

    path = gs.vitals_path(repo, root=root)
    assert path == os.path.join(cfg, "guardian", gs.LAYOUT["vitals"])
    assert gv.append(repo, {"locTotal": 5}, sweep_id="s1", root=root,
                     now="2026-07-21")["ok"] is True
    assert os.path.isfile(path)
    assert gv.read_trend(repo, root=root)["records"][0]["vitals"]["locTotal"] == 5
    # global mode leaves no trace in the repo
    assert not os.path.exists(os.path.join(repo, ".claude", "superheroes", "guardian"))

def test_incomplete_scan_marks_loc_and_todo_not_collected(tmp_path, monkeypatch):
    """Oversize / unreadable tracked files must not publish a partial locTotal."""
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n", "big.py": "y = 2\n"})
    monkeypatch.setattr(gv, "_MAX_FILE_BYTES", 1)
    out = gv.collect(repo)
    assert out["vitals"]["fileCount"] == 2
    assert out["vitals"]["locTotal"] is None
    assert out["vitals"]["todoCount"] is None
    assert "incomplete" in out["notCollected"]["locTotal"]
    assert "incomplete" in out["notCollected"]["todoCount"]


# --- 11. lens vitals completeness + stale-digest guards ---

def _dup_lens_result(digest, status="collected", fresh=True):
    return {
        "duplication": {
            "lens": gld.LENS,
            "status": status,
            "digest": digest,
            "reason": None if status == "collected" else "partial reason",
            "fresh": fresh,
        },
    }


def test_stale_carried_forward_lens_result_is_not_collected(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": gld.LENS,
            "status": "collected",
            "digest": {"duplicationPercent": 99.0},
            "reason": None,
            "fresh": False,
        },
    })
    _assert_not_collected(out, ("duplicationPercent",))
    assert "did not run" in out["notCollected"]["duplicationPercent"]


def test_partial_lens_status_publishes_usable_digest_as_partial(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_result(
        {"duplicationPercent": 3.0}, status="partial"))
    assert out["vitals"]["duplicationPercent"] == 3.0
    assert out["completeness"]["duplicationPercent"]["state"] == "partial"
    assert out["completeness"]["duplicationPercent"]["reason"] == "partial reason"
    assert "duplicationPercent" not in out["notCollected"]


def test_partial_deps_lens_python_vulns_publishes_count_with_derived_gap(tmp_path):
    import guardian_lens_deps as deps_mod
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    vuln_id = "deps:audit:python:foo:PYSEC-2020-1"
    section_reason = "some advisories unrated"
    digest = {
        "ecosystems": {
            "python": {
                "vulns": {
                    "status": "partial",
                    "items": {vuln_id: {"id": vuln_id}},
                    "reason": section_reason,
                },
            },
        },
    }
    out = gv.collect(repo, lens_results={
        "deps": {
            "lens": deps_mod.LENS,
            "status": "partial",
            "digest": digest,
            "reason": "python ecosystem partially collected",
            "fresh": True,
        },
    })
    assert out["vitals"]["vulnCount"] == 1
    assert out["completeness"]["vulnCount"]["state"] == "partial"
    assert section_reason in out["completeness"]["vulnCount"]["reason"]
    assert "python vulns:" in out["completeness"]["vulnCount"]["reason"]
    assert "pip-audit" not in out["completeness"]["vulnCount"]["reason"]
    assert "#569" not in out["completeness"]["vulnCount"]["reason"]
    assert "vulnCount" not in out["notCollected"]


def test_partial_lens_never_launders_complete_reading(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": type("L", (), {
                "name": "duplication",
                "vitals": staticmethod(lambda digest: {
                    "duplicationPercent": (3.0, None),
                }),
            })(),
            "status": "partial",
            "digest": {},
            "reason": "lens collection was partial this sweep",
            "fresh": True,
        },
    })
    assert out["vitals"]["duplicationPercent"] == 3.0
    assert out["completeness"]["duplicationPercent"]["state"] == "partial"
    assert out["completeness"]["duplicationPercent"]["reason"] == (
        "lens collection was partial this sweep")


def test_unknown_vital_from_lens_is_rejected(tmp_path, capsys):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})

    class BadLens:
        name = "duplication"

        def vitals(self, digest):
            return {"bogusVital": (1, None), "duplicationPercent": (2.0, None)}

    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": BadLens(), "status": "collected", "digest": {},
            "reason": None, "fresh": True,
        },
    })
    assert out["vitals"]["duplicationPercent"] == 2.0
    assert "bogusVital" not in out["vitals"]
    assert "unknown vital" in capsys.readouterr().err


def test_extractor_raise_does_not_break_collect(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})

    class BoomLens:
        name = "duplication"

        def vitals(self, digest):
            raise RuntimeError("boom")

    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": BoomLens(), "status": "collected", "digest": {},
            "reason": None, "fresh": True,
        },
    })
    _assert_not_collected(out, ("duplicationPercent",))
    assert "raised" in out["notCollected"]["duplicationPercent"]


def test_broken_digest_key_mutation_probe_duplication(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_result({"pairs": {}}))
    _assert_not_collected(out, ("duplicationPercent",))
    assert out["vitals"]["duplicationPercent"] is None
    assert out["vitals"]["duplicationPercent"] != 0
    prev = {"duplicationPercent": 0}
    cur = {"duplicationPercent": out["vitals"]["duplicationPercent"]}
    assert "duplicationPercent" not in gv.delta(prev, cur)
    assert gv.crossings(prev, cur) == []


def test_broken_digest_key_mutation_probe_deps_majors(tmp_path):
    import guardian_lens_deps as deps_mod
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    digest = {
        "ecosystems": {
            "node": {
                "freshness": {
                    "status": "collected",
                    "majorsBehindTotal": 3,
                    "items": {},
                },
            },
        },
    }
    broken = {"ecosystems": {"node": {"freshness": {"status": "collected"}}}}
    out = gv.collect(repo, lens_results={
        "deps": {
            "lens": deps_mod.LENS,
            "status": "collected",
            "digest": broken,
            "reason": None,
            "fresh": True,
        },
    })
    _assert_not_collected(out, ("majorsBehind",))
    assert out["vitals"]["majorsBehind"] is None
    prev = {"majorsBehind": 1}
    cur = {"majorsBehind": out["vitals"]["majorsBehind"]}
    assert "majorsBehind" not in gv.delta(prev, cur)
    assert gv.crossings(prev, cur) == []


def test_partial_vital_publishes_number_and_tags_completeness(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    gap = "python gap for #569"
    out = gv.collect(repo, lens_results={
        "deps": {
            "lens": type("L", (), {
                "name": "deps",
                "vitals": staticmethod(lambda digest: {
                    "vulnCount": (4, gap),
                }),
            })(),
            "status": "collected",
            "digest": {},
            "reason": None,
            "fresh": True,
        },
    })
    assert out["vitals"]["vulnCount"] == 4
    assert out["completeness"]["vulnCount"]["state"] == "partial"
    assert out["completeness"]["vulnCount"]["reason"] == gap


def _dup_lens_with_vitals(reading):
    return {
        "duplication": {
            "lens": type("L", (), {
                "name": "duplication",
                "vitals": staticmethod(lambda digest: {
                    "duplicationPercent": reading,
                }),
            })(),
            "status": "collected",
            "digest": {},
            "reason": None,
            "fresh": True,
        },
    }


def test_partial_reading_with_empty_reason_fails_closed(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, "")))
    assert out["vitals"]["duplicationPercent"] is None
    assert out["completeness"]["duplicationPercent"]["state"] == "not-collected"
    reason = out["completeness"]["duplicationPercent"]["reason"]
    assert "contract violation" in reason
    assert "duplication" in reason
    assert "duplicationPercent" in reason
    assert out["notCollected"]["duplicationPercent"] == reason


def test_partial_reading_with_whitespace_reason_fails_closed(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, "   ")))
    assert out["vitals"]["duplicationPercent"] is None
    assert out["completeness"]["duplicationPercent"]["state"] == "not-collected"
    assert "contract violation" in out["completeness"]["duplicationPercent"]["reason"]


def test_partial_reading_with_non_string_reason_fails_closed(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, 123)))
    assert out["vitals"]["duplicationPercent"] is None
    assert out["completeness"]["duplicationPercent"]["state"] == "not-collected"
    assert "contract violation" in out["completeness"]["duplicationPercent"]["reason"]


def test_partial_reading_with_real_gap_still_publishes(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    gap = "a real gap"
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, gap)))
    assert out["vitals"]["duplicationPercent"] == 3.0
    assert out["completeness"]["duplicationPercent"]["state"] == "partial"
    assert out["completeness"]["duplicationPercent"]["reason"] == gap


def test_complete_reading_with_none_reason_unchanged(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, None)))
    assert out["vitals"]["duplicationPercent"] == 3.0
    assert out["completeness"]["duplicationPercent"]["state"] == "complete"


def test_not_collected_reading_with_reason_unchanged(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results=_dup_lens_with_vitals((None, "reason")))
    assert out["vitals"]["duplicationPercent"] is None
    assert out["completeness"]["duplicationPercent"]["state"] == "not-collected"
    assert out["completeness"]["duplicationPercent"]["reason"] == "reason"


def test_contract_violating_partial_readings_do_not_cross(tmp_path):
    """Two invalid partial tuples must not compare as equal partials and cross."""
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out1 = gv.collect(repo, lens_results=_dup_lens_with_vitals((3.0, "")))
    out2 = gv.collect(repo, lens_results=_dup_lens_with_vitals((5.0, "   ")))
    comp1 = out1["completeness"]["duplicationPercent"]
    comp2 = out2["completeness"]["duplicationPercent"]
    assert comp1["state"] == "not-collected"
    assert comp2["state"] == "not-collected"
    assert not gv._comparable_completeness(comp1, comp2)
    assert gv.crossings(
        {"duplicationPercent": 3.0},
        {"duplicationPercent": 5.0},
        prev_completeness={"duplicationPercent": comp1},
        cur_completeness={"duplicationPercent": comp2},
    ) == []


def test_partial_crossing_requires_matching_gap_reason():
    gap = "python ratings unavailable until issue #569"
    comp = {"state": "partial", "reason": gap}
    prev = {"vulnCount": 2}
    cur = {"vulnCount": 5}
    assert gv.crossings(prev, cur,
                        prev_completeness={"vulnCount": comp},
                        cur_completeness={"vulnCount": comp})
    different = {"state": "partial", "reason": "other gap"}
    assert gv.crossings(prev, cur,
                        prev_completeness={"vulnCount": comp},
                        cur_completeness={"vulnCount": different}) == []
    assert gv.delta(prev, cur,
                    prev_completeness={"vulnCount": comp},
                    cur_completeness={"vulnCount": different})["_notComparable"]["vulnCount"]


def _deps_partial_lens_result(digest, lens_reason):
    import guardian_lens_deps as deps_mod
    return {
        "deps": {
            "lens": deps_mod.LENS,
            "status": "partial",
            "digest": digest,
            "reason": lens_reason,
            "fresh": True,
        },
    }


def _python_partial_vuln_digest(vuln_count, *, vuln_reason, freshness_reason):
    items = {
        "deps:audit:python:foo:PYSEC-%d" % i: {"id": "deps:audit:python:foo:PYSEC-%d" % i}
        for i in range(vuln_count)
    }
    return {
        "ecosystems": {
            "python": {
                "vulns": {
                    "status": "partial",
                    "items": items,
                    "reason": vuln_reason,
                },
                "freshness": {
                    "status": "partial",
                    "reason": freshness_reason,
                    "items": {},
                },
            },
        },
    }


def test_unrelated_partial_part_reason_change_does_not_suppress_crossing(tmp_path):
    """vulnCount 2→5 with only an unrelated freshness gap reworded must still cross."""
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    vuln_reason = "severity source offline this sweep"
    freshness_a = "policy gap A"
    freshness_b = "policy gap B"
    lens_reason_s1 = "python vulns: %s; python freshness: %s" % (vuln_reason, freshness_a)
    lens_reason_s2 = "python vulns: %s; python freshness: %s" % (vuln_reason, freshness_b)

    out1 = gv.collect(repo, lens_results=_deps_partial_lens_result(
        _python_partial_vuln_digest(2, vuln_reason=vuln_reason, freshness_reason=freshness_a),
        lens_reason_s1))
    out2 = gv.collect(repo, lens_results=_deps_partial_lens_result(
        _python_partial_vuln_digest(5, vuln_reason=vuln_reason, freshness_reason=freshness_b),
        lens_reason_s2))

    assert out1["vitals"]["vulnCount"] == 2
    assert out2["vitals"]["vulnCount"] == 5
    comp1 = out1["completeness"]["vulnCount"]
    comp2 = out2["completeness"]["vulnCount"]
    assert comp1["state"] == "partial"
    assert comp2["state"] == "partial"
    vital_gap = "python vulns: %s" % vuln_reason
    assert comp1["reason"] == vital_gap
    assert comp2["reason"] == vital_gap
    assert comp1["reason"] == comp2["reason"]
    assert comp1["reason"].count("python vulns:") == 1
    assert freshness_a not in comp1["reason"]
    assert freshness_b not in comp2["reason"]
    assert lens_reason_s1 not in comp1["reason"]
    assert lens_reason_s2 not in comp2["reason"]

    crossings = gv.crossings(
        {"vulnCount": out1["vitals"]["vulnCount"]},
        {"vulnCount": out2["vitals"]["vulnCount"]},
        prev_completeness={"vulnCount": comp1},
        cur_completeness={"vulnCount": comp2},
    )
    assert [c["vital"] for c in crossings] == ["vulnCount"]


def test_vital_own_gap_reason_change_still_fences_crossing(tmp_path):
    """A change in the vital's own gap reason must keep sweeps non-comparable."""
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    gap_a = "severity source offline this sweep"
    gap_b = "ratings unavailable this sweep"
    out1 = gv.collect(repo, lens_results=_deps_partial_lens_result(
        _python_partial_vuln_digest(2, vuln_reason=gap_a, freshness_reason="policy gap"),
        "python vulns: %s; python freshness: policy gap" % gap_a))
    out2 = gv.collect(repo, lens_results=_deps_partial_lens_result(
        _python_partial_vuln_digest(5, vuln_reason=gap_b, freshness_reason="policy gap"),
        "python vulns: %s; python freshness: policy gap" % gap_b))

    comp1 = out1["completeness"]["vulnCount"]
    comp2 = out2["completeness"]["vulnCount"]
    assert comp1["reason"] != comp2["reason"]
    assert gv.crossings(
        {"vulnCount": out1["vitals"]["vulnCount"]},
        {"vulnCount": out2["vitals"]["vulnCount"]},
        prev_completeness={"vulnCount": comp1},
        cur_completeness={"vulnCount": comp2},
    ) == []


def test_completeness_persisted_in_trend_record(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    completeness = {"locTotal": {"state": "complete"}}
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1",
                       completeness=completeness, now="2026-07-21")
    rec = gv.read_trend(repo)["records"][0]
    assert rec["completeness"]["locTotal"]["state"] == "complete"


def test_not_collected_lens_result_uses_real_reason_not_did_not_run(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    fail_reason = "jscpd timed out after 120s"
    out = gv.collect(repo, lens_results={
        "duplication": {
            "lens": gld.LENS,
            "status": "not-collected",
            "digest": None,
            "reason": fail_reason,
            "fresh": True,
        },
    })
    _assert_not_collected(out, ("duplicationPercent",))
    assert fail_reason in out["notCollected"]["duplicationPercent"]
    assert "did not run" not in out["notCollected"]["duplicationPercent"]
    assert out["completeness"]["duplicationPercent"]["reason"] == fail_reason


def test_absent_lens_result_still_reads_did_not_run(tmp_path):
    repo = _plain_repo(tmp_path, {"a.py": "x = 1\n"})
    out = gv.collect(repo, lens_results={})
    assert "did not run" in out["notCollected"]["duplicationPercent"]


def test_completeness_for_sweep_joins_on_sweep_id(tmp_path):
    repo = init_calibrated_repo(tmp_path)
    gv.append_unlocked(repo, {"locTotal": 10}, sweep_id="s1",
                       completeness={"locTotal": {"state": "complete"}},
                       now="2026-07-21")
    gv.append_unlocked(repo, {"locTotal": 20}, sweep_id="s2",
                       completeness={"locTotal": {"state": "partial",
                                                   "reason": "newer sweep"}},
                       now="2026-07-22")
    assert gv.completeness_for_sweep(repo, "s1") == {
        "locTotal": {"state": "complete"}}
    assert gv.completeness_for_sweep(repo, "s2")["locTotal"]["state"] == "partial"
    assert gv.completeness_for_sweep(repo, "missing") == {}


def test_trend_ahead_of_snapshot_suppresses_false_crossing(tmp_path):
    """Trend advanced past snapshot → unknown prev completeness → no crossing."""
    prev_comp = {"vulnCount": {"state": "complete"}}
    newer_comp = {"vulnCount": {"state": "partial", "reason": "from newer sweep"}}
    prev = {"vulnCount": 2}
    cur = {"vulnCount": 5}
    # Wrong join (newer completeness) would allow crossing complete→partial mismatch
    # to be suppressed differently; with empty prev completeness, delta is not comparable.
    assert gv.crossings(prev, cur, prev_completeness={},
                        cur_completeness=newer_comp) == []
    assert gv.crossings(prev, cur, prev_completeness=prev_comp,
                        cur_completeness=newer_comp) == []
    assert "vulnCount" in gv.delta(prev, cur, prev_completeness={},
                                   cur_completeness=newer_comp).get(
                                       "_notComparable", {})
