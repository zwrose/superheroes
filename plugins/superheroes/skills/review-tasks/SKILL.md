---
name: review-tasks
description: "Use to review the-architect's `tasks` definition-doc (the bite-sized, test-first executable steps for a work-item) before the producer's Build runs it. Revises it in place and — on a clean pass — records the review gate (`gates.review: passed`) the autonomous loop reads."
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Review Tasks

Red-team the-architect's **`tasks` definition-doc** — the bite-sized, test-first executable
steps for a work-item (`docs/superheroes/<work-item>/tasks.md`) — **before** the producer's
Build executes them. The main context is an orchestrator: it locates the tasks doc, reads
its parent `plan` (and the `spec` behind it) for the work it must cover, dispatches the same
five specialist agents `/superheroes:review-code` uses (architecture, code, security, test,
premortem) in parallel against the tasks doc, compiles their findings under the base rubric,
attaches its own point of view to each finding, and **revises the tasks doc in place** —
auto-applying mechanical fixes and stopping to ask only about findings it would skip/defer or
fixes that involve a judgment call. On a clean exit it **records the review gate**
(`gates.review: passed`); if blocking findings remain it records `changes-requested`.

This is the **Tasks leg of the superheroes review trio** (`review-spec` / `review-plan` /
`review-tasks`) — the automated gate the-architect's `tasks` skill calls. Read the base
rubric (`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`) for severity calibration and the
verification rules every finding must pass; if anything below contradicts the base rubric,
the base rubric wins.

> **Band posture.** This reviews the superheroes `tasks` definition-doc (CONVENTIONS §3),
> designed to run inside the band alongside the-architect. If handed a doc with no
> `superheroes: doc` / `docType: tasks` frontmatter it **degrades, it does not crash**: it
> still red-teams the document, but skips the gate write and says so.

