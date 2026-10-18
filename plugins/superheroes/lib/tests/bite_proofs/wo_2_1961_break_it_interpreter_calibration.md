# WO-2 (#1961) bite-proof — the `breakItInterpreter` calibration: writer validation, rewrite carry, config emission, suggestion

**Provenance:** claude / sonnet-5.5 (implementer, WO-2), `plugins/superheroes/lib/core_md.py` (`write_break_it_interpreter`, `render_core`, `confirm`, `_break_it_interpreter_suggestion`) and `plugins/superheroes/lib/review_code_config.py` (`_break_it_interpreter_value`); detector file `plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py`.

Declared guarded-element set (from the order): **H1-H5**. Each was neutralized by one targeted edit (the Edit tool, an exact old-string to new-string swap), its detector node run, the inverse edit applied, and the same node run again. No `git checkout`, `git restore`, `git reset` or `git stash` was used. Command: `scripts/pinned-python -B -X pycache_prefix=/tmp/pyc-wo2 -m pytest -q -p no:cacheprovider <node>`.

## Guarded elements

| ID | Guarded element | Axis | Proving node |
|---|---|---|---|
| H1 | the writer's validation refusal in `write_break_it_interpreter` (`if break_it_interpreter_argv(value) is None: return refused`) | C2: a launcher that does not validate is refused before any write, core.md bytes unchanged | `test_c2_malformed_write_is_refused_and_core_bytes_unchanged (2 params: `-x`, `'unterminated`)` |
| H2 | the confirm-site carry in `confirm` (`if BREAK_IT_INTERPRETER_KEY in existing: facts[...] = existing[...]`) | C4: a provisional-to-confirmed rewrite keeps the stored value raw, malformed and null included | `test_c4_confirm_carries_the_value (4 params: valid, malformed-int, null, malformed-dash)` |
| H3 | the render_core carry (`if BREAK_IT_INTERPRETER_KEY in facts: block[...] = copy.deepcopy(...)`) | C4: parse_core then render_core keeps the stored value raw | `test_c4_parse_then_render_carries_the_value (4 params)` |
| H4 | review_code_config's non-string to `""` branch (`_break_it_interpreter_value`'s final `return ""`) | C5: a non-string stored value is emitted as `""` so the driver reads it as set-but-invalid (fail closed), never unset | `test_c5_emission_then_handoff_fails_closed[non-string]` |
| H5 | the suggestion's executable check in `_break_it_interpreter_suggestion` (`os.access(path, os.X_OK)`) | C3: the suggestion is offered only for a regular executable file | `test_c3_suggestion_follows_the_executable_file` |

## Disclosures

- All five elements went red under their neutralization (pytest exit 1) and green after the inverse edit (exit 0).
- Parametrized nodes were run whole (every param), so each red reports every param failing together.
- H2 (confirm) and H3 (render_core) are separate failure modes: the H2 node drives `confirm_all` on a provisional core.md; the H3 node calls `render_core` / `parse_core` directly. Neutralizing H3 would also redden the H2 node (confirm re-renders through render_core); that was not run, only the named detector node per element.
- Not separately neutralized (outside the declared set): the `parse_core` and `read` carry sites, the reader's malformed branch, the CLI handlers and the view lines. The same test file exercises them but they have no recorded red here.
- Red captures are well under 32 KiB; none is written off-repo.
- Restore receipts: the restored lines are quoted back from the file after the inverse edit (a grep read, with line numbers as they stand).

---

## H1 — the writer's validation refusal in `write_break_it_interpreter` (`if break_it_interpreter_argv(value) is None: return refused`)

- **axis:** C2: a launcher that does not validate is refused before any write, core.md bytes unchanged
- **detector:** `test_c2_malformed_write_is_refused_and_core_bytes_unchanged (2 params: `-x`, `'unterminated`)`

