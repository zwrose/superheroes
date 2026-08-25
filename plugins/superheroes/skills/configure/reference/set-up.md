## Contents

- §1 — Decide the storage mode (FR-2), with disclosure
- §2 — Seed the core + the light hero layers (FR-16)
- §3 — Verify command first (UFR-5)
- §4 — Optional heavier heroes — provisional defaults disclose (FR-3)
- §4.4 — Show-it surface — provisional default
- §4.5 — Engine preferences — per-role defaults (FR-11/12/13/14)
- §4.6 — Review-discipline CLAUDE.md — offer recorded, not written unasked
- §5 — Secrets stay out of shared calibration (NFR)
- Recovering an interrupted set-up (UFR-7)

# configure — set-up path

Reached from `configure` when a project has nothing configured yet (FR-1). Sets the project up
end to end: storage mode, the shared core, the light hero layers, and named provisional defaults
for optional heroes. Set-up takes declared defaults and discloses them in the layer carriers — it
does not interview.

`ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"` is assigned once per bash block below.

## 1 — Decide the storage mode (FR-2), with disclosure

A project keeps its calibration either **repo-shared** (committed with the repo, **visible to
collaborators**) or **out-of-repo** (kept on the local machine, the repo stays pristine). Present
both with that consequence **before** recording the mode — repo-shared publishes the calibration to
anyone with the repo. Resolve the band-wide decision (it is decided once and is sticky, FR-11):

<!-- decision-point: id=configure-setup-storage-location mode=notify kind=storage-location default="recorded mode when one exists, else provisional global (out-of-repo)" carrier=review-crew-layer -->

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
DEC=$(python3 -B "$ROOT_DIR/lib/review_store.py" decide-location) || { echo "decide-location exited non-zero; halting rather than taking an undisclosed storage default" >&2; exit 1; }
LOC=$(printf '%s' "$DEC" | jq -r '.mode')
SOURCE=$(printf '%s' "$DEC" | jq -r '.source')
PROVISIONAL=$(printf '%s' "$DEC" | jq -r '.provisional')
[ -n "$LOC" ] && [ -n "$PROVISIONAL" ] && [ -n "$SOURCE" ] || { echo "decide-location returned no usable decision; halting" >&2; exit 1; }
```

**Default:** recorded mode when one exists, else provisional `global` (out-of-repo). An
already-decided mode is reported, not re-asked. **Disclosure:** when `$PROVISIONAL` is `true`, state
in the set-up output which storage mode was taken, that it is provisional, and that
`/superheroes:configure` changes it. **Follow-up:** the owner changes storage mode via
`/superheroes:configure` (view-and-tune §3 for a flip after set-up).

NOTIFY: take the returned `.mode` from `decide-location`, record mode/source/provisional status in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note, disclose in set-up output when provisional, and the run continues. Follow-up:
`/superheroes:configure`.

<!-- /decision-point: id=configure-setup-storage-location -->

## 2 — Seed the core + the light hero layers (FR-16)

Once the mode is set, seed the shared **core** (the project's stack, verify command, threat model)
and the two light layers — the-architect's doc-policy and review-crew's threat model — in the same
pass. Drive each hero's calibration logic through its now-internal `*-init` skill (reached from
here, not advertised separately). Detect facts from the repo; do not ask. Write the core
**provisional**, stating which fields were defaulted rather than answered; the owner confirms via
the FR-18 confirm step.

Set-up's decisions are disclosed in the **set-up output** — this path's own report to the owner.
Each hero's `## Setup disclosures` section is **assembled and written by that hero's `*-init`
skill**, which this path drives; set-up hands its defaults to those skills, it does not write hero
layers itself. Review-crew disclosures are written in `review-init` Step 4b; test-pilot disclosures
in `test-pilot-init` Step 6.

## 3 — Verify command first (UFR-5)

<!-- decision-point: id=configure-setup-verify-command mode=notify kind=ask-user-question default="mode: review-only when no verify command is detectable" carrier=review-crew-layer -->

