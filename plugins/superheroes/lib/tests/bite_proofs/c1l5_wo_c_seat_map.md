# Bite-proof record: C1-L5 WO-C, the build session's family is always a maker (#2209)

Detector: `plugins/superheroes/lib/tests/test_seat_map_c1l5.py`. Guarded surface: `seat_map.py` `main`, compose,
`--implementation-engine` path. Command for each half: `scripts/pinned-python -B -m pytest plugins/superheroes/lib/tests/test_seat_map_c1l5.py -q -k <test>`.
Nothing in the captures below needed redaction (no secrets, tokens, URLs or PII); the `UV_NATIVE_TLS` warning line the
launcher prints is dropped from each capture.

## E1: the host family is added to the makers when the implementation engine is not claude

- **guarded element:** `seat_map.py` `extra_maker_families` block after the `--implementation-engine` branch
  (`if host_maker_family is not None and host_maker_family != author_family:`, line 1657). Axis: independence, a
  codex-engine run on an anthropic host seats no anthropic reviewer.
- **neutralization:** the condition became
  `if args.implementation_engine == "claude" and host_maker_family is not None and host_maker_family != author_family:`
  (the pre-change rule: host family a maker only on a claude engine).
- **guarding test:** `test_i2_codex_engine_on_an_anthropic_host_keeps_both_families_off_every_seat`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_i2_codex_engine_on_an_anthropic_host_keeps_both_families_off_every_seat _

capsys = <_pytest.capture.CaptureFixture object at 0x7f4bbc6abec0>

    def test_i2_codex_engine_on_an_anthropic_host_keeps_both_families_off_every_seat(capsys):
        # axis: the build session applies the fixes, so its family is a maker on every implementation engine
        receipt = _compose(capsys, "--live-vendors", "claude,codex", "--implementation-engine", "codex",
                           "--host-model", "claude-opus-5", "--pr-number", "2209")
        assert receipt["authorFamily"] == "openai" and receipt["hostFamily"] == "anthropic"
>       assert receipt["makerFamilies"] == ["anthropic", "openai"]
E       AssertionError: assert ['openai'] == ['anthropic', 'openai']
E         
E         At index 0 diff: 'openai' != 'anthropic'
E         Right contains one more item: 'openai'
E         Use -v to get more diff

/home/user/wt-2209-c/plugins/superheroes/lib/tests/test_seat_map_c1l5.py:250: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_c1l5.py::test_i2_codex_engine_on_an_anthropic_host_keeps_both_families_off_every_seat
1 failed, 15 deselected in 7.90s
```

- **restore:** the inverse edit, putting the condition back to `if host_maker_family is not None and host_maker_family != author_family:`.
- **restore receipt:** the restored line quoted back from the file (grep on `host_maker_family`):
  `1657:        if host_maker_family is not None and host_maker_family != author_family:`
- **raw green:**

```
.                                                                        [100%]
1 passed, 15 deselected in 0.89s
```

## E2: the claude fallback family is added when the host model is unknown

- **guarded element:** `seat_map.py` `host_maker_family = host_fam or claude_host_fam` (line 1631). Axis: independence under
  an unknown host, where the host family stands in as the claude host family (disclosed by `host-model-unknown`).
- **neutralization:** `host_maker_family = host_fam or claude_host_fam` became `host_maker_family = host_fam`.
- **guarding test:** `test_i2_codex_engine_with_an_unknown_host_keeps_the_claude_fallback_family_off_every_seat`
- **raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_i2_codex_engine_with_an_unknown_host_keeps_the_claude_fallback_family_off_every_seat _

capsys = <_pytest.capture.CaptureFixture object at 0x7f0109e6b140>

    def test_i2_codex_engine_with_an_unknown_host_keeps_the_claude_fallback_family_off_every_seat(capsys):
        # axis: an unknown host model falls back to the claude host family, which is a maker
        receipt = _compose(capsys, "--live-vendors", "claude,codex", "--implementation-engine", "codex",
                           "--host-model", "", "--pr-number", "2209")
        assert receipt["authorFamily"] == "openai" and receipt["hostFamily"] is None
>       assert receipt["makerFamilies"] == ["anthropic", "openai"]
E       AssertionError: assert ['openai'] == ['anthropic', 'openai']
E         
E         At index 0 diff: 'openai' != 'anthropic'
E         Right contains one more item: 'openai'
E         Use -v to get more diff

/home/user/wt-2209-c/plugins/superheroes/lib/tests/test_seat_map_c1l5.py:269: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_seat_map_c1l5.py::test_i2_codex_engine_with_an_unknown_host_keeps_the_claude_fallback_family_off_every_seat
1 failed, 15 deselected in 0.27s
```

- **restore:** the inverse edit, `host_maker_family = host_fam` back to `host_maker_family = host_fam or claude_host_fam`.
- **restore receipt:** the restored lines quoted back from the file:
  `1631:            host_maker_family = host_fam or claude_host_fam`
  `1657:        if host_maker_family is not None and host_maker_family != author_family:`
- **raw green:**

```
.                                                                        [100%]
1 passed, 15 deselected in 0.20s
```

## Not covered by a neutralization

The other detectors in the file (the I1 roster pairs, the per-seat-kind I2 pickers, the I3 removal checks) pin
behaviour that already held on the base or that the removal changed; this order declared two guarded elements (E1, E2) and
both are proven above. The I1, picker and I3 tests carry no neutralization here and are unproven by this record.
