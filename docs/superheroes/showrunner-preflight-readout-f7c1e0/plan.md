---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: showrunner-preflight-readout-f7c1e0
issue: null
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.5.0"
created: "2026-07-03"
updated: "2026-07-03"
---
# Showrunner preflight readout — Plan

## Overview

The showrunner already runs a deterministic, zero-token pre-flight gate (`preflight.py`)
before it hands the run to the Workflow bundle, and it already renders a zero-token
*end-of-run* readout (`run_readout.py` + `readout.py`). This work adds a third
deterministic surface between those two: a **launch-time preflight readout** that shows,
in plain language, exactly what the confirmed run will dispatch — engine, model, and
effort per phase/role — plus external-engine authorization, calibration provisional-ness,
the verify command, and the storage mode and doc locations. The owner reads it, may
override any overridable role's engine/model/effort for this run, then confirms; only then
does the first agent dispatch.

The strategy is **assemble-from-the-same-resolvers, freeze-at-confirm, dispatch-from-frozen**.
The readout is not a new description that could drift from dispatch: it is built by calling
the exact resolvers the run already uses to pick a model (`model_tier`) and an engine +
effort (`engine_pref`), reading the exact authorization probes the run already trusts
(`engine_detect`), and the exact verify/storage/calibration readers the band already has
(`verify_command_cli`, `mode_registry`, `core_md`). A pure `assemble()` produces a plain
data structure (the "readout snapshot"); a pure `render()` prints it; the interactive
confirm/override loop lives in the showrunner *skill* (the one interactive surface — the
bundle runs sandboxed and cannot prompt). On confirm, the snapshot — including any
per-run overrides — is frozen and threaded into the run as the authoritative dispatch
source, so every phase dispatches with the value the owner saw. This mirrors the band's
established pattern: pure Python deciders do the judgement, the skill does the narration
and the one human touchpoint, and the accuracy guarantee comes from *sharing the
resolver*, never from a second copy of the dispatch picture.

## Goals & non-goals

**Goals** (from the spec):

- Render a scannable, zero-token, deterministic readout at launch — after the existing
  pre-flight gate passes and before the first dispatch — of every phase/role's engine,
  model, and effort (FR-1, FR-2, NFR cost/determinism/scannability).
- Show the orchestration role as session-inherited-and-expected, and flag any *other*
  session-inherit as unexpected rather than dropping it (FR-3, UFR-4).
- Show, per external engine the run would use, whether it is authorized, and note the
  Claude fallback when it is not — for both configured and overridden engines (FR-4).
- Label each setting configured-vs-default and flag a provisional calibration (FR-5).
- Show the verify command (or "unverified") and the storage mode + doc read/write
  locations (FR-6, FR-7).
- Gate dispatch behind explicit confirmation; freeze the confirmed snapshot so config
  edited after the render never changes what dispatches; re-render on relaunch/resume
  (FR-1, FR-8, FR-9).
- Let the owner override any overridable role's engine/model/effort before confirming;
  re-render marking the override; dispatch on the override for this run only; record the
  override durably; reapply + re-validate it on relaunch (FR-10 through FR-14).
- Degrade, not fail, on a single unresolvable setting (mark "unavailable", still confirm);
  fail closed only when *nothing* assembles; show an unknown value raw + "unrecognized"
  (UFR-2, UFR-3, UFR-5); reject an invalid override with the accepted values (UFR-6);
  abort cleanly on decline with no side effects (UFR-1).

