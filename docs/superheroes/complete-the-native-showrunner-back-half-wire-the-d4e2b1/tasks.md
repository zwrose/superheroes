---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: complete-the-native-showrunner-back-half-wire-the-d4e2b1
issue: 120
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-30"
updated: "2026-06-30"
---
# Complete the native showrunner back-half — wire the deferred remediation (CI-fix loop, freshen, fence) — Tasks

> **Build contract (superheroes).** These tasks are executed by the producer's **Build**
> phase — **not here**. Build invokes superpowers **subagent-driven-development** with the
> worktree **pre-verified, not created**, and **without** `finishing-a-development-branch`;
> the **producer enforces both clips** at invocation. `size: large`. Advance to Build
> only once `gates.review: passed`.

**Goal:** Wire the manual producer's step-8/step-9 recovery (base catch-up, bounded CI-fix loop, return-to-draft, concurrency fence, structured hand-back) into the native showrunner `shipPhase`, reusing the parity-locked deciders unchanged.

**Architecture:** `shipPhase` becomes the orchestrator: it gathers world-reads and performs the mechanical merge/push/fix/flip via new `ship_phase.py` steps, while the existing pure deciders (`freshness.decide`, `ci_loop.decide`, `ci_status.classify`, `pr_phase.mark_ready_action`, `journal.ci_attempts`, `readout.build_readout`) remain the source of truth for *what to do*. Every new branch-/PR-mutating boundary renews-then-fences the lease generation (fail-closed). A new generic `idempotent_write.py` primitive (read-reality, apply-once) backs create/ready-flip/draft-flip/push-reconcile so #118 can generalize it spine-wide.

**Tech Stack:** Node.js (the spine `showrunner.js`, bundled to `showrunner.bundle.js`), Python 3 (the `ship_phase.py` leaf + deciders), `git`/`gh` CLIs, pytest + standalone `node` smoke scripts.

## Global Constraints

- **Commits:** Conventional Commits scoped to `superheroes` (e.g. `feat(superheroes): wire native ship-phase CI-fix loop`). Do **not** hand-edit `version` in either `plugin.json` — release-please owns it.
- **Deciders are byte-for-byte frozen:** no logic change to `freshness.py`, `ci_loop.py`, `ci_status.py`, `pr_phase.py`, `journal.ci_attempts`, `readout.build_readout`/`scrub`. This work *connects* them. (Adding an `--attempt` parameter passthrough in `ship_phase.py` is a caller change, not a decider change.)
- **No change to the manual producer** (`skills/workhorse/SKILL.md`, `build_phase.js`) — it is the mirrored reference.
- **Push boundary (FR-8/FR-9):** the showrunner never merges the PR, never force-pushes, never pushes to the default branch. Every push is an ordinary non-force push to the work-item's own branch. These stay on the permitted side of `enforcer.py` (unchanged).
- **Node-smoke discovery guard:** every new `plugins/superheroes/lib/tests/showrunner_*_smoke.js` MUST be added to `SHOWRUNNER_SMOKES` in `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py`, or `test_showrunner_node_smokes_are_enforced` fails.
- **Bundle drift:** any edit to `showrunner.js` MUST be followed by `node plugins/superheroes/lib/bundle_showrunner.js` to regenerate `showrunner.bundle.js`; commit both. `test_bundle_drift.py` runs `bundle_showrunner.js --check`.
- **#118 coordination:** build the idempotency guard as a GENERIC primitive (`idempotent_write.py`) with ≥3 real call sites; document the fence/lease seam; leave clean per-stretch seams — do NOT fold couriers or relabel leaves (that is #118). The hand-back is best-effort: the run's advance/ship outcome must NOT depend on the hand-back landing.
- **Local CI gate (run before any push):**
  ```bash
  python3 .github/scripts/validate_marketplace.py
  python3 .github/scripts/validate_hosts.py
  python3 .github/scripts/validate_skills.py
  python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
  ```

---

### Task 1: Generic per-write idempotency primitive (`idempotent_write.py`)

**Files:**
- Create: `plugins/superheroes/lib/idempotent_write.py`
- Test: `plugins/superheroes/lib/tests/test_idempotent_write.py`

**Interfaces:**
- Consumes: nothing (foundational, pure — reader/applier injected).
- Produces: `idempotent_apply(key, current_reader, apply_fn) -> {"key": str, "already": bool, "applied": bool, "ok": bool, "reason": str, "detail": Any}`. `current_reader() -> (reflects: bool|None, detail)` (None = unreadable → fail-closed, no apply). `apply_fn() -> (ok: bool, detail)` (called only when not already reflected).

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_idempotent_write.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import idempotent_write as iw


def test_already_reflected_is_a_noop():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (True, "isDraft=false"),
                              apply_fn=lambda: calls.append("applied") or (True, "pushed"))
    assert res["already"] is True
    assert res["applied"] is False
    assert res["ok"] is True
    assert calls == []                     # apply must NOT run when reality already reflects the write


def test_not_reflected_applies_once():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (False, "isDraft=true"),
                              apply_fn=lambda: (calls.append("a"), (True, "flipped"))[1])
    assert res["already"] is False
    assert res["applied"] is True
    assert res["ok"] is True
    assert calls == ["a"]


def test_unreadable_current_state_fails_closed():
    calls = []
    res = iw.idempotent_apply("ready:pr=7",
                              current_reader=lambda: (None, "gh read failed"),
                              apply_fn=lambda: calls.append("a") or (True, "x"))
    assert res["ok"] is False
    assert res["applied"] is False
    assert calls == []                     # fail-closed: never apply against an unreadable state


def test_apply_failure_propagates_not_ok():
    res = iw.idempotent_apply("head=abc",
                              current_reader=lambda: (False, "behind"),
                              apply_fn=lambda: (False, "push rejected"))
    assert res["applied"] is True
    assert res["ok"] is False
    assert res["reason"]


def test_reconcile_head_pattern_in_sync_and_local_ahead():
    # Teeth for ship_phase reconcile-head (UFR-6 call-site 1): it wires reader=(remote==local),
    # applier=push, key='head=<local>'. Drive both happy paths through the primitive with that exact
    # shape — in sync (remote==local) is a no-op; local-ahead (remote!=local) applies the push once.
    pushed = []
    in_sync = iw.idempotent_apply("head=abc",
                                  current_reader=lambda: (True, "remote=abc local=abc"),
                                  apply_fn=lambda: pushed.append(1) or (True, "pushed"))
    assert in_sync["already"] is True and in_sync["ok"] is True and pushed == []
    ahead = iw.idempotent_apply("head=abc",
                                current_reader=lambda: (False, "remote=old local=abc"),
                                apply_fn=lambda: (pushed.append(1), (True, "pushed"))[1])
    assert ahead["applied"] is True and ahead["ok"] is True and pushed == [1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_idempotent_write.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'idempotent_write'`.

- [ ] **Step 3: Write minimal implementation**

```python
# plugins/superheroes/lib/idempotent_write.py
"""A generic per-write idempotency primitive: apply a durable/remote write AT MOST ONCE
by reading reality, never by trusting a stored flag (the spine's reality-wins rule,
CONVENTIONS §4.7). Built generic (a key + a reader + an applier) so create / ready-flip /
draft-flip / push-reconcile all route through one seam; #118 generalizes it spine-wide
(its FR-4) rather than retrofitting a divergent scheme.

Fail-CLOSED: an unreadable current state never applies and never reports ok.
"""


def idempotent_apply(key, current_reader, apply_fn):
    """Apply `apply_fn` only if the live state does not already reflect `key`.

    key: an opaque string naming the intended end-state (informational; the actual
        match is decided by current_reader, which reads reality).
    current_reader: () -> (reflects, detail). reflects is True (already done — no-op),
        False (apply needed), or None (unreadable — fail closed, never apply).
    apply_fn: () -> (ok, detail). Performs the write; invoked only when reflects is False.

    Returns {key, already, applied, ok, reason, detail}.
    """
    try:
        reflects, read_detail = current_reader()
    except Exception as e:  # noqa: BLE001 — a throwing reader is an unreadable state, fail closed
        return {"key": key, "already": False, "applied": False, "ok": False,
                "reason": "current-state read raised: %s" % e, "detail": None}
    if reflects is None:
        return {"key": key, "already": False, "applied": False, "ok": False,
                "reason": "current state unreadable — fail closed", "detail": read_detail}
    if reflects is True:
        return {"key": key, "already": True, "applied": False, "ok": True,
                "reason": "already reflects intended write — no-op", "detail": read_detail}
    try:
        ok, apply_detail = apply_fn()
    except Exception as e:  # noqa: BLE001 — a throwing applier is a failed write, fail closed
        return {"key": key, "already": False, "applied": True, "ok": False,
                "reason": "apply raised: %s" % e, "detail": None}
    return {"key": key, "already": False, "applied": True, "ok": bool(ok),
            "reason": "applied" if ok else "apply failed", "detail": apply_detail}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_idempotent_write.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/idempotent_write.py plugins/superheroes/lib/tests/test_idempotent_write.py
git commit -m "feat(superheroes): generic per-write idempotency primitive (idempotent_write) for the native back-half (#120, #118 coord)"
```

---

### Task 2: `ship_phase.py --step reconcile-head` + freshness `--attempt` (push-reconcile, idempotency call-site 1)

**Files:**
- Create: `plugins/superheroes/lib/ship_reconcile.py` (pure push-reconcile decider — UFR-6 call-site 1)
- Modify: `plugins/superheroes/lib/ship_phase.py`
- Test: `plugins/superheroes/lib/tests/test_ship_phase_steps.py`

**Interfaces:**
- Consumes: `idempotent_write.idempotent_apply` (Task 1); `control_plane.paths`, `checkpoint.read`.
- Produces: `ship_reconcile.reconcile_head(local, remote, branch, push_fn) -> idempotent_apply result` (pure — reader=(remote==local), applier=`push_fn`; the gh/git IO stays in the leaf, so the wiring is testable without a gh stub, matching the codebase's pure-decider pattern). `ship_phase.py --step reconcile-head --work-item <wi> [--worktree <path>]` → prints `{"ok": bool, "head": <sha|null>, "reason": str}` (pushes the local branch when the local HEAD is ahead of the remote PR head; idempotent no-op when in sync; fail-closed on an unreadable head). `ship_phase.py --step freshness ... --attempt <n>` now threads the 1-based catch-up attempt into `freshness.decide` (default 1, unchanged behavior).
- Helpers added (module-level, importable by the test): `_git(args, cwd=None) -> (rc, out)`, `_remote_pr_head(work_item) -> sha|None`, `_local_head(cwd) -> sha|None`.

- [ ] **Step 1: Write the failing test**

```python
# plugins/superheroes/lib/tests/test_ship_phase_steps.py
import json, os, subprocess, sys
LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(step, *extra, cwd=None):
    cmd = [sys.executable, os.path.join(LIB, "ship_phase.py"), "--step", step,
           "--work-item", "wi", *extra]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd or LIB, timeout=30)
    return r


