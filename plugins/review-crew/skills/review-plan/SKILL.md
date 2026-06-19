---
name: review-plan
description: Use to review the-architect's `plan` definition-doc (the technical *how* for a work-item) before it advances to Tasks. Red-teams the plan against the base rubric with the five specialist agents, revises it in place, and — on a clean pass — records the review gate (`gates.review: passed`) the autonomous loop reads. The Plan leg of the superheroes review trio (review-spec / review-plan / review-tasks).
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools via `hosts/<your-host>-tools.md` in this plugin — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Review Plan

Red-team the-architect's **`plan` definition-doc** — the technical *how* for a work-item
(`docs/superheroes/<work-item>/plan.md`) — **before** it advances to Tasks. The main
context is an orchestrator: it locates the plan, reads its parent `spec` for the
requirements the plan must satisfy, dispatches the same five specialist agents
`/review-crew:review-code` uses (architecture, code, security, test, premortem) in parallel
against the plan doc instead of a diff, compiles their findings under the base rubric,
attaches its own point of view to each finding, and **revises the plan in place** —
auto-applying the mechanical fixes it recommends and stopping to ask only about findings it
would skip/defer or fixes that involve a judgment call. On a clean exit it **records the
review gate** (`gates.review: passed`); if blocking findings remain it records
`changes-requested`.

This is the **Plan leg of the superheroes review trio** (`review-spec` / `review-plan` /
`review-tasks`) — the automated gate the-architect's `plan` skill calls. Read the base
rubric (`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`) for severity calibration and the
verification rules every finding must pass; if anything below contradicts the base rubric,
the base rubric wins.

> **Band posture.** This reviews the superheroes `plan` definition-doc (CONVENTIONS §3) and
> is designed to run inside the band, alongside the-architect. It does not aim to review
> loose, non-definition-doc plans — that is out of contract (CONVENTIONS "Band posture").
> If handed a doc with no `superheroes: doc` / `docType: plan` frontmatter it **degrades,
> it does not crash**: it still red-teams the document, but skips the gate write (there is
> no gate to set) and says so.

Plan-time review is intentionally narrower than code-time review. The agents are told they
are reading a draft *how* — their job is to flag what the plan **omits or gets wrong**
against the plan contract (a decision with no named downside, a one-way door taken without
weighing ≥2 options, a spec requirement left unaddressed, an unverified package, missing
operability/rollback, wrong altitude), not to nitpick wording or pre-grade implementation
details the plan reasonably defers to Tasks.

## Invocation

| Form                              | Behavior                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `/review-crew:review-plan`        | Review the most recent `docs/superheroes/*/plan.md`.                                                  |
| `/review-crew:review-plan <work-item>` | Review `docs/superheroes/<work-item>/plan.md`.                                                   |
| `/review-crew:review-plan <path>` | Review the plan doc at `<path>` (relative to repo root or absolute).                                 |

If no plan doc is found and no argument was passed, ask the user via `AskUserQuestion` before
continuing — there is nothing to review otherwise.

## Session Directory

All review artifacts live in a per-invocation temp directory so parallel reviews don't collide:

```bash
SESSION_DIR=$(mktemp -d /tmp/review-plan-XXXXXXXX)
```

| Path                                      | Written by   | Purpose                                                        |
| ----------------------------------------- | ------------ | -------------------------------------------------------------- |
| `$SESSION_DIR/meta.json`                  | orchestrator | Plan path, work-item, session dir, classification              |
| `$SESSION_DIR/plan.md`                    | orchestrator | Stable copy of the target plan doc — subagents read this       |
| `$SESSION_DIR/spec.md`                    | orchestrator | Stable copy of the parent spec (context for the reviewers)     |
| `$SESSION_DIR/findings-architecture.json` | arch agent   | Architecture-reviewer findings array                           |
| `$SESSION_DIR/findings-code.json`         | code agent   | Code-reviewer findings array                                   |
| `$SESSION_DIR/findings-security.json`     | sec agent    | Security-reviewer findings array                               |
| `$SESSION_DIR/findings-test.json`         | test agent   | Test-reviewer findings array                                   |
| `$SESSION_DIR/findings-premortem.json`    | premortem agent | Premortem-reviewer (Failure-Mode) findings array            |
| `$SESSION_DIR/compiled.json`              | orchestrator | Deduplicated, verified findings + summary + verdict            |

## Workflow

### 1. Setup

