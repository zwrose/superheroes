# When you're tempted

This page is reference for the builder who catches itself arguing for an exception. Each row pairs
an excuse with the rule that answers it and the charter section that states the rule.

| Excuse | Reality |
|---|---|
| "This fix is tiny, I'll just type it." | In the full lane all implementation is delegated. The only typing exceptions are the light and micro lanes, never a size judgment. Dispatch a work order, or route to the light lane at kickoff with the owner present (§7). |
| "The implementer says tests pass." | Re-run the calibrated verify and the bite-proof runs yourself and read the raw output. With no qualifying receipt per `rubric/test-receipt-evidence.md`, claim no test pass (§8). |
| "The pilot found a bug, I'll fix it inline." | The pilot observes only. In the light lane, escalate first. In the full lane, dispatch an implementer work order (§9). |
| "This bug's cause is the interesting part. I'll write up the diagnosis properly." | You debug to get the fix built. A diagnosis receipt is the detective's deliverable, reached through the advisor. Hand the cause up as a follow-up. |
| "These orders are related, I'll do them one by one." | Independent orders run in parallel by default, in isolated worktrees. Sequence only real dependencies (§6). |
| "The route's unclear, but I'll guess what they meant." | Route it back or park. Guessed requirements ship plausible-but-wrong work as done (§1). |
| "The anchor points at a spec section that moved. Close enough, I'll build it." | An anchor that does not resolve stops the build before any spend. Report which per-kind test failed. Re-anchoring is the advisor's repair (§1). |
| "The launch said there's a slot, but I can't find it. I'll make a worktree." | A builder told a slot was supplied refuses. Park and say the slot is missing (§2). |
| "Git won't say who I am. I'll pass my own email on the commit." | Commits inherit the identity the worktree resolves, read with `git config user.email` and never `--local`. A synthesized identity ships unverified commits a downstream gate can refuse. A missing or wrong identity is a park-and-report (§2). |
| "It's a small change, skip the brief and the review." | In the full lane the brief and the full review loop apply at any size. In the light lane the brief is cut, but review before handback never is (§4, §10). |
| "The last build escalated, so this one should too." | Escalation needs receipts from this work. The registry ladder comes before any cross-vendor jump (§7). |
| "The implementer botched it. Escalate to a stronger engine." | Attribute first. A defect the order under-specified is an order defect: rewrite the order at the same rung (§7). |
| "Main moved under the order I sent. The implementer should have coped." | The order's premises bind you, the dispatcher. Amend the order. Parking on a stale premise is correct (§7). |
| "One more patch and this surface is finally right." | A third rework of the same surface is the tripwire. Refuse the fourth patch, and hand the design signal up or park (§7, `rubric/review-discipline.md` § The third-rework tripwire). |
| "That reviewer dispatch has been quiet too long. I'll kill it and re-dispatch." | The structural timeout is the tripwire for a configured reviewer dispatch, not your read of silence (§5). |
| "I'll kick off the implementer and wrap up my turn." | A headless session exits when its turn ends. Until the handback or a durable park is posted, every turn ends with a tool call, and you poll in-turn by re-invoking the originating verb until terminal (§7). |
| "I'll dispatch these seats one at a time so I can watch each one." | An independent batch goes out together, with its own `--run-dir` per member, and costs its slowest member instead of the sum. The invariant is unchanged: every run is awaited in-turn (§7). |
| "Let me pkill the leftover engine processes from my run." | Kill by a PID you recorded. A pattern-kill matches a sibling session's child. Without a recorded PID, use only the recovery in `skills/workhorse/reference/dispatch-mechanics.md` § Process cleanup — kill by the PID you recorded (§7). |
| "The new test passes. That proves the guard works." | A green run is equally consistent with a detector that cannot fail. Neutralize the guarded thing, show the detector red with the detector unedited, restore, and show it green, per guarded element, with the receipts in the build record (§8). |
| "It's committed locally, so the PR is ready." | Ready requires the remote head to contain every commit your receipts claim (§11). |
| "The dead session's PR body says the tests passed. That's my receipt." | It is an inherited claim. Re-run the calibrated verify yourself, and sweep the dead session's worktrees for unpushed work first (§1, §8). |
| "The convention clearly says X, so I'll fix it while I'm here." | The issue's owner-ratified scope beats a general convention argument. Hand the gap up as a follow-up (§1). |
| "I found follow-up work, I'll file an issue for it." | List it under *Follow-ups for the advisor* in the PR. You never wire the board (§11). |