**neutralization** (`plugins/superheroes/lib/core_md.py`):
```diff
-    if break_it_interpreter_argv(value) is None:
+    if False:
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FF                                                                       [100%]
=================================== FAILURES ===================================
______ test_c2_malformed_write_is_refused_and_core_bytes_unchanged['-x'] _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_c2_malformed_write_is_ref0')
text = '-x'

    @pytest.mark.parametrize("text", ["-x", "'unterminated"], ids=repr)
    def test_c2_malformed_write_is_refused_and_core_bytes_unchanged(tmp_path, text):
        # axis: C2 a launcher that does not validate is refused before any write — core.md bytes equal
        repo, store = _setup_repo(tmp_path)
        before = _core_bytes(repo, store)
        out = _cli("write-break-it-interpreter", repo, store, text + "\n")
>       assert out == {"action": "refused", "reason": "break-it-interpreter-malformed"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...er-malformed'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'break-it-interpreter-malformed'}
E         Use -v to get more diff

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:197: AssertionError
_ test_c2_malformed_write_is_refused_and_core_bytes_unchanged["'unterminated"] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_c2_malformed_write_is_ref1')
text = "'unterminated"

    @pytest.mark.parametrize("text", ["-x", "'unterminated"], ids=repr)
    def test_c2_malformed_write_is_refused_and_core_bytes_unchanged(tmp_path, text):
        # axis: C2 a launcher that does not validate is refused before any write — core.md bytes equal
        repo, store = _setup_repo(tmp_path)
        before = _core_bytes(repo, store)
        out = _cli("write-break-it-interpreter", repo, store, text + "\n")
>       assert out == {"action": "refused", "reason": "break-it-interpreter-malformed"}
E       AssertionError: assert {'action': 'written'} == {'action': 'r...er-malformed'}
E         
E         Differing items:
E         {'action': 'written'} != {'action': 'refused'}
E         Right contains 1 more item:
E         {'reason': 'break-it-interpreter-malformed'}
E         Use -v to get more diff

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:197: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c2_malformed_write_is_refused_and_core_bytes_unchanged['-x']
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c2_malformed_write_is_refused_and_core_bytes_unchanged["'unterminated"]
2 failed in 2.91s
exit=1
```

**decisive assertion:** `>       assert out == {"action": "refused", "reason": "break-it-interpreter-malformed"}` (`E       AssertionError: assert {'action': 'written'} == ...`) — the malformed value was written.

**restore:** the inverse edit (the neutralized lines replaced by the original text).

**restored lines** (as they stand):
```
plugins/superheroes/lib/core_md.py:2514:    if break_it_interpreter_argv(value) is None:
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
..                                                                       [100%]
2 passed in 1.20s
exit=0
```

---

## H2 — the confirm-site carry in `confirm` (`if BREAK_IT_INTERPRETER_KEY in existing: facts[...] = existing[...]`)

- **axis:** C4: a provisional-to-confirmed rewrite keeps the stored value raw, malformed and null included
- **detector:** `test_c4_confirm_carries_the_value (4 params: valid, malformed-int, null, malformed-dash)`

**neutralization** (`plugins/superheroes/lib/core_md.py`):
```diff
-            if BREAK_IT_INTERPRETER_KEY in existing:
+            if False:
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF                                                                     [100%]
=================================== FAILURES ===================================
___________________ test_c4_confirm_carries_the_value[valid] ___________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_c4_confirm_carries_the_va0')
raw = 'scripts/pinned-python'

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_confirm_carries_the_value(tmp_path, raw):
        # axis: C4 confirm (provisional to confirmed) re-renders core.md and keeps the key raw
        repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
        assert CM.confirm_all(repo, root=store)["core"]["action"] == "confirmed"
        parsed = _parsed(repo, store)
>       assert _KEY in parsed
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'verifyCommand': 'pytest -q', 'stackTags': ['python'], 'enginePreferences': {}}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:380: AssertionError
_______________ test_c4_confirm_carries_the_value[malformed-int] _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_c4_confirm_carries_the_va1')
raw = 5

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_confirm_carries_the_value(tmp_path, raw):
        # axis: C4 confirm (provisional to confirmed) re-renders core.md and keeps the key raw
        repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
        assert CM.confirm_all(repo, root=store)["core"]["action"] == "confirmed"
        parsed = _parsed(repo, store)
>       assert _KEY in parsed
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'verifyCommand': 'pytest -q', 'stackTags': ['python'], 'enginePreferences': {}}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:380: AssertionError
___________________ test_c4_confirm_carries_the_value[null] ____________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_c4_confirm_carries_the_va2')
raw = None

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_confirm_carries_the_value(tmp_path, raw):
        # axis: C4 confirm (provisional to confirmed) re-renders core.md and keeps the key raw
        repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
        assert CM.confirm_all(repo, root=store)["core"]["action"] == "confirmed"
        parsed = _parsed(repo, store)
>       assert _KEY in parsed
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'verifyCommand': 'pytest -q', 'stackTags': ['python'], 'enginePreferences': {}}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:380: AssertionError
______________ test_c4_confirm_carries_the_value[malformed-dash] _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-19/test_c4_confirm_carries_the_va3')
raw = '-x'

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_confirm_carries_the_value(tmp_path, raw):
        # axis: C4 confirm (provisional to confirmed) re-renders core.md and keeps the key raw
        repo, store = _setup_repo(tmp_path, extra_block={_KEY: raw}, status="provisional")
        assert CM.confirm_all(repo, root=store)["core"]["action"] == "confirmed"
        parsed = _parsed(repo, store)
>       assert _KEY in parsed
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'verifyCommand': 'pytest -q', 'stackTags': ['python'], 'enginePreferences': {}}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:380: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_confirm_carries_the_value[valid]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_confirm_carries_the_value[malformed-int]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_confirm_carries_the_value[null]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_confirm_carries_the_value[malformed-dash]
4 failed in 2.09s
exit=1
```