def test_freshness_accepts_attempt_and_gives_up_past_cap(tmp_path):
    # A behind branch on attempt 4 (> DEFAULT_MAX_SYNCS=3) must return give_up_notify, proving
    # --attempt is threaded into freshness.decide (default 1 keeps current behavior).
    repo = tmp_path / "r"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "a").write_text("2")               # main advances; feat is now behind
    subprocess.run(["git", "commit", "-qam", "advance"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    r = _run("freshness", "--base", "main", "--attempt", "4", cwd=repo)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["decision"] == "give_up_notify"


def test_reconcile_head_no_pr_fails_closed(tmp_path, monkeypatch):
    # Run from a NON-git dir with an isolated store → local HEAD unreadable → fail closed (ok False),
    # deterministically (never claim ready; never depend on the ambient repo's branch/gh PR state).
    # (The in-sync no-op and local-ahead apply WIRING is covered with teeth by
    #  test_reconcile_head_helper_paths below, which drives the pure ship_reconcile.reconcile_head.)
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = _run("reconcile-head", cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert "ok" in out and out["ok"] is False
    assert out["reason"]


def test_reconcile_head_helper_paths():
    # Teeth for the reconcile-head BRANCH wiring (UFR-6 call-site 1): drive the pure decider with an
    # injected push_fn + remote, covering in-sync no-op, local-ahead apply-once, unreadable fail-closed,
    # and no-branch. The gh/git IO stays in the leaf; this is exactly the wiring the branch delegates to.
    sys.path.insert(0, LIB)
    import ship_reconcile
    pushed = []
    r1 = ship_reconcile.reconcile_head("abc", "abc", "feat", lambda: pushed.append(1) or True)
    assert r1["already"] is True and r1["ok"] is True and pushed == []            # in sync -> no push
    r2 = ship_reconcile.reconcile_head("abc", "old", "feat", lambda: (pushed.append(1), True)[1])
    assert r2["applied"] is True and r2["ok"] is True and pushed == [1]            # ahead -> push once
    r3 = ship_reconcile.reconcile_head("abc", None, "feat", lambda: pushed.append(1) or True)
    assert r3["ok"] is False and pushed == [1]                                     # unreadable -> fail closed, no push
    r4 = ship_reconcile.reconcile_head("abc", "old", "", lambda: True)
    assert r4["ok"] is False                                                       # no branch -> cannot push


def test_freshness_reads_the_worktree_not_cwd(tmp_path):
    # CRITICAL (the catch-up loop must converge): --step freshness must judge the BUILD WORKTREE's
    # branch HEAD, not the process cwd. Run from a NEUTRAL cwd (LIB) with --worktree pointed at a
    # behind-base repo and assert it sees 'sync' (behind) — a cwd-rooted read would see LIB and mis-judge.
    repo = tmp_path / "r"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a").write_text("1")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "a").write_text("2")
    subprocess.run(["git", "commit", "-qam", "advance"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    r = _run("freshness", "--base", "main", "--worktree", str(repo), "--attempt", "1", cwd=LIB)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["decision"] == "sync"   # behind base, attempt 1 -> sync (not gate/up_to_date)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -q`
Expected: FAIL — `--step` rejects `reconcile-head` (argparse `choices`) and freshness rejects `--attempt`.

- [ ] **Step 3: Write minimal implementation**

In `plugins/superheroes/lib/ship_phase.py`, add the import and helpers near the top (after the existing imports), extend the argparse `choices` and add `--attempt`/`--worktree`, thread `--attempt` into the freshness branch, and add the `reconcile-head` branch.

Add to the import line (it currently imports `freshness, ci_loop, control_plane, journal, ci_status, checkpoint as ckpt_lib, base_ref`):

```python
import freshness, ci_loop, control_plane, journal, ci_status, checkpoint as ckpt_lib, base_ref
import idempotent_write, ship_reconcile
```

Add these module-level helpers (after `_resolve_pr_number`):

```python
def _git(args, cwd=None):
    """(rc, stdout). A timeout/raise -> (2, '') so callers fail closed."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=60)
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return 2, ""


def _local_head(cwd=None):
    rc, out = _git(["rev-parse", "HEAD"], cwd=cwd)
    return out if rc == 0 and out else None


def _remote_pr_head(work_item):
    """The PR's current remote head SHA via gh, or None on any unreadable read (fail closed)."""
    pr = _resolve_pr_number(work_item)
    if not pr:
        return None
    try:
        r = subprocess.run(["gh", "pr", "view", pr, "--json", "headRefOid", "--jq", ".headRefOid"],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None
```

Replace the argparse block's `--step` and add args:

```python
ap.add_argument("--step", required=True,
                choices=["freshness", "ci", "reconcile-head", "freshen", "ci-decide",
                         "ci-record", "fix-push", "revert-draft"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--emit-checks", action="store_true",
                help="IO-only mode: emit raw checks array (or {error:...}) without classifying")
ap.add_argument("--base", default=None,
                help="configurable base branch name; absent -> default 'main' (current behavior)")
ap.add_argument("--attempt", type=int, default=1,
                help="1-based catch-up attempt threaded into freshness.decide (default 1)")
ap.add_argument("--worktree", default=None,
                help="the build worktree the git mechanics run in; absent -> cwd")
```

In the freshness branch, root the base resolution and the ancestor read in the **build worktree** (`--worktree`) and thread `--attempt`, so the freshness re-judge runs against the same branch HEAD `--step freshen` merges into (not the repo-root checkout — otherwise the catch-up loop never converges and falsely gives up). Replace the freshness branch body — from `base_name = a.base if a.base else "main"` through `print(json.dumps({"decision": decision}))` — with:

```python
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    # C-I1: resolve the base via the SHARED resolver (local->origin), rooted in the worktree.
    resolved = base_ref.resolve_configured_base(wt, base_name)
    if resolved is None:
        print(json.dumps({"decision": "gate",
                          "reason": base_ref.unresolvable_reason(base_name, wt)}))
    else:
        try:
            rc = subprocess.run(["git", "merge-base", "--is-ancestor", resolved, "HEAD"],
                                capture_output=True, timeout=10, cwd=wt).returncode
        except subprocess.TimeoutExpired:
            rc = 2                                       # a hung read -> unreadable -> freshness gate
        is_anc = True if rc == 0 else (False if rc == 1 else None)
        decision, _reason = freshness.decide(is_anc, a.attempt)
        print(json.dumps({"decision": decision}))
```

Create `plugins/superheroes/lib/ship_reconcile.py` — the pure push-reconcile decider (so the branch's reader/applier wiring is testable without a gh stub, matching `freshness.py` / `ci_loop.py` / `pr_phase.py`):

```python
# plugins/superheroes/lib/ship_reconcile.py
"""Pure push-reconcile decider (UFR-6 call-site 1): given the local integrated HEAD, the remote PR
head (or None if unreadable), the branch, and an injected push_fn, route through the generic
idempotency primitive — already-in-sync is a no-op, local-ahead applies the push, an unreadable
remote fails closed. The gh/git IO stays in the ship_phase leaf; this only decides."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import idempotent_write


def reconcile_head(local, remote, branch, push_fn):
    """local: the worktree's local HEAD (the integrated head the remote must match).
    remote: the PR's current remote head SHA, or None (unreadable -> fail closed).
    branch: the work-item's branch ("" -> cannot push).
    push_fn: () -> bool — performs the non-force push + read-back-confirm; called only when local-ahead.
    Returns the idempotent_apply result dict {key, already, applied, ok, reason, detail}."""
    def _reader():
        if remote is None:
            return (None, "remote PR head unreadable")
        return (remote == local, "remote=%s local=%s" % (remote, local))

    def _apply():
        if not branch:
            return (False, "no branch recorded — cannot push")
        return (bool(push_fn()), "pushed")

    return idempotent_write.idempotent_apply("head=%s" % local, _reader, _apply)
```

Add the `reconcile-head` branch (place it as an `elif a.step == "reconcile-head":` before the `elif a.emit_checks:` line) — it delegates the reader/applier wiring to the pure decider and keeps only the gh/git IO:

```python
elif a.step == "reconcile-head":
    # UFR-6: bring the remote PR head into agreement with the reconciled local head by pushing
    # local-ahead. The reader=(remote==local)/applier=push WIRING lives in the pure ship_reconcile
    # decider (testable without gh); this leaf only does the gh/git IO.
    wt = a.worktree or os.getcwd()
    local = _local_head(wt)
    if not local:
        print(json.dumps({"ok": False, "head": None, "reason": "local HEAD unreadable — fail closed"}))
        sys.exit(0)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""

    def _push():
        rc, _ = _git(["push", "origin", branch], cwd=wt)          # ordinary non-force push (FR-9)
        if rc != 0:
            return False
        return _remote_pr_head(a.work_item) == local              # read-back-confirm the push landed

    res = ship_reconcile.reconcile_head(local, _remote_pr_head(a.work_item), branch, _push)
    print(json.dumps({"ok": bool(res["ok"]),
                      "head": local if res["ok"] else None,
                      "reason": res["reason"]}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -q`
Expected: PASS (4 passed). Also run `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_freshness.py -q` — Expected: PASS (the `--attempt` default keeps existing behavior; the freshness branch still defaults `wt` to cwd when `--worktree` is absent).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/ship_reconcile.py plugins/superheroes/lib/ship_phase.py plugins/superheroes/lib/tests/test_ship_phase_steps.py
git commit -m "feat(superheroes): ship_phase reconcile-head step (pure ship_reconcile decider) + freshness --attempt/--worktree (#120)"
```

---

### Task 3: `ship_phase.py --step freshen` (base catch-up; merge / conflict-abort / non-force push)

**Files:**
- Modify: `plugins/superheroes/lib/ship_phase.py`
- Test: `plugins/superheroes/lib/tests/test_ship_phase_steps.py` (add cases)

**Interfaces:**
- Consumes: `base_ref.resolve_configured_base`, `_git`, `_remote_pr_head` (Task 2).
- Produces: `ship_phase.py --step freshen --work-item <wi> --base <name> [--worktree <path>]` → `{"ok": bool, "head": <sha|null>, "conflict": bool, "reason": str}`. Fast-forward or git-auto-merged (non-overlapping) base → committed + non-force pushed (the "trivially-correct, high-confidence" auto-resolution, UFR-1 guarantee b). A real (overlapping) conflict → `git merge --abort`, head unchanged (UFR-1 guarantee a), `conflict: true`, no push.

- [ ] **Step 1: Write the failing test**

```python
# add to plugins/superheroes/lib/tests/test_ship_phase_steps.py
def _init_repo(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def test_freshen_conflict_aborts_head_unchanged(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "f").write_text("main-change\n")                       # main edits line 1
    subprocess.run(["git", "commit", "-qam", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    (repo / "f").write_text("feat-change\n")                       # feat edits the SAME line -> conflict
    subprocess.run(["git", "commit", "-qam", "feat"], cwd=repo, check=True)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    r = _run("freshen", "--base", "main", "--worktree", str(repo), cwd=repo)
    out = json.loads(r.stdout)
    assert out["conflict"] is True
    assert out["ok"] is False
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert before == after                                         # UFR-1(a): aborted -> head unchanged
    # the tree is clean after abort (no conflict markers left behind)
    st = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert st.strip() == ""


def test_freshen_clean_automerge_commits(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    subprocess.run(["git", "branch", "feat"], cwd=repo, check=True)
    (repo / "g").write_text("new-on-main\n")                       # main adds a DIFFERENT file -> auto-merges
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "main"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "feat"], cwd=repo, check=True)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    r = _run("freshen", "--base", "main", "--worktree", str(repo), cwd=repo)
    out = json.loads(r.stdout)
    assert out["conflict"] is False
    after = out["head"]
    assert after and after != before                              # branch advanced to contain base
    assert (repo / "g").exists()                                  # base change integrated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k freshen -q`
Expected: FAIL — `--step freshen` reaches no branch (no output / KeyError on `out`).

- [ ] **Step 3: Write minimal implementation**

Add the `freshen` branch to `ship_phase.py` (as `elif a.step == "freshen":`, before `elif a.emit_checks:`):

```python
elif a.step == "freshen":
    # FR-1/UFR-1/FR-9: bring the base into the branch. git's own auto-merge of non-overlapping
    # changes IS the "trivially-correct, high-confidence" resolution (committed + pushed + re-checked,
    # UFR-1 guarantee b). A real overlapping conflict -> `git merge --abort` leaving the head EXACTLY
    # where it was (UFR-1 guarantee a) + park; never a guessed or half-integrated branch.
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    resolved = base_ref.resolve_configured_base(wt, base_name)
    if resolved is None:
        print(json.dumps({"ok": False, "head": _local_head(wt), "conflict": False,
                          "reason": base_ref.unresolvable_reason(base_name, wt)}))
        sys.exit(0)
    _git(["fetch", "--quiet", "origin"], cwd=wt)                  # best-effort; local resolve still works
    before_head = _local_head(wt)
    rc, _ = _git(["merge", "--no-edit", resolved], cwd=wt)
    if rc != 0:
        # conflict (or merge error) -> abort to the exact prior head, leave a clean tree.
        _git(["merge", "--abort"], cwd=wt)
        print(json.dumps({"ok": False, "head": _local_head(wt), "conflict": True,
                          "reason": "base integration conflicts — aborted (head unchanged), owner must resolve"}))
        sys.exit(0)
    after_head = _local_head(wt)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""
    if after_head and after_head != before_head and branch:
        push_rc, _ = _git(["push", "origin", branch], cwd=wt)     # ordinary non-force push (FR-9)
        if push_rc != 0:
            print(json.dumps({"ok": False, "head": after_head, "conflict": False,
                              "reason": "merged base but push failed — reconcile on resume"}))
            sys.exit(0)
    print(json.dumps({"ok": True, "head": after_head, "conflict": False,
                      "reason": "base integrated" if after_head != before_head else "already up to date"}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k freshen -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/ship_phase.py plugins/superheroes/lib/tests/test_ship_phase_steps.py
git commit -m "feat(superheroes): ship_phase freshen step — base catch-up with conflict-abort + non-force push (#120, FR-1/UFR-1/FR-9)"
```

---

### Task 4: `ship_phase.py --step ci-decide` (journal-replayed CI-fix bound) + `--step ci-record`

**Files:**
- Modify: `plugins/superheroes/lib/ship_phase.py`
- Test: `plugins/superheroes/lib/tests/test_ship_phase_steps.py` (add cases)

**Interfaces:**
- Consumes: `journal.ci_attempts`, `journal.append`, `ci_loop.decide`, `control_plane.paths`.
- Produces:
  - `ship_phase.py --step ci-decide --work-item <wi> --failing <json-array>` → `{"action": "fix"|"revert_and_gate", "round": <int>, "reason": str}`. Reads the prior round count + history from the write-ahead `ci_fix_attempt` journal (so it survives a crash — UFR-5), then `ci_loop.decide(failing, history, prior_rounds + 1)`.
  - `ship_phase.py --step ci-record --work-item <wi> --round <n> --failing <json-array>` → `{"ok": bool}`. Write-ahead append of one `ci_fix_attempt` event *before* the fixer runs (UFR-5). Fail-closed `{"ok": false}` on a `DurableWriteError`.

- [ ] **Step 1: Write the failing test**

```python
# add to plugins/superheroes/lib/tests/test_ship_phase_steps.py
# NOTE: control_plane.paths resolves the store from SUPERHEROES_STORE_ROOT (NOT cwd), so every test that
# touches the journal/checkpoint monkeypatches it to an isolated dir — never the real ~/.claude/workhorse.
def test_ci_decide_respects_cap_after_replayed_rounds(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    import importlib
    sys.path.insert(0, LIB)
    cp = importlib.import_module("control_plane")
    jr = importlib.import_module("journal")
    paths = cp.paths(str(tmp_path), "wi")
    # seed 4 prior ci_fix_attempt rounds -> the next decide is round 5 = the cap -> revert_and_gate.
    for i in range(1, 5):
        jr.append(paths["events"], "ci_fix_attempt", payload={"round": i, "failing": ["x"]}, root=str(tmp_path))
    r = _run("ci-decide", "--failing", json.dumps(["x"]), cwd=str(tmp_path))
    out = json.loads(r.stdout)
    assert out["action"] == "revert_and_gate"
    assert out["round"] == 5


def test_ci_decide_first_round_fixes(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    r = _run("ci-decide", "--failing", json.dumps(["build"]), cwd=str(tmp_path))
    out = json.loads(r.stdout)
    assert out["action"] == "fix"
    assert out["round"] == 1


def test_ci_record_appends_round(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))
    import importlib
    sys.path.insert(0, LIB)
    cp = importlib.import_module("control_plane"); jr = importlib.import_module("journal")
    paths = cp.paths(str(tmp_path), "wi")
    r = _run("ci-record", "--round", "1", "--failing", json.dumps(["build"]), cwd=str(tmp_path))
    assert json.loads(r.stdout)["ok"] is True
    rounds, hist = jr.ci_attempts(paths["events"])
    assert rounds == 1 and hist == [["build"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k "ci_decide or ci_record" -q`
Expected: FAIL — `--step` rejects `ci-decide`/`ci-record`.

- [ ] **Step 3: Write minimal implementation**

Add `--round`/`--failing` args to the argparse block:

```python
ap.add_argument("--round", type=int, default=None, help="1-based CI-fix round for ci-record")
ap.add_argument("--failing", default=None, help="JSON array of current failing check signatures")
```

Add the two branches (before `elif a.emit_checks:`):

```python
elif a.step == "ci-decide":
    # FR-3/FR-4/UFR-5: replay the write-ahead round count from the journal (survives a crash),
    # then let ci_loop.decide (parity-locked) choose fix vs revert_and_gate.
    try:
        failing = json.loads(a.failing) if a.failing else []
    except ValueError:
        failing = []
    paths = control_plane.paths(os.getcwd(), a.work_item)
    prior_rounds, history = journal.ci_attempts(paths["events"])
    rnd = prior_rounds + 1
    action, reason = ci_loop.decide(failing, history, rnd)
    print(json.dumps({"action": action, "round": rnd, "reason": reason}))
elif a.step == "ci-record":
    # Write-ahead ONE ci_fix_attempt BEFORE the fixer runs (UFR-5: a crash over-counts, never under).
    try:
        failing = json.loads(a.failing) if a.failing else []
    except ValueError:
        failing = []
    paths = control_plane.paths(os.getcwd(), a.work_item)
    try:
        journal.append(paths["events"], "ci_fix_attempt",
                       payload={"round": a.round, "failing": failing}, root=os.getcwd())
        print(json.dumps({"ok": True}))
    except journal.DurableWriteError as e:
        print(json.dumps({"ok": False, "reason": "durable write failed: %s" % e}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k "ci_decide or ci_record" -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/ship_phase.py plugins/superheroes/lib/tests/test_ship_phase_steps.py
git commit -m "feat(superheroes): ship_phase ci-decide (journal-replayed bound) + ci-record write-ahead (#120, FR-3/4, UFR-5)"
```

---

### Task 5: `ship_phase.py --step fix-push` (clean-tree precondition + non-fast-forward replay-onto-PR-head)

**Files:**
- Modify: `plugins/superheroes/lib/ship_phase.py`
- Test: `plugins/superheroes/lib/tests/test_ship_phase_steps.py` (add cases)

**Interfaces:**
- Consumes: `_git`, `_local_head`, `_remote_pr_head` (Task 2); `control_plane.paths`, `checkpoint.read`.
- Produces: `ship_phase.py --step fix-push --work-item <wi> [--worktree <path>]` → `{"ok": bool, "head": <sha|null>, "pushed": bool, "reason": str}`. **Clean-tree precondition:** commits + pushes only a worktree carrying exactly the fixer's intended change — a tree with conflict markers (`git diff --check`) or no change parks fail-closed (`pushed: false`, no push). **Non-fast-forward recovery:** on a rejected push it re-reads the *current remote PR head*, fetches the advanced branch tip, and rebases **all local-ahead commits** onto it (not just `HEAD~1`, which would drop an un-pushed freshen merge or earlier fix), then re-pushes; if it cannot cleanly rebase it parks — never the base, never a force-push, never dropping a commit.

- [ ] **Step 1: Write the failing test**

```python
# add to plugins/superheroes/lib/tests/test_ship_phase_steps.py
def test_fix_push_dirty_conflict_marker_parks_no_push(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    # leave a conflict marker in the worktree (a crashed fixer's residue)
    (repo / "f").write_text("<<<<<<< HEAD\na\n=======\nb\n>>>>>>> x\n")
    r = _run("fix-push", "--worktree", str(repo), cwd=repo)
    out = json.loads(r.stdout)
    assert out["pushed"] is False
    assert out["ok"] is False
    assert "conflict" in out["reason"] or "marker" in out["reason"]


def test_fix_push_no_change_parks(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "f").write_text("base\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    r = _run("fix-push", "--worktree", str(repo), cwd=repo)       # clean tree, nothing to commit
    out = json.loads(r.stdout)
    assert out["pushed"] is False
    assert out["ok"] is False
    assert "no change" in out["reason"] or "nothing" in out["reason"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k fix_push -q`
Expected: FAIL — `--step fix-push` unrecognized.

- [ ] **Step 3: Write minimal implementation**

Add the `fix-push` branch (before `elif a.emit_checks:`):

```python
elif a.step == "fix-push":
    # The fixer agent (in the orchestrator) edited the worktree to fix failing checks. This step
    # commits + non-force pushes ONLY a clean worktree carrying exactly that change. A crashed fixer's
    # residue (conflict markers) or a no-op tree parks fail-closed (no push). On a non-fast-forward
    # rejection it replays the fixer commit onto the CURRENT remote PR head — never the base, never a
    # force, never dropping the commit; parks if it cannot cleanly replay.
    wt = a.worktree or os.getcwd()
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""
    # clean-tree precondition: reject leftover conflict markers (a crashed/garbage fixer state).
    marker_rc, _ = _git(["diff", "--check"], cwd=wt)
    if marker_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "worktree carries conflict markers — crashed fixer, park (no push)"}))
        sys.exit(0)
    _git(["add", "-A"], cwd=wt)
    staged_rc, staged = _git(["diff", "--cached", "--name-only"], cwd=wt)
    if not staged:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "no change to push — nothing the fixer produced"}))
        sys.exit(0)
    commit_rc, _ = _git(["commit", "-m", "fix(superheroes): repair failing checks [showrunner]"], cwd=wt)
    if commit_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "commit failed"}))
        sys.exit(0)
    if not branch:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "no branch recorded — cannot push"}))
        sys.exit(0)
    push_rc, _ = _git(["push", "origin", branch], cwd=wt)         # ordinary non-force push (FR-9)
    if push_rc == 0:
        print(json.dumps({"ok": True, "head": _local_head(wt), "pushed": True, "reason": "fix pushed"}))
        sys.exit(0)
    # non-fast-forward: the remote PR head advanced. Replay ALL local-ahead commits onto THAT head
    # (never base). HEAD~1 would replay only the last commit and silently DROP an un-pushed freshen
    # merge or an earlier fix commit when the worktree is >1 ahead; rebasing onto the fetched branch
    # tip replays the whole local-ahead range, dropping nothing.
    remote = _remote_pr_head(a.work_item)
    if not remote:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "push rejected and remote PR head unreadable — park"}))
        sys.exit(0)
    fetch_rc, _ = _git(["fetch", "--quiet", "origin", branch], cwd=wt)
    if fetch_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "push rejected and could not fetch the advanced remote head — park"}))
        sys.exit(0)
    rebase_rc, _ = _git(["rebase", "FETCH_HEAD"], cwd=wt)         # replay local-ahead onto the advanced remote
    if rebase_rc != 0:
        _git(["rebase", "--abort"], cwd=wt)                      # never force, never drop a commit
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "cannot cleanly replay local-ahead commits onto advanced PR head — park"}))
        sys.exit(0)
    repush_rc, _ = _git(["push", "origin", branch], cwd=wt)
    if repush_rc != 0:
        print(json.dumps({"ok": False, "head": _local_head(wt), "pushed": False,
                          "reason": "replay push still rejected — park (no force)"}))
        sys.exit(0)
    print(json.dumps({"ok": True, "head": _local_head(wt), "pushed": True,
                      "reason": "fix replayed onto advanced PR head and pushed"}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k fix_push -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/ship_phase.py plugins/superheroes/lib/tests/test_ship_phase_steps.py
git commit -m "feat(superheroes): ship_phase fix-push — clean-tree precondition + NFF replay-onto-PR-head (#120, UFR-6 partial-failure invariant)"
```

---

### Task 6: `ship_phase.py --step revert-draft` (draft-flip, call-site 2) + mark-ready ready-flip via primitive (call-site 3)

**Files:**
- Modify: `plugins/superheroes/lib/ship_phase.py`, `plugins/superheroes/lib/pr_entry.py`
- Test: `plugins/superheroes/lib/tests/test_ship_phase_steps.py`, `plugins/superheroes/lib/tests/test_pr_phase.py` (add a marker assertion)

**Interfaces:**
- Consumes: `idempotent_write.idempotent_apply` (Task 1), `_resolve_pr_number`.
- Produces: `ship_phase.py --step revert-draft --work-item <wi>` → `{"ok": bool, "reason": str}`. Routes the draft-flip through `idempotent_apply` keyed `draft:pr=<n>` (reflects when `isDraft` is already True → no-op; else `gh pr ready --undo <n>`). `pr_entry.py` mark-ready's `flip` branch routes the ready-flip through the same primitive keyed `ready:pr=<n>` — the 3rd real call site (idempotent no-op when already ready).

- [ ] **Step 1: Write the failing test**

```python
# add to plugins/superheroes/lib/tests/test_ship_phase_steps.py
def test_revert_draft_no_pr_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))  # isolated store; non-git cwd
    r = _run("revert-draft", cwd=str(tmp_path))                   # no checkpoint PR, no gh PR -> fail closed
    out = json.loads(r.stdout)
    assert out["ok"] is False
    assert out["reason"]
```

And a structural assertion that the ready-flip routes through the primitive:

```python
# add to plugins/superheroes/lib/tests/test_ship_phase_steps.py
def test_pr_entry_and_ship_phase_use_idempotent_primitive():
    pe = open(os.path.join(LIB, "pr_entry.py")).read()
    sp = open(os.path.join(LIB, "ship_phase.py")).read()
    sr = open(os.path.join(LIB, "ship_reconcile.py")).read()
    assert "idempotent_write" in pe and "ready:pr=" in pe        # call-site 3: ready-flip
    assert "idempotent_write" in sp and "draft:pr=" in sp        # call-site 2: draft-flip
    assert "idempotent_write" in sr and "head=" in sr            # call-site 1: push-reconcile (pure decider)
    assert "ship_reconcile.reconcile_head" in sp                 # ship_phase delegates the reconcile wiring


def test_ship_phase_pushes_are_non_force_to_the_branch():
    # FR-9: every push the back-half makes is an ordinary non-force push to the work-item's OWN branch
    # — never a force-push, never a push to a literal default branch. (FR-8's never-merge twin is the
    # guard smoke; this is FR-9's structural assertion.)
    import re
    sp = open(os.path.join(LIB, "ship_phase.py")).read()
    pushes = re.findall(r'\["push"[^\]]*\]', sp)
    assert pushes, "expected git push calls in ship_phase.py"
    for p in pushes:
        assert "force" not in p.lower(), "force-push found: %s" % p
        assert '"-f"' not in p and '"+' not in p, "force/forced-refspec push found: %s" % p
        assert '"origin"' in p, "push not to origin: %s" % p
    # never a push to a hardcoded default branch (pushes target the checkpoint `branch` variable)
    assert '"push", "origin", "main"' not in sp and '"push", "origin", "master"' not in sp
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k "revert_draft or idempotent_primitive" -q`
Expected: FAIL — `--step revert-draft` unrecognized; `pr_entry.py` does not yet reference `idempotent_write`.

- [ ] **Step 3: Write minimal implementation**

Add the `revert-draft` branch to `ship_phase.py` (before `elif a.emit_checks:`):

```python
elif a.step == "revert-draft":
    # FR-4: return the PR to draft on terminal CI failure. Idempotent via the primitive: a no-op
    # when the PR is already draft. Draft-flip is call-site 2 of the generic idempotency guard.
    pr = _resolve_pr_number(a.work_item)
    if not pr:
        print(json.dumps({"ok": False, "reason": "no PR to revert — fail closed"}))
        sys.exit(0)

    def _reader():
        try:
            r = subprocess.run(["gh", "pr", "view", pr, "--json", "isDraft", "--jq", ".isDraft"],
                               capture_output=True, text=True, timeout=30)
        except Exception:
            return (None, "isDraft unreadable")
        if r.returncode != 0:
            return (None, "isDraft unreadable")
        v = r.stdout.strip()
        if v == "true":
            return (True, "already draft")
        if v == "false":
            return (False, "ready")
        return (None, "isDraft ambiguous")

    def _apply():
        try:
            rc = subprocess.run(["gh", "pr", "ready", "--undo", pr], capture_output=True, timeout=60).returncode
        except Exception:
            return (False, "gh pr ready --undo raised")
        return (rc == 0, "reverted to draft")

    res = idempotent_write.idempotent_apply("draft:pr=%s" % pr, _reader, _apply)
    print(json.dumps({"ok": bool(res["ok"]), "reason": res["reason"]}))
```

In `pr_entry.py`, add the import (top, after the existing import line):

```python
import checkpoint as ckpt_lib, control_plane, pr_phase, recover, ship_gate, test_pilot_status
import idempotent_write
```

Replace the mark-ready `flip` block (the `if decision == "flip":` ... `gh pr ready` subprocess) with a primitive-routed flip:

```python
    if decision == "flip":
        n = str(pr["number"])

        def _reader():
            cur = _gh_pr(branch)
            if not isinstance(cur, dict):
                return (None, "PR isDraft unreadable")
            d = cur.get("isDraft")
            if d is False:
                return (True, "already ready")
            if d is True:
                return (False, "draft")
            return (None, "isDraft ambiguous")

        def _apply():
            try:
                rc = subprocess.run(["gh", "pr", "ready", n], capture_output=True, timeout=60).returncode
            except subprocess.TimeoutExpired:
                return (False, "gh pr ready timed out — PR still draft")
            return (rc == 0, "flipped to ready")

        res = idempotent_write.idempotent_apply("ready:pr=%s" % n, _reader, _apply)
        if not res["ok"]:
            print(json.dumps({"ok": False, "reason": res["reason"] or "gh pr ready failed — PR still draft"}))
            sys.exit(0)
    print(json.dumps({"ok": True}))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py -k "revert_draft or idempotent_primitive" plugins/superheroes/lib/tests/test_pr_phase.py -q`
Expected: PASS (the ship-phase cases pass; existing `test_pr_phase.py` still passes — mark-ready behavior is unchanged for the readable cases, just routed through the primitive).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/ship_phase.py plugins/superheroes/lib/pr_entry.py plugins/superheroes/lib/tests/test_ship_phase_steps.py
git commit -m "feat(superheroes): revert-draft + mark-ready route through idempotency primitive — 3 call sites (#120, UFR-6)"
```

---

### Task 7: Thread `generation` into `shipPhase` + `shipFenceOrPark` helper + build-worktree resolution

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.js` (`runPhases` ship branch ~1023; new helper near `shipPhase`)
- Modify: `plugins/superheroes/lib/tests/showrunner_ship_smoke.js` (stub the new entry leaves)
- Regen: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Consumes: `exec`, `cmdRunner`, `shq`, `resolveBuildTarget` (existing).
- Produces: `shipPhase(workItem, pr, generation)` (new 3rd param, defaulted so existing direct callers degrade); module-level `async function shipFenceOrPark(workItem, generation)` → `boolean` (renew-then-fence via `fence_cli.py`; `false` ⇒ caller parks). `runPhases` ship branch passes `deps.generation`.

- [ ] **Step 1: Write the failing test**

Update `showrunner_ship_smoke.js` so the green/none paths still pass once `shipPhase` resolves the build worktree and does the entry reconcile. Add stubs for `build_entry.py`, `rev-parse`, and `reconcile-head`, and call `shipPhase` with a generation:

```js
// in showrunner_ship_smoke.js run(), extend the agent stub BEFORE the throw:
    // resolve build worktree (resolveBuildTarget): build_entry.py AND rev-parse BOTH dispatch via exec
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head-sha' }]
    // entry fence (the entry reconcile may push) + reconcile-head: in sync, no-op ok
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head-sha', reason: 'in sync' }
```

And change each `shipPhase('wi', { number: 7 })` call to `shipPhase('wi', { number: 7 }, 5)` (a generation), then add at the end of the IIFE:

```js
  // generation threaded: a green path still reaches 'ready' with the entry reconcile in place.
  sr = run([{ name: 'ci', bucket: 'pass', state: 'success' }])
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green + generation -> ready')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_smoke.js`
Expected: FAIL — `shipPhase` ignores the new leaves / throws "unexpected agent" (the entry reconcile isn't wired yet).

- [ ] **Step 3: Write minimal implementation**

In `showrunner.js`, change the ship dispatch in `runPhases` (currently `return (deps.ship || shipPhase)(workItem, await loadPr(workItem))`):

```js
    if (phase === 'ship') {                              // terminal: returns {outcome,phase,reason}
      return (deps.ship || shipPhase)(workItem, await loadPr(workItem), deps.generation)
    }
```

Add the fence helper immediately above `shipPhase`:

```js
// renew-then-fence the lease generation immediately before a branch-/PR-mutating boundary (UFR-4).
// Fail-closed: a null generation or a lost/unreadable lease returns false -> the caller parks BEFORE
// any mutation. Mirrors build_phase.js's fenceOrPark; #118 folds this seam spine-wide.
async function shipFenceOrPark(workItem, generation) {
  if (generation == null) return false
  const out = await cmdRunner(
    `python3 plugins/superheroes/lib/fence_cli.py --work-item ${shq(workItem)} --generation ${shq(String(generation))}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, reason: { type: 'string' } } } })
  return !!(out && out.ok)
}
module.exports.shipFenceOrPark = shipFenceOrPark
```

Change the `shipPhase` signature and add the entry reconcile at the top of its body (keeping the existing freshness/ci logic below for now — later tasks replace it):

```js
async function shipPhase(workItem, pr, generation) {
  // Resolve the build worktree the back-half git mechanics run in (mirrors review-code/test-pilot).
  // FAIL-CLOSED: if the build worktree can't be resolved, every git mutation below would otherwise
  // default to the repo-root checkout (the wrong tree) — park rather than merge/commit/push there.
  const target = await resolveBuildTarget(workItem)
  const worktree = target && target.worktree ? target.worktree : null
  if (!worktree) {
    return park(workItem, pr, 'could not resolve the build worktree for the back-half — park (no mutation against the repo root)')
  }
  const wtArg = ` --worktree ${shq(worktree)}`
  // UFR-4: the entry reconcile MAY push (when local HEAD is ahead of the remote PR head), so fence first.
  if (!(await shipFenceOrPark(workItem, generation))) {
    return park(workItem, pr, 'lease lost before reconciling the PR head — park (UFR-4)')
  }
  // UFR-6 entry reconcile: bring the remote PR head into agreement with the local HEAD before judging.
  const rec = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step reconcile-head --work-item ${shq(workItem)}${wtArg}`,
    { schema: { type: 'object', required: ['ok'], properties: { ok: {}, head: {}, reason: { type: 'string' } } } })
  if (!rec || !rec.ok) {
    return park(workItem, pr, `could not reconcile the PR head before judging readiness (${(rec && rec.reason) || 'unreadable'})`)
  }
  // (existing freshness + ci logic stays below until Tasks 8-9 replace it)
  const _srBase = (typeof globalThis !== 'undefined' && globalThis.__SR_BASE) ? String(globalThis.__SR_BASE) : null
  const _baseArg = _srBase ? ` --base ${shq(_srBase)}` : ''
  const fresh = await cmdRunner(
    `python3 plugins/superheroes/lib/ship_phase.py --step freshness --work-item ${shq(workItem)}${_baseArg}`,
    { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' } } } })
  if (fresh.decision !== 'up_to_date') {
    return park(workItem, pr, `branch not up to date with base (${fresh.decision})`)
  }
  const ciResults = await exec([
    `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)} --emit-checks`,
  ])
  if (!ciResults[0] || !ciResults[0].ok) { return park(workItem, pr, 'CI status could not be read') }
  let ciChecks = null
  try { ciChecks = JSON.parse(ciResults[0].stdout) } catch (_) {}
  if (ciChecks === null) { return park(workItem, pr, 'CI status could not be read') }
  if (!Array.isArray(ciChecks) && ciChecks.error) { return park(workItem, pr, ciChecks.error || 'CI status could not be read') }
  const checksArr = Array.isArray(ciChecks) ? ciChecks : []
  const ciRes = ciStatusTwin.classify(checksArr)
  if (ciRes.status === 'green') { return park(workItem, pr, 'merge-ready: CI green and branch up to date — awaiting owner merge', true) }
  if (ciRes.status === 'none') { return park(workItem, pr, 'merge-ready: no required checks gate this PR — confirm checks before merging', true) }
  const ciReason = ciRes.failing && ciRes.failing.length ? 'checks not green: ' + ciRes.failing.join(', ') : 'CI could not be made green'
  return park(workItem, pr, ciReason)
}
```

- [ ] **Step 4: Run test, regenerate the bundle, verify both pass**

```bash
node plugins/superheroes/lib/tests/showrunner_ship_smoke.js
node plugins/superheroes/lib/bundle_showrunner.js
python3 -m pytest plugins/superheroes/lib/tests/test_bundle_drift.py -q
```
Expected: the smoke prints `OK: ...`; the bundle regenerates; `test_bundle_drift.py` PASSES.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/tests/showrunner_ship_smoke.js
git commit -m "feat(superheroes): thread generation + entry reconcile + shipFenceOrPark into shipPhase (#120, UFR-4/UFR-6)"
```

---

### Task 8: `shipPhase` catch-up stretch (freshen loop, conflict-abort, post-review note tracking)

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.js` (`shipPhase`)
- Create: `plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (register the new smoke)
- Regen: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Consumes: `shipFenceOrPark` (Task 7), `ship_phase.py --step freshness --attempt` (Task 2), `ship_phase.py --step freshen` (Task 3).
- Produces: a bounded catch-up loop inside `shipPhase` (max 3 by `freshness.decide`): `up_to_date` → exit; `sync` → fence → `freshen` (abort→park UFR-1; else re-read freshness on the pushed head); `give_up_notify` → park (FR-2); `gate` → park (UFR-2). Tracks `integrated` (a base merge advanced HEAD) for the FR-7 hand-back note.

- [ ] **Step 1: Write the failing test**

```js
// plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js
const assert = require('assert')
function run(plan) {
  // plan: { freshnessSeq: [...decisions], freshen: 'ok'|'conflict', fence: true|false }
  let fi = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('fence_cli')) return { ok: plan.fence !== false }
    if (label === 'lib' && p.includes('--step freshness')) { const d = plan.freshnessSeq[Math.min(fi++, plan.freshnessSeq.length - 1)]; return { decision: d } }
    if (label === 'lib' && p.includes('--step freshen')) {
      if (plan.freshen === 'conflict') return { ok: false, head: '/wt-head', conflict: true, reason: 'conflicts — aborted' }
      return { ok: true, head: '/wt-head2', conflict: false, reason: 'base integrated' }
    }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // sync once -> integrated -> up_to_date -> green -> ready (FR-1)
  let sr = run({ freshnessSeq: ['sync', 'up_to_date'], freshen: 'ok', fence: true })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'sync then up_to_date + green -> ready')

  // conflict on freshen -> park, never ready (UFR-1)
  sr = run({ freshnessSeq: ['sync'], freshen: 'conflict', fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'freshen conflict -> parked')
  assert.ok(/conflict|resolve/i.test(out.reason), 'conflict park names the conflict')

  // give_up_notify -> park (FR-2)
  sr = run({ freshnessSeq: ['give_up_notify'], fence: true })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'give_up_notify -> parked (FR-2)')

  // lost fence before a sync push -> park before mutation (UFR-4)
  sr = run({ freshnessSeq: ['sync'], freshen: 'ok', fence: false })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence -> parked before freshen')

  console.log('OK: catch-up sync->ready, conflict->park, give_up->park, lost-fence->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js`
Expected: FAIL — `shipPhase` parks on the first non-`up_to_date` freshness (the catch-up loop isn't wired).

- [ ] **Step 3: Write minimal implementation**

In `showrunner.js` `shipPhase`, replace the single freshness check (the `const fresh = ...` through the `if (fresh.decision !== 'up_to_date') { return park(...) }` block) with the bounded catch-up loop. The `const _srBase` / `const _baseArg` declarations Task 7 added (just above `const fresh =`) STAY — the loop reuses them; do **not** re-declare them or you get a duplicate-`const` SyntaxError. The freshness re-judge must carry `${wtArg}` so it runs against the **build worktree's branch HEAD** — the same tree `--step freshen` merges into — not the repo-root checkout (else the loop never converges and falsely gives up):

```js
  // FR-1/FR-2/UFR-1: bounded base catch-up. freshness.decide caps at 3 syncs; the attempt is
  // re-derived from reality each iteration (a merge converges, so no stored counter — FR-2 note).
  // (_srBase / _baseArg are already declared above by Task 7 — reuse them, don't re-declare.)
  let integrated = false                                    // FR-7: did a base merge advance HEAD after review?
  for (let attempt = 1; attempt <= 4; attempt += 1) {       // 4 = max syncs (3) + the terminal read
    const fresh = await cmdRunner(
      `python3 plugins/superheroes/lib/ship_phase.py --step freshness --work-item ${shq(workItem)}${_baseArg}${wtArg} --attempt ${shq(String(attempt))}`,
      { schema: { type: 'object', required: ['decision'], properties: { decision: { type: 'string' } } } })
    if (fresh.decision === 'up_to_date') break
    if (fresh.decision === 'give_up_notify') {
      return park(workItem, pr, 'branch is behind its base after the catch-up limit — update it before merge')
    }
    if (fresh.decision !== 'sync') {                        // 'gate' / unknown -> UFR-2 fail-closed
      return park(workItem, pr, `branch freshness could not be confirmed (${fresh.decision})`)
    }
    if (!(await shipFenceOrPark(workItem, generation))) {
      return park(workItem, pr, 'lease lost before base catch-up — park (UFR-4)')
    }
    const fr = await cmdRunner(
      `python3 plugins/superheroes/lib/ship_phase.py --step freshen --work-item ${shq(workItem)}${_baseArg}${wtArg}`,
      { schema: { type: 'object', required: ['ok'], properties: { ok: {}, head: {}, conflict: {}, reason: { type: 'string' } } } })
    if (fr && fr.conflict) {
      return park(workItem, pr, 'bringing in the base conflicts — undone (branch unchanged); please resolve and re-run')
    }
    if (!fr || !fr.ok) {
      return park(workItem, pr, `could not bring the base into the branch (${(fr && fr.reason) || 'unknown'})`)
    }
    integrated = true
  }
```

(Keep the existing CI block below for now; Task 9 replaces it and consumes `integrated` in the FR-7 hand-back note. An unused `let integrated` at this task's own commit is harmless — node runs the smoke and no linter gates `showrunner.js`.)

- [ ] **Step 4: Run, register the smoke, regen the bundle, verify**

Add to `SHOWRUNNER_SMOKES` in `test_showrunner_node_smokes.py`:

```python
    # #120: native ship-phase catch-up stretch (freshen loop, conflict-abort, fence, FR-2 give-up).
    "plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js",
```

```bash
node plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js
node plugins/superheroes/lib/bundle_showrunner.js
python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
```
Expected: the smoke prints `OK: ...`; the discovery-guard test and drift test PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "feat(superheroes): shipPhase base catch-up stretch — bounded freshen loop + conflict-abort + fence (#120, FR-1/2/7, UFR-1/4)"
```

---

### Task 9: `shipPhase` CI-fix stretch (fix loop, fixer dispatch, revert-to-draft)

**Files:**
- Create: `plugins/superheroes/lib/ship_ci.py` (pure FR-5 stale-head decider)
- Modify: `plugins/superheroes/lib/ship_phase.py` (`--emit-checks` FR-5 head-match)
- Modify: `plugins/superheroes/lib/showrunner.js` (`shipPhase`)
- Create: `plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_ship_phase_steps.py` (add `test_emit_checks_is_stale`)
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (register)
- Regen: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Consumes: `shipFenceOrPark`; `ship_phase.py --step ci --emit-checks` (now with the FR-5 `--worktree` head-match via `ship_ci.is_stale`), `ci-decide`, `ci-record`, `fix-push`, `revert-draft` (Tasks 4–6); `ciStatusTwin.classify` (existing twin).
- Produces: `ship_ci.is_stale(local, remote) -> bool` (pure FR-5 decider — confirmed head mismatch ⇒ the rollup is for an earlier commit).
- Produces: the CI stretch replacing the old single CI read. green → ready hand-back; none → honest "checks did not run" hand-back (UFR-3) ready-with-carve-out; red → `ci-decide`: `fix` → `ci-record` (write-ahead) → fence → fixer `agent` (label `'fix'`) → `fix-push` (park on `pushed:false`) → re-read checks on the new head (FR-5); `revert_and_gate` → fence → `revert-draft` → park (FR-4). A bounded re-check budget ends in an honest hand-back.

- [ ] **Step 1: Write the failing test**

```js
// plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js
const assert = require('assert')
function run(plan) {
  // plan: { checksSeq: [...arrays], ciDecide: 'fix'|'revert_and_gate', fixPush: 'ok'|'dirty' }
  let ci = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'exec' && p.includes('--emit-checks')) { const c = plan.checksSeq[Math.min(ci++, plan.checksSeq.length - 1)]; return [{ index: 0, ok: true, stdout: JSON.stringify(c) }] }
    if (label === 'lib' && p.includes('--step ci-decide')) return { action: plan.ciDecide, round: 1, reason: 'r' }
    if (label === 'lib' && p.includes('--step ci-record')) return plan.ciRecord === 'fail' ? { ok: false, reason: 'durable write failed' } : { ok: true }
    if (label === 'fix') return { fixed: true }
    if (label === 'lib' && p.includes('--step fix-push')) {
      if (plan.fixPush === 'dirty') return { ok: false, head: '/wt-head', pushed: false, reason: 'crashed fixer' }
      return { ok: true, head: '/wt-head2', pushed: true, reason: 'fix pushed' }
    }
    if (label === 'lib' && p.includes('--step revert-draft')) return plan.revertDraft === 'fail' ? { ok: false, reason: 'gh timeout' } : { ok: true, reason: 'reverted to draft' }
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // red -> fix -> push -> green -> ready (FR-3, FR-5: re-judged on the new head)
  let sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]], ciDecide: 'fix', fixPush: 'ok' })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'red->fix->green -> ready')

  // red -> revert_and_gate -> draft + park (FR-4)
  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', fixPush: 'ok' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate -> parked')
  assert.ok(/pass|draft|check/i.test(out.reason), 'park reason explains the checks could not pass')

  // red -> fix -> fix-push dirty (crashed fixer) -> park, no false ready (UFR-6 partial-failure)
  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', fixPush: 'dirty' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'dirty fix-push -> parked (no false ready)')

  // none on the ready head -> honest hand-back, ready-with-carve-out (UFR-3)
  sr = run({ checksSeq: [[]], ciDecide: 'fix', fixPush: 'ok' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'none -> ready (carve-out)')
  assert.ok(/no required checks|did not run|confirm/i.test(out.reason), 'none names the honest carve-out (UFR-3)')

  // FR-5 stale-pass rejection: the leaf marks the rollup stale (PR head != integrated head), so the
  // orchestrator NEVER classifies it as green — it re-waits (bounded) and ends in an honest park.
  sr = run({ checksSeq: [{ stale: true, local: 'abc', remote: 'old' }], ciDecide: 'fix', fixPush: 'ok' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'stale rollup -> never ready (FR-5)')
  assert.ok(/did not complete|confirm CI/i.test(out.reason), 'stale -> honest "checks did not complete" hand-back')

  // P4: a FAILED draft-flip must NOT let the hand-back claim "returned to draft".
  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'revert_and_gate', revertDraft: 'fail' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'revert_and_gate + failed draft-flip -> parked')
  assert.ok(/could NOT be returned to draft|set it to draft/i.test(out.reason), 'failed draft-flip surfaced honestly (P4)')

  // UFR-5 record-before-push: a failed write-ahead parks BEFORE the fixer/push (the round is never
  // left unrecorded, so the bound can't under-count).
  sr = run({ checksSeq: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]], ciDecide: 'fix', ciRecord: 'fail' })
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'ci-record durable-write fail -> parked before push (UFR-5)')
  assert.ok(/record the CI-fix round|durable write/i.test(out.reason), 'park names the failed write-ahead')

  console.log('OK: cifix red->fix->ready, revert->park, dirty->park, none->honest-ready, stale->never-green, revert-fail->honest, record-fail->park')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js`
Expected: FAIL — the old CI block parks on red instead of entering the fix loop.

- [ ] **Step 3: Write minimal implementation**

First, add the FR-5 stale-pass decider and wire it into `ship_phase.py`'s `--emit-checks`. `gh pr checks` reports on the PR's CURRENT remote head, so its rollup may only be judged when that head equals the worktree's local (integrated) HEAD; a confirmed mismatch means the rollup belongs to an earlier commit. Extract the comparison as a pure decider so it is testable without a gh stub (matching `freshness.py`/`ship_reconcile.py`).

Write a failing unit test (add to `plugins/superheroes/lib/tests/test_ship_phase_steps.py`):

```python
def test_emit_checks_is_stale():
    # FR-5: a confirmed head MISMATCH is stale (rollup is for an earlier commit); a match is judgeable;
    # an unreadable head is NOT 'stale' here (the leaf's own fail-closed paths handle those).
    sys.path.insert(0, LIB)
    import ship_ci
    assert ship_ci.is_stale("abc", "old") is True       # mismatch -> stale (reject the rollup)
    assert ship_ci.is_stale("abc", "abc") is False      # match -> judge the rollup
    assert ship_ci.is_stale("abc", None) is False       # unreadable remote -> not stale
    assert ship_ci.is_stale(None, "abc") is False       # unreadable local -> not stale
