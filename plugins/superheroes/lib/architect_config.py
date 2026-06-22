# plugins/superheroes/lib/architect_config.py
#!/usr/bin/env python3
"""the-architect doc-policy record + repo analyzer + scoped .gitignore-ensuring
(CONVENTIONS §2.3/§3.3/§4.2). Stdlib-only. The in-repo-only doc-policy lives as
doc-policy.json in the I1 project store; the mode authority (registry.json) is untouched."""
import json
import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import mode_registry  # noqa: E402  (sibling)
import store_core      # noqa: E402  (sibling)

SCHEMA_VERSION = 1
DEFAULT_LOCATION = "docs/superheroes"
COMMITTED = "committed"
GITIGNORED = "gitignored"
_VISIBILITIES = (COMMITTED, GITIGNORED)


def policy_path(cwd, root=None):
    return os.path.join(mode_registry.project_store_dir(cwd, root), "doc-policy.json")


def _safe_location(location):
    """A repo-relative location that cannot escape the repo, else the default (UFR-4).
    Rejects absolute paths and any `..` traversal — a write must stay inside the repo."""
    if not isinstance(location, str) or not location:
        return DEFAULT_LOCATION
    norm = os.path.normpath(location)
    if os.path.isabs(norm) or norm == ".." or norm.startswith(".." + os.sep):
        return DEFAULT_LOCATION
    return norm


def _migrate(rec):
    """Fill an older/partial record forward to the current shape (migrate-on-read).
    Returns a normalized dict, or None if it cannot be coerced to a valid policy."""
    if not isinstance(rec, dict):
        return None
    location = _safe_location(rec.get("location"))
    visibility = rec.get("visibility")
    if visibility not in _VISIBILITIES:
        visibility = COMMITTED
    confirmed = bool(rec.get("confirmed", False))
    return {"schemaVersion": SCHEMA_VERSION, "location": location,
            "visibility": visibility, "confirmed": confirmed}


def read_policy(cwd, root=None):
    """{location, visibility, confirmed} or None (absent/corrupt). Migrates an older/partial
    record forward **in memory only** (no write-back on read) — the next write_policy persists
    the current shape. This deliberately removes the migrate-write-back failure mode the plan
    flagged while still satisfying the spec's UFR-5 (migrate on read, no manual re-init)."""
    try:
        with open(policy_path(cwd, root), encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    migrated = _migrate(rec)
    if migrated is None:
        return None
    return {"location": migrated["location"], "visibility": migrated["visibility"],
            "confirmed": migrated["confirmed"]}


def write_policy(cwd, policy, root=None):
    """Record the doc-policy under the project config lock. Returns the written record,
    or None if the lock is contended (caller proceeds + surfaces a notice — UFR-1)."""
    rec = _migrate(policy)
    if rec is None:
        raise ValueError("invalid doc-policy: %r" % (policy,))
    if mode_registry.ensure_project_store(cwd, root) is None:
        return None
    with mode_registry.config_lock(cwd, root) as got:
        if not got:
            return None
        store_core.atomic_write(policy_path(cwd, root), json.dumps(rec, indent=2))
        return rec


def _gitignore_covers(repo_root, location):
    """True iff git's ignore rules already cover `location`. Falls back to a textual
    .gitignore scan when git isn't available (non-git dir / git missing)."""
    probe = location.rstrip("/") + "/.superheroes-probe"
    out = store_core.run_git(repo_root, "check-ignore", "-q", probe)
    # run_git returns "" (stripped stdout) on rc 0 (ignored), None on non-zero/no-git.
    if out is not None:
        return True
    gi = os.path.join(repo_root, ".gitignore")
    try:
        with open(gi, encoding="utf-8") as fh:
            patterns = {ln.strip().rstrip("/") for ln in fh if ln.strip()
                        and not ln.lstrip().startswith("#")}
    except OSError:
        return False
    loc = location.strip("/")
    parts = loc.split("/")
    # match the dir or any parent prefix (e.g. "docs/" covers "docs/superheroes").
    return any("/".join(parts[:i]) in patterns for i in range(1, len(parts) + 1))


def analyze_repo(repo_root):
    """Recommend {location, visibility} from the repo's existing documentation strategy."""
    # Prefer a location superheroes already uses, else an existing docs dir, else the default.
    candidates = ["docs/superheroes", "docs", "doc", "documentation"]
    location = DEFAULT_LOCATION
    for c in candidates:
        if os.path.isdir(os.path.join(repo_root, c)):
            location = "docs/superheroes" if c in ("docs", "docs/superheroes") else c
            break
    visibility = GITIGNORED if _gitignore_covers(repo_root, location) else COMMITTED
    return {"location": location, "visibility": visibility}


def _is_tracked(repo_root, location):
    """True iff git already tracks any file under `location` (run_git returns the file list
    on rc 0, None otherwise — bool() is True only when something is tracked there)."""
    return bool(store_core.run_git(repo_root, "ls-files", location))


def ensure_ignored(repo_root, location):
    """Ensure `location` is kept out of version control via a scoped ignore rule.
    Returns False (could-not-ensure) when it is already tracked or .gitignore can't be
    written — the caller then applies UFR-8 (refuse rather than write exposed)."""
    if _is_tracked(repo_root, location):
        return False  # an ignore rule cannot untrack an already-tracked path (→ UFR-8)
    if _gitignore_covers(repo_root, location):
        return True   # already ignored — idempotent no-op
    rule = location.strip("/") + "/"
    gi = os.path.join(repo_root, ".gitignore")
    try:
        existing = ""
        if os.path.isfile(gi):
            with open(gi, encoding="utf-8") as fh:
                existing = fh.read()
        sep = "" if (existing == "" or existing.endswith("\n")) else "\n"
        store_core.atomic_write(gi, existing + sep + rule + "\n")
    except OSError:
        return False  # unwritable .gitignore (→ UFR-8)
    return True
