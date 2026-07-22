#!/usr/bin/env python3
# plugins/superheroes/lib/guardian_census.py
"""Shared git-tracked file census for Guardian lenses.

Stdlib-only. Lenses that hand a tracked-file set to content-reading tools (jscpd, radon,
lizard) must census through this module so the population cannot drift per-lens.

Fail-direction: a ``git ls-files`` failure returns ``(None, reason)`` — never an empty
set. An empty set would erase a lens baseline and make a broken sweep look clean.

``git ls-files -z`` emits literal NUL-delimited pathnames; it never emits porcelain rename
syntax like ``a/{b => c}/d``. A brace/arrow filter on path strings would silently drop
legitimately-named tracked files (``src/{generated}.py``, ``weird=>name.ts``) and
manufacture a false-clean measurement. Safety comes from per-path ``isfile`` / ``islink``
checks instead.
"""
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import guardian_collect as gc  # noqa: E402

# A lens handing the tracked-file census as explicit operands to a content scanner could
# push argv past the kernel's ARG_MAX on a very large repo. macOS ARG_MAX is 262144 bytes
# and the sanitized child env consumes a share of that; cap the operand payload well under
# it. The bound is measured on the ABSOLUTIZED payload (invoke prepends the repo realpath
# + a path separator to every operand before execve), not the repo-relative bytes, so the
# guard reflects the real argv the kernel sees.
MAX_TRACKED_OPERAND_BYTES = 100_000


def _git(ctx, cwd, args, timeout=gc.DEFAULT_TIMEOUT):
    """Run a git subcommand via run_tool with an absolute ``-C`` repo target.

    ``git -C <abs repo>`` targets the repo even though invoke runs collectors from a
    neutral cwd (git resolves via PATH; it is not a repo-local executable).
    """
    return gc.run_tool(["git", "-C", cwd, *args], ctx=ctx, cwd=cwd, timeout=timeout)


def tracked_existing_files(ctx, cwd, *, exclude_symlinks=True):
    """Repo-relative paths that are ``git ls-files`` tracked and present on disk.

    Returns ``(files, None)`` on success or ``(None, reason)`` on a git failure — a git
    failure must NEVER be read as an empty tracked set.

    When ``exclude_symlinks`` is true (the default), tracked symlinks are omitted even if
    ``os.path.isfile`` would follow the link to an on-disk target. A tracked symlink whose
    target is an untracked file under the repo would otherwise pass ``isfile`` and let a
    content scanner read untracked bytes (#564 by another door).
    """
    res = _git(ctx, cwd, ["ls-files", "-z"])
    if not res["ok"]:
        return None, res["reason"]
    out = set()
    for raw in (res.get("stdout") or "").split("\0"):
        if not raw:
            continue
        full = os.path.join(cwd, raw)
        if not os.path.isfile(full):
            continue
        if exclude_symlinks and os.path.islink(full):
            continue
        out.add(raw)
    return out, None


def operand_payload_bytes(cwd, files):
    """Size of the absolutized operand payload the kernel would see.

    ``invoke`` prepends ``realpath(cwd)`` + a path separator to every operand before
    ``execve``, so repo-relative byte counts under-count argv size.
    """
    abs_prefix_bytes = len(os.path.realpath(cwd).encode("utf-8")) + 1
    return sum(len(p.encode("utf-8")) + abs_prefix_bytes for p in files)
