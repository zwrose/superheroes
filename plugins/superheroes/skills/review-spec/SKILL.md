---
name: review-spec
description: Use to review the-architect's `spec` definition-doc (the plain-language requirements / the *what* for a work-item) before the owner gives final approval. Red-teams and revises the spec in place; it never records `passed` (the owner is the spec's gate authority in Discovery) — improves the doc and reports a readiness verdict.
user-invocable: true
---

This skill speaks in host-neutral actions. Resolve them to your runtime's tools by reading the host tool map at `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/hosts/<your-host>-tools.md` (the leading variable is this plugin's root directory) — `claude-tools.md` on Claude Code, `codex-tools.md` on Codex.

# Review Spec

Red-team the-architect's **`spec` definition-doc** — the plain-language requirements (the
*what*) for a work-item (`docs/superheroes/<work-item>/spec.md`) — **before the owner gives
final approval**. Discovery runs this (step 7) so the automated review catches ambiguity,
missing coverage, and tech leakage **before** the owner spends their time. The main context
is an orchestrator: it locates the spec, dispatches the same five specialist agents
`/superheroes:review-code` uses (architecture, code, security, test, premortem) — **reframed
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
grants `passed`). Read the base rubric (`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/rubric/review-base.md`)
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
| `/superheroes:review-spec`        | Review the most recent `docs/superheroes/*/spec.md`.                         |
| `/superheroes:review-spec <work-item>` | Review `docs/superheroes/<work-item>/spec.md`.                          |
| `/superheroes:review-spec <path>` | Review the spec doc at `<path>` (relative to repo root or absolute).         |

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

**Staleness self-check (first action).** Before the profile bootstrap and before locating the spec or dispatching anything, run the deterministic staleness/degraded self-check. It soft-fails (always exit 0) and **must never block the review** on drift — it only produces a non-blocking nudge surfaced at end of run. review-spec reads the working tree (default root), so no `--root` is passed. Run it only when a profile already resolved (`$EXISTS` is `true`) — a MISSING profile (`$LOCATION` is `none`) routes to the profile bootstrap below, not to staleness:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
if [ "$EXISTS" = "true" ]; then
  DOCTOR_JSON=$(python3 "$ROOT_DIR/lib/repo_doctor.py" \
    "$PROFILE" "$PLUGIN_VERSION" "$RUBRIC_VERSION")
