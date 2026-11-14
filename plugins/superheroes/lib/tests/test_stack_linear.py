"""Units for stack_linear.py (#2459): is a stack linear, and did a straightening keep every layer's files?

`check_local` and `prove` run against real throwaway git repos built under pytest's tmp path; the git
fixture ignores the user's and the system's git config and passes its commit identity inline.
`check_rest` runs against a faked `gh`: the commit-row shape used here is the measured one (live,
2026-11-14, `gh api "repos/zwrose/superheroes/pulls/2407/commits?per_page=2&page=1"`, projected to
sha and parents; the parents' objects also carry url and html_url)."""
import datetime
import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import stack_linear as sl  # noqa: E402

# pinned condition: every fixture git call ignores the user's and the system's git config and passes its
# commit identity inline, so a host whose global config rewrites hooks, signing or default branches
# cannot change the repos built here.
_GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]

REPO = "o/r"
SHA_A = "a" * 40
SHA_B = "b" * 40
TODAY = datetime.date(2026, 11, 14)


# ---------------------------------------------------------------------------------------------
# Real-git fixture.
# ---------------------------------------------------------------------------------------------

def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + _ID + list(args), capture_output=True,
                          text=True, env=_GIT_ENV)
    assert done.returncode == 0, "git %s: %s" % (list(args), done.stderr)
    return done.stdout.strip()


def _head(repo):
    return _git(repo, "rev-parse", "HEAD")


def _commit_file(repo, name, text, message):
    with open(os.path.join(str(repo), name), "w") as handle:
        handle.write(text)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)
    return _head(repo)


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    """main (c0, then m1), and a three-layer --no-ff stack: l1 has main merged into it, l2 has a side
    branch merged into it, l3 is linear on l2. `new` is each layer rebased in turn onto the one below,
    on detached heads, starting from `base` (main's tip, which l1 already contains)."""
    repo = tmp_path_factory.mktemp("stack")
    _git(repo, "init", "-q", "-b", "main")
    _commit_file(repo, "a.txt", "0\n", "c0")
    _git(repo, "checkout", "-q", "-b", "l1")
    _commit_file(repo, "f1.txt", "1\n", "f1")
    _git(repo, "checkout", "-q", "main")
    base = _commit_file(repo, "m.txt", "m\n", "m1")
    _git(repo, "checkout", "-q", "l1")
    _git(repo, "merge", "-q", "--no-ff", "-m", "main into l1", "main")
    merge1 = _head(repo)
    _git(repo, "checkout", "-q", "-b", "side")
    _commit_file(repo, "g.txt", "g\n", "g")
    _git(repo, "checkout", "-q", "-b", "l2", "l1")
    _commit_file(repo, "f2.txt", "2\n", "f2")
    _git(repo, "merge", "-q", "--no-ff", "-m", "side into l2", "side")
    merge2 = _head(repo)
    _git(repo, "checkout", "-q", "-b", "l3")
    _commit_file(repo, "f3.txt", "3\n", "f3")
    vetted = [_git(repo, "rev-parse", name) for name in ("l1", "l2", "l3")]

    new = []
    prev_new, prev_old = base, base
    for sha in vetted:
        _git(repo, "checkout", "-q", "--detach", sha)
        _git(repo, "rebase", "-q", "--onto", prev_new, prev_old)
        prev_new, prev_old = _head(repo), sha
        new.append(prev_new)
    _git(repo, "checkout", "-q", "main")
    return SimpleNamespace(repo=str(repo), base=base, vetted=vetted, new=new,
                           branches=["l1", "l2", "l3"], merges=[merge1, merge2])


def _amend(stack, sha, *, message=None, change=None):
    """A new commit that replaces `sha` on a detached head: the same tree with another message, or a
    changed file when `change` is a file name."""
    _git(stack.repo, "checkout", "-q", "--detach", sha)
    if change is not None:
        with open(os.path.join(stack.repo, change), "a") as handle:
            handle.write("changed\n")
        _git(stack.repo, "add", change)
    args = ["commit", "-q", "--amend"] + (["-m", message] if message else ["--no-edit"])
    _git(stack.repo, *args)
    out = _head(stack.repo)
    _git(stack.repo, "checkout", "-q", "main")
    return out


def _triples(stack, new=None, vetted=None):
    new = stack.new if new is None else new
    vetted = stack.vetted if vetted is None else vetted
    return [(stack.branches[i], vetted[i], new[i]) for i in range(3)]


def _proc(argv, rc=0, out="", err=""):
    return subprocess.CompletedProcess(argv, rc, out, err)


class _GitRun:
    """A `run` that records every call and runs real git, except where `fake(argv)` answers. `fake`
    returns None to let the real git run, a CompletedProcess to answer, or an exception to raise."""

    def __init__(self, fake=None):
        self.fake = fake
        self.calls = []
        self.kw = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kw.append(dict(kwargs))
        if self.fake is not None:
            out = self.fake(list(argv))
            if isinstance(out, BaseException):
                raise out
            if out is not None:
                return out
        return subprocess.run(argv, env=_GIT_ENV, **kwargs)


def _fail_when(match, **proc_kwargs):
    """A fake that answers a CompletedProcess(**proc_kwargs) to every argv `match` accepts."""
    def fake(argv):
        if match(argv):
            return _proc(argv, **proc_kwargs)
        return None
    return fake


def _raise_when(match, exc):
    def fake(argv):
        return exc if match(argv) else None
    return fake


def _is_shallow_probe(argv):
    return argv[1:] == ["rev-parse", "--is-shallow-repository"]


def _is_ancestor_call(newer):
    return lambda argv: argv[1:3] == ["merge-base", "--is-ancestor"] and argv[4] == newer


def _is_tree_read(sha):
    return lambda argv: argv[1:3] == ["rev-parse", "--verify"] and argv[-1] == sha + "^{tree}"


def _is_merges_scan(newer):
    return lambda argv: argv[1:3] == ["rev-list", "--merges"] and argv[3].endswith(".." + newer)