```

Run it: `python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py::test_emit_checks_is_stale -q` → FAIL (`No module named 'ship_ci'`). Then create the pure decider `plugins/superheroes/lib/ship_ci.py`:

```python
# plugins/superheroes/lib/ship_ci.py
"""Pure CI-head decider for the ship phase. FR-5 stale-pass rejection: `gh pr checks` reports on the
PR's CURRENT remote head, so its rollup may only be judged when that head equals the integrated local
HEAD. A confirmed mismatch is 'stale' (the rollup belongs to an earlier commit). Unreadable heads are
NOT 'stale' here — the leaf's own fail-closed paths handle those."""


def is_stale(local, remote):
    """True iff local and remote are both known and DIFFER (the rollup is for an earlier commit)."""
    return bool(local and remote and local != remote)
```

Import it in `ship_phase.py` (extend the second import line to `import idempotent_write, ship_reconcile, ship_ci`), and at the very top of the `elif a.emit_checks:` branch (immediately after the `elif a.emit_checks:` line, before `pr = _resolve_pr_number(...)`), add the head-match guard:

```python
    # FR-5 stale-pass rejection: only judge checks on the INTEGRATED head. If the remote PR head gh
    # reports the rollup for differs from the worktree's local HEAD, the rollup belongs to an EARLIER
    # commit -> emit {stale:true} so the orchestrator re-waits, never adopting an older green.
    if a.worktree:
        _local = _local_head(a.worktree)
        _remote = _remote_pr_head(a.work_item)
        if ship_ci.is_stale(_local, _remote):
            print(json.dumps({"stale": True, "local": _local, "remote": _remote}))
            sys.exit(0)
