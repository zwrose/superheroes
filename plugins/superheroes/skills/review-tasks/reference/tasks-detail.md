<!-- tasks-detail-version: 2 -->

## Acceptance suppression (re-review consume, FR-14)

Runs in §4 Compile, after dedupe and **before the verdict**: an owner-accepted finding on
unchanged content never re-blocks — the owner is never re-asked a decision they already made.
Load the ledger's candidates (absent ledger / failed read ⇒ `[]`: skip suppression entirely and
judge everything afresh — the fail-closed direction):

```bash
python3 "$ROOT_DIR/lib/review_acceptance.py" candidates --docs-dir "$(dirname "$TASKS_PATH")" \
  --doc tasks --doc-path "$TASKS_PATH" > "$SESSION_DIR/acceptance-candidates.json" 2>/dev/null \
  || echo '[]' > "$SESSION_DIR/acceptance-candidates.json"
```

When any candidate has `"hashMatches": true`: write the deduped findings array to
`$SESSION_DIR/merged.json`, then for each finding whose identity appears among the hash-matched
candidates judge from the doc: *is this re-raised finding the same concern the owner accepted?*
Write `$SESSION_DIR/acceptance-verdicts.json` as
`[{"id": "<identity copied VERBATIM from acceptance-candidates.json>", "action": "same" | "different", "reason": "<why>"}]`.
**Keep-on-uncertain: anything you cannot confidently call the same is `"different"`** — it is
judged afresh (a wrong call re-asks, which is safe; it never silently accepts). Then fold
deterministically — the tested consumer owns the accounting, and only a clear `same` with a
reason suppresses:

```bash
python3 "$ROOT_DIR/lib/acceptance_rereview.py" --merged "$SESSION_DIR/merged.json" \
  --leaf "$SESSION_DIR/acceptance-verdicts.json" \
  --candidates "$SESSION_DIR/acceptance-candidates.json" > "$SESSION_DIR/consumed.json" 2>/dev/null \
  || rm -f "$SESSION_DIR/consumed.json"
```

On success, `consumed.json`'s `findings` array is the **effective finding set** for the verdict
and blocking tally; report each `drops[]` entry carrying `"accepted": true` in the terminal
summary as `accepted (unchanged content) — not re-asked: <reason>`. A candidate with
`"hashMatches": false` means the concerned content changed — the finding is judged afresh
(FR-14's second rule). If the consumer invocation fails, proceed with the un-suppressed deduped
set and disclose: `acceptance suppression unavailable — accepted findings may be re-asked this
round`.

## Acceptance ledger (gate-approval)

When `REVIEW` is `passed`, persist the **parked round's open blockers** (Critical/Important
findings from the terminal round in `round-records.json`) to `tasks-accept.json` **before**
`gate_write.py` — FR-14 records acceptance first, then `gates.review` (UFR-1: ledger failure
never blocks the gate; disclose in the terminal summary). Stage the terminal round from
`$SESSION_DIR/compiled.json`, collect open blockers via the same helper the showrunner uses,
then record:

```bash
ROOT=$(git rev-parse --show-toplevel)
DOCS_DIR=$(dirname "$TASKS_PATH")
RECORDS="$SESSION_DIR/round-records.json"
ACCEPTED="$SESSION_DIR/open-blockers.json"
python3 -c "
import json, os
compiled = json.load(open('$SESSION_DIR/compiled.json', encoding='utf-8'))
records = []
if os.path.exists('$RECORDS'):
    try:
        with open('$RECORDS', encoding='utf-8') as f:
            records = json.load(f)
    except (OSError, ValueError):
        records = []
if not isinstance(records, list):
    records = []
records.append({'round': len(records) + 1, 'findings': compiled.get('findings') or []})
with open('$RECORDS', 'w', encoding='utf-8') as out:
    json.dump(records, out)
"
python3 "$ROOT_DIR/lib/review_handoff.py" collect-blocking --records-path "$RECORDS" \
  > "$SESSION_DIR/collect-blocking.json" 2>/dev/null \
  || echo '{"ok":false}' > "$SESSION_DIR/collect-blocking.json"
python3 -c "
import json, sys
with open('$SESSION_DIR/collect-blocking.json', encoding='utf-8') as f:
    collect = json.load(f)
if not collect.get('ok'):
    sys.exit(1)
with open('$ACCEPTED', 'w', encoding='utf-8') as out:
    json.dump(collect.get('findings') or [], out)
" && ACC=$(python3 "$ROOT_DIR/lib/review_acceptance.py" record \
  --docs-dir "$DOCS_DIR" --doc tasks --findings "$ACCEPTED" --doc-path "$TASKS_PATH" 2>/dev/null) \
  || ACC='{"ok":false}'
```

Skip when `REVIEW` is not `passed`. If open blockers are unreadable, or `$ACC` is unparseable or
`{"ok":false}`, disclose: `acceptance record could not be written — a re-review of unchanged
content will re-judge this finding rather than treat it as accepted`.
