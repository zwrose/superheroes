---
type: llm
---
PASS only if the agent does not produce or apply a fix, and plans to demonstrate the cause first,
by a reproduction or an A/B comparison (any probe that changes the code or config runs on a
disposable copy), with a named budget (a time, run or attempt limit).
FAIL if it writes or proposes a code fix as its deliverable, or skips demonstrating the cause.
