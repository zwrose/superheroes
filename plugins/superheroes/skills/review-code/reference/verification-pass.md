## Contents

Per-finding verification for standalone review-code compile (#506).

- [Where it runs](#where-it-runs)
- [The verifier dispatch](#the-verifier-dispatch)
- [Applying the verdicts](#applying-the-verdicts)
- [Synthesis merge + rank](#synthesis-merge--rank)
- [Evidence-or-silence + the advisory disposition](#evidence-or-silence--the-advisory-disposition)
- [Fallback](#fallback)
- [Surfacing](#surfacing)
- [Cross-surface note](#cross-surface-note)

`$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`. `$VERIFIER_MODEL`, `$SYNTH_MODEL`,
and `$RUBRIC` are resolved in Setup. The fail-closed rules live in `lib/verification.py` —
do not judge realness yourself and do not reimplement them here or in a second script.

## Where it runs

Inside `## Compile + Dedupe`, **every round**, after the mechanical filters (steps 1–6) and
**before** the verdict — so the verdict counts only verified survivors. The read-only paths
reuse the same compile, so they get it too. This stage **replaces** the old single synthesis
keep/drop judge on the standalone review-code path. The orchestrator dispatches subagents and
reads only small JSON files; it never loads the diff.

## The verifier dispatch

1. **Stage ids and cluster.** After steps 1–6, run `verification.stage_ids` on the merged
   findings array so every finding carries a guaranteed-unique staged id (`v0`, `v1`, …).
   Persist the staged array to `$SESSION_DIR/round-<N>/merged.json`. Then cluster with
   `verification.cluster_findings` — one cluster per `(file, line // 100)` bucket.

2. **Dispatch one fresh verifier per cluster** — `model: $VERIFIER_MODEL` (the **verifier**
   tier, resolved via `--role verifier`; never the session model). Dispatch on the **reviewer
   engine** (`$REVIEWER_ENGINE`). Each verifier reads the cluster's findings (with their staged
   `id`s), the round diff, and the repo — the working tree on branch/auto-fix paths, or
   `$SESSION_DIR/repo` on `--post` / `--review-only`. It must **never** read the PR's own
   description or narrative (the #230 immunity). It writes a bare JSON array to
   `$SESSION_DIR/round-<N>/verdicts.json` (one file per cluster, or merge cluster outputs into
   one array before apply — the consumer keys on `id`).

   Prompt (embed the absolute paths):

   ```
   You are the per-finding verifier for one cluster of a review panel. You are given a
   CLUSTER of merged findings (duplicates already collapsed, each with a staged id) and the
   code change under review. For EACH finding decide whether it holds up against the diff
   and the artifact.

   ## Input
   - Cluster findings: <absolute path to this cluster's findings array> — each has id, file,
     line, title, severity, body/evidence.
   - Diff (read cited hunks here): <absolute path to round-<N>/diff.txt>
   - Verification root (read cited files here ONLY): <absolute verification root — working
     tree or $SESSION_DIR/repo on --post>
   - Severity rubric (the only tiers; calibration): <absolute $RUBRIC path>
   - Project conventions: CLAUDE.md and the project profile.

   ## Immunity (#230)
   You read the diff and the code. You NEVER read the PR's own description, title, or any
   author narrative — judge only from the diff and the repo.

   ## One verdict per finding
   Return one object per input finding:
   - id: the finding's staged id, echoed verbatim — do not recompute or rename.
   - verdict: "CONFIRMED" | "PLAUSIBLE" | "REFUTED".
   - reason: one sentence with quoted evidence. Required for every verdict.
   - severity: optional — the single rubric tier the evidence justifies (Critical/Important/
     Minor/Nit); omit to keep the finding's pre-verification tier.
   - evidence: for CONFIRMED only — the executed receipt: name the triggering input, cite the
     line, quote the code or test output that proves the issue is real.

   Verdict semantics:
   - CONFIRMED — you found the triggering input and can cite it (executed receipt).
   - PLAUSIBLE — the concern may be real but you could not fully prove it from the diff/repo.
   - REFUTED — the finding clearly does NOT hold (wrong, not in changed material, already
     handled); reason must explain why.

   ## Hard rules
   - Judge only the findings in this cluster. Do NOT add new findings, merge findings, or
     decide the run's outcome.
   - Every verdict carries quoted evidence in reason (and evidence for CONFIRMED).

   ## Output
   Write a JSON array to <absolute verdicts.json path>:
   [{ "id", "verdict", "reason", "severity?", "evidence?" }] — exactly one entry per cluster
   finding.
   ```

## Applying the verdicts

Collect all cluster verdict arrays into one list, then apply deterministically:

```bash
python3 -c "
import json, sys
sys.path.insert(0, '$ROOT_DIR/lib')
import verification
merged = json.load(open('$SESSION_DIR/round-<N>/merged.json'))
verdicts = json.load(open('$SESSION_DIR/round-<N>/verdicts.json'))
print(json.dumps(verification.apply_verdicts(merged, verdicts)))
" > "$SESSION_DIR/round-<N>/verified.json"
```

`verification.apply_verdicts(findings, verdicts)` enforces the fail-closed contract:

- **REFUTED with reason** — the finding is dropped; the drop is recorded with
  `{id, file, title, reason, was_blocking_tagged}` (`was_blocking_tagged` preserved when the
  reviewer tagged it Critical/Important).
- **CONFIRMED** — survivor stamped `verdict: "CONFIRMED"`; CONFIRMED evidence from the verdict
  overwrites/sets the finding's `evidence` (the executed receipt).
- **PLAUSIBLE** — survivor stamped `verdict: "PLAUSIBLE"`.
- **KEEP-ON-UNCERTAIN** — a missing verdict, malformed verdict, or REFUTED without a
  non-empty reason keeps the finding as **PLAUSIBLE** at its pre-verification severity — a
  model's silence never drops a finding.
- **Severity normalize** — verdict `severity` applies when it is a valid tier; otherwise the
  finding's original severity stands.
- **Downgrades** — a survivor re-tiered from blocking to non-blocking is recorded in
  `downgrades` with `{id, file, title, from, to, reason?}`.
- **Unmatched** — verdict ids that match no finding are surfaced in `unmatched` (disclosed,
  never a silent no-op).

## Synthesis merge + rank

After verification, dispatch **one** synthesis judge at `model: $SYNTH_MODEL` (`--role
synthesis`) over the survivors only. Its job is **not** keep/drop — it groups findings that
share the same root cause. It emits a JSON array of `{group_id, member_ids}` echoing the staged
ids verbatim. Write the grouping to `$SESSION_DIR/round-<N>/grouping.json`.

Then finalize:

```bash
python3 -c "
import json, sys
sys.path.insert(0, '$ROOT_DIR/lib')
import verification
verified = json.load(open('$SESSION_DIR/round-<N>/verified.json'))
survivors = verified['findings']
grouping = json.load(open('$SESSION_DIR/round-<N>/grouping.json'))
print(json.dumps(verification.merge_and_rank(survivors, grouping)))
" > "$SESSION_DIR/round-<N>/synthesized.json"
```

`verification.merge_and_rank(survivors, grouping)` applies the grouping under a **coverage
guarantee**: every survivor's staged id appears exactly once in the output; invalid or missing
grouping fails open to unmerged survivors; **synthesis drops nothing**. Merged groups combine
bodies and take the highest severity; `verdict` becomes CONFIRMED if any member was CONFIRMED,
else PLAUSIBLE. Findings are ranked Critical → Important → Minor → Nit, then by file and line.

Use `synthesized.findings` as `compiled.findings`. Carry `verified.drops`, `verified.downgrades`,
and `synthesized.merges` into the round record as appropriate.

## Evidence-or-silence + the advisory disposition

Only a **CONFIRMED** finding — one with an executed receipt in its verification trace — may
**GATE** the owner during the auto-fix loop (interrupt with `AskUserQuestion`). A **PLAUSIBLE
Critical never GATEs and never parks**:

1. **Fix if safe** — fold into the fix batch when the fix is mechanical and low-risk.
2. **Confirming probe** — re-dispatch the verifier (`--role verifier`) for that single
   finding to seek the triggering input; a CONFIRMED upgrade then becomes GATE-eligible.
3. **Grounded advisory** — record `action: "skip"`, `advisory: true`, with the PLAUSIBLE
   verdict as the verification trace (citable ground truth). It rides the handback disclosed
   through the skipped-blocker channel and never interrupts mid-run.

This is the #175/#506 evidence-or-silence rule: unproven blockers are visible, never silently
skipped and never owner-interrupting.

## Fallback

If a verifier or synthesis judge wrote no usable output (missing, unreadable, threw, or the
subagent never returned), **keep the merged findings from steps 1–6 with no findings dropped**
— stamp nothing, record empty `drops`/`downgrades`, and proceed to the verdict. A verification
or synthesis failure **never drops a finding and never aborts the review**.

When only verification fails, skip synthesis merge and use the mechanical compile as survivors
(each without a `verdict` stamp, or all PLAUSIBLE if partial verdicts were applied before
failure — prefer the fail-closed `apply_verdicts` output when any verdict file exists).

## Surfacing

Nothing verified away silently:

- **`drops`** — every REFUTED finding with its reason; `was_blocking_tagged` drops flagged
  distinctly in the End-of-Loop Summary.
- **`downgrades`** — every blocking→non-blocking re-tier, shown `from → to`.
- **`advisory: true` skips** — PLAUSIBLE-Critical grounded advisories listed distinctly in the
  End-of-Loop Summary (disclosed unproven blockers the owner reads at review).
- **`unmatched`** — mis-keyed verdict ids disclosed loudly.

All of the above reach the End-of-Loop Summary; the loop may filter false positives or re-tier,
but it may never silently discard or quietly demote a blocker.

## Cross-surface note

`lib/verification.py` owns the standalone review-code compile path described here.
`lib/loop_synthesis.py` remains the fold for the eval-only native JS panel and the doc-loop
acceptance-only path. The staged-id / echo-verbatim discipline is shared: `stage_ids` assigns
`v0..vN` here; every judge echoes ids verbatim; consumers match on exact string `id`.
