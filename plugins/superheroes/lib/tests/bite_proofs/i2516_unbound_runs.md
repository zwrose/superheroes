# Bite-proof record — a review record names a reviewer run with a nonce and no bound run folder (#2516)

Detector file: `plugins/superheroes/lib/tests/test_unbound_runs_2516.py`, unedited between each red and its green. Every entry is a targeted, reversible edit to one production file, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2516 -m pytest '<exact node id>' -q`, one test node each, output captured whole; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of each capture, and the `tmp_path` directory names are as the runner printed them (no secret, token, URL or personal data appears in any capture, so nothing is redacted). The eight guarded elements are the eight the order declared; none is grouped. Each target occurred exactly once in the edit's `old_string` (the edit tool refuses a non-unique match).

Files neutralized: `plugins/superheroes/lib/review_record_session.py` (entries 1 to 5) and `plugins/superheroes/lib/review_record.py` (entries 6 to 8).

## 1. The `not-in-extras` classification (`review_record_session.py`, `_cost_and_unbound`, line 310)

- **Axis:** a nonce no listed folder claims, with every listed folder naming a run of this session, is `not-in-extras`, not `unmatched`.
- **Detector:** `test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras`.
- **Neutralization:** `"case": "unmatched" if nonce in clash or foreign else "not-in-extras"})` became `"case": "unmatched"})`, so every listed run gets `unmatched`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_t1_a_run_whose_folder_the0')

    def test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras(tmp_path):
        # axis: a nonce no listed folder claims, with every listed folder naming a run of this session, is `not-in-extras`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1")})
>       assert rec["unboundRuns"] == [N2]
E       AssertionError: assert [{'case': 'un...ty-reviewer'}] == [{'seat': 'se...t-in-extras'}]
E         
E         At index 0 diff: {'case': 'unmatched', 'nonce': 'n2', 'seat': 'security-reviewer'} != {'seat': 'security-reviewer', 'nonce': 'n2', 'case': 'not-in-extras'}
E         Use -v to get more diff

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:51: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras
1 failed in 2.03s
```

**Restore:** the inverse edit put `"case": "unmatched" if nonce in clash or foreign else "not-in-extras"})` back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:310`): `        unbound.append({"seat": name, "nonce": nonce, "case": "unmatched" if nonce in clash or foreign else "not-in-extras"})`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.97s
```

## 2. The foreign-folder rule (`review_record_session.py`, `_cost_and_unbound`, lines 293 and 298)

- **Axis:** a folder that raised, is no dict, carries no nonce, or carries a nonce no run of this session has is foreign, and makes an unclaimed nonce `unmatched` instead of `not-in-extras`.
- **Detectors:** `test_unbound_runs_2516.py::test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched[other-nonce]` (shape a: a folder naming a nonce no run carries; this goes through the check at line 297) and `...[raises]` (shape b: a folder whose read raises; this goes through the `except` branch at line 293). Both reds are recorded.
- **Neutralization:** both marking sites, so that no folder is ever marked foreign: `foreign = True  # an unreadable dir may be the folder of a run it was never matched to` became `foreign = False  # ...` (the `except` branch), and under `if not (isinstance(n, str) and n and n in run_nonces):` the line `foreign = True` became `foreign = False`.

