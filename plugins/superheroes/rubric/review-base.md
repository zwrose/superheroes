<!-- rubric-version: 7 -->
# review-base

The source of truth for review **severity, verification rules, findings format,
triage, and verdicts** — shared by every review-crew skill and agent. It is
stack-neutral and universal. All **project calibration** (threat model, scope
exclusions, the verify command, focus hints, canonical patterns) lives in the
project profile at `.claude/review-profile.md`; **conventions** live in the
project's `CLAUDE.md`. If a review finding contradicts this file, this file wins.

`rubric-version` (top of file) is the staleness signal for "the rubric changed";
bump it on a semantic change to **this file's own stated scope** — severity,
verification rules, findings format, triage, or verdicts. **Additively extending
the Dimensions data list with a new lens label is NOT a version-bumping change** — it
adds a data entry, not a rule, and no *project calibration* changed.

## Calibration comes from the profile (not baked in here)

This rubric is deliberately neutral about audience, threat model, and what is
in/out of scope — those vary per project and are read from
`.claude/review-profile.md` + `CLAUDE.md`. Reviewer strictness (how aggressively
to flag) is profile-tunable. **When the profile or a needed field is absent,
default to the STRICT posture** (assume a multi-user threat model and err toward
flagging) — it is safer to over-flag than to miss a real access-control bug.
Minor and Nit findings never change the verdict regardless of strictness.

## Severity tiers

| Tier             | Definition (stack-neutral)                                                                                   | Example (illustrative, not stack-specific)                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- |
| **Critical**     | Corrupts data, leaks data across a trust boundary, or breaks production. NEVER for tests or style.           | A request handler returns records belonging to another principal            |
| **Important**    | Likely bug in normal use, OR a security/correctness issue warranting a fix before merge                      | A value that can be absent is dereferenced on a reachable path              |
| **Minor**        | Real issue, small impact                                                                                     | A magic number; an inconsistent error message                              |
| **Nit**          | Style/naming/cleanup; take-it-or-leave-it                                                                     | "This name could be clearer"                                                |
| **Pre-existing** | Issue only in lines the diff did not change (unchanged files, or context lines) — SKIPPED, not reported      | A pattern in code the change didn't touch                                   |

## Verification rules (binding — violations are dropped at compile time)

1. **`file:line` citation required.** No citation → drop.
2. **Diff-scope rule** (diff modes only): flag only code on `+`/`-` lines. Context
   lines and unchanged code are pre-existing → SKIP. (Audit/sweep mode reviews the
   whole repo; this rule does not apply there.)
3. **Grep-before-flag.** Before flagging "missing X", search the codebase for X
   under variant names. A thing that exists under another name is not missing.
4. **Reachability check on Important findings.** Read the caller(s); if the only
   caller already guards the case, downgrade or drop. (Critical findings are also
   checked for reachability, but under the strict posture, flag when in doubt.)
5. **Docs/spec changes:** spot-check factual claims (signatures, paths, error
   types) against source, not just prose. **Mirror-claim verification.** A **mirror
   claim** — a finding asserting the spec contradicts, misstates, or fabricates a repo
   fact — may be emitted **High** confidence only if the reviewer has **read the cited
   source** (or, when the spec left it uncited, the repo location it mirrors). Without
   that read, emit it **Low** (naming the unread source in `evidence`) or drop it. The
   deterministic `citation_validator.py` covers only *existence* (does the cited
   path/anchor resolve); whether the source *says* what the spec claims — content-match
   — is this verifier judgment. **Carve-out:** A `[cite: …]` provenance marker is a
   sanctioned spec construct (CONVENTIONS §3.2), not leaked implementation detail and
   not a leftover placeholder — never strip or flag it as tech-leak, a path reference,
   or `{{…}}`/TBD noise.
6. **Single source of truth for cross-boundary facts.** A fact consumed across a
   module or language boundary (phase lists, event/verb names, schema field sets,
   verdict/reason tokens, path layouts, reviewer rosters) must have one
   authoritative home; every other copy reads it at runtime or is guarded by a
   drift test that reads the home and asserts equality. **Two hand-maintained
   copies with no drift test is review-blocking** — and a contract test that
   restates the constant instead of reading the home proves nothing. (In this repo
   the rule is formalized as **CONVENTIONS §11**, with the phase-list drift test as
   its worked example; cite it by number.)

