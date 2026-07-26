"""Shared guardian census — git ls-files intersected with on-disk files."""
import os
from types import SimpleNamespace

import pytest

import guardian_census as gcensus
import guardian_tools as gt


class Tools:
    """Injected ctx['run'] seam stub for git ls-files."""

    def __init__(self, *, lsfiles=(), fail_markers=None):
        self.lsfiles = list(lsfiles)
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
        if os.path.basename(argv[0]) == "git" and "ls-files" in argv:
            return self._R("".join(p + "\0" for p in self.lsfiles))
        return self._R("", 0)


def _ctx(cwd, run):
    return {"cwd": str(cwd), "run": run}


def _write(tmp_path, rel, text="x\n"):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return rel


def test_git_failure_returns_none_not_empty_set(tmp_path):
    run = Tools(lsfiles=["a.py"], fail_markers={"ls-files": 128})
    tracked, reason = gcensus.tracked_existing_files(
        _ctx(tmp_path, run), os.path.realpath(str(tmp_path)))
    assert tracked is None
    assert reason
    assert tracked != set()


def test_success_returns_tracked_on_disk_regular_files(tmp_path):
    _write(tmp_path, "keep.py")
    _write(tmp_path, "sub/nested.py")
    run = Tools(lsfiles=["keep.py", "sub/nested.py", "missing.py"])
    tracked, reason = gcensus.tracked_existing_files(
        _ctx(tmp_path, run), os.path.realpath(str(tmp_path)))
    assert reason is None
    assert tracked == {"keep.py", "sub/nested.py"}


def test_missing_on_disk_path_excluded(tmp_path):
    _write(tmp_path, "here.py")
    run = Tools(lsfiles=["here.py", "gone.py"])
    tracked, reason = gcensus.tracked_existing_files(
        _ctx(tmp_path, run), os.path.realpath(str(tmp_path)))
    assert reason is None
    assert "here.py" in tracked
    assert "gone.py" not in tracked


def test_tracked_symlink_to_untracked_target_excluded_by_default(tmp_path):
    _write(tmp_path, "regular.py")
    _write(tmp_path, "untracked_target.py", "secret\n")
    os.symlink("untracked_target.py", str(tmp_path / "link.py"))
    run = Tools(lsfiles=["regular.py", "link.py"])
    cwd = os.path.realpath(str(tmp_path))
    tracked, reason = gcensus.tracked_existing_files(_ctx(tmp_path, run), cwd)
    assert reason is None
    assert tracked == {"regular.py"}


def test_tracked_symlink_included_when_exclude_symlinks_false(tmp_path):
    _write(tmp_path, "untracked_target.py", "secret\n")
    os.symlink("untracked_target.py", str(tmp_path / "link.py"))
    run = Tools(lsfiles=["link.py"])
    cwd = os.path.realpath(str(tmp_path))
    tracked, reason = gcensus.tracked_existing_files(
        _ctx(tmp_path, run), cwd, exclude_symlinks=False)
    assert reason is None
    assert tracked == {"link.py"}


def test_brace_and_arrow_filenames_are_censused(tmp_path):
    """F5: git ls-files -z never emits porcelain rename syntax — do not filter braces."""
    brace_rel = "src/{generated}.py"
    arrow_rel = "weird=>name.ts"
    _write(tmp_path, brace_rel)
    _write(tmp_path, arrow_rel)
    run = Tools(lsfiles=[brace_rel, arrow_rel])
    tracked, reason = gcensus.tracked_existing_files(
        _ctx(tmp_path, run), os.path.realpath(str(tmp_path)))
    assert reason is None
    assert brace_rel in tracked
    assert arrow_rel in tracked


def test_operand_payload_bytes_uses_absolutized_paths(tmp_path):
    cwd = os.path.realpath(str(tmp_path))
    rel_only = sum(len(p.encode("utf-8")) for p in ("a.py", "sub/b.py"))
    absolutized = gcensus.operand_payload_bytes(cwd, ("a.py", "sub/b.py"))
    prefix = len(cwd.encode("utf-8")) + 1
    expected = rel_only + 2 * prefix
    assert absolutized == expected
    assert absolutized > rel_only


def test_max_tracked_operand_bytes_constant_removed():
    assert not hasattr(gcensus, "MAX_TRACKED_OPERAND_BYTES")


def test_argv_operand_budget_bytes_positive_and_below_platform_max(tmp_path):
    repo = os.path.realpath(str(tmp_path))
    fixed = ["vulture", "--min-confidence", "80", "--exclude", "venv"]
    budget = gcensus.argv_operand_budget_bytes(repo, fixed)
    platform_max = os.sysconf("SC_ARG_MAX")
    assert isinstance(budget, int)
    assert budget > 0
    assert budget < platform_max


