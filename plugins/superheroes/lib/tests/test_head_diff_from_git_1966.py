#!/usr/bin/env python3
"""#1966 — the apply-fixes fold derives the post-fix diff from git and refuses a mismatched supplied one."""
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from session_checkout import seed_session_meta  # noqa: E402

from test_round_driver import (  # noqa: E402
    RD, DIFF, HEAD, _CONSEQUENCE, _cfg, _drive_to_phase, _newsurf, _responder, _run_loop_capturing_state,
    _seams,
)


def _pin_git_env(monkeypatch):
    """The driver's own git calls read the process environment; keep them off the global config."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        ["git", "-c", "user.email=t@t.local", "-c", "user.name=t", "-C", repo, *args],
        check=True, capture_output=True, env=env).stdout.decode("utf-8")


def _rev_parse(repo):
    return _git(repo, "rev-parse", "HEAD").strip()


def _git_diff(repo, base):
    return _git(repo, "diff", "%s...HEAD" % base)


def _commit_file(repo, path, body, message="fix"):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full) or repo, exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(body.encode("utf-8"))
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)


def _init_repo(tmp_path):
    """Base commit, then the round-1 head commit changing f.py. Returns (repo, base_sha, round1_diff)."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    _commit_file(repo, "f.py", "old\n", "base")
    base_sha = _rev_parse(repo)
    _commit_file(repo, "f.py", "new\n", "head")
    return repo, base_sha, _git_diff(repo, base_sha)


_A_SECTION = ("diff --git a/a.py b/a.py\nnew file mode 100644\nindex 0..1\n--- /dev/null\n+++ b/a.py\n"
              "@@ -0,0 +1,4 @@\n+a1\n+a2\n+a3\n+a4\n")
_ROUND1 = _A_SECTION + DIFF
_FULL = _A_SECTION + HEAD + _newsurf()
_FIX_ONLY = HEAD + _newsurf()
_FINDING_F = [{"title": "bug", "severity": "Important", "consequence": _CONSEQUENCE,
               "file": "f.py", "line": 1}]
_FINDINGS_A = [
    {"title": "a-two", "severity": "Important", "consequence": _CONSEQUENCE, "file": "a.py", "line": 2},
    {"title": "a-three", "severity": "Important", "consequence": _CONSEQUENCE, "file": "a.py", "line": 3},
]


def _loop(supplied, scoped_findings=None, seam=None):
    """A run_loop over a scripted fix step supplying `supplied` (None = nothing) and a git answer."""
    fired = {"scoped": False}

    def reviewer(dim, tier, rnd, ctx):
        if dim == "code-reviewer" and rnd == 1:
            return list(_FINDING_F)
        if dim == "scoped-finder" and scoped_findings and not fired["scoped"]:
            fired["scoped"] = True
            return list(scoped_findings)
        return []

    def fix_step(batch, rnd, payload):
        art = {"fixes": [], "changedSubjects": ["Code"]}
        if supplied is not None:
            art["headDiff"] = supplied
        return art

    seams = _seams(reviewer=reviewer, fix_step=fix_step, vendors=["claude", "codex"])
    seams["panel_diff"] = seam or (lambda config, head: (_FULL, None))
    return _run_loop_capturing_state(seams, _cfg(diff=_ROUND1))


def test_t1_supplied_full_diff_matches_and_fix_only_diff_is_refused():
    _result_a, state_a = _loop(_FULL)
    rec_a = state_a["rounds"]["1"]
    assert rec_a["headDiffSource"] == "git"
    assert rec_a["headDiffCheck"] == "match"
    assert state_a["reviewedDiff"] == _FULL
    assert "a.py" in state_a["reviewedDiff"]
    assert state_a["round"] >= 2

    _result_b, state_b = _loop(_FIX_ONLY)
    rec_b = state_b["rounds"]["1"]
    assert rec_b["headDiffSource"] == "git"
    assert rec_b["headDiffCheck"] == "mismatch"
    assert state_b["terminal"] == "cannot-certify"
    reason = state_b["certification"]["reason"]
    assert reason.startswith("head-diff-mismatch")
    only_in_git = reason.split("only-in-git=")[1].split(" only-in-supplied=")[0]
    assert "a.py" in only_in_git
    assert state_b["headDiff"] is None
    assert state_b["reviewedDiff"] != _FIX_ONLY
    assert state_b["round"] == 1
    assert "2" not in state_b["rounds"]


def _kept_in_round_three(state):
    """The finding ids the round after the fix handed to its fix audits."""
    return state["rounds"]["3"]["focus"]["fixes"]


