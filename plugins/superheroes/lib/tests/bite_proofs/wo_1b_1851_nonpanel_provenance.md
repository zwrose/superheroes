# WO-1b (#1851, review C5 L4) bite-proof — every non-panel result is authenticated against its order's vendor and the shared eligibility bar

**Provenance:** claude / sonnet-5.5 (implementer), `plugins/superheroes/lib/round_driver.py`, `plugins/superheroes/lib/round_adapters.py`; detector file `plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py`.

Declared guarded-element set (from the order): P1-P10. P2-P10 were each neutralized by an exact text swap in production code only, the proving node(s) were run red, the neutralization was undone by the inverse text swap, and the same node(s) were run green. The swaps, the runs and the sha256 comparisons were driven by one throwaway script (outside the repository) so the captures below are pasted by the script, never retyped. Nothing is redacted: temp paths are the real ones. All commands ran from the worktree root. Each capture is under the 32 KiB ceiling, so nothing overflowed to disk.

## Disclosures

- **P1 is not implemented, so it has no proof.** The order places (b) in the `_trusted_vendors` runner-evidence branch (a barred executed vendor "not trusted"). That would blank `verifierSeatVendors` for a barred seat, and the `verifierProvenance` row would then read `ran: None` where the existing tests `test_a_verdict_executed_by_the_maker_vendor_is_ignored_through_advance` and `test_a_maker_cluster_does_not_void_a_proven_cluster` assert `ran: "claude"` (an exact-dict and a set assertion). The order forbids rewriting a guarding test, so (b) is applied where it closes the same hole without losing the executed vendor: in `_fold_verifiers` (P3, both branches) and in `_authenticate_finder` (P2). The K outcome for the verifier and the finders is the same; only the row's `ran` differs. Status of P1: `Unprovable as placed` (not placed). The orchestrator can re-order it if the `ran: None` shape is wanted.
- P2, P3 and P10 each ran two nodes in one command (P2: the gap-sweep and the scoped-finder phase; P3: the per-seat branch and the hand-claim branch; P10: the maker-family host and the null host), and both went red under the one neutralization. P3's neutralization is a single edit (`barred = lambda _v: False`) because both branches read the one `barred` predicate.
- Because P1 is not placed, P2 is provable directly: with (b) dropped from `_authenticate_finder` nothing else refuses a barred executed vendor that equals the recorded one.
- The P9 proving node drives `run_loop` over a big diff so the gap sweep really runs; the unit-level `_library_finder_unauthenticated` tests are separate nodes and are not what P9 neutralizes (P9 neutralizes the call site in `run_loop`).
- Not separately neutralized, listed as unproven: the `_library_finder_unauthenticated` helper's own branches (unseatable selection, no report while the engine was replaced, reported-vendor equality and eligibility). Each has a green unit test in the new file with no red shown here; the P9 red shows only that the loop folds when the call site is removed.
- Restore receipts: sha256 of the touched production file before the neutralization and after the restore, and the restored lines quoted back from the file.

Baseline sha256 (before the first neutralization):
```
260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820  plugins/superheroes/lib/round_driver.py
a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979  plugins/superheroes/lib/round_adapters.py
```

## P2 — `round_adapters._authenticate_finder`: (b) eligibility of the executed vendor

- **axis:** an executed vendor equal to the recorded one still does not count when it is ineligible

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
--- before (restored text)
        ineligible = executed is not None and callable(is_barred) and is_barred(executed)
+++ neutralized
        ineligible = False
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-gap-sweep-gap-sweep-maker-family] plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-scoped-finder-scoped-finder-fixer-vendor] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-gap-sweep-gap-sweep-maker-family] _

phase = 'dispatch-gap-sweep', seat = 'gap-sweep', how = 'maker-family'

    @pytest.mark.parametrize("how", BAR_HOW)
    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t2_advance_finder_ineligible_recorded_vendor_is_refused(phase, seat, how):
        # axis: (b) in the finder authentication — executed == recorded is not enough (P2)
        state = _state()
        _bar_codex(state, how)
        art, why = _assemble_finder(state, phase, seat, "codex", "codex")
>       assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
E       AssertionError: ({'findings': [], 'provenance': {'provenanceSource': {'gap-sweep': 'runner-record'}}}, None)
E       assert ({'findings': [], 'provenance': {'provenanceSource': {'gap-sweep': 'runner-record'}}} is None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:165: AssertionError
_ test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-scoped-finder-scoped-finder-fixer-vendor] _

