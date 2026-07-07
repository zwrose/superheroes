# Contents

- Render the combined view
- The tune menu
- Switch the storage mode

# configure — view & tune path

Reached from `configure` when a project is configured and healthy (FR-1). Renders the whole
calibration on one screen and offers a small menu of targeted changes. A view-only run on an
up-to-date project changes nothing (FR-12).

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## 1 — Render the combined view (FR-4) + drift notice (FR-7)

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import configure_view
print(configure_view.render('.'))"
```

One plain-text screen, top to bottom: the project's core facts, each hero's layer, the pinned
patterns, and the effective per-role model tiers — "here is everything superheroes knows about
this project," not a list of files. Any current staleness/drift is shown as a **single,
dismissible reminder on every run** (whether or not it was dismissed before); the owner can act on
it or dismiss it again for that run. Rendering is read-only — it never confirms a provisional
calibration (FR-18).

## 2 — The tune menu (FR-5)

Present, inline beneath the view, the things the owner can change — each routed to the **smallest**
action that owns it, leaving the rest of the calibration untouched:

- **Change a single discrete field** (the verify command, the threat model) → a focused guided edit
  through `core_md`.
- **Re-calibrate a prose-heavy hero layer** → re-run that hero's own (now-internal) calibration.
- **Set up a hero skipped at set-up** (FR-6) → list every optional hero not yet set up and not
  previously declined, and offer to run each one's set-up from here. Get the list from the lib —
  never guess which heroes apply:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 "$ROOT_DIR/lib/hero_setup.py" offerable --cwd .
  ```

  This is the mandatory/optional split: a missing **review-crew** layer is an incomplete set-up the
  route already sends to `fix`; optional heroes (test-pilot) never force a repair — they surface
  here as an offer. A hero the owner declines (here or at set-up) is recorded so it is not re-offered.
- **Sweep orphaned per-project stores** → when the view's `storage health` line reports orphaned
  or unknown-provenance stores, offer the sweep. Always report first, show the counts and the
  orphan list, and delete only on the owner's explicit confirm:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 "$ROOT_DIR/lib/store_sweep.py" report
  # show the owner the counts + orphaned paths; on their explicit confirm:
  python3 "$ROOT_DIR/lib/store_sweep.py" sweep
  ```

  `sweep` deletes only provenance-orphaned stores (recorded source path gone, no real content) —
  never stores with content or a live source path. `unknown` stores (pre-provenance, no content)
  are kept unless the owner explicitly opts in with `--include-unknown`. Any classification doubt
  reads as real and is kept.
- **View or edit the permission posture** (the auto-allow routine families that let an owner-absent
  showrunner run finish without babysitting, below the owner-role floor) → follow
  `reference/permission.md`. The full allow set is already on the view's **Permission posture**
  section; edits go only through `permission_rules.set_rule` / `remove_rule` (the one sanctioned
  change path, FR-9).
- **Write the review-discipline section into the project's `CLAUDE.md`** — offered ONLY when
  the storage mode is **in-repo** (out-of-repo mode exists to keep the repo free of superheroes
  traces; there the SessionStart bootstrap note is the sole carrier). Owner-gated like every
  write: show the section text (source of truth:
  `$ROOT_DIR/rubric/review-discipline.md`), and on explicit confirm
  append it under a `## Review discipline` heading. Idempotent — if a `Review discipline`
  heading already exists in the project's `CLAUDE.md`, report that and change nothing.
