import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "config_dir.py")


def _load():
    spec = importlib.util.spec_from_file_location("config_dir", _MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cd = _load()


def test_refusal_constants_spelled():
    assert cd.REFUSAL_CONFIG_DIR_UNRESOLVABLE == "config-dir-unusable:unresolvable"
    assert cd.REFUSAL_CONFIG_DIR_NOT_A_DIRECTORY == "config-dir-unusable:not-a-directory"