## Findings output format (the single schema — agents reference this, never restate it)

Every agent emits a JSON array at the path the dispatching skill specifies. This
is the one authoritative schema; agents must not redefine the fields inline.

```json
[
  {
    "id": "<agent-name>-001",
    "severity": "Critical | Important | Minor | Nit",
    "dimension": "<one of the dimensions below>",
    "taxonomy": "<the dimension's named taxonomy term, where one applies; optional>",
    "title": "<short descriptive title>",
    "file": "<path relative to repo root>",
    "line": "<number or null>",
    "body": "<explanation with code references>",
    "suggestion": "<what to do, or null>",
    "evidence": "<for Important/Critical: trigger + impact / the reachable path; omit or null for Minor/Nit>",
    "confidence": "High | Low",
    "tradeoff": "<true only if multiple valid fix approaches exist; omit otherwise>"
  }
]
```

- `confidence` is the agent's own confidence after running the in-pass Chain-of-Verification (below). **High** = the chain passed cleanly. **Low** = emitted but genuinely unsure — it flags the finding for scrutiny rather than dropping a possibly-real issue. Required on Critical/Important (a **Low** Critical/Important MUST name exactly what is uncertain in its `evidence` line); may be omitted on Minor/Nit (treated as High). Low confidence does not, on its own, change the verdict beyond what the finding's severity already implies.
- `taxonomy` carries the dimension's named taxonomy term where one applies (e.g. OWASP class for Security, defect class for Code, test smell for Test, failure class for Failure-Mode). Optional for most agents; **required** by the Failure-Mode reviewer. Omit when no named term applies to the finding.
- `severity` is a **closed enum** — exactly one of `Critical`, `Important`, `Minor`, `Nit`. Do **not** emit any other scale: no `high`/`medium`/`low`, no `blocker`/`major`/`info`, no lowercase variants. A blocker is `Critical` or `Important`. Consumers fail **closed** — any unrecognized severity is treated as **blocking**, so an off-scale label mis-routes your finding rather than silently downgrading it.

**Dimensions** (the orchestrator reads this list; it is data, not hard-wired —
adding one later is a single-place change): `Architecture`, `Code`, `Security`,
`Test`, `Failure-Mode`, `Clarity`, `Verifiability`, `Coherence`, `Safety-access`,
`Grounding`. The crew carries **two label sets drawn from the same reviewer
agents**: a **code-leg** set (`Architecture`, `Code`, `Security`, `Test`,
`Failure-Mode`) that `/superheroes:review-code` and `/superheroes:audit-debt`
dispatch, and a **doc-native spec-leg** set (`Clarity`, `Verifiability`,
`Coherence`, `Safety-access`, `Failure-Mode`, `Grounding`) that
`/superheroes:review-spec` dispatches — the five shared reviewers reframed to
requirements quality, plus `Grounding`, a spec-only seat with no review-code agent.
Each dispatching skill names the subset it runs and assigns each agent its dimension
and its `id` prefix; a leg runs one agent per dimension (e.g. the Security reviewer
emits `security-001`, …; the Failure-Mode reviewer emits `premortem-001`, …).

Separately from those five risk-domain dimensions, the review crew has one **narrow
sixth seat — the grounding seat** (`agents/grounding-seat.md`), which is **NOT** one of
the five code-leg risk lenses above and must not be counted as one: it adds no risk
lens, it checks the PR's self-claims against the repo. It runs at the `reviewer` model
tier and **never** `mechanical` — a false "the claims check out" is a silence nothing
downstream re-checks, so it must not go to the tier whose failure mode is confident wrong
fills. On the **spec leg** this seat is already live — it is the `Grounding` label in the
Dimensions enumeration line above, dispatched by `/superheroes:review-spec` (as of
#515/#517). Its **code-leg (review-code) live dispatch is owned by #510** (panel
composition v2); until then the review-code orchestrator performs the same self-claims /
PR-body-honesty check inline (the interim mechanism). As a code-leg lens it is not yet
part of review-code's dispatched dimensions, and no code-leg drift test should read it as
one.

## Severity caps

- **Nits:** at most 5 reported per review; summarize the rest as a count.
- **Critical / Important:** uncapped (load-bearing).
- **Minor:** uncapped, but each must pass the verification rules; if reporting
  >10, dedupe — they're usually facets of one issue.