**Resolve the base rubric path once.** The base rubric is bundled at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`. Capture the rubric path so it can be embedded — **expanded to an absolute path** — into subagent prompts (subagents may not inherit `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RUBRIC="$ROOT_DIR/rubric/review-base.md"   # absolute; embed the expanded value in subagent prompts
```

**Resolve the profile and decisions paths once (resolver-driven).** The profile/decisions may live in-repo (`./.claude/`) or in the global per-repo store; `review_store.py resolve` returns the resolved path (or `location: none` when nothing exists yet). Capture `$PROFILE`, `$LOCATION`, `$EXISTS`, and `$DECISIONS` here, before the staleness self-check and profile bootstrap below use them:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RES=$(python3 "$ROOT_DIR/lib/review_store.py" resolve --kind profile) \
  || { echo "review_store resolve failed — continuing with strict fallback"; RES='{"location":"none","exists":false,"path":null}'; }
PROFILE=$(printf '%s' "$RES" | jq -r '.path // empty')
LOCATION=$(printf '%s' "$RES" | jq -r .location)
EXISTS=$(printf '%s' "$RES" | jq -r .exists)
DRES=$(python3 "$ROOT_DIR/lib/review_store.py" resolve --kind decisions) \
  || { echo "review_store resolve --kind decisions failed"; DRES='{"path":null}'; }
DECISIONS=$(printf '%s' "$DRES" | jq -r '.path // empty')
```

Also resolve the engine versions the staleness self-check (next) needs — the **plugin version** from `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/.claude-plugin/plugin.json` (`version`) and the **rubric-version** from the first line of `$RUBRIC` (`<!-- rubric-version: N -->`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
PLUGIN_VERSION=$(python3 -c "import json;print(json.load(open('$ROOT_DIR/.claude-plugin/plugin.json'))['version'])")
RUBRIC_VERSION=$(sed -n 's/.*rubric-version: *\([0-9][0-9]*\).*/\1/p' "$RUBRIC" | head -1)
```

**Staleness self-check (first action).** Before the profile bootstrap and before locating the plan or dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. review-plan reads the working tree (default root), so no `--root` is passed. Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below (which runs review-init/bootstrap), not to staleness:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$EXISTS" = "true" ]; then
  DOCTOR_JSON=$(python3 "$ROOT_DIR/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION")
fi
```

Capture the JSON in `DOCTOR_JSON`. On `readable: false`, tell the user "profile unreadable — re-run `/review-crew:review-init`" and **continue** (do not crash, do not block). Otherwise retain `message`, `signal_hash`, and `nudge_acked` for the **end-of-run staleness nudge** (see §5's terminal summary). Do NOT act on `drift` here — it is informational only.

**Profile bootstrap (run before locating the plan or dispatching anything).** The review engine reads its per-project calibration (threat model, scope, focus hints, canonical patterns) from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$LOCATION" = "none" ]; then
  INTERACTIVE=true   # the orchestrator sets this to false on a headless/non-interactive run (no human to answer), so decide-location returns "global" deterministically instead of "ask"
  LOC=$(python3 "$ROOT_DIR/lib/review_store.py" decide-location --interactive "$INTERACTIVE")
  # If LOC is "ask", STOP — present the in-repo-vs-global AskUserQuestion, set LOC, then run the create calls below.
  PROFILE=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind profile --location "$LOC")
  DECISIONS=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind decisions --location "$LOC")
fi
```

When `decide-location` returns `ask`, present the in-repo-vs-global `AskUserQuestion` (per the spec's *Halt-and-ask init flow*) and use the answer as `$LOC`.

When `$LOCATION` is `none`, run review-init's create procedure inline (`plugins/review-crew/skills/review-init/SKILL.md`, Steps 1–4: detect → interview → seed canonical patterns → write the profile to `$PROFILE`), then continue. Headless / non-interactive runs get a provisional, strict-threat-model profile from detected defaults. (Do not run any staleness, reconcile, or learning-loop step here — out of scope.)

**Locate the target plan doc.** Resolve by work-item slug, explicit path, or most-recent:

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
if [ -n "$ARG" ] && [ -f "$ARG" ]; then
  PLAN_PATH="$ARG"                                            # explicit path
elif [ -n "$ARG" ] && [ -f "$ROOT/docs/superheroes/$ARG/plan.md" ]; then
  PLAN_PATH="$ROOT/docs/superheroes/$ARG/plan.md"             # work-item slug
else
  PLAN_PATH=$(ls -t "$ROOT"/docs/superheroes/*/plan.md 2>/dev/null | head -1)   # most recent
fi
```

If `$PLAN_PATH` is empty or the file doesn't exist, use `AskUserQuestion` to ask for a work-item or path. Do not invent one.

**Derive the work-item and confirm this is a plan definition-doc.** The work-item is the parent directory name; confirm the frontmatter so the gate write (step 6) targets a real definition-doc:

```bash
WORK_ITEM=$(basename "$(dirname "$PLAN_PATH")")
IS_DEF_DOC=$(grep -qE '^superheroes:\s*doc' "$PLAN_PATH" && grep -qE '^docType:\s*plan' "$PLAN_PATH" && echo yes || echo no)
```

