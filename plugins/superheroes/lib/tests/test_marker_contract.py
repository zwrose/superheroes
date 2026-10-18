"""Marker contract — the scope-marker writers share one sidecar directory, and the build-lane
writer carries every key its reader, the review record, reads (#624)."""
import importlib.util
import os
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BL = _load("build_lane")
RD = _load("round_driver")
RR = _load("review_record")


def test_sidecar_directory_name_agrees():
    assert BL.SIDECAR_DIRNAME == RD.SIDECAR_DIRNAME


def _init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    return str(repo)


def test_build_lane_writer_carries_every_key_the_review_record_reads(tmp_path):
    declared = BL.declare(_init_repo(tmp_path), "full", "624")
    assert declared["ok"]
    assert {"schema", "lane", "issue", "branch"} <= set(declared["marker"])
    assert RR._lane_marker(declared["marker"]["repoRoot"])["branch"] == declared["marker"]["branch"]
