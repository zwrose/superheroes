# C7r-1 bite-proof — the relay's start, liveness and delivery check

**Provenance:** work order C7r-1 (claude implementer), worktree `build/1786-cloud-relay`, edits left uncommitted.

**Method.** Each guarded element is neutralized on its own by a targeted edit to the consumer
(never the detector), the detector is run alone by exact node id (`-q`, no `-k`), the edit is
undone by its inverse edit, the detector is re-run green, and the restored lines are read back with
a search over the file. One neutralization was live at a time. Redaction: pytest temp paths are kept
as printed; nothing else needed redacting. Every capture is far under the 32 KiB ceiling.

Command for every run (`<node>` is the exact node id given per element):

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "<node>" -q
```

Guarded-element set (declared by the order): G1 mismatch-beats-delivered, G2 attribution by id,
G3 id-bound results, G4 liveness is listing, G5 start directory, G6 the census narrowing.

## G1 — mismatch beats delivered (`cloud_relay.py` `_decide`; axis: an altered send is never overridden by an exact one)

- **Detector:** `plugins/superheroes/lib/tests/test_cloud_relay.py::test_altered_send_beats_an_exact_send_for_the_same_message`
- **Neutralization:** in `_decide`, the exact-success block (`exact = [...]` / `if any(r and r[0] ...): return "delivered"`) moved above the `other = [...]` / `if other:` mismatch block.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_altered_send_beats_an_exact_send_for_the_same_message __________
...
        out, clock = _check(world, msg["msgId"])
>       assert out["ok"] is False and out["delivered"] is False
E       assert (True is False)

plugins/superheroes/lib/tests/test_cloud_relay.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_altered_send_beats_an_exact_send_for_the_same_message
1 failed in 0.83s
```

(elided: the `world` fixture repr and the test body echo, the same source lines as in the file.)

- **Restore:** inverse edit, the mismatch block back above the exact-success block.
- **Restore receipt:** `cloud_relay.py:309: other = [t for t, _ in sends if t != msg["forward"]]`, `:310: if other:`, `:312: exact = [results.get(i) for t, i in sends if t == msg["forward"]]`, `:313: if any(r and r[0] for r in exact):`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.92s
```

## G2 — attribution by id (`cloud_relay.py` `_decide`; axis: a send carrying another pending message's id is ignored for this message)

- **Detector:** `plugins/superheroes/lib/tests/test_cloud_relay.py::test_another_pending_messages_send_is_not_this_messages_mismatch`
- **Neutralization:** the filter `sends = [(t, i) for t, i in sends if mine in t or not any(_marker(p) in t for p in pending_ids)]` replaced by `sends = [(t, i) for t, i in sends]` (every send to the session attributed).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_another_pending_messages_send_is_not_this_messages_mismatch _______
...
        out, _ = _check(world, first["msgId"])
>       assert out["delivered"] is True and out["reason"] is None
E       assert (False is True)

plugins/superheroes/lib/tests/test_cloud_relay.py:292: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_another_pending_messages_send_is_not_this_messages_mismatch
1 failed in 1.37s
```

(elided: fixture repr and test body echo.)

- **Restore:** inverse edit, the two-line filter back.
- **Restore receipt:** `cloud_relay.py:307: sends = [(t, i) for t, i in sends` / `:308:              if mine in t or not any(_marker(p) in t for p in pending_ids)]`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.11s
```

## G3 — id-bound results (`cloud_relay.py` `_sends`; axis: a call needs a non-empty string `id` and a result a non-empty string `tool_use_id`)

- **Detector:** `plugins/superheroes/lib/tests/test_cloud_relay.py::test_results_and_calls_need_their_ids`
- **Neutralization (three edits, one neutralization):** deleted the two lines `if not (isinstance(call_id, str) and call_id):` / `continue` in the `tool_result` branch; dropped `isinstance(b.get("id"), str) and b["id"] and` from the `tool_use` condition; `sends.append((args["message"], b["id"]))` became `b.get("id")`.
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_results_and_calls_need_their_ids _____________________
...
        for lines in cases:
            _write_record(world, lines)
            out, _ = _check(world, msg["msgId"], wait=4, interval=2)
>           assert out["delivered"] is False and out["reason"] == "relay-silent"
E           assert (True is False)

plugins/superheroes/lib/tests/test_cloud_relay.py:325: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_results_and_calls_need_their_ids
1 failed in 0.93s
```

(elided: fixture repr and test body echo.)

