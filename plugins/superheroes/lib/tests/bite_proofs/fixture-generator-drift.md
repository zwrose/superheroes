# Bite-proof record — WO-P4-A (certification fixture generator drift test)

Contract: `rubric/bite-proof.md`. Proof ran with the **detector unedited**; neutralization was a
targeted, reversible extra key in a checked-in fixture file, reverted by exact inverse before the
green half.

## Detector — `test_generated_certification_fixtures_match_producer`

**Guarded element.** `plugins/superheroes/lib/tests/test_round_certification_fixture_generator_drift.py` —
tree compare of `fixtures/round_certification_generated/` against `regenerate_all` output.
**Axis.** A checked-in fixture that no longer matches what the production generator would write must
fail without editing the test.

**Neutralization** (added key to checked-in fixture
`fixtures/round_certification_generated/policy-and-base/meta.json`):

```json
"biteProofPlant": true
```

**Raw red** — `PYTEST_EXIT=1`:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_generated_certification_fixtures_match_producer _____________

    def test_generated_certification_fixtures_match_producer():
        scratch = tempfile.mkdtemp(prefix="rc-fixture-drift-")
        try:
            regenerate_all(scratch)
            if not _compare_trees(GENERATED_ROOT, scratch):
                missing = sorted(set(os.listdir(scratch)) - set(os.listdir(GENERATED_ROOT)))
                extra = sorted(set(os.listdir(GENERATED_ROOT)) - set(os.listdir(scratch)))
>               raise AssertionError(
                    "generated certification fixtures drifted from producer; "
                    "regenerate with: cd plugins/superheroes/lib && "
                    "/usr/bin/python3 -B tests/generate_round_certification_fixtures.py "
                    "(missing in checked-in tree: %s; extra: %s)"
                    % (missing, extra))
E                   AssertionError: generated certification fixtures drifted from producer; regenerate with: cd plugins/superheroes/lib && /usr/bin/python3 -B tests/generate_round_certification_fixtures.py (missing in checked-in tree: []; extra: [])

plugins/superheroes/lib/tests/test_round_certification_fixture_generator_drift.py:29: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification_fixture_generator_drift.py::test_generated_certification_fixtures_match_producer
1 failed in 0.17s
```

**Restore.** Removed the `"biteProofPlant": true` entry from
`fixtures/round_certification_generated/policy-and-base/meta.json`; restored lines:

```json
{"headSha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "mode": "branch", "sessionId": "test-session-001"}
```

**Restore receipt.** The planted key is absent from the checked-in `meta.json`; no other fixture
files were touched.

**Raw green** — `PYTEST_EXIT=0`:

```
.                                                                        [100%]
1 passed in 0.16s
```
