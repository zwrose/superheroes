---
name: review-spec
description: Use to review the-architect's `spec` definition-doc (the plain-language requirements / the *what* for a work-item) before the owner gives final approval. Red-teams the spec against the base rubric with the five specialist agents — reframed to requirements quality (EARS, acceptance criteria, unhappy-path coverage, no tech leak, plain language) — and revises it in place. ADVISORY: it never records `passed` (the owner is the spec's gate authority in Discovery); it improves the doc and reports a readiness verdict. The Spec leg of the superheroes review trio (review-spec / review-plan / review-tasks).
user-invocable: true
---

# Review Spec

Red-team the-architect's **`spec` definition-doc** — the plain-language requirements (the
*what*) for a work-item (`docs/superheroes/<work-item>/spec.md`) — **before the owner gives
final approval**. Discovery runs this (step 7) so the automated review catches ambiguity,
missing coverage, and tech leakage **before** the owner spends their time. The main context
is an orchestrator: it locates the spec, dispatches the same five specialist agents
`/review-crew:review-code` uses (architecture, code, security, test, premortem) — **reframed
to requirements quality** — in parallel against the spec, compiles their findings under the
base rubric, attaches its own point of view, and **revises the spec in place** (auto-applying
mechanical fixes, asking about judgment calls), then reports a readiness verdict.

**review-spec is ADVISORY — it never records `gates.review: passed`.** The **owner** is the
spec's gate authority (the spec is the *what*, which only the owner can approve); Discovery
records the owner's approval (its step 8). review-spec advises and improves; it does not
approve on the owner's behalf. This is the deliberate asymmetry with `review-plan` /
`review-tasks` (which *certify* an autonomous doc's gate) — see the base rubric's verdict
mapping.

This is the **Spec leg of the superheroes review trio** — the automated *spec-review*
the-architect's `discovery` skill calls (an automated **review**, not a gate: it never
grants `passed`). Read the base rubric (`${CLAUDE_PLUGIN_ROOT}/rubric/review-base.md`)
for severity calibration and the verification rules every finding must pass; if anything
below contradicts the base rubric, the base rubric wins.

> **Band posture.** This reviews the superheroes `spec` definition-doc (CONVENTIONS §3),
> designed to run inside the band alongside the-architect. If handed a doc with no
> `superheroes: doc` / `docType: spec` frontmatter it **degrades, it does not crash**: it
> still red-teams the document and reports (it never grants `passed`; a non-definition-doc
> has no gate to reset either).

Spec review is about the **requirements**, not code or design. The spec is plain-language,
owner-facing, and **carries no technical *how*** (that is the `plan`). The reviewers' job is
to flag where the spec is **vague, unverifiable, internally inconsistent, missing a
significant unhappy path, or leaking implementation** — not to propose a technical approach
(proposing the *how* here is itself a finding).

## Invocation

| Form                              | Behavior                                                                     |
| --------------------------------- | ---------------------------------------------------------------------------- |
| `/review-crew:review-spec`        | Review the most recent `docs/superheroes/*/spec.md`.                         |
| `/review-crew:review-spec <work-item>` | Review `docs/superheroes/<work-item>/spec.md`.                          |
| `/review-crew:review-spec <path>` | Review the spec doc at `<path>` (relative to repo root or absolute).         |

If no spec doc is found and no argument was passed, ask the user via `AskUserQuestion` before
continuing — there is nothing to review otherwise.

## Session Directory

All review artifacts live in a per-invocation temp directory so parallel reviews don't collide:

```bash
SESSION_DIR=$(mktemp -d /tmp/review-spec-XXXXXXXX)
```

| Path                                      | Written by   | Purpose                                                        |
| ----------------------------------------- | ------------ | -------------------------------------------------------------- |
| `$SESSION_DIR/meta.json`                  | orchestrator | Spec path, work-item, session dir, classification              |
| `$SESSION_DIR/spec.md`                    | orchestrator | Stable copy of the target spec doc — subagents read this       |
| `$SESSION_DIR/findings-architecture.json` | arch agent   | Architecture-reviewer findings array                           |
| `$SESSION_DIR/findings-code.json`         | code agent   | Code-reviewer findings array                                   |
| `$SESSION_DIR/findings-security.json`     | sec agent    | Security-reviewer findings array                               |
| `$SESSION_DIR/findings-test.json`         | test agent   | Test-reviewer findings array                                   |
| `$SESSION_DIR/findings-premortem.json`    | premortem agent | Premortem-reviewer (Failure-Mode) findings array            |
| `$SESSION_DIR/compiled.json`              | orchestrator | Deduplicated, verified findings + summary + verdict            |