- **Restore:** the three inverse edits.
- **Restore receipt:** `cloud_relay.py:266: if not (isinstance(call_id, str) and call_id):` / `:267: continue`; `:280: if (isinstance(b.get("id"), str) and b["id"] and isinstance(args, dict)`; `:283: sends.append((args["message"], b["id"]))`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 1.42s
```

## G4 — liveness is listing (`cloud_relay.py` `_listing`; axis: an entry the default listing shows is alive whatever its `state`)

- **Detector:** `plugins/superheroes/lib/tests/test_cloud_relay.py::test_listed_entry_is_alive_whatever_its_state`
- **Neutralization:** `and e.get("name") == name], None` became `and e.get("name") == name and e.get("state") not in ("done", "stopped")], None` (`done`/`stopped` read as dead again).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_listed_entry_is_alive_whatever_its_state _________________
...
>       assert out == {"ok": True, "reason": None, "name": name, "sessionId": RELAY_ID, "started": False}
E       AssertionError: assert {'ok': False,...y-claude-two'} == {'ok': True, ...afd22ad', ...}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'reason': 'relay-start-failed'} != {'reason': None}
E         {'ok': False} != {'ok': True}
E         Right contains 2 more items:
E         {'sessionId': '5534cbe0-5d2a-4783-8980-09c4bafd22ad', 'started': False}
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_cloud_relay.py:476: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_listed_entry_is_alive_whatever_its_state
1 failed in 0.51s
```

(elided: fixture repr and test body echo.)

- **Restore:** inverse edit.
- **Restore receipt:** `cloud_relay.py:156-157: return [e for e in entries if isinstance(e, dict) and e.get("kind") == "background"` / `and e.get("name") == name], None`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.51s
```

## G5 — start directory (`cloud_relay.py` `ensure`; axis: the start runs with `cwd` equal to the real path of the repository root)

- **Detector:** `plugins/superheroes/lib/tests/test_cloud_relay.py::test_relay_starts_in_the_repository_root`
- **Neutralization:** `cwd = os.path.realpath(repo_root)` replaced by `cwd = os.path.join(os.path.dirname(path), "relay-" + name)` plus `os.makedirs(cwd, exist_ok=True)` (a fresh directory beside the ledger).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_relay_starts_in_the_repository_root ___________________
...
        (start,) = run.starts()
>       assert start.cwd == os.path.realpath(world.repo) != str(link)
E       AssertionError: assert '/private/tmp...ay-claude-two' == '/private/tmp...e_repos0/repo'
E         
E         Skipping 75 identical leading characters in diff, use -v to show
E         - he_repos0/repo
E         + he_repos0/ledger-root/032f7c0639bf01e5127c69ba28385d967d67dcaaa3d71366afabdc6935f8d6c0/relay-superheroes-relay-claude-two

plugins/superheroes/lib/tests/test_cloud_relay.py:453: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_relay.py::test_relay_starts_in_the_repository_root
1 failed in 0.54s
```

(elided: fixture repr and test body echo.)

- **Restore:** inverse edit, the two lines back to the single `realpath` line.
- **Restore receipt:** `cloud_relay.py:177: cwd = os.path.realpath(repo_root)`; no `makedirs` remains in the file.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.59s
```

## G6 — the census narrowing (`test_claude_background_retired_census.py` `_admitted_relay_flag`; axis: `--bg` is admitted only inside `claude_relay_argv` of `engine_adapter.py`)

- **Detector:** `plugins/superheroes/lib/tests/test_claude_background_retired_census.py::test_census_admits_the_flag_only_in_the_relay_argv_builder`
- **Neutralization:** in `_admitted_relay_flag`, `for fn in ast.walk(tree)` / `if isinstance(fn, ast.FunctionDef) and fn.name == _RELAY_ARGV_FUNCTION` replaced by `for fn in [tree]` (every `--bg` in `engine_adapter.py` admitted).
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_census_admits_the_flag_only_in_the_relay_argv_builder __________
...
        problems, _scanned = retired_background_problems(str(tmp_path))
>       assert problems == ["elsewhere.py:2:--bg", "engine_adapter.py:2:--bg"]
E       AssertionError: assert ['elsewhere.py:2:--bg'] == ['elsewhere.p...er.py:2:--bg']
E         
E         Right contains one more item: 'engine_adapter.py:2:--bg'
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_claude_background_retired_census.py:177: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_claude_background_retired_census.py::test_census_admits_the_flag_only_in_the_relay_argv_builder
1 failed in 0.26s
```

(elided: fixture repr and test body echo.)

- **Restore:** inverse edit.
- **Restore receipt:** `test_claude_background_retired_census.py:70: for fn in ast.walk(tree)` / `:71: if isinstance(fn, ast.FunctionDef) and fn.name == _RELAY_ARGV_FUNCTION` / `:72: for inner in ast.walk(fn)`.
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.18s
```