fi
```

Capture the JSON in `DOCTOR_JSON`. On `readable: false`, tell the user "profile unreadable — re-run `/superheroes:configure`" and **continue** (do not crash, do not block). Otherwise retain `message`, `signal_hash`, and `nudge_acked` for the **end-of-run staleness nudge** (see §6). Do NOT act on `drift` here — it is informational only.

**Profile bootstrap (run before locating the spec or dispatching anything).** The review engine reads its per-project calibration from the resolved profile. If nothing resolved (`$LOCATION` is `none`), decide where to store it, create it, then write it:

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

ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
RUN_ID="review-${WORK_ITEM}-${SESSION_DIR##*/}"
REVIEWED_HASH=$(python3 "$ROOT_DIR/lib/definition_doc.py" content-hash --path "$SESSION_DIR/spec.md")
LEASE="${SESSION_DIR##*/}"

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
2. **Dedupe by spec section + topic.** When two findings target the same requirement and same topic (e.g. both flagging "no acceptance criterion"), merge them: concatenate bodies with a separator, keep the higher severity, list both dimensions (e.g. `"Test + Code"`).
3. **Nit cap.** If more than 5 Nits remain after dedupe, keep the first 5 and summarize the rest as a count.

Determine the verdict per the base rubric's "Verdict labels & mapping". For `/superheroes:review-spec` the labels are **SPEC READY** / **REVISE BEFORE OWNER REVIEW** / **MAJOR GAPS — RETURN TO DISCOVERY**:

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
7. **Interventions — escalate only owner-weighable blockers (per `escalation-base.md`).** For each
   **Critical/Important** effective finding, route its disposition with the shared rubric (modes
   PROCEED/NOTIFY/GATE). **GATE** (one consolidated `AskUserQuestion`) only the blockers whose
   skip-or-fix is genuinely the owner's call — a product/scope/risk trade-off. For the rest,
   **verify and proceed**, recording the disposition so `loop_state` still sees it:
   - **Fix, one right answer per the project's conventions** → auto-revise `$SPEC_PATH` (a step-6
     auto-revise).
   - **Verifiably-safe skip / believed false-positive** → record a **skip** (add the identity to the
     `skip-set`) **with a verification trace** (cite the spec line / source you checked). A skip with
     no citable ground truth is **not** eligible — it GATEs. **Never silently drop a blocker.**
   - Minor/Nit → apply the triage recommendation automatically (auto-revise or skip-set), reported
     in the terminal summary, never asked (the F4 win, preserved).
   Add every skipped identity (owner-skip or autonomous-skip) to the `skip-set`; it feeds
   `SKIPPED_BLOCKING` (step 8) so the gate reflects it. Record GATE outcomes and NOTIFY decisions in
   the terminal summary with their reverse-path/expiry, per `escalation-base.md`. **Advisory note:**
   review-spec is advisory (the spec is **owner-gated** — the owner approves it at Discovery's
   final-approval gate regardless), so more of its blocking findings route to **present-to-owner**
   than in the plan/tasks legs; that is correct by construction, not a regression — for a genuine
   requirements question the owner's answer becomes the requirement (never an invented answer).

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
8. **Refresh + continuation gate.** Re-copy the revised spec: `cp "$SPEC_PATH" "$SESSION_DIR/spec.md"`. Whether to re-review is **decided by a script, not by you** — a model rationalizes early exits ("the revision obviously resolved it", "it'll be clean next round"). Compute `SKIPPED_BLOCKING` = the count of Critical/Important findings in this round's `compiled.findings` whose identity is in the `skip-set` — the *present* skipped blockers (equivalently: blocking findings minus blocking **effective** findings from step 3). Count this **cumulatively every round**, not just the ones you added this round — the specialists re-flag a skipped finding each round, so a once-skipped blocker stays present and must keep being counted as skipped, else it reads as "present and addressed" forever and the loop can never reach `exit_skipped`. The gate **derives the number of blockers addressed from this round's `compiled.json`** (blockers present minus the present-and-skipped), so the addressed count is **not yours to self-report**. Run it and obey its `action`:

   ```bash
   ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
   python3 "$ROOT_DIR/lib/loop_state.py" --round <N> --max-rounds 7 \
     --compiled "$SESSION_DIR/compiled.json" --skipped-blocking <SKIPPED_BLOCKING>
   ```

   - **`review`** → `round += 1` and repeat from step 1. **MANDATORY** — you revised a blocking finding; re-review to verify it actually resolved and introduced nothing new. Do **not** exit because the revision "looks resolved."
   - **`exit_clean`** → **EXIT** the loop (then report, §6 — review-spec records no `passed`).
   - **`exit_skipped`** → **EXIT**, listing the deliberately-skipped blocking finding(s) — not a plain SPEC READY.
   - **`halt`** → the 7-round cap was hit with blocking findings still being revised: report them; do **not** declare SPEC READY.

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

Set `REVISED=yes` **iff** the step-5 loop actually applied at least one revision to the spec
this run (otherwise `REVISED=no`) — a clean, zero-edit re-run on an approved spec must
**not** revoke a still-valid approval:

The reset itself — resolve the-architect's lib cross-plugin, the canonical-path guard, the
"only revoke an actually-`passed` gate" check, and the guarded `set-gate pending` — lives in
the **same tested helper** the certifying legs use, `lib/gate_write.py` (mode `reset`). The
skill only gates it on `REVISED` (a loop concern the helper can't know); the helper does the
rest and **never grants `passed`** (it can only reset `passed`→`pending` or no-op):

```bash
if [ "$REVISED" = yes ]; then
  ROOT=$(git rev-parse --show-toplevel)
  GATE=$(python3 "$ROOT_DIR/lib/gate_write.py" --mode reset --doc spec \
    --work-item "$WORK_ITEM" --reviewed-path "$SPEC_PATH" --root "$ROOT" \
    --expected-hash "$REVIEWED_HASH" --run-id "$RUN_ID" --lease "$LEASE")
fi
```

`$GATE` is `reset:pending`, `noop:not-approved`, `skipped:*`, or `failed:set-gate` — surface stderr on failure; the helper never grants `passed`.

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

For recurrence handling, coverage decisions, dimension skipping, tier cascade, final confirmation, and telemetry, use `plugins/superheroes/reference/review-loop.md` as the shared loop contract. This skill owns only its leg-specific setup, reviewer framing, and gate-write rules.

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

The common-mistake table for review-spec is in `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}/skills/review-spec/reference/spec-detail.md` — read it before finalizing findings.
