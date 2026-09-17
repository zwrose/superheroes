import importlib
import os
import subprocess
import sys
import textwrap

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


def _subprocess_certify_script(session_dir):
    return textwrap.dedent(
        """
import importlib
import sys

LIB = %(lib)r
SESSION = %(session)r
FORBIDDEN = frozenset(("round_driver", "round_phases", "round_records"))

class _ForbiddenFinder:
    def find_module(self, fullname, path=None):
        if fullname in FORBIDDEN:
            return self
        return None

    def load_module(self, fullname):
        raise ImportError("forbidden import blocked: %%s" %% fullname)

if LIB not in sys.path:
    sys.path.insert(0, LIB)
sys.meta_path.insert(0, _ForbiddenFinder())

import round_certification as rc

receipt, refusal = rc.certify(SESSION)
if refusal is not None:
    raise SystemExit(2)
if receipt is None:
    raise SystemExit(3)
"""
        % {"lib": _LIB, "session": session_dir}
    )


def _run_subprocess_certify(session_dir):
    return subprocess.run(
        [sys.executable, "-B", "-c", _subprocess_certify_script(session_dir)],
        capture_output=True,
        text=True,
    )


def test_certify_subprocess_with_forbidden_modules_unimportable(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer"}],
    )
    result = _run_subprocess_certify(session_dir)
    assert result.returncode == 0, result.stdout + result.stderr


def test_module_source_has_no_forbidden_driver_imports():
    _assert_no_forbidden_imports(_module_source())


def test_certify_runs_without_importing_driver_modules(tmp_path):
    session_dir = write_session(
        tmp_path,
        envelopes=[{"seat": "code-reviewer"}],
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
