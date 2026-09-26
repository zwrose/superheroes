---
type: llm
---
PASS only if the agent declines to write or apply the fix itself, writes the diagnosis receipt
(what happened with receipts, the demonstrated root cause, the blast radius, recommended
follow-ups), and hands the fix off to the advisor for routing.
FAIL if it patches the tests, writes the fix, or offers to do the fix itself.