```

`test_emit_checks_is_stale` now passes (`python3 -m pytest plugins/superheroes/lib/tests/test_ship_phase_steps.py::test_emit_checks_is_stale -q`).

Then replace the existing CI block in `shipPhase` (from `const ciResults = await exec(...)` through the final `return park(workItem, pr, ciReason)`) with the CI stretch — note `${wtArg}` on the `--emit-checks` read (so the leaf does the head match), the `{stale}` re-wait, and the **checked** `revert-draft` result:

```js
  // FR-3/FR-4/FR-5/UFR-3/UFR-5: judge checks on the reconciled head; fix + re-check up to the
  // ci_loop cap (round count replayed from the journal, so a crash never resets it).
  const MAX_CI_PASSES = 6                                   // re-check budget > ci_loop cap; ends honest
  for (let pass = 0; pass < MAX_CI_PASSES; pass += 1) {
    const ciResults = await exec([
      `python3 plugins/superheroes/lib/ship_phase.py --step ci --work-item ${shq(workItem)} --emit-checks${wtArg}`,
    ])
    if (!ciResults[0] || !ciResults[0].ok) { return park(workItem, pr, 'CI status could not be read') }
    let ciChecks = null
    try { ciChecks = JSON.parse(ciResults[0].stdout) } catch (_) {}
    if (ciChecks === null) { return park(workItem, pr, 'CI status could not be read') }
    if (!Array.isArray(ciChecks) && ciChecks.error) { return park(workItem, pr, ciChecks.error || 'CI status could not be read') }
    if (!Array.isArray(ciChecks) && ciChecks.stale) {
      // FR-5: the PR head gh reports checks for is not yet the integrated local head — the rollup
      // belongs to an EARLIER commit. Re-wait (bounded by MAX_CI_PASSES); NEVER adopt an older green.
      continue
    }
    const ciRes = ciStatusTwin.classify(Array.isArray(ciChecks) ? ciChecks : [])
    if (ciRes.status === 'green') {
      return shipHandback(workItem, pr, { ready: true, ci: 'green', integrated, reason: 'merge-ready: CI green and branch up to date — awaiting owner merge' })
    }
    if (ciRes.status === 'none') {                          // UFR-3: provider but no checks on the ready head
      return shipHandback(workItem, pr, { ready: true, ci: 'none', integrated, reason: 'merge-ready: no required checks ran on the ready PR — confirm checks before merging' })
    }
    // red: let the parity-locked ci_loop bound decide fix vs revert.
    const decided = await cmdRunner(
      `python3 plugins/superheroes/lib/ship_phase.py --step ci-decide --work-item ${shq(workItem)} --failing ${shq(JSON.stringify(ciRes.failing))}`,
      { schema: { type: 'object', required: ['action'], properties: { action: { type: 'string' }, round: {}, reason: { type: 'string' } } } })
    if (!decided || decided.action === 'revert_and_gate') {
      if (!(await shipFenceOrPark(workItem, generation))) { return park(workItem, pr, 'lease lost before return-to-draft — park (UFR-4)') }
      const rd = await cmdRunner(
        `python3 plugins/superheroes/lib/ship_phase.py --step revert-draft --work-item ${shq(workItem)}`,
        { schema: { type: 'object', required: ['ok'], properties: { ok: {}, reason: { type: 'string' } } } })
      // P4: a failed draft-flip leaves a READY PR with broken checks — the hand-back must not lie.
      const reverted = !!(rd && rd.ok)
      return shipHandback(workItem, pr, { ready: false, ci: 'red', integrated, reverted,
        reason: reverted
          ? 'checks could not be made to pass — returned to draft for you'
          : `checks could not be made to pass, and the PR could NOT be returned to draft (${(rd && rd.reason) || 'unknown'}) — please set it to draft before merging` })
    }
    // fix: write-ahead the round (UFR-5), fence, run the fixer, push the clean tree, re-check.
    // Record-before-push invariant: a FAILED write-ahead (durable write error -> {ok:false}) must PARK
    // before the fixer/push, else the round goes unrecorded and UFR-5 under-counts. No back-half leaf
    // call is fire-and-forget on a durable/mutating step.
    const recd = await cmdRunner(
      `python3 plugins/superheroes/lib/ship_phase.py --step ci-record --work-item ${shq(workItem)} --round ${shq(String(decided.round))} --failing ${shq(JSON.stringify(ciRes.failing))}`,
      { schema: { type: 'object', required: ['ok'], properties: { ok: {}, reason: { type: 'string' } } } })
    if (!recd || !recd.ok) {
      return park(workItem, pr, 'could not record the CI-fix round (durable write failed) — park before the fix push (UFR-5)')
    }
    if (!(await shipFenceOrPark(workItem, generation))) { return park(workItem, pr, 'lease lost before CI fix push — park (UFR-4)') }
    await agent(
      `Fix the failing CI checks for this PR in the build worktree${worktree ? ' at ' + worktree : ''}: ${ciRes.failing.join(', ')}. ` +
      `Make ONLY the code changes needed to make the checks pass; do not write CI-log text into a commit.`,
      { label: 'fix' })
    const fp = await cmdRunner(
      `python3 plugins/superheroes/lib/ship_phase.py --step fix-push --work-item ${shq(workItem)}${wtArg}`,
      { schema: { type: 'object', required: ['ok'], properties: { ok: {}, head: {}, pushed: {}, reason: { type: 'string' } } } })
    if (!fp || !fp.pushed) {
      return park(workItem, pr, `could not push the CI fix (${(fp && fp.reason) || 'unknown'}) — park, no false ready`)
    }
    // loop: re-read checks on the new head (FR-5 stale-pass rejection — a fresh read, never an old green).
  }
  return park(workItem, pr, 'checks did not complete within the bound — confirm CI before merging')
