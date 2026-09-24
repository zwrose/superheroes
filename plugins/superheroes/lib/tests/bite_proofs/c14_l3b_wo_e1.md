# WO-1273-L3B-E1 bite-proof — SessionStart host model

**Provenance:** cursor / composer-2.5 (implementer).

## Guarded elements

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| BP-E1a | `_write_host_model_env` always-append | model-less start must still append empty export to clear stale env | `test_host_model_stale_reset_clears_via_env_file` |
| BP-E1b | `_host_model` shape check (`_HOST_MODEL_RE`) | injection/malformed model values rejected before shell export | `test_host_model_malformed_or_injection_writes_empty[claude-opus-5; rm -rf /]` |

---

## BP-E1a — always-write on accepted source

- **axis:** every accepted SessionStart appends `SUPERHEROES_HOST_MODEL` even when empty

**neutralization** (`plugins/superheroes/hooks/session_start.py`, `_write_host_model_env`):
```python
    if not env_file or not value:  # bite-proof BP-E1a neutralization
        return
```

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273-pyc/E1 -m pytest plugins/superheroes/lib/tests/test_session_start_hook.py::test_host_model_stale_reset_clears_via_env_file -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_host_model_stale_reset_clears_via_env_file ________________

        lines = env_file.read_text(encoding="utf-8").splitlines()
>       assert lines[-1] == "export SUPERHEROES_HOST_MODEL=''"
E       assert 'export SUPER...claude-opus-5' == "export SUPER...HOST_MODEL=''"
E         
E         - export SUPERHEROES_HOST_MODEL=''
E         + export SUPERHEROES_HOST_MODEL=claude-opus-5

plugins/superheroes/lib/tests/test_session_start_hook.py:252: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_start_hook.py::test_host_model_stale_reset_clears_via_env_file
1 failed in 1.01s
```

**restore** (`plugins/superheroes/hooks/session_start.py`, `_write_host_model_env`):
```python
    if not env_file:
        return
```

**restore receipt:** restored lines quoted above; inverse removes `or not value` guard.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.66s
```

---

## BP-E1b — shape check rejects injection

- **axis:** shell-bound model values must match `^[A-Za-z0-9._:/\[\]-]{1,128}$`

**neutralization** (`plugins/superheroes/hooks/session_start.py`, `_host_model`):
```python
    # bite-proof BP-E1b neutralization: skip shape check
    return value
```
(replaces the `_HOST_MODEL_RE.match` rejection block)

**command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/wh1273-pyc/E1 -m pytest "plugins/superheroes/lib/tests/test_session_start_hook.py::test_host_model_malformed_or_injection_writes_empty[claude-opus-5; rm -rf /]" -q -p no:cacheprovider
```

**raw red** (exit 1):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_host_model_malformed_or_injection_writes_empty[claude-opus-5; rm -rf /] _

>       assert env_file.read_text(encoding="utf-8") == "export SUPERHEROES_HOST_MODEL=''\n"
E       assert "export SUPER...; rm -rf /'\n" == "export SUPER...ST_MODEL=''\n"
E         
E         - export SUPERHEROES_HOST_MODEL=''
E         + export SUPERHEROES_HOST_MODEL='claude-opus-5; rm -rf /'

plugins/superheroes/lib/tests/test_session_start_hook.py:278: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_session_start_hook.py::test_host_model_malformed_or_injection_writes_empty[claude-opus-5; rm -rf /]
1 failed in 0.48s
```

**restore** (`plugins/superheroes/hooks/session_start.py`, `_host_model`):
```python
    if not _HOST_MODEL_RE.match(value):
        return ""
    return value
```

**restore receipt:** restored lines quoted above; shape-check block reinstated.

**raw green** (exit 0):
```
.                                                                        [100%]
1 passed in 0.86s
```
