import os
import subprocess

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
GUARD = os.path.join("plugins", "superheroes", "lib", "tests", "structured_output_schema_guard.js")


def test_structured_output_schemas_reject_top_level_combinators():
    result = subprocess.run(["node", GUARD], cwd=ROOT, text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
