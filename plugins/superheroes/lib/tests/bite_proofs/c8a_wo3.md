# C8a WO3 bite-proof: the environment reader's detector classes, and the read-only and slug-once detectors

**Provenance:** claude write channel, `sonnet`.

**Run command.** `scripts/pinned-python -B -m pytest "<node>" -q -p no:cacheprovider`, one node at a time, from the worktree root. Each pytest capture below omits the one `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line `uv` prints before pytest starts; that line is not pytest output. Nothing else is trimmed except where a capture is labelled incomplete. No fixture holds a secret, so nothing is redacted.

**Restore.** Every neutralization is a targeted Edit and every restore is the inverse Edit, never a checkout. The restore receipt quotes the restored line.

**Unrunnable here.** The git-commit signing step fails inside the implementer's sandbox, so any test whose fixture makes a git commit errors at setup with `fatal: failed to write commit object`. Those detectors are marked `Unrunnable here — the orchestrator runs red and green outside the sandbox`. The exact command is the run command above with the node; the environment that can run it is the orchestrator's, outside the sandbox. The substitute evidence is the manifest entry (`old` is the exact current text, once in its file) at `/tmp/claude-0/-home-user-superheroes/bd2af963-41b8-5ccb-b3bf-9cbed29d3a97/scratchpad/manifests/wo3.json`. The orchestrator owns the outstanding captures.

## Summary

| Element | Axis | Proving test | Runs here | Verdict |
|---|---|---|---|---|
| C4bFU3 class 1, retry-keeps-or-asks | an unchanged value equal to the confirmed id is kept on a retry | `test_retry_with_the_same_environment_keeps_the_confirmed_id` | yes | proven |
| C4bFU3 class 2, compare-verdict | a picked id that differs from the compared id is `mismatched` | `test_compare_mismatched_returns_the_current_picked_environment` | yes | proven |
| C4bFU3 class 3, refuses-malformed | a `before` that is not an environment id is refused | `test_pick_refuses_a_malformed_before` | yes | proven |
| C4bFU3 class 4, never-raises/unreadable | an unexpected exception in the read is reported as unreadable | `test_unexpected_exception_is_reported_as_unreadable` | yes | proven |
| C4bFU3 class 5, snapshot-reads | a snapshot returns the well-formed picked id | `test_snapshot_reads_the_current_value_and_none_when_never_picked` | yes | proven |
| C5bFU2-a | the readiness read behind `still` never backfills the storage-mode record | `test_cli_still_with_hero_evidence_and_no_core_md_writes_no_mode_record` | git fixture | Unrunnable here |
| FU7a-a | `still` and `report` create no missing ledger root | `test_still_and_report_do_not_create_a_missing_ledger_root` | git fixture | Unrunnable here |
| FU7b-a | `still` and `report` write nothing under the ledger root | `test_B10_one_store_report_and_still_write_nothing` | git fixture | Unrunnable here |
| FU7c-a | the launch day is the start day, not the reservation day | `test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready` | git fixture | Unrunnable here |
| FU7d-a | no title lookup for a batch with no report | `test_a_batch_with_no_report_looks_up_no_titles` | git fixture | Unrunnable here |
| C7FU2-a | the repository slug is resolved once per tick | `test_the_repository_slug_is_resolved_once_per_tick` | git fixture | Unrunnable here |
| C7FU2-b | the cached validator rides page one only | `test_a_primed_validator_rides_page_one_only_and_a_multi_page_read_clears_it` | git fixture | Unrunnable here |
| C7FU2-c | a 200 after an empty cached read returns the response's comments | `test_a_note_arriving_after_an_empty_cached_read_is_surfaced` | git fixture | Unrunnable here |

The proofs for C4bFU2-a and the S-note elements are in their existing records: `wo_b_1771_setup_sitting_text.md` and `cloud_doctrine_pointers.md`.

## Declared guarded-element set

C4bFU3 as five failure-mode classes (below); C5bFU2-a; FU7a-a; FU7b-a; FU7c-a; FU7d-a; C7FU2-a; C7FU2-b; C7FU2-c.

## C4bFU3 — the classes of `test_cloud_environment.py`

Each class is named by its failure mode, and each detector test that cites this record sits in exactly one.

1. **retry-keeps-or-asks** (a retry that should keep the confirmed id asks again, or one that should ask keeps an id): `test_first_pick_confirmed_by_name_returns_the_id`, `test_retry_with_the_same_environment_keeps_the_confirmed_id` (representative), `test_retry_with_a_different_environment_returns_the_new_id`, `test_retry_unchanged_value_that_is_not_the_confirmed_id_asks_again`, `test_retry_with_a_missing_value_asks_again`, `test_retry_with_an_unreadable_file_asks_again`, `test_cli_confirmed_retry`.
2. **compare-verdict** (the wrong one of matched, mismatched and unchecked): `test_compare_matched_when_the_id_is_the_picked_environment`, `test_compare_mismatched_returns_the_current_picked_environment` (representative), `test_compare_unchecked_without_a_valid_current_pick`, `test_compare_unchecked_for_a_malformed_environment`, `test_compare_cli_exit_codes`.
3. **refuses-malformed** (a value that is not an environment id is accepted): `test_pick_refuses_a_malformed_before` (representative), `test_pick_refuses_a_malformed_before_before_reading_the_file`, `test_pick_refuses_a_malformed_confirmed`.
4. **never-raises/unreadable** (an exception or an unreadable file escapes, or reads as an id): `test_unexpected_exception_is_reported_as_unreadable` (representative), `test_compare_never_raises`, `test_unreadable_settings_never_give_an_id`, `test_unresolvable_config_dir_is_unreadable_not_a_raise`.
5. **snapshot-reads** (the snapshot returns the wrong value for a readable file): `test_snapshot_reads_the_current_value_and_none_when_never_picked` (representative), `test_reader_follows_the_account_config_dir`, `test_cli_relative_config_dir_with_relative_cwd_reads`.

The three tests with their own records are cited by name to `wo_a_1771_environment_reader.md` and are not in a class here: `test_pick_unchanged_setting_asks_again_with_no_id` (section R1), `test_pick_missing_setting_asks_again_with_no_id` (sections R2 and R3), `test_first_pick_unchanged_asks_to_confirm_by_name` (section R6).

**Unproven (no class):** `test_settings_path_has_one_home_and_the_external_spelling_is_pinned`, `test_pick_changed_setting_returns_the_new_id`, `test_no_message_asks_to_type_or_paste_an_id`, `test_cli_exit_codes`. Each cites this record for its axis line, and none has a neutralization run here.

**Unproven members of a class:** the representative stands for its class's other members by failure mode; those members were not neutralized themselves.

### Class 1, retry-keeps-or-asks. Representative: `test_retry_with_the_same_environment_keeps_the_confirmed_id`

**guarded element:** the kept-confirmed condition in `pick`, `plugins/superheroes/lib/cloud_environment.py:130`. **axis:** an unchanged value equal to the confirmed id returns `picked`/`kept-confirmed` with that id.

**neutralization:** `if value == before and confirmed is not None and value == confirmed:` became `if value == before and confirmed is not None and value != confirmed:`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_retry_with_the_same_environment_keeps_the_confirmed_id __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-90/test_retry_with_the_same_envir0')

    def test_retry_with_the_same_environment_keeps_the_confirmed_id(tmp_path):
        # axis: retry-keeps-or-asks — the same environment on a retry keeps the confirmed id — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
        _write(env, _with_value(ENV_ID))
        result = CE.pick(before=ENV_ID, confirmed=ENV_ID, env=env)
>       assert result == {"action": "picked", "reason": "kept-confirmed", "environment": ENV_ID,
                          "message": CE._KEPT}
E       assert {'action': 'n...n it's done."} == {'action': 'p...environment.'}
E         
E         Differing items:
E         {'reason': 'pick-unchanged'} != {'reason': 'kept-confirmed'}
E         {'action': 'not-picked'} != {'action': 'picked'}
E         {'message': "I can't see a new pick yet. In Claude Code on this account, run /remote-env, choose the environment you made for this project by its name, and tell me when it's done."} != {'message': 'Got it: I can see you kept the same environment.'}
E         {'environment': None} != {'environment': 'env_01ABCdef'}
E         Use -v to get more diff

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:263: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_retry_with_the_same_environment_keeps_the_confirmed_id
1 failed in 0.14s
EXIT=1
```

