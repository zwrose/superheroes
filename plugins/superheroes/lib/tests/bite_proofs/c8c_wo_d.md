# WO-D bite-proofs — the unreadable cloud-builds setting and the archive-tool sentence

**Declared guarded-element set:** D1, D1b, D2.

Every entry was produced by one script that applied the neutralization, ran the single detector
node, restored the file by the inverse replace, re-read the file (byte-identical to its pre-edit
content: `True` in every entry), quoted the restored line and ran the node again. Redaction: the
worktree's absolute path prefix in the raw captures is replaced with `<worktree>`; nothing else is
changed. Each raw capture is short, so none is elided. The command of every red and green run is
the one-node form:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<node>' -q -p no:cacheprovider --tb=short
```

## D1 — the profile's unparseable flag (`test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off`)

**Guarded element:** `cloud_setup._cloud_builds_setting`, the read of `profileUnparseable`. Axis: a
corrupt profile is an unreadable setting, never the default off.

**Neutralization:** `unparseable = got.get("profileUnparseable")` became `unparseable = False` (the
flag ignored, so a corrupt profile is read as a read one).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off ______
<worktree>/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:405: in test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version. "
E   AssertionError: assert 'Cloud review... check again.' == 'Cloud review... check again.'
E     
E     Skipping 49 identical leading characters in diff, use -v to show
E     - on version. I could not read whether cloud builds are on. Run the setup check again.
E     + on version, so cloud builds stay off until a check passes. Run the setup check again.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off
1 failed in 4.66s
```

**Restore:** wrote `unparseable = got.get("profileUnparseable")` back (the inverse replace).

**Restore receipt:** `        unparseable = got.get("profileUnparseable")`

**Raw green:**
```
.                                                                        [100%]
1 passed in 6.07s
```

---

## D1b — the profile-presence check (`test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off`)

**Guarded element:** `cloud_setup._cloud_builds_setting`, the `os.path.lexists(...)` check that
tells a profile file that exists but cannot be read (unknown) from no profile file (off). Axis: an
unparseable report with a core file on disk is unreadable, not off.

**Neutralization:** `return None if os.path.lexists(core_md.core_path(cwd, root, persist_backfill=False)) else False`
became `return None if False and os.path.lexists(core_md.core_path(cwd, root, persist_backfill=False)) else False`
(the presence check always reads as absent).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off ______
<worktree>/plugins/superheroes/lib/tests/test_cloud_setup_gardening.py:405: in test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off
    assert got["line"] == ("Cloud reviewer pass: the last cloud check failed on version. "
E   AssertionError: assert 'Cloud review... check again.' == 'Cloud review... check again.'
E     
E     Skipping 49 identical leading characters in diff, use -v to show
E     - on version. I could not read whether cloud builds are on. Run the setup check again.
E     + on version, so cloud builds stay off until a check passes. Run the setup check again.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_setup_gardening.py::test_a_corrupt_profile_is_an_unreadable_setting_not_the_default_off
1 failed in 5.45s
```

**Restore:** removed the inserted `False and ` (the inverse replace).

**Restore receipt:** `            return None if os.path.lexists(core_md.core_path(cwd, root, persist_backfill=False)) else False`

**Raw green:**
```
.                                                                        [100%]
1 passed in 4.01s
```

---

## D2 — the archive-tool sentence (`test_section_does_not_promise_a_cloud_session_an_archive_tool`)

**Guarded element:** the last paragraph of `orchestration.md` § Acting on the builders' account.
Axis: the section never promises every cloud session an archive tool.

**Neutralization:** the sentence tail `can include one that archives a session by its id; a builder without one says so on its issue, as`
`the builder's cloud reference says.` became `include one that archives a session by its id.`, so the
section reads "A cloud session's own tools include one that archives a session by its id." (the old
sentence, restored as a probe).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_section_does_not_promise_a_cloud_session_an_archive_tool _________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:107: in test_section_does_not_promise_a_cloud_session_an_archive_tool
    assert "A cloud session's own tools include one" not in text
E   assert 'A cloud ses... include one' not in "The builder...s steps say."
E     
E     "A cloud session's own tools include one" is contained here:
E       hive one. A cloud session's own tools include one that archives a session by its id. Confirm every archive from the session list, and report one that is not confirmed as the cleanup's steps say.
E     ?           +++++++++++++++++++++++++++++++++++++++
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_does_not_promise_a_cloud_session_an_archive_tool
1 failed in 0.11s
```

**Restore:** wrote the new tail back (the inverse replace).

**Restore receipt:** `can include one that archives a session by its id; a builder without one says so on its issue, as`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.10s
```
