"""Regression for collection-time Git routing escaping three fixtures (collector 601-2)."""

import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize("module_file", [
    "test_kept_head_resolver_2393.py",
    "test_size_base_ref_1978.py",
    "test_cloud_dependency_hook_2009.py",
])
def test_fixture_git_env_drops_collection_time_routing(module_file, tmp_path, monkeypatch):
    # axis: the module-level _GIT_ENV a fixture's git calls use must not keep GIT_DIR /
    # GIT_WORK_TREE inherited by the process that collected the module.
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

    source = Path(__file__).with_name(module_file)
    with monkeypatch.context() as collection:
        collection.setenv("GIT_DIR", str(ambient / ".git"))
        collection.setenv("GIT_WORK_TREE", str(ambient))
        spec = importlib.util.spec_from_file_location("_fixture_git_env_probe", source)
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)

    monkeypatch.delenv("GIT_DIR", raising=False)
    monkeypatch.delenv("GIT_WORK_TREE", raising=False)
    assert "GIT_DIR" not in fresh._GIT_ENV and "GIT_WORK_TREE" not in fresh._GIT_ENV
    observed = subprocess.run(
        ["git", "-C", str(intended), "rev-parse", "--show-toplevel"],
        check=True, capture_output=True, text=True, env=fresh._GIT_ENV,
    ).stdout.strip()
    assert Path(observed).resolve() == intended.resolve(), observed
