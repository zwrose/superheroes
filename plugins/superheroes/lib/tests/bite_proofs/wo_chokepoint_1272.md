# Bite-proof record — #1272 WO-2 (recorded-row revision-identity chokepoint)

Contract: `rubric/bite-proof.md`. Every proof below ran with the **detector unedited**; the
neutralization was applied as a targeted, reversible edit to the **production call site**, and
reverted by its exact inverse.

| # | Guarded element | Axis |
|---|---|---|
| G1 | `round_driver._journal_append` → `require_complete_revision` | a partial `recorded` row cannot reach the journal file |
| G2 | `round_commit.Commit.add_journal_append` → `require_complete_revision` | a partial `recorded` row cannot enter a commit |
| G3 | `round_records._head_anchor_check` mismatch branch | envelope `headSha` ≠ anchor `headSha` → `head-anchor-mismatch` |
| G4 | each field of `REVISION_IDENTITY_FIELDS` (representative: `citedHead`) | omitting one identity field is refused at both journal sinks |

---

## G1 — `_journal_append` sink check

**Neutralization** (`round_driver.py`):

```python
-    round_records.require_complete_revision(entry)
+    # round_records.require_complete_revision(entry)
```

**Raw red** — `test_recorded_row_missing_identity_refused_at_journal_sinks`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_recorded_row_missing_identity_refused_at_journal_sinks
Failed: DID NOT RAISE <class 'round_records.IncompleteRevisionIdentity'>
1 failed in 3.70s
```

**Restore:** uncommented `round_records.require_complete_revision(entry)`.

**Restore receipt (quoted lines):**

```python
    round_records.require_complete_revision(entry)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.56s
```

---

## G2 — `Commit.add_journal_append` sink check

**Neutralization** (`round_commit.py`):

```python
-        try:
-            round_records.require_complete_revision(entry)
-        except round_records.IncompleteRevisionIdentity as exc:
-            raise CommitRefused("recorded-row-incomplete", ", ".join(exc.missing))
+        # try:
+        #     round_records.require_complete_revision(entry)
+        # except round_records.IncompleteRevisionIdentity as exc:
+        #     raise CommitRefused("recorded-row-incomplete", ", ".join(exc.missing))
```

**Raw red** — same detector, commit-path half:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_recorded_row_missing_identity_refused_at_journal_sinks
Failed: DID NOT RAISE <class 'round_commit.CommitRefused'>
1 failed in 2.74s
```

**Restore:** restored the `try` / `except` block verbatim.

**Restore receipt (quoted lines):**

```python
        try:
            round_records.require_complete_revision(entry)
        except round_records.IncompleteRevisionIdentity as exc:
            raise CommitRefused("recorded-row-incomplete", ", ".join(exc.missing))
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 3.44s
```

---

## G3 — `_anchor_check` head comparison (`head-anchor-mismatch`)

**Neutralization** (`round_records.py` `_head_anchor_check`):

```python
-    if env_head != anchor_head:
-        return "head-anchor-mismatch"
+    if env_head != anchor_head:
+        pass  # return "head-anchor-mismatch"
```

**Raw red** — `test_anchor_check_head_sha_edges`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_anchor_check_head_sha_edges
AssertionError: assert None == 'head-anchor-mismatch'
1 failed in 0.29s
```

**Restore:** restored `return "head-anchor-mismatch"`.

**Restore receipt (quoted lines):**

```python
    if env_head != anchor_head:
        return "head-anchor-mismatch"
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 0.27s
```

---

## G4 — per-field revision identity (`citedHead` representative)

**Neutralization** (`round_records.py` `require_complete_revision`):

```python
-    missing = tuple(field for field in REVISION_IDENTITY_FIELDS if field not in entry)
+    missing = tuple(field for field in REVISION_IDENTITY_FIELDS
+                    if field not in entry and field != "citedHead")
```

**Raw red** — `test_recorded_row_missing_one_identity_field_refused_at_sinks[citedHead]`:

```
FAILED plugins/superheroes/lib/tests/test_recorded_row_chokepoint_1272.py::test_recorded_row_missing_one_identity_field_refused_at_sinks[citedHead]
Failed: DID NOT RAISE <class 'round_records.IncompleteRevisionIdentity'>
1 failed in 3.12s
```

**Restore:** restored the unfiltered `missing = tuple(...)` comprehension.

**Restore receipt (quoted lines):**

```python
    missing = tuple(field for field in REVISION_IDENTITY_FIELDS if field not in entry)
```

**Raw green:**

```
.                                                                        [100%]
1 passed in 2.48s
```
