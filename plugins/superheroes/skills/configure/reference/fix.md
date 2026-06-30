# configure — fix path

Reached from `configure` when a project is configured but needs repair (FR-1): a legacy/pre-registry
layout, an incomplete set-up, a pending structural change, or a calibration still marked
provisional. Apply what is unambiguous silently; surface what needs an owner decision.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## 1 — Apply mechanical updates silently (FR-8)

A calibration file brought up to date by a single unambiguous transformation (a format/version bump
with exactly one correct result) is applied **without prompting**. In repo-shared mode the change
travels with the repo (collaborators receive it); in out-of-repo mode it is made only on the local
machine. Migrate-on-read is the trigger:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import core_md
print(core_md.resolve_shared('.'))"
```

If a write cannot complete, the original file is left intact and the failure is surfaced — never a
partial or corrupt file (UFR-8). Any update needing an owner **choice** is surfaced as a fix below,
never applied silently.

## 2 — Adopt a legacy / pre-registry project (FR-15), safely (UFR-9)

`resolve_shared` adopts an older single-hero profile into the current world on read — never a
destructive re-initialize. If a legacy profile is **unreadable or malformed**, report that it
cannot be read, **leave the file untouched**, and ask rather than guess (UFR-9).

## 3 — First-push rebind (FR-9) and its recovery (UFR-10)

When a project that previously had no remote has just gained one, re-anchor its stored settings to
that remote so pre-remote work does not fork:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/mode_migrate.py" rebind --cwd .
```

A `conflict` result means the pre-remote and an existing remote-keyed setting disagree on a value —
**surface the conflict for the owner; nothing is silently overwritten**. An interrupted rebind is
recovered automatically by the Step-1 `recover` on the next run (the journal lives at a key that
survives the re-anchoring). A headless run records a rebind conflict un-applied and continues (FR-17).

## 4 — Confirm provisional calibration (FR-18)

If the calibration is still **provisional** (auto-generated, not yet validated), surface it as
unconfirmed and offer the owner to review and confirm it. On the owner's explicit confirm, flip the
whole calibration — the shared core **and** every present hero layer — through the lib's confirm
path. `write` cannot do this (reuse-not-clobber returns `reused` on an existing file); `confirm`
re-renders the core in place and surgically flips each layer, preserving `created`/`nudge-ack` and
bumping `updated`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/core_md.py" confirm --cwd .
```

**Read the result, don't assume success.** `confirm` returns `{core: {action}, layers: {hero: {action}}}`.
Only `confirmed`/`noop` means done — surface anything else to the owner instead of reporting success: `behind`
= the calibration is from a **newer plugin version**, tell them to upgrade rather than confirm; `deferred` =
the store/lock was busy, retry; `absent` = nothing to confirm. A non-confirmed core leaves the layers
untouched (no split state), so the whole calibration stays provisional until it genuinely confirms.

Merely viewing the profile never confirms it (FR-18); only this explicit owner-confirm does.

## Headless posture (FR-17)

While running with no human to answer, do not perform any fix that needs an owner decision — a
rebind conflict, an owner-choice migration, or a storage-mode switch. Record the situation as a
provisional, un-applied fix, apply only what is mechanical, and continue without blocking.
