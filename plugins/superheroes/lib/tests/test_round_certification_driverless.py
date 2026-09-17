import importlib
import os
import sys

import pytest

from round_certification_fixtures import write_session

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FORBIDDEN_IMPORTS = ("round_driver", "round_phases", "round_records")


def _module_source():
    path = os.path.join(_LIB, "round_certification.py")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _assert_no_forbidden_imports(source):
    for name in _FORBIDDEN_IMPORTS:
        assert ("import %s" % name) not in source
        assert ("from %s" % name) not in source


def test_certify_runs_without_importing_driver_modules(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
    )
    saved = {name: sys.modules.pop(name) for name in list(sys.modules) if name in _FORBIDDEN_IMPORTS}
    try:
        if "round_certification" in sys.modules:
            del sys.modules["round_certification"]
        mod = importlib.import_module("round_certification")
        receipt, refusal = mod.certify(session_dir)
        assert refusal is None
        assert receipt["terminalState"] == "certified"
    finally:
        sys.modules.update(saved)


def test_module_source_has_no_forbidden_driver_imports():
    _assert_no_forbidden_imports(_module_source())


def test_bite_added_round_driver_import_fails_forbidden_import_guard():
    poisoned = _module_source().replace(
        "import re\n",
        "import re\nimport round_driver  # bite-proof probe\n",
    )
    with pytest.raises(AssertionError):
        _assert_no_forbidden_imports(poisoned)
