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
_REQUIRED_BASENAME = "engine_dispatch.py"


def _lib_module_basenames():
    """Every .py directly under lib/, excluding the exempt home."""
    names = []
    for name in os.listdir(_LIB):
        if name == _EXEMPT_MODULE:
            continue
        path = os.path.join(_LIB, name)
        if os.path.isfile(path) and name.endswith(".py"):
            names.append(name)
    names.sort()
    return names


def _validate_census_population(basenames):
    if not basenames:
        raise RuntimeError(
            "Background-refusal census population collapsed: derived zero modules from %s "
            "(expected every .py directly under lib/ except %s)"
            % (_LIB, _EXEMPT_MODULE)
        )
    if _REQUIRED_BASENAME not in basenames:
        raise RuntimeError(
            "Background-refusal census population collapsed: derived population missing "
            "required module %s" % _REQUIRED_BASENAME
        )


_CENSUS_MODULES = _lib_module_basenames()
_validate_census_population(_CENSUS_MODULES)


def _literal_offenders(source_path, banned):
    with open(source_path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=source_path)
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in banned:
                offenders.append((node.value, node.lineno))
    return offenders


@pytest.mark.parametrize("basename", _CENSUS_MODULES)
def test_background_refusal_literals_only_in_home(basename):
    banned = background_outcome.ALL_REFUSALS
    path = os.path.join(_LIB, basename)
    offenders = _literal_offenders(path, banned)
    assert offenders == [], offenders
