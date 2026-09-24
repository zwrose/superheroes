"""Shared test helper: make a session's repository a real git checkout.

INVARIANT: every session a test drives resolves its repository to a real git repository with
at least one commit, built by `make_checkout` here. The test conftest isolates every test from
the ambient checkout (it runs each test from `tmp_path` and strips inherited `GIT_*`
variables), while the driver in production always runs inside a checkout and reads
`git rev-parse HEAD` there; a test session with no repository would model a situation
production never sees.
"""

import os
import subprocess

_IDENTITY = (
    "-c", "user.name=superheroes-test",
    "-c", "user.email=superheroes-test@example.invalid",
    "-c", "commit.gpgsign=false",
    "-c", "init.defaultBranch=main",
)


def _git_env():
    """Every inherited GIT_* variable dropped, so git discovers the repository from `path`
    alone; LC_ALL=C keeps git's messages stable."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["LC_ALL"] = "C"
    return env


def _git(path, *args):
    """Run git in `path`; raise with git's stderr on any failure (never return None)."""
    try:
        return subprocess.run(["git", *_IDENTITY, "-C", str(path), *args], capture_output=True,
                              text=True, check=True, env=_git_env())
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("git %s in %s failed (rc=%s): %s"
                           % (" ".join(args), path, exc.returncode, exc.stderr.strip())) from exc


def _own_head(path):
    """HEAD of the repository whose top level is `path`, or None when `path` is not the top
    of a repository with a commit."""
    try:
        top = _git(path, "rev-parse", "--show-toplevel").stdout.strip()
    except RuntimeError:
        return None
    if os.path.realpath(top) != os.path.realpath(str(path)):
        return None
    try:
        return _git(path, "rev-parse", "--verify", "HEAD").stdout.strip()
    except RuntimeError:
        return None


def make_checkout(path):
    """Make `path` a git repository holding one commit of everything present; return HEAD.

    Idempotent: a `path` that is already a repository with a HEAD returns that HEAD without
    committing again. Raises when git is missing or any git step fails."""
    os.makedirs(str(path), exist_ok=True)
    head = _own_head(path)
    if head:
        return head
    _git(path, "init", "-q")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "--allow-empty", "-m", "session checkout")
    head = _git(path, "rev-parse", "--verify", "HEAD").stdout.strip()
    if len(head) != 40:
        raise RuntimeError("git rev-parse HEAD in %s returned %r" % (path, head))
    return head
