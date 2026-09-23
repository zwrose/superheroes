# C14 layer 3c WO-A2 — bite-proofs

Stdout drop-cause recording and save-time byte digest check for held claude print results.

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-A2-1 | `_observe_stdout_completion` terminal `except` branches: `_record_stdout_drop_cause(..., "final-read-failed")` | terminal read failure reports `stdout-result-dropped` / `final-read-failed` at admission | `test_stdout_final_read_failed_reports_dropped_cause` |
| BP-A2-2 | `_observe_stdout_completion` size-regression branch: `_record_stdout_drop_cause(..., "shrunk-below-read")` | stdout shrink reports `stdout-result-dropped` / `shrunk-below-read` at admission | `test_stdout_shrunk_below_read_reports_dropped_cause` |
| BP-A2-3 | `_held_stdout_bytes_unchanged` digest compare | bytes changed after stamp drop with `bytes-changed` and nothing materialized | `test_stdout_bytes_changed_reports_dropped_cause` |
| BP-A2-4 | `_held_stdout_bytes_unchanged` body | save-time check never calls `json.loads` | `test_held_stdout_bytes_check_never_reparses` |

---

## BP-A2-1 — final-read-failed

- **axis:** terminal read failure reports `stdout-result-dropped` with `final-read-failed`

**neutralization** (`engine_dispatch.py`, `_observe_stdout_completion` terminal except branches):

remove both `_record_stdout_drop_cause(obs_state, "final-read-failed")` lines.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-A2 -m pytest plugins/superheroes/lib/tests/test_stdout_read_failures.py::test_stdout_final_read_failed_reports_dropped_cause -q -p no:xdist
```

**raw red** (exit 1):
```
F                                                                        [100%]
AssertionError: assert None == 'final-read-failed'
```

**restore:** reinstate both `_record_stdout_drop_cause(obs_state, "final-read-failed")` lines.

**restore receipt:** post-restore `git status --porcelain -- plugins/superheroes/lib/engine_dispatch.py` shows only unrelated untracked paths.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.76s
```

---

## BP-A2-2 — shrunk-below-read

- **axis:** stdout shrink below bytes already read reports `stdout-result-dropped` with `shrunk-below-read`

**neutralization** (`engine_dispatch.py`, size-regression branch):

remove `_record_stdout_drop_cause(obs_state, "shrunk-below-read")`.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-A2 -m pytest plugins/superheroes/lib/tests/test_stdout_read_failures.py::test_stdout_shrunk_below_read_reports_dropped_cause -q -p no:xdist
```

**raw red** (exit 1):
```
F                                                                        [100%]
AssertionError: assert None == 'shrunk-below-read'
```

**restore:** reinstate `_record_stdout_drop_cause(obs_state, "shrunk-below-read")`.

**restore receipt:** neutralization removed from `engine_dispatch.py`.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.98s
```

---

## BP-A2-3 — bytes-changed

- **axis:** bytes changed after stamp drop with `bytes-changed` and nothing materialized

**neutralization** (`engine_dispatch.py`, `_held_stdout_bytes_unchanged`):

add `return True` as the first statement.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-A2 -m pytest plugins/superheroes/lib/tests/test_stdout_read_failures.py::test_stdout_bytes_changed_reports_dropped_cause -q -p no:xdist
```

**raw red** (exit 1):
```
F                                                                        [100%]
AssertionError: assert None == 'bytes-changed'
```

**restore:** remove unconditional `return True`.

**restore receipt:** `_held_stdout_bytes_unchanged` body restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.77s
```

---

## BP-A2-4 — no second parse

- **axis:** save-time byte check never calls `json.loads`

**neutralization** (`engine_dispatch.py`, `_held_stdout_bytes_unchanged`):

add `json.loads(line_bytes)` after reading bytes.

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-l3c-A2 -m pytest plugins/superheroes/lib/tests/test_stdout_read_failures.py::test_held_stdout_bytes_check_never_reparses -q -p no:xdist
```

**raw red** (exit 1):
```
F                                                                        [100%]
assert [1] == []
```

**restore:** remove `json.loads(line_bytes)`.

**restore receipt:** helper body restored.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.13s
```