def _all_scope_drops(state):
    return [d for rec in state["rounds"].values() for d in (rec.get("compileDrops") or [])
            if "outside the round diff scope" in str(d.get("reason"))]


def test_t3_findings_on_untouched_lines_are_not_dropped_by_a_fix_only_diff():
    # The fixture bites: a fix-only reviewed diff drops exactly these findings; the full one keeps them.
    _kept, dropped = RD.mechanical_compile(list(_FINDINGS_A), _FIX_ONLY)
    assert [d["reason"] for d in dropped] == ["outside the round diff scope"] * 2
    kept, dropped = RD.mechanical_compile(list(_FINDINGS_A), _FULL)
    assert len(kept) == 2 and not dropped

    # B: the fix-only diff is refused before any later compile can run.
    _r, state_b = _loop(_FIX_ONLY, _FINDINGS_A)
    assert state_b["terminal"] == "cannot-certify"
    assert state_b["certification"]["reason"].startswith("head-diff-mismatch")
    assert "2" not in state_b["rounds"]
    assert _all_scope_drops(state_b) == []

    # B': nothing supplied, git derives the full diff; A: the full diff supplied. Same outcome.
    for supplied in (None, _FULL):
        _r, state = _loop(supplied, _FINDINGS_A)
        assert state["terminal"] == "converged"
        assert _all_scope_drops(state) == []
        assert state["rounds"]["2"].get("compileDrops") in (None, [])
        assert sorted(_kept_in_round_three(state)) == ["a.py::athree@L3", "a.py::atwo@L2"]


# ---- CLI path over a real repository -----------------------------------------------------------

_TWO_LINE_FINDINGS = [
    {"title": "one", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 1},
    {"title": "two", "severity": "Important", "consequence": _CONSEQUENCE, "file": "f.py", "line": 2},
]


def _init_two_line_repo(tmp_path):
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", "main")
    _commit_file(repo, "f.py", "old1\nold2\n", "base")
    base_sha = _rev_parse(repo)
    _commit_file(repo, "f.py", "new1\nnew2\n", "head")
    return repo, base_sha, _git_diff(repo, base_sha)


class _Cli:
    """A CLI-path session over a real two-commit repository, driven to the first apply-fixes step."""

    def __init__(self, tmp_path, monkeypatch, findings=None, **cfg_over):
        _pin_git_env(monkeypatch)
        self.findings = findings or _FINDING_F
        init = _init_two_line_repo if findings else _init_repo
        self.repo, self.base, round1 = init(tmp_path)
        self.d = str(tmp_path / "session")
        seed_session_meta(self.d, self.repo)
        self.cfg = _cfg(verifyCommand="pytest -q", diff=round1, repoRoot=self.repo,
                        baseRef=self.base, **cfg_over)
        self.fix_calls = 0
        self.fixer_body = "fixed head\n"
        self.supply = lambda cli: {}

    def respond(self, phase, payload, rnd):
        if phase == RD.P_APPLY_FIXES and rnd == 1:
            self.fix_calls += 1
            body = self.fixer_body if self.fix_calls == 1 else "%sslice %d\n" % (
                self.fixer_body, self.fix_calls)
            _commit_file(self.repo, "f.py", body, "fixer commit %d" % self.fix_calls)
            art = {"fixes": [{"file": "f.py"}], "changedSubjects": ["Code"]}
            art.update(self.supply(self))
            return art
        return _responder(round1_findings=self.findings)(phase, payload, rnd)

    def to_fixer(self):
        return _drive_to_phase(self.d, self.cfg, self.respond, RD.P_APPLY_FIXES)

    def submit(self, n):
        return RD.cmd_submit(self.d, n["phase"], n["attempt"], n["expectedStateHash"],
                             self.respond(n["phase"], n["payload"], n["round"]))

    def fold_fixer(self):
        n = self.to_fixer()
        out = self.submit(n)
        assert out["ok"], out
        ok, state = RD.load_state(self.d)
        assert ok
        return n, state

    def git_full(self):
        return _git_diff(self.repo, self.base)

    def fix_only(self):
        return _git(self.repo, "diff", "HEAD~1", "HEAD")


def _assert_parked(state, token):
    assert state["terminal"] == "cannot-certify"
    assert state["certification"]["reason"].startswith(token)
    assert state["headDiff"] is None


def _empty_file(tmp_path):
    path = tmp_path / "empty.diff"
    path.write_text("", encoding="utf-8")
    return str(path)


