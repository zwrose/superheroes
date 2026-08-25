<!-- headless-presentation — review-code -->

# `--review-only` presentation contract

This file is the **single** presentation path for `--review-only`. Presence is an event — the
owner's words in the current turn — not a state a run can detect, so a review never bets its
output on a human being there. The run always writes its presentation to the durable artifact
and never opens a question that could block waiting for an answer.

`--review-only` is the charter's focused vet-escalation instrument and, since `--post` was removed
(#1121), the only read-only review path. The presentation completes every time: findings the POV
marks `Fix` land under **Approved**; findings that need a human call land under **Undecided** —
listed in full, neither approved nor dropped.

## What this path runs

Everything up to the review gate is **unchanged** — the same single pass under `round-1/`, the
same compaction recovery from `compiled.json` + `meta.json`, and the same **orchestrator POV**
formed per finding. Only the gate's resolution changes: it is written down instead of asked.

Open no `AskUserQuestion` on any review-code path, for any purpose.

## The artifact

Write the presentation as plain prose to `$SESSION_DIR/round-1/presentation.md`, then exit
cleanly. Never a stall, and never a silent skip — an absent artifact is indistinguishable from
a review that never ran.

The artifact carries, in this order:

1. **The verdict banner and the one-line summary** — the same content the terminal report prints
   first, including any base-fetch degradation line (`SKILL.md`: a `$BASE_FETCH` other than
   `fetched` is surfaced *before* any finding is shown).
2. **Approved — POV `Fix`.** The `auto-include` set: findings whose POV recommends fixing.
   Per finding: severity tag, `file:line`, title, body, and the POV line.
3. **Undecided — needs a human call.** The `ask-set` (POV `Skip` or `Defer`), listed **in full**
   — severity tag, `file:line`, the finding text, the suggested fix, and the POV line — under that
   heading, verbatim.
4. **A count summary that states the two sets separately** — e.g.
   `"3 Critical, 5 Important approved; 2 Important, 4 Minor undecided"`. One number covering both
   would read as a decision that was never made.

**The undecided set is neither approved nor dropped.** A review run has no authority to answer
its own review gate: approving the `ask-set` would ship findings the POV recommended skipping,
and dropping it would bury findings a human might have kept. Recording either as an outcome is
a claim without a receipt. They stay undecided, in writing, for the human who reads the
artifact.

## After the artifact

Print the artifact's path and the same terminal report (the approved set, grouped by severity,
verdict label in bold), then state in one line that the `ask-set` went undecided because no
human answered the review gate.

**Record no `decisions.py` entries on this path.** The learning loop learns from decisions a
human made; a gate nobody answered produced none, and writing `skip` or `fix` records for the
undecided set would teach the profile from a silence.

Of the three end-of-run steps in `SKILL.md` § Learning Loop & Staleness Nudge, run **only the
staleness nudge** — it is a print, and it blocks nothing. The **learning-loop proposal** and the
**provisional-profile confirmation** are not run — the learning loop learns from decisions a
human made, and a gate nobody answered produced none.

## Scope

This path is `--review-only`'s, and `--review-only` is now the only read-only path — `--post`,
which posted to GitHub and kept its own `AskUserQuestion` review-event gate, was removed (#1121).
The presentation answers nothing on the owner's behalf: it writes findings down instead of
asking, and selects nothing.
