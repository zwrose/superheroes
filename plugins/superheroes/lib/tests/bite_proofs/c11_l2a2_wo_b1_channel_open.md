# WO-B1 (#1270 L2) bite-proof — the channel-open detectors

**Provenance:** produced by the layer-2a2 orchestrator session (opus, medium), orchestrator-typed,
in its own build worktree. The detectors themselves were implemented under **WO-B1** by cursor /
composer-2.5 on the layer-2 head; the record is owed by R27's birth duty and was routed to this
stack by [Layer 2 order, amendment 2 § Ruling 3](https://github.com/zwrose/superheroes/issues/1270#issuecomment-5731600264)
("2c retires nothing it has not seen proven"). Every proof below is the orchestrator's own run —
verification authority never delegates.

**Head these proofs were run on:** `df31ae5f` — this layer's code head. Every proof below was
**re-run in full on this head** by the adopting orchestrator session (opus, medium) on 2026-09-18,
because commit `661e3437` touched `engine_dispatch.py` after the first recording at `e96aca2d`. The
raw red and green output quoted under each proof is from that re-run. The only commits after
`df31ae5f` on this branch add prose records and change no code; if any later commit touches
`engine_dispatch.py`, every proof here is re-run on that head and this line is updated.

**Method.** Each guarded element is neutralized on its own — the *thing the detector guards* is
disabled, never the detector — with a targeted edit applied through the host's edit action and
reverted by the exact inverse edit. Every command selects its test by **exact test name**, never
`-k`. The working tree was confirmed clean (`git status --porcelain` empty) after each restore and
before each green run.

## Guarded elements

| ID | Guarded element | Neutralized thing | Proving test |
|---|---|---|---|
| BP-B1-1 | a codex review run opens on the native channel with its schema on disk and `--output-schema` in the journaled argv | the native-channel establishment at open (the branch is taken as if every engine were marker-channel) | `test_codex_review_open_records_native_channel` |
| BP-B1-2 | a cursor review run opens **untouched**: marker channel, no schema file, argv byte-identical to `build_argv_result` | the engine test that keeps the native establishment off cursor's path | `test_cursor_review_open_records_marker_channel_unchanged_argv` |
| BP-B1-3 | an undeclarable schema **refuses at open, nothing opened** | the fail-closed refusal on the declare failure (falls open to a marker-shaped open) | `test_codex_review_open_refuses_undeclarable_schema` |
| BP-B1-4 | an unwritable schema **refuses at open, nothing opened** | the fail-closed refusal on the write failure (falls open to a marker-shaped open) | `test_codex_review_open_refuses_unwritable_schema` |

Common command prefix:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::<exact test name> -q
```

All four neutralizations live in one function,
`plugins/superheroes/lib/engine_dispatch.py::_open_native_channel_argv` — which is the point: the
native channel is established at exactly one place, so the coverage is by construction and not a
list of sites (R27 (iii)).

---

## BP-B1-1 — the native open establishes channel, schema and argv

- **axis:** a codex review open records `channel: "native"`, writes `native-schema.json` whose
  content round-trips as `declared_schema`, and journals argv ending in
  `--output-schema <that path>`.

**neutralization** (`engine_dispatch.py`, `_open_native_channel_argv`):
```python
    if True:  # bite-proof BP-B1-1
        return list(argv), None, None
```
(replaces `if engine_result_channel.channel_for(engine) != engine_result_channel.CHANNEL_NATIVE:` —
the establishment is skipped for every engine, exactly as if codex were marker-channel)

**command:** `…::test_codex_review_open_records_native_channel -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_codex_review_open_records_native_channel _________________
        opened = _review_opened_record(run_dir)
        assert opened["channel"] == ERC.CHANNEL_NATIVE
        schema_path = os.path.join(run_dir, ED.NATIVE_SCHEMA_NAME)
>       assert os.path.isfile(schema_path)
E       AssertionError: assert False
E        +  where False = <function isfile at 0x100b309d0>('…/run/native-schema.json')

plugins/superheroes/lib/tests/test_engine_dispatch.py:10047: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_codex_review_open_records_native_channel
1 failed in 0.81s
```

**restore** (inverse edit): `if engine_result_channel.channel_for(engine) != engine_result_channel.CHANNEL_NATIVE:`

**raw green** (exit 0, tree clean — `git status --porcelain` empty):
```
.                                                                        [100%]
1 passed in 0.69s
```

---

## BP-B1-2 — cursor is untouched by the native channel

- **axis:** a cursor review open records `channel: "marker"`, writes no schema file, and its argv is
  byte-identical to `engine_adapter.build_argv_result`'s own output.

**neutralization** (`engine_dispatch.py`, `_open_native_channel_argv`):
```python
    if False:  # bite-proof BP-B1-2
        return list(argv), None, None
```
(replaces the same guard with its opposite: the native establishment now runs for **every** engine,
cursor included — the exact "the native channel leaked onto the marker engine" defect)

**command:** `…::test_cursor_review_open_records_marker_channel_unchanged_argv -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_cursor_review_open_records_marker_channel_unchanged_argv _________
        opened = _review_opened_record(run_dir)
        assert opened["channel"] == ERC.CHANNEL_MARKER
>       assert not os.path.exists(os.path.join(run_dir, ED.NATIVE_SCHEMA_NAME))
E       AssertionError: assert not True
E        +  where True = <function exists at 0x104cb08b0>('…/run/native-schema.json')

plugins/superheroes/lib/tests/test_engine_dispatch.py:10074: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_cursor_review_open_records_marker_channel_unchanged_argv
1 failed in 0.73s
```

**restore** (inverse edit): the real guard.

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.66s
```

---

## BP-B1-3 — an undeclarable schema refuses, nothing opened

- **axis:** when `declared_schema` raises, the open returns `(False, "native-schema-undeclarable")`
  and no `run-opened` record exists.

**neutralization** (`engine_dispatch.py`, `_open_native_channel_argv`):
```python
    except Exception:
        return list(argv), None, None  # bite-proof BP-B1-3
```
(replaces `return None, "native-schema-undeclarable", None` — the refusal falls open into a
marker-shaped open, which is precisely the wasted-dispatch failure the guard exists to prevent)

**command:** `…::test_codex_review_open_refuses_undeclarable_schema -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_codex_review_open_refuses_undeclarable_schema ______________
>       assert not ok
E       assert not True

plugins/superheroes/lib/tests/test_engine_dispatch.py:10099: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_codex_review_open_refuses_undeclarable_schema
1 failed in 0.78s
```

**restore** (inverse edit): `return None, "native-schema-undeclarable", None`

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.62s
```

---

## BP-B1-4 — an unwritable schema refuses, nothing opened

- **axis:** when the schema file cannot be written, the open returns
  `(False, "native-schema-unwritable")` and no `run-opened` record exists.

**neutralization** (`engine_dispatch.py`, `_open_native_channel_argv`):
```python
    except OSError:
        return list(argv), None, schema_path  # bite-proof BP-B1-4
```
(replaces `return None, "native-schema-unwritable", None` — the open proceeds, and argv would name a
schema path that does not exist)

**command:** `…::test_codex_review_open_refuses_unwritable_schema -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_codex_review_open_refuses_unwritable_schema _______________
>       assert not ok
E       assert not True

plugins/superheroes/lib/tests/test_engine_dispatch.py:10130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_codex_review_open_refuses_unwritable_schema
1 failed in 0.74s
```

**restore** (inverse edit): `return None, "native-schema-unwritable", None`

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.95s
```

---

## Vacuity check

None of the four proofs is vacuous in the four ways `rubric/bite-proof.md` names: each
neutralization disables the **guarded behaviour** and leaves the detector's own code untouched; each
red run names the guarded assertion rather than an import or collection error; each test is selected
by exact name; and no assertion in these tests is pinned to a symbol that moves with the
neutralization — the schema filename is read through `ED.NATIVE_SCHEMA_NAME` on both sides, but the
neutralized thing is the *establishment*, not the name, so the red is real.

**Not covered here, and why:** `test_opened_channel_defaults_missing_key_to_marker` (a legacy
`run-opened` record without a `channel` key reads as marker) is a pure-function default, not a
detector — there is nothing to neutralize but the default itself. The stale-result lifecycle WO-B1
first shipped was **replaced** in this layer by per-attempt result files, and its proof is
`BP-2a2-4` in `c11_l2a2_admission_authority.md`.
