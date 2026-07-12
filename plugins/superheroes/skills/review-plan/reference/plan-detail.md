<!-- plan-detail-version: 1 -->

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
