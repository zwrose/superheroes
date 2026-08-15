"""Tests for pilot_paths.py — path containment direction and boundary cases."""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.realpath(os.path.join(_HERE, ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import pilot_paths  # noqa: E402


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
