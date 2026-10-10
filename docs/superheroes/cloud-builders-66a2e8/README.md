# cloud-builders-66a2e8 — the spec and its breakdown

**Spec (owner-approved 2026-10-10, committed in this folder):** [`spec.md`](spec.md), cloud
builders: setting a project up for the cloud, where a build runs, a cloud build's life, cleanup,
keeping the reviewer pass alive, and keeping the plugin version in step. Approval is recorded in the
spec's frontmatter (`approved: "2026-10-10"`). Its Amendments log is empty, so every child anchors
at `as-of amendment #0`. The breakdown rides the spec PR, #1740, and one merge word covers spec and
breakdown; the children file, with the owner's word, as it merges.

The spec's own working files stay where discovery left them: [`board/`](board/) (the approved build
board and the journeys board, with the board README and the redraw record), [`sheets/`](sheets/)
(discovery's sheets) and [`checks-record.md`](checks-record.md) (the spec checks' record).

**Status:** breakdown drafted; package read not yet run.

The breakdown:

- [`coverage-map.md`](coverage-map.md): every acceptance criterion of the spec owned exactly once:
  66 acceptance bullets (three splits declared, two of them splitting one bullet into two rows) and
  5 Definition of done bullets, 73 rows in all, checked by script.
- [`register.md`](register.md): the cross-child contract register (11 entries). R7 is this side of
  the seam with epic #1708; R8 records the owner's ruling that the children build ahead of #1708 and
  merge together as one stack.
- [`epic.md`](epic.md): the epic issue body, as it would be filed. The epic is the stack's feature
  issue, so it quotes every register entry verbatim.
- `children/C1.md` to `children/C8.md`: the child issue bodies, as they would be filed. Each child is
  a direct sub-issue of the epic and one layer of the stack, numbered by its position; each names the
  entries that bind it, and its register-quote check runs on the epic's body with its token.
- The package-read audit trail is not here yet: the independent package read writes it before the
  children file, with its filing dry-run.

## The children

| Child | What | Criteria | Size (non-test lines) | Wave | Lane | Presentation |
| --- | --- | --- | --- | --- | --- | --- |
| [C1](children/C1.md) | The cloud lane, the seam (stack bottom, on `main`) | 4 | ~550 | 0 | full | say it |
| [C2](children/C2.md) | The setting and the setup record | 4 | ~250 | 0 | full | say it |
| [C3](children/C3.md) | The setup text and the pass command | 2 | ~300 | 0 | full | say it |
| [C4](children/C4.md) | The setup sitting and the check session | 7 | ~250 | 1 | full | say it |
| [C5](children/C5.md) | Where a build runs: routing, readiness, the launch report | 15 | ~500 | 1 | full | say it |
| [C6](children/C6.md) | The builder's cloud path | 13 | ~500 | 1, after #1708's #1709 and #1710 | full | say it |
| [C7](children/C7.md) | The advisor's side of a running cloud build | 14 | ~450 | 2 | full | say it |
| [C8](children/C8.md) | Cleanup and the reviewer pass's upkeep (stack top) | 9 | ~280 | 1, after #1708's #1716 and #1718 | full | say it |

Every child is `kind:machinery` and on the full lane. Five criteria, the spec's Definition of done,
belong to the epic's closure validation run.

## Sequencing

One native stack, the unit of merge (R8; owner ruling Canon 2026-10-10-dcc2b5e5-8), C1 on `main` at
the bottom and C8 at the top. Wave 0, now: C1, C2 and C3. Wave 1: C4 once C1, C2 and C3 have handed
back; C5 once C1 and C2 have; C6 once C1 and C3 have and epic #1708's review record is on main; C8
once C1 and C2 have and epic #1708's #1716 and #1718 are on main. Wave 2: C7. Launches are the
owner's word, one wave at a time. No PR merges on its own: the stack merges with one
`gh stack merge` once every layer is vetted, and it never ships partly in any release.

## Cross-epic seam

This epic builds on epic #1708 (the review redesign, `docs/superheroes/risk-calibrated-review-that-learns-dec0af/`):
its builds carry that epic's review record and follow its independence and not-run rules unchanged.
The seam is recorded in both registers: here as R7, and on #1708's side by *Status:* notes on its
R1 and R5 (the cloud-builders package builds on that entry; see our R7) and on its R2 (if this stack
lands before #1708's release is cut, that release carries it whole and never part of it). Those
notes are trailer lines only (advisor edit, 2026-10-10). The seam is one-directional by design:
#1708's builders take no input about where a build ran, so no first paragraph of #1708's register
changes and no #1708 child body changes.

Shared files need no text on #1708's side. #1708's #1710 and #1713 edit `rubric/review-discipline.md`,
its #1712 edits `lib/project_config.py`, and its #1716 and #1718 edit `owner-decisions.md`; our C6,
C2 and C8 edit the same files. Our R11 and sequencing bring #1708's merged edits forward into the
stack (and hold C8 until #1716 and #1718 are on main). #1708's #1732 assesses the charters' size;
our R11 keeps charter additions to pointer lines.
