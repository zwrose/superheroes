# Completion round (#1107) bite-proofs — the detectors this branch owed

Every proof below was **produced and re-run by the orchestrator**, not inherited from an implementer
report. Mutations were applied as targeted revertible edits through the host's edit action (never a
whole-file rewrite, never an ad-hoc shell edit, never a git discard), each reverted by its **inverse
edit**, with `git status --porcelain` confirmed **empty** afterwards.

**Normalization, stated because it changes what the runs mean.** Every command ran under
`-B -X pycache_prefix=/private/tmp/superheroes-pyc` so Apple Python's out-of-tree bytecode cache
(`~/Library/Caches/com.apple.python/`) could not serve stale objects across same-second edits — the
exact shape of every mutation here. Every command also ran **serially**, never under `-n auto`:
`test_handback_gate.py` and `test_interim_receipt.py` prove their guards bite by rewriting
`handback_gate.py` on disk, and under `pytest-xdist` those save/restore cycles interleave and leave
the shipped source mutated with guards disabled. That race is a **known, reproduced defect on `main`**
and is out of scope for this round; these proofs route around it rather than repairing it.

`grep -c 'if False' plugins/superheroes/lib/handback_gate.py` was confirmed **0** after the probe
sequence, and the working tree was confirmed byte-identical to `HEAD`.

**Naming.** These are `BP-CR-*` (completion round). The earlier `BP-C1`/`BP-C2` ids in
`wo_r2_1107.md` are a different round's proofs and are unrelated.

---

## BP-CR-1 — the receipt key partition is total

**Guarded element:** `_receipt_forbidden_keys()` — the derivation that makes *forbidden* mean "absent
from this key's form mapping", so required ∪ optional ∪ forbidden covers every declared key.

**Neutralization:** replaced the derivation body with `return ()`.

**Red run:**
```
>           assert required | optional | forbidden == declared
E           AssertionError: assert {'base', 'bas...egraded', ...} == {'artifacts',...onShape', ...}
E             Extra items in the right set:
E             'stop'  'roster'  'artifacts'  'attestation'
3 failed, 3 passed in 0.13s
```

Three detectors bite: the partition census, the certified optional/forbidden pin, and the
certification-only-key pin.

**Green run after inverse revert:** `6 passed in 0.12s`.

**Limitation, recorded rather than smoothed over:** this mutation is deliberately coarse — it blanks
the whole derivation, so it does not isolate any single detector. BP-CR-2 and BP-CR-3 below carry the
per-element mutations; read this one only as proof that the partition invariant is load-bearing.

---

## BP-CR-2 — the attested validator reads the declaration, not a hand list

**Guarded element:** the `for key in _receipt_forbidden_keys(RECEIPT_FORM_ATTESTED)` loop in the
attested validator — the leg that makes a new certification-only key reject on attested receipts
**without a second edit**.

**Neutralization:** restored the pre-fix shape — a hand-maintained literal tuple
`("certification", "certificationShape", "schemaVersion", "stop")` in place of the derivation. This is
exactly the defect class the declaration closed, reintroduced.

**Red run:**
```
>           assert ok is False, reason
E           AssertionError: None
E           assert True is False
FAILED …::test_one_line_certification_only_key_forbids_attested_and_interim
1 failed, 5 passed in 0.12s
```

The synthetic certification-only key sails through the attested validator once the list is
hand-maintained — a receipt that should have been refused validates. **Exactly one** detector bites,
which is what a smallest-edit-per-guarded-element mutation should produce.

**Green run after inverse revert:** `6 passed`.

---

## BP-CR-3 — each builder strips exactly its forbidden set

**Guarded element:** `build_interim_receipt`'s
`for key in _receipt_forbidden_keys(RECEIPT_FORM_INTERIM): receipt.pop(key, None)` — the loop that
makes the strip-list and the forbid-list *the same object*, so the `:3631` both-ways disagreement
cannot be expressed.