def _is_parents_scan(newer):
    return lambda argv: argv[1:3] == ["rev-list", "--parents"] and argv[3].endswith(".." + newer)


def _is_commit_resolve(ref):
    return lambda argv: argv[1:3] == ["rev-parse", "--verify"] and argv[-1] == ref + "^{commit}"


# ---------------------------------------------------------------------------------------------
# check_local.
# ---------------------------------------------------------------------------------------------

def test_local_no_ff_stack_is_not_linear(stack):
    run = _GitRun()
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=["l1", "l2", "l3"], run=run)
    assert result["ok"] is False
    assert result["linear"] is False
    assert result["reason"] == "stack-not-linear"
    assert [entry["layer"] for entry in result["layers"]] == ["l1", "l2", "l3"]
    assert result["layers"][0]["mergeCommits"] == [stack.merges[0]]
    assert result["layers"][1]["mergeCommits"] == [stack.merges[1]]
    assert result["layers"][2]["mergeCommits"] == []
    assert [entry["commits"] for entry in result["layers"]] == [2, 3, 1]
    assert "layer l1" in result["detail"] and stack.merges[0] in result["detail"]
    assert "layer l2" in result["detail"] and stack.merges[1] in result["detail"]
    assert set(result) == {"ok", "linear", "reason", "detail", "layers"}


def test_local_a_merge_in_only_the_top_layer_is_still_not_linear(stack):
    # layers l3 only, with its base at the vetted l2: l3 is linear; with its base at l1 it holds l2's merge
    linear = sl.check_local(repo_root=stack.repo, base=stack.vetted[1], layers=["l3"], run=_GitRun())
    assert linear["linear"] is True
    holds = sl.check_local(repo_root=stack.repo, base=stack.vetted[0], layers=["l3"], run=_GitRun())
    assert holds["reason"] == "stack-not-linear"
    assert holds["layers"][0]["mergeCommits"] == [stack.merges[1]]


def test_local_rebased_stack_is_linear(stack):
    run = _GitRun()
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=list(stack.new), run=run)
    assert result == {
        "ok": True, "linear": True, "reason": None, "detail": None,
        "layers": [{"layer": stack.new[0], "commits": 1, "mergeCommits": []},
                   {"layer": stack.new[1], "commits": 2, "mergeCommits": []},
                   {"layer": stack.new[2], "commits": 1, "mergeCommits": []}],
    }
    for argv in run.calls:
        assert argv[0] == "git"
    for kwargs in run.kw:
        assert kwargs["cwd"] == stack.repo
        assert kwargs["timeout"] == sl.GIT_TIMEOUT
        assert kwargs["capture_output"] is True and kwargs["text"] is True


def test_local_ranges_run_layer_below_to_layer(stack):
    run = _GitRun()
    sl.check_local(repo_root=stack.repo, base=stack.base, layers=list(stack.new), run=run)
    scans = [argv[3] for argv in run.calls if argv[1:3] == ["rev-list", "--parents"]]
    assert scans == ["%s..%s" % (stack.base, stack.new[0]),
                     "%s..%s" % (stack.new[0], stack.new[1]),
                     "%s..%s" % (stack.new[1], stack.new[2])]


def test_local_shallow_clone_is_unreadable(stack, tmp_path):
    clone = str(tmp_path / "shallow")
    done = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "l3",
                           "file://" + stack.repo, clone],
                          capture_output=True, text=True, env=_GIT_ENV)
    assert done.returncode == 0, done.stderr
    result = sl.check_local(repo_root=clone, base="HEAD", layers=["HEAD"], run=_GitRun())
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert result["detail"] == "history-shallow"


def test_local_shallow_true_is_unreadable_and_nothing_else_runs():
    run = _GitRun(_fail_when(_is_shallow_probe, out="true\n"))
    result = sl.check_local(repo_root="/x", base="main", layers=["a"], run=run)
    assert result["reason"] == "linearity-unreadable"
    assert result["detail"] == "history-shallow"
    assert len(run.calls) == 1


@pytest.mark.parametrize("fake", [
    _fail_when(_is_shallow_probe, rc=128, err="fatal: not a git repository"),
    _fail_when(_is_shallow_probe, rc=1, out="false\n"),
    _fail_when(_is_shallow_probe, rc=0, out="maybe\n"),
    _fail_when(_is_shallow_probe, rc=0, out=""),
    _raise_when(_is_shallow_probe, OSError("no git")),
    _raise_when(_is_shallow_probe, subprocess.TimeoutExpired("git", 60)),
], ids=["exit-128", "exit-1-says-false", "prints-maybe", "prints-nothing", "oserror", "timeout"])
def test_local_shallow_probe_that_cannot_answer_is_unreadable(stack, fake):
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=list(stack.new),
                            run=_GitRun(fake))
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert result["detail"] != "history-shallow"
    assert [entry["layer"] for entry in result["layers"]] == list(stack.new)


def test_local_ref_that_does_not_resolve_is_unreadable_and_no_range_is_read(stack):
    for base, layers in (("no-such-ref", ["l1"]), (stack.base, ["l1", "no-such-ref"])):
        run = _GitRun()
        result = sl.check_local(repo_root=stack.repo, base=base, layers=layers, run=run)
        assert result["reason"] == "linearity-unreadable"
        assert "no-such-ref" in result["detail"]
        assert not [argv for argv in run.calls if argv[1] == "rev-list"]


@pytest.mark.parametrize("rc,out", [(1, None), (0, "zzz\n"), (0, "")], ids=["exit-1", "not-a-sha", "empty"])
def test_local_resolve_that_prints_no_object_id_is_unreadable(stack, rc, out):
    out = out if out is not None else stack.base + "\n"
    run = _GitRun(_fail_when(_is_commit_resolve("l1"), rc=rc, out=out))
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=["l1"], run=run)
    assert result["reason"] == "linearity-unreadable"


def test_local_rev_list_failure_is_unreadable_not_linear(stack):
    run = _GitRun(_fail_when(_is_parents_scan(stack.new[1]), rc=128, err="fatal: bad revision"))
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=list(stack.new), run=run)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert result["layers"][1]["commits"] is None
    assert result["layers"][0]["commits"] == 1 and result["layers"][2]["commits"] == 1


