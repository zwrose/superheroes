# WO-1 (#1910) bite-proof — a review with zero verified survivors folds synthesis without dispatching it

**Provenance:** claude / sonnet-5.5 (implementer, WO-1, continuation dispatch), `plugins/superheroes/lib/round_driver.py` (`_fold_verifiers`), `decision_kinds.py`, `skills/review-code/reference/round-driver.md`; tests in `plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py` and `test_round_driver_advance.py`.

Declared guarded-element set (from the order): **B1** and **B2**. Each was neutralized by one targeted edit (the Edit tool, exact-text match), the single detector selection run, the inverse edit applied, and the selection run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. The sha256 of each neutralized file was taken before and after the round trip.

## Guarded elements

| ID | Guarded element | Axis | Proving nodes |
|---|---|---|---|
| B1 | the zero-survivor skip branch (`round_driver.py` `_fold_verifiers`, `if not state["_verified"]:`) | a round with no survivors emits no synthesis order and folds to its next step | `test_synthesis_no_survivors_1910.py::test_t1_a_panel_with_no_findings_folds_synthesis_and_converges_on_advance`, `::test_t2_a_round_whose_every_finding_is_refuted_never_offers_synthesis` |
| B2 | the durable-path refusal of an unauthenticated synthesis landing (`round_adapters.py` `_assemble`, `P_SYNTHESIS` branch, `if fault is not None: return None, fault`) | an empty grouping landed without runner evidence, while survivors exist, refuses rather than folding | `test_synthesis_no_survivors_1910.py::test_t4_a_durable_empty_grouping_without_execution_evidence_is_refused` |

## Disclosures

- Both elements went red under their neutralization (pytest exit 1) and green after the restore (exit 0).
- T3 (`test_t3_…`) is a survivors-kept guard on E3/E4 and is not selected by any B1/B2 command; it is green in the whole-file run and was not separately neutralized, so it carries no bite-proof of its own here.
- The `UV_NATIVE_TLS` deprecation warning line that `scripts/pinned-python` prints before each pytest capture is omitted below; everything else is verbatim (default `--tb`, no filter).
- Both captures are well under 32 KiB, so none is written off-repo.

---

## B1 — the zero-survivor skip branch (`round_driver.py` `_fold_verifiers`)

- **axis:** a round with no survivors emits no synthesis order and folds to its next step

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
-    if not state["_verified"]:
+    if False and not state["_verified"]:
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py -k "t1 or t2"
```

**decisive assertion lines (red tokens):**
- T1, `test_synthesis_no_survivors_1910.py:84`: `assert out["terminal"] == "converged", out` → `KeyError: 'terminal'`
- T2, `test_synthesis_no_survivors_1910.py:96`: `assert RDT.P_SYNTHESIS not in seen, seen` → `AssertionError: ['dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis']`

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
__ test_t1_a_panel_with_no_findings_folds_synthesis_and_converges_on_advance ___

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_t1_a_panel_with_no_findin0')
adapters = <test_round_driver_advance.FakeAdapters object at 0x7f66181b22d0>

    def test_t1_a_panel_with_no_findings_folds_synthesis_and_converges_on_advance(tmp_path, adapters):
        # axis: a round with no survivors emits no synthesis order and folds to its terminal (E2)
        gitdir = ADV._gitdir(tmp_path)
        git = ADV._fake_git(gitdir)
        d = ADV._session(tmp_path, **ADV.SYNTHESIS_SEATABLE)
        ADV._record_all_panel_seats(d)
        out = RDA.cmd_advance(d, git=git)
        assert out["ok"], out
        out = RDA.cmd_advance(d, git=git)  # the verifier fold: empty roster, no survivors
        assert out["ok"] is True, out
>       assert out["terminal"] == "converged", out
               ^^^^^^^^^^^^^^^
E       KeyError: 'terminal'

/home/user/wt-1910-wo1/plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py:84: KeyError
____ test_t2_a_round_whose_every_finding_is_refuted_never_offers_synthesis _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_t2_a_round_whose_every_fi0')

    def test_t2_a_round_whose_every_finding_is_refuted_never_offers_synthesis(tmp_path):
        # axis: a round with no survivors emits no synthesis order and folds to its next step (E1, E6)
        session_dir, seen = _drive(tmp_path, "REFUTED")
        ok, state = RDT.load_state(session_dir)
        assert ok and state["terminal"], state.get("terminal")
>       assert RDT.P_SYNTHESIS not in seen, seen
E       AssertionError: ['dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis']
E       assert 'dispatch-synthesis' not in ['dispatch-panel', 'dispatch-verifiers', 'dispatch-synthesis']
E        +  where 'dispatch-synthesis' = RDT.P_SYNTHESIS

/home/user/wt-1910-wo1/plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py:96: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py::test_t1_a_panel_with_no_findings_folds_synthesis_and_converges_on_advance
FAILED plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py::test_t2_a_round_whose_every_finding_is_refuted_never_offers_synthesis
2 failed, 2 deselected in 4.12s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_driver.py`; sha256 before the neutralization `d9beaaa2a5c7627c7715b5e182adff5fb3504425ab0a9fae2151fdc3e624c023`, after the restore `d9beaaa2a5c7627c7715b5e182adff5fb3504425ab0a9fae2151fdc3e624c023` — identical.

