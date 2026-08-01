# Launch doctrine

This document is the standing doctrine for headless builder launches: the six rulings a dispatch
must carry verbatim, and the eight-check dispatch preflight every launch records before it goes
autonomous. Advisors read it for intent; `lib/launch_doctrine.py` parses it fail-closed.

The rulings block exists because reconstructing those lines from memory is what caused the
shared-checkout collision — `own-worktree` is first because that ruling is the one that collision
dropped.

**Machine-parsed blocks:** the two HTML-comment-delimited sections below are parsed byte-for-byte.
Editing any line inside them changes what `lib/launch_doctrine.py` accepts.

<!-- launch-doctrine:rulings:begin -->
- `own-worktree` — build in your OWN worktree, NEVER the primary checkout.
- `base-moved` — if your base merges mid-build, rebase onto main, retarget, and disclose.
- `no-force-push` — never force-push (it is gated); use a fresh branch if history must move.
- `design-forks` — design forks inside ratified scope are your call with disclosure; park only genuinely consequential ones.
- `await-dispatches` — await every dispatch in-turn; background-and-poll is fine when a dispatch cannot fit the foreground cap — the failure is ending a turn with a dispatch unawaited.
- `remote-head` — verify the REMOTE head against your receipts before declaring the PR ready.
<!-- launch-doctrine:rulings:end -->

<!-- launch-doctrine:preflight:begin -->
- `quota` (always) — Account and quota headroom
- `engine-auth` (always) — Engine and CLI authentication
- `base-state` (always) — Base state matches the premise
- `disjoint-surfaces` (conditional) — Surfaces genuinely disjoint
- `workspace-isolation` (always) — Workspace isolation, one per build
- `standing-rulings` (conditional) — Standing rulings present verbatim
- `owner-capability` (conditional) — Owner-capability preconditions cleared, with a stated duration
- `grant-state` (conditional) — Grant state
<!-- launch-doctrine:preflight:end -->
