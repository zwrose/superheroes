# Contents

- [What this check is](#what-this-check-is)
- [Stack layer inputs](#stack-layer-inputs)
- [The invocation](#the-invocation)
- [The result contract](#the-result-contract)
- [What counts as a quoted register block](#what-counts-as-a-quoted-register-block)
- [A child that consumes no entry](#a-child-that-consumes-no-entry)
- [Vocabulary](#vocabulary)
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

## Stack layer inputs

For a **stack layer**, run `--child` with the **feature issue's child token** and pass the **feature
issue's body** to `--body-file`, not the layer sub-issue's body — register entries stay quoted on the
feature issue ([Each layer is a sub-issue](../../../rubric/native-stacks.md#each-layer-is-a-sub-issue)).
The layer's body states that the check uses those inputs.

## The invocation

The stable invocation (from a plugin-cache install, `ROOT_DIR` is
`${CLAUDE_PLUGIN_ROOT}`):

```bash
ROOT_DIR="${CLAUDE_PLUGIN_ROOT}"
python3 -B "$ROOT_DIR/lib/register_check.py" check \
  --register <path to the register .md> \
  --body-file <path to the consumer body .md> \
  --child <token> \
  [--register-copy {auto,main,worktree}] \
  [--allow-no-required-entries]
```

`--register-copy` selects **which copy** of the register to read (default: `auto`). `main`
reads the blob at `<main-ref>:<path-relative-to-repo-root>` where `<main-ref>` is `origin/main`
when it exists, otherwise `main`. `worktree` reads the file on disk. `auto` chooses `main` when
the register path resolves inside a git work tree, `worktree` when it resolves outside one, and
`main` when git cannot run or the repo-root probe fails — a read that could not be made must not
silently become the worktree copy. **When the selected copy
is `main` and the blob cannot be resolved or read** — no `origin/main`, no `main`, a shallow
clone, `git` not on PATH, a non-zero exit, a path not tracked on main — the result is
`undecided` with reason `register-unreadable` and a detail naming the ref and path tried. The
check **never** falls back to the worktree file unless the caller passes
`--register-copy worktree` explicitly.

**A register kept in an out-of-repo project store** is read with `--register-copy worktree`,
passed by the caller. The store is a git work tree with no `origin/main` and no `main`, so `auto`
selects `main` and answers `undecided` / `register-unreadable`; the file on disk is the only copy.

A child that consumes **no** register entry is declared on the register's `*No-entry children:*`
line — see [A child that consumes no entry](#a-child-that-consumes-no-entry). **That declaration
is the path for such a child.** `--allow-no-required-entries` is not that path: it only makes
the required set empty for a caller that asks for it, and **none of the three invocation points
ever passes it** — nothing there needs it, because the declaration covers the case. At those
points a `--child` that is neither named on a `*Consumers:*` line nor declared is a
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
`RESULT_FIELDS` in `lib/register_check.py` for the authoritative field list.
`--help` prints usage and exits 0 without JSON. `ok` is true only on `pass`. `reason` is null
except on `undecided`. `registerCopy` is `"main"` or `"worktree"` — the copy that was selected.
`registerRef` is the ref actually read (`"origin/main"` or `"main"`), or `null` for the worktree
copy. Both appear on every result, including every `undecided` path, so a caller never has to
infer which copy a refusal is about. `firstDifference` is the first `text-drift` finding, else null.
`noEntryDeclaration` is described under
[A child that consumes no entry](#a-child-that-consumes-no-entry).

**Results:**

| Result | Exit code | Meaning |
| --- | --- | --- |
| `pass` | 0 | Every required quote matches byte-exactly and every quoted block matches its register entry |
| `fail` | 1 | At least one `text-drift`, `missing-quote`, or `unknown-entry` finding |
| `undecided` | 2 | The check could not run to a pass/fail verdict |

A finding object carries the fields listed under **Finding fields** in
`FINDING_FIELDS` in `lib/register_check.py`. For `text-drift`, `line` is 1-based
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
- the block ends at the first line that does not begin with `>` at column 0, and **every** stripped
  line of the block is compared — an appended `>`-prefixed paragraph is drift, not decoration; a
  lazy continuation (a non-`>` line immediately after the quote with no blank line) is **not** part
  of the block here but GitHub renders it as blockquote continuation, so source and rendering can
  disagree;
- a blockquote inside a ``` or ~~~ **fence is ignored on purpose**, so an example quote inside a
  fenced code block never counts as a real one.

A register entry's **quotable text is a single paragraph** — the entry header line and the lines
immediately following it, up to the first blank line, italic metadata line, `---`, or heading.
Text after a blank line is trailer, not quotable.

## A child that consumes no entry

A register declares the children that consume no entry on **one** line:

```text
*No-entry children:* C7, the background child.
```

- **Form** — exactly `*No-entry children:* <list>`, outside any code fence. The list is
  comma-separated; each token is trimmed of spaces and may contain spaces. One trailing `.` at the
  end of the whole list is allowed.
- **Placement** — above the first entry header (`**R<n> — `), so it is never part of an entry's
  quotable text or trailer.
- **Matching is exact** — a child is declared when `--child` equals a token exactly. `C1` declared
  does not declare `C10`, and `C10` declared does not declare `C1`.
- **What a declared child gets** — a `pass` with `requiredEntries: []` and no quotes required.
  Any quoted block in its body is still compared exactly: drift is `text-drift`, an id the
  register does not define is `unknown-entry`.
- **A forgotten line still blocks** — a child that is neither declared nor named on any
  `*Consumers:*` line stays `undecided` / `child-unrecognized`.
- **Contradiction** — a child that is declared **and** named on an entry's `*Consumers:*` line is
  `undecided` / `child-contradicted` (exit 2). The detail names the child, the declaration line,
  and the entry ids. Other children of the register are unaffected.
- **Malformed fails closed** — any line that looks like the declaration (it begins, ignoring
  leading `*`, `_` and spaces and ignoring case, with `no-entry children` or `no entry children`)
  must be a valid declaration, or the whole register is `undecided` / `register-malformed` for
  **every** child, consuming children included. Malformed means: a damaged label (for example
  `*No-entry children: C2`, `**No-entry children:** C2`, `*no-entry children:* C2`,
  `_No-entry children:_ C2`); a candidate below the first entry header, including inside an
  entry's trailer; a second candidate; an empty list or an empty token (`C7,,C8`, `C7,`); a
  token containing `(`, `)`, `;`, `*` or a backtick. A declaration inside a code fence is ignored.

**`noEntryDeclaration`** is on every result. It is `{"line": <1-based line of the declaration>,
"children": [<tokens in order>], "childDeclared": <bool>}` whenever the register parsed and carries
a declaration — on `pass`, `fail`, `child-unrecognized` and `child-contradicted` alike. It is
`null` when the register has no declaration, and `null` on every other `undecided` result
(`usage`, `register-unreadable`, `register-empty`, `register-malformed`, `body-unreadable`,
`body-malformed`, `internal-error`), even if the register carries a declaration. The pass that
rests on the declaration is the one with `requiredEntries: []` and
`noEntryDeclaration.childDeclared: true`. The schema stays `register-check/1`.

## Vocabulary

The schema token, result tokens, finding kinds, undecided reasons, exit codes (`EXIT_PASS`,
`EXIT_FAIL`, `EXIT_UNDECIDED`), result fields, and finding fields are defined in
`lib/register_check.py` (`SCHEMA`, `RESULTS`, `FINDING_KINDS`, `UNDECIDED_REASONS`, `EXIT_PASS`,
`EXIT_FAIL`, `EXIT_UNDECIDED`, `RESULT_FIELDS`, `FINDING_FIELDS`).

## The three invocation points

**Child filing (showrunner duty 2).** When the advisor files a **register-consuming child** — an
epic child of a package that has a register, or a single-issue child standing in for one under
FR-36 — run the check against the body **before filing**, whether or not the body contains a
quoted block; a body with zero quoted blocks is exactly the case the check is there to fail for a
child that consumes an entry. A child declared on the register's `*No-entry children:*` line
passes with zero quotes; an undeclared child that no `*Consumers:*` line names still blocks as
`child-unrecognized`. For a
stack layer, use the [stack layer inputs](#stack-layer-inputs). Where applicability cannot be
derived from the issue alone, the route names the register and child token at routing for the
builder to pass. On `fail`, fix the body — do not file a drifted
quote. On `pass`, record the check's own output in the filing note — the `result` line, or `pass`
together with `requiredEntries` and `registerCopy`/`registerRef` — not merely a claim that it ran. When the register path and child
token are known — the route names them or they are derivable — **run the check**; an `undecided`
result blocks exactly like `fail`. When they are not known and applicability is genuinely unclear,
that is a **routing gap, not a reason to proceed**: raise it with the advisor (a builder **parks**;
the advisor resolves it before filing or before marking the package verified) rather than silently
treating the check as inapplicable; that is the same fail-closed direction as **A non-zero exit
blocks**. **A non-zero exit blocks** filing — `undecided` blocks until the inputs are readable and
the child token is recognized, exactly like `fail`. See the showrunner charter's board-hygiene duty
for the filing obligation.

**Child build intake (workhorse §1).** When the routed issue is a **register-consuming child**,
run the check at intake before the brief, whether or not the body contains a quoted block. A body
with zero quotes fails for a child that consumes an entry; a child declared on the register's
`*No-entry children:*` line passes with zero quotes, and an undeclared child that no
`*Consumers:*` line names still blocks as `child-unrecognized`. For a
stack layer, use the [stack layer inputs](#stack-layer-inputs). On
`fail`, **park** — the quoted text is the contract the build is graded on, so a drifted quote is
not a buildable surface. On `pass`, record the check's own output in the intake note — the
`result` line, or `pass` together with `requiredEntries` and `registerCopy`/`registerRef` — not merely a claim that it ran. When
the register path and child token are known — the route names them or they are derivable — **run
the check**; an `undecided` result blocks exactly like `fail`. When they are not known and
applicability is genuinely unclear, that is a **routing gap, not a reason to proceed**: raise it
with the advisor (a builder **parks**; the advisor resolves it before filing or before marking the
package verified) rather than silently treating the check as inapplicable; that is the same
fail-closed direction as **A non-zero exit blocks**. **A non-zero exit blocks** the build —
`undecided` is a **park**, exactly like `fail`. See the workhorse charter's intake section for the
park obligation.

**Package-read verification pass (showrunner duty 3).** At an epic package read's verification
pass, re-run the check per **register-consuming child** across **both** directions, whether or
not each body contains a quoted block. A body with zero quotes fails for a child that consumes an
entry; a child declared on the register's `*No-entry children:*` line passes with zero quotes, and
an undeclared child that no `*Consumers:*` line names still blocks as `child-unrecognized`. For a
stack layer, use the [stack layer inputs](#stack-layer-inputs). On `fail`, record a blocking package-read finding and do
not treat the package as verified. On `pass`, record the check's own output in the package-read
verification record — the `result` line, or `pass` together with `requiredEntries` and `registerCopy`/`registerRef` — not merely a
claim that it ran. When the register path and child token are known — the route names them or they
are derivable — **run the check**; an `undecided` result blocks exactly like `fail`. When they are
not known and applicability is genuinely unclear, that is a **routing gap, not a reason to
proceed**: raise it with the advisor (a builder **parks**; the advisor resolves it before filing
or before marking the package verified) rather than silently treating the check as inapplicable;
that is the same fail-closed direction as **A non-zero exit blocks**. **A non-zero exit blocks**
verified — `undecided` blocks exactly like `fail`. See the showrunner charter's size/decompose/route
duty for the verification obligation.

## What this check does not do

- **Rendered output** — the check compares **source text, not rendered output**. Two known constructs
  can make source and GitHub rendering disagree in the **fail-open** direction (both pre-existing,
  not closed by the fence fix): an **HTML comment** (`<!--` … `-->`) hides a quoted register entry
  from rendering while the checker still collects it as live; and a **lazy blockquote continuation**
  (exact quote immediately followed by a non-`>` line with no blank line) renders as a two-line
  blockquote on GitHub while only the `>`-prefixed lines are compared. Each requires a body that
  carries the construct.
- **Fence indent** — fence recognition follows CommonMark §4.5 at indent **0–3**; indented code
  blocks (four or more spaces) are not implemented. A consumer that accepts indented content applies
  its own indent guard.
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
