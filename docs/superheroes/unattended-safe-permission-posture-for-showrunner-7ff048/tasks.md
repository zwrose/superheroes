---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: unattended-safe-permission-posture-for-showrunner-7ff048
issue: 149
size: medium
status: approved
gates: {review: passed}
producedBy: "the-architect@0.5.0"
created: "2026-07-03"
updated: "2026-07-05"
---
# Unattended-safe permission posture for showrunner runs — Tasks

## Goal

Make an owner-absent showrunner run finish without babysitting while the owner-role floor stays
exactly as strong as today. Two independent moves layered on the *existing* deterministic gate
(`plugins/superheroes/lib/enforcer.py`, wired as the `PreToolUse` hook):

1. **Fewer prompts fire.** A new pure core `plugins/superheroes/lib/permission_rules.py` holds an
   *allowance layer* the enforcer calls **only on the non-gated branch** of `classify_command`
   (where today's outcome is the unconditional `allow`). It turns a would-be prompt into an `allow`
   when — and only when — the command matches an owner-curated routine family (FR-6), is confined to
   a real managed build worktree under `~/.superheroes-worktrees/` (FR-5), or byte-equals a
   spine-composed command frozen for the current `run_id` (FR-8). Rules live in the common-dir-keyed
   out-of-repo store (`projects/<config_key>/permission/`, alongside `registry.json`), so they reach
   every session and fresh worktree with no repo artifact, and are frozen per run so a mid-run edit
   never affects a running run (UFR-9). Any error falls through to the existing prompt path — the
   fail-safe direction is always *toward prompting* (UFR-2).

2. **A prompt that still fires self-resolves within 15 minutes.** The enforcer stays synchronous, so
   the bound is realized where the wait actually lives: the leaf/reviewer instruction contract the
   spine dispatches says "proceed-without-it after 15 min, report the denied action honestly," and
   the **denial is recorded deterministically** as a new `permission_denied` journal event. The spine
   absorbs it: a denied verification probe becomes a low-confidence check (FR-2), a denied substantive
   build step becomes incomplete build evidence that holds the PR a draft via the ship gate
   (UFR-6/UFR-8), and every denial is enumerated in the readout (UFR-3). The whole timeout half is
   gated on an *active run* (the `ref_lock` lease), so interactive sessions are untouched (FR-3).

The build is **test-first and additive**. The allowance layer sits strictly *below* the owner-role
floor's unconditional deny/ask, and a defensive re-check of `enforcer.gated_action` inside `evaluate`
makes "never allow a gated command" local to the function too (UFR-1). The owner-role floor
(merge/release/workflow-run/force-push/push-to-default) is never widened. Every task lands with its
test; the doc is done when the whole gate (3 validators + pytest + node smokes) is green.

## Architecture

The design is a thin extension of the *existing* single deterministic gate, plus one out-of-repo data
store, plus instruction-level steering, plus run-side bookkeeping. The command classifier already
runs, in order: non-string → canary → safety-write → owner-role gate → default `allow`. We insert one
call on the **non-gated branch only**, after `gated_action` returns falsy and before the final
`return ('allow', '')`:

```
PreToolUse(Bash) ──> enforcer.hook(host) ──> classify_command(command, host, in_scope)
        1. non-string / canary / safety-write            -> deny (unconditional)
        2. owner-role gated set (FLOOR — never allowance-checked):
             out-of-scope                                 -> allow (not gated in this repo)
             in-scope + host==claude                      -> ask
             in-scope + other host                        -> deny  (hook runs allowance.py nonce overlay)
        3. else (non-gated, today = allow):
             permission_rules.evaluate(command, cwd, run_id)
               routine family (FR-6) │ worktree-confined (FR-5) │ composed-exact (FR-8) -> allow
               error / no match / no active run                                          -> fall through
        4. default                                        -> allow (Claude host may native-ask here)
```

Four seams, each on an existing boundary:

1. **Enforcer allowance layer** — `lib/permission_rules.py` (new pure core) + one guarded call added
   to `lib/enforcer.py`'s `classify_command` non-gated branch. `permission_rules.evaluate` is the pure
   decision; it re-checks `enforcer.gated_action` defensively and refuses to allow a gated command.
2. **Out-of-repo rules store** — `projects/<config_key>/permission/rules.json` (owner-edited via the
   configure front door, provenance-stamped), `audit.json` (the FR-7 record), and
   `runs/<run_id>.json` (the per-run frozen snapshot + composed-command hashes + denial events).
   Keyed on `mode_registry.config_key` — the same common-dir key `registry.json` uses — so a fresh
   build worktree resolves the same rules.
3. **Run-active signal + timeout contract** — "a run is active" is the existing `ref_lock` lease on
   `refs/superheroes/locks/<work-item>`; its `generation` field is the `run_id`. The 15-min bound is
   an *instruction contract* embedded in every dispatched leaf/reviewer prompt, paired with the
   deterministic `permission_denied` journal event so the outcome is recorded, not merely narrated.
4. **Run-side absorption + readout** — `lib/journal.py` gains the `permission_denied` event type; the
   review loop reads a denied probe as `confidence: low` (FR-2, reusing the existing receipt/low-
   confidence path); a denied substantive build step is recorded against build provenance so
   `lib/ship_gate.py`'s `decide` returns `gate` ("build evidence incomplete/tainted"), which
   `pr_phase.mark_ready_action` / `ship_phase.py`'s `revert-draft` already read to hold the PR a draft
   (UFR-6/UFR-8); `lib/run_readout.py`'s `assemble` enumerates the journal's denial events (UFR-3).

The configure front door (`skills/configure` → a new permission sub-init) reads and edits the rules
store (FR-9); the enforcer is the single place a rule ever takes effect.

## Tech Stack

Python 3 for the deterministic core (`lib/permission_rules.py`, `lib/enforcer.py`,
`lib/journal.py`, `lib/ship_gate.py`, `lib/run_readout.py`) and its pytest suite under
`plugins/superheroes/lib/tests/`, matching the existing lib idiom: no third-party deps, `sys.path`
insert to import sibling libs, `json`/`os`/`os.path.realpath` for the store and path work. Node.js for
the spine seams in `plugins/superheroes/lib/showrunner.js` (dispatch prompt strings + `record_composed`
/ `freeze_run_rules` calls at run start), validated by the existing showrunner node smoke tests. The
out-of-repo store is plain JSON files under `control_plane.store_root()/projects/<config_key>/
permission/`, resolved via `mode_registry.config_key(cwd)` and written with atomic write-then-rename
(reuse `lib/idempotent_write.py` if present, else `os.replace`). Provenance stamps reuse the existing
`prov_entry`/provenance idiom already used by `mode_registry`/`control_plane`. The managed-worktree
root is resolved via the existing `buildtree.managed_root()` (never a re-hardcoded literal), so the
`SUPERHEROES_WORKTREES_ROOT` override stays honored. The `ref_lock` lease is
read via `ref_lock.read_lease(store, work_item)` — which returns a `(blob_sha, lease_dict)` tuple to
unpack, not the dict directly — + `ref_lock.is_stale`. CI gate: the three validators
(`validate_marketplace.py`, `validate_hosts.py`, `validate_skills.py`) plus
`pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/
eval/lib/tests/ -q` plus the node smoke tests the pytest wrapper drives.

## Tasks

### Task 1: worktree_confined — realpath strict-descendant check (FR-5, UFR-5)

Write `plugins/superheroes/lib/tests/test_permission_rules.py` first. Assert
`permission_rules.worktree_confined(command, cwd)` is `True` only when `os.path.realpath(cwd)` is a
**strict descendant** of `os.path.realpath(pr._worktrees_root())` — the canonical managed-worktree root
`_worktrees_root()` resolves via `buildtree.managed_root()` (which honors the `SUPERHEROES_WORKTREES_ROOT`
override; never re-hardcode the `~/.superheroes-worktrees` literal in the check) — AND the command is an
interpreter invocation. The tests monkeypatch `pr._worktrees_root` to a `tmp_path`-based root, so no test
depends on the real home dir. Path tricks (symlink into the worktrees root, `..` parent-hop out of it,
the root itself) earn nothing.

```python
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import permission_rules as pr

def test_real_worktree_interpreter_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc123"
    wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'print(1)'", str(wt)) is True

def test_root_itself_is_not_a_strict_descendant(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(root)) is False

def test_parent_hop_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "wt").mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # cwd escapes the root via `..` — realpath resolves it OUT of the root
    escaped = os.path.join(str(root), "wt", "..", "..")
    assert pr.worktree_confined("python3 -c 'x'", escaped) is False

def test_symlink_into_root_is_resolved_and_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    (root / "real").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(root / "real")
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    # a symlink whose realpath IS under root -> confined
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is True

def test_symlink_lookalike_outside_root_earns_nothing(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    root.mkdir(parents=True)
    outside = tmp_path / "evil"
    outside.mkdir()
    link = root.parent / ".superheroes-worktrees-evil"   # name-prefix lookalike, not a descendant
    link.symlink_to(outside)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("python3 -c 'x'", str(link)) is False

def test_non_interpreter_command_not_confined(monkeypatch, tmp_path):
    root = tmp_path / ".superheroes-worktrees"
    wt = root / "abc"; wt.mkdir(parents=True)
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(root))
    assert pr.worktree_confined("gh pr merge 1", str(wt)) is False

def test_missing_or_bad_cwd_not_confined(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "_worktrees_root", lambda: str(tmp_path / ".superheroes-worktrees"))
    assert pr.worktree_confined("python3 -c 'x'", None) is False
    assert pr.worktree_confined("python3 -c 'x'", "") is False
```

Then create `plugins/superheroes/lib/permission_rules.py` with:
- `_worktrees_root()` → **delegate to the existing canonical resolver** `buildtree.managed_root()` (add
  `import buildtree` alongside the other sibling-lib imports). Do NOT re-hardcode the
  `~/.superheroes-worktrees` literal here — `buildtree.managed_root()` already realpaths
  `os.path.expanduser(...)` AND honors the `SUPERHEROES_WORKTREES_ROOT` env override (the `store_root()`
  pattern). Re-hardcoding the literal would silently break FR-5 for any run whose worktrees root is
  relocated via that env var (the confined check would never match a real managed worktree). This stays
  the seam the tests monkeypatch (`monkeypatch.setattr(pr, "_worktrees_root", ...)`); `buildtree` already
  realpaths, so `_worktrees_root` just returns its result.
- `_INTERPRETER = re.compile(...)` matching interpreter invocations (`python`, `python3`, `node`,
  `ruby`, `perl`, `bash -c`, `sh -c`, `zsh -c` — the improvised-probe shapes; a leading `env`/path
  prefix tolerated). Keep it a literal enumerated set, not a catch-all.
- `worktree_confined(command, cwd)`: return `False` for a falsy/non-str `cwd`; compute
  `real = os.path.realpath(cwd)` and `root = _worktrees_root()`; require
  `os.path.commonpath([real, root]) == root and real != root` (strict descendant); AND require
  `_INTERPRETER.search(command)`. Wrap in `try/except Exception: return False` (UFR-2/UFR-5).

Do NOT let a `ValueError` from `commonpath` (different drives) leak — catch it to `False`.

### Task 2: Rules store paths + provenance-checked read (FR-6 substrate, UFR-9)

Add to `test_permission_rules.py`. Assert `permission_rules._store_dir(cwd, root=...)` resolves to
`<root>/projects/<config_key>/permission/` (reusing `mode_registry.config_key`), and that
`rules(cwd, root=...)` reads `rules.json`, **dropping any entry whose `provenance` stamp is absent or
malformed** (UFR-9) — those fall back to prompting, never to allowing.

```python
import json
def _write_rules(root, cwd, entries, monkeypatch):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(root, "projects", "KEY", "permission")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "rules.json"), "w") as f:
        json.dump({"rules": entries}, f)
    return d

def test_store_dir_is_config_keyed(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    got = pr._store_dir("/some/cwd", root=str(tmp_path))
    assert got == os.path.join(str(tmp_path), "projects", "KEY", "permission")

def test_rules_reads_provenance_valid_only(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
        {"family": "sneaky", "pattern": "gh pr merge", "provenance": None},   # untraceable -> ignored
        {"family": "sneaky2", "pattern": "rm -rf"},                            # no provenance key -> ignored
    ], monkeypatch)
    got = pr.rules("/cwd", root=str(tmp_path))
    fams = [r["family"] for r in got]
    assert fams == ["test-run"]

def test_rules_missing_store_is_empty(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "NONE")
    assert pr.rules("/cwd", root=str(tmp_path)) == []

def test_rules_corrupt_store_is_empty_not_raise(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission"); os.makedirs(d)
    with open(os.path.join(d, "rules.json"), "w") as f:
        f.write("{ this is not json")
    assert pr.rules("/cwd", root=str(tmp_path)) == []   # UFR-2 fail-safe: corrupt -> empty -> prompt
```

Then implement in `permission_rules.py`:
- `_store_dir(cwd, root=None)`: `base = root or control_plane.store_root()`; return
  `os.path.join(base, "projects", mode_registry.config_key(cwd), "permission")`.
- `_provenance_ok(entry)`: `True` iff `entry.get("provenance")` is a dict carrying a `source` and an
  `at` timestamp (the shape the front door stamps in Task 9). Anything else → `False`.
- `rules(cwd, root=None)`: read `<store_dir>/rules.json`; return `[]` on missing/corrupt/non-dict
  (fail-safe); filter to entries where `_provenance_ok(entry)`; return the list.

### Task 3: freeze_run_rules / frozen_rules / record_composed + lazy reap (FR-8, UFR-9, retention)

Add to `test_permission_rules.py`. Assert `freeze_run_rules(run_id, cwd, root=...)` snapshots the
current provenance-valid `rules.json` into `runs/<run_id>.json`, `frozen_rules(run_id, cwd, root=...)`
reads *that snapshot* (not live `rules.json`), `record_composed(run_id, command, cwd, root=...)` adds a
byte-exact composed-command hash to the same run file, and a run-start freeze reaps stale sibling run
files (no live lease, older than 30 days) but keeps a live/recent one.

```python
def test_freeze_snapshots_current_rules(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
    ], monkeypatch)
    pr.freeze_run_rules("RUN1", "/cwd", root=str(tmp_path))
    frozen = pr.frozen_rules("RUN1", "/cwd", root=str(tmp_path))
    assert [r["family"] for r in frozen["rules"]] == ["test-run"]
    assert frozen["composed"] == []

def test_frozen_read_ignores_live_edit(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "2026-07-05T00:00:00Z"}},
    ], monkeypatch)
    pr.freeze_run_rules("RUN2", "/cwd", root=str(tmp_path))
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": "pytest", "provenance": {"source": "configure", "at": "x"}},
        {"family": "broad", "pattern": "gh pr merge", "provenance": {"source": "configure", "at": "y"}},  # mid-run edit
    ], monkeypatch)
    frozen = pr.frozen_rules("RUN2", "/cwd", root=str(tmp_path))
    assert [r["family"] for r in frozen["rules"]] == ["test-run"]   # UFR-9: edit invisible to the run

def test_record_composed_is_exact(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("RUN3", "/cwd", root=str(tmp_path))
    pr.record_composed("RUN3", "gh pr create --draft --title X", "/cwd", root=str(tmp_path))
    frozen = pr.frozen_rules("RUN3", "/cwd", root=str(tmp_path))
    assert pr._hash("gh pr create --draft --title X") in frozen["composed"]
    assert pr._hash("gh pr create --draft --title Y") not in frozen["composed"]

def test_reap_deletes_stale_keeps_recent(monkeypatch, tmp_path):
    import time
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    d = os.path.join(str(tmp_path), "projects", "KEY", "permission", "runs")
    os.makedirs(d, exist_ok=True)
    stale = os.path.join(d, "OLD.json"); open(stale, "w").write("{}")
    old = time.time() - 40 * 86400
    os.utime(stale, (old, old))
    monkeypatch.setattr(pr, "_run_is_live", lambda rid, cwd, root: False)  # no live lease
    pr.freeze_run_rules("NEW", "/cwd", root=str(tmp_path))
    assert not os.path.exists(stale)                 # stale + no lease -> reaped
    assert os.path.exists(os.path.join(d, "NEW.json"))
```

Then implement:
- `_hash(command)`: `hashlib.sha256(command.encode("utf-8")).hexdigest()` (byte-exact — any char diff
  or different run misses, per FR-8's exact-match rule).
- `_run_path(run_id, cwd, root)`: `<store_dir>/runs/<run_id>.json`.
- `freeze_run_rules(run_id, cwd, root=None)`: build `{"rules": rules(cwd, root), "composed": [],
  "denials": []}`, atomic-write it to the run path (mkdir `runs/` first), THEN `_reap_stale(cwd,
  root)`. Run-*start* reap only (crash-tolerant — a crashed run never leaks its file forever).
- `frozen_rules(run_id, cwd, root=None)`: read the run file; on missing/corrupt return
  `{"rules": [], "composed": [], "denials": []}` (fail-safe → no allowance → prompt).
- `record_composed(run_id, command, cwd, root=None)`: read-modify-write, append `_hash(command)` to
  `composed` if absent (idempotent).
- `_run_is_live(run_id, cwd, root)`: `True` iff a fresh (`not ref_lock.is_stale`) lease exists whose
  `generation == run_id`; a seam the reap test stubs.
- `_reap_stale(cwd, root)`: for each `runs/*.json`, delete iff `not _run_is_live(...)` AND mtime older
  than `30 * 86400`. Guard the whole reap in `try/except` — a reap error must never fail a freeze.

### Task 4: evaluate — the pure allowance decision (FR-5/6/8, UFR-1, UFR-2)

Add to `test_permission_rules.py`. Assert `evaluate(command, cwd, run_id, root=...)` returns
`("allow", reason)` iff a frozen routine family matches (FR-6), the command is worktree-confined
(FR-5), OR it byte-equals a composed command frozen for `run_id` (FR-8); it returns `("fall", ...)` on
no match, on any error (UFR-2), and — belt-and-suspenders — it **never** allows a gated command even
if a rule would match it (UFR-1). With no active run (`run_id` None), the composed/freeze machinery is
inert.

```python
def test_evaluate_routine_family_allows(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "test-run", "pattern": r"\bpytest\b", "provenance": {"source": "configure", "at": "z"}},
    ], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("python3 -m pytest -q", "/cwd", "R", root=str(tmp_path))[0] == "allow"

def test_evaluate_composed_exact_allows_only_exact(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    pr.record_composed("R", "gh pr create --draft", "/cwd", root=str(tmp_path))
    assert pr.evaluate("gh pr create --draft", "/cwd", "R", root=str(tmp_path))[0] == "allow"
    assert pr.evaluate("gh pr create --draft ", "/cwd", "R", root=str(tmp_path))[0] == "fall"  # 1-char diff

def test_evaluate_gated_command_never_allowed_even_with_matching_rule(monkeypatch, tmp_path):
    # A malicious/overbroad rule that would match a floor command must NOT allow it (UFR-1).
    _write_rules(str(tmp_path), "/cwd", [
        {"family": "bad", "pattern": r"gh pr merge", "provenance": {"source": "configure", "at": "z"}},
    ], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("gh pr merge 1", "/cwd", "R", root=str(tmp_path))[0] == "fall"

def test_evaluate_no_match_falls_through(monkeypatch, tmp_path):
    _write_rules(str(tmp_path), "/cwd", [], monkeypatch)
    pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
    assert pr.evaluate("curl http://evil", "/cwd", "R", root=str(tmp_path))[0] == "fall"

def test_evaluate_any_error_falls_through(monkeypatch, tmp_path):
    monkeypatch.setattr(pr, "frozen_rules", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert pr.evaluate("python3 -m pytest", "/cwd", "R", root=str(tmp_path))[0] == "fall"  # UFR-2
```

Then implement `evaluate(command, cwd, run_id, root=None)`:
1. Non-str command → `("fall", "non-string")`.
2. **Defensive floor re-check** (UFR-1): `if enforcer.gated_action(command): return ("fall",
   "gated command — floor owns it")`. This reproduces only the gated/not-gated partition; that is
   sufficient because `evaluate` is called solely where the floor already resolved to the non-gated
   default `allow`.
3. Wrap the rest in `try/except Exception: return ("fall", "allowance error (fail-safe)")` (UFR-2).
4. Load `frozen_rules(run_id, cwd, root)`. Composed-exact (FR-8): `if _hash(command) in
   frozen["composed"]: return ("allow", "composed-exact")`. Routine family (FR-6): for each rule,
   `re.search(rule["pattern"], command)` → `("allow", "routine:%s" % rule["family"])`. Worktree
   (FR-5): `if worktree_confined(command, cwd): return ("allow", "worktree-confined")`.
5. Otherwise `("fall", "no matching allowance")`.

Return values are `"allow"` / `"fall"` so the enforcer can distinguish "turn into allow" from "leave
today's outcome alone."

### Task 5: Wire the allowance layer into enforcer.classify_command (non-gated branch only, UFR-1/UFR-2)

Add tests to `plugins/superheroes/lib/tests/test_enforcer.py` (extend the existing file). Assert the
allowance call fires **only** on the non-gated branch and never widens the floor.

```python
import enforcer, permission_rules

def test_owner_role_outcome_unchanged_with_rules_present(monkeypatch):
    # A rule that would match a merge must never flip the floor's ask/deny.
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("allow", "should-not-be-consulted"))
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=True)[0] == "ask"
    assert enforcer.classify_command("gh pr merge 1", host="codex", in_scope=True)[0] == "deny"
    assert enforcer.classify_command("gh pr merge 1", host="claude", in_scope=False)[0] == "allow"

def test_non_gated_command_allowed_when_rule_matches(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("allow", "routine:test-run"))
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)[0] == "allow"

def test_non_gated_command_falls_through_to_default_allow(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("fall", "no match"))
    # today's outcome is preserved (default allow)
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)[0] == "allow"

def test_allowance_exception_falls_through(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    assert enforcer.classify_command("python3 -m pytest", host="claude", in_scope=True)[0] == "allow"

def test_unconditional_surfaces_still_deny_before_allowance(monkeypatch):
    monkeypatch.setattr(permission_rules, "evaluate", lambda *a, **k: ("allow", "should-not-be-reached"))
    assert enforcer.classify_command(": workhorse-enforcer-canary")[0] == "deny"
```

Then change `enforcer.py`:
- Add `import permission_rules` near the `allowance`/`escalation` imports.
- Give `classify_command` an optional `cwd=None, run_id=None` so the hook can thread them; keep the
  existing signature order stable by appending kwargs.
- On the non-gated branch — the final `return ("allow", "")` — replace with:
  ```python
  try:
      verdict, why = permission_rules.evaluate(command, cwd, run_id)
      if verdict == "allow":
          return ("allow", "auto-allowed (%s)" % why)
  except Exception:
      pass
  return ("allow", "")
  ```
  The canary, safety-write, and owner-role gate all `return` *before* this, so the allowance layer is
  never reached for them (belt-and-suspenders with Task 4's re-check).
- Do NOT touch the owner-role gate arms, the canary/safety-write surfaces, or the hook's Codex
  `allowance.py` nonce overlay.

### Task 6: enforcer.hook threads cwd + run_id; selfcheck asserts the invariant (UFR-1, observability)

Add to `test_enforcer.py`. Assert `hook` passes the payload's `cwd` and the active run's `run_id`
(from the lease) into `classify_command`, and that `selfcheck` fails if the allowance layer would
allow an owner-role command.

```python
def test_hook_passes_cwd_and_run_id(monkeypatch):
    seen = {}
    def fake_classify(command, host="codex", in_scope=True, cwd=None, run_id=None):
        seen.update(cwd=cwd, run_id=run_id); return ("allow", "")
    monkeypatch.setattr(enforcer, "classify_command", fake_classify)
    monkeypatch.setattr(enforcer, "_active_run_id", lambda cwd: "RUN9")
    payload = '{"tool_name":"Bash","tool_input":{"command":"python3 -m pytest"},"cwd":"/w"}'
    enforcer.hook(payload, host="claude")
    assert seen["cwd"] == "/w" and seen["run_id"] == "RUN9"

def test_selfcheck_matrix_holds_with_allowance(monkeypatch):
    assert enforcer.selfcheck() == 0   # the added assertions pass on a correct build
```

Then change `enforcer.py`:
- Add `_active_run_id(cwd)`: resolve the control-plane store (via `mode_registry` / `control_plane`),
  read the work-item's lease with `ref_lock.read_lease`. Note `read_lease(store, work_item)` returns a
  `(blob_sha, lease_dict)` **tuple** — unpack it (`_sha, lease = ref_lock.read_lease(store, work_item)`),
  it is NOT the lease dict directly; `lease` is `None` when the ref is absent or the blob is unreadable.
  Return `lease["generation"]` iff `lease` is a present dict and
  `not ref_lock.is_stale(lease, ref_lock.DEFAULT_TTL)`, else `None`. Fail-safe: any error (including a
  `None` lease) → `None` (no active run → allowance's composed/freeze machinery is inert, FR-3). Cache
  per hook invocation (a single Bash call resolves it once).
- In `hook`, for the `_CMD_TOOLS` branch, pass `cwd=cwd, run_id=_active_run_id(cwd)` into
  `classify_command`.
- Extend `selfcheck`'s `ok` matrix with: (a) an owner-role command keeps its per-host/scope outcome
  with a matching allowance rule present (monkeypatch-free: assert `classify_command("gh pr merge 1",
  host="claude", in_scope=True)[0] == "ask"` etc. still hold — Task 4's re-check guarantees it), and
  (b) a would-be routine command allows only when a matching rule exists (assert a command with no
  store present stays `allow`-by-default, i.e. the layer never *denies*). A broken allowance layer that
  raises must be caught so `selfcheck` reports it, not crash.

### Task 7: Add the permission_denied journal event type (hard prerequisite for absorption)

Add to `plugins/superheroes/lib/tests/test_journal.py` (extend). Assert `journal.append` accepts
`"permission_denied"` and rejects an unknown type (the existing park-on-unknown behavior is preserved).

```python
import journal

def test_permission_denied_is_a_valid_event_type(tmp_path):
    p = str(tmp_path / "events.jsonl")
    journal.append(p, "permission_denied", step="build:task-3", detail={"command": "python3 -c x"})
    lines = open(p).read().splitlines()
    assert any('"type": "permission_denied"' in l for l in lines)

def test_unknown_event_type_still_parks(tmp_path):
    p = str(tmp_path / "events.jsonl")
    try:
        journal.append(p, "not_a_real_type")
        assert False, "expected DurableWriteError"
    except journal.DurableWriteError:
        pass
```

Then add `"permission_denied"` to `journal.py`'s `EVENT_TYPES` set. This is a **hard prerequisite**:
`journal.append` raises `DurableWriteError` (→ orchestrator park) for any type absent from the set, so
skipping this would park every run that hits a timeout denial — the exact failure this feature
prevents. Read-side is forward/backward compatible: older readers and denial-unaware consumers ignore
the new type.

### Task 8: Ship gate reads a denied build step as incomplete evidence → gate (UFR-6, UFR-8)

Add to `plugins/superheroes/lib/tests/test_ship_gate.py` (extend). Assert that when the run's build
provenance carries a denial, `ship_gate.decide` returns `{"action": "gate", ...}` even though the build
step "ran" — a denied substantive build sub-step is incomplete/tainted evidence, not "build ran."

```python
import ship_gate

def _clean_review(head):
    return {"action": ship_gate._TERMINAL}

def test_denied_build_step_gates_even_with_build_present():
    prov = {"build": {"engine": "claude", "head": "abc"},
            "review": {"covers": "abc"},
            "buildDenials": [{"step": "task-3", "command": "python3 -c x"}]}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc")
    assert out["action"] == "gate"
    assert "incomplete" in out["reason"] or "denied" in out["reason"]

def test_clean_build_still_proceeds():
    prov = {"build": {"engine": "claude", "head": "abc"}, "review": {"covers": "abc"}}
    out = ship_gate.decide(prov, _clean_review("abc"), "abc")
    assert out["action"] == "proceed"
```

Then change `ship_gate.py`:
- Add a helper `record_build_denial(path, *, step, command)` alongside `write_build` (read-modify-
  write; append to a `buildDenials` list, never clobber) — the seam the spine calls when a substantive
  build step is denied.
- In `decide`, after the build-present check (step 1) and before the review-terminal check, add:
  ```python
  denials = provenance.get("buildDenials") if isinstance(provenance, dict) else None
  if denials:
      return {"action": "gate",
              "reason": "build evidence incomplete — a substantive build step was denied "
                        "by the 15-min timeout (%d step(s))" % len(denials)}
  ```
  This is the *one* new gate input the plan adds. The draft-hold then reuses the existing path: a
  `gate` ship decision keeps the PR a draft via `pr_phase.mark_ready_action` / `ship_phase.py`'s
  `revert-draft` (UFR-8) — no change to `pr_phase.py`, and NOT via `panel_tally.roundGate` (whose
  `incomplete` gate is the distinct reviewer-roster gap).

### Task 9: run_readout enumerates timeout denials (UFR-3)

Add to `plugins/superheroes/lib/tests/test_run_readout.py` (extend). Assert `run_readout.assemble`
adds a `permissionDenials` list to the readout context — one entry per `permission_denied` journal
event, naming the affected step/check — and that a run with no denials produces an empty list, never a
silent skip.

`assemble(state)` today reads only **flat scalar keys** off `state` (e.g. `state.get("ci")`,
`state.get("pr_url")`); it does NOT carry an inlined `state["journal"]` list, and journal events are
read module-wide via `journal.read_events(events_path)` (the `control_plane` `events` path), never as a
pre-materialized list. So the denial source is the run's `events` path threaded onto `state` (e.g.
`state["events_path"]`), and the test writes a real `events.jsonl` via `journal.append` and points
`assemble` at it — matching the module's derive-from-events_path convention rather than inventing a raw
`state["journal"]` list.

```python
import os, run_readout, journal

def test_assemble_enumerates_permission_denials(tmp_path):
    ep = str(tmp_path / "events.jsonl")
    journal.append(ep, "permission_denied", step="build:task-3", detail={"command": "python3 -c x"})
    journal.append(ep, "step_completed", step="build:task-4")
    journal.append(ep, "permission_denied", step="review:code-reviewer", detail={"check": "probe"})
    ctx = run_readout.assemble({"events_path": ep})
    denials = ctx["permissionDenials"]
    assert len(denials) == 2
    assert denials[0]["step"] == "build:task-3"
    assert denials[1]["step"] == "review:code-reviewer"

def test_assemble_no_denials_is_empty_list(tmp_path):
    ep = str(tmp_path / "events.jsonl")           # absent/empty events -> empty list, never a skip
    ctx = run_readout.assemble({"events_path": ep})
    assert ctx["permissionDenials"] == []
```

Then change `run_readout.py`'s `assemble` additively: resolve the run's `events` path off the `state`
dict `assemble` already receives (thread `events_path` onto `state` from the caller — the smallest
additive change, since `assemble` reads flat keys and does not receive an inlined journal list), read
its events via `journal.read_events(events_path)` (fail-soft: a missing/unreadable path yields no
denials, never a raise), filter to `isinstance(ev, dict) and ev.get("type") == "permission_denied"`, and
map each to `{"step": ev.get("step"), "detail": ev.get("detail")}` under a new `permissionDenials`
context key. Purely additive — no denial/incomplete/draft *decision* logic goes here (that stays in
`ship_gate.py`/`pr_phase.py`/`ship_phase.py`), matching the plan's "enumerate, don't decide" split.

### Task 10: Review loop reads a denied probe as low-confidence (FR-2)

Add a node smoke assertion (extend the showrunner node smoke suite the pytest wrapper drives, e.g.
`plugins/superheroes/lib/tests/showrunner_smoke*.js` / the existing smoke harness). Assert that when a
reviewer leaf's verification probe is denied (a `permission_denied` event tagged to that reviewer), the
review loop treats the dimension as `confidence: low` and routes it to the existing deep-retry /
degraded-dimension path — and that a check whose deep retry is *also* denied is reported as a degraded
dimension and not retried again (the loop's existing single-retry ceiling, FR-2 rule).

Then, in `plugins/superheroes/lib/showrunner.js`, at the reviewer-result assembly seam — the
`ensureReviewerShape(out, opts)` function (the confidence is normalized/derived there, currently around
lines 220–247; `REVIEWER_RESULT_INSTRUCTION` at 214–215 is only the leaf-instruction string, not the
computation): when the reviewer's run recorded a
`permission_denied` for its probe, force that dimension's `confidence` to `'low'` and write the denial
into the journal via the Python `journal.append` seam (`permission_denied`, step
`review:<reviewer>`). Reuse the existing low-confidence → deep-retry path; add no new retry cycle. The
"deep retry also denied → report degraded, don't re-cycle" bound reuses the loop's existing single-
retry ceiling — assert it, do not add a new counter.

### Task 11: Reviewer/leaf instruction contracts — steer probes + 15-min proceed contract (FR-1, FR-4, UFR-6)

Add a node smoke assertion that every dispatched leaf/reviewer prompt string in `showrunner.js`
carries BOTH: (a) the FR-4 steering — name the throwaway-test-file-in-worktree + allowed test-run
family as the required probe shape and explicitly discourage inline interpreter probes; and (b) the
15-minute contract — "if an action awaits owner permission with no response for 15 minutes, proceed
without it and report the denied action honestly (never as done)." Assert the strings are present in
the reviewer prompt and the builder/leaf prompt.

```js
// showrunner smoke: assert the contract text is embedded in the dispatched prompts
assert(reviewerPrompt.includes('throwaway test file') && reviewerPrompt.includes('do not improvise inline'))
assert(leafPrompt.includes('15 minutes') && leafPrompt.includes('report the denied action'))
```

Then edit the prompt strings in `showrunner.js` (the `REVIEWER_RESULT_INSTRUCTION` region and the
builder/leaf dispatch prompt) to embed both blocks. Cross-reference the same steering text into
`plugins/superheroes/skills/review-code/` reference material (a short pointer, so the human-facing doc
and the dispatched prompt agree). Keep the additions concise — the SKILL.md 505-line ceiling and the
"oversized tool_result derails subagents" gotcha both apply; a tight paragraph, not a section.

### Task 12: Spine freezes rules + records composed commands at run start (FR-8, UFR-9 wiring)

Add a node smoke assertion that the spine, at run start, calls `permission_rules.freeze_run_rules(run_id,
cwd)` once (via the Python seam) and calls `record_composed(run_id, command)` for each command it
composes for a leaf — so `evaluate`'s composed-exact set (Task 4) is populated for the run that
composed them, and only that run.

Then wire `showrunner.js`: at the run-start point where the `run_id` (the lease `generation`) is known,
shell the Python seam once to `freeze_run_rules`; at each point the spine composes a command string for
a leaf to execute, shell `record_composed(run_id, command)`. Use the existing Python-shim pattern the
spine already uses to call lib helpers (do not re-implement hashing in JS — call
`permission_rules.record_composed` so the hash matches `evaluate`'s byte-exact check). Fail-open: a
freeze/record error is logged and the run proceeds (the allowance simply won't fire → prompt path,
UFR-2).

### Task 13: Configure front door — permission sub-init + one-screen view + rule CRUD (FR-9, UFR-9)

Add to `test_permission_rules.py` for the write surface, and a configure-view test.

```python
def test_set_rule_stamps_provenance(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.set_rule("/cwd", {"family": "test-run", "pattern": r"\bpytest\b"}, root=str(tmp_path))
    got = pr.rules("/cwd", root=str(tmp_path))
    assert got[0]["family"] == "test-run"
    assert got[0]["provenance"]["source"] == "configure"   # front-door stamp -> evaluate honors it

def test_remove_rule(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.set_rule("/cwd", {"family": "a", "pattern": "x"}, root=str(tmp_path))
    pr.set_rule("/cwd", {"family": "b", "pattern": "y"}, root=str(tmp_path))
    pr.remove_rule("/cwd", "a", root=str(tmp_path))
    assert [r["family"] for r in pr.rules("/cwd", root=str(tmp_path))] == ["b"]
```

Then implement:
- `set_rule(cwd, rule, root=None)`: read-modify-write `rules.json`; stamp
  `rule["provenance"] = {"source": "configure", "at": <utc-now>}` (the ONLY writer of the stamp
  `_provenance_ok` accepts, so a direct hand-edit that omits it is ignored at evaluate time — UFR-9);
  atomic write.
- `remove_rule(cwd, family, root=None)`: read-modify-write, drop entries matching `family`.
- `configure_view` (in `lib/configure_view.py`): add a "Permission posture" section listing the full
  provenance-valid allow set on one screen (FR-9), reading via `permission_rules.rules`.
- `skills/configure/SKILL.md` + a permission sub-init (mirroring `review-init` / `architect-init` /
  `test-pilot-init`): route the owner's view/edit through `set_rule` / `remove_rule`. It is the only
  sanctioned change path (FR-9). Keep the SKILL edit tight (505-line ceiling).

### Task 14: Seed the initial rules.json families + audit.json from the FR-7 audit (FR-6, FR-7)

Add a test asserting the seeded families cover the routine set the spec enumerates and **exclude** the
owner-role set.

```python
def test_seed_families_cover_routine_exclude_floor(monkeypatch, tmp_path):
    import mode_registry
    monkeypatch.setattr(mode_registry, "config_key", lambda c: "KEY")
    pr.seed_default_rules("/cwd", root=str(tmp_path))
    fams = {r["family"] for r in pr.rules("/cwd", root=str(tmp_path))}
    assert {"test-run", "validators", "worktree-vcs", "draft-pr"} <= fams
    # the owner-role floor set must NOT be auto-allowed by any seeded rule
    for cmd in ["gh pr merge 1", "gh release create v1", "git push --force",
                "gh workflow run ci.yml", "git push origin main"]:
        pr.freeze_run_rules("R", "/cwd", root=str(tmp_path))
        assert pr.evaluate(cmd, "/cwd", "R", root=str(tmp_path))[0] == "fall"
```

Then implement `seed_default_rules(cwd, root=None)`: write, via `set_rule` (so each is provenance-
stamped), the four routine families the spec/plan name:
- **test-run** — the repo's test invocation (`\bpytest\b`, `python3 -m pytest`, the node smoke runner).
- **validators** — the three validators (`validate_marketplace\.py`, `validate_hosts\.py`,
  `validate_skills\.py`).
- **worktree-vcs** — VCS confined to managed worktrees, **excluding** the owner-role set (the exclusion
  is guaranteed structurally by Task 4's `enforcer.gated_action` re-check, but the seeded patterns are
  also written narrow: `git add`, `git commit`, `git status`, `git diff`, a non-default-branch
  `git push` that is NOT force and NOT to `main` — the floor still catches those).
- **draft-pr** — `gh pr create --draft`, `gh pr edit` (title/body/metadata), the draft→ready promotion
  step; NOT `gh pr edit --base` (changing base is not in the family — normal prompt path).
Also create `audit.json` recording the prompt-provoking commands observed in a full run and each one's
disposition (allow-rule id or "keep prompting"); the seeded families must each trace to an audit entry
(FR-7). Author the audit from a real run's prompt inventory during the build.

### Task 15: Full gate — validators + pytest + node smokes green

Run the whole CI gate locally and make it green:

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```

Fix any failures. Confirm: (a) the enforcer `selfcheck` still exits 0 with the allowance layer present
and asserts the owner-role matrix holds (Task 6); (b) the new `permission_denied` journal event round-
trips (Task 7); (c) no repo artifact is written anywhere under the repo tree by the rules store (grep
the worktree for `permission/rules.json` — it must resolve only under the out-of-repo store); (d) the
node smoke suite the pytest wrapper drives passes the contract-string, freeze/record, and low-
confidence assertions (Tasks 10–12). The doc is done when the full gate is green and the owner-role
floor blocks exactly what it blocked before — nothing less, nothing more.
