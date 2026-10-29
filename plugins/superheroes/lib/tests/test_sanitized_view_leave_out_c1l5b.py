"""C1-L5b (#2243) WO-F: engine reviewers get the patch without proven copies.

`dispatch-review --leave-out-file` names changed files that the change proves byte-for-byte copies of
a named source; the sanitized view's review patch leaves their sections out. Real git, no network,
no engine.
"""
import json
import os
import subprocess
import sys

import pytest

_LIB = os.path.join(os.path.dirname(__file__), "..")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import engine_dispatch as ED
import sanitized_view as sv
from test_engine_dispatch import FakeRunner, _codex_seat, _valid_prompt

INVALID = "sanitized-view-leave-out-invalid"
NOTICE_SENTENCE = (
    "%d changed file(s) were left out of the review patch because the change proves each one a "
    "byte-for-byte copy of a named source; they are not part of what you review, and their "
    "absence is not a finding.\n"
)

_built = []


@pytest.fixture(autouse=True)
def _pinned_git_and_temp_base(tmp_path, monkeypatch):
    """Pin git config, keep views off the real temp directory, and destroy every view built."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    base = str(tmp_path / "sanitized-temp-base")
    os.makedirs(base, exist_ok=True)
    monkeypatch.setattr(sv.tempfile, "gettempdir", lambda: base)
    _built.clear()
    yield
    for view_path in _built:
        sv.destroy_sanitized_view(view_path)
    assert [n for n in os.listdir(base) if n.startswith(sv.SANITIZED_VIEW_DIR_PREFIX)] == []


def _git(repo, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "maintenance.auto=false", "-c", "gc.auto=0",
         "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
         *args],
        capture_output=True, text=True, check=True, env=env)
    return proc.stdout.strip()


def _write(repo, rel, content):
    full = os.path.join(str(repo), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(content)


def _make_change(tmp_path, base_files, head_files, moves=()):
    """A repo with a base commit and a head commit; returns (repo, base oid)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    for rel, content in base_files.items():
        _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")
    base = _git(repo, "rev-parse", "HEAD")
    for old, new in moves:
        _git(repo, "mv", old, new)
    for rel, content in head_files.items():
        _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "head")
    return str(repo), base


def _three_files(tmp_path):
    return _make_change(
        tmp_path, {"README.md": "base\n"},
        {"a.txt": "alpha\n", "b.txt": "bravo\n", "c.txt": "charlie\n"})


def _build(repo, base, **kwargs):
    view = sv.build_sanitized_view(repo, diff_base=base, **kwargs)
    _built.append(view["path"])
    return view


def _patch(view):
    with open(os.path.join(view["path"], view["diffPath"]), "rb") as fh:
        return fh.read()


def _section_paths(patch_bytes):
    sections, spans = sv._split_patch_sections(patch_bytes)
    assert spans == 0
    return [sv._paths_from_diff_section(s) for s in sections]


def _leave_out_file(tmp_path, doc, name="reviewer-leave-out.json"):
    path = tmp_path / name
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return str(path)


def _doc(files):
    return {"schema": "leave-out/1", "files": files}


def test_leave_out_drops_only_the_named_section(tmp_path):
    repo, base = _three_files(tmp_path)
    full = _build(repo, base)
    left = _build(repo, base, leave_out=frozenset({"b.txt"}))
    full_patch, left_patch = _patch(full), _patch(left)
    assert _section_paths(full_patch) == ["a.txt", "b.txt", "c.txt"]
    assert _section_paths(left_patch) == ["a.txt", "c.txt"]
    sections, _ = sv._split_patch_sections(full_patch)
    expected = b"".join(s for s in sections if sv._paths_from_diff_section(s) != "b.txt")
    assert left_patch == expected
    assert left["diffLeftOut"] == ["b.txt"]
    assert left["diffBytes"] == len(left_patch)
    notice = sv.sanitized_view_notice(left)
    assert NOTICE_SENTENCE % 1 in notice
    assert notice.index("The change under review is the patch") < notice.index(NOTICE_SENTENCE % 1)


