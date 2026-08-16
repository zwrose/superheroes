# Contents

- [What this check is](#what-this-check-is)
- [The invocation](#the-invocation)
- [The result contract](#the-result-contract)
- [Vocabulary (drift-tested)](#vocabulary-drift-tested)
- [The three invocation points](#the-three-invocation-points)
- [What this check does not do](#what-this-check-does-not-do)

# Register-quote exact-text check

## What this check is

This file is the one home for the **register-quote exact-text check** — the machine comparison
that proves a child issue body quotes its register entries byte-exactly and carries every entry
whose `*Consumers:*` line names that child. The check runs at child filing, child build intake,
and an epic package read's verification pass. **Register-to-child text agreement is machine
work, never model judgment** — the script reports pass, fail, or undecided; the charters decide
what to do with the result.

## The invocation

The stable invocation (from a plugin-cache install, `ROOT_DIR` is
`${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT}}"
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register <path to the register .md> \
  --body-file <path to the consumer body .md> \
  --child <token> \
  [--allow-no-required-entries]
```

**Epic child** — the child's body quotes blocks from its epic's register; pass the epic register
path and the child token from that entry's `*Consumers:*` line (for example `C9`):

```bash
gh issue view <n> --json body -q .body > body.md
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register docs/superheroes/<epic-slug>/register.md \
  --body-file body.md \
  --child C9
```

**Single-issue child** — the child's body stands in for a register under FR-36's shared-seam
rule; its quote header names an epic register. Pass that register path and the consumer token
from the quoted entry's `*Consumers:*` line (for example `the detective child` on R9):

```bash
gh issue view <n> --json body -q .body > body.md
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register docs/superheroes/<epic-slug>/register.md \
  --body-file body.md \
  --child "the detective child"
```

The caller reads the quote header in the body and supplies `--register`; the script never
resolves register paths from prose.

## The result contract

The script prints **exactly one JSON object on stdout**, always, with every key present:
`schema`, `result`, `ok`, `reason`, `detail`, `child`, `register`, `body`, `registerEntries`,
`requiredEntries`, `quotedEntries`, `duplicateQuoteIds`, `entriesWithoutConsumers`, `findings`,
`firstDifference`. `ok` is true only on `pass`. `reason` is null except on `undecided`.
`firstDifference` is the first `text-drift` finding, else null.

**Results:**

| Result | Exit code | Meaning |
| --- | --- | --- |
| `pass` | 0 | Every required quote matches byte-exactly and every quoted block matches its register entry |
| `fail` | 1 | At least one drifted or missing required quote |
| `undecided` | 2 | The check could not run to a pass/fail verdict |

A finding object carries `kind`, `entry`, `line`, `column`, `expected`, `actual`, and `detail`.
For `text-drift`, `line` is 1-based **within the quoted block** and `column` is the 1-based
first differing character — the pass/fail result names the first differing line.

**Worked `text-drift` example** (excerpt):

```json
{
  "schema": "register-check/1",
  "result": "fail",
  "ok": false,
  "reason": null,
  "firstDifference": {
    "kind": "text-drift",
    "entry": "R3",
    "line": 2,
    "column": 41,
    "expected": "machine work (a script with a stable invocation",
    "actual": "machine work — a script with a stable invocation",
    "detail": "R3: first differing line 2, column 41"
  },
  "findings": [
    {
      "kind": "text-drift",
      "entry": "R3",
      "line": 2,
      "column": 41,
      "expected": "machine work (a script with a stable invocation",
      "actual": "machine work — a script with a stable invocation",
      "detail": "R3: first differing line 2, column 41"
    }
  ]
}
```

Line 2, column 41 is the first character where the quoted block in the body diverges from the
register entry on disk.

**Both directions:** every quoted block must match byte-exactly, **and** every register entry
whose `*Consumers:*` line names the child must appear quoted in that child's body — a missing
required quote fails the same as a drifted one.

Per CONVENTIONS §13, this validator has named charter consumers and a ledger row; unlike the
advisory issue-contract check, its exit codes are load-bearing for the charters that call it.

## Vocabulary (drift-tested)

The Python module `register_check.py` is the authoritative home for these tokens; this list is
checked against it by `lib/tests/test_ssot_drift.py` per CONVENTIONS §11.2.

**Schema:**

- `register-check/1`

**Results:**

- `pass`
- `fail`
- `undecided`

**Finding kinds:**

- `text-drift`
- `missing-quote`
- `unknown-entry`

**Undecided reasons:**

- `register-unreadable`
- `body-unreadable`
- `register-empty`
- `register-malformed`
- `child-unrecognized`
- `usage`
- `internal-error`

**Exit codes:**

- `0` — pass
- `1` — fail
- `2` — undecided

## The three invocation points

**Child filing (showrunner duty 2).** When the advisor files an issue that quotes register text,
run the check against the body **before filing**. On `fail`, fix the body — do not file a drifted
quote. On `undecided`, treat as a filing blocker until the inputs are readable and the child
token is recognized. See the showrunner charter's board-hygiene duty for the filing obligation.

**Child build intake (workhorse §1).** When the routed issue's body quotes register text, run the
check at intake before the brief. On `fail`, **park** — the quoted text is the contract the build
is graded on, so a drifted quote is not a buildable surface. See the workhorse charter's intake
section for the park obligation.

**Package-read verification pass (showrunner duty 3).** At an epic package read's verification
pass, re-run the check per child across **both** directions. On `fail`, record a blocking
package-read finding and do not treat the package as verified. See the showrunner charter's
size/decompose/route duty for the verification obligation.

## What this check does not do

- **Register path resolution** — the caller reads the quote header and passes `--register`. That
  keeps the script call-site-agnostic.
- **Issue fetch** — the caller supplies a body file (for example
  `gh issue view <n> --json body -q .body > body.md`). The script never reaches the network.
- **Writes** — it never edits or writes a file.
- **Entries without consumers** — a register entry with no `*Consumers:*` line is reported in
  `entriesWithoutConsumers` and is never required. An entry naming no consumer is FR-28's
  package-read finding, not this check's.
- **Duplicate quotes** — a duplicate quote of one entry is reported in `duplicateQuoteIds` and is
  not, by itself, a failure.
- **Semantic judgment** — it checks **text agreement only**. Whether the quoted entry is the
  *right* entry to consume, and whether the register itself is correct, stay model and advisor
  judgment.

**Declared normalization — line terminators.** Comparison is byte-exact **modulo the line
terminator**: files are read without universal-newline translation and a trailing `\r` is not
compared, because GitHub returns issue bodies CRLF while the register on disk is LF. Trailing
spaces, tabs, and every other interior byte **are** compared. This is a disclosed normalization,
not a hidden one.
