# Bite-proof record: #2294 `ensure` replaces a relay a usage limit left dead

Detectors under proof: the tests added to `plugins/superheroes/lib/tests/test_cloud_relay.py` for
`cloud_relay.ensure` / `_liveness` / `check` (rows named per element below) and the argv-builder tests in
`plugins/superheroes/lib/tests/test_engine_adapter_relay_argv.py` (those pin builder output exactly and are
not part of the seven declared elements).
Guarded code: `plugins/superheroes/lib/cloud_relay.py`. Base: `7787133745b99073fe0fb12cb48c52040dac07d4`.
Every neutralization was a targeted edit through the host's edit tool, undone by the inverse edit before the
next element. No `git checkout`, `restore`, `reset` or `stash` was used. No test was edited to make a run red.
One test edit happened before G2's neutralization (a `{"pid": 4242}` case added to the row, see G2); nothing
was edited between a red and its green.
Command for every run (worktree root), with `-k` naming the row:
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2294 -m pytest plugins/superheroes/lib/tests/test_cloud_relay.py -q -k <row>`.
Captures: the `UV_NATIVE_TLS` deprecation warning line is dropped from every capture; the long `world = namespace(...)`
fixture lines and repeated parametrized tracebacks are trimmed (marked `...`). Nothing was redacted. Disclosure
about how the runs were made: the G1 red run was piped through `grep -v UV_NATIVE` (that warning only); the G2 red
run through `cut -c1-220` (lines cut to 220 characters, so the capture below is line-truncated at that width);
the G3 red run was first piped through a `grep` for result lines and then re-run unfiltered (the unfiltered run
is the one quoted). Every other run was unfiltered.

## G1 `_liveness` rule 4: a blocked job record with no process field is a dead candidate

- **Guarded element:** `_liveness`, the `return "dead-candidate"` under
  `if state == "blocked" and isinstance(entry.get("id"), str) and entry["id"]:` (`cloud_relay.py:182`);
  axis: such an entry is classified dead, so `ensure` replaces it.
- **Neutralization:** `        return "dead-candidate"` → `        return "alive"` ("listed means alive").
- **Row:** `test_a_dead_relay_is_replaced_and_the_dead_entry_stopped` (3 parametrized versions).
- **Raw red:**

```
FFF                                                                      [100%]
>       (start,) = run.starts()
E       ValueError: not enough values to unpack (expected 1, got 0)
  (the same failure for [2.1.316 (Claude Code)], [2.2.0 (Claude Code)], [10.0.1 (Claude Code)])
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_dead_relay_is_replaced_and_the_dead_entry_stopped[2.1.316 (Claude Code)]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_dead_relay_is_replaced_and_the_dead_entry_stopped[2.2.0 (Claude Code)]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_dead_relay_is_replaced_and_the_dead_entry_stopped[10.0.1 (Claude Code)]
3 failed, 140 deselected in 0.71s
```

- **Restore:** the inverse edit.
- **Restore receipt (restored line quoted, `cloud_relay.py:182`):** `        return "dead-candidate"`
- **Raw green:** `3 passed, 140 deselected in 2.01s`

## G2 `_liveness` rule 1: a pid is never dead

- **Guarded element:** `_liveness`, the `if "pid" in entry:` branch (`cloud_relay.py:175`); axis: an entry
  with a pid is alive (or undetermined), never a stop target.
- **Neutralization:** deleted the two lines
  `    if "pid" in entry:` / `        return "alive" if state in _KNOWN_STATES else "undetermined"`.
- **Row:** `test_a_blocked_entry_with_a_process_is_alive`. The order's row used pid plus `status: waiting`
  only; with the branch deleted that entry falls to the `status` rule (undetermined) and goes red for that
  weaker reason, so the row was given a second case, pid alone (`{"pid": 4242}`), where the deleted branch is the
  only thing keeping the entry alive. Added before the neutralization.
- **Raw red (line-truncated at 220 characters; the `[extra1]` case is the pid-only discriminator, it turns the
  live relay dead, starts a second relay and refuses):**

```
FF                                                                       [100%]
_____________ test_a_blocked_entry_with_a_process_is_alive[extra0] _____________
extra = {'pid': 4242, 'status': 'waiting'}
>       assert out == _plain(name)
E         Left contains 2 more items:
E         {'say': 'ensure could not tell whether relay superheroes-relay-claude-two-eaf0b258 is alive (listed state blocked); it is kept as alive.',
E          'undetermined': {'sessionId': '5534cbe0-5d2a-4783-8980-09c4bafd22ad', 'state': 'blocked'}}
_____________ test_a_blocked_entry_with_a_process_is_alive[extra1] _____________
extra = {'pid': 4242}
>       assert out == _plain(name)
E       AssertionError: assert {'ok': False,...: 'blocked'}]} == {'ok': True, ...afd22ad', ...}
E         Differing items:
E         {'ok': False} != {'ok': True}
E         {'reason': 'relay-start-failed'} != {'reason': None}
E         Left contains 1 more item:
E         {'deadEntries': [{'id': 'daf1d3b4',...
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_blocked_entry_with_a_process_is_alive[extra0]
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_blocked_entry_with_a_process_is_alive[extra1]
2 failed, 142 deselected in 1.78s
```

- **Restore:** the inverse edit (the two lines re-added above `if "status" in entry:`).
- **Restore receipt (restored line quoted, `cloud_relay.py:175`):** `    if "pid" in entry:`
- **Raw green:** `2 passed, 142 deselected in 0.52s`

## G3 the contract gate comparison

- **Guarded element:** `known()` in `ensure`, `return version[0] is not None and version[0] >= _CONTRACT_VERSION`
  (`cloud_relay.py:228`); axis: a candidate becomes dead only on a claude at or past the measured version.
- **Neutralization:** that return → `        return True` (any version, or none, counts as known).
- **Row:** `test_a_claude_whose_listing_contract_is_not_known_never_makes_a_relay_dead` (older version,
  unparseable output, non-zero exit).
- **Raw red (unfiltered run, fixture lines trimmed):**

```
FFF                                                                      [100%]
kwargs = {'version_out': '2.1.315 (Claude Code)'}
>       assert out["ok"] is True and out["started"] is False and out["sessionId"] == "dead-1"
E       assert (False is True)
kwargs = {'version_out': 'garbage'}
E       assert (False is True)
kwargs = {'version_code': 1}
E       assert (False is True)
FAILED ...::test_a_claude_whose_listing_contract_is_not_known_never_makes_a_relay_dead[kwargs0]
FAILED ...::test_a_claude_whose_listing_contract_is_not_known_never_makes_a_relay_dead[kwargs1]
FAILED ...::test_a_claude_whose_listing_contract_is_not_known_never_makes_a_relay_dead[kwargs2]
3 failed, 141 deselected in 0.60s
```

- **Restore:** the inverse edit.
- **Restore receipt (restored line quoted, `cloud_relay.py:228`):**
  `        return version[0] is not None and version[0] >= _CONTRACT_VERSION`
- **Raw green:** `3 passed, 141 deselected in 0.45s`

## G4 the freshness check

- **Guarded element:** `if started and not (isinstance(fresh, str) and fresh and fresh not in first_dead):`
  (`cloud_relay.py:278`); axis: the replacement must carry a session id no first-listing dead entry had.
- **Neutralization:** the condition → `    if started and not (isinstance(fresh, str) and fresh):`.
- **Row:** `test_a_relay_listed_under_the_dead_sessions_id_is_not_a_fresh_one`.
- **Raw red:**

```
F                                                                        [100%]
>       assert out["ok"] is False and out["reason"] == "relay-start-failed"
E       assert (True is False)
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_a_relay_listed_under_the_dead_sessions_id_is_not_a_fresh_one
1 failed, 143 deselected in 0.48s
```

- **Restore:** the inverse edit.
- **Restore receipt (restored line quoted, `cloud_relay.py:278`):**
  `    if started and not (isinstance(fresh, str) and fresh and fresh not in first_dead):`
- **Raw green:** `1 passed, 143 deselected in 0.37s`

## G5 stop targets are the latest listing's dead that were also dead in the first

- **Guarded element:** the `targets` comprehension's `and (not started or e.get("sessionId") in first_dead)`
  (`cloud_relay.py:282`); axis: after a start, an entry that only turned up dead in the second listing is
  not stopped.
- **Neutralization:** `               and (not started or e.get("sessionId") in first_dead)]` → `               and True]`
  (stop every dead entry of the latest listing).
- **Row:** `test_only_the_dead_entries_of_the_first_listing_are_stopped`.
- **Raw red:**

```
F                                                                        [100%]
>       assert [c.argv for c in run.stops()] == [["claude", "stop", "d1"]]
E       AssertionError: assert [['claude', '...'stop', 'd2']] == [['claude', 'stop', 'd1']]
E         Left contains one more item: ['claude', 'stop', 'd2']
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_only_the_dead_entries_of_the_first_listing_are_stopped
1 failed, 143 deselected in 0.53s
```

- **Restore:** the inverse edit.
- **Restore receipt (restored line quoted, `cloud_relay.py:282`):**
  `               and (not started or e.get("sessionId") in first_dead)]`
- **Raw green:** `1 passed, 143 deselected in 0.39s`

## G6 no stop on the start-failure paths

- **Guarded element:** the absence of any stop before the start and on `refuse_start` (`cloud_relay.py`, the
  `if not kept:` branch); axis: a start that fails leaves the dead entry named, never stopped.
- **Neutralization:** inserted, right after `    if not kept:`, the two lines
  `        for e in dead:` / `            _call(run, ["claude", "stop", e["id"]], dict(env, CLAUDE_CONFIG_DIR=config_dir), _LIST_TIMEOUT)`
  (the stops run before the start).
- **Row:** `test_a_fresh_start_that_fails_refuses_names_the_dead_and_stops_nothing` (4 cases).
- **Raw red (the failure is identical in the four cases; the first is quoted, fixture lines trimmed):**

```
FFFF                                                                     [100%]
>       assert run.stops() == []
E       AssertionError: assert [namespace(ar...'}, cwd=None)] == []
E         Left contains one more item: namespace(argv=['claude', 'stop', 'd1'], env={...}, cwd=None)
FAILED ...[start-exits-1]
FAILED ...[second-listing-only-dead]
FAILED ...[second-listing-empty]
FAILED ...[second-listing-unreadable]
4 failed, 140 deselected in 0.56s
```

- **Restore:** the inverse edit (the two inserted lines removed).
- **Restore receipt:** the final-state grep over `cloud_relay.py` for `_call(run, ["claude", "stop"` and `if False`
  matched nothing; the post-restore `git diff` check is in the return.
- **Raw green:** `4 passed, 140 deselected in 0.43s`

## G7 the `check` note

- **Guarded element:** `check`, `if verdict == "relay-silent" and relay.get("liveness") == "undetermined":`
  (`cloud_relay.py:699`); axis: a silent relay whose liveness ensure could not tell says so; every other
  `say` stays today's sentence.
- **Neutralization:** `    if verdict == ...` → `    if False and verdict == "relay-silent" and relay.get("liveness") == "undetermined":`.
- **Row:** `test_check_says_when_the_silent_relays_liveness_was_undetermined`.
- **Raw red:**

```
F                                                                        [100%]
>       assert out["say"] == today + (" ensure could not tell whether the relay was alive "
E       AssertionError: assert 'The relay di...ot delivered.' == 'The relay di...h may be why.'
E         -  delivered. ensure could not tell whether the relay was alive (listed state failed), which may be why.
E         +  delivered.
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_check_says_when_the_silent_relays_liveness_was_undetermined
1 failed, 143 deselected in 0.48s
```

- **Restore:** the inverse edit.
- **Restore receipt (restored line quoted, `cloud_relay.py:699`):**
  `    if verdict == "relay-silent" and relay.get("liveness") == "undetermined":`
- **Raw green:** `1 passed, 143 deselected in 0.50s`
