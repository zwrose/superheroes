# Launch doctrine

This document is the standing doctrine for headless builder launches and recovery: the six rulings
a dispatch must carry verbatim, the eight-check dispatch preflight every launch records before it
goes autonomous, and the recovery doctrine for taking over a build that stopped. Advisors read it
for intent; `lib/launch_doctrine.py` parses the two marked blocks below fail-closed — not the
recovery prose. A whole-file SHA-256 digest of this artifact is still recorded on every dispatch
as `doctrineDigest` — editing recovery prose changes that digest even though it is not
machine-parsed.

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

## Recovery — taking over a build that stopped

A launched builder can stop for reasons unrelated to its work — the account it burns hits a limit,
the host kills the session, a turn ends on something that never wakes it. Recovery is the other
half of launch doctrine, and it is where the expensive mistakes are: work that was never pushed
gets discarded, or a dead session's claims get inherited as though someone had checked them.

### Adopt; do not resume across instances or accounts

Resume (`claude --resume <session-uuid> -p`) reopens the dead session's own context and works
**only from the same config dir** — the same instance and account it launched on. The UUID must be
the full one, not a prefix. A resumed session **appends to its original transcript file** rather
than creating a new one; the transcript you were watching stays the transcript.

Adoption is the other move: a **fresh** session takes the build over from durable artifacts only —
**the pushed branch at a named sha**, the issue, the PR, the posted receipts — and nothing travels
from the dead session's head. Across a different instance or account, **adoption is the only path**,
because sessions do not transfer across config dirs; do not reach for resume there and do not
quietly relaunch the work on the recovering session's own account.

**Every claim inherited from the dead session is unverified until re-run.** A commit message
asserting tests passed, a PR body asserting a panel ran, or a comment asserting a gate was probed
are **inputs, not receipts** — adopt the artifacts, re-earn the claims.

### Sweep for unpushed work before adopting

A dead build leaves work **no PR list and no** `gh` query will show: commits made in its worktree
but **never pushed**, and edits never committed at all. Adopting the pushed tip without looking
discards them silently.

Before any new order goes out, sweep the dead build's worktrees and branches — enumerate them, read
each one's local head and working tree, reconcile against what is actually pushed — then adjudicate
every piece of residue explicitly as **integrated** (already contained in the pushed tip),
**subsumed** (superseded by later work — name what superseded it), or **contested** (real work that
is neither, decided in the open before the build moves on, never dropped by omission). Residue that
is not already contained in the pushed tip is **made durable before the build moves on** — pushed
to a retrievable branch (or otherwise preserved) and named in the durable post by its sha. When the
dead build **pushed nothing at all**, there is no tip to adopt: preserve the worktree's work first,
then adopt from what you preserved. **An adoption that records no sweep is an adoption that has not
looked.** The advisor runs this sweep before composing the successor's launch and records what it
found for handoff; the adopting builder re-runs the sweep at intake and reconciles against that
handoff — both halves run, neither replaces the other.

### Pin the transcript; never re-discover it

Map a builder to its transcript by grepping the **first 4KB** of each transcript file for the
**issue token** the launch prompt carries. The token match must be **unique before you pin** — more
than one match is a signal to disambiguate, not to pick one. The launch ledger records each dispatch's
**pid** and **logPath** at start — **pid** identifies the **process**, not the transcript; it is the
right handle for the liveness read in the next sub-section. **logPath** is the child process's stdout
log, not a transcript identifier. The launcher records **no transcript identifier** — when the token
match is not unique, disambiguate by **reading the candidates' content** (which one carries this
build's actual work), not by recency — and **never** by taking the newest file. Once uniquely matched,
**pin that file path** and use it for the rest of the run. **Never
re-discover** a builder's transcript by taking the newest file — **a dead launch attempt leaves a
stub**, and newest-first hands you the stub while the live retry runs elsewhere. Because a resumed
session appends to its original file, "look for a new transcript" is wrong for the resume case too.

### Read liveness from the right signals

A **double-confirmed** process check — the process must read as gone twice, separated in time,
because single reads false-negative. Pinned-transcript **mtime** freshness: quiet for a long stretch
while the process is still alive is a stall or a blocked permission prompt, not progress.

The **stdout log is not a liveness signal** — a `-p` session **buffers its output to exit**, so an
empty or unchanging log says nothing about whether the session is working. **Never identify a worker
by a global process match**: a `pgrep` on an engine's name catches long-lived daemons and, under
parallel load, sibling sessions' dispatches — poll the thing you own (your own output file, your own
recorded pid, your own task id).

### Suspect quota before you suspect a defect

An **unexplained early exit** — a session that stops with no park, no handback, and no error that
explains it — is checked against **the account the builder was burning** before it is treated as a
defect in the work. A cross-instance launch makes this easy to miss: the recovering session cannot
feel the builder's quota pressure, and a cheap probe that passes on that account is **not proof of
deep headroom**. Rule out the limit first.