If `IS_DEF_DOC` is `no`, note it and **proceed without a gate write** (degrade-not-crash, per Band posture): you can still red-team the document, but step 6 is skipped.

Copy the plan to a stable artifact path, copy its **parent spec** for context (the plan must satisfy it), and classify what the plan touches with simple, stack-neutral topic heuristics:

```bash
cp "$PLAN_PATH" "$SESSION_DIR/plan.md"
SPEC_PATH="$ROOT/docs/superheroes/$WORK_ITEM/spec.md"
[ -f "$SPEC_PATH" ] && cp "$SPEC_PATH" "$SESSION_DIR/spec.md"   # context; absent → reviewers note the spec couldn't be cross-checked

TOUCHES=()
grep -Eqi 'route|endpoint|api|handler'                  "$SESSION_DIR/plan.md" && TOUCHES+=("API")
grep -Eqi 'component|view|page|screen|UI'               "$SESSION_DIR/plan.md" && TOUCHES+=("UI")
grep -Eqi 'schema|migration|database|collection|table|model' "$SESSION_DIR/plan.md" && TOUCHES+=("data")
grep -Eqi 'auth|session|permission|owner|tenant'        "$SESSION_DIR/plan.md" && TOUCHES+=("auth")
grep -Eqi 'test|spec|coverage'                          "$SESSION_DIR/plan.md" && TOUCHES+=("tests")
grep -Eqi 'architecture|layering|abstraction|module'    "$SESSION_DIR/plan.md" && TOUCHES+=("architecture")
```

Write metadata:

```bash
cat > "$SESSION_DIR/meta.json" <<EOF
{
  "planPath": "$PLAN_PATH",
  "workItem": "$WORK_ITEM",
  "isDefinitionDoc": "$IS_DEF_DOC",
  "sessionDir": "$SESSION_DIR",
  "touches": $(printf '%s\n' "${TOUCHES[@]}" | jq -R . | jq -sc 'map(select(length>0))')
}
EOF
```

The classification is informational — it appears in the dispatch summary and is passed to subagents as context, but **all five specialists still run**. Coverage uniformity beats saving one agent dispatch; a "no data flow proposed" guess is exactly when a missing ownership check slips through.

### 2. Dispatch Summary

Print this dispatch summary as a plain status message, then dispatch the specialists immediately (no approval gate):

- **Plan doc:** `$PLAN_PATH` (work-item `$WORK_ITEM`) and its line count (`wc -l < $SESSION_DIR/plan.md`)
- **Gate:** will be recorded on the plan doc (`isDefinitionDoc == yes`), or skipped (`no` — degraded)
- **Classification:** the `touches` array (e.g. `["API", "data", "auth"]`)
- **Specialists to dispatch (all five, in parallel):**
  - `architecture-reviewer` → `findings-architecture.json` _(does the heaviest lifting at plan time)_
  - `security-reviewer` → `findings-security.json`
  - `test-reviewer` → `findings-test.json`
  - `code-reviewer` → `findings-code.json` _(lighter at plan time)_
  - `premortem-reviewer` → `findings-premortem.json` _(inverse reasoning: failure modes + unstated assumptions)_
- **Session directory:** `$SESSION_DIR`

### 3. Dispatch Specialists in Parallel

Launch all five specialists in a **single message with five parallel reviewer dispatches** so they run in parallel, each dispatched by its reviewer name (resolve dispatch via `hosts/<your-host>-tools.md`). On Codex, dispatch is `spawn_agent` loading `agents/<name>.md`'s methodology; collect with `wait_agent` — see the tool map. Each gets the same prompt template, parameterized by reviewer name, dimension label, and findings filename. The agent's review methodology is its own system prompt — the prompt below is context-only (paths and rules); do **not** tell it to read an agent file. Embed the **absolute** base-rubric path (the expanded value of `RUBRIC`) so the subagent can read it. Substitute `<PROFILE_PATH>` with the resolved absolute `$PROFILE` when building each subagent prompt (subagents do not inherit shell vars):

