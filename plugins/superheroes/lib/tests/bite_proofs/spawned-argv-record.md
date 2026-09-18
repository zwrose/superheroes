# Bite-proof — the fail-closed spawned-argv journal record

**Detector.** `engine_dispatch._derive_and_record_spawn_argv` and its two fail-closed call sites.

**What it guards.** For every attempt that reaches the per-attempt spawn-argv derivation — on the
real subprocess spawn path and on the injected `run_engine` seam — the run journal carries an
`engine-launching` record for that attempt whose `spawnArgv` key holds the argv actually handed to
the engine; and when that journal append fails, the engine is **not** invoked and the attempt ends
with refusal `journal-append-failed`.

**Coverage is complete by construction, not by a list.** `_argv_for_attempt` has exactly one caller,
`_derive_and_record_spawn_argv`, so deriving a per-attempt argv and journaling it are the same act;
that helper has exactly two call sites, a closed set (`_run_engine_files`, `_execute_injected_attempt`).
Census at the proof head:

```
$ grep -n "_argv_for_attempt(\|_derive_and_record_spawn_argv(" plugins/superheroes/lib/engine_dispatch.py
2637:    argv, recorded = _derive_and_record_spawn_argv(
2791:    argv, recorded = _derive_and_record_spawn_argv(
2914:def _argv_for_attempt(argv, run_dir_real, attempt, engine):
2932:def _derive_and_record_spawn_argv(run_dir_real, attempt, argv, engine):
2934:    spawn_argv = _argv_for_attempt(argv, run_dir_real, attempt, engine)
```

**Declared guarded-element set.** **Four elements.** Three were declared by the advisor in amendment
16 on issue #1271 before that work was dispatched, and carried verbatim into work order
`WO-1271-A16-A`: the append at the real-spawn site, the append at the injected-seam site, and the
fail-closed check on the append's return. The third has two independently neutralizable branches, so
it is proven twice (E3a, E3b) rather than once — strictly finer than the declaration.

The **fourth** element was declared by the advisor in **amendment 17**, after a merge review found
that writing the record and reading it back were two different guarantees. It is the **started-gate**
on the reader — the check in `_with_run_fields` that the attempt whose `spawnArgv` is reported also
carries an `engine-started` record. It is proven as **E4**. Its reason is worth stating, because it
is why one record needed two proofs: the write half must happen **before** the spawn (that is what
makes the append fail-closed), so the existence of a `spawnArgv` record is by construction **not**
evidence that the engine ever ran. Without E4's gate, a spawn that failed — or a later attempt that
refused before invoking — was reported as the command that ran.

**Coverage of the fourth element is by construction too.** `_with_run_fields` is the only place the
result's `argv` is resolved from the journal. Census at the proof head:

```
$ grep -n 'spawned\[max(\|state\["spawned"\]\|get("spawned")' plugins/superheroes/lib/engine_dispatch.py
846:                if "spawnArgv" in rec:
847:                    state["spawned"][att] = list(rec["spawnArgv"])
2364:            spawned = folded.get("spawned") or {}
2372:                resolved_argv = list(spawned[max(started)])
```

Lines 846–847 are the fold that populates the map; 2364 and 2372 are both inside `_with_run_fields`.
There is no second reader, so every one of that function's ~20 callers inherits the gate.

**Method.** Every neutralization was applied as a targeted, reversible edit through the host's edit
action and reverted by the exact inverse edit; no `git checkout`, no whole-file rewrite. The landed
implementer work was committed (`87eb6cfb` for E1–E3b, `cfa317b3` for E4) **before** the first probe
of each round, so no probe's revert could reach uncommitted work. Every probe ran in a **detached
worktree of its own** (`/private/tmp/wh1271a17-bp` for this round), never in a tree a live review
seat was reading. Every detector ran **unedited**. No redaction was needed: no secrets, tokens,
private URLs, or PII appear in any capture.

**Every proof is re-proven, red, at the final head — and the heads are named individually rather
than summarized**, because an older red is not evidence about a head that moved under it. The
sequence of heads in this build, and what was proven at each:

| Head | What it added | Proofs taken red there |
|---|---|---|
| `87eb6cfb` | the write-side detector | E1, E2, E3a, E3b (original) |
| `cfa317b3` | the started-gate | E4 (first), and E1, E2, E3a, E3b re-proven |
| `87e9300d` | the `except` revert; one fixture rewritten | E4 (re-proven against the rewritten fixture) |
| **`538ccea7`** | **the last head that changes any code** | **E1, E2, E3a, E3b re-proven again** |