**restore:** the inverse edit, `value != confirmed` back to `value == confirmed`.

**restore receipt:** `grep -n "confirmed is not None and value" cloud_environment.py` printed `130:        if value == before and confirmed is not None and value == confirmed:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.11s
EXIT=0
```

### Class 2, compare-verdict. Representative: `test_compare_mismatched_returns_the_current_picked_environment`

**guarded element:** the match test in `compare`, `cloud_environment.py:154`. **axis:** a compared id that differs from the picked one is `mismatched` and carries the picked id.

**neutralization:** `if environment == current:` became `if True:`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_compare_mismatched_returns_the_current_picked_environment ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-92/test_compare_mismatched_return0')

    def test_compare_mismatched_returns_the_current_picked_environment(tmp_path):
        # axis: compare-verdict — a different picked environment: mismatched, with the picked id — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
        _write(env, _with_value(OTHER_ENV_ID))
        result = CE.compare(ENV_ID, env=env, cwd=str(tmp_path))
>       assert result["action"] == "mismatched"
E       AssertionError: assert 'matched' == 'mismatched'
E         
E         - mismatched
E         ? ---
E         + matched

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:353: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_compare_mismatched_returns_the_current_picked_environment
1 failed in 0.13s
EXIT=1
```

**restore:** the inverse edit, `if True:` back to `if environment == current:`.

**restore receipt:** `grep -n "if environment == current" cloud_environment.py` printed `154:        if environment == current:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.13s
EXIT=0
```

### Class 3, refuses-malformed. Representative: `test_pick_refuses_a_malformed_before`

**guarded element:** the `before` grammar check in `pick`, `cloud_environment.py:120`. **axis:** a `before` that is not an environment id (`abc`, empty, `env_`, an int) is refused with `before-invalid`.

**neutralization:** `if before is not None and not _is_id(before):` became `if before is not None and False:`.

**raw red (incomplete: the run was piped through `tail -40`, so the first parametrized failures and the pytest header are not shown; all four parametrized cases failed, per the last line):**
```
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-94/test_pick_refuses_a_malformed_2')
before = 'env_'

    @pytest.mark.parametrize("before", ["abc", "", "env_", 123])
    def test_pick_refuses_a_malformed_before(tmp_path, before):
        # axis: refuses-malformed — a before value that is not an environment id is refused — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
        _write(env, _with_value(OTHER_ENV_ID))
        result = CE.pick(before=before, env=env)