```
You are reviewing the-architect's `plan` definition-doc (the technical *how* for
a work-item), NOT code and NOT a diff.

## Your assignment
Review the plan at $SESSION_DIR/plan.md for your dimension. Its parent
requirements `spec` is at $SESSION_DIR/spec.md (if present) — the plan must
satisfy it; cross-check against it. Read the base rubric (absolute path below)
for severity calibration, verification rules, and the findings output format.
Read the project profile and CLAUDE.md for calibration (threat model, scope,
focus hints, canonical patterns, conventions).

## Context files
- Plan (the doc under review): $SESSION_DIR/plan.md
- Parent spec (the requirements it must satisfy): $SESSION_DIR/spec.md
- Base rubric (severity, verification rules, findings format): <absolute RUBRIC path>
- Project profile (threat model, scope, focus hints, canonical patterns): <PROFILE_PATH>
- CLAUDE.md (project conventions): CLAUDE.md
- Project structure: feel free to Read/Grep/Glob the current repo for pattern
  verification (existing modules, conventions, neighbors) and to confirm any
  package/API the plan names actually exists.
- <if focus notes> Focus: <focus notes>

## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > profile (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## What a good `plan` definition-doc must do (flag departures)
The plan is the *how* for an approved spec. It is sound when:
- **Every spec requirement is addressed** — each functional requirement,
  non-functional requirement, and significant unhappy path maps to something in
  the plan (the "How the requirements are met" coverage), and nothing in the plan
  lacks a spec basis (no gold-plating / YAGNI violation).
- **Significant decisions weigh ≥2 materially different options** (differing on a
  named axis — data model, a boundary, sync vs async, build vs buy — not parameter
  tweaks) and **each records an accepted downside** and whether it is a one-way or
  two-way door. A decision with no named downside, or a one-way door taken without
  a real alternative, is a finding.
- **Non-functional requirements are validated** against the design (not just "does
  it work"): reliability/failure modes, the load/target, security/privacy.
- **Operability is answered**: "how does on-call debug this at 2am?" and "how do we
  turn it off / roll back?" — or an explicit N/A with a reason.
- **Right altitude**: strategy, not steps. Pasted full schemas, full code, test
  cases, or dated rollout sequences belong to Tasks — flag them here as wrong-level,
  not as content to grade.

## Per-dimension framing (you are reviewing a DRAFT *how*)
- Architecture-reviewer: pattern fit against the real codebase; abstraction
  justification (rule of three — a new util/module needs real call sites, not one);
  module coupling implied by the design; complexity that isn't traceable to a spec
  requirement.
- Security-reviewer: new user-data flows, auth/ownership changes, new trust
  boundaries or API surface — are the checks specified? Flag "we'll add validation
  later." Honor the profile's threat model.
- Test-reviewer: does the plan name a verification strategy proportionate to the
  risk? Are the unhappy paths from the spec covered by the approach? Is what's
  proposed testable as designed? (Exact test cases are Tasks-level — don't demand
  them here.)
- Code-reviewer (lighter at plan time): does the plan reference correct
  conventions, and does it name any package/API/version that must be verified to
  exist? **A plausible-but-nonexistent package or API is a real finding** — grep /
  check before trusting it. Flag anything that contradicts project rules.
- Premortem-reviewer: assume the plan shipped and FAILED — surface unstated
  assumptions and incident narratives for the failure classes (concurrency, partial
  failure, dependency failure, resource exhaustion, migration/rollback,
  detectability). Honor the profile's threat model — no race findings under a
  single-user model.

## Out of scope at plan time
- Naming preferences ("call it Foo not Bar").
- Implementation details the plan reasonably defers to Tasks.
- Style / lint / type checks that only matter on the eventual code.

## Verification rules
- `file:line` citation required. Cite the plan-doc heading + line number, OR a
  related project file if the finding references existing code.
- Before flagging "missing X", grep the project for X under variant names. Don't
  flag a missing helper that already exists.
- Before flagging "new abstraction is unjustified", check whether the plan
  articulates why (a justification in the plan itself defuses the finding).
- Before flagging "package/API doesn't exist", actually check (the repo, the
  installed version) — but a name you cannot confirm IS worth flagging as
  unverified.

## Output
Write findings to $SESSION_DIR/findings-<agent>.json as a JSON array per the base
rubric's "Findings output format" section. The `file` field may be the plan path
OR a related project file path. Set `dimension` to "<dimension>" on every entry.
If you have nothing to flag, write `[]` — do not skip writing the file.
```

Per-agent substitutions:

| reviewer | `<agent>` (findings filename) | `<dimension>` |
| ---------------------------- | ----------------------------- | ------------- |
| architecture-reviewer        | architecture                  | Architecture  |
| code-reviewer                | code                          | Code          |
| security-reviewer            | security                      | Security      |
| test-reviewer                | test                          | Test          |
| premortem-reviewer           | premortem                     | Failure-Mode  |

After dispatch, wait for all five agents to return. Each writes its findings file to `$SESSION_DIR/`. The orchestrator does not read agent transcripts — only the JSON files.

### 4. Compile Findings (main context)

Read the five `$SESSION_DIR/findings-*.json` files. Apply, in order:

