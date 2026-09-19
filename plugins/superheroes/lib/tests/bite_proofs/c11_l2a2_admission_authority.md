# Layer 2a2 (#1270) bite-proof — the admission authority on codex's native review channel

**Provenance:** produced by the layer-2a2 orchestrator session (opus, medium), orchestrator-typed,
in its own build worktree. The detectors were implemented under **WO-2a2-A** (the chokepoint, the
predicate deletion, the schema pinning) and **WO-2a2-B** (per-attempt result files) by cursor /
composer-2.5; every run below is the orchestrator's own.

**Head these proofs were run on:** `df31ae5f` — this layer's code head. Every proof below was
**re-run in full on this head** by the adopting orchestrator session (opus, medium) on 2026-09-18,
because commit `661e3437` touched `engine_dispatch.py` after the first recording at `e96aca2d`. The
raw red and green output quoted under each proof is from that re-run. The only commits after
`df31ae5f` on this branch add prose records and change no code; if any later commit touches
`engine_dispatch.py`, every proof here is re-run on that head and this line is updated.

**Why this record exists.** [Layer 2 order, amendment 2](https://github.com/zwrose/superheroes/issues/1270#issuecomment-5731600264)
ruled that on the native channel a review result is admitted **if and only if** it validates against
the schema bytes that were sent — one authority, with `native_schema_allows_scrub_finish` deleted
rather than patched. The proof the ruling asks for is here: a result that fails schema validation
but **would have graded `ok` under the deleted predicate** now forfeits
`native-result-schema-invalid`, one specimen per old salvage branch.

**Method.** Each guarded element is neutralized on its own — the *thing the detector guards* is
disabled, never the detector — with a targeted edit applied through the host's edit action and
reverted by the exact inverse edit. Every command selects its test by **exact test name**, never
`-k`. The working tree was confirmed clean (`git status --porcelain` empty) after each restore and
before each green run.

## Guarded elements

| ID | Guarded element | Neutralized thing | Proving test(s) |
|---|---|---|---|
| BP-2a2-1 | schema validation is the **only** admission authority — nothing downstream of a schema failure produces `ok` | the validator's verdict at the one call site (it still runs; its answer is discarded) | `test_admit_native_review_schema_invalid_mistyped_investigated_forfeits`, `test_admit_native_review_schema_invalid_mistyped_finding_member_forfeits` |
| BP-2a2-2 | the schema **on disk** must be the schema the shell declares — a substituted schema refuses | the on-disk/declared comparison | `test_admit_native_review_schema_substitution_refuses` |
| BP-2a2-3 | a semantic refusal is **final** — marker stdout cannot rescue it on the native path | the finality (a marker-stdout rescue is reinstated on the forfeit path) | `test_grade_native_review_attempt_ignores_stdout_on_semantic_refusal` |
| BP-2a2-4 | each attempt is graded against **its own** result file | the attempt scoping of the result path | `test_grade_attempt2_does_not_read_attempt1_stale_result` (+ `test_native_result_paths_differ_per_attempt_and_attempt1_preserved` on green) |

Common command prefix:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::<exact test name> -q
```

BP-2a2-1 through BP-2a2-3 all neutralize inside `_admit_native_review_result` /
`_grade_native_review_attempt` — the single admission chokepoint; BP-2a2-4 neutralizes
`_native_result_path`, the single place the result path is derived. That is R27 (iii)'s
by-construction coverage: one chokepoint each, no site list.

---

## BP-2a2-1 — the schema is the one admission authority

- **axis:** a native review result that parses but fails schema validation forfeits
  `native-result-schema-invalid`, for both shapes the deleted predicate used to salvage — a
  mistyped `investigated` element, and a mistyped finding member.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_admit_native_review_result`):
```python
    ok, validation_reason, _validation_detail = engine_result_channel._validate_with_detail(
        declared, envelope)
    ok = True  # bite-proof BP-2a2-1: the validator runs, its verdict is discarded
```
(the validator still runs; only its verdict is thrown away — the exact shape of the old
`native_schema_allows_scrub_finish` salvage, which let a schema failure finish through the scrub)

**commands and raw red** (exit 1 each). Both failures show the graded result coming back **`ok`,
with findings** — that is the deleted predicate's behaviour reproduced, which is what makes this
proof the ruling's proof and not a generic assertion:

```
FAILED …::test_admit_native_review_schema_invalid_mistyped_investigated_forfeits
E       AssertionError: assert None is True
E        +  where None = …{'engagement': {'read': 'engaged', …}, 'findings': [{'body': 'ex…
E            'investigatedRejectedRecords': [{'path': '42', 'reason': 'not-a-string'}, …]}.get('forfeit')
plugins/superheroes/lib/tests/test_engine_dispatch.py:10617: AssertionError
1 failed in 0.77s
```
```
FAILED …::test_admit_native_review_schema_invalid_mistyped_finding_member_forfeits
E       AssertionError: assert None is True
E        +  where None = …{'engagement': {'read': 'engaged', …}, 'findings': [{'body': 'ex…}.get('forfeit')
plugins/superheroes/lib/tests/test_engine_dispatch.py:10626: AssertionError
1 failed in 0.78s
```

**restore** (inverse edit): the `ok = True` line is removed.

**raw green** (exit 0, tree clean, both specimens in one run):
```
..                                                                       [100%]
2 passed in 0.71s
```

---

## BP-2a2-2 — the schema that graded is the schema that was sent

