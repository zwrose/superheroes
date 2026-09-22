# Bite-proof — layer 2e-b clamp-exact legacy-key collision (#1272)

Declared guarded-element set (exactly three, proven separately):

1. `legacy_key_collision`'s **claimant predicate** — `entry[0] == bare`.
2. `legacy_key_collision`'s **global minted-key guard** — `if minted in identity_keys` on each legacy bare-key pair.
3. `legacy_key_collision`'s **pair-disagreement leg** — `(identity, minted) != (ref_identity, ref_minted)` (content is not an identity discriminator).

Fail-direction control for all three: `test_e12_same_finding_duplicate_no_collision` stays green under each neutralization.

Production file `lib/session_contract.py` is byte-identical to pre-dispatch state after all proofs (neutralizations restored by inverse edit).

---

## Element 1 — claimant predicate

**Guarded element.** `session_contract.legacy_key_collision`, `claimants = [entry for entry in entries if entry[0] == bare]`.
**Axis:** a row whose stored identity equals the shared bare key is treated as a legacy bare-key claimant.

**Neutralization.** → `claimants = [entry for entry in entries if False and entry[0] == bare]`.

**Detector.** `test_layer2e_ledger_evidence_1272.py::test_e9_clamp_exact_long_short_pair_refuses_certification` (e9).

**Red** (EXIT=1, scoped pytest — detector node only):

```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 1 item

plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e9_clamp_exact_long_short_pair_refuses_certification FAILED [100%]

=================================== FAILURES ===================================
__________ test_e9_clamp_exact_long_short_pair_refuses_certification ___________
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py:222: in test_e9_clamp_exact_long_short_pair_refuses_certification
    assert by_key == {}
E   AssertionError: assert {'f.py::xxxxx... 'f.py', ...}} == {}
E     
E     Left contains 1 more item:
E     {'f.py::xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@L5': {'disposition': 'fixed',
E                                                                                                                                                                                 'dispositionRound': 1,
E                                                                                                                                                                                 'file': 'f.py',
E       ...
E     
E     ...Full output truncated (18 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e9_clamp_exact_long_short_pair_refuses_certification
============================== 1 failed in 0.10s ===============================
```

Elision: pytest truncated 18 lines of the long bare-key dict diff from the failure banner (bounded raw capture).

**Fail-direction control (e12).** Green under this neutralization — scoped pytest `test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision`:

```
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision PASSED [100%]
1 passed in 0.06s
```

**Restore.** Inverse edit: `False and` removed from claimant predicate.

**Restore receipt.** `git status --porcelain plugins/superheroes/lib/session_contract.py` → empty.

**Green** (EXIT=0, full module after restore):

```
26 passed in 0.08s
```

---

## Element 2 — global minted-key guard

**Guarded element.** `session_contract.legacy_key_collision`, `if minted in identity_keys:` inside the `legacy_pairs` loop.
**Axis:** a legacy bare-keyed row's derived minted key claimed globally by another row's stored identity refuses even when the claimant rows do not share a bare location key.

**Neutralization.** → `if False and minted in identity_keys:`.

**Detector.** `test_layer2e_ledger_evidence_1272.py::test_e11b_cross_location_minted_key_claimant_refuses` (e11b).

**Red** (EXIT=1, scoped pytest — detector node only):

```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 1 item

plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e11b_cross_location_minted_key_claimant_refuses FAILED [100%]

=================================== FAILURES ===================================
_____________ test_e11b_cross_location_minted_key_claimant_refuses _____________
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py:286: in test_e11b_cross_location_minted_key_claimant_refuses
    assert by_key == {}
E   AssertionError: assert {'f.py::xxxxx...ortant', ...}} == {}
E     
E     Left contains 2 more items:
E     {'f.py::xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx@L5': {'disposition': 'fixed',
E                                                                                                                                                                                 'dispositionRound': 1,
E                                                                                                                                                                                 'file': 'f.py',
E      ...
E     
E     ...Full output truncated (34 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e11b_cross_location_minted_key_claimant_refuses
============================== 1 failed in 0.07s ===============================
```

Elision: pytest truncated 34 lines of the long bare/minted-key dict diff from the failure banner (bounded raw capture).

**Fail-direction control (e12).** Green under this neutralization — scoped pytest `test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision`:

```
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision PASSED [100%]
1 passed in 0.06s
```

**Restore.** Inverse edit: `False and` removed from global minted-key guard.

**Restore receipt.** `git status --porcelain plugins/superheroes/lib/session_contract.py` → empty.

**Green** (EXIT=0, full module after restore):

```
26 passed in 0.08s
```

---

## Element 3 — pair-disagreement leg

**Guarded element.** `session_contract.legacy_key_collision`, `if (identity, minted) != (ref_identity, ref_minted):`.
**Axis:** rows sharing a bare key with a legacy claimant must agree on the stored-identity and minted pair; content drift is not an identity discriminator.

**Neutralization.** → `if False and (identity, minted) != (ref_identity, ref_minted):`.

**Detector.** `test_layer2e_ledger_evidence_1272.py::test_e10_clamp_exact_long_short_pair_helper_refuses` (e10).

**Red** (EXIT=1, scoped pytest — detector node only):

```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
collecting ... collected 1 item

plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e10_clamp_exact_long_short_pair_helper_refuses FAILED [100%]

=================================== FAILURES ===================================
_____________ test_e10_clamp_exact_long_short_pair_helper_refuses ______________
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py:241: in test_e10_clamp_exact_long_short_pair_helper_refuses
    assert collision is not None
E   assert None is not None
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e10_clamp_exact_long_short_pair_helper_refuses
============================== 1 failed in 0.07s ===============================
```

**Fail-direction control (e12).** Green under this neutralization — scoped pytest `test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision`:

```
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e12_same_finding_duplicate_no_collision PASSED [100%]
1 passed in 0.06s
```

**Content non-discriminator control (e11).** Green under this neutralization — scoped pytest `test_layer2e_ledger_evidence_1272.py::test_e11_same_bare_and_minted_different_content_not_collision`:

```
plugins/superheroes/lib/tests/test_layer2e_ledger_evidence_1272.py::test_e11_same_bare_and_minted_different_content_not_collision PASSED [100%]
1 passed in 0.06s
```

**Restore.** Inverse edit: `False and` removed from pair comparison.

**Restore receipt.** `git status --porcelain plugins/superheroes/lib/session_contract.py` → empty.

**Green** (EXIT=0, full module after restore):

```
26 passed in 0.08s
```
