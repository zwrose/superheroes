# Contents

- [The spec checks](#the-spec-checks)
- [The three checks](#the-three-checks)
- [The spec-reviewer seat](#the-spec-reviewer-seat)
- [Grounding against the default branch](#grounding-against-the-default-branch)
- [The same reviewer across rounds](#the-same-reviewer-across-rounds)
- [Running a round](#running-a-round)
- [What a reviewer may do](#what-a-reviewer-may-do)
- [Sorting findings into three piles](#sorting-findings-into-three-piles)
- [Rounds, and when they stop](#rounds-and-when-they-stop)
- [The running record](#the-running-record)
- [The reviewer's prompt](#the-reviewers-prompt)

# The spec checks

When a spec is written, three checks run on it in parallel: gap review, the source check, and
grounding. The source check runs in both directions. Discovery runs the checks and follows this
doc. No other surface restates these rules.

The checks run again after each set of owner rulings (see [Rounds, and when they
stop](#rounds-and-when-they-stop)). The existing citation check runs beside grounding every round.

## The three checks

Gap review reads the spec for clarity, testability, contradictions between statements, and safety
and access. It also reads for missing unhappy paths within the project's threat model. The threat
model is configure's threat-model item. An unhappy path outside it is not a gap.

The source check runs both ways.

- Forward. Every statement in the spec has a source and matches it, and the approved board is the
  first source to look in. Nothing in the spec belongs to another piece of work.
- Backward. Every ruling for this piece is in the spec and written down right. So is every element
  of the approved board that belongs to this piece, and so is the framing.

The source check is an agent reading plain files. No script reads a source tag.

Grounding checks every claim the spec makes about the product or the repository. It checks each
claim against the project's current default branch. It never checks against the session's own
branch, which may be stale.

The citation check runs beside grounding every round.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/citation_validator.py" check --spec <spec> --root <root>
```

`<root>` is the grounding base (see [Grounding against the default
branch](#grounding-against-the-default-branch)). The command prints JSON findings. Put the output
in that round's record, including an empty `[]`. When no grounding base could be built that round,
run the check with `--root` set to the repository root, and write in the record that it ran without
a grounding base.

## The spec-reviewer seat

Resolve the seat once, at round 1. The author engine is the engine your own session runs on:
`claude` on Claude Code, `codex` on Codex, `cursor` on Cursor.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/core_md.py" spec-reviewer-seat --cwd . --author-engine <engine>
```

The verb is read-only. It prints one JSON object and exits 0. The keys you need are these.

- `engine`, `model`, and `effort`. The seat's engine, and the model and effort it runs with.
- `family`, and `authorFamily` for the author engine you passed.
- `sameFamily`. True when the two families are equal.
- `source`: `configured`, `cross-family-installed`, or `same-family-fallback`.
- `configuredState`: `unset`, `valid`, `invalid`, or `unreadable`. `configuredReason` says why a
  configured seat was not used, or is null.
- `seat`. The bundle you pass to `--seat` on every dispatch.

The verb applies this rule. A configured seat is configure's spec-reviewer seat, which names an
engine and no model. The verb uses it when it is a different model family from the author's and is
installed. Otherwise it takes an installed engine of a different family. Only when none is
installed does it take the same-family path, and only when the author's own engine is still
installed. Claude counts as always installed, until you exclude it. When no usable engine remains,
the verb prints `"ok": false` with `"reason": "no-usable-reviewer"` and none of the seat keys; stop
and tell the owner no reviewer can run. The model and the
effort come from the plugin's model registry. This doc never names them.

All three checks use that one seat. Each check is its own dispatch.

### The same-family path

When `sameFamily` is true, a fresh reviewer from the author's own family runs the checks. Fresh
means a new context that never saw the conversation that wrote the spec. Write the fact in the
running record's header. The owner's final sheet says so plainly. Every other rule in this doc
applies on this path unchanged.

## Grounding against the default branch

Build a fresh grounding base every round. The base is a detached worktree at the tip of the
default branch. The command fetches the branch first.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/definition_doc.py" grounding-base --root . --dest <a new directory outside the repository>
```

On success the command prints `{"ok": true, "ref": ..., "sha": ..., "path": ...}`. Dispatch the
grounding check with `path` as `--repo-root`. The reviewer's view of the repository is then the
default branch. The spec itself travels in the prompt. Record the base's `ref` and `sha` in the
round.

On a refusal the command prints `{"ok": false, "reason": ..., "detail": ...}`, exits 1, and creates
nothing. The reason is one of `grounding-base-not-a-repo`, `grounding-base-no-origin`,
`grounding-base-default-unknown`, `grounding-base-fetch-failed`, `grounding-base-dest-exists`,
`grounding-base-dest-inside-repo`, or `grounding-base-worktree-failed`.

A refusal has no fallback. Never ground against the session's own branch. Grounding is not run that
round, the record says why, and grounding cannot count as clean. Fix the cause and retry when it is
fixable. A remedy named in `detail` is fixable, and so is a clashing directory.

After the round, release the worktree with the plain command. Never add `--force`.

```bash
git -C <repo> worktree remove <path>
```

## The same reviewer across rounds

Each check keeps the same reviewer across rounds. The seat you resolved at round 1 is reused
unchanged, with the same engine, model, and effort.

From round 2, each check's prompt hands that check three things: its own previous findings
verbatim, your disposition of each one, and the spec's diff since the reviewer last read it.

The reviewer's first task is to confirm last round's fixes and answer each decline. Only then does
it look for new problems. The confirmation vocabulary is in [The reviewer's
prompt](#the-reviewers-prompt).

When the seat's engine can no longer run, resolve a new seat with the same verb, passing
`--exclude-engine <the engine that stopped running>` (repeat the flag for each engine that has
failed). Note on the record
that the reviewer changed and why. Hand the new reviewer the previous round anyway, and ask it for
the confirmations.

## Running a round

1. Stage each check's input from the template in [The reviewer's prompt](#the-reviewers-prompt)
   plus the inputs below. Write one prompt file per check.
2. Give each check its own run directory for the round, outside the repository.
3. Dispatch the three checks concurrently, and re-invoke each until its result is terminal.
4. Run the citation check and record its output.

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/engine_dispatch.py" dispatch-review \
  --mode brief-check --expected-result-kind findings \
  --seat '<seat>' --prompt-path <prompt> --repo-root <root> \
  --run-dir <dir> --max-wait <slice>
```

Launch with a short slice, such as 60 seconds. Then run the same command again on the same run
directory, with a slice of up to 540 seconds, until the result is terminal. `--repo-root` is the
repository for gap review and the source check. For grounding it is the grounding base.

### The source check's inputs

Stage each of these into the source check's prompt, with a label on each: the spec, Canon, the
approved board's files, the framing brief, and the rulings for this piece.

Read Canon as `rubric/canon-contract.md` § "Reading Canon" says. Stage the default-branch copy and
this branch's copy, and label each copy with the sessions it binds. That section holds the
procedure, so follow it there.

When a required input cannot be read, the source check is not run that round. Put the reason in the
record.

### A result counts only when it is real

A result is real when it is terminal, `ok` is true, `attempts` is at least 1, and its engagement
read is `engaged`. Exit status zero alone is not evidence.

Re-dispatch a result that falls short, once. When the re-dispatch also falls short, that check is
not run this round, and the record says why. A check that did not run is never clean.

## What a reviewer may do

A reviewer finds problems. It never adds product behaviour.

When the only fix for a finding would add behaviour, the reviewer marks it with the `adds-behaviour`
tag from [The reviewer's prompt](#the-reviewers-prompt). Discovery queues the finding for the
owner with a recommendation. Weigh the recommendation on its merits and the project's context.
A recommendation is not biased toward cutting: keeping, cutting and changing the behaviour are
weighed the same way.

A fix that changes no behaviour is craft. Wording, consistency, and a missing acceptance criterion
for a behaviour already decided are all craft.

## Sorting findings into three piles

Sort every finding into exactly one pile, and write the pile in the record.

Craft. You fix it in the spec. A standing ruling in Canon, or a call the owner ceded, that already
answers the finding makes it craft.

The owner's. You leave it unfixed and queue it for the owner, each item with a recommendation.
Three kinds of finding belong here.

- A fix that would add behaviour.
- A product decision the spec states with no source.
- Two rulings that conflict. Show them side by side.

Declined. A decline is allowed for one of five reasons, and each reason cites its proof.

- The finding is wrong. Cite the spec line that shows it.
- The finding is outside the threat model. Cite the threat-model entry.
- The finding asks for implementation.
- The finding belongs to another spec. Name that spec.
- The finding duplicates an item already queued. Name the item.

A decline with no proof is not allowed. Sort that finding into another pile.

### A contested decline

The next round hands the decline back to the same reviewer, with its reason and proof. When the
reviewer still contests it, the finding joins the owner's queue marked `contested`, with both
sides. Keep every decline on the record. The final sheet lists them folded away.

## Rounds, and when they stop

Rounds run without asking the owner. They stop when all three checks are clean apart from items
already in the owner's queue, or after round 4, whichever comes first.

A check is clean in a round when its result is real, it confirmed every previous fix and accepted
every decline, and it raised no new finding that is not already queued.

After round 4, every finding still open joins the owner's queue. That includes a fix round 4 could
not confirm and a check that was not run. Mark each one "the review didn't settle this".

### After rulings

After each set of owner rulings, the checks run again on the parts that changed. They get up to four
rounds of their own and the same stopping rule. Each check's prompt carries the diff between the
spec before and after the rulings. The reviewer reviews only those parts, and reads whatever
surrounding text it needs to judge them. The same reviewers continue.

## The running record

Keep one running record per spec. It is a plain markdown file named `checks-record.md`, in the
spec's work-item folder beside `spec.md`. `definition_doc.py dir --work-item <slug>` prints that
folder, and the folder follows the project's definition-doc policy. You write the record as each
round closes. No script reads or validates it. Another session can pick it up from disk.

Copy this skeleton and fill it in. Add one section per cycle, which is the first review and then
"after rulings 1", "after rulings 2", and so on. Add one subsection per round. Repeat the per-check
block for each of the three checks.

```markdown
# Spec checks record

- Work item: <slug>
- Author engine and family: <engine>, <family>
- Seat: <engine>, <model>, <effort>, <family>
- Same family: <yes or no>
  When yes, the final sheet states: "The reviewer is from the same model family as the author. It
  is a fresh reviewer that never saw the conversation that wrote the spec."

## The first review

### Round 1

#### <Check name>
- Run directory: <path>
- Result: <real, or not run and why>
- Grounding base, for grounding: <ref>, <sha>
- Confirmations: <previous finding id> -> <fixed, not-fixed, fix-introduced-problem,
  decline-accepted, or decline-contested>

| id | check | finding | pile | recommendation, or decline reason and proof | status |
| --- | --- | --- | --- | --- | --- |
| <id> | <check> | <finding> | <craft, owner's, or declined> | <text> | <status> |

#### Citation check
<the JSON output, including [], and whether it ran without a grounding base>

## After rulings 1

<the same round layout>

## The owner's queue

- <id>: <finding>. Recommendation: <text>. Marks: <contested, or "the review didn't settle this">
```

Discovery builds each remainder sheet's items and its "why only these" facts from this record. It
builds the final sheet's history and folded declines from it too.

## The reviewer's prompt

The seat's working directory is a sanitized copy of the repository. In a consuming project that
copy does not contain this plugin. So copy the template below verbatim into each prompt file, and do
not point the reviewer at this doc. Fill the `<like this>` placeholders. Keep the one lens paragraph
for the check being run. Keep the continuation paragraph from round 2 on, and delete it in round 1.
Keep the after-rulings paragraph only in a re-run after owner rulings, where the continuation
paragraph is kept too, and delete it otherwise.

```text
You are reviewing a requirements spec. A requirements spec says what the product does, in plain
language, and holds no technical how. You find problems. You never add product behaviour. Ground
every claim by reading files in your working directory. Report findings only.

The spec is at <spec path>. Its text: <the spec text>

Your lens for this check:

Gap review. Read the spec for clarity, testability, missing unhappy paths, contradictions between
statements, and safety and access. An unhappy path counts as missing only when it is inside the
project's threat model: <the threat-model entries>.

Source check. Read the spec against its sources, which follow, each labelled. Forward: every
statement in the spec must have a source and match it, the approved board first, and nothing in the
spec may belong to another piece of work. Backward: every ruling for this piece, every element of
the approved board that belongs to this piece, and the framing must be in the spec and written down
right. Sources: <the labelled inputs>

Grounding. Check every claim the spec makes about the product or the repository against the
repository in your working directory. That repository is the project's default branch. Report each
claim the files do not support.

Continuation, for rounds after the first. You reviewed this spec before. Below are your previous
findings, verbatim, each with the disposition the author gave it, and the diff of the spec since
you last read it. First confirm each fix and answer each decline. Only then look for new problems.
Previous findings and dispositions: <the findings, verbatim, with dispositions>
Spec diff since you last read it: <the diff>

After the owner's rulings, for a re-run on the changed parts. The owner has ruled since your last
round, and the spec diff above shows what changed. Review only the parts the diff changes, reading
the surrounding text you need to judge them. Do not raise new findings on text the diff leaves
unchanged.

Output rules. Return the findings object the dispatch asks for: {"findings": [...],
"investigated": [...]}. Never a bare list. The finding fields and the severity values are the ones
in the example block appended after this prompt; do not restate them.

- file is the spec path and line is the line in it. investigated lists the paths you actually read.
- dimension is one of Clarity, Verifiability, Failure-Mode, Coherence, Safety-access, Grounding.
- Confirmations come first in the list, one for each previous finding and each decline. Its id is
  the previous id. Its taxonomy is one of confirm:fixed, confirm:not-fixed,
  confirm:fix-introduced-problem, confirm:decline-accepted, confirm:decline-contested. Its severity
  is Nit for confirm:fixed and confirm:decline-accepted. Otherwise it is the previous finding's
  severity.
- New findings follow the confirmations. The taxonomy of a new finding names the check: gap,
  source:forward, source:backward, or grounding. When the only fix would add product behaviour, end
  the taxonomy with ;adds-behaviour.
- When you have no findings and owe no confirmations, "findings" is [] and "investigated" still
  lists what you read.
```
