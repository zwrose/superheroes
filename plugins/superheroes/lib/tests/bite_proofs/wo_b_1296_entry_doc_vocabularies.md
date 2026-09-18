# WO-B (#1296) bite-proof — dispatch entry doc declared vocabularies

**Provenance:** cursor / composer-2.5

Re-take of S10 (`dispatch_entry_doc.py --check` and cross-process determinism) against the new
Declared vocabularies sections.

## Guarded elements

| ID | Guarded element | Axis | Proving detector |
|---|---|---|---|
| BP-B-1 | `dispatch_entry_doc.py --check` vs `resolved_inputs_vocab.SOURCE_MARKERS` | committed doc stale when vocabulary home drifts without regeneration | `dispatch_entry_doc.py --check` |
| BP-B-2 | `dispatch_entry_doc.py --check` vs `seat_bundle.ENTRY_REFUSAL_REASONS` | committed doc stale when vocabulary home drifts without regeneration | `dispatch_entry_doc.py --check` |

---

## BP-B-1 — SOURCE_MARKERS drift refuses at --check

- **axis:** committed doc stale when `resolved_inputs_vocab.SOURCE_MARKERS` drifts without regeneration

**neutralization** (`plugins/superheroes/lib/resolved_inputs_vocab.py`, `SOURCE_MARKERS`):
```python
    TEMP_DIRECTORY,
    "bite-proof-throwaway",
})
```

**command:**
```
/usr/bin/python3 -B plugins/superheroes/lib/dispatch_entry_doc.py --check
```

**raw red** (exit 1):
```
dispatch_entry_doc error: /private/tmp/wh1296-b/plugins/superheroes/skills/workhorse/reference/dispatch-entry.md is stale — run the generator
```

**restore** (`plugins/superheroes/lib/resolved_inputs_vocab.py`, `SOURCE_MARKERS`):
```python
    TEMP_DIRECTORY,
})
```

**raw green:**
```
/private/tmp/wh1296-b/plugins/superheroes/skills/workhorse/reference/dispatch-entry.md: ok
```

**restore receipt** (`git status --porcelain` after inverse edit):
```
(no bite-proof-throwaway in tree; resolved_inputs_vocab.py matches pre-plant state)
```

---

## BP-B-2 — ENTRY_REFUSAL_REASONS drift refuses at --check

- **axis:** committed doc stale when `seat_bundle.ENTRY_REFUSAL_REASONS` drifts without regeneration

**neutralization** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    "verb-role-mismatch",
    "bite-proof-throwaway",
})
```

**command:**
```
/usr/bin/python3 -B plugins/superheroes/lib/dispatch_entry_doc.py --check
```

**raw red** (exit 1):
```
dispatch_entry_doc error: /private/tmp/wh1296-b/plugins/superheroes/skills/workhorse/reference/dispatch-entry.md is stale — run the generator
```

**restore** (`plugins/superheroes/lib/seat_bundle.py`, `ENTRY_REFUSAL_REASONS`):
```python
    "verb-role-mismatch",
})
```

**raw green:**
```
/private/tmp/wh1296-b/plugins/superheroes/skills/workhorse/reference/dispatch-entry.md: ok
```

**restore receipt** (`git status --porcelain` after inverse edit):
```
 M plugins/superheroes/lib/dispatch_entry_doc.py
 M plugins/superheroes/lib/dispatch_selftest.py
 M plugins/superheroes/lib/engine_adapter.py
 M plugins/superheroes/lib/tests/test_dispatch_entry_doc.py
 M plugins/superheroes/skills/workhorse/reference/dispatch-entry.md
```
(no `bite-proof-throwaway` member; vocabulary homes restored)
