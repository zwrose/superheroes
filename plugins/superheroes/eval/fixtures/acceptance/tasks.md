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
  - tasks
  - build
  - review
  - ship
producedBy: "the-architect@0.4.0"
created: "2026-07-02"
updated: "2026-07-02"
---
# Acceptance-harness fixture — Tasks

## Goal

Append exactly one dated line to `target.txt` and nothing else, shipping it to a
ready-for-review PR. This is the throwaway change the acceptance harness runs the real
showrunner over end-to-end.

## Architecture

One append to one tracked file, `target.txt`. No modules, no interfaces.

## Tech Stack

Plain text file edit. No language, no dependency, no build tool.

### Task 1: Append the dated line to target.txt

**Files:**
- Modify: `target.txt`

- [ ] **Step 1: Write the failing check**

Confirm the current line count of `target.txt`:

```bash
wc -l target.txt
```

Expected: the committed single line (plus its trailing newline).

- [ ] **Step 2: Append exactly one dated line**

Append one dated line below the existing content of `target.txt` — touch no other file:

```bash
printf 'acceptance run: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> target.txt
```

- [ ] **Step 3: Verify exactly one line was added**

```bash
wc -l target.txt
```

Expected: the previous count plus one. `git status --porcelain` shows only `target.txt` modified.

- [ ] **Step 4: Commit**

```bash
git add target.txt
git commit -m "feat: append acceptance-run dated line to target.txt"
```