**decisive assertion:** `>       assert _KEY in parsed` — confirm dropped the key from core.md.

**restore:** the inverse edit (the neutralized lines replaced by the original text).

**restored lines** (as they stand):
```
plugins/superheroes/lib/core_md.py:3122:            if BREAK_IT_INTERPRETER_KEY in existing:
plugins/superheroes/lib/core_md.py:3123:                facts[BREAK_IT_INTERPRETER_KEY] = existing[BREAK_IT_INTERPRETER_KEY]
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed in 1.33s
exit=0
```

---

## H3 — the render_core carry (`if BREAK_IT_INTERPRETER_KEY in facts: block[...] = copy.deepcopy(...)`)

- **axis:** C4: parse_core then render_core keeps the stored value raw
- **detector:** `test_c4_parse_then_render_carries_the_value (4 params)`

**neutralization** (`plugins/superheroes/lib/core_md.py`):
```diff
-    if BREAK_IT_INTERPRETER_KEY in facts:
+    if False:
         block[BREAK_IT_INTERPRETER_KEY] = copy.deepcopy(facts[BREAK_IT_INTERPRETER_KEY])
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFF                                                                     [100%]
=================================== FAILURES ===================================
______________ test_c4_parse_then_render_carries_the_value[valid] ______________

raw = 'scripts/pinned-python'

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_parse_then_render_carries_the_value(raw):
        # axis: C4 parse_core then render_core keeps the key raw, malformed and null included
        text = CM.render_core(dict(_CORE_FACTS, **{_KEY: raw}), "confirmed", "2026-06-26",
                              "2026-06-26")
        facts = CM.parse_core(text)
>       assert _KEY in facts
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'status': 'confirmed', 'verifyCommand': 'pytest -q', 'stackTags': ['python'], ...}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:390: AssertionError
__________ test_c4_parse_then_render_carries_the_value[malformed-int] __________

raw = 5

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_parse_then_render_carries_the_value(raw):
        # axis: C4 parse_core then render_core keeps the key raw, malformed and null included
        text = CM.render_core(dict(_CORE_FACTS, **{_KEY: raw}), "confirmed", "2026-06-26",
                              "2026-06-26")
        facts = CM.parse_core(text)
>       assert _KEY in facts
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'status': 'confirmed', 'verifyCommand': 'pytest -q', 'stackTags': ['python'], ...}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:390: AssertionError
______________ test_c4_parse_then_render_carries_the_value[null] _______________

raw = None

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_parse_then_render_carries_the_value(raw):
        # axis: C4 parse_core then render_core keeps the key raw, malformed and null included
        text = CM.render_core(dict(_CORE_FACTS, **{_KEY: raw}), "confirmed", "2026-06-26",
                              "2026-06-26")
        facts = CM.parse_core(text)
>       assert _KEY in facts
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'status': 'confirmed', 'verifyCommand': 'pytest -q', 'stackTags': ['python'], ...}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:390: AssertionError
_________ test_c4_parse_then_render_carries_the_value[malformed-dash] __________

raw = '-x'

    @pytest.mark.parametrize("raw", list(_CARRIED.values()), ids=list(_CARRIED))
    def test_c4_parse_then_render_carries_the_value(raw):
        # axis: C4 parse_core then render_core keeps the key raw, malformed and null included
        text = CM.render_core(dict(_CORE_FACTS, **{_KEY: raw}), "confirmed", "2026-06-26",
                              "2026-06-26")
        facts = CM.parse_core(text)
>       assert _KEY in facts
E       AssertionError: assert 'breakItInterpreter' in {'schemaVersion': 2, 'status': 'confirmed', 'verifyCommand': 'pytest -q', 'stackTags': ['python'], ...}

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:390: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_parse_then_render_carries_the_value[valid]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_parse_then_render_carries_the_value[malformed-int]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_parse_then_render_carries_the_value[null]
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c4_parse_then_render_carries_the_value[malformed-dash]
4 failed in 0.36s
exit=1
```

