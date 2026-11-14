"""Regression for collection-time Git routing escaping fixture isolation."""

import importlib.util
import os
from pathlib import Path
import subprocess


def test_fixture_git_does_not_restore_collection_time_routing(tmp_path, monkeypatch):
    # axis: the stack-layer fixture's Git helper must target its explicit repository
    # after per-test isolation removes routing inherited during module collection.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    intended = tmp_path / "intended"
    ambient = tmp_path / "ambient"
    for repo in (intended, ambient):
        repo.mkdir()
        subprocess.run(
            ["git", "-C", str(repo), "init", "-q"],
            check=True, capture_output=True, env=env,
        )

    source = Path(__file__).with_name("test_break_it_stack_layers_2463.py")
    with monkeypatch.context() as collection:
        collection.setenv("GIT_DIR", str(ambient / ".git"))
        collection.setenv("GIT_WORK_TREE", str(ambient))
        spec = importlib.util.spec_from_file_location("_stack_git_env_probe", source)
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)

    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    observed = fresh._git(intended, "rev-parse", "--show-toplevel")
    assert Path(observed).resolve() == intended.resolve(), observed
