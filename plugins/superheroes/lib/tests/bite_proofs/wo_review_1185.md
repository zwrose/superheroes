# Review-round detectors (#1185) — orchestrator bite-proofs on the FINAL head

Every proof below was run by the **orchestrator** on the final head `d2e1baaf`, after the certified
loop terminated. Each neutralization was applied as a targeted edit through the host's edit action
and reverted with the inverse edit; `git status --porcelain` was empty before and after.

This record covers the detector elements the **review rounds** added (the census legs, the allowlist
budget, and the two owner-provenance guards). The build's own work orders keep their records in
`wo_a_1185.md`, `wo_b_1185.md`, `wo_d_1185.md`, `wo_f_1185.md`, `wo_g_1185.md`, `wo_h_1185.md`.

Two elements are recorded **UNPROVEN** with the cause named — see BP-R5 and BP-R6. Nothing here is
claimed as proven that was not observed red.

---

## BP-R1 — comparison and binding legs run on modules with no pinned-symbol reference

Re-run of `wo_g_1185.md` BP-G1 on the final head (the detector-narrowing staleness rule: every proof
is re-run on the head that ships).

**Guarded element:** `census_module` comparison/binding legs — axis: a module that hand-spells the
version WITHOUT naming a pinned symbol is still reported.

**Neutralization:** re-gated both legs behind `refs_pinned` in `census_module`
(`plugins/superheroes/lib/tests/test_state_version_spelling_census.py`).

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_no_pinned_symbol_module \
  -q --tb=line
```

**Red run (exit 1):**
```
F                                                                        [100%]
=================================== FAILURES ===================================
.../test_state_version_spelling_census.py:748: AssertionError: comparison leg must run on a module with no pinned-symbol reference
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_no_pinned_symbol_module
1 failed in 0.11s
```

**Green after inverse edit (exit 0):** included in the closing all-green run below.

---

## BP-R2 — string-literal leg finds an EMBEDDED `receipt-certified/<n>`

Re-run of `wo_g_1185.md` BP-G2 on the final head.

**Guarded element:** `_scan_string_literals` / `_RECEIPT_CERTIFIED_LITERAL_RE` — axis: the literal is
found inside a longer string, not only as a whole-string match.

**Neutralization:** `.search(node.value)` → `.fullmatch(node.value)`.

**Red run (exit 1):**
```
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_embedded_string_literal
1 failed in 0.12s
```

**Green after inverse edit (exit 0):** included in the closing all-green run below.

---

## BP-R3 — binding leg recognizes `get` / `setdefault` schema-version defaults

Added by the review's round-1 and round-2 fix legs; no record existed until now.

**Guarded element:** `_scan_bindings` call branch — axis: `x.get("schemaVersion", <int>)` and
`x.setdefault("schemaVersion", <int>)` are reported as bindings.

**Neutralization:** `func.attr in ("get", "setdefault")` → `func.attr in ("update",)`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_get_default_binding \
  plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_setdefault_binding \
  -q --tb=line
```

**Red run (exit 1) — both elements die, so each leg is separately load-bearing:**
```
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_get_default_binding
FAILED plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_setdefault_binding
2 failed in 0.11s
```

**Green after inverse edit (exit 0):** included in the closing all-green run below.

---

## BP-R4 — constant-assignment leg recognizes an ANNOTATED pinned-symbol assignment

**Guarded element:** `_scan_constant_assignments` `ast.AnnAssign` arm — axis:
`STATE_SCHEMA_VERSION: int = 99` outside the pinned block is reported.

**Neutralization:** `elif isinstance(node, ast.AnnAssign):` → `elif isinstance(node, ast.NamedExpr):`.

**Red run (exit 1):**
```
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_state_version_spelling_census.py::test_synthetic_injection_ann_assign_constant
1 failed in 0.11s
```

**Green after inverse edit (exit 0):** included in the closing all-green run below.

---

## BP-R5 — allowlist `max_count` budget — **UNPROVEN**