1. **Citation check.** Drop any finding with `file == null` or `line == null` — the base rubric's verification rules require a `file:line` citation.
2. **Dedupe by plan section + topic.** When two findings target the same plan section heading and same topic (e.g. both flagging "no accepted downside on the data-model decision"), merge them: concatenate bodies with a separator, keep the higher severity, list both dimensions (e.g. `"Architecture + Failure-Mode"`).
3. **Nit cap.** If more than 5 Nits remain after dedupe, keep the first 5 and summarize the rest as a count (e.g. `"+ 8 more Nits — see $SESSION_DIR/findings-*.json"`).

Determine the verdict per the base rubric's "Verdict labels & mapping". For `/review-crew:review-plan` the labels are **PLAN READY** / **REVISE BEFORE TASKS** / **MAJOR GAPS — RECONSIDER DESIGN**:

- 0 Critical, 0 Important → **PLAN READY**
- 0 Critical, 1+ Important → **REVISE BEFORE TASKS**
- 1+ Critical → **MAJOR GAPS — RECONSIDER DESIGN**
- Only Minor and/or Nit → **PLAN READY** (Minor/Nit are informational)

Write to `$SESSION_DIR/compiled.json`:

```json
{
  "summary": "<1-2 sentence overall summary>",
  "verdict": "PLAN READY" | "REVISE BEFORE TASKS" | "MAJOR GAPS — RECONSIDER DESIGN",
  "findings": [<deduplicated, verified findings array>]
}
```

Order findings: Critical → Important → Minor → Nit, then by `file` then by `line`.

### 5. Revise Loop

This skill **revises the plan in place** until it passes review. The deliverable is the improved plan document at `$PLAN_PATH`. Findings are **printed in chat each round — never written to a markdown file in the repo.** (The subagent JSON under `$SESSION_DIR` is internal plumbing and stays.)

Initialize `round = 1` and an empty `skip-set` (finding identities the user chose not to act on; identity = `plan-section::normalized-title`). If context was compacted mid-loop, re-read `$SESSION_DIR/meta.json` and the latest `$SESSION_DIR/compiled.json` to restore state, and re-derive the `skip-set` from your chat record.

Each round:

1. **Review.** (Round 1: the five specialists dispatched in §3 have already written `$SESSION_DIR/findings-*.json`.) For round > 1, re-dispatch the five specialists per §3 against the freshly-copied `$SESSION_DIR/plan.md`.
2. **Compile** per §4 into `$SESSION_DIR/compiled.json` with verdict.
3. **Effective findings** = `compiled.findings` whose identity is NOT in the `skip-set`.
4. **Form POV + classification for every effective finding.** Per the base rubric's "Orchestrator POV", from a targeted read of the cited plan section in `$SESSION_DIR/plan.md` (and any cited project file), emit for each finding a **recommendation** (`Fix` = revise the plan; `Defer` = real gap fine to nail down during Tasks/implementation; `Skip` = not worth a plan change) + one-sentence rationale + High/Low confidence, and a **classification** (`mechanical` = one obvious plan edit, e.g. adding the accepted-downside sentence to a recorded decision; `judgment` = a real choice in wording or design among options).
5. **Print findings in chat** — grouped by plan section heading, each with its POV line (e.g. `→ POV: Defer (High confidence) — real gap, but the exact retry budget is fine to settle in Tasks`). Do **not** write these to a file.
6. **Auto-revise.** For each effective finding where `recommendation == Fix` AND `classification == mechanical`, edit the plan document at `$PLAN_PATH` directly to address it (apply the finding's suggested replacement). Make these edits without asking.
7. **Interventions — escalate only owner-weighable blockers (per `escalation-base.md`).** For each
   **Critical/Important** effective finding, route its disposition with the shared rubric (modes
   PROCEED/NOTIFY/GATE). **GATE** (one consolidated `AskUserQuestion`) only the blockers whose
   skip-or-fix is genuinely the owner's call — a product/scope/risk trade-off. For the rest,
   **verify and proceed**, recording the disposition so `loop_state` still sees it:
   - **Fix, one right answer per the project's conventions** → auto-revise `$PLAN_PATH` (a step-6
     auto-revise).
   - **Verifiably-safe skip / believed false-positive** → record a **skip** (add the identity to the
     `skip-set`) **with a verification trace** (cite the spec line / source you checked). A skip with
     no citable ground truth is **not** eligible — it GATEs. **Never silently drop a blocker.**
   - Minor/Nit → apply the triage recommendation automatically (auto-revise or skip-set), reported
     in the terminal summary, never asked (the F4 win, preserved).
   Add every skipped identity (owner-skip or autonomous-skip) to the `skip-set`; it feeds
   `SKIPPED_BLOCKING` (step 8) so the gate reflects it. Record GATE outcomes and NOTIFY decisions in
   the terminal summary with their reverse-path/expiry, per `escalation-base.md`.

   Resolve the rubric for this dispatch once via the wrapper — with
   `REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)` (the project's canonical
   safe-capture pattern) defined in setup:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   RUBRIC_RES=$(python3 "$ROOT_DIR/lib/escalation_resolve.py" rubric --root "$REPO_ROOT")
   ```

   Read its `path` and embed the rubric (if `degraded` is true, apply the embedded fail-closed
   posture: apply the hard floor and GATE anything owner-weighable). **Keep step-8's `loop_state.py`
   invocation unchanged** (`--compiled "$SESSION_DIR/compiled.json" --skipped-blocking
   <SKIPPED_BLOCKING>`, the present-∩-skip-set integer per the `arch-r2-001` cumulative-PRESENT
   contract). The trio's `SKIPPED_BLOCKING` stays a prose-computed present-∩-skip-set integer and is
   deliberately **not** externalized to a cumulative `resolutions.json` — doing so drops the
   present-set intersection (the resolutions entries carry no finding identity) and reintroduces the
   loop-skipping bug.
   **Record decisions (learning loop):** append one `decisions.py` record per resolution to the resolved decisions store (`$DECISIONS`) (**Apply as suggested** → `fix`; **Apply with my guidance** → `guidance`; **Skip** → `skip`), per `## Learning Loop & Staleness Nudge`. Also append a `fix` record for each finding auto-revised in step 6. This append is non-blocking and never gates the loop.
