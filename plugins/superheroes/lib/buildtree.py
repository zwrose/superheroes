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


# append to plugins/superheroes/lib/buildtree.py
RECORD_SCHEMA = 1


class RecordSchemaError(RuntimeError):
    """Raised by record_read on an unknown (future) record schemaVersion — fail closed
    loudly (the engine.py/state.py precedent); never silently drop a forward-version
    record."""


def record_path(cwd, *, store_root=None):
    """The durable record's location: <checkout control-plane dir>/worktrees.json."""
    return os.path.join(control_plane.checkout_dir(cwd, store_root), "worktrees.json")


def record_read(record_file):
    """Fail-closed read. Missing/garbled -> [] (degrades to git-registry recognition,
    self-heals on the next reconcile). An explicit unknown schemaVersion -> raise."""
    try:
        with open(record_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    ver = data.get("schemaVersion")
    if ver is not None and ver != RECORD_SCHEMA:
        raise RecordSchemaError("unknown worktrees.json schemaVersion: %r" % (ver,))
    wts = data.get("worktrees")
    return [w for w in wts if isinstance(w, dict)] if isinstance(wts, list) else []


def record_write(record_file, worktrees):
    """Atomic write of the full record."""
    control_plane.atomic_write(record_file, json.dumps(
        {"schemaVersion": RECORD_SCHEMA, "worktrees": worktrees}))


def record_add(record_file, entry):
    """Idempotent add, deduped by path."""
    kept = [w for w in record_read(record_file) if w.get("path") != entry.get("path")]
    kept.append(entry)
    record_write(record_file, kept)


def record_remove(record_file, path):
    """Idempotent remove by path."""
    record_write(record_file,
                 [w for w in record_read(record_file) if w.get("path") != path])
