# Contents

- [What this check is](#what-this-check-is)
- [The invocation](#the-invocation)
- [The result contract](#the-result-contract)
- [What counts as a quoted register block](#what-counts-as-a-quoted-register-block)
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

`--allow-no-required-entries` exists for the single legitimate case of a child that consumes
**no** register entry — it makes the required set legitimately empty. **None of the three
invocation points ever passes this flag.** At those points an unmatched `--child` is a
`child-unrecognized` `undecided`, which blocks per the gate below.

**Epic child** — a register-consuming epic child; pass the epic register path and the child
token from that entry's `*Consumers:*` line (for example `C9`):

```bash
BODY_FILE="$(mktemp "${TMPDIR:-/tmp}/register-check-body.XXXXXX")"
trap 'rm -f "$BODY_FILE"' EXIT
gh issue view <n> --json body -q .body >"$BODY_FILE" || { echo "issue body fetch failed" >&2; exit 1; }
[ -s "$BODY_FILE" ] || { echo "issue body fetch returned empty" >&2; exit 1; }
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register docs/superheroes/<epic-slug>/register.md \
  --body-file "$BODY_FILE" \
  --child C9
```

**Single-issue child** — a register-consuming child standing in for a register under FR-36's
shared-seam rule; its quote header names an epic register. Pass that register path and the
consumer token from the entry's `*Consumers:*` line (for example `the detective child` on R9):

```bash
BODY_FILE="$(mktemp "${TMPDIR:-/tmp}/register-check-body.XXXXXX")"
trap 'rm -f "$BODY_FILE"' EXIT
gh issue view <n> --json body -q .body >"$BODY_FILE" || { echo "issue body fetch failed" >&2; exit 1; }
[ -s "$BODY_FILE" ] || { echo "issue body fetch returned empty" >&2; exit 1; }
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register docs/superheroes/<epic-slug>/register.md \
  --body-file "$BODY_FILE" \
  --child "the detective child"
```

The caller reads the quote header in the body and supplies `--register`; the script never
resolves register paths from prose.

## The result contract

Every **`check`** invocation emits exactly one JSON object on stdout — including every failure
and every `undecided` path — with every key present; see **Result fields** in
[Vocabulary (drift-tested)](#vocabulary-drift-tested) for the authoritative field list.
`--help` prints usage and exits 0 without JSON. `ok` is true only on `pass`. `reason` is null
except on `undecided`. `firstDifference` is the first `text-drift` finding, else null.

**Results:**

| Result | Exit code | Meaning |
| --- | --- | --- |
| `pass` | 0 | Every required quote matches byte-exactly and every quoted block matches its register entry |
| `fail` | 1 | At least one `text-drift`, `missing-quote`, or `unknown-entry` finding |
| `undecided` | 2 | The check could not run to a pass/fail verdict |

A finding object carries the fields listed under **Finding fields** in
[Vocabulary (drift-tested)](#vocabulary-drift-tested). For `text-drift`, `line` is 1-based
**within the quoted block** and `column` is the 1-based first differing character — the
pass/fail result names the first differing line.

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

## What counts as a quoted register block

- the block is a markdown blockquote whose lines begin with `>` **at column 0**;
- one `>` plus **at most one** following space is stripped per line;
- the **first** stripped line must be the entry header `**R<n> — `;
- the block ends at the first line that does not begin with `>`, and **every** stripped line of the
  block is compared — an appended quoted paragraph is drift, not decoration;
- a blockquote inside a ``` or ~~~ **fence is ignored on purpose**, so an example quote inside a
  fenced code block never counts as a real one.

A register entry's **quotable text is a single paragraph** — the entry header line and the lines
immediately following it, up to the first blank line, italic metadata line, `---`, or heading.
Text after a blank line is trailer, not quotable.

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
- `register-malformed` — a `*Consumers:*` line before any entry header; a duplicate entry id; an
  entry with empty quotable text; multiple `*Consumers:*` lines in one entry's trailer; or an
  unterminated code fence in the register (reported at the fence **opener's** line number)
- `body-malformed` — an unterminated code fence in the consumer body (reported at the fence
  **opener's** line number)
- `child-unrecognized`
- `usage`
- `internal-error`

**Exit codes:**

- `0` — pass
- `1` — fail
- `2` — undecided

**Result fields:**

- `schema`
- `result`
- `ok`
- `reason`
- `detail`
- `child`
- `register`
- `body`
- `registerEntries`
- `requiredEntries`
- `quotedEntries`
- `duplicateQuoteIds`
- `entriesWithoutConsumers`
- `findings`
- `firstDifference`

**Finding fields:**

- `kind`
- `entry`
- `line`
- `column`
- `expected`
- `actual`
- `detail`

## The three invocation points

**Child filing (showrunner duty 2).** When the advisor files a **register-consuming child** — an
epic child of a package that has a register, or a single-issue child standing in for one under
FR-36 — run the check against the body **before filing**, whether or not the body contains a
quoted block; a body with zero quoted blocks is exactly the case the check is there to fail.
Where applicability cannot be derived from the issue alone, the route names the register and
child token at routing for the builder to pass. On `fail`, fix the body — do not file a drifted
quote. On `pass`, record the check's own output in the filing note — the `result` line, or `pass`
together with `requiredEntries` — not merely a claim that it ran. When whether the check applies
cannot be established here, run it anyway and let `undecided` block — never skip on unclear
applicability; that is the same fail-closed direction as **A non-zero exit blocks**. **A non-zero
exit blocks** filing — `undecided` blocks until the inputs are readable and the child token is
recognized, exactly like `fail`. See the showrunner charter's board-hygiene duty for the filing
obligation.

**Child build intake (workhorse §1).** When the routed issue is a **register-consuming child**,
run the check at intake before the brief, whether or not the body contains a quoted block. On
`fail`, **park** — the quoted text is the contract the build is graded on, so a drifted quote is
not a buildable surface. On `pass`, record the check's own output in the intake note — the
`result` line, or `pass` together with `requiredEntries` — not merely a claim that it ran. When
whether the check applies cannot be established here, run it anyway and let `undecided` block —
never skip on unclear applicability; that is the same fail-closed direction as **A non-zero exit
blocks**. **A non-zero exit blocks** the build — `undecided` is a **park**, exactly like `fail`.
See the workhorse charter's intake section for the park obligation.

**Package-read verification pass (showrunner duty 3).** At an epic package read's verification
pass, re-run the check per **register-consuming child** across **both** directions, whether or
not each body contains a quoted block. On `fail`, record a blocking package-read finding and do
not treat the package as verified. On `pass`, record the check's own output in the package-read
verification record — the `result` line, or `pass` together with `requiredEntries` — not merely a
claim that it ran. When whether the check applies cannot be established here, run it anyway and
let `undecided` block — never skip on unclear applicability; that is the same fail-closed
direction as **A non-zero exit blocks**. **A non-zero exit blocks** verified — `undecided` blocks
exactly like `fail`. See the showrunner charter's size/decompose/route duty for the verification
obligation.

## What this check does not do

- **Register path resolution** — the caller reads the quote header and passes `--register`. That
  keeps the script call-site-agnostic.
- **Issue fetch** — the caller supplies a body file. The script never reaches the network and
  cannot tell an empty body from a failed fetch — that is the caller's to establish, which is why
  the recipes above check `gh` exit and file non-emptiness before running the checker.
- **`--allow-no-required-entries`** — with the flag, a `pass` means "no required entries and no
  drifted quotes", not "this child's register consumption was verified".
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
