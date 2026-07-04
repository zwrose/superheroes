<!-- review-loop-version: 1 -->
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

> ℹ️ Profile may be stale: `<message>`. Run `/superheroes:configure` to refresh (this nudge won't repeat once acknowledged).

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

- **Confirm (mark stable)** — flip the profile's provenance `status: provisional` → `status: stable` in the resolved profile (`$PROFILE`) (bump `updated:`). Nothing else changes.
- **Refresh via configure** — point the user at `/superheroes:configure` and do not change the profile now.
- **Keep provisional** — record a dismissal using the constant provisional-confirm signal hash so this does not re-ask until the profile changes.

Skip this entirely when the run is **headless/non-interactive**, when `status:` is already `stable`, or when the provisional-confirm signal is already acknowledged.

### Recording a dismissal (shared)

The staleness nudge, the learning-loop proposal, and the provisional-profile confirmation share one dismissal mechanism: **write the relevant `signal_hash` into the profile's `nudge-ack` map** in the resolved profile (`$PROFILE`)'s provenance block, so the same signal does not re-fire until it changes. The map is `nudge-ack: {<hash>: true, ...}` on the provenance line; add the hash as a new key (the staleness nudge uses `DOCTOR_JSON.signal_hash`; the proposal uses `proposal.signal_hash`; the provisional-profile confirmation's **Keep provisional** uses the constant literal `provisional-confirm`). This is the ONLY write any of these nudges makes to the profile, and only on dismissal.

## Convergent Shared Review Loop

Round 1 is always a full `reviewer-deep` panel. Intermediate rounds may skip only dimensions with a high-confidence clean result whose subject area was not touched; unknown subject impact runs all dimensions. Intermediate run dimensions start at `reviewer` and escalate to `reviewer-deep` whenever the result is missing or low-confidence.

Recurring blocking classes are detected from durable round memory and passed only to the reviser/fix step as `generalizeRequired`. Reviewers never receive prior-round finding lists. Any dismissal or class-covering principle is recorded as a visible coverage decision and is passed to every later reviewer as a challengeable claim.

Certification after any fix requires that **one** full `reviewer-deep` confirmation round has run (all dimensions fresh, high-confidence, with valid verification receipts) and that every logged finding is fixed and verified (or explicitly deferred with a reason). A confirmation panel that surfaces new findings does **not** by itself forfeit certification: the surfaced findings are fixed and scope-verified (their dimension re-runs the next scoped round, since it carries a finding), then the loop certifies — it does not re-review until a fresh panel comes back pristine (#174). Only a **Critical** surfaced by a confirmation, or cross-cutting rework (the fix touched ≥3 of the 5 policy subjects), re-arms one additional full confirmation; new Importants are resolved by a scoped round only. At most **two** full confirmation panels run per loop; at the cap a non-Critical is resolved by scoped verify and the readout says so, while a Critical still parks (certification withheld). A blocking `clean-with-skips`, malformed receipt, stale writer, corrupt memory, or failed coverage-decision write still does not pass. The certification record states what was established — how many full panels ran and whether the last panel's findings were resolved with scoped verification — never implying a pristine fresh pass.

Telemetry records rounds, run/skip/tier counts, per-leaf token usage completeness, and benchmark validity. Telemetry failure does not change the review terminal, but incomplete benchmark telemetry cannot satisfy the cost comparison.
