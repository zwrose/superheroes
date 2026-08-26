# Contents

- Render the combined view
- The tune menu
- Switch the storage mode

# configure — view & tune path

Reached from `configure` when a project is configured and healthy (FR-1). Renders the whole
calibration on one screen and offers a small menu of targeted changes. A view-only run on an
up-to-date project changes nothing (FR-12).

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

Gate write-downs on this path are written down in the run output and are never written into a
hero layer — their payloads carry machine-local absolute paths that must not reach a collaborator-visible in-repo file, and `write-layer` replaces a layer wholesale.

## 1 — Render the combined view (FR-4) + drift notice (FR-7)

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import configure_view
print(configure_view.render('.'))"
```

One plain-text screen, top to bottom: the project's core facts (including the **Show-it surface**
declaration when present), the **Dispatch calibration** (the
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
- **Tune the guardian calibration** → read the existing `guardian.md` layer first, change the
  knob you want inside the `guardian-config` JSON fence, and submit the **complete** body (the
  whole fence with every sibling knob preserved) through `core_md.py write-layer --hero guardian`
  (owner confirms the body on stdin). `write-layer` replaces the entire layer file — a partial
  fence silently drops every other guardian knob (thresholds, cadence, coverage, vitals,
  `reportCard`, …) and the next sweep still reads `configStatus: healthy`. The fence shape is in
  `skills/guardian/reference/calibration.md`.
- **Set up a hero skipped at set-up** (FR-6) → list every optional hero not yet set up and not
  previously declined, and offer to run each one's set-up from here. Get the list from the lib —
  never guess which heroes apply:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 -B "$ROOT_DIR/lib/hero_setup.py" offerable --cwd .
  ```

  This is the mandatory/optional split: a missing **review-crew** layer is an incomplete set-up the
  route already sends to `fix`; optional heroes (test-pilot, guardian) surface here as an offer
  rather than forcing a repair. A hero the owner declines (here or at set-up) is recorded so it is not
  re-offered. The combined view renders each hero layer — including guardian — under
  `## Layer: <hero>`.
- **Sweep orphaned per-project stores** → when the view's `storage health` line reports orphaned
  or unknown-provenance stores:

<!-- decision-point: id=configure-tune-orphan-store-sweep mode=gate kind=owner-gate default="report only — no sweep without current-turn owner authorization" carrier=run-output -->

  Always run the read-only report first. GATE: write the counts and orphan list down in the run
  output, and hand back — do **not** run `store_sweep.py sweep` on the default path.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 -B "$ROOT_DIR/lib/store_sweep.py" report
  ```

  `sweep` deletes only provenance-orphaned stores (recorded source path gone, no real content) —
  never stores with content or a live source path. `unknown` stores (pre-provenance, no content)
  are kept unless the owner explicitly opts in with `--include-unknown`. Any classification doubt
  reads as real and is kept.

  **Only when the owner authorizes deletion in this turn** — not the default path — run:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 -B "$ROOT_DIR/lib/store_sweep.py" sweep
  ```

  Follow-up: `/superheroes:configure`.

<!-- /decision-point: id=configure-tune-orphan-store-sweep -->

- **Write the review-discipline section into the project's `CLAUDE.md`** — offered ONLY when
  the storage mode is **in-repo** (out-of-repo mode exists to keep the repo free of superheroes
  traces; there the SessionStart bootstrap note is the sole carrier). Owner-gated like every
  write: show the section text (source of truth:
  `$ROOT_DIR/rubric/review-discipline.md`), and on explicit confirm
  append it under a `## Review discipline` heading. Idempotent — if a `Review discipline`
  heading already exists in the project's `CLAUDE.md`, report that and change nothing.
- **Flip the storage mode** → the confirmed flip below.
- **Change the per-role engine** (reviewer / implementer / brief-check / pilot) → the engine step in
  `skills/configure/reference/set-up.md` §4.5 (availability → preference → show-authorization → test-dispatch),
  writing `enginePreferences` through `core_md` (keys `reviewer`, `implementation`, `briefCheck`,
  `pilot`). Set a role back to `claude` (or clear it) to fall fully open — **except `briefCheck`**,
  which falls open to **codex** (the cross-vendor default; a Claude brief-check is a disclosed
  degradation running at opus, one tier up from the implementer).
