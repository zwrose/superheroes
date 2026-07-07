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
import datetime
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


def _cwd_in_managed_worktree(cwd):
    """True iff `cwd` realpaths to a STRICT descendant of the managed-worktree root.

    The cwd-only confinement predicate, factored out of `worktree_confined` so the FR-6
    worktree-vcs routine family can reuse the EXACT same strict-descendant realpath check
    (never a duplicated, drift-prone copy). Strict descendant: the root itself is NOT confined
    (`real != root`); a `..` parent-hop that resolves out of the root earns nothing; a symlink
    whose realpath lands under the root IS confined (realpath resolves it); a name-prefix
    lookalike sibling (`...-worktrees-evil`) is NOT a descendant. Fail-safe (UFR-2/UFR-5): a
    falsy/non-str `cwd`, a `ValueError` from `commonpath` (different drives), or any other
    error → False.
    """
    if not cwd or not isinstance(cwd, str):
        return False
    try:
        real = os.path.realpath(cwd)
        root = _worktrees_root()
        if os.path.commonpath([real, root]) != root or real == root:
            return False
        return True
    except Exception:
        return False


def worktree_confined(command, cwd):
    """True iff `cwd` is a real managed build worktree (`_cwd_in_managed_worktree`) AND
    `command` is an interpreter invocation.

    Fail-safe (UFR-2/UFR-5): a cwd that is not a strict descendant of the managed-worktree
    root, or a non-str `command`, → False (never toward allowing).
    """
    if not _cwd_in_managed_worktree(cwd):
        return False
    try:
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


def resolve_active_lease(cwd, run_id=None):
    """Resolve the live (non-stale) work-item lease for `cwd`'s clone — the ONE shared
    lease-resolution path behind `enforcer._active_run_id`, `enforcer._active_work_item`,
    and `_run_is_live` (so they can never drift into three parallel lookups).

    Uses the #170 `ref_lock.active_work_items` seam — the honest "what is running in this
    clone" signal that REPLACED the removed `control_plane.get_current` / `current.json`
    pointer (the pre-#170 seam this branch was authored against, which no longer exists). The
    lease store is ALWAYS the real per-clone control-plane checkout store
    (`control_plane.checkout_dir`); a permission-store `root` override never relocates it, and
    a fresh build worktree shares the same common-dir key.

    Returns `(work_item, generation)`:
      * `run_id is None` — the "what run is active here" query: the first (sorted, for
        determinism) live work-item and its lease `generation`.
      * `run_id` given — the "is THIS run live / which work-item is it" query: the live
        work-item whose lease `generation` matches `run_id`, else `(None, None)`. Matched by
        string value so an int fence-token `generation` and a string run-id (e.g. a
        `runs/<id>.json` filename stem) name the same run.

    Fail-SAFE (UFR-2): any error, no store, no live lease, an absent/None lease, or no
    generation match → `(None, None)`. `active_work_items` already filters to non-stale leases,
    so a stale/released lease resolves to `(None, None)` — never a spurious run id. A
    `(None, None)`/None result only makes the allowance layer MORE conservative, so the
    fail-safe direction is always toward prompting."""
    try:
        store = control_plane.checkout_dir(cwd)
        for work_item in ref_lock.active_work_items(store):
            _sha, lease = ref_lock.read_lease(store, work_item)
            if not isinstance(lease, dict):
                continue
            generation = lease.get("generation")
            if run_id is None:
                return (work_item, generation)
            if str(generation) == str(run_id):
                return (work_item, generation)
    except Exception:
        return (None, None)
    return (None, None)