When no verify command is detectable, take the provisional default **`mode: review-only`** (matching
`review-init`'s default for the same field) — **never edit the owner's build config yourself** and
never guess a command. NOTIFY: record `mode: review-only` in the core facts and disclose it in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note, and the run continues. The owner may set a real
verify command via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-verify-command -->

## 4 — Optional heavier heroes — provisional defaults disclose (FR-3)

<!-- decision-point: id=configure-setup-optional-heroes mode=notify kind=ask-user-question default="do not set up optional heroes" carrier=review-crew-layer -->

Where a heavier or optional hero applies (**test-pilot**, **guardian**, or any hero needing extra
tooling such as a connected browser), the default is to **leave it un-set-up** and disclose that
optional heroes were skipped and that `/superheroes:configure` can add them. NOTIFY: record the
skipped heroes in the set-up output and carry them into the hero's `## Setup disclosures` section
per the §2 carrier note and the run continues.
Set-up still **completes** and the project is usable without them.

<!-- /decision-point: id=configure-setup-optional-heroes -->

<!-- decision-point: id=configure-setup-browser-tool-gap mode=notify kind=ask-user-question default="record the browser-tool gap; do not guide" carrier=test-pilot-layer -->

When test-pilot would apply but no browser tool is connected, NOTIFY: record the browser-tool gap
in `## Setup disclosures` for the test-pilot layer and the run continues — do not guide the owner
to connect one and do not block set-up (UFR-4). Follow-up: `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-browser-tool-gap -->

<!-- decision-point: id=configure-setup-guardian-tuning mode=notify kind=ask-user-question default="guardian tuning off — sweeps on plugin defaults" carrier=review-crew-layer -->

**Guardian** works with zero configuration on plugin defaults — sweeps run even when the owner
skips tuning. The default is **off**: do not offer guardian threshold/cadence tuning during
set-up; disclose that guardian runs on defaults and that `/superheroes:configure` can tune it.
`guardian.md` is a thin adder for those deviations (empty is valid). The `guardian-config` fence
shape is in `skills/guardian/reference/calibration.md`. NOTIFY: record guardian-left-on-defaults in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note and the run continues.

<!-- /decision-point: id=configure-setup-guardian-tuning -->

<!-- decision-point: id=configure-setup-hero-decline mode=proceed kind=owner-gate default="optional heroes not set up — not recorded as declined" carrier=review-crew-layer -->

Absent explicit decline language in the owner's **current-turn words**, the default is that optional
heroes are simply **not set up** — that is **not** the same as declined; do **not** call
`hero_setup.py decline`. PROCEED: record the not-set-up posture in `## Setup disclosures` and
continue. Only when the owner explicitly declines an optional hero in this turn, record it so the
view tune-menu does not re-offer it on every run (FR-6 / #121):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/hero_setup.py" decline --cwd . --hero test-pilot
# or, for guardian:
python3 -B "$ROOT_DIR/lib/hero_setup.py" decline --cwd . --hero guardian
```

Follow-up: `/superheroes:configure` can still set up a hero later unless it was explicitly
declined.

<!-- /decision-point: id=configure-setup-hero-decline -->

When test-pilot calibration is written and the profile declares a `pilot` block,
run the headless conformance pass before set-up completes (normative CLI in
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
report, not an error to swallow** — show which surfaces are `unexercised` and
why, from the report's `resolution` list. The matrix's `ok` is **false** when
any row is `unexercised`, when the reference worktree is dirty, or when the
run itself left surfaces `unexercised` — that is the honest outcome for a
project that has not exercised everything, **not a failure to work around**.
`--commit` must be a **full object id** (run `git rev-parse HEAD` in the
reference project — not a branch name). **Dirty** is derived from
`git status --porcelain` in the **CLI process's current working directory** when
neither `--dirty` nor `--clean` is passed; pass `--dirty` or `--clean` to
override. The run **never** writes into the repository when `--allow-live-effects` is not passed. The `cleanup-end-to-end`,
`mint-gate-off`, and `ownership-probe` exercises are reported as
**unexercised** unless the operator explicitly passes `--allow-live-effects`;
opting in runs the project's own destructive cleanup, gate-off, and
ownership-probe commands against live datastore and checkout resources. A
`mint-gate-off` exercise that does not produce a usable receipt is reported as
**unexercised**, never recorded as exercised — configure refuses to claim it.
The matrix is **generated, not stored** by the plugin — where a project keeps
it is the project's own decision.

## 4.4 — Show-it surface — provisional default

<!-- decision-point: id=configure-setup-show-it mode=notify kind=ask-user-question default="honest evidenced level, or none when nothing is detectable" carrier=review-crew-layer -->

Record **where the owner goes to look at a finished change** — the entry point a **show it** PR's
*How to see it* section points at. The declaration lives as prose under `## Show-it surface` in
`core.md`; it holds the **shape** (command pattern or URL form), not the per-branch instance the PR
carries. **Absent means `none`** — no level is claimed for the project. Ranked levels and the
disclosure rule (`link` > `running` > `command` > `attended` > `none`; take the highest the project
supports; disclose at `command` or below) are defined in `rubric/review-discipline.md` — cite that
doc rather than restating the table here.

The default is the honest level the repo evidences, or **`none`** when nothing is detectable —
disclose any degradation per the show-it contract. NOTIFY: record the level in the set-up output and
carry it into the hero's `## Setup disclosures` section per the §2 carrier note and the run
continues. Set-up still **completes**; the owner may change
the declaration via `/superheroes:configure`.

To persist a declaration when the owner supplies one in this turn (multi-line prose on stdin):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
printf '%s\n' '<Level/What-the-owner-does/Notes prose>' | \
  python3 -B "$ROOT_DIR/lib/core_md.py" write-show-it --cwd .
```

**Read the result, don't assume success.** `write-show-it` returns `{action, reason?}`.
Only `written` or `noop` means the Show-it declaration was saved — surface any other
`action` (`refused`, `deferred`, `behind`) to the owner with its `reason`; the command
exits 0 either way, so check `action`, not exit status.

An empty stdin body clears the section and returns the project to `none`.

<!-- /decision-point: id=configure-setup-show-it -->

## 4.5 — Engine preferences — per-role defaults (FR-11/12/13/14)

<!-- decision-point: id=configure-setup-engine-preferences mode=notify kind=interview-step default="reviewer/implementer/pilot claude; briefCheck codex" carrier=review-crew-layer -->

After the verify command (§3) is set — external implementers are verify-gated, so this must follow it —
bring **Codex** and/or **Cursor** into the loop per role on the owner's word. The **primary path**
is the named provisional defaults — **reviewer**, **implementer**, and **pilot** → `claude`;
**briefCheck** → `codex` (the cross-vendor default — a Claude brief-check is a disclosed
degradation). NOTIFY: probe availability, record the per-role defaults (or owner overrides from
this turn) into `enginePreferences` and disclose the picks in the set-up output and carry them
into the hero's `## Setup disclosures` section per the §2 carrier note, and the run continues.
Follow-up: `/superheroes:configure`.

1. **Availability (FR-11).** Probe both engines and show a readiness matrix — installed + signed in, or
   what to fix:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 -B "$ROOT_DIR/lib/engine_detect.py"   # JSON verdict per engine: installed/authed + remediation
   ```
   A not-ready engine is shown with its next-command remediation; it is never offered as ready.

2. **Per-role preference (FR-12).** Record the provisional defaults (or owner picks from this turn)
   into `core.md`'s machine block
   `enginePreferences: {reviewer, implementation, briefCheck, pilot}` via `core_md` (schemaVersion 2).
   Optionally, `enginePreferences.seatPins` holds a per-review-panel-seat pin map (vendor required; model and effort optional per seat).
   An absent block reads as `claude` for every role **except `briefCheck`, which falls open to
   `codex`** (the cross-vendor default — a Claude brief-check is a disclosed degradation).
   When Codex is selected and no concrete model pin exists, explain the effective GPT-5.6 defaults.
   Codex tier map: haiku=gpt-5.6-terra, sonnet=gpt-5.6-terra, opus=gpt-5.6-sol.
   `max` effort is owner opt-in only (never a default).

3. **Show the build authorization — never apply it (FR-13).** If an external **implementation** engine
   is chosen, an external autonomous write needs a one-time owner grant. Show the exact snippet and where
   it goes; do **not** write it:

   ```bash
   python3 -B "$ROOT_DIR/lib/engine_authz.py" snippet --host claude --engine <codex|cursor>
   # prints the autoMode.allow block + its location (.claude/settings.local.json). SHOW it; never write it.
   ```

4. **Test dispatch (FR-14), bounded by the stall limit (UFR-5).** Run the test dispatch **only** when
   the owner grants authorization in this turn; when no authorization is present, leave the external
   implementation engine **not-ready**, disclose that in `## Setup disclosures`, and continue — do not
   block set-up:

   ```bash
   python3 -B "$ROOT_DIR/lib/engine_authz.py" test-dispatch --engine <codex|cursor> --cwd .
   # -> {"engine":E,"ok":true}  (ready)
   # -> {"engine":E,"ok":false} (denied or no-response bounded by the UFR-5 limit -> falls open to
   #    Claude; tell the owner how to enable, leave the engine not-ready with a retry instruction)
   ```
   For Codex, this probes the GPT-5.6 Sol capability explicitly as well as the host write grant, so
   an authenticated CLI that is too old for GPT-5.6 remains not-ready.
   A failed or timed-out test dispatch leaves the engine **not-ready** — builds and mechanical fixes fall
   open to Claude until it works. Never present a not-working engine as ready.

**Set-up posture.** Take the strict/provisional posture: probe and record what is detectable, but
never block and never apply the authorization — leave any external implementation engine not-ready
until the owner grants and tests it via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-engine-preferences -->

## 4.6 — Review-discipline CLAUDE.md — offer recorded, not written unasked

<!-- decision-point: id=configure-setup-claude-md-section mode=notify kind=ask-user-question default="never write the project CLAUDE.md unasked; record the offer as un-made" carrier=review-crew-layer -->

When the storage mode decided in §1 is **in-repo**, **never write** the project's `CLAUDE.md`
unasked — the band's review-discipline section (source of truth:
`$ROOT_DIR/rubric/review-discipline.md`) is owner-gated. NOTIFY: record the offer as **un-made** in
the set-up output and carry it into the hero's `## Setup disclosures` section per the §2 carrier
note and the run continues. The owner may append it
via `/superheroes:configure` (show the text before writing; idempotent — an existing `Review
discipline` heading means report-and-skip). **Never offer this in out-of-repo mode** — that mode
exists to keep the repo free of superheroes traces; there the SessionStart bootstrap note is the sole
carrier. A skipped offer still completes set-up; it is not persisted as a hero decline, so it
remains available on the view-and-tune menu.

<!-- /decision-point: id=configure-setup-claude-md-section -->

## 5 — Secrets stay out of shared calibration (NFR)

Any hero credential (such as test-pilot's sign-in) records **only non-secret references — the names
of environment variables, never their values** — into committed or collaborator-visible
calibration. This is test-pilot's existing rule; preserve it.

## Recovering an interrupted set-up (UFR-7)

<!-- decision-point: id=configure-setup-recovery mode=notify kind=ask-user-question default="report what is missing; do not offer to finish" carrier=review-crew-layer -->

If `route` reported "incomplete set-up" — the storage mode was recorded but not every light layer
was written (a prior run was interrupted) — do **not** present the project as healthy. NOTIFY:
report what is missing in the set-up output and carry it into the hero's `## Setup disclosures`
section per the §2 carrier note, and the run continues. The owner may finish the remaining layers
via `/superheroes:configure`.

<!-- /decision-point: id=configure-setup-recovery -->
