"""#1582: every write run that folds carries the size tripwire, or says why it does not.

Invariant: a write run opened with size inputs folds with `sizeTripwire`, counted by
`size_count.collect` on the run's own worktree against the base journaled at open; a write run
opened without them folds with `sizeTripwireAbsent`; a review run carries neither. Computing the
field never raises and never changes the run's `ok`, `reason`, `detail` or `forfeited`."""
import os

# The write-dispatch suite's helpers and its autouse tmp-base/journal-root/uv-absent fixture.
from test_engine_dispatch_write import (  # noqa: F401
    ED,
    FakeRunner,
    _build_ok_stdout,
    _dispatch_write,
    _git,
    _linked_worktree,
    _pin_temp_base_to_tmp_path,
)


def _implementing_runner(files):
    """A fake engine that 'implements' by writing `files` ({relpath: line count}) into cwd."""
    def run(_argv, _prompt, _timeout, _progress_cb, cwd):
        for rel, lines in files.items():
            path = os.path.join(cwd, *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x = 1\n" * lines)
        return _build_ok_stdout(), False, 0, ""
    return FakeRunner([run])


def _head(wt):
    return _git(wt, "rev-parse", "HEAD").stdout.strip()


def _folded_result(run_dir):
    records, _ = ED._journal_read(run_dir)
    return next(r for r in records if r.get("kind") == "run-folded")["result"]


def _opened_record(run_dir):
    records, _ = ED._journal_read(run_dir)
    return next(r for r in records if r.get("kind") == "run-opened")


def _run(tmp_path, files, line=240):
    wt, _main = _linked_worktree(tmp_path)
    sha = _head(wt)
    run_dir = str(tmp_path / "run")
    res = _dispatch_write(
        tmp_path, _implementing_runner(files), cwd=wt, run_dir=run_dir,
        size_base=sha, size_line=line,
    )
    return res, run_dir, sha


# axis: a worktree past the line crosses; the field is the exact count shape and is journaled.
def test_t1_crossed(tmp_path):
    res, run_dir, sha = _run(tmp_path, {"big.py": 241})
    assert res["ok"] is True, res
    expected = {
        "status": "ok", "base": sha, "line": 240, "tripwireCount": 241, "crossed": True,
        "barCount": 241, "deletedFiles": [], "binary": [], "untrackedRepos": [],
    }
    assert res["sizeTripwire"] == expected
    assert _folded_result(run_dir)["sizeTripwire"] == expected
    assert "sizeTripwireAbsent" not in res


# axis: a worktree exactly at the line has not crossed it.
def test_t2_at_the_line(tmp_path):
    res, _run_dir, _sha = _run(tmp_path, {"big.py": 240})
    assert res["sizeTripwire"]["tripwireCount"] == 240
    assert res["sizeTripwire"]["crossed"] is False


# axis: test files do not count toward the tripwire.
def test_t3_tests_do_not_count(tmp_path):
    res, _run_dir, _sha = _run(tmp_path, {"small.py": 10, "tests/test_big.py": 500})
    assert res["sizeTripwire"]["tripwireCount"] == 10
    assert res["sizeTripwire"]["crossed"] is False


# axis: a run opened without size inputs says so, and adds nothing else to the result.
def test_t4_absent(tmp_path, monkeypatch):
    def fold(sub):
        sub.mkdir()
        wt, _main = _linked_worktree(sub)
        return _dispatch_write(
            sub, _implementing_runner({"big.py": 241}), cwd=wt, run_dir=str(sub / "run"),
        )

    res = fold(tmp_path / "a")
    assert "sizeTripwire" not in res
    assert res["sizeTripwireAbsent"] == "size-inputs-not-supplied"
    monkeypatch.setattr(ED, "_fold_size_tripwire", lambda _state: None)
    baseline = fold(tmp_path / "b")
    baseline.pop("sizeTripwireAbsent")
    assert set(res) - {"sizeTripwireAbsent"} == set(baseline)


# axis: each malformed size input refuses by its own token before anything opens.
def test_t5_refusals(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    sha = _head(wt)
    cases = [
        ({"size_base": sha}, "size-inputs-incomplete"),
        ({"size_line": 240}, "size-inputs-incomplete"),
        ({"size_base": sha, "size_line": 0}, "size-line-invalid"),
        ({"size_base": sha, "size_line": -1}, "size-line-invalid"),
        ({"size_base": sha, "size_line": True}, "size-line-invalid"),
        ({"size_base": sha, "size_line": "240"}, "size-line-invalid"),
        ({"size_base": "main", "size_line": 240}, "size-base-not-an-object-id"),
        ({"size_base": "a" * 40, "size_line": 240}, "size-base-unresolvable"),
    ]
    for index, (kwargs, token) in enumerate(cases):
        run_dir = str(tmp_path / ("run-%d" % index))
        fake = FakeRunner([])
        res = _dispatch_write(tmp_path, fake, cwd=wt, run_dir=run_dir, **kwargs)
        assert res["ok"] is False, (kwargs, res)
        assert res["detail"] == token, (kwargs, res)
        assert res["attempts"] == 0 and res["forfeited"] is False and res["terminal"] is True
        assert fake.calls == []
        records, _ = ED._journal_read(run_dir)
        assert not any(r.get("kind") == "run-opened" for r in records), (kwargs, records)


# axis: a continuation with other inputs refuses, active or finished; one with none reuses the journal.
def test_t6_continuation(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    sha = _head(wt)
    active = str(tmp_path / "active")
    _dispatch_write(
        tmp_path, FakeRunner([(_build_ok_stdout(), False, 0, "")]), cwd=wt, run_dir=active,
        size_base=sha, size_line=240, max_wait=0,
    )
    res = _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=active, size_base=sha, size_line=999, max_wait=0,
    )
    assert res["detail"] == "size-inputs-mismatch"
    assert res["attempts"] == 0
    res = _dispatch_write(
        tmp_path, _implementing_runner({"big.py": 241}), cwd=wt, run_dir=active, max_wait=120,
    )
    assert res["ok"] is True, res
    assert res["sizeTripwire"]["line"] == 240
    assert res["sizeTripwire"]["crossed"] is True

    finished = str(tmp_path / "finished")
    first = _dispatch_write(
        tmp_path, _implementing_runner({}), cwd=wt, run_dir=finished,
        size_base=sha, size_line=240,
    )
    assert first["sizeTripwire"]["status"] == "ok"
    res = _dispatch_write(
        tmp_path, FakeRunner([]), cwd=wt, run_dir=finished, size_base=sha, size_line=999,
    )
    assert res["detail"] == "size-inputs-mismatch"
    assert "sizeTripwire" not in res
    replay = _dispatch_write(tmp_path, FakeRunner([]), cwd=wt, run_dir=finished)
    assert replay["sizeTripwire"] == first["sizeTripwire"]


# axis: an unusable count is reported as no count and never changes the run's outcome.
def test_t7_indeterminate(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ED.size_count, "collect", lambda *_a, **_k: {"ok": False, "reason": "git-timeout"},
    )
    res, _run_dir, sha = _run(tmp_path, {"big.py": 241})
    assert res["ok"] is True
    assert res["sizeTripwire"] == {
        "status": "indeterminate", "base": sha, "line": 240, "reason": "git-timeout"}

    def boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(ED.size_count, "collect", boom)
    sub = tmp_path / "raised"
    sub.mkdir()
    res, _run_dir, sha = _run(sub, {"big.py": 241})
    assert res["ok"] is True
    assert res["sizeTripwire"] == {
        "status": "indeterminate", "base": sha, "line": 240, "reason": "count-raised"}


# axis: a failed run still gets the field, and its outcome is untouched.
def test_forfeited_write_run_still_counted(tmp_path):
    wt, _main = _linked_worktree(tmp_path)
    sha = _head(wt)

    def run(_argv, _prompt, _timeout, _progress_cb, cwd):
        with open(os.path.join(cwd, "big.py"), "w", encoding="utf-8") as fh:
            fh.write("x = 1\n" * 241)
        return "not a report\n", False, 0, ""

    res = _dispatch_write(
        tmp_path, FakeRunner([run, run, run]), cwd=wt, run_dir=str(tmp_path / "run"),
        size_base=sha, size_line=240,
    )
    assert res["ok"] is False
    assert res["sizeTripwire"]["tripwireCount"] == 241
    assert res["sizeTripwire"]["crossed"] is True


# axis: the inputs are journaled once at open, and only when supplied.
def test_t8_open_time_journaling(tmp_path):
    _res, run_dir, sha = _run(tmp_path, {})
    assert _opened_record(run_dir)["sizeTripwireInputs"] == {"base": sha, "line": 240}
    sub = tmp_path / "plain"
    sub.mkdir()
    wt, _main = _linked_worktree(sub)
    plain_dir = str(sub / "run")
    _dispatch_write(sub, _implementing_runner({}), cwd=wt, run_dir=plain_dir)
    assert "sizeTripwireInputs" not in _opened_record(plain_dir)


def _fold_captured(monkeypatch, tmp_path, opened):
    captured = {}
    monkeypatch.setattr(
        ED, "_terminate_run",
        lambda _rd, _state, record_kind, result: captured.update(result) or result,
    )
    ED._fold_run(str(tmp_path), {"opened": opened}, {"ok": True})
    return captured


# axis: a journal opened by an older plugin (no key) folds with the absent marker.
def test_old_journal_folds_absent(tmp_path, monkeypatch):
    opened = {"runKind": ED.RUN_KIND_WRITE, "cwd": str(tmp_path)}
    folded = _fold_captured(monkeypatch, tmp_path, opened)
    assert folded["sizeTripwireAbsent"] == "size-inputs-not-supplied"
    assert "sizeTripwire" not in folded


# axis: a review run carries neither key.
def test_review_run_carries_neither(tmp_path, monkeypatch):
    opened = {"runKind": ED.RUN_KIND_REVIEW, "cwd": str(tmp_path)}
    folded = _fold_captured(monkeypatch, tmp_path, opened)
    assert "sizeTripwire" not in folded
    assert "sizeTripwireAbsent" not in folded


# axis: the CLI carries both flags through to the dispatch.
def test_t9_cli(tmp_path):
    sha = "a" * 40
    args = ED.build_parser().parse_args([
        "dispatch-write", "--seat", "codex:implementer", "--prompt-path", "p.txt",
        "--cwd", str(tmp_path), "--run-dir", str(tmp_path / "run"),
        "--size-base", sha, "--size-line", "240",
    ])
    assert args.size_base == sha
    assert args.size_line == 240
