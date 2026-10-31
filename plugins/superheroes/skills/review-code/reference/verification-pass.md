## Contents

Per-finding verification for standalone review-code compile (#506).

- [Where it runs](#where-it-runs)
- [The verifier dispatch](#the-verifier-dispatch)
- [Applying the verdicts](#applying-the-verdicts)
- [The grade and the missed-path step](#the-grade-and-the-missed-path-step)
- [Synthesis merge + rank](#synthesis-merge--rank)
- [Evidence-or-silence + the advisory disposition](#evidence-or-silence--the-advisory-disposition)
- [Fallback](#fallback)
- [Surfacing](#surfacing)
- [Cross-surface note](#cross-surface-note)

`$ROOT_DIR` is `${CLAUDE_PLUGIN_ROOT}`. `$VERIFIER_MODEL`, `$SYNTH_MODEL`,
and `$RUBRIC` are resolved in Setup. The fail-closed rules live in `lib/verification.py` —
do not judge realness yourself and do not reimplement them here or in a second script.

## Where it runs

On the loop, **every round**, the mechanical compile (steps 1–3 + 4 nit cap, in `## Compile + Dedupe`)
and this verification stage run **inside `round_driver.py`** when findings are submitted, before
the verdict — see `round-driver.md`. This stage **replaces**
the old single synthesis keep/drop judge. The orchestrator dispatches subagents and reads only
small JSON files; it never loads the diff.

## The verifier dispatch

1. **Stage ids and cluster.** After mechanical compile (citation, diff-scope, dedupe, nit cap —
   driver-owned), run `verification.stage_ids`
   on the merged findings array so every finding carries a guaranteed-unique staged id (`v0`, `v1`, …).
   Persist the staged array to `$SESSION_DIR/round-<N>/merged.json`. Then cluster with
   `verification.cluster_findings` — one cluster per `(file, line // 100)` bucket.

**Before dispatching this round's verifiers, clear any stale verdict files.** On a same-round
restart/resume the round dir may already hold `verdicts-*.json` from a prior, abandoned attempt.
Remove them first — `find "$SESSION_DIR/round-<N>" -maxdepth 1 -name 'verdicts-*.json' -delete 2>/dev/null`
— so each attempt writes a **fresh** set and the Applying glob only ever concatenates THIS
attempt's files. (This is a glob-free `find … -delete`, not a shell glob: under zsh an unmatched
`*.json` glob aborts the command with `no matches found` (exit 1) — i.e. it would fail exactly on
the empty/fresh round dir where there is nothing to clean. `find` never lets the shell expand a
glob, so it no-ops cleanly, exit 0, on an empty dir.) A stale per-cluster file from a prior
attempt must never be globbed and honored.

2. **Dispatch one fresh verifier per cluster** — `model: $VERIFIER_MODEL` (the **verifier**
   tier, resolved via `--role verifier`; never the session model). Dispatch on the **vendor the
   driver selected** — on the auto-fix loop the `vendor` of this seat in the orders manifest
   (`seats.<skey>.vendor`), which replaces the reviewer engine (`$REVIEWER_ENGINE`) whenever that
   engine sits in a maker family; `$REVIEWER_ENGINE` only stands when no manifest vendor is named.
   Submit that vendor as `verifierVendor` beside `verdicts`: verdicts from any other vendor are
   ignored by the fold. `$VERIFIER_MODEL` is a Claude tier alias and stands only for a native
   Claude dispatch: when the vendor was switched to `codex` or `cursor` for independence, resolve
   that vendor's own verifier model (and effort) from the registry cell
   `model_registry.matrix_config("verifier", <vendor>)` and dispatch that pair instead — the
   manifest carries the vendor, not its model, and `dispatch_guard check` with role `verifier`
   validates the vendor/model pair, so a Claude alias on another vendor is refused. The driver seats a non-panel reviewer only on a vendor whose dispatched cell for the phase (the verifier cell here, the reviewer-deep cell for gap sweep and scoped) the seat map proves live, and a native host seat takes the host's family. Each verifier reads the cluster's findings (with their staged
   `id`s), the round diff, and the repo — the working tree. It must **never** read the PR's own
   description or narrative (the #230 immunity). The clusters' verifiers run in **parallel**,
   so each writes its **OWN** file — `$SESSION_DIR/round-<N>/verdicts-<cluster-index>.json`,
   where `<cluster-index>` is the cluster's 0-based position in the `cluster_findings` order —
   so no two verifiers race on a shared path. The apply step below concatenates every
   per-cluster file into one array (the consumer keys on `id`).

   **On the auto-fix loop**, the driver emits each verifier's complete order at
   `$SESSION_DIR/round-<N>/orders/dispatch-verifiers/<skey>.a<K>.md` on `next` — dispatch that
   file, do not hand-compose. Template body: `rubric/orders/dispatch-verifiers.md`.

   **Delivery channel — file vs stdout.** The emitted order's `## Output` / channel block names
   which path this seat uses:
   - **File channel** (native subagent or `claude` host seat): write
     `$SESSION_DIR/round-<N>/verdicts-<cluster-index>.json` — a JSON array of verdict objects, one
     per cluster issue. This is the workflow the glob in "Applying the verdicts" below merges.
   - **Stdout channel** (`codex`/`cursor` engine seat): emit `{"verdicts": [...]}` as final stdout
     through `dispatch-review` — the seat writes **no** `verdicts-*.json` file. Fold the terminal
     `dispatch-review` result's `verdicts` array into the phase artifact the same way you would
     have read the per-cluster file. Do not follow the file workflow on a read-only engine dispatch
     or the verdicts are lost.

## Applying the verdicts

Concatenate **every** per-cluster verdict file into one list — **sorted by cluster index** so
the merged order is deterministic — then apply. (The glob below trusts that stale `verdicts-*.json`
from a prior same-round attempt were already removed before dispatch by the glob-free
`find … -delete` in "The verifier dispatch" — so it only ever sees the current attempt's fresh set.)

```bash
python3 -B -c "
import json, sys, glob, os, re
sys.path.insert(0, '$ROOT_DIR/lib')
import verification
merged = json.load(open('$SESSION_DIR/round-<N>/merged.json'))
def _idx(p):
    m = re.search(r'verdicts-(\d+)\.json$', os.path.basename(p))
    return int(m.group(1)) if m else 0
verdicts = []
for p in sorted(glob.glob('$SESSION_DIR/round-<N>/verdicts-*.json'), key=_idx):
    part = json.load(open(p))
    if isinstance(part, list):
        verdicts.extend(part)
print(json.dumps(verification.apply_verdicts(merged, verdicts)))
" > "$SESSION_DIR/round-<N>/verified.json"
```

`verification.apply_verdicts(findings, verdicts)` enforces the fail-closed contract:

- **REFUTED with reason** — the finding is dropped; the drop is recorded with
  `{id, file, title, reason, was_blocking_tagged}` and the grade wrong with that reason
  (`was_blocking_tagged` preserved when the reviewer tagged it Critical/Important), **unless**
  its reason or evidence shows a check that did not execute the code under test
  (`command not found`, exit 127, `ERR_MODULE_NOT_FOUND`, `Cannot find module`,
  `Cannot find package`, `ModuleNotFoundError`, `No module named`, or the tokens
  `command-not-found` / `module-not-found`): that keeps the finding PLAUSIBLE at its
  pre-verification severity with `unverified: true`, its id in `unverified`, and an entry in
  `notExecuted`.
- **CONFIRMED** — survivor stamped `verdict: "CONFIRMED"`; CONFIRMED evidence from the verdict
  overwrites/sets the finding's `evidence` (the verification evidence), and the grade confirmed.
- **PLAUSIBLE** — survivor stamped `verdict: "PLAUSIBLE"`, and the grade plausible.
- **KEEP-ON-UNCERTAIN** — a missing verdict, malformed verdict, or REFUTED without a
  non-empty reason keeps the finding as **PLAUSIBLE** at its pre-verification severity — a
  model's silence never drops a finding. It carries no grade.
- **Severity normalize** — verdict `severity` applies when it is a valid tier; otherwise the
  finding's original severity stands.
- **Downgrades** — a survivor re-tiered from blocking to non-blocking is recorded in
  `downgrades` with `{id, file, title, from, to, reason?}`.
- **Unmatched** — verdict ids that match no finding are surfaced in `unmatched` (disclosed,
  never a silent no-op).
- **Unverified** — finding ids that received **no** matching verdict this round (verifier
  silence or a lost verdict file) are surfaced in `unverified`; the findings still survive as
  PLAUSIBLE (keep-on-uncertain), but the coverage gap is disclosed, never invisible.
- **Ambiguous** — a finding id carried by more than one verdict is ambiguous: honor none of
  them (keep-on-uncertain, so a later REFUTED can't silently drop it) and surface the id in
  `ambiguous`.

## The grade and the missed-path step

Only the [verifier](../../../rubric/glossary.md#verifier) closes a finding as wrong. The fold
gives every finding a verdict was honored for a `grade` — `{"verdict": "confirmed" | "plausible"
| "wrong", "reason": …}` — on the finding and on its ledger row, and the review record shows it.
A receiptless CONFIRMED, and a REFUTED resting on a check that did not execute, are graded
plausible. A finding the verifier was silent on, or gave a malformed or ambiguous verdict, has no
grade. A grade a reviewer put on its own finding is removed when findings are staged. The record
reads `shown-wrong` only for a refuted finding that carries the verifier's wrong grade, or one an
earlier record already listed as shown wrong; any other attempt to write `shown-wrong` is refused
or leaves the finding open. The author-justification post-filter carries a finding to the owner,
never to `shown-wrong`.

**A passing test that missed its path.** For a finding whose break-it test passed on the unfixed
code, the verdict also says `pathReached`. A test that reached the finding's path and still
passed, and whose assertions check the behaviour the finding names, is evidence the finding does
not hold: REFUTED, graded wrong, and sent to no fix; when its assertions are too weak to decide
it, the verifier judges from the code. One that never reached the path (`pathReached: false`, with any verdict but an evidenced CONFIRMED) is
held: it is not graded, dropped or grouped, and it is listed in the verify record's `held`. The
driver then emits `dispatch-second-test`: a fresh run of the [test role](../../../rubric/glossary.md#test-role), seated outside every
maker's family, gets the held findings, each with its first test, that test's output and the
verifier's note, and writes one more test for each
([the order](../../../rubric/orders/dispatch-second-test.md)). The build session runs each new
test as it runs the first, in its own working copy at the unfixed head, and records the run with
the finding and in the round's `breakItRuns`; the finding is marked `secondTest: true`. Then the
held findings alone go back to the verifiers. On that pass `pathReached` is not acted on: a
REFUTED closes the finding as wrong, and any other verdict keeps it, graded, as a judgment call
when its test again missed the path. No third test is written. The findings kept in the first
pass rejoin the second pass's survivors, freshly staged, before synthesis.

A held finding never goes missing: when no reviewer outside the makers' families can be seated,
no order is emitted, the round records `secondTestUnseatable`, and the held findings go straight
to the second pass with no new test. A held finding the seat returns no test for goes to the
second pass with its first test only, listed under the round's `secondTest.noTest`.

## Synthesis merge + rank

After verification, dispatch **one** synthesis judge at `model: $SYNTH_MODEL` (`--role
synthesis`) over the survivors only. Its job is to group findings that share the same root
cause, not keep/drop. It also receives the round's refuted findings and the PR's earlier findings.
It emits a JSON array of `{group_id, member_ids, repeatOf}` echoing the staged ids verbatim;
`repeatOf` is an earlier finding's ref or null. Refuted ids may sit in a group only to carry a
mark and are never merged. When only refuted findings remain and the PR has earlier findings,
synthesis runs repeat-only. What a mark does is in
[synthesis-pass.md § Repeats](synthesis-pass.md#repeats). Write the grouping to
`$SESSION_DIR/round-<N>/grouping.json`.

The synthesis seat sits outside every maker family on a proven synthesis cell; when no vendor qualifies, no synthesis order is emitted and the findings are not grouped (each stays separate, nothing is dropped), which the receipt discloses.

**On the auto-fix loop**, dispatch the driver-emitted order at
`$SESSION_DIR/round-<N>/orders/dispatch-synthesis/<skey>.a<K>.md` (template body:
`rubric/orders/dispatch-synthesis.md`).

Then finalize:

```bash
python3 -B -c "
import json, sys
sys.path.insert(0, '$ROOT_DIR/lib')
import verification
verified = json.load(open('$SESSION_DIR/round-<N>/verified.json'))
survivors = verified['findings']
grouping = json.load(open('$SESSION_DIR/round-<N>/grouping.json'))
print(json.dumps(verification.merge_and_rank(survivors, grouping)))
" > "$SESSION_DIR/round-<N>/synthesized.json"
```

The grouping must account for **every** staged survivor id **exactly once** and each refuted id at
most once, under a **coverage guarantee**. When a **non-empty** grouping is submitted, each survivor
id must appear in exactly one group's `member_ids`; a grouping that omits any staged id is
**refused** with `staged-id-unresolvable` naming the omitted id — submit the grouping again with
the missing ids as singleton groups. A `repeatOf` ref that names no earlier finding is refused at
submit the same way. A submit with no `grouping` key is **refused** at submit. **`grouping: null`**
or an **empty-list** grouping carries no coverage obligation:
`verification.merge_and_rank(survivors, grouping)` falls open to unmerged survivors;
**synthesis drops nothing** and synthesis failure never aborts the review. In a group, a finding that carries a
break-it test is never merged into another finding: it keeps its test and its runs, while the
group's other members merge as above. The group's resulting findings, when they number two or more
and include a test-carrying one, form a fix group with one fix; `merge_and_rank` returns them as
`fixGroups` (`{group_id, member_ids}`) beside `merges`, which lists real merges only, and the driver
mints the group's id. A group with no test-carrying member is unchanged: its merge is its one fix.
Merged groups combine bodies and take the highest severity; the merged `verdict` is **CONFIRMED only when a member at
the merged (highest) severity is CONFIRMED-with-evidence** — computed **order-independently**, so
model-supplied member order can't flip GATE-eligibility, and carrying that member's receipt (the
first such member in input order). A lower-severity confirmation **never promotes** the merged
finding (no receiptless CONFIRMED is fabricated onto the higher-severity finding); otherwise the
merge is PLAUSIBLE. Findings are ranked Critical → Important → Minor → Nit, then by file and line.
Merged severity is the **highest effective severity among the group's members**, computed on the
normalized fail-closed vocabulary in `circuit_breaker` (`severity_rank` / `effective_severity` /
`canonical_severity`), so the merge can never produce a group less blocking than a member; `_kept_severity`
honors a verdict severity at its **canonical** tier, so a mis-cased tier is neither ignored nor
silently demoted.

Use `synthesized.findings` as `compiled.findings`. Carry `verified.drops`, `verified.downgrades`,
`synthesized.merges`, and `synthesized.fixGroups` into the round record as appropriate.

**Author-justification post-filter (PR mode, after merge_and_rank).** May take off the fix path
only non-CONFIRMED findings with a substantive prior justification (quoted in the record),
carrying each to the owner (`left-for-owner` in the review record, never `shown-wrong`); CONFIRMED
survives stamped `challenge: "author-justified"`. Full rules: `round-driver.md`.

## Evidence-or-silence + the advisory disposition

Only a **CONFIRMED** finding — one whose verification trace cites the triggering input — may route
to **GATE** under the escalation rubric (`escalation-base.md`). **When escalation resolves GATE**
for a CONFIRMED finding, **stop the auto-fix loop immediately** — write the GATE down per
`escalation-base.md` § Writing a GATE into the durable artifact into `$SESSION_DIR/round-receipt.json`
(the terminal receipt the driver writes on exit), force terminal with verdict **`handed-back`**
(certification withheld), and hand back — **never
wait**. **Never** fold a GATE finding into `fix-batch.json` and **never** set `apply-fixes`
past it. A GATE is a terminal hand-back, not a mid-run question.

A **PLAUSIBLE Critical never GATEs and never parks** — for unproven blockers, use only:

1. **Fix if safe** — fold into the fix batch when the fix is mechanical and low-risk.
2. **Confirming probe** — re-dispatch the verifier (`--role verifier`) for that single
   finding to seek the triggering input in the diff and the repo; a CONFIRMED upgrade then
   becomes GATE-eligible. Where the triggering input can only be established by a **mutation**,
   that run is the orchestrator's — the verifier never mutates. A review seat is **obliged**
   never to change the repository and never to claim a run it did not make — the base rubric's
   verification rule **"A review seat never changes the repository, and never claims a run it did
   not make."** (`rubric/review-base.md`) is the authoritative statement; this is the pointer, not
   a second copy.
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
- **`unmatched`** — mis-keyed verdict ids (a verdict that matched no finding) disclosed loudly.
- **`unverified`** — findings that received no verdict this round (verifier silence / a lost
  verdict file); they survive as PLAUSIBLE, but the coverage gap is disclosed, never invisible.
- **`notExecuted`** — a REFUTED that rested on a check that did not execute the code under test,
  kept as an unverified PLAUSIBLE finding, each entry `{id, file, title, reason}` with the reason
  `not-executed: <token>: <the verifier's reason>`; never a drop.
- **`held`** — findings whose passing break-it test missed their path; each gets one more test
  and is graded on the second pass, never dropped.
- **`ambiguous`** — findings whose id carried conflicting duplicate verdicts; honored as none
  (keep-on-uncertain) and disclosed, never a silent last-write-wins drop.

All of the above reach the End-of-Loop Summary; the loop may filter false positives or re-tier,
but it may never silently discard or quietly demote a blocker.

## Cross-surface note

`lib/verification.py` owns the standalone review-code compile path described here.
`lib/loop_synthesis.py` remains the fold for the eval-only native JS panel and the doc-loop
acceptance-only path (`skills/review-code/reference/synthesis-pass.md`). The staged-id / echo-verbatim discipline is shared: `stage_ids` assigns
`v0..vN` here; every judge echoes ids verbatim; consumers match on exact string `id`.
