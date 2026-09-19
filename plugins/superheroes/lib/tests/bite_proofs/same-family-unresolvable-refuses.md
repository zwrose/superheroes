# same-family-unresolvable-refuses bite-proof

## unresolvable-maker-family-refusal

**Guarded element:** `check_same_family_seat` — axis: an unresolvable maker family refuses whether or not any same-family degradation was declared.

**Neutralization:** replaced the unresolvable-family refusal with `return None` so the control passes when the maker family cannot be resolved.

**Command:**
```
/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-p3a -m pytest plugins/superheroes/lib/tests/test_round_certification.py::test_bite_same_family_unresolvable_refuses -q
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_bite_same_family_unresolvable_refuses __________________

tmp_path = PosixPath('/private/var/folders/dy/s097fm_n7tldcbdtthd1zgqh0000gn/T/pytest-of-zwrose/pytest-1339/test_bite_same_family_unresolv0')

    def test_bite_same_family_unresolvable_refuses(tmp_path):
        unknown_vendor = "not-a-registered-vendor"
        session_dir = write_certifiable_session(
            tmp_path,
            state={
                "config": {"fixerVendor": unknown_vendor},
                "seatMapReceipts": [
                    {
                        "round": "1",
                        "map": {
                            "seats": {
                                "code-reviewer": {"vendor": "codex", "model": "gpt-5.6-sol"},
                            },
                        },
                    }
                ],
            },
            envelopes=[{"seat": "code-reviewer", "payloadSha256": "abc123"}],
        )
        ctx, _ = RC._load_context(session_dir)
        refusal = RC.check_same_family_seat(ctx)
>       assert refusal is not None
E       assert None is not None

plugins/superheroes/lib/tests/test_round_certification.py:910: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_round_certification.py::test_bite_same_family_unresolvable_refuses
1 failed in 0.11s
```

**Restore:** restored the unresolvable-family refusal:
```python
    if not author:
        cfg = state.get("config") or {}
        vendor = cfg.get("fixerVendor")
        return _refusal(
            "unfetched-findings",
            _seat_map_artifact(state),
            "maker family could not be resolved for fixerVendor %r" % (vendor,),
        )
```

**Restore receipt:** restored lines quoted above in `check_same_family_seat`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.09s
```
