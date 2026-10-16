# WO-R (#1851) bite-proof — the native host family follows the seat map's host

**Provenance:** claude / sonnet-5.5 (implementer, effort high), `plugins/superheroes/lib/receipt_disclosures.py`, `plugins/superheroes/lib/round_adapters.py`, `plugins/superheroes/lib/round_driver.py`, `plugins/superheroes/lib/seat_map.py`, `plugins/superheroes/lib/seat_map_receipts.py`.

Declared guarded-element set (from the order): R1-R7. Each was neutralized by an exact one-site text swap in production code only, the proving node was run red, the neutralization was undone by the inverse text swap, and the same node was run green. Temp paths are the only redaction (`<repo>` for the worktree root); nothing else was edited. All commands ran from `<repo>`, with `-X pycache_prefix=/tmp/l4-pyc`.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| R1 | the native host family in `reviewer_ineligible` (`receipt_disclosures.py`) | a native (registered, non-runner) seat takes the HOST family, not `family_for("reviewer", vendor)`; a host in a maker family bars native claude whatever its registry family | `test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family` |
| R2 | an unknown host makes the native seat ineligible (`reviewer_ineligible`, `receipt_disclosures.py`) | a null or non-string host family leaves a native seat with no family, so it is ineligible and a runner vendor is seated in its place | `test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible` |
| R3 | `round_adapters._maker_barred` passes the host family (`round_adapters.py`) | the authentication side judges a native seat by the same host family the selection used | `test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family` |
| R4 | `round_driver._nonpanel_reviewer_vendor` passes the host family to `independent_reviewer` (`round_driver.py`) | the selection judges a native seat by the seat map's host family | `test_the_selection_judges_the_native_seat_by_the_seat_map_host_family` |
| R5 | the removed no-makers shortcut in `_nonpanel_reviewer_vendor` (`round_driver.py`) | with no makers and no fixer a native engine on an unknown host is still not seated (no early return that skips the host-family bar) | `test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated` |
| R6 | compose's `hostFamily` from the host model (`seat_map.py`) | the composed receipt's `hostFamily` is the registry family of `--host-model` | `test_host_family_is_the_registry_family_of_the_host_model` |
| R7 | the projection's host-family agreement rule (`seat_map_receipts.py`) | receipts that disagree on the host leave the projected host family None; it survives only on agreement | `test_projection_host_family_survives_only_on_agreement` |

## Disclosures

- Every element has a proving node that went red under its neutralization; none is recorded as unproven.
- R5's node is parametrized over the three non-panel phases; all three cases went red together under the one neutralization and green together after the restore. R6's node is parametrized over five host models; the two with a recognized host (`gpt-5.6-sol`, `claude-opus-5`) went red and the three with an unknown host stayed green, as they should under an always-`None` neutralization.
- No test was edited or weakened; the proving nodes are the ones already in `test_nonpanel_host_family_1851.py` and `test_seat_map_host_family_1851.py`, each carrying an `axis:` comment that points at this record where it guards an element.
- Not separately neutralized, so unproven: the runner-channel vendors keeping their registry family (guarded green by `test_with_no_makers_and_no_fixer_a_runner_engine_is_unaffected_by_the_host` and `test_independent_reviewer_without_the_keyword_keeps_the_registry_family`, with no red shown here), and the `hostFamily` key's `to_receipt` carry-through and legacy-receipt handling in `seat_map_receipts.py`.
- Restore receipts: the neutralized lines are quoted back as they stand in the file after the inverse edit, and the sha256 of the neutralized file before the neutralization, while neutralized, and after the restore is printed in each entry; before and after are equal in every entry.

Baseline sha256, taken before R1 (the same line came back after every restore of that file):
```
c4ceff1d37b6784afbcbfadb8e0fde91a1a9658a0ab84481999ade27fb2b4b32  plugins/superheroes/lib/receipt_disclosures.py
783dd5710fc985b146e666482b19cb7872777fe338c4b42f6eb87c90ddcc918b  plugins/superheroes/lib/round_adapters.py
e3cf5509c560cbb4fbe3909a03348768fd63d74a31c8b9683bb44a8321ec6475  plugins/superheroes/lib/round_driver.py
45b5593d48926a9e0ff2bc47a53048db2f2b9f0df28c9c627afc4e433886fd80  plugins/superheroes/lib/seat_map.py
9070ff909e6b3de7bb37cbe81ec16167de394fabb700a9ed5e26e91f46fc6cf3  plugins/superheroes/lib/seat_map_receipts.py
```

