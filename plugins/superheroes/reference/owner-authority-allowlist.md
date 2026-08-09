# Owner-authority workflow allowlist

If you arrived here from an approval prompt, you are in the right place. The gate asked because
`gh workflow run` is an owner-authority action on a superheroes-calibrated project.

## What this is

The owner-authority gate asks before merge, release, force-push, push-to-default, and workflow
commands on calibrated projects — the never-merge floor. The allow file can only narrow asking,
never widen silence by accident. If an unattended session keeps stalling on the **same** workflow dispatch you
have already decided is safe, pre-authorize that one workflow by exact name in a hand-edited allow
file. Everything else still asks.

## Where the file goes

Create `owner-authority-allow.json` in your project's superheroes store — the same owner-only
directory that holds `registry.json` and `doc-policy.json` (default root:
`~/.claude/superheroes/projects/<project-key>/`). **Find the directory by locating the folder that
already contains `registry.json` for this project** rather than hand-computing a key.

## The schema (v1)

Hand-edit only — no `configure` surface yet.

```json
{
  "schemaVersion": 1,
  "allow": [
    { "action": "run-workflow", "workflow": "Preview seed" }
  ]
}
```

- `schemaVersion` — must be `1`; any other value is ignored (gate behaves as if no file exists).
- `allow` — list of entries. In v1 each entry has `action` (`run-workflow` only) and `workflow`
  (exact name or id as typed on the command line; case-sensitive; no wildcards, globs, or
  `.yml`/display-name equivalence).

## Worked example

Workflow named `Preview seed` — write the JSON above, then this runs without prompting:

```bash
gh workflow run "Preview seed"
```

**Near-misses that still ask:**

```bash
gh workflow run "Preview Seed"    # different capitalization — not an exact match
git status && gh workflow run "Preview seed"    # compound command — asks regardless
```

## What can never be allowlisted

Structurally excluded in code — an entry naming one is **ignored**, with notice on stderr and in
the approval prompt: `merge-pr`, `merge-api`, `merge-graphql`, `release`, `force-push`. **Why:**
the gate is the never-merge floor; a config that could exempt a merge would be no gate.

Also not allowlistable in v1: `push-to-default` (ignored with a quieter note); `gh workflow enable`
and `gh workflow disable` (only `run` can be pre-authorized).

## When the file is wrong

Missing, unreadable, malformed, or wrong-schema file **changes nothing** — the gate asks as today.
The allowlist is read only when calibration is positively known; an indeterminate probe (corrupt or
unreadable registry) → gate asks, file not read. **Promise:** nothing in this file can make the
gate quieter except by exactly naming one workflow dispatch you intend to allow.

## Limitations in v1

- Hand-edited only; exact names only; **Claude Code only** (Codex hook config has no PreToolUse
  entry).
- **Supported workflow-name characters:** the whole command must use only `A-Z a-z 0-9`, space, and
  `_ - . / : = , ' " @ +`. Any other character anywhere — `$`, backtick, `*`, `?`, `[`, `]`, `{`,
  `}`, `~`, `\`, `;`, `&`, `|`, `<`, `>` — means the gate asks. A name the shell could expand or
  glob cannot be matched honestly, so the mechanism refuses rather than guesses. **Consequence:**
  `Preview & seed` **cannot be pre-authorized in v1** and will keep asking — an extra prompt, never
  an unapproved run.
- Also asks regardless of the file: compound commands, env-var prefixes, absolute `gh` path,
  unrecognized flags, `--ref` / `--repo` (a dispatch naming another repository or another ref is
  not the dispatch you pre-authorized), or anything that does not name exactly one workflow.
