# plugins/superheroes/lib/buildtree.py
"""Managed build-worktree lifecycle for Workhorse: the deterministic path under the
managed root, reuse/reclaim of a clean worktree, a durable record of outstanding
worktrees, and tiered teardown gated by pure fail-closed decisions. Modeled on
devserver.py (pure helpers + idempotent, never-raising effectful ops). All destructive
logic lives in the pure decision functions; the effectful shell only executes a
pre-computed decision.
"""
import json
import os
import subprocess

import control_plane


def managed_root(root=None):
    """The managed-worktree root: ~/.superheroes-worktrees by default, overridable via
    SUPERHEROES_WORKTREES_ROOT (the store_root() pattern) or an explicit root."""
    if root is not None:
        return os.path.realpath(os.path.expanduser(root))
    return os.path.realpath(os.path.expanduser(
        os.environ.get("SUPERHEROES_WORKTREES_ROOT", "~/.superheroes-worktrees")))


def branch_name(work_item, content_hash):
    """The content-addressed build branch (unchanged identity — never recomputed)."""
    return "superheroes/%s-%s" % (work_item, content_hash)


def worktree_path(cwd, work_item, content_hash, *, root=None):
    """The deterministic FR-1 path: <managed_root>/<checkout-key>/<work-item>-<hash>.
    The checkout-key (control_plane.checkout_key — the --absolute-git-dir hash) makes
    two distinct checkouts of one repo resolve to distinct paths (FR-1 no-collision).
    Total — never raises (checkout_key falls back to realpath(cwd))."""
    key = control_plane.checkout_key(cwd)
    return os.path.join(managed_root(root), key, "%s-%s" % (work_item, content_hash))