```

Add a temporary `shipHandback` shim near `park` (Task 10 fills it in fully):

```js
// Structured hand-back (FR-6/FR-7). Task 10 builds the full readout; for now it delegates to park
// so the stretch wiring lands and is testable; the merge-ready flag carries through unchanged.
async function shipHandback(workItem, pr, info) {
  return park(workItem, pr, info.reason, !!info.ready)
}
module.exports.shipHandback = shipHandback
```

- [ ] **Step 4: Run, register, regen, verify**

Add to `SHOWRUNNER_SMOKES`:

```python
    # #120: native ship-phase CI-fix stretch (fix loop, fixer dispatch, revert-to-draft, UFR-3/5/6).
    "plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js",
```

**Update the existing `showrunner_ship_smoke.js` for the fix loop (required — else its `red -> parked` case reds at this commit).** After Task 9 a failing check enters the CI-fix loop instead of parking immediately, so the smoke's `run()` stub must answer the new leaves (its `fence_cli` stub was already added in Task 7; the green / none / error / sentinel / garbled cases short-circuit before the loop and stay unchanged):

```js
    // CI-fix loop (red path): decide -> revert-to-draft so the existing `red -> parked` case still parks
    if (label === 'lib' && p.includes('--step ci-decide')) return { action: 'revert_and_gate', round: 5, reason: 'cap' }
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
```

```bash
node plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js
node plugins/superheroes/lib/tests/showrunner_ship_smoke.js
node plugins/superheroes/lib/bundle_showrunner.js
python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
```
Expected: both smokes print `OK: ...`; discovery-guard + drift tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js plugins/superheroes/lib/tests/showrunner_ship_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "feat(superheroes): shipPhase CI-fix stretch — bounded fix loop + fixer dispatch + revert-to-draft (#120, FR-3/4/5, UFR-3/5/6)"
```

