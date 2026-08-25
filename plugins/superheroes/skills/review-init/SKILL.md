---
name: review-init
description: "Internal helper reached from `superheroes:configure` to refresh review-crew's calibration layer for a project. Not a front door; owners run `superheroes:configure` instead."
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# review-init

Generate or refresh a project's **review profile** — `.claude/review-profile.md` —
the per-project calibration the review-crew engine reads (threat model, verify
command, scope, focus hints, canonical patterns). Two modes: **create** (no
profile yet) and **reconcile** (profile exists → re-detect and migrate).

## The profile is a CLAUDE.md-aware ADDER

The profile carries ONLY what the project's `CLAUDE.md` does not already cover.
Read `CLAUDE.md` first; never duplicate its conventions into the profile —
`## Conventions` points at `CLAUDE.md`. Skip any interview question whose answer
is already clear from detection or `CLAUDE.md`.

## Step 1 — Detect (no questions where the repo answers)

Run these and read the results; do not ask the user what you can observe:

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
# Package manager / stack
ls "$ROOT"/package.json "$ROOT"/pyproject.toml "$ROOT"/Cargo.toml "$ROOT"/go.mod 2>/dev/null
# Verify-command candidate (JS): a "check"/"test" script
[ -f "$ROOT/package.json" ] && python3 -B -c "import json;print(json.load(open('$ROOT/package.json')).get('scripts',{}))" 2>/dev/null
# Default branch
git symbolic-ref --quiet refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' \
  || git rev-parse --abbrev-ref HEAD
# Forge
git remote get-url origin 2>/dev/null
# Top-level source dirs
ls -d "$ROOT"/src "$ROOT"/lib "$ROOT"/app 2>/dev/null
```

Derive: **package manager / framework / test runner**; a **verify-command**
candidate (`npm run check` → `npm test` → `pnpm/yarn` equivalents → `make check`
→ none); **default-branch** (the `git symbolic-ref` result, else current branch);
**forge** (`github` if the remote host is github.com, `gitlab` if gitlab.*, else
`none`); **dep-set** (top-level dependency names, with major version where cheap);
**src-dirs**. Also **read `CLAUDE.md`** (root and any nested) to learn what
conventions/threat context it already states.

Read the engine versions for provenance:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
sed -n '1p' "$ROOT_DIR/rubric/review-base.md"          # -> <!-- rubric-version: N -->
python3 -B -c "import json;print(json.load(open('$ROOT_DIR/.claude-plugin/plugin.json'))['version'])"
```

## Step 2 — Choose mode

Resolve where the profile lives (it may be in-repo under `./.claude/` or in the
global per-repo store). `review_store.py resolve` returns the resolved path, or
`location: none` when no profile exists yet:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RES=$(python3 -B "$ROOT_DIR/lib/review_store.py" resolve --kind profile) \
  || RES='{"location":"none","exists":false,"path":null}'
LOCATION=$(printf '%s' "$RES" | jq -r .location)
PROFILE=$(printf '%s' "$RES" | jq -r '.path // empty')
# FR-7/8: surface the single coalesced storage-mode reconcile nudge (non-blocking, ack-gated).
NUDGE_MSG=$(python3 -B "$ROOT_DIR/lib/mode_reconcile.py" signals 2>/dev/null | jq -r 'if . == null then empty else .message end' 2>/dev/null)
[ -n "$NUDGE_MSG" ] && echo "⚠ storage-mode: $NUDGE_MSG"
```

If `$LOCATION` is not `none` (a profile resolved at `$PROFILE`) → **Reconcile**
(Step 5). Otherwise (`$LOCATION` is `none`) → **Create** (Steps 3–4); decide the
storage location and mint the path before writing:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$LOCATION" = "none" ]; then
  DEC=$(python3 -B "$ROOT_DIR/lib/review_store.py" decide-location) || { echo "decide-location exited non-zero (exit $?); halting rather than taking an undisclosed storage default" >&2; exit 1; }
  LOC=$(printf '%s' "$DEC" | jq -r '.mode')            # "in-repo" | "global" — never "ask"
  SOURCE=$(printf '%s' "$DEC" | jq -r '.source')
  PROVISIONAL=$(printf '%s' "$DEC" | jq -r '.provisional')   # "true" | "false"
  [ -n "$LOC" ] && [ -n "$PROVISIONAL" ] || { echo "decide-location returned no usable decision; halting rather than taking an undisclosed storage default" >&2; exit 1; }
  PROFILE=$(python3 -B "$ROOT_DIR/lib/review_store.py" create --kind profile --location "$LOC")
fi
```