>       assert result["action"] == "refused" and result["reason"] == "before-invalid"
E       AssertionError: assert ('picked' == 'refused'
E         
E         - refused
E         + picked)

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:198: AssertionError
__________________ test_pick_refuses_a_malformed_before[123] ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-94/test_pick_refuses_a_malformed_3')
before = 123

    @pytest.mark.parametrize("before", ["abc", "", "env_", 123])
    def test_pick_refuses_a_malformed_before(tmp_path, before):
        # axis: refuses-malformed — a before value that is not an environment id is refused — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
        _write(env, _with_value(OTHER_ENV_ID))
        result = CE.pick(before=before, env=env)
>       assert result["action"] == "refused" and result["reason"] == "before-invalid"
E       AssertionError: assert ('picked' == 'refused'
E         
E         - refused
E         + picked)

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:198: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_refuses_a_malformed_before[abc]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_refuses_a_malformed_before[]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_refuses_a_malformed_before[env_]
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_pick_refuses_a_malformed_before[123]
4 failed in 0.23s
```

**restore:** the inverse edit, `and False:` back to `and not _is_id(before):`.

**restore receipt:** `grep -n "if before is not None" cloud_environment.py` printed `120:        if before is not None and not _is_id(before):`.

**raw green:**
```
....                                                                     [100%]
4 passed in 0.13s
EXIT=0
```

### Class 4, never-raises/unreadable. Representative: `test_unexpected_exception_is_reported_as_unreadable`

**guarded element:** the `except Exception:` that closes `snapshot`, `cloud_environment.py:108`. **axis:** an exception raised by the read is reported as `settings-unreadable`, never raised.

**neutralization:** the line after `return {"action": "read", "reason": None, "environment": value}` changed from `    except Exception:` to `    except ZeroDivisionError:`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_unexpected_exception_is_reported_as_unreadable ______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-96/test_unexpected_exception_is_r0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fb3f89eb530>

    def test_unexpected_exception_is_reported_as_unreadable(tmp_path, monkeypatch):
        # axis: never-raises/unreadable — an unexpected exception in the read is reported as unreadable — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
    
        def boom(*args, **kwargs):
            raise RuntimeError("boom")
    
        monkeypatch.setattr(CE, "_read", boom)
>       snap = CE.snapshot(env=env)
               ^^^^^^^^^^^^^^^^^^^^

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:185: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/c8a-wo3/plugins/superheroes/lib/cloud_environment.py:101: in snapshot
    readable, value = _read(env, cwd)
                      ^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

args = ({'CLAUDE_CONFIG_DIR': '/tmp/claude-0/pytest-of-root/pytest-96/test_unexpected_exception_is_r0/acct', 'HOME': '/tmp/claude-0/pytest-of-root/pytest-96/test_unexpected_exception_is_r0'}, None)
kwargs = {}

    def boom(*args, **kwargs):
>       raise RuntimeError("boom")
E       RuntimeError: boom

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:182: RuntimeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_unexpected_exception_is_reported_as_unreadable
1 failed in 0.19s
EXIT=1
```