**Guarded element:** `_unexpected_findings`'s per-key `max_count` budget (default 1) — axis: when
more live sites share one `(relpath, segment)` allowlist key than the budget allows, the extras are
reported instead of silently exempted. Added by the review's round-1 fix leg.

**Neutralization:** `max_count = _SPELLING_ALLOWLIST[key].get("max_count", 1)` → `max_count = 10 ** 6`,
so no group can ever exceed its budget.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_state_version_spelling_census.py -q --tb=line
```

**Status: UNPROVEN.** With the budget neutralized the **whole file stayed green** (exit 0,
`17 passed in 2.95s`). No committed test exercises the budget leg, so reverting it would not be
caught. This reproduces, on the final head, exactly what the round-1 audit seat reported as its new
issue 1.

**Why no test was added:** the third-rework tripwire had already fired on
`test_state_version_spelling_census.py` (four patches in this build). Adding one here would be the
fifth. Shipped as a disclosed follow-up. The probe was reverted before leaving the worktree.

---

## BP-R6 — duplicate-provenance-field guard — **UNPROVEN**

**Guarded element:** `_parse_provenance_field_shapes`'s duplicate-field check — axis: a second,
contradictory `ruledBy — …` line in the doc's fenced block raises instead of being silently
overwritten by last-write-wins. Added by the review's round-1 fix leg.

**Neutralization:** removed the `if field in pairs: raise RuntimeError(...)` branch.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_round_driver_owner_artifact_vocabulary_sync.py -q --tb=line
```

**Status: UNPROVEN.** With the guard removed the file stayed green (exit 0, `11 passed in 0.11s`).
The guard fires only against a doc that actually carries a duplicate field, and no committed test
constructs that doc; the round-2 audit seat verified the behaviour by its own reading, but reverting
the guard is not caught by the suite.

**A note on why the detector-unedited form was not used here:** injecting a duplicate line into the
real fenced block also makes the block disagree with `OWNER_PROVENANCE_FIELD_SHAPES`, so
`test_owner_provenance_field_shapes_match_docs` goes red either way — the duplicate axis cannot be
isolated without a synthetic-document fixture, which is the shape the follow-up should take. Probe
reverted.

---

## BP-R7 — the documented gate-artifact example is not submittable

**Guarded element:** `test_gate_artifact_example_provenance_is_not_submittable` — axis: the worked
`_provenance` example in `round-driver.md` must NOT satisfy
`round_driver._owner_artifact_provenance_well_formed`, so a caller who pastes it unchanged cannot
falsely journal `owner-supplied`.

**Neutralization:** made the documented example submittable — replaced the three `null` values with
`"the owner"` / `"2026-01-01T00:00:00Z"` / `["https://example.invalid/ruling"]` in
`plugins/superheroes/skills/review-code/reference/round-driver.md`.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_round_driver_owner_artifact_vocabulary_sync.py::test_gate_artifact_example_provenance_is_not_submittable \
  -q --tb=line
```

**Red run (exit 1):**
```
.../test_round_driver_owner_artifact_vocabulary_sync.py:182: AssertionError: assert not True
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_driver_owner_artifact_vocabulary_sync.py::test_gate_artifact_example_provenance_is_not_submittable
1 failed in 0.10s
```

**Partial-neutralization note (recorded because it changes what the proof means):** setting only
`ruledBy` non-null left the test **green** (exit 0) — the validator requires all three fields, so the
detector bites on the artifact as a whole, not per field. The red above is the all-three form.

**Green after inverse edit (exit 0):** included in the closing all-green run below.

---

## Closing all-green run, every probe reverted

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_state_version_spelling_census.py \
  plugins/superheroes/lib/tests/test_round_driver_owner_artifact_vocabulary_sync.py \
  plugins/superheroes/lib/tests/test_state_version_rollback.py -q --tb=line
......................................                                   [100%]
38 passed in 11.26s
```

`git status --porcelain` empty; `git rev-parse HEAD` = `d2e1baaf9e5e77887ee8f6a99914ff6b65d18d3a`.
