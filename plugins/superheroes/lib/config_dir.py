"""Resolve the Claude config directory for a spawned child process.

Stdlib-only; no imports from the plugin. ``launcher.spawn_config_dir`` delegates here.
"""
from __future__ import annotations

import os

CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
DEFAULT_CONFIG_DIR_NAME = ".claude"


def _expand_home(path, env):
    """expanduser against the SUPPLIED env's HOME, not the ambient process env.

    The child inherits the env passed here, so expanding `~` through the launcher's own
    HOME would record a root the child never uses.
    """
    if not path.startswith("~"):
        return path
    home = env.get("HOME")
    if not isinstance(home, str) or not home:
        return os.path.expanduser(path)
    if path == "~" or path.startswith("~" + os.sep):
        return home + path[1:]
    return os.path.expanduser(path)


def resolve(env=None, cwd=None):
    """The absolute config root the spawned child will write its session transcript under.

    An explicit caller-provided ``CLAUDE_CONFIG_DIR`` wins: the override branch below is
    read first. The one normalization it does apply to an override is ``.strip()``.

    Every branch resolves through the SUPPLIED env and the child's own ``cwd`` — never the
    launcher's ambient environment or working directory. A relative override resolves against
    the child's cwd (the build worktree); returns None when ``cwd`` is not absolute.

    Default is ``$HOME/.claude`` from the supplied env, falling back to
    ``os.path.expanduser("~")``. Returns None when no absolute root can be derived.
    """
    base = dict(env if env is not None else os.environ)
    configured = base.get(CONFIG_DIR_ENV)
    if isinstance(configured, str) and configured.strip():
        path = _expand_home(configured.strip(), base)
        if os.path.isabs(path):
            return path
        if isinstance(cwd, str) and os.path.isabs(cwd):
            return os.path.normpath(os.path.join(cwd, path))
        return None
    home = base.get("HOME")
    if not isinstance(home, str) or not home.strip():
        home = os.path.expanduser("~")
    if not os.path.isabs(home):
        return None
    return os.path.join(home, DEFAULT_CONFIG_DIR_NAME)
