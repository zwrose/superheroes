# Charter eval suite

A `claude plugin eval` suite that checks whether the superheroes charters still produce their key
behaviors: the workhorse, showrunner and detective duties, one covenant rule, and one routing
over-trigger check. It was built to compare the charters before and after a restructure. Each case
grades what the agent **does** (stops, refuses, writes the right shape, never calls a forbidden
tool), never which page it read.

The older `eval/` directory is a separate harness; this suite does not touch it.

## Layout

- `<case>/prompt.md`: the scenario. Its frontmatter pins the agent model (`claude-opus-5-5`), 3 runs,
  the turn cap and the granted tools. The prompt opens with the charter's slash command, and it
  carries every fixture inline: runs start in an empty directory with no GitHub, network or shell.
- `<case>/graders/*.md`: the scored checks, each with PASS and FAIL stated in outcome terms.
- Graders named `diag-*` are diagnostics: "did it open page X". The tool refuses a weight of 0, so
  they carry weight 0.001. **Pass counts ignore them**, and `summary.jq` reports them separately.
  The tool's own pass rate does count them, so read pass counts from `summary.jq`, not the report.
- `summary.jq`: prints, per case and arm, the pass count (outcome graders only; a run that errored
  or was never graded never counts), the cost, the diagnostic hit count and the failing graders.
- `results/`: run output. It is gitignored.

## Running it

Checked on Claude Code 2.1.281. Three tool facts shape every command:

1. **Run against an export, never the checkout.** The tool refuses a plugin inside a git checkout
   with many linked worktrees ("registers more linked worktrees than can be screened"). Export the
   plugin with `git archive` instead; that also pins the run to an exact commit.
2. **Grant Write and Edit.** Some cases write their answer to a file, and some check that no Write
   or Edit happened. That needs the operator grant `--allow-tools Write Edit`. Writes stay inside
   the run's own sandboxed directory.
3. **Pin the judge.** `--judge-model` is a command-line option only.

Set these once. `SUITE` is the commit holding this suite; `TARGET` is the commit under test.
`CLAUDE_CONFIG_DIR` is the account the runs bill to.

```bash
REPO=/path/to/superheroes            # any checkout of the repository
SUITE=<commit with plugins/superheroes/evals>
TARGET=<commit under test>           # main for the baseline, the stack head, or one layer's head
DIR=$(mktemp -d)
git -C "$REPO" archive "$TARGET" plugins/superheroes | tar -x -C "$DIR"
rm -rf "$DIR/plugins/superheroes/evals"   # drop any copy the target carries
git -C "$REPO" archive "$SUITE" plugins/superheroes/evals | tar -x -C "$DIR"
cd "$DIR/plugins/superheroes"
FLAGS=(--trust-plugin --no-publish --allow-tools Write Edit
       --judge-model claude-haiku-4-5-20251001 --max-cost-usd 60 -j 4)
```

**Full run (the baseline, or the stack head):** version against version, no no-plugin arm.

```bash
CLAUDE_CONFIG_DIR=~/.claude-four claude plugin eval . --ablation none --runs 3 \
  "${FLAGS[@]}" --json run.json
jq -r -f evals/summary.jq run.json
```

**Finding the layer (one case per layer):** when a case regresses at the stack head, export each
layer's head as `TARGET` in turn and run only that case.

```bash
CLAUDE_CONFIG_DIR=~/.claude-four claude plugin eval . --case w2-size-tripwire --ablation none \
  --runs 3 "${FLAGS[@]}" --json w2.json
jq -r -f evals/summary.jq w2.json
```

**The no-plugin check (bite-proof):** `--ablation with-without --runs 1` adds a run with no plugin
loaded. A case that passes without the plugin is not testing the plugin. R8 is the known exception:
with no plugin, no superheroes skill can fire, so it passes by construction.

## Reading the result

- **Regression:** a case at 3/3 on the baseline that reads 0/3 or 1/3 on a head. A 2/3 gets one
  re-run before it counts.
- A case that fails on the baseline is a finding about the baseline, not a gate.
- Cost per run is in the summary; it is a rough cross-check on startup context, not a measurement.
