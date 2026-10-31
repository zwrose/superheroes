# Bite-proof record: c2_wo2_read_parts_evidence

Detector: `plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py`, guarding the read-list binding in
`round_driver._assemble_dispatch_evidence` and the carry in `engine_dispatch.run_execution_record`.

Declared guarded-element set (from the order): E1 the mismatch refusal; E2 the adoption of the runner's list when none
landed; E3 the carry in `run_execution_record`. Every neutralization was one targeted edit with the edit tool, restored by
the inverse edit; tests unedited throughout. Tests selected with `-k` as the order's command specifies (the run line
prints the selected and deselected counts, shown below). Command, every run:
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo -m pytest plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py -q -k <expr>`.
Captures are well under the 32 KiB per-element ceiling; the only redaction is the `UV_NATIVE_TLS` tool warning line
and the pytest temp paths, which are shown as the tool printed them (no secrets present).

## E1: mismatch refusal (`round_driver.py`, `_assemble_dispatch_evidence`)

- Axis: a landed panel read list that differs from the runner's graded list is refused `evidence-read-parts-mismatch`.
- Neutralization: the comparison's right operand `round_records.payload_sha256(runner_parts)` replaced by
  `round_records.payload_sha256(envelope_payload["readParts"])`, so the list is compared to itself and the branch never fires.
- Test: `-k differs_from_the_runners` (1 selected).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_landed_list_that_differs_from_the_runners_is_refused __________
    def test_a_landed_list_that_differs_from_the_runners_is_refused(tmp_path, adapters, monkeypatch):
        # axis: the panel seat's read list must equal the list in the runner's graded result; a different landed list refuses
        d, run_dir, path, _env, before = _landed(
            tmp_path, monkeypatch, RUNNER, {"findings": [], "readParts": OTHER}, "c2-differs")
        out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
>       assert out["ok"] is False
E       assert True is False
/home/user/wt-2218-wo2/plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py:73: AssertionError
FAILED plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py::test_a_landed_list_that_differs_from_the_runners_is_refused
1 failed, 8 deselected in 2.30s
```

(fixture-argument lines `tmp_path = ...`, `adapters = ...`, `monkeypatch = ...` elided from the quote; 3 lines.)

- Restore: inverse edit; restored lines quoted back (`round_driver.py` lines 14404-14405):
  `if (round_records.payload_sha256(envelope_payload["readParts"])` / `!= round_records.payload_sha256(runner_parts)):`.
  `git diff --stat -- plugins/superheroes/lib/round_driver.py` after restore: `1 file changed, 21 insertions(+)` (the intended change only).
- Raw green:

```
.                                                                        [100%]
1 passed, 8 deselected in 2.05s
```

## E2: adoption of the runner's list when none landed (`round_driver.py`)

- Axis: a landing with no `readParts` is recorded with the runner's list.
- Neutralization: the two lines `envelope_payload["readParts"] = list(runner_parts)` and `payload_adopted = True`
  replaced by `pass`.
- Test: `-k no_list_takes_the_runners` (1 selected).
- Raw red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
______ test_a_landing_with_no_list_takes_the_runners_and_the_row_shows_it ______
    def test_a_landing_with_no_list_takes_the_runners_and_the_row_shows_it(tmp_path, adapters, monkeypatch):
        # axis: a landing that names no list is recorded with the runner's list, and the record's reviewer row shows it
        d, run_dir, path, _env, _before = _landed(
            tmp_path, monkeypatch, RUNNER, {"findings": []}, "c2-adopt")
        out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
        assert out["ok"], out
        stored = _stored(out)