- **Change the per-role model tier** (reviewer/reviewer-deep/verifier/mechanical/synthesis/code-fixer/doc-reviser/
  implementer/pilot) → show the effective map first, then write only the `## Model tiers` block in
  the resolved review-crew profile. This is an optional tune action: if the owner declines, change
  nothing.
- **Change the builder-dispatch tier** — which Claude tier a headless builder session launches on.
  Unconfigured resolves to `opus`; an unreadable or structurally ambiguous profile also resolves to
  `opus` (fail-closed), never an inherited session tier. `fable` is **refused** — it is a
  judgment-seat tier, never a launch default.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' 'sonnet' | python3 -B "$ROOT_DIR/lib/core_md.py" write-builder-tier --cwd .
  ```

  To clear (empty stdin returns the project to the `opus` default):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '' | python3 -B "$ROOT_DIR/lib/core_md.py" write-builder-tier --cwd .
  ```

  **Read the result, don't assume success.** `write-builder-tier` returns `{action, reason?}`.
  Only `written` or `noop` means the builder-dispatch tier was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

  ```json
  {
    "enginePreferences": {
      "builderDispatchTier": "sonnet"
    }
  }
  ```

- **Declare or change the Show-it surface** → persist **only** the `## Show-it surface`
  section in `core.md`, leaving every other section untouched. Clearing it (empty stdin)
  returns the project to `none`:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '<Level/What-the-owner-does/Notes prose>' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
  ```

  To clear:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '' | python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
  ```

  **Read the result, don't assume success.** `write-show-it` returns `{action, reason?}`.
  Only `written` or `noop` means the Show-it declaration was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

- **Pin a concrete Codex model for one role** → keep the provider-neutral `## Model tiers` block
  unchanged and write the pin under `core.md`'s `enginePreferences.codexModels`. Valid role keys are
  `reviewer`, `reviewer-deep`, `code-fixer`, `implementer`, and `pilot`; valid
  model IDs are `gpt-5.6-terra` and `gpt-5.6-sol`. Codex tier map:
  haiku=gpt-5.6-terra, sonnet=gpt-5.6-terra, opus=gpt-5.6-sol.
  Show the current engine preferences and
  effective model first, merge only the requested role into the existing object, and preserve every
  sibling key. Before writing, validate the selected model/effort with
  `engine_pref.valid_codex_model_effort`; reject an invalid (model, effort) pair and leave the prior
  valid config unchanged. `max` is owner opt-in only — never proposed as a default.

  ```json
  {
    "enginePreferences": {
      "reviewer": "codex",
      "implementation": "codex",
      "briefCheck": "codex",
      "effort": {"review": "high"},
      "codexModels": {"reviewer": "gpt-5.6-terra"}
    }
  }
  ```

  A Codex pin applies only while that role's engine is `codex`; switching the role to Claude or
  Cursor ignores it. Per-run preflight model overrides have highest precedence, followed by this
  persistent pin, then the shared-tier GPT-5.6 mapping.

