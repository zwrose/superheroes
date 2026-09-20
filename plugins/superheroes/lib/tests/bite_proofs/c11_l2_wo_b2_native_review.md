# WO-B2 (#1270 L2a) bite-proof — codex's native review grading path

**Superseded (layer 2a2):** The salvage predicate `native_schema_allows_scrub_finish` and the
`_scrub_native_review_branch` retry branch it proved were deleted when the declared schema became
the one admission authority. The proofs below record behaviour **as it stood at 2a's head**; live
guarded elements are now listed in `c11_l2a2_admission_authority.md`.

**Provenance:** produced by the layer-2a orchestrator session (opus, medium) in its own build
worktree. The detectors themselves were implemented by cursor / composer-2.5 under WO-B1/WO-B2 on
the adopted head `7630d6dd`; this record is the verification receipt the orchestrator re-ran
itself, per the charter's rule that verification authority never delegates.

**Head these proofs were run on:** `8202570e` — the layer's final head, after the review loop's
fix rounds. An earlier copy of this record quoted the pre-fix call shapes
(`engine_result_channel.validate(...)` and `_native_schema_allows_scrub_finish(validation_reason)`);
the review's confirmation panel caught that staleness, and **all six proofs below were then re-run
from scratch on `8202570e`** — these are those runs, not the earlier ones.

**Method.** Each guarded element is neutralized on its own — the *thing the detector guards* is
disabled, never the detector — with a targeted edit applied through the host's edit action and
reverted by the exact inverse edit. Every command selects its test by **exact test name**, never
`-k`. The working tree was confirmed clean (`git status --porcelain` empty) after each restore and
before the green run. Every proof below was re-run on the layer's final head.

## Guarded elements

| ID | Guarded element | Neutralized thing | Proving test |
|---|---|---|---|
| BP-B2-1 | schema-invalid forfeit | `validate`'s verdict is ignored at the call site | `test_grade_native_review_attempt_schema_invalid` |
| BP-B2-2 | oversized-result forfeit | both size checks (stat leg and read leg) | `test_grade_native_review_attempt_result_oversized` |
| BP-B2-3 | malformed-result forfeit | the JSON-parse guard | `test_grade_native_review_attempt_result_malformed_json` |
| BP-B2-4 | scrub egress on the typed result | scrubbed findings replaced by the raw branch value | `test_grade_native_review_attempt_scrubs_secret_from_result_and_journal` |
| BP-B2-5 | kind-recognised-before-validation ordering | validation's verdict decides before the kind check | `test_grade_native_review_attempt_kind_before_validation` |
| BP-B2-6 | marker-path non-reachability (five functions) | the marker parser is consulted on the native path | `test_grade_native_review_attempt_marker_salvage_path_not_reached` |

Common command prefix:

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest \
  plugins/superheroes/lib/tests/test_engine_dispatch.py::<exact test name> -q
```

---

## BP-B2-1 — the schema-invalid forfeit

- **axis:** a typed result that parses but fails schema validation must forfeit
  `native-result-schema-invalid`.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_grade_native_review_attempt`):
```python
    engine_result_channel._validate_with_detail(schema, envelope)
    ok, validation_reason, validation_detail = True, None, None  # bite-proof BP-B2-1
```
(replaces the three-tuple call
`ok, validation_reason, validation_detail = engine_result_channel._validate_with_detail(schema, envelope)`;
the validator still runs, its verdict is discarded — the exact "ignored at the call site" shape)

**command:** `…::test_grade_native_review_attempt_schema_invalid -q`

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_grade_native_review_attempt_schema_invalid ________________

    def test_grade_native_review_attempt_schema_invalid(tmp_path):
        branch = _native_review_branch("findings")
        branch["findings"] = None
        run_dir, state = _native_review_grade_state(tmp_path, branch)
        grade = ED._grade_review_attempt(run_dir, state, 1)
        assert grade.get("forfeit") is True
>       assert grade.get("detail") == "native-result-schema-invalid"
E       AssertionError: assert None == 'native-result-schema-invalid'
E        +  where None = <built-in method get of dict object at 0x109565b00>('detail')

plugins/superheroes/lib/tests/test_engine_dispatch.py:10428: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_schema_invalid
1 failed in 0.75s
```

**restore** (inverse edit):
```python
    ok, validation_reason, validation_detail = engine_result_channel._validate_with_detail(
        schema, envelope)
```

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.61s
```

---

## BP-B2-2 — the oversized-result forfeit