@pytest.mark.parametrize("exc", [OSError("no git"), subprocess.TimeoutExpired("git", 60)],
                         ids=["oserror", "timeout"])
def test_local_run_raising_on_rev_list_is_unreadable(stack, exc):
    run = _GitRun(_raise_when(_is_parents_scan(stack.new[2]), exc))
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=list(stack.new), run=run)
    assert result["reason"] == "linearity-unreadable"


def test_local_unreadable_layer_wins_over_a_merge_commit(stack):
    run = _GitRun(_fail_when(_is_parents_scan(stack.vetted[1]), rc=128))
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=["l1", "l2"], run=run)
    assert result["layers"][0]["mergeCommits"] == [stack.merges[0]]
    assert result["reason"] == "linearity-unreadable"
    assert result["linear"] is None


def test_local_run_raising_on_resolve_is_unreadable(stack):
    run = _GitRun(_raise_when(_is_commit_resolve("l2"), OSError("gone")))
    result = sl.check_local(repo_root=stack.repo, base=stack.base, layers=["l1", "l2"], run=run)
    assert result["reason"] == "linearity-unreadable"


@pytest.mark.parametrize("kwargs", [
    dict(repo_root="", base="main", layers=["a"]),
    dict(repo_root=None, base="main", layers=["a"]),
    dict(repo_root="/x", base="", layers=["a"]),
    dict(repo_root="/x", base="-x", layers=["a"]),
    dict(repo_root="/x", base="a b", layers=["a"]),
    dict(repo_root="/x", base=None, layers=["a"]),
    dict(repo_root="/x", base="main", layers=[]),
    dict(repo_root="/x", base="main", layers=None),
    dict(repo_root="/x", base="main", layers="abc"),
    dict(repo_root="/x", base="main", layers=("a",)),
    dict(repo_root="/x", base="main", layers=["a", ""]),
    dict(repo_root="/x", base="main", layers=["a", "--exec"]),
    dict(repo_root="/x", base="main", layers=["a", 5]),
    dict(repo_root="/x", base="main", layers=["a", "b c"]),
])
def test_local_bad_argument_runs_nothing(kwargs):
    run = _GitRun()
    result = sl.check_local(run=run, **kwargs)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "bad-argument"
    assert result["layers"] == []
    assert run.calls == []


# ---------------------------------------------------------------------------------------------
# check_rest.
# ---------------------------------------------------------------------------------------------

def _row(sha, *parents):
    return {"sha": sha, "node_id": "C_x", "commit": {"message": "m"},
            "parents": [{"sha": p, "url": "https://api.github.com/x", "html_url": "https://github.com/x"}
                        for p in parents]}


def _rows(n, prefix):
    out = []
    for i in range(n):
        sha = "%s%038d" % (prefix, i)
        parent = "%s%038d" % (prefix, i - 1) if i else SHA_A
        out.append(_row(sha, parent))
    return out


_COMMITS_RE = re.compile(r"\Arepos/o/r/pulls/(\d+)/commits\?per_page=100&page=(\d+)\Z")


class _Gh:
    """A faked gh: serves each pull request's rows a page at a time. `override(argv)` answers first."""

    def __init__(self, layers, override=None):
        self.layers = layers
        self.override = override
        self.calls = []
        self.kw = []

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kw.append(dict(kwargs))
        if self.override is not None:
            out = self.override(list(argv))
            if isinstance(out, BaseException):
                raise out
            if out is not None:
                return out
        assert argv[:2] == ["gh", "api"] and len(argv) == 3, argv
        match = _COMMITS_RE.match(argv[2])
        assert match, "unexpected endpoint: %r" % (argv,)
        rows = self.layers[int(match.group(1))]
        page = int(match.group(2))
        return _proc(argv, 0, json.dumps(rows[(page - 1) * 100:page * 100]))


class _Clock:
    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sl.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def test_rest_measured_row_shape_two_parent_row_is_not_linear():
    rows = [
        {"sha": "41301094d58dedceb5d4d9f287a325fa4e88773f",
         "parents": [{"sha": "7ecf48fbd3c1b3d8a6f3a1f0f6a6e0b4b0d0c0aa"}]},
        {"sha": "7f17bde8c3eac1de06fa6a120ad83494435f2822",
         "parents": [{"sha": "41301094d58dedceb5d4d9f287a325fa4e88773f"},
                     {"sha": "020255894897e44a5cec4a1bcb6a173a42977898"}]},
    ]
    gh = _Gh({2407: rows})
    result = sl.check_rest(repo=REPO, prs=[2407], run=gh)
    assert result["ok"] is False and result["linear"] is False
    assert result["reason"] == "stack-not-linear"
    assert result["layers"] == [{"layer": 2407, "commits": 2,
                                 "mergeCommits": ["7f17bde8c3eac1de06fa6a120ad83494435f2822"]}]
    assert "2407" in result["detail"] and "7f17bde8c3eac1de06fa6a120ad83494435f2822" in result["detail"]


def test_rest_linear_stack_is_linear_and_reads_by_page_number():
    gh = _Gh({11: _rows(3, "1"), 12: _rows(150, "2"), 13: []})
    result = sl.check_rest(repo=REPO, prs=[11, 12, 13], run=gh)
    assert result == {
        "ok": True, "linear": True, "reason": None, "detail": None,
        "layers": [{"layer": 11, "commits": 3, "mergeCommits": []},
                   {"layer": 12, "commits": 150, "mergeCommits": []},
                   {"layer": 13, "commits": 0, "mergeCommits": []}],
    }
    assert [argv[2] for argv in gh.calls] == [
        "repos/o/r/pulls/11/commits?per_page=100&page=1",
        "repos/o/r/pulls/12/commits?per_page=100&page=1",
        "repos/o/r/pulls/12/commits?per_page=100&page=2",
        "repos/o/r/pulls/13/commits?per_page=100&page=1",
    ]
    for argv in gh.calls:
        assert "--paginate" not in argv
    for kwargs in gh.kw:
        assert kwargs["capture_output"] is True and kwargs["text"] is True
        assert kwargs["timeout"] == sl.GH_TIMEOUT


