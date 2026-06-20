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

def test_guard_fixture_exact_match():
    band = [os.path.join(_REPO_ROOT, "plugins", "superheroes")]
    for case in _fixture()["guard"]:
        path = os.path.join(_REPO_ROOT, case["path"])
        assert (not ESC.is_safety_machinery(path, band)) == case["allow"], case

def test_guard_fixture_covers_every_safety_member():
    # Anti-drift: the eval fixture's refuse-cases must cover EVERY SAFETY_MACHINERY member, so a
    # future 10th member can't be pinned in the unit test yet silently uncovered by the eval gate.
    refused = {os.path.basename(c["path"]) for c in _fixture()["guard"] if c["allow"] is False}
    missing = set(ESC.SAFETY_MACHINERY) - refused
    assert not missing, missing
