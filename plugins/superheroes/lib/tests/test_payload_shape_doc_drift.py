"""Drift pin: auto-fix-loop payloadShape paragraph tokens stay in REVIEW_PAYLOAD_SHAPES."""
import fnmatch
import importlib.util
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(_HERE, "..")
_PLUGIN_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

_AUTO_FIX_LOOP_DOC = os.path.join(
    _PLUGIN_ROOT, "skills", "review-code", "reference", "auto-fix-loop.md",
)

_ANCHOR = "`payloadShape` on shape-unreadable forfeit"
_LITERAL_TOKEN_RE = re.compile(r"`([a-z]+(?:-[a-z]+)+)`")
_GLOB_TOKEN_RE = re.compile(r"`(\*-[a-z-]+)`")


def _load_engine_adapter():
    spec = importlib.util.spec_from_file_location(
        "engine_adapter", os.path.join(_LIB, "engine_adapter.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _payload_shape_paragraph():
    with open(_AUTO_FIX_LOOP_DOC, encoding="utf-8") as fh:
        text = fh.read()
    anchor_pos = text.find(_ANCHOR)
    if anchor_pos < 0:
        raise AssertionError(
            "auto-fix-loop.md missing anchor %r" % _ANCHOR
        )
    block_start = text.rfind("\n>", 0, anchor_pos)
    if block_start < 0:
        block_start = anchor_pos
    block_end = text.find("\n>\n", anchor_pos)
    if block_end < 0:
        block_end = len(text)
    else:
        block_end += 1
    return text[block_start:block_end]


def test_payload_shape_doc_tokens_pinned_to_review_payload_shapes():
    # axis: inline payloadShape tokens named in auto-fix-loop.md are members of REVIEW_PAYLOAD_SHAPES
    ea = _load_engine_adapter()
    paragraph = _payload_shape_paragraph()
    literals = _LITERAL_TOKEN_RE.findall(paragraph)
    globs = _GLOB_TOKEN_RE.findall(paragraph)
    assert literals, "expected at least one literal shape token in payloadShape paragraph"
    assert globs, "expected at least one glob shape token in payloadShape paragraph"
    for token in literals:
        assert token in ea.REVIEW_PAYLOAD_SHAPES, (
            "literal token %r not in REVIEW_PAYLOAD_SHAPES" % token
        )
    for pattern in globs:
        matches = [
            shape for shape in ea.REVIEW_PAYLOAD_SHAPES
            if fnmatch.fnmatch(shape, pattern)
        ]
        assert matches, (
            "glob %r matches no member of REVIEW_PAYLOAD_SHAPES" % pattern
        )
