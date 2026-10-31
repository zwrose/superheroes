# Cloud C6b bite-proof: the router judges specs by where they are, not by the storage mode

> Note (2026-10-31, #2296): owner-machine paths and the name of a consuming project in this record were replaced with neutral placeholders after capture; nothing else changed.

Bite-proof record for `plugins/superheroes/lib/launch_place.py` (`_specs_outside`), detector in `plugins/superheroes/lib/tests/test_launch_place.py::test_specs_in_the_repository_whatever_the_storage_mode` (`TL`). It replaces the mode leg (G7) that `wo_a_place_call.md` recorded; that record is not edited here.

**Status.** The implementer ran the one proof (F2-1): the neutralization is a targeted Edit in the source file, the red is the single named test function run alone (no `-n auto`), the restore is the inverse Edit, and the green is the same function. Reds and greens below are the pytest output of each run; the absolute `tmp_path` prefix and the worktree path are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/private/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_launch_place.py::test_specs_in_the_repository_whatever_the_storage_mode" -q -p no:cacheprovider`.
- **Pinned condition.** `TL` builds its git repository, project store, doc policy and mode registry under `tmp_path`; the policy is `POLICY_OK` (visibility `committed`, a safe location), the Canon is in the repository, and the store holds no `spec.md`. The pin makes unobservable: the real home directory, the process environment, the network and the real wall clock.
- **Function-level node.** The node runs three worlds in one function (mode `global`, mode absent, and a registry whose `schemaVersion` is 99); each is built under its own `_sub(tmp_path, ...)`, and the first world that disagrees fails the function.

## Declared guarded-element set

F2-1 the storage mode does not decide where the specs are (axis: removed condition).

## Per-element receipts

### F2-1: the storage mode does not decide; axis: removed condition

- **Neutralization applied.** In `launch_place._specs_outside`, after the `location` check and before the `docs = ...` line, these two lines were inserted (the condition this change deleted):
  `        if mode_registry.resolve(cwd, root, persist_backfill=False)["mode"] != mode_registry.IN_REPO:` and `            return True`.
- **Node.** `TL::test_specs_in_the_repository_whatever_the_storage_mode`
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_specs_in_the_repository_whatever_the_storage_mode ____________

tmp_path = PosixPath('/private/tmp/claude-501/pytest-of-zwrose/pytest-1483/test_specs_in_the_repository_w0')

    def test_specs_in_the_repository_whatever_the_storage_mode(tmp_path):
        # axis: the storage mode does not decide where the specs are; a global, absent or too-new mode
        # with a committed policy and no store spec is in the repository
        worlds = (
            dict(mode=mode_registry.GLOBAL),
            dict(mode=None),
            dict(mode=None,
                 registry_text=json.dumps({"schemaVersion": 99, "storageMode": "in-repo"})),
        )
        for index, world in enumerate(worlds):
            repo, store = _world(_sub(tmp_path, str(index)), **world)
            before = _tree(store)
>           assert LP.machine_needs(repo, {}, root=store) == [], world
E           AssertionError: {'mode': 'global'}
E           assert ["this project's specs"] == []
E             
E             Left contains one more item: "this project's specs"
E             Use -v to get more diff

/path/to/home/.superheroes-worktrees/superheroes/issue-1777-b0308f0d510d1b2a/plugins/superheroes/lib/tests/test_launch_place.py:454: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_place.py::test_specs_in_the_repository_whatever_the_storage_mode
1 failed in 1.27s
```

- **Restore.** The inverse Edit removed the two inserted lines. Restore receipt: `grep -n "mode_registry" plugins/superheroes/lib/launch_place.py` printed only `20:import mode_registry  # noqa: E402` and `129:        docs = os.path.join(mode_registry.project_store_dir(cwd, root), "docs")`, with no `resolve` line; the restored source at `launch_place.py:129` reads `        docs = os.path.join(mode_registry.project_store_dir(cwd, root), "docs")`, directly after the `location` check's `            return True`.
- **Green.**

```
.                                                                        [100%]
1 passed in 2.67s
```
