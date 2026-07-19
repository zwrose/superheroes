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

One plain-text screen, top to bottom: the project's core facts, the **Dispatch calibration** (the
effective engine + model for every v2 dispatch role) and its Codex model-pin detail, each hero's
layer, the pinned patterns, and the **Model tiers** block — "here is everything superheroes knows
about this project," not a list of files. Any current staleness/drift is shown as a **single,
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
- **Write the review-discipline section into the project's `CLAUDE.md`** — offered ONLY when
  the storage mode is **in-repo** (out-of-repo mode exists to keep the repo free of superheroes
  traces; there the SessionStart bootstrap note is the sole carrier). Owner-gated like every
  write: show the section text (source of truth:
  `$ROOT_DIR/rubric/review-discipline.md`), and on explicit confirm
  append it under a `## Review discipline` heading. Idempotent — if a `Review discipline`
  heading already exists in the project's `CLAUDE.md`, report that and change nothing.
- **Switch the storage mode** → the confirmed switch below.
- **Change the per-role engine** (reviewer / implementer / brief-check / pilot) → the engine step in
  `reference/set-up.md` §4.5 (availability → preference → show-authorization → test-dispatch),
  writing `enginePreferences` through `core_md` (keys `reviewer`, `implementation`, `briefCheck`,
  `pilot`). Set a role back to `claude` (or clear it) to fall fully open — **except `briefCheck`**,
  which falls open to **codex** (the cross-vendor default; a Claude brief-check is a disclosed
  degradation running at opus, one tier up from the implementer).
- **Change the per-role model tier** (reviewer/reviewer-deep/mechanical/synthesis/fixer/pr-body/
  implementer/pilot) → show the effective map first, then write only the `## Model tiers` block in
  the resolved review-crew profile. This is an optional tune action: if the owner declines, change
  nothing.

- **Pin a concrete Codex model for one role** → keep the provider-neutral `## Model tiers` block
  unchanged and write the pin under `core.md`'s `enginePreferences.codexModels`. Valid role keys are
  `reviewer`, `reviewer-deep`, `fixer`, `implementer`, and `pilot`; valid
  model IDs are `gpt-5.5`,
  `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna`. Codex tier map:
  haiku=gpt-5.6-luna, sonnet=gpt-5.6-terra, opus=gpt-5.6-sol, fable=gpt-5.6-sol.
  Show the current engine preferences and
  effective model first, merge only the requested role into the existing object, and preserve every
  sibling key. Before writing, validate the selected model/effort with
  `engine_pref.valid_codex_model_effort`; reject `gpt-5.5` + `max` and leave the prior valid config
  unchanged. `max` is never proposed as a default — it is owner opt-in only.

  ```json
  {
    "enginePreferences": {
      "reviewer": "codex",
      "implementation": "codex",
      "briefCheck": "codex",
      "effort": {"review": "high"},
      "codexModels": {"reviewer": "gpt-5.5"}
    }
  }
  ```

  A Codex pin applies only while that role's engine is `codex`; switching the role to Claude or
  Cursor ignores it. Per-run preflight model overrides have highest precedence, followed by this
  persistent pin, then the shared-tier GPT-5.6 mapping.

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
  confirm. v2 has no machine-readable in-flight signal (the spine's lease store was retired with the
  execution spine, #478), so `configure_route.work_in_flight('.')` always reports no known in-flight
  work — rely on your own judgment about what's mid-flight before switching. This is a strong
  warning, not a hard block.
- **Switch to the mode already in effect (FR-11):** reported as already in that mode; no change.
- **Destination unwritable (UFR-6):** an `execute` result of `blocked` means the destination could
  not be written — report exactly what it needs; the project stays in its prior mode with nothing
  removed from the source.
- **Interrupted switch:** finished or backed out automatically by the Step-1 `recover` on the next
  run (UFR-1) — every file ends up in exactly one location.
