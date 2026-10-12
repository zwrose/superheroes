---
superheroes: doc
schemaVersion: 1
docType: plan
workItem: codex-and-cursor-as-review-and-build-engines-5b60ca
issue: 38
size: large
status: approved
gates: {review: passed}
producedBy: "the-architect@0.3.0"
created: "2026-06-30"
updated: "2026-06-30"
---
# Codex and Cursor as review and build engines — Plan

## Overview

The band already resolves *which Claude model* a role runs at (`lib/model_tier.py`
`resolve_model(role) → "sonnet"|"opus"|"haiku"|None`) and injects that string into the
Workflow spine's `agent(prompt, {model})` leaves. This work adds one **orthogonal** axis
*above* that resolver — *which engine* runs a role: `claude` (today's path, unchanged),
`codex`, or `cursor` — chosen per role, independently, by the owner.

The strategy is a **leaf-level adapter swap, not a spine change.** The pieces that make
review and build sound — the `reviewPanel` shell + tally + synthesis + circuit breaker
(`review_panel_shell.js`, `panel_tally.py`, `loop_state.py`), the build loop
(`build_phase.js`), the verify gate (`verify_gate.py`), the audit journal (`journal.py`),
the managed build worktree (`buildtree.py`), the secret scrubber (`readout.scrub`), and the
owner-authority enforcer (`enforcer.py`) — all stay **byte-for-byte**. Only the handful of
leaf functions that *become a running worker* gain an engine branch: `engine == claude`
keeps calling `agent()`; `engine ∈ {codex, cursor}` shells the external CLI through the
spine's existing command-runner leaf, confined to a worktree, and returns the **same result
shape** (findings array for review, `{ok, signal, evidence}` for build). Because the return
shapes are preserved, everything downstream — the loop's verdict math, the verify gate, the
journal, the fail-closed park paths — is reused unchanged.

Two postures are kept strictly separate, mirroring what the codebase already does:
**engine *selection* fails open** (an unknown / unavailable / stalled engine silently
degrades to Claude — the exact posture `model_tier.py` documents for a bad tier: "a
wrong/absent tier is a cost concern, never a safety one"), while a **completed external
*result* fails closed** (a build or fix that fails or can't run verify stops the run; an
unauditable run stops; an unreadable or incomplete review is re-run on Claude, never
accepted as green). No new safety logic is invented for the fail-closed side — it reuses the
gates that already exist.

Onboarding lands in the existing `configure` front door: engine readiness detection modeled
on `gh_preflight.py`, a per-role preference persisted in `core.md`'s machine-readable block,
and a *show-but-don't-apply* step for the one-time write authorization (the owner adds an
`autoMode.allow` rule to their own `.claude/settings.local.json`; the band never writes it),
followed by a test dispatch.

## Goals & non-goals

**Goals (from the spec):**
- A per-role engine preference — reviewer engine and implementation engine, independent,
  each `claude|codex|cursor`, default `claude` (FR-1, FR-2, FR-12).
- Run the code-review panel on the chosen reviewer engine, emitting the **standard findings
  form**, driving the **same** review-and-fix loop (FR-3, Review-parity NFR).
- Perform the build role's work — the build and the mechanical fixes, including
  review-code's own auto-fix — on the chosen implementation engine (FR-4, FR-15).
- Verify-gate every external implementation result; audit every external action with
  engine + model/effort + verify result (FR-5, FR-6, Auditability NFR).
- Read-only review (FR-7); isolated in-place build/fix in the managed worktree (FR-8).
- Depth/effort tiers per engine — Codex high for review/build, low for mechanical; Cursor
  composer-only (FR-9, FR-10).
- `configure` onboarding: availability, preference, show-authorization, test-dispatch
  (FR-11–FR-14).
- The full fail-open (UFR-1/2/4/5) and fail-closed (UFR-3/6/7) unhappy-path set.
- Owner-authority boundary preserved for external producers (Constraints); secret hygiene
  of external output (Secret-hygiene NFR).
- Docs updated in the same change: the cross-engine contract note (CONVENTIONS §7), the
  build-engine contract (the `model_tier` docstring / the build leg), README, CONVENTIONS
  (DoD).

**Non-goals (deliberately excluded here):**
- **Teaching the manual/superpowers SDD build path to use an external engine.** The build
  axis lands on the **native `build_phase.js`** producer leg only. The manual bridged path
  is superpowers-driven (being removed under #111) and `model_tier.py` already exempts it
  ("Workhorse's Build leg… is NOT a consumer"). Recorded as a NOTIFY (Key decisions).
- **Re-implementing the host's permission classifier.** Authorization is *enforced by the
  host* (the owner-granted `autoMode.allow` rule); the band detects its absence behaviorally
  and falls open (UFR-4). We do not parse or shadow the host's allow-list.
- **Changing the loop's decision logic** (`loop_state`, `panel_tally`, `circuit_breaker`,
  `ship_gate`, `freshness`, `ci_loop`) — they are parity-locked deciders, reused, not edited.
- **Dynamic/cost-aware routing, usage telemetry (#24), non-composer Cursor models,
  test-pilot browser-fix on an external engine** — all explicit spec out-of-scope.
- **Multi-host authorization parity.** The authorization *snippet* is host-specific; it is
  resolved through the existing host-adaptation layer (§7.2) and demonstrated on the Claude
  Code host. Codex-host authorization parity is best-effort, consistent with §7.3 anti-scope
  (no new dual-mode burden). NOTIFY.

## Architecture

Three thin new units sit beside the existing dispatch seam; nothing downstream of a leaf
changes.

```
            OWNER PREFERENCE (core.md machine block: enginePreferences)
                          │
                 engine_pref (py + js twin)         ← NEW: which engine + what effort (fail-open→claude)
        resolve_engine(roleKind, prefs) → claude|codex|cursor
        resolve_effort(engine, roleKind, overrides) → effort flag
                          │
        ┌─────────────────┴──────────────────┐
   engine == claude                    engine ∈ {codex, cursor}
        │                                     │
   existing agent()                    engine_dispatch (js)  ← NEW: shell the CLI via the
   leaf (UNCHANGED)                          │                 spine's command-runner leaf,
                                             │                 cwd-confined, structured out
                                   engine_adapter.py (py)   ← NEW: build argv + parse result
                                             │            (deterministic, unit-tested)
                                             ▼
        ┌───────────── SAME RETURN SHAPE ─────────────┐
   review: findings[]  (rubric/review-base.md form)   build/fix: {ok, signal, evidence}
        │                                              │
   reviewPanel shell / review-code skill        build_phase.js loop
   tally · synthesis · circuit breaker          verify_gate · journal · buildtree
        (ALL UNCHANGED — consume the shape, not the engine)
```

The engine axis is consumed at **four leaf sites** (the only places a role becomes a running
worker), identified during grounding:

1. **Native spine reviewers** — `reviewCodeLeaves` in `showrunner.js:55–119`
   (`reviewerAgent`, `synthesisLeaf`, `fixStep`), driven by `review_panel_shell.js`.
2. **Standalone `/review-code` skill** — its markdown orchestrator dispatches the five
   bundled specialists + the fixer subagent (`skills/review-code/SKILL.md:116–132`).
3. **Native build worker + fixer + final review** — `build_phase.js:337`
   (`buildOneTask`), `:461` (fixer), `:470–489` (final review).
4. **`configure`** — the onboarding surface (readiness, preference, authorization, test).

Reviewer sites 1 & 2 route through the reviewer engine (read-only). Build/fix sites 1
(`fixStep`), 2 (the fixer subagent), and 3 route through the implementation engine. The
adapter contract is identical at every site, so one `engine_adapter.py` + one
`engine_dispatch.js` serve all of them.

**The external reviewer preserves the panel, not replaces it.** An external review runs the
*same five specialist personas* — one external dispatch per specialist, in parallel (the
panel is already `parallel([...])`), each handed its persona + the shared
`rubric/review-base.md`, each returning that specialist's findings slot. This keeps the
completeness check (`panel_tally` keys on per-reviewer presence → `cannot-certify` +
`missing[]`), the synthesis leg, and the circuit breaker working with zero change; a missing
or garbled specialist slot is exactly the `cannot-certify` signal UFR-7 hangs off.

## Components & interfaces

**`lib/engine_pref.py` + `lib/engine_pref.js` (NEW, Python source-of-truth + JS twin,
parity-tested like `model_tier`).** Pure, deterministic, fail-open.
- `resolve_engine(role_kind, prefs) → "claude"|"codex"|"cursor"`. `role_kind ∈
  {"review","build","fix"}` (review→reviewer engine; build/fix→implementation engine). A
  missing/unknown/malformed pref → `"claude"`. Mirrors `model_tier.resolve_model`'s fail-open
  contract exactly.
- `resolve_effort(engine, role_kind, overrides) → effort_token|None`. Defaults table
  (FR-9/FR-10): `codex` → `high` for `review`/`build`, `low` for `fix`; `cursor` → a single
  composer sentinel for all (exempt — one model). `claude` → `None` (the model tier already
  governs it). Owner override wins (same override-merge shape as `resolve_model`).
- Loaders: `load_engine_prefs(cwd, root) → {reviewer, implementation}` reads `core.md`'s
  machine block via `core_md.read`; absent block → `{claude, claude}`.
- *Error cases:* any read/parse failure → the all-`claude` default (fail-open, never raises).

**`lib/engine_adapter.py` (NEW, Python, deterministic + unit-tested).** The argv/parse core,
kept out of the model-driven layer so it is testable.
- `build_argv(engine, role_kind, effort, {cwd, schema_path, prompt_path}) → [argv]`.
  Read paths use the read-only sandbox (`codex exec --sandbox read-only …`,
  `cursor-agent … --mode plan`); write paths use workspace-write
  (`codex exec --sandbox workspace-write …`, `cursor-agent … -f`), always with an explicit
  model/effort so the developer's ambient CLI config never leaks (Config-determinism NFR).
  Exact flags are the Tasks'; the spike (memory `engine-dispatch-38-discovery`) verified them
  live (codex `0.141.0`, cursor-agent `2026.06.19`).
- `parse_result(engine, role_kind, stdout) → {ok, findings?|signal, evidence?}`. Codex
  review uses `--output-schema`; Cursor uses stream-json `raw_decode` of the last JSON
  object. Unparseable/empty → `{ok: false, reason: "unreadable"}` (drives UFR-2/UFR-7).
  `evidence` is constrained to the **structured, secret-free shape the native worker returns**
  (`{testFailed, testPassed}` booleans) — *never* raw external stdout/stderr — so the value
  threaded into the reused, unscrubbed journal `payload` at `build_phase.js:369` can carry no
  external free-text (Secret-hygiene NFR; see below). Any external free-text the adapter
  surfaces anywhere else (a notice, a PR comment) is `readout.scrub`-gated first.
- *Error cases:* returns a structured failure, never raises; the JS layer decides fall-open
  vs fail-closed.

**`lib/engine_dispatch.js` (NEW, spine leaf wrapper).** The single seam every JS call site
calls instead of `agent()` when the engine is external.
- `dispatchExternal({engine, roleKind, effort, prompt, cwd, schema}) → result`. Runs
  `engine_adapter.py build-argv`, executes the argv via the spine's existing command-runner leaf
  (`cmdRunner`/`exec`, `showrunner.js:541,649`), runs `engine_adapter.py parse-result`, and
  **journals** an `external_dispatch` event (engine, effort, verify-later marker, outcome)
  before returning the native worker's `{ok, signal, evidence}` shape.
- **Commit discipline (write roles) — the engine edits, the adapter commits.** The external
  engine is dispatched to **edit files only, not commit**. Before **each** external write dispatch — every build
  task **and every fix round** of the multi-round loop (`build_phase.js:401–467`) — the adapter
  **re-captures** the worktree HEAD (`git rev-parse HEAD` — call it `preSHA`, strictly *after*
  every prior task's *and* prior fix-round's landed commit). Capturing per-dispatch, not
  once-per-task, is load-bearing: it keeps a later round's stray-commit cleanup scoped to *that*
  round's commits, so it can never fold an earlier round's already-landed adapter commit for the
  same task. On the engine's **success signal only**, the **adapter is the sole committer**:
  it makes the single `Task-Id:`-trailered commit itself. Today no commit-making primitive
  exists — each Claude worker authors its own commit inside its `agent()` turn
  (`build_phase.js:339–340,462`), and `build_state.py`/`build_state_cli.py` only *parse* the
  trailer (read-only, `build_phase.js:344–357` `unmapped_commits`). So this adds a **small new
  committer step** whose one job is to emit that trailer; the Task-Id trailer string is
  **single-sourced** (a shared constant the committer and the existing `build_state` parser both
  reference) so the convention isn't silently forked across the JS↔Python boundary. If a
  mis-behaving engine left stray commits despite the instruction, the adapter `git reset --soft`
  **to the captured `preSHA`** (not an implicit target) — folding only *this dispatch's* commits
  into the index (every prior task's and prior fix-round's commit is before `preSHA`, so none can
  be in range), discarding no prior work — then makes its trailered commit; this is what backs the
  "UFR-12-safe" claim. Net: the
  downstream `unmapped_commits` gather never meets an untrailered external commit, the
  malformed-external-trailer case cannot arise, and the discard-on-failure path (UFR-2) reuses
  the existing `resetUncommitted` primitive with no new hard-reset (see UFR-2).
- *Timeout:* wraps the run in the finite UFR-5 limit (default in `engine_pref`, test-settable
  via the same override channel); a stall → `{ok:false, reason:"timeout"}`.
- *Test seam:* `dispatchExternal` (UFR-1/2/5) and `implementation_dispatch_allowed` (UFR-4)
  are unit-tested through the project's proven **global fake-`agent()`/`cmdRunner` stub**
  (the pattern in `lib/tests/showrunner_reviewcode_smoke.js`), so the fail-open/fail-closed
  paths are exercised **without a live external CLI**.
- *Error cases:* any non-success → the caller runs the existing fall-open-to-Claude path.

**`lib/engine_detect.py` (NEW, readiness — the `gh_preflight.py` shape).**
- `probe(root) → {codex:{installed,authed,error}, cursor:{installed,authed,error}}` —
  best-effort world-read (`shutil.which` + each CLI's cheap whoami/auth check), never raises,
  never prints credentials.
- `decide(probe, engine) → (ok, cause, remediation)` — pure, fail-closed, operator-friendly
  next-command remediation (FR-11).

**`lib/engine_authz.py` (NEW, the show-but-don't-apply helper + run-time preflight).**
- `authorization_snippet(host, engine) → text` — the exact `autoMode.allow` block for the
  owner to paste into `.claude/settings.local.json`, resolved per host via §7.2. Configure
  *shows* it; never writes it (FR-13, Authorization NFR).
- `implementation_dispatch_allowed(cwd) → bool` — the run-time preflight: a trivial
  throwaway external *write* to observe allow vs deny before any real build/fix write.
  Denied/failed → the run's implementation role falls open to Claude (UFR-4). Also reused by
  configure's test dispatch (FR-14). **Proxy fidelity:** the host authorization grant is
  **host-global (it matches the dispatch command, not a path)**, verified live in discovery —
  so a probe write is a sound predictor of the worktree write; to keep the proxy exact even if
  that ever changes, the probe runs **inside the managed worktree** (not an unrelated temp
  dir). A wrong assumption would only *fall open* to Claude (a cost, never a corrupt or
  half-written result), so the failure mode is safe by construction.

**`core.md` machine block (EXTEND, `core_md.py`).** Add `enginePreferences:
{reviewer, implementation}` to the JSON block; **bump its `schemaVersion` 1 → 2**
(additive — an absent block reads as `{claude, claude}`; older files upgrade in-memory,
newer read `behind=True`, never auto-rewritten — the existing `core_md` UFR-2/UFR-3 policy).

**`lib/journal.py` (EXTEND).** Add `"external_dispatch"` to `EVENT_TYPES`. Callers pass
`world`/`detail` (auto-scrubbed fail-closed) and a non-secret `payload`
(`{engine, effort, roleKind, verify, outcome}`). A failed durable append raises
`DurableWriteError` → the orchestrator parks (UFR-6) — unchanged.

**Unchanged, reused as-is:** `review_panel_shell.js`, `panel_tally.*`, `loop_state.*`,
`loop_synthesis.*`, `circuit_breaker.*`, `verify_gate.*`, `verify_command_cli.py`,
`buildtree.py`, `readout.scrub`, `enforcer.py`, `ship_gate.py`, `freshness.py`, `ci_loop.py`.

## Data flow & data model

**New persisted data — one field.** `core.md`'s machine block gains
`enginePreferences: {reviewer: "claude|codex|cursor", implementation: "claude|codex|cursor"}`.
It lands wherever `core.md` already lives (in-repo `.claude/superheroes/core.md`, or the
project store in global mode) via `core_md.read/write` — no new store, no new key. Backward
compatibility: a v1 block (no field) reads as both-`claude`; forward compatibility: the
`schemaVersion` bump means an older plugin encountering a v2 block fails closed with the
existing "update the plugin" message (§6.4) rather than silently dropping the preference.

**New transient data — the audit entry.** Each external action appends one
`external_dispatch` line to the per-issue `events.jsonl` (`journal.append`) carrying engine,
effort/model, the verify result, and outcome. This is append-only runtime state (§4), not a
schema others read; no migration.

**No other data model is touched.** Findings keep the `rubric/review-base.md` shape; the
build worker keeps `{ok, signal, evidence}`; the branch/worktree/PR model is unchanged.

## How the requirements are met

**FR-1 / FR-2 / FR-12 (per-role preference; default Claude; recorded by configure):**
`enginePreferences` in `core.md`, written by configure, read by `engine_pref.load_engine_prefs`;
absent → `{claude, claude}` (`resolve_engine` fail-open default). Reviewer and implementation
are independent keys.

**FR-3 + Review-parity NFR (review on the engine, standard findings form):** the reviewer
leaf/subagent (sites 1 & 2) routes to the reviewer engine via `dispatchExternal`
(read-only), running the five specialist personas against `rubric/review-base.md` and
emitting the standard findings array. The **same** `reviewPanel` shell / synthesis /
tally / circuit breaker consumes it — parity is structural because only the leaf changed.

**FR-4 + FR-15 (build and mechanical fixes — incl. review-code's auto-fix — on the engine):**
the build worker (`build_phase.js:337`), the build fixer (`:461`), and both fix leaves
(spine `fixStep` and the standalone skill's fixer subagent) route to the implementation
engine via `dispatchExternal` (write). The review stays on the reviewer engine (read-only);
the fix that resolves a finding runs on the implementation engine — exactly FR-15's split.

**FR-5 + UFR-3 (verify-gate build & fix; fail-closed on failure/unrunnable):** the external
write result flows through the **existing** verify path — `build_phase.js` runs
`verify_gate.run_verify` (command via `verify_command_cli.resolve_command`, from `core.md`);
the review-code loop's `legKind:{code:true}` runs verify after a fix. Pass → accept; fail /
timeout / unrunnable → the existing halt/park (draft PR retained), which is UFR-3.

**FR-6 + Auditability NFR + UFR-6 (audit each action; stop if unauditable):** every
`dispatchExternal` writes an `external_dispatch` journal line (engine + effort + verify +
outcome) *before* the change is accepted; a `DurableWriteError` parks the run (UFR-6). No
external action executes without a recorded entry.

**FR-7 (read-only review) / FR-8 (isolated implementation):** review argv uses the
read-only sandbox (`--sandbox read-only` / `--mode plan`) → the tree is unchanged
(FR-7). Write argv uses workspace-write with `cwd` = the managed build worktree
(`buildtree.reclaim_or_create().path`) → changes are confined to that worktree/branch
(FR-8).

**FR-9 / FR-10 (depth tiers; Cursor composer-only):** `engine_pref.resolve_effort` — Codex
`high` for review/build, `low` for fix; Cursor a single composer model (exempt). Owner
override via configure; the effort used is in every audit entry (FR-6).

**FR-11 / FR-13 / FR-14 (configure onboarding):** `engine_detect.probe/decide` renders the
readiness matrix (FR-11); `engine_authz.authorization_snippet` shows the exact
`autoMode.allow` grant and where, without applying it (FR-13); `engine_authz`'s test
dispatch reports success / failure / no-response (the last bounded by the UFR-5 limit),
never presenting a not-working engine as ready (FR-14).

**UFR-1 (unavailable / bad override → fall open):** `resolve_engine` returns `claude` for an
unknown engine; a dispatch that can't run as configured (not installed, rejected
model/effort) returns a failure → the caller runs on Claude + one non-blocking notice.

**UFR-2 (mid-run fail/stall → discard partial, redo on Claude clean):** because the adapter
commits only on the engine's success (Commit discipline, above), a failed or stalled write
leaves **only uncommitted edits** — discarded by the **existing** `resetUncommitted`
primitive (`build_phase.js:286`, `git checkout -- . && git clean -fd .`), which honors the
UFR-12 invariant "never discard a commit" (no commit ever existed, so no new hard-reset is
introduced and no owning module is reinvented). The caller then redoes that unit on Claude; a
review failure drops partial output and re-runs. One notice; loop not blocked. (A completed,
*committed* external write that later fails verify is **not** this path — it is UFR-3's
fail-closed park with the commit retained and the PR left draft.)

**UFR-4 + Authorization NFR (no authorization → no external write; both build & fix on
Claude):** `engine_authz.implementation_dispatch_allowed` preflights before the first
external *write*; denied → the implementation role (build **and** fixes) runs on Claude for
the run + a "how to enable" notice. Review (read-only) needs no authorization.

**UFR-5 (finite stall limit, configurable, test-settable):** `dispatchExternal` wraps every
run in the finite default from `engine_pref` (test-settable via the override channel); a
stall past it → abandon + fall open. Always finite.

**UFR-7 (unreadable / incomplete review → treat as failure, re-run on Claude):** an external
review that yields empty/unparseable output, or a panel missing/garbling a required
specialist slot, surfaces through the **existing** `cannot-certify` + `missing[]` detection;
the engine wrapper maps that to *discard + re-run the panel on Claude*, whose findings drive
the loop — never recorded as a clean pass.

**Secret-hygiene NFR:** the rule is **scrub external free-text at the trust boundary — the
adapter — so it is clean at every downstream surface**, not scrub-at-each-consumer. Concretely:
- `engine_adapter.parse_result` **scrubs the external reviewer's finding free-text**
  (`body`/`suggestion`) via `readout.scrub` before it enters the standard findings form. This
  is what covers the standalone `/review-code --post` path, which builds the PR-comment body
  straight from `body`/`suggestion` and posts via `gh api` with **no scrub of its own**
  (`skills/review-code/reference/auto-fix-loop.md`) — the one surface the native
  `readout.build_readout` handoff doesn't gate. With external findings pre-scrubbed at the
  adapter, that public PR comment carries no external secret in the clear.
- The build adapter's `evidence` is constrained to the structured, secret-free
  `{testFailed, testPassed}` shape (Components → `engine_adapter.parse_result`), so the one journal
  field `journal.append` writes **as-is** (`payload`, §4.6) — `payload.evidence` at the reused
  `build_phase.js:369` call — never receives external free-text.
- `journal.append` scrubs `detail`/`world` fail-closed; any external free-text the adapter
  surfaces directly (a notice) is `readout.scrub`-gated.

**Config-determinism NFR:** `engine_adapter.build_argv` always passes an explicit model/effort;
the audit shows the band's value, not the developer's ambient CLI default.

**Owner-authority boundary (Constraints):** external engines are write-*confined*
(workspace-write, no remote authority) and the band performs every push/PR/merge through its
existing `enforcer.py`-gated path. An external producer therefore cannot merge, force-push, or
push-to-default (see Key decisions + Risks for the confinement guarantee and its residual).

**DoD — docs:** the same change updates the CONVENTIONS §7 cross-engine contract note, the
build-engine contract (the `model_tier.py` docstring's "not a consumer" line + a note that the
native build leg is now an engine consumer), README, and CONVENTIONS.

**DoD — verification strategy (what CI covers vs. what a live run covers).** CI is
`ubuntu-latest` + pytest with **no external CLI installed or signed in**, so the DoD test set
splits cleanly:
- **Automated (the pytest/validation gate):** the preference round-trip, **including at least
  one mixed-engine configuration (reviewer ≠ implementation, e.g. reviewer=Codex /
  implementation=Cursor per FR-15)** so a same-engine-only fixture set can't mask a cross-engine
  routing bug; `engine_pref` fail-open (unknown/unavailable/stalled) via its JS↔Python parity
  fixtures; `engine_adapter` `build_argv`/`parse_result` against **canned per-engine stdout
  fixtures** — including a well-formed review that reports a Critical, and the empty/garbled/
  unreadable cases that drive UFR-7 — asserting the findings enter the `reviewPanel` shape
  (per-engine *parity of form*); build-then-verify, the fail-closed trio, owner-authority
  boundary, and secret-scrub (including the external-finding-free-text → `--post` PR-comment
  path), all via the existing tested seams + the fake-`agent()`/`cmdRunner` stub; the
  **commit-discipline multi-round fold invariant** — a fixture where a fix-round dispatch leaves
  a stray commit and the assertion is that the per-dispatch `preSHA`-scoped `git reset --soft`
  folds only *that* round's commits while a prior round's already-landed `Task-Id`-trailered
  commit survives (guards UFR-12 across fix rounds — the mechanism the Commit-discipline decision
  calls load-bearing); and availability detection (`engine_detect` with an injected probe, the
  `gh_preflight` pattern).
- **Live (a one-time manual/dogfood verification, documented as such — the pattern this
  project already uses for live-dependent features, e.g. the #115/#102/#112 eval runs):** the
  spec's FR-3/DoD acceptance that a **real** Codex review pass *and* a **real** Cursor review
  pass each surface the seeded path-traversal defect as a Critical against a live process; a
  real build on each engine; and **the Cursor remote-confinement acceptance — that a live Cursor
  implementer cannot reach the remote (network-off); if that cannot be shown, the fallback is
  to default Cursor implementation to the diff-apply path** (Risks). This bucket is **not** wired
  into CI (it can't be) and is **not** silently dropped — Tasks records it as an explicit
  live-verification step.

## Key decisions & alternatives

- **Decision:** Engine axis as a **leaf-adapter swap above `model_tier`**, spine unchanged.
  · **Options weighed:** (a) new orthogonal `engine_pref` resolver + per-leaf engine branch,
  reusing `reviewPanel`/`build_phase`/verify/journal as-is; (b) fold engine *into*
  `model_tier` (make `resolve_model` return an `{engine, model}` pair and thread it
  everywhere); (c) a parallel "external run" framework beside the native spine.
  · **Choice + why:** (a). Engine and model are genuinely orthogonal (an engine has its own
  depth knob), and the spine already isolates dispatch to a few `agent()` leaves — so an
  additive resolver + a leaf branch is the smallest change that touches no decision logic.
  · **Accepted downside:** two resolvers to keep coherent (`model_tier` for Claude model,
  `engine_pref` for engine+effort) instead of one. · **Reversible?** two-way (additive; delete
  the branch to revert). · **Mode:** PROCEED. · **Escalated?** no.
  · **Runner-up case:** (b) would give one call returning a full dispatch spec — tidy — but it
  overloads a pure, widely-called cost resolver with a safety-bearing axis and forces edits at
  every model call site; rejected for blast radius.

- **Decision:** **Preserve the five-specialist panel** for external review (one external
  dispatch per persona, parallel) rather than one all-dimensions pass.
  · **Options weighed:** (a) per-specialist external dispatch, drop-in to each `reviewerAgent`
  slot; (b) a single external review pass emitting all dimensions, split into slots afterward.
  · **Choice + why:** (a) keeps `panel_tally`'s completeness check, synthesis, and the
  circuit breaker working unchanged, and gives each dimension a focused rubric — the truest
  cross-family safety net (the spike's whole value). · **Accepted downside:** ~5× external
  invocations per round → higher cost/usage (bounded: they run in parallel, and the owner
  opted into cost + controls depth via FR-9). · **Reversible?** two-way. · **Mode:** PROCEED.
  · **Runner-up case:** (b) is ~5× cheaper, but a dimension with zero findings is ambiguous
  (clean vs not-reviewed), which *weakens* the UFR-7 incomplete-panel detection the spec
  demands; rejected for eroding a required safety signal to save cost the owner accepted.

- **Decision:** **Cover the review role wherever it runs — the standalone `/review-code`
  skill AND the native spine review** — while the **build role covers the native
  `build_phase.js` leg only.**
  · **Options weighed:** (a) engine-aware review on both review surfaces + build on the native
  leg; (b) native-spine-only for both (defer the standalone `/review-code` command).
  · **Choice + why:** (a). The spec's DoD literally says "run review-code on a branch," whose
  most-used form is the standalone command; scoping review *below* the DoD would be the
  surprising choice. Build has no such pull — the manual SDD path is superpowers (removal
  tracked #111) and already exempt from the dispatch seam. · **Accepted downside:** the
  standalone skill's engine branch is *model-driven* markdown (dispatch the CLI adapter
  instead of the named subagent), less deterministic than the JS leaf-swap, and adds a second
  integration surface. · **Reversible?** two-way. · **Mode:** **NOTIFY** — if you'd rather ship
  the native spine first and fast-follow the standalone `/review-code` command, say so before
  build. · **Reverse path:** drop the standalone-skill branch; the native surface still meets
  the DoD's in-run review. · **Expiry:** before Tasks freezes the build surface. · **Escalated?**
  no (confident, reversible default).

- **Decision:** **Owner-authority guaranteed by confinement, not by policing the external
  process.** External engines run workspace-write / read-only with **no remote authority**
  (network-restricted); the band owns every commit/push/PR/merge through its
  `enforcer.py`-gated path.
  · **Options weighed:** (a) confine the engine (no network / no push creds) + band performs
  all remote ops; (b) rely on `enforcer.py` to police the engine's own git/gh calls; (c)
  read-only engine → emit a diff → band applies it natively.
  · **Choice + why:** (a). `enforcer.py` is a PreToolUse hook on the *host's* Bash calls — it
  gates the `codex exec`/`cursor-agent` invocation, but **not** commands the external process
  runs internally, so (b) is unsound. For **Codex**, (a) is fully structural: `--sandbox
  workspace-write` disables network → it can't reach the remote regardless of intent. For
  **Cursor**, whose sandbox may not guarantee network-off, the guarantee rests on the **same
  `enforcer.py` gate over merge / release / force-push / push-to-default** (the owner-authority
  set) — *not* on the engine cooperating — with the deeper diff-apply path (c) as the fallback
  when even network-off can't be assured. The band's gated path is the only sanctioned route to
  the remote either way. · **Accepted downside:** the Cursor residual is narrower but real — a
  rogue Cursor push to the work-item's **own feature branch** is outside the enforcer's gated
  set (which anchors on force-push and the default branch); it is contained by the gate on
  merge/push-to-default + the single-owner threat model, or removed by defaulting Cursor to (c)
  (see Risks). · **Reversible?** two-way (confinement flags are per-dispatch). · **Mode:** PROCEED
  (record) + a Risk. · **Escalated?** no — the only sound design under the single-owner threat
  model; (c) is the deeper fallback if the residual bites.

- **Decision:** **Authorization is host-enforced; the band detects absence behaviorally.**
  No parsing of the host allow-list; a run-time throwaway write preflight observes allow vs
  deny (UFR-4), and configure surfaces + tests the grant (FR-13/14).
  · **Options weighed:** (a) behavioral preflight + configure onboarding; (b) read/parse the
  effective `autoMode.allow` list at run time.
  · **Choice + why:** (a) is host-agnostic and matches the ground truth the classifier enforces
  live (proven in discovery: the owner-authored rule flips deny→allow, no restart); (b) couples
  the band to a Claude-Code-internal config surface that differs per host and version.
  · **Accepted downside:** one extra trivial dispatch before the first external write.
  · **Reversible?** two-way. · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** **Store `enginePreferences` in `core.md`'s machine block (schemaVersion 1→2),
  not the review-crew model-tiers layer.**
  · **Options weighed:** (a) `core.md` band-wide block; (b) the review-crew `## Model tiers`
  override block.
  · **Choice + why:** (a) — engine choice spans review-crew *and* workhorse, so it belongs in
  the shared brain next to `verifyCommand`/`stackTags`; (b) is review-crew-owned and wouldn't
  be visible to the build leg. · **Accepted downside:** a `core.md` schema bump (migration
  policy already exists, so cost is low). · **Reversible?** one-way-ish (schema version), but
  additive + back-compatible. · **Mode:** PROCEED. · **Escalated?** no.

- **Decision:** **Name the new modules `engine_pref` / `engine_dispatch` / `engine_adapter` /
  `engine_detect` / `engine_authz`** — keep the owner-facing term "engine," avoid **both** the
  bare `lib/engine.py` (already test-pilot's manifest system) **and its existing test path
  `lib/tests/test_engine_cli.py`** (which tests test-pilot's engine CLI) — hence the argv/parse
  core is `engine_adapter.py` (test `test_engine_adapter.py`), *not* `engine_cli.py`.
  · **Options weighed:** (a) `engine_*` prefixed names chosen to dodge the existing
  `engine.py`/`test_engine_cli.py` files; (b) a different domain word (`backend`/`runner`) to
  fully sidestep the collision.
  · **Choice + why:** (a) keeps code and config/owner vocabulary aligned ("engine"
  everywhere, `enginePreferences`); the two real clashes (`engine.py`, `test_engine_cli.py`) are
  both sidestepped by the chosen names. · **Accepted downside:** readers must not conflate
  `engine_*` with test-pilot's `engine.py`. · **Reversible?** two-way (rename). · **Mode:**
  PROCEED. · **Escalated?** no.

- **Decision (NOTIFY — scope):** **The manual/superpowers SDD build path stays Claude-only.**
  · Recorded above under non-goals. · **Reverse path:** add an engine branch to the manual
  path later if it outlives #111. · **Expiry:** before Tasks. · **Mode:** NOTIFY.

- **Decision (NOTIFY — scope):** **Authorization onboarding targets the host the band runs
  on** (snippet resolved per host); multi-host authorization parity is out of scope (§7.3).
  · **Reverse path:** add the Codex-host snippet variant when Codex-host dispatch is
  prioritized. · **Expiry:** before Tasks. · **Mode:** NOTIFY.

## Cross-cutting concerns

- **Security & privacy:** the new trust boundary is *the external process*. It is contained
  three ways: **read-only** for review (no tree writes, FR-7); **workspace-write + no remote
  authority** for implementation (confined to the managed worktree, band owns all remote ops,
  FR-8 + Constraints); and **secret-scrubbed** output on every surface (`readout.scrub`,
  fail-closed). Authorization to write is owner-only and never band-applied (FR-13). No new
  PII; engines are the owner's own signed-in tools (single-owner threat model).
- **Observability:** the `external_dispatch` journal line is the 2am signal — for any run you
  can read, per action, which engine ran, at what effort, whether verify passed, and the
  outcome; a fall-open leaves a `notify` event naming the cause. The kill switch is trivial:
  set the role's preference back to `claude` (or remove `enginePreferences`) — the next run is
  all-Claude with no code change. Availability is inspectable any time via `configure`
  (`engine_detect`).
- **Reliability & failure modes:** external engines are treated as **non-critical
  dependencies** — every selection/availability/stall failure degrades to Claude (fail-open,
  UFR-1/2/4/5), so no run can hang or hard-fail on engine choice (Fail-open NFR). The
  *opposite* bar applies to a completed-but-unsound result: verify-fail / unrunnable-verify
  (UFR-3), unauditable (UFR-6), and unreadable/incomplete review (UFR-7) are fail-closed,
  reusing the spine's existing park/halt/re-run paths. Concurrency: the engine adds **no new
  shared-write surface** — an external write lands in the same per-work-item isolated worktree
  a Claude build uses, under the same lease/fence; the band's existing concurrency model
  (§4.4/§4.5) governs unchanged (the spec's Coverage "Defer-to-plan" row, confirmed here: no
  new contention introduced).

## Rollout & migration

- **Rollout:** opt-in and dark by default — a project that sets no preference is byte-for-byte
  today's all-Claude behavior (FR-2, Constraints). The `core.md` `schemaVersion` 1→2 bump is
  **additive**: existing files read as both-`claude` (upgraded in-memory, not rewritten), and
  an older plugin meeting a v2 block fails closed with the standard "update the plugin"
  message — no data-loss, no forced migration.
- **Rollback / kill-switch:** per-role and instant — set the preference to `claude` or delete
  `enginePreferences`; the next run degrades cleanly with no redeploy. The whole feature is
  removable by deleting the leaf branches (the spine never learned about engines).

## Risks & mitigations

- **Cursor network/remote confinement is weaker than Codex's.** Codex `--sandbox
  workspace-write` disables network (no push/merge possible); Cursor's workspace-trust mode may
  not guarantee network-off, so a rogue Cursor process could in principle run `git push`. The
  guarantee must therefore be **structural, not cooperative** — "the band never asks the engine
  to touch the remote" is *not* the backstop (that is the advisory posture rejected for the
  enforcer). *Mitigation, in order:* (1) the load-bearing backstop is the **`enforcer.py` gate
  over merge / release / force-push / push-to-default** (owner-authority set), which no external
  process can bypass because it fires on the *host's* mutation of the remote; (2) Tasks makes it
  a hard acceptance gate that **a Cursor implementer cannot reach the remote** (network-off
  confinement, verified) — **and if that cannot be guaranteed, Cursor implementation defaults to
  the diff-apply fallback** (read-only engine → emit diff → band applies natively) rather than
  direct workspace-write, keeping the guarantee structural. The **named residual** the gate does
  *not* cover is a rogue Cursor push to the work-item's **own feature branch** (outside the
  force-push/default-branch matchers); it is contained by the single-owner threat model
  (the engine is the owner's own signed-in tool) and eliminated outright by the (2) fallback.
  NOTIFY-level residual, correctly, under that threat model.
- **Cost blow-up from 5× high-effort Codex review per round.** *Mitigation:* parallel
  dispatch bounds latency; FR-9 effort is owner-overridable; fall-open and the circuit breaker
  bound runaway rounds. Surfaced in the audit so cost is visible, not silent.
- **CLI drift (flags/auth/output format change under us).** The spike verified today's
  versions; parsing is via structured output (`--output-schema` / stream-json), not
  screen-scraping, and an unparseable result fails safe (UFR-2/UFR-7 → Claude). *Mitigation:*
  `engine_adapter.py` centralizes argv/parse so a drift is a one-file fix with unit tests; Codex's
  known unrelated stderr (Vercel MCP) is ignored by parsing stdout only.
- **JS-twin ↔ Python drift** for `engine_pref`. *Mitigation:* the parity-test harness that
  already covers `model_tier` (`lib/tests/parity/model_tier`) is extended to `engine_pref`.
- **Authorization false-confidence** (configure's test passes but a later run is denied).
  *Mitigation:* the run-time preflight (`implementation_dispatch_allowed`) re-checks before the
  first real write, so a revoked/edited grant falls open rather than half-writing.

## Dependencies & assumptions

- **Dependencies:** the Codex and Cursor CLIs installed + signed in on the running machine
  (else the role falls open, UFR-1); the band's existing pieces this builds on — the dispatch
  seam (`model_tier`), the `reviewPanel` shell, the native build leg, `core.md`/`configure`,
  the managed worktree, the journal, the verify gate, and `enforcer.py`. No new third-party
  library. Coordinates with #24 (usage telemetry) as a future input but does **not** depend on
  it.
- **Assumptions:** the verify command is resolvable pre-run (existing preflight) so UFR-3's
  "verify couldn't run" is rare in-run breakage, not the norm; the PR is a draft during the run
  and "left in draft" means not-advanced (never auto-merged); the owner-authored `autoMode.allow`
  rule flips external write from deny→allow with no restart (**verified live in discovery** —
  the memory records the deny→allow flip). If any assumption fails, its unhappy path already
  covers it (fall-open or fail-closed), not a parked question.
