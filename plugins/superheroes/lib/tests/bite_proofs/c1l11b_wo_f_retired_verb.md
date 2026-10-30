# C1-L11b (WO-F, issue #2266) bite-proof — a retired round-driver verb cannot stay auto-approved

**Provenance:** implementer WO-F / `hooks/plugin_scripts_allow.py`, `lib/tests/test_plugin_scripts_allow_hook.py`

Declared guarded element (from the order): the census test `test_every_approved_driver_verb_is_a_parser_subcommand`, guarding the invariant that every verb in `ROUND_DRIVER_VERBS` is a subcommand of `round_driver.py`'s own argparse parser. One element, one neutralization, one red. The neutralization was a targeted edit and was restored with the inverse edit; no `git checkout`, `restore`, `reset` or `stash` was used. Run from `/home/user/wt-2266-f` under `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider`. The captures are the runner's whole output apart from the `UV_NATIVE_TLS` deprecation warning line, which is left out; nothing is redacted (no secrets, tokens or URLs appear).

| ID | Guarded element | Axis | Proving test |
|---|---|---|---|
| E1 | `plugin_scripts_allow.py` `ROUND_DRIVER_VERBS`, the verb set the hook auto-approves | every approved verb is a subcommand the driver's parser accepts | `test_every_approved_driver_verb_is_a_parser_subcommand` |

Not separately neutralized (the unproven part of this record): the non-empty-and-contains-`next` guard on the derived subcommand set (fail-closed edge E2). Its failure mode is "no subparsers action found", which needs a change to `round_driver.py` (WO-D's file) to produce; it was not neutralized.

---

## E1 — the approved-verb census

**axis:** every verb in `hook.ROUND_DRIVER_VERBS` is among the `choices` of the subparsers action of `round_driver.build_parser()`.

**neutralization** (`hooks/plugin_scripts_allow.py`, `ROUND_DRIVER_VERBS`: the retired verb `correct-fixer-refusals` put back):
```python
-    "next", "submit", "record-result", "record-missing", "advance",
+    "next", "submit", "record-result", "record-missing", "advance", "correct-fixer-refusals",
```

**raw red:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest -q -p no:cacheprovider plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py -k test_every_approved_driver_verb_is_a_parser_subcommand`
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_every_approved_driver_verb_is_a_parser_subcommand ____________

    def test_every_approved_driver_verb_is_a_parser_subcommand():
        # axis: a verb the driver retired cannot stay auto-approved — every approved verb is a subcommand
        # of the driver's own argparse parser
        known = _driver_subcommands()
        assert known and "next" in known, sorted(known)
        assert hook.ROUND_DRIVER_VERBS, "the hook approves no driver verb"
        unknown = sorted(hook.ROUND_DRIVER_VERBS - known)
>       assert not unknown, "approved but not a round_driver subcommand: %s" % unknown
E       AssertionError: approved but not a round_driver subcommand: ['correct-fixer-refusals']
E       assert not ['correct-fixer-refusals']

/home/user/wt-2266-f/plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_plugin_scripts_allow_hook.py::test_every_approved_driver_verb_is_a_parser_subcommand
1 failed, 172 deselected in 0.34s
```

**restore:** the inverse edit (`, "correct-fixer-refusals"` removed from the `ROUND_DRIVER_VERBS` tuple).

**restore receipt:** a search of `plugin_scripts_allow.py` for `"advance"` finds lines 48-49, which read again:
```python
    "next", "submit", "record-result", "record-missing", "advance",
    "attest", "checkpoint",
```

**raw green:** same command
```
.                                                                        [100%]
1 passed, 171 deselected in 0.33s
```