---

## R1 — the native host family in `reviewer_ineligible` (`receipt_disclosures.py`)

- **axis:** a native (registered, non-runner) seat takes the HOST family, not `family_for("reviewer", vendor)`; a host in a maker family bars native claude whatever its registry family

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`): use `model_registry.family_for("reviewer", vendor)` for native seats (the host-family branch made unreachable with `False and`)
```diff
--- before (restored text)
        if (host_family is not HOST_FAMILY_REGISTRY
+++ neutralized
        if (False and host_family is not HOST_FAMILY_REGISTRY
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fe300937490>

    def test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family(monkeypatch):
        # axis: a native seat takes the HOST family, not family_for("reviewer", "claude") — see bite-proof
        # record wo_r_1851_host_family (R1)
        assert model_registry.family_for("reviewer", "claude") == "anthropic"
        _engine(monkeypatch, "claude")
        openai_host = _state(_map(host="openai", makerFamilies=["openai"]), vendors=["claude", "codex"])
        # claude is barred (host openai == maker openai); codex is openai too -> nobody qualifies
>       assert _pick(openai_host) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:91: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_a_host_in_a_maker_family_bars_native_claude_whatever_its_registry_family
1 failed in 1.75s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the neutralization `c4ceff1d37b6784afbcbfadb8e0fde91a1a9658a0ab84481999ade27fb2b4b32`, neutralized `ed72ed31534154133e992b2ff692512f6bba18e51f47d524a84b0cb4dbc16ae3`, after the restore `c4ceff1d37b6784afbcbfadb8e0fde91a1a9658a0ab84481999ade27fb2b4b32` (equal to the before value). The restored lines as they stand in the file:
```
        if (host_family is not HOST_FAMILY_REGISTRY
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 4.52s

green exit: 0
```


---

## R2 — an unknown host makes the native seat ineligible (`reviewer_ineligible`, `receipt_disclosures.py`)

- **axis:** a null or non-string host family leaves a native seat with no family, so it is ineligible and a runner vendor is seated in its place

**neutralization** (`plugins/superheroes/lib/receipt_disclosures.py`): treat a null host family as the registry family (the `else None` falls back to `family_for("reviewer", vendor)`)
```diff
--- before (restored text)
            fam = host_family if isinstance(host_family, str) and host_family else None
+++ neutralized
            fam = host_family if isinstance(host_family, str) and host_family else model_registry.family_for("reviewer", vendor)
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible ____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fef0a9f7490>

    def test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible(monkeypatch):
        # axis: an unknown host (no seat map) leaves a native claude seat ineligible — see bite-proof
        # record wo_r_1851_host_family (R2)
        _engine(monkeypatch, "claude")
        state = _state(vendors=["claude", "codex"])
        assert RD.effective_seat_map(state) == {}
        assert RDS.host_family(RD.effective_seat_map(state)) is None
        # codex is a runner-channel vendor, unaffected by the host: it is seated in claude's place
>       assert _pick(state) == ("codex", RD.VENDOR_SOURCE_INDEPENDENT)
E       AssertionError: assert ('claude', 'configured') == ('codex', 'independent')
E         
E         At index 0 diff: 'claude' != 'codex'
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:61: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_no_seat_map_is_an_unknown_host_and_leaves_native_claude_ineligible
1 failed in 0.15s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/receipt_disclosures.py` before the neutralization `c4ceff1d37b6784afbcbfadb8e0fde91a1a9658a0ab84481999ade27fb2b4b32`, neutralized `ee6f953cec672d5f938d4e89510fff03cd3684ffce6dbd19de89620eda987a70`, after the restore `c4ceff1d37b6784afbcbfadb8e0fde91a1a9658a0ab84481999ade27fb2b4b32` (equal to the before value). The restored lines as they stand in the file:
```
            fam = host_family if isinstance(host_family, str) and host_family else None
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.12s

green exit: 0
```


---

## R3 — `round_adapters._maker_barred` passes the host family (`round_adapters.py`)

- **axis:** the authentication side judges a native seat by the same host family the selection used

**neutralization** (`plugins/superheroes/lib/round_adapters.py`): drop the `host_family=` keyword
```diff
--- before (restored text)
        receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"),
        host_family=receipt_disclosures.host_family(seat_map_receipts.effective_seat_map(state)))
+++ neutralized
        receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"))
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family ____

    def test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family():
        # axis: round_adapters._maker_barred passes the host family the selection used — see bite-proof
        # record wo_r_1851_host_family (R3)
        cfg = {"vendors": ["claude", "codex"]}
        bar = RA._maker_barred(_state(_map(host="openai", makerFamilies=["openai"]), **cfg), cfg)
>       assert bar("claude") is True
E       AssertionError: assert False is True
E        +  where False = <function reviewer_ineligible.<locals>.is_ineligible at 0x7f11ebcdef20>('claude')

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:133: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_maker_barred_judges_a_native_seat_with_the_selection_s_host_family
1 failed in 0.11s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/round_adapters.py` before the neutralization `783dd5710fc985b146e666482b19cb7872777fe338c4b42f6eb87c90ddcc918b`, neutralized `64664cafc1e68af041247f7740b55685e0ac00f172bdc20793c72de49992900b`, after the restore `783dd5710fc985b146e666482b19cb7872777fe338c4b42f6eb87c90ddcc918b` (equal to the before value). The restored lines as they stand in the file:
```
        receipt_disclosures.accumulated_maker_families(state), cfg.get("fixerVendor"),
        host_family=receipt_disclosures.host_family(seat_map_receipts.effective_seat_map(state)))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s

green exit: 0
```


---

## R4 — `round_driver._nonpanel_reviewer_vendor` passes the host family to `independent_reviewer` (`round_driver.py`)

- **axis:** the selection judges a native seat by the seat map's host family

**neutralization** (`plugins/superheroes/lib/round_driver.py`): drop the `host_family=` keyword
```diff
--- before (restored text)
        cfg, vendor, makers, fixer,
        host_family=receipt_disclosures.host_family(effective_seat_map(state)))
+++ neutralized
        cfg, vendor, makers, fixer)
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_the_selection_judges_the_native_seat_by_the_seat_map_host_family -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_the_selection_judges_the_native_seat_by_the_seat_map_host_family _____

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd937f37490>

    def test_the_selection_judges_the_native_seat_by_the_seat_map_host_family(monkeypatch):
        # axis: the selection passes the host family to independent_reviewer — see bite-proof record
        # wo_r_1851_host_family (R4)
        _engine(monkeypatch, "claude")
        state = _state(_map(host="openai", makerFamilies=["openai"]), vendors=["claude"])
>       assert _pick(state) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:103: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_the_selection_judges_the_native_seat_by_the_seat_map_host_family
1 failed in 0.11s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the neutralization `e3cf5509c560cbb4fbe3909a03348768fd63d74a31c8b9683bb44a8321ec6475`, neutralized `7803f99b11acbd905f9e78ec6b13409b922a815a2171befdd62f656dd1ad5e71`, after the restore `e3cf5509c560cbb4fbe3909a03348768fd63d74a31c8b9683bb44a8321ec6475` (equal to the before value). The restored lines as they stand in the file:
```
        cfg, vendor, makers, fixer,
        host_family=receipt_disclosures.host_family(effective_seat_map(state)))
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.10s

green exit: 0
```


---

## R5 — the removed no-makers shortcut in `_nonpanel_reviewer_vendor` (`round_driver.py`)

- **axis:** with no makers and no fixer a native engine on an unknown host is still not seated (no early return that skips the host-family bar)

**neutralization** (`plugins/superheroes/lib/round_driver.py`): restore `if not makers and not fixer: return vendor, source`
```diff
--- before (restored text)
    fixer = cfg.get("fixerVendor")
    chosen, _family = receipt_disclosures.independent_reviewer(
+++ neutralized
    fixer = cfg.get("fixerVendor")
    if not makers and not fixer: return vendor, source
    chosen, _family = receipt_disclosures.independent_reviewer(
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_ test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-verifiers] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f9d4bf63490>
phase = 'dispatch-verifiers'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated(monkeypatch, phase):
        # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
        # wo_r_1851_host_family (R5)
        _engine(monkeypatch, "claude")
        assert phase in NONPANEL
        # unknown host (no seat map): the native engine is ineligible although nothing is barred
>       assert _pick(_state(vendors=["claude"])) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:159: AssertionError
_ test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-gap-sweep] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f9d4bf62190>
phase = 'dispatch-gap-sweep'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated(monkeypatch, phase):
        # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
        # wo_r_1851_host_family (R5)
        _engine(monkeypatch, "claude")
        assert phase in NONPANEL
        # unknown host (no seat map): the native engine is ineligible although nothing is barred
>       assert _pick(_state(vendors=["claude"])) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:159: AssertionError
_ test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-scoped-finder] _

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f9d4b9ef410>
phase = 'dispatch-scoped-finder'

    @pytest.mark.parametrize("phase", NONPANEL)
    def test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated(monkeypatch, phase):
        # axis: the removed `not makers and not fixer` shortcut — see bite-proof record
        # wo_r_1851_host_family (R5)
        _engine(monkeypatch, "claude")
        assert phase in NONPANEL
        # unknown host (no seat map): the native engine is ineligible although nothing is barred