def _run_is_live(run_id, cwd, root):
    """True iff a fresh (non-stale) lease exists whose `generation` matches `run_id`.

    A seam the reap test stubs. Delegates to `resolve_active_lease` — the single shared
    lease-resolution path (no drift with enforcer's `_active_run_id`/`_active_work_item`).
    Fail-safe (UFR-2): resolve_active_lease returns `(None, None)` on any error / no store /
    absent-or-stale lease, so a run file is only ever KEPT (not reaped) on the strength of a
    positively-read fresh matching lease. The permission-store `root` override does NOT
    relocate the real lease store (kept in the signature for the reap seam, but unused for
    resolution) — resolve_active_lease always reads through the real control-plane checkout
    store (a fresh worktree shares the common-dir key)."""
    return resolve_active_lease(cwd, run_id)[0] is not None


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
    per-run `composed` command-hash set (FR-8). Reap runs AFTER the write so a crash
    mid-freeze still leaves this run's own file intact."""
    snapshot = {"rules": rules(cwd, root), "composed": []}
    path = _run_path(run_id, cwd, root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    control_plane.atomic_write(path, json.dumps(snapshot))
    _reap_stale(cwd, root)


def frozen_rules(run_id, cwd, root=None):
    """Read the per-run frozen snapshot for `run_id`. Fail-safe (UFR-2): a missing / corrupt /
    non-dict run file yields the empty snapshot `{"rules": [], "composed": []}`
    (→ no allowance → prompt), never a raise."""
    empty = {"rules": [], "composed": []}
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
    # FR-3: the layer is INERT with no active showrunner run. A falsy `run_id` (an interactive
    # session with no live lease — enforcer._active_run_id yields None) leaves prompting
    # UNCHANGED; every allowance arm (composed-exact, routine family, worktree-confined) is
    # scoped to "a showrunner leaf" (FR-5). Bail before any arm so an interpreter command run
    # from inside a managed build worktree is NOT auto-allowed when no run is active.
    if not run_id:
        return ("fall", "no active run (FR-3)")
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
                family = rule.get("family")
                # FR-6: "version-control operations confined to managed build worktrees." The
                # seeded worktree-vcs family is confined only by branch-ref regex, not by cwd;
                # additionally require the command's cwd to be a real managed build worktree
                # (the same strict-descendant realpath check `worktree_confined` uses, UFR-5).
                # A worktree-vcs match from outside a managed worktree earns nothing → fall.
                if family == "worktree-vcs" and not _cwd_in_managed_worktree(cwd):
                    continue
                return ("allow", "routine:%s" % family)
        # Worktree-confined (FR-5): an interpreter probe inside a real managed worktree.
        if worktree_confined(command, cwd):
            return ("allow", "worktree-confined")
    except Exception:
        return ("fall", "allowance error (fail-safe)")
    return ("fall", "no matching allowance")


# --- Task 13: configure front door — provenance-stamped rule CRUD (FR-9, UFR-9) ---


def _utc_now():
    """An ISO-8601 UTC timestamp for the provenance `at` stamp."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_rules_raw(cwd, root=None):
    """Read the raw `rules.json` list WITHOUT the provenance filter — the CRUD read side.

    `rules()` is the evaluate-time read that drops unstamped entries; the CRUD writers
    instead round-trip whatever is on disk so a `remove_rule` still reaches an entry that
    predates the stamp shape. Fail-safe: a missing / corrupt / non-dict store reads as `[]`."""
    try:
        path = os.path.join(_store_dir(cwd, root), "rules.json")
        with open(path) as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    entries = data.get("rules")
    return entries if isinstance(entries, list) else []


def _write_rules_raw(cwd, entries, root=None):
    """Atomic-write the `rules.json` list back to the config-keyed store."""
    d = _store_dir(cwd, root)
    os.makedirs(d, exist_ok=True)
    control_plane.atomic_write(os.path.join(d, "rules.json"), json.dumps({"rules": entries}))


def set_rule(cwd, rule, root=None):
    """Add (or replace, by `family`) an allow rule, stamping the ONLY provenance
    `_provenance_ok` accepts (`{"source": "configure", "at": <utc-now>}`).

    This front-door stamp is what makes the rule visible to `evaluate` (UFR-9): a direct
    hand-edit that omits it is filtered out at read time, so `configure` is the only
    sanctioned change path (FR-9). Read-modify-write, atomic. A repeated `family` replaces
    the prior entry rather than accumulating duplicates."""
    stamped = dict(rule)
    stamped["provenance"] = {"source": "configure", "at": _utc_now()}
    family = stamped.get("family")
    entries = [e for e in _read_rules_raw(cwd, root)
               if not (isinstance(e, dict) and e.get("family") == family)]
    entries.append(stamped)
    _write_rules_raw(cwd, entries, root)


def remove_rule(cwd, family, root=None):
    """Drop every rule whose `family` matches. Read-modify-write, atomic; a no-op when the
    family is absent."""
    entries = [e for e in _read_rules_raw(cwd, root)
               if not (isinstance(e, dict) and e.get("family") == family)]
    _write_rules_raw(cwd, entries, root)


# --- Task 14: seed the initial rules families + audit.json from the FR-7 audit (FR-6, FR-7) ---

# The four routine command families a full showrunner run exercises, grounded in the FR-7
# audit of which permission prompts actually fire during a run (`_AUDIT` below). Each pattern
# is written NARROW — the owner-role floor set (merge/release/workflow-run/force-push/
# push-to-default) is deliberately NOT matched, and even if a pattern were overbroad the
# floor still catches those via `evaluate`'s defensive `enforcer.gated_action` re-check (UFR-1),
# so the exclusion is guaranteed structurally, not merely by regex care.
#
# - test-run     — the repo's test invocations: pytest, the `python3 -m pytest` form, and the
#                  node smoke runner the pytest wrapper drives.
# - validators   — the three CI validators run at the gate.
# - worktree-vcs — VCS operations a build performs. `git push` is admitted ONLY for a
#                  superheroes/* feature branch (never force, never a `:main`/` main`
#                  destination — the floor owns those). read-only/staging verbs are broad.
# - draft-pr     — draft PR creation + title/body/metadata edits + the draft→ready promotion.
#                  `gh pr edit ... --base` (changing base) is NOT here — normal prompt path.
_SEED_FAMILIES = [
    {
        "family": "test-run",
        "pattern": r"\b(?:python[0-9.]*\s+-m\s+pytest|pytest)\b|\bnode\b.*\bsmoke",
    },
    {
        "family": "validators",
        "pattern": r"\bvalidate_(?:marketplace|hosts|skills)\.py\b",
    },
    {
        "family": "worktree-vcs",
        # staging / read-only VCS verbs, plus a NON-force feature-branch push (no `main`/
        # `master` destination). The push arm requires a `superheroes/` ref so it can never
        # name the default branch; force/`:main` still fall to the floor.
        "pattern": (
            r"\bgit\s+(?:add|commit|status|diff|log|show|fetch|switch|checkout|restore|stash|worktree)\b"
            r"|\bgit\s+push\b(?!.*(?:--force\b|-f\b|--force-with-lease|(?::|[ \t])(?:refs/heads/)?(?:main|master)(?:\s|$)))"
            r".*\bsuperheroes/"
        ),
    },
    {
        "family": "draft-pr",
        # create a draft PR, edit its title/body/labels/etc., and the draft→ready promotion.
        # `--base` (changing the base branch) is intentionally excluded — normal prompt path.
        "pattern": (
            r"\bgh\s+pr\s+create\b(?=.*--draft\b)"
            r"|\bgh\s+pr\s+edit\b(?!.*--base\b)"
            r"|\bgh\s+pr\s+ready\b"
        ),
    },
]

# The FR-7 audit: the prompt-provoking commands observed in a full showrunner run and each
# one's disposition (the routine family that allows it, or "keep prompting" for a command left
# to the normal permission path). Every seeded family traces to at least one entry here, and
# the owner-role floor commands are recorded as "keep prompting" so the audit shows they were
# considered and deliberately NOT auto-allowed.
_AUDIT = [
    {"command": "python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ -q",
     "disposition": "test-run"},
    {"command": "pytest -q", "disposition": "test-run"},
    {"command": "node plugins/superheroes/lib/tests/showrunner_smoke.js",
     "disposition": "test-run"},
    {"command": "python3 .github/scripts/validate_marketplace.py", "disposition": "validators"},
    {"command": "python3 .github/scripts/validate_hosts.py", "disposition": "validators"},
    {"command": "python3 .github/scripts/validate_skills.py", "disposition": "validators"},
    {"command": "git add -A", "disposition": "worktree-vcs"},
    {"command": "git commit -m 'feat(superheroes): ...'", "disposition": "worktree-vcs"},
    {"command": "git status", "disposition": "worktree-vcs"},
    {"command": "git push origin superheroes/<work-item>", "disposition": "worktree-vcs"},
    {"command": "gh pr create --draft --title '...' --body '...'", "disposition": "draft-pr"},
    {"command": "gh pr edit 12 --body '...'", "disposition": "draft-pr"},
    {"command": "gh pr ready 12", "disposition": "draft-pr"},
    # Owner-role floor commands were observed and deliberately left to the prompt path (UFR-1).
    {"command": "gh pr merge 12", "disposition": "keep prompting"},
    {"command": "gh release create v1.0.0", "disposition": "keep prompting"},
    {"command": "gh workflow run ci.yml", "disposition": "keep prompting"},
    {"command": "git push --force origin superheroes/<work-item>", "disposition": "keep prompting"},
    {"command": "git push origin main", "disposition": "keep prompting"},
    # Changing a PR's base branch is not in the draft-pr family — normal prompt path.
    {"command": "gh pr edit 12 --base develop", "disposition": "keep prompting"},
]


def seed_default_rules(cwd, root=None):
    """Seed the four routine families (FR-6) via `set_rule` (so each is provenance-stamped and
    thus visible to `evaluate`), and write the FR-7 `audit.json` alongside `rules.json`.

    Idempotent per family: `set_rule` replaces a same-family entry rather than duplicating, so
    a re-seed refreshes the seeded patterns without accumulating. The seeded VCS/PR patterns
    are written narrow, but the owner-role floor set is excluded STRUCTURALLY by `evaluate`'s
    `enforcer.gated_action` re-check regardless (UFR-1)."""
    for fam in _SEED_FAMILIES:
        set_rule(cwd, dict(fam), root=root)
    d = _store_dir(cwd, root)
    os.makedirs(d, exist_ok=True)
    control_plane.atomic_write(
        os.path.join(d, "audit.json"),
        json.dumps({"observed": _AUDIT}, indent=2),
    )


def audit(cwd, root=None):
    """Read the FR-7 audit record — the prompt-provoking commands observed in a full run and
    each one's disposition (a routine family id, or "keep prompting"). Fail-safe (UFR-2): a
    missing / corrupt / non-dict record reads as `[]`."""
    try:
        with open(os.path.join(_store_dir(cwd, root), "audit.json")) as f:
            data = json.load(f)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    observed = data.get("observed")
    return observed if isinstance(observed, list) else []
