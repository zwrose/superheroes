"""Repo-root pytest configuration — loads source_guard for every test tree, keeps a cloud session's CLAUDE_CODE_REMOTE out of every test, and pins every test's git to a config the session owns."""
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


@pytest.fixture(autouse=True, scope="session")
def _session_git_config(tmp_path_factory):
    # axis: tests commit against the session's own git config, never the developer's
    # global or system one (signing, identity, hooks); repo-local and `git -c` still win
    config = tmp_path_factory.mktemp("git_config") / "gitconfig"
    config.write_text(
        "[user]\n\tname = Test User\n\temail = test@example.invalid\n"
        "[commit]\n\tgpgsign = false\n"
        "[tag]\n\tgpgsign = false\n"
    )
    names = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")
    originals = {name: os.environ.get(name) for name in names}
    os.environ["GIT_CONFIG_GLOBAL"] = str(config)
    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
    try:
        yield
    finally:
        for name, original in originals.items():
            if original is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = original
