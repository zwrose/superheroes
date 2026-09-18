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

**Declared guarded-element set.** Three elements, declared by the advisor in amendment 16 on issue
#1271 before this work was dispatched, and carried verbatim into work order `WO-1271-A16-A`: the
append at the real-spawn site, the append at the injected-seam site, and the fail-closed check on the
append's return. The third element has two independently neutralizable branches, so it is proven
twice (E3a, E3b) rather than once — strictly finer than the declaration.

**Method.** Every neutralization was applied as a targeted, reversible edit through the host's edit
action and reverted by the exact inverse edit; no `git checkout`, no whole-file rewrite. The landed
implementer work was committed (`87eb6cfb`) **before** the first probe, so no probe's revert could
reach uncommitted work. Every detector ran **unedited**. All four proofs were re-run green on the
final head. No redaction was needed: no secrets, tokens, private URLs, or PII appear in any capture.

Proof head: `87eb6cfbe6dbb67079f6403bfd4dfb7d34c611eb`.

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

---

## All proofs green on the final head

```
$ /usr/bin/python3 -B -X pycache_prefix=... -m pytest \
    test_engine_dispatch_e2e.py::test_e2e_review_real_path_terminal_success \
    test_engine_dispatch.py::test_injected_seam_journals_spawn_argv_for_the_attempt \
    test_engine_dispatch.py::test_run_engine_files_spawn_argv_append_failure_refuses_before_spawn \
    test_engine_dispatch.py::test_injected_seam_append_failure_refuses_before_invoking_engine -q
....                                                                     [100%]
4 passed in 1.91s
```

## Keep-or-retire

This detector's entry is **D31** in `docs/superheroes/KEEP-OR-RETIRE.md` — citation-based, 45 days,
tagged structural. R27's three birth duties are discharged: this record (i), the D31 entry (ii), and
by-construction coverage through the single-caller derivation and its closed two-site call set (iii).
