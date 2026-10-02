"""Tests for the size count's lockfile and sizeExclude exclusions (#1583).

Token literals are spelled out as strings on purpose: a test that reaches them through the
module constants stays green under any value (rubric/bite-proof.md, external-contract constant).

Detector axes (bite-proof):
- test_lockfile_* / test_literal_lockfile_set — exclusion: lockfiles leave both counts and are listed
- test_glob_* — exclusion: calibration globs leave both counts and are listed
- test_absent_key_identity / test_declared_empty — preservation: no key, no change to the output
- test_collect_* / test_edge_* — refusal and precedence at the collect and count chokepoints
"""
import json
import os
import subprocess

import pytest

import core_md
import mode_registry
import size_count

_FACTS = {
    "verifyCommand": "npm test",
    "stackTags": ["node"],
    "threatModel": "single-user",
    "patterns": "- x: a.ts:1",
}

_ACCEPTED_GLOB = "a repo-relative glob, no leading /"


def _lines(n):
    return "".join("line %d\n" % i for i in range(n))


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def _init_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True, capture_output=True)
    _git(root, "remote", "add", "origin", "git@github.com:o/r.git")
    return root


def _apply(root, files):
    for rel, content in files.items():
        path = root / rel
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c")


def _build(tmp_path, base, head):
    """Commit ``base``, then ``head`` on top (None deletes). Returns (repo, base sha)."""
    root = _init_repo(tmp_path)
    _apply(root, base)
    sha = _git(root, "rev-parse", "HEAD")
    _apply(root, head)
    return root, sha


def _store(tmp_path):
    return str(tmp_path / "store")


def _calibrate(tmp_path, repo, block):
    """Write core.md into the tmp store (global mode, so never part of the counted diff)."""
    store = _store(tmp_path)
    mode_registry.write_registry(str(repo), mode_registry.GLOBAL, "rk", root=store)
    core_md.write(str(repo), dict(_FACTS), "confirmed", root=store, now="2026-06-26")
    path = core_md.core_path(str(repo), store)
    assert not path.startswith(str(repo))
    text = open(path).read()
    inner = core_md._JSON_BLOCK.search(text).group(1)
    data = json.loads(inner)
    data.update(block)
    open(path, "w").write(text.replace(inner, json.dumps(data, indent=2)))


def _no_core(tmp_path, repo):
    mode_registry.write_registry(str(repo), mode_registry.GLOBAL, "rk", root=_store(tmp_path))


def _collect(tmp_path, repo, base, **kw):
    return size_count.collect(str(repo), base, root=_store(tmp_path), **kw)


# --- the lockfile list ----------------------------------------------------------------------

def test_literal_lockfile_set():
    # axis: the one home of the lockfile list is exactly these twelve names
    assert size_count.LOCKFILE_NAMES == frozenset({
        "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "uv.lock", "poetry.lock", "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "composer.lock",
        "go.sum",
    })


@pytest.mark.parametrize("path", [
    "package-lock.json", "web/yarn.lock", "a/b/c/Cargo.lock", "go.sum", "web\\pnpm-lock.yaml",
], ids=repr)
def test_is_lockfile_true(path):
    assert size_count.is_lockfile(path) is True


@pytest.mark.parametrize("path", [
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "Gemfile", "Yarn.lock",
    "package-lock.json.bak", "yarn.lock/x.txt", "my-yarn.lock", "docs/uv.lock.md",
], ids=repr)
def test_is_lockfile_false(path):
    # axis: a manifest, a near-miss name, or a lockfile name used as a directory is not a lockfile
    assert size_count.is_lockfile(path) is False


# --- DoD 1: lockfiles -----------------------------------------------------------------------

def test_lockfile_left_out_of_both_counts(tmp_path):
    # axis: DoD 1 a lockfile counts toward neither number and is listed; its manifest still counts
    repo, base = _build(
        tmp_path,
        {"package.json": "a\n", "README.md": "r\n"},
        {"package.json": "a\nb\nc\nd\n", "package-lock.json": _lines(40)},
    )
    out = _collect(tmp_path, repo, base)
    assert out["ok"] is True
    assert out["tripwireCount"] == 3
    assert out["barCount"] == 3
    assert out["lockfilesExcluded"] == [{"path": "package-lock.json", "lines": 40}]
    assert "pathsExcluded" not in out