def test_rest_a_root_commit_with_no_parents_is_not_a_merge():
    result = sl.check_rest(repo=REPO, prs=[11], run=_Gh({11: [_row(SHA_A)]}))
    assert result["linear"] is True


def test_rest_three_parent_row_is_a_merge_commit_in_its_layer_only():
    gh = _Gh({11: _rows(2, "1"), 12: [_row(SHA_B, SHA_A, "c" * 40, "d" * 40)] + _rows(1, "2")})
    result = sl.check_rest(repo=REPO, prs=[11, 12], run=gh)
    assert result["reason"] == "stack-not-linear"
    assert result["layers"][0]["mergeCommits"] == []
    assert result["layers"][1]["mergeCommits"] == [SHA_B]


def test_rest_249_commits_is_read_and_250_is_at_the_cap():
    below = sl.check_rest(repo=REPO, prs=[11], run=_Gh({11: _rows(249, "1")}))
    assert below["linear"] is True and below["layers"][0]["commits"] == 249
    at_cap = sl.check_rest(repo=REPO, prs=[11], run=_Gh({11: _rows(sl.PR_COMMITS_CAP, "1")}))
    assert at_cap["ok"] is False and at_cap["linear"] is None
    assert at_cap["reason"] == "linearity-unreadable"
    assert "250" in at_cap["detail"]
    assert at_cap["layers"][0]["commits"] is None


def test_rest_unreadable_layer_wins_over_a_merge_commit():
    gh = _Gh({11: [_row(SHA_B, SHA_A, "c" * 40)], 12: _rows(sl.PR_COMMITS_CAP, "2")})
    result = sl.check_rest(repo=REPO, prs=[11, 12], run=gh)
    assert result["reason"] == "linearity-unreadable"
    assert result["linear"] is None
    assert result["layers"][0]["mergeCommits"] == [SHA_B]
    assert len(gh.calls) == 1 + 3, "every layer is read before the answer"


@pytest.mark.parametrize("override", [
    lambda argv: _proc(argv, 1, "", "gh: Not Found (HTTP 404)"),
    lambda argv: _proc(argv, 0, "not json"),
    lambda argv: _proc(argv, 0, ""),
    lambda argv: _proc(argv, 0, json.dumps({"message": "Not Found"})),
    lambda argv: _proc(argv, 0, json.dumps("rows")),
    lambda argv: _proc(argv, 0, "null"),
], ids=["exit-1", "not-json", "empty", "page-is-object", "page-is-string", "page-is-null"])
def test_rest_unreadable_page_is_unreadable_never_linear(override):
    gh = _Gh({11: _rows(2, "1")}, override=override)
    result = sl.check_rest(repo=REPO, prs=[11], run=gh)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert result["layers"] == [{"layer": 11, "commits": None, "mergeCommits": []}]


def test_rest_gh_exiting_non_zero_is_unreadable_even_with_rows_on_stdout():
    rows = json.dumps(_rows(2, "1"))
    gh = _Gh({11: _rows(2, "1")}, override=lambda argv: _proc(argv, 1, rows, "gh: rate limited"))
    result = sl.check_rest(repo=REPO, prs=[11], run=gh)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert "exited 1" in result["detail"]


def test_rest_second_page_unreadable_is_not_a_partial_list():
    def override(argv):
        return _proc(argv, 1, "", "boom") if argv[2].endswith("page=2") else None
    result = sl.check_rest(repo=REPO, prs=[11], run=_Gh({11: _rows(150, "1")}, override=override))
    assert result["reason"] == "linearity-unreadable"


BAD_ROWS = {
    "row-string": "abc",
    "row-null": None,
    "row-list": [],
    "sha-missing": {"parents": []},
    "sha-int": {"sha": 5, "parents": []},
    "sha-empty": {"sha": "", "parents": []},
    "parents-missing": {"sha": SHA_A},
    "parents-null": {"sha": SHA_A, "parents": None},
    "parents-empty-dict": {"sha": SHA_A, "parents": {}},
    "parents-empty-string": {"sha": SHA_A, "parents": ""},
    "parent-string": {"sha": SHA_A, "parents": ["b"]},
    "parent-sha-int": {"sha": SHA_A, "parents": [{"sha": 5}]},
    "parent-sha-missing": {"sha": SHA_A, "parents": [{"url": "u"}]},
}


@pytest.mark.parametrize("bad", list(BAD_ROWS.values()), ids=list(BAD_ROWS))
def test_rest_unreadable_row_makes_the_layer_unreadable(bad):
    gh = _Gh({11: _rows(1, "1") + [bad] + _rows(1, "2")})
    result = sl.check_rest(repo=REPO, prs=[11], run=gh)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "linearity-unreadable"
    assert result["layers"] == [{"layer": 11, "commits": None, "mergeCommits": []}]


def test_rest_gh_not_on_path_is_unreadable_and_runs_nothing(monkeypatch):
    monkeypatch.setattr(sl.shutil, "which", lambda name: None)
    gh = _Gh({11: _rows(1, "1")})
    result = sl.check_rest(repo=REPO, prs=[11, 12], run=gh)
    assert result["reason"] == "linearity-unreadable"
    assert "gh" in result["detail"]
    assert [entry["layer"] for entry in result["layers"]] == [11, 12]
    assert gh.calls == []


@pytest.mark.parametrize("exc", [OSError("gone"), FileNotFoundError("gh"),
                                 subprocess.TimeoutExpired("gh", 5)],
                         ids=["oserror", "filenotfound", "timeout"])
def test_rest_run_raising_is_unreadable_not_raised(exc):
    result = sl.check_rest(repo=REPO, prs=[11], run=_Gh({11: _rows(1, "1")}, override=lambda a: exc))
    assert result["reason"] == "linearity-unreadable"