phase = 'dispatch-scoped-finder', seat = 'scoped-finder', how = 'fixer-vendor'

    @pytest.mark.parametrize("how", BAR_HOW)
    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t2_advance_finder_ineligible_recorded_vendor_is_refused(phase, seat, how):
        # axis: (b) in the finder authentication — executed == recorded is not enough (P2)
        state = _state()
        _bar_codex(state, how)
        art, why = _assemble_finder(state, phase, seat, "codex", "codex")
>       assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
E       AssertionError: ({'findings': [], 'provenance': {'provenanceSource': {'scoped-finder': 'runner-record'}}}, None)
E       assert ({'findings': [], 'provenance': {'provenanceSource': {'scoped-finder': 'runner-record'}}} is None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:165: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-gap-sweep-gap-sweep-maker-family]
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_finder_ineligible_recorded_vendor_is_refused[dispatch-scoped-finder-scoped-finder-fixer-vendor]
2 failed in 1.17s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979`, after the restore `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979` (identical); the neutralized file hashed `b7e77850da6538ba9c9a6b99a5d8f600554c1d0a2f29669b325791150429dcbe`. Restored lines quoted back from the file:
```
                               is_barred)
        ineligible = executed is not None and callable(is_barred) and is_barred(executed)
```

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 1.25s
```

---

## P3 — `round_driver._fold_verifiers`: (b) in both branches (per-seat and hand claim)

- **axis:** a verdict from the recorded vendor does not count when that vendor is ineligible

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
    barred = _adapters()._maker_barred(state, config)
+++ neutralized
    barred = lambda _v: False
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_hand_verifier_ineligible_recorded_vendor_claim_is_ignored[maker-family] plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_verifier_ineligible_recorded_vendor_is_ignored[maker-family] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t2_hand_verifier_ineligible_recorded_vendor_claim_is_ignored[maker-family] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-67/test_t2_hand_verifier_ineligib0')
how = 'maker-family'

    @pytest.mark.parametrize("how", BAR_HOW)
    def test_t2_hand_verifier_ineligible_recorded_vendor_claim_is_ignored(tmp_path, how):
        # axis: (b) on the hand claim branch (P3)
        state = _state()
        _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
        _bar_codex(state, how)
        row, unverified = _fold(state, tmp_path, {"verdicts": _verdicts(state), "verifierVendor": "codex"})
>       assert row == {"expected": "codex", "ran": "codex", "outcome": "verdicts-ignored",
                       "reason": "vendor-ineligible"}
E       AssertionError: assert {'expected': ...dicts-folded'} == {'expected': ...r-ineligible'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'outcome': 'verdicts-folded'} != {'outcome': 'verdicts-ignored'}
E         Right contains 1 more item:
E         {'reason': 'vendor-ineligible'}
E         Use -v to get more diff

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:176: AssertionError
_ test_t2_advance_verifier_ineligible_recorded_vendor_is_ignored[maker-family] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-67/test_t2_advance_verifier_ineli0')
how = 'maker-family'

    @pytest.mark.parametrize("how", BAR_HOW)
    def test_t2_advance_verifier_ineligible_recorded_vendor_is_ignored(tmp_path, how):
        # axis: (b) on the per-seat branch — equal to the recorded vendor is not enough (P3)
        state = _state()
        _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
        _bar_codex(state, how)
        row, unverified = _fold(state, tmp_path, _seat_artifact(state, "codex"))
>       assert row == {"expected": "codex", "ran": "codex", "outcome": "verdicts-ignored",
                       "reason": "vendor-ineligible"}