The tasks doc is the *how-exactly*: the writing-plans body (bite-sized checkbox TDD steps)
captured under the superheroes build contract (CONVENTIONS §3.2). Tasks-time review checks
that the steps are **executable and complete** and **faithfully cover the plan** — not that
they re-litigate the plan's design (that was `review-plan`'s job). A task that re-decides the
architecture is itself a finding (it belongs in the plan, or it's drift).

## Invocation

| Form                               | Behavior                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| `/superheroes:review-tasks`        | Review the most recent `docs/superheroes/*/tasks.md`.                        |
| `/superheroes:review-tasks <work-item>` | Review `docs/superheroes/<work-item>/tasks.md`.                         |
| `/superheroes:review-tasks <path>` | Review the tasks doc at `<path>` (relative to repo root or absolute).        |

If no tasks doc is found and no argument was passed, ask the user via `AskUserQuestion` before
continuing — there is nothing to review otherwise.

## Session Directory

All review artifacts live in a per-invocation temp directory so parallel reviews don't collide:

```bash
SESSION_DIR=$(mktemp -d /tmp/review-tasks-XXXXXXXX)
```

| Path                                      | Written by   | Purpose                                                        |
| ----------------------------------------- | ------------ | -------------------------------------------------------------- |
| `$SESSION_DIR/meta.json`                  | orchestrator | Tasks path, work-item, session dir, classification             |
| `$SESSION_DIR/tasks.md`                   | orchestrator | Stable copy of the target tasks doc — subagents read this      |
| `$SESSION_DIR/plan.md`                    | orchestrator | Stable copy of the parent plan (context for the reviewers)     |
| `$SESSION_DIR/spec.md`                    | orchestrator | Stable copy of the spec behind the plan (context)              |
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

**Staleness self-check (first action).** Before the profile bootstrap and before locating the tasks doc or dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. review-tasks reads the working tree (default root), so no `--root` is passed. Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below, not to staleness:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$EXISTS" = "true" ]; then
  DOCTOR_JSON=$(python3 "$ROOT_DIR/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION")
fi
```

Capture the JSON in `DOCTOR_JSON`. On `readable: false`, tell the user "profile unreadable — re-run `/superheroes:configure`" and **continue** (do not crash, do not block). Otherwise retain `message`, `signal_hash`, and `nudge_acked` for the **end-of-run staleness nudge** (see §6). Do NOT act on `drift` here — it is informational only.

**Profile bootstrap (run before locating the tasks doc or dispatching anything).** The review engine reads its per-project calibration from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$LOCATION" = "none" ]; then
  INTERACTIVE=true   # the orchestrator sets this to false on a headless/non-interactive run (no human to answer), so decide-location returns "global" deterministically instead of "ask"
  LOC=$(python3 "$ROOT_DIR/lib/review_store.py" decide-location --interactive "$INTERACTIVE")
  # If LOC is "ask" → AskUserQuestion, set LOC to owner's pick, then record band-wide (FR-3).
  # If LOC is already in-repo/global → skip record, go straight to create.
  REC=$(python3 "$ROOT_DIR/lib/mode_reconcile.py" reconcile --mode "$LOC" 2>/dev/null) || REC=""
  if [ -z "$REC" ] || printf '%s' "$REC" | jq -e '.written == false' >/dev/null 2>&1; then
    echo "note: couldn't record the band storage mode this run — you'll be asked again next time."
  fi
  PROFILE=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind profile --location "$LOC")
  DECISIONS=$(python3 "$ROOT_DIR/lib/review_store.py" create --kind decisions --location "$LOC")
fi
```

When `decide-location` returns `ask`, present the in-repo-vs-global `AskUserQuestion` (per the spec's *Halt-and-ask init flow*) and use the answer as `$LOC`.

When `$LOCATION` is `none`, run review-init's create procedure inline (`plugins/superheroes/skills/review-init/SKILL.md`, Steps 1–4: detect → interview → seed canonical patterns → write the profile to `$PROFILE`), then continue. Headless / non-interactive runs get a provisional, strict-threat-model profile from detected defaults. (Do not run any staleness, reconcile, or learning-loop step here — out of scope.)

**Locate the target tasks doc.** Resolve by work-item slug, explicit path, or most-recent:

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
if [ -n "$ARG" ] && [ -f "$ARG" ]; then
  TASKS_PATH="$ARG"                                            # explicit path
elif [ -n "$ARG" ] && [ -f "$ROOT/docs/superheroes/$ARG/tasks.md" ]; then
  TASKS_PATH="$ROOT/docs/superheroes/$ARG/tasks.md"            # work-item slug
else
  TASKS_PATH=$(ls -t "$ROOT"/docs/superheroes/*/tasks.md 2>/dev/null | head -1)   # most recent
fi
```

If `$TASKS_PATH` is empty or the file doesn't exist, use `AskUserQuestion` to ask for a work-item or path. Do not invent one.

**Derive the work-item and confirm this is a tasks definition-doc:**

```bash
WORK_ITEM=$(basename "$(dirname "$TASKS_PATH")")
IS_DEF_DOC=$(grep -qE '^superheroes:\s*doc' "$TASKS_PATH" && grep -qE '^docType:\s*tasks' "$TASKS_PATH" && echo yes || echo no)
```

If `IS_DEF_DOC` is `no`, note it and **proceed without a gate write** (degrade-not-crash): red-team the document, skip step 6.

Copy the tasks doc to a stable artifact path, copy its **parent plan** and the **spec** behind it for context (the tasks must faithfully cover the plan, which satisfies the spec), and classify what it touches:

```bash
cp "$TASKS_PATH" "$SESSION_DIR/tasks.md"
[ -f "$ROOT/docs/superheroes/$WORK_ITEM/plan.md" ] && cp "$ROOT/docs/superheroes/$WORK_ITEM/plan.md" "$SESSION_DIR/plan.md"
[ -f "$ROOT/docs/superheroes/$WORK_ITEM/spec.md" ] && cp "$ROOT/docs/superheroes/$WORK_ITEM/spec.md" "$SESSION_DIR/spec.md"

TOUCHES=()
grep -Eqi 'route|endpoint|api|handler'                  "$SESSION_DIR/tasks.md" && TOUCHES+=("API")
grep -Eqi 'component|view|page|screen|UI'               "$SESSION_DIR/tasks.md" && TOUCHES+=("UI")
grep -Eqi 'schema|migration|database|collection|table|model' "$SESSION_DIR/tasks.md" && TOUCHES+=("data")
grep -Eqi 'auth|session|permission|owner|tenant'        "$SESSION_DIR/tasks.md" && TOUCHES+=("auth")
grep -Eqi 'test|spec|coverage'                          "$SESSION_DIR/tasks.md" && TOUCHES+=("tests")
grep -Eqi 'architecture|layering|abstraction|module'    "$SESSION_DIR/tasks.md" && TOUCHES+=("architecture")
```

Write metadata:

```bash
cat > "$SESSION_DIR/meta.json" <<EOF
{
  "tasksPath": "$TASKS_PATH",
  "workItem": "$WORK_ITEM",
  "isDefinitionDoc": "$IS_DEF_DOC",
  "sessionDir": "$SESSION_DIR",
  "touches": $(printf '%s\n' "${TOUCHES[@]}" | jq -R . | jq -sc 'map(select(length>0))')
}
EOF
```

The classification is informational — **all five specialists still run**.

### 2. Dispatch Summary

Print this dispatch summary as a plain status message, then dispatch the specialists immediately (no approval gate):

- **Tasks doc:** `$TASKS_PATH` (work-item `$WORK_ITEM`) and its line count (`wc -l < $SESSION_DIR/tasks.md`)
- **Gate:** will be recorded on the tasks doc (`isDefinitionDoc == yes`), or skipped (`no` — degraded)
- **Classification:** the `touches` array
- **Specialists to dispatch (all five, in parallel):**
  - `test-reviewer` → `findings-test.json` _(does the heaviest lifting at tasks time — TDD discipline + coverage)_
  - `code-reviewer` → `findings-code.json` _(the step code: paths, snippets, type-consistency, no placeholders)_
  - `architecture-reviewer` → `findings-architecture.json` _(decomposition fidelity to the plan)_
  - `security-reviewer` → `findings-security.json`
  - `premortem-reviewer` → `findings-premortem.json` _(inter-task ordering / broken-tree-between-steps hazards)_
- **Session directory:** `$SESSION_DIR`

**Resolve the model tiers once (band-wide knob).** Resolve each specialist's dispatch model
via the shared knob, honoring any `## Model tiers` override block in the project profile
(`$PROFILE`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
MT="$ROOT_DIR/lib/model_tier_resolve.py"
OV=$(python3 "$ROOT_DIR/lib/model_tier_overrides.py" --profile "$PROFILE")  # {role:model} or {}
REVIEWER_MODEL=$(python3 "$MT" --role reviewer --overrides "$OV" | jq -r '.model // empty')
DEEP_MODEL=$(python3 "$MT" --role reviewer-deep --overrides "$OV" | jq -r '.model // empty')
```

When dispatching the specialists, pass `model: $DEEP_MODEL` to `security-reviewer` and
`architecture-reviewer`, and `model: $REVIEWER_MODEL` to the other three. An empty value means
"inherit the session model" — omit the `model` arg in that case.

### 3. Dispatch Specialists in Parallel

Launch all five specialists in a **single message with five parallel reviewer dispatches** so they run in parallel, each dispatched by its reviewer name (resolve dispatch via the host tool map). On Codex, dispatch is `spawn_agent` loading `agents/<name>.md`'s methodology; collect with `wait_agent` — see the tool map. Each gets the same prompt template, parameterized by reviewer name, dimension label, and findings filename. The agent's review methodology is its own system prompt — the prompt below is context-only (paths and rules); do **not** tell it to read an agent file. Embed the **absolute** base-rubric path (the expanded value of `RUBRIC`) so the subagent can read it. Substitute `<PROFILE_PATH>` with the resolved absolute `$PROFILE` when building each subagent prompt (subagents do not inherit shell vars):

```
You are reviewing the-architect's `tasks` definition-doc (the bite-sized,
test-first executable steps for a work-item), NOT code and NOT a diff.

## Your assignment
Review the tasks doc at $SESSION_DIR/tasks.md for your dimension. Its parent
`plan` is at $SESSION_DIR/plan.md and the `spec` behind it at $SESSION_DIR/spec.md
(if present) — the tasks must faithfully COVER the plan (which satisfies the
spec); cross-check against them. Read the base rubric (absolute path below) for
severity calibration, verification rules, and the findings output format. Read
the project profile and CLAUDE.md for calibration.

## Context files
- Tasks (the doc under review): $SESSION_DIR/tasks.md
- Parent plan (what the tasks must cover): $SESSION_DIR/plan.md
- Spec behind the plan (the ultimate requirements): $SESSION_DIR/spec.md
- Base rubric (severity, verification rules, findings format): <absolute RUBRIC path>
- Project profile (threat model, scope, focus hints, canonical patterns): <PROFILE_PATH>
- CLAUDE.md (project conventions): CLAUDE.md
- Project structure: feel free to Read/Grep/Glob the current repo to confirm the
  file paths, symbols, and packages the tasks reference actually exist.
- <if focus notes> Focus: <focus notes>

## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > profile (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## What a good `tasks` definition-doc must do (flag departures)
The tasks doc is the writing-plans body (bite-sized checkbox TDD steps) under the
superheroes build contract (CONVENTIONS §3.2). It is sound when:
- **Executable & complete — NO placeholders.** Every step is concrete: exact file
  paths, complete code in each code step, exact test commands with expected output.
  "TBD", "add error handling", "handle edge cases", "similar to Task N", "write
  tests for the above" (without the test code) are **failures**, not nits.
- **Faithful coverage of the plan.** Every plan component/interface and every spec
  requirement (functional, NFR, significant unhappy path) maps to at least one task;
  nothing in the tasks lacks a plan/spec basis. A requirement with no task is a gap;
  a task with no basis is scope creep.
- **TDD discipline.** Behavior is introduced test-first (a failing test, then the
  minimal code, then green); the spec's significant unhappy paths have test steps,
  not just the happy path.
- **Type/name consistency across tasks.** A symbol defined in an early task is
  referenced by the same name/signature later (e.g. `clearLayers()` in Task 3 vs
  `clearFullLayers()` in Task 7 is a bug).
- **Right altitude — steps, not strategy.** The tasks execute the plan; they do not
  re-decide the architecture. A task that re-architects (vs the plan) is a finding:
  it belongs in the plan, or it is drift.
- **Build contract present.** The doc carries the superheroes wrapper (size, the
  SDD clips) and the writing-plans body verbatim (Goal/Architecture/Tech-Stack, the
  **Global Constraints** block, and `### Task N` steps with their per-task **Interfaces**
  blocks where `writing-plans` ≥ 6.0 emits them), with the agentic-worker handoff replaced
  by the build contract and no orphan superpowers/plans artifact. The Global Constraints
  and Interfaces blocks are a quality SIGNAL — do not flag their presence; flag their
  absence only when the plan clearly needed them (cross-task contracts, a version/dependency
  floor) and they're missing.

## Per-dimension framing (you are reviewing executable steps)
- Test-reviewer (heaviest here): TDD ordering (failing test precedes implementation);
  are the spec's unhappy paths covered by test steps; are the tests meaningful (not
  tautologies / mock-echo); is anything asserted that the step's code can't satisfy.
- Code-reviewer: do the step code blocks fit conventions and reference real
  paths/symbols/packages (grep to confirm); type/name consistency across tasks;
  placeholder scan (the No-Placeholders bar).
- Architecture-reviewer: decomposition fidelity — do the tasks realize the plan's
  components/boundaries without re-architecting; is the task breakdown coherent and
  appropriately granular.
- Security-reviewer: where the plan specified an auth/ownership/validation check, do
  the tasks actually include a step that implements (and tests) it? Honor the
  profile's threat model.
- Premortem-reviewer: inter-task hazards — a step order that leaves the tree broken
  or untested between commits; a missing rollback/cleanup step; a task that depends
  on something an earlier task never produced. Honor the profile's threat model.

## Out of scope at tasks time
- Re-litigating the plan's design decisions (that was review-plan's job; only flag a
  task that CONTRADICTS or drifts from the plan).
- Naming preferences that don't break type-consistency.

## Verification rules
- `file:line` citation required. Cite the tasks-doc heading/step + line number, OR a
  related project file if the finding references existing code.
- Before flagging "missing X", grep the project for X under variant names.
- Before flagging a path/symbol/package "doesn't exist", actually check the repo /
  installed version — but a reference you cannot confirm IS worth flagging.

## Output
Write findings to $SESSION_DIR/findings-<agent>.json as a JSON array per the base
rubric's "Findings output format" section. The `file` field may be the tasks path
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

1. **Citation check.** Drop any finding with `file == null` or `line == null`.
2. **Dedupe by tasks section + topic.** When two findings target the same task/step and same topic, merge them: concatenate bodies with a separator, keep the higher severity, list both dimensions (e.g. `"Test + Code"`).
3. **Nit cap.** If more than 5 Nits remain after dedupe, keep the first 5 and summarize the rest as a count.

Determine the verdict per the base rubric's "Verdict labels & mapping". For `/superheroes:review-tasks` the labels are **TASKS READY** / **REVISE BEFORE BUILD** / **MAJOR GAPS — RECONSIDER PLAN**:

- 0 Critical, 0 Important → **TASKS READY**
- 0 Critical, 1+ Important → **REVISE BEFORE BUILD**
- 1+ Critical → **MAJOR GAPS — RECONSIDER PLAN**
- Only Minor and/or Nit → **TASKS READY** (Minor/Nit are informational)

Write to `$SESSION_DIR/compiled.json`:

```json
{
  "summary": "<1-2 sentence overall summary>",
  "verdict": "TASKS READY" | "REVISE BEFORE BUILD" | "MAJOR GAPS — RECONSIDER PLAN",
  "findings": [<deduplicated, verified findings array>]
}
```

Order findings: Critical → Important → Minor → Nit, then by `file` then by `line`.

### 5. Revise Loop

This skill **revises the tasks doc in place** until it passes review. The deliverable is the improved tasks document at `$TASKS_PATH`. Findings are **printed in chat each round — never written to a markdown file in the repo.** (The subagent JSON under `$SESSION_DIR` is internal plumbing and stays.)

Initialize `round = 1` and an empty `skip-set` (finding identities the user chose not to act on; identity = `task-step::normalized-title`). If context was compacted mid-loop, re-read `$SESSION_DIR/meta.json` and the latest `$SESSION_DIR/compiled.json` to restore state, and re-derive the `skip-set` from your chat record.

Each round:

1. **Review.** (Round 1: the five specialists dispatched in §3 have already written `$SESSION_DIR/findings-*.json`.) For round > 1, re-dispatch the five specialists per §3 against the freshly-copied `$SESSION_DIR/tasks.md`.
2. **Compile** per §4 into `$SESSION_DIR/compiled.json` with verdict.
3. **Effective findings** = `compiled.findings` whose identity is NOT in the `skip-set`.
4. **Form POV + classification for every effective finding.** Per the base rubric's "Orchestrator POV", from a targeted read of the cited step in `$SESSION_DIR/tasks.md` (and any cited project file), emit for each finding a **recommendation** (`Fix` = revise the tasks doc; `Defer` = real but fine to settle during Build; `Skip` = not worth a change) + one-sentence rationale + High/Low confidence, and a **classification** (`mechanical` = one obvious edit, e.g. filling in a placeholder with the concrete code/command; `judgment` = a real choice among options, e.g. how to decompose a step). A **placeholder** or a **missing-coverage** finding is almost always `Fix` + `mechanical` — the tasks bar forbids placeholders.
5. **Print findings in chat** — grouped by task/step, each with its POV line. Do **not** write these to a file.
6. **Auto-revise.** For each effective finding where `recommendation == Fix` AND `classification == mechanical`, edit the tasks document at `$TASKS_PATH` directly to address it. Make these edits without asking. **If a finding exposes a real gap in the PLAN** (a requirement the plan never covered, so no task can faithfully cover it), do **not** invent a task — flag it for the user as a loop-back to `review-plan`/`plan` (a `judgment` intervention), since tasks must not re-decide design.
7. **Interventions — escalate only owner-weighable blockers (per `escalation-base.md`).** For each
   **Critical/Important** effective finding, route its disposition with the shared rubric (modes
   PROCEED/NOTIFY/GATE). **GATE** (one consolidated `AskUserQuestion`) only the blockers whose
   skip-or-fix is genuinely the owner's call — a product/scope/risk trade-off. For the rest,
   **verify and proceed**, recording the disposition so `loop_state` still sees it:
   - **Fix, one right answer per the project's conventions** → auto-revise `$TASKS_PATH` (a step-6
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
8. **Refresh + continuation gate.** Re-copy the revised doc: `cp "$TASKS_PATH" "$SESSION_DIR/tasks.md"`. Whether to re-review is **decided by a script, not by you** — a model rationalizes early exits ("the revision obviously resolved it", "it'll be clean next round"). Compute `SKIPPED_BLOCKING` = the count of Critical/Important findings in this round's `compiled.findings` whose identity is in the `skip-set` — the *present* skipped blockers (equivalently: blocking findings minus blocking **effective** findings from step 3). Count this **cumulatively every round**, not just the ones you added this round — the specialists re-flag a skipped finding each round, so a once-skipped blocker stays present and must keep being counted as skipped, else it reads as "present and addressed" forever and the loop can never reach `exit_skipped`. The gate **derives the number of blockers addressed from this round's `compiled.json`** (blockers present minus the present-and-skipped), so the addressed count is **not yours to self-report**. Run it and obey its `action`:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 "$ROOT_DIR/lib/loop_state.py" --round <N> --max-rounds 7 \
     --compiled "$SESSION_DIR/compiled.json" --skipped-blocking <SKIPPED_BLOCKING>
   ```

   - **`review`** → `round += 1` and repeat from step 1. **MANDATORY** — you revised a blocking finding; re-review to verify it actually resolved and introduced nothing new. Do **not** exit because the revision "looks resolved."
   - **`exit_clean`** → **EXIT** the loop (then record the gate, §6).
   - **`exit_skipped`** → **EXIT**, listing the deliberately-skipped blocking finding(s) — not a plain TASKS READY.
   - **`halt`** → the 7-round cap was hit with blocking findings still being revised: report them; do **not** declare TASKS READY.

### 6. Record the review gate

After the loop exits, record the outcome on the tasks doc — the machine-readable signal the
producer's Build reads (it supersedes the-architect's `tasks` self-certification). **Skip
this step entirely when `isDefinitionDoc == no`.**

- **TASKS READY** (no unresolved Critical/Important) → record `passed`.
- **REVISE BEFORE BUILD / MAJOR GAPS**, or the 7-round cap hit with Critical/Important still
  open, or the user **skipped** a blocking finding → record `changes-requested`.

The gate write — and its guards — live in **one tested place**, `lib/gate_write.py` (the
same handshake review-plan and review-spec use, so a fix can't miss a copy). It owns the
whole sequence and **degrades, it does not crash**: resolve the-architect's lib (the single
§3.1 frontmatter writer) cross-plugin → a **canonical-path guard** (refuse to stamp a doc
other than the one reviewed — `set-gate` reconstructs `docs/superheroes/<work-item>/tasks.md`
from `--work-item`, so an out-of-layout `<path>` would otherwise hit a *different* doc) → the
**parent-gate precondition** (tasks are never certified `passed` while the `plan` isn't
approved — it downgrades to `changes-requested`) → a guarded `set-gate`. It prints a
human-readable detail to stderr and a one-word outcome to stdout:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
ROOT=$(git rev-parse --show-toplevel)
# REVIEW is "passed" or "changes-requested" per the verdict above.
GATE=$(python3 "$ROOT_DIR/lib/gate_write.py" --mode certify --doc tasks \
  --work-item "$WORK_ITEM" --reviewed-path "$TASKS_PATH" --review "$REVIEW" \
  --parent-doc plan --root "$ROOT")
```

`$GATE` is one of `recorded:passed` / `recorded:changes-requested` / `skipped:noncanonical` /
`failed:set-gate` — surface it (and any stderr detail) in the terminal
summary. Never hand-edit the frontmatter — `gate_write.py` (via the-architect's CLI) is the
only writer.

After exit, print a terminal summary in chat:

- Lead with the final verdict label in bold, and the **gate outcome** (`$GATE` from the
  helper; or "not recorded — not a definition-doc" when `isDefinitionDoc == no`, in which case
  step 6 was skipped). If the loop hit the 7-round cap with Critical/Important unresolved, the
  verdict is **REVISE** and the gate is `changes-requested` — do **not** declare TASKS READY.
- List, grouped by task/step, the revisions applied (auto + user-approved) and the findings the
  user chose to skip — each with its POV line.
- End with a count summary (e.g. `"3 auto-revised, 1 skipped; TASKS READY; gate → passed"`).

**Then, after the terminal summary**, run the three non-blocking end-of-run steps from `## Learning Loop & Staleness Nudge`, in order: (1) the **staleness nudge**, (2) the **learning-loop proposal**, then (3) the **provisional-profile confirmation**. All three are placed after the review output and none blocks.

Nothing else is written to the repo — the revised `$TASKS_PATH` and its gate are the deliverables (plus the project-level `.claude/review-decisions.json` learning-loop store and, only on a dismissal, the profile's `nudge-ack` map).

For recurrence handling, coverage decisions, dimension skipping, tier cascade, final confirmation, and telemetry, use `plugins/superheroes/reference/review-loop.md` as the shared loop contract. This skill owns only its leg-specific setup, reviewer framing, and gate-write rules.

## Tasks-Content Requirements (Opinionated)

Agents flag departures from these — every one is in the writing-plans + CONVENTIONS §3.2 contract:

- **No placeholders** — no "TBD", "add validation", "handle edge cases", "similar to Task N", or "write tests for the above" without the actual code. Every code step shows the code; every test step shows the command + expected output.
- **Plan/spec coverage** — every plan component/interface and every spec requirement (functional, NFR, unhappy path) maps to at least one task; nothing lacks a basis.
- **TDD discipline** — behavior is introduced test-first; the spec's significant unhappy paths have test steps.
- **Type/name consistency** — symbols defined in early tasks are referenced identically later.
- **Right altitude** — executable steps, not the plan's strategy restated; no task re-decides the design.
- **Build contract present** — size + the SDD clips + the writing-plans body verbatim (incl. the Global Constraints + per-task Interfaces blocks where `writing-plans` ≥ 6.0 emits them); no orphan superpowers/plans artifact.

## Out of Scope at Tasks Time

- **Re-litigating the plan's design** — that was review-plan. Only flag a task that contradicts or drifts from the plan.
- **Naming preferences** that don't break type-consistency.
- **Style / lint / type checks** — they fire on the eventual code.

## Common Mistakes

| Mistake                                                                     | Fix                                                                                                                                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Re-reviewing the plan's design decisions at tasks time                      | That was review-plan's job. Here, only flag a task that contradicts or drifts from the plan — design is settled.                                                |
| Tolerating a placeholder ("add error handling")                             | The tasks bar forbids placeholders. A placeholder is a Fix + mechanical finding — fill it with the concrete code/command, or flag the plan gap behind it.        |
| Inventing a task to cover a missing requirement                             | If the PLAN never covered a requirement, tasks can't faithfully add it — loop back to review-plan/plan. Tasks must not re-decide design.                         |
| Overwriting a `changes-requested` gate with `passed`                        | The gate write reflects the verdict. A skipped blocking finding or a 7-round cap with open Critical/Important → `changes-requested`, never `passed`.            |
| Hand-editing the frontmatter to set the gate                                | The gate is written only via the-architect's `definition_doc.py set-gate`. If that lib is absent, report "gate not recorded" — never hand-edit the YAML.        |
| Citing line numbers from the wrong file                                     | Tasks-doc citations point at `$SESSION_DIR/tasks.md`; project-file citations point at repo paths. Don't mix them.                                               |
| Re-raising findings the user skipped                                        | Check the `skip-set` and prior rounds before raising a finding.                                                                                                 |
| Skipping the all-five-specialists rule based on classification              | The `touches` array is informational. All five always run — each returns `[]` when there's nothing in its dimension.                                            |
| Dispatching reviewers by reading an agent file                              | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map).               |
| Skipping the profile bootstrap                                              | If no profile resolves, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                                        |
