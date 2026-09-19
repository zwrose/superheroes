# WO-R1-A item 4 — empty seat set refuses certification

Contract: `rubric/bite-proof.md`. Proof ran with the **detector unedited**; neutralization was a
targeted, reversible edit to `check_empty_seat_set` in `round_certification.py`, reverted by
exact inverse before the green half.

## Detector — `check_empty_seat_set`

**Guarded element.** `round_certification.py` — `check_empty_seat_set` early gate in `certify`.
**Axis.** When `_collect_seats(ctx)` is empty, certification must refuse with class
`unrun-review` and artifact `driver-journal.jsonl` — never emit a certified receipt with
`seats: []`.

**Neutralization:**

```python
-    if not _collect_seats(ctx):
+    if False and not _collect_seats(ctx):
```

**Raw red** — node `test_empty_seat_set_refuses_certification`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_empty_seat_set_refuses_certification ___________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-1400/test_empty_seat_set_refuses_ce0')

    def test_empty_seat_set_refuses_certification(tmp_path):
        session_dir = write_session(tmp_path, journal_lines=[], envelopes=[])
        path = os.path.join(session_dir, RC.JOURNAL_FILE)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n")
        receipt, refusal = RC.certify(session_dir)
>       assert receipt is None
E       AssertionError: assert {'baseGuard': 'checked-stat-bound', 'certification': {'base': 'fetched', 'fullPanel': True, 'independence': 'independe...tificationShape': 'full-panel-confirmed', 'decisions': [{'detail': 'certified', 'kind': 'converged', 'round': 1}], ...} is None

plugins/superheroes/lib/tests/test_round_certification.py:1939: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_empty_seat_set_refuses_certification
1 failed in 0.11s
```

**Restore.** Inverse edit — `if False and not _collect_seats(ctx):` restored to
`if not _collect_seats(ctx):`.

**Restore receipt (quoted restored lines):**

```python
def check_empty_seat_set(ctx):
    if not _collect_seats(ctx):
        return _refusal(
            "unrun-review",
            JOURNAL_FILE,
            "no recorded seat results — certification over zero seats is not a certification",
        )
    return None
```

**Supplementary `git status --porcelain` after restore:**

```
 M plugins/superheroes/lib/round_certification.py
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.11s
```
