# Bite-proof record — wo/1107-rbB (one owner, fail-closed, for the skew status vocabulary)

Per `plugins/superheroes/rubric/bite-proof.md`. Three guarded elements, three neutralizations,
three reds, three restores, three greens. Each neutralization was a targeted, reversible `Edit`;
restore was the inverse `Edit` (never `git checkout`/`restore`/`reset`/`stash`).

## Element 1 — the census (`test_every_status_member_has_disposition`, issue #1107 defect 7a)

**Guarded element:** `plugins/superheroes/lib/tests/test_skew_disposition.py::test_every_status_member_has_disposition`,
which iterates `version_skew.STATUSES` and asserts every member has a `STATUS_DISPOSITIONS` entry.
**Axis:** an undispositioned `STATUSES` member fails the census by construction, so a future
enum member cannot ship silently non-degrading.

**Neutralization:** added a fourth `STATUSES` member with no `STATUS_DISPOSITIONS` entry, in
`plugins/superheroes/lib/version_skew.py`:
```python
STATUS_BITE_PROOF_PROBE = "bite-proof-probe"  # WO-rbB neutralization — removed after red capture
STATUSES = frozenset({
    STATUS_NOT_CHECKED,
    STATUS_CHECKED_DEGRADED,
    STATUS_CHECKED_CLEAN,
    STATUS_BITE_PROOF_PROBE,
})
```

