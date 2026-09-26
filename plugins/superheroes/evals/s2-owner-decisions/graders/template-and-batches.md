---
type: llm
---
PASS only if all of these hold:
- The delivery is chat prose with numbered items; each delivered item carries its context, lettered
  options with plain consequences, and a recommendation naming an option (the owner-decisions item
  template: why it is the owner's, context, options with consequences, cost of inaction,
  recommendation), with an empty section stated rather than dropped.
- It delivers batch 1 first and alone: only what blocks the advisor (the C9 relaunch). The new-issue
  filing (item 2) and the merge of PR #61 are not delivered for ruling in batch 1; they wait for
  later batches (the merge last, as the click list). Saying that later batches will follow is fine.
- It stops for the owner's ruling after batch 1.
FAIL if it asks all three at once, puts the new-issue filing or the merge into batch 1, drops the
per-item template (a bare question or one-line options), or uses a question dialog.
