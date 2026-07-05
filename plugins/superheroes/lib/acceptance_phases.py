"""Read the showrunner pipeline phase list from the JS source of truth.

The acceptance harness must not carry a second hand-maintained phase list. The
showrunner owns the canonical `PHASES` literal; Python reads that literal and
fails closed if it cannot be parsed as a simple list of strings.
"""
import ast
import os
import re


_PHASES_RE = re.compile(r"const\s+PHASES\s*=\s*(\[[^\]]+\])", re.MULTILINE | re.DOTALL)


def showrunner_js_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "showrunner.js")


def read_pipeline_phases(path=None):
    path = path or showrunner_js_path()
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise RuntimeError("showrunner phase source is unreadable: %s" % exc) from exc
    match = _PHASES_RE.search(text)
    if not match:
        raise RuntimeError("showrunner PHASES literal was not found")
    try:
        phases = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError) as exc:
        raise RuntimeError("showrunner PHASES literal is not parseable") from exc
    if not isinstance(phases, list) or not phases or not all(
            isinstance(p, str) and p for p in phases):
        raise RuntimeError("showrunner PHASES literal must be a non-empty string list")
    return list(phases)
