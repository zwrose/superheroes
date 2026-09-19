# plugins/superheroes/eval/tests/test_escalation_eval.py
import importlib.util
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))
_ESC_PATH = os.path.join(_REPO_ROOT, "plugins/superheroes/lib/escalation.py")
_FIX = os.path.join(_HERE, "..", "escalation", "expected.json")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ESC = _load(_ESC_PATH, "architect_escalation_eval")


def _fixture():
    with open(_FIX, encoding="utf-8") as fh:
        return json.load(fh)


def test_route_fixture_exact_match():
    for case in _fixture()["route"]:
        assert ESC.route(case["axes"]) == case["mode"], case

def test_classify_fixture_exact_match():
    for case in _fixture()["classify"]:
        assert ESC.classify_floor(case["action"]) == case["on_floor"], case

def test_guard_fixture_retired():
    assert "guard" not in _fixture()

def test_safety_machinery_tuple_retired():
    assert not hasattr(ESC, "SAFETY_MACHINERY")