- **`enginePreferences.effort`** — a `{role_kind: effort_token}` map under `core.md`'s
  `enginePreferences` block. Valid role-kind keys are `review`, `review-deep`, `build`, `fix`,
  `brief-check`, and `pilot` (role **kinds**, not dispatch role names — `build`, never
  `implementation`). This map governs **Codex model-pin validation** (`engine_pref.normalize_codex_pin_map`
  calls `resolve_effort` to decide whether a pinned model + effort pair is valid) and **configure
  display** only — it does **not** set the effort a dispatch actually runs at. Dispatch effort comes
  from the registry or a per-seat pin (`enginePreferences.seatPins`), resolved through
  `dispatch_guard` / `seat_map`; use the per-role engine and model-tier tune actions above for
  those knobs.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '{"reviewer": "gpt-5.6-terra"}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-engine-pins --key codexModels --cwd .
  ```

  Clearing is per-entry: pass `null` for each role you want removed; when the last entry is
  removed the whole `codexModels` key is dropped from the block. An empty object (`{}`) clears
  nothing — it is never a clear-all. It usually returns `noop` with the file untouched, but it
  can return `written` when the block was already degenerate (a present-but-empty or mistyped pin
  map, or a missing `enginePreferences` block), in which case the write only normalizes structure
  and still removes no pins. A returned `written` therefore does not mean pins were cleared, and a
  returned `noop` does not mean a clear-all succeeded.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '{"reviewer": null}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-engine-pins --key codexModels --cwd .
  ```

  **Read the result, don't assume success.** `write-engine-pins` returns `{action, reason?}`.
  Only `written` or `noop` means the pin map was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 -B "$ROOT_DIR/lib/model_tier_overrides.py" show
  ```

  To set overrides (including `fable` only when the role's engine is `claude` — `fable` is
  anthropic-native and is **refused** with `fable-on-external-engine` when that role routes to
  codex or cursor; the same command also **refuses** with `core-md-unreadable` when the project's
  `core.md` exists but cannot be read — the tier is not saved and the refusal names the file, so it
  is a broken-config signal, not a rejected tier) or clear overrides back to `DEFAULT_TIERS`, run the helper; it creates the
  block if absent, replaces it if present, and preserves every other profile section. `fixer` is
  accepted as a legacy alias for `code-fixer` (read, write, and clear):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  python3 -B "$ROOT_DIR/lib/model_tier_overrides.py" write --set reviewer=sonnet --clear code-fixer
  ```

  Role names are validated against `KNOWN_ROLES`; unknown roles are dropped with a warning. Unknown
  model strings warn but do not fail, so newly available model names can be deliberately configured
  before the plugin ships a new allowlist.

