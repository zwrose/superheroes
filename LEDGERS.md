# Ledgers — bespoke-vs-platform and anti-opportunities

Two standing ledgers required by [PHILOSOPHY.md](PHILOSOPHY.md): **B6** (bespoke
machinery only where the platform lacks the primitive — every divergence is a named
decision with a re-check trigger) and **B7** (evidence before machinery — the things we
deliberately do not build are a first-class artifact, cited instead of re-litigated).

The **orientation review** (standing monthly-ish routine, deliberately independent of
the release path) walks both ledgers each pass: the first against the platform's current
primitives, the second against its own unlock conditions; when the harness has been
upgraded since the previous pass, the pass also runs
`plugins/superheroes/lib/harness_probe.py` so the native project-context tripwire (#629)
has an owner and a cadence instead of sitting unplayed. Changes land by PR. An entry
nobody has re-checked in months is just drift with a paper trail.

## 1. Bespoke-vs-platform ledger

Every custom mechanism we maintain, the platform primitive that could absorb it, why we
still diverge, and the trigger that reopens the decision. Upstream requests are cited,
never duplicated — corroborate on the existing thread.

The v2 pivot (see [ROADMAP.md](ROADMAP.md); PR #478) retired the deterministic
execution spine, and with it the four spine divergences this ledger tracked — recorded in §1.2
below as B6 requires (a divergence that retires leaves its record, not a blank). No
maintained spine divergence remains. A new, non-spine divergence is now maintained: the
restored owner-authority gate (issue #482, §1.1 below) — a minimal PreToolUse hook,
distinct from (and much smaller than) the retired enforcer it partially recreates. A
second maintained divergence now has its entry in §1.1: review-code's multi-model review
panel (issue #513, from the ratified #474 design, the S2 Review-Crew-v2 lane) — a fresh
B6 analysis, not authored on the spine's exit.

### 1.1 Maintained divergences

| Mechanism | Platform primitive that could absorb it | Why we still diverge | Re-check trigger |
|---|---|---|---|
| **Owner-authority gate (minimal PreToolUse Bash hook, issue #482)** — emits a native `ask` on the enumerated merge/release/publish/force-push/push-to-default set, scoped to superheroes-calibrated projects; the never-merge floor as a mechanical tripwire behind the covenant's hardest line | Plugin-shippable native permission rules — a plugin able to ship declarative deny/ask permission sets (the platform's permission model does not today let a plugin ship an owner-authority ask set; it must be a hook) | No plugin-shippable permission-rule primitive exists yet, so the floor must be a bespoke PreToolUse hook; owner policy requires an owner-named risk (never-merge) to have a mechanical tripwire, not prose alone (PHILOSOPHY B6) | Claude Code ships plugin-shippable native permission rules (declarative deny/ask sets a plugin can carry) → move the gate onto the primitive and retire the hook |
| **Worktree guard (minimal PreToolUse Bash hook, issue #682)** — emits `permissionDecision: "deny"` when a classified git command would irrecoverably discard uncommitted worktree content — `git checkout` that reads paths (a `--` pathspec, `--pathspec-from-file`, two or more operands, or a lone operand that names an existing path, does not resolve as a commit, or cannot be resolved at all: fail-closed), `git checkout -f`/`--force`, `git switch -f`/`--force`/`--discard-changes`, `git restore` except index-only `--staged`, `git reset --hard`, any `git clean` that is not a dry run, `git checkout-index -f`/`--force`, `git rm -f`/`--force`, and `git worktree remove -f`/`--force` — scoped to superheroes-calibrated projects on **Claude Code only** (wired on `hooks/hooks.json`, not Codex); the checkout-revert wipe class — a mutation probe or fix subagent reverting with `git checkout -- <file>` while a prior order's uncommitted delivery sits at that path | Plugin-shippable native permission rules — declarative deny/ask sets a plugin can carry — but the platform's permission model has no way for a plugin to express *deny conditionally, based on live repository state*: a static allow/deny/ask set cannot consult `git status`, so even the primitive the owner-authority gate awaits would not, on its own, absorb this one | An owner-named risk with eight recorded in-repo occurrences (plus five in a sibling project) needs a mechanical tripwire, not prose alone (PHILOSOPHY B6); prose demonstrably failed — twice with the warning already loaded in the session's context and the charter's prose rule in force | A platform primitive that lets a plugin express a **state-conditional** deny → move the guard onto it and retire the hook; OR Codex's PreToolUse payload shape is measured and the gate can be wired on Codex without a wrong guess shipping a silently-inert hook; OR the refusals turn out in practice to be mostly false positives → revisit the dirtiness heuristic |
| **Multi-model review panel (review-code's multi-model review loop)** — the five-lens cross-vendor panel + fix loop + durable receipts, shipped as the review-code v2 arc (#505–#513, design #474) | Anthropic's upstream code-review surfaces — the public code-review plugin and the built-in `/code-review` skill. The #474 design deliberately adopted three of their patterns where they CONVERGED with ours: per-finding verification with a CONFIRMED/PLAUSIBLE/REFUTED verdict ladder requiring quoted evidence, an explicit do-not-flag list, and a no-silent-drops final merge | Four capabilities the upstream surfaces lack: multi-round fix loops with fresh-eyes fix audits, cross-vendor seats (family-keyed independence), durable receipts posted on the PR, and owner-facing stall/park handling. These are the product's spine — PHILOSOPHY promises 4/6 — not incidental extras a single-pass code-review skill could stand in for | An upstream release absorbing ANY of those four capabilities → re-walk this row (the orientation review, #318, owns the cadence). Logged: the upstream low/medium/high effort-cells mechanic was evaluated and DEFERRED as adoptable-later (#474 position 14) — delta rounds fixed the cost curve instead |
| **Dangling-citation validator (`lib/citation_validator.py`, issue #517)** — a deterministic existence check of a spec's `[cite: …]` provenance markers (cited path resolves, and its anchor text occurs in that file; fail-closed), invoked by `review-spec`'s compile step; the #205 fabricated-fact class made mechanically catchable | None today — no platform primitive validates a doc's internal repo citations (and per the §2 "no plugin-owned enforcement" bar this stays advisory analysis, not enforcement) | It is an **advisory review-seat finding producer** inside an owner-gated review (never blocks, never writes `passed`), so it is neither a new standing honesty/grounding gate (§2 "No new honesty/grounding gates…") nor plugin-owned enforcement machinery (§2 "No plugin-owned enforcement machinery"); owner-ratified #514 D3 (2026-07-20) against the #205 fabricated-fact corpus | A platform (or owner-toolchain) doc-citation/link validator that resolves repo paths lands, OR the dispatched Grounding seat's judgment (wired in the lens-recast issue #514 D1) subsumes the deterministic check |
| **Mechanical focus flags (`lib/focus_flags.py`, #511)** — grep-detects migration/lockfile changes in the round diff and injects additive rollback/supply-chain emphasis into the finder briefs; **additions only, never a lens removal**. Named consumer: the review-code specialist dispatch (`skills/review-code/reference/auto-fix-loop.md`) | None — there is no host primitive that computes per-diff review focus today; the closest is the review engine's own prompt assembly, which exposes no diff-classification hook a plugin can populate. This is lightweight in-repo diff introspection near the ordinary-code line, recorded here only because §13 asks any new deterministic decider to carry a named consumer + a ledger entry | The additive flags are cheap deterministic emphasis the finder LLMs would otherwise rediscover per run; keeping it a tiny pure function with **no authority** (it can only add emphasis, never drop a lens or a finding) keeps it off the classifier-driven lens-removal path #474 bans | The review host ships a native per-diff focus/routing hook a plugin can populate → move the flags onto it and retire the script; OR the flag set grows past a couple of grep rules (a sign it's drifting toward a classifier that decides coverage) → revisit whether it belongs in the loop at all |
| **Guardian sweep machinery (`lib/guardian_*.py`, issue #535)** — the deterministic sweep shell (registry + per-lens baseline/diff, drift-over-state, red-line detection, report + snapshot writers, dispositions ledger + report card, vitals trend append) that the `/superheroes:guardian` skill runs to produce a read-only repo-health **drift report** of plain-language consequences. Its named consumer is the `/superheroes:guardian` skill. | None today — no platform primitive runs a calibrated, drift-over-baseline, convention-validated repo-health sweep and renders plain-language consequences with receipts. | Per the §2 "no plugin-owned enforcement" bar this stays **advisory analysis**: it detects and reports; it never gates, edits, commits, or files. The sweep recommends, the advisor triages and consults the owner, nothing is auto-applied — so it is analysis+discipline, not managed enforcement. | A platform-native drift-over-baseline repo-health sweep with convention validation lands and subsumes it, OR the guardian's lenses graduate into owner-adopted toolchain checks (§2) that make the plugin-run sweep redundant. |
| **Headless builder launcher (`rubric/launch-doctrine.md`, `lib/launch_doctrine.py`, `lib/launch_ledger.py`, `lib/launcher.py`, issue #656)** — composes an advisor-invoked headless builder launch from fail-closed versioned doctrine, stamps the dispatch premise, keeps an append-only durable dispatch record, and runs R1's mechanical park/refusal accounting. Named consumer: the Showrunner charter's orchestration duty — `skills/showrunner/SKILL.md` §9 dispatch preflight; the advisor invokes the launcher per launch | Nearest primitives today are the host's subagent/Task spawning and `lib/engine_dispatch.py` (external-engine dispatches with a supervisor journal and confinement tripwires, evaluated for review/write seats) — neither composes a headless *builder* session from a versioned fail-closed doctrine artifact, stamps enumerated grant scope and owner-capability premises at reserve time, or keeps an interprocess-locked append-only launch ledger whose `count` refuses a batch rate when the fold is incomplete | Ratified precondition: #526 seat ruling B (owner-settled 2026-07-26, LEDGERS.md §4) — *launch shape becomes scripted so nothing is reconstructed from memory*. Evidence: the shared-checkout collision (a rulings block rebuilt from memory dropped the own-worktree line; two builders shared the primary checkout and a sibling's uncommitted work was wiped), three corpus launch failures behind the bounded retry, and R1's sentence making the mechanical count a blocking deliverable of this build. **§2 boundary:** advisor-invoked, one launch at a time — not queue machinery, not board-driven automatic dispatch; does not partial-unlock the #526 "No queue machinery ahead of the build-dispatch discovery" entry | The host ships a native headless-launch primitive that carries versioned standing rulings, enumerated premise stamping, and durable per-batch dispatch accounting the advisor can invoke without bespoke modules → the orientation review re-walks this row and retires the launcher stack; OR sustained field evidence that manual launch discipline plus ledgered accounting has had zero doctrine-parse, premise-stamp, or overlap escapes across measured multi-build waves → revisit whether the divergence still earns its keep |
| **Builder liveness heartbeat + advisor sweep (`lib/heartbeat.py`, launcher lane-id/root export via `SUPERHEROES_LAUNCH_ID` / `SUPERHEROES_HEARTBEAT_ROOT`, showrunner wave sweep duty)** — the builder stamps semantic liveness (`staleAfterSeconds` is its own next-stamp promise); the advisor runs `heartbeat.py sweep` on a schedule during waves and acts on `fresh` / `stale` / `terminal` / `unknown`. Named consumer: the Showrunner charter's orchestration duty 9 wave heartbeat sweep — `skills/showrunner/SKILL.md` duty 9 | The host's own background-task completion notification / wake delivery — on harness 2.1.219 the primitive exists but, with the spawning agent dormant, completions reach the **root session**, not the spawning builder, so wake-on-completion does not reliably resume the lane that launched the work | Field evidence (harness 2.1.219): six lanes, zero handbacks by morning despite near-complete work — builders' review seats woke the advisor instead of the builder, all six stalled for hours on finished soaks until an advisor sweep resumed each lane; plus the induction trap (re-wake proven early in-session only proves the active-task regime); plus **3 watchdog design failures and 3 false alarms** from mtime and process-table signals that rule out those cheaper substitutes | The harness delivers completion notifications reliably to the **spawning agent** (not the root session) → re-walk this row and consider retiring the heartbeat; OR field evidence that the sweep's own classes produced a false `fresh` |
| **Forfeit ledger + attribution decider + dispatch-outcome chokepoint (`lib/forfeit_ledger.py`, `lib/dispatch_outcome.py`, per-attempt telemetry in `lib/engine_dispatch.py`)** — a durable append-only record of each terminal dispatch with a validated repo root (folded runs, pre-spawn refusals, and run-abandoned), its per-attempt telemetry when present, and its attribution. Named consumers: the Showrunner charter's duty-4 forfeit accounting (`skills/showrunner/SKILL.md`) and the runner's own outcome minting | The nearest primitives today are the host's own task/agent telemetry and `engine_dispatch`'s supervisor journal — neither keeps a cross-run, cross-session, attributed record a later session can read | Field evidence (#747): forfeit classification failed **quietly in both directions** — a run scored "terminal forfeit ×2" held a complete engaged review whose sharpest finding later reproduced under a probe; a spurious duplicate record overwrote a real `exit: 0`; six implementer dispatches forfeited their reports while leaving correct work on disk; diagnosis was archaeology from residue that `tmp` cleanup was about to claim | A platform primitive that carries durable, attributed, cross-session dispatch-outcome telemetry the advisor can read → retire this stack; **or** the ledger's own accounting shows the forfeit rate and the salvage rate at zero across measured waves → revisit whether the divergence still earns its keep |
| **Pilot contract-home validator (`lib/pilot_contract.py`, wired into `lib/engine.py`'s `load_profile_config`, with `lib/pilot_probe.py`, `lib/pilot_slot.py`, and `lib/pilot_seed.py` as its type/vocabulary/call-shape homes), issue #822** — validates the optional nested `pilot` key inside `test-pilot-config`, including declare-and-exercise registry checks and fail-closed refusals. Named consumer: `engine.load_profile_config`, on the `apply` and `clean` paths | None today: no host primitive validates a plugin's own project-calibration artifact schema; the nearest thing in-repo is the engine's existing manifest and plan-record validation, which this sits alongside rather than duplicates | This is artifact-schema validation inside the engine that already validates its own manifests, and the design's refusals must fail closed (an unexercised declaration is absent; an absent effects-escape declaration refuses). **Open §13 residue:** C7 (#829) is now the live consumer of `is_exercised`, `require_exercised`, and `account_keys`; the **remaining** open residue is `supports_unattended_horizon` and `pilot_probe`'s `routes_to_lapse`, `is_infrastructure`, and `classify`, all of which belong to **B6** (#828) — A3 closed the rest (`seed_request`, `mint_request`, `sentinel_probe_request`, `format_slot_ref`, `parse_slot_ref`, `declaration_digest`, `verify_artifact` transitively via `pilot_seed.seed_request`); A2a closed `validate_slot_id`, `validate_generation`, and `slot_account_set` | The epic's remaining consumers land (B6) and the residue closes, at which point this row is re-walked; **or** those consumers do not land and the unconsumed surface is retired rather than left to bit-rot; **or** a platform primitive for plugin-owned calibration schema validation appears and absorbs the validator |
| **Per-slot target boundary, policy home, and provisioning authorization (`lib/pilot_boundary.py`, `lib/pilot_policy.py`, `lib/pilot_provision.py`), issue #825** — exact-origin bindings, protected-target refusal, policy document resolution outside reach, results-only traveling verdicts, and the `authorize_credentials` chokepoint gating every credential-producing call. Named consumers: sub-issues C7 (#829) and C8 (#830) — C7 has now landed as the live consumer of `gate_provisioning`, `gate_datastore_identity`, and `require_declarations_exercised`, so the row's **open §13 residue** narrows to **C8 alone** | None today — no host primitive enforces an application-level target allowlist or holds a policy document outside a branch's reach | The ratified design (#660 §3, §10) places the boundary in the framework because the check must run before any credential exists and must not route through branch-controlled code | C8 lands and the residue closes; **or** it does not and the surface is retired; **or** a platform primitive appears and absorbs it |
| **Pilot slot lifecycle + provisioning journal (`lib/pilot_lifecycle.py`, `lib/pilot_journal.py`), issue #823** — the slot state machine, serialized generation allocation, the durable provisioning journal, and the partial-failure report. Named consumers are the epic's successors — **C7** (broker-side stale-generation enforcement, design seam S1), **A2b** (reclaim, which consumes the state machine), and **C8** (the owner-facing partial-failure report) — so like the #822 row, this ships as pinned mechanism **ahead of its first caller, disclosed rather than claimed compliant** under CONVENTIONS §13. This build **closes the rest of #822's declared slot-type residue** by becoming the live consumer of `pilot_slot`'s `validate_slot_id`, `validate_generation`, and `slot_account_set` (A3 had already closed `format_slot_ref` and `parse_slot_ref`, which this build also consumes). C7 has now landed — it consumes `generation_check` at broker admission and `pilot_journal.effect()` / `mark_applied` for the server receipts — so the row's **open §13 residue** narrows to **A2b and C8** | No host primitive carries a per-slot lifecycle record with generation fencing identity, a crash-honest before-and-after provisioning journal, or a fail-closed partial-failure gate; the nearest in-repo things are `lib/file_lock.py` (an engine-apply lock with TTL-based stale reclaim, which is the wrong shape here because TTL reclaim is exactly the "second read of the same liveness marker" this design refuses) and `lib/heartbeat.py` (liveness, not allocation) | The design's own requirement that a journal written only on success reports a shared effect as never having happened; plus the repo-carried incident receipts named on issue #823 — the LEDGERS §1.1 launcher row's reconstructed-prompt shared-checkout collision, and the worktree-guard row's 8 in-repo plus 5 sibling uncommitted-work wipes | The epic's remaining consumers land (A2b/C8) and the §13 residue closes, at which point the row is re-walked; **or** those consumers do not land and the unconsumed surface is retired rather than left to bit-rot; **or** a platform primitive appears that carries durable per-slot allocation with generation fencing and absorbs it |
| **Per-slot browser topology, context-side seed injection, and live provisioning gate (`lib/pilot_browser.py`, `lib/pilot_context.py`, the new `lib/pilot_provision.py` gate surface), issue #829** — each slot gets its own browser and automation server with generation fencing at broker admission; context creation enforces capture-option matching and verify-at-seed; the live declare-and-exercise and datastore-identity strength gates run at provisioning time. Named consumers: sub-issues C8 (#830), C9, and B5 — none has landed yet | None today — no host primitive provisions a per-slot automation server with generation fencing, nor enforces capture-option matching at context creation | The ratified #660 §9 topology ruling and §10's refusals, and the S1/S3 seams — the framework must own per-slot browser isolation and context-side injection because branch-controlled code cannot be trusted to enforce them | The epic's remaining consumers land (C8/C9/B5) and the residue closes; **or** they do not and the surface is retired rather than left to bit-rot; **or** a platform primitive appears and absorbs it |

### 1.2 Retired divergences (record kept per B6)

| Mechanism | What it was | Why it retired / what absorbed it | Retired in |
|---|---|---|---|
| **Showrunner Workflow bundle** | The whole pipeline (build → review → ship) compiled into one Workflow-tool script (`lib/bundle_showrunner.js` emitted it; smoke tests + a script-size cap guarded it) | v2 no longer runs builds — the platform's own agent sessions run them, and superheroes became the discipline layer around them; bespoke orchestration was no longer earned (not the upstream fs/exec primitive landing — the job itself moved off the spine) | PR #478 |
| **Couriers** | Single-command Bash subagents the spine dispatched as dumb pipes for shell side effects (git, gh, store writes) | Retired with the spine that dispatched them — a session does its own git/gh/store work directly; there is no orchestrator left to pipe side effects for | PR #478 |
| **Enforcer (PreToolUse hook)** | Deterministic guardrail floor: owner-authority (never merge/release/publish), worktree confinement, role-scoped command policy | It WAS wired fail-closed in the shipped plugin: `hooks/hooks.json` wrapped `lib/enforcer.py hook …` on the Bash and Edit\|Write\|MultiEdit matchers with a `\|\| printf '…deny…'` fallback. PR #478 unwired it when it retired the whole file with the spine. v2 leaned on the platform permission model + owner presence instead — then found the never-merge line rode prose alone (branch protection blocks direct pushes, not `gh pr merge` on a green PR), so a minimal owner-authority gate is restored under issue #482 (see the maintained-divergence row in §1.1) | PR #478 |
| **run_watch** | CLI watcher rendering a live run's `events.jsonl` into an owner-readable progress view | No spine run to watch; the promise-6 trail now rides the durable artifacts (issue, PR, review dispositions) a session leaves, read directly by the owner or their advisor | PR #478 |
| **`pr-body` model tier role** | A registered, owner-tunable model-tier role in the band taxonomy (`lib/model_registry.py` `_MATRIX`/`_ROLE_META`/`_MODEL_TIER_ROLES`, mirrored in `lib/model_tier_resolve.py` and surfaced in `configure`'s tuning list) that resolved a Claude tier for composing a PR body | Orphaned: introduced by `dff5409` (#219 / PR #376) for the v1 draft-PR-body composer, whose consumer retired with the execution spine (#478, `9e11860` — CONVENTIONS §10.7 records `pr_entry.py`/`dod_gate.py` going with it); #509/#523 carried the role into the new taxonomy without re-checking. The workhorse charter assigns the PR body to the orchestrator as its own handback artifact, so no future consumer is coming — a knob that changes nothing is a false statement in the calibration surface. Retired-not-rebuilt; a regression guard (`test_pr_body_role_is_retired`) pins it | #692 |

## 2. Anti-opportunities ledger

Owner-ratified negative space (2026-07-05 complexity-audit walkthrough, amended
2026-07-08/09). When tempted to propose any of these, the answer is no unless the
stated unlock condition is met — cite this ledger instead of re-arguing.

- **No sixth review LENS.** The ban always meant *lens*: no sixth **risk-domain review
  lens** without escape/recall evidence; the remediation order is unchanged — rubric
  amendment → seat swap → sixth lens. #184 (the old decision-framework owner) closed into
  **#474 + #131** in the v2 audit, so the evidence bar for any future lens now points at
  **#131 (the benchmark)**. The owner-ratified (#474, 2026-07-20) **grounding seat** is
  deliberately **NOT a lens** — it is a narrow claims-vs-repo check (PR self-claims, DoD
  rows), `reviewer` tier, never `mechanical`, with **no risk domain** — so it neither adds
  a lens nor drops one: the five lenses stay five. **#511 is this framework working as
  designed:** its deleted-line audit, caller tracing, and do-not-flag bar are all **rung-1
  (rubric amendments into the existing briefs)** — exactly the path the ban prefers. #511
  formalizes the grounding seat's brief + tier bar only; its **code-leg (review-code)
  dispatch is gated to #510**, while the spec leg's Grounding seat is live as of
  **#515/#517**.
- **No traceability reviewer built on spec.** Parked behind #131 + a named consumer;
  #230's conditional-dispatch seam makes it cheap IF evidence ever calls. *(The #33
  investigation itself unlocked 2026-07-09 — the false merge-ready escape + the terminal
  intent-gap audit — and folded into the spec-fidelity instrument's discovery, still not
  a new seat.)*
- **No per-phase engine matrices.** The engine surface is the highest external-drift
  burden per feature; it grows only if cross-vendor diversity demonstrably catches
  findings Claude misses (#131 measures — meaningful only once external review
  genuinely dispatches).
- **No general diff-aware round-1 roster routing.** #131 holds it; #230's narrow
  shape-trigger is the single sanctioned exception.
- **No calendar-based eval cadences.** Release-tied triggers (#237) superseded them;
  don't re-add "monthly runs." *(Scoped exception, owner-ratified 2026-07-08: the
  **orientation review** runs on a standing monthly-ish cadence, deliberately OFF the
  release path — a hotfix must never drag a research sweep into its critical path. The
  ban still fully covers calendar-based release evals and instrument runs.)*
- **No issue-level status tables in committed docs.** *(Reshaped, owner-ratified
  2026-07-09: [ROADMAP.md](ROADMAP.md) DOES carry the release train — cut rules,
  bundles, claims owed, build lane — updated at train-level events only, per CLAUDE.md's
  rule. The ban still covers issue-level status in committed docs, and the mechanics
  inventory stays a re-derived artifact, never committed.)*
- **No new honesty/grounding gates without a named escape that penetrated every
  existing layer.** The four verification layers (CI/parity, review evals, acceptance
  live-runs, release gate) absorb incidents within existing structure. *(This bar was
  met once: the 2026-07-08 engine-fidelity escape penetrated all four — the resulting
  investment is the 0.12–0.13 truth-telling train, not a fifth standing layer.)*
- **No plugin-owned enforcement machinery.** *(Owner-ratified 2026-07-20, spike #475.)*
  Mechanical checks — boundary/import rules included — live in the owner's own toolchain
  as owner-adopted repo furniture (standard OSS tools: dependency-cruiser,
  import-linter); superheroes ships analysis and discipline — it recommends, advises,
  and helps the owner maintain such a check, never manages one. No configure surface, no
  standing CI gate, no per-build hook, no plugin-owned config. The spike's tool
  evaluations and sweep design live on as guardian-lens input (#41, epic #503). The
  review-time middle option — arming the architecture reviewer with a per-PR
  dependency-graph evidence pass — was **considered and deferred, not banned** (owner
  call 2026-07-20; the guardian pulled forward instead). *Unlock:* a boundary-class
  escape that penetrates every existing layer, including the full standard five-lens
  panel (B7's test — the #424 acceptance case did not: substitute panel with no
  architecture lens, later adjudicated won't-fix by the consuming repo), OR guardian
  sweeps showing the same wall repeatedly violated or couplings that merge and grow
  between sweeps — either reopens both the gate question and the deferred review-time
  option. *(Scoped exception, owner-ratified 2026-07-31: a minimal safety floor on an
  **irreversible local destructive action** — the worktree guard (issue #682), alongside
  the owner-authority gate (#482) already recorded in §1.1. A third member of this class
  requires **owner ratification per member, with recorded occurrence evidence** (same bar
  as this member and the owner-authority gate). The banned class is
  **analysis and architecture enforcement** that belongs in the owner's toolchain — checks
  that *recommend*; a safety floor on an irreversible action is a different job, because
  there is nothing to recommend to once the work is already gone. Evidence: eight recorded
  in-repo occurrences plus five in a sibling project, twice with the warning already in the
  session's context and the charter's prose rule in force. Everything else in this entry
  stays banned — no configure surface, no standing CI gate, no plugin-owned config, and no
  enforcement of boundary/import or analysis-class rules; the exception is for *this class
  only*, not a general licence.)*
- **No storage-mode machinery investment.** Status quo decided 2026-07-05;
  `mode_migrate` demotion re-checks only inside the superpowers-severance pass (#111).
  Store-dir naming legibility (#137) is a different layer — allowed as a read-only
  mapping view, not dir renames.
- **No config knobs that keep both implementation variants alive** (e.g. fix-in-loop
  on/off) — pick once, deliberately. *(An owner-declared degradation **policy** is
  calibration — an owner trade under promise 5 — not an implementation hedge; that
  distinction was ruled in its issue, not here.)*
- **No queue machinery ahead of the build-dispatch discovery (#526).** The
  multi-item pain the old backlog/TPM-hero + queue-controller cluster (#27–#31, #22)
  waited on arrived — the 2026-07-20/21 multi-build waves — and the owner ruled
  2026-07-21 that the cluster is superseded: the advisor absorbed the TPM role, and the
  remaining launcher question is now the build-dispatch discovery **#526**. No queue
  machinery gets built before #526's discovery concludes and B7's evidence bar is met;
  cite #526 instead of re-proposing the pair.
- **Nothing already shipped gets rebuilt** because a session forgot it exists — check
  the store, the CHANGELOG, and the Project first.
- **No superpowers-vs-charter reconciliation machinery.** *(Owner-ratified 2026-07-24, spike #627
  F3.)* The textual tension between the superpowers SessionStart injection and the charters is **real
  in text but nil in behavior** across a 543-session corpus (#627 F3). Cite this instead of proposing
  machinery to reconcile the two layers.
- **No charter/skill description prune for context economy.** *(Owner-ratified 2026-07-24,
  #626/#627.)* Measurable but **unmotivated**: routing is not degrading, the combined-description
  ratchet already forbids growth, and a wrong prune carries asymmetric misroute risk. Declined.
- **No prune of the charter redundancy devices without a behavioral instrument.** *(Owner-ratified
  2026-07-24, #626 leg 3.)* The "When you're tempted" tables and the covenant's hard-lines are pure
  restatement, but their purpose is redundancy under pressure; deleting them without measuring whether
  a Claude-5 orchestrator still obeys is the accretion mistake run in reverse. The instrument is
  **parked as #628** with unlock conditions; an advisor observational watch is adopted meanwhile.
- **No mid-range partial under-scan detection for the guardian duplication lens until a real
  specimen exists.** *(Owner-ratified 2026-07-26, PR #644, three-seat flag.)* The failure mode is
  **hypothetical**: every observed jscpd failure is all-or-nothing (cap refusal, tool missing, nonzero
  exit), never a silent partial scan. Both candidate designs rest on **unverified premises** — that
  jscpd's set of recognizable formats is enumerable, and the semantics of degrade-records telemetry.
  The removed `scanRatio` guard was proven broken **in both directions** (PR #644 round-2 stranding
  proof); any future design must answer that proof. **Unlock / tripwire:** persisted `filesScanned` /
  `scanRatio` telemetry — a **vitals trend showing a real partial under-scan** is the filing trigger.
- **No lock or transaction fix for the check-to-write race between the two configuration
  gates until concurrent calibration writers exist.** *(Owner-ratified 2026-07-26, issue #652
  rider 6; analysis PR #675, finding 7.)* Single-user posture; the check-to-write window is
  narrow; and no current workflow runs two simultaneous configure-writing sessions. A lock or
  transaction design without concurrent writers is **speculative machinery** — the named-consumer
  rule: no producer without at least one named consumer built alongside. **Blocking tripwire:** any
  future work that makes concurrent calibration writers real — orchestration machinery writing
  config from subagents or parallel sessions, or a `configure` feature that does so — **inherits a
  blocking precondition to solve this race first.**
- **No standalone fix for `store_core.normalize_remote` dropping the port** so two forges sharing
  a hostname but differing by port normalize equal and produce a false MATCH in the base guard's
  repo comparison. *(Owner-ratified 2026-07-26, issue #652 rider 8; PR #667 follow-up 3.)*
  GitHub.com never carries explicit ports and the review flow is `gh`-built, so triggering it
  requires a **self-hosted, multi-instance-on-one-host forge that no current user runs**. The fix is
  **not a one-liner**: default ports must still normalize away (ssh and https implicit ports; `:443`
  must equal the bare host), and the helper's **other callers** need checking. **Blocking tripwire:**
  the **first user on a ported forge**, or any work **adding non-GitHub forge support**, inherits
  this as a blocking precondition.

- **No fail-closed hardening beyond the last observed incident — a real specimen is the
  upgrade trigger** (owner-ratified 2026-08-02, from the session-external complexity audit
  read with the 2026-07-29 threat-model re-basing in §3). Defensive depth is built to the
  incident record, not to the imaginable attack surface: a hardening round on a
  defense-in-depth layer needs a recorded incident, a reproduced specimen, or an
  owner-named risk (which takes a mechanical tripwire per standing practice) — never "an
  attacker could conceivably". This codifies the rule `review_base_guard.py` already
  states in prose ("a real specimen is the upgrade trigger"; fork support "deliberately
  deferred until a named consumer exists — detect and fail loud only") and the rule the
  owner applied in closing #807. The two standing zero-incident clusters are frozen and
  ledgered in §3 (sanitized-view deep layers; guardian PATH-hijack defense) — findings
  against them disposition as one-line citations of those rows. **Unlock:** a recorded
  incident or reproduced specimen on the frozen surface — which re-opens exactly the layer
  it demonstrates, not the whole cluster.

**Unlock rhythm:** the stability gate (two consecutive releases whose first real runs
diagnose clean) re-opens the growth posture; #131's checkpoint re-opens
panel-composition; a real four-layer escape re-opens gate questions (spent once, see
above); the enforcement-machinery entry re-opens on its own stated unlock (a
panel-penetrating boundary escape, or guardian-sweep evidence).

## 3. Accepted residual risks

Known, owner-accepted gaps between a guarantee's prose and its enforcement — each with
its bound, why it was accepted, and the trigger that reopens it. Promise 5 applied to
ourselves: a residual risk we carry knowingly is a trade; one nobody wrote down is a
hidden defect. The orientation review walks this section too.

| Residual | Bound | Why accepted (owner-ratified) | Re-check trigger |
|---|---|---|---|
| **Worktree-confinement is a heuristic, not a sandbox — and engine subprocesses are not bound at all** (2026-07-09, #311/PR #335; amended 2026-07-15, #355). The enforcer's auto-allow parses command text for confined shapes, and its PreToolUse hook binds OUR agents' Bash — NOT a `--trust -f` external engine subprocess's children. The residual's re-check trigger FIRED in the wild (2026-07-10): a cursor fix leaf committed to the primary checkout's `main`, then self-reverted (no push, no damage this time). *(The enforcer machinery that carried this — auto-allow, worktree confinement, role policy — retired with the spine in PR #478; only the tripwire's finding stands as history.)* | The **post-dispatch confinement tripwire** (#355, `engine_dispatch.js`) now DETECTS an out-of-worktree engine write on the primary repo after every confined write dispatch — snapshotting HEAD reflog / HEAD sha / porcelain status before and after, where the **append-only reflog** catches a commit-and-self-revert excursion whose end state is clean — and emits a first-class `confinement_tripwire` journal event + a distinct narrator notice. It DETECTS, it does not prevent. Disclosed remaining blind spots (accepted): a direct `git push` mutates a remote and leaves the local probe clean; a write to a DIFFERENT on-disk repo, or a commit to a branch the primary has not checked out (only that branch's ref-log grows, not the primary HEAD reflog), is outside probed scope; a `.git`-internal write (planted hook / rewritten config) or a count-neutral working-tree edit (write-then-restore, or a further edit to an already-dirty file) moves none of the three signals; a within-window reflog gc/expiry could in principle mask count growth (very low probability); a detached child outliving the post-probe window escapes the sample; under concurrent runs sharing the primary checkout a breach receipt may mis-attribute the delta to the wrong engine/work-item (the reflog-only-grows property means concurrency never MASKS a real breach — attribution noise, not a missed detection). A timeout/threw dispatch whose CLI was never joined reports INDETERMINATE, not confined, and a breach whose durable receipt fails to persist is surfaced loudly on the live narrator line. | Detection-over-prevention is the honest bound today: physically sandboxing a `--trust` CLI is a shell sandbox the platform should own, and the ambient-credential push risk belongs to the enforcer/credential layer (#311/#335), not a per-dispatch probe. The tripwire converts a silent escape into an auditable receipt, so a real push / other-repo escape surfaces in review rather than transcript archaeology. | Claude Code ships a native process-sandboxing primitive that can confine a spawned CLI (walk with the enforcer's bespoke-vs-platform entry above); OR the tripwire observes a breach whose blast radius reached a REMOTE (a push) — that upgrades prevention from residual to defect (the local-only bound no longer holds) |
| **Audit-result provenance in the review loop's fix audits is manifest-keyed attestation, not proof of executor identity** (2026-07-21, #507/PR #555). `audits.apply_audit_results` authenticates a clearing ruling against the orchestrator's out-of-band collection manifest matched to the driver-recorded expected auditor; the in-result vendor echo is advisory (`echoMismatch` disclosed). The driver cannot cryptographically verify which engine produced a result JSON — a dishonest or compromised orchestrator could attest a forged manifest. Provenance: this PR's pre-handback review, third audit's residual demand (cryptographic executor identity), ruled unfulfillable by construction for subprocess CLI dispatches. | The trusted party is exactly the dispatching orchestrator — the same party the whole loop already trusts to run the scripts, collect results, and submit artifacts; the manifest narrows forgery to that single already-trusted role, and the receipt records `auditProvenance: "collection-manifest"` per round so the boundary is visible at vet. | Owner call 2026-07-21 on PR #555 — recording the boundary beats a dangling hardening issue no engine CLI can currently satisfy. | Any supported engine CLI ships signed/attestable outputs (per-result signatures or attestation tokens) — that upgrades the manifest from attestation to verification and reopens the row; OR a field incident where a receipt's audit provenance is shown false. |
| **The owner-authority gate is a regex heuristic over command text, not a sandbox** (issue #482). It covers the exact enumerated owner-authority shapes (all `gh pr merge` / REST + GraphQL merge / `gh release` / `gh workflow` / force-push / push-to-`main`\|`master` paths), but by construction does NOT catch every conceivable variant — a leading-`+` force refspec (`git push origin +main`), a default branch named neither `main` nor `master`, or a backslash-continued multiline command can slip; and it is wired for the **Claude host only** (`hooks/hooks.json`), NOT Codex (`hooks-codex.json`), mirroring SessionStart today. On process failure the fail-closed wrapper denies ALL Bash wherever the plugin is enabled (loud, catastrophic-env-only). | The enumerated merge/release paths — the ones an honest owner-agent would actually run — are covered exactly; the gate emits only `ask` (a prompt), never blocks, on those. The residual is edge command shapes + the Codex-host gap + the process-failure blast radius, all disclosed. It detects-and-prompts against an honest agent; it is not a containment boundary. | #482 is deliberately minimal — lift the proven enumeration, do not re-derive/widen the regexes (that risks false-positives the v1 tests never vetted); Codex-host wiring is explicitly out of scope. The floor is a tripwire, not a jail. | An observed escape through an un-enumerated shape in the wild; OR Codex-host parity is requested (wire `hooks-codex.json`); OR plugin-shippable native permission rules ship (see the §1 maintained-divergence row) — which would replace the hook wholesale |
| **Guardian ledger — an owner hand-editing `guardian/ledger.md` in another window at the exact write instant can lose that hand-edit** (2026-07-22, #539/PR #556). The advisor is the sole *automated* writer, but the owner's text editor honors no lock the plugin can hold. The never-clobber writer re-reads and re-splices onto the latest on-disk content, and immediately before writing it re-reads and requires a **full-byte match** against the exact bytes it spliced from — so any owner edit (prose or the machine-owned regions) that has landed by that final check triggers a re-splice, never a clobber. `atomic_write_bytes` gives torn-write safety (atomic *replace*, not compare-and-swap). The residual window is the sub-instant from that final full-byte re-check through the temp-file rename — an owner save landing inside it is not detected and is lost. | Best-effort conflict avoidance, not mutual exclusion. Every owner edit that has landed and settled before the final full-byte re-check is preserved (re-spliced onto the fresh content); loss requires the owner to save inside the recheck→rename sub-instant of an advisor `commit-ledger` running concurrently. The advisor writes interactively, when the owner is present and not mid-edit, which is what makes this rare in practice. | Owner-ratified 2026-07-22 — the alternatives were rejected by the owner: splitting machine state from owner prose into two files breaks §5's one-hand-editable-file contract; more locking cannot bind an external editor. Relocating the write to the sole interactive advisor closes the class by **workflow**; the residual is the small remaining mechanism gap, knowingly carried. | A **field incident of a lost owner hand-edit** to the ledger (reported or observed) — that upgrades the residual to a defect and reopens the two-file split. |
| **Sanitized review view — repo-local agent-config discovery is closed, but an external seat's context is not provably neutral** (#684). The runner strips the named config surface from a fresh export with no reachable source objects, so neither filesystem discovery nor `git show` on a stripped path reaches it. Outside that bound: **home-level operator config** (`~/.codex/`, `~/.cursor/`, `~/.gitconfig`) — the dispatcher's own configuration, not the reviewed repo's — and any instruction the reviewed **code or diff itself** carries (the review's subject; no view can strip it). **History:** the view is one synthetic commit — no `git log` / `git blame`; reading files (and `git grep`) is the grounded-read capability #665 shipped. | Config stripping is bounded to `SANITIZED_CONFIG_FILES` / `SANITIZED_CONFIG_DIRS` on the export tree; history loss is total inside the view (single commit). | #684 targeted repo-local config steering a reviewer; operator home config is trusted by definition; text inside the diff is what a reviewer is supposed to read (with judgment). History loss is accepted because file reads ground findings today. | A seat demonstrably influenced by content the view did not strip; OR a new engine config-discovery surface (CLI or discovery path) not covered by the sanitized basename/dir lists; OR a review seat that demonstrably needed `git log`/`git blame` to ground a finding. |
| **Lane assignment is judgement with no mechanical check** (2026-07-26, spike #577, built in #671). The advisor calls the lane at routing (`rubric/review-discipline.md` carries the canonical lane statement); nothing mechanically verifies the call. | **Light:** the advisor's **vet** is the late backstop before merge — it can catch a wrong lane call there. **Micro:** there is **no advisor vet**; the backstop is the one **non-Anthropic** reviewer plus **per-change owner authorization** — materially weaker than light's vet. Nothing catches a wrong call earlier at routing or mid-build except escalation triggers the builder notices. | A mechanical lane rule is exactly the plugin-owned enforcement machinery §2 bans ("No plugin-owned enforcement machinery", owner-ratified 2026-07-20, spike #475), and the evidence could not support one anyway — the guidance was right about three times in four. | A defect **escapes through a light-lane PR the vet passed**; OR a defect **escapes through a micro-lane PR** (no vet backstop); OR the vet formalization ([#672](https://github.com/zwrose/superheroes/issues/672)) lands and changes the bound — **fired 2026-07-29 (built in #694): bound UNCHANGED.** A vet receipt with a fixed shape is still judgement about the lane, adds no mechanical lane check, and does not reach **micro** at all (micro has no vet); light's vet backstop is now better *recorded*, not stronger. The first two triggers in this cell remain live. |
| **The light lane's safety is asserted from field practice, not measured** (2026-07-26, spike #577, built in #671). Eight of eight field-lean changes match where this guidance routes them (`rubric/review-discipline.md`), and none has a recorded escape. | **No panel ran on any of those eight**, so "no findings" is **absence of measurement, not evidence of absence**. Compounding it, the 8-of-8 alignment is **in-sample** — the guidance was fitted to the same 23 changes it validates against, so it is a fit and not a test. | Owner call — learn from the field rather than run a shadow panel over the same changes. The recording duty in the Showrunner charter (the lane call plus one line of reasoning) is what generates the out-of-sample evidence over time. | A defect **traced to a light-lane change**; OR enough recorded lane calls accumulate to compare out-of-sample. |
| **The vet receipt has no independent checker** (2026-07-29, spike [#672](https://github.com/zwrose/superheroes/issues/672) ratified 2026-07-27, built in #694). The grounding seat checks a PR's self-claims; **nothing checks the vet's**. Its verdict, its probes and its dispositions are the advisor's own claims. | Self-attesting by construction. The shape (spine + triggered fields + explicit `None`) makes an omission *readable* to a later reader; it does not make a false claim detectable at the time it is made. The owner's read at merge is the only party downstream. | The alternative is a checker for the checker, and that regress was refused explicitly rather than deferred: this spike hardens the last independent read and knowingly leaves it self-attesting, because the owner's read at merge is the real terminus. | A vet receipt is found to have claimed a **probe or a disposition that did not happen**. |
| **A project that stops vetting has a stale collector, and nothing catches it** (2026-07-29, #672/#694). The standing proposals collector is reconciled **at vet**; the actor is the next vet, so no vets means no actor. | Bounded to quiet periods — nothing accrues while nothing is vetted, so staleness costs nothing *while* it lasts. The real exposure is narrower and real: a proposal made just before a quiet period sits unread for the whole of it, and its age stamp is the only thing that surfaces it afterwards. | The honest cost of shipping no cadence machinery. A release-tied default is not portable (not every project cuts releases, so it would work in one and silently do nothing in another — worse, because it reads as covered), a calendar rule is banned, and a scheduled routine over the collector is a project owner's own tooling choice, not ours to ship (§2). | A **dropped proposal traced to a quiet period**. |
| **The principle check is judgement with no floor of its own** (2026-07-29, #672/#694, adopting #661's P4). The vet asks, unconditionally, what the owner still carries that the PR's owner half does not say — and **nothing checks the answer**. | The review seat's omission-floor presence match (CONVENTIONS §10.7) is a floor for **presence**, not for the principle. The vet can miss an unstated consequence exactly as the builder did; a `None` in that field is an assertion, not a verification. | Scoped to the principle deliberately: a second presence match would duplicate the seat, and the judgment is precisely the part with no mechanical form. Made **unconditional** (no floor-green precondition) because the conditional bought nothing and coupled it to another load's maturity. | An owner discovers **post-merge** that they carried something **neither half stated**. |
| **Triggered receipt fields inherit the artifacts' honesty** (2026-07-29, #672/#694). A field is raised by a greppable fact in the PR's own artifacts — so a build record that **omits** the fact raises no field. | A trigger is weaker than a check. The vet reads the diff too, so a trigger is a second chance rather than the only one, but nothing guarantees the artifact says what happened. Bounded to omission: a trigger whose fact is present and **false** is still readable. | The alternative shapes are worse in ways this section can name: ~19 always-on fields become a form and get hollowed out, and plain conditional fields reintroduce the silent omission the receipt shape exists to kill. Artifact-raised fields escape both, at exactly this cost. | A triggered field is **missed because its trigger was absent rather than false**. |
| **The receipt shape is fitted to two projects and one dominant advisor** (2026-07-29, #672/#694). The spine is convergent across two independent advisor sessions (42 receipts scored), which is real out-of-sample support **for the spine**; the loads above it are witnessed almost entirely in this repo. | Out-of-sample support exists for the spine and **not** for the newer loads. The scoring was presence-by-grep, which measures mention rather than coverage, so even the in-sample rates are directional. | Ratifying a shape two sessions had already converged on beats inventing one, and the second project's receipts under the shipped shape are the only real test available — which requires shipping it first. | A second project accumulates receipts **under the shipped shape** and they **disagree** with it. |
| **RETIRED 2026-07-31 — the builder charter now carries the preserve-contents rule** ([#734](https://github.com/zwrose/superheroes/issues/734)). **Pre-#734 record** — the following was the state as filed when this row was opened: **A builder body rewrite can silently drop the advisor's owner-half write** (2026-07-29, #672/#694). The `## Advisor vet` slot is advisor-owned and append-only, but the builder charter guarantees re-adding **the slot**, not preserving its **contents** — a rewrite that re-creates the heading and drops the text leaves a slot that looks present and says nothing. | Detection is the advisor noticing the absent `<!-- superheroes:advisor-vet -->` marker the next time it reads the body. That covers a re-vet, a re-review, or the read before handing back to the owner — but **nothing guarantees any of those happens** between a post-vet body rewrite and the merge, so on that path the verdict silently vanishes from the page the owner reads. Residual after the fix: the builder's read-and-rewrite is not atomic, so an advisor write landing between the builder's final re-read and its submit can still be overwritten by the builder's older copy — the window is narrowed, not closed, and it is not closable in prose, because nothing the two charters can say makes a whole-body edit atomic. What has changed is that the loss is now **detectable**: the advisor's backstop compares the slot's text against its own vet-receipt copy, so a marker-present, content-stale slot is caught where a marker-presence check was blind to it. The residual is **detection, not prevention** — and detection still depends on the advisor actually reading the body again before merge, which nothing guarantees. | The builder-side half (preserve advisor-authored content verbatim across a body rewrite) lives in the workhorse charter, which is outside this change's owner-ratified file set; widening it here was declined in favour of recording the hole and routing the fix. The marker is what makes the loss *detectable at all* — before it there was no signal. | A vet verdict is found **missing from a merged PR's owner half** after the advisor wrote it; OR the builder charter gains a preserve-contents rule (**fired via [#734](https://github.com/zwrose/superheroes/issues/734)**, which retires this row). |
| **The vet-receipt marker drift guard is location-blind in the charter** (2026-07-29, #672/#694). `test_vet_receipt_markers_match_conventions_10_7` binds the marker literals across CONVENTIONS §10.7, `vet-receipt.md`'s `## Markers` section and `showrunner/SKILL.md`, but the charter leg only asserts that **some** §10.7-named vet marker is present, not that the *stamp instruction* names the **body** marker specifically. | A rename cannot slip through (any renamed-in-home/stale-in-charter state fails loudly, verified live). What passes is a deliberate valid-for-valid **substitution** — hand-editing the stamp instruction from `advisor-vet` to a sibling such as `vet-receipt` — which would misdirect the advisor to stamp the wrong marker and break the detection path the advisor-write-loss row above depends on. | Closing it means a **third consecutive rework of the same assertion** in one build; the recurring class (each round the assertion binds to slightly the wrong prose feature, and a new gap appears) is a design signal, not a patch target, so it is recorded instead. The named closure needs no new literal and keeps the derive-from-home property: §10.7's bullet already distinguishes the body marker in text ("the only one in the **PR body**"), so the test can regex that bullet, extract the marker, and assert the charter carries exactly it. | The stamp instruction is found naming a marker other than the body marker; OR a vet verdict is lost because the wrong marker was stamped; OR any further rework lands on this assertion (take the named closure then). |
| **RESOLVED (a) 2026-07-30 — vet-age is a monotonic ordinal, not a count of receipts** (#672/#694; originally recorded as an open design call in this build, ruled by the advisor's adjudication of the held review on [PR #729](https://github.com/zwrose/superheroes/pull/729#issuecomment-5126730519)). The collector's escalation tripwire fires when an item was proposed two or more vets ago. Three successive attempts computed that by **counting vet receipts**, and each fixed one boundary and exposed another (late by one; then an implicit anchor risking early by one; then an in-place-corrected receipt whose posting time predates intervening vets, and any later in-place re-vet failing to advance the count at all). | **Resolved, not carried:** each collector entry is stamped with a **monotonic vet ordinal at append time**, and age is the subtraction `this vet's ordinal − the item's ordinal`. Because nothing is counted, in-place receipt edits cannot move it. The ordinal lives in the advisor's durable memory (duty 8) and is **also written into each receipt**, so the sequence is recoverable as one more than the highest ordinal in the collector or the receipts. Residual after the fix: the ordinal is **advisor-maintained prose discipline, not machinery** — a skipped or duplicated increment is not mechanically detectable, though it is inspectable in the receipts. | Ruled (a) on three grounds recorded in the adjudication: it **restores an owner-ratified guarantee** (the #672 V4/F1 tripwire) to something computable rather than adding scope; options (b) and (c) were **structurally refuted on the record** by this build's three rounds, and (b)'s immunity claim was retracted; and the mechanism is the advisor's own duty machinery, exercised at every vet. A fourth *rewording* was declined under the third-rework tripwire — this is a change of **mechanism**, not another rewording. | A receipt is found whose ordinal skips, repeats, or contradicts the collector's highest stamp; OR an escalation line is observed firing at the wrong vet under the ordinal rule; OR the ordinal's upkeep proves burdensome enough that a project asks for machinery (which would need its own ratified precondition, §2). |
| **The `check-runner` seat's no-mutation rule is prose backstopped by an orchestrator probe, not a sandbox** (2026-07-30, #719). The seat is granted `Bash` and withheld `Edit`/`Write`, so the tool grant removes the ergonomic path to a code edit but not the shell one — a `sed`, a redirect, or a mutating `git` call is still reachable. The Workhorse charter's before/after probe (`git rev-parse HEAD`, full `git status --porcelain`, HEAD reflog count, over a **committed** baseline) detects a tracked or untracked change and fails the verification outright. Disclosed blind spots, all accepted: a write-then-restore edit inside the window moves none of the three signals; a write to a **different** on-disk repo, or a `.git`-internal write (a planted hook, a rewritten config), is outside probed scope; a `git push` mutates a remote and leaves the local probe clean; a detached child that writes after the post-probe escapes the sample; `git status --porcelain` does not report **ignored** files, so a change confined to ignored repository state (`.pytest_cache`, bytecode, coverage artifacts) moves none of the three signals either — deliberately, since a legitimate test run creates exactly that state and watching it would fire the probe on every honest run; and the receipt binds an output file to a command only by the seat's own `# ran:` line, which the orchestrator compares against its authored list — a seat that fabricates both the line and plausible output is not caught by the probe. | **Detection, not containment** — and the seat is trusted no more than an implementer: its files are *inputs* to the orchestrator's verification, and the check a verdict actually turns on is one the orchestrator runs itself, so a fabricated or mutated result cannot by itself carry a claim. A dispatch that timed out or whose child was never joined reports **INDETERMINATE**, never clean. This is the subagent-scope sibling of the worktree-confinement row above, which carries the same detection-over-prevention bound at engine-subprocess scope. The same prose-only bound applies to a **bundled review seat**'s `Write` grant, which is path-unrestricted (`hosts/claude-tools.md` defines `Write` as "Create / edit / delete a file") — so rule 7's never-change-the-repository half is prose only for those seats too, and unlike `check-runner` they get **no** before/after tree probe at all. | The alternative is a real execution sandbox for a subagent's shell, which no host primitive offers today; the honest bound is the probe plus the standing rule that the *decisive* check never delegates (Workhorse §8). Withholding `Edit`/`Write` is kept anyway — it is free, and it makes the constraint legible in the seat's own frontmatter, where a drift test can guard it. | A host ships a per-subagent command-scoped or read-only execution primitive that can withhold a shell's write capability (walk with the worktree-confinement row) → move the guarantee onto it and retire the probe; OR a field incident where a `check-runner`'s output is shown to have been fabricated, or a mutation it made went undetected → that upgrades the residual to a defect. |
| **Dispatch-layer same-user process exposure** (2026-07-29, #702/PR #710). The dispatch layer does not defend against same-user processes, including its own dispatched engines; engine-written files are advisory evidence. Findings on this surface are graded as reliability, by consequence and recoverability. | The supervisor **journal** is the decision record — every spawn, retry, fold, and abandon decision reads `_journal_state`, not engine stdout/stderr. Engine stdout/stderr under the run directory are **advisory evidence** parsed only for findings or build signals, never to decide liveness or retries. The **worktree lease** and **pgroup-aware liveness gate** inside `_spawn_attempt` are reliability guards against double-spawn and stray engines, not security boundaries. The design does **not** claim engine-proof state, sealed launch files, nonces, reference hashes, or run-child re-verification of authority. | Owner re-based the risk posture on **2026-07-29** after five review rounds on PR #710 chased an unattainable property; the security walls are the owner merge gate, review discipline, git recoverability, and sanitized views. | A platform process-sandboxing primitive that can confine a spawned CLI (walk with the §1 bespoke-vs-platform row); OR a field incident where a corrupted supervisor journal or lease caused work loss that git could not recover. |
| **Inert-seat trigger ([#687](https://github.com/zwrose/superheroes/issues/687)) — intermittent and unlocalized** (2026-07-31, ratified on PR #761's ordinal-11 vet). Four live dispatches plus #668's six probes all engaged; the big-diff hypothesis refuted (a 1,871-line diff engaged fully at 173K tokens). #748's A/B eliminated the gitless-sanitized-view hypothesis as well: 9/9 instrumented dispatches engaged, including 3/3 on the pre-fix control. | Residual accepted: the genuinely inert seat is neither reproduced nor pinned. Nothing was fixed — #748 eliminated the leading candidate rather than pinning a cause, so the row stays *unlocalized* rather than converting to *pinned: environment-side, ours*. | Owner-ratified 2026-07-31, ruling (b) on the ordinal-11 vet of PR #761. This resolves collector item 34's deferral: of its two branches, neither "fix dissolves the residual" nor "row ratified then" fired cleanly, and the owner ruled the amended shape. Companion move, same ruling: the still-unexplained forfeits get their own live home as #767. | The next vacuous cluster through the post-#687 runner, which now carries `payloadShape` and real `wallSeconds`. |
| **Heartbeat store — unbounded per-launch JSON files** (issue #657). One small JSON file per launch under `<root>/<repoId>/heartbeats/<launchId>.json`, retained indefinitely; nothing reaps them; the sweep ignores launches the ledger no longer reports live, so orphaned files have no continuing consumer | No automatic reap or TTL on the heartbeat store | Knowingly accepted accumulation — semantic liveness needs a durable per-launch record the advisor can sweep without waking every builder; cleanup machinery would need its own consumer and failure modes; cost per file is negligible at current scale | A project where the accumulation becomes material (disk, inode pressure, or operational clutter) — revisit reap policy or a ledger-driven retirement path |
| **The sanitized-view deep defense layers beyond #684's config stripping are frozen at their shipped depth — zero-incident hardening takes no further rounds without a specimen** (2026-08-02, complexity-audit ratification; layers shipped across #684/#688 and the #761 lane: the patch header-spoof check, hostile `diff.external`/`textconv` defenses, forged-gitlink handling, symlink-swap race guards, ancestry scratch isolation). No recorded incident has ever exercised any of them, and #748's instrumented A/B eliminated the sanitized view as the inert-seat cause (9/9 dispatches engaged, including 3/3 on the pre-fix control). | The shipped code and its tests stay — freeze means **no further hardening rounds** on this cluster: a new finding against these layers dispositions as "frozen per §2, cite this row" absent a specimen. The threat these layers face is already bounded by the dispatch-layer posture row above (same-user processes are outside the defended perimeter; the security walls are the owner merge gate, review discipline, git recoverability, and the view's config-stripping purpose). | Owner-ratified 2026-08-02 — and the owner had already applied the rule to this exact surface in closing #807 ("hypothetical future drift … without a reproduced user outcome"). Review panels re-find these layers' residuals on every pass (5 Minor/Nit plus 7 carried items at the #761 vet alone); the freeze converts that recurring churn into a one-line citation. | A recorded incident or reproduced specimen against any frozen layer — that layer re-opens, not the cluster; OR the dispatch-layer threat-model row is re-based to include same-user adversaries. |
| **`guardian_tools`' PATH-hijack defense is frozen at its shipped depth — zero-incident hardening** (2026-08-02, complexity-audit ratification). The guardian sweep resolves its external tools defensively against PATH manipulation; no recorded incident has ever exercised the defense. | Shipped code and tests stay; no further hardening rounds absent a specimen. The guardian is advisory analysis (per its §1.1 row): it never gates, edits, commits, or files, so a hypothetical hijack's blast radius is a wrong drift *report* read by an advisor who triages with the owner — not a mutation. **This freeze does not touch #771** — the forgeable-`.git`-marker trust-boundary defect is a filed, reproduced specimen-class and proceeds on its own. | Owner-ratified 2026-08-02, same §2 rule. | A recorded incident or reproduced specimen of PATH hijack against a guardian run; OR the guardian's advisory-only boundary in its §1.1 row changes. |

## 4. Orchestration rulings (ratified 2026-07-26)

This section is the canonical in-repo record of the ruling set ratified 2026-07-26 from the
build-dispatch discovery ([#526](https://github.com/zwrose/superheroes/issues/526)). It is
policy, not machinery — the Showrunner and Workhorse charters carry enforcement; every entry
below traces to at least one of two sources: [the ratified proposal](https://github.com/zwrose/superheroes/issues/526#issuecomment-5084102492)
and [the advisor review](https://github.com/zwrose/superheroes/issues/526#issuecomment-5084118354)
(where they conflict, the review wins). Nearly all evidence behind these rulings is this repo
building itself — one repo, one advisor, one machine, no app and no ordinary end users — so
the rules are written generically and the first consuming project is the real test.

### R1 — Orchestration as a named advisor duty, with a two-guard tripwire

**Ruled:** orchestration becomes a named advisor duty with mandatory guards. Review panels check
the diff against the brief, never the brief against the world — a bad advisor premise is invisible
to them. The two guards that have actually caught that class are prose: (a) a builder parking or
refusing, and (b) the advisor's vet re-running a claim against the world (receipt-integrity; see
the advisor review on PR #644). **Standing accounting:** park/refusal rate **and** vet
receipt-integrity catches, each record naming its window, tracked alongside the existing
order-vs-implementer ratio. **Zero of either is a signal to inspect, never a clean sheet** — a
future agreeable model can drive both rates to zero and look healthy. Honest gap: this is
accounting, not machinery — prose discipline wearing a number. Sequencing: manual accounting starts
now; the mechanical count is a **blocking** deliverable of the launcher build, not nice-to-have
(the ratified proposal, build item 2; the advisor review accepted this sequencing).

### R2 — Owner involvement before the merge click keys on two properties

**Ruled:** whether the owner is in the loop *before* the merge approval (R3 owns the approval
itself) keys on two tests. **Test 1:** would a user notice this without reading the diff?
**Test 2:** is the call the owner's taste or trade, rather than a craft judgment a review lens
already owns? Three tiers — both tests → owner spot-check; perceivable but a craft call → the PR
states it plainly, no spot-check; neither → nothing. Fail-direction is explicitly **not** an owner
call (premortem and security lenses own it). The operative rule and the perceivability list live in
the Showrunner charter; `CONVENTIONS.md` §14 carries the contract framing — this entry is the
record, not a third copy. **Untested half:** every tier-1 **visual** case — this repo has no
visual surface, so it is a poor sole witness for that half (the ratified proposal; the review
named the configure profile as the eventual home for per-owner taste domains). *[Superseded
2026-07-27 by the #661 ratification: tier 1 / 2 / 3 are now **show it** / **say it** / **nothing to
see**; operative text in the Showrunner charter; presentation standard in
`rubric/review-discipline.md`.]*

### R3 — Covenant merge line repaired; train-driving duty formalized

**Ruled:** the covenant line that read as if merge execution itself was never delegable was
repaired after four days of practice where delegated `gh pr merge` plus owner gate clicks was the
actual shape — the text did not say which reading was right. The never-delegable act is the
**approval** — the gate click, the release cut, the publish decision. **Merge-command execution**
is delegable, but **only where a mechanical per-merge approval checkpoint exists on that host or
path**; where none exists, execution stays in the owner's hands. **Release PRs and anything
needing a force-push are never delegated.** Delegated otherwise: issuing the merge command,
sequencing, `update-branch`, CI-green waiting, conflict resolution under an advisor-authored recipe,
post-merge hygiene — with advisor vet, CI green, and branch current as preconditions that never
waive. **Approval stays per-PR** (owner ruling; "approve once, execute five" not adopted). The
owner-authority gate is a **backstop, not an authorization boundary** — delegation stands on advisor
discipline with the gate behind it, never the reverse. Cross-reference §1.1 and the §3 owner-
authority-gate row: the gate is wired **Claude-host only**, not Codex — that host gap is exactly
the evidence the host-conditional clause rests on (the advisor review pushback 3; the ratified
proposal §3). The §1.1 row's *"never-merge floor"* framing predates this ruling; under it the
same gate is also the mechanical per-merge approval checkpoint the host-conditional clause
depends on. **Known divergence (covenant "say so"):** Under this ruling the never-delegable act
is **approval**, and read that way the covenant and PHILOSOPHY agree. `PHILOSOPHY.md`'s current
wording still describes merge **execution** as never taken on the owner's behalf — so the two
documents **read literally still disagree**. **Disclosed, not resolved:** the constitution was
left untouched on purpose; an **owner-authored amendment to `PHILOSOPHY.md` is owed** before the
document set is coherent. `PHILOSOPHY.md` remains the authority in the meantime. **Re-check
trigger:** the owner amends `PHILOSOPHY.md` to align execution wording with this ruling, or
rules that no amendment is wanted — which would instead reopen the covenant repair.

**Resolved 2026-07-29 (#706):** the owner amended `PHILOSOPHY.md` promise 1 — the constitution now
draws the approval/execution distinction itself: the decisions that bind the owner are never made on
their behalf, executing an approved merge may be delegated **only** behind a mechanical checkpoint
that guarantees the owner's approval every time, and releases, publications, and rewritten history
stay in the owner's hands. The re-check trigger above is therefore **satisfied on its first branch**,
and the covenant's disclosed-divergence note is removed in the same change. The divergence record
above stands as history, not as current state. **What this change did.** The owner ratified a scope
extension on 2026-07-29, and the residual *acts*-framing passages were repaired **in this same
change**, not deferred: §3 bet **B1** now reads "they do the final review and give the merge approval
at the end (the approval is always theirs)", §4 item 1 now ranks "the decisions that bind the owner
(the approval behind a merge, a release, a publication)" as never moving, and §4's closing line names
"the owner-approval rule" in place of "the never-merge rule". The covenant's drift clause now
prescribes an action rather than only a disclosure — park the difference with the owner, with
`PHILOSOPHY.md` governing until they rule.

**What it closes, and what it does not.** This entry closes R3's re-check trigger and the §2-vs-§4
*acts*/*decisions* divergence that trigger tracked. **It makes no wider coherence claim.** The
cross-vendor review of this change raised three questions it does not settle — recorded here open,
rather than closed by assertion:

- **Which document governs is settled; whether it should be, is the owner's to weigh.** The
  covenant's ratified header answers today's question outright: on any disagreement, say so, park the
  difference with the owner, and `PHILOSOPHY.md` governs until they rule. What remains open is a
  policy question, not an ambiguity — the covenant carries an epistemic fail-closed default
  `PHILOSOPHY.md` does not state (where you cannot establish that a checkpoint fires on this host and
  path, execution stays in the owner's hands), so on that one point the settled rule resolves toward
  the looser text. Whether a stricter covenant safeguard should instead win by construction is an
  amendment for the owner; this entry neither presumes it nor treats today's rule as unsettled.
- **The checkpoint bar is stated two ways.** `PHILOSOPHY.md` licenses delegated execution where a
  checkpoint "guarantees the owner's approval every time"; the covenant, `CONVENTIONS.md` and the
  `showrunner` charter set the bar at one that *exists* — and §3 above records the wired gate as a regex
  heuristic that by construction does not catch every variant.
- **Host coverage is unchanged by this amendment.** The gate is wired Claude-host only;
  `hooks/hooks-codex.json` is empty, so on that host neither the gate nor the covenant injection fires.

`README.md`'s review-independence bullet reads "the owner merges": that one is **pipeline shorthand,
not a divergence** — the same document carries the approval/execution qualification at
`README.md:78-80` (approval stays with the owner; execution only behind a per-merge checkpoint),
exactly as `CONVENTIONS.md:61` is qualified at `:80-84`. The complete restatements — qualification
plus the host/path fail-closed fallback and the release/force-push exclusions — live in
`CONVENTIONS.md` and the `showrunner` charter's merge duty; the `workhorse` charter deliberately does
not repeat the standing orders, deferring to the covenant for them. A wording cleanup, not a
contradiction.

### R4 — Channel and attendance are two independent axes

**Ruled:** a headless session is not re-woken — harness-tracked in-flight work dies with the turn;
poll in-turn or park durably. Advisor-launch does **not** mean the owner is absent; the corpus spans
attended, reachable-with-latency, and asleep. Needs sort by: **owner capability** (what an agent
structurally cannot do — credentials, an account action) must reach the owner; **owner authority**
can wait behind a park; **a live human to unblock** resolves to the advisor. **Owner-capability
preconditions are cleared at dispatch time, by the advisor with the owner, before the session goes
autonomous — with a stated duration** (a session that expires mid-build is the same failure, later).
**Mid-run:** when such a need surfaces after launch anyway, **park durably, never improvise a
channel** — the escalation path is the corpus's weakest link until it is machinery (the ratified
proposal §1–§2, R4; charter channel-conditioned text carries §1's receipt).

### R5 — Advisor preflight before dispatch; explicit scope on every grant

**Ruled:** existing doctrine — never go autonomous on an assumption you have not exercised — applied
one layer up at advisor dispatch. The preflight **must scale with the batch**: cheap mechanical
checks always; expensive ones only when the work needs them, with **explicit N/A rather than silent
skipping**. The eight checks are enumerated in the Showrunner charter (the ratified proposal lists
the corpus failures behind each). **Grant scope:** a grant bounded by a fuzzy noun is real looseness;
scope is stated as **enumerated PRs, a time box, or a count**, with **release PRs excluded and
force-push never** — anything outside needs a fresh grant (adopted effective at ratification in the
advisor review).

### Seat ruling — B with A's mechanization inside

**Ruled:** option B with A's mechanization inside — the advisor keeps route, premise, park
adjudication and the vet; mechanical duties go to cheap in-session subagents under advisor-authored
recipes; launch shape becomes scripted so nothing is reconstructed from memory. **Why the others
lost:** A targets the error mechanism but gives no cost relief; C's separate long-lived courier
session protects the independent check but cross-session reach is the least reliable channel in the
corpus; D is board-driven automatic dispatch — queue machinery held by §2 with B7's evidence bar
unmet. **Three safety conditions** (build content, not caveats):

1. Recipes are **durable versioned artifacts, not session context** — a fresh subagent has none of
   the advisor's context.
2. The delegated seat gets a **refusal duty, not discretion** — when the recipe does not cover what
   the seat is looking at, it stops and hands back, never improvises.
3. Recipes **assume gated steps bounce** — permission-gated commands bubble to the root session by
   design, so each recipe names the steps it expects to hand back.

**C's written reopening trigger:** a **second orchestrator-attributed defect within one dispatch
batch** reopens the judgment/courier split — with the **attribution test** from the advisor review:
the triggering defect must be attributable to the **advisor's own execution**, not to a recipe
defect a different seat would also have hit. Writing the trigger down now is the point — it gets
decided on evidence rather than in the middle of a bad day.

### Settled by the owner (2026-07-26)

- Seat B with A's mechanization inside.
- Merge approval stays per-PR ("approve once, execute five" not adopted).
- The authenticated-app spike gates the first advisor-launched build on the first consuming
  project and is in the MVP.
- The review-seamlessness question is split out as its own spike; R2's visual duty ships meanwhile
  under the attended-or-disclose fallback.
- Mission-control gets an issue sequenced behind the liveness signal.
- **"Wave" is not formalized** — each mechanism states its own scope.
- Corroborating the existing upstream report ([#74685](https://github.com/anthropics/claude-code/issues/74685))
  is approved rather than filing a duplicate.
- This section (§4) is the canonical in-repo home of the ruling set.