def test_rest_deadline_already_passed_makes_no_call():
    gh = _Gh({11: _rows(1, "1")})
    result = sl.check_rest(repo=REPO, prs=[11], deadline_at=10, run=gh, monotonic=_Clock(10))
    assert result["reason"] == "linearity-unreadable"
    assert "deadline" in result["detail"]
    assert gh.calls == []
    past = sl.check_rest(repo=REPO, prs=[11], deadline_at=10, run=gh, monotonic=_Clock(11))
    assert past["reason"] == "linearity-unreadable"
    assert gh.calls == []


def test_rest_per_call_timeout_is_capped_by_the_time_left():
    gh = _Gh({11: _rows(1, "1")})
    result = sl.check_rest(repo=REPO, prs=[11], timeout=120, deadline_at=130, run=gh,
                           monotonic=_Clock(100))
    assert result["linear"] is True
    assert [kwargs["timeout"] for kwargs in gh.kw] == [30]
    gh2 = _Gh({11: _rows(1, "1")})
    sl.check_rest(repo=REPO, prs=[11], timeout=20, deadline_at=1000, run=gh2, monotonic=_Clock(100))
    assert [kwargs["timeout"] for kwargs in gh2.kw] == [20]


def test_rest_deadline_that_passes_between_layers_stops_the_calls():
    gh = _Gh({11: _rows(1, "1"), 12: _rows(1, "2")})
    result = sl.check_rest(repo=REPO, prs=[11, 12], deadline_at=100, run=gh,
                           monotonic=_Clock(0, 100))
    assert result["reason"] == "linearity-unreadable"
    assert len(gh.calls) == 1
    assert result["layers"][0]["commits"] == 1
    assert result["layers"][1]["commits"] is None


@pytest.mark.parametrize("kwargs", [
    dict(repo=None, prs=[1]),
    dict(repo="owner", prs=[1]),
    dict(repo="o/r/x", prs=[1]),
    dict(repo="o/ r", prs=[1]),
    dict(repo=REPO, prs=[]),
    dict(repo=REPO, prs=None),
    dict(repo=REPO, prs="12"),
    dict(repo=REPO, prs=(1, 2)),
    dict(repo=REPO, prs=[0]),
    dict(repo=REPO, prs=[-3]),
    dict(repo=REPO, prs=[True]),
    dict(repo=REPO, prs=["5"]),
    dict(repo=REPO, prs=[5.0]),
    dict(repo=REPO, prs=[1, 2, 1]),
    dict(repo=REPO, prs=[1], timeout=0),
    dict(repo=REPO, prs=[1], timeout=True),
    dict(repo=REPO, prs=[1], timeout=float("nan")),
    dict(repo=REPO, prs=[1], timeout=float("inf")),
    dict(repo=REPO, prs=[1], timeout=None),
    dict(repo=REPO, prs=[1], deadline_at="soon"),
    dict(repo=REPO, prs=[1], deadline_at=True),
    dict(repo=REPO, prs=[1], deadline_at=float("nan")),
])
def test_rest_bad_argument_runs_nothing(kwargs):
    gh = _Gh({1: _rows(1, "1")})
    result = sl.check_rest(run=gh, **kwargs)
    assert result["ok"] is False and result["linear"] is None
    assert result["reason"] == "bad-argument"
    assert result["layers"] == []
    assert gh.calls == []


# ---------------------------------------------------------------------------------------------
# prove.
# ---------------------------------------------------------------------------------------------

def _prove(stack, triples=None, **kwargs):
    kwargs.setdefault("run", _GitRun())
    kwargs.setdefault("today", TODAY)
    return sl.prove(repo_root=stack.repo, base=stack.base,
                    layers=_triples(stack) if triples is None else triples, **kwargs)


def _assert_not_proven(result, reason):
    assert result["ok"] is False and result["proven"] is False
    assert result["reason"] == reason
    assert result["repin"] == [] and result["push"] is None


def test_prove_rebased_stack_is_proven_with_repin_lines_and_the_exact_push(stack):
    result = _prove(stack)
    assert set(result) == {"ok", "proven", "reason", "detail", "base", "layers", "repin", "push"}
    assert result["ok"] is True and result["proven"] is True and result["reason"] is None
    assert result["base"] == stack.base
    trees = [_git(stack.repo, "rev-parse", sha + "^{tree}") for sha in stack.new]
    assert trees == [_git(stack.repo, "rev-parse", sha + "^{tree}") for sha in stack.vetted]
    assert result["repin"] == [
        "Re-pinned 2026-11-14 (stack straightened for a merge-queue base): %s %s -> %s, tree %s equal." % (
            stack.branches[i], stack.vetted[i], stack.new[i], trees[i])
        for i in range(3)
    ]
    assert len(result["repin"]) == 3
    assert result["push"] == (
        ["git", "push", "--atomic", "origin"]
        + ["--force-with-lease=refs/heads/%s:%s" % (stack.branches[i], stack.vetted[i]) for i in range(3)]
        + ["%s:refs/heads/%s" % (stack.new[i], stack.branches[i]) for i in range(3)]
    )
    assert result["layers"] == [
        {"branch": stack.branches[i], "vetted": stack.vetted[i], "new": stack.new[i], "tree": trees[i],
         "treeEqual": True, "mergeCommits": [], "onLayerBelow": True}
        for i in range(3)
    ]


def test_prove_accepts_refs_by_name_and_a_custom_remote(stack):
    triples = [(stack.branches[i], stack.branches[i], stack.new[i]) for i in range(3)]
    result = _prove(stack, triples, remote="upstream")
    assert result["proven"] is True
    assert result["push"][:4] == ["git", "push", "--atomic", "upstream"]
    assert result["layers"][0]["vetted"] == stack.vetted[0]


def test_prove_today_defaults_to_the_utc_date_and_takes_a_datetime(stack):
    result = _prove(stack, today=None)
    assert re.match(r"\ARe-pinned \d{4}-\d{2}-\d{2} \(stack straightened", result["repin"][0])
    stamp = datetime.datetime(2026, 1, 2, 23, 59)
    again = _prove(stack, today=stamp)
    assert again["repin"][0].startswith("Re-pinned 2026-01-02 (")