def test_two_left_out_are_counted_and_listed_sorted(tmp_path):
    repo, base = _three_files(tmp_path)
    left = _build(repo, base, leave_out=frozenset({"c.txt", "a.txt"}))
    assert left["diffLeftOut"] == ["a.txt", "c.txt"]
    assert _section_paths(_patch(left)) == ["b.txt"]
    assert NOTICE_SENTENCE % 2 in sv.sanitized_view_notice(left)


def test_no_leave_out_is_todays_behaviour(tmp_path):
    repo, base = _three_files(tmp_path)
    today = _build(repo, base)
    explicit_none = _build(repo, base, leave_out=None)
    assert _patch(explicit_none) == _patch(today)
    assert _section_paths(_patch(today)) == ["a.txt", "b.txt", "c.txt"]
    assert sv.sanitized_view_notice(explicit_none) == sv.sanitized_view_notice(today)
    assert "left out" not in sv.sanitized_view_notice(today)
    assert today["diffLeftOut"] is None and explicit_none["diffLeftOut"] is None


def test_no_diff_base_has_no_patch_and_no_left_out(tmp_path):
    repo, _base = _three_files(tmp_path)
    view = sv.build_sanitized_view(repo, leave_out=frozenset({"b.txt"}))
    _built.append(view["path"])
    assert view["diffPath"] is None and view["diffLeftOut"] is None
    assert "left out" not in sv.sanitized_view_notice(view)


MALFORMED = [
    pytest.param("not json at all", id="not-json"),
    pytest.param("", id="empty-file"),
    pytest.param([], id="top-level-list"),
    pytest.param({"schema": "leave-out/2", "files": []}, id="wrong-schema"),
    pytest.param({"files": []}, id="missing-schema"),
    pytest.param({"schema": "leave-out/1"}, id="missing-files"),
    pytest.param({"schema": "leave-out/1", "files": [], "extra": 1}, id="extra-key"),
    pytest.param({"schema": "leave-out/1", "files": "a.txt"}, id="files-not-a-list"),
    pytest.param(_doc([None]), id="entry-null"),
    pytest.param(_doc([3]), id="entry-int"),
    pytest.param(_doc([""]), id="entry-empty"),
    pytest.param(_doc(["   "]), id="entry-blank"),
    pytest.param(_doc(["/etc/passwd"]), id="entry-absolute"),
    pytest.param(_doc(["a/b\\c.txt"]), id="entry-backslash"),
    pytest.param(_doc(["a.txt", "a.txt"]), id="entry-duplicate"),
]


def test_loader_accepts_a_well_formed_file(tmp_path):
    path = _leave_out_file(tmp_path, _doc(["a.txt", "dir/b.txt", "a..b", "..hidden", "x/..y/z"]))
    assert sv.load_leave_out_file(path) == frozenset(
        {"a.txt", "dir/b.txt", "a..b", "..hidden", "x/..y/z"})
    assert sv.load_leave_out_file(_leave_out_file(tmp_path, _doc([]), "empty.json")) == frozenset()


@pytest.mark.parametrize("doc", MALFORMED)
def test_loader_refuses_each_malformed_shape(tmp_path, doc):
    # axis: the loader refuses every malformed shape with the one invalid-file detail, so no bad file reaches a reviewer's patch
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.load_leave_out_file(_leave_out_file(tmp_path, doc))
    assert exc.value.detail == INVALID


@pytest.mark.parametrize("entry", ["..", "../x.txt", "a/../b.txt", "a/b/.."])
def test_loader_refuses_a_dotdot_segment(tmp_path, entry):
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.load_leave_out_file(_leave_out_file(tmp_path, _doc([entry])))
    assert exc.value.detail == INVALID