E       AssertionError: assert {'expected': ...dicts-folded'} == {'expected': ...r-ineligible'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'outcome': 'verdicts-folded'} != {'outcome': 'verdicts-ignored'}
E         Right contains 1 more item:
E         {'reason': 'vendor-ineligible'}
E         Use -v to get more diff

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:153: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_hand_verifier_ineligible_recorded_vendor_claim_is_ignored[maker-family]
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_advance_verifier_ineligible_recorded_vendor_is_ignored[maker-family]
2 failed in 1.34s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `c29789a0e83c3781cd6fba6880116167b814e313c85904d540407b38cf15caa3`. Restored lines quoted back from the file:
```
)
)
        )
            state,
    barred = _adapters()._maker_barred(state, config)
            )
        )
                state,
                state,
    )
            state,
            state,
            state,
    )
    )
        )
            )
            )
```

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 1.34s
```

---

## P4 — `round_driver._finder_hand_claim_fault`: (b) eligibility of the expected vendor

- **axis:** a hand finder claim equal to the recorded vendor is refused when that vendor is ineligible

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
    if _adapters()._maker_barred(state, state.get("config"))(expected):
+++ neutralized
    if False and _adapters()._maker_barred(state, state.get("config"))(expected):
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_hand_finder_ineligible_recorded_vendor_claim_is_refused[dispatch-gap-sweep-gap-sweep-maker-family] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_hand_finder_ineligible_recorded_vendor_claim_is_refused[dispatch-gap-sweep-gap-sweep-maker-family] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-69/test_t2_hand_finder_ineligible0')
phase = 'dispatch-gap-sweep', seat = 'gap-sweep', how = 'maker-family'

    @pytest.mark.parametrize("how", BAR_HOW)
    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t2_hand_finder_ineligible_recorded_vendor_claim_is_refused(tmp_path, phase, seat, how):
        # axis: (b) in the hand finder claim check (P4)
        state = _state()
        _emit(state, tmp_path, phase, "codex")
        claim = {"findings": [], "reviewerVendor": "codex"}
        assert RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim) is None
        _bar_codex(state, how)
        fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim)
>       assert fault is not None and "ineligible" in fault, fault
E       AssertionError: None
E       assert (None is not None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:191: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_hand_finder_ineligible_recorded_vendor_claim_is_refused[dispatch-gap-sweep-gap-sweep-maker-family]
1 failed in 1.23s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `6095d9407d61ecc673dde0c5cd1937f4cfd6693ff5a376fcf22fcd7b1c0f00cb`. Restored lines quoted back from the file:
```
)
)
    ):
        )
            state,
    ):
            )
        )
                state,
                state,
    )
            state,
            state,
            state,
    ):
    if _adapters()._maker_barred(state, state.get("config"))(expected):
    )
    )
        )
            )
            )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.22s
```

---

## P5 — `round_driver._finder_hand_claim_fault`: (c) the unverifiable-emission refusal

- **axis:** a hand finder claim on an emission whose manifest does not verify is refused, not judged against the live selection

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
    if _emission_unverifiable(state, session_dir, phase):
        return "%s dispatch recorded+++ neutralized
    if False and _emission_unverifiable(state, session_dir, phase):
        return "%s dispatch recorded```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t3_claim_on_a_lost_or_tampered_emission_is_refused[dispatch-scoped-finder-scoped-finder-rewrite] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t3_claim_on_a_lost_or_tampered_emission_is_refused[dispatch-scoped-finder-scoped-finder-rewrite] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-71/test_t3_claim_on_a_lost_or_tam0')
phase = 'dispatch-scoped-finder', seat = 'scoped-finder', tamper = 'rewrite'

    @pytest.mark.parametrize("tamper", ["rewrite", "delete"])
    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t3_claim_on_a_lost_or_tampered_emission_is_refused(tmp_path, phase, seat, tamper):
        # axis: (c) an emission whose manifest no longer verifies authenticates nothing (P5)
        state = _state()
        manifest = _emit(state, tmp_path, phase, "codex")
        claim = {"findings": [], "reviewerVendor": "codex"}
        assert RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim) is None
        path = RD._orders_manifest_path(str(tmp_path), state["round"], phase, 0)
        if tamper == "rewrite":
            for entry in manifest["seats"].values():
                entry["vendor"] = "cursor"
            RR.atomic_write_json(path, manifest)
        else:
            os.remove(path)
        assert RD._emission_unverifiable(state, str(tmp_path), phase)
        fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, claim)
