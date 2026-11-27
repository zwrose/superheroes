# Bite-proof record — the driver takes its vendors from the seat map; an all-unseatable audits round halts (#2667)

Detector file: `plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py`, unedited between each red and its green. Each entry is a targeted, reversible edit to one production file (`plugins/superheroes/lib/round_driver.py`), restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Runs: `timeout 600 scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc-2667 -m pytest plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py -q -p no:cacheprovider -k <test name>`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture. The two guarded elements are the two the order declared; none is grouped.

## 1. The seat map's vendors feed `config.vendors` (`_dispatch`, `next` branch)

- **Axis:** I1 — a fresh `next` carrying `--seat-map` with a non-empty `liveVendors` and no `--vendors` sets the session's `config.vendors` to the sorted distinct `liveVendors`.
- **Detector:** `plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py::test_no_vendors_flag_the_seat_map_supplies_codex`.
- **Neutralization:** `round_driver.py`, in `_dispatch`: `overrides["vendors"] = map_vendors` became `pass`, so with no `--vendors` the vendor list is read from the default config again.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_no_vendors_flag_the_seat_map_supplies_codex _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_no_vendors_flag_the_seat_0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f4a96989520>

    def test_no_vendors_flag_the_seat_map_supplies_codex(tmp_path, capsys):
        # axis: I1 — a fresh `next` with a seat map and no `--vendors` reads config.vendors off liveVendors
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2667_vendors_from_seat_map.md
        d = str(tmp_path)
        path = _write_map(d, liveVendors=["codex", "claude"])
        rc, out = _cli_next_json(d, _guard_argv(d) + ["--seat-map", path], capsys)
        assert rc == 0 and out["ok"], out
        ok, state = RD.load_state(d)
        assert ok and state is not None
        cfg = state["config"]
>       assert cfg["vendors"] == ["claude", "codex"]
E       AssertionError: assert ['claude'] == ['claude', 'codex']
E         
E         Right contains one more item: 'codex'
E         Use -v to get more diff

/home/user/superheroes/.claude/worktrees/issue-2667/plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py::test_no_vendors_flag_the_seat_map_supplies_codex
1 failed, 17 deselected in 1.48s
```

- **Restore:** inverse edit (`pass` back to `overrides["vendors"] = map_vendors`, keyed on the `overrides["vendorsSource"] = "seat-map"` line below it).
- **Restore receipt** (the restored line, read back by `grep -n 'overrides\["vendors"\] = map_vendors'`; a second grep for the neutralized `pass` at that indent matched nothing):

```
19512:                    overrides["vendors"] = map_vendors
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 17 deselected in 1.51s
```

## 2. The halt after an all-unseatable audits fold (`_after_audits`)

- **Axis:** I2 and I3 — a fold of an audits round in which every target has no auditor ends the session `halted` / `audits-unseatable`, its certification reason carrying the cause text, before any later phase is entered.
- **Detector:** `plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py::test_an_all_unseatable_audits_fold_halts_with_the_cause`.
- **Neutralization:** `round_driver.py`, in `_after_audits`: the body of `if isinstance(unseatable, dict):` (`_halt_audits_unseatable(state, unseatable)` then `return`) became `pass`, so the mark is popped and the halt never happens; the round continues down the scoped-finder routing.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_an_all_unseatable_audits_fold_halts_with_the_cause ____________

    def test_an_all_unseatable_audits_fold_halts_with_the_cause():
        # axis: I2 and I3 — the fold marks every no-auditor entry and the round, and the session halts
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2667_vendors_from_seat_map.md
        state = _fix_state(_cfg(vendors=["claude"]))
        targets = _targets(state)
        ids = [t["id"] for t in targets]
        assert ids and all(t.get("auditorVendor") is None for t in targets)
        RD._fold_audits(state, state["config"], {"results": []})
>       assert state["terminal"] == "halted"
E       AssertionError: assert 'handed-back' == 'halted'
E         
E         - halted
E         + handed-back

/home/user/superheroes/.claude/worktrees/issue-2667/plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py:137: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_vendors_from_seat_map_2667.py::test_an_all_unseatable_audits_fold_halts_with_the_cause
1 failed, 17 deselected in 1.39s
```

- **Restore:** inverse edit (`pass` back to `_halt_audits_unseatable(state, unseatable)` and `return`).
- **Restore receipt** (the restored lines, read back by `grep -n -A 3 '_halt_audits_unseatable\|unseatable = state.pop'`; 1507 is the definition):

```
10199:    unseatable = state.pop("_auditsUnseatable", None)
10200-    if isinstance(unseatable, dict):
10201:        _halt_audits_unseatable(state, unseatable)
10202-        return
```

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 17 deselected in 1.24s
```

## Not proven (outside the declared set)

The order declared the two elements above. These other elements are asserted by tests in the file (each with an `# axis:` line) but have no neutralization and no red recorded here, so their protection is **unverified by a bite-proof**: the `--vendors` / seat-map disagreement refusal and the `liveVendors` validation in `_seat_map_vendors`; the per-entry `cause` and the `auditsUnseatable` round record in `_fold_audits`; the stale-mark pop at the top of `_fold_audits`; the post-fix verify gate running before the halt; the three causes in `receipt_disclosures.audit_unseatable_cause`; the `seat-missing` envelope's evidence for an audit slot; the healthy-session path.