**Non-goals** (deliberately excluded here — several restate the spec's Out-of-scope):

- The threat-model / scope-exclusions block of the readout — deferred (spec Out of scope).
- Any surface other than the showrunner launch — no on-demand re-print flag, no
  `configure` view. The phase enumeration is built reusable so those can adopt it later,
  but they are not built here.
- Fixing the #160 inheritance bug — it landed as #163; this work only reads its result.
- Overriding anything other than a role's engine/model/effort — verify, storage, and
  doc-locations stay read-only in the readout.
- Seeding overrides from launch flags/arguments — overrides are entered only at the
  confirmation gate this version.
- Changing the saved project calibration — that stays `configure`'s job.
- Any change to the pass/fail pre-flight gate's checks or remediations — this supplements
  that gate, it does not touch it.
- Per-phase token/cost accounting in the readout — separate work (#130).

## Architecture

The readout slots into the showrunner **Start** flow as a new step 1.5, between the
existing pre-flight gate (SKILL step 1) and the bundle launch (SKILL step 2):

```
launch → preflight.py gate (unchanged)         [deterministic pass/fail — SKILL step 1]
           │ ok:true
           ▼
       preflight_readout.assemble(work_item, root, run_overrides)   [NEW, pure, zero-token]
           │  → snapshot (plain dict: phases[], engines{}, calibration, verify, storage, degraded[])
           ▼
       preflight_readout.render(snapshot)       [NEW, pure] → terminal text
           │
       ── skill confirm/override loop ──         [SKILL, the one interactive surface]
           │   confirm → freeze snapshot, persist run overrides, thread frozen snapshot in
           │   override → validate, re-assemble with the override, re-render, re-confirm
           │   decline → abort, no side effects (UFR-1)
           ▼
       bundle launch (Workflow tool)             [SKILL step 2, unchanged plumbing]
           │   reads the frozen snapshot as the dispatch source of truth (FR-8/FR-12)
```

The design has three layers, each matching an existing band boundary:

1. **A pure assembler + renderer** (`preflight_readout.py`) — a new `lib/` module in the
   deterministic-decider family alongside `preflight.py`, `run_readout.py`, `readout.py`.
   It calls the *same* resolvers the run dispatches through (never a parallel table), and
   returns a JSON-able snapshot. It never dispatches an agent, never prompts, never writes
   (the durable override write is a separate seam, below). A JSON `main()` mirrors
   `preflight.py`'s CLI so the skill can shell it.

2. **The interactive confirm/override loop in the showrunner skill** — the bundle runs in
   a sandbox and cannot prompt (that is why `preflight.py` is already shelled from the
   skill, not the bundle). The skill shells `assemble`/`render`, prints the readout, and
   uses the host's ask primitive (`AskUserQuestion` on Claude) for confirm / override /
   decline. Every *judgement* stays in the pure module; the skill only narrates and
   carries the one human touchpoint — the band's standing division of labor.

3. **A durable per-run override record + a frozen-snapshot handoff** — the accepted
   overrides and the frozen render are recorded with the run (control-plane run record,
   §4.2 store) so they outlive one launch (FR-13) and are reapplied + re-validated on
   relaunch (FR-14), and so the bundle dispatches from the frozen values, not from
   re-reading config that may have changed (FR-8).

The whole surface is **read-mostly and deterministic**: `assemble` reads config through
existing readers; the only writes are the durable override record and the frozen snapshot,
both keyed to the run. It satisfies the spec's zero-token / determinism / no-drift NFRs by
construction, because there is exactly one code path from "what will dispatch" to "what the
readout shows" — the shared resolvers.

## Components & interfaces

**`lib/preflight_readout.py` (new — the pure core).** Design-altitude interface (exact
field names finalize in Tasks):

- `enumerate_dispatch(...) -> [ {phase, role, roleLabel, engine, model, effort, kind} ]` —
  the phase/role roster (FR-2). Built by walking the *same* phase list the spine drives
  (`PHASES = ['plan','review-plan','tasks','review-tasks','workhorse','review-code',
  'draft-PR','test-pilot','mark-ready','ship']` in `showrunner.js`) and, per phase, the
  roles it dispatches (author for plan/tasks; reviewer for the review phases; builder +
  per-task reviewer + fixer + final reviewer for build; deep reviewer for review-code;
  orchestration for test-pilot; fixer-on-CI-failure for ship). Each role's model comes from
  `model_tier.resolve_model(role, overrides, context)` and its engine + effort from
  `engine_pref.resolve_engine(role_kind, prefs)` / `resolve_effort(engine, role_kind,
  effort_overrides)`. This roster is the reusable piece a future `configure` view can adopt
  (spec Out-of-scope note), so it takes its inputs (prefs, tier overrides, run overrides)
  as arguments rather than reading disk itself — the disk reads live in `assemble`.
- `assemble(work_item, root, run_overrides=None) -> snapshot` — reads calibration once
  (`core_md.read` for enginePreferences + status; `model_tier_overrides.load_overrides`
  over the resolved review-crew profile for the `## Model tiers` block; `engine_detect.probe`
  for the authorization matrix; `verify_command_cli.resolve_command`; `mode_registry`
  read + `definition_doc` doc-dir resolution), then calls `enumerate_dispatch`, applies
  `run_overrides`, and returns the snapshot: `{workItem, phases[...], externalEngines{...},
  calibration{status, provisional}, verify{command|unverified}, storage{mode, docsPath},
  degraded[...], version}`. Each phase entry carries `configuredOrDefault`, an
  `inherit`/`expected`/`unexpectedInherit` marker (FR-3/UFR-4), an `unrecognized` marker
  (UFR-5), an `unavailable` marker + reason (UFR-2), and an `overridden` marker (FR-11).
  A per-field read that raises is caught and recorded in `degraded` with the field marked
  `unavailable` (UFR-2); assembly only fails outright — returning a sentinel `assemble`
  couldn't build anything — when it cannot produce *any* usable frame (UFR-3).
- `render(snapshot) -> str` — pure text rendering (the spec's UI sketch is the target
  shape: a phase/role table, then External-engines / Calibration / Verify / Storage lines).
  Kept ≤40 lines for the default pipeline + one external engine (NFR scannability); an
  engine→model display rule maps `codex → gpt-5.5`, `cursor → composer` (from
  `engine_adapter._CODEX_MODEL` / `_CURSOR_MODEL`) and `claude → the tier model`; an
  unknown engine/effort renders raw + "unrecognized".
- `validate_override(role, field, value, snapshot) -> {ok, accepted|acceptedValues, reason}`
  — pure; `ok:false` with the accepted set for an invalid engine/model/effort (UFR-6) or a
  non-overridable role (the orchestration role, FR-10); `ok:true` echoing the concrete value
  otherwise. The accepted sets come from the resolvers' own domains
  (`engine_pref.ENGINES`, `model_tier_overrides.KNOWN_MODELS`, the engine's effort tokens).
- `main(argv)` — JSON CLI (`assemble` → snapshot JSON; `render` → text; `validate-override`
  → verdict JSON), so the skill shells the verified interface exactly as it shells
  `preflight.py` today. **Contract:** exit 0 with a snapshot even when `degraded` is
  non-empty (UFR-2 is not a launch failure); a non-zero exit + reason only for total
  assembly failure (UFR-3).

**`lib/run_overrides.py` (new — the durable override seam, or a small addition to an
existing run-record module).** `read(work_item, root) -> {overrides, frozenSnapshot|None}`
and `write(work_item, root, overrides, frozenSnapshot)` against the control-plane run
record (§4.2 store, the same substrate the run's journal/checkpoint already use). Overrides
persist as `{role: {engine?, model?, effort?}}`. On relaunch, `assemble` is passed the
recorded overrides and re-validates each against the *current* option set + authorization,
marking any now-invalid one flagged rather than silently applying it (FR-14). The frozen
snapshot is what the bundle dispatches from (FR-8).

**`skills/showrunner/SKILL.md` (changed — the interactive step).** A new **Start step 1.5**
between the pre-flight gate and the launch: shell `preflight_readout.py assemble|render`,
print the readout, then loop on the host ask primitive — confirm (freeze + persist +
proceed), override (validate → re-assemble → re-render → re-confirm), decline (abort, no
changes). The step reuses the existing "the skill carries the interactive touchpoint"
pattern already in the file for the pre-flight verdict.

**Spine dispatch read-side (changed — thread the frozen snapshot).** The bundle's
per-phase dispatch (`showrunner.js` → `model_tier.js` / `engine_pref.js` twins) gains a
frozen-snapshot lookup ahead of the resolver call: if the confirmed snapshot pins a
concrete value for this phase/role, dispatch uses it; a field the snapshot marked
"unavailable" has no pin, so that phase resolves normally at dispatch (FR-8 second clause,
UFR-2 second acceptance). This is the one spine change; it is additive (a pin-or-resolve
fork), leaving the resolvers themselves byte-unchanged.

**Interfaces reused unchanged:** `model_tier.resolve_model`, `engine_pref.resolve_engine`
/ `resolve_effort` / `load_engine_prefs`, `engine_detect.probe` / `decide`,
`model_tier_overrides.load_overrides`, `verify_command_cli.resolve_command`,
`mode_registry.read_registry`, `core_md.read`, `definition_doc` doc-dir resolution. The
readout adds no new resolver — it composes the existing ones.

## Data flow & data model

**Read path (assemble):** config on disk → existing readers (`core_md`,
`model_tier_overrides`, `engine_detect`, `verify_command_cli`, `mode_registry`,
`definition_doc`) → in-memory `prefs` + `tier_overrides` + `authz_matrix` + `verify` +
`storage` → `enumerate_dispatch` → per-role `{engine, model, effort}` → apply
`run_overrides` → **snapshot** (a plain JSON-able dict). No new persistent read model; the
snapshot is a derived, in-memory projection.

**Write path (confirm):** the accepted `run_overrides` map + the frozen `snapshot` are the
only new persisted data, written to the control-plane run record (§4.2 store, JSON, keyed by
work-item). Schema shape:

- `overrides`: `{ <role>: { engine?: str, model?: str, effort?: str } }` — sparse; only the
  fields the owner overrode.
- `frozenSnapshot`: the exact `assemble` output the owner confirmed, carrying a
  `version` field.

**Compatibility (one-way-door care):** the override record is a *new* additive key on the
run record — absent for every pre-existing run, so a run without it behaves exactly as
today (no overrides, resolve-at-dispatch). The snapshot carries a `version` so a future
shape change is detectable; an unreadable/older-version override record fails **open** to
"no overrides" (a cost/UX concern, never a correctness one — the run still resolves each
phase through the live resolvers), consistent with the band's fail-open posture for the
model/engine axis. This keeps the persisted addition a two-way door.

## How the requirements are met

- **FR-1 (render + wait):** SKILL step 1.5 renders after the `preflight.py` gate passes and
  blocks on the host ask primitive before launching the bundle; no dispatch precedes confirm.
- **FR-2 (per-phase/role engine·model·effort):** `enumerate_dispatch` walks the spine's
  `PHASES` and each phase's role set, resolving each through `model_tier` + `engine_pref`;
  the build phase yields four role lines (builder, per-task reviewer, fixer, final reviewer),
  a single-role phase yields one; no dispatching role is omitted.
- **FR-3 (orchestration inherits, expected):** the orchestration role resolves to
  `model_tier` `orchestrator` → `None` (inherit); the snapshot marks it `inherit` +
  `expected`; every other role carries a concrete model.
- **FR-4 (authz + Claude fallback, config or override):** `assemble` reads
  `engine_detect.probe`/`decide` for each external engine any role would use (configured
  *or* overridden), sets `externalEngines[engine].authorized`, and where a role's engine is
  unauthorized marks that role `fallbackToClaude` with the flagged engine — an override does
  not bypass this check (it re-runs authz on the overridden engine).
- **FR-5 (configured-vs-default + provisional flag):** each phase entry carries
  `configuredOrDefault` (set when the reader returned an explicit configured value, default
  when it fell back); `calibration.provisional` is `core_md.read(...).status != confirmed`.
- **FR-6 (verify or unverified):** `verify.command` from `verify_command_cli.resolve_command`;
  `"none"` renders as "unverified".
- **FR-7 (storage + doc locations):** `storage.mode` from `mode_registry`; `storage.docsPath`
  from the `definition_doc` doc-dir resolution (the same path `resolve-write` uses).
- **FR-8 (freeze at confirm, dispatch from frozen):** on confirm the snapshot is persisted
  and threaded into the bundle; the spine's pin-or-resolve fork dispatches each phase from
  the frozen value; a post-render config edit changes nothing (the frozen snapshot, not live
  config, is read); an "unavailable" field has no pin and resolves normally at dispatch.
- **FR-9 (relaunch/resume re-renders):** SKILL step 1.5 runs on every entry (Start is
  re-invocable); a relaunch re-assembles with current settings + recorded overrides and
  re-confirms.
- **FR-10 (override any overridable role):** the confirm loop accepts an override on any
  role whose `kind != orchestration`; `validate_override` rejects the orchestration role and
  accepts a valid value on any other role — including one previously shown "unavailable"
  (UFR-2) or "unrecognized" (UFR-5), which then takes the concrete overridden value.
- **FR-11 (re-render marks override, others unchanged):** an override triggers a re-assemble
  that carries the override into `run_overrides`; the overridden line gets `overridden:true`;
  every non-overridden line is unchanged from the prior snapshot (same inputs → same
  resolvers → same values — the determinism NFR guarantees it); the loop re-waits for confirm.
- **FR-12 (dispatch on overrides, saved calibration untouched):** the frozen snapshot carries
  the overrides; the spine dispatches on them; the durable write targets the *run* record, not
  the calibration profile, so `configure`'s saved values are unchanged.
- **FR-13 (durable overrides):** `run_overrides.write` persists to the run record; a park
  reads it back present.
- **FR-14 (reapply + re-validate on relaunch):** relaunch reads the recorded overrides,
  `assemble` re-validates each against the current option set + `engine_detect` authorization,
  marks any now-invalid/unauthorized one flagged (not silently applied), and re-confirms.
- **UFR-1 (decline aborts clean):** decline returns before any persist/launch — no agent, no
  branch/PR, run not marked started (the launch side effects all live *after* confirm).
- **UFR-2 (one field unresolvable → degrade + confirm):** a per-field read that raises is
  caught, the field marked `unavailable` (+ reason), recorded in `degraded`; `render` shows the
  rest; the loop still requires confirm; at dispatch that phase resolves normally (no pin).
- **UFR-3 (nothing assembles → fail closed):** if `assemble` cannot produce any usable frame
  it returns the failure sentinel; the skill shows the plain reason + remediation and does not
  launch (fail-closed, matching `preflight.py`'s posture).
- **UFR-4 (unexpected inherit shown, not dropped):** a non-orchestration role resolving to
  `None` (session inherit) is marked `unexpectedInherit` and rendered flagged, never omitted.
- **UFR-5 (unknown value → raw + unrecognized):** an engine/effort/model outside the display
  rules renders as-is with `unrecognized:true`; no line dropped; confirm still required.
- **UFR-6 (invalid override rejected):** `validate_override` returns `ok:false` with the
  accepted values; the confirm loop keeps the currently-effective value and does not proceed.
- **NFR accuracy/no-drift:** the snapshot is built from the same resolvers the run dispatches
  through; there is no second description — a config/override change moves both together.
- **NFR cost:** `assemble`/`render` are pure Python (like `preflight.py` and `run_watch.py`);
  no agent dispatch.
- **NFR determinism:** pure functions over unchanged config → identical snapshot → identical
  render.
- **NFR scannability:** `render` emits one line per phase/role of the default pipeline plus
  the four summary lines; bounded ≤40 lines for the default pipeline + one external engine —
  asserted by a test.
- **NFR privacy:** the readout is skill-terminal text only; nothing is written to a PR,
  comment, or shared log (the only writes are the local run record); verify/storage strings
  echo verbatim, owner-only, as the spec permits.

## Key decisions & alternatives

- **Decision:** Assemble the readout by calling the *same* resolvers the run dispatches
  through (`model_tier` / `engine_pref` / `engine_detect` / the existing readers), not a new
  readout-only description. · **Options weighed:** (a) share the resolvers [chosen]; (b) a
  separate readout config/template the owner maintains, rendered independently of dispatch. ·
  **Choice + why:** (a) is the only shape that satisfies the no-drift NFR *structurally* —
  option (b) makes the readout a hand-maintained copy that the spec explicitly forbids ("no
  separately maintained description that could disagree"). The strongest case for (b) is
  decoupling: the readout could evolve its wording without touching dispatch — but that is
  exactly the drift risk the spec names, so the coupling is the feature. · **Accepted
  downside:** the readout is now bound to the resolver signatures; adding a phase/role means
  extending `enumerate_dispatch` too, or the readout under-reports. This is caught by a test
  that asserts the roster equals the spine's `PHASES` roster. · **Reversible?** two-way (a
  pure module, swappable). · **Mode:** PROCEED (engineering-internal; the spec mandates it). ·
  **Escalated?** no.

- **Decision:** Freeze the confirmed snapshot and dispatch from it, rather than re-resolving
  live at each phase. · **Options weighed:** (a) freeze a snapshot at confirm + dispatch from
  it [chosen]; (b) re-resolve live at each dispatch and trust that config hasn't changed since
  the render. · **Choice + why:** FR-8 requires that a config edit *after* the render never
  changes what dispatches — "never a value the owner did not see." Only (a) guarantees that;
  (b) races the owner's own editor and would silently dispatch an unseen value. · **Accepted
  downside:** a persisted snapshot per run + the spine's pin-or-resolve fork — a small state
  addition and one new read on the dispatch path. · **Reversible?** two-way (the snapshot is
  additive; absent → resolve live, today's behavior). · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** Put the interactive confirm/override loop in the showrunner *skill*, not the
  bundle. · **Options weighed:** (a) skill-side interaction [chosen]; (b) teach the bundle to
  prompt. · **Choice + why:** the Workflow bundle runs sandboxed and cannot prompt — which is
  precisely why the existing `preflight.py` gate is already shelled from the skill. Following
  that seam keeps the bundle non-interactive and deterministic; (b) would require a new
  prompt-out-of-sandbox channel the band deliberately avoids. · **Accepted downside:** the
  interaction is prose in `SKILL.md`, not unit-testable Python; mitigated by keeping *every
  judgement* (assemble/validate/render) in the pure module and leaving the skill only the
  narration + host ask call. · **Reversible?** two-way. · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** Persist per-run overrides + the frozen snapshot on the **control-plane run
  record** (§4.2 store), not the calibration profile. · **Options weighed:** (a) run record
  [chosen]; (b) a per-run scratch file; (c) the calibration profile. · **Choice + why:** FR-13
  requires overrides to outlive a launch and FR-14 to reapply on relaunch — the run record is
  the exact substrate the run's journal/checkpoint already use and that resume already reads,
  so overrides ride the same durability + reconcile path with no new store. (c) is disqualified
  by the constraint that a per-run override must *never* touch saved calibration; (b) invents a
  parallel lifecycle the resume path would have to learn. · **Accepted downside:** the run
  record grows two keys; a schema-version guard is needed (handled: additive key + fail-open on
  an unreadable/older shape). · **Reversible?** two-way (additive keys; absent → no overrides).
  · **Mode:** PROCEED (persistence shape — internal; no owner-weighable product trade-off). ·
  **Escalated?** no.

- **Decision:** Fail **open** on an unreadable/older-version override record (→ "no overrides",
  resolve live), consistent with the band's model/engine fail-open posture, but keep the
  *readout assembly* fail-**closed** when nothing renders (UFR-3). · **Options weighed:** (a)
  split posture — override-record fail-open, whole-readout fail-closed [chosen]; (b) uniform
  fail-closed on any override-read error (block the launch). · **Choice + why:** a lost/garbled
  override is a cost/UX regression (the run resolves each phase capably through the live
  resolvers) — matching `model_tier`/`engine_pref`'s stated "wrong/absent tier is a cost
  concern, never a safety one"; blocking the whole launch on it (b) would be
  disproportionate. But UFR-3 explicitly wants *no run at all* when the readout can't be
  produced, so total-assembly failure stays fail-closed. · **Accepted downside:** a corrupted
  override record silently reverts to configured defaults rather than surfacing loudly; the
  owner re-enters the override at the (still-shown) readout. FR-14's re-validation already
  surfaces a *stale-but-readable* override, so only an *unreadable* one degrades quietly. ·
  **Reversible?** two-way. · **Mode:** NOTIFY — this is a defaulting choice an owner might have
  a mild preference on (surface-loudly vs quiet-revert). **Reverse path:** flip the
  override-read to surface-and-confirm before build if the owner prefers loud; **Expiry:** until
  the override-record reader is built (change is a one-line posture flip in that reader). ·
  **Escalated?** no — reversible, safely defaulted; recorded here as a heads-up.

- **Decision:** Reuse `engine_detect.probe` for the readout's authorization column rather than
  the *runtime write-probe* (`engine_authz.implementation_dispatch_allowed`). · **Options
  weighed:** (a) the read-only readiness probe `engine_detect` (installed + authed) [chosen];
  (b) the behavioral write-probe `engine_authz` that actually issues a throwaway write. ·
  **Choice + why:** the readout must cost zero model tokens and cause no side effects (NFR
  cost/privacy); `engine_detect` is a read-only CLI-status check, while `engine_authz`'s probe
  issues a real dispatch (a token cost + a workspace write) — wrong for a pre-launch, zero-cost
  readout. The build phase still runs the authoritative write-probe at its own dispatch, so the
  readout's readiness column is a faithful *forecast*, and any residual mismatch falls open to
  Claude exactly as today. · **Accepted downside:** the readout could show "authorized" yet the
  build's write-probe later denies (auth revoked between readout and build), in which case that
  role falls open to Claude at dispatch — a safe, already-handled fallback, and a rare window. ·
  **Reversible?** two-way. · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** Map engine → displayed model with a small static rule (`codex → gpt-5.5`,
  `cursor → composer`, `claude → the resolved tier model`), sourced from
  `engine_adapter._CODEX_MODEL`/`_CURSOR_MODEL`. · **Options weighed:** (a) import the adapter's
  model constants [chosen]; (b) re-hardcode the strings in the readout. · **Choice + why:** (a)
  keeps a single source of truth for the external-engine model id, so a future model bump in the
  adapter updates the readout automatically; (b) would be a second copy that could drift — the
  same anti-drift principle as the top decision. · **Accepted downside:** a light import
  coupling to `engine_adapter`. · **Reversible?** two-way. · **Mode:** PROCEED. · **Escalated?**
  no.

## Cross-cutting concerns

- **Security & privacy:** No new trust boundary, no new PII, no authn/authz change. The
  readout is read-only over local config and is shown only in the owner's own terminal (NFR
  privacy). It may echo owner-authored config (verify command, storage paths) verbatim — the
  spec explicitly permits this because the audience is the single owner who authored it; the
  spec's caveat (revisit redaction before ever routing readout content to a shared
  destination) is carried into the code as a comment at the render boundary, since routing
  elsewhere is out of scope here. The authorization column reads engine *readiness*
  (`engine_detect`) and never prints credentials (that module is already credential-safe).

- **Observability:** The readout is *itself* the observability surface this work exists to
  add — the owner reads exactly what will dispatch. For debugging the readout at 2am: the
  `assemble` JSON CLI can be run standalone (like `preflight.py --work-item …`) to dump the
  raw snapshot including the `degraded[]` list, so a "why did it show unavailable?" question is
  answered by inspecting that field and the per-reader error it records. No new logging/metrics
  are warranted — this is a local, synchronous, zero-token terminal tool.

- **Reliability & failure modes:** The readout depends on the existing config readers, each of
  which already fails soft (fail-open to defaults or "none"). `assemble` wraps each per-field
  read so one reader's failure degrades that one field to "unavailable" (UFR-2) rather than
  sinking the readout; only a total failure to produce any frame blocks the launch (UFR-3,
  fail-closed). The override record read fails open to "no overrides". No external service,
  no concurrency beyond the pre-flight gate's existing no-active-run check (which already runs
  first) — a second concurrent run is blocked before the readout renders, so the readout adds
  no new concurrency surface (spec Coverage: conflicting/simultaneous use → the gate handles it).

## Rollout & migration

N/A migration for existing data — the only persisted addition (per-run overrides + frozen
snapshot) is a **new additive key** on the run record, absent for every existing/in-flight
run, so no backfill and no schema migration of prior records is needed; an old run reads as
"no overrides" and behaves exactly as today. **Rollout / kill-switch:** the feature is the
new SKILL step 1.5 plus the spine's pin-or-resolve fork. Because a run with no frozen
snapshot resolves live (today's path), the capability is inert until a readout is confirmed
— there is no flag day. If the readout step needed to be disabled, the skill step is the
single removal point and the spine fork no-ops without a pinned snapshot; the spine change
is behavior-preserving when the snapshot is absent, which is the safe default and the
rollback state. No user-facing data is versioned beyond the snapshot's own `version` field.

## Risks & mitigations

- **Roster drift (the readout under-reports a phase/role):** because the readout enumerates
  the dispatch roster, a future spine change that adds a phase or a role could leave the
  readout silently missing it. *Mitigation:* a test asserts `enumerate_dispatch`'s phase set
  equals the spine's `PHASES` and that each phase's role lines match what that phase actually
  dispatches; the roster is derived from `PHASES`, not a hand-copied list, so a phase *add*
  surfaces in the test rather than in production. (Tasks pins the exact assertion.)
- **Freeze/dispatch divergence (the spine ignores the frozen snapshot for some phase):** the
  value of the freeze is void if a dispatch path doesn't consult it. *Mitigation:* the
  pin-or-resolve fork sits at the single per-phase resolve site the twins already funnel
  through (`model_tier.js`/`engine_pref.js` calls in `showrunner.js`); a smoke test confirms a
  pinned snapshot value is what dispatches and a config edit after freeze does not change it
  (FR-8 acceptance is directly testable).
- **Scannability regression as the pipeline grows:** the ≤40-line bound could silently break.
  *Mitigation:* a test asserts the rendered line count for the default pipeline + one external
  engine is ≤40; a growth beyond that fails the test and forces a rendering decision rather
  than a silent scroll.
- **Interactive loop is prose, not unit-tested:** the confirm/override loop lives in
  `SKILL.md`. *Mitigation:* every judgement it makes (assemble/validate/render) is pushed into
  the pure module with its own tests; the skill is left only the host ask call + branch, which
  is the minimum untestable surface — the same posture the pre-flight gate already takes.
- **Authz forecast vs runtime reality (revoked between readout and build):** covered under
  Key decisions (falls open to Claude at the build's own write-probe); low-severity, already
  handled — noted here for the pre-mortem record.

## Dependencies & assumptions

**Dependencies:**

- **#160 / PR #163 (session-model inheritance fix) — already landed** (merged to `main`
  2026-07-03). This work-item's base is `main` at or after #163; the readout reads each phase's
  configured setting and #163 is what makes each phase actually honor it, so the readout matches
  what runs. No further dependency work is blocking.
- The existing band readers and resolvers (`model_tier`, `engine_pref`, `engine_detect`,
  `model_tier_overrides`, `verify_command_cli`, `mode_registry`, `core_md`, `definition_doc`) —
  all present in `plugins/superheroes/lib/`; this work composes them, adds no new external
  package or service (no new dependency to justify).
- The control-plane run record substrate (§4.2 store) already used by the run's
  journal/checkpoint/resume — the override record rides it.

**Assumptions:**

- The owner is present and interactive at launch (the confirm gate assumes an interactive
  launch, matching how the showrunner is invoked today — spec assumption). If a future
  non-interactive launch mode is added, that mode must decide its own confirm policy; it is
  out of scope here.
- The deterministic pre-flight pass/fail gate runs first and has already blocked on unreadable
  config, so `assemble` runs over config that at least parses (spec assumption). This is why
  `config_resolves` staying in the pre-flight gate is a precondition, not re-checked here.
- The spine funnels every per-phase model/engine resolution through the `model_tier.js` /
  `engine_pref.js` twins (verified in `showrunner.js`), so the pin-or-resolve fork has a single
  site. If a phase resolved a model outside those twins, the freeze would miss it — the
  roster-drift test guards this by construction.