@pytest.mark.parametrize("case", ["fix-only", "inline-empty", "path-empty"])
def test_t2_mismatched_supplied_diff_refuses_on_the_cli_path(tmp_path, monkeypatch, case):
    cli = _Cli(tmp_path, monkeypatch)
    cli.supply = {
        "fix-only": lambda c: {"headDiff": c.fix_only()},
        "inline-empty": lambda c: {"headDiff": ""},
        "path-empty": lambda c: {"headDiffPath": _empty_file(tmp_path)},
    }[case]
    n, state = cli.fold_fixer()
    _assert_parked(state, "head-diff-mismatch")
    rec = state["rounds"][str(n["round"])]
    assert rec["headDiffSource"] == "git"
    assert rec["headDiffCheck"] == "mismatch"
    assert state["reviewedDiff"] != cli.git_full()
    assert RD.cmd_next(cli.d)["action"] == RD.P_TERMINAL


def test_t4_no_supplied_diff_derives_git_and_schedules_the_fix_audit(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    n, state = cli.fold_fixer()
    rec = state["rounds"][str(n["round"])]
    assert rec["headDiffSource"] == "git"
    assert rec["headDiffCheck"] == "none-supplied"
    n2 = RD.cmd_next(cli.d)
    assert n2["phase"] == RD.P_AUDITS
    ok, state = RD.load_state(cli.d)
    assert ok
    assert state["headDiff"] == cli.git_full()
    assert state["reviewedDiff"] == cli.git_full()
    assert state["rounds"][str(state["round"])]["focus"]["on"] == "fixes"


# ---- T5 edges ----------------------------------------------------------------------------------

def test_e3_non_absolute_path_is_unreadable_and_git_governs(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)

    def supply(c):
        # driving to the fixer step moves the cwd into the session checkout, so the relative file is made where the
        # driver reads from, holding text git's diff does not: only the absolute-path rule keeps it unread
        os.makedirs("relative", exist_ok=True)
        with open("relative/fix.diff", "w", encoding="utf-8") as fh:
            fh.write("not git's diff\n")
        return {"headDiffPath": "relative/fix.diff"}

    cli.supply = supply
    n, state = cli.fold_fixer()
    assert state.get("terminal") is None
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("git", "supplied-unreadable")
    assert state["headDiff"] == cli.git_full()


def test_e4_missing_file_path_is_unreadable_and_git_governs(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    cli.supply = lambda c: {"headDiffPath": str(tmp_path / "missing.diff")}
    n, state = cli.fold_fixer()
    assert state.get("terminal") is None
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("git", "supplied-unreadable")
    assert state["headDiff"] == cli.git_full()


def test_e5_git_refusal_beside_a_supplied_diff_parks_unverifiable(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    real = RD._derive_panel_diff_at_head
    monkeypatch.setattr(RD, "_derive_panel_diff_at_head",
                        lambda config, head: real(dict(config, baseRef="not-a-commit"), head))
    cli.supply = lambda c: {"headDiff": c.fix_only()}
    n, state = cli.fold_fixer()
    _assert_parked(state, "head-diff-unverifiable")
    assert "baseRef not a commit" in state["certification"]["reason"]
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("unknown", "unverifiable")


def test_e6_empty_git_diff_with_nothing_supplied_takes_the_unknown_path(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    cli.fixer_body = "old\n"
    n, state = cli.fold_fixer()
    _assert_parked(state, "panel-diff-underivable")
    assert "empty diff" in state["certification"]["reason"]
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("unknown", "unverifiable")


def test_e7_unresolved_head_with_nothing_supplied_takes_the_unknown_path(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    monkeypatch.setattr(RD, "_resolve_fix_fold_head_sha",
                        lambda session_dir, state: (None, "fix-fold head: repo root unresolvable"))
    n, state = cli.fold_fixer()
    _assert_parked(state, "panel-diff-underivable")
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("unknown", "unverifiable")
    assert rec["fixFoldHeadRefused"] == "fix-fold head: repo root unresolvable"


def test_e7_unresolved_head_beside_a_supplied_diff_parks_with_the_resolver_text(tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch)
    monkeypatch.setattr(RD, "_resolve_fix_fold_head_sha",
                        lambda session_dir, state: (None, "fix-fold head: repo root unresolvable"))
    cli.supply = lambda c: {"headDiff": c.fix_only()}
    _n, state = cli.fold_fixer()
    _assert_parked(state, "head-diff-unverifiable")
    assert "fix-fold head: repo root unresolvable" in state["certification"]["reason"]


def test_e7_in_process_seam_receives_an_unresolved_head():
    seen = []

    def seam(config, head):
        seen.append(head)
        return _FULL, None

    _r, state = _loop(None, seam=seam)
    assert seen and seen[0] is None
    assert state["rounds"]["1"]["headDiffCheck"] == "none-supplied"


@pytest.mark.parametrize("how", ["path", "inline-lf"])
def test_e8_crlf_content_matches_after_newline_normalization(tmp_path, monkeypatch, how):
    cli = _Cli(tmp_path, monkeypatch)
    cli.fixer_body = "x\r\ny\r\n"

    def supply(c):
        git_text = c.git_full()
        assert "\r\n" in git_text
        if how == "inline-lf":
            return {"headDiff": git_text.replace("\r\n", "\n")}
        path = tmp_path / "crlf.diff"
        path.write_bytes(git_text.encode("utf-8"))
        return {"headDiffPath": str(path)}

    cli.supply = supply
    n, state = cli.fold_fixer()
    assert state.get("terminal") is None
    rec = state["rounds"][str(n["round"])]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("git", "match")
    assert state["headDiff"] == cli.git_full()


def test_e9_second_fix_slice_with_a_mismatching_diff_parks_without_post_fix_entry(
        tmp_path, monkeypatch):
    cli = _Cli(tmp_path, monkeypatch, findings=_TWO_LINE_FINDINGS, fixBatchCap=1)
    cli.supply = lambda c: {"headDiff": c.git_full()} if c.fix_calls == 1 else {
        "headDiff": c.fix_only()}
    n1 = cli.to_fixer()
    out1 = cli.submit(n1)
    assert out1["ok"], out1
    ok, state = RD.load_state(cli.d)
    assert ok and state.get("terminal") is None
    assert state["rounds"][str(n1["round"])]["headDiffCheck"] == "match"
    n2 = RD.cmd_next(cli.d)
    assert n2["phase"] == RD.P_APPLY_FIXES
    out2 = cli.submit(n2)
    assert out2["ok"], out2
    ok, state = RD.load_state(cli.d)
    assert ok
    _assert_parked(state, "head-diff-mismatch")
    rec = state["rounds"][str(n1["round"])]
    assert rec["headDiffCheck"] == "mismatch"
    assert [b["index"] for b in rec["fixBatches"]] == [0, 1]
    assert str(n1["round"] + 1) not in state["rounds"]
    assert RD.cmd_next(cli.d)["action"] == RD.P_TERMINAL


def _no_repo_loop(fix_artifact):
    seams = _seams(
        reviewer=lambda dim, tier, rnd, ctx: list(_FINDING_F) if (
            dim == "code-reviewer" and rnd == 1) else [],
        fix_step=lambda batch, rnd, payload: fix_artifact, vendors=["claude", "codex"])
    return _run_loop_capturing_state(seams, _cfg(diff=DIFF))


def test_e10_no_repository_run_keeps_the_supplied_inline_diff():
    _r, state = _no_repo_loop({"fixes": [], "headDiff": HEAD, "changedSubjects": ["Code"]})
    rec = state["rounds"]["1"]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("inline", "no-repository")
    assert state["reviewedDiff"] == HEAD


def test_e10_no_repository_inline_empty_text_is_still_inline():
    _r, state = _no_repo_loop({"fixes": [], "headDiff": "", "changedSubjects": ["Code"]})
    rec = state["rounds"]["1"]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("inline", "no-repository")


@pytest.mark.parametrize("case", ["path", "no-key", "relative", "empty-file", "empty-string"])
def test_e10_no_repository_path_and_unknown_rows(tmp_path, case):
    good = tmp_path / "head.diff"
    good.write_text(HEAD, encoding="utf-8")
    extra = {
        "path": {"headDiffPath": str(good)},
        "no-key": {},
        "relative": {"headDiffPath": "head.diff"},
        "empty-file": {"headDiffPath": _empty_file(tmp_path)},
        "empty-string": {"headDiffPath": ""},
    }[case]
    _r, state = _no_repo_loop(dict({"fixes": [], "changedSubjects": ["Code"]}, **extra))
    rec = state["rounds"]["1"]
    source = "path" if case == "path" else "unknown"
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == (source, "no-repository")


def test_e10_no_repository_unreadable_path_is_unknown_and_never_an_empty_surface(tmp_path):
    missing = str(tmp_path / "does-not-exist.diff")
    _r, state = _no_repo_loop({"fixes": [], "headDiffPath": missing, "changedSubjects": ["Code"]})
    rec = state["rounds"]["1"]
    assert (rec["headDiffSource"], rec["headDiffCheck"]) == ("unknown", "no-repository")
    assert state["terminal"] == "cannot-certify"
    reason = state["certification"]["reason"]
    assert reason.startswith("panel-diff-underivable")
    assert "repoRoot missing" in reason
    assert "2" not in state["rounds"]