**Raw red** (`/usr/bin/python3 -B -X pycache_prefix=/private/tmp/superheroes-pyc-rbb -m pytest plugins/superheroes/lib/tests/test_skew_disposition.py::test_every_status_member_has_disposition -q`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________________ test_every_status_member_has_disposition ___________________

    def test_every_status_member_has_disposition():
        for status in version_skew.STATUSES:
>           assert status in version_skew.STATUS_DISPOSITIONS, (
                "undispositioned STATUSES member: %r" % status
            )
E           AssertionError: undispositioned STATUSES member: 'bite-proof-probe'
E           assert 'bite-proof-probe' in {'checked-clean': False, 'checked-degraded': True, 'not-checked': False}
E            +  where {'checked-clean': False, 'checked-degraded': True, 'not-checked': False} = version_skew.STATUS_DISPOSITIONS

plugins/superheroes/lib/tests/test_skew_disposition.py:192: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_skew_disposition.py::test_every_status_member_has_disposition
1 failed in 0.13s
```

**Restore:** inverse `Edit` — removed the `STATUS_BITE_PROOF_PROBE` line and its `STATUSES` member,
returning `STATUSES` to its original three-member frozenset.

**Restore receipt:** `git diff` of `version_skew.py` after restore shows no trace of
`STATUS_BITE_PROOF_PROBE` or `bite-proof-probe` anywhere in the file (confirmed by re-reading the
file and by the final `git diff` used for this PR, which carries no such token).

**Raw green** (same command, post-restore):
```
.                                                                        [100%]
1 passed in 0.12s
```

## Element 2 — the fail-closed disposition (`test_appends_degradation_unknown_status_fails_closed`)

**Guarded element:** `plugins/superheroes/lib/version_skew.py::appends_degradation`, the unified
predicate (this order retired `is_degrading` and moved its fail-closed semantics onto
`appends_degradation`, replacing the old fail-open `APPENDS_DEGRADATION`-membership form).
**Axis:** unknown, undispositioned, `None`, and unhashable statuses must return `True` (append/
degrading) — the new-enum-member fall-open class named in issue #1107 defect 7a.

**Neutralization:** flipped the two fail-closed branches to return `False`:
```python
def appends_degradation(status: object) -> bool:
    try:
        known = status in STATUSES
    except TypeError:
        return False  # WO-rbB neutralization — should be True; removed after red capture
    if not known:
        return False  # WO-rbB neutralization — should be True; removed after red capture
    if status not in STATUS_DISPOSITIONS:
        return True
    return STATUS_DISPOSITIONS[status]
```

**Raw red** (`... -m pytest plugins/superheroes/lib/tests/test_skew_disposition.py::test_appends_degradation_unknown_status_fails_closed -q`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_appends_degradation_unknown_status_fails_closed _____________

    def test_appends_degradation_unknown_status_fails_closed():
>       assert version_skew.appends_degradation("future-status") is True
E       AssertionError: assert False is True
E        +  where False = <function appends_degradation at 0x1045c84c0>('future-status')
E        +    where <function appends_degradation at 0x1045c84c0> = version_skew.appends_degradation

plugins/superheroes/lib/tests/test_skew_disposition.py:204: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_skew_disposition.py::test_appends_degradation_unknown_status_fails_closed
1 failed in 0.14s
```

**Restore:** inverse `Edit` — both `return False  # WO-rbB neutralization...` lines reverted to
`return True`, removing the neutralization comments.

**Restore receipt:** post-restore `git diff` of `appends_degradation` shows only the real,
intended diff (old fail-open `APPENDS_DEGRADATION`-membership body replaced by the fail-closed
body with its `bite-axis` comment) — no `WO-rbB neutralization` residue anywhere in the file.

**Raw green** (same command, post-restore):
```
.                                                                        [100%]
1 passed in 0.16s
```

## Element 3 — the chokepoint (`test_plugin_version_skew_chokepoint_census`)

**Guarded element:** `plugins/superheroes/lib/tests/test_ssot_drift.py::test_plugin_version_skew_chokepoint_census`
(unedited, per the order — this is the failing test the order named to turn green), which fails
if any file outside `version_skew.py` names `STATUS_CHECKED_DEGRADED` or the `"checked-degraded"`
literal. **Axis:** only `version_skew.py` may own the skew status vocabulary; a bare reference
elsewhere is the violation issue #1107 defect 7 flags.

**Neutralization:** reintroduced the bare reference this order was written to remove, in
`plugins/superheroes/lib/round_driver.py`:
```python
    status = rec.get("status")
    if status in (None, ""):
        rec["status"] = version_skew.STATUS_CHECKED_DEGRADED  # WO-rbB neutralization — removed after red capture
        status = rec["status"]
```

**Raw red** (`... -m pytest plugins/superheroes/lib/tests/test_ssot_drift.py::test_plugin_version_skew_chokepoint_census -q`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_plugin_version_skew_chokepoint_census __________________

    def test_plugin_version_skew_chokepoint_census():
        """§11: only version_skew.py may reference STATUS_CHECKED_DEGRADED or checked-degraded."""
        import version_skew

        home = os.path.join(PLUGIN, "lib", "version_skew.py")
        violations = []
        for path in _plugin_python_sources_excluding_tests():
            if os.path.normpath(path) == os.path.normpath(home):
                continue
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            rel = os.path.relpath(path, PLUGIN)
            if "STATUS_CHECKED_DEGRADED" in text:
                violations.append((rel, "STATUS_CHECKED_DEGRADED"))
            if '"checked-degraded"' in text or "'checked-degraded'" in text:
                violations.append((rel, "checked-degraded literal"))
>       assert not violations, (
            "plugin-version-skew chokepoint violation outside version_skew.py: %r" % violations
        )
E       AssertionError: plugin-version-skew chokepoint violation outside version_skew.py: [('lib/round_driver.py', 'STATUS_CHECKED_DEGRADED')]
E       assert not [('lib/round_driver.py', 'STATUS_CHECKED_DEGRADED')]

plugins/superheroes/lib/tests/test_ssot_drift.py:619: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_ssot_drift.py::test_plugin_version_skew_chokepoint_census
1 failed in 0.37s
```
This reproduces exactly the failure the work order quoted as the acceptance target.

**Restore:** inverse `Edit` — the bare `version_skew.STATUS_CHECKED_DEGRADED` reference replaced
back with `version_skew.default_missing_status()`, the new chokepoint-respecting helper.

**Restore receipt:**
```
$ git diff --stat plugins/superheroes/lib/round_driver.py
 plugins/superheroes/lib/round_driver.py | 8 ++++----
 1 file changed, 4 insertions(+), 4 deletions(-)
$ git status --porcelain plugins/superheroes/lib/round_driver.py
 M plugins/superheroes/lib/round_driver.py
```
(the 4-line diff is the real, intended change: three `is_degrading` → `appends_degradation` call
sites plus the one `STATUS_CHECKED_DEGRADED` → `default_missing_status()` call site; no
`WO-rbB neutralization` residue remains anywhere in the file.)

**Raw green** (same command, post-restore):
```
.                                                                        [100%]
1 passed in 0.28s
```
