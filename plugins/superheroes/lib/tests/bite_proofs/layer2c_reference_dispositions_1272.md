# C13 layer 2c (#1272, WO-B) bite-proof — owner-gate action-table byte pins

**Provenance:** documentation and census re-pins built by cursor composer-2.5 (WO-B on `l2c-wob/1272`,
cut from `af9ed8f2`). The proof below was run in that worktree by the implementer dispatch,
neutralizing through a targeted edit of the `present-judgment` actions-table row and restoring by the
inverse edit (never `git checkout` / `git restore`).

Command for every run:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-wob -m pytest plugins/superheroes/lib/tests/test_decision_point_census.py::test_byte_pin_lines_exist -q
```

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-2c-CENSUS-J | `present-judgment` actions-table row in `round-driver.md` | owner-gate submit shape (`followUp?` on disposition objects) stays byte-pinned to `_BYTE_PIN_LINES` | `test_byte_pin_lines_exist` |

The `present-stall-menu` row was re-pinned in the same change; the neutralization below targets the
judgment row only — one representative failure mode for the pair.

## BP-2c-CENSUS-J — owner-gate row drift

**neutralization** (`plugins/superheroes/skills/review-code/reference/round-driver.md`, actions
table `present-judgment` row): remove `, followUp?` from the submit shape and drop the sentence
"`skip` needs a citable `reason` and may carry an optional `followUp`." — restoring the pre-layer
`{dispositions: [{id, disposition, guidance?, reason?}, ...]}` / reason-only `skip` prose.

**raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________________ test_byte_pin_lines_exist ___________________________

    def test_byte_pin_lines_exist():
        """#1144: a pin for a line that no longer exists must fail, not sit in the table."""
        stale = []
        all_stripped = set()
        for path in _walk_skills_files():
            if _census_excluded(path):
                continue
            try:
                lines = _read_text(path).splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            all_stripped.update(ln.strip() for ln in lines)
        for pinned in _BYTE_PIN_LINES:
            if pinned not in all_stripped:
                stale.append(repr(pinned))
>       assert not stale, (
            "#1144 byte-pin table contains dead entries — re-adjudicate (#1144). Stale:\n"
            + "\n".join(stale)
        )
E       AssertionError: #1144 byte-pin table contains dead entries — re-adjudicate (#1144). Stale:
E         "| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here — an **intervention gate, not a terminal**. Present each `payload.findings[]` (id, file, line, title, severity) with `payload.findings[].dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`). Submit `{dispositions: [{id, disposition, guidance?, reason?, followUp?}, ...]}` — `skip` needs a citable `reason` and may carry an optional `followUp`. Fixes fold into the round's fix batch and the loop proceeds into the fix leg; skips ride the exit disclosure. Fail-closed: a missing/unknown disposition (or a reasonless skip) folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the dispute yourself. |"
E       assert not ['"| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here — an **intervent...kip) folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the dispute yourself. |"']

plugins/superheroes/lib/tests/test_decision_point_census.py:468: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_decision_point_census.py::test_byte_pin_lines_exist
1 failed in 0.07s
```

**restore:** inverse edit — restore `, followUp?` on the submit shape and the optional-`followUp`
sentence for `skip`.

**restored lines quoted back** (actions table `present-judgment` row):

```
| `present-judgment` | A tradeoff/product-choice blocker is an **owner-judgment** call routed here — an **intervention gate, not a terminal**. Present each `payload.findings[]` (id, file, line, title, severity) with `payload.findings[].dispositions` (`fix-as-suggested`, `fix-with-guidance`, `skip`). Submit `{dispositions: [{id, disposition, guidance?, reason?, followUp?}, ...]}` — `skip` needs a citable `reason` and may carry an optional `followUp`. Fixes fold into the round's fix batch and the loop proceeds into the fix leg; skips ride the exit disclosure. Fail-closed: a missing/unknown disposition (or a reasonless skip) folds as `fix-as-suggested` — a judgment blocker is never silently skipped. Never judge the dispute yourself. |
```

**raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.06s
```

---

# BP-2c-CENSUS-S — the `present-stall-menu` row, proved at the final head

**Provenance (this section only):** run by the **orchestrator** in a dedicated detached probe
worktree (`issue-1272-r5-probe`) cut at the final head **`8128ca43`**, closing the gap the round-4
park recorded as owed: the section above proves the `present-judgment` row only, and the record's own
sentence — "one representative failure mode for the pair" — is not a proof of the second row. It is
now proved in its own right. Neutralization is a targeted revertible edit through the host's edit
action; restore is its exact inverse. The probe worktree was confirmed byte-clean after restore.

Command for every run in this section:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-probe -m pytest plugins/superheroes/lib/tests/test_decision_point_census.py::test_byte_pin_lines_exist -q
```

## Guarded element

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-2c-CENSUS-S | `present-stall-menu` actions-table row in `round-driver.md` | the stall-gate submit shape (`followUp?` on the choice object) stays byte-pinned to `_BYTE_PIN_LINES` | `test_byte_pin_lines_exist` |

## BP-2c-CENSUS-S — stall-gate row drift

**Neutralization** (`plugins/superheroes/skills/review-code/reference/round-driver.md`, actions
table `present-stall-menu` row): replace

```
Submit `{choice, followUp?}` — **`accept-the-disclosed-risk`** may carry an optional `followUp`. **`hold`**
```

with the pre-layer text

```
Submit `{choice}`. **`hold`**
```

**Raw red** (exit 1):

```
        for pinned in _BYTE_PIN_LINES:
            if pinned not in all_stripped:
                stale.append(repr(pinned))
>       assert not stale, (
E       AssertionError: #1144 byte-pin table contains dead entries — re-adjudicate (#1144). Stale:
E       assert not ["'| `present-stall-menu` | The **audit-stall owner gate** — reached only after one invisible self-recovery (never for...recorded on the round); an empty/unresolvable stall-target snapshot parks `cannot-certify` instead of re-entering. |'"]
plugins/superheroes/lib/tests/test_decision_point_census.py:468: AssertionError
FAILED plugins/superheroes/lib/tests/test_decision_point_census.py::test_byte_pin_lines_exist
1 failed in 0.10s
```

The stale entry named in the failure is the **`present-stall-menu`** row — a different pin from the
one BP-2c-CENSUS-J's red names, which is what makes this a proof of the second row rather than a
re-run of the first.

**Restore.** Exact inverse edit.

**Restored line quoted back** (actions table `present-stall-menu` row):

```
| `present-stall-menu` | The **audit-stall owner gate** — reached only after one invisible self-recovery (never for a judgment blocker; those go to `present-judgment`). Present `payload.choices` (three-choice menu: `one-more-round`, `accept-the-disclosed-risk`, `hold`; `accept-the-disclosed-risk` only when `payload.acceptRiskEligible` — gated on a stalled audit target that is CONFIRMED with evidence; `one-more-round` only when offered — once per session). Submit `{choice, followUp?}` — **`accept-the-disclosed-risk`** may carry an optional `followUp`. **`hold`** → terminal `held`, certification withheld (absorbs the retired scope-reduction choice). **`accept-the-disclosed-risk`** → certifies when eligible. **`one-more-round`** → not a terminal: clears the stall once, re-enters `dispatch-fixer` → `dispatch-audits` with the stalled targets as the batch (journaled; recorded on the round); an empty/unresolvable stall-target snapshot parks `cannot-certify` instead of re-entering. |
```

**Raw green** (exit 0): `31 passed in 0.30s` in the closing run that covered this detector together
with the whole ledger detector file.

## BP-2c-CENSUS-J re-run at the final head

The `present-judgment` neutralization above was **re-established by the orchestrator at `8128ca43`**
and produced the same stale-pin failure (exit 1, the `present-judgment` row named as stale), then
restored and green. It is not carried as the implementer's inherited claim.