---

### Task 10: Structured hand-back via `readout.build_readout` (FR-6/FR-7, secret-scrubbed, best-effort)

**Files:**
- Modify: `plugins/superheroes/lib/showrunner.js` (`shipHandback`), add `ship_phase.py --step handback` OR reuse `readout_post.py`
- Create: `plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (register)
- Modify: `plugins/superheroes/lib/readout_post.py` (accept a structured `--ctx` JSON so `build_readout` runs server-side, scrubbed)
- Test: `plugins/superheroes/lib/tests/test_readout.py` (add a build_readout-from-ctx assertion)
- Regen: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Consumes: `readout.build_readout`, `readout.scrub`, `readout_post` delivery contract (`posted`/`recorded`).
- Produces: `readout_post.py --work-item <wi> [--pr <n>] (--reason <text> | --ctx <json>)`. With `--ctx`, it builds the structured readout server-side via `readout.build_readout` (every free-text field scrubbed), then posts/records it with the existing best-effort contract. `shipHandback(workItem, pr, info)` assembles the ctx (pr_url, ci_status, built-vs-acceptance, test-results, spot-check list, FR-7 integration note when `info.integrated`) and posts it; the run's outcome does **not** depend on the post landing (best-effort — `park`'s delivered/undelivered reason surfacing is reused).

- [ ] **Step 1: Write the failing test**

```python
# add to plugins/superheroes/lib/tests/test_readout.py
import json, os, subprocess, sys
LIB_R = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_readout_post_builds_structured_ctx(tmp_path, monkeypatch):
    # FR-6/FR-7 teeth: --ctx must build (and durably record) a hand-back carrying the PR link,
    # built-vs-asked, the spot-check list, the "never merges" statement, AND the FR-7 integration note.
    monkeypatch.setenv("SUPERHEROES_STORE_ROOT", str(tmp_path / "store"))  # isolate the store (never the real one)
    sys.path.insert(0, LIB_R)
    import control_plane
    ctx = {"pr_url": "https://x/pr/7", "ci_status": "green — all required checks pass",
           "built_vs_acceptance": "all FRs met", "smoke": ["confirm catch-up", "review the diff"],
           "integration_note": "the final head carries post-review base integration"}
    r = subprocess.run([sys.executable, os.path.join(LIB_R, "readout_post.py"),
                        "--work-item", "wi", "--ctx", json.dumps(ctx)],
                       capture_output=True, text=True, cwd=str(tmp_path), timeout=30)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out.get("recorded") is True or out.get("posted") is True
    # no --pr -> recorded to the store; read the structured hand-back back and assert the FR-6/FR-7 elements
    body = open(control_plane.paths(str(tmp_path), "wi")["resume_brief"]).read()
    assert "https://x/pr/7" in body                          # FR-6: PR link
    assert "all FRs met" in body                             # FR-6: built-vs-asked
    assert "confirm catch-up" in body                        # FR-6: spot-check list
    assert "Merge is yours" in body                          # FR-6: never-merges statement
    assert "post-review base integration" in body            # FR-7: integration note
