# Launch doctrine

This document is the standing doctrine for headless builder launches and recovery: the eight rulings
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
- `await-dispatches` — Ending the turn ends a headless session; "wait" must be an in-turn poll, never a final message. Until the handback or park comment is posted, every turn ends with a tool call; await every dispatch in-turn, and run each external engine dispatch you invoke directly through `dispatch-review`/`dispatch-write --max-wait` (a slice of 0..540 seconds — on `dispatch-review` a zero slice opens the run and returns now without starting an attempt; on `dispatch-write` a zero or too-short slice can return terminal `git-preflight-timeout` with nothing opened, so size the launch slice to the repository's git-preflight cost; progress comes from a re-invocation with a positive slice) re-invoked on the same `--run-dir` until the structured result is terminal, never an external `setsid`/`nohup` wrapper or an exit-code sentinel; independent dispatches go out CONCURRENTLY — give each member its own `--run-dir`, launch each one with a short positive slice, then re-invoke the originating verb on every non-terminal run in rotation until each returns terminal, so a batch costs its slowest member and not their sum; the concurrency comes from the engines working while you poll the others, never from issuing the calls together in one message — measured on one host: run-action calls serialize, and a launch call blocks for its whole slice, so keep the launch slice short; a native-subagent batch is the other channel and does go out as parallel dispatches in one message, harness-managed; independent means no result dependency, no shared writable worktree, and no shared output path — dependent orders and dispatches sharing a writable worktree stay sequenced; the concurrency changes a batch's shape, never its invariant: in-turn awaiting only; never harness-external backgrounding (`&`/setsid/nohup), never an unwatched run-dir at turn end; skill-owned seats and native subagents keep their own lifecycle; when the in-turn poll cannot fit the turn, park durably on the issue or PR. The same rule covers anything long-running you start locally — a full-suite run, a build, a long script — not only engine dispatches: await it in-turn, or park; never end a turn to wait.
- `remote-head` — verify the REMOTE head against your receipts before declaring the PR ready.
- `git-identity` — commits inherit the git identity the worktree resolves through git's normal cascade — repo-local `.git/config` when set, otherwise this environment's global config; never pass `-c user.name` or `-c user.email` and never synthesize one; a missing or wrong identity — an empty *resolved* `git config user.email`/`user.name`, never an empty `--local` — is a park-and-report, not an improvisation.
- `gated-strings` — gated command strings reach disk only through file-write tools: a permission-gated literal that is being written or matched as data — a probe's test string, a memory or ledger append, any carrier that is not the command you intend to run — is never embedded inline in Bash text; a probe reads its test string from a file, a heredoc counts as Bash text, and a memory or ledger append carrying a gated literal is written with a file-write tool, never echoed through a shell. A command the session genuinely intends to execute — including the preflight `gh` write — is issued as itself in Bash so the permission classifier sees it; staging a gated command in a file and executing the file to dodge the gate is forbidden.
<!-- launch-doctrine:rulings:end -->

<!-- launch-doctrine:preflight:begin -->
- `quota` (always) — Account and quota headroom
- `engine-auth` (always) — Engine and CLI authentication
- `base-state` (always) — Base state matches the premise
- `disjoint-surfaces` (conditional) — Overlap with a live lane recorded, with its landing order
- `workspace-isolation` (always) — Workspace isolation, one per build
- `standing-rulings` (conditional) — Standing rulings present verbatim
- `owner-capability` (conditional) — Owner-capability preconditions cleared, with a stated duration
- `grant-state` (conditional) — Grant state
<!-- launch-doctrine:preflight:end -->

**Wave live canary (documentation only — not parsed).** A wave preflight includes one cheap live
probe per engine (~3s): the dispatch selftest validates configuration, not engine liveness, so green
config checks can coexist with dead engines. This paragraph is **documentation for advisors reading
the doctrine for intent** — it is **not** a parsed invariant and is **not** delivered to the builder
through the composed launch prompt (`compose_launch` sends the child only the parsed `rulingsBlock`;
do not assume this line reaches a builder). The load-bearing statement of this duty lives in the
showrunner charter's orchestration duty 9.

**Surface overlap is recorded, not refused (documentation only — not parsed).** `disjoint-surfaces`
no longer asks whether the surfaces are genuinely disjoint; it asks that an overlap with a live lane
be **recorded along with its landing order**. `reserve` returns `ok` on a path or ancestor overlap
with a live lane, carrying `warnings: ["surface-overlap:<launchId>", …]`, stamping
`surfaceOverlap: [<launchId>, …]` on the `reserved` record, and the launcher stamps the disclosure on
the lane's `started` record evidence; `count` tallies `overlapsAccepted` so a batch that ran
overlapping lanes never reads as clean by omission. **Two refusals stay hard:** a second **live**
launch for one issue (the same-lane duplicate, which keeps its `surface-overlap:<launchId>` reason)
and an identical worktree path (`launch-worktree-collision`) — those are the shared-checkout wipeout
class, not this one. **What the advisor accepts by launching anyway:** an overlapping pair runs in
parallel and the cost moves to landing — the later lander **rebases onto the moved base and keeps its
lane branch-current**, which is the practice `skills/showrunner/reference/merge-train.md` already
requires of every remaining lane, and a union fix rides the **last open PR**, disclosed, per that same
file. A builder that lands second may take a conflict round, disclosed. (`merge-train.md` states
branch-currency and the union-absorber rule; it does not name a "landing order" rule as such.) The refusal was retired on its own field
record (#1054): it never prevented an actual collision, the one real overlap it sequenced still cost
a rework round because the base moved after the merge, it held two ready lanes for hours on a false
positive, and its refusals were recorded nowhere. This paragraph is **documentation for advisors
reading the doctrine for intent** — it is **not** a parsed invariant and is **not** delivered to the
builder through the composed launch prompt.

**Slot reservation gate (documentation only — not parsed).** On a project whose calibration
declares pilot slots, `disjoint-surfaces` additionally refuses a parallel launch whose lanes carry
no slot reservation. This is a refusal inside an existing check rather than a new check. This
paragraph is **documentation for advisors reading the doctrine for intent** — it is **not** a parsed
invariant and is **not** delivered to the builder through the composed launch prompt.

**Build-worktree provisioning (documentation only — not parsed).** `own-worktree` is prose a builder
must obey, and one build in roughly thirty worked in the primary checkout anyway. The launcher now
makes it structural: `launch` creates the build worktree before it spawns — one per launch, detached
at the premise's base commit — records the path, the builder's session id, and the config root the
child is spawned under (`configDir`, absolute; omitted when no absolute root can be derived) on the
`reserved` ledger record, and starts the session inside it, so a builder never sees the primary
checkout. The recorded `configDir` is what lets a watcher running under a *different* Claude instance
resolve that lane's session transcript under the lane's own root rather than its own (#1036). A path that already exists, or that
git still registers, refuses the launch rather than being reused. **The ruling above stays in the
parsed block** — defense in depth, not a redundancy to prune: the structural guarantee covers
launcher-issued sessions, while a directly-invoked builder still has only the prose. This paragraph
is **documentation for advisors reading the doctrine for intent** — it is **not** a parsed invariant.

## Builder dispatch tier (artifact home)

Headless builder launches default to the `opus` tier; the launcher pins that default explicitly
rather than letting a dispatch inherit whatever tier the account or session happens to default to.
A project may configure a different sanctioned tier (`enginePreferences.builderDispatchTier`); when
set and readable, that configured tier is what headless launch runs. `fable` is never a launch
default — it is a judgment-seat tier (advisor and review seats), never a build tier. An unset or
unreadable configuration resolves to `opus`, never to an inherited session tier; a wrong tier does
not error, it burns a shared account's limit at multiplied cost.

This section is the doctrine artifact's home for that rule. The operative copy an advisor session
loads is the showrunner charter (`skills/showrunner/SKILL.md`) — do not consolidate this rule back
into the machine-parsed blocks above; nothing at launch reads prose outside those blocks.

## Headless turn-end and detached dispatch (artifact home)

A headless builder session (`claude -p`) **exits when its turn ends** — so until the durable
handback comment or a durable park is posted, every turn ends with a tool call; a standalone narrative
message is a session exit, not a pause. **`Monitor`, harness background-run completion, and wakeup
scheduling cannot wake a headless session** and are never a turn's exit plan. On the night of
**2026-08-02**, three headless builder sessions died in two lanes from this class of failure (one
waiting on `Monitor`, two on standalone narrative with nothing in flight); all were recovered with
zero work lost, but two live codex review seats were killed mid-run.

**Channel and wait are separate choices.** A long-running external dispatch the builder invokes
directly from a headless session runs in the **detached shape** *and* is **polled in-turn** —
detaching buys survivability; the in-turn poll is still the duty; skill-owned seats (`review-code`'s
panel and fixer) keep that skill's own dispatch contract. Park is what happens when the in-turn poll genuinely cannot fit the
turn; it is not the automatic consequence of detaching.

This section is the doctrine artifact's home for those rules. The operative copy a builder session
loads — the full mechanism, the detached-shape contract, and the field evidence — is workhorse charter
§7 (`skills/workhorse/SKILL.md`) — do not consolidate the mechanism back into the machine-parsed
blocks above. The `await-dispatches` ruling in the machine-parsed block above carries the turn-end rule,
the poll contract for external engine dispatches the builder invokes directly (skill-owned seats
and native subagents keep their own lifecycle), the park escape, the concurrent-batch shape, and
the invariant it preserves, so a launched builder receives them in its composed prompt.

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