8. **Refresh + continuation gate.** Re-copy the revised plan: `cp "$PLAN_PATH" "$SESSION_DIR/plan.md"`. Whether to re-review is **decided by a script, not by you** — a model rationalizes early exits ("the revision obviously resolved it", "it'll be clean next round"). Compute `SKIPPED_BLOCKING` = the count of Critical/Important findings in this round's `compiled.findings` whose identity is in the `skip-set` — the *present* skipped blockers (equivalently: blocking findings minus blocking **effective** findings from step 3). Count this **cumulatively every round**, not just the ones you added this round — the specialists re-flag a skipped finding each round, so a once-skipped blocker stays present and must keep being counted as skipped, else it reads as "present and addressed" forever and the loop can never reach `exit_skipped`. The gate **derives the number of blockers addressed from this round's `compiled.json`** (blockers present minus the present-and-skipped), so the addressed count is **not yours to self-report**. Run it and obey its `action`:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 "$ROOT_DIR/lib/loop_state.py" --round <N> --max-rounds 7 \
     --compiled "$SESSION_DIR/compiled.json" --skipped-blocking <SKIPPED_BLOCKING>
   ```

   - **`review`** → `round += 1` and repeat from step 1. **MANDATORY** — you revised a blocking finding; re-review to verify it actually resolved and introduced nothing new. Do **not** exit because the revision "looks resolved" (that belief is what this gate overrides).
   - **`exit_clean`** → **EXIT** the loop (then record the gate, §6).
   - **`exit_skipped`** → **EXIT**, listing the deliberately-skipped blocking finding(s) — not a plain PLAN READY.
   - **`halt`** → the 7-round cap was hit with blocking findings still being revised: report them; do **not** declare PLAN READY (coverage may be incomplete).

### 6. Record the review gate

After the loop exits, record the outcome on the plan doc — this is the machine-readable
signal the-architect's autonomous loop reads (it supersedes the plan skill's degraded-mode
self-certification). **Skip this step entirely when `isDefinitionDoc == no`** (there is no
gate to set; say so and stop at the terminal summary).

- **PLAN READY** (no unresolved Critical/Important; any Minor/Nit are informational) →
  record `passed`.
- **REVISE BEFORE TASKS / MAJOR GAPS**, or the 7-round cap was hit with Critical/Important
  still open, or the user **skipped** a blocking finding → record `changes-requested` (the
  plan is not cleared to advance; report what remains).

The gate write — and its guards — live in **one tested place**, `lib/gate_write.py` (the
same handshake review-tasks and review-spec use, so a fix can't miss a copy). It owns the
whole sequence and **degrades, it does not crash**: resolve the-architect's lib (the single
§3.1 frontmatter writer) cross-plugin → a **canonical-path guard** (refuse to stamp a doc
other than the one reviewed — `set-gate` reconstructs `docs/superheroes/<work-item>/plan.md`
from `--work-item`, so an out-of-layout `<path>` would otherwise hit a *different* doc) → the
**parent-gate precondition** (a plan is never certified `passed` while its `spec` isn't
approved — it downgrades to `changes-requested`) → a guarded `set-gate`. It prints a
human-readable detail to stderr and a one-word outcome to stdout:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
# REVIEW is "passed" or "changes-requested" per the verdict above.
GATE=$(python3 "$ROOT_DIR/lib/gate_write.py" --mode certify --doc plan \
  --work-item "$WORK_ITEM" --reviewed-path "$PLAN_PATH" --review "$REVIEW" \
  --parent-doc spec --root "$ROOT")
```

