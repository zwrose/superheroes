## Contents

- §1 — Apply mechanical updates silently (FR-8)
- §2 — Adopt a legacy / pre-registry project (FR-15), safely (UFR-9)
- §3 — First-push rebind (FR-9) and its recovery (UFR-10)
- §4 — Confirm provisional calibration (FR-18)
- Fix posture (FR-17)

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
machine. `resolve_shared` returns shared facts from `core.md` or the `legacy-profile-unsupported`
refusal; it never migrates, unlinks, or commits (detection writes nothing) but is not write-free —
`read()` inherits `mode_registry.resolve`'s project-store backfill:

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

- **legacy profile, no `core.md`** → **fix** (not set-up): legacy is hero evidence so
  `mode_registry.resolve` backfills a registry; seed `core.md` + hero layers keeping the recorded
  mode. Once `core.md` parses, `resolve_shared` stops refusing.
- **`core.md` present + stray legacy** → **fix** via `legacy-profile-unsupported`. Branch on
  `coreFactsEmpty` from the reconcile signal's `detail` (step 1's `configure_route.route` JSON) —
  not from `resolve_shared`, which carries only hero detail and `coreMd`. Treat a missing or
  unknown `coreFactsEmpty` as true (cautious). When false, tell the owner the stray file is no
  longer read and they may remove or archive it. When true, name the legacy path as the only
  populated calibration and require its content into `core.md` + the layer before removal.

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
survives the re-anchoring). A rebind conflict is recorded un-applied and the run continues (FR-17).

## 4 — Confirm provisional calibration (FR-18)

If the calibration is still **provisional** (auto-generated, not yet validated):

**Default:** do not run `confirm` — leave the calibration provisional. **Disclosure:** write into
the run's durable output what is unconfirmed and what confirming would change (the shared core and
every present hero layer flip from provisional to confirmed). **Follow-up:** `core_md.py confirm`
runs **only** when the owner asks for confirmation in this turn — invoking `/superheroes:configure`
is not itself the confirm.

`write` cannot do this (reuse-not-clobber returns `reused` on an existing file); `confirm`
re-renders the core in place and surgically flips each layer, preserving `created`/`nudge-ack` and
bumping `updated`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/core_md.py" confirm --cwd .
```

**Read the result, don't assume success.** `confirm` returns `{core: {action}, layers: {hero: {action}}}`.
Only `confirmed`/`noop` means done — surface anything else to the owner instead of reporting success: `behind`
= the calibration is from a **newer plugin version**, tell them to upgrade rather than confirm; `deferred` without `reason` =
store/lock busy, retry; `deferred` with `reason: core-md-unreadable` = not retryable, surface `detail`; `absent` = nothing to confirm. A non-confirmed core leaves the layers
untouched (no split state), so the whole calibration stays provisional until it genuinely confirms.

Only this explicit owner-confirm confirms the profile; merely viewing it never does (FR-18).

## Fix posture (FR-17)

Do not perform any fix that needs an owner decision — a rebind conflict, an owner-choice migration,
or a storage-mode flip. Record the situation as a provisional, un-applied fix, apply only what is
mechanical, and continue without blocking.
