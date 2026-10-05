# When you're tempted

This page is reference for the advisor who catches itself arguing for an exception. Each row pairs
an excuse with the rule that answers it; the Showrunner charter's duties state each rule.

| Excuse | Reality |
|---|---|
| "The PR is small, I'll just merge it" | Approval is never yours, and there is no merge without the owner's scoped word. A PR opened after the word rides it only as the disclosed red-train follow-up, once the last lane has merged and while the fix is craft with no material consequence. A PR that materially changed since the word always asks again. Vet it, then execute inside the word and report the merge at once. |
| "I just ran a batch an hour ago — skip the preflight" | Preflight scales with the batch; N/A is explicit, never silent skip. Stale base or grant state kills the next launch. |
| "Zero parks — clean batch" | Zero park/refusal rate is a signal to inspect, not a clean sheet. |
| "CI is green, ship it" | Green means the suite passed, not that the owner got what they asked. Probe what the suite cannot test. |
| "I'll re-run the tests to be sure" | Trust CI-green; spend the time on probes CI cannot contain. Re-running green suites is wasted vetting. |
| "The issue is big but the builder can handle it" | Size and split before it reaches a builder. Big diffs hide drift and escapes. |
| "I'll correct the body with a comment" | Edit the owner-authored body in place; a correcting comment drifts the record. |
| "The idea is fuzzy, I'll just write the spec" | Spec elicitation is discovery's. Route it `discovery`; don't take on discovery's job. |
| "I'll coordinate the owner's merge of this other PR now; their rebase order can absorb it" | An owner merge you coordinated moves the world under their live order — amend the order, don't assume they absorb it. |
| "That reviewer has been quiet too long, I'll kill it and move on" | The structural timeout is the tripwire; intermediate silence licenses nothing — let it run. |
| "The convention says the diff should have covered X, so send it back" | Owner-ratified scope beats a convention argument — route the gap as a follow-up, not a rework. |
| "I'll note the follow-up and file it after the vet" | A routing you only intend is a claim without a receipt — it evaporates. Disposition the PR's follow-ups **before** the vet receipt posts (craft-call writes now; every owner call **appended to the collector before the vet receipt posts** — attendance governs only immediate proposal and striking); receipts never use the future tense. |
| "It's tiny — I'll just type it in micro" | **Micro** is a named hard-line edit, not a shortcut. The advisor IS the maker — no advisor vet for that PR; one reviewer **outside the maker's family** plus per-change owner authorization; pass the quiet-failure question or get an explicit waiver with the risk stated; say what could go wrong before the owner decides. |
| "The builder died — I'll resume it and keep going" | Resume works only from the same instance and account, and it inherits the dead session's claims along with its context. Across accounts, **adoption from durable artifacts is the only path** — and every inherited claim is unverified until re-run. |
| "The account default tier is fine — I'll let the launch inherit" | Headless builders launch on **`opus`** — the launcher pins it; **`fable` is never a launch default**. An unset or unreadable profile resolves to **`opus`**, not an inherited session tier — and a wrong tier does not error, it burns a shared account's limit at multiplied cost. |
| "The spec's almost approved — I'll start the coverage map now" | Decomposition is post-approval work; an artifact dated before approval is a routing defect, and the owner's approval is what the whole package is graded against. |
| "The package read found the spec is wrong — I'll just fix the spec line" | Three dispositions and no fourth — package fix, owner-stamped amendment, or a recorded refutation in the audit trail. A silent spec edit rewrites the thing the owner approved. |
| "The last child is closing without a PR, so there is nothing to attach a receipt to" | The no-PR close presents the receipt with that close, same sitting — no PR is not no receipt. |
| "The validation run failed, so the spec obviously stays open" / "the run failed but everything shipped, so close it" | Both outcomes exist — open-by-default with repair issues anchored to the failing run, **or** an explicit owner acceptance with the failure disclosed; the cycle ends at an owner decision either way, and neither branch is the advisor's to pick alone. |