```

And the node smoke:

```js
// plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js
const assert = require('assert')
function run(capture) {
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) { capture.ctxSeen = /--ctx/.test(p); return { posted: true } }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  const capture = {}
  const sr = run(capture)
  const out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready via structured hand-back')
  assert.ok(capture.ctxSeen, 'hand-back posts a STRUCTURED ctx (--ctx), not a one-line reason (FR-6)')

  // best-effort: even when delivery reports neither posted nor recorded, the run still reports ready,
  // and surfaces the undelivered warning (FR-6 / #118 carve-out: never ship-GATE on the hand-back).
  global.agent = (orig => async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'lib' && (p.includes('readout_post') || p.includes('readout'))) return { posted: false, recorded: false, error: 'disk full' }
    return orig(p, opts)
  })(global.agent)
  delete require.cache[require.resolve('../showrunner.js')]
  const sr2 = require('../showrunner.js')
  const out2 = await sr2.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out2.outcome, 'ready', 'undelivered hand-back still reports ready (best-effort, not ship-gated)')
  assert.ok(/warning|deliver/i.test(out2.reason), 'undelivered hand-back is surfaced as a warning')
  console.log('OK: structured hand-back ctx + best-effort delivery')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js`
Expected: FAIL — `shipHandback` still calls `park` with a one-line reason (no `--ctx`).

- [ ] **Step 3: Write minimal implementation**

In `readout_post.py`, add a `--ctx` arg and build the structured readout when present:

```python
ap.add_argument("--ctx", default=None, help="JSON context for readout.build_readout (structured hand-back)")
```

After parsing, before the `text, _ok = readout.scrub(...)` line, branch on `--ctx`:

```python
if a.ctx:
    try:
        ctx = json.loads(a.ctx)
    except ValueError:
        ctx = {}
    ctx.setdefault("root", os.getcwd())
    note = ctx.pop("integration_note", None)
    body = readout.build_readout(ctx)                # every free-text field scrubbed inside build_readout
    if note:
        body = body + "\n\n> _" + readout.scrub(note, root=os.getcwd())[0] + "_"
    text = body
else:
    text, _ok = readout.scrub(a.reason, root=os.getcwd())
```

Make `--reason` optional (since `--ctx` can replace it):

```python
ap.add_argument("--reason", default=None)
```

In `showrunner.js`, replace the `shipHandback` shim with the full builder:

```js
async function shipHandback(workItem, pr, info) {
  const prNum = pr && pr.number ? ` --pr ${shq(String(pr.number))}` : ''
  const prUrl = pr && pr.url ? pr.url : ''
  const ctx = {
    pr_url: prUrl,
    ci_status: info.ci === 'green' ? 'green — all required checks pass'
      : info.ci === 'none' ? 'no required checks ran on the ready PR — confirm before merging'
      : 'checks could not be made to pass — returned to draft',
    built_vs_acceptance: info.reason || '',
    smoke: ['Confirm the PR branch contains its base', 'Confirm CI on the ready head', 'Review the diff before merging'],
  }
  if (info.integrated) {
    ctx.integration_note = 'the final commit carries base integration done after the code review (the merged-in base was check-vetted, not re-reviewed)'
  }
  const rPost = await cmdRunner(
    `python3 plugins/superheroes/lib/readout_post.py --work-item ${shq(workItem)}${prNum} --ctx ${shq(JSON.stringify(ctx))}`,
    { schema: { type: 'object', required: ['posted'], properties: { posted: {}, recorded: {}, error: { type: 'string' } } } })
  const delivered = rPost && (rPost.posted || rPost.recorded)
  const reasonOut = delivered ? info.reason
    : `${info.reason} [warning: hand-back could not be delivered (${(rPost && rPost.error) || 'unknown'})]`
  return { outcome: info.ready ? 'ready' : 'parked', phase: 'ship', reason: reasonOut }
}
```

- [ ] **Step 4: Run, register, regen, verify**

Add to `SHOWRUNNER_SMOKES`:

```python
    # #120: native ship-phase structured hand-back (FR-6/FR-7, scrubbed, best-effort delivery).
    "plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js",
```

```bash
node plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js
node plugins/superheroes/lib/tests/showrunner_ship_freshen_smoke.js
node plugins/superheroes/lib/tests/showrunner_ship_cifix_smoke.js
node plugins/superheroes/lib/bundle_showrunner.js
python3 -m pytest plugins/superheroes/lib/tests/test_readout.py plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
```
Expected: all smokes print `OK: ...`; pytest PASSES. (The freshen/cifix smokes stub `readout`/`readout_post` already, so the `--ctx` change is compatible.)

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/readout_post.py plugins/superheroes/lib/tests/showrunner_ship_handback_smoke.js plugins/superheroes/lib/tests/test_readout.py plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "feat(superheroes): structured ship hand-back via build_readout — scrubbed, FR-7 note, best-effort (#120, FR-6/7)"
```

---

### Task 11: Fail-closed guard-read smoke + never-merge backstop (UFR-2, UFR-4, FR-8)

**Files:**
- Create: `plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (register)

**Interfaces:**
- Consumes: the wired `shipPhase` (Tasks 7–10). No production code change — this task *proves* the fail-closed and never-merge invariants the prior tasks built.

- [ ] **Step 1: Write the failing test**

```js
// plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js
const assert = require('assert')
function run(stub) {
  const calls = []
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    calls.push(p)
    const r = stub(label, p)
    if (r !== undefined) return r
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return { sr: require('../showrunner.js'), calls }
}
function base(label, p) {
  if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
  if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
  if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
  return undefined
}
;(async () => {
  // UFR-2: an unreadable entry reconcile -> park, never ready. (Entry fence passes, reconcile fails.)
  let { sr } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: false, reason: 'remote head unreadable' }
    return base(label, p)
  })
  let out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'unreadable reconcile -> parked (UFR-2)')

  // S1 / UFR-4: the ENTRY reconcile is itself fenced — a lost lease parks BEFORE the reconcile push,
  // so reconcile-head never even runs.
  let calls
  ;({ sr, calls } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) return { ok: false, reason: 'lease lost' }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'entry fence lost -> parked before the reconcile push (S1)')
  assert.ok(!calls.some((c) => c.includes('reconcile-head')), 'entry fence parks BEFORE reconcile-head runs')

  // UFR-4 at the SECOND boundary: entry fence ok, then the catch-up (sync) fence is lost -> park.
  let fenceCalls = 0
  ;({ sr } = run((label, p) => {
    if (label === 'lib' && p.includes('fence_cli')) { fenceCalls += 1; return { ok: fenceCalls === 1 } }  // entry ok, next lost
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'sync' }
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'parked', 'lost fence before the sync push -> parked (UFR-4, second boundary)')

  // FR-8: across the whole ship path, no leaf ever issues `gh pr merge` / a merge.
  let merged = false
  ;({ sr } = run((label, p) => {
    if (/gh pr merge|--merge\b|pr merge/.test(p)) merged = true
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('--step freshness')) return { decision: 'up_to_date' }
    if (label === 'exec' && p.includes('--emit-checks')) return [{ index: 0, ok: true, stdout: JSON.stringify([{ name: 'ci', bucket: 'pass', state: 'success' }]) }]
    return base(label, p)
  }))
  out = await sr.shipPhase('wi', { number: 7 }, 5)
  assert.strictEqual(out.outcome, 'ready', 'green -> ready')
  assert.strictEqual(merged, false, 'FR-8: the ship path never merges the PR')
  console.log('OK: UFR-2 reconcile-park, S1 entry-fence, UFR-4 second-boundary fence, FR-8 never-merge')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js`
Expected: PASS if Tasks 7–10 wired the guards correctly (this is a confirmation smoke). If it FAILS, fix the corresponding guard in `shipPhase` before proceeding — do not weaken the assertion.

- [ ] **Step 3: Register the smoke**

Add to `SHOWRUNNER_SMOKES`:

```python
    # #120: ship-phase guard invariants (UFR-2 unreadable-park, UFR-4 fence fail-closed, FR-8 never-merge).
    "plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js",
