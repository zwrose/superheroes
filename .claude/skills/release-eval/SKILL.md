---
name: release-eval
description: Use before cutting a release to discharge the pre-release evidence gate on the open release-please PR — "run the release eval", "clear the release-evidence check", "evaluate this release before merge". It reads the CI check's owed-summary, runs ONLY the instruments the release owes (the live acceptance run and/or the review benchmark), posts the evidence the check verifies, and watches the check flip green. It evaluates — it NEVER releases or merges; that stays yours.
user-invocable: true
---

# release-eval — discharge the pre-release evidence gate

> **Repo-local dev tool** (issue #237). It validates the band before a release and is not
> distributed with the plugin. It runs on Claude Code; each "run this shell command" step is the
> Bash tool. See [RELEASING.md](../../../RELEASING.md) → "Pre-release verification".

This skill is the conductor for the **classify → run → record → merge** ritual — it owns
**run → record**. It does **NOT classify or re-check anything itself**: the `release-evidence`
CI check is the single authority on what a release owes (one classifier, running only in the
check — a skill-side copy would be a duplicated cross-boundary fact). The skill is driven
entirely by the check's machine-readable **owed-summary**. It **stops before merge** — merging
the release PR is always the owner's.

Resolve the checkout once: `ROOT=$(git rev-parse --show-toplevel)`.

## Steps

1. **Find the open release PR and read the check's owed-summary.** The check posts a sticky
   comment carrying `<!-- release-evidence-owed -->` and a machine-readable JSON block. Read it —
   never re-derive it.

   ```bash
   PR=$(gh pr list --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)" \
         --state open --json number,headRefName \
         --jq 'map(select(.headRefName | startswith("release-please--"))) | .[0].number')
   test -n "$PR" || { echo "no open release-please PR — nothing to evaluate"; exit 0; }
   gh api "repos/{owner}/{repo}/issues/$PR/comments" --paginate \
     --jq 'map(select(.body | contains("<!-- release-evidence-owed -->"))) | last | .body' \
     | sed -n '/```json/,/```/p' | sed '1d;$d' > /tmp/owed.json
   cat /tmp/owed.json
   ```

   From `/tmp/owed.json` read: `releaseSha` (the SHA every evidence leg must bind to),
   `bundleSha256` (the released bundle hash the acceptance leg must match), `owed`, `missing`.
   - If the owed-summary comment is absent, the check has not run yet — push nothing; ask the
     owner to wait for / re-trigger the `release-evidence` workflow, then re-run this skill.
   - **If `missing` is empty, the check is already green — say so and STOP.** Do nothing.

2. **Run ONLY the owed-and-missing instruments.** For each entry in `missing`:

   - **`acceptance`** — invoke the repo-local **`acceptance`** skill to run the live pre-release
     acceptance gate (it points `--spine-lib` at this checkout's `plugins/superheroes/lib`, so it
     validates the exact spine being released and records the bundle's SHA-256). This wraps
     `acceptance`; do not re-implement it. When it finishes, read the result record it names:

     ```bash
     # the acceptance report prints the record path; read verdict + provenance from it
     python3 - "$RECORD_PATH" <<'PY'
     import json, sys
     r = json.load(open(sys.argv[1]))
     print("verdict:", r["verdict"])
     print("bundleSha256:", (r.get("spine_provenance") or {}).get("bundle_sha256"))
     PY
     ```

     The record's `spine_provenance.bundle_sha256` MUST equal the owed-summary's `bundleSha256`
     (both are the released bundle's hash). If it doesn't, the run validated a different spine —
     stop and reconcile (usually: the checkout is not on the released commit). Only a `pass`
     verdict is postable.

   - **`benchmark`** — run the review A/B dual-dispatch per
     [`plugins/superheroes/eval/README.md`](../../../plugins/superheroes/eval/README.md), score
     with `plugins/superheroes/eval/score.py`, and **append a dated verdict** to
     [`plugins/superheroes/eval/RESULTS.md`](../../../plugins/superheroes/eval/RESULTS.md)
     referencing this release ref. The ledger is what remembers; the comment below is what gates.

3. **Post the evidence in the exact format the check verifies.** One fenced
   ` ```release-eval-evidence ` JSON comment on the release PR, `releaseSha` set to the
   owed-summary's `releaseSha`, one entry per owed instrument you ran, each `verdict: pass`:

   ````bash
   cat > /tmp/evidence.md <<EOF
   Pre-release evidence for this release (posted by \`release-eval\`).

   \`\`\`release-eval-evidence
   {
     "schemaVersion": 1,
     "releaseSha": "<owed-summary releaseSha>",
     "instruments": [
       {"instrument": "acceptance", "verdict": "pass", "bundleSha256": "<record bundle_sha256>", "recordPath": "<record path>", "date": "$(date -u +%F)"},
       {"instrument": "benchmark", "verdict": "pass", "resultsRef": "plugins/superheroes/eval/RESULTS.md", "recordPath": "plugins/superheroes/eval/RESULTS.md", "date": "$(date -u +%F)"}
     ]
   }
   \`\`\`
   EOF
   gh pr comment "$PR" --body-file /tmp/evidence.md
   ````

   Include **only** the instruments that were owed. (Evidence is pooled across comments and
   SHA-bound, so a prior release's leftover evidence can never satisfy this one.)

4. **Watch the check flip green, then STOP.** Posting the comment re-triggers the check
   (`issue_comment`). Poll the `release-evidence` commit status until it is `success`:

   ```bash
   gh api "repos/{owner}/{repo}/commits/<releaseSha>/status" \
     --jq '.statuses[] | select(.context=="release-evidence") | .state'
   ```

   - Green → report: the release owes `<owed>`, evidence posted and verified, the check is green.
     **Stop. Do not merge** — cutting the release is the owner's one-click act.
   - Still red → read the refreshed owed-summary for the reason (e.g. a binding mismatch), fix it,
     re-post, and re-poll. Never bypass the gate from here; the admin-bypass override is the
     owner's, at merge.