The branch's tip is `2291445d`, one commit later; that commit edits this record and the keep-or-retire
entry and **nothing else** (`git diff --name-only 538ccea7 2291445d` returns two `.md` paths), so
every guarded element and every detector is byte-identical between `538ccea7` and the tip and the
reds above describe the shipped code exactly.

Each row is a genuine neutralize → red → restore cycle, not a green run inherited from the row above.
The final row exists because the confirmation round's corrective touched `_with_run_fields` itself —
the guarded reader — so reds taken before it no longer describe the shipped function. The `538ccea7`
reds are recorded in E1, E2, E3a and E3b's own sections below, under *Re-proof at the final head*;
E4's `87e9300d` re-proof is in its own section, and E4 is unaffected by the `except` revert (the
revert is outside its neutralized element, and its two detectors are re-run green at `538ccea7` in
the closing block).

---

## E1 — the spawned-argv record at the real-spawn site

- **Guarded element.** `engine_dispatch.py:2637` (`_run_engine_files`).
- **Axis.** *Value* — the argv reported on the result is the argv actually handed to the engine, not
  merely that some record exists.
- **Detector (unedited).** `test_engine_dispatch_e2e.py::test_e2e_review_real_path_terminal_success`,
  which compares the argv a real fake-engine child recorded receiving against the result's `argv`.

**Neutralization.** Derive the per-attempt argv without journaling it, leaving the fail-closed branch
structurally intact so the red cannot come from a syntax or flow change:

```python
-    argv, recorded = _derive_and_record_spawn_argv(
-        run_dir_real, attempt, spawn_argv, opened.get("engine"))
+    argv = _argv_for_attempt(
+        spawn_argv, run_dir_real, attempt, opened.get("engine"))
+    recorded = True
```

**Raw red.**

```
        with open(argv_file, encoding="utf-8") as fh:
            spawned_argv = json.load(fh)
        # argv[0] is PATH-resolved in the child; tail must match the journaled argv exactly.
        assert os.path.basename(spawned_argv[0]) == res["argv"][0]
>       assert spawned_argv[1:] == res["argv"][1:]
E       AssertionError: assert ['exec', '--s...a', '-c', ...] == ['exec', '--s...a', '-c', ...]
E
E         At index 9 diff: '--json' != '-'
E         Left contains 3 more items, first extra item: '--output-last-message'

plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py:381: AssertionError
1 failed in 1.34s
```

The red is on the declared axis: with no record, the result falls back to the run-opened canonical
argv, which is missing the per-attempt codex flags the engine actually received.

**Restore.** The exact inverse edit, restoring the two-line call and dropping `recorded = True`.

**Re-proof at `cfa317b3`.** The same neutralization, applied again in the detached probe worktree,
red again on the same axis:

```
        # argv[0] is PATH-resolved in the child; tail must match the journaled argv exactly.
        assert os.path.basename(spawned_argv[0]) == res["argv"][0]
>       assert spawned_argv[1:] == res["argv"][1:]
E       AssertionError: assert ['exec', '--s...a', '-c', ...] == ['exec', '--s...a', '-c', ...]
E
E         At index 9 diff: '--json' != '-'
E         Left contains 3 more items, first extra item: '--output-last-message'

plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py:381: AssertionError
1 failed in 2.15s
```

**Re-proof at the final head (`538ccea7`).** Same neutralization once more, in a fresh detached probe
worktree pinned to the final head, red again:

```
E         Use -v to get more diff

plugins/superheroes/lib/tests/test_engine_dispatch_e2e.py:381: AssertionError
1 failed in 2.92s
```

**Restore receipt.**

```
$ git status --porcelain plugins/superheroes/lib/engine_dispatch.py
(no output — file identical to HEAD)
```

**Raw green.**

```
.                                                                        [100%]
1 passed in 1.41s
```

---

## E2 — the spawned-argv record at the injected-seam site

- **Guarded element.** `engine_dispatch.py:2791` (`_execute_injected_attempt`).
- **Axis.** *Value* — the seam's journaled `spawnArgv` equals the argv `run_engine` received.
- **Detector (unedited).**
  `test_engine_dispatch.py::test_injected_seam_journals_spawn_argv_for_the_attempt`.

**Neutralization.** The same shape as E1, applied at the seam's call site only:

```python
-    argv, recorded = _derive_and_record_spawn_argv(
-        run_dir_real, attempt, spawn_argv, opened.get("engine"))
+    argv = _argv_for_attempt(
+        spawn_argv, run_dir_real, attempt, opened.get("engine"))
+    recorded = True
```

**Raw red.**

