# Bite-proof record c1l11c_wo3_group_restore

The detector this change adds: `test_fix_groups_c1l11c.py::test_fr18_a_weakened_member_is_restored_by_the_restore_alone_and_the_other_member_is_untouched`
(DoD row 2 of issue #2268: a fix-group member whose test the build session weakens is restored per member by
C1-L10b's restore, and the other member is unaffected). It drives the real path: two grouped break-it findings, one
shared fix commit that weakens only member A's test, the audit fold with a `weakened` answer for A and `matches` for B,
`_advance` to the restore-only `apply-fixes` step, the restore commit, and the restore fold.

Guarded elements, declared up front by the order: E1 only the mismatched member is restorable (B is not in `restores`);
E2 the restored bytes are the test role's version (A_TEST), never the weakened committed bytes. E3 (B's committed test
and carried rows unchanged) and E4 (the fix group survives) are asserted by the test too, but the order names no
neutralization for them; they are listed as unproven below.

Every run used, from the worktree root:
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo3 -m pytest plugins/superheroes/lib/tests/test_fix_groups_c1l11c.py plugins/superheroes/lib/tests/test_c1l10b_test_restore.py -q -p no:cacheprovider -n auto`
Each neutralization was a targeted edit through the edit tool to `plugins/superheroes/lib/round_driver.py`, undone by the
exact inverse edit; no `git checkout`, `git restore`, `git reset` or `git stash` was run. Nothing is redacted. The red
captures below are the failing assertion lines and summaries read off the run (the runs' output was filtered to the
`E`, `>` and `FAILED` lines for N2 and cut to its tail for N1), not the complete logs.

---

## E1 — only the mismatched member is restorable (`round_driver.py:7757`, the audit-fold entry)

- neutralization: `    restorable = [tid for tid in mismatch_ids if tid not in rider_ids]` became
  `    restorable = [tid for tid in targets_by_id if tid not in rider_ids]`.
- detector: the new test, at its `step["payload"]["restores"] == [...]` assertion (`test_fix_groups_c1l11c.py:232`).
- red: `2 failed, 86 passed`. The new test fails with `At index 0 diff: {'findingKey': 'tests/test_charge_amount.py::breakit a retried 250 charge runs twice@L1', 'path': 'tests/test_charge_amount.py', 'content': ...B's test...}` — member B appears in `restores`. The other failure is C1-L10b's own
  `test_t8_with_no_mismatch_the_audit_continues_exactly_as_before` (`assert RD.TEST_RESTORE_FIELD not in w.state`).
- restore: the inverse edit; the line reads again `    restorable = [tid for tid in mismatch_ids if tid not in rider_ids]`.

## E2 — the restored bytes are the test role's version (`round_driver._restore_items`, line 5964)

- neutralization: `items.append({"findingKey": tid, "path": path, "content": content,` became
  `items.append({"findingKey": tid, "path": path, "content": facts.get("committedTest") or content,`.
- detector: the new test, at the same `restores` assertion (`test_fix_groups_c1l11c.py:232`).
- red: `20 failed, 68 passed` (the neutralization breaks 19 C1-L10b restore tests too). The new test fails with
  `At index 0 diff: {'findingKey': 'tests/test_charge_once.py::breakit a retried charge runs twice@L1', ... 'content': "...assert len(ledger) >= 1, ..."` against the expected `== 1` bytes — A's restore carries the weakened committed bytes.
- restore: the inverse edit; the line reads again `items.append({"findingKey": tid, "path": path, "content": content,`.

## Unproven

E3 (B's committed test and B's carried rows are unchanged by the restore) and E4 (both live rows keep the one fix
group) are asserted by the test, but no neutralization of them was ordered or applied, so nothing here shows the test
goes red if they break.

## Green

Both restored: `88 passed`, exit 0 (the same scoped command). After the last inverse edit
`git diff --stat -- plugins/superheroes/lib/round_driver.py` printed nothing.