## Workflow

### 1. Setup

**Resolve the base rubric path once.** The base rubric is bundled at `${CLAUDE_PLUGIN_ROOT}/rubric/review-base.md`. Capture the rubric path so it can be embedded — **expanded to an absolute path** — into subagent prompts (subagents may not inherit `${CLAUDE_PLUGIN_ROOT}`):

```bash
RUBRIC="${CLAUDE_PLUGIN_ROOT}/rubric/review-base.md"   # absolute; embed the expanded value in subagent prompts
```

**Resolve the profile and decisions paths once (resolver-driven).** The profile/decisions may live in-repo (`./.claude/`) or in the global per-repo store; `review_store.py resolve` returns the resolved path (or `location: none` when nothing exists yet). Capture `$PROFILE`, `$LOCATION`, `$EXISTS`, and `$DECISIONS` here, before the staleness self-check and profile bootstrap below use them:

```bash
RES=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/review_store.py" resolve --kind profile) \
  || { echo "review_store resolve failed — continuing with strict fallback"; RES='{"location":"none","exists":false,"path":null}'; }
PROFILE=$(printf '%s' "$RES" | jq -r '.path // empty')
LOCATION=$(printf '%s' "$RES" | jq -r .location)
EXISTS=$(printf '%s' "$RES" | jq -r .exists)
DRES=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/review_store.py" resolve --kind decisions) \
  || { echo "review_store resolve --kind decisions failed"; DRES='{"path":null}'; }
DECISIONS=$(printf '%s' "$DRES" | jq -r '.path // empty')
```

Also resolve the engine versions the staleness self-check (next) needs — the **plugin version** from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` (`version`) and the **rubric-version** from the first line of `$RUBRIC` (`<!-- rubric-version: N -->`):

```bash
PLUGIN_VERSION=$(python3 -c "import json;print(json.load(open('${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json'))['version'])")
RUBRIC_VERSION=$(sed -n 's/.*rubric-version: *\([0-9][0-9]*\).*/\1/p' "$RUBRIC" | head -1)
```

**Staleness self-check (first action).** Before the profile bootstrap and before locating the spec or dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. review-spec reads the working tree (default root), so no `--root` is passed. Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below, not to staleness:

```bash
if [ "$EXISTS" = "true" ]; then
  DOCTOR_JSON=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION")
fi
```

Capture the JSON in `DOCTOR_JSON`. On `readable: false`, tell the user "profile unreadable — re-run `/review-crew:review-init`" and **continue** (do not crash, do not block). Otherwise retain `message`, `signal_hash`, and `nudge_acked` for the **end-of-run staleness nudge** (see §6). Do NOT act on `drift` here — it is informational only.

**Profile bootstrap (run before locating the spec or dispatching anything).** The review engine reads its per-project calibration from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

```bash
if [ "$LOCATION" = "none" ]; then
  INTERACTIVE=true   # the orchestrator sets this to false on a headless/non-interactive run (no human to answer), so decide-location returns "global" deterministically instead of "ask"
  LOC=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/review_store.py" decide-location --interactive "$INTERACTIVE")
  # If LOC is "ask", STOP — present the in-repo-vs-global AskUserQuestion, set LOC, then run the create calls below.
  PROFILE=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/review_store.py" create --kind profile --location "$LOC")
  DECISIONS=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/review_store.py" create --kind decisions --location "$LOC")
fi
```

When `decide-location` returns `ask`, present the in-repo-vs-global `AskUserQuestion` (per the spec's *Halt-and-ask init flow*) and use the answer as `$LOC`.

When `$LOCATION` is `none`, run review-init's create procedure inline (`plugins/review-crew/skills/review-init/SKILL.md`, Steps 1–4: detect → interview → seed canonical patterns → write the profile to `$PROFILE`), then continue. Headless / non-interactive runs get a provisional, strict-threat-model profile from detected defaults. (Do not run any staleness, reconcile, or learning-loop step here — out of scope.)

**Locate the target spec doc.** Resolve by work-item slug, explicit path, or most-recent:

```bash
ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
if [ -n "$ARG" ] && [ -f "$ARG" ]; then
  SPEC_PATH="$ARG"                                            # explicit path
