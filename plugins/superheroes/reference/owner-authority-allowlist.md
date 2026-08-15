# Contents

1. [What this is](#what-this-is)
2. [Where the file goes](#where-the-file-goes)
3. [The schema (v1)](#the-schema-v1)
4. [Schema v2 — ref-carrying dispatches](#schema-v2--ref-carrying-dispatches)
5. [Worked example](#worked-example)
6. [What can never be allowlisted](#what-can-never-be-allowlisted)
7. [When the file is wrong](#when-the-file-is-wrong)
8. [Limitations](#limitations)

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

- `schemaVersion` — must be `1` or `2`; any other value is ignored (gate behaves as if no file exists).
- `allow` — list of entries. In v1 each entry has `action` (`run-workflow` only) and `workflow`
  (exact name or id as typed on the command line; case-sensitive; no wildcards, globs, or
  `.yml`/display-name equivalence).

## Schema v2 — ref-carrying dispatches

Use `schemaVersion: 2` when you need to pre-authorize a dispatch that names a ref (`-r` /
`--ref`). Add `ref: "any"` to opt in — the only supported value:

```json
{
  "schemaVersion": 2,
  "allow": [
    { "action": "run-workflow", "workflow": "Preview seed", "ref": "any" }
  ]
}
```

Grant `ref: "any"` only for a workflow whose definition you are willing to have run from any
branch of this repository.

**Threat model:** granting `ref: "any"` on a workflow means **any ref's definition of that
workflow may run** — not just the default branch. For a seed workflow whose design is that the
dispatched ref *is* the target (no branch input), this is precisely what you want. Ref *patterns*
(`feat/*`) are deliberately not supported in this shape.

A v2 entry with `ref: "any"` also covers the bare dispatch (no ref flag) — a superset grant
includes the default ref. Entries without a `ref` key behave identically under both schema versions.

Under `schemaVersion: 1`, a `ref` key on any entry is **dropped** — the note is printed to
stderr, not promoted into the approval prompt, and the entry does not apply (you see an extra
prompt, not an unapproved run). Bump to `schemaVersion: 2` if you need ref support. An invalid
`ref` value under v2 is dropped the same way — stderr notice only, entry ignored.

**Rollback:** bumping the file to `schemaVersion: 2` means an older superheroes install
rejects the **entire** file (its check is `ver != 1`), so every entry — including plain bare-name
grants that would otherwise still work — stops applying and the gate asks for everything. That
direction is correct (fail closed). Keep v1 if you may roll back to an older plugin, and expect
extra prompts rather than unapproved runs if you bump to 2 and then roll back.

## Worked example

Workflow named `Preview seed` — write the JSON above, then this runs without prompting:

```bash
gh workflow run "Preview seed"
```

**Branch-preview seeding** (requires v2 with `ref: "any"`):

```bash
gh workflow run "Preview seed" --ref my-feature-branch
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

Those actions can never be allowlisted **directly**. A `ref: "any"` grant can still reach them
**indirectly** — GitHub runs the workflow file as it exists on the named ref, and a workflow step
on an ungated branch can perform actions the gate lists as never allowlistable (for example, a
step that merges a pull request). **As the owner, treat `ref: "any"` as authorizing whatever CI
code exists under that workflow name on any branch, with `GITHUB_TOKEN`.**

Also not allowlistable: `push-to-default` (ignored with a quieter note); `gh workflow enable`
and `gh workflow disable` (only `run` can be pre-authorized).

## When the file is wrong

Missing, unreadable, malformed, or wrong-schema file **changes nothing** — the gate asks as today.
The allowlist is read only when calibration is positively known; an indeterminate probe (corrupt or
unreadable registry) → gate asks, file not read. **Promise:** nothing in this file can widen silence
beyond a workflow you named by hand — the workflow **name** is still pinned by hand, but with
`ref: "any"` the **content** that name runs is not (see the limitations below for what the name
pins and what it does not: inputs, environment overrides, ref-selected workflow definitions).

## Limitations

- Hand-edited only; exact names only; **Claude Code only** (Codex hook config has no PreToolUse
  entry).
- An entry pre-authorizes the **workflow**, not its **inputs** — if the workflow's inputs can
  change what it checks out or runs, pre-authorizing it pre-authorizes all of those.
- The gate matches on the **text of the command** and cannot see the environment it will run in.
  If `GH_REPO` (or another `gh` environment override) is set in the session, a pre-authorized
  dispatch may target a **different repository** than the one whose allow file authorized it. Do
  not pre-authorize a workflow in a session or project where `GH_REPO` is set.
- **Supported workflow-name characters:** the whole command must use only `A-Z a-z 0-9`, space, and
  `_ - . / : = , ' " @ +`. Any other character anywhere — `$`, backtick, `*`, `?`, `[`, `]`, `{`,
  `}`, `~`, `\`, `;`, `&`, `|`, `<`, `>` — means the gate asks. A name the shell could expand or
  glob cannot be matched honestly, so the mechanism refuses rather than guesses. **Consequence:**
  `Preview & seed` **cannot be pre-authorized** and will keep asking — an extra prompt, never
  an unapproved run.
- Also asks regardless of the file: compound commands, env-var prefixes, absolute `gh` path,
  unrecognized flags, `-R` / `--repo` (a dispatch naming another repository is not the dispatch
  you pre-authorized), or anything that does not name exactly one workflow. Ref flags (`-r` /
  `--ref`) ask **unless** a `schemaVersion: 2` entry with `ref: "any"` covers them.
- **Shell quoting:** owner ratification 2026-08-14 (#1000): the gate is a **best-effort text
  matcher over shell syntax** that **errs closed**; **no shell lexer will be built** and quoting
  semantics are **declined**, because skipping quoted text would choose fail-open in a security
  gate. Known silent-bypass shapes are **closed as they are found**; **over-matching is an
  accepted cost**. **Redirection is handled** for the operator spellings the code models — fd
  optional (`\d{0,9}`), then `>>`, `>`, `<<`, `<`, with optional `&` or `|` suffix (`2>&1`,
  `&>`, `>|`, `<&`, and similar) — and the operand is consumed when adjacent (`gh pr
  merge>/dev/null` asks; `gh 2>&1 pr merge 123` asks). Operators not in that set (`<<<`,
  `<>`, zero-padded file descriptors beyond the bounded fd) are **not** modelled. **Shell word
  terminators on gated words are handled** — a gated shell word ends at any shell word-terminator
  (whitespace, `)`, `(`, backtick, `"`, `'`, redirection characters, end-of-string) in
  subshell, command-substitution, paren, and `bash -c` wrappers (`\`gh pr merge\``,
  `bash -c "git push origin main"`, and `(gh release create)` classify correctly; #1000).
  **Payload identifiers** inside arguments (the `merge-api` REST path segment and the
  `merge-graphql` GraphQL field name) terminate on **any non-word character** — so
  `pulls/42/merge-async`, `pulls/42/merge.json`, and `.mergePullRequest.number` ask. **Still
  open by ratified decline:** a real shell lexer, quote **pairing**, and escape handling.
  **Over-match costs an extra prompt, never an unapproved run** — the fail direction is
  unchanged. **Accepted over-match (ratified 2026-08-14):** a command that merely **quotes or
  mentions** a gated phrase now asks — for example `git commit -m "fix the push to main"`,
  `echo "git push origin main"`, and `grep -r 'git push origin main' docs/`. That is the
  accepted cost of declining quote semantics. A commit message that does not put `push` and
  `main` as bare words in the same segment stays silent (e.g. `git commit -m 'merge main into
  feature'`). **The `+` refspec form is a force spelling** (owner-ruled 2026-08-15): a refspec
  word beginning with `+` — `git push origin +feature`, `+main`, `+refs/heads/main`,
  `+HEAD:main`, `+*:refs/review/*`, `+@{u}:refs/heads/x`, `++feature` (a branch literally named
  `+feature`), quoted or parenthesised, on any refspec position — asks as `force-push`, exactly
  as `--force` does. The `+` must start a word (never after `=`, `:`, `.`, `/`, `-` or a word
  character) and be followed by anything that is not whitespace or a separator, so
  `--push-option=+x`, `a+b`, a bare `+`, `HEAD:refs/heads/+feature` (a `+`-named branch),
  `./+repo` (a repository path) and `git pull origin +main` are not force. **Accepted
  over-matches — they ask, one prompt, never an unapproved run:** a redirection to a file whose
  name begins with `+` (`2>+log`), the separate-argument push option (`-o +x`, `--push-option
  +x`), a repository operand named `+…` (`git push +repo feature`), and a quoted inline option
  value (`--push-option="+x"`) — telling those apart from a refspec would need option parsing,
  which the ratified posture declines.
  **Known-open specimens still silent today:** a **quote-concatenated command word**
  (`g''h pr merge 123`, `gi''t push --force origin f`), a **separator inside a quoted value**
  (`git -c user.name="x;y" push --force`, `git -c user.name="x|y" push --force`), a
  **zero-padded file descriptor** (`gh pr 0000000001>&1 merge 123`), a **composite `<>` operator
  with a spaced operand** (`gh pr <> /dev/null merge 123`), and a **here-string `<<<` operator**
  (`gh pr <<< foo merge 123`).
