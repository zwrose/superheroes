"""Static census: background refusal tokens live only in background_outcome.py (#1273)."""
import ast
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import background_outcome  # noqa: E402

_EXEMPT_MODULE = "background_outcome.py"


def _literal_offenders(source_path, banned):
    with open(source_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=source_path)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in banned:
                offenders.append((node.value, node.lineno))
    return offenders


@pytest.mark.parametrize("basename", ["engine_dispatch.py"])
def test_background_refusal_literals_only_in_home(basename):
    banned = background_outcome.ALL_REFUSALS
    path = os.path.join(_LIB, basename)
    offenders = _literal_offenders(path, banned)
    assert offenders == [], offenders