**restore:** the inverse edit, `except ZeroDivisionError:` back to `except Exception:`.

**restore receipt:** `sed -n 107,108p cloud_environment.py` printed `        return {"action": "read", "reason": None, "environment": value}` then `    except Exception:`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.11s
EXIT=0
```

### Class 5, snapshot-reads. Representative: `test_snapshot_reads_the_current_value_and_none_when_never_picked`

**guarded element:** the id returned by `snapshot`, `cloud_environment.py:107`. **axis:** a readable, well-formed picked value is returned as `environment`.

**neutralization:** `return {"action": "read", "reason": None, "environment": value}` became `return {"action": "read", "reason": None, "environment": None}`.

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_snapshot_reads_the_current_value_and_none_when_never_picked _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-98/test_snapshot_reads_the_curren0')

    def test_snapshot_reads_the_current_value_and_none_when_never_picked(tmp_path):
        # axis: snapshot-reads — the current well-formed value, or none-set when never picked — see bite-proof record c8a_wo3.md
        env = _env(tmp_path)
        assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
        _write(env, {"remote": {}})
        assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
        _write(env, _with_value("env_ab-cd"))
        assert CE.snapshot(env=env) == {"action": "read", "reason": "none-set", "environment": None}
        _write(env, _with_value(ENV_ID))
>       assert CE.snapshot(env=env) == {"action": "read", "reason": None, "environment": ENV_ID}
E       AssertionError: assert {'action': 'r...onment': None} == {'action': 'r...env_01ABCdef'}
E         
E         Omitting 2 identical items, use -vv to show
E         Differing items:
E         {'environment': None} != {'environment': 'env_01ABCdef'}
E         Use -v to get more diff

/home/user/c8a-wo3/plugins/superheroes/lib/tests/test_cloud_environment.py:132: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_environment.py::test_snapshot_reads_the_current_value_and_none_when_never_picked
1 failed in 0.15s
EXIT=1
```

**restore:** the inverse edit, `"environment": None}` back to `"environment": value}`.

**restore receipt:** `sed -n 107p cloud_environment.py` printed `        return {"action": "read", "reason": None, "environment": value}`.

**raw green:**
```
.                                                                        [100%]
1 passed in 0.13s
EXIT=0
```

## C5bFU2-a — the readiness read behind `still` never backfills the storage-mode record

**guarded element:** the `persist_backfill=False` the readiness call passes in `launch_report.still_check`. **axis:** `launcher still` on a world with hero evidence and no `core.md` or registry leaves `mode_registry.read_registry(...)` as `None` and the store, repository and ledger-root tree unchanged.

**neutralization:** in `launch_report.py`, `repo_root, reported=None, root=root, persist_backfill=False)` became `repo_root, reported=None, root=root, persist_backfill=True)`.

**detector:** `test_launch_report_verbs.py::test_cli_still_with_hero_evidence_and_no_core_md_writes_no_mode_record`, a git-commit fixture (`_init_repo`).

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `C5bFU2-a`.

## FU7a-a — `still` and `report` create no missing ledger root