def test_loader_refuses_a_missing_and_an_unreadable_file(tmp_path):
    for path in (str(tmp_path / "absent.json"), str(tmp_path)):
        with pytest.raises(sv.SanitizedViewError) as exc:
            sv.load_leave_out_file(path)
        assert exc.value.detail == INVALID


def test_loader_refuses_bytes_that_are_not_utf8(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b'{"schema": "leave-out/1", "files": ["\xff"]}')
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.load_leave_out_file(str(path))
    assert exc.value.detail == INVALID


def test_every_changed_file_left_out_is_fully_withheld(tmp_path):
    repo, base = _three_files(tmp_path)
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, diff_base=base, leave_out=frozenset({"a.txt", "b.txt", "c.txt"}))
    assert exc.value.detail == "sanitized-view-diff-fully-withheld"


def test_only_survivor_left_out_beside_a_stripped_path_is_fully_withheld(tmp_path):
    repo, base = _make_change(
        tmp_path, {"README.md": "base\n"}, {"a.txt": "alpha\n", "CLAUDE.md": "config\n"})
    with pytest.raises(sv.SanitizedViewError) as exc:
        sv.build_sanitized_view(repo, diff_base=base, leave_out=frozenset({"a.txt"}))
    assert exc.value.detail == "sanitized-view-diff-fully-withheld"


def test_a_listed_path_not_in_the_change_has_no_effect(tmp_path):
    repo, base = _three_files(tmp_path)
    plain = _build(repo, base)
    ignored = _build(repo, base, leave_out=frozenset({"nope.txt", "README.md", "dir/gone.txt"}))
    assert _patch(ignored) == _patch(plain)
    assert ignored["diffLeftOut"] == []
    assert sv.sanitized_view_notice(ignored) == sv.sanitized_view_notice(plain)


def test_a_left_out_stripped_config_path_is_not_staged_anywhere(tmp_path):
    repo, base = _make_change(
        tmp_path, {"README.md": "base\n"}, {"a.txt": "alpha\n", "CLAUDE.md": "config line\n"})
    plain = _build(repo, base)
    assert plain["configDiffPath"] is not None and plain["diffWithheldCount"] == 1
    left = _build(repo, base, leave_out=frozenset({"CLAUDE.md"}))
    assert left["diffLeftOut"] == ["CLAUDE.md"]
    assert left["configDiffPath"] is None and left["configDiffBytes"] is None
    assert left["diffWithheldCount"] == 0
    assert not os.path.exists(os.path.join(left["path"], sv.CONFIG_CHANGES_FILE_NAME))
    assert b"config line" not in _patch(left)
    assert _patch(left) == _patch(plain)


def test_a_rename_is_left_out_by_its_head_side_path_only(tmp_path):
    repo, base = _make_change(
        tmp_path, {"old.txt": "moved bytes\n", "keep.txt": "k\n"},
        {"keep.txt": "k2\n"}, moves=[("old.txt", "new.txt")])
    plain = _build(repo, base)
    assert _section_paths(_patch(plain)) == ["keep.txt", "new.txt", "old.txt"]

    head_side = _build(repo, base, leave_out=frozenset({"new.txt"}))
    assert head_side["diffLeftOut"] == ["new.txt"]
    assert _section_paths(_patch(head_side)) == ["keep.txt", "old.txt"]

    base_side = _build(repo, base, leave_out=frozenset({"old.txt"}))
    assert base_side["diffLeftOut"] == []
    assert _patch(base_side) == _patch(plain)


def test_the_sanitized_view_receipt_key_set_is_unchanged(tmp_path):
    repo, base = _three_files(tmp_path)
    left = _build(repo, base, leave_out=frozenset({"b.txt"}))
    assert "diffLeftOut" in left
    receipt = ED._sanitized_view_receipt(left)
    assert set(receipt) == {
        "strategy", "stripped", "strippedCount", "headSha", "sourceDirty", "buildSeconds",
        "bytes", "fileCount", "diffBase", "diffPath", "diffBytes", "diffWithheldCount",
        "configDiffPath", "configDiffBytes", "prBodyPath", "prBodyBytes",
    }


