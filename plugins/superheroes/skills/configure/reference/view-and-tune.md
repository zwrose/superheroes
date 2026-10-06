# Contents

- Render the combined view
- The tune menu
- Switch the storage mode

# configure — view & tune path

Reached from `configure` when a project is configured and healthy. Renders the whole
calibration on one screen and offers a small menu of targeted changes. A view-only run on an
up-to-date project changes nothing.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"` is assigned once per bash block below.

Gate write-downs on this path are written down in the run output and are never written into a
hero layer — their payloads carry machine-local absolute paths that must not reach a collaborator-visible in-repo file, and `write-layer` replaces a layer wholesale.

## 1 — Render the combined view + drift notice

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B -c "
import sys; sys.path.insert(0,'$ROOT_DIR/lib'); import configure_view
print(configure_view.render('.'))"
```

One plain-text screen, top to bottom: the project's core facts (including the **Show-it surface**
declaration when present and the declared **Vet checks** block with any malformed or unreadable
calibration flagged), the **Sandbox access** block (`all off (offline)` when nothing is set, with any
malformed or unreadable value flagged), the **Size count exclusions** block (the declared path globs,
`(none — …)` when nothing is declared, with any malformed or unreadable value flagged), the
**Dispatch calibration** (the
effective engine + model for every v2 dispatch role) and its Codex model-pin detail, each hero's
layer, the pinned patterns, and the **Model tiers** block — "here is everything superheroes knows
about this project," not a list of files. Any current staleness/drift is shown as a **single,
dismissible reminder on every run** (whether or not it was dismissed before); the owner can act on
it or dismiss it again for that run. Rendering is read-only — it never confirms a provisional
calibration.

The view also shows the **Spec reviewer seat** block, and lists configuration item 14 right after
item 10.

## 2 — The tune menu

Present, inline beneath the view, the things the owner can change — each routed to the **smallest**
action that owns it, leaving the rest of the calibration untouched:

- **Change the verify command** → there is no write verb for it: edit `verifyCommand` in the
  calibration file's `superheroes-core` json block directly (a non-empty string, or `null` for
  none), then run the view again and confirm it reads back. A wrong-typed, empty, or
  whitespace-only value is refused by name (`verify-command-malformed`) on every read until fixed.
  Set it to the fast iteration check (lint, types, the touched tests), not the full gate; set-up § 3
  says why.
- **Change the threat model** → `core_md.write_threat_model`, which replaces only that section.
- **Change one project-configuration item** → write only that item's home through `project_config`.
  Show the current value from the view first, then pipe the new value on stdin. A refusal is
  reported to the owner and never worked around.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '"gh-stack"' | python3 -B "$ROOT_DIR/lib/project_config.py" set --item stackingTool --cwd .
  ```

  **Read the result, don't assume success.** `set` returns `{action, reason?}`. Only `written` or
  `noop` means the item was saved — surface any other `action` (`refused`, `deferred`, `behind`)
  to the owner with its `reason`; the command exits 0 either way, so check `action`, not exit
  status.
