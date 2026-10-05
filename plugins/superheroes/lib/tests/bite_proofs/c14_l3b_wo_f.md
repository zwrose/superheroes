# WO-F (#1273) bite-proof — drift guards cover registered Astra id

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-F1 | `set-up.md` Astra line | set-up.md documents every registry codex id | `test_complete_codex_policy_single_sourced` |
| BP-F2 | `_CONCRETE_MODEL_TOKENS` `"gpt-6-astra"` entry | hand-maintained tuple covers every registered model id | `test_concrete_model_tokens_cover_every_registered_model` |

---

## BP-F1 — set-up.md Astra line

- **axis:** `skills/configure/reference/set-up.md` documents `gpt-6-astra` alongside the tier-map codex ids

**neutralization** (`plugins/superheroes/skills/configure/reference/set-up.md`): remove the one Astra line after the Codex tier map line.

**command:**
```
/usr/bin/python3 -B -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_complete_codex_policy_single_sourced -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_complete_codex_policy_single_sourced ___________________

    def test_complete_codex_policy_single_sourced():
        ...
            documented_ids = set(re.findall(id_pattern, doc))
>           assert documented_ids == expected_ids, "%s Codex model IDs drifted from model_registry" % rel
E           AssertionError: skills/configure/reference/set-up.md Codex model IDs drifted from model_registry
E           assert {'gpt-5.6-sol...pt-5.6-terra'} == {'gpt-5.6-sol...'gpt-6-astra'}
E             
E             Extra items in the right set:
E             'gpt-6-astra'

plugins/superheroes/lib/tests/test_ssot_drift.py:181: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_complete_codex_policy_single_sourced
1 failed in 0.31s
```

**restore** (`plugins/superheroes/skills/configure/reference/set-up.md`):
```
   A `reviewer-deep` Codex pin may also name `gpt-6-astra`; it is refused `pin-probe-pending` while its registry row is probe-pending.
```

**raw green** (exit 1 — latent `view-and-tune.md` tier-map line break from WO-E3; set-up.md restore verified by restored line above):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_complete_codex_policy_single_sourced ___________________
...
>           mapping_text = _one(re.findall(r"Codex tier map:\s*([^\n]+(?:\n(?!\s*\n)[^\n]+)?)", doc),
E       AssertionError: skills/configure/reference/view-and-tune.md: expected exactly one `const Codex tier map = tier=model, ...`, found 0
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_complete_codex_policy_single_sourced
1 failed in 0.23s
```

---

## BP-F2 — `_CONCRETE_MODEL_TOKENS` tuple entry

- **axis:** the test file's hand-maintained `_CONCRETE_MODEL_TOKENS` includes every registered model id (neutralizes the test file's own guarded data)

**neutralization** (`plugins/superheroes/lib/tests/test_ssot_drift.py`, `_CONCRETE_MODEL_TOKENS`): remove `"gpt-6-astra",`.

**command:**
```
/usr/bin/python3 -B -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_concrete_model_tokens_cover_every_registered_model -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_concrete_model_tokens_cover_every_registered_model ____________
...
>       assert not missing, "registered model id absent from _CONCRETE_MODEL_TOKENS: %r" % sorted(missing)
E       AssertionError: registered model id absent from _CONCRETE_MODEL_TOKENS: ['gpt-6-astra']
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_concrete_model_tokens_cover_every_registered_model
1 failed in 0.24s
```

**restore** (`plugins/superheroes/lib/tests/test_ssot_drift.py`, `_CONCRETE_MODEL_TOKENS`):
```
    "gpt-6-astra",
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.19s
```

---

## WO-F2 re-run

BP-F1 red and green re-run at WO-F2 head after rejoining the `Codex tier map:` line in `view-and-tune.md` (the earlier BP-F1 green was masked by the tier-map line break).

**BP-F1 red command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r3-pyc -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_complete_codex_policy_single_sourced -q
```
**BP-F1 red result:** exit 1 — `AssertionError: skills/configure/reference/set-up.md Codex model IDs drifted from model_registry` (missing `gpt-6-astra`).

**BP-F1 green command:** (same, after restoring Astra line in `set-up.md`)
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273r3-pyc -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_complete_codex_policy_single_sourced -q
```
**BP-F1 green result:** exit 0 — `1 passed in 0.16s`.