>       assert fault is not None and "does not verify" in fault, fault
E       AssertionError: None
E       assert (None is not None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:284: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t3_claim_on_a_lost_or_tampered_emission_is_refused[dispatch-scoped-finder-scoped-finder-rewrite]
1 failed in 1.51s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `e3469f5bebe7769d2aa0ad8fbf44792e25fe1241d7c06903c4e9e67b1f0f1e05`. Restored lines quoted back from the file:
```
)
)
            return
            return
    ):
        return
        )
            return
            return
            return
            return
            return
        return
        return
        return
        return
            state,
        return
        return
    ):
            return
            return
            return
            return
                return
        return
        return
        return
        return
            return
                return
                    return
                    return
                    return
        return
        return
            return
        return
        return
        return
            return
            return
            )
        return
            return
        return
        return
            return
        return
        return
        return
        return
        )
        return
            return
        return
        return
        return
        return
        return
        return
        return
        return
        return
        return
            return
            return
        return
        return
                state,
            return
                state,
            return
            return
        return
        return
            return
        return
    )
            return
            state,
            state,
            state,
        return
            return
        return
            return
        return
        return
        return
        return
        return
        return
        return
    ):
    if _emission_unverifiable(state, session_dir, phase):
        return
    )
    )
        )
                                phase):
            session_dir,
            session_dir,
            session_dir,
                session_dir,
                session_dir,
            )
                session_dir,
            )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.15s
```

---

## P6 — `round_adapters._authenticate_finder`: equality of the executed and recorded vendor

- **axis:** an executed vendor other than the recorded one never counts (the seat folds as missing)

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
--- before (restored text)
or executed != expected or ineligible:+++ neutralized
or executed != executed or ineligible:```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_advance_finder_executed_other_than_recorded_is_refused[dispatch-gap-sweep-gap-sweep] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_advance_finder_executed_other_than_recorded_is_refused[dispatch-gap-sweep-gap-sweep] _

phase = 'dispatch-gap-sweep', seat = 'gap-sweep'

    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t1_advance_finder_executed_other_than_recorded_is_refused(phase, seat):
        # axis: the finder authentication compares the executed vendor with the recorded one (P6)
        art, why = _assemble_finder(_state(), phase, seat, "cursor", "codex")
>       assert art is None and why.startswith("missing-seat-refuse-fold:%s" % seat), (art, why)
E       AssertionError: ({'findings': [], 'provenance': {'provenanceSource': {'gap-sweep': 'runner-record'}, 'vendorEchoMismatch': [{'seat': 'gap-sweep', 'occurrence': 0, 'echo': 'codex', 'recorded': 'cursor'}]}}, None)
E       assert ({'findings': [], 'provenance': {'provenanceSource': {'gap-sweep': 'runner-record'}, 'vendorEchoMismatch': [{'seat': 'gap-sweep', 'occurrence': 0, 'echo': 'codex', 'recorded': 'cursor'}]}} is None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:107: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_advance_finder_executed_other_than_recorded_is_refused[dispatch-gap-sweep-gap-sweep]
1 failed in 1.16s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979`, after the restore `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979` (identical); the neutralized file hashed `8eff795fb21da622006602905ef8016e434c7cc626a3384604c33588a453e41e`. Restored lines quoted back from the file:
```

```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.13s
```

---

## P7 — `round_driver._fold_verifiers`, per-seat branch: equality of the seat's vendor and the recorded one

- **axis:** a seat whose executed vendor is not the recorded one folds as silence

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
                proven = ran_vendor == selected and not barred(ran_vendor)
+++ neutralized
                proven = ran_vendor is not None and not barred(ran_vendor)
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_advance_verifier_executed_other_than_recorded_is_ignored -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_t1_advance_verifier_executed_other_than_recorded_is_ignored _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-75/test_t1_advance_verifier_execu0')

    def test_t1_advance_verifier_executed_other_than_recorded_is_ignored(tmp_path):
        # axis: per-seat equality against the vendor recorded at emission (P7)
        state = _state()
        _emit(state, tmp_path, RD.P_VERIFIERS, "codex")
        row, unverified = _fold(state, tmp_path, _seat_artifact(state, "cursor"))
>       assert row == {"expected": "codex", "ran": "cursor", "outcome": "verdicts-ignored"}
E       AssertionError: assert {'expected': ...dicts-folded'} == {'expected': ...icts-ignored'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'outcome': 'verdicts-folded'} != {'outcome': 'verdicts-ignored'}
E         Use -v to get more diff

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:91: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_advance_verifier_executed_other_than_recorded_is_ignored
1 failed in 1.20s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `7dd203bbfb6826d3e8e20e94f0179fcff36d1fbf4c2b0291c74538028abc04ec`. Restored lines quoted back from the file:
```
)
)
        )
                proven = ran_vendor == selected and not barred(ran_vendor)
            )
        )
    )
    )
    )
        )
            )
            )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.30s