def test_prove_one_layer_stack(stack):
    result = _prove(stack, [("l1", stack.vetted[0], stack.new[0])])
    assert result["proven"] is True and len(result["repin"]) == 1
    assert result["push"][-1] == "%s:refs/heads/l1" % stack.new[0]


def test_prove_changed_file_is_tree_changed_naming_the_layer(stack):
    changed = _amend(stack, stack.new[1], change="f2.txt")
    new = [stack.new[0], changed, stack.new[2]]
    result = _prove(stack, _triples(stack, new=new))
    _assert_not_proven(result, "tree-changed")
    assert "l2" in result["detail"] and changed in result["detail"]
    assert [entry["branch"] for entry in result["layers"]] == ["l1", "l2"]
    assert result["layers"][0]["treeEqual"] is True
    assert result["layers"][1]["treeEqual"] is False
    assert result["layers"][1]["mergeCommits"] is None and result["layers"][1]["onLayerBelow"] is None


def test_prove_changed_bottom_layer_stops_at_the_bottom(stack):
    changed = _amend(stack, stack.new[0], change="f1.txt")
    result = _prove(stack, _triples(stack, new=[changed, stack.new[1], stack.new[2]]))
    _assert_not_proven(result, "tree-changed")
    assert [entry["branch"] for entry in result["layers"]] == ["l1"]


def test_prove_merge_commit_left_in_a_new_head(stack):
    # the vetted bottom is itself the "new" head: it still carries the merge of main
    result = _prove(stack, [("l1", stack.vetted[0], stack.vetted[0])])
    _assert_not_proven(result, "merge-commit-remains")
    assert stack.merges[0] in result["detail"]
    assert result["layers"][0]["mergeCommits"] == [stack.merges[0]]
    assert result["layers"][0]["treeEqual"] is True and result["layers"][0]["onLayerBelow"] is None


def test_prove_merge_commit_left_in_a_middle_layer(stack):
    triples = [("l1", stack.vetted[0], stack.new[0]), ("l2", stack.vetted[1], stack.vetted[1])]
    result = _prove(stack, triples)
    _assert_not_proven(result, "merge-commit-remains")
    assert "l2" in result["detail"]
    assert stack.merges[1] in result["layers"][1]["mergeCommits"]


def test_prove_new_head_not_on_the_layer_below(stack):
    other = _amend(stack, stack.new[0], message="a different commit with the same tree")
    assert other != stack.new[0]
    triples = [("l1", stack.vetted[0], other), ("l2", stack.vetted[1], stack.new[1])]
    result = _prove(stack, triples)
    _assert_not_proven(result, "not-on-layer-below")
    assert "l2" in result["detail"]
    assert result["layers"][0]["onLayerBelow"] is True
    assert result["layers"][1]["onLayerBelow"] is False
    assert result["layers"][1]["mergeCommits"] == []


def test_prove_bottom_that_does_not_descend_from_the_base_is_not_on_layer_below(stack):
    c0 = _git(stack.repo, "rev-parse", stack.base + "~1")
    tree = _git(stack.repo, "rev-parse", stack.vetted[0] + "^{tree}")
    orphan = _git(stack.repo, "commit-tree", "-p", c0, "-m", "same files, forked before the base", tree)
    result = _prove(stack, [("l1", stack.vetted[0], orphan)])
    _assert_not_proven(result, "not-on-layer-below")
    assert result["layers"][0]["treeEqual"] is True
    assert result["layers"][0]["mergeCommits"] == []
    assert result["layers"][0]["onLayerBelow"] is False


def test_prove_base_not_contained_in_the_vetted_bottom(stack):
    later = _git(stack.repo, "commit-tree", "-p", stack.base, "-m", "m2", stack.base + "^{tree}")
    result = sl.prove(repo_root=stack.repo, base=later, layers=_triples(stack), run=_GitRun(),
                      today=TODAY)
    _assert_not_proven(result, "base-not-contained")
    assert later in result["detail"]
    assert result["layers"] == []


def test_prove_shallow_clone_is_history_shallow(stack, tmp_path):
    clone = str(tmp_path / "shallow")
    done = subprocess.run(["git", "clone", "-q", "--depth", "1", "--branch", "l3",
                           "file://" + stack.repo, clone],
                          capture_output=True, text=True, env=_GIT_ENV)
    assert done.returncode == 0, done.stderr
    run = _GitRun()
    result = sl.prove(repo_root=clone, base="HEAD", layers=[("l3", "HEAD", "HEAD")], run=run, today=TODAY)
    _assert_not_proven(result, "history-shallow")
    assert len(run.calls) == 1


def test_prove_shallow_true_stops_before_any_other_git_call():
    run = _GitRun(_fail_when(_is_shallow_probe, out="true\n"))
    result = sl.prove(repo_root="/x", base="b", layers=[("l1", "v", "n")], run=run, today=TODAY)
    _assert_not_proven(result, "history-shallow")
    assert len(run.calls) == 1


@pytest.mark.parametrize("fake", [
    _fail_when(_is_shallow_probe, rc=128, err="fatal: not a git repository"),
    _fail_when(_is_shallow_probe, rc=1, out="false\n"),
    _fail_when(_is_shallow_probe, rc=0, out="maybe\n"),
    _raise_when(_is_shallow_probe, OSError("no git")),
    _raise_when(_is_shallow_probe, subprocess.TimeoutExpired("git", 60)),
], ids=["exit-128", "exit-1-says-false", "prints-maybe", "oserror", "timeout"])
def test_prove_shallow_probe_that_cannot_answer_is_git_failed(stack, fake):
    result = _prove(stack, run=_GitRun(fake))
    _assert_not_proven(result, "git-failed")
    assert result["layers"] == []


def test_prove_unresolvable_base_is_git_failed_naming_the_ref(stack):
    result = sl.prove(repo_root=stack.repo, base="no-such-base", layers=_triples(stack),
                      run=_GitRun(), today=TODAY)
    _assert_not_proven(result, "git-failed")
    assert "no-such-base" in result["detail"] and "base" in result["detail"]


