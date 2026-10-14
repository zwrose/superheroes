# WO-C bite-proofs — acting on the builders' account, the owner's conditional archive step, and three detector repairs

**Declared guarded-element set:** C1a, C1b, C1c, C1d, C1e, C2, C4, C5, C6.

Every entry was produced by one script that applied the neutralization, ran the single detector
node, restored the file by writing back its pre-edit bytes (the inverse edit), re-read the file,
quoted the restored line and ran the node again. Redaction: the worktree's absolute path prefix in
the raw captures is replaced with `<worktree>`; nothing else is changed. Each raw capture is
short, so none is elided. The command of every red and green run is the one-node form:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest '<node>' -q -p no:cacheprovider --tb=short
```

Post-run `git status --porcelain` does not list `lib/launch_doctrine.py`, the one probe-only file.

## C1a — the rule sentence (`test_section_states_the_rule_sentence`)

**Guarded element:** the sentence "an action scoped to the builders' account goes through a session
on that account" in `orchestration.md` § Acting on the builders' account. Axis: the rule an advisor
acts on when a step is scoped to the builders' account.

**Neutralization:** deleted `**an action scoped to the builders' account goes through a session on that account**. ` (the bold rule sentence and the space after it).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_section_states_the_rule_sentence _____________________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:75: in test_section_states_the_rule_sentence
    assert _RULE in _collapsed(_section())
E   assert "an action scoped to the builders' account goes through a session on that account" in "The builders can run on a different Claude account from the advisor; the launch names it by its config dir. A session... its id. Confirm every archive from the session list, and report one that is not confirmed as the cleanup's steps say."
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_states_the_rule_sentence
1 failed in 0.09s
```

**Restore:** wrote the deleted sentence back (the inverse edit).

**Restore receipt:** `**an action scoped to the builders' account goes through a session on that account**. Never hand`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## C1b — the merge-train citation (`test_section_cites_both_homes_by_their_exact_headings`)

**Guarded element:** the citation of `merge-train.md` § Cleaning up a finished cloud lane. Axis: each
citation names a heading that exists in the cited file.

**Neutralization:** `§ Cleaning up a finished cloud lane: the relay` became `§ Cleaning up a finished cloud session: the relay` (one word).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_section_cites_both_homes_by_their_exact_headings _____________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:86: in test_section_cites_both_homes_by_their_exact_headings
    assert citation in text, citation
E   AssertionError: `skills/showrunner/reference/merge-train.md` § Cleaning up a finished cloud lane
E   assert '`skills/showrunner/reference/merge-train.md` § Cleaning up a finished cloud lane' in "The builders can run on a different Claude account from the advisor; the launch names it by its config dir. A session... its id. Confirm every archive from the session list, and report one that is not confirmed as the cleanup's steps say."
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_cites_both_homes_by_their_exact_headings
1 failed in 0.10s
```

**Restore:** wrote `lane` back in place of `session` (the inverse edit).

**Restore receipt:** `  `skills/showrunner/reference/merge-train.md` § Cleaning up a finished cloud lane: the relay`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.10s
```

---

## C1c — the helper command's effort flag (`test_section_carries_the_helper_command`)

**Guarded element:** `--effort low` in the helper command. Axis: the command's pinned account,
background flag, name, model and effort.

**Neutralization:** `--model haiku --effort low "<prompt>"` became `--model haiku "<prompt>"`.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_section_carries_the_helper_command ____________________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:94: in test_section_carries_the_helper_command
    assert needle in text, needle
E   AssertionError: --effort low
E   assert '--effort low' in "\nThe builders can run on a different Claude account from the advisor; the launch names it by its\nconfig dir. A sess...s id. Confirm every archive from the session list, and\nreport one that is not confirmed as the cleanup's steps say.\n"
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_carries_the_helper_command
1 failed in 0.09s
```

**Restore:** wrote ` --effort low` back (the inverse edit).

**Restore receipt:** `    CLAUDE_CONFIG_DIR=<the builders' config dir> claude --bg -n <name> --model haiku --effort low "<prompt>"`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## C1d — the never-delete sentence (`test_section_says_the_helper_never_deletes_and_deleting_needs_the_owner`)

**Guarded element:** "and that it never deletes a session" in the helper's prompt paragraph. Axis:
the never-delete limit.

**Neutralization:** `(read, message, stop or archive), and that it never deletes a session.` became `(read, message, stop or archive).`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_section_says_the_helper_never_deletes_and_deleting_needs_the_owner ____
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:100: in test_section_says_the_helper_never_deletes_and_deleting_needs_the_owner
    assert "that it never deletes a session" in text