def test_lockfile_nested_is_excluded(tmp_path):
    # axis: matching is on the base name at any depth
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"web/yarn.lock": _lines(7), "src/x.py": _lines(2)},
    )
    out = _collect(tmp_path, repo, base)
    assert out["tripwireCount"] == 2
    assert out["barCount"] == 2
    assert out["lockfilesExcluded"] == [{"path": "web/yarn.lock", "lines": 7}]


def test_lockfile_counts_added_plus_deleted(tmp_path):
    # axis: the listed line count is additions plus deletions
    repo, base = _build(
        tmp_path,
        {"Cargo.lock": _lines(10), "README.md": "r\n"},
        {"Cargo.lock": _lines(4) + "changed\n"},
    )
    out = _collect(tmp_path, repo, base)
    assert out["tripwireCount"] == 0
    assert out["lockfilesExcluded"] == [{"path": "Cargo.lock", "lines": 7}]


def test_lockfiles_sorted_by_path(tmp_path):
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"z/yarn.lock": _lines(1), "a/uv.lock": _lines(2), "go.sum": _lines(3)},
    )
    out = _collect(tmp_path, repo, base)
    assert out["lockfilesExcluded"] == [
        {"path": "a/uv.lock", "lines": 2},
        {"path": "go.sum", "lines": 3},
        {"path": "z/yarn.lock", "lines": 1},
    ]


# --- DoD 2: sizeExclude globs ---------------------------------------------------------------