**Storage location (`decide-location`).** `decide-location` returns JSON: `.mode` is `in-repo` or
`global` (`ask` no longer exists); `.source` is where the decision came from (e.g. `recorded`,
`default`, `env`); `.provisional` is `true` when the mode was not owner-recorded. **Default:**
the returned `.mode` (recorded when configured, else the lib's provisional default). Bootstrap
blocks never record — an unrecorded mode is re-taken next run. **Disclosure.** Write into the
**review-crew layer body** (`$REVIEW_LAYER_BODY`, written through `core_md.py write-layer` in Step
4b — a `## Setup disclosures` section, not the generated provenance block): the storage mode
taken, its source, whether it is provisional, and that `/superheroes:configure` changes it. When
`.provisional` is `true`, also state that it is a provisional default rather than an owner choice
and will be re-taken on the next run when not recorded. **Follow-up:** `/superheroes:configure`.
The minted `$PROFILE` is the path Step 4 writes to.

## Step 3 — Create: detection + defaults (no interview)

Do not interview. Build the profile from Step 1 detection + `CLAUDE.md` + named provisional
defaults. Write `status: provisional` always on this path — the interview branch that produced
`status: confirmed` is retired; only `/superheroes:configure` confirms a profile with a real verify
story. State in the **profile provenance block** which fields were defaulted rather than answered.

Defaults when detection + `CLAUDE.md` did not answer:

1. **Threat model** — `strict` (provisional default when unknown).
2. **Verify command** — if none was detected, `mode: review-only` (provisional default).
3. **Scope exclusions** — none (provisional default).

If **no `CLAUDE.md` exists**, record a minimal conventions pointer in `## Conventions` (point at
`CLAUDE.md` once the owner adds one); do not generate or commit `CLAUDE.md` here.

## Step 4 — Create: seed canonical patterns, assemble core + layer bodies

Seed `## Canonical patterns` by detection — grep for the project's own idioms so
generalized agents stay sharp (each is `pattern: file:line`):

```bash
grep -rnE "getServerSession|requireAuth|withAuth|authorize\(" "$ROOT"/src 2>/dev/null | head -1   # auth wrapper
grep -rlE "export const [A-Z_]+_ERRORS|errors?\.(ts|js|py)$" "$ROOT"/src 2>/dev/null | head -1     # error constants
grep -rnE "userId|ownerId|tenantId" "$ROOT"/src 2>/dev/null | head -1                              # ownership idiom
```

Record only patterns you actually found. From the Step 3 interview, assemble two payloads —
**do not** write the legacy single-file template to `$PROFILE` (that path is the unified layer
file; clobbering it breaks dispatch):

- `$CORE_FACTS_JSON` — JSON for `core_md.py write`: `verifyCommand`, `stackTags`, `threatModel`,
  `patterns` (canonical patterns block as a string).
- `$REVIEW_LAYER_BODY` — markdown body for `core_md.py write-layer`: `## Setup disclosures`
  (storage mode, source, provisional status, and `/superheroes:configure` follow-up from Step 2
  when bootstrap ran), `## Scope exclusions`, `## Focus hints`, `## Conventions` (hero-owned
  sections only; no provenance block).

Proceed to Step 4b to write both files. When the layer path is in-repo (under
`./.claude/superheroes/`), **do not commit** — write the files and leave them **uncommitted and
untracked**. State that in the run output; the owner commits via git or confirms via
`/superheroes:configure`.

`status` is always `provisional` on this create path; `confirmed` is reached only through
`/superheroes:configure` after a real verify story.

### Step 4b — Write the shared brain (core.md) + the review-crew layer

The shared facts (stack, verify command, threat model, canonical patterns) belong in
the band-wide `core.md`; review-crew's own sections (scope exclusions, focus hints,
conventions) belong in its layer `review-crew.md`. Both are written through the lib —
never hand-format core.md (CONVENTIONS §2.2). Always pass `--status provisional` on this create path
(FR-5); `confirmed` is reached only via `/superheroes:configure`:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
STATUS=provisional   # always on this create path; confirmed only via /superheroes:configure (FR-5)
# CREATE: shared facts → core.md (lock-guarded, reuse-not-clobber FR-6/FR-7; a
# `proposed`/`deferred` action is surfaced, never silently overwritten).
printf '%s' "$CORE_FACTS_JSON" \
  | python3 -B "$ROOT_DIR/lib/core_md.py" write --status "$STATUS"
# CREATE: review-crew's own sections → its layer file (FR-3).
printf '%s' "$REVIEW_LAYER_BODY" \
  | python3 -B "$ROOT_DIR/lib/core_md.py" write-layer --hero review-crew --status "$STATUS" --rubric-version "$RUBRIC_VERSION"
