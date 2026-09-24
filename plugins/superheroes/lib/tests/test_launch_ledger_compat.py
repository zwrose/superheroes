"""The background dispatch-mode literal has one home (claude_modes); launch_ledger and engine_adapter bind none."""
import ast
import os

import claude_modes

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(_HERE)


def test_background_mode_literal_pinned():
    assert claude_modes.MODE_BACKGROUND == "background"


def _background_mode_literal_problems(path):
    rel = os.path.relpath(path, _LIB)
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return [f"background-mode-census-unparseable:{rel}"]
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "background":
            problems.append(f"background-mode-literal-outside-home:{rel}:{node.lineno}")
    return problems


def test_background_mode_single_home():
    problems = []
    for name in ("launch_ledger.py", "engine_adapter.py"):
        problems.extend(_background_mode_literal_problems(os.path.join(_LIB, name)))
    assert problems == []