`$GATE` is one of `recorded:passed` / `recorded:changes-requested` / `skipped:noncanonical` /
`skipped:lib-absent` / `failed:set-gate` — surface it (and any stderr detail) in the terminal
summary. Never hand-edit the frontmatter — `gate_write.py` (via the-architect's CLI) is the
only writer.

After exit, print a terminal summary in chat:

- Lead with the final verdict label in bold, and the **gate outcome** (`$GATE` from the
  helper — e.g. `recorded:passed`, `recorded:changes-requested`, `skipped:noncanonical`,
  `skipped:lib-absent`; or "not recorded — not a definition-doc" when `isDefinitionDoc == no`,
  in which case step 6 was skipped). If the loop hit the 7-round cap with Critical/Important
  unresolved, the verdict is **REVISE** and the gate is `changes-requested` — do **not**
  declare PLAN READY.
- List, grouped by plan section heading, the revisions applied (auto + user-approved) and
  the findings the user chose to skip — each with its POV line.
- End with a count summary (e.g. `"2 auto-revised, 1 applied with guidance, 1 skipped;
  PLAN READY; gate → passed"`).

**Then, after the terminal summary**, run the three non-blocking end-of-run steps from `## Learning Loop & Staleness Nudge`, in order: (1) the **staleness nudge** (print the doctor `message` only when non-null and `nudge_acked` is false), (2) the **learning-loop proposal** (`decisions.py analyze` → at most one user-gated `AskUserQuestion`, never auto-applied), then (3) the **provisional-profile confirmation** (interactive only — offer to confirm a `status: provisional` profile; skipped when headless, already stable, or already acked). All three are placed after the review output and none blocks.

Nothing else is written to the repo — the revised `$PLAN_PATH` and its gate are the deliverables (plus the project-level `.claude/review-decisions.json` learning-loop store and, only on a dismissal, the profile's `nudge-ack` map).

## Learning Loop & Staleness Nudge

These four behaviors are **non-blocking**, run **at end of run** (after the terminal summary), and are **identical across `review-code`, `review-plan`, `review-spec`, `review-tasks`, and `audit-debt`**. Nothing here ever auto-applies a profile or `CLAUDE.md` edit — every change is user-gated.

### Recording decisions (at resolution time)

Wherever the user resolves a finding (this skill: the §5 step 7 interventions, plus the auto-revised findings in step 6), append ONE record per decision to the **project-level** learning-loop store at the resolved `$DECISIONS` path (NOT the temp `$SESSION_DIR`). Use the bundled helper:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/decisions.py" \
  append "$DECISIONS" '<record-json>'
```

`<record-json>` is `{"dimension": "<finding dimension>", "category": "<finding taxonomy/topic>", "action": "skip"|"guidance"|"fix"}`:
- `action` maps from the user's choice: **Skip** → `skip`; **Apply with my guidance** → `guidance`; **Apply as suggested** (and step-6 auto-revises) → `fix`.
- `dimension` is the finding's `dimension`; `category` is the finding's taxonomy/topic (its normalized title or topic tag). The store is append-only and atomic; it soft-fails on a bad/missing store, so this never blocks.

### Staleness nudge (end of run)

Using the `DOCTOR_JSON` captured in Setup: print the doctor's `message` as a single non-blocking line **only when** `message` is non-null AND `nudge_acked` is false:

> ℹ️ Profile may be stale: `<message>`. Run `/review-crew:review-init` to refresh (this nudge won't repeat once acknowledged).

If the user declines or ignores it, record the dismissal (see "Recording a dismissal" below) using the doctor's `signal_hash`. Suppress the line entirely when `nudge_acked` is true or `message` is null.

### Learning-loop proposal (end of run)

After the staleness nudge, analyze the decision store for a repeated signal:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 "$ROOT_DIR/lib/decisions.py" \
  analyze "$DECISIONS" --nudge-ack <comma-separated profile nudge-ack hashes>
```

Pass the profile's current `nudge-ack` map keys (read from the resolved profile (`$PROFILE`)'s provenance block) as the comma-separated `--nudge-ack` list so an already-dismissed proposal does not re-fire. If the result's `proposal` is non-null, present it via **ONE** `AskUserQuestion` (lead with `proposal.text`; the proposal names a `target` of `profile` or `CLAUDE.md`):
- **Apply to `<target>`** — apply the proposed calibration/convention edit to the named target.
- **Edit then apply** — open a free-text edit, then apply the edited version.
- **Dismiss** — do not apply; record the dismissal using `proposal.signal_hash` (see below).

**NEVER auto-apply.** A proposal is applied ONLY on the user's explicit **Apply** / **Edit then apply** choice. If `proposal` is null, do nothing.

### Provisional-profile confirmation (interactive only, end of run)

If the loaded profile's `status:` is `provisional` AND this run is interactive (a human is present to answer) AND the provisional-confirm signal is not already in the profile's `nudge-ack`, offer ONE non-blocking `AskUserQuestion` after the review output:

> This project's review profile was auto-generated (provisional) and hasn't been confirmed. Confirm it now?

- **Confirm (mark stable)** — flip the profile's provenance `status: provisional` → `status: stable` in the resolved profile (`$PROFILE`) (a small, user-approved provenance write; bump `updated:`). Nothing else changes.
- **Refresh via review-init** — point the user at `/review-crew:review-init` (its reconcile re-detects + can flip status) and do not change the profile now.
- **Keep provisional** — record a dismissal (see "Recording a dismissal") using the constant provisional-confirm signal hash so this does not re-ask until the profile changes.

Skip this entirely when the run is **headless/non-interactive** (no human to answer — never block an automated run), when `status:` is already `stable`, or when the provisional-confirm signal is already acknowledged.

### Recording a dismissal (shared)

The staleness nudge (above), the learning-loop proposal, and the provisional-profile confirmation share one dismissal mechanism: **write the relevant `signal_hash` into the profile's `nudge-ack` map** in the resolved profile (`$PROFILE`)'s provenance block, so the same signal does not re-fire until it changes. The map is `nudge-ack: {<hash>: true, ...}` on the provenance line; add the hash as a new key (the staleness nudge uses `DOCTOR_JSON.signal_hash`; the proposal uses `proposal.signal_hash`; the provisional-profile confirmation's **Keep provisional** uses a **constant signal** — the literal `provisional-confirm`). This is the ONLY write any of these nudges makes to the profile, and only on dismissal — it is not a calibration edit.

## Plan-Content Requirements (Opinionated)

Agents flag departures from these — the plan author should be able to point to each, or explicitly note "N/A — because …":

- **Spec coverage** — every functional requirement, NFR, and significant unhappy path in the parent spec maps to something in the plan ("How the requirements are met"); nothing in the plan lacks a spec basis.
- **≥2 options + accepted downside per significant decision** — each key decision names the alternatives weighed (materially different, on a named axis), the choice, the **accepted downside**, and reversible vs one-way door.
- **NFR validation** — the non-functional requirements are walked through the design, not just asserted.
- **Operability** — "how is this debugged at 2am / turned off / rolled back?" answered, or N/A with a reason.
- **Failure-handling** — for any multi-step write, outbound dependency, or migration the plan introduces: what happens on partial failure (or an explicit N/A). The premortem-reviewer checks this deterministically.
- **Right altitude** — strategy, not steps; no pasted full schemas / full code / test cases / dated rollout sequences (those are Tasks).

## Out of Scope at Plan Time

- **Naming preferences** — bikeshedding; names can change when code lands.
- **Implementation details the plan reasonably defers** — plans are not pseudocode.
- **Style / lint / type checks** — they fire on the eventual code.

## Common Mistakes

| Mistake                                                                     | Fix                                                                                                                                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Flagging implementation details at plan time                                | Those are Tasks/code-time concerns. The plan may defer "how" as long as "what" and "why" are clear.                                                             |
| Demanding exact test cases in the plan                                      | Test *strategy* belongs in the plan; the enumerated test list is Tasks. Don't grade Tasks-level content here.                                                    |
| Overwriting a `changes-requested` gate with `passed`                        | The gate write reflects the verdict. A skipped blocking finding or a 7-round cap with open Critical/Important → `changes-requested`, never `passed`.            |
| Hand-editing the frontmatter to set the gate                                | The gate is written only via the-architect's `definition_doc.py set-gate`. If that lib is absent, report "gate not recorded" — never hand-edit the YAML.        |
| Citing line numbers from the wrong file                                     | Plan-doc citations point at `$SESSION_DIR/plan.md`; project-file citations point at repo paths. Don't mix them.                                                 |
| Re-raising findings the user skipped                                        | Check the `skip-set` and prior rounds before raising a finding. The author shouldn't see the same finding twice without a new technical basis.                  |
| Skipping the all-five-specialists rule based on classification              | The `touches` array is informational. All five always run — each returns `[]` when there's nothing in its dimension.                                            |
| Dispatching reviewers by reading an agent file                              | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via `hosts/<your-host>-tools.md`).               |
| Skipping the profile bootstrap                                              | If no profile resolves, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                                        |
