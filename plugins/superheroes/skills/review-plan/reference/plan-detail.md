<!-- plan-detail-version: 2 -->

## Acceptance ledger (gate-approval)

When `REVIEW` is `passed`, persist effective findings (not in the `skip-set`) to
`plan-accept.json` **before** `gate_write.py` — FR-14 records acceptance first, then
`gates.review` (UFR-1: ledger failure never blocks the gate; disclose in the terminal summary).
Write the skip-set to `$SESSION_DIR/skip-set.json` as `{"identities":[...]}` (each entry is the
same `finding_identity` key step 3 uses) immediately before this block:

```bash
ROOT=$(git rev-parse --show-toplevel)
DOCS_DIR=$(dirname "$PLAN_PATH")
ACCEPTED="$SESSION_DIR/accepted-findings.json"
python3 -c "
import json, sys, os
sys.path.insert(0, '$ROOT_DIR/lib')
import finding_identity
skip = set()
if os.path.exists('$SESSION_DIR/skip-set.json'):
    skip = set(json.load(open('$SESSION_DIR/skip-set.json', encoding='utf-8')).get('identities') or [])
with open('$SESSION_DIR/compiled.json', encoding='utf-8') as f:
    findings = json.load(f).get('findings') or []
effective = [f for f in findings if isinstance(f, dict) and finding_identity.finding_identity(f) not in skip]
with open('$ACCEPTED', 'w', encoding='utf-8') as out:
    json.dump(effective, out)
"
ACC=$(python3 "$ROOT_DIR/lib/review_acceptance.py" record \
  --docs-dir "$DOCS_DIR" --doc plan --findings "$ACCEPTED" --doc-path "$PLAN_PATH" 2>/dev/null) \
  || ACC='{"ok":false}'
```

Skip when `REVIEW` is not `passed`. If `$ACC` is unparseable or `{"ok":false}`, disclose:
`acceptance record could not be written — a re-review of unchanged content will re-judge this
finding rather than treat it as accepted`.

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