```

---

## P8 — `round_driver._finder_hand_claim_fault`: the hand claim equals the recorded vendor

- **axis:** a hand finder claim that differs from the recorded vendor is refused

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
    if claimed is not None and claimed != expected:
+++ neutralized
    if False and claimed is not None and claimed != expected:
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_hand_finder_claim_other_than_recorded_is_refused[dispatch-scoped-finder-scoped-finder] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t1_hand_finder_claim_other_than_recorded_is_refused[dispatch-scoped-finder-scoped-finder] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-77/test_t1_hand_finder_claim_othe0')
phase = 'dispatch-scoped-finder', seat = 'scoped-finder'

    @pytest.mark.parametrize("phase,seat", FINDERS)
    def test_t1_hand_finder_claim_other_than_recorded_is_refused(tmp_path, phase, seat):
        # axis: the hand claim must equal the vendor recorded at emission (P8)
        state = _state()
        _emit(state, tmp_path, phase, "codex")
        fault = RD._finder_hand_claim_fault(state, str(tmp_path), phase, {"findings": [], "reviewerVendor": "cursor"})
>       assert fault is not None and "'cursor'" in fault and "recorded 'codex'" in fault, fault
E       AssertionError: None
E       assert (None is not None)

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t1_hand_finder_claim_other_than_recorded_is_refused[dispatch-scoped-finder-scoped-finder]
1 failed in 1.23s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `79d4ec18061edb413c49a453e5c7b2702bd84b61696235716767236b2794d335`. Restored lines quoted back from the file:
```
    if claimed is not None and claimed != expected:
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.15s
```

---

## P9 — `round_driver.run_loop`: the library finder guard (L)

- **axis:** a library gap-sweep result not from the selected eligible vendor parks the loop and is never folded

**neutralization** (`plugins/superheroes/lib/round_driver.py`):
```diff
--- before (restored text)
            if action in (P_GAPSWEEP, P_SCOPED) and _library_finder_unauthenticated(
+++ neutralized
            if action in (P_GAPSWEEP, P_SCOPED) and False and _library_finder_unauthenticated(
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_library_gap_sweep_that_does_not_authenticate_parks_the_loop[maker-vendor] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_library_gap_sweep_that_does_not_authenticate_parks_the_loop[maker-vendor] _

reported = {'findings': [], 'vendor': 'claude'}

    @pytest.mark.parametrize("reported", [
        pytest.param({"findings": [], "vendor": "claude"}, id="maker-vendor"),
        pytest.param({"findings": [], "vendor": "cursor"}, id="other-vendor"),
        pytest.param([], id="nothing-reported-while-the-engine-was-replaced"),
    ])
    def test_t2_library_gap_sweep_that_does_not_authenticate_parks_the_loop(reported):
        # axis: the library finder guard — a result not from the selected eligible vendor never folds (P9)
        state, calls = _library_run(reported)
>       assert calls == 1 and _parked(state), (state.get("terminal"), state.get("certification"))
E       AssertionError: ('converged', {'shape': 'full-panel-confirmed-degraded', 'fullPanel': True, 'independence': 'independent', 'base': 'fetched', ...})
E       assert (1 == 1 and False)
E        +  where False = _parked({'schemaVersion': 5, 'sessionGeneration': 3, 'config': {'leg': 'code', 'panel': False, 'code': True, 'vendors': ['claude', 'codex'], ...}, 'round': 1, ...})

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:223: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t2_library_gap_sweep_that_does_not_authenticate_parks_the_loop[maker-vendor]
1 failed in 1.17s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820`, after the restore `260164b2747f797ff9bf6216b241ff13f05b3a24a0b2822c01bd5524b685c820` (identical); the neutralized file hashed `7b5f693127e215b04ce7338725d073a591293efd95eecc487e69d0cad838b057`. Restored lines quoted back from the file:
```
)
)
        )
            )
        )
    )
            if action in (P_GAPSWEEP, P_SCOPED) and _library_finder_unauthenticated(
    )
    )
        )
            )
            )
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.07s
```

---

## P10 — `round_adapters._trusted_vendors`: the barred predicate reaches `_manifest_vendor_for_wrapped_seat`

- **axis:** a driver-wrapped native host-seat landing is trusted only when the host family is known and outside the makers

**neutralization** (`plugins/superheroes/lib/round_adapters.py`):
```diff
--- before (restored text)
                    envelope, seat, occurrence, orders_manifest, is_barred)
+++ neutralized
                    envelope, seat, occurrence, orders_manifest, None)
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-is-a-maker-family] plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-null] -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF                                                                       [100%]
=================================== FAILURES ===================================
_ test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-is-a-maker-family] _

cfg = {'fixer': 'codex', 'host': 'anthropic', 'makers': ['anthropic']}
trusted = False

    @pytest.mark.parametrize("cfg,trusted", HOSTS)
    def test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host(cfg, trusted):
        # axis: the barred predicate reaches the driver-wrapped host-seat manifest path (P10)
        art = _wrapped_verifier_artifact(_state(**cfg))