def _clean_review_runner():
    return FakeRunner([(json.dumps({"findings": [], "investigated": ["a.txt"]}), False, 0, "")])


def _recording_build_view(seen):
    def build_view(repo_root, **kwargs):
        view = sv.build_sanitized_view(repo_root, **kwargs)
        _built.append(view["path"])
        seen.append({
            "kwargs": dict(kwargs),
            "patch": _patch(view) if view["diffPath"] else None,
            "diffLeftOut": view["diffLeftOut"],
        })
        return view
    return build_view


def test_dispatch_review_threads_the_leave_out_file_into_the_view(tmp_path):
    repo, base = _three_files(tmp_path)
    leave_out_path = _leave_out_file(tmp_path, _doc(["b.txt", "not-in-change.txt"]))
    seen = []
    res = ED.dispatch_review(
        seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=repo,
        run_engine=_clean_review_runner(), build_view=_recording_build_view(seen),
        diff_base=base, leave_out_file=leave_out_path)
    assert res["ok"] is True, res
    assert len(seen) == 1
    assert seen[0]["kwargs"]["leave_out"] == frozenset({"b.txt", "not-in-change.txt"})
    assert _section_paths(seen[0]["patch"]) == ["a.txt", "c.txt"]
    assert seen[0]["diffLeftOut"] == ["b.txt"]
    assert "diffLeftOut" not in res["sanitizedView"]


def test_dispatch_review_without_diff_base_loads_then_ignores_a_well_formed_file(tmp_path):
    repo, _base = _three_files(tmp_path)
    leave_out_path = _leave_out_file(tmp_path, _doc(["b.txt"]))
    seen = []
    res = ED.dispatch_review(
        seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=repo,
        run_engine=_clean_review_runner(), build_view=_recording_build_view(seen),
        leave_out_file=leave_out_path)
    assert res["ok"] is True, res
    assert seen[0]["patch"] is None and seen[0]["diffLeftOut"] is None


def test_dispatch_review_without_a_leave_out_file_passes_no_leave_out(tmp_path):
    repo, base = _three_files(tmp_path)
    seen = []
    res = ED.dispatch_review(
        seat=_codex_seat(), prompt_path=_valid_prompt(tmp_path), repo_root=repo,
        run_engine=_clean_review_runner(), build_view=_recording_build_view(seen),
        diff_base=base)
    assert res["ok"] is True, res
    assert "leave_out" not in seen[0]["kwargs"]
    assert _section_paths(seen[0]["patch"]) == ["a.txt", "b.txt", "c.txt"]


@pytest.mark.parametrize("with_diff_base", [True, False])
def test_cli_refuses_a_malformed_leave_out_file_before_any_spawn(
        tmp_path, monkeypatch, capsys, with_diff_base):
    repo, base = _three_files(tmp_path)
    bad = _leave_out_file(tmp_path, _doc(["../escape.txt"]))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def forbidden(*_a, **_k):
        raise AssertionError("an engine argv was built after a malformed leave-out file")

    monkeypatch.setattr(ED.engine_adapter, "build_argv_result", forbidden)
    argv = [
        "dispatch-review", "--seat", json.dumps(_codex_seat()),
        "--prompt-path", _valid_prompt(tmp_path), "--repo-root", repo,
        "--run-dir", str(run_dir), "--leave-out-file", bad,
    ]
    if with_diff_base:
        argv += ["--diff-base", base]
    assert ED.main(argv) == 1
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result["ok"] is False
    assert result["detail"] == INVALID
    assert result["attempts"] == 0
    assert result["forfeited"] is False
    assert result["terminal"] is True


def test_the_cli_declares_the_leave_out_flag():
    sub = ED.build_parser()._subparsers._actions[-1].choices["dispatch-review"]  # noqa: SLF001
    flag = [a for a in sub._actions if a.dest == "leave_out_file"]  # noqa: SLF001
    assert len(flag) == 1 and flag[0].default is None