E   assert 'that it never deletes a session' in "The builders can run on a different Claude account from the advisor; the launch names it by its config dir. A session... its id. Confirm every archive from the session list, and report one that is not confirmed as the cleanup's steps say."
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_says_the_helper_never_deletes_and_deleting_needs_the_owner
1 failed in 0.09s
```

**Restore:** wrote `, and that it never deletes a session` back (the inverse edit).

**Restore receipt:** `(read, message, stop or archive), and that it never deletes a session. It asks for one result line`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## C1e — the relay's steps keep one home (`test_section_restates_none_of_the_relays_steps`)

**Guarded element:** the section's freedom from the relay's own words (`compose`, `ensure`,
`cloud_relay`, `record --repo-root`). Axis: the relay's steps keep one home, in the wave-watch
reference.

**Neutralization:** `Name it for its job, and put the account in the name` became `Name it for its job, compose it, and put the account in the name` (adds the word `compose`).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_section_restates_none_of_the_relays_steps ________________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:108: in test_section_restates_none_of_the_relays_steps
    assert found == [], found
E   AssertionError: ['compose']
E   assert ['compose'] == []
E     
E     Left contains one more item: 'compose'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_section_restates_none_of_the_relays_steps
1 failed in 0.09s
```

**Restore:** removed `compose it, ` (the inverse edit).

**Restore receipt:** `Name it for its job, and put the account in the name, as the relay's name does.`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## C2 — the owner's step follows the conditional message (`test_cleanup_steps_point_at_the_owner_message_not_one_tap`)

**Guarded element:** step 3 of `merge-train.md` § Cleaning up a finished cloud lane ("Ask nothing
more of the owner than the `ownerMessage` asks."). Axis: the owner's step follows the conditional
message instead of promising one tap.

**Neutralization:** restored the old step-3 sentence: `Ask nothing of the owner: the only step the owner is ever asked` / `for is the one tap on the archive prompt.` in place of the new one.

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_cleanup_steps_point_at_the_owner_message_not_one_tap ___________
<worktree>/plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py:137: in test_cleanup_steps_point_at_the_owner_message_not_one_tap
    assert "the only step the owner is ever asked for is the one tap" not in section
E   assert 'the only st... the one tap' not in 'A cloud lan...s the owner.'
E     
E     'the only step the ... for is the one tap' is contained here:
E     ?           ^^^^^^^^^^^^^
E       he owner: the only step the owner is ever asked for is the one tap on the archive prompt. 4. **The branch.** Run `cloud_cleanup.py branch --repo-root <root> --repo <owner/name> --pr <number> --launch-id <the plan's launchId>`. GitHub deletes the pull request's branch when the repository deletes merged branches; otherwise this step deletes it through GitHub, only while it still points at the pull request's head. It reports `deleted: false` with `already: "absent"` when the branch was ...
E     
E     ...Full output truncated (2 lines hidden), use '-vv' to show
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_c8c_relay_doctrine.py::test_cleanup_steps_point_at_the_owner_message_not_one_tap
1 failed in 0.09s
```

**Restore:** wrote the new step-3 sentence back (the inverse edit).

**Restore receipt:** `   and that its session stays listed. Ask nothing more of the owner than the `ownerMessage` asks.`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.08s
```

---

## C4 — the parsed block's label (`test_cloud_launch_block_is_introduced_as_parsed`)

**Guarded element:** the label `**Cloud launch permission (parsed).**` above the cloud-launch block
in `rubric/launch-doctrine.md`. Axis: the label above the parsed block must not call it unparsed.

**Neutralization:** `**Cloud launch permission (parsed).**` became `**Cloud launch permission (documentation only — not parsed).**` (the old label).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_cloud_launch_block_is_introduced_as_parsed ________________
<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:109: in test_cloud_launch_block_is_introduced_as_parsed
    assert "not parsed" not in label, label
E   AssertionError: **Cloud launch permission (documentation only — not parsed).** The block below holds one sentence.
E     `lib/launch_doctrine.py` parses it as one line that must carry the never-a-force-push and
E     never-`main` limits, and `compose_launch` carries it in every cloud launch prompt and in no local one. A cloud session pushes only to its own designated branch unless
E     its launch says otherwise, so the sentence is how the owner's standing permission to push reaches
E     the builder.
E   assert 'not parsed' not in '**Cloud lau...the builder.'
E     
E     'not parsed' is contained here:
E       on only — not parsed).** The block below holds one sentence.
E     ?           ++++++++++
E       `lib/launch_doctrine.py` parses it as one line that must carry the never-a-force-push and
E       never-`main` limits, and `compose_launch` carries it in every cloud launch prompt and in no local one. A cloud session pushes only to its own designated branch unless
E       its launch says otherwise, so the sentence is how the owner's standing permission to push reaches
E       the builder.
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_cloud_launch_block_is_introduced_as_parsed
1 failed in 0.10s
```

**Restore:** wrote the new label back (the inverse edit).

**Restore receipt:** `**Cloud launch permission (parsed).** The block below holds one sentence.`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## C5 — the cloud-launch sentence oracle (`test_shipped_doctrine_carries_the_cloud_launch_line`)

**Guarded element:** the parser's return of the doctrine block's own text
(`lib/launch_doctrine.py`, `_parse_cloud_launch_block`'s `return lines[0], None`). Axis: the parser
returns the doctrine block's text, compared with a read of the file by plain string operations.

**Neutralization (probe edit, `lib/launch_doctrine.py`):** `    return lines[0], None` became `    return lines[0][:-1], None` (the block's text with its last character dropped).

**Raw red (the rewritten test):**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_shipped_doctrine_carries_the_cloud_launch_line ______________
<worktree>/plugins/superheroes/lib/tests/test_launch_doctrine.py:98: in test_shipped_doctrine_carries_the_cloud_launch_line
    assert result["cloudLaunchLine"] == block
E   AssertionError: assert 'Standing per... never `main`' == 'Standing per...never `main`.'
E     
E     Skipping 288 identical leading characters in diff, use -v to show
E     - ever `main`.
E     ?            -
E     + ever `main`
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_shipped_doctrine_carries_the_cloud_launch_line
1 failed in 0.10s
```

