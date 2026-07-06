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
Task 3 scope: `freeze_run_rules` / `frozen_rules` / `record_composed` + lazy reap — the
per-run frozen snapshot (a mid-run edit never reaches a running run, UFR-9), the byte-exact
composed-command set (FR-8), and stale-run-file retention (30-day, no-live-lease reap).
"""
import hashlib
import json
import os
import re
import time

import buildtree
import control_plane
import mode_registry
import ref_lock


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


# --- Task 3: freeze_run_rules / frozen_rules / record_composed + lazy reap (FR-8, UFR-9) ---

_REAP_MAX_AGE = 30 * 86400   # a stale run file with no live lease is reaped after 30 days


def _hash(command):
    """The byte-exact composed-command fingerprint (FR-8). Any single-char difference — or a
    command composed by a different run — misses, because the enforcer allows a composed
    command only when its hash byte-equals one frozen for the *current* run."""
    return hashlib.sha256(command.encode("utf-8")).hexdigest()


def _run_path(run_id, cwd, root):
    return os.path.join(_store_dir(cwd, root), "runs", "%s.json" % run_id)


def _run_is_live(run_id, cwd, root):
    """True iff a fresh (`not ref_lock.is_stale`) lease exists whose `generation == run_id`.

    A seam the reap test stubs. Fail-safe (UFR-2): any error — no store, unreadable ref,
    absent/None lease — is treated as *not live*, so a run file is only ever reaped, never
    kept alive, on the strength of a positively-read fresh matching lease. The permission
    store `root` override does not relocate the real lease store, so lease reads always go
    through the real control-plane store (a fresh worktree shares the common-dir key)."""
    try:
        store = control_plane.checkout_dir(cwd)
        work_item = control_plane.get_current(cwd)
        if not work_item:
            return False
        _sha, lease = ref_lock.read_lease(store, work_item)
        if not isinstance(lease, dict):
            return False
        if ref_lock.is_stale(lease, ref_lock.DEFAULT_TTL):
            return False
        return lease.get("generation") == run_id
    except Exception:
        return False


def _reap_stale(cwd, root):
    """Delete every sibling `runs/*.json` that is NOT live AND older than 30 days.

    Run-*start* reap only (crash-tolerant — a crashed run never leaks its file forever, and
    a live/recent run's file is always kept). Guarded whole: a reap error must never fail a
    freeze (UFR-2), so any exception is swallowed."""
    try:
        runs_dir = os.path.join(_store_dir(cwd, root), "runs")
        cutoff = time.time() - _REAP_MAX_AGE
        for name in os.listdir(runs_dir):
            if not name.endswith(".json"):
                continue
            path = os.path.join(runs_dir, name)
            try:
                if os.path.getmtime(path) >= cutoff:
                    continue                                 # recent -> keep
                rid = name[:-len(".json")]
                if _run_is_live(rid, cwd, root):
                    continue                                 # live lease -> keep
                os.remove(path)
            except OSError:
                continue                                     # one bad file never stops the sweep
    except Exception:
        return


def freeze_run_rules(run_id, cwd, root=None):
    """Snapshot the current provenance-valid `rules.json` into `runs/<run_id>.json`, then
    lazily reap stale sibling run files.

    The snapshot is the per-run frozen view a running run reads (UFR-9): a mid-run edit to
    `rules.json` never reaches a run that already froze. The run file also carries the
    per-run `composed` command-hash set (FR-8) and a `denials` list (Task 7 absorption).
    Reap runs AFTER the write so a crash mid-freeze still leaves this run's own file intact."""
    snapshot = {"rules": rules(cwd, root), "composed": [], "denials": []}
    path = _run_path(run_id, cwd, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    control_plane.atomic_write(path, json.dumps(snapshot))
    _reap_stale(cwd, root)


def frozen_rules(run_id, cwd, root=None):
    """Read the per-run frozen snapshot for `run_id`. Fail-safe (UFR-2): a missing / corrupt /
    non-dict run file yields the empty snapshot `{"rules": [], "composed": [], "denials": []}`
    (→ no allowance → prompt), never a raise."""
    empty = {"rules": [], "composed": [], "denials": []}
    try:
        with open(_run_path(run_id, cwd, root)) as f:
            data = json.load(f)
    except Exception:
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        "rules": data.get("rules") if isinstance(data.get("rules"), list) else [],
        "composed": data.get("composed") if isinstance(data.get("composed"), list) else [],
        "denials": data.get("denials") if isinstance(data.get("denials"), list) else [],
    }


def record_composed(run_id, command, cwd, root=None):
    """Append the byte-exact hash of a spine-composed `command` to `run_id`'s frozen file
    (read-modify-write, idempotent — a repeat of the same command is a no-op). This is how
    `evaluate`'s composed-exact allow set (FR-8) is populated for the run that composed the
    command, and only that run."""
    snapshot = frozen_rules(run_id, cwd, root)
    h = _hash(command)
    if h not in snapshot["composed"]:
        snapshot["composed"].append(h)
    path = _run_path(run_id, cwd, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    control_plane.atomic_write(path, json.dumps(snapshot))


# --- Task 4: evaluate — the pure allowance decision (FR-5/6/8, UFR-1, UFR-2) ---


def evaluate(command, cwd, run_id, root=None):
    """The pure below-the-floor allowance decision. Returns ('allow', reason) iff a frozen
    routine family matches (FR-6), the command byte-equals a spine-composed command frozen
    for `run_id` (FR-8), or the command is confined to a real managed worktree (FR-5);
    otherwise ('fall', reason) — the enforcer then leaves today's outcome (default allow)
    untouched.

    Every non-allow path returns 'fall', never a raise:
    - a non-string command → ('fall', ...);
    - a gated (owner-role) command is NEVER allowed, even if a rule would match it (UFR-1) —
      a belt-and-suspenders re-check of `enforcer.gated_action`, since `evaluate` is only
      called where the floor already resolved to the non-gated default allow;
    - any error is caught and falls through toward prompting (UFR-2).

    `enforcer` is imported lazily inside the function to avoid a module-level import cycle
    (enforcer imports permission_rules for the Task-5 wiring)."""
    if not isinstance(command, str):
        return ("fall", "non-string")
    # Defensive floor re-check (UFR-1): a gated command is the floor's to decide — never
    # allowance-allow it, even against a matching rule. Reproduces only the gated/not-gated
    # partition; sufficient because `evaluate` is called solely where the floor already
    # resolved to the non-gated default allow.
    try:
        import enforcer
        if enforcer.gated_action(command):
            return ("fall", "gated command — floor owns it")
    except Exception:
        return ("fall", "allowance error (fail-safe)")
    try:
        frozen = frozen_rules(run_id, cwd, root)
        # Composed-exact (FR-8): a command byte-frozen for THIS run.
        if _hash(command) in frozen.get("composed", []):
            return ("allow", "composed-exact")
        # Routine family (FR-6): an owner-curated, provenance-valid pattern.
        for rule in frozen.get("rules", []):
            pattern = rule.get("pattern") if isinstance(rule, dict) else None
            if pattern and re.search(pattern, command):
                return ("allow", "routine:%s" % rule.get("family"))
        # Worktree-confined (FR-5): an interpreter probe inside a real managed worktree.
        if worktree_confined(command, cwd):
            return ("allow", "worktree-confined")
    except Exception:
        return ("fall", "allowance error (fail-safe)")
    return ("fall", "no matching allowance")