**Neutralization:** restored a hand-maintained strip tuple
`("certification", "certificationShape", "schemaVersion")` — i.e. the same set minus `verdict`.

**Red run:**
```
>       assert forbidden_interim & set(interim) == set()
E       AssertionError: assert {'verdict'} == set()

>           assert stripped == forbidden & set(pre.keys()), (
E           AssertionError: form 'interim': stripped ['certification', 'certificationShape', 'schemaVersion']
E                           != forbidden ['certification', 'certificationShape', 'schemaVersion', 'verdict']
3 failed, 3 passed in 0.13s
```

The strip pin names the drifted key (`verdict`) in its own failure message, so a future divergence
fails with the diagnosis attached rather than as a bare mismatch.

**Green run after inverse revert:** `6 passed in 0.10s`.

---

## BP-CR-4 — the materializer census derives from the production registry

**Guarded element:** `_derive_driver_materialized_round_paths()`'s
`for fn in RD.ROUND_MATERIALIZER_REGISTRY.values()` — the walk that makes a newly registered
materializer appear in the census without anyone remembering to add it.

**Neutralization:** replaced the registry walk with the hand-maintained triple
`(RD._ensure_round_diff, RD._ensure_round_head_diff, RD._ensure_fix_batch_file)`.

**Red run:**
```
>           assert synth_rel in derived
E           AssertionError: assert 'synthetic-registry-probe.json' in frozenset({… 'diff.txt', 'fix-batch.json', 'head.diff', …})
FAILED …::test_materializer_census_derives_from_production_registry
1 failed, 5 passed in 0.11s
```

**Limitation, recorded because it bears on what this proves:** the guarded element here is **test-side
derivation logic**, not production code, so the mutation necessarily edits the test file. That makes
this proof weaker than the production-side proofs above: it shows the derivation axis is load-bearing
(a hand list *is* detected), but it cannot show that production behaviour changes. The production-side
counterpart is BP-CR-5.

**Green run after inverse revert:** `6 passed in 0.11s`.

---

## BP-CR-5 — fix-batch.json round-trips a non-empty batch

**Guarded element:** `_ensure_fix_batch_file`'s read of `state["_fixBatch"]` / `state["fixBatch"]` —
the step that makes the materialized file carry finding ids rather than merely exist.

**Neutralization:** replaced the state read with `batch = []`, so the file is still written, still
valid JSON, and still exists — but empty. This is the precise failure the round-trip test exists to
catch: an artifact whose *existence* check passes while its *content* is gone.

**Red run:**
```
>       assert len(on_disk) == 1
E       assert 0 == 1
E        +  where 0 = len([])
FAILED …::test_fix_batch_file_round_trips_non_empty_batch
1 failed, 5 passed in 0.11s
```

**Green run after inverse revert:** `6 passed in 0.11s`.

---

## BP-CR-6 — v2 certified receipts omit `verifyPasses`

**Guarded element:** `_round_entry_key_allowed()` — the form gate that keeps `verifyPasses` out of a
`receipt-certified/2` even when the round genuinely recorded a non-empty list.

**Neutralization:** replaced the body with `return True`, making every round-entry key allowed on
every form.

**Red run:**
```
>       assert "verifyPasses" not in receipt["rounds"][0]
E       AssertionError: assert 'verifyPasses' not in {'auditProvenance': None, 'audits': None, …}
FAILED …::test_verify_passes_absent_from_certified_v2_with_truthy_list
1 failed, 25 passed in 18.15s
```

The mutation is a genuine fall-open (the gate blesses everything) and exactly one detector catches it.

**Green run after inverse revert:** `26 passed`.

---

## BP-CR-7 — the binding-failure token count pin

**Guarded element:** `test_receipt_bindings_ok_failure_token_count` — the AST count asserting
`_receipt_bindings_ok` has exactly 7 binding-failure returns, so a new token cannot ship without a
disposition.

