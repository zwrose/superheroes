# WO-D existing-label preservation bite-proof

## Existing-label preservation

**Guarded element:** `test_apply_creates_only_missing_labels` — axis: apply skips labels already present and creates only the missing one.

**Neutralization:** in `kind_labels.py` `ensure_kind_labels`, changed the apply loop to iterate `KIND_LABEL_NAMES` instead of `missing`:
```python
        for name in KIND_LABEL_NAMES:
```

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_kind_labels.py::test_apply_creates_only_missing_labels -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_apply_creates_only_missing_labels ____________________

    def test_apply_creates_only_missing_labels():
        # axis: apply skips labels already present and creates only the missing one
        run, calls = _make_run(
            {
                tuple(_auth_argv()): _auth_ok(),
                tuple(_list_argv()): [
                    _list_ok(["kind:machinery"]),
                    _list_ok(list(kl.KIND_LABEL_NAMES)),
                ],
                tuple(_create_argv("kind:product")): _create_ok(),
            }
        )
>       result = kl.ensure_kind_labels(REPO, apply=True, run=run)

plugins/superheroes/lib/tests/test_kind_labels.py:124: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
plugins/superheroes/lib/kind_labels.py:212: in ensure_kind_labels
    did_create, create_err = _create_label(repo, label, run)
plugins/superheroes/lib/kind_labels.py:167: in _create_label
    proc, err = _run(_gh_label_create_argv(repo, label), run)
plugins/superheroes/lib/kind_labels.py:82: in _run
    return run(argv, capture_output=True, text=True, timeout=timeout), None
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

argv = ['gh', 'label', 'create', 'kind:machinery', '--repo', 'owner/example', ...]
kwargs = {'capture_output': True, 'text': True, 'timeout': 120}
key = ('gh', 'label', 'create', 'kind:machinery', '--repo', 'owner/example', ...)

    def _run(argv, **kwargs):
        calls.append(list(argv))
        key = tuple(argv)
        if key not in queues or not queues[key]:
>           raise AssertionError("unexpected gh argv: %r" % argv)
E           AssertionError: unexpected gh argv: ['gh', 'label', 'create', 'kind:machinery', '--repo', 'owner/example', '--color', '5319E7', '--description', "Work whose subject is the development process rather than the product's behavior."]

plugins/superheroes/lib/tests/test_kind_labels.py:33: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_kind_labels.py::test_apply_creates_only_missing_labels
1 failed in 0.18s
```

**Restore:** reverted the apply loop to iterate `missing`:
```python
        for name in missing:
```

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/kind_labels.py` showed only `?? plugins/superheroes/lib/kind_labels.py` (new file, no neutralization residue).

**Green run:**
```
.                                                                        [100%]
1 passed in 0.24s
```