```

`write` above is the **create** path: on an existing core it returns `reused`/`proposed`/`refused`/`deferred`.
A `refused` result (including `fable-on-external-engine`, `core-md-unreadable`, or
`dispatch-gate-evaluation-failed`) means the write did not apply — surface the `violations` to the
owner and **stop**; never proceed to write the layer as if the write had succeeded. For
`core-md-unreadable`, the existing `core.md` could not be read, so the write was refused rather than
overwriting it — surface the path from the violation's `detail` to the owner. On a successful create path without refusal, `reused`/`proposed`
apply as before. Confirming a pre-existing **provisional** core/layer is a separate path —
`core_md.py confirm` (reached from `superheroes:configure`'s fix flow), which re-renders the core
and surgically flips each layer, preserving `created`/`nudge-ack` and bumping `updated` (FR-18).

On **reconcile** (a pre-existing legacy profile), nothing is adopted automatically —
`core_md.resolve_shared` returns the `legacy-profile-unsupported` refusal, surfaced to the owner
with its `remedy` and routed to `superheroes:configure` — there are no shared facts to read yet;
the owner must re-calibrate through configure first (`core_md resolve` is only meaningful after
`core.md` exists). Settle any ambiguous/provisional state through the single coalesced reconcile
nudge (already surfaced in Step 2). See CONVENTIONS §2.1 (layout) and §2.2 (format).

## Step 5 — Reconcile (profile already exists)

1. Read the existing profile and its `schema:`.
2. **Read-side guard:** if the profile's `schema` is **higher** than this plugin
   supports (the template's `schema` above), STOP with a loud message
   ("profile schema N is newer than this review-crew; upgrade the plugin") and do
   not rewrite it — degrade conservatively (strict posture) rather than misread
   newer fields.
3. **Apply migrations** for each step between the profile's `schema` and the
   plugin's. *(Schema 1 is current; there are no migration steps yet. When a
   future schema adds/renames fields, each `N→N+1` step is listed here and applied
   in order.)*
4. Re-read `CLAUDE.md` and re-detect (Step 1). Compute proposed changes: new
   `dep-set`, changed `default-branch`/`forge`, newly-covered-by-CLAUDE.md items
   to drop from the profile, etc.
   **Detect `rubric-version` drift.** Read the engine's current rubric-version
   (Step 1: the `<!-- rubric-version: N -->` line of `review-base.md`). If the profile's
   `rubric-version` is **lower** than the engine's, flag
   it as drift in the proposed-changes diff ("rubric-version M→N: the review rubric
   has advanced; recalibrating") and update it on write (step 7). This is the same
   signal `repo_doctor.py` surfaces as a staleness nudge during a review — reconcile
   is where it actually gets cleared.
5. **Migration rules:** unknown `## ` sections/keys are **preserved verbatim**
   (forward-compat); missing fields are filled per the create defaults only when
   safe; never silently delete user calibration. The `nudge-ack` map is user
   state — **preserve it verbatim** across the reconcile (do not reset acks the
   user has already dismissed). Add the `nudge-ack:` field (empty `{}`) only if an
   older profile predates it.
6. **Do not apply by default.** Write the proposed-changes **diff** into the run output as
   disclosure (the conservative default — this path can overwrite user calibration). Point the
   owner at `/superheroes:configure` to apply, edit, or skip. Preserve all hand-edits below the
   provenance block unless the owner approves a change through configure.
7. Write the profile only when the owner applies via `/superheroes:configure`; on this init path
   without an explicit apply, **do not write** the reconciled profile — the diff disclosure is the
   hand-back. When configure applies: bump `updated:` and refresh `signals` + `rubric-version` +
   `plugin` (set `rubric-version` to the engine's current value, clearing any
   drift detected in step 4). **Preserve the `nudge-ack` map** (carry the existing
   acks forward unchanged). `status` stays `provisional` until `/superheroes:configure` confirms
   with a real verify story.

## Common mistakes

| Mistake | Fix |
| --- | --- |
| Duplicating CLAUDE.md conventions into the profile | The profile is an adder — point `## Conventions` at CLAUDE.md; only add gaps. |
| Asking the user something detection/CLAUDE.md already answers | Detect and read first; the interview covers only the remainder. |
| Rewriting a profile from a newer schema | Honor the read-side guard: stop and tell the user to upgrade. |
| Silently dropping hand-edits on reconcile | Preserve everything below provenance; show a diff; only change on approval. |
| Editing the user's build config to "set up" a verify command | Propose the command; let the user add it. |