>       assert set(art["verifierSeatVendors"].values()) == ({"claude"} if trusted else {""}), art
E       AssertionError: {'verdicts': [{'id': 'v0', 'verdict': 'REFUTED', 'reason': 'intentional', 'evidence': 'read x'}], 'verifierVendor': 'claude', 'verifierSeatVendors': {'v0': 'claude'}, 'verifierSeatProvenance': {'v0': 'dispatch-manifest'}, ...}
E       assert {'claude'} == {''}
E         
E         Extra items in the left set:
E         'claude'
E         Extra items in the right set:
E         ''
E         Use -v to get more diff

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:332: AssertionError
_ test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-null] _

cfg = {'fixer': 'codex', 'host': None}, trusted = False

    @pytest.mark.parametrize("cfg,trusted", HOSTS)
    def test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host(cfg, trusted):
        # axis: the barred predicate reaches the driver-wrapped host-seat manifest path (P10)
        art = _wrapped_verifier_artifact(_state(**cfg))
>       assert set(art["verifierSeatVendors"].values()) == ({"claude"} if trusted else {""}), art
E       AssertionError: {'verdicts': [{'id': 'v0', 'verdict': 'REFUTED', 'reason': 'intentional', 'evidence': 'read x'}], 'verifierVendor': 'claude', 'verifierSeatVendors': {'v0': 'claude'}, 'verifierSeatProvenance': {'v0': 'dispatch-manifest'}, ...}
E       assert {'claude'} == {''}
E         
E         Extra items in the left set:
E         'claude'
E         Extra items in the right set:
E         ''
E         Use -v to get more diff

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:332: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-is-a-maker-family]
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_t4_native_host_seat_verifier_is_trusted_only_for_a_known_non_maker_host[host-family-null]
2 failed in 1.17s
```

**restore:** inverse text swap of the neutralized lines.

**restore receipt:** sha256 before the neutralization `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979`, after the restore `a6420b6585b1558bbd94fe89b9db1a50549faa35f1745d1631f5d757eced1979` (identical); the neutralized file hashed `7e062353b4816137e785434090858c0e5f62c36cbcd13b9c115df30aad668fa0`. Restored lines quoted back from the file:
```
                    envelope, seat, occurrence, orders_manifest, is_barred)
                                   orders_manifest, is_barred)
                               is_barred)
```

**raw green** (exit 0):
```
..                                                                       [100%]
2 passed in 1.24s
```

---

## F1 — `receipt_disclosures.nonpanel_barred`: the one home of the non-panel eligibility predicate

- **axis:** the shared predicate takes the host family from the effective seat map, so a native seat is judged by the host family and not by the registry's family (the driver and the adapters read this one function, not the adapters seam)
- Added by WO-F1 (#1851, review C5 L4) after P1-P10; the neutralization was applied and undone by two targeted edits, not by the P2-P10 script. No sha256 was taken for this entry; the restore is shown by the quoted lines.

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`):
```diff
--- before (restored text)
    return reviewer_ineligible(accumulated_maker_families(state), cfg.get("fixerVendor"),
                               host_family=host_family(seat_map_receipts.effective_seat_map(state)))
+++ neutralized
    return reviewer_ineligible(accumulated_maker_families(state), cfg.get("fixerVendor"))
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family ___

    def test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family():
        # axis: receipt_disclosures.nonpanel_barred passes the seat map's host family — see bite-proof
        nonpanel_barred = RD.receipt_disclosures.nonpanel_barred
    
        def bar(vendor, **cfg):
            state = _state(fixer=None, **cfg)
            return nonpanel_barred(state, state["config"])(vendor)
    
        assert bar("claude", host="anthropic", makers=["anthropic"]) is True
        assert bar("codex", host="anthropic", makers=["anthropic"]) is False
        # the host family, not the registry's anthropic, decides for the native seat
>       assert bar("claude", host="openai", makers=["openai"]) is True
E       AssertionError: assert False is True
E        +  where False = <function test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family.<locals>.bar at 0x7f7b150823e0>('claude', host='openai', makers=['openai'])

/home/user/l4/plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py:360: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_provenance_1851.py::test_f1_nonpanel_barred_is_the_shared_predicate_and_reads_the_host_family
1 failed in 1.24s
```

**restore:** inverse edit of the neutralized line. Restored lines quoted back from the file:
```
    return reviewer_ineligible(accumulated_maker_families(state), cfg.get("fixerVendor"),
                               host_family=host_family(seat_map_receipts.effective_seat_map(state)))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 2.31s
```

---
