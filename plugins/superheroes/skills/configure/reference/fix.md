# configure — fix path

Reached from `configure` when a project is configured but needs repair (FR-1): a legacy/pre-registry
layout, an incomplete set-up, a pending structural change, or a calibration still marked
provisional. Apply what is unambiguous silently; surface what needs an owner decision.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## 1 — Apply mechanical updates silently (FR-8)

An unambiguous format/version update is applied **without prompting** where such an update exists
(`core_md.py confirm`, and `write` on a create path). On the shared-facts read path there is no
on-disk transformation at all — older `schemaVersion` is upgraded **in memory only**, never written
back (UFR-2), and a legacy profile is refused rather than converted (#724). In repo-shared mode the change
travels with the repo (collaborators receive it); in out-of-repo mode it is made only on the local
machine. `resolve_shared` is a **pure read** — it returns the shared facts from `core.md`, or the
named `legacy-profile-unsupported` refusal when `core.md` cannot supply them and a pre-`core.md`
legacy profile is present. It applies nothing and writes nothing:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import core_md
print(core_md.resolve_shared('.'))"
```

Probe it: a **fact dict** means nothing to apply here; a dict whose `action` is `refused` means go
to section 2; **`None`** means greenfield — that is a set-up, not a fix.

If a write cannot complete, the original file is left intact and the failure is surfaced — never a
partial or corrupt file (UFR-8). Any update needing an owner **choice** is surfaced as a fix below,
never applied silently.

## 2 — Adopt a legacy / pre-registry project (FR-15), safely (UFR-9)

A legacy profile is **no longer adopted automatically**. `resolve_shared` returns the named
refusal `legacy-profile-unsupported`, carrying `paths` (where the legacy file was found) and
`remedy`. Re-calibration takes minutes, and fail-loud-with-remedy beats silent destruction — the
old automatic adoption could clobber a `core.md` and the legacy profile itself (issue #724).

The remedy is **re-calibration through this skill**, and it has two shapes:

- **legacy profile, no `core.md`** → `configure` routes to **set-up**: write a fresh `core.md`
  plus the hero layers from detection + the owner's answers. Once `core.md` parses,
  `resolve_shared` stops refusing.
- **`core.md` already present, a stray legacy profile still on disk** → `configure` routes to
  **fix**, driven by the `legacy-profile-unsupported` reconcile signal. Nothing is refused (the
  facts come from `core.md`); the fix is to tell the owner the stray file is no longer read and let
  **them** remove or archive it.

**Superheroes never deletes the legacy file** — the owner does. An unreadable or malformed legacy
profile is reported, left untouched, and asked about rather than guessed at (UFR-9). The refusal
reports *presence*, not content: it never reads the file, so a malformed one refuses identically
to a well-formed one. `configure` does not archive, move, or delete anything on the owner's behalf.

## 3 — First-push rebind (FR-9) and its recovery (UFR-10)

When a project that previously had no remote has just gained one, re-anchor its stored settings to
that remote so pre-remote work does not fork:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/mode_migrate.py" rebind --cwd .
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
python3 -B "$ROOT_DIR/lib/core_md.py" confirm --cwd .
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