def test_prove_unresolvable_vetted_head_is_git_failed_naming_the_ref(stack):
    result = _prove(stack, [("l1", "no-such-vetted", stack.new[0])])
    _assert_not_proven(result, "git-failed")
    assert "no-such-vetted" in result["detail"] and "vetted" in result["detail"]


def test_prove_unresolvable_new_head_is_git_failed_naming_the_ref(stack):
    result = _prove(stack, [("l1", stack.vetted[0], "no-such-new")])
    _assert_not_proven(result, "git-failed")
    assert "no-such-new" in result["detail"] and "new head" in result["detail"]


@pytest.mark.parametrize("rc,out", [(1, None), (0, "zzz\n"), (0, "")], ids=["exit-1", "not-a-sha", "empty"])
def test_prove_resolve_that_prints_no_object_id_is_git_failed(stack, rc, out):
    out = out if out is not None else stack.base + "\n"
    result = _prove(stack, run=_GitRun(_fail_when(_is_commit_resolve(stack.base), rc=rc, out=out)))
    _assert_not_proven(result, "git-failed")


def test_prove_run_raising_on_a_resolve_is_git_failed(stack):
    result = _prove(stack, run=_GitRun(_raise_when(_is_commit_resolve(stack.new[1]), OSError("gone"))))
    _assert_not_proven(result, "git-failed")
    assert "layer l2 new head" in result["detail"] and "gone" in result["detail"]


def test_prove_containment_check_failing_is_git_failed_not_base_not_contained(stack):
    run = _GitRun(_fail_when(_is_ancestor_call(stack.vetted[0]), rc=128, err="fatal: bad object"))
    result = _prove(stack, run=run)
    _assert_not_proven(result, "git-failed")


def test_prove_containment_check_raising_is_git_failed(stack):
    run = _GitRun(_raise_when(_is_ancestor_call(stack.vetted[0]), subprocess.TimeoutExpired("git", 60)))
    _assert_not_proven(_prove(stack, run=run), "git-failed")


@pytest.mark.parametrize("which", ["new", "vetted"])
def test_prove_unreadable_tree_is_git_failed(stack, which):
    sha = stack.new[1] if which == "new" else stack.vetted[1]
    run = _GitRun(_fail_when(_is_tree_read(sha), rc=128, err="fatal"))
    result = _prove(stack, run=run)
    _assert_not_proven(result, "git-failed")
    assert "l2" in result["detail"]


def test_prove_tree_read_that_prints_no_object_id_is_git_failed(stack):
    run = _GitRun(_fail_when(_is_tree_read(stack.new[0]), rc=0, out="zzz\n"))
    _assert_not_proven(_prove(stack, run=run), "git-failed")


def test_prove_merge_scan_failing_is_git_failed_and_never_proven(stack):
    run = _GitRun(_fail_when(_is_merges_scan(stack.new[1]), rc=128, err="fatal"))
    result = _prove(stack, run=run)
    _assert_not_proven(result, "git-failed")
    assert "l2" in result["detail"]


def test_prove_merge_scan_raising_is_git_failed(stack):
    run = _GitRun(_raise_when(_is_merges_scan(stack.new[2]), subprocess.TimeoutExpired("git", 60)))
    _assert_not_proven(_prove(stack, run=run), "git-failed")


def test_prove_layer_below_check_failing_is_git_failed_not_not_on_layer_below(stack):
    run = _GitRun(_fail_when(_is_ancestor_call(stack.new[1]), rc=128, err="fatal"))
    result = _prove(stack, run=run)
    _assert_not_proven(result, "git-failed")
    assert result["layers"][1]["onLayerBelow"] is None


def test_prove_git_calls_are_plain_git_argv_in_the_repo(stack):
    run = _GitRun()
    _prove(stack, run=run)
    assert run.calls[0] == ["git", "rev-parse", "--is-shallow-repository"]
    assert ["git", "merge-base", "--is-ancestor", stack.base, stack.vetted[0]] in run.calls
    assert ["git", "rev-list", "--merges", "%s..%s" % (stack.base, stack.new[0])] in run.calls
    assert ["git", "rev-list", "--merges", "%s..%s" % (stack.new[0], stack.new[1])] in run.calls
    assert ["git", "rev-parse", "--verify", stack.new[2] + "^{tree}"] in run.calls
    for argv in run.calls:
        assert argv[0] == "git"
    for kwargs in run.kw:
        assert kwargs["cwd"] == stack.repo and kwargs["timeout"] == sl.GIT_TIMEOUT
        assert kwargs["capture_output"] is True and kwargs["text"] is True


GOOD = ("l1", SHA_A, SHA_B)


