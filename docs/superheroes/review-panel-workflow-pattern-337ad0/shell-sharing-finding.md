# Shell-sharing finding (#86, Task 1)

**Question:** Can the native Workflow shell be shared (JS import / `workflow()` within the
1-level nesting limit), or must it ship as a copied documented template?

**Evidence:** The native Workflow JS sandbox has **no filesystem or Node.js API access**, so a
Workflow script cannot `require('./review_panel_shell.js')` — the JS-import sharing path is
unavailable. And `workflow()` composition is **one level of nesting only** ("workflow() inside a
child throws"): a real consumer chain (per-issue Workflow → review-code Workflow → panel) would
need 2 levels, exceeding the limit — so the shared-workflow path is unreliable too. Neither shared
path is reliable.

**Decision: SHELL_FORM = copied-template**

**Consequence for Task 7:** ship the shell as a copied documented template consumers instantiate
(the plan's baseline — not a blocker); the Python core (`panel_tally.py`) remains the single shared
source of truth for all judging.