**restored lines** (as they stand):
```
3744:     # axis: a round with no verified survivors emits no synthesis order and folds to its next step — see bite-proof record wo_1_1910_synthesis_no_survivors
3745:     if not state["_verified"]:
3746:         _decision(state, "synthesis-no-survivors",
```

**raw green** (exit 0), same command:
```
..                                                                       [100%]
2 passed, 2 deselected in 4.60s
```

---

## B2 — the durable-path refusal of an unauthenticated synthesis landing (`round_adapters.py` `_assemble`, `P_SYNTHESIS` branch)

- **axis:** an empty grouping landed without runner evidence, while survivors exist, refuses rather than folding

**neutralization** (`plugins/superheroes/lib/round_adapters.py`, the `P_SYNTHESIS` branch's check only):
```diff
-        if fault is not None:
+        if False:
             return None, fault
```

**command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo1 -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py -k t4
```

**decisive assertion line (red token):** T4, `test_synthesis_no_survivors_1910.py:134`: `assert art is None, (art, why)` → `AssertionError: ({'grouping': [], 'provenance': {'provenanceUnderived': ['synthesis'], 'unauthenticatedFinder': {'seat': 'synthesis', 'executed': None, 'recorded': 'claude'}}}, None)`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t4_a_durable_empty_grouping_without_execution_evidence_is_refused ____

    def test_t4_a_durable_empty_grouping_without_execution_evidence_is_refused():
        # axis: a durable synthesis landing counts only with runner execution evidence, survivors or not (E5)
        state = S1858._state()
        state["_verified"] = [dict(_FINDING, verdict="CONFIRMED")]
        env = P17._finder_envelope(RA.SEAT_SYNTHESIS)  # no executionEvidence
        env["payload"] = {"grouping": []}
        art, why = RA.assemble(RDT.P_SYNTHESIS, [env], state, state["config"],
                               orders_manifest=P17._finder_manifest(RA.SEAT_SYNTHESIS, vendor="claude"))
>       assert art is None, (art, why)
E       AssertionError: ({'grouping': [], 'provenance': {'provenanceUnderived': ['synthesis'], 'unauthenticatedFinder': {'seat': 'synthesis', 'executed': None, 'recorded': 'claude'}}}, None)
E       assert {'grouping': [], 'provenance': {'provenanceUnderived': ['synthesis'], 'unauthenticatedFinder': {'seat': 'synthesis', 'executed': None, 'recorded': 'claude'}}} is None

/home/user/wt-1910-wo1/plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py:134: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_no_survivors_1910.py::test_t4_a_durable_empty_grouping_without_execution_evidence_is_refused
1 failed, 3 deselected in 2.16s
```

**restore:** the inverse edit on `plugins/superheroes/lib/round_adapters.py`; sha256 before the neutralization `26ea55109381daaa76b91c155e01cca9e97e96197dfaa9a2d919d000f3e8e1de`, after the restore `26ea55109381daaa76b91c155e01cca9e97e96197dfaa9a2d919d000f3e8e1de` — identical; `git diff 04ed0e38… -- plugins/superheroes/lib/round_adapters.py` is empty (the file is byte-identical to base).

**restored lines** (as they stand):
```
449:     elif phase == P_SYNTHESIS:
450:         fault = _authenticate_finder(roster, indexed, dispatch_manifest, orders_manifest,
451:                                      _maker_barred(state, config), disclosures)
452:         if fault is not None:
453:             return None, fault
454:         artifact = _assemble_synthesis(roster, indexed, disclosures)
```

**raw green** (exit 0), same command:
```
.                                                                        [100%]
1 passed, 3 deselected in 2.07s
```
