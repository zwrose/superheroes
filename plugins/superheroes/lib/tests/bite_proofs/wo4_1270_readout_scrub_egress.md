# WO-4 (#1270) bite-proof — `build_readout` scrub egress chokepoint

**Provenance:** cursor composer-2.5 / dispatch-write

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-WO4-1 | `pr_url` | scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission | `test_build_readout_scrubs_pr_url_secret` |
| BP-WO4-2 | `dev_url` | scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission | `test_build_readout_scrubs_dev_url_secret` |
| BP-WO4-3 | `ci_status` | scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission | `test_build_readout_scrubs_ci_status_secret` |
| BP-WO4-4 | `smoke[]` | scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission | `test_build_readout_scrubs_smoke_item_secret` |
| BP-WO4-5 | `permissionDenials[].step` | scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission | `test_build_readout_scrubs_permission_denial_step_secret` |

---

## BP-WO4-1 — `pr_url` egress

- **axis:** scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission

**neutralization** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
    "pr_url",
})
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_pr_url_secret -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_build_readout_scrubs_pr_url_secret ____________________

    def test_build_readout_scrubs_pr_url_secret():
        # Pattern 3: key=value query/form params (token=...)
        secret = "supersecretvalue123"
        body = readout.build_readout({
            "pr_url": "http://example.com/pr/1?token=%s" % secret,
            "ci_status": "green",
        })
>       assert secret not in body
E       AssertionError: assert 'supersecretvalue123' not in '## Workhors...ver merges._'
E         
E         'supersecretvalue123' is contained here:
E           r/1?token=supersecretvalue123
E           - **CI:** green
E           
E           _Merge is yours — Workhorse never merges._

plugins/superheroes/lib/tests/test_readout.py:66: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_pr_url_secret
1 failed in 0.10s
```

**restore:** remove `"pr_url",` from `_READOUT_SCRUB_EXEMPT`.

**restore receipt** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.11s
```

---

## BP-WO4-2 — `dev_url` egress

- **axis:** scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission

**neutralization** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
    "dev_url",
})
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_dev_url_secret -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_build_readout_scrubs_dev_url_secret ___________________

    def test_build_readout_scrubs_dev_url_secret():
        # URI userinfo credentials: scheme://user:pass@host
        secret = "hunter2pass"
        body = readout.build_readout({
            "dev_url": "https://user:%s@dev.example.com" % secret,
            "ci_status": "green",
        })
>       assert secret not in body
E       AssertionError: assert 'hunter2pass' not in '## Workhors...ver merges._'
E         
E         'hunter2pass' is contained here:
E           ps://user:hunter2pass@dev.example.com
E         ?           +++++++++++
E           - **CI:** green
E           
E           _Merge is yours — Workhorse never merges._

plugins/superheroes/lib/tests/test_readout.py:77: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_dev_url_secret
1 failed in 0.09s
```

**restore:** remove `"dev_url",` from `_READOUT_SCRUB_EXEMPT`.

**restore receipt** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.12s
```

---

## BP-WO4-3 — `ci_status` egress

- **axis:** scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission

**neutralization** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
    "ci_status",
})
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_ci_status_secret -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_build_readout_scrubs_ci_status_secret __________________

    def test_build_readout_scrubs_ci_status_secret():
        # Pattern 1b: mid-line x-api-key (key: value form)
        secret = "sk-live-abc123def456"
        body = readout.build_readout({
            "ci_status": "x-api-key: %s" % secret,
        })
>       assert secret not in body
E       AssertionError: assert 'sk-live-abc123def456' not in '## Workhors...ver merges._'
E         
E         'sk-live-abc123def456' is contained here:
E           -api-key: sk-live-abc123def456
E           
E           _Merge is yours — Workhorse never merges._

plugins/superheroes/lib/tests/test_readout.py:87: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_ci_status_secret
1 failed in 0.10s
```

**restore:** remove `"ci_status",` from `_READOUT_SCRUB_EXEMPT`.

**restore receipt** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```

---

## BP-WO4-4 — `smoke[]` egress

- **axis:** scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission

**neutralization** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
    "smoke[]",
})
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_smoke_item_secret -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_build_readout_scrubs_smoke_item_secret __________________

    def test_build_readout_scrubs_smoke_item_secret():
        # Pattern 2: Bearer tokens
        secret = "abcdef0123456789"
        body = readout.build_readout({
            "ci_status": "green",
            "smoke": ["verify Authorization: Bearer %s" % secret],
        })
>       assert secret not in body
E       AssertionError: assert 'abcdef0123456789' not in '## Workhors...ver merges._'
E         
E         'abcdef0123456789' is contained here:
E           n: Bearer abcdef0123456789
E           
E           _Merge is yours — Workhorse never merges._

plugins/superheroes/lib/tests/test_readout.py:98: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_smoke_item_secret
1 failed in 0.11s
```

**restore:** remove `"smoke[]",` from `_READOUT_SCRUB_EXEMPT`.

**restore receipt** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.11s
```

---

## BP-WO4-5 — `permissionDenials[].step` egress

- **axis:** scrub-by-default — an unlisted field is scrubbed, so a new field cannot leak by omission

**neutralization** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
    "permissionDenials[].step",
})
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_permission_denial_step_secret -q -p no:randomly
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_build_readout_scrubs_permission_denial_step_secret ____________

    def test_build_readout_scrubs_permission_denial_step_secret():
        # Pattern 1b: mid-line x-api-key (key: value form)
        secret = "plantedsecret123"
        body = readout.build_readout({
            "ci_status": "green",
            "permissionDenials": [{"step": "deploy x-api-key: %s" % secret, "detail": ""}],
        })
>       assert secret not in body
E       AssertionError: assert 'plantedsecret123' not in '## Workhors...ver merges._'
E         
E         'plantedsecret123' is contained here:
E           -api-key: plantedsecret123**
E           
E           _Merge is yours — Workhorse never merges._

plugins/superheroes/lib/tests/test_readout.py:109: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_readout.py::test_build_readout_scrubs_permission_denial_step_secret
1 failed in 0.09s
```

**restore:** remove `"permissionDenials[].step",` from `_READOUT_SCRUB_EXEMPT`.

**restore receipt** (`plugins/superheroes/lib/readout.py`, `_READOUT_SCRUB_EXEMPT`):
```python
_READOUT_SCRUB_EXEMPT = frozenset({
    "courierRetries.retried",  # Python int rendered with %d; cannot carry a string.
})
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.09s
```