>       assert stored["payload"]["readParts"] == RUNNER
E       KeyError: 'readParts'
/home/user/wt-2218-wo2/plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py:87: KeyError
FAILED plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py::test_a_landing_with_no_list_takes_the_runners_and_the_row_shows_it
1 failed, 8 deselected in 2.47s
```

(fixture-argument lines elided from the quote; 3 lines.)

- Restore: inverse edit; restored lines quoted back: `envelope_payload["readParts"] = list(runner_parts)` /
  `payload_adopted = True` (inside the `else:` of the `"readParts" in envelope_payload` test).
  `git diff --stat -- plugins/superheroes/lib/round_driver.py` after restore: `1 file changed, 21 insertions(+)`.
- Raw green:

```
.                                                                        [100%]
1 passed, 8 deselected in 2.42s
```

## E3: the carry in `run_execution_record` (`engine_dispatch.py`)

- Axis: the runner's record of a review run holds the `readParts` of its admitted result.
- Neutralization: `record["readParts"] = res["readParts"]` replaced by `pass` (the line deleted in effect).
- Tests: `-k "run_execution_record_carries or equal_lists_are_accepted or differs_from_the_runners"` (3 selected).
- Raw red:

```
FFF                                                                      [100%]
=================================== FAILURES ===================================
_________ test_a_landed_list_that_differs_from_the_runners_is_refused __________
        assert out["ok"] is False
        assert out["reason"] == RD.EVIDENCE_READ_PARTS_MISMATCH_REFUSAL == "evidence-read-parts-mismatch"
        assert out["landedReadPartsSha256"] == RR.payload_sha256(OTHER)
>       assert out["runnerReadPartsSha256"] == RR.payload_sha256(RUNNER)
E       AssertionError: assert '4f53cda18c2b...f11161202b945' == '5242ca9cab0d...479bc990072c0'
E         
E         - 5242ca9cab0d3aa4627cf7694af592610e9b5708c279f7100b7479bc990072c0
E         + 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945

/home/user/wt-2218-wo2/plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py:76: AssertionError
___________________ test_equal_lists_are_accepted_unchanged ____________________
    def test_equal_lists_are_accepted_unchanged(tmp_path, adapters, monkeypatch):
        # axis: a landed list equal to the runner's is accepted and kept as it landed
        payload = {"findings": [], "readParts": RUNNER}
        d, run_dir, _path, _env, _before = _landed(tmp_path, monkeypatch, RUNNER, payload, "c2-equal")
        out = RD.cmd_record_result(d, SEAT, evidence_run_dir=run_dir)
>       assert out["ok"], out
E       AssertionError: {'ok': False, 'reason': 'evidence-read-parts-mismatch', 'seat': 'code-reviewer', 'landedReadPartsSha256': '5242ca9cab0d3aa4627cf7694af592610e9b5708c279f7100b7479bc990072c0', ...}
E       assert False

/home/user/wt-2218-wo2/plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py:100: AssertionError
______ test_run_execution_record_carries_the_runners_list_on_a_review_run ______
    def test_run_execution_record_carries_the_runners_list_on_a_review_run(tmp_path, adapters, monkeypatch):
        # axis: the runner's record of a review run holds the readParts of its admitted result, and no key when it had none
        _d, run_dir, _path, _env, _before = _landed(
            tmp_path, monkeypatch, RUNNER, {"findings": []}, "c2-carry")
        record, err = ED.run_execution_record(run_dir)
        assert err is None
>       assert record["readParts"] == RUNNER
E       KeyError: 'readParts'

/home/user/wt-2218-wo2/plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py:144: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py::test_a_landed_list_that_differs_from_the_runners_is_refused
FAILED plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py::test_equal_lists_are_accepted_unchanged
FAILED plugins/superheroes/lib/tests/test_read_parts_evidence_c2.py::test_run_execution_record_carries_the_runners_list_on_a_review_run
3 failed, 6 deselected in 4.26s
```

(Elided from the quote, nothing else changed: the `tmp_path = ...`, `adapters = ...`, `monkeypatch = ...` argument lines of each
failure, and the first lines of the first test's body above its `assert out["ok"]` line.)

- What this shows about E1's test: with the carry gone the runner list reads as `[]`, so the mismatch test does not pass
  vacuously: it still sees a refusal (the landed list differs from `[]` too), but it fails on its assertion that the runner
  hash equals the hash of the real runner list. The equal-lists test goes red because the equal landed list now differs from `[]`.
  What the mismatch refusal alone cannot tell apart from this case is "runner list absent" versus "runner list present and different";
  the runner-hash assertion and the equal-lists test are what separate them.
- Restore: inverse edit; restored lines quoted back (`engine_dispatch.py` lines 7515-7517):
  `# the reviewer's read list as the runner admitted it; a consumer binds a landed list to this one` /
  `if isinstance(res, dict) and isinstance(res.get("readParts"), list):` / `record["readParts"] = res["readParts"]`.
  `git diff --stat -- plugins/superheroes/lib/engine_dispatch.py` after restore: `1 file changed, 3 insertions(+)`.
- Raw green:

```
...                                                                      [100%]
3 passed, 6 deselected in 4.91s
```
