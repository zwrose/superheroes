---
superheroes: doc
schemaVersion: 1
docType: tasks
workItem: acceptance-fixture-placeholder
issue: null
parent: {workItem: acceptance-fixture-placeholder, docType: plan}
size: small
status: approved
gates: {review: passed}
expected_phases:
  - plan
  - review-plan
  - tasks
  - review-tasks
  - workhorse
  - review-code
  - draft-PR
  - test-pilot
  - mark-ready
  - ship
producedBy: "the-architect@0.4.0"
created: "2026-07-02"
updated: "2026-07-13"
---
# Acceptance-harness fixture — Tasks

## Goal

Create `target.txt` on the work-item branch as one commit: the seeded one-line baseline plus
exactly one dated line below it. Nothing else — then ship to a ready-for-review PR. This is
the throwaway change the acceptance harness runs the real showrunner over end-to-end.

The branch starts WITHOUT `target.txt` (it is cut from a repo that does not carry one). The
one-line baseline ships alongside this work-item's docs — `target.txt` in the SAME directory
as this tasks document, placed there by the harness. Your build instructions name this tasks
doc's absolute path; that path's directory is where the baseline lives, and reading it is
within your permitted doc scope. Do not treat the file's absence from the branch as an error.

## Architecture

One commit creating one two-line file, `target.txt`. No modules, no interfaces. The execution
engine may only ever produce one commit for the task; reviewers judge the file content and the
diff scope, never the commit count.

## Tech Stack

Plain text file edit. No language, no dependency, no build tool.

### Task 1: Create target.txt — seeded baseline plus one dated line

**Files:**
- Create: `target.txt` (the seeded one-line baseline, then one appended dated line)

- [ ] **Step 1: Check the starting state**

```bash
wc -l target.txt 2>/dev/null || echo "absent as expected"
```

- `absent as expected` — the normal fresh start: continue with Step 2.
- `2 target.txt` and line 2 matches `acceptance run: <UTC timestamp>` — a prior attempt of
  THIS task already completed; verify it is committed (`git status --porcelain` clean for
  `target.txt`) and report the task done instead of redoing it.
- Anything else (a `target.txt` with other content) — STOP and report: the branch is not at
  the fixture's known starting state.

- [ ] **Step 2: Seed the baseline and append the dated line**

Set `TASKS_DOC_DIR` to the directory of this tasks document's absolute path as named in your
build instructions, then:

```bash
cp "$TASKS_DOC_DIR/target.txt" target.txt
wc -l target.txt   # expected: 1 (the seeded baseline)
printf 'acceptance run: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> target.txt
```

- [ ] **Step 3: Verify the final shape**

```bash
wc -l target.txt          # expected: 2
git status --porcelain    # expected: only target.txt listed
```

Line 1 is the seeded baseline; line 2 is the single dated line. No other file is touched.

- [ ] **Step 4: Commit (one commit, with the Task-Id trailer)**

```bash
git add target.txt
git commit -m "feat: create acceptance target.txt — seeded baseline plus dated line" -m "Task-Id: 1"
```

- [ ] **Step 5: Verify the commit**

```bash
git show --numstat HEAD -- target.txt   # expected numstat: 2 added, 0 deleted, target.txt only
```