def test_argv_operand_budget_bytes_larger_fixed_argv_yields_smaller_budget(tmp_path):
    repo = os.path.realpath(str(tmp_path))
    small = ["vulture"]
    large = ["vulture"] + ["--extra-flag"] * 200
    budget_small = gcensus.argv_operand_budget_bytes(repo, small)
    budget_large = gcensus.argv_operand_budget_bytes(repo, large)
    assert budget_large < budget_small


def test_argv_operand_budget_bytes_subtracts_env_term(tmp_path, monkeypatch):
    repo = os.path.realpath(str(tmp_path))
    fixed = ["vulture"]
    baseline = gcensus.argv_operand_budget_bytes(repo, fixed)

    def huge_env(base_env=None, repo=None, **kwargs):
        return {"K" + str(i): "V" * 5000 for i in range(500)}

    monkeypatch.setattr(gt, "sanitized_env", huge_env)
    shrunk = gcensus.argv_operand_budget_bytes(repo, fixed)
    assert shrunk < baseline


def _sysconf_raises_value(_name):
    raise ValueError("bad")


def _sysconf_raises_oserror(_name):
    raise OSError("bad")


@pytest.mark.parametrize(
    "sysconf_side",
    [
        pytest.param(_sysconf_raises_value, id="ValueError"),
        pytest.param(_sysconf_raises_oserror, id="OSError"),
        pytest.param(lambda name: 0, id="zero"),
        pytest.param(lambda name: -1, id="negative"),
        pytest.param(lambda name: "not-int", id="non-int"),
    ],
)
def test_argv_operand_budget_bytes_sysconf_unavailable_uses_fallback(
        tmp_path, monkeypatch, sysconf_side):
    repo = os.path.realpath(str(tmp_path))
    fixed = ["vulture"]
    monkeypatch.setattr(
        os, "sysconf", lambda name: gcensus.FALLBACK_ARG_MAX_BYTES)
    expected = gcensus.argv_operand_budget_bytes(repo, fixed)
    monkeypatch.setattr(os, "sysconf", sysconf_side)
    budget = gcensus.argv_operand_budget_bytes(repo, fixed)
    assert budget == expected


def test_argv_operand_budget_bytes_sysconf_attribute_error(tmp_path, monkeypatch):
    repo = os.path.realpath(str(tmp_path))
    fixed = ["vulture"]

    def missing_sysconf(name):
        raise AttributeError("no sysconf")

    monkeypatch.setattr(
        os, "sysconf", lambda name: gcensus.FALLBACK_ARG_MAX_BYTES)
    expected = gcensus.argv_operand_budget_bytes(repo, fixed)
    monkeypatch.setattr(os, "sysconf", missing_sysconf)
    budget = gcensus.argv_operand_budget_bytes(repo, fixed)
    assert budget == expected


def test_argv_operand_budget_bytes_sanitized_env_raises(tmp_path, monkeypatch):
    repo = os.path.realpath(str(tmp_path))

    def boom(*args, **kwargs):
        raise RuntimeError("env failed")

    monkeypatch.setattr(gt, "sanitized_env", boom)
    budget = gcensus.argv_operand_budget_bytes(repo, ["vulture"])
    assert budget == 0


def test_argv_operand_budget_bytes_oversized_env_yields_zero(tmp_path, monkeypatch):
    repo = os.path.realpath(str(tmp_path))
    platform = gcensus.FALLBACK_ARG_MAX_BYTES
    monkeypatch.setattr(gcensus, "platform_arg_max_bytes", lambda: platform)

    def huge_env(base_env=None, repo=None, **kwargs):
        return {"BIG": "x" * (platform + 1)}

    monkeypatch.setattr(gt, "sanitized_env", huge_env)
    budget = gcensus.argv_operand_budget_bytes(repo, ["vulture"])
    assert budget == 0


def test_argv_operand_budget_bytes_empty_fixed_argv_and_non_ascii(tmp_path):
    repo = os.path.realpath(str(tmp_path))
    budget_empty = gcensus.argv_operand_budget_bytes(repo, [])
    budget_ascii = gcensus.argv_operand_budget_bytes(repo, ["a" * 64])
    budget_unicode = gcensus.argv_operand_budget_bytes(repo, ["é" * 64])
    assert budget_unicode < budget_ascii
    assert budget_unicode < budget_empty