**The old test body under the same neutralization** (its three assertions run in one
`pinned-python -c` against the neutralized parser: `ok is True`,
`cloudLaunchLine == LD.load()["cloudLaunchLine"]`, `cloudLaunchLine.count("\n") == 0`):
```
old test body: green; cloudLaunchLine ends with: 'never `main`'
[exit 0]
```
The old body stayed green against a parser that drops the sentence's last character, which is why
the oracle was replaced.

**Restore:** wrote `return lines[0], None` back (the inverse edit).

**Restore receipt:** `    return lines[0], None`; `git status --porcelain` does not list `lib/launch_doctrine.py`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## C6 — the retired-label scan skips the bite-proof records (`test_the_old_label_scan_skips_the_bite_proof_records`)

**Guarded element:** the `os.path.join(root, d) != _BITE_PROOFS` exclusion in
`_scanned_for_the_old_label`. Axis: the scan's walk leaves out `lib/tests/bite_proofs` only, by path.

**Neutralization:** `if d not in _SKIPPED_DIRS and os.path.join(root, d) != _BITE_PROOFS` became `if d not in _SKIPPED_DIRS` (the exclusion dropped).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_the_old_label_scan_skips_the_bite_proof_records _____________
<worktree>/plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py:225: in test_the_old_label_scan_skips_the_bite_proof_records
    assert under == [], under
E   AssertionError: ['<worktree>/plugins/superheroes/lib/tests/bite_proofs/wo_11....<worktree>/plugins/superheroes/lib/tests/bite_proofs/wo_l2_b_1271.md', ...]
E   assert ['<worktree>/...1271.md', ...] == []
E     
E     Left contains 390 more items, first extra item: '<worktree>/plugins/superheroes/lib/tests/bite_proofs/wo_11_1269_spawn_sandbox.md'
E     Use -v to get more diff
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_cleanup_doctrine.py::test_the_old_label_scan_skips_the_bite_proof_records
1 failed in 0.10s
```

**Restore:** wrote ` and os.path.join(root, d) != _BITE_PROOFS` back (the inverse edit).

**Restore receipt:** `            if d not in _SKIPPED_DIRS and os.path.join(root, d) != _BITE_PROOFS`

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## Measurement (not a proof): the write channel's sandbox and `-X pycache_prefix`

This is a measurement taken to settle one line of `skills/workhorse/reference/cloud.md`; no
detector was neutralized. Run in the write channel's own sandboxed shell, from the worktree root:

```
$ scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -c "import sys; print(sys.pycache_prefix, sys.dont_write_bytecode)"
/private/tmp/superheroes-pyc True
exit=0
```

The flag was accepted, so the line in `cloud.md` now says a gate command keeps
`-B -X pycache_prefix=…` and drops the flag only where a sandbox refuses it.
