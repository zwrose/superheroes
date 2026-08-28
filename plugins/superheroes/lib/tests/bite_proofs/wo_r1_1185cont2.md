# Continuation-2 review round 1 (#1185) bite-proofs — the version-spelling census, re-proved on the final head

The auto-fix round of the certified loop (commit `e57d5000`, finding `v5`) **widened two axes of the
`test_state_version_spelling_census` detector**: the comparison leg now resolves per-scope local
aliases, and the constant-assignment leg now recognises qualified attribute targets. A detector that
changed is a detector whose proofs are stale, so every leg is re-run here **on the final head**, and
the two newly-covered forms get proofs of their own.

Orchestrator-produced (the census fix was implemented by the loop's cursor fixer; the proofs and this
record are the orchestrator's, per the charter's verification rule that the orchestrator re-runs every
receipt itself). Every neutralization was applied as a targeted revertible edit through the host's
edit action and reverted immediately after its red run; the landed work was committed **before** any
probe ran, and `git status --porcelain` plus `git diff --stat` were both **empty** after the last
restore.

**Command (every leg):**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_state_version_spelling_census.py -q
```

**Final green run on the restored tree (exit 0):**
```
...................                                                      [100%]
19 passed in 4.40s
```

---

## BP-C1 — mod-format

**Guarded element:** `census_module` / `_scan_mod_format` — axis: no hand-spelled integer in
`RECEIPT_CERTIFIED_SCHEMA % …` outside the pinned version path.

**Neutralization:** `return RECEIPT_CERTIFIED_SCHEMA % _receipt_version(state)` →
`return RECEIPT_CERTIFIED_SCHEMA % 99` at `plugins/superheroes/lib/round_driver.py:235`.

**Red run (exit 1):**
```
E       AssertionError: hand-spelled state/receipt version sites:
E           round_driver.py:235 [mod-format] 'RECEIPT_CERTIFIED_SCHEMA % 99' — mod-format
E       assert not [Finding(relpath='round_driver.py', line=235, segment='RECEIPT_CERTIFIED_SCHEMA % 99', leg='mod-format')]
1 failed, 18 passed in 4.49s
```

**Restore:** inverse edit back to `RECEIPT_CERTIFIED_SCHEMA % _receipt_version(state)`.

---

## BP-C2a — comparison, read directly in the operand

**Guarded element:** `census_module` / `_scan_comparisons` — axis: no hand-spelled integer compared
to a `schemaVersion` read appearing syntactically inside the comparison operand.

**Neutralization:** `if _state_version(loaded) != STATE_SCHEMA_VERSION:` →
`if loaded.get("schemaVersion") == 99:` at `plugins/superheroes/lib/round_driver.py:5049`.

**Red run (exit 1):**
```
E           round_driver.py:5049 [comparison] 'loaded.get("schemaVersion") == 99' — comparison
E       assert not [Finding(relpath='round_driver.py', line=5049, segment='loaded.get("schemaVersion") == 99', leg='comparison')]
1 failed, 18 passed in 4.43s
```

---

## BP-C2b — comparison through a local alias (the axis the fix added)

**Guarded element:** `census_module` / `_scan_comparisons` + `_schema_version_aliases_in_scope` —
axis: a `schemaVersion` read **bound to a local first** and compared on a later line is reported.
This is the exact form review finding `v5` demonstrated the detector could not see; the proof is
its fail-direction receipt, taken in the **real channel** (an edit to shipped `round_driver.py`,
not a synthetic source string handed to `census_module`).

**Neutralization:** at `plugins/superheroes/lib/round_driver.py:5049`, replaced the guarded
comparison with the two-line aliased form:
```
    _bp_version = loaded.get("schemaVersion")
    if _bp_version == 99:
```

**Red run (exit 1):**
```
E           round_driver.py:5050 [comparison] '_bp_version == 99' — comparison
E       assert not [Finding(relpath='round_driver.py', line=5050, segment='_bp_version == 99', leg='comparison')]
1 failed, 18 passed in 4.43s
```

**Restore:** inverse edit back to `if _state_version(loaded) != STATE_SCHEMA_VERSION:`.

---

## BP-C3 — binding

**Guarded element:** `census_module` / `_scan_bindings` — axis: no hand-spelled integer bound to
`schemaVersion`.

**Neutralization:** `"schemaVersion": STATE_SCHEMA_VERSION,` → `"schemaVersion": 99,` at
`plugins/superheroes/lib/round_driver.py:1198`.

**Red run (exit 1):**
```
E       assert not [Finding(relpath='round_driver.py', line=1198, segment='"schemaVersion": 99', leg='binding')]
1 failed, 18 passed in 4.47s
```

**Restore:** inverse edit back to `"schemaVersion": STATE_SCHEMA_VERSION,`.

---

## BP-C4a — constant-assignment, bare name target

**Guarded element:** `census_module` / `_scan_constant_assignments` — axis: a pinned version symbol
may be assigned only inside the marker-delimited block.

**Neutralization:** inserted `STATE_SCHEMA_VERSION = 99` immediately **after** the pinned
declaration block END marker at `plugins/superheroes/lib/round_driver.py:152`.

**Red run (exit 1):** two tests fail — the census leg, and the prose leg (which is doing its job:
the rebound constant no longer matches the documented value).
```
E       AssertionError: hand-spelled state/receipt version sites:
E           round_driver.py:152 [constant-assignment] 'STATE_SCHEMA_VERSION = 99' — constant-assignment
E       assert not [Finding(relpath='round_driver.py', line=152, segment='STATE_SCHEMA_VERSION = 99', leg='constant-assignment')]
E       AssertionError: prose leg: round-driver.md states STATE_SCHEMA_VERSION=4 but round_driver.STATE_SCHEMA_VERSION=99
E       assert not ['prose leg: round-driver.md states STATE_SCHEMA_VERSION=4 but round_driver.STATE_SCHEMA_VERSION=99']
2 failed, 17 passed in 4.61s
```

---

## BP-C4b — constant-assignment, qualified attribute target (the axis the fix added)

**Guarded element:** `census_module` / `_scan_constant_assignments` — axis: a pinned version symbol
rebound through a **qualified attribute target** outside the pinned block is reported. Before the
fix, only `ast.Name` targets counted, so this form passed silently.

**Neutralization:** at the same site, `os.STATE_SCHEMA_VERSION = 99` (an attribute target that is
importable, so the census's own module import still succeeds — an unimportable stand-in would have
made the run fail for the wrong reason, and the first attempt with an undefined name did exactly
that: `NameError: name '_bp_mod' is not defined`, recorded here rather than hidden).

**Red run (exit 1):**
```
E       AssertionError: hand-spelled state/receipt version sites:
E           round_driver.py:152 [constant-assignment] 'os.STATE_SCHEMA_VERSION = 99' — constant-assignment
E       assert not [Finding(relpath='round_driver.py', line=152, segment='os.STATE_SCHEMA_VERSION = 99', leg='constant-assignment')]
1 failed, 18 passed in 4.52s
```

**Restore:** the inserted line removed; the END marker is again immediately followed by
`RECEIPT_FORM_CERTIFIED = "certified"`.

---

## BP-C5 — string-literal, embedded in a longer string

**Guarded element:** `census_module` / `_scan_string_literals` — axis: no `receipt-certified/N`
literal outside the pinned spelling path, **including one embedded inside a longer string** (the
cross-line form WO-G's regression tests added).

**Neutralization:** appended to `plugins/superheroes/lib/handback_gate.py`:
`_BP_SYNTH = "the receipt-certified/9 form is embedded inside a longer sentence"`.

**Red run (exit 1):**
```
E           handback_gate.py:1077 [string-literal] '"the receipt-certified/9 form is embedded inside a longer sentence"' — string-literal
1 failed, 18 passed in 4.41s
```

**Restore:** the appended line removed; `handback_gate.py` again ends at its `_allow(...)` return.

---

## BP-C6 — prose

**Guarded element:** `census_prose` — axis: `round-driver.md` states the same
`STATE_SCHEMA_VERSION` as `round_driver`.

**Neutralization:** `(`STATE_SCHEMA_VERSION` = 4) emits 4.` → `(`STATE_SCHEMA_VERSION` = 3) emits 3.`
at `plugins/superheroes/skills/review-code/reference/round-driver.md:700`.

**Red run (exit 1):**
```
E       AssertionError: prose leg: round-driver.md states STATE_SCHEMA_VERSION=3 but round_driver.STATE_SCHEMA_VERSION=4
E       assert not ['prose leg: round-driver.md states STATE_SCHEMA_VERSION=3 but round_driver.STATE_SCHEMA_VERSION=4']
1 failed, 18 passed in 4.51s
```

**Restore:** inverse edit back to `= 4) emits 4.`

---

## What this record does not cover

- The **doc deletion** at `round-driver.md:218` (this continuation's authorized one-line change) adds
  and changes **no detector** — the drift test that guards the fenced `_provenance` block is
  unchanged, and its own proof stands in the earlier records. Its receipts are the drift test
  (`11 passed`) and `validate_skills.py` (exit 0), both re-run by the orchestrator.
- **BP-R5** (`max_count` allowlist budget) and **BP-R6** (duplicate-field guard) remain **UNPROVEN**
  exactly as `wo_review_1185.md` discloses; the review round independently re-found both as Minor
  findings (`v6`, `v7`) and the loop's terminal certification carries them as disclosed residuals.
  They are unchanged by this continuation, not newly unproven.
