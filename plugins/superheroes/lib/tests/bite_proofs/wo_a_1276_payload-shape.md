# Payload-shape bite-proof

## Payload-shape

**Guarded element:** `core_md.py:2256` — `isinstance(mapping, dict)` check in the `write-project-config` CLI verb — axis: refuse a JSON value that is not an object.

**Neutralization:** replaced the refusal with coercion to an empty mapping:

```python
                if not isinstance(mapping, dict):
                    mapping = {}
```

**Command:**

```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_cli_write_project_config_payload_shape_axis -q
```

**Red run:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_bite_cli_write_project_config_payload_shape_axis _____________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/com.apple.shortcuts.mac-helper/pytest-of-zwrose/pytest-159/test_bite_cli_write_project_co0')
capsys = <_pytest.capture.CaptureFixture object at 0x10640cb50>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x105eaf7f0>

    def test_bite_cli_write_project_config_payload_shape_axis(tmp_path, capsys, monkeypatch):
        """axis: payload-shape — CLI must refuse a JSON value that is not an object."""
        repo, store = _setup_repo(tmp_path)
        monkeypatch.setattr("sys.stdin", io.StringIO('"string"'))
        rc = CM.main(["write-project-config", "--cwd", repo, "--root", store])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
>       assert out["action"] == "refused"
E       AssertionError: assert 'noop' == 'refused'
E         
E         - refused
E         + noop

plugins/superheroes/lib/tests/test_core_md_project_config.py:500: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_core_md_project_config.py::test_bite_cli_write_project_config_payload_shape_axis
1 failed in 8.56s
```

**Restore:** restored the original refusal:

```python
                if not isinstance(mapping, dict):
                    out = {"action": "refused", "reason": PROJECT_CONFIG_REASON_NOT_A_MAPPING}
                    sys.stdout.write(json.dumps(out, indent=2) + "\n")
                    return 0
```

**Restore receipt:** restored lines quoted above; `git status --porcelain plugins/superheroes/lib/core_md.py` showed no output.

**Green run:**

```
.                                                                        [100%]
1 passed in 5.45s
```