**Raw red, shape a** (`[other-nonce]`, exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched[other-nonce] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_t2_a_nonce_no_folder_clai0')
shape = 'other-nonce'

    @pytest.mark.parametrize("shape", ["other-nonce", "error-record", "no-nonce", "raises", "blank-nonce"])
    def test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched(tmp_path, shape):
        # axis: a folder that raised, is no dict, carries no nonce or one no run has makes an unclaimed nonce `unmatched`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        dirs = ["/run/n1", "/run/x"]
        runs = {"/run/n1": run("n1")}
        if shape == "other-nonce":
            runs["/run/x"] = run("n9")
        elif shape == "error-record":
            runs["/run/x"] = (None, "error")
        elif shape == "no-nonce":
            runs["/run/x"] = (dict(GOOD_RUN), None)
        elif shape == "blank-nonce":
            runs["/run/x"] = (dict(GOOD_RUN, runnerNonce=""), None)
        else:
            dirs = ["/run/n1", "/run/boom"]
        fake = Raising(runs=runs)
        out = send(tmp_path, two_seats(tmp_path).save(), fake, ci="green", runDirs=dirs)
        assert out["ok"], out
>       assert rr.read(7, readers=fake.readers())["unboundRuns"] == [N2_UNMATCHED]
E       AssertionError: assert [{'case': 'no...ty-reviewer'}] == [{'seat': 'se... 'unmatched'}]
E         
E         At index 0 diff: {'case': 'not-in-extras', 'nonce': 'n2', 'seat': 'security-reviewer'} != {'seat': 'security-reviewer', 'nonce': 'n2', 'case': 'unmatched'}
E         Use -v to get more diff

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched[other-nonce]
1 failed in 1.85s
```

**Raw red, shape b** (`[raises]`, exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched[raises] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_t2_a_nonce_no_folder_clai0')
shape = 'raises'

    @pytest.mark.parametrize("shape", ["other-nonce", "error-record", "no-nonce", "raises", "blank-nonce"])
    def test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched(tmp_path, shape):
        # axis: a folder that raised, is no dict, carries no nonce or one no run has makes an unclaimed nonce `unmatched`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        dirs = ["/run/n1", "/run/x"]
        runs = {"/run/n1": run("n1")}
        if shape == "other-nonce":
            runs["/run/x"] = run("n9")
        elif shape == "error-record":
            runs["/run/x"] = (None, "error")
        elif shape == "no-nonce":
            runs["/run/x"] = (dict(GOOD_RUN), None)
        elif shape == "blank-nonce":
            runs["/run/x"] = (dict(GOOD_RUN, runnerNonce=""), None)
        else:
            dirs = ["/run/n1", "/run/boom"]
        fake = Raising(runs=runs)
        out = send(tmp_path, two_seats(tmp_path).save(), fake, ci="green", runDirs=dirs)
        assert out["ok"], out
>       assert rr.read(7, readers=fake.readers())["unboundRuns"] == [N2_UNMATCHED]
E       AssertionError: assert [{'case': 'no...ty-reviewer'}] == [{'seat': 'se... 'unmatched'}]
E         
E         At index 0 diff: {'case': 'not-in-extras', 'nonce': 'n2', 'seat': 'security-reviewer'} != {'seat': 'security-reviewer', 'nonce': 'n2', 'case': 'unmatched'}
E         Use -v to get more diff

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:83: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t2_a_nonce_no_folder_claims_beside_a_foreign_folder_is_unmatched[raises]
1 failed in 1.84s
```

**Restore:** the inverse edits put `foreign = True` back at both sites.
**Restore receipt** (the restored lines, quoted from `review_record_session.py:293` and `:297-298`): `            foreign = True  # an unreadable dir may be the folder of a run it was never matched to` / `        if not (isinstance(n, str) and n and n in run_nonces):` / `            foreign = True`

**Raw green, shape a** (exit 0):

```
.                                                                        [100%]
1 passed in 1.83s
```

**Raw green, shape b** (exit 0):

```
.                                                                        [100%]
1 passed in 2.06s
```

## 3. The clash rule (`review_record_session.py`, `_cost_and_unbound`, line 307)

- **Axis:** a nonce two different listed folders claim is not bound: it is listed, as `unmatched`.
- **Detector:** `test_unbound_runs_2516.py::test_t2c_a_nonce_two_different_folders_claim_is_unmatched`.
- **Neutralization:** `if nonce is None or (nonce in seen and nonce not in clash):` became `if nonce is None or (nonce in seen):`, so a clashing nonce is treated as bound and not listed.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_t2c_a_nonce_two_different_folders_claim_is_unmatched ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_t2c_a_nonce_two_different0')

    def test_t2c_a_nonce_two_different_folders_claim_is_unmatched(tmp_path):
        # axis: two different folders claiming one nonce leave that run unbound, `unmatched`, though both folders are listed
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1"), "n2a": run("n2"), "n2b": run("n2")})
>       assert rec["unboundRuns"] == [N2_UNMATCHED]
               ^^^^^^^^^^^^^^^^^^
E       KeyError: 'unboundRuns'

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:90: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t2c_a_nonce_two_different_folders_claim_is_unmatched
1 failed in 2.18s
```

**Restore:** the inverse edit put `and nonce not in clash` back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:307`): `        if nonce is None or (nonce in seen and nonce not in clash):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.49s
```

## 4. The bound-run exclusion (`review_record_session.py`, `_cost_and_unbound`, line 307)

- **Axis:** a nonce exactly one listed folder claims is bound and never listed.
- **Detector:** `test_unbound_runs_2516.py::test_t3_a_run_whose_folder_is_listed_is_never_named`.
- **Neutralization:** `if nonce is None or (nonce in seen and nonce not in clash):` became `if nonce is None:`, so every nonce-carrying run is listed.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_t3_a_run_whose_folder_is_listed_is_never_named ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_t3_a_run_whose_folder_is_0')

    def test_t3_a_run_whose_folder_is_listed_is_never_named(tmp_path):
        # axis: a nonce exactly one folder claims is bound and never listed, in the record or the account
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        session = two_seats(tmp_path).save()
        runs = {"n1": run("n1"), "n2": run("n2")}
>       assert "unboundRuns" not in written(tmp_path, session, runs)
E       AssertionError: assert 'unboundRuns' not in {'ok': True, 'url': 'http://c/3', 'carriedRechecks': [], 'checked': ['CI on bbbbbbb: green', 'Reviewers that ran: none'], ...}
E        +  where {'ok': True, 'url': 'http://c/3', 'carriedRechecks': [], 'checked': ['CI on bbbbbbb: green', 'Reviewers that ran: none'], ...} = written(PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_t3_a_run_whose_folder_is_0'), '/tmp/claude-0/pytest-of-root/pytest-10/test_t3_a_run_whose_folder_is_0/session', {'n1': ({'source': 'codex', 'engineModel': 'gpt-5.6-sol', 'viewHeadSha': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', '...wHeadSha': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'observation': {'tokens': 100, 'wallSeconds': 120}, ...}, None)})

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:99: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t3_a_run_whose_folder_is_listed_is_never_named
1 failed in 2.60s
```

**Restore:** the inverse edit put `or (nonce in seen and nonce not in clash)` back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:307`): `        if nonce is None or (nonce in seen and nonce not in clash):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.00s
```

