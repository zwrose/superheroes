"""Part 1 of C6-WO-B: the reviewer pass never reaches a child of the runner, on any machine, whether
or not the session-start scrub ran. Every child inherits from os.environ, so dropping the variable
from the runner's own process at each public entry keeps it out of all of them."""
import os
import sys

import pytest

import cloud_pass
import engine_dispatch
from test_dispatch_review_cloud_history import (
    clean_review_runner, make_shallow_clone, review)
from test_engine_dispatch import FakeRunner, _codex_seat, _valid_prompt

PASS = cloud_pass.PASS_ENV
MARKER = cloud_pass.PASS_MARKER_ENV


class EnvRecordingRunner(FakeRunner):
    """A fake engine that records the process environment it is called under: the injected
    engine takes no env argument, so what it inherits is os.environ at call time."""

    def __init__(self, responses):
        super().__init__(responses)
        self.envs = []

    def __call__(self, *args, **kwargs):
        self.envs.append(dict(os.environ))
        return super().__call__(*args, **kwargs)


def recording_runner():
    return EnvRecordingRunner(clean_review_runner().responses)


def test_engine_does_not_see_the_pass_without_a_session_scrub(tmp_path, monkeypatch):
    # Axis: Part 1 (a). The pass variable is set and nothing scrubbed it; the engine's env lacks it.
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv(PASS, "x")
    clone, shas = make_shallow_clone(tmp_path)
    runner = recording_runner()
    review(tmp_path, clone, shas[0], runner)
    assert len(runner.envs) == 1
    assert PASS not in runner.envs[0]


def test_engine_does_not_see_the_pass_outside_a_cloud_session(tmp_path, monkeypatch):
    # Axis: the drop is cloud-independent: CLAUDE_CODE_REMOTE unset, variable set, engine's env lacks it.
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.setenv(PASS, "x")
    clone, shas = make_shallow_clone(tmp_path)
    # No diff base, so the shallow clone needs no history and the review reaches the engine.
    runner = recording_runner()
    res = review(tmp_path, clone, None, runner)
    assert res["ok"] is True, res
    assert len(runner.envs) == 1
    assert PASS not in runner.envs[0]


def test_the_marker_is_not_dropped(tmp_path, monkeypatch):
    # Axis: control. The sha256 marker is a different variable and stays in the engine's env.
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv(PASS, "x")
    monkeypatch.setenv(MARKER, "abc123")
    clone, shas = make_shallow_clone(tmp_path)
    runner = recording_runner()
    review(tmp_path, clone, shas[0], runner)
    assert runner.envs[0][MARKER] == "abc123"
    assert PASS not in runner.envs[0]


def test_with_no_pass_set_the_engine_env_is_exactly_the_process_env(tmp_path, monkeypatch):
    # Axis: non-cloud and G4. With the variable unset, no key is added or removed: the engine's env
    # equals the environment as it stood before the call, and the drop is a no-op.
    monkeypatch.delenv("CLAUDE_CODE_REMOTE", raising=False)
    monkeypatch.delenv(PASS, raising=False)
    clone, shas = make_shallow_clone(tmp_path)
    runner = recording_runner()
    before = dict(os.environ)
    res = review(tmp_path, clone, None, runner)
    assert res["ok"] is True, res
    assert runner.envs[0] == before
    engine_dispatch._drop_reviewer_pass()
    assert dict(os.environ) == before


def test_git_subprocesses_do_not_see_the_pass(tmp_path, monkeypatch):
    # Axis: Part 1 (b). Every real git call made while the review runs sees an env without the pass.
    # The recorder takes the env kwarg, or os.environ at call time when none is passed, then
    # delegates to the real run; no production seam is involved.
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv(PASS, "x")
    monkeypatch.setenv(MARKER, "abc123")
    clone, shas = make_shallow_clone(tmp_path)
    seen = []
    real_run = engine_dispatch.subprocess.run

    def recorder(argv, *args, **kwargs):
        env = kwargs.get("env")
        seen.append((list(argv), dict(os.environ if env is None else env)))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(engine_dispatch.subprocess, "run", recorder)
    res = review(tmp_path, clone, shas[0], clean_review_runner())
    assert res["ok"] is True, res
    engine_dispatch._git_scrubbed(clone, "rev-parse", "HEAD")
    git_calls = [(argv, env) for argv, env in seen if argv and os.path.basename(argv[0]) == "git"]
    assert len(git_calls) >= 3
    assert all(PASS not in env for _, env in git_calls)
    assert all(env.get(MARKER) == "abc123" for _, env in git_calls)


def test_run_child_supervisor_does_not_see_the_pass_on_the_detached_path(tmp_path, monkeypatch):
    # Axis: Part 1 (c). The detached path spawns the run-child supervisor with Popen; its env lacks
    # the pass. The recorder delegates to the real Popen but swaps the supervisor's argv for a
    # no-op interpreter, so no real engine ever starts.
    monkeypatch.setenv("CLAUDE_CODE_REMOTE", "true")
    monkeypatch.setenv(PASS, "x")
    monkeypatch.setenv(MARKER, "abc123")
    clone, shas = make_shallow_clone(tmp_path)
    seen = []
    real_popen = engine_dispatch.subprocess.Popen

    def recorder(argv, *args, **kwargs):
        env = kwargs.get("env")
        seen.append((list(argv), dict(os.environ if env is None else env)))
        if "run-child" in argv:
            argv = [sys.executable, "-c", "pass"]
        return real_popen(argv, *args, **kwargs)

    monkeypatch.setattr(engine_dispatch.subprocess, "Popen", recorder)
    res = engine_dispatch.dispatch_review(
        seat=_codex_seat(),
        prompt_path=_valid_prompt(tmp_path), repo_root=clone,
        diff_base=shas[0], run_dir=str(tmp_path / "run"), max_wait=2, order_id="scrub-detached")
    supervisors = [env for argv, env in seen if "run-child" in argv]
    assert supervisors, (res, [argv for argv, _ in seen])
    assert all(PASS not in env for env in supervisors)
    assert all(env.get(MARKER) == "abc123" for env in supervisors)


@pytest.mark.parametrize("entry", ["dispatch_poll", "dispatch_abandon"])
def test_poll_and_abandon_entries_drop_the_pass(tmp_path, monkeypatch, entry):
    # Axis: the other library entries drop the pass first, even when they refuse the run dir.
    monkeypatch.setenv(PASS, "x")
    getattr(engine_dispatch, entry)(str(tmp_path / "no-such-run"))
    assert PASS not in os.environ


def test_dispatch_write_entry_drops_the_pass(tmp_path, monkeypatch):
    # Axis: dispatch_write drops the pass first, even when it refuses the call.
    monkeypatch.setenv(PASS, "x")
    engine_dispatch.dispatch_write(cwd=str(tmp_path))
    assert PASS not in os.environ


def test_main_drops_the_pass_before_anything_else(tmp_path, monkeypatch, capsys):
    # Axis: every CLI subcommand goes through main, so main drops the pass first, including on the
    # dropped-flags refusal branch and for an unknown run dir.
    monkeypatch.setenv(PASS, "x")
    engine_dispatch.main(["dispatch-poll", "--run-dir", str(tmp_path)])
    capsys.readouterr()
    assert PASS not in os.environ
