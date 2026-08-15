"""Tests for pilot_paths.py — path containment direction and boundary cases.

**Residual blind spots:**

- this census guards only the ``realpath(path).split(os.sep)`` containment idiom and four
  remembered helper names (``_is_inside``, ``_is_same_or_ancestor``, ``_path_parts``,
  ``_path_components``); ``os.path.commonpath`` containment (six call sites across five
  ``lib/`` modules today) and helpers under other names are explicitly out of reach;
- the census proves nothing about whether containment logic is correct, only that the
  idiom is not reimplemented locally outside ``pilot_paths.py``.
"""
import ast
import glob
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_paths  # noqa: E402

_REALPATH_SPLIT_HOME = "pilot_paths.py"

# Measured grep census (issue #1005 FIX-7, narrowed FIX-9) — pin the realpath+split idiom home.
_REALPATH_SPLIT_RE = re.compile(r"os\.path\.realpath\([^)]+\)\.split\(os\.sep\)")
_LOCAL_CONTAINMENT_DEF_RE = re.compile(
    r"def\s+(_is_inside|_is_same_or_ancestor|_path_parts|_path_components)\s*\("
)

# Non-containment uses of split(os.sep) — visible exceptions, not silent skips.
_SPLIT_SEP_ALLOWLIST = {
    "pilot_seed.py": (
        "_path_has_traversal_component detects '..' components, not prefix containment"
    ),
}


def _lib_py_modules():
    return sorted(glob.glob(os.path.join(_LIB, "*.py")))


def _function_source_lines(source, node):
    lines = source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    return "\n".join(lines[start:end])


def _is_delegate_to_pilot_paths(func_source):
    """True when the function body only forwards to pilot_paths.is_inside."""
    return "pilot_paths.is_inside" in func_source and "_path_components" not in func_source


def _realpath_split_containment_census_violations(source_path):
    basename = os.path.basename(source_path)
    if basename == _REALPATH_SPLIT_HOME:
        return []

    with open(source_path, encoding="utf-8") as fh:
        source = fh.read()

    violations = []
    if _REALPATH_SPLIT_RE.search(source):
        violations.append(
            "%s: realpath+split(os.sep) containment idiom (home is %s)"
            % (basename, _REALPATH_SPLIT_HOME)
        )

    if _LOCAL_CONTAINMENT_DEF_RE.search(source):
        tree = ast.parse(source, filename=source_path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name not in (
                "_is_inside",
                "_is_same_or_ancestor",
                "_path_parts",
                "_path_components",
            ):
                continue
            func_source = _function_source_lines(source, node)
            if _is_delegate_to_pilot_paths(func_source):
                continue
            if "_path_components" in func_source or _REALPATH_SPLIT_RE.search(func_source):
                violations.append(
                    "%s:%d: local %s reimplements realpath+split(os.sep) containment "
                    "(home is %s)"
                    % (basename, node.lineno, node.name, _REALPATH_SPLIT_HOME)
                )
    return violations


def run_realpath_split_containment_census():
    violations = []
    for path in _lib_py_modules():
        violations.extend(_realpath_split_containment_census_violations(path))
    return violations


def test_realpath_split_containment_census_clean():
    violations = run_realpath_split_containment_census()
    assert violations == [], (
        "realpath+split(os.sep) containment census violations:\n" + "\n".join(violations)
    )


def test_realpath_split_census_red_on_realpath_split_idiom(tmp_path):
    """Bite-axis: leg 1 — realpath+split(os.sep) outside pilot_paths.py must fail the census."""
    decoy = tmp_path / "pilot_decoy_containment.py"
    decoy.write_text(
        "import os\n"
        "def _path_components(path):\n"
        "    return os.path.realpath(path).split(os.sep)\n",
        encoding="utf-8",
    )
    violations = _realpath_split_containment_census_violations(str(decoy))
    assert violations, "census must flag a throwaway realpath+split(os.sep) implementation"
    assert any("realpath+split(os.sep) containment idiom" in v for v in violations)


def test_realpath_split_census_red_on_leg2_local_helper(tmp_path):
    """Bite-axis: leg 2 — local helper reimplementation without module-scope realpath+split."""
    decoy = tmp_path / "pilot_decoy_leg2.py"
    decoy.write_text(
        "def _path_components(path):\n"
        "  parts = []\n"
        "  for piece in path.split('/'):\n"
        "    parts.append(piece)\n"
        "  return parts\n",
        encoding="utf-8",
    )
    violations = _realpath_split_containment_census_violations(str(decoy))
    assert violations, "census must flag leg-2 local _path_components without realpath+split"
    assert not any("realpath+split(os.sep) containment idiom (home" in v for v in violations)
    assert any("local _path_components reimplements realpath+split(os.sep)" in v for v in violations)


def test_realpath_split_census_green_on_delegate(tmp_path):
    """Bite-axis: delegate bodies forwarding to pilot_paths.is_inside must pass."""
    decoy = tmp_path / "pilot_decoy_delegate.py"
    decoy.write_text(
        "import pilot_paths\n"
        "def _is_inside(path, root):\n"
        "    return pilot_paths.is_inside(path, root)\n",
        encoding="utf-8",
    )
    violations = _realpath_split_containment_census_violations(str(decoy))
    assert violations == []


def test_split_os_sep_allowlist_disclosed():
    """Every non-home split(os.sep) use outside pilot_paths is explicitly allowlisted."""
    for path in _lib_py_modules():
        basename = os.path.basename(path)
        if basename == _REALPATH_SPLIT_HOME:
            continue
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        if "split(os.sep)" not in source:
            continue
        assert basename in _SPLIT_SEP_ALLOWLIST, (
            "%s uses split(os.sep) but is not in _SPLIT_SEP_ALLOWLIST" % basename
        )


def test_is_inside_path_under_root(private_tmp):
    # bite-axis: containment direction — descendant under root is inside; root is not inside descendant.
    root = os.path.join(private_tmp, "reach")
    inside = os.path.join(root, "nested", "file.txt")
    os.makedirs(os.path.dirname(inside))
    assert pilot_paths.is_inside(inside, root) is True
    assert pilot_paths.is_inside(root, inside) is False


def test_is_inside_root_equals_itself(private_tmp):
    # bite-axis: containment boundary — a root matches itself (equality pinned True).
    root = os.path.join(private_tmp, "reach")
    os.makedirs(root)
    assert pilot_paths.is_inside(root, root) is True


def test_is_inside_rejects_prefix_sibling_not_component(private_tmp):
    # bite-axis: prefix-sibling rejection — shared string prefix without a shared component is outside.
    root = os.path.join(private_tmp, "a", "b")
    sibling = os.path.join(private_tmp, "a", "bc")
    parent = os.path.join(private_tmp, "a")
    os.makedirs(parent, exist_ok=True)
    os.makedirs(root)
    os.makedirs(sibling)
    assert pilot_paths.is_inside(sibling, root) is False
    assert pilot_paths.is_inside(root, parent) is True


def test_is_inside_path_outside_root(private_tmp):
    # bite-axis: outside rejection — unrelated paths are outside; descendants remain inside.
    root = os.path.join(private_tmp, "reach")
    outside = os.path.join(private_tmp, "elsewhere")
    child = os.path.join(root, "child")
    os.makedirs(root)
    os.makedirs(outside)
    os.makedirs(child)
    assert pilot_paths.is_inside(outside, root) is False
    assert pilot_paths.is_inside(child, root) is True