**Neutralization:** added an eighth failure return to `_receipt_bindings_ok`
(`if receipt.get("_wo1107ProbeKey"): return False, "probe-token"`) — i.e. exactly the
new-enum-member-walks-through-the-old-gate move this pin exists to stop.

**Red run:**
```
>       assert _count_binding_failure_returns(tree) == 7
E       assert 8 == 7
FAILED …::test_receipt_bindings_ok_failure_token_count
1 failed, 9 passed in 1.50s
```

The pin fails **by construction** on an undispositioned member rather than by anyone's recall.

**Green run after inverse revert:** `10 passed`.

---

## BP-CR-8 — every non-`receipt-invalid:` token closes to the allowlisted reason

**Guarded element:** the chokepoint mapping in `_validate_binding` — the branch WO-C1 installed.

**Neutralization:** restored the pre-fix shape exactly — the `verdict-not-allowlisted` special case
plus the bare `return _refuse(bind_why, …)` fall-through that leaked internal tokens.

**Red run:**
```
FAILED …::test_binding_failure_token_surfaces_declared_reason[verdict-mismatch-handback-verdict-not-allowlisted]
FAILED …::test_binding_failure_token_surfaces_declared_reason[no-certification-handback-verdict-not-allowlisted]
FAILED …::test_binding_failure_token_surfaces_declared_reason[no-attestation-handback-verdict-not-allowlisted]
FAILED …::test_binding_failure_fail_closed_edges[None]
FAILED …::test_binding_failure_fail_closed_edges[]
5 failed, 5 passed in 4.45s
```

Five cases bite independently, including **both** fail-closed edges (`None` and `""`) — so the
default-closes-shut property is proven, not assumed. The protected test
`test_handback_gate.py::test_receipt_verdict_mismatch_refuses` also goes red under the same mutation
(`1 failed, 95 passed`), confirming the pre-existing detector and the new census agree.

**Limitation, recorded:** this mutation does **not** turn the interim case red — the old fall-through
happened to pass `receipt-interim-not-handback-evidence` through unchanged, which is why the leak went
unnoticed. The interim branch is covered separately by BP-CR-9.

**Green run after inverse revert:** `10 passed`.

---

## BP-CR-9 — the interim receipt still surfaces its own token

**Guarded element:** the `receipt-interim-not-handback-evidence` branch in the chokepoint — the one
element BP-CR-8's mutation leaves untouched.

**Neutralization:** deleted that three-line branch outright, with `test_interim_receipt.py`
**unedited**. This is the smallest edit that removes exactly one guarded element.

**Red run:**
```
>       assert red["reason"] == "receipt-interim-not-handback-evidence"
E       AssertionError: assert 'handback-ver...t-allowlisted' == 'receipt-inte...back-evidence'
FAILED …::test_bite_public_handback_interim_token
1 failed in 0.70s
```

An interim receipt would refuse handback for the *wrong stated reason* — still fail-safe, but the
operator loses the diagnosis. The detector catches it.

**Green run after inverse revert:** `26 passed` (whole file).

**Note on this detector's own repair.** WO-C1 changed the chokepoint text that this bite-proof
neutralizes by string-replacement, so its search literal stopped matching and `str.replace` silently
no-opped. The test's own `assert patched != src` self-check caught it — a detector refusing to pass
once it can no longer bite. WO-C2 re-pointed the literal at the shipped text; this proof is the
receipt that the repaired detector bites again.

---

## Closing state

After the full probe sequence:

```
git status --porcelain      → (empty)
grep -c 'if False' plugins/superheroes/lib/handback_gate.py   → 0

test_receipt_schema_declaration.py        6 passed
test_order_input_ownership_doc_drift.py   6 passed
test_interim_receipt.py                  26 passed
test_handback_gate_refusal_census.py     10 passed
test_handback_gate.py                    96 passed
```
