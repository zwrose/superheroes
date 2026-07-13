<!-- tasks-detail-version: 1 -->

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
