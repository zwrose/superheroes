---
name: test-pilot-init
description: "Internal helper reached from `superheroes:configure` to refresh test-pilot's profile, seeding blocks, and browser tooling layer. Not a front door; owners run `superheroes:configure` instead."
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# test-pilot-init

Create or reconcile a project's **test-pilot profile** plus its starter
seeding blocks. Two modes: **create** (nothing resolves) and **reconcile**
(profile exists → re-detect, diff, migrate; NEVER silently overwrite).

## Step 1 — Resolve

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RES=$(python3 -B "$ROOT_DIR/lib/store.py" resolve) || RC=$?
RC=${RC:-0}
if printf '%s' "$RES" | jq -e '.refusal != null' >/dev/null 2>&1; then
  printf '%s' "$RES" | jq -r '"\(.refusal.reason): \(.refusal.detail)"' >&2
  exit 1
fi
if [ "$RC" -ne 0 ]; then
  echo "store.py resolve exited non-zero (exit $RC)" >&2
  exit "$RC"
fi
LOCATION=$(printf '%s' "$RES" | jq -r .location)
# FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
NUDGE_MSG=$(python3 -B "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
[ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
```

`location: none` → create mode (Steps 2–6). Otherwise → reconcile (Step 7).

## Step 2 — Detect (no questions the repo can answer)

Read `CLAUDE.md` first — the profile is an ADDER over it. Then detect:
stack/scripts (`package.json` scripts, `pyproject.toml`), dev command and
port, DB env vars (`.env*` files — names only, never read values into the
profile), docker-compose services, existing seed scripts, `git remote
get-url origin`.

<!-- decision-point: id=tp-init-uv mode=proceed kind=interview-step default="record uv absent; blocks limited to stdlib + run-command" carrier=test-pilot-layer -->
Check `uv` availability (`command -v uv`). When absent, record `uv` absent in
`## Setup disclosures` and state that blocks are limited to stdlib + run-command
designs — do not offer to install. When present, record `uv` available. Continue
detection. Follow-up: `/superheroes:configure`.
<!-- /decision-point: id=tp-init-uv -->

## Step 3 — Browser tooling gate

Use ToolSearch to check which browser MCPs are connected (search
"chrome-devtools", "Claude_in_Chrome", "playwright").

<!-- decision-point: id=tp-init-browser-tools mode=proceed kind=interview-step default="chrome-devtools, playwright, Claude_in_Chrome — detected subset in that order" carrier=test-pilot-layer -->
**`browserTools` provisional default.** When one or more tools are detected,
write `browserTools` as the detected subset in fixed preference order:
`chrome-devtools`, then `playwright`, then `Claude_in_Chrome` (omit undetected
names; never write an empty array). Record the chosen order in
`## Setup disclosures`. Continue. Follow-up: `/superheroes:configure`.
<!-- /decision-point: id=tp-init-browser-tools -->

<!-- decision-point: id=tp-init-browser-gate mode=gate kind=owner-gate default="hand back; no browser tool connected" carrier=run-output -->
When **no** browser MCP is connected, GATE: write the remediation down in the
run output (install chrome-devtools MCP, Playwright plugin, or Claude in Chrome
extension), record that no browser tool is connected, leave `browserTools`
**absent** (not an empty array), and **hand back** — do not continue init or
drive browser tooling. **No layer is written on this path** — init stops here
before Step 6's writer runs. Follow-up: `/superheroes:configure`.
<!-- /decision-point: id=tp-init-browser-gate -->

## Step 4 — Decide location

<!-- decision-point: id=tp-init-storage mode=notify kind=storage-location default="returned .mode from store CLI" carrier=test-pilot-layer -->
```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
DEC=$(python3 -B "$ROOT_DIR/lib/store.py" decide-location) || { echo "decide-location exited non-zero (exit $?); halting rather than taking an undisclosed storage default" >&2; exit 1; }
LOC=$(printf '%s' "$DEC" | jq -r '.mode')            # "in-repo" | "global" — never "ask"
SOURCE=$(printf '%s' "$DEC" | jq -r '.source')
PROVISIONAL=$(printf '%s' "$DEC" | jq -r '.provisional')   # "true" | "false"
[ -n "$LOC" ] && [ -n "$PROVISIONAL" ] && [ -n "$SOURCE" ] || { echo "decide-location returned no usable decision; halting rather than taking an undisclosed storage default" >&2; exit 1; }
PATHS=$(python3 -B "$ROOT_DIR/lib/store.py" create --location "$LOC") || RC=$?
RC=${RC:-0}
if [ "$RC" -ne 0 ]; then
  printf '%s' "$PATHS" | jq -r 'if .reason then "\(.reason): \(.detail)" else "store.py create exited non-zero (exit '"$RC"')" end' >&2
  exit "$RC"
fi
```

**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is `in-repo` or
`global` (`ask` no longer exists); `.source` is where the decision came from: `env` (environment
override `TEST_PILOT_STORAGE` for this run only; never recorded), `registry` (a mode the owner
recorded; authoritative), `backfilled` (a mode inferred from consistent existing evidence and then
recorded), `provisional` (nothing recorded and no consistent evidence; the lib's default, re-taken
next run); `.provisional` is `true` when the mode was not owner-recorded. **Default:**
the returned `.mode` (recorded when configured, else the lib's provisional default). Bootstrap
blocks never record — an unrecorded mode is re-taken next run. **Disclosure.** Write into the
**test-pilot layer body** (the markdown piped to `core_md.py write-layer --hero test-pilot` in
Step 6 — a `## Setup disclosures` section, not the generated provenance block): the storage mode
taken, its source, whether it is provisional, and that `/superheroes:configure` changes it. When
`.provisional` is `true`, also state that it is a provisional default rather than an owner choice
and will be re-taken on the next run when not recorded. **Follow-up:** `/superheroes:configure`.
NOTIFY: the run continues after the disclosure lands in `## Setup disclosures`.
<!-- /decision-point: id=tp-init-storage -->

## Step 5 — Provisional defaults (no interview)

<!-- decision-point: id=tp-init-provisional-defaults mode=proceed kind=interview-step default="named provisional defaults per field list below" carrier=test-pilot-layer -->
Do not interview. Take named provisional defaults for every field detection + `CLAUDE.md` left
open. Write which fields were defaulted into `## Setup disclosures` of `$TEST_PILOT_LAYER_BODY`
(the markdown piped to `core_md.py write-layer --hero test-pilot` in Step 6). Never guess a
protected target — when detection cannot name a production-shaped DB/surface to refuse, state
that in `## Setup disclosures` and leave the gate **refusing** rather than inventing a target.
Continue to Step 6. Follow-up: `/superheroes:configure`.

**Provisional defaults** (when detection + `CLAUDE.md` did not answer):

1. **Auth strategy** — `review-only` (provisional default): unattended execute cannot assume
   credentials; the owner confirms via `/superheroes:configure`.
2. **Protected targets** — only names detection actually found; if none, record `none detected —
   gate refuses` and do not scaffold a target list.
3. **Base URL / readiness probe** — detected dev URL/port when present, else
   `http://localhost:<detected-port>` when a port was detected, else refuse to guess.
4. **`dbEnvVar`** — first database-related env var **name** detected from `.env*` files (names
   only, never values); if none, omit the field and record `none detected` in
   `## Setup disclosures`.
5. **`apiBase`** — `{baseUrl}/api` when `baseUrl` is known; if `baseUrl` is unknown, omit the
   field and record `none detected` in `## Setup disclosures`.
6. **`allowedOrigins`** — `[]` (provisional default).
7. **`devCommand`** — detected from `package.json` scripts (`dev`, then `start`) or
   `pyproject.toml` `[project.scripts]`; if none detected, omit the field and record
   `none detected` in `## Setup disclosures`.
8. **`mayManageServer`** — `false` (provisional default): execute will not start the server
   without owner confirmation via `/superheroes:configure`.
9. **`browserTools`** — per Step 3 (`tp-init-browser-tools` / `tp-init-browser-gate`); when none
   detected, the field stays absent.
<!-- /decision-point: id=tp-init-provisional-defaults -->

## Step 6 — Scaffold

1. Fill `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/templates/profile.md` (prose AND the
   `json test-pilot-config` block — keep them consistent) and write it to
   the resolved profile path. Set provenance `status=provisional` always on this create path —
   only `/superheroes:configure` confirms with real answers.
2. Write 1–2 starter blocks bespoke to this app into the resolved
   `blocks_dir`, from `templates/starter-block.py` — e.g. an HTTP seeder
   against the detected API, or a `run-command` design wrapping an existing
   seed script. Every block declares non-empty `targets` and pins PEP 723
   dependency versions.
3. Generate the catalog:
   `python3 -B "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/catalog.py" --blocks-dir <blocks_dir>`
4. CREATE path (fresh setup, FR-5): Fail-closed guard before the pipes below — not the
   mechanical-carrier redesign: refuse when either the shared facts JSON (stack, verify command,
   threat model) or `$TEST_PILOT_LAYER_BODY` (test-pilot's `json test-pilot-config` block + prose,
   including the `## Setup disclosures` section assembled from Steps 4–5) is empty, because
   `write-layer` replaces the entire layer file and an empty piped payload would silently blank it.
   When either payload is empty, surface `assembly produced empty payloads; halting rather than
   writing an empty layer` and **stop** — do not pipe into `write` or `write-layer`. This guard's
   protection is **unverified**: nothing in the test suite executes skill prose, so no automated
   test exercises this refusal. Provability would require expressing Step 6's write path as
   executable shell **and** driving it with a harness that actually executes it — `review-init`
   Step 4b already uses executable shell for its guard, but that guard remains unproven for the
   same reason: no harness runs skill prose. With both halves in place, the empty-payload halt
   could be observed at runtime. When both
   payloads are present, pipe the shared facts JSON into
   `python3 -B "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/core_md.py" write
   --status provisional` to write the band-wide `core.md`, and pipe `$TEST_PILOT_LAYER_BODY` into
   `core_md.py write-layer --hero test-pilot --status <s>` so they land in the `test-pilot.md`
   layer (FR-3). On reconcile of a pre-existing profile, the legacy `profile.md` is not adopted —
   `resolve_shared` returns the `legacy-profile-unsupported` refusal pointing at
   `superheroes:configure` — no shared facts to read yet; re-calibrate through configure first
   (`core_md resolve` only after `core.md` exists; CONVENTIONS §2.1 / §2.2). Never hand-format core.md — the lib owns
   the format and the config lock. `write --status confirmed` is the CREATE path only; confirming
   a pre-existing **provisional** core/layer goes through `core_md.py confirm` (reached from
   `superheroes:configure`), which `write` cannot do on an existing file (it returns `reused`).
   After `write`, check the result's `action`: `refused` (`fable-on-external-engine`,
   `core-md-unreadable`, or `dispatch-gate-evaluation-failed`) means the core was **not** written —
   surface the `violations` to the user and **stop**; do not run `write-layer` (`write` exits 0 either
   way, so check `action`, not exit status).

Report what was written and where; remind the user that `test-pilot-plan`
picks it up from here.

### Conformance run (when `pilot` block is declared)

After calibration is written, and **only when** the profile declares a `pilot`
block, run the headless conformance pass (normative CLI in
`reference/pilot-contract.md` §The conformance run):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
REPORT_JSON="$(mktemp)"
trap 'rm -f "$REPORT_JSON"' EXIT
CONFORMANCE_ARGS=(run --cwd .)
if [ -n "${PILOT_REGISTRY:-}" ]; then
  CONFORMANCE_ARGS+=(--registry-path "$PILOT_REGISTRY")
fi
python3 -B "$ROOT_DIR/lib/pilot_conformance.py" "${CONFORMANCE_ARGS[@]}" > "$REPORT_JSON"
python3 -B "$ROOT_DIR/lib/pilot_acceptance.py" matrix \
  --report-path "$REPORT_JSON" \
  --project "$(basename "$(pwd)")" \
  --commit "$(git rev-parse HEAD)" \
  --format markdown
```

When the project maintains a declare-and-exercise registry (see
`reference/pilot-contract.md` §Declare and exercise), set `PILOT_REGISTRY` to
that JSON path before running the conformance step so `--registry-path` is passed
and the report carries a `declarations` envelope. **Without a registry path** the
conformance report's `declarations` key is `null` — the matrix CLI still
renders, but declaration-backed rows read `unexercised` with a stated reason;
that is the ordinary adopter case, not a refusal.

Stdout is the report JSON from the conformance run; the matrix step prints
markdown on stdout. Stderr carries diagnostics. **Exit 1 is a real outcome to
report, not an error to swallow** — show the operator which surfaces came back
`unexercised` and why, from the report's `resolution` list. The matrix's `ok`
is **false** when any row is `unexercised`, when the reference worktree is
dirty, or when the run itself left surfaces `unexercised` — that is the honest
outcome for a project that has not exercised everything, **not a failure to
work around**. `--commit` must be a **full object id** (run `git rev-parse
HEAD` in the reference project — not a branch name). **Dirty** is derived from
`git status --porcelain` in the **CLI process's current working directory** when
neither `--dirty` nor `--clean` is passed; pass `--dirty` or `--clean` to
override. The run **never** writes into the repository when `--allow-live-effects` is not passed. The
`cleanup-end-to-end`, `mint-gate-off`, and `ownership-probe` exercises are
reported as **unexercised** unless the operator explicitly passes
`--allow-live-effects`; opting in runs the project's own destructive cleanup,
gate-off, and ownership-probe commands against live datastore and checkout
resources. A `mint-gate-off` exercise that does not produce a usable receipt is
reported as **unexercised**, never recorded as exercised — configure refuses to
claim it. The matrix is **generated, not stored** by the plugin — where a
project keeps it is the project's own decision.

### Pilot block (optional)

The nested `pilot` key inside `test-pilot-config` is **omitted entirely** unless the owner
has answered every one of its no-default fields. Do not scaffold it during init.

- `effectsEscape`, the mint envelope, and expected pilot identities are **never synthesized,
  defaulted, or placeholder-filled** — an unanswered declaration is absent and absent refuses.
- Expected identity and the mintable-account allowlist are **policy**; they do not belong in
  the `pilot` block at all (resolved via `policyRef.declaration` against an external policy
  document).
- Normative field table, refusal tokens, and probe vocabulary:
  `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/reference/pilot-contract.md`.

## Step 7 — Reconcile mode

<!-- decision-point: id=tp-init-reconcile-drift mode=gate kind=owner-gate default="hand back; apply nothing" carrier=run-output -->
Re-run detection, then DIFF against the existing profile. GATE: write the drift diff down in the
run output (changed dev command, new env vars, vanished scripts, and any other detected deltas)
and **hand back** — apply **no** profile changes and write **no** layer on this init path.
Hand-edits in the profile are preserved because nothing is written. Never regenerate from scratch
over an existing profile. Follow-up: `/superheroes:configure` to apply, edit, or skip changes.
<!-- /decision-point: id=tp-init-reconcile-drift -->