- **Authorize the spine's courier transport (project-level allow-rules)** — offered when the
  owner reports runtime-classifier blocks on showrunner runs (issue #255 class: courier
  dispatches denied as suspected oversight-evasion). Project-scoped, never user-wide; the
  target follows the storage mode — **in-repo** → `.claude/settings.json` (committed,
  team-shared; rules embed this checkout's absolute paths, collaborators re-run this offer),
  **out-of-repo** → `.claude/settings.local.json` (machine-local, git-ignored, zero committed
  traces). Owner-gated like every write: show the exact rules first (`emit`), and on explicit
  confirm apply them (idempotent merge; never clobbers unrelated settings):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 "$ROOT_DIR/lib/courier_allow_rules.py" emit --root .
  # show the owner the rules; on their explicit confirm (mode per the storage mode above):
  python3 "$ROOT_DIR/lib/courier_allow_rules.py" apply --root . --mode local   # or --mode in-repo
  ```

  The rules stay scoped — rooted at this project, its managed worktrees, the plugin-cache lib
  path, or the spine's own `__SR_EOF__` write marker; never blanket verb grants. The enforcer
  hooks still deny gated verbs (merge/release/force-push) regardless of any allow rule. When
  the CLI creates `settings.local.json` fresh, confirm it is git-ignored (Claude Code only
  auto-ignores the file when it creates it itself).
- **Switch the storage mode** → the confirmed switch below.
- **Change the per-role engine** (reviewer engine / implementation engine / plan-author engine) → the
  engine step in `reference/set-up.md` §4.5 (availability → preference → show-authorization →
  test-dispatch), writing `enginePreferences` through `core_md` (keys `reviewer`, `implementation`,
  `planAuthor`). Set a role back to `claude` (or clear it) to fall fully open. `planAuthor` routes ONLY
  the showrunner's plan-author leaf; tasks authoring always runs native.
- **Change the per-role model tier** (orchestrator/reviewer/reviewer-deep/mechanical/synthesis/fixer/
  author/author-plan) → show the effective map first, then write only the `## Model tiers` block in the
  resolved review-crew profile. This is an optional tune action: if the owner declines, change nothing.
  `author-plan` is a split role: unset, it resolves exactly as `author`; set (e.g. `author-plan: fable`,
  only on explicit owner ask) it moves plan authoring alone. Fable-via-Cursor plan authoring = both
  `author-plan: fable` and `planAuthor: cursor` (the cursor adapter maps the tier to its own fable
  model id).

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 "$ROOT_DIR/lib/model_tier_overrides.py" show
  ```

  To set overrides (including `fable`, but only when the owner explicitly asks for it) or clear
  overrides back to `DEFAULT_TIERS`, run the helper; it creates the block if absent, replaces it if
  present, and preserves every other profile section:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 "$ROOT_DIR/lib/model_tier_overrides.py" write --set reviewer=fable --clear fixer
  ```

  Role names are validated against `KNOWN_ROLES`; unknown roles are dropped with a warning. Unknown
  model strings warn but do not fail, so newly available model names can be deliberately configured
  before the plugin ships a new allowlist.

## 3 — Switch the storage mode (FR-10), always showing what will move

The switch is the only destructive action — always show **exactly what will move** and require an
explicit confirm before doing anything. First preview, then (on confirm) execute:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/mode_migrate.py" preview --cwd . --target <in-repo|global>
# present the calibration + definition documents it lists, and the collaborator-visibility note;
# on the owner's explicit confirm:
python3 "$ROOT_DIR/lib/mode_migrate.py" execute --cwd . --target <in-repo|global>
```

- **What moves:** the full calibration (the shared core, every hero layer, the pinned patterns) and
  **every definition document**. A switch into the repo newly publishes all of it to collaborators —
  say so. Machine-local bookkeeping (the mode record, in-progress run state) is updated in place, not
  relocated.
- **In-flight work (UFR-3):** if a piece of work is mid-flight (its documents would move underneath
  it), warn the owner — naming the work and what could break — and proceed only on an explicit
  confirm. Check with `configure_route.work_in_flight('.')`. This is a strong warning, not a hard block.
- **Switch to the mode already in effect (FR-11):** reported as already in that mode; no change.
- **Destination unwritable (UFR-6):** an `execute` result of `blocked` means the destination could
  not be written — report exactly what it needs; the project stays in its prior mode with nothing
  removed from the source.
- **Interrupted switch:** finished or backed out automatically by the Step-1 `recover` on the next
  run (UFR-1) — every file ends up in exactly one location.
