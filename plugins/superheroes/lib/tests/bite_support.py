"""Shared test support — bite-proofs and journal fixture helpers."""
import importlib.util
import json
import os
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)

_ED = None
_ERC = None


def _engine_dispatch():
    global _ED
    if _ED is None:
        spec = importlib.util.spec_from_file_location(
            "engine_dispatch", os.path.join(_LIB, "engine_dispatch.py"))
        _ED = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ED)
    return _ED


def _engine_result_channel():
    global _ERC
    if _ERC is None:
        spec = importlib.util.spec_from_file_location(
            "engine_result_channel", os.path.join(_LIB, "engine_result_channel.py"))
        _ERC = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_ERC)
    return _ERC


def _ended_with_completion_stamp(payload, *, complete_at=1.0, deadline_mono=None, **ended_base):
    """Build attempt-ended fields with a completion stamp over scrubbed payload digest."""
    ed = _engine_dispatch()
    erc = _engine_result_channel()
    ended = dict(ended_base)
    if isinstance(payload, dict):
        payload = ed._scrub_native_payload(payload)
    digest = erc.canonical_payload_digest(payload)
    ended.update(erc.completion_stamp(complete_at, digest))
    if deadline_mono is not None:
        ended.update(erc.deadline_stamp(deadline_mono))
    return ended


def _stamp_ended_from_native_result(run_dir, ended, attempt=1):
    """Add completion stamp to attempt-ended fields from on-disk native result file."""
    ed = _engine_dispatch()
    erc = _engine_result_channel()
    result_path = ed._native_result_path(run_dir, attempt)
    if not result_path or not os.path.isfile(result_path):
        return ended
    try:
        with open(result_path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return ended
    if isinstance(payload, dict):
        payload = ed._scrub_native_payload(payload)
    digest = erc.canonical_payload_digest(payload)
    if digest is None:
        return ended
    out = dict(ended)
    out.update(erc.completion_stamp(1.0, digest))
    return out


def patched_module(module, edits, name=None):
    """Compile a neutralized in-memory copy of `module`. Never writes to disk.

    `edits` is a sequence of (old, new) pairs, each applied exactly once, in order.
    Raises AssertionError if an `old` target is absent, or occurs more than once.
    """
    if edits and isinstance(edits[0], str):
        edits = (edits,)
    normalized = []
    for item in edits:
        if (
            not isinstance(item, (tuple, list))
            or len(item) != 2
            or not isinstance(item[0], str)
            or not isinstance(item[1], str)
        ):
            raise AssertionError(
                "edits must be a sequence of (old, new) string pairs, got %r" % item
            )
        normalized.append((item[0], item[1]))
    edits = normalized
    with open(module.__file__, encoding="utf-8") as fh:
        src = fh.read()
    patched = src
    for old, new in edits:
        count = patched.count(old)
        if count == 0:
            raise AssertionError("neutralization target not found: %r" % (old,))
        if count != 1:
            raise AssertionError(
                "neutralization target %r occurs %d times (expected 1)" % (old, count)
            )
        patched = patched.replace(old, new, 1)
    mod = types.ModuleType(name or module.__name__ + "__patched")
    mod.__file__ = module.__file__
    exec(compile(patched, module.__file__, "exec"), mod.__dict__)
    return mod