## 5. The account carry (`review_record_session.py`, `account_from_session`, line 1724)

- **Axis:** the account lists the unbound runs exactly when there are any.
- **Detector:** `test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras`.
- **Neutralization:** `**({"unboundRuns": unbound_runs} if unbound_runs else {}),` became `**({}),`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-12/test_t1_a_run_whose_folder_the0')

    def test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras(tmp_path):
        # axis: a nonce no listed folder claims, with every listed folder naming a run of this session, is `not-in-extras`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1")})
>       assert rec["unboundRuns"] == [N2]
               ^^^^^^^^^^^^^^^^^^
E       KeyError: 'unboundRuns'

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:51: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras
1 failed in 2.00s
```

**Restore:** the inverse edit put the entry back.
**Restore receipt** (the restored line, quoted from `review_record_session.py:1724`): `            **({"unboundRuns": unbound_runs} if unbound_runs else {}),`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.01s
```

## 6. The record carry (`review_record.py`, `build_record`, lines 2122-2123)

- **Axis:** a reviewer run with a nonce and no bound run folder is named in the record whenever the account lists one.
- **Detector:** `test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras`.
- **Neutralization:** `for e in a["unboundRuns"]]} if a.get("unboundRuns") else {}),` became `for e in a["unboundRuns"]]} if False and a.get("unboundRuns") else {}),`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-14/test_t1_a_run_whose_folder_the0')

    def test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras(tmp_path):
        # axis: a nonce no listed folder claims, with every listed folder naming a run of this session, is `not-in-extras`
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        rec = written(tmp_path, two_seats(tmp_path).save(), {"n1": run("n1")})
>       assert rec["unboundRuns"] == [N2]
               ^^^^^^^^^^^^^^^^^^
E       KeyError: 'unboundRuns'

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:51: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t1_a_run_whose_folder_the_extras_leave_out_is_named_not_in_extras
1 failed in 2.00s
```

**Restore:** the inverse edit removed `False and `.
**Restore receipt** (the restored line, quoted from `review_record.py:2123`): `                            for e in a["unboundRuns"]]} if a.get("unboundRuns") else {}),`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.15s
```

## 7. The validator's case check (`review_record.py`, `_validate`, line 1049)