- **axis:** if the schema file on disk does not **parse to the same JSON value** as what
  `declared_schema` re-derives, the attempt refuses `native-schema-unreadable` — a result cannot be
  admitted against a schema the shell did not declare.

  *Axis narrowed 2026-09-18, review round 1 (Minor, Test seat).* The earlier wording said
  **byte-equal**, which the detector does not check and the production code does not do: the
  comparison at `engine_dispatch.py`'s `_admit_native_review_result` is `json.load` on the file
  against the re-derived object, so a schema re-serialized with different whitespace or key order
  is admitted. That is deliberate — the pin is on the schema's *value*, not its bytes — but the
  axis line must claim only what the detector bites on. What the proof below demonstrates is
  rejection of a **semantically different** schema (`{}` substituted for the declared one).

**neutralization** (`engine_dispatch.py`, `_admit_native_review_result`):
```python
    if False:  # bite-proof BP-2a2-2: the on-disk/declared comparison is discarded
        return _native_review_forfeit(engagement, "native-schema-unreadable")
```
(replaces `if on_disk != declared:`)

**command:** `…::test_admit_native_review_schema_substitution_refuses -q`

**raw red** (exit 1 — the substituted schema is accepted as the grading authority and the refusal
arrives, if at all, under the wrong token):
```
>       assert grade.get("detail") == "native-schema-unreadable"
E       AssertionError: assert 'native-result-schema-invalid' == 'native-schema-unreadable'
plugins/superheroes/lib/tests/test_engine_dispatch.py:10672: AssertionError
1 failed in 0.74s
```

**restore** (inverse edit): `if on_disk != declared:`

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.59s
```

---

## BP-2a2-3 — a semantic refusal cannot be rescued from stdout

- **axis:** when the adapter's own parser refuses a schema-valid branch (here: every substance key
  blanked, a hollow finding), the attempt forfeits `native-result-malformed` — and a perfectly good
  marker-channel payload sitting in the attempt's stdout does not rescue it.

**neutralization** (`engine_dispatch.py`, `_grade_native_review_attempt`) — the pre-retirement
marker-stdout rescue reinstated on the forfeit path:
```python
    if admitted.get("forfeit"):
        # bite-proof BP-2a2-3: marker-stdout rescue reinstated on the native path
        try:
            with open(os.path.join(run_dir_real, "attempt-%d.stdout" % attempt),
                      encoding="utf-8") as fh:
                rescue_stdout = fh.read()
        except OSError:
            rescue_stdout = ""
        rescued = engine_adapter.parse_result(
            opened["engine"], opened.get("roleKind", RUN_KIND_REVIEW), rescue_stdout,
            echo_nonce=echo_nonce)
        if rescued.get("ok"):
            return _finish_review_grade_from_parse(opened, cwd, engagement, rescued)
        return admitted
```

**command:** `…::test_grade_native_review_attempt_ignores_stdout_on_semantic_refusal -q`

**raw red** (exit 1 — the hollow native result is refused, and the run is then graded `ok` off the
transcript, which is the salvage tier this child retires):
```
        grade = ED._grade_review_attempt(run_dir, state, 1)
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = {'engagement': {…'stdoutBytes': 54…}, 'findings': [{'body': 'issue found', 'id': 'f1', …}], 'ok': True, 'resultKind': 'findings'}.get('forfeit')
plugins/superheroes/lib/tests/test_engine_dispatch.py:10683: AssertionError
1 failed in 0.80s
```

**restore** (inverse edit): the block collapses back to `return admitted`.

**raw green** (exit 0, tree clean — `git status --porcelain` and `git diff --stat` both empty):
```
.                                                                        [100%]
1 passed in 0.58s
```

---

## BP-2a2-4 — each attempt is graded against its own result file

- **axis:** attempt 2 is graded against `native-result-2.json`; attempt 1's result never stands in
  for it. With attempt 2 having written nothing, the grade is `native-result-missing`, not attempt
  1's findings.

**neutralization** (`engine_dispatch.py`, `_native_result_path`):
```python
    return os.path.join(run_dir_real, "native-result.json")  # bite-proof BP-2a2-4
```
(replaces `return os.path.join(run_dir_real, "native-result-%d.json" % attempt)` — the run-level
path this layer replaced, which is exactly the v20 defect)

**command:** `…::test_grade_attempt2_does_not_read_attempt1_stale_result -q`

**raw red** (exit 1 — attempt 2 is graded `ok` off attempt 1's result):
```
        grade = ED._grade_review_attempt(run_dir, state, 2)
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = {'engagement': {…}, 'findings': [{'body': 'ex…}], …}.get('forfeit')
plugins/superheroes/lib/tests/test_engine_dispatch.py:10871: AssertionError
1 failed in 0.99s
```

**restore** (inverse edit): the attempt-suffixed path.

**raw green** (exit 0, tree clean — the isolation test and the path-shape test together):
```
..                                                                       [100%]
2 passed in 0.84s
```

---

## Vacuity check

No proof here is vacuous in the four ways `rubric/bite-proof.md` names. Each neutralization disables
the **guarded behaviour** while the detector's own code is untouched; each red run fails on the
guarded assertion, not on an import or a collection error; each test is selected by exact name; and
BP-2a2-1's two red runs show the graded result coming home `ok` — the deleted predicate's exact
behaviour — rather than merely a different refusal token, so the proof measures admission and not
wording.

**Constants are not detectors.** The two one-home fixes this layer also carries
(`NATIVE_RESULT_MAX_BYTES` reading `engine_adapter.ENGINE_OUTPUT_MAX_BYTES`, and
`_grade_build_report_obj` reading `WRITE_SIGNAL_ENUM`) add no detector and owe no bite-proof; they
are covered by their own tests.
