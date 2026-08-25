<!-- headless-presentation — review-code -->

# Headless presentation — `--review-only` with no interactive channel

The `--review-only` tiered presentation in `SKILL.md` § Read-Only Path is the **interactive**
form: it resolves its review gate by asking. A run with no one to answer cannot take it — an
`AskUserQuestion` opened on a headless `claude -p` run never returns, so the review **stalls**
until its harness kills it, and every artifact the pass already produced is stranded behind a
question nobody will see. That is the failure this file disposes of. Field record: the #609
stage-2 build (PR #1130, follow-up 4) hit it live — a headless builder chose `--review-only`,
reached the presentation, stalled, and had to switch paths.

The disposition is a **degradation, not a refusal**: the run completes, and the presentation
becomes a durable prose artifact instead of a conversation. `--review-only` is the charter's
focused vet-escalation instrument and, since `--post` was removed (#1121), the only read-only
review path — refusing it headless would leave a headless caller with no read-only review at
all, while the degradation costs only the answers a headless run was never able to give.

## When this path is taken

Take it when `$INTERACTIVE` is **false**, and when this run's interactivity is **unknown**.

`$INTERACTIVE` is resolved once in `setup.md` § Setup resolution, before anything is
dispatched — the same flag `decide-location` already consumes.

**Unknown falls to this path deliberately, and the asymmetry is the whole reason:** a run
wrongly sent here still finishes, writes its artifact, and says what went undecided — the cost
is one round trip the owner could have answered live. A run wrongly sent to the interactive
presentation **stalls**, and the cost is the whole review. The cheap failure is the one that
falls open.

## What the headless path runs

Everything up to the review gate is **unchanged** — the same single pass under `round-1/`, the
same compaction recovery from `compiled.json` + `meta.json`, and the same **orchestrator POV**
formed per finding. Only the gate's resolution changes: it is written down instead of asked.

Open no `AskUserQuestion` on this path, for any purpose.

## The artifact

Write the presentation as plain prose to `$SESSION_DIR/round-1/presentation.md`, then exit
cleanly. Never a stall, and never a silent skip — an absent artifact is indistinguishable from
a review that never ran.

The artifact carries, in this order:

1. **The verdict banner and the one-line summary** — the same content the interactive path
   prints first, including any base-fetch degradation line (`SKILL.md`: a `$BASE_FETCH` other
   than `fetched` is surfaced *before* any finding is shown, on this path too).
2. **Approved — POV `Fix`.** The `auto-include` set: the findings the interactive path adds to
   the approved set without asking. Nothing about that set depends on a human, so it carries
   over exactly. Per finding: severity tag, `file:line`, title, body, and the POV line.
3. **Undecided — needs a human call.** The interactive path's `ask-set` (POV `Skip` or
   `Defer`), listed **in full** — severity tag, `file:line`, the finding text, the suggested
   fix, and the POV line — under that heading, verbatim.
4. **A count summary that states the two sets separately** — e.g.
   `"3 Critical, 5 Important approved; 2 Important, 4 Minor undecided (headless)"`. One number
   covering both would read as a decision that was never made.

**The undecided set is neither approved nor dropped.** A headless run has no authority to
answer its own review gate: approving the `ask-set` would ship findings the POV recommended
skipping, and dropping it would bury findings a human might have kept. Recording either as an
outcome is a claim without a receipt. They stay undecided, in writing, for the human who reads
the artifact.

## After the artifact

Print the artifact's path and the same terminal report the interactive path ends with (the
approved set, grouped by severity, verdict label in bold), then state in one line that the
`ask-set` went undecided because the run had no interactive channel.

**Record no `decisions.py` entries on this path.** The learning loop learns from decisions a
human made; a gate nobody answered produced none, and writing `skip` or `fix` records for the
undecided set would teach the profile from a silence.

Of the three end-of-run steps in `SKILL.md` § Learning Loop & Staleness Nudge, run **only the
staleness nudge** — it is a print, and it blocks nothing. The **learning-loop proposal** and
the **provisional-profile confirmation** are both `AskUserQuestion`-gated: skip both, exactly
as `reference/review-loop.md` already rules for the
provisional-profile confirmation. Running either here would reintroduce the stall this file
exists to remove, one step past the finish line.

## Scope

This path is `--review-only`'s, and `--review-only` is now the only read-only path — `--post`,
which posted to GitHub and kept its own `AskUserQuestion` review-event gate, was removed (#1121).
The degradation still answers nothing on the owner's behalf: it writes the presentation down
instead of asking, and selects nothing.