- **Set who it's for and what it's for (item 14)** → write only item 14, with the answer as a JSON
  string on stdin. The command touches no other item.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/project_config.py" set --item whoItsFor --cwd . <<'SUPERHEROES_ANSWER'
  <the answer as a one-line JSON string>
  SUPERHEROES_ANSWER
  ```

  The answer is free text, so it goes in through a quoted here-document, never inside shell single
  quotes: an apostrophe would break the command and a `$(...)` would run. Write the JSON on one
  line, flush left, with no indent before the closing `SUPERHEROES_ANSWER` line. Read the result
  the same way as the `stackingTool` write above: only `written` or `noop` means it was saved.

- **Item 13 after the move into Canon** → once item 13 points to Canon, it holds no value of its
  own, and `set --item materialConsequenceLine` is refused with `material-line-in-canon`. Record a
  new example of what counts as a material consequence in Canon as a standing ruling, by
  [Canon's contract](../../../rubric/canon-contract.md). Before the move, set item 13 as before.
- **Move item 13 into Canon** → run the move from the branch it should ride when Canon lives in the
  repository. The command commits only Canon's files there. When Canon lives in the project store,
  the command commits in the store. Pass `--session <this session's id>` to record the session.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/project_config.py" migrate-material-line --cwd .
  ```

  Once the first step has run, item 13's examples cannot change until the move finishes. Finish
  the move first, then record any change in Canon as a new ruling.

  Each paragraph of the item-13 value becomes one standing ruling. Each ruling is marked as migrated
  from configure item 13 on that date, with its original session and time unknown. Then item 13
  points to Canon. The result's `action` is `migrated`, `already-adopted`, `pending-default-branch`,
  or `refused` with a `reason`. Only `migrated` and `already-adopted` mean done.
  `pending-default-branch` is the first of two steps. When Canon lives in the repository, the move
  always finishes in two steps, wherever the project's calibration lives, unless the default branch
  already holds every ruling. The
  entries are committed on this branch, and item 13 keeps its value so other branches still see the
  examples. Land the branch, then run the move again. That second run commits nothing new and
  writes the pointer. A repository with no origin default branch stays
  pending until it has one holding the entries. When Canon lives in the project store, there is one
  shared copy and the move finishes in one step. Report a `refused` result to the owner with its
  `reason`, and never work around it. Nine reasons are ones the owner can act on:
  - `canon-dirty`: commit or discard local edits to `canon.md`, then run the move again.
  - `canon-git-root-not-a-repo`: run configure's set-up for the project store.
  - `material-line-changed-during-migration`: item 13 changed while it was moving, so run the move
    again.
  - `canon-default-probe-failed`: the default branch could not be read, so fetch and retry.
  - `canon-lock-contended`: another configure change was saving at the same moment, so run the move
    again.
  - `canon-write-failed`: a file could not be written — fix the permission or disk space, then run
    the move again. The move puts Canon back as it was, so the retry starts clean.
  - `canon-id-conflict`: Canon holds migrated entries that share one id but carry different
    rulings, so the move leaves item 13 as it is. Report the detail to the owner; the duplicate is
    theirs to settle.
  - `profile-structurally-ambiguous`: the project's calibration file is ambiguous (a repeated key or
    two calibration blocks); fix it through configure's fix path, then run the move again.
  - `material-line-changed-since-migration`: item 13 changed after an earlier run of the move
    recorded these entries. Set item 13 back to exactly the text the detail lists, finish the
    move, then record any change in Canon as a new ruling. An emptied item 13 meets the same
    refusal while those entries stand.

  The other reasons are `profile-absent`, `profile-unparseable`, `behind`, `malformed-value`,
  `session-id-malformed`, `date-malformed`, `canon-lookup-refused`, `canon-commit-failed`, and
  `marker-write-failed`. Report the `reason` and the `detail` as they stand.
- **Set or clear the spec-reviewer seat** → write the engine that reviews specs. Empty stdin clears
  it.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' 'codex' | python3 -B "$ROOT_DIR/lib/core_md.py" write-spec-reviewer --cwd .
  ```

  The seat names an engine only, never a model, and is separate from the review-panel seats. What
  the spec checks do while it is unset is the `## Spec reviewer seat` block of the rendered view
  (`lib/configure_view.py` owns that wording) — point the owner at that block rather than
  restating it. Read the result, don't assume success: `write-spec-reviewer` returns `{action,
  reason?}` and exits 0 either way, so only `written` or `noop` means the seat was saved. Surface
  `refused` (`spec-reviewer-unknown-engine` names a value that is not `claude`, `codex`, or
  `cursor`; `spec-reviewer-round-trip-refused`), `deferred` (`lock-contended`, `store-unwritable`,
  `spec-reviewer-write-failed`, `repo-root-unavailable`, `spec-reviewer-cli-failed`), and `behind`
  (`core-schema-behind`) to the
  owner with the `reason`.
- **Re-calibrate a prose-heavy hero layer** → re-run that hero's own (now-internal) calibration.
- **Tune the guardian calibration** → read the existing `guardian.md` layer first, change the
  knob you want inside the `guardian-config` JSON fence, and submit the **complete** body (the
  whole fence with every sibling knob preserved) through `core_md.py write-layer --hero guardian`
  (owner confirms the body on stdin). `write-layer` replaces the entire layer file — a partial
  fence silently drops every other guardian knob (thresholds, cadence, coverage, vitals,
  `reportCard`, …) and the next sweep still reads `configStatus: healthy`. The fence shape is in
  `skills/guardian/reference/calibration.md`.
- **Set up a hero skipped at set-up** → list every optional hero not yet set up and not
  previously declined, and offer to run each one's set-up from here. Get the list from the lib —
  never guess which heroes apply:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/store_sweep.py" report
  ```

  `sweep` deletes only provenance-orphaned stores (recorded source path gone, no real content) —
  never stores with content or a live source path. `unknown` stores (pre-provenance, no content)
  are kept unless the owner explicitly opts in with `--include-unknown`. Any classification doubt
  reads as real and is kept.

  **Only when the owner authorizes deletion in this turn** — not the default path — run:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  which falls open to **codex** (the cross-vendor default; a brief-check on the host model is a disclosed
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' 'sonnet' | python3 -B "$ROOT_DIR/lib/core_md.py" write-builder-tier --cwd .
  ```

  To clear (empty stdin returns the project to the `opus` default):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '<Level/What-the-owner-does/Notes prose>' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
  ```

  To clear:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '' | python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
  ```

  **Read the result, don't assume success.** `write-show-it` returns `{action, reason?}`.
  Only `written` or `noop` means the Show-it declaration was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

- **Declare or change the project's vet checks** → write **only** the `vetChecks` key in `core.md`'s
  JSON block, leaving every other key untouched. Stdin carries a JSON list; empty stdin is refused
  (use `--clear` to remove the key):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '[{"name":"Example check","evidence":"PR body · Build record","records":"what was read and what the vet recorded"}]' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-vet-checks --cwd .
  ```

  To clear:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/core_md.py" write-vet-checks --cwd . --clear
  ```

  **Read the result, don't assume success.** `write-vet-checks` returns `{action, reason?,
  malformed?}`. Only `written` or `noop` means the list was saved — surface any other `action`
  (`refused`, `deferred`, `behind`) to the owner with its `reason`; refusal `vet-checks-malformed`
  carries `malformed` for the owner to fix. Refusal reasons also include `vet-checks-input-unparseable`,
  `duplicate-core-key:<key>`, `core-md-absent`, `core-md-unparseable`, and
  `vet-checks-round-trip-refused`. The command exits 0 either way, so check `action`, not exit
  status. List shape: `skills/showrunner/reference/vet-receipt.md` § Project vet checks.

- **Open sandbox access for the claude implementer** → write **only** the `sandboxAccess` key in
  `core.md`'s JSON block, leaving every other key untouched. Every field is optional and a missing
  field is off. `allowedDomains` lets sandboxed commands reach those hosts; `localPorts` allows
  listening and connecting on loopback, including a bind on 0.0.0.0; `localSockets` allows
  Unix-domain sockets in the sandbox's per-user temp dir; `extraWritePaths` adds writable paths, and
  the deny list (the git hooks, the git config files, the worktree identity files) still wins over
  any extra path. Writes under `/tmp` and localhost binding (macOS) are already on by default for
  every project, so `localPorts` is redundant on macOS; elsewhere it is still refused with
  `sandbox-access-unsupported-platform`. The Claude Code setting each one maps to is in
  `skills/workhorse/reference/dispatch-mechanics.md` § The claude write sandbox.
  Show the current value from the view's **Sandbox access** block first. Stdin carries a JSON
  object; empty stdin is refused (use `--clear` to remove the key):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '{"allowedDomains":["pypi.org"],"localPorts":true,"localSockets":true,"extraWritePaths":["/Users/me/Library/Caches/ms-playwright"]}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-sandbox-access --cwd .
  ```

  To clear:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/core_md.py" write-sandbox-access --cwd . --clear
  ```

  To read the saved value:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/core_md.py" sandbox-access --cwd .
  ```

  **Read the result, don't assume success.** `write-sandbox-access` returns `{action, reason?,
  malformed?}`. Only `written` or `noop` means the object was saved — surface any other `action`
  (`refused`, `deferred`, `behind`) to the owner with its `reason`; refusal `sandbox-access-malformed`
  carries `malformed` for the owner to fix, each item naming its field, its reason, and the accepted
  shape. Refusal reasons also include `sandbox-access-input-unparseable`, `duplicate-core-key:<key>`,
  `core-md-absent`, `core-md-unparseable`, and `sandbox-access-round-trip-refused`. The command exits
  0 either way, so check `action`, not exit status. A claude write run reads the value once when it
  opens, so a run already open keeps the access it opened with and an edit applies to the next run.
  A malformed saved value refuses the next claude write open with
  `engine-config:sandbox-access-malformed`.

- **Leave paths out of the size count** → write **only** the `sizeExclude` key in `core.md`'s JSON
  block, leaving every other key untouched. The value is a JSON list of repo-relative path globs,
  such as `["docs/**", "*.generated.ts"]`. A glob is matched with Python `fnmatch`, case-sensitive,
  against the repo-relative path, and `*` also crosses `/`. A matched path is left out of both size
  counts and is listed with its line counts. Lockfiles are always left out without any setting. A
  project that wants test-pilot plans left out lists `.claude/test-pilot/**` itself. An absolute
  glob (a leading `/`) can never match a repo-relative path and is refused; `[]` declares that
  nothing extra is excluded. Show the current value from the view's **Size count exclusions** block
  first. Stdin carries a JSON list; empty stdin is refused (use `--clear` to remove the key):

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '["docs/**","*.generated.ts"]' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-size-exclude --cwd .
  ```

  To clear:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/core_md.py" write-size-exclude --cwd . --clear
  ```

  To read the saved value:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  python3 -B "$ROOT_DIR/lib/core_md.py" size-exclude --cwd .
  ```

  **Read the result, don't assume success.** `write-size-exclude` returns `{action, reason?,
  malformed?}`. Only `written` or `noop` means the list was saved — surface any other `action`
  (`refused`, `deferred`, `behind`) to the owner with its `reason`; refusal `size-exclude-malformed`
  carries `malformed` for the owner to fix, each item naming its index, its reason
  (`size-exclude-not-a-list`, `size-exclude-entry-not-a-nonempty-string`, or
  `size-exclude-entry-absolute`), and the accepted shape. Refusal reasons also include
  `size-exclude-input-unparseable`, `duplicate-core-key:<key>`, `core-md-absent`,
  `core-md-unparseable`, and `size-exclude-round-trip-refused`. The command exits 0 either way, so
  check `action`, not exit status. The read verb never raises: a saved value that cannot be read
  comes back `globs` null with reason `size-exclude-unreadable` and a `detail`, and a malformed
  saved value comes back `size-exclude-malformed`.

- **Pin a concrete Codex model for one role** → keep the provider-neutral `## Model tiers` block
  unchanged and write the pin under `core.md`'s `enginePreferences.codexModels`. Valid role keys are
  `reviewer`, `reviewer-deep`, `code-fixer`, `implementer`, and `pilot`; valid
  model IDs are `gpt-6.1-sol`, `gpt-6-sol`, `gpt-5.6-sol`, and `gpt-6-astra` (eligible only for
  `reviewer-deep` at effort `high`; pinning it on any other role is refused
  `pin-role-not-eligible`). A pin to the retired `gpt-5.6-terra` is refused at write time
  (`model-retired`; `model_registry.retired_model_reason` names the text). A pin must
  also resolve on its role's own codex allowlist, else it is refused `pin-not-on-allowlist`
  (any model on `pilot`, which has no codex cell — it remains a valid role key
  but admits no codex model).
  Codex tier map: each Claude tier that has a codex peer runs the codex model that `model_registry.codex_peer_for_claude_tier` names (`lib/model_registry.py` is its one source; the configure readout shows the effective model per role), and `fable` has none; an unpinned project never
  dispatches Astra and gpt-6.1-sol is the default deep cell. A pinned model runs at the effort its role's
  registry allowlist resolves for it — gpt-6.1-sol, gpt-6-sol and gpt-5.6-sol at `high` on `reviewer`, `code-fixer`
  and `implementer` and `xhigh` on `reviewer-deep`, and Astra at `high` — the
  role's `enginePreferences.effort` setting is not
  consulted for a pinned model. Show the current engine preferences and effective model first, merge
  only the requested role into the existing object, and preserve every sibling key. Before writing,
  validate the selected model with `model_registry.codex_pin_verdict`; reject an invalid model
  and leave the prior valid config unchanged. `max` is owner opt-in only — never proposed as a
  default.

  ```json
  {
    "enginePreferences": {
      "reviewer": "codex",
      "implementation": "codex",
      "briefCheck": "codex",
      "effort": {"review": "high"},
      "codexModels": {"reviewer": "gpt-5.6-sol"}
    }
  }
  ```

  A Codex pin applies only while that role's engine is `codex`; switching the role to Claude or
  Cursor ignores it. For `reviewer` and `reviewer-deep`, the pin now reaches the review panel's
  codex seat — it no longer only changes the calibration readout; when the pinned cell is not live
  the seat falls back to the default cell with a `role-pin-not-live` degradation, and a pin the
  tier's allowlist does not admit falls back with `role-pin-not-honorable` carrying the refusal's
  reason. Per-run preflight model
  overrides have highest precedence, followed by this persistent pin, then the shared-tier codex
  mapping.

- **`enginePreferences.effort`** — a `{role_kind: effort_token}` map under `core.md`'s
  `enginePreferences` block. Valid role-kind keys are `review`, `review-deep`, `build`, `fix`,
  `brief-check`, and `pilot` (role **kinds**, not dispatch role names — `build`, never
  `implementation`). This map governs **configure display** and non-pin Codex effort resolution only
  — it does **not** set the effort a **pinned** model runs at (that comes from the model's own
  registry rung). Dispatch effort for unpinned roles comes from the registry or a per-seat pin
  (`enginePreferences.seatPins`), resolved through `dispatch_guard` / `seat_map`; use the per-role
  engine and model-tier tune actions above for those knobs.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '{"reviewer": "gpt-5.6-sol"}' | \
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '{"reviewer": null}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-engine-pins --key codexModels --cwd .
  ```

  **Read the result, don't assume success.** `write-engine-pins` returns `{action, reason?}`.
  Only `written` or `noop` means the pin map was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
  exits 0 either way, so check `action`, not exit status.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
  a gate the driver would otherwise park on. A `skip` (or stall `accept-the-disclosed-risk`) rule
  may carry a `followUp` `{item, revisitTrigger, classClosure}`; a new follow-up must include a
  nonblank `item`. A present but malformed `followUp` (missing or blank `item`, missing
  `revisitTrigger`, missing `classClosure`, wrong shape) is refused at overlay load and at
  calibration write and never reaches resolution; only an absent `followUp` lets the rule
  resolve and record the disposition, after which certification refuses it for the missing
  follow-up. A `followUp` may ride only a judgment `skip` or a stall
  `accept-the-disclosed-risk` rule; on any other disposition it is `layer-follow-up-not-allowed`.
  Show the resolved policy layers and rule counts first, then merge only the requested overlay
  document. Pass `null` (or empty stdin) to remove the overlay and return to shipped-defaults-only.

<!-- decision-point: id=configure-tune-gate-policy mode=proceed kind=owner-gate default="retain shipped-defaults-only gate policy overlay" carrier=run-output -->

  PROCEED: retain the shipped-defaults-only overlay unless the owner selects this tune action in
  this turn, record in the run output that the shipped-defaults-only gate-policy overlay was
  retained and that `/superheroes:configure` changes it, and continue. Follow-up:
  `/superheroes:configure`.

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf '%s\n' '{"schema":"gate-policy/1","default":"park","rules":[{"gate":"present-judgment","findingClass":"judgment:important","disposition":"skip"}]}' | \
    python3 -B "$ROOT_DIR/lib/core_md.py" write-review-gate-policy --cwd .
  ```

  To clear the overlay:

  ```bash
  ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
  printf 'null\n' | python3 -B "$ROOT_DIR/lib/core_md.py" write-review-gate-policy --cwd .
  ```

  **Read the result, don't assume success.** `write-review-gate-policy` returns
  `{action, reason?}`. Only `written` or `noop` means the overlay was saved — surface any other
  `action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command exits 0
  either way, so check `action`, not exit status.

<!-- /decision-point: id=configure-tune-gate-policy -->

## 3 — Flip the storage mode, always showing what will move

<!-- decision-point: id=configure-tune-storage-flip mode=gate kind=owner-gate default="preview only — no execute without current-turn owner authorization" carrier=run-output -->

The flip is the only destructive action — always show **exactly what will move**. GATE: run
preview only, write the exact move list down in the run output, and hand back — do **not** run
`execute` on the default path.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/mode_migrate.py" preview --cwd . --target <in-repo|global>
```

Present the calibration + definition documents + work-item records the preview lists, and the
collaborator-visibility note.

**Only when the owner authorizes the migration in this turn** — invoking configure is not itself
the authorization — run:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
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
- **In-flight work:** if a piece of work is mid-flight (its documents would move underneath
  it), warn the owner — naming the work and what could break — and proceed only on an explicit
  confirm. v2 has no machine-readable in-flight signal (the spine's lease store was retired with the
  execution spine, #478), so `configure_route.work_in_flight('.')` always reports no known in-flight
  work — rely on your own judgment about what's mid-flight before flipping. This is a strong
  warning, not a hard block.
- **Switch to the mode already in effect:** reported as already in that mode; no change.
- **Destination unwritable:** an `execute` result of `blocked` means the destination could
  not be written — report exactly what it needs; the project stays in its prior mode with nothing
  removed from the source.
- **Interrupted flip:** finished or backed out automatically by the Step-1 `recover` on the next
  run — every file ends up in exactly one location.
