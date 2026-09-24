# C14 layer 3c WO-B — bite-proofs

**Covers:** WO-B (abbreviated diff-base token; probe path normalization).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-B1 | `_require_pinned_commit_oid` abbreviated length gate | 4–39 hex ids get `sanitized-view-diff-base-abbreviated` | `test_require_pinned_commit_oid_names_abbreviated_id` |
| BP-B2 | `_require_pinned_commit_oid` non-abbreviated refusals | non-hex and 41-char hex keep `sanitized-view-diff-base-unresolved` | `test_require_pinned_commit_oid_non_hex_stays_unresolved` (green only) |
| BP-B3 | `probe()` run_dir `os.fspath` normalization | `pathlib.Path` run_dir behaves like `str` | `test_probe_accepts_pathlib_run_dir` |
| BP-B4 | `probe()` run_dir normalization `try`/`except` | non-path `run_dir` refuses with `run-dir-invalid` instead of raising | `test_probe_refuses_non_path_run_dir` |
| BP-B5 | `probe()` run_dir `os.fsdecode` | bytes `run_dir` decodes to `str` before strip/endwith | `test_probe_accepts_bytes_run_dir` |

---

## BP-B1 — abbreviated id token

- **axis:** 4–39 hex ids get `sanitized-view-diff-base-abbreviated`

**neutralization** (`plugins/superheroes/lib/sanitized_view.py`, `_require_pinned_commit_oid`): delete the abbreviated length check block.

**red** (exit 1):
```
FF                                                                       [100%]
AssertionError: assert 'sanitized-view-diff-base-unresolved' == 'sanitized-view-diff-base-abbreviated'
```

**restore:** reinstate the `4 <= len(value) <= 39` abbreviated check raising `"sanitized-view-diff-base-abbreviated"`.

**restore receipt:** `if all(c in "0123456789abcdef" for c in value.lower()):` / `if 4 <= len(value) <= 39:` / `raise SanitizedViewError("sanitized-view-diff-base-abbreviated")`

**green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.19s
```

---

## BP-B2 — healthy-case guard (green only)

- **axis:** non-hex and over-39 hex keep `sanitized-view-diff-base-unresolved`
- **neutralization owed:** none (healthy-case guard)

**green** (exit 0):
```
..                                                                       [100%]
2 passed in 0.18s
```

---

## BP-B3 — pathlib run_dir normalization

- **axis:** `pathlib.Path` run_dir behaves like `str`

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `probe()`): remove the `run_dir` normalization block (the `os.fsdecode(os.fspath(run_dir))` path).

**red** (exit 1):
```
AttributeError: 'PosixPath' object has no attribute 'endswith'
```

**restore:** reinstate the full `run_dir` normalization block with `os.fsdecode(os.fspath(run_dir))` inside `try`/`except`.

**restore receipt:** `run_dir = os.fsdecode(os.fspath(run_dir))` inside `try`/`except Exception` with `run-dir-invalid` refusal.

**green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP-B4 — non-path run_dir refusal

- **axis:** non-path `run_dir` refuses with `run-dir-invalid` instead of raising

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `probe()`): remove the `try`/`except` around `run_dir` normalization.

**red** (exit 1):
```
TypeError: expected str, bytes or os.PathLike object, not object
TypeError: expected _MalformedPathLike.__fspath__() to return str or bytes, not int
```

**restore:** reinstate `try`/`except Exception` around `os.fsdecode(os.fspath(run_dir))`.

**restore receipt:** `try:` / `run_dir = os.fsdecode(os.fspath(run_dir))` / `except Exception:` / `return _refuse(engine, "run-dir-invalid", None)`

**green** (exit 0):
```
..                                                                       [100%]
2 passed in 2.97s
```

---

## BP-B5 — bytes run_dir decode

- **axis:** bytes `run_dir` decodes to `str` before strip/endwith

**neutralization** (`plugins/superheroes/lib/conformance_probe.py`, `probe()`): replace `os.fsdecode(os.fspath(run_dir))` with `os.fspath(run_dir)` and drop the `isinstance(run_dir, str)` conjunct so bytes reach the strip loop.

**red** (exit 1):
```
TypeError: endswith first arg must be bytes or a tuple of bytes, not str
```

**restore:** reinstate `run_dir = os.fsdecode(os.fspath(run_dir))` and `if not isinstance(run_dir, str) or not run_dir:`.

**restore receipt:** `os.fsdecode(os.fspath(run_dir))` with `isinstance(run_dir, str)` guard.

**green** (exit 0):
```
.                                                                        [100%]
1 passed in 1.08s
```