- **Axis:** the writer refuses an `unboundRuns` entry whose `case` is not one of `UNBOUND_RUN_CASES`, naming `unboundRuns`.
- **Detector:** `test_unbound_runs_2516.py::test_t5_the_validator_refuses_a_malformed_part_by_name_and_posts_nothing[unknown-case]`.
- **Neutralization:** `and e["case"] in UNBOUND_RUN_CASES for e in unbound), "unboundRuns")` became `for e in unbound), "unboundRuns")`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_t5_the_validator_refuses_a_malformed_part_by_name_and_posts_nothing[unknown-case] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-16/test_t5_the_validator_refuses_0')
bad = [{'seat': 'security-reviewer', 'nonce': 'n2', 'case': 'elsewhere'}]

    @pytest.mark.parametrize("bad", [
        [dict(N2, case="elsewhere")],
        [dict(N2, case="")],
        [dict(N2, extra=1)],
        [{"seat": "s", "nonce": "n"}],
        [dict(N2, nonce="")],
        [dict(N2, nonce="  ")],
        [dict(N2, nonce=5)],
        [dict(N2, seat="")],
        [dict(N2, seat=None)],
        [N2, "not an entry"],
        dict(N2),
        "unbound",
    ], ids=["unknown-case", "empty-case", "extra-key", "missing-key", "blank-nonce", "space-nonce", "int-nonce", "blank-seat",
            "none-seat", "non-dict-entry", "dict-not-list", "string-not-list"])
    def test_t5_the_validator_refuses_a_malformed_part_by_name_and_posts_nothing(tmp_path, bad):
        # axis: the writer's validation of the part: exactly the keys seat, nonce, case; non-blank seat and nonce; a known case; a list
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        fake = trr.Fake()
        out = rr.write(trr.put(tmp_path, trr.account(unboundRuns=bad)), str(tmp_path), fake.readers())
>       assert (out["ok"], out["reason"], out["detail"]) == (False, "review-account-invalid", "unboundRuns"), out
                           ^^^^^^^^^^^^^
E       KeyError: 'reason'

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:153: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t5_the_validator_refuses_a_malformed_part_by_name_and_posts_nothing[unknown-case]
1 failed in 2.20s
```

**Restore:** the inverse edit put `and e["case"] in UNBOUND_RUN_CASES` back.
**Restore receipt** (the restored line, quoted from `review_record.py:1049`): `            and e["case"] in UNBOUND_RUN_CASES for e in unbound), "unboundRuns")`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.01s
```

## 8. The summary line (`review_record.py`, `_unbound_line`, line 2858)

- **Axis:** the record summary carries an `Unbound runs:` line, naming each run at level 0 and the count at the compact levels, whenever the record lists any.
- **Detector:** `test_unbound_runs_2516.py::test_t6_level_zero_names_each_run_and_the_compact_levels_give_the_count`.
- **Neutralization:** `if not (isinstance(runs, list) and runs):` (the `None` guard of `_unbound_line`) became `if True or not (isinstance(runs, list) and runs):`, so the function always returns `None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_t6_level_zero_names_each_run_and_the_compact_levels_give_the_count ____

    def test_t6_level_zero_names_each_run_and_the_compact_levels_give_the_count():
        rec = trr.build(trr.account(unboundRuns=[N2]))
        # bite-proof: plugins/superheroes/lib/tests/bite_proofs/i2516_unbound_runs.md
        # axis: level 0 names every run (seat, nonce, case) and the compact levels give only the count
>       assert unbound_lines(rec, 0) == ["Unbound runs: security-reviewer nonce n2 (not-in-extras)."]
E       AssertionError: assert [] == ['Unbound run...-in-extras).']
E         
E         Right contains one more item: 'Unbound runs: security-reviewer nonce n2 (not-in-extras).'
E         Use -v to get more diff

/home/user/wt-2516/plugins/superheroes/lib/tests/test_unbound_runs_2516.py:176: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_unbound_runs_2516.py::test_t6_level_zero_names_each_run_and_the_compact_levels_give_the_count
1 failed in 2.02s
```

**Restore:** the inverse edit removed `True or `.
**Restore receipt** (the restored line, quoted from `review_record.py:2858`): `    if not (isinstance(runs, list) and runs):`

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 1.81s
```

## Not proven (outside the declared set)

These carry an `# axis:` line or a test but no neutralization of their own, so nobody should read them as covered by this record: the `unmatched`-case token of `_unbound_line`'s level-0 text beyond the two seats in T6; the `[REDACTED SEAT]` / `[REDACTED NONCE]` display of the record carry and the claim-check exemption of the unbound line (`l is not unbound_line`, `review_record.py`, tested only by `test_t6b_...`); the validator legs other than the unknown-case leg (extra key, missing key, blank, non-string or non-list shapes: the tests drive them, none was neutralized); the `listed-twice` and `listed-once` legs of T3b and the figureless-folder test T1b (T1b guards the same foreign rule as entry 2 from the other side); the T4 and T7 assertions on the same-pass wrapper `_session_cost`; and the empty-list-writes-no-key edge in `build_record` (`a.get("unboundRuns")` truthiness, driven by `test_t5b_...`).