- **axis:** a typed result larger than `NATIVE_RESULT_MAX_BYTES` must forfeit
  `native-result-oversized`.
- **note:** the element has **two** sites — the `stat` size leg and the post-read length leg.
  Neutralizing only one leaves the other catching the case, which would make the proof vacuous, so
  both legs are neutralized in this single probe and both are restored together.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_read_native_review_envelope`):
```python
    if False:  # bite-proof neutralization BP-B2-2 (size check, stat leg)
        return _native_review_forfeit(engagement, "native-result-oversized")
...
    if False:  # bite-proof neutralization BP-B2-2 (size check, read leg)
        return _native_review_forfeit(engagement, "native-result-oversized")
```
(replaces `if st.st_size > engine_result_channel.NATIVE_RESULT_MAX_BYTES:` and
`if len(raw) > engine_result_channel.NATIVE_RESULT_MAX_BYTES:`)

**command:** `…::test_grade_native_review_attempt_result_oversized -q`

**raw red** (exit 1):
```
        run_dir, state = _native_review_grade_state(tmp_path, branch)
        result_path = state["opened"]["nativeResultPath"]
        with open(result_path, "wb") as fh:
            fh.write(b"x" * (ERC.NATIVE_RESULT_MAX_BYTES + 1))
        grade = ED._grade_review_attempt(run_dir, state, 1)
        assert grade.get("forfeit") is True
>       assert grade.get("detail") == "native-result-oversized"
E       AssertionError: assert 'native-result-malformed' == 'native-result-oversized'

plugins/superheroes/lib/tests/test_engine_dispatch.py:10389: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_result_oversized
1 failed in 1.65s
```

**restore** (inverse edits, both legs):
```python
    if st.st_size > engine_result_channel.NATIVE_RESULT_MAX_BYTES:
        return _native_review_forfeit(engagement, "native-result-oversized")
...
    if len(raw) > engine_result_channel.NATIVE_RESULT_MAX_BYTES:
        return _native_review_forfeit(engagement, "native-result-oversized")
```

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 0.93s
```

---

## BP-B2-3 — the malformed-result forfeit

- **axis:** a result file that is not parseable JSON must forfeit `native-result-malformed`.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_read_native_review_envelope`):
```python
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        envelope = {"result": {}}  # bite-proof neutralization BP-B2-3 (JSON-parse guard)
```
(replaces the two-line forfeit return in the same `except` clause — the parse failure is swallowed
and grading continues)

**command:** `…::test_grade_native_review_attempt_result_malformed_json -q`

**raw red** (exit 1):
```
    def test_grade_native_review_attempt_result_malformed_json(tmp_path):
        run_dir, state = _native_review_grade_state(tmp_path, _native_review_branch("findings"))
        with open(state["opened"]["nativeResultPath"], "w", encoding="utf-8") as fh:
            fh.write("not-json\n")
        grade = ED._grade_review_attempt(run_dir, state, 1)
        assert grade.get("forfeit") is True
>       assert grade.get("detail") == "native-result-malformed"
E       AssertionError: assert 'native-result-schema-invalid' == 'native-result-malformed'

plugins/superheroes/lib/tests/test_engine_dispatch.py:10398: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_result_malformed_json
1 failed in 1.58s
```

**restore** (inverse edit):
```python
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        shape = engine_result_channel.native_review_payload_shape("native-result-malformed")
        return _native_review_forfeit(engagement, "native-result-malformed", payload_shape=shape)
```

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 1.00s
```

---

## BP-B2-4 — the scrub egress on the typed result

- **axis:** a secret-shaped token inside a schema-validated typed result is absent from the returned
  result **and** from the journal.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`,
`_scrub_native_review_branch`):
```python
        _unused, findings_rejected = engine_adapter._scrub_findings(
            branch.get("findings") or [], echo_nonce=echo_nonce)
        findings_list = branch.get("findings") or []  # bite-proof neutralization BP-B2-4
```
(replaces the binding of `findings_list` to the scrubbed value; the scrub still runs, its output is
discarded — the "returning the unscrubbed value" shape)

**command:** `…::test_grade_native_review_attempt_scrubs_secret_from_result_and_journal -q`

**raw red** (exit 1; the planted token is the test's own fake specimen, not a live secret):
```
        assert res.get("ok") is True
>       assert _NATIVE_REVIEW_SECRET not in json.dumps(res)
E       assert 'sk-EXAMPLEf...arealsecret0' not in '{"ok": true...": "review"}'
E
E         'sk-EXAMPLEfakenotarealsecret0' is contained here:
E           n: Bearer sk-EXAMPLEfakenotarealsecret0", "suggestion": "example", …