## High-signal bar (global Do NOT Flag)

This is the consolidated, citable **global "Do NOT Flag" bar** the agent briefs
reference — the one place that names the low-signal classes every dimension drops, so
downstream verification (synthesis, orchestrator POV) is cheaper because these never
enter the finding stream. It does **not** restate thresholds (per CONVENTIONS §11
single-source spirit); it **points at** the rule that already owns each class. Drop a
candidate finding that is only:

- **Pre-existing** — an issue in lines the diff did not change. Governed by the
  **Diff-scope rule** (verification rule #2, above) and the **Pre-existing** severity
  tier (in the Severity-tiers table, above): these are SKIPPED, not reported. (Audit/sweep
  mode is the sole exception, per that rule.)
- **Linter / tooling territory** — anything an automated formatter, linter, or
  type-checker already surfaces. Governed by **CoV step 4** ("Not tooling-caught", below);
  human-judgment style/naming/cleanup a tool does *not* catch remains reportable as a Nit.
- **Pedantic nit** — take-it-or-leave-it style/naming the author has no real decision to
  make on. Governed by the **Nit** severity tier (table, above) and the **Nit caps**
  (Severity caps, above: ≤5 reported, rest summarized as a count). When in doubt whether a
  style point clears the bar, it does not — summarize it in the count, don't flag it.

An agent brief may cite this section as "the base rubric's global 'Do NOT Flag' /
high-signal bar"; it is the shared home those citations resolve to.

## Document-review severity (applies only when `docType` is `plan` or `tasks`)

This section **overrides the severity tiers above for document reviews only**. It does not
apply to code review (`docType` absent). A document is not code: judge every finding against
the reviewed document's **own job**, not against code-review severity.

**Blocking bar (FR-1).** A finding is **blocking** only if *following the document as written
would mislead the build or cause it to build something unsafe or incorrect*, judged against
the document's own job. Everything else is **non-blocking** and routes forward — it never
blocks the gate and never re-arms the loop.

**Plan vs tasks asymmetry.**
- In a **plan** review, task- and test-*specification granularity* is **non-blocking**:
  "no named unit test for this option", "this value appears as two separate literals", "this
  test doesn't pin a controlled clock" — specifying tasks and tests is the *tasks* document's
  job, not the plan's. Route these to the hand-off list.
- In a **tasks** review, a finding that the tasks document *mis-specifies a task or test the
  build will follow* is judged **directly against the bar** — never categorically demoted as
  "specification granularity" — because the tasks document is the build's contract.

**Always blocking (incident-anchored).** A finding of the class that legitimately blocked
round 1 of the 2026-07-12 incident run — an unauthenticated access path, a required security exemption missing, a design that would corrupt or lose data — is **blocking** in either
document.

**Ambiguity fails closed.** A finding you cannot confidently place on either side of the bar
is **blocking**. A wrongly-demoted real blocker is invisible; a wrongly-promoted one costs at
most a readable park the owner can rule on. Example: "the plan's error-handling approach *may
be insufficient*" without naming what would break cannot be confidently placed — so it blocks.

*Few-shot anchors (2026-07-12 incident corpus).* Blocking (its round-1 findings): an
unauthenticated write path; a missing security-exemption the design required; a data-model
that would drop records on a concurrent edit. Non-blocking on a **plan** (its rounds 5–7
findings, which fueled the treadmill): "no named unit test for the fallback branch"; "the
retry constant is written twice as two literals"; "this test description doesn't specify a
frozen clock". On a **tasks** doc those same three ARE judged against the bar.

## Triage rubric (mechanical vs judgment)

For each finding, classify the **fix** (not whether to fix):

- **judgment** when ANY of: `tradeoff: true`; the fix is a UX/design call with more
  than one reasonable option; or it changes established product behavior the user
  may have an opinion on.
- **mechanical** when the fix is determinate (one obviously-correct change).

Bias hard toward **mechanical**. Example (stack-neutral): "replace the hardcoded
not-found string with the project's error constant" = mechanical. "This empty
state needs copy and a layout decision" = judgment.

## Orchestrator POV (on every presented finding)

When a skill presents a finding for a decision, the orchestrator attaches its own
point of view — advisory; the user's decision always wins and the POV never
auto-applies.

- **Recommendation:** `Fix` (correct and worth it here) | `Skip` (good reason not
  to: correct-but-not-worth-it for this project, cost > benefit, or borderline
  false positive) | `Defer` (real but not now/here).
- **Rationale:** one sentence.
- **Confidence:** `High` | `Low` (Low flags where to scrutinize). This is the
  *orchestrator's* advisory confidence, distinct from a finding's own
  `confidence` field (the agent's self-assessment, above).

Form it from a small targeted read of the cited code — not a re-review.

## In-pass Chain-of-Verification & single-pass discipline

Each **finder** (specialist) runs **once** per review. Do NOT re-run a finder or
chain a second finder pass over the same artifact: a finder that has exhausted the
real issues starts fabricating, so a repeat search buys false positives, not
coverage. (Re-reviewing from scratch on the *next* round's fresh diff, after a fix,
is a different thing — that is how the loop converges.)

This is a ban on re-**finding**, not on **verifying**. A distinct judgment stage
run over the *already-emitted* findings — deciding per finding whether it holds
against the artifact and never searching for new ones — is **not** a second finder
pass. It is the documented low-noise production pattern and is band policy: on the
**standalone review-code path**, **per-finding verification** applies 3-state CONFIRMED/PLAUSIBLE/REFUTED
verdicts with quoted evidence — REFUTED drops only with a reason, silence or malformed
verdicts keep the finding as PLAUSIBLE (keep-on-uncertain), and a dropped Critical/Important
is flagged for human scrutiny; a **synthesis** judge then merges same-root-cause survivors
and ranks them, dropping nothing. Verifying findings lowers false positives without hunting
for more, so it does not trigger the finding-exhaustion failure mode above; the earlier
blanket "any multi-turn review degrades F1" ban conflated the two, but only re-finding
is forbidden.

Within its single pass, each finder still runs an ordered **Chain-of-Verification**
on each candidate finding before emitting it, dropping (or downgrading) failures in
order:

1. **Citation in scope** — `file:line` is present; in diff modes it lands on a
   `+`/`-` line (context/unchanged lines are pre-existing → drop).
2. **Reachable / not already guarded** — read the caller; if the only caller
   already guards the case, drop or downgrade.
3. **Claimed-missing actually missing** — grep for the symbol under variant
   names before flagging "missing X".
4. **Not tooling-caught** — drop issues a linter/formatter/type-checker already
   surfaces. (Human-judgment Nit style/naming/cleanup that tooling does not
   catch remains reportable.)
5. **Assign confidence** — if any check above is shaky, drop the finding or emit
   it at **Low** confidence.

Where a dimension defines a named taxonomy (the per-agent files do), label the
finding with its taxonomy term.

## Verdict labels & mapping

- `/superheroes:review-code`: `READY FOR PR` / `FIX BEFORE PR` / `MAJOR FIXES NEEDED`
- `/superheroes:review-spec`: `SPEC READY` / `REVISE BEFORE OWNER REVIEW` / `MAJOR GAPS — RETURN TO DISCOVERY` *(advisory — the owner is the spec's gate authority; review-spec records no `passed`)*
- `/superheroes:audit-debt`: no single verdict — a prioritized backlog

Mapping (post-dedupe, post-filter counts) — the same shape for every skill (the first / second / third label):
- 0 Critical, 0 Important → the **READY** label (`READY FOR PR` / `SPEC READY`)
- 0 Critical, ≥1 Important → the **REVISE** label (`FIX BEFORE PR` / `REVISE BEFORE OWNER REVIEW`)
- ≥1 Critical → the **MAJOR** label
- Only Minor/Nit → the READY label (informational)

`review-spec` is **advisory** — it never records `passed` (the owner approves the spec in Discovery); its only gate write is resetting a *stale* approval to `pending`.

## Where calibration comes from (read these, in order)

1. `CLAUDE.md` — project conventions (the primary, user-maintained source).
2. `.claude/review-profile.md` — the review profile: threat model, scope
   exclusions, verify command, focus hints, canonical patterns. It is an **adder**
   over `CLAUDE.md` (it only carries what `CLAUDE.md` doesn't cover).
3. If a needed field is absent in both → the STRICT fallback (see the
   "Calibration comes from the profile" section above).
