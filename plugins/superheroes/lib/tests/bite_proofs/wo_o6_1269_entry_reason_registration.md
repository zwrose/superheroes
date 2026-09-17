# WO-O6 bite-proof — entry reason registration

This round registered the entry-undeclared reason in the dispatch outcome vocabulary and strengthened two detectors that had been unable to fail. Both proofs neutralize production code with the detector unedited, and each neutralization was reverted with an inverse edit, not a git discard.

---

## BP-O6-1 — entry-refusal producer census pins each producer to its declared token

- **guarded element:** `plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons` — each producer pinned to the specific declared token it emits
- **axis:** a producer that emits the **wrong declared** refusal token is caught (membership in the declared set is not enough)

Before this round the assertion was `reason in ENTRY_REFUSAL_REASONS`, so a producer emitting any other declared member still passed; the mutant below emits a declared token that is simply the wrong one, which the old assertion could not catch and the new one must.

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `legacy_refusal`):

```python
        "reason": "unknown-verb",
```

(replaces `"reason": "legacy-seat-args",` in the returned refusal dict)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest "plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons" -q
```

**raw red** (exit 1):

```
        assert isinstance(reason, str), (producer, result)
>       assert reason == expected, (producer, expected, reason, result)
E       AssertionError: ('dispatch-review-library-legacy', 'legacy-seat-args', 'unknown-verb', {'argv': [], 'attempts': 0, 'detail': 'dispatch...(the effort key is required; its value may be null; role is required and must not be null).', 'forfeited': False, ...})
E       assert 'unknown-verb' == 'legacy-seat-args'
E         
E         - legacy-seat-args
E         + unknown-verb

plugins/superheroes/lib/tests/test_engine_dispatch.py:9094: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_entry_refusal_producer_census_declared_reasons
1 failed in 0.71s
```

**restore:**

```python
        "reason": "legacy-seat-args",
```

**raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.64s
```

---

## BP-O6-2 — dropped-flag refusals must name the dropped flag

- **guarded element:** `plugins/superheroes/lib/tests/test_seat_bundle.py` — `test_dropped_flags_refuse_and_name_seat_dispatch_review`, `…_dispatch_write`, `…_guard_check` (36 parametrized cases)
- **axis:** a refusal that stops naming the dropped flag is caught (a bare exit-1 assertion is not enough)

Before this round the three tests asserted only `main(argv) == 1`, so a refusal that named nothing — or a different refusal reached for a different reason — still passed; the mutant below removes the clause that names the dropped flag, leaving the exit code unchanged.

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `legacy_refusal`):

```python
    if False and dropped_flags:  # bite-proof neutralization
```

(replaces `if dropped_flags:` — the refusal still fires and still exits 1; only the clause naming the dropped flags is removed)

**command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-bp -m pytest plugins/superheroes/lib/tests/test_seat_bundle.py -q -k "dropped_flags_refuse_and_name_seat"
```

**raw red** (exit 1) — tail:

All 36 of 36 selected cases went red. The block below is the tail of the failure list, not the whole of it.

```
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_dispatch_write[equals---role]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---engine]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---model]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---effort]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---engine-model]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---vendor]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[value---role]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---engine]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---model]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---effort]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---engine-model]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---vendor]
FAILED plugins/superheroes/lib/tests/test_seat_bundle.py::test_dropped_flags_refuse_and_name_seat_guard_check[equals---role]
36 failed, 72 deselected in 0.34s
```

**restore:**

```python
    if dropped_flags:
```

**raw green** (exit 0):

```
....................................                                     [100%]
36 passed, 72 deselected in 0.17s
```

---

## Coverage limits and restore discipline

The single-member accepted-tier branch of `seat_canary._resolve_canary_identity` is unreachable on this head. Every seat in the panel roster returns exactly two accepted tiers (`reviewer`, `reviewer-deep`), so the `len(accepted_tiers) == 1` branch and its `requires tier %r` refusal cannot be reached through this entry point and carries no proof. Record it as **unproven, unreachable** — do not claim a proof for it.

Both neutralizations were applied and reverted as targeted edits, and the probe worktree was verified clean (`git status --porcelain` empty) after each restore and before the green run.