- **Pin a review-panel seat to a vendor/model** → write the pin under `core.md`'s
  `enginePreferences.seatPins`. Valid seat keys are `architecture-reviewer`, `code-reviewer`,
  `security-reviewer`, `test-reviewer`, `premortem-reviewer`, and `grounding-seat`; each pin is
  `{vendor, model?, effort?}` — a present `model` or `effort` must be a non-empty string or the whole
  pin is rejected into `invalidSeatPins` (an absent optional field is fine; a vendor-only pin uses the
  seat's default model). It feeds the review-code panel's `seat_map compose --pins`; a pin the
  account/registry **cannot honor** (unknown seat, offline vendor, disallowed model, or a
  grounding/strong-seat independence break) **stays loud** — the shipped seat-map machinery
  (#510/#603) emits a `pin` / `pin-not-honorable` / `pin-breaks-constraint` degradation into the
  review receipt and the seat falls back to rotation. The loader does structural validation only; a
  structurally-broken entry is surfaced as `invalidSeatPins` in `configure view`. Show the current
  engine preferences and effective seat map context first, merge only the requested seat into the
  existing `seatPins` object, and preserve every sibling key.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '{"security-reviewer": {"vendor": "claude"}}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-engine-pins --key seatPins --cwd .
  ```

  Clearing is per-entry: pass `null` for each seat you want removed; when the last entry is
  removed the whole `seatPins` key is dropped from the block. An empty object (`{}`) clears
  nothing — it is never a clear-all. It usually returns `noop` with the file untouched, but it
  can return `written` when the block was already degenerate (a present-but-empty or mistyped pin
  map, or a missing `enginePreferences` block), in which case the write only normalizes structure
  and still removes no seats. A returned `written` therefore does not mean seats were cleared, and a
  returned `noop` does not mean a clear-all succeeded.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '{"security-reviewer": null}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-engine-pins --key seatPins --cwd .
  ```

  **Read the result, don't assume success.** `write-engine-pins` returns `{action, reason?}`.
  Only `written` or `noop` means the pin map was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

  ```json
  {
    "enginePreferences": {
      "seatPins": {
        "security-reviewer": {"vendor": "claude"},
        "code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"}
      }
    }
  }
  ```

- **Pre-authorize owner-judgment review gates** → write a narrow `gate-policy/1` overlay under
  `core.md`'s `reviewGatePolicy` key (a sibling of `enginePreferences`, not inside it). The
  shipped default pre-authorizes nothing — every rule added here is a narrow pre-authorization of
  a gate the driver would otherwise park on. Show the resolved policy layers and rule counts
  first, then merge only the requested overlay document. Pass `null` (or empty stdin) to remove
  the overlay and return to shipped-defaults-only.

<!-- decision-point: id=configure-tune-gate-policy mode=proceed kind=owner-gate default="retain shipped-defaults-only gate policy overlay" carrier=run-output -->

  PROCEED: retain the shipped-defaults-only overlay unless the owner selects this tune action in
  this turn, record in the run output that the shipped-defaults-only gate-policy overlay was
  retained and that `/superheroes:configure` changes it, and continue. Follow-up:
  `/superheroes:configure`.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf '%s\n' '{"schema":"gate-policy/1","default":"park","rules":[{"gate":"present-judgment","findingClass":"judgment:important","disposition":"skip"}]}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-review-gate-policy --cwd .
  ```

  To clear the overlay:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
  printf 'null\n' | python3 -B "$ROOT_DIR/lib/core_md.py" write-review-gate-policy --cwd .
  ```

  **Read the result, don't assume success.** `write-review-gate-policy` returns
  `{action, reason?}`. Only `written` or `noop` means the overlay was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command exits 0
  either way, so check `action`, not exit status.

<!-- /decision-point: id=configure-tune-gate-policy -->

## 3 — Flip the storage mode (FR-10), always showing what will move

<!-- decision-point: id=configure-tune-storage-flip mode=gate kind=owner-gate default="preview only — no execute without current-turn owner authorization" carrier=run-output -->

The flip is the only destructive action — always show **exactly what will move**. GATE: run
preview only, write the exact move list down in the run output, and hand back — do **not** run
`execute` on the default path.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/mode_migrate.py" preview --cwd . --target <in-repo|global>
```

Present the calibration + definition documents + work-item records the preview lists, and the
collaborator-visibility note.

**Only when the owner authorizes the migration in this turn** — invoking configure is not itself
the authorization — run:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/mode_migrate.py" execute --cwd . --target <in-repo|global> --owner-authorized true
```

Pass `--owner-authorized true` **only** when the owner confirmed the migration in the current turn.
A run with no such authorization passes nothing — `execute` reports the blocked result as-is.

Follow-up: `/superheroes:configure`.

<!-- /decision-point: id=configure-tune-storage-flip -->

- **What moves:** the full calibration (the shared core, every hero layer, the pinned patterns),
  **every definition document**, and **every other work-item record** the preview lists under
  `workItemRecords` — a discovery's findings record is one, and it moves with its folder without
  being a definition document. A flip into the repo newly publishes all of it to collaborators —
  say so. Machine-local bookkeeping (the mode record, in-progress run state) is updated in place, not
  relocated.
- **In-flight work (UFR-3):** if a piece of work is mid-flight (its documents would move underneath
  it), warn the owner — naming the work and what could break — and proceed only on an explicit
  confirm. v2 has no machine-readable in-flight signal (the spine's lease store was retired with the
  execution spine, #478), so `configure_route.work_in_flight('.')` always reports no known in-flight
  work — rely on your own judgment about what's mid-flight before flipping. This is a strong
  warning, not a hard block.
- **Switch to the mode already in effect (FR-11):** reported as already in that mode; no change.
- **Destination unwritable (UFR-6):** an `execute` result of `blocked` means the destination could
  not be written — report exactly what it needs; the project stays in its prior mode with nothing
  removed from the source.
- **Interrupted flip:** finished or backed out automatically by the Step-1 `recover` on the next
  run (UFR-1) — every file ends up in exactly one location.
