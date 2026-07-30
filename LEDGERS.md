# Ledgers — bespoke-vs-platform and anti-opportunities

Two standing ledgers required by [PHILOSOPHY.md](PHILOSOPHY.md): **B6** (bespoke
machinery only where the platform lacks the primitive — every divergence is a named
decision with a re-check trigger) and **B7** (evidence before machinery — the things we
deliberately do not build are a first-class artifact, cited instead of re-litigated).

The **orientation review** (standing monthly-ish routine, deliberately independent of
the release path) walks both ledgers each pass: the first against the platform's current
primitives, the second against its own unlock conditions. Changes land by PR. An entry
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
| **Multi-model review panel (review-code's multi-model review loop)** — the five-lens cross-vendor panel + fix loop + durable receipts, shipped as the review-code v2 arc (#505–#513, design #474) | Anthropic's upstream code-review surfaces — the public code-review plugin and the built-in `/code-review` skill. The #474 design deliberately adopted three of their patterns where they CONVERGED with ours: per-finding verification with a CONFIRMED/PLAUSIBLE/REFUTED verdict ladder requiring quoted evidence, an explicit do-not-flag list, and a no-silent-drops final merge | Four capabilities the upstream surfaces lack: multi-round fix loops with fresh-eyes fix audits, cross-vendor seats (family-keyed independence), durable receipts posted on the PR, and owner-facing stall/park handling. These are the product's spine — PHILOSOPHY promises 4/6 — not incidental extras a single-pass code-review skill could stand in for | An upstream release absorbing ANY of those four capabilities → re-walk this row (the orientation review, #318, owns the cadence). Logged: the upstream low/medium/high effort-cells mechanic was evaluated and DEFERRED as adoptable-later (#474 position 14) — delta rounds fixed the cost curve instead |
| **Dangling-citation validator (`lib/citation_validator.py`, issue #517)** — a deterministic existence check of a spec's `[cite: …]` provenance markers (cited path resolves, and its anchor text occurs in that file; fail-closed), invoked by `review-spec`'s compile step; the #205 fabricated-fact class made mechanically catchable | None today — no platform primitive validates a doc's internal repo citations (and per the §2 "no plugin-owned enforcement" bar this stays advisory analysis, not enforcement) | It is an **advisory review-seat finding producer** inside an owner-gated review (never blocks, never writes `passed`), so it is neither a new standing honesty/grounding gate (§2 "No new honesty/grounding gates…") nor plugin-owned enforcement machinery (§2 "No plugin-owned enforcement machinery"); owner-ratified #514 D3 (2026-07-20) against the #205 fabricated-fact corpus | A platform (or owner-toolchain) doc-citation/link validator that resolves repo paths lands, OR the dispatched Grounding seat's judgment (wired in the lens-recast issue #514 D1) subsumes the deterministic check |
| **Mechanical focus flags (`lib/focus_flags.py`, #511)** — grep-detects migration/lockfile changes in the round diff and injects additive rollback/supply-chain emphasis into the finder briefs; **additions only, never a lens removal**. Named consumer: the review-code specialist dispatch (`skills/review-code/reference/auto-fix-loop.md`) | None — there is no host primitive that computes per-diff review focus today; the closest is the review engine's own prompt assembly, which exposes no diff-classification hook a plugin can populate. This is lightweight in-repo diff introspection near the ordinary-code line, recorded here only because §13 asks any new deterministic decider to carry a named consumer + a ledger entry | The additive flags are cheap deterministic emphasis the finder LLMs would otherwise rediscover per run; keeping it a tiny pure function with **no authority** (it can only add emphasis, never drop a lens or a finding) keeps it off the classifier-driven lens-removal path #474 bans | The review host ships a native per-diff focus/routing hook a plugin can populate → move the flags onto it and retire the script; OR the flag set grows past a couple of grep rules (a sign it's drifting toward a classifier that decides coverage) → revisit whether it belongs in the loop at all |
| **Guardian sweep machinery (`lib/guardian_*.py`, issue #535)** — the deterministic sweep shell (registry + per-lens baseline/diff, drift-over-state, red-line detection, report + snapshot writers, dispositions ledger + report card, vitals trend append) that the `/superheroes:guardian` skill runs to produce a read-only repo-health **drift report** of plain-language consequences. Its named consumer is the `/superheroes:guardian` skill. | None today — no platform primitive runs a calibrated, drift-over-baseline, convention-validated repo-health sweep and renders plain-language consequences with receipts. | Per the §2 "no plugin-owned enforcement" bar this stays **advisory analysis**: it detects and reports; it never gates, edits, commits, or files. The sweep recommends, the advisor triages and consults the owner, nothing is auto-applied — so it is analysis+discipline, not managed enforcement. | A platform-native drift-over-baseline repo-health sweep with convention validation lands and subsumes it, OR the guardian's lenses graduate into owner-adopted toolchain checks (§2) that make the plugin-run sweep redundant. |

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
  option.
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
| **Lane assignment is judgement with no mechanical check** (2026-07-26, spike #577, built in #671). The advisor calls the lane at routing (`rubric/review-discipline.md` carries the canonical lane statement); nothing mechanically verifies the call. | **Light:** the advisor's **vet** is the late backstop before merge — it can catch a wrong lane call there. **Micro:** there is **no advisor vet**; the backstop is the one **non-Anthropic** reviewer plus **per-change owner authorization** — materially weaker than light's vet. Nothing catches a wrong call earlier at routing or mid-build except escalation triggers the builder notices. | A mechanical lane rule is exactly the plugin-owned enforcement machinery §2 bans ("No plugin-owned enforcement machinery", owner-ratified 2026-07-20, spike #475), and the evidence could not support one anyway — the guidance was right about three times in four. | A defect **escapes through a light-lane PR the vet passed**; OR a defect **escapes through a micro-lane PR** (no vet backstop); OR the vet formalization ([#672](https://github.com/zwrose/superheroes/issues/672)) lands and changes the bound — **fired 2026-07-30 (built in #694): bound UNCHANGED.** A vet receipt with a fixed shape is still judgement about the lane, adds no mechanical lane check, and does not reach **micro** at all (micro has no vet); light's vet backstop is now better *recorded*, not stronger. The first two triggers in this cell remain live. |
| **The light lane's safety is asserted from field practice, not measured** (2026-07-26, spike #577, built in #671). Eight of eight field-lean changes match where this guidance routes them (`rubric/review-discipline.md`), and none has a recorded escape. | **No panel ran on any of those eight**, so "no findings" is **absence of measurement, not evidence of absence**. Compounding it, the 8-of-8 alignment is **in-sample** — the guidance was fitted to the same 23 changes it validates against, so it is a fit and not a test. | Owner call — learn from the field rather than run a shadow panel over the same changes. The recording duty in the Showrunner charter (the lane call plus one line of reasoning) is what generates the out-of-sample evidence over time. | A defect **traced to a light-lane change**; OR enough recorded lane calls accumulate to compare out-of-sample. |
| **The vet receipt has no independent checker** (2026-07-30, spike [#672](https://github.com/zwrose/superheroes/issues/672) ratified 2026-07-27, built in #694). The grounding seat checks a PR's self-claims; **nothing checks the vet's**. Its verdict, its probes and its dispositions are the advisor's own claims. | Self-attesting by construction. The shape (spine + triggered fields + explicit `None`) makes an omission *readable* to a later reader; it does not make a false claim detectable at the time it is made. The owner's read at merge is the only party downstream. | The alternative is a checker for the checker, and that regress was refused explicitly rather than deferred: this spike hardens the last independent read and knowingly leaves it self-attesting, because the owner's read at merge is the real terminus. | A vet receipt is found to have claimed a **probe or a disposition that did not happen**. |
| **A project that stops vetting has a stale collector, and nothing catches it** (2026-07-30, #672/#694). The standing proposals collector is reconciled **at vet**; the actor is the next vet, so no vets means no actor. | Bounded to quiet periods — nothing accrues while nothing is vetted, so staleness costs nothing *while* it lasts. The real exposure is narrower and real: a proposal made just before a quiet period sits unread for the whole of it, and its age stamp is the only thing that surfaces it afterwards. | The honest cost of shipping no cadence machinery. A release-tied default is not portable (not every project cuts releases, so it would work in one and silently do nothing in another — worse, because it reads as covered), a calendar rule is banned, and a scheduled routine over the collector is a project owner's own tooling choice, not ours to ship (§2). | A **dropped proposal traced to a quiet period**. |
| **The principle check is judgement with no floor of its own** (2026-07-30, #672/#694, adopting #661's P4). The vet asks, unconditionally, what the owner still carries that the PR's owner half does not say — and **nothing checks the answer**. | The review seat's omission-floor presence match (CONVENTIONS §10.7) is a floor for **presence**, not for the principle. The vet can miss an unstated consequence exactly as the builder did; a `None` in that field is an assertion, not a verification. | Scoped to the principle deliberately: a second presence match would duplicate the seat, and the judgment is precisely the part with no mechanical form. Made **unconditional** (no floor-green precondition) because the conditional bought nothing and coupled it to another load's maturity. | An owner discovers **post-merge** that they carried something **neither half stated**. |
| **Triggered receipt fields inherit the artifacts' honesty** (2026-07-30, #672/#694). A field is raised by a greppable fact in the PR's own artifacts — so a build record that **omits** the fact raises no field. | A trigger is weaker than a check. The vet reads the diff too, so a trigger is a second chance rather than the only one, but nothing guarantees the artifact says what happened. Bounded to omission: a trigger whose fact is present and **false** is still readable. | The alternative shapes are worse in ways this section can name: ~19 always-on fields become a form and get hollowed out, and plain conditional fields reintroduce the silent omission the receipt shape exists to kill. Artifact-raised fields escape both, at exactly this cost. | A triggered field is **missed because its trigger was absent rather than false**. |
| **The receipt shape is fitted to two projects and one dominant advisor** (2026-07-30, #672/#694). The spine is convergent across two independent advisor sessions (42 receipts scored), which is real out-of-sample support **for the spine**; the loads above it are witnessed almost entirely in this repo. | Out-of-sample support exists for the spine and **not** for the newer loads. The scoring was presence-by-grep, which measures mention rather than coverage, so even the in-sample rates are directional. | Ratifying a shape two sessions had already converged on beats inventing one, and the second project's receipts under the shipped shape are the only real test available — which requires shipping it first. | A second project accumulates receipts **under the shipped shape** and they **disagree** with it. |

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
