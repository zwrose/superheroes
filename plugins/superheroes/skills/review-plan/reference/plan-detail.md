<!-- plan-detail-version: 3 -->

## Acceptance ledger (gate-approval)

When `REVIEW` is `passed`, persist the **parked round's open blockers** (Critical/Important
findings from the terminal round in `round-records.json`) to `plan-accept.json` **before**
`gate_write.py` — FR-14 records acceptance first, then `gates.review` (UFR-1: ledger failure
never blocks the gate; disclose in the terminal summary). Stage the terminal round from
`$SESSION_DIR/compiled.json`, collect open blockers via the same helper the showrunner uses,
then record:

```bash
ROOT=$(git rev-parse --show-toplevel)
DOCS_DIR=$(dirname "$PLAN_PATH")
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
  --docs-dir "$DOCS_DIR" --doc plan --findings "$ACCEPTED" --doc-path "$PLAN_PATH" 2>/dev/null) \
  || ACC='{"ok":false}'
```

Skip when `REVIEW` is not `passed`. If open blockers are unreadable, or `$ACC` is unparseable or
`{"ok":false}`, disclose: `acceptance record could not be written — a re-review of unchanged
content will re-judge this finding rather than treat it as accepted`.

## Common Mistakes

| Mistake                                                                     | Fix                                                                                                                                                             |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Flagging implementation details at plan time                                | Those are Tasks/code-time concerns. The plan may defer "how" as long as "what" and "why" are clear.                                                             |
| Demanding exact test cases in the plan                                      | Test *strategy* belongs in the plan; the enumerated test list is Tasks. Don't grade Tasks-level content here.                                                    |
| Overwriting a `changes-requested` gate with `passed`                        | The gate write reflects the verdict. A skipped blocking finding or a three-round cap with open Critical/Important → `changes-requested`, never `passed`.            |
| Hand-editing the frontmatter to set the gate                                | The gate is written only via the-architect's `definition_doc.py set-gate`. If that lib is absent, report "gate not recorded" — never hand-edit the YAML.        |
| Citing line numbers from the wrong file                                     | Plan-doc citations point at `$SESSION_DIR/plan.md`; project-file citations point at repo paths. Don't mix them.                                                 |
| Re-raising findings the user skipped                                        | Check the `skip-set` and prior rounds before raising a finding. The author shouldn't see the same finding twice without a new technical basis.                  |
| Skipping the all-five-specialists rule based on classification              | The `touches` array is informational. All five always run — each returns `[]` when there's nothing in its dimension.                                            |
| Dispatching reviewers by reading an agent file                              | The five reviewers are bundled plugin agents — dispatch the `<name>` reviewer with its methodology (resolve dispatch via the host tool map (`hosts/<host>-tools.md` at the plugin root)).               |
| Skipping the profile bootstrap                                              | If no profile resolves, run review-init's create procedure inline first. Headless runs get a provisional strict profile.                                        |
