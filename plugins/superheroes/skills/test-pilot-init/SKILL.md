---
name: test-pilot-init
description: "Internal helper reached from `superheroes:configure` to refresh test-pilot's profile, seeding blocks, and browser tooling layer. Not a front door; owners run `superheroes:configure` to set up, fix, view, or tune calibration."
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# test-pilot-init

Create or reconcile a project's **test-pilot profile** plus its starter
seeding blocks. Two modes: **create** (nothing resolves) and **reconcile**
(profile exists → re-detect, diff, migrate; NEVER silently overwrite).

## Step 1 — Resolve

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RES=$(python3 "$ROOT_DIR/lib/store.py" resolve)
LOCATION=$(printf '%s' "$RES" | jq -r .location)
# FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
NUDGE_MSG=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
[ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
```

`location: none` → create mode (Steps 2–6). Otherwise → reconcile (Step 7).

## Step 2 — Detect (no questions the repo can answer)

Read `CLAUDE.md` first — the profile is an ADDER over it. Then detect:
stack/scripts (`package.json` scripts, `pyproject.toml`), dev command and
port, DB env vars (`.env*` files — names only, never read values into the
profile), docker-compose services, existing seed scripts, `git remote
get-url origin`. Check `uv` availability (`command -v uv`); if absent, offer
to help install it (https://docs.astral.sh/uv/) — without it, blocks are
limited to stdlib + run-command designs.

## Step 3 — Browser tooling gate

Use ToolSearch to check which browser MCPs are connected (search
"chrome-devtools", "Claude_in_Chrome", "playwright"). If NONE is available,
STOP and guide the user through installing one (chrome-devtools MCP,
Playwright plugin, or the Claude in Chrome extension) before continuing.
Record the preference order for the profile.

## Step 4 — Decide location

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
LOC=$(python3 "$ROOT_DIR/lib/store.py" decide-location --interactive true)
# "ask" -> AskUserQuestion: in-repo (committed, team-shared) vs global
# (~/.claude/test-pilot/, zero git footprint). Headless runs get "global".
# If LOC is "ask" → AskUserQuestion, set LOC to owner's pick, then record band-wide (FR-3).
# If LOC is already in-repo/global → skip record, go straight to create.
REC=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" reconcile --mode "$LOC" 2>/dev/null) || REC=""
if [ -z "$REC" ] || printf '%s' "$REC" | jq -e '.written == false' >/dev/null 2>&1; then
  echo "note: couldn't record the band storage mode this run — you'll be asked again next time."
fi
PATHS=$(python3 "$ROOT_DIR/lib/store.py" create --location "$LOC")
```

## Step 5 — Interview only the gaps

Ask ONLY what detection + CLAUDE.md left open. The user may not know the
option space — for each question, present the options with one-line
trade-offs AND a recommendation derived from what you detected.

1. **Auth strategy** — how execute gets a signed-in session:
   - *Test-user credentials* (env var NAMES only, never secrets): needs a
     password/credentials login to already exist in the app.
   - *Auth bypass*: a dev-only sign-in path; enables unattended runs in a
     clean browser, but requires an app code change and care that it can
     never reach production.
   - *Real browser session* (forces Claude in Chrome): zero app changes;
     runs are semi-attended and drive the user's real, signed-in browser.
   Recommend from detection: OAuth-only providers and no credentials/test
   login → real browser session is the zero-code default.
2. **Protected targets** — which DB/surface the gate must refuse. Suggest
   the production/main DB you detected. If the app reads the same local DB
   the seeds would target, ALSO ask which seeding story the user wants:
   seed the local dev DB the app already reads (simplest — the app sees the
   data; protect only production-shaped names/URIs), or seed an isolated
   scratch DB with the profile's `devCommand` overriding the connection env
   var (stricter; the app only sees it when started via the profile).
3. **Base URL / readiness probe** — confirm.

## Step 6 — Scaffold

1. Fill `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/templates/profile.md` (prose AND the
   `json test-pilot-config` block — keep them consistent) and write it to
   the resolved profile path. Set provenance `status=stable` when the user
   answered the interview, `status=provisional` on headless defaults.
2. Write 1–2 starter blocks bespoke to this app into the resolved
   `blocks_dir`, from `templates/starter-block.py` — e.g. an HTTP seeder
   against the detected API, or a `run-command` design wrapping an existing
   seed script. Every block declares non-empty `targets` and pins PEP 723
   dependency versions.
3. Generate the catalog:
   `python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/catalog.py" --blocks-dir <blocks_dir>`
4. CREATE path (fresh setup, FR-5): pipe the shared facts JSON (stack, verify command,
   threat model) into `python3 "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/lib/core_md.py" write
   --status confirmed` (use `provisional` on a headless run) to write the band-wide `core.md`,
   and pipe test-pilot's own sections (its `json test-pilot-config` block + prose) into
   `core_md.py write-layer --hero test-pilot --status <s>` so they land in the `test-pilot.md`
   layer (FR-3). On reconcile of a pre-existing profile, run `core_md migrate --hero test-pilot`
   then `core_md resolve` (CONVENTIONS §2.1 / §2.2). Never hand-format core.md — the lib owns
   the format and the config lock. `write --status confirmed` is the CREATE path only; confirming
   a pre-existing **provisional** core/layer goes through `core_md.py confirm` (reached from
   `superheroes:configure`), which `write` cannot do on an existing file (it returns `reused`).

Report what was written and where; remind the user that `test-pilot-plan`
picks it up from here.

## Step 7 — Reconcile mode

Re-run detection, then DIFF against the existing profile. Present drift to
the user (changed dev command, new env vars, vanished scripts) and apply
only what they approve. Hand-edits in the profile are preserved verbatim
unless the user approves replacing them. Never regenerate from scratch over
an existing profile.
