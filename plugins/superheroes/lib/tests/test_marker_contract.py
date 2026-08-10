"""Marker filename/schema contract — writers and handback_gate reader must agree (#624)."""
import ast
import importlib.util
import inspect
import os
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_LIB, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BL = _load("build_lane")
RD = _load("round_driver")
HG = _load("handback_gate")


def _for_loop_string_keys(validator):
    tree = ast.parse(inspect.getsource(validator))
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "key":
            continue
        if not isinstance(node.iter, ast.Tuple):
            continue
        return frozenset(
            elt.value for elt in node.iter.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
    pytest.fail("could not derive required string keys from %s" % validator.__name__)


def _inline_dict_keys(func, dict_name="marker"):
    tree = ast.parse(inspect.getsource(func))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id != dict_name:
                continue
            if not isinstance(node.value, ast.Dict):
                continue
            return frozenset(
                k.value for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
    pytest.fail("could not derive inline dict keys from %s.%s" % (func.__name__, dict_name))


def _init_repo(tmp_path, branch="main"):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", branch], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "--allow-empty", "-m", "init"], cwd=repo)
    return str(repo)


def test_build_lane_filename_and_schema_agree():
    assert BL.BUILD_LANE_FILE == HG.BUILD_LANE_FILE
    assert BL.BUILD_LANE_SCHEMA == HG.BUILD_LANE_SCHEMA


def test_review_session_filename_and_schema_agree():
    assert RD._REVIEW_SESSION_MARKER == HG.REVIEW_SESSION_FILE
    assert RD._REVIEW_SESSION_SCHEMA == HG.REVIEW_SESSION_SCHEMA


def test_sidecar_directory_name_agrees():
    assert BL.SIDECAR_DIRNAME == RD.SIDECAR_DIRNAME
    assert HG._SIDECAR_DIR == RD.SIDECAR_DIRNAME


def test_build_lane_writer_keys_match_reader_validator(tmp_path):
    repo = _init_repo(tmp_path)
    declared = BL.declare(repo, "full", "624")
    assert declared["ok"]
    writer_keys = frozenset(declared["marker"].keys())
    reader_keys = _for_loop_string_keys(HG._validate_build_lane) | {"schema", "lane"}
    assert writer_keys == reader_keys


def test_review_session_writer_keys_match_reader_validator():
    writer_keys = _inline_dict_keys(RD._bootstrap_review_session_marker)
    reader_keys = _for_loop_string_keys(HG._validate_review_session) | {"schema"}
    assert writer_keys == reader_keys


def test_handback_gate_imports():
    assert HG.BUILD_LANE_FILE
    assert HG.REVIEW_SESSION_FILE
