# Bite-proof — layer 2e-b clamp-exact legacy-key collision (#1272)

Declared guarded-element set (exactly two, proven separately):

1. `legacy_key_collision`'s **claimant predicate** — `entry[0] == bare`.
2. `legacy_key_collision`'s **triple-disagreement leg** — `(identity, minted, content) != ref`.

Fail-direction control for both: `test_e12_same_finding_duplicate_no_collision` stays green under each neutralization.

---

## Element 1 — claimant predicate

**Guarded element.** `session_contract.legacy_key_collision`, `claimants = [entry for entry in entries if entry[0] == bare]`.
**Axis:** a row whose stored identity equals the shared bare key is treated as a legacy bare-key claimant.

**Neutralization.** → `claimants = [entry for entry in entries if False and entry[0] == bare]`.

**Detector.** `test_e9_clamp_exact_long_short_pair_refuses_certification` (e9).

**Red** (EXIT=1) — decisive lines:

```
>       assert by_key == {}
E       AssertionError: assert {'f.py::xxxxx...xxx@L5', ...}} == {}
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e9_clamp_exact_long_short_pair_refuses_certification
```

**Fail-direction control (e12).** Green under this neutralization (included in same run: 17 passed).

**Restore.** Inverse edit: `False and` removed from claimant predicate.

**Restore receipt.** Restored line: `claimants = [entry for entry in entries if entry[0] == bare]`.

**Green** (EXIT=0): `25 passed in 0.20s`.

---

## Element 2 — triple-disagreement leg

**Guarded element.** `session_contract.legacy_key_collision`, `if (identity, minted, content) != ref:`.
**Axis:** rows sharing a bare key with a legacy claimant must agree on the stored-identity, minted, and content triple.

**Neutralization.** → `if False and (identity, minted, content) != ref:`.

**Detector.** `test_e11_same_bare_and_minted_different_content_refuses` (e11).

**Red** (EXIT=1) — decisive lines:

```
>       assert collision is not None
E       assert None is not None
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e11_same_bare_and_minted_different_content_refuses
```

**Fail-direction control (e12).** Green under this neutralization (included in same run: 17 passed).

**Restore.** Inverse edit: `False and` removed from triple comparison.

**Restore receipt.** Restored line: `if (identity, minted, content) != ref:`.

**Green** (EXIT=0): `25 passed in 0.22s`.
