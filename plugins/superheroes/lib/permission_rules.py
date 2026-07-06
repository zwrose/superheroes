# plugins/superheroes/lib/permission_rules.py
"""Pure allowance layer for the deterministic PreToolUse gate (enforcer.py).

This module is the *below-the-floor* decision the enforcer consults ONLY on its
non-gated branch (where today's outcome is the unconditional `allow`). It turns a
would-be permission prompt into an `allow` when — and only when — a command matches an
owner-curated routine family (FR-6), is confined to a real managed build worktree under
the managed-worktree root (FR-5), or byte-equals a spine-composed command frozen for the
current run (FR-8). Every code path is fail-safe *toward prompting* (UFR-2): any error,
non-match, or missing data falls through, never toward allowing.

Task 1 scope: `worktree_confined` — the realpath strict-descendant + interpreter check.
Task 2 scope: `_store_dir` / `_provenance_ok` / `rules` — the config-keyed out-of-repo
rules store and the provenance-checked read (FR-6 substrate, UFR-9).
"""
import json
import os
import re

import buildtree
import control_plane
import mode_registry


def _worktrees_root():
    """The canonical managed-worktree root, realpathed.

    Delegates to the existing canonical resolver `buildtree.managed_root()`, which
    realpaths `os.path.expanduser(...)` AND honors the `SUPERHEROES_WORKTREES_ROOT`
    env override (the `store_root()` pattern). We do NOT re-hardcode the
    `~/.superheroes-worktrees` literal here: re-hardcoding it would silently break FR-5
    for any run whose worktrees root is relocated via that env var. This stays the seam
    the tests monkeypatch.
    """
    return buildtree.managed_root()


# Interpreter invocations — the improvised-probe shapes. A literal enumerated set, not a
# catch-all. A leading `env`/absolute-path prefix is tolerated (e.g. `/usr/bin/python3`,
# `env node`). `bash`/`sh`/`zsh` only count when invoked as a `-c` one-liner probe.
_INTERPRETER = re.compile(
    r"(?:^|[\s;|&])"                      # start or a shell boundary before the token
    r"(?:env\s+)?"                        # optional `env ` prefix
    r"(?:\S*/)?"                          # optional absolute/relative path prefix
    r"(?:"
    r"python[0-9.]*|node|ruby|perl"       # bare interpreter binaries
    r"|(?:bash|sh|zsh)\s+-c"              # POSIX shells only as `-c` probes
    r")"
    r"(?:\s|$)"
)


def worktree_confined(command, cwd):
    """True iff `cwd` realpaths to a STRICT descendant of the managed-worktree root AND
    `command` is an interpreter invocation.

    Strict descendant: the root itself is NOT confined (`real != root`); a `..` parent-hop
    that resolves out of the root earns nothing; a symlink whose realpath lands under the
    root IS confined (realpath resolves it); a name-prefix lookalike sibling
    (`...-worktrees-evil`) is NOT a descendant. Fail-safe (UFR-2/UFR-5): a falsy/non-str
    `cwd`, a `ValueError` from `commonpath` (different drives), or any other error → False.
    """
    if not cwd or not isinstance(cwd, str):
        return False
    try:
        real = os.path.realpath(cwd)
        root = _worktrees_root()
        if os.path.commonpath([real, root]) != root or real == root:
            return False
        return bool(_INTERPRETER.search(command))
    except Exception:
        return False


# --- Task 2: rules store paths + provenance-checked read (FR-6 substrate, UFR-9) ---


def _store_dir(cwd, root=None):
    """The out-of-repo permission store dir: `<store_root>/projects/<config_key>/permission/`.

    Keyed on `mode_registry.config_key(cwd)` — the same common-dir key `registry.json`
    uses — so a fresh build worktree resolves the same rules with no repo artifact. The
    `root` override (tests / an explicit store base) shadows `control_plane.store_root()`.
    """
    base = root or control_plane.store_root()
    return os.path.join(base, "projects", mode_registry.config_key(cwd), "permission")


def _provenance_ok(entry):
    """True iff `entry` carries a well-formed provenance stamp (UFR-9).

    A valid stamp is a dict with a truthy `source` and a truthy `at` timestamp — the shape
    the configure front door stamps (Task 9/13). Anything else (missing key, `None`,
    non-dict, absent field) → False, so an untraceable or hand-edited rule falls back to
    prompting, never to allowing.
    """
    prov = entry.get("provenance") if isinstance(entry, dict) else None
    if not isinstance(prov, dict):
        return False
    return bool(prov.get("source")) and bool(prov.get("at"))


def rules(cwd, root=None):
    """The provenance-valid allow rules for `cwd`'s project.

    Reads `<store_dir>/rules.json`; fail-safe (UFR-2): a missing / corrupt / non-dict store
    yields `[]` (→ no allowance → prompt). Filters to entries whose provenance stamp is
    present and well-formed (`_provenance_ok`), so an untraceable entry never allows.
    """
    try:
        path = os.path.join(_store_dir(cwd, root), "rules.json")
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("rules")
    if not isinstance(entries, list):
        return []
    return [e for e in entries if _provenance_ok(e)]
