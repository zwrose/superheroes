# Bite-proof record — #1271 WO-A14-C (orders-manifest seat-entry roster refusal)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited** — the
neutralization is a targeted, reversible edit to the guarded code in `round_certification.py`,
reverted by exact inverse before each green half. Probes ran in the implementer worktree on branch
`wo/1271a14-C` at base `75decbbf`.

**The guarded-element set — three elements, one per fail-closed edge.** Each is independently
neutralizable; no representative stands for the others.

| # | Guarded element | Axis |
|---|---|---|
| 1 | `if not isinstance(entry, dict):` refusal in `_orders_emitted_roster_or_refusal` | non-object `seats` entry must refuse, not skip |
| 2 | `if not isinstance(seat, str) or not seat:` refusal | missing, non-string, or empty `seat` must refuse, not skip |
| 3 | present-but-bad `occurrence` refusal | coerce-to-zero on bad `occurrence` must not ship; must refuse |

---

## 1 — non-object seat entry

**Guarded element.** `round_certification.py` — the `if not isinstance(entry, dict):` refusal in
`_orders_emitted_roster_or_refusal`.
**Axis.** A hash-authenticated manifest whose `seats` mapping holds a non-object entry must refuse
`unfetched-findings` naming the manifest path and the entry key — never return an empty roster.

**Neutralization.** Replace the refusal block with `continue` (the pre-change skip).

**Test.** `plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_non_object_seat_entry`.

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_orders_emitted_roster_refuses_non_object_seat_entry _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1226/test_orders_emitted_roster_ref0')

    def test_orders_emitted_roster_refuses_non_object_seat_entry(tmp_path):
        ...
        roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
>       assert roster is None
E       assert [] is None

plugins/superheroes/lib/tests/test_round_certification.py:2074: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_non_object_seat_entry
1 failed in 0.16s
```

**Restore.** `continue` → the `return None, _refusal(...)` block naming
`orders manifest seat entry '%s' is not an object`.

**Restore receipt.** `git status --porcelain plugins/superheroes/lib/round_certification.py` →
` M plugins/superheroes/lib/round_certification.py` (only the intended implementation edit remains).

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.13s
```

---

## 2 — unusable seat field

**Guarded element.** `round_certification.py` — the `if not isinstance(seat, str) or not seat:`
refusal in `_orders_emitted_roster_or_refusal`.
**Axis.** An entry whose `seat` is missing, not a string, or the empty string must refuse — never
skip silently.

**Neutralization.** Replace the refusal block with `continue`.

**Test.** `plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_unusable_seat_field`.

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_orders_emitted_roster_refuses_unusable_seat_field ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1228/test_orders_emitted_roster_ref0')

    def test_orders_emitted_roster_refuses_unusable_seat_field(tmp_path):
        ...
        roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
>       assert roster is None
E       assert [] is None

plugins/superheroes/lib/tests/test_round_certification.py:2104: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_unusable_seat_field
1 failed in 0.17s
```

**Restore.** `continue` → the `return None, _refusal(...)` block naming
`orders manifest seat entry '%s' has unusable seat field`.

**Restore receipt.** Same path shows only the implementation edit after inverse.

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.15s
```

---

## 3 — unusable occurrence when present

**Guarded element.** `round_certification.py` — the present-but-bad `occurrence` refusal in
`_orders_emitted_roster_or_refusal`.
**Axis.** A present `occurrence` that is a bool, not an int, or negative must refuse — never
coerce to `0`.

**Neutralization.** Replace the refusal block with `occurrence = 0` (the pre-change coercion).

**Test.** `plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_unusable_occurrence`.

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_orders_emitted_roster_refuses_unusable_occurrence ____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-1231/test_orders_emitted_roster_ref0')

    def test_orders_emitted_roster_refuses_unusable_occurrence(tmp_path):
        ...
        roster, refusal = RC._orders_emitted_roster_or_refusal(session_dir, event)
>       assert roster is None
E       AssertionError: assert [('security-reviewer', 0)] is None

plugins/superheroes/lib/tests/test_round_certification.py:2121: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_orders_emitted_roster_refuses_unusable_occurrence
1 failed in 0.19s
```

**Restore.** `occurrence = 0` → the `return None, _refusal(...)` block naming
`orders manifest seat entry '%s' has unusable occurrence`.

**Restore receipt.** Same path shows only the implementation edit after inverse.

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.16s
```