elif [ -n "$ARG" ] && [ -f "$ROOT/docs/superheroes/$ARG/spec.md" ]; then
  SPEC_PATH="$ROOT/docs/superheroes/$ARG/spec.md"             # work-item slug
else
  SPEC_PATH=$(ls -t "$ROOT"/docs/superheroes/*/spec.md 2>/dev/null | head -1)   # most recent
fi
```

If `$SPEC_PATH` is empty or the file doesn't exist, use `AskUserQuestion` to ask for a work-item or path. Do not invent one.

**Derive the work-item and note whether this is a spec definition-doc** (review-spec never grants `passed`; the work-item labels the report and scopes the step-6 stale-approval reset):

```bash
WORK_ITEM=$(basename "$(dirname "$SPEC_PATH")")
IS_DEF_DOC=$(grep -qE '^superheroes:\s*doc' "$SPEC_PATH" && grep -qE '^docType:\s*spec' "$SPEC_PATH" && echo yes || echo no)
```

Copy the spec to a stable artifact path and classify what it touches (over the requirements text):

```bash
cp "$SPEC_PATH" "$SESSION_DIR/spec.md"

TOUCHES=()
grep -Eqi 'sign|login|account|permission|owner|private|personal' "$SESSION_DIR/spec.md" && TOUCHES+=("access")
grep -Eqi 'screen|page|view|button|form|display|show'             "$SESSION_DIR/spec.md" && TOUCHES+=("UI")
grep -Eqi 'save|store|record|history|data|list'                   "$SESSION_DIR/spec.md" && TOUCHES+=("data")
grep -Eqi 'limit|maximum|at most|per |rate'                       "$SESSION_DIR/spec.md" && TOUCHES+=("limits")
grep -Eqi 'payment|charge|money|price|cost|bill'                  "$SESSION_DIR/spec.md" && TOUCHES+=("money")
```

Write metadata:

```bash
cat > "$SESSION_DIR/meta.json" <<EOF
{
  "specPath": "$SPEC_PATH",
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

- **Spec doc:** `$SPEC_PATH` (work-item `$WORK_ITEM`) and its line count (`wc -l < $SESSION_DIR/spec.md`)
- **Gate:** advisory — never grants `passed` (the owner approves in Discovery); may reset a *stale* approval to `pending` (step 6).
- **Classification:** the `touches` array (e.g. `["access", "data", "money"]`)
- **Specialists to dispatch (all five, in parallel — reframed to requirements quality):**
  - `code-reviewer` → `findings-code.json` _(requirements clarity: EARS form, anti-slop, no tech leak)_
  - `test-reviewer` → `findings-test.json` _(verifiability: every requirement has an acceptance criterion)_
  - `premortem-reviewer` → `findings-premortem.json` _(coverage gaps: which significant unhappy path is missing)_
  - `security-reviewer` → `findings-security.json` _(are access/privacy requirements captured as owner-visible outcomes)_
  - `architecture-reviewer` → `findings-architecture.json` _(scope coherence: one work-item or several; internal consistency)_
- **Session directory:** `$SESSION_DIR`

### 3. Dispatch Specialists in Parallel

Launch all five specialists in a **single message with five `Agent` tool calls** so they run in parallel, each dispatched by its `subagent_type` (the agent's name). Each gets the same prompt template, parameterized by `subagent_type`, dimension label, and findings filename. The agent's review methodology is its own system prompt — the prompt below is context-only (paths and rules); do **not** tell it to read an agent file. Embed the **absolute** base-rubric path (the expanded value of `RUBRIC`) so the subagent can read it. Substitute `<PROFILE_PATH>` with the resolved absolute `$PROFILE` when building each subagent prompt (subagents do not inherit shell vars):

```
You are reviewing the-architect's `spec` definition-doc — the plain-language
REQUIREMENTS (the *what*) for a work-item. NOT code, NOT a technical design.

## Your assignment
Review the spec at $SESSION_DIR/spec.md for your dimension, reframed to
requirements quality (below). Read the base rubric (absolute path below) for
severity calibration, verification rules, and the findings output format. Read
the project profile and CLAUDE.md for calibration.

## Context files
- Spec (the doc under review): $SESSION_DIR/spec.md
- Base rubric (severity, verification rules, findings format): <absolute RUBRIC path>
- Project profile (threat model, scope, focus hints): <PROFILE_PATH>
- CLAUDE.md (project conventions): CLAUDE.md
- <if focus notes> Focus: <focus notes>

## Calibration precedence
Base rubric (binding) > CLAUDE.md (conventions) > profile (adder over CLAUDE.md)
> strict fallback when a needed field is absent in all of them.

## The spec is the *what*, owner-facing, NO tech
The spec is plain-language requirements the owner co-authored. It must carry **no
implementation/how** (libraries, schemas, APIs, frameworks) — that is the `plan`.
**Proposing a technical approach is itself out of scope here; flag tech that LEAKED
into the spec, don't add more.** A good spec is:
- **Functional requirements in EARS** (`When`/`While`/`Where`/`If-Then` + "the
  system shall …"), one behavior each (no "and/or" chaining), with **≥1 acceptance
  criterion** apiece (Given-When-Then for a flow, a pass/fail rule for a constraint).
- **No vague/unmeasurable words** (fast, secure, robust, user-friendly, handle,
  support, manage, always/never, some/most) — each replaced by a concrete behavior
  or fit-criterion.
- **Significant unhappy paths covered** (the coverage checklist: empty/first-run,
  invalid input, boundaries, errors, access/permissions, duplicates/double-actions,
  concurrent use, misuse/abuse, reach) — each owner-facing area Specify / Defer-to-
  plan / N-A. A missing significant unhappy path is the #1 spec gap.
- **Non-functional requirements as outcomes with a fit-criterion** (e.g. "a page
  they wait on responds within 2 seconds"), never as a mechanism.
- **UI/UX references the Claude Design handoff output**, not a reinterpretation.
- **Internally consistent and singular in scope** (one work-item, not several
  bundled), with definition of done, assumptions, constraints, and out-of-scope
  present. No leftover `{{…}}` / TBD / author-guidance comments.

## Per-dimension framing (you are reviewing REQUIREMENTS)
- Code-reviewer: requirements clarity & anti-slop — EARS form, one-behavior-each,
  no vague words, an acceptance criterion on every functional requirement, and
  **no technical *how* leaked** into the spec. Split compound requirements; flag
  unmeasurable ones.
- Test-reviewer: verifiability — is each requirement testable as written? Does each
  carry an acceptance criterion, and do the significant unhappy paths have criteria
  (not just the happy path)? A requirement you can't write a pass/fail for is too
  vague.
- Premortem-reviewer: coverage gaps — walk the coverage checklist and name the
  significant unhappy path the spec OMITS (the empty state, the invalid input, the
  wrong-person-access case, the double-submit, the limit) that will bite later.
  Honor the profile's threat model (don't demand multi-user cases for a single-user
  product).
- Security-reviewer: are the **owner-visible** security/privacy/access requirements
  captured — who may see/do what, what the wrong person sees, what must never leak —
  as outcomes, not mechanisms? Flag a sensitive feature (money, personal data) with
  no stated access rule. Do NOT propose an implementation.
- Architecture-reviewer: scope coherence — is this genuinely ONE work-item, or
  several bundled (should it be decomposed)? Are requirements mutually consistent
  (no two that contradict)? Is anything specified that isn't this work-item's job?

## Out of scope at spec time
- Proposing or grading a technical approach (that is the `plan`; only flag tech that
  leaked in).
- Wording/style preferences that don't affect clarity or verifiability.

## Verification rules
- `file:line` citation required — cite the spec heading/requirement + line number.
- Before flagging "missing unhappy path X", check it isn't already covered under a
  different heading or tagged Defer-to-plan / N-A.
- Before flagging "vague", confirm there is no acceptance criterion elsewhere that
  pins it.

## Output
Write findings to $SESSION_DIR/findings-<agent>.json as a JSON array per the base
rubric's "Findings output format" section. The `file` is the spec path. Set
`dimension` to "<dimension>" on every entry. If you have nothing to flag, write
`[]` — do not skip writing the file.
```

Per-agent substitutions:

| Agent slug / `subagent_type` | `<agent>` (findings filename) | `<dimension>` |
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
2. **Dedupe by spec section + topic.** When two findings target the same requirement and same topic (e.g. both flagging "no acceptance criterion"), merge them: concatenate bodies with a separator, keep the higher severity, list both dimensions (e.g. `"Test + Code"`).
3. **Nit cap.** If more than 5 Nits remain after dedupe, keep the first 5 and summarize the rest as a count.

Determine the verdict per the base rubric's "Verdict labels & mapping". For `/review-crew:review-spec` the labels are **SPEC READY** / **REVISE BEFORE OWNER REVIEW** / **MAJOR GAPS — RETURN TO DISCOVERY**:

- 0 Critical, 0 Important → **SPEC READY** (ready for the owner's review)
- 0 Critical, 1+ Important → **REVISE BEFORE OWNER REVIEW**
- 1+ Critical → **MAJOR GAPS — RETURN TO DISCOVERY**
- Only Minor and/or Nit → **SPEC READY** (Minor/Nit are informational)

"Ready" here means **ready for the owner to review and approve** — *not* approved. review-spec never approves the spec.

Write to `$SESSION_DIR/compiled.json`:

```json
{
  "summary": "<1-2 sentence overall summary>",
  "verdict": "SPEC READY" | "REVISE BEFORE OWNER REVIEW" | "MAJOR GAPS — RETURN TO DISCOVERY",
  "findings": [<deduplicated, verified findings array>]
}
```

Order findings: Critical → Important → Minor → Nit, then by `file` then by `line`.

### 5. Revise Loop

This skill **revises the spec in place** until it is ready for the owner's review. The deliverable is the improved spec at `$SPEC_PATH`. Findings are **printed in chat each round — never written to a markdown file in the repo.** (The subagent JSON under `$SESSION_DIR` is internal plumbing and stays.)

Keep every revision in the spec's voice: **plain language, owner-facing, no technical *how***. A fix that adds implementation detail is wrong even if it resolves the finding.

Initialize `round = 1` and an empty `skip-set` (finding identities the user chose not to act on; identity = `spec-section::normalized-title`). If context was compacted mid-loop, re-read `$SESSION_DIR/meta.json` and the latest `$SESSION_DIR/compiled.json`, and re-derive the `skip-set` from your chat record.

Each round:

1. **Review.** (Round 1: the five specialists dispatched in §3 have already written `$SESSION_DIR/findings-*.json`.) For round > 1, re-dispatch the five specialists per §3 against the freshly-copied `$SESSION_DIR/spec.md`.
2. **Compile** per §4 into `$SESSION_DIR/compiled.json` with verdict.
3. **Effective findings** = `compiled.findings` whose identity is NOT in the `skip-set`.
4. **Form POV + classification for every effective finding.** Per the base rubric's "Orchestrator POV", from a targeted read of the cited requirement in `$SESSION_DIR/spec.md`, emit for each finding a **recommendation** (`Fix` = revise the spec; `Defer` = legitimately defer-to-plan; `Skip` = not worth a change) + one-sentence rationale + High/Low confidence, and a **classification** (`mechanical` = one obvious edit, e.g. rephrasing a requirement into EARS or adding an acceptance criterion; `judgment` = a real requirements question only the owner can answer — e.g. "what SHOULD happen on a double-submit?").
   **A genuine requirements question is a `judgment` finding for the owner, never an invented answer.** review-spec must not fabricate a requirement the owner never stated; surface it.
5. **Print findings in chat** — grouped by spec section, each with its POV line. Do **not** write these to a file.
6. **Auto-revise.** For each effective finding where `recommendation == Fix` AND `classification == mechanical`, edit the spec at `$SPEC_PATH` directly (EARS rephrasing, adding a missing acceptance criterion, removing leaked tech, splitting a compound requirement). Make these edits without asking. Keep the owner's voice; never invent a behavior the owner didn't state.
7. **Interventions.** `present-set` = effective findings where `recommendation` is `Skip` or `Defer`, OR (`recommendation` is `Fix` AND `classification` is `judgment`). If non-empty, present ONE consolidated `AskUserQuestion`: lead with each finding's POV; offer **Apply as suggested** / **Apply with my guidance** (free text) / **Skip** in this neutral order. For a genuine requirements question, the owner's answer becomes the requirement. Apply the chosen revisions to `$SPEC_PATH`. Add every `Skip` identity to the `skip-set`.
   **Record decisions (learning loop):** append one `decisions.py` record per resolution to the resolved decisions store (`$DECISIONS`) (**Apply as suggested** → `fix`; **Apply with my guidance** → `guidance`; **Skip** → `skip`), per `## Learning Loop & Staleness Nudge`. Also append a `fix` record for each finding auto-revised in step 6. This append is non-blocking and never gates the loop.
8. **Refresh + exit check.** Re-copy the revised spec: `cp "$SPEC_PATH" "$SESSION_DIR/spec.md"`. If any edits were made this round AND one or more Critical/Important findings remain that are not in the `skip-set` AND `round < 7`, set `round += 1` and repeat from step 1. Otherwise **EXIT** the loop — but if it is exiting because it hit the **7-round cap** with Critical/Important findings still unresolved, `log` that the cap was reached and report those remaining findings explicitly; do **not** declare SPEC READY in that case.

### 6. Report (advisory — never grants the gate)

review-spec **never writes `passed`** — the spec reaches `passed` only when the **owner**
approves it (Discovery step 8). It does not approve the spec. (It may **revoke** a now-stale
approval — see below — but it can never grant one; that is the advisory invariant.)

**Stale-approval guard.** review-spec normally runs *before* approval (Discovery step 7,
gate `pending`). But if it is **re-run on an already-approved spec** (`gates.review: passed`)
**and makes any revision**, the revision invalidates the owner's approval — the owner
approved the *old* content, and plan's HARD-GATE reads `gates.review` **programmatically**
(it can't see a chat warning). So **reset the gate to `pending`** — marking "needs
(re-)approval". Resetting is advisory-consistent: review-spec *revokes* a stale approval, it
never *grants* one. Do this **only when this run actually revised an already-`passed`
spec** (no revision → the approval still holds; leave it):

```bash
ROOT=$(git rev-parse --show-toplevel)
CANON="$ROOT/docs/superheroes/$WORK_ITEM/spec.md"
LIB=$(python3 "${CLAUDE_PLUGIN_ROOT}/lib/architect_lib.py" --root "$ROOT") || LIB=""
if [ -n "$LIB" ] && [ "$SPEC_PATH" -ef "$CANON" ]; then
  CURRENT=$(python3 "$LIB" read-gate --doc spec --work-item "$WORK_ITEM" --root "$ROOT" 2>/dev/null || echo unknown)
  if [ "$CURRENT" = passed ]; then
    python3 "$LIB" set-gate --doc spec --work-item "$WORK_ITEM" --review pending --root "$ROOT" \
      && echo "spec was already approved and has now been revised — gate reset to 'pending'; the owner must re-approve before it advances." >&2
  fi
else
  echo "⚠ if the spec was already approved, its gate could not be reset (the-architect lib unresolvable, or the doc is outside the canonical layout) — warn the owner: the 'passed' gate may be STALE; the spec needs re-approval." >&2
fi
```

`set-gate --review pending` derives `status: draft` (§3.1), so a programmatic consumer sees
the spec is no longer approved. (The fuller "any content change invalidates approval"
contract is the §7 owner-approval-contract's; this closes the in-repo programmatic hole.)

After the loop exits, print a terminal summary in chat:

- Lead with the final verdict label in bold (`SPEC READY` = ready for the owner to review,
  **not** approved). If the loop hit the 7-round cap with Critical/Important unresolved, the
  verdict is **REVISE** — do **not** declare SPEC READY.
- List, grouped by spec section, the revisions applied (auto + owner-answered) and the
  findings skipped — each with its POV line. Surface any **open requirements question** the
  owner still needs to answer (a `judgment` finding not yet resolved).
- End with a count summary (e.g. `"3 auto-revised, 1 answered by owner, 1 skipped; SPEC
  READY for owner review"`) and a one-line reminder that **the owner's approval is the gate**
  (Discovery records it).

**Then, after the terminal summary**, run the three non-blocking end-of-run steps from `## Learning Loop & Staleness Nudge`, in order: (1) the **staleness nudge**, (2) the **learning-loop proposal**, then (3) the **provisional-profile confirmation**. All three are placed after the review output and none blocks.

Nothing else is written to the repo — the revised `$SPEC_PATH` is the deliverable (plus the project-level `.claude/review-decisions.json` learning-loop store and, only on a dismissal, the profile's `nudge-ack` map). **The only gate write review-spec can make is the stale-approval reset to `pending` above — it never writes `passed`.**

## Learning Loop & Staleness Nudge

These four behaviors are **non-blocking**, run **at end of run** (after the terminal summary), and are **identical across `review-code`, `review-plan`, `review-spec`, `review-tasks`, and `audit-debt`**. Nothing here ever auto-applies a profile or `CLAUDE.md` edit — every change is user-gated.

### Recording decisions (at resolution time)

Wherever the user resolves a finding (this skill: the §5 step 7 interventions, plus the auto-revised findings in step 6), append ONE record per decision to the **project-level** learning-loop store at the resolved `$DECISIONS` path (NOT the temp `$SESSION_DIR`). Use the bundled helper:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/decisions.py" \
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
python3 "${CLAUDE_PLUGIN_ROOT}/lib/decisions.py" \
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

- **Confirm (mark stable)** — flip the profile's provenance `status: provisional` → `status: stable` in the resolved profile (`$PROFILE`) (bump `updated:`). Nothing else changes.
- **Refresh via review-init** — point the user at `/review-crew:review-init` and do not change the profile now.
- **Keep provisional** — record a dismissal using the constant provisional-confirm signal hash so this does not re-ask until the profile changes.

Skip this entirely when the run is **headless/non-interactive**, when `status:` is already `stable`, or when the provisional-confirm signal is already acknowledged.

### Recording a dismissal (shared)

The staleness nudge, the learning-loop proposal, and the provisional-profile confirmation share one dismissal mechanism: **write the relevant `signal_hash` into the profile's `nudge-ack` map** in the resolved profile (`$PROFILE`)'s provenance block, so the same signal does not re-fire until it changes. The map is `nudge-ack: {<hash>: true, ...}` on the provenance line; add the hash as a new key (the staleness nudge uses `DOCTOR_JSON.signal_hash`; the proposal uses `proposal.signal_hash`; the provisional-profile confirmation's **Keep provisional** uses the constant literal `provisional-confirm`). This is the ONLY write any of these nudges makes to the profile, and only on dismissal.

## Spec-Content Requirements (Opinionated)

Agents flag departures from these — the spec contract (CONVENTIONS §3.2):

- **EARS functional requirements** — `When`/`While`/`Where`/`If-Then` + "the system shall …", one behavior each, no "and/or" chaining.
- **An acceptance criterion on every functional requirement** — Given-When-Then for a flow, a pass/fail rule for a constraint. A requirement with none is too vague to keep.
- **Significant unhappy paths covered** — the coverage checklist (empty/first-run, invalid input, boundaries, errors, access, duplicates, concurrency, abuse, reach), each Specify / Defer-to-plan / N-A.
- **No vague/unmeasurable words** — replaced by a concrete behavior or fit-criterion.
- **No technical *how*** — no libraries/schemas/APIs/frameworks; that is the `plan`.
- **NFRs as outcomes with a fit-criterion**, UI/UX referencing the Claude Design handoff, plus definition of done / assumptions / constraints / out-of-scope.

## Out of Scope at Spec Time

- **Proposing or grading a technical approach** — that is the `plan`. Only flag tech that leaked into the spec.
- **Wording/style preferences** that don't affect clarity or verifiability.
- **Inventing a requirement the owner never stated** — surface it as a question; never answer it for them.

## Common Mistakes

| Mistake                                                                     | Fix                                                                                                                                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Marking the spec approved / writing `passed`                                | review-spec is **advisory** — it **never writes `passed`** (the owner approves in Discovery step 8). Its only gate write is resetting a *stale* approval to `pending` (step 6). Never grant approval.                |
| Proposing a technical approach in a finding                                 | The spec is the *what*. Flag tech that leaked in; don't add more. The *how* is the `plan`.                                                                       |
| Inventing an answer to a requirements question                              | A genuine "what should happen here?" is a `judgment` finding for the owner — surface it; never fabricate the behavior.                                           |
| Adding implementation detail while "fixing" a vague requirement             | Keep the owner's plain-language voice. Replace vagueness with a concrete behavior/fit-criterion, not a mechanism.                                                |
| Flagging a missing unhappy path already tagged Defer-to-plan / N-A          | Check the coverage tags before raising it — a recorded Defer/N-A is a decision, not a gap.                                                                       |
| Citing line numbers from the wrong file                                     | Spec citations point at `$SESSION_DIR/spec.md`. There is no parent doc to cross-cite for a spec.                                                                 |
| Re-raising findings the user skipped                                        | Check the `skip-set` and prior rounds before raising a finding.                                                                                                 |
| Skipping the all-five-specialists rule based on classification              | The `touches` array is informational. All five always run — each returns `[]` when there's nothing in its dimension.                                            |
| Dispatching reviewers by reading an agent file                              | The five reviewers are bundled plugin agents — dispatch each by its `subagent_type` (its name). The methodology is the agent's own system prompt.               |
| Skipping the profile bootstrap                                              | If no profile resolves, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                                        |