**guarded element:** `create=False` on the ledger read in `launch_report.still_check`. **axis:** with `LEDGER_ROOT_ENV` pointing at a path that does not exist, `still` and `report` report an empty ledger and the path still does not exist.

**neutralization:** in `launch_report.py`, `read = ll.read(repo_root, create=False)` became `read = ll.read(repo_root, create=True)`.

**detector:** `test_still_and_report_do_not_create_a_missing_ledger_root`, a git-commit fixture (`_init_repo`).

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `FU7a-a`.

## FU7b-a — `still` and `report` write nothing under the ledger root

**guarded element:** the ledger root in `_snapshot` of `test_B10_one_store_report_and_still_write_nothing`. **axis:** a file made under the ledger root by `still` changes the whole-tree snapshot.

**neutralization:** one line inserted before `candidates = _fallbacks(...)` in `launch_report.still_check`: `open(os.path.join(ll.resolve_root(repo_root)["root"], "probe"), "w").close()`. `os` is already imported there, so no import is added or removed. Restored by the inverse Edit, which removes the line.

**detector:** `test_B10_one_store_report_and_still_write_nothing`, a git-commit fixture (the `world` fixture calls `_init_repo`).

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `FU7b-a`.

## FU7c-a — the launch day is the start day

**guarded element:** `startedTs` read before `reservedTs` in `launch_report.launch_day`. **axis:** `_day_launch` reserves one day before it starts, and asserts `LR.launch_day(info) == day`.

**neutralization:** `stamp = info.get("startedTs", info.get("reservedTs"))` became `stamp = info.get("reservedTs", info.get("startedTs"))`.

**detector:** the B6 tests, for example `test_B6_a_reported_fact_clears_only_on_a_check_after_the_start_day_that_reads_ready`, which build their launches through `_day_launch`; a git-commit fixture.

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `FU7c-a`.

## FU7d-a — no title lookup for a batch with no report

**guarded element:** the `wanted` gate on the title lookup in `launcher.launch_report_for_batch`. **axis:** an all-local, cloud-off batch makes zero title lookups and reports `None`.

**neutralization:** `"title": _report_title(lookup, repo_root, issue) if wanted else None,` became `"title": _report_title(lookup, repo_root, issue),`.

**detector:** `test_a_batch_with_no_report_looks_up_no_titles`, a git-commit fixture (`world`).

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `FU7d-a`.

## C7FU2-a — the repository slug is resolved once per tick

**guarded element:** `_slug_for_read` in `wave_watch._read_issue_comments`. **axis:** one `gh repo view` per tick, however many readers need the slug.

**neutralization:** in `_read_issue_comments`, the line `slug = _slug_for_read(repo_root, deadline, monotonic, gh_run, env, known_slug, slug_cell)` became the earlier `slug = known_slug` / `if slug is None:` / `slug, _refusal_result = _resolve_repo_slug(repo_root, deadline, monotonic, gh_run, env, granted=True)`.

**detector:** `test_wave_watch_builder_note.py::test_the_repository_slug_is_resolved_once_per_tick`, a git-commit fixture (`repo` from `test_wave_watch_cloud.py`).

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `C7FU2-a`.

## C7FU2-b — the cached validator rides page one only

**guarded element:** `page == 1` in the `If-None-Match` condition of `wave_watch._read_issue_comments`. **axis:** page one carries the stored ETag and pages 2 and 3 do not.

**neutralization:** `if page == 1 and stored is not None and stored[1]:` became `if stored is not None and stored[1]:`.

**detector:** `test_a_primed_validator_rides_page_one_only_and_a_multi_page_read_clears_it`, a git-commit fixture.

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `C7FU2-b`.

## C7FU2-c — a 200 after an empty cached read returns the response's comments

**guarded element:** the comment list returned after a complete read in `wave_watch._read_issue_comments`. **axis:** with an empty cached read primed and a 200 carrying one builder note, the note is surfaced.

**neutralization:** after `note_state[0] = (url, etag, comments)`, `return True, comments` became `return True, (stored[2] if stored is not None else comments)`.

**detector:** `test_a_note_arriving_after_an_empty_cached_read_is_surfaced`, a git-commit fixture.

**Unrunnable here — the orchestrator runs red and green outside the sandbox.** Manifest element `C7FU2-c`.