```

- [ ] **Step 4: Run the discovery guard**

Run: `python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py -q`
Expected: PASS (the new smoke is registered and passes).

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/tests/showrunner_ship_guard_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "test(superheroes): ship-phase guard invariants — UFR-2 park, UFR-4 fence fail-closed, FR-8 never-merge (#120)"
```

---

### Task 12: Forged-ship walkthrough smoke (DoD end-to-end) + #118 seam documentation

**Files:**
- Create: `plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js`
- Modify: `plugins/superheroes/lib/tests/test_showrunner_node_smokes.py` (register)
- Modify: `plugins/superheroes/lib/showrunner.js` (a documented seam comment-block above `shipPhase`)
- Regen: `plugins/superheroes/lib/showrunner.bundle.js`

**Interfaces:**
- Consumes: the full wired `shipPhase`. No behavior change — the walkthrough drives catch-up → fix-loop → return-to-draft → structured hand-back end-to-end (the spec's DoD), and the seam comment documents the fence/lease threading + the per-stretch foldable seams for #118 (coordination B).

- [ ] **Step 1: Write the failing test**

```js
// plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js
// Forged-ship DoD walkthrough: one run exercises catch-up, the fix-the-checks loop, return-to-draft,
// and the structured hand-back end-to-end with forged leaves.
const assert = require('assert')
function run(script) {
  let fi = 0, ci = 0
  global.agent = async (p, opts) => {
    const label = (opts && opts.label) || ''
    if (label === 'exec' && p.includes('build_entry.py')) return [{ index: 0, ok: true, stdout: JSON.stringify({ path: '/wt', outcome: 'reused' }) }]
    if (label === 'exec' && p.includes('rev-parse')) return [{ index: 0, ok: true, stdout: '/wt-head' }]
    if (label === 'lib' && p.includes('reconcile-head')) return { ok: true, head: '/wt-head', reason: 'in sync' }
    if (label === 'lib' && p.includes('fence_cli')) return { ok: true }
    if (label === 'lib' && p.includes('--step freshness')) { const d = script.freshness[Math.min(fi++, script.freshness.length - 1)]; return { decision: d } }
    if (label === 'lib' && p.includes('--step freshen')) return { ok: true, head: '/wt-head2', conflict: false, reason: 'base integrated' }
    if (label === 'exec' && p.includes('--emit-checks')) { const c = script.checks[Math.min(ci++, script.checks.length - 1)]; return [{ index: 0, ok: true, stdout: JSON.stringify(c) }] }
    if (label === 'lib' && p.includes('--step ci-decide')) return script.ciDecide
    if (label === 'lib' && p.includes('--step ci-record')) return { ok: true }
    if (label === 'fix') return { fixed: true }
    if (label === 'lib' && p.includes('--step fix-push')) return { ok: true, head: '/wt-head3', pushed: true, reason: 'fix pushed' }
    if (label === 'lib' && p.includes('--step revert-draft')) return { ok: true, reason: 'reverted to draft' }
    if (label === 'lib' && (p.includes('readout') || p.includes('pr_comment'))) return { posted: true }
    throw new Error('unexpected agent: label=' + label + ' prompt=' + p.slice(0, 80))
  }
  global.log = () => {}
  delete require.cache[require.resolve('../showrunner.js')]
  return require('../showrunner.js')
}
;(async () => {
  // catch-up (sync->up_to_date) then fix-the-checks (red->fix->green) -> ready, FR-7 integration note.
  let sr = run({ freshness: ['sync', 'up_to_date'],
                 checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }], [{ name: 'ci', bucket: 'pass', state: 'success' }]],
                 ciDecide: { action: 'fix', round: 1, reason: 'r' } })
  let out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'ready', 'walkthrough catch-up + fix -> ready')

  // terminal: red -> revert_and_gate -> draft + hand-back park.
  sr = run({ freshness: ['up_to_date'], checks: [[{ name: 'ci', bucket: 'fail', state: 'failure' }]],
             ciDecide: { action: 'revert_and_gate', round: 5, reason: 'cap' } })
  out = await sr.shipPhase('wi', { number: 7, url: 'https://x/pr/7' }, 5)
  assert.strictEqual(out.outcome, 'parked', 'walkthrough terminal fail -> draft + parked')
  console.log('OK: forged-ship walkthrough catch-up+fix->ready, terminal->draft')
})().catch((e) => { console.error('FAIL:', e.message); process.exit(1) })
```

- [ ] **Step 2: Run test to verify it passes**

Run: `node plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js`
Expected: PASS (the full back-half is wired). Fix any gap it exposes before proceeding.

- [ ] **Step 3: Document the #118 seam**

Add this comment block immediately above `async function shipPhase` in `showrunner.js`:

```js
// ── Native back-half seam map (for #118 courier-surface collapse, which sequences AFTER #120) ──
// shipPhase orchestrates four SEPARABLE per-stretch seams, each with the same shape:
//   world-read → renew-then-fence(generation) → mutate (git/gh leaf) → read-back-confirm.
//   1. entry reconcile  — ship_phase.py --step reconcile-head  (idempotent push-reconcile)
//   2. catch-up stretch — ship_phase.py --step freshen          (merge base / conflict-abort / push)
//   3. ci-fix stretch   — ship_phase.py --step {ci,ci-decide,ci-record,fix-push,revert-draft}
//   4. hand-back        — readout_post.py --ctx                 (best-effort; never ship-gated)
// FENCE/LEASE SEAM: the lease generation is threaded from reconcile() → runPhases(deps.generation)
//   → shipPhase(_, _, generation); every mutating boundary calls shipFenceOrPark(workItem, generation)
//   (renew-then-fence, fail-closed) BEFORE the mutation — the same generation build_phase.js fences on.
// IDEMPOTENCY SEAM: create / ready-flip / draft-flip / push-reconcile route through idempotent_write.py
//   (read-reality, apply-once). #118 generalizes that primitive to EVERY durable write (its FR-4).
// #118 may fold/relabel these leaves; #120 deliberately leaves them as clean, un-folded seams.
```

- [ ] **Step 4: Register, regen, verify**

Add to `SHOWRUNNER_SMOKES`:

```python
    # #120: forged-ship DoD walkthrough — catch-up + fix-loop + return-to-draft + hand-back end-to-end.
    "plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js",
```

```bash
node plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js
node plugins/superheroes/lib/bundle_showrunner.js
python3 -m pytest plugins/superheroes/lib/tests/test_showrunner_node_smokes.py plugins/superheroes/lib/tests/test_bundle_drift.py -q
```
Expected: the walkthrough prints `OK: ...`; discovery-guard + drift tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/superheroes/lib/showrunner.js plugins/superheroes/lib/showrunner.bundle.js plugins/superheroes/lib/tests/showrunner_ship_walkthrough_smoke.js plugins/superheroes/lib/tests/test_showrunner_node_smokes.py
git commit -m "test(superheroes): forged-ship DoD walkthrough + documented #118 fence/idempotency/per-stretch seams (#120)"
```

---

### Task 13: Full local gate — every requirement green, no drift

**Files:**
- No new code; this task runs the complete gate the CI enforces and fixes any residual failure.

**Interfaces:**
- Consumes: every prior task.
- Produces: a green tree ready for the producer's review-code + PR — all validators, the full pytest suite, every node smoke, and the bundle-drift check pass.

- [ ] **Step 1: Run the full validator + pytest gate**

```bash
python3 .github/scripts/validate_marketplace.py
python3 .github/scripts/validate_hosts.py
python3 .github/scripts/validate_skills.py
python3 -m pytest .github/scripts/tests/ plugins/superheroes/lib/tests/ plugins/superheroes/eval/tests/ eval/lib/tests/ -q
```
Expected: all validators print OK; pytest reports all passed (the new `test_idempotent_write.py`, `test_ship_phase_steps.py`, the node-smoke wrapper, and the drift test included).

- [ ] **Step 2: Run every showrunner node smoke directly**

```bash
for f in plugins/superheroes/lib/tests/showrunner_ship_*_smoke.js; do echo "== $f"; node "$f" || exit 1; done
```
Expected: each prints its `OK: ...` line; the loop exits 0.

- [ ] **Step 3: Confirm the requirement→smoke coverage floor**

Verify (by inspection against the plan's verification floor) that every FR/UFR has a smoke or assertion:
FR-1/2/7 + UFR-1 → `showrunner_ship_freshen_smoke.js`; FR-3/4/5 + UFR-3/5/6 + partial-failure → `showrunner_ship_cifix_smoke.js` + `test_ship_phase_steps.py` (dirty-tree, NFF replay); FR-6/7 → `showrunner_ship_handback_smoke.js`; FR-8 + UFR-2/4 → `showrunner_ship_guard_smoke.js`; FR-9 → `test_ship_phase_steps.py` (non-force push asserted in freshen/reconcile/fix-push) + the seam doc; UFR-6 idempotency → `test_idempotent_write.py` + `test_ship_phase_steps.py::test_pr_entry_and_ship_phase_use_idempotent_primitive`; DoD end-to-end → `showrunner_ship_walkthrough_smoke.js`.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test(superheroes): green the full local gate for the native back-half (#120)"
```

(If Step 1–2 were already green with nothing to fix, skip the commit.)

---

## Self-Review

**Spec coverage:** FR-1 (Task 8 freshen), FR-2 (Task 8 give_up_notify), FR-3 (Task 9 fix loop), FR-4 (Task 9 revert_and_gate + Task 6 revert-draft), FR-5 (Task 9 head-SHA-matched CI read — `--emit-checks --worktree` emits `{stale}` when the PR head ≠ the integrated worktree HEAD, never adopting an older green; Task 2 reconcile-head), FR-6 (Task 10 structured hand-back), FR-7 (Task 8 `integrated` flag → Task 10 note), FR-8 (Task 11 never-merge), FR-9 (Tasks 2/3/5 non-force push). UFR-1 (Task 3 conflict-abort + Task 8 park), UFR-2 (Task 8 gate-park + Task 11), UFR-3 (Task 9 none→honest), UFR-4 (Task 7 fence helper + Tasks 8/9 fence-before-mutation + Task 11), UFR-5 (Task 4 journal replay), UFR-6 (Tasks 1/2/5/6 idempotency + reconcile). NFRs: secret hygiene (Task 10 via build_readout scrub), bounded autonomy (Task 9 `MAX_CI_PASSES` + the deciders' caps), behavior parity (deciders reused unchanged). DoD (Task 12 walkthrough). #118 coordination: generic primitive with 3 call sites (Tasks 1/2/6), fence/lease seam doc (Task 12), best-effort hand-back (Task 10), no courier-folding.

**Type consistency:** `ship_phase.py` steps all return `{ok, ...}`; the JS reads `.ok`/`.decision`/`.action`/`.pushed` consistently. `shipFenceOrPark(workItem, generation)`, `shipHandback(workItem, pr, info)`, `idempotent_apply(key, current_reader, apply_fn)` are referenced with the same signatures everywhere. `_git`/`_local_head`/`_remote_pr_head` are defined once (Task 2) and reused (Tasks 3/5).
