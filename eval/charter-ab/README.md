# Charter A/B eval

## The question it answers

When a charter changes, does the seat that reads it still behave the same way? The eval gives fresh
headless seats a set of situations, once with the charter as it was (BASE) and once as it would be
(CANDIDATE), and a blind judge scores each answer against the rule the situation is meant to trigger.
It reports PASS only if the candidate did not lose ground on any scenario.

## When to run it

Before merging a change that moves or deletes charter text. The advisor runs it at vets of
charter-moving changes. A change that only adds text, or touches nothing a seat reads, does not need it.

## What it needs

- the `claude` and `codex` CLIs, both logged in;
- `CLAUDE_CONFIG_DIR` exported (seats and runs refuse without it; there is no default);
- live model access. It is not wired into CI.

Each seat loads the plugin from its own side's worktree, through `--plugin-dir <worktree>/<plugin dir>`. The
plugin dir is the nearest directory above the charter that holds `.claude-plugin/plugin.json` (for the default
charter, `plugins/superheroes`), found once per run in the `--repo` checkout and kept in `sides.json`. So the
reference files a charter points at resolve to the commit under test, not to the plugin installed in
`CLAUDE_CONFIG_DIR`. If the charter has no plugin above it, no flag is passed. A side whose commit lacks the
manifest is refused.

## What it costs

For 15 scenarios at 3 replicates: about 90 seat calls (15 x 2 sides x 3) and 15 judge calls, roughly
10 to 15 minutes of wall time. There is no cost guard on charter size.

## Commands

All of it, with BASE and CANDIDATE as git refs (a branch, tag or SHA):

    export CLAUDE_CONFIG_DIR=~/.claude
    python3 eval/charter-ab/ab.py run --base 06269f3d --candidate 0435146d --run-dir /tmp/ab-1883

Without `--base`, BASE is the merge-base of `main` (else `origin/main`) and the candidate. The run dir
must be outside the repo. The eval makes two throwaway worktrees for the seats and removes them
afterwards; it never touches your checkout.

Stage by stage (each resumes; finished outputs are kept unless `--force`):

    python3 eval/charter-ab/ab.py seats  --base 06269f3d --candidate 0435146d --run-dir /tmp/ab-1883
    python3 eval/charter-ab/ab.py judge  --run-dir /tmp/ab-1883
    python3 eval/charter-ab/ab.py report --run-dir /tmp/ab-1883

The first stage on a run dir writes `sides.json`, the run identity (both commit SHAs, charter, scenarios
hash, models, replicates, seed). Later stages are refused if they disagree with it, so answers from two
different setups can never be mixed. Other options: `--model`, `--judge-model`, `--replicates`,
`--jobs` (max 4), `--judge-jobs`, `--seed`, `--repo`.

## How to read the verdict

The exit code is 0 for PASS, 1 for FAIL, 2 for INCOMPLETE, 3 for a refusal. `results.md` and
`verdict.json` are written to the run dir.

- **PASS**: on every scenario the candidate is right at least as often as BASE minus 1 (out of the
  replicates), and no scenario has the candidate wrong in 2 or more replicates while BASE is right in 2
  or more.
- **FAIL**: some scenario breaks either test; the report lists each one with its reason.
- **INCOMPLETE**: no verdict. Some scenario is missing answers, the judge output did not parse, or the
  judge output was made over different answers than the current ones (checked by prompt hash). There is
  never a PASS on zero scenarios. Re-run the same command to resume.
- **Both-wrong list**: scenarios where BASE and the candidate were both wrong every time. That is a gap
  in the charter, not an effect of the change; it does not fail the run.
- **Material-difference column**: the judge's view of whether the two sides act differently. It is
  informational and does not enter the verdict.

## Writing scenarios for another charter

Pass `--charter <repo-relative path>` and `--scenarios <file>`. The file is a JSON object
`{"role": "...", "scenarios": [...]}` (a bare list also works, with a generic role). The role fills "You
are {role} for this repository". Each scenario has `id` (unique), `situation`, `question`,
`expected_rule` and `targeted_block`; `control: true` marks a scenario on text the change does not touch.
Take `expected_rule` from the BASE text, so the key does not favour the candidate. The charter must exist
on both sides.

## Scoring keys

A scoring key changed after a run's answers were seen must be disclosed in the results. Set `key_change`
on the scenario (a sentence on what changed and why) and keep the old key as `expected_rule_v1`; the
report lists every `key_change` in its scoring-key section. The C11 run did this.

## Where results go

The run dir is outside the repo (a fresh temp dir if `--run-dir` is omitted; the path is printed). To
record a run, copy its `results.md` into `results/` under a dated name and add a line to
`results/README.md`. The two C11 files there came from the seed version of the eval.