plugins/superheroes/lib/tests/test_engine_dispatch.py:10469: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_scrubs_secret_from_result_and_journal
1 failed in 3.17s
```

**restore** (inverse edit):
```python
        findings_list, findings_rejected = engine_adapter._scrub_findings(
            branch.get("findings") or [], echo_nonce=echo_nonce)
```

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 4.44s
```

---

## BP-B2-5 — kind recognised before validation decides

- **axis:** a recognised-but-wrong `resultKind` forfeits `result-kind-mismatch`, **not**
  `native-result-schema-invalid` — the ordering keeps `result-kind-mismatch` meaningful.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_grade_native_review_attempt`):
```python
        if False:  # bite-proof neutralization BP-B2-5 (validation decides before kind)
```
(replaces
`if scrub_try.get("ok") and engine_result_channel.native_schema_allows_scrub_finish(validation_detail, branch=branch):`
— the step that lets a recognised wrong kind reach the kind check instead of being swallowed by the
schema verdict; disabling it is exactly the two steps swapped)

**command:** `…::test_grade_native_review_attempt_kind_before_validation -q`

**raw red** (exit 1):
```
            tmp_path, branch, expected_result_kind="findings",
        )
        grade = ED._grade_review_attempt(run_dir, state, 1)
        assert grade.get("forfeit") is True
>       assert grade.get("detail") == ED.RESULT_KIND_MISMATCH_DETAIL
E       AssertionError: assert 'native-result-schema-invalid' == 'result-kind-mismatch'

plugins/superheroes/lib/tests/test_engine_dispatch.py:10439: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_kind_before_validation
1 failed in 3.88s
```

**restore** (inverse edit):
```python
        if scrub_try.get("ok") and engine_result_channel.native_schema_allows_scrub_finish(
                validation_detail, branch=branch):
```

**raw green** (exit 0, tree clean):
```
.                                                                        [100%]
1 passed in 3.76s
```

---

## BP-B2-6 — the marker path is not reachable on a good native grade

- **axis:** on a well-formed native review result none of the five marker-channel functions
  (`parse_result`, `normalize_review_stdout`, `review_payload_shape`, `review_artifact_shape`,
  `salvage_from_artifact`) is consulted.

**neutralization** (`plugins/superheroes/lib/engine_dispatch.py`, `_grade_native_review_attempt`) —
the pre-retirement behaviour reinstated on the success path:
```python
    if ok and scrub_try.get("ok"):
        # bite-proof neutralization BP-B2-6: marker parser consulted on the native path
        engine_adapter.parse_result(
            engine, role_kind, stdout if isinstance(stdout, str) else "",
            echo_nonce=echo_nonce)
        return _finish_review_grade_from_parse(opened, cwd, engagement, scrub_try)
```

**command:** `…::test_grade_native_review_attempt_marker_salvage_path_not_reached -q`

**raw red** (exit 1 — the detector fires through the test's own boom stub, proving reachability is
what it measures):
```
plugins/superheroes/lib/engine_dispatch.py:3512: in _grade_review_attempt
    return _grade_native_review_attempt(
plugins/superheroes/lib/engine_dispatch.py:3392: in _grade_native_review_attempt
    engine_adapter.parse_result(
_args = ('codex', 'review', ''), _kwargs = {'echo_nonce': None}

    def boom(*_args, **_kwargs):
>       raise AssertionError("marker parser must not run on native review grade")
E       AssertionError: marker parser must not run on native review grade

plugins/superheroes/lib/tests/test_engine_dispatch.py:10518: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_engine_dispatch.py::test_grade_native_review_attempt_marker_salvage_path_not_reached
1 failed in 4.50s
```

**restore** (inverse edit):
```python
    if ok and scrub_try.get("ok"):
        return _finish_review_grade_from_parse(opened, cwd, engagement, scrub_try)
```

**raw green** (exit 0, tree clean — `git status --porcelain` and `git diff --stat` both empty):
```
.                                                                        [100%]
1 passed in 1.82s
```

---

## Scope of what this record proves, stated plainly

These six proofs cover the **native review grading path** on codex. They do not cover codex's
**write** path, which still comes home on the marker channel until layer 2b, nor the retirement of
the marker parser and the salvage tiers from codex's non-success branches, which is layer 2c. On a
*good* native review result the marker functions are provably not reached (BP-B2-6); the residual
stdout-diagnosis branches reached only after a native read or scrub failure are deliberately still
present at this head and are 2c's to gate.