def test_glob_left_out_of_both_counts(tmp_path):
    # axis: DoD 2 a path matching a calibration glob counts toward neither number and is listed
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"docs/a/b.md": _lines(5), "src/x.py": _lines(2)},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": ["docs/**"]})
    out = _collect(tmp_path, repo, base)
    assert out["ok"] is True
    assert out["tripwireCount"] == 2
    assert out["barCount"] == 2
    assert out["pathsExcluded"] == [{"path": "docs/a/b.md", "lines": 5, "glob": "docs/**"}]
    assert "lockfilesExcluded" not in out


def test_glob_not_declared_counts_everything(tmp_path):
    # axis: the same diff with no calibration counts the docs path
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"docs/a/b.md": _lines(5), "src/x.py": _lines(2)},
    )
    _no_core(tmp_path, repo)
    out = _collect(tmp_path, repo, base)
    assert out["tripwireCount"] == 7
    assert out["barCount"] == 7
    assert "pathsExcluded" not in out


def test_glob_star_crosses_slash():
    rows = [(3, 0, "a/b/c/gen.ts"), (1, 0, "src/x.py")]
    out = size_count.count(rows, set(), size_exclude=["*.ts"])
    assert out["tripwireCount"] == 1
    assert out["pathsExcluded"] == [{"path": "a/b/c/gen.ts", "lines": 3, "glob": "*.ts"}]


def test_glob_match_is_case_sensitive():
    out = size_count.count([(3, 0, "docs/A.md")], set(), size_exclude=["DOCS/**"])
    assert out["tripwireCount"] == 3
    assert out["pathsExcluded"] == []


def test_glob_backslash_path_is_normalized():
    out = size_count.count([(3, 0, "docs\\a.md")], set(), size_exclude=["docs/**"])
    assert out["tripwireCount"] == 0
    assert out["pathsExcluded"] == [{"path": "docs\\a.md", "lines": 3, "glob": "docs/**"}]


def test_glob_lines_are_added_plus_deleted():
    out = size_count.count([(3, 4, "docs/a.md")], set(), size_exclude=["docs/**"])
    assert out["pathsExcluded"] == [{"path": "docs/a.md", "lines": 7, "glob": "docs/**"}]


def test_paths_excluded_sorted_by_path():
    rows = [(1, 0, "docs/z.md"), (2, 0, "docs/a.md")]
    out = size_count.count(rows, set(), size_exclude=["docs/**"])
    assert [item["path"] for item in out["pathsExcluded"]] == ["docs/a.md", "docs/z.md"]


# --- the absent-key identity and the declared-empty key --------------------------------------

def test_absent_key_identity(tmp_path):
    # axis: with no calibration and no lockfile row the output is today's, key for key
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"src/x.py": _lines(2), "README.md": None},
    )
    _no_core(tmp_path, repo)
    out = _collect(tmp_path, repo, base)
    head = out.pop("head")
    assert out.pop("base") == base
    assert head == "HEAD"
    assert json.dumps(out, sort_keys=True) == (
        '{"barCount": 2, "binary": [], "deletedFiles": [{"lines": 1, "path": "README.md"}], '
        '"ok": true, "tripwireCount": 2}'
    )


def test_absent_key_identity_in_count():
    out = size_count.count([(2, 0, "src/x.py")], set())
    assert json.dumps(out, sort_keys=True) == (
        '{"barCount": 2, "binary": [], "deletedFiles": [], "tripwireCount": 2}'
    )


def test_declared_empty(tmp_path):
    # axis: a key declared [] lists nothing and changes no other key
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"docs/a/b.md": _lines(5), "src/x.py": _lines(2), "README.md": None},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": []})
    out = _collect(tmp_path, repo, base)
    assert out["pathsExcluded"] == []
    assert out["tripwireCount"] == 7
    assert out["barCount"] == 7
    assert out["deletedFiles"] == [{"path": "README.md", "lines": 1}]
    assert out["binary"] == []
    assert sorted(out) == [
        "barCount", "base", "binary", "deletedFiles", "head", "ok", "pathsExcluded",
        "tripwireCount",
    ]


# --- collect refusals ------------------------------------------------------------------------

def test_collect_malformed_refuses_with_items(tmp_path):
    # axis: edge 2 a malformed calibration refuses the count and carries the reader's items
    repo, base = _build(tmp_path, {"README.md": "r\n"}, {"src/x.py": _lines(2)})
    _calibrate(tmp_path, repo, {"sizeExclude": ["ok", "/abs"]})
    out = _collect(tmp_path, repo, base)
    assert out == {
        "ok": False,
        "reason": "size-exclude-malformed",
        "malformed": [
            {"index": 1, "reason": "size-exclude-entry-absolute", "accepted": _ACCEPTED_GLOB},
        ],
    }


def test_edge_reader_raises_is_unreadable(tmp_path, monkeypatch):
    # axis: edge 1 a reader that raises refuses as unreadable, never raises out of collect
    repo, base = _build(tmp_path, {"README.md": "r\n"}, {"src/x.py": _lines(2)})

    def boom(cwd, root=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(core_md, "read_size_exclude", boom)
    out = _collect(tmp_path, repo, base)
    assert out == {
        "ok": False,
        "reason": "size-exclude-unreadable",
        "detail": "RuntimeError: boom",
    }


def test_edge_reader_unreadable_core_md(tmp_path):
    # axis: edge 3 a core.md the reader cannot parse refuses as unreadable
    repo, base = _build(tmp_path, {"README.md": "r\n"}, {"src/x.py": _lines(2)})
    _calibrate(tmp_path, repo, {"verifyCommand": 42})
    out = _collect(tmp_path, repo, base)
    assert out["ok"] is False
    assert out["reason"] == "size-exclude-unreadable"
    assert out["detail"].startswith("VerifyCommandMalformed")


def test_edge_core_md_absent_counts_as_today(tmp_path):
    # axis: edge 4 no core.md counts every non-test path and adds no pathsExcluded key
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"docs/a/b.md": _lines(5), "src/x.py": _lines(2)},
    )
    _no_core(tmp_path, repo)
    out = _collect(tmp_path, repo, base)
    assert out["ok"] is True
    assert out["tripwireCount"] == 7
    assert "pathsExcluded" not in out


# --- edges 6-11: precedence -----------------------------------------------------------------

def test_edge_lockfile_whole_deleted_is_deleted_files_only(tmp_path):
    # axis: edge 6 a deleted lockfile is listed once, under deletedFiles
    repo, base = _build(
        tmp_path,
        {"yarn.lock": _lines(3), "README.md": "r\n"},
        {"yarn.lock": None, "src/x.py": "alpha\nbeta\n"},
    )
    out = _collect(tmp_path, repo, base)
    assert out["deletedFiles"] == [{"path": "yarn.lock", "lines": 3}]
    assert "lockfilesExcluded" not in out
    assert out["tripwireCount"] == 2


def test_edge_binary_lockfile_is_binary_only(tmp_path):
    # axis: edge 7 a binary lockfile is listed once, under binary
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"bun.lockb": b"\x00\x01\x02\x00bun", "src/x.py": _lines(2)},
    )
    out = _collect(tmp_path, repo, base)
    assert out["binary"] == ["bun.lockb"]
    assert "lockfilesExcluded" not in out
    assert out["tripwireCount"] == 2


def test_edge_lockfile_under_test_dir_is_in_no_list(tmp_path):
    # axis: edge 8 a lockfile under a test directory is skipped as test code
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"tests/yarn.lock": _lines(9), "src/x.py": _lines(2)},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": ["tests/**"]})
    out = _collect(tmp_path, repo, base)
    assert "lockfilesExcluded" not in out
    assert out["pathsExcluded"] == []
    assert out["binary"] == []
    assert out["deletedFiles"] == []
    assert out["tripwireCount"] == 2


def test_edge_lockfile_matching_glob_is_lockfiles_only(tmp_path):
    # axis: edge 9 a lockfile that also matches a glob is listed once, under lockfilesExcluded
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"web/yarn.lock": _lines(6), "src/x.py": _lines(2)},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": ["*.lock"]})
    out = _collect(tmp_path, repo, base)
    assert out["lockfilesExcluded"] == [{"path": "web/yarn.lock", "lines": 6}]
    assert out["pathsExcluded"] == []
    assert out["tripwireCount"] == 2


def test_edge_two_globs_list_once_with_first(tmp_path):
    # axis: edge 10 a path matching two globs is listed once, with the first glob in list order
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"docs/a.md": _lines(4), "src/x.py": _lines(2)},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": ["docs/**", "*.md"]})
    out = _collect(tmp_path, repo, base)
    assert out["pathsExcluded"] == [{"path": "docs/a.md", "lines": 4, "glob": "docs/**"}]
    assert out["tripwireCount"] == 2


def test_edge_bar_exclude_path_matching_glob_is_paths_excluded(tmp_path):
    # axis: edge 11 a bar-excluded path that matches a glob is listed under pathsExcluded only
    repo, base = _build(
        tmp_path,
        {"README.md": "r\n"},
        {"gen/out.json": _lines(8), "src/x.py": _lines(2)},
    )
    _calibrate(tmp_path, repo, {"sizeExclude": ["gen/**"]})
    out = _collect(tmp_path, repo, base, bar_exclude=("gen/out.json",))
    assert out["pathsExcluded"] == [{"path": "gen/out.json", "lines": 8, "glob": "gen/**"}]
    assert out["barExcluded"] == []
    assert out["tripwireCount"] == 2
    assert out["barCount"] == 2


# --- count() precedence on pure rows --------------------------------------------------------

def test_count_precedence_on_pure_rows():
    rows = [
        (5, 0, "tests/yarn.lock"),
        (None, None, "bun.lockb"),
        (0, 3, "old/go.sum"),
        (6, 1, "web/yarn.lock"),
        (4, 0, "gen/yarn.lock"),
        (2, 2, "gen/a.ts"),
        (8, 0, "gen/b.ts"),
        (1, 0, "src/x.py"),
        (9, 0, "keep/out.json"),
    ]
    out = size_count.count(
        rows,
        {"old/go.sum"},
        bar_exclude=("gen/b.ts", "keep/out.json"),
        size_exclude=["gen/**", "web/**"],
    )
    assert out == {
        "tripwireCount": 10,
        "barCount": 1,
        "deletedFiles": [{"path": "old/go.sum", "lines": 3}],
        "binary": ["bun.lockb"],
        "barExcluded": ["keep/out.json"],
        "lockfilesExcluded": [
            {"path": "gen/yarn.lock", "lines": 4},
            {"path": "web/yarn.lock", "lines": 7},
        ],
        "pathsExcluded": [
            {"path": "gen/a.ts", "lines": 4, "glob": "gen/**"},
            {"path": "gen/b.ts", "lines": 8, "glob": "gen/**"},
        ],
    }


def test_count_lockfile_applies_with_no_size_exclude():
    out = size_count.count([(3, 1, "yarn.lock"), (2, 0, "src/x.py")], set())
    assert out["tripwireCount"] == 2
    assert out["lockfilesExcluded"] == [{"path": "yarn.lock", "lines": 4}]
    assert "pathsExcluded" not in out