>       assert _pick(_state(vendors=["claude"])) == (None, None)
E       AssertionError: assert ('claude', 'configured') == (None, None)
E         
E         At index 0 diff: 'claude' != None
E         Use -v to get more diff

<repo>/plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py:159: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-verifiers]
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-gap-sweep]
FAILED plugins/superheroes/lib/tests/test_nonpanel_host_family_1851.py::test_with_no_makers_and_no_fixer_a_native_engine_on_an_unknown_host_is_not_seated[dispatch-scoped-finder]
3 failed in 0.13s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/round_driver.py` before the neutralization `e3cf5509c560cbb4fbe3909a03348768fd63d74a31c8b9683bb44a8321ec6475`, neutralized `efaeeed760daca1a7991dc40628ec585ddd1a9fe59566b7223b3d4f29120c619`, after the restore `e3cf5509c560cbb4fbe3909a03348768fd63d74a31c8b9683bb44a8321ec6475` (equal to the before value). The restored lines as they stand in the file:
```
    fixer = cfg.get("fixerVendor")
    chosen, _family = receipt_disclosures.independent_reviewer(
```

**raw green** (exit 0):
```
...                                                                      [100%]
3 passed in 0.13s

green exit: 0
```


---

## R6 — compose's `hostFamily` from the host model (`seat_map.py`)

- **axis:** the composed receipt's `hostFamily` is the registry family of `--host-model`

**neutralization** (`plugins/superheroes/lib/seat_map.py`): `receipt_host_family` always `None`
```diff
--- before (restored text)
            receipt_host_family = host_fam
+++ neutralized
            receipt_host_family = None
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py::test_host_family_is_the_registry_family_of_the_host_model -q -p no:cacheprovider
```

**raw red** (exit 1):
```
FF...                                                                    [100%]
=================================== FAILURES ===================================
_ test_host_family_is_the_registry_family_of_the_host_model[host_args0-openai] _

capsys = <_pytest.capture.CaptureFixture object at 0x7fe821b3ba10>
host_args = ['--host-model', 'gpt-5.6-sol'], expected = 'openai'

    @pytest.mark.parametrize(
        "host_args, expected",
        [
            (["--host-model", "gpt-5.6-sol"], "openai"),
            (["--host-model", "claude-opus-5"], "anthropic"),
            (["--host-model", ""], None),
            (["--host-model", "no-such-model-1851"], None),
            ([], None),
        ],
    )
    def test_host_family_is_the_registry_family_of_the_host_model(capsys, host_args, expected):
        receipt = _host_family_receipt(capsys, host_args)
    
        assert "hostFamily" in receipt
>       assert receipt["hostFamily"] == expected
E       AssertionError: assert None == 'openai'

<repo>/plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py:50: AssertionError
_ test_host_family_is_the_registry_family_of_the_host_model[host_args1-anthropic] _

capsys = <_pytest.capture.CaptureFixture object at 0x7fe822924b90>
host_args = ['--host-model', 'claude-opus-5'], expected = 'anthropic'

    @pytest.mark.parametrize(
        "host_args, expected",
        [
            (["--host-model", "gpt-5.6-sol"], "openai"),
            (["--host-model", "claude-opus-5"], "anthropic"),
            (["--host-model", ""], None),
            (["--host-model", "no-such-model-1851"], None),
            ([], None),
        ],
    )
    def test_host_family_is_the_registry_family_of_the_host_model(capsys, host_args, expected):
        receipt = _host_family_receipt(capsys, host_args)
    
        assert "hostFamily" in receipt
>       assert receipt["hostFamily"] == expected
E       AssertionError: assert None == 'anthropic'

<repo>/plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py:50: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py::test_host_family_is_the_registry_family_of_the_host_model[host_args0-openai]
FAILED plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py::test_host_family_is_the_registry_family_of_the_host_model[host_args1-anthropic]
2 failed, 3 passed in 0.26s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map.py` before the neutralization `45b5593d48926a9e0ff2bc47a53048db2f2b9f0df28c9c627afc4e433886fd80`, neutralized `3a3fa6e76c5783e6f179d2830b66c87338fc0df4e832576d99328c07888f3e9f`, after the restore `45b5593d48926a9e0ff2bc47a53048db2f2b9f0df28c9c627afc4e433886fd80` (equal to the before value). The restored lines as they stand in the file:
```
            receipt_host_family = host_fam
```

**raw green** (exit 0):
```
.....                                                                    [100%]
5 passed in 0.23s

green exit: 0
```


---

## R7 — the projection's host-family agreement rule (`seat_map_receipts.py`)

- **axis:** receipts that disagree on the host leave the projected host family None; it survives only on agreement

**neutralization** (`plugins/superheroes/lib/seat_map_receipts.py`): last-wins (`host_families[-1]`)
```diff
--- before (restored text)
        base["hostFamily"] = host_families[0] if agreed else None
+++ neutralized
        base["hostFamily"] = host_families[-1]
```

**command:**
```
python3 -B -X pycache_prefix=/tmp/l4-pyc -m pytest plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py::test_projection_host_family_survives_only_on_agreement -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_projection_host_family_survives_only_on_agreement ____________

    def test_projection_host_family_survives_only_on_agreement():
        anthropic = _seat_map(hostFamily="anthropic")
        openai = _seat_map(hostFamily="openai")
        unknown = _seat_map(hostFamily=None)
    
        assert SMR.emit_receipt_seat_map(_state(anthropic, anthropic))["hostFamily"] == "anthropic"
>       assert SMR.emit_receipt_seat_map(_state(anthropic, openai))["hostFamily"] is None
E       AssertionError: assert 'openai' is None

<repo>/plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py:93: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_host_family_1851.py::test_projection_host_family_survives_only_on_agreement
1 failed in 0.11s

red exit: 1
```

**restore:** the inverse text swap of the neutralization above (the "before" text put back; no `git checkout`, `git restore`, `git reset` or `git stash`).

**restore receipt:** sha256 of `plugins/superheroes/lib/seat_map_receipts.py` before the neutralization `9070ff909e6b3de7bb37cbe81ec16167de394fabb700a9ed5e26e91f46fc6cf3`, neutralized `e037bd71c41ed7df8cacd7c3082b325065801f27a5b69a7c8fff8e29350d6ee6`, after the restore `9070ff909e6b3de7bb37cbe81ec16167de394fabb700a9ed5e26e91f46fc6cf3` (equal to the before value). The restored lines as they stand in the file:
```
        base["hostFamily"] = host_families[0] if agreed else None
```

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.09s

green exit: 0
```