@pytest.mark.parametrize("kwargs", [
    dict(repo_root="", base="b", layers=[GOOD]),
    dict(repo_root=None, base="b", layers=[GOOD]),
    dict(repo_root="/x", base="", layers=[GOOD]),
    dict(repo_root="/x", base="-x", layers=[GOOD]),
    dict(repo_root="/x", base="a b", layers=[GOOD]),
    dict(repo_root="/x", base=None, layers=[GOOD]),
    dict(repo_root="/x", base="b", layers=[]),
    dict(repo_root="/x", base="b", layers=None),
    dict(repo_root="/x", base="b", layers=(GOOD,)),
    dict(repo_root="/x", base="b", layers=[("l1", SHA_A)]),
    dict(repo_root="/x", base="b", layers=[("l1", SHA_A, SHA_B, SHA_B)]),
    dict(repo_root="/x", base="b", layers=["l1v"]),
    dict(repo_root="/x", base="b", layers=[("", SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("a b", SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("a:b", SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("-x", SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("a~1", SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[(5, SHA_A, SHA_B)]),
    dict(repo_root="/x", base="b", layers=[GOOD, ("l1", SHA_B, SHA_A)]),
    dict(repo_root="/x", base="b", layers=[("l1", "", SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("l1", "-x", SHA_B)]),
    dict(repo_root="/x", base="b", layers=[("l1", SHA_A, "b c")]),
    dict(repo_root="/x", base="b", layers=[("l1", SHA_A, None)]),
    dict(repo_root="/x", base="b", layers=[GOOD], remote=""),
    dict(repo_root="/x", base="b", layers=[GOOD], remote="-f"),
    dict(repo_root="/x", base="b", layers=[GOOD], remote="a b"),
    dict(repo_root="/x", base="b", layers=[GOOD], remote=None),
    dict(repo_root="/x", base="b", layers=[GOOD], today="2026-11-14"),
])
def test_prove_bad_argument_runs_nothing(kwargs):
    run = _GitRun()
    result = sl.prove(run=run, **kwargs)
    _assert_not_proven(result, "bad-argument")
    assert result["layers"] == [] and result["base"] is None
    assert run.calls == []


def test_prove_layers_may_be_lists_as_well_as_tuples(stack):
    triples = [list(t) for t in _triples(stack)]
    assert _prove(stack, triples)["proven"] is True


# ---------------------------------------------------------------------------------------------
# Command line.
# ---------------------------------------------------------------------------------------------

def _cli(capsys, argv, **kwargs):
    code = sl.main(argv, **kwargs)
    out = capsys.readouterr().out
    assert out.endswith("\n") and out.count("\n") == 1, out
    return code, json.loads(out)


def test_cli_check_local_non_linear_exits_one(stack, capsys):
    argv = ["check", "--repo-root", stack.repo, "--base", stack.base,
            "--layer", "l1", "--layer", "l2", "--layer", "l3"]
    code, result = _cli(capsys, argv, run=_GitRun())
    assert code == 1
    assert result["reason"] == "stack-not-linear"


def test_cli_check_local_linear_exits_zero(stack, capsys):
    argv = ["check", "--repo-root", stack.repo, "--base", stack.base]
    for sha in stack.new:
        argv += ["--layer", sha]
    code, result = _cli(capsys, argv, run=_GitRun())
    assert code == 0
    assert result["ok"] is True and result["linear"] is True


def test_cli_check_rest_linear_and_not_linear(capsys):
    gh = _Gh({11: _rows(2, "1"), 12: [_row(SHA_B, SHA_A, "c" * 40)]})
    code, result = _cli(capsys, ["check", "--repo", REPO, "--pr", "11"], run=gh)
    assert code == 0 and result["linear"] is True
    code, result = _cli(capsys, ["check", "--repo", REPO, "--pr", "11", "--pr", "12"], run=gh)
    assert code == 1 and result["reason"] == "stack-not-linear"
    assert [layer["layer"] for layer in result["layers"]] == [11, 12]


def test_cli_check_rest_unreadable_exits_one(capsys):
    gh = _Gh({11: []}, override=lambda argv: _proc(argv, 1))
    code, result = _cli(capsys, ["check", "--repo", REPO, "--pr", "11"], run=gh)
    assert code == 1 and result["reason"] == "linearity-unreadable"


@pytest.mark.parametrize("argv", [
    ["check"],
    ["check", "--repo", REPO, "--pr", "1", "--repo-root", "/x", "--base", "b", "--layer", "a"],
    ["check", "--repo", REPO, "--pr", "1", "--base", "b"],
    ["check", "--repo-root", "/x"],
    ["check", "--repo", REPO],
    ["check", "--pr", "1"],
    ["check", "--repo", REPO, "--pr", "0"],
    ["check", "--repo-root", "/x", "--base", "b"],
], ids=["neither", "both", "mixed", "root-only", "repo-only", "pr-only", "pr-zero", "no-layer"])
def test_cli_check_needs_exactly_one_form(capsys, argv):
    gh = _Gh({1: _rows(1, "1")})
    code, result = _cli(capsys, argv, run=gh)
    assert code == 1
    assert result["ok"] is False and result["reason"] == "bad-argument"
    assert gh.calls == []


def test_cli_prove_proven_prints_repin_and_push(stack, capsys):
    argv = ["prove", "--repo-root", stack.repo, "--base", stack.base, "--remote", "upstream"]
    for i in range(3):
        argv += ["--layer", stack.branches[i], stack.vetted[i], stack.new[i]]
    code, result = _cli(capsys, argv, run=_GitRun(), today=TODAY)
    assert code == 0
    assert result["proven"] is True and len(result["repin"]) == 3
    assert result["push"][:4] == ["git", "push", "--atomic", "upstream"]
    assert result["repin"][0].startswith("Re-pinned 2026-11-14 (")


def test_cli_prove_refusal_exits_one(stack, capsys):
    argv = ["prove", "--repo-root", stack.repo, "--base", stack.base,
            "--layer", "l1", stack.vetted[0], stack.vetted[0]]
    code, result = _cli(capsys, argv, run=_GitRun(), today=TODAY)
    assert code == 1
    assert result["reason"] == "merge-commit-remains" and result["push"] is None


@pytest.mark.parametrize("argv", [
    [],
    ["bogus"],
    ["prove"],
    ["prove", "--repo-root", "/x", "--base", "b"],
    ["prove", "--repo-root", "/x", "--base", "b", "--layer", "l1", "a"],
    ["check", "--pr", "abc", "--repo", REPO],
    ["check", "--unknown"],
    ["prove", "--help"],
    ["-h"],
])
def test_cli_malformed_is_bad_argument_json_exit_one(capsys, argv):
    run = _GitRun()
    code, result = _cli(capsys, argv, run=run)
    assert code == 1
    assert result["ok"] is False and result["reason"] == "bad-argument"
    assert run.calls == []
    if argv[:1] == ["prove"]:
        assert "proven" in result and result["push"] is None
    else:
        assert "linear" in result


def test_cli_exit_code_is_zero_only_when_ok(stack, capsys):
    # a result that is a refusal exits 1 even though it printed a full JSON result
    argv = ["prove", "--repo-root", stack.repo, "--base", "no-such-ref", "--layer", "l1", "a", "b"]
    code, result = _cli(capsys, argv, run=_GitRun())
    assert code == 1 and result["reason"] == "git-failed"
