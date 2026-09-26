import os
import sys

# Put the eval module dir (parent of tests/) on sys.path so tests can
# `import score` directly, mirroring the review-code conftest.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

# The band evals fold fixers through run_loop with fixture head diffs and no repository: they use
# the lib suite's test-only git double (see lib/tests/head_diff_double.py), opt-out marker and all.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "lib", "tests"))
import head_diff_double  # noqa: E402


@pytest.fixture(autouse=True)
def _head_diff_git_double(request, monkeypatch):
    if request.node.get_closest_marker(head_diff_double.MARKER) is None:
        head_diff_double.install(monkeypatch, extra=(request.module,))
    yield
