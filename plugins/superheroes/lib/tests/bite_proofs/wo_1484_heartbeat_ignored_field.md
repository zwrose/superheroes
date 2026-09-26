# Bite-proof record — WO-A2 (#1484) heartbeat ignored field + retired-promise census

**Guarded-element set (declared in the work order):** (1) `_validate_record` ignores legacy `staleAfterSeconds` on load — detector `test_old_record_stale_after_field_is_ignored`; (2) the plugin census skips non-text artifacts and does not false-positive on `__pycache__` — detector `test_no_reader_or_builder_keeps_the_retired_promise`.

**Command:** each run used the exact node id below, never `-k`:

```
scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc-woA2 -m pytest <node id> -q
```

## 1 — legacy `staleAfterSeconds` is ignored on read (non-int case)

- **Guarded element:** `plugins/superheroes/lib/heartbeat.py` `_validate_record`, axis: a non-int `staleAfterSeconds` on an otherwise-valid on-disk record must not invalidate classification.
- **Neutralization** (before `return True, None` in `_validate_record`):

```
     if note is not None:
         if not isinstance(note, str) or len(note) > _NOTE_MAX_LEN:
             return False, "heartbeat-note-invalid"
+    if "staleAfterSeconds" in record and not isinstance(record["staleAfterSeconds"], int):
+        return False, "heartbeat-stale-after-invalid"
     return True, None
```

- **Node:** `plugins/superheroes/lib/tests/test_heartbeat.py::test_old_record_stale_after_field_is_ignored[x]`
- **Raw red** (exit 1):

```
>       assert result["class"] == "nonterminal"
E       AssertionError: assert 'unknown' == 'nonterminal'
E         
E         - nonterminal
E         + unknown

FAILED plugins/superheroes/lib/tests/test_heartbeat.py::test_old_record_stale_after_field_is_ignored[x]
1 failed in 25.28s
```

- **Restore:** remove the two-line `staleAfterSeconds` type check (inverse of neutralization). Restored tail of `_validate_record`:

```
    if note is not None:
        if not isinstance(note, str) or len(note) > _NOTE_MAX_LEN:
            return False, "heartbeat-note-invalid"
    return True, None
```

- **Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 2.86s
```

## 2 — retired-promise census scans text sources only

- **Guarded element:** `test_no_reader_or_builder_keeps_the_retired_promise`, axis: a retired token in a shipped `.py` reader surface is reported (not masked by binary/`__pycache__` noise).
- **Neutralization** (append to `plugins/superheroes/lib/wave_watch.py`):

```
 if __name__ == "__main__":
     raise SystemExit(main(sys.argv))
+# staleAfterSeconds
```

- **Node:** `plugins/superheroes/lib/tests/test_heartbeat_docs_drift.py::test_no_reader_or_builder_keeps_the_retired_promise`
- **Raw red** (exit 1):

```
>       assert not offenders, "retired promise token(s) found:\n" + "\n".join(sorted(offenders))
E       AssertionError: retired promise token(s) found:
E         plugins/superheroes/lib/wave_watch.py:2243:staleAfterSeconds
E       assert not ['plugins/superheroes/lib/wave_watch.py:2243:staleAfterSeconds']

FAILED plugins/superheroes/lib/tests/test_heartbeat_docs_drift.py::test_no_reader_or_builder_keeps_the_retired_promise
1 failed in 0.38s
```

- **Restore:** delete the `# staleAfterSeconds` comment line from the end of `wave_watch.py`. Restored lines:

```
if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- **Raw green** (exit 0):

```
.                                                                        [100%]
1 passed in 0.40s
```
