# risk-calibrated-review-that-learns-dec0af — the spec and its breakdown

**Spec (owner-approved 2026-10-10, committed in this folder):** [`spec.md`](spec.md), the review
redesign from discovery #1472: what "reviewed" means and the review record; Risk and trust, the
lanes and the panel; findings and the fix loop; the owner's decisions on the index, the PR sheets and
the walk; learning from escapes; and what an existing project gets. Approval is recorded in the
spec's frontmatter (`approved: "2026-10-10"`). Its Amendments log is empty, so every child anchors at
`as-of amendment #0`. The breakdown rides the spec PR, #1702, and one merge word covers spec and
breakdown; the children file, with the owner's word, as it merges.

The spec's own working files stay where discovery left them: [`board/`](board/) (the approved build
board and the journeys board, with the board README), [`sheets/`](sheets/) (discovery's remainder and
final sheets) and [`checks-record.md`](checks-record.md) (the spec checks' record).

The breakdown:

- [`coverage-map.md`](coverage-map.md): every acceptance criterion of the spec owned exactly once:
  141 acceptance bullets (six splits declared, two of them splitting one bullet into two rows), 4 non-functional lines and 3 Definition of
  done bullets, 150 rows in all, checked by script.
- [`register.md`](register.md): the cross-child contract register (13 entries); children quote it
  verbatim. R9 is the reciprocal half of the spec-alignment landing package's seam R12.
- [`epic.md`](epic.md): the epic issue body, as it would be filed.
- `children/C1.md` to `children/C10.md`: the child (feature) issue bodies, as they would be filed.
- `children/C2-L1.md` to `C2-L5.md` and `children/C9-L1.md` to `C9-L3.md`: the eight layer
  sub-issue bodies of the two stacked children.
- The package-read audit trail is not here yet: the independent package read writes it before the
  children file, with its filing dry-run.

## The children

| Child | What | Criteria | Size (non-test lines) | Stack | Wave | Lane | Presentation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [C1](children/C1.md) | The review record, the seam | 10 | ~500 | no | 0 | full | say it |
| [C2](children/C2.md) | Retire the certificate parts; keep the wiring and admission checks | 13 | ~5,250, mostly deletion | 5 layers | 1 | full | say it |
| [C3](children/C3.md) | The advisor's vet reads the review record | 3 | ~150 | no | 1 | full | nothing to see |
| [C4](children/C4.md) | Risk and trust: the configure item, its reader and the setup sitting | 6 | ~800 | no | 2 (first) | full | show it |
| [C5](children/C5.md) | Lanes and the panel follow Risk and trust; independence | 16 | ~900 | no | 2 | full | say it |
| [C6](children/C6.md) | The test role replaces the test reviewer | 14 | ~600 | no | 2 | full | say it |
| [C7](children/C7.md) | Findings and the fix loop | 21 | ~850 | no | 3 | full | say it |
| [C8](children/C8.md) | The owner's decisions: batches, the walk, the merge word, receipts, Canon | 14 | ~400 | no | 3 | full | say it |
| [C9](children/C9.md) | The PR sheet and the index | 39 | ~1,800 | 3 layers | 3 | full | show it |
| [C10](children/C10.md) | Learning from escapes | 11 | ~350 | no | 4 | full | say it |

Every child is `kind:machinery` and on the full lane. Three criteria, the spec's Definition of done,
belong to the epic's closure validation run.

## Sequencing

Seam first: wave 0 is C1; wave 1 is C2 and C3 in parallel; wave 2 is C4, then C5 and C6 in parallel;
wave 3 is C7, C8 and C9; wave 4 is C10. Launches are the owner's word, one wave at a time. Nothing
releases until every child has merged (R2).

## Cross-epic seam

The spec-alignment landing package (`docs/superheroes/spec-alignment-landing-2026-10-05/`) recorded
its seam with this work as its register entry R12, owed reciprocally once this spec was approved.
R9 here quotes R12 verbatim and records this package's answer (the risk questions join the
who-it's-for sitting; risk-tolerance records live in Risk and trust), consumed by C4. The other
register's R12 status line now points at R9 (advisor edit, 2026-10-10).
