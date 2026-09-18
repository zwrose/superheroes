# WO-1299 bite-proof — fixer file-scope guard retirement pin

**Provenance:** cursor / composer-2.5 (auto-fix round 2).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-1299-1 | `escalation.py` module surface | must not expose `SAFETY_MACHINERY` or `is_safety_machinery` | `test_escalation_module_has_no_file_scope_guard` |
| BP-1299-2 | dispatch-fixer order rendered via `round_driver._build_order_render_context` | must not cite wrapper/guard vocabulary | `test_dispatch_fixer_order_has_no_guard_instruction` |
| BP-1299-3 | `rubric/review-discipline.md` | retired guard vocabulary absent | `test_retired_guard_vocabulary_absent[review-discipline.md]` |
| BP-1299-4 | `skills/review-code/reference/auto-fix-loop.md` | retired guard vocabulary absent | `test_retired_guard_vocabulary_absent[auto-fix-loop.md]` |

---

## BP-1299-1 — escalation module guard machinery

- **axis:** `SAFETY_MACHINERY` must not be exposed on the module

**neutralization** (`plugins/superheroes/lib/escalation.py`, module tail):
```python
SAFETY_MACHINERY = frozenset()
```

**command:**
```
/Users/zwrose/.claude/superheroes/projects/8fa39520fa839af0/venv/bin/python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_fixer_guard_retirement_pin.py::test_escalation_module_has_no_file_scope_guard -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
FAILED plugins/superheroes/lib/tests/test_fixer_guard_retirement_pin.py::test_escalation_module_has_no_file_scope_guard
1 failed in 0.05s
```

**restore:** removed the planted `SAFETY_MACHINERY` assignment.

**restore receipt:** `git status --porcelain` over `plugins/superheroes/lib/escalation.py` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.04s
```

---

## BP-1299-2 — fixer order guard instruction

- **axis:** rendered fixer order must not contain `file-scope guard`

**neutralization** (`plugins/superheroes/rubric/orders/dispatch-fixer.md`, job section):
```markdown
3. Run the file-scope guard before every edit.
```

**command:**
```
/Users/zwrose/.claude/superheroes/projects/8fa39520fa839af0/venv/bin/python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_fixer_guard_retirement_pin.py::test_dispatch_fixer_order_has_no_guard_instruction -q
```

**raw red** (exit 1):
```
F                                                                        [100%]
AssertionError: dispatch-fixer order must not cite 'file-scope guard'
1 failed in 0.08s
```

**restore:** removed the planted line from `dispatch-fixer.md`.

**restore receipt:** `git status --porcelain` over `plugins/superheroes/rubric/orders/dispatch-fixer.md` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.07s
```

---

## BP-1299-3 — review-discipline retired vocabulary

- **axis:** `safety machinery` must be absent from `review-discipline.md`

**neutralization** (`plugins/superheroes/rubric/review-discipline.md`):
```markdown
Restored safety machinery wording for the bite-proof probe.
```

**command:**
```
/Users/zwrose/.claude/superheroes/projects/8fa39520fa839af0/venv/bin/python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_fixer_guard_retirement_pin.py::test_retired_guard_vocabulary_absent[review-discipline.md]' -q
```

**raw red** (exit 1):
```
AssertionError: ... retired vocabulary 'safety machinery' present
1 failed in 0.04s
```

**restore:** removed the planted sentence.

**restore receipt:** `git status --porcelain` over `plugins/superheroes/rubric/review-discipline.md` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.04s
```

---

## BP-1299-4 — auto-fix-loop retired vocabulary

- **axis:** `file-scope guard` must be absent from `auto-fix-loop.md`

**neutralization** (`plugins/superheroes/skills/review-code/reference/auto-fix-loop.md`):
```markdown
Run the file-scope guard before applying each fix.
```

**command:**
```
/Users/zwrose/.claude/superheroes/projects/8fa39520fa839af0/venv/bin/python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_fixer_guard_retirement_pin.py::test_retired_guard_vocabulary_absent[auto-fix-loop.md]' -q
```

**raw red** (exit 1):
```
AssertionError: ... retired vocabulary 'file-scope guard' present
1 failed in 0.04s
```

**restore:** removed the planted sentence.

**restore receipt:** `git status --porcelain` over `plugins/superheroes/skills/review-code/reference/auto-fix-loop.md` empty.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.04s
```
