# Bite-proof — layer 2e-b clamp-exact legacy-key collision (#1272)

Declared guarded-element set (exactly three, proven separately):

1. `legacy_key_collision`'s **claimant predicate** — `entry[0] == bare`.
2. `legacy_key_collision`'s **global minted-key guard** — `if minted in identity_keys` on each legacy bare-key pair.
3. `legacy_key_collision`'s **pair-disagreement leg** — `(identity, minted) != (ref_identity, ref_minted)` (content is not an identity discriminator).

Fail-direction control for all three: `test_e12_same_finding_duplicate_no_collision` stays green under each neutralization.

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

**Green** (EXIT=0): `26 passed in 0.21s`.

---

## Element 2 — global minted-key guard

**Guarded element.** `session_contract.legacy_key_collision`, `if minted in identity_keys:` inside the `legacy_pairs` loop.
**Axis:** a legacy bare-keyed row's derived minted key claimed globally by another row's stored identity refuses even when the claimant rows do not share a bare location key.

**Neutralization.** → `if False and minted in identity_keys:`.

**Detector.** `test_e11b_cross_location_minted_key_claimant_refuses` (e11b).

**Red** (EXIT=1) — decisive lines:

```
>       assert by_key == {}
E       AssertionError: assert {'f.py::xxxxx...xxx@L5', ...}} == {}
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e11b_cross_location_minted_key_claimant_refuses
```

**Fail-direction control (e12).** Green under this neutralization (included in same run: 17 passed).

**Restore.** Inverse edit: `False and` removed from global minted-key guard.

**Restore receipt.** Restored line: `if minted in identity_keys:`.

**Green** (EXIT=0): `26 passed in 0.21s`.

---

## Element 3 — pair-disagreement leg

**Guarded element.** `session_contract.legacy_key_collision`, `if (identity, minted) != (ref_identity, ref_minted):`.
**Axis:** rows sharing a bare key with a legacy claimant must agree on the stored-identity and minted pair; content drift is not an identity discriminator.

**Neutralization.** → `if False and (identity, minted) != (ref_identity, ref_minted):`.

**Detector.** `test_e10_clamp_exact_long_short_pair_helper_refuses` (e10).

**Red** (EXIT=1) — decisive lines:

```
>       assert collision is not None
E       assert None is not None
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e10_clamp_exact_long_short_pair_helper_refuses
```

**Fail-direction control (e12).** Green under this neutralization (included in same run: 17 passed).

**Content non-discriminator control (e11).** `test_e11_same_bare_and_minted_different_content_not_collision` stays green under this neutralization — body/severity drift alone must not refuse.

**Restore.** Inverse edit: `False and` removed from pair comparison.

**Restore receipt.** Restored line: `if (identity, minted) != (ref_identity, ref_minted):`.

**Green** (EXIT=0): `26 passed in 0.21s`.
