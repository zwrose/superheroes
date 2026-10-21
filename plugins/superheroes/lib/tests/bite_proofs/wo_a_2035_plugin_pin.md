# Bite-proof record: WO-A2 (#2035), the plugin pin hook (`lib/cloud_plugin_pin.py`)

Declared guarded-element set (from the order): G1, G2, G3, G4, G5, G6; G7 and G8 were added by work order C (#2039). One neutralization and one red
each, applied to the production code with the detectors unedited, each reverted by the inverse edit.
Every run was `scripts/pinned-python -B -X pycache_prefix=<scratchpad>/pyc -m pytest "<node id>" -q -p no:cacheprovider`
from the worktree, selected by exact node id (never `-k`). Production code was at `be46d43a`.
Nothing in the captures needed redaction. Captures are trimmed to the decisive lines: the `UV_NATIVE_TLS`
deprecation warning, the unchanged `@pytest.mark.parametrize` / test-body echo and the `tmp_path` line are
elided. Node ids for parametrized cases were read off `pytest --collect-only -q` (one extra invocation).
Each restore receipt below is the restored line quoted back from the file, plus an empty `git diff --stat`
taken after the restore (no tracked change).

## G1 — `at_commit`, a commit that cannot be read is broken, not absent, when hook files are in the tree

- **Guarded element and axis:** `cloud_plugin_pin.py:284-287` (`# axis: hook files in the working tree and a
  commit that cannot be read are never absent`); the broken-vs-absent split of the commit-unreadable fallback.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_at_commit_unreadable_commit_with_a_pin_in_the_working_tree_is_broken`
- **Neutralization (line 284):** `if in_tree(repo_root)["state"] == "absent":` became
  `if True or in_tree(repo_root)["state"] == "absent":`, so the fallback returns `absent` whatever the
  working tree holds.
- **Raw red:**
  ```
  >       assert at(root, "d" * 40) == {"state": "broken", "reason": "commit-unreadable", "pin": None}
  E       AssertionError: assert {'state': 'ab..., 'pin': None} == {'state': 'br..., 'pin': None}
  E         Differing items:
  E         {'state': 'absent'} != {'state': 'broken'}
  E         {'reason': None} != {'reason': 'commit-unreadable'}
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_at_commit_unreadable_commit_with_a_pin_in_the_working_tree_is_broken
  1 failed in 0.46s
  ```
  The red is on the claimed axis: a pin in the working tree read as `absent` instead of `broken`.
- **Restore:** the inverse edit, removing `True or `.
- **Restore receipt (line 284 quoted back):** `        if in_tree(repo_root)["state"] == "absent":`; `git diff --stat` empty.
- **Raw green:** `1 passed in 0.29s`

## G2 — `at_commit`, the script must be byte-identical to `script_text()`

- **Guarded element and axis:** `cloud_plugin_pin.py:222-223` (`# axis: bytes that differ from ours mean a stale
  or other hook runs`); a script that differs from ours is broken with `script-differs`.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_at_commit_is_broken_with_the_first_reason_that_holds[script-differs-changes1-script-differs]`
- **Neutralization (line 222):** `elif script != script_text().encode("utf-8"):` became
  `elif False and script != script_text().encode("utf-8"):`.
- **Raw red:**
  ```
  name = 'script-differs', changes = {'script': b'#!/bin/bash\nexit 0\n'}
  reason = 'script-differs'
  >       assert _state(at(root)) == ("broken", reason)
  E       AssertionError: assert ('valid', None) == ('broken', 'script-differs')
  E         At index 0 diff: 'valid' != 'broken'
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_at_commit_is_broken_with_the_first_reason_that_holds[script-differs-changes1-script-differs]
  1 failed in 0.36s
  ```
  The red is on the claimed axis: a foreign script reads `valid`.
- **Restore:** the inverse edit, removing `False and `.
- **Restore receipt (line 222 quoted back):** `    elif script != script_text().encode("utf-8"):`; `git diff --stat` empty.
- **Raw green:** `1 passed in 0.30s`

## G3 — the script's version check before the swap (`script_text`, `cloud_plugin_pin.py`)

- **Guarded element and axis:** `cloud_plugin_pin.py:169-175` (`# axis: a tree whose commit or version is not
  the pin's is never linked`), the version leg: a fetched tree whose `version.txt` disagrees with the pin's
  version is skipped, not linked.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_does_not_link_a_tree_whose_version_disagrees_with_the_pin`
- **Neutralization (line 174, in the script text):**
  `'[ "$GOT_VERSION" = "$VERSION" ] || skip "the fetched plugin is version ${GOT_VERSION:-unknown}, '` became
  `'true || skip "the fetched plugin is version ${GOT_VERSION:-unknown}, '`. The commit check on line 171 was left in place.
- **Raw red:**
  ```
  >       assert "plugin pin not applied: the fetched plugin is version 9.9.9, not the pinned 8.8.8" in done.stdout
  E       AssertionError: assert 'plugin pin not applied: the fetched plugin is version 9.9.9, not the pinned 8.8.8' in 'superheroes: plugin 8.8.8 installed at the pinned commit 7675581730f4.\n'
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_does_not_link_a_tree_whose_version_disagrees_with_the_pin
  1 failed in 0.41s
  ```
  The red is on the claimed axis: the script installed a 9.9.9 tree under a pin of 8.8.8.
- **Restore:** the inverse edit, `true` back to `[ "$GOT_VERSION" = "$VERSION" ]`.
- **Restore receipt (line 174 quoted back):** `        '[ "$GOT_VERSION" = "$VERSION" ] || skip "the fetched plugin is version ${GOT_VERSION:-unknown}, '`; `git diff --stat` empty.
- **Raw green:** `1 passed in 0.42s`

## G4 — the script's same-commit no-fetch exit

- **Guarded element and axis:** `cloud_plugin_pin.py:145-148` (`# axis: a session already at the pinned commit
  fetches nothing`); an installed commit equal to the pin's exits silently before any fetch.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_at_the_pinned_commit_fetches_nothing_and_says_nothing`
- **Neutralization (line 146, in the script text):** `'if [ "$INSTALLED" = "$COMMIT" ]; then',` became
  `'if [ "$INSTALLED" = "x$COMMIT" ]; then',`, so the equality never holds.
- **Raw red:**
  ```
  >       assert (done.returncode, done.stdout) == (0, "")
  E       AssertionError: assert (0, 'superher...f0388079).\n') == (0, '')
  E         At index 1 diff: 'superheroes: plugin pin not applied: the pinned commit could not be fetched; this session runs the plugin already installed (7ef8420c229553dc009f2d94f663f2a0f0388079).\n' != ''
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_at_the_pinned_commit_fetches_nothing_and_says_nothing
  1 failed in 0.49s
  ```
  The red is on the claimed axis: with the source unreachable, the script tried to fetch although it was already at the pinned commit.
- **Restore:** the inverse edit, `x$COMMIT` back to `$COMMIT`.
- **Restore receipt (line 146 quoted back):** `        'if [ "$INSTALLED" = "$COMMIT" ]; then',`; `git diff --stat` empty.
- **Raw green:** `1 passed in 0.37s`

## G5 — `sync`'s secret refusal

- **Guarded element and axis:** `cloud_plugin_pin.py:346-347` (`# axis: nothing is written, the script and pin
  included`); a secret-shaped settings file refuses with `secret-shaped` and nothing is written.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_sync_refuses_and_leaves_every_file_byte_identical[pin3-{"env": {"X_API_KEY": "abc123def456"}}-secret-shaped]`
- **Neutralization (line 346, the scan call in `_sync`):** `if _secret_shaped(texts, checked):  # axis: ...`
  became `if False and _secret_shaped(texts, checked):  # axis: ...`.
- **Raw red:**
  ```
  settings = '{"env": {"X_API_KEY": "abc123def456"}}', reason = 'secret-shaped'
  >       assert pin_mod.sync(str(tmp_path), pin) == {"action": "refused", "reason": reason, "changed": []}
  E       AssertionError: assert {'action': 'w...-plugin-pin']} == {'action': 'r...'changed': []}
  E         Differing items:
  E         {'reason': None} != {'reason': 'secret-shaped'}
  E         {'action': 'written'} != {'action': 'refused'}
  E         {'changed': ['.claude/hooks/superheroes-plugin-pin.sh', '.claude/settings.json', '.claude/superheroes-plugin-pin']} != {'changed': []}
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_sync_refuses_and_leaves_every_file_byte_identical[pin3-{"env": {"X_API_KEY": "abc123def456"}}-secret-shaped]
  1 failed in 0.43s
  ```
  The red is on the claimed axis: the refusal token is gone and the three files were written.
- **Restore:** the inverse edit, removing `False and `.
- **Restore receipt (line 346 quoted back):** `    if _secret_shaped(texts, checked):  # axis: nothing is written, the script and pin included`; `git diff --stat` empty.
- **Raw green:** `1 passed in 0.27s`

## G6 — `_remove_ours` scopes its removal to `script_rel`

- **Guarded element and axis:** `cloud_dependency_hook.py:437-450` (`_remove_ours(obj, script_rel=SCRIPT_REL)`);
  removing the pin hook leaves the dependency hook, its script and the shared settings file byte-identical.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_pin_hook_and_the_dependency_hook_share_the_settings_file`
- **Neutralization (one added line at the top of the body, so `script_rel` is ignored and the default path is used):**
  inserted `    script_rel = SCRIPT_REL` before `    removed = 0` in `_remove_ours`.
- **Raw red:**
  ```
  >       assert commands == [dep.HOOK_COMMAND, pin_mod.HOOK_COMMAND]
  E       assert ['bash "$CLAU...ugin-pin.sh"'] == ['bash "$CLAU...ugin-pin.sh"']
  E         At index 0 diff: 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/superheroes-plugin-pin.sh"' != 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/superheroes-cloud-dependencies.sh"'
  E         Right contains one more item: 'bash "$CLAUDE_PROJECT_DIR/.claude/hooks/superheroes-plugin-pin.sh"'
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_pin_hook_and_the_dependency_hook_share_the_settings_file
  1 failed in 0.33s
  ```
  The red is on the claimed axis, with a note on where it fires: the pin's `sync` calls `_remove_ours`
  while writing, and the default scope removed the dependency hook's entry, so the dependency command was lost
  from the shared settings. It fired on the write-time assertion at line 200, before the removal-time
  assertions (lines 201-206); the removal path in `_sync` takes the same `_remove_ours` call and is covered by
  the same detector, but this proof did not separately observe it red.
- **Restore:** the inverse edit, deleting the inserted line.
- **Restore receipt (lines 437-440 quoted back):**
  ```
  def _remove_ours(obj, script_rel=SCRIPT_REL):
      """Takes every hook of ours out of `obj` (in place), dropping a group, list or key only when
      that removal emptied it. Returns the number removed."""
      removed = 0
  ```
  `git diff --stat` empty.
- **Raw green:** `1 passed in 0.30s`

## G7 — `_secret_shaped` scans the script and pin texts (work order C, #2039, review finding test-001)

- **Guarded element and axis:** `cloud_plugin_pin.py:295` (`_secret_shaped`, the `any(_scan(t) for t in texts)`
  leg); a secret shape in the generated script text or in the pin text refuses with `secret-shaped` and writes
  nothing, with the settings clean and `_scan` real.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_sync_refuses_a_secret_shape_in_the_script_or_pin_text[script_text]`
  and `...[pin_text]` (both ids in one invocation; each wraps only its own generator to append a comment line
  carrying `"npm_" + "a" * 36`, built by concatenation in the test source).
- **Neutralization (line 295):** `return any(_scan(t) for t in texts) or (` became `return False or (`, the
  settings leg kept.
- **Raw red (both cases; `tmp_path` lines and the unchanged decorator and body echo elided):**
  ```
  FF                                                                       [100%]
  generator = 'script_text'
  >       assert pin_mod.sync(str(tmp_path), PIN) == {
  E       AssertionError: assert {'action': 'w...-plugin-pin']} == {'action': 'r...'changed': []}
  E         Differing items:
  E         {'changed': ['.claude/hooks/superheroes-plugin-pin.sh', '.claude/settings.json', '.claude/superheroes-plugin-pin']} != {'changed': []}
  E         {'action': 'written'} != {'action': 'refused'}
  E         {'reason': None} != {'reason': 'secret-shaped'}
  generator = 'pin_text'
  >       assert pin_mod.sync(str(tmp_path), PIN) == {
  E       AssertionError: assert {'action': 'w...-plugin-pin']} == {'action': 'r...'changed': []}
  E         Differing items:
  E         {'changed': ['.claude/hooks/superheroes-plugin-pin.sh', '.claude/settings.json', '.claude/superheroes-plugin-pin']} != {'changed': []}
  E         {'action': 'written'} != {'action': 'refused'}
  E         {'reason': None} != {'reason': 'secret-shaped'}
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_sync_refuses_a_secret_shape_in_the_script_or_pin_text[script_text]
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_sync_refuses_a_secret_shape_in_the_script_or_pin_text[pin_text]
  2 failed in 11.17s
  ```
  The red is on the claimed axis, for each text independently: with the text leg gone the secret-shaped script
  or pin was written.
- **Restore:** the inverse edit, `return False or (` back to `return any(_scan(t) for t in texts) or (`.
- **Restore receipt (lines 295-296 quoted back):**
  ```
      return any(_scan(t) for t in texts) or (
          settings is not None and hook._settings_secret_shaped(settings))
  ```
- **Raw green:** `2 passed in 0.29s`

## G8 — the script refuses a cached tree at another commit (work order C, #2039, review finding test-002)

- **Guarded element and axis:** `cloud_plugin_pin.py:171` (the commit leg of `# axis: a tree whose commit or
  version is not the pin's is never linked`); a cached destination whose HEAD is not the pinned commit is
  skipped, not linked, even when its `version.txt` matches the pin.
- **Detector:** `plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_does_not_link_a_cached_tree_at_another_commit`
- **Neutralization (line 171, in the script text):** `'[ "$GOT" = "$COMMIT" ] || skip "the fetched plugin is not at the pinned commit"',`
  became `'true || skip "the fetched plugin is not at the pinned commit"',`. The version check on line 174 was left in place.
- **Raw red (`tmp_path` line and the unchanged body echo elided):**
  ```
  >       assert "plugin pin not applied: the fetched plugin is not at the pinned commit;" in done.stdout
  E       AssertionError: assert 'plugin pin not applied: the fetched plugin is not at the pinned commit;' in 'superheroes: plugin 9.9.9 installed at the pinned commit 6d372c080396.\n'
  FAILED plugins/superheroes/lib/tests/test_cloud_plugin_pin.py::test_the_script_does_not_link_a_cached_tree_at_another_commit
  1 failed in 0.82s
  ```
  The red is on the claimed axis: the script linked a cached tree whose HEAD was an extra empty commit past the pin.
- **Restore:** the inverse edit, `true` back to `[ "$GOT" = "$COMMIT" ]`.
- **Restore receipt (line 171 quoted back):** `        '[ "$GOT" = "$COMMIT" ] || skip "the fetched plugin is not at the pinned commit"',`
- **Raw green:** `1 passed in 0.40s`

## Whole-file run after the last restore (work order C)

`plugins/superheroes/lib/tests/test_cloud_plugin_pin.py`: `62 passed in 2.86s`. `git diff -- plugins/superheroes/lib/cloud_plugin_pin.py`
is empty (production code byte-identical to the committed head). The earlier whole-file run of `60 passed` predates
work order C; the two added tests (the `pin_text` / `script_text` parametrization and the cached-tree test) make 62.