**decisive assertion:** `>       assert _KEY in facts` — the rendered core.md carries no key.

**restore:** the inverse edit (the neutralized lines replaced by the original text).

**restored lines** (as they stand):
```
plugins/superheroes/lib/core_md.py:418:    if BREAK_IT_INTERPRETER_KEY in facts:
plugins/superheroes/lib/core_md.py:419:        block[BREAK_IT_INTERPRETER_KEY] = copy.deepcopy(facts[BREAK_IT_INTERPRETER_KEY])
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
....                                                                     [100%]
4 passed in 0.31s
exit=0
```

---

## H4 — review_code_config's non-string to `""` branch (`_break_it_interpreter_value`'s final `return ""`)

- **axis:** C5: a non-string stored value is emitted as `""` so the driver reads it as set-but-invalid (fail closed), never unset
- **detector:** `test_c5_emission_then_handoff_fails_closed[non-string]`

**neutralization** (`plugins/superheroes/lib/review_code_config.py`):
```diff
-    return ""
+    return value
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_c5_emission_then_handoff_fails_closed[non-string] ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-23/test_c5_emission_then_handoff_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fad326ae840>
case = 'non-string'

    @pytest.mark.parametrize("case", list(_EMISSIONS), ids=list(_EMISSIONS))
    def test_c5_emission_then_handoff_fails_closed(tmp_path, monkeypatch, case):
        # axis: C5 resolve emits null / verbatim string / "" faithfully and the setup handoff turns each into the driver's answer
        block, emitted, launcher = _EMISSIONS[case]
        repo, store = _setup_repo(tmp_path, extra_block=block)
        import calibration_resolve
        monkeypatch.setattr(calibration_resolve, "resolve",
                            lambda cwd, root=None, **kw: {"exists": False, "dispatch_layer": None,
                                                          "legacy_path": None})
        out = review_code_config.resolve(repo, root=store)
        assert out["verifyCommand"] == "pytest -q"
>       assert out[_KEY] == emitted
E       AssertionError: assert 5 == ''

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:471: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c5_emission_then_handoff_fails_closed[non-string]
1 failed in 0.89s
exit=1
```

**decisive assertion:** `>       assert out[_KEY] == emitted` (`E       AssertionError: assert 5 == ''`).

**restore:** the inverse edit (the neutralized lines replaced by the original text).

**restored lines** (as they stand):
```
plugins/superheroes/lib/review_code_config.py:76:    if value is None or isinstance(value, str):
plugins/superheroes/lib/review_code_config.py:77:        return value
plugins/superheroes/lib/review_code_config.py:78:    return ""
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.61s
exit=0
```

---

## H5 — the suggestion's executable check in `_break_it_interpreter_suggestion` (`os.access(path, os.X_OK)`)

- **axis:** C3: the suggestion is offered only for a regular executable file
- **detector:** `test_c3_suggestion_follows_the_executable_file`

**neutralization** (`plugins/superheroes/lib/core_md.py`):
```diff
-        if os.path.isfile(path) and os.access(path, os.X_OK):
+        if os.path.isfile(path):
```

**raw red** (exit 1):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_c3_suggestion_follows_the_executable_file ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-25/test_c3_suggestion_follows_the0')

    def test_c3_suggestion_follows_the_executable_file(tmp_path):
        # axis: C3 the suggestion is scripts/pinned-python only for an executable regular file
        repo, store = _setup_repo(tmp_path)
        assert _cli("break-it-interpreter", repo, store)["suggestion"] is None
        _make_launcher(repo, mode=0o644)
>       assert _cli("break-it-interpreter", repo, store)["suggestion"] is None
E       AssertionError: assert 'scripts/pinned-python' is None

/home/user/wt-1961-wo2/plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py:294: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_break_it_interpreter_calibration_1961.py::test_c3_suggestion_follows_the_executable_file
1 failed in 1.11s
exit=1
```

**decisive assertion:** `>       assert _cli("break-it-interpreter", repo, store)["suggestion"] is None` (`E       AssertionError: assert 'scripts/pinned-python' is None`) — a mode-0644 file was suggested.

**restore:** the inverse edit (the neutralized lines replaced by the original text).

**restored lines** (as they stand):
```
plugins/superheroes/lib/core_md.py:2446:        if os.path.isfile(path) and os.access(path, os.X_OK):
```

**raw green** (exit 0):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.32s
exit=0
```
