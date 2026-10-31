<!-- review-loop-version: 3 -->
## Learning Loop & Staleness Nudge

These four behaviors are **non-blocking**, run **at end of run** (after the terminal summary), in `review-code`. Nothing here ever auto-applies a profile or `CLAUDE.md` edit — every change is user-gated.

### Recording decisions (at resolution time)

Wherever the user resolves a finding (this skill: the §5 step 7 interventions, plus the auto-revised findings in step 6), append ONE record per decision to the **project-level** learning-loop store at the resolved `$DECISIONS` path (NOT the temp `$SESSION_DIR`). Use the bundled helper:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/decisions.py" \
  append "$DECISIONS" '<record-json>'
```

`<record-json>` is `{"dimension": "<finding dimension>", "category": "<finding taxonomy/topic>", "action": "skip"|"guidance"|"fix"}`:
- `action` maps from the user's choice: **Skip** → `skip`; **Apply with my guidance** → `guidance`; **Apply as suggested** (and step-6 auto-revises) → `fix`.
- `dimension` is the finding's `dimension`; `category` is the finding's taxonomy/topic (its normalized title or topic tag). The store is append-only and atomic; it soft-fails on a bad/missing store, so this never blocks.

### Staleness nudge (end of run)

Using the `DOCTOR_JSON` captured in Setup: print the doctor's `message` as a single non-blocking line **only when** `message` is non-null AND `nudge_acked` is false:

> ℹ️ Profile may be stale: `<message>`. Run `/superheroes:configure` to refresh (this nudge won't repeat once acknowledged).

If the user declines or ignores it, record the dismissal (see "Recording a dismissal" below) using the doctor's `signal_hash`. Suppress the line entirely when `nudge_acked` is true or `message` is null.

### Learning-loop proposal (end of run)

**Not run.** The learning loop learns from decisions a human made; a gate nobody answered produced
none, and applying a calibration edit unasked would be the worse failure. Proposals are not
surfaced this run — recorded decisions remain in `$DECISIONS` for a future run when an owner
reviews them. Keep the analyze snippet below for reference only; do not invoke it at end of run
here:

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/decisions.py" \
  analyze "$DECISIONS" --nudge-ack <comma-separated profile nudge-ack hashes>
```

### Provisional-profile confirmation (end of run)

**Not run** — same reason as the learning-loop proposal above; confirming a provisional profile
unasked would apply a calibration edit nobody authorized. Recorded decisions and the provisional
profile remain for a future owner review.

### Recording a dismissal (shared)

The staleness nudge, the learning-loop proposal, and the provisional-profile confirmation share one dismissal mechanism: **write the relevant `signal_hash` into the profile's `nudge-ack` map** in the resolved profile (`$PROFILE`)'s provenance block, so the same signal does not re-fire until it changes. The map is `nudge-ack: {<hash>: true, ...}` on the provenance line; add the hash as a new key (the staleness nudge uses `DOCTOR_JSON.signal_hash`; the proposal uses `proposal.signal_hash`; the provisional-profile confirmation's **Keep provisional** uses the constant literal `provisional-confirm`). This is the ONLY write any of these nudges makes to the profile, and only on dismissal.

## Convergent Shared Review Loop

Spec review does not run this loop — it follows `skills/architect-discovery/reference/spec-checks.md`.

Round 1 is always a full `reviewer-deep` panel. Intermediate rounds may skip only dimensions with a high-confidence clean result whose subject area was not touched; unknown subject impact runs all dimensions. Intermediate run dimensions start at `reviewer` and escalate to `reviewer-deep` whenever the result is missing or unparseable (transport failure).

Recurring blocking classes are detected from durable round memory and passed only to the reviser/fix step as `generalizeRequired`. Reviewers never receive prior-round finding lists. Any dismissal or class-covering principle is recorded as a visible coverage decision and is passed to every later reviewer as a challengeable claim.

After a fix, the loop certifies once every logged finding is fixed and verified (or explicitly deferred with a reason). A code review that needed fixes does not finish on a full `reviewer-deep` panel: only round 1 runs one. Every round after it runs only the fix auditor over each fix and the scoped finder over the code the fixes touched, and the review ends on a round's audit and scoped finder; the record names the terminal shape `audited-chain`. `full-panel-confirmed` is for a review whose round-1 panel found nothing to fix. A new finding the scoped finder raises is fixed and audited in the next round, and the loop certifies once that round comes back clean — it does not re-review until a fresh panel comes back pristine. A fix whose reach cannot be worked out hands the PR back with its findings still open (certification withheld). A blocking `clean-with-skips`, malformed receipt, stale writer, corrupt memory, or failed coverage-decision write still does not pass. The certification record states what was established — that one full panel ran and whether the findings it raised were resolved by audited fixes — never implying a pristine fresh pass.

**Document reviews diverge on the re-arm rule and the confirmation budget (#397, #518).** A
doc-panel round is a full-document, full-panel spend with no cheap scoped tier, so **any open
blocking finding** (Critical **or** Important) re-arms the one further confirmation, not only a
Critical or cross-cutting rework — no scoped-round tier for new Importants, no scoped-verify
certify at the confirmation cap. **Two caps, not one (#518):** the overall round cap is **7**
(`--max-rounds 7`, enforced by `loop_state.decide` / `circuit_breaker`); **at that cap an open blocking finding always
parks** (verdict REVISE, certification withheld) — documents lack a stronger downstream reviewer, so the gate never
scoped-certifies a blocker (code review may); a clean full-deep confirmation at the cap still certifies. The
**confirmation-panel budget is separate**: at most **two** full panels per loop (`MAX_CONFIRMATIONS = 2` in
`review_round_policy`); doc-mode confirmations at that budget park rather than scoped-certifying. The
any-open-blocker trigger stacks on the cross-cutting/unknown-surface trigger — below the confirmation-panel cap unknown
surface still fails closed on the doc leg; at the cap with nothing blocking open, the doc leg certifies as code review
does. The earlier three-round phrasing conflated these caps and is retired. Everything else in
this section — the full baseline panel, the convergence record, fail-closed on malformed/stale
receipts — is identical. The re-arm/park **rule** lives once in
`review_round_policy.confirmation_followup(doc_mode=True)` and its bundled JS twin; the two cap
numbers live once each — the `7` in the deciders' `--max-rounds` default (the skills' operative
`--max-rounds 7` arg), the `2` in `MAX_CONFIRMATIONS`. Do not restate either elsewhere.

**Post-halt document edits are a named violation (#518).** That cap park is a whistle: **after the
halt, any write to the reviewed document invalidates the loop's terminal claim** — the verdict
covered the pre-halt content, so an edit after the whistle is an unreviewed change wearing a
reviewed document's clothes. The receipt says so: a post-halt edit voids the READY/REVISE claim
and the document is unreviewed until the loop re-runs.

Telemetry records rounds, run/skip/tier counts, per-leaf token usage completeness, and benchmark validity. Telemetry failure does not change the review terminal, but incomplete benchmark telemetry cannot satisfy the cost comparison.
