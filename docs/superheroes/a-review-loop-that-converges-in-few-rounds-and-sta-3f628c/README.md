# a-review-loop-that-converges-in-few-rounds-and-sta-3f628c — the spec and its breakdown

**Spec (owner-approved 2026-10-27, committed in this folder):** [`spec.md`](spec.md), a review loop
that converges in few rounds and stays simple: who applies the fixes; round 1's panel, big changes,
break-it tests and the verifier, synthesis and repeats, and copies of a bug; findings outside the PR;
rounds 2 to 4 and how a session stops; after handback; what is removed; the review record; the lanes;
and how we know it worked. Approval is recorded in the spec's frontmatter (`approved: "2026-10-27"`).
Its Amendments log holds one entry (2026-10-28, substantive: FR-6, files a change proves identical to a named source are not counted or read). The epic, C1, C1-L5 and C2, whose text or quoted register entry it touches, anchor at `as-of amendment #1`; every other child anchors at `as-of amendment #0`, which still resolves because the sections it cites did not change. The breakdown rides the
spec PR, #2199, and one merge word covers spec and breakdown; the children file, with the owner's
word, as it merges. The epic is the discovery's issue, #2185, whose body is rewritten in place to
[`epic.md`](epic.md) at filing.

The spec's own working files stay where discovery left them: [`board/`](board/) (the approved build
board, version 7, with its README and redraw record), [`sheets/`](sheets/) (discovery's sheets) and
[`checks-record.md`](checks-record.md) (the spec checks' record).

The breakdown:

- [`coverage-map.md`](coverage-map.md): every acceptance criterion of the spec owned exactly once:
  74 acceptance bullets (one split inside C1, declared), 3 non-functional lines and 2 Definition of
  done bullets, 80 rows in all, checked by script (re-checked after amendment 1, 2026-10-28). FR-53 is owned by #2189, as the spec says.
- [`register.md`](register.md): the cross-child contract register (16 entries; 8 carry a
  decide-by). R9 and R10 are the seam with #2189 and R11 the seam with #2190.
- [`epic.md`](epic.md): #2185's body, as it would be rewritten at filing.
- `children/C1.md` to `children/C4.md`: the child (feature) issue bodies, as they would be filed.
- `children/C1-L1.md` to `children/C1-L13.md`: the thirteen layer sub-issue bodies of C1's stack.
- [`seams/2189.md`](seams/2189.md) and [`seams/2190.md`](seams/2190.md): the blocks the advisor
  appends to #2189's and #2190's bodies at filing, so each seam is recorded on both sides.
- The package-read audit trail is not here yet: the independent package read writes it before the
  children file, with its filing dry-run.

## The children

| Child | What | Criteria | Size (non-test lines) | Stack | Wave | Lane | Presentation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [C1](children/C1.md) | The core loop | 62 | ~5,710, much of it deletion | 13 layers | 1 | full | show it |
| [C2](children/C2.md) | Big changes | 6 | ~550 | no | 2 | full | show it |
| [C3](children/C3.md) | Findings outside the PR | 3 | ~300 | no | 2 | full | show it |
| [C4](children/C4.md) | Copies of a bug | 5 | ~550 | no | 3 | full | show it |

C1's layers, bottom to top:

| Layer | What | Criteria | Size | Presentation |
| --- | --- | --- | --- | --- |
| [C1-L1](children/C1-L1.md) | The review record (the seam) | FR-51, UFR-6, No silent loss | ~350 | show it |
| [C1-L2](children/C1-L2.md) | The grounding seat removed | FR-47 | ~400 counted + ~1,600 whole-file deletions | say it |
| [C1-L3](children/C1-L3.md) | Review runs only as the loop | FR-48 (first sentence), FR-49, UFR-7 | ~350 | say it |
| [C1-L4](children/C1-L4.md) | Rounds and stops | FR-35 to FR-38, FR-41, UFR-8 | ~650 | show it |
| [C1-L5](children/C1-L5.md) | Round 1's panel, read lists, countable lines | FR-3, FR-4, FR-6, Independence | ~360 | say it |
| [C1-L6](children/C1-L6.md) | Break-it tests the build session runs | FR-11 to FR-13, FR-50, UFR-4 | ~600 | show it |
| [C1-L7](children/C1-L7.md) | The verifier's grade | FR-2, FR-14 to FR-17 | ~350 | show it |
| [C1-L8](children/C1-L8.md) | Synthesis and repeats | FR-18 to FR-22 | ~400 | say it |
| [C1-L9](children/C1-L9.md) | The build session applies the fixes | FR-1, FR-30, UFR-3 | ~800, mostly deletion | say it |
| [C1-L10](children/C1-L10.md) | Rounds 2 to 4 | FR-31 to FR-34, UFR-5 | ~450 | show it |
| [C1-L11](children/C1-L11.md) | A PR that comes back, and the lanes | FR-44, FR-45, FR-52, UFR-1, UFR-2 | ~450 | say it |
| [C1-L12](children/C1-L12.md) | The vet at handback | FR-39, FR-40, FR-42, FR-43, FR-46, FR-48 (second sentence) | ~300 | show it |
| [C1-L13](children/C1-L13.md) | The gardening pass's revisit checks (top) | FR-54, No target number | ~250 | say it; carries C1's entry point |

Every child and layer is `kind:machinery` and on the full lane (the lane rule's floor is none: no
declared risk area is touched). The Definition of done's two bullets belong to the epic's closure.

## Sequencing

Seam first: wave 1 is C1, its layers bottom-up, the record first, then the removals that shrink what
later layers edit, then the driver's stops, round 1, the fixes, the later rounds, a returning PR and
the advisor's side; C1-L12 and C1-L13 touch only the advisor's doctrine and may build in parallel.
Wave 2 is C2 and C3 in parallel, wave 3 is C4. Launches are the owner's word, one wave at a time.
C1 ships whole in one release; each add-on ships whole, C4 with or after C3 (R1).

## Cross-epic seams

#2189 (the gardening-pass measure) builds the count of the advisor's choices at the cap (FR-53) and
the per-seat cost the seating check reads; R9 and R10 bind what this epic records for it and what it
reads back. #2190 (the escape logging) owns the misses-log entry shape; R11 binds the false-PR-claim
entry this epic adds beside it. Both issues are single issues, so each one's body is its side's
register home: the advisor appends the blocks in `seams/` at filing.
