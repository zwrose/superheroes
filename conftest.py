"""Repo-root pytest configuration — loads source_guard for every test tree and keeps a cloud session's CLAUDE_CODE_REMOTE out of every test."""
import os

import pytest

pytest_plugins = ("source_guard",)


@pytest.fixture(autouse=True, scope="session")
def _no_cloud_session_env():
    # axis: no CLAUDE_CODE_REMOTE in os.environ for the whole session (module-scoped
    # fixtures and tests that call monkeypatch.undo() included) — see bite-proof
    # record c8c_wo_b.md
    original = os.environ.pop("CLAUDE_CODE_REMOTE", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["CLAUDE_CODE_REMOTE"] = original