```
        launching = [
            r for r in records
            if r.get("kind") == "engine-launching" and r.get("attempt") == 1 and "spawnArgv" in r
        ]
>       assert len(launching) == 1
E       assert 0 == 1
E        +  where 0 = len([])

plugins/superheroes/lib/tests/test_engine_dispatch.py:2970: AssertionError
1 failed in 0.81s
```

This red is separate evidence from E1: E1's neutralization leaves the seam recording and E2's leaves
the real-spawn path recording, so neither red is the other's. The seam is the path that journaled no
`engine-launching` record at all before this change, which is why it needs its own proof.

**Restore.** The exact inverse edit.

**Restore receipt.**

```
$ git status --porcelain plugins/superheroes/lib/engine_dispatch.py
(no output — file identical to HEAD)
```

**Raw green.**

```
.                                                                        [100%]
1 passed in 0.74s
```

**Re-proof at `cfa317b3`.** Same neutralization, red again on the same axis, with the restore of E1's
site verified first (`git diff --stat` showed exactly the seam's own changed lines):

```
        launching = [
            r for r in records
            if r.get("kind") == "engine-launching" and r.get("attempt") == 1 and "spawnArgv" in r
        ]
>       assert len(launching) == 1
E       assert 0 == 1
E        +  where 0 = len([])

plugins/superheroes/lib/tests/test_engine_dispatch.py:2970: AssertionError
1 failed in 1.31s
```

**Re-proof at the final head (`538ccea7`).** Same neutralization, red again, the seam recording
nothing:

```
E        +  where 0 = len([])

plugins/superheroes/lib/tests/test_engine_dispatch.py:2970: AssertionError
1 failed in 3.41s
```

---

## E3a — the fail-closed check at the real-spawn site

- **Guarded element.** The `if not recorded:` branch at `engine_dispatch.py:2639`.
- **Axis.** *Refusal* — append fails ⇒ the engine is **not spawned**, and the attempt ends
  `journal-append-failed`.
- **Detector (unedited).**
  `test_engine_dispatch.py::test_run_engine_files_spawn_argv_append_failure_refuses_before_spawn`.

**Neutralization.** Disable the guard without deleting it, so the red cannot be an import or
name error:

```python
-    if not recorded:
+    if False:
         # axis: spawnArgv append failed — engine not invoked, attempt ends journal-append-failed.
```

**Raw red.**

```
        monkeypatch.setattr(ED, "_journal_append", fail_spawn_argv)
        ED._run_engine_files(...)
>       assert not os.path.exists(marker_path)
E       AssertionError: assert not True
E        +  where True = <function exists at 0x1054b08b0>('.../test_run_engine_files_spawn_ar0/engine-ran.marker')

plugins/superheroes/lib/tests/test_engine_dispatch.py:3031: AssertionError
1 failed in 1.44s
```

The red is on the refusal axis in its strongest form: with the guard disabled the fake engine
**actually ran** and wrote its marker file. An assertion reading only the refusal string could not
tell "refused before spawning" from "spawned, then refused"; the marker is what discriminates.

**Restore.** The exact inverse edit (`if False:` → `if not recorded:`).

**Restore receipt.** Taken as part of E3b's pre-probe diff, which showed exactly one changed line —
the seam branch — confirming the real-spawn branch was already back to its HEAD state:

```
$ git diff --stat
 plugins/superheroes/lib/engine_dispatch.py | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)
```

**Re-proof at `cfa317b3`.** Same neutralization (`if not recorded:` → `if False:`), red again in its
strongest form — the fake engine ran and wrote its marker:

```
            os.path.join(run_dir, "progress.jsonl"),
        )
>       assert not os.path.exists(marker_path)
E       AssertionError: assert not True
E        +  where True = <function exists at 0x1018958b0>('.../test_run_engine_files_spawn_ar0/engine-ran.marker')

plugins/superheroes/lib/tests/test_engine_dispatch.py:3031: AssertionError
1 failed in 4.76s
```

**Re-proof at the final head (`538ccea7`).** Same neutralization, red again on the marker assertion —
the guard disabled, the fake engine ran:

```
E        +      where <module 'posixpath' ...> = os.path

plugins/superheroes/lib/tests/test_engine_dispatch.py:3031: AssertionError
1 failed in 5.96s
```

---

## E3b — the fail-closed check at the injected-seam site

- **Guarded element.** The `if not recorded:` branch at `engine_dispatch.py:2794`.
- **Axis.** *Refusal* — append fails ⇒ `run_engine` is **not invoked**, and the attempt refuses
  `journal-append-failed`.
- **Detector (unedited).**
  `test_engine_dispatch.py::test_injected_seam_append_failure_refuses_before_invoking_engine`.

**Neutralization.**

```python
-    if not recorded:
+    if False:
         # axis: spawnArgv append failed — run_engine not invoked, attempt ends journal-append-failed.
```

**Raw red.**

```
        res = ED.dispatch_review(
            seat=_codex_seat(),
            prompt_path=_valid_prompt(tmp_path), repo_root=repo_root,
            run_engine=counting_never_call,
            build_view=_fake_build_view(tmp_path), run_dir=run_dir,
        )
>       assert calls["n"] == 0
E       assert 1 == 0

plugins/superheroes/lib/tests/test_engine_dispatch.py:2999: AssertionError
1 failed in 0.83s
```

Red on the refusal axis: the seam's engine callable was invoked once where the guarantee is zero.

**Restore.** The exact inverse edit.

**Restore receipt.** Whole-tree, after the last probe:

```
$ git status --porcelain
(no output)
$ git rev-parse HEAD
87eb6cfbe6dbb67079f6403bfd4dfb7d34c611eb
```

No residue: every neutralized surface is byte-identical to the committed head, and nothing could not
be reverted.

**Re-proof at `cfa317b3`.** Same neutralization, red again on the refusal axis — the seam's engine
callable invoked once where the guarantee is zero:

```
            run_engine=counting_never_call,
            build_view=_fake_build_view(tmp_path), run_dir=run_dir,
        )
>       assert calls["n"] == 0
E       assert 1 == 0

plugins/superheroes/lib/tests/test_engine_dispatch.py:2999: AssertionError
1 failed in 3.01s
```

**Re-proof at the final head (`538ccea7`).** Same neutralization, red again, one invocation where the
guarantee is zero:

```
E       assert 1 == 0

plugins/superheroes/lib/tests/test_engine_dispatch.py:2999: AssertionError
1 failed in 2.57s
```

**Whole-tree restore after the final-head round**, taken once after the last of the four:

```
$ git status --porcelain
(no output)
$ git rev-parse HEAD
538ccea77548d4e926a28883903c1b4ed6200811
```

---

## E4 — the started-gate on the reported argv

- **Guarded element.** The started-gate in `_with_run_fields` (`engine_dispatch.py:2366–2372`) — the
  check that an attempt whose `spawnArgv` is reported also carries an `engine-started` record.
- **Axis.** *Value, in the fail-safe direction* — the reported `argv` names only a command an engine
  actually received. A record written before the spawn is evidence of intent, never of execution;
  this element is what stops intent being reported as execution.
- **Detectors (unedited).** Two, because the element has two failure shapes:
  `test_engine_dispatch.py::test_with_run_fields_argv_falls_back_when_spawn_failed_before_engine_started`
  (a spawn that failed) and
  `test_engine_dispatch.py::test_with_run_fields_argv_ignores_later_unstarted_attempt_spawn_argv`
  (a later attempt that refused before invoking). A third,
  `test_dispatch_review_result_argv_matches_started_attempt_spawn_argv`, is the unchanged-behaviour
  guard and is expected to stay green under this neutralization — it does, which is itself part of
  the evidence that the red is on the declared axis and not collateral.

**Neutralization.** Drop the started predicate from the comprehension, leaving the selection and the
`max()` structurally intact so the red cannot come from a name or flow change:

```python
     started = [
         att for att in spawned
-        if attempts.get(att, {}).get("enginePgid") is not None
     ]
```

That restores exactly the pre-fix behaviour (`max` over every attempt with a `spawnArgv` record).

**Raw red — the spawn that failed.**

```
        assert [r for r in records if r.get("kind") == "engine-started"] == []
        assert launching["spawnArgv"] != canonical_argv
        res = ED._with_run_fields(
            {"ok": False, "terminal": True}, run_dir=run_dir, argv=canonical_argv,
        )
>       assert res["argv"] == canonical_argv
E       AssertionError: assert ['codex', 'ex...5.6-sol', ...] == ['codex', 'ex...5.6-sol', ...]
E
E         At index 10 diff: '--json' != '-'
E         Left contains 3 more items, first extra item: '--output-last-message'

plugins/superheroes/lib/tests/test_engine_dispatch.py:3068: AssertionError
1 failed in 3.48s
```

The red is the defect itself, reproduced: `PATH` is emptied so `Popen` fails, no `engine-started`
record is ever written, and the result nonetheless reports the per-attempt spawn argv — complete with
the codex flags — as the command that ran.

**Raw red — the later attempt that refused before invoking**, run in the same neutralized state:

```
>       assert res["argv"] == attempt1_spawn_argv
E       AssertionError: assert ['codex', 'ex...pt-2-refused'] == ['codex', 'ex...empt-1-spawn']
E
E         At index 2 diff: 'attempt-2-refused' != 'attempt-1-spawn'

plugins/superheroes/lib/tests/test_engine_dispatch.py:3104: AssertionError
```

This is the sharper of the two: attempt 1 genuinely reached the engine, attempt 2 refused before
invoking, and the un-gated `max(spawned)` reports **attempt 2's** argv. The two reds are independent
evidence — the first shows a never-started run reporting a command, the second shows a started run
reporting the *wrong* command.

The combined run of all three detectors under the neutralization:

```
2 failed, 1 passed in 1.61s
```

— the third being the unchanged-behaviour guard, green as expected.

**Restore.** The exact inverse edit, restoring the `if attempts.get(att, {}).get("enginePgid") is not
None` line.

**Restore receipt.**

```
$ git status --porcelain
(no output — whole tree identical to HEAD)
```

**Re-proof at `87e9300d`, after the confirmation round's corrective.** The corrective rewrote the
second detector's fixture — attempt 1 now ends before attempt 2 begins, and attempt 2's refusal is
the `spawn-failed:` shape `_run_engine_files` actually writes rather than `journal-append-failed`
(which is the shape of a *post*-`Popen` append failure, and so described the opposite of what the
test asserts about). A rewritten fixture can stop exercising the thing it was written for, so E4 was
proven again against it. Same neutralization, same two reds, the third detector green as before:

```
>       assert res["argv"] == attempt1_spawn_argv
E       AssertionError: assert ['codex', 'ex...pt-2-refused'] == ['codex', 'ex...empt-1-spawn']
E
E         At index 2 diff: 'attempt-2-refused' != 'attempt-1-spawn'

plugins/superheroes/lib/tests/test_engine_dispatch.py:3111: AssertionError
2 failed, 1 passed in 1.38s
```

Restored by the exact inverse edit; `git status --porcelain` empty afterwards.

---

## Known limits of this element — stated, not papered over

E4's gate establishes its invariant on the **production** dispatch path and not on every path, and
the two gaps are recorded here rather than left for a later reader to rediscover. Both were raised by
the confirmation round and both were checked by execution.

- **A successful spawn whose `engine-started` append then fails is excluded.** On the real spawn path
  `Popen` returns before that append; if the append fails, the engine has received the argv but the
  fold carries no `enginePgid`, so the gate falls back to the canonical argv. This is a false
  negative in the **safe** direction — it under-claims — and it occurs only on a path where the
  runner immediately terminates the process group and the journal is already refusing writes.
- **On the injected seam the gate does not establish that an engine was reached**, because
  `_execute_injected_attempt` appends `engine-started` *before* calling `run_engine`. That path is
  taken only when a caller injects a `run_engine` that is not the module's own `_run_engine` —
  `_spawn_attempt`'s `run_engine is not _run_engine` branch — so it is the test seam and never a
  production dispatch. Closing it would mean moving a record `_launching_uncertain` also reads, which
  is beyond what this change was authorized to touch.

---

## All proofs green on the final head

All seven detectors, every element's, green together at the final head `538ccea7`, whole tree
restored:

```
$ git status --porcelain
(no output)
$ git rev-parse HEAD
538ccea77548d4e926a28883903c1b4ed6200811
$ /usr/bin/python3 -B -X pycache_prefix=... -m pytest \
    test_engine_dispatch_e2e.py::test_e2e_review_real_path_terminal_success \
    test_engine_dispatch.py::test_injected_seam_journals_spawn_argv_for_the_attempt \
    test_engine_dispatch.py::test_run_engine_files_spawn_argv_append_failure_refuses_before_spawn \
    test_engine_dispatch.py::test_injected_seam_append_failure_refuses_before_invoking_engine \
    test_engine_dispatch.py::test_with_run_fields_argv_falls_back_when_spawn_failed_before_engine_started \
    test_engine_dispatch.py::test_with_run_fields_argv_ignores_later_unstarted_attempt_spawn_argv \
    test_engine_dispatch.py::test_dispatch_review_result_argv_matches_started_attempt_spawn_argv -q
.......                                                                  [100%]
7 passed in 5.79s
```

## Keep-or-retire

This detector's entry is **D31** in `docs/superheroes/KEEP-OR-RETIRE.md` — citation-based, 45 days,
tagged structural. R27's three birth duties are discharged: this record (i), the D31 entry (ii), and
by-construction coverage — through the single-caller derivation and its closed two-site call set for
the write half, and through `_with_run_fields` being the sole reader for the started-gate (iii).
