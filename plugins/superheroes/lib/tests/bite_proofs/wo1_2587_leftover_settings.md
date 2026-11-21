# WO-1 (#2587) bite-proofs - the leftover-settings detector

Detector file: `plugins/superheroes/lib/tests/test_leftover_settings_2587.py`; guarded file:
`plugins/superheroes/lib/leftover_settings.py`. Each element below was neutralized by a targeted edit made
with the edit tool and restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`).
Every command ran from the worktree root as
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo1-2587-pyc -m pytest <node> -q -p no:randomly`.
Redaction: none needed (no secrets); the one line `warning: The UV_NATIVE_TLS environment variable is
deprecated ...` that the runner prints first is left out of each capture, and the pytest temp paths are kept
as printed. Every capture is far under the 32 KiB ceiling.

The restore receipt of each entry is the restored line quoted back from the file after the inverse edit (read
with the search tool over `leftover_settings.py` after all seven restores: lines 68, 96, 97, 101, 108, 111,
286 and 343 of the restored file are quoted in each entry).

Disclosure: for G1 only, the inverse edit and the green run were issued in the same tool block; the green run
passed, which it could not have done with the neutralization still in place.

Guarded-element set (declared by the order): G1 to G7, one neutralization and one red each, no grouping.

## G1 - the realpath alias check

**Guarded element:** `_gather`, `os.path.realpath(slot) == real_reads` (`leftover_settings.py:108`) - axis: a copy
that is the same file on disk as the slot read (a link either way, or a linked directory) is never listed.

**Neutralization:** `if os.path.realpath(slot) == real_reads:` became `if False and os.path.realpath(slot) == real_reads:`.

**Node:** `test_leftover_settings_2587.py::test_alias_core_symlink_is_not_listed`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_alias_core_symlink_is_not_listed _____________________

w = <test_leftover_settings_2587.W object at 0x7f361242f4d0>

    def test_alias_core_symlink_is_not_listed(w):
        # axis: a global core.md that is a link to the in-repo core.md is one file, never a leftover; retire leaves it readable
        w.register(mr.GLOBAL)
        in_core = _put(w.d_in("core.md"), _CORE)
        os.makedirs(os.path.dirname(w.d_gl("core.md")), exist_ok=True)
        os.symlink(in_core, w.d_gl("core.md"))
        _put(w.d_in("guardian.md"), "stale guardian\n")
        _put(w.d_gl("guardian.md"), "guardian\n")
        result = w.find()
>       assert [f["path"] for f in result["files"]] == [w.d_in("guardian.md")]
E       AssertionError: assert ['/tmp/claude.../guardian.md'] == ['/tmp/claude.../guardian.md']
E         
E         At index 0 diff: '/tmp/claude-0/pytest-of-root/pytest-1/test_alias_core_symlink_is_not0/repo/.claude/superheroes/core.md' != '/tmp/claude-0/pytest-of-root/pytest-1/test_alias_core_symlink_is_not0/repo/.claude/superheroes/guardian.md'
E         Left contains one more item: '/tmp/claude-0/pytest-of-root/pytest-1/test_alias_core_symlink_is_not0/repo/.claude/superheroes/guardian.md'
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:260: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_alias_core_symlink_is_not_listed
1 failed in 0.43s
```

**Restore:** inverse edit, `if False and os.path.realpath(slot) == real_reads:` back to `if os.path.realpath(slot) == real_reads:`.

**Restore receipt:** `leftover_settings.py:108` reads `        if os.path.realpath(slot) == real_reads:`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
```

## G2 - the alignment gate

**Guarded element:** `_gather`, `if not aligned: return []` (`leftover_settings.py:96`) - axis: the co-located families
(every other `*.md`, and test-pilot) list nothing when the read core.md sits on the other side.

**Neutralization:** `if not aligned:` became `if False and not aligned:`.

**Node:** `test_leftover_settings_2587.py::test_alignment_core_on_the_other_side_lists_nothing`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_alignment_core_on_the_other_side_lists_nothing ______________

w = <test_leftover_settings_2587.W object at 0x7f85a5856240>

    def test_alignment_core_on_the_other_side_lists_nothing(w):
        # axis: with the only core.md on the other side, the co-located families list nothing
        w.register(mr.GLOBAL)
        _put(w.d_in("core.md"), _CORE)
        _put(w.d_in("guardian.md"), "in-repo guardian\n")
        _put(w.d_gl("guardian.md"), "global guardian\n")
        _put(w.d_in("test-pilot.md"), _PILOT)
        _put(w.d_gl("test-pilot.md"), _PILOT)
>       assert w.find()["files"] == []
E       AssertionError: assert [{'path': '/t...st-pilot.md'}] == []
E         
E         Left contains 2 more items, first extra item: {'path': '/tmp/claude-0/pytest-of-root/pytest-3/test_alignment_core_on_the_oth0/repo/.claude/superheroes/guardian.md',...pytest-of-root/pytest-3/test_alignment_core_on_the_oth0/_store_isolation/projects/238a7b644f5fb344/config/guardian.md'}
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:288: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_alignment_core_on_the_other_side_lists_nothing
1 failed in 0.84s
```

**Restore:** inverse edit, `if False and not aligned:` back to `if not aligned:`.

**Restore receipt:** `leftover_settings.py:96-97` read `    if not aligned:` / `        return []`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

## G3 - the populated-core gate

**Guarded element:** `_gather`, `reads == layer and populated()` (`leftover_settings.py:111`) - axis: a legacy profile is
listed only while the layer is what is read and the core that replaces it is populated.

**Neutralization:** `not (reads == layer and populated())` became `not (reads == layer and True)`.

**Node:** `test_leftover_settings_2587.py::test_legacy_profile_needs_a_populated_core[no-core]` (the `empty-core`
case shares this neutralization and failure mode; only the `no-core` node was run red).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_legacy_profile_needs_a_populated_core[no-core] ______________

w = <test_leftover_settings_2587.W object at 0x7faeb933ade0>, core = None
listed = False

    @pytest.mark.parametrize("core,listed", [
        pytest.param(None, False, id="no-core"),
        pytest.param(_EMPTY_CORE, False, id="empty-core"),
        pytest.param(_CORE, True, id="populated-core"),
    ])
    def test_legacy_profile_needs_a_populated_core(w, core, listed):
        # axis: the legacy review profile is listed only when the core that replaces it is populated
        w.register(mr.GLOBAL)
        _put(w.d_gl("review-crew.md"), "## Focus hints\n- global\n")
        legacy = _put(w.inrepo("review-profile.md"), "## Threat model\nold\n")
        if core is not None:
            _put(w.d_gl("core.md"), core)
>       assert w.paths() == ([legacy] if listed else [])
E       AssertionError: assert ['/tmp/claude...w-profile.md'] == []
E         
E         Left contains one more item: '/tmp/claude-0/pytest-of-root/pytest-5/test_legacy_profile_needs_a_po0/repo/.claude/review-profile.md'
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:305: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_legacy_profile_needs_a_populated_core[no-core]
1 failed in 0.45s
```

**Restore:** inverse edit, `and True)` back to `and populated())`.

**Restore receipt:** `leftover_settings.py:111` reads `        if slot in legacy and not (reads == layer and populated()):`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.28s
```

## G4 - a family with no present picked slot lists nothing

**Guarded element:** `_gather`, the `if reads is None: return []` branch (`leftover_settings.py:99-101`) - axis: the only
copy is never retired.

**Neutralization:** the branch's `return []` became `reads = picked[0]` (the missing picked slot is then treated as the
slot read, so every present unpicked copy is listed).

**Node:** `test_leftover_settings_2587.py::test_only_copy_is_never_listed`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________________ test_only_copy_is_never_listed ________________________

w = <test_leftover_settings_2587.W object at 0x7f14de96dc40>

    def test_only_copy_is_never_listed(w):
        # axis: a family with no copy in the picked slot lists nothing, so the only copy is never retired
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        _put(w.d_in("review-crew.md"), "## Focus hints\n- only copy\n")
        _put(w.d_in("test-pilot.md"), _PILOT)
        _put(w.inrepo("review-profile.md"), "old\n")
        _put(w.inrepo("review-decisions.json"), "{}\n")
        _put(w.d_in("guardian.md"), "guardian\n")
>       assert w.find()["files"] == []
E       AssertionError: assert [{'path': '/t...st-pilot.md'}] == []
E         
E         Left contains 5 more items, first extra item: {'path': '/tmp/claude-0/pytest-of-root/pytest-7/test_only_copy_is_never_listed0/repo/.claude/review-decisions.json', '...root/pytest-7/test_only_copy_is_never_listed0/_store_isolation/projects/238a7b644f5fb344/config/review-decisions.json'}
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:246: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_only_copy_is_never_listed
1 failed in 0.42s
```

**Restore:** inverse edit, `reads = picked[0]` back to `return []`.

**Restore receipt:** `leftover_settings.py:99-101` read `    if reads is None:` / the axis comment / `        return []`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.33s
```

## G5 - `lexists` (not `exists`) for presence

**Guarded element:** `_present` (`leftover_settings.py:68`) - axis: a dangling link counts as present, so a broken
picked copy is still the slot read and the stale copy is listed. (The `directory` case of the same test passes
under `exists` too, since a directory exists; the `dangling-link` case is the one that bites.)

**Neutralization:** `return os.path.lexists(path)` became `return os.path.exists(path)`.

**Node:** `test_leftover_settings_2587.py::test_broken_picked_copy_still_is_the_read_slot[dangling-link]`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_broken_picked_copy_still_is_the_read_slot[dangling-link] _________

w = <test_leftover_settings_2587.W object at 0x7fdab46ea630>
shape = 'dangling-link'

    @pytest.mark.parametrize("shape", ["directory", "dangling-link"])
    def test_broken_picked_copy_still_is_the_read_slot(w, shape):
        # axis: a picked copy that is a directory or a dangling link is present, so it is the slot read and the stale copy is listed
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        picked = w.d_gl("review-crew.md")
        if shape == "directory":
            os.makedirs(picked)
        else:
            os.symlink(str(w.tmp / "no-such-layer.md"), picked)
        stale = _put(w.d_in("review-crew.md"), "## Focus hints\n- stale\n")
        result = w.find()
>       assert [f["path"] for f in result["files"]] == [stale]
E       AssertionError: assert [] == ['/tmp/claude...view-crew.md']
E         
E         Right contains one more item: '/tmp/claude-0/pytest-of-root/pytest-9/test_broken_picked_copy_still_0/repo/.claude/superheroes/review-crew.md'
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:333: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_broken_picked_copy_still_is_the_read_slot[dangling-link]
1 failed in 0.44s
```

**Restore:** inverse edit, `os.path.exists(path)` back to `os.path.lexists(path)`.

**Restore receipt:** `leftover_settings.py:68` reads `    return os.path.lexists(path)`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.31s
```

## G6 - the digest check in `retire`

**Guarded element:** `retire`, `if current["digest"] != list_digest:` (`leftover_settings.py:286`) - axis: the files moved are
the files the owner saw, so a changed list moves nothing.

**Neutralization:** `if current["digest"] != list_digest:` became `if False and current["digest"] != list_digest:`.

**Node:** `test_leftover_settings_2587.py::test_retire_with_a_stale_digest_moves_nothing`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_retire_with_a_stale_digest_moves_nothing _________________

w = <test_leftover_settings_2587.W object at 0x7f15eafe26c0>

    def test_retire_with_a_stale_digest_moves_nothing(w):
        # axis: a digest from before a new leftover appeared moves nothing and returns the new list
        left = _everything_left_behind(w)
        stale_digest = w.find()["digest"]
        newcomer = _put(w.d_in("guardian.md"), "new in-repo guardian\n")
        _put(w.d_gl("guardian.md"), "guardian\n")
        done = w.retire(stale_digest)
>       assert done["status"] == "blocked" and done["reason"] == "list-changed"
E       AssertionError: assert ('retired' == 'blocked'
E         
E         - blocked
E         + retired)

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:427: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_retire_with_a_stale_digest_moves_nothing
1 failed in 0.47s
```

**Restore:** inverse edit, `if False and current["digest"] != list_digest:` back to `if current["digest"] != list_digest:`.

**Restore receipt:** `leftover_settings.py:286` reads `            if current["digest"] != list_digest:`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.39s
```

## G7 - `restore`'s occupancy check

**Guarded element:** `restore`, `if _present(src):` (`leftover_settings.py:343`) - axis: restore never overwrites a
present path.

**Neutralization:** `if _present(src):` became `if False and _present(src):`.

**Node:** `test_leftover_settings_2587.py::test_retire_moves_exactly_the_listed_files_and_restore_puts_them_back`

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_retire_moves_exactly_the_listed_files_and_restore_puts_them_back _____

w = <test_leftover_settings_2587.W object at 0x7f77ee86a810>

    def test_retire_moves_exactly_the_listed_files_and_restore_puts_them_back(w):
        # axis: retire moves the listed files into a dated folder, leaves the selected copies untouched, and restore undoes it
        left = _everything_left_behind(w)
        before = {p: _read(p) for p in left}
        selected_before = {p: _read(p) for p in _selected(w)}
        listed = w.find()
        done = w.retire(listed["digest"])
        assert done["status"] == "retired"
        backup = os.path.join(w.store_dir(), "leftover-backups", STAMP)
        assert done["backup"] == backup
        assert done["manifest"] == os.path.join(backup, "retired.json")
        assert [m["from"] for m in done["moved"]] == left
        assert backup in done["undo"] and "restore" in done["undo"]
        for index, move in enumerate(done["moved"], start=1):
            assert move["to"] == os.path.join(backup, "%02d-%s" % (index, os.path.basename(move["from"])))
            assert not os.path.lexists(move["from"])
            assert _read(move["to"]) == before[move["from"]]
        for path, data in selected_before.items():
            assert _read(path) == data
        with open(done["manifest"], encoding="utf-8") as fh:
            manifest = json.load(fh)
        assert manifest["schema"] == 1 and manifest["mode"] == mr.GLOBAL
        assert [(e["from"], e["to"]) for e in manifest["entries"]] == [(m["from"], m["to"]) for m in done["moved"]]
        assert {e["family"] for e in manifest["entries"]} == {
            "core", "review-crew", "test-pilot", "decisions"}
        assert w.find()["files"] == []
        assert w.retire(listed["digest"])["reason"] == "nothing-to-retire"
    
        # an occupied slot is skipped, never overwritten; the rest come back byte for byte
        occupied = w.d_in("core.md")
        _put(occupied, "the owner wrote this meanwhile\n")
        back = ls.restore(w.cwd, backup, root=w.root)
        assert back["status"] == "restored"
>       assert back["skipped"] == [{"from": occupied, "why": "occupied"}]
E       AssertionError: assert [] == [{'from': '/t...: 'occupied'}]
E         
E         Right contains one more item: {'from': '/tmp/claude-0/pytest-of-root/pytest-13/test_retire_moves_exactly_the_0/repo/.claude/superheroes/core.md', 'why': 'occupied'}
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:376: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_retire_moves_exactly_the_listed_files_and_restore_puts_them_back
1 failed in 0.48s
```

**Restore:** inverse edit, `if False and _present(src):` back to `if _present(src):`.

**Restore receipt:** `leftover_settings.py:343` reads `                if _present(src):`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.41s
```

# WO-1b additions (rework of WO-1): G8 and G9

Guarded-element set (declared by WO-1b): G8 and G9, one neutralization and one red each, no grouping. Same method as
above: targeted edit with the edit tool, inverse edit to restore, no `git checkout`, `restore`, `reset` or `stash`.
Commands ran from the worktree root as
`scripts/pinned-python -B -X pycache_prefix=/tmp/wo1b-2587-pyc -m pytest <node> -q -p no:randomly`. Redaction: none
needed; the `UV_NATIVE_TLS` warning line the runner prints first is left out of each capture. Line numbers in G8 and
G9 are those of the file as of WO-1b (the G1 to G7 line numbers above predate this rework).

## G8 - the legacy-read gate

**Guarded element:** `_gather`, `if layer_only and reads != layer: return []` (`leftover_settings.py:107`) - axis: a
review-crew or test-pilot family whose read slot is the recorded side's legacy profile (not its unified layer) lists
nothing, because readers do not let a legacy profile supersede the other side's layer.

**Neutralization:** `if layer_only and reads != layer:` became `if False and layer_only and reads != layer:`.

**Node:** `test_leftover_settings_2587.py::test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_review_crew`
(test 1 of the order; the test-pilot and in-repo-mirror nodes share this neutralization and failure mode and were not
run red separately).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_review_crew ___

w = <test_leftover_settings_2587.W object at 0x7f2a975ca720>

    def test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_review_crew(w):
        # axis: a review-crew family whose read slot is the recorded legacy profile lists nothing, since the reader still reads the other side's layer
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        _put(os.path.join(w.entry(w.rr), "review-profile.md"), "## Threat model\nread\n")
        in_layer = _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
        assert _dispatch_layer(w) == in_layer
>       assert w.paths() == []
E       AssertionError: assert ['/tmp/claude...view-crew.md'] == []
E         
E         Left contains one more item: '/tmp/claude-0/pytest-of-root/pytest-18/test_legacy_read_with_a_layer_0/repo/.claude/superheroes/review-crew.md'
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:332: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_review_crew
1 failed in 1.57s
```
(The red is for the stated reason: the in-repo layer, which `calibration_resolve.resolve` reads, is listed for
retirement. The preceding `_dispatch_layer(w) == in_layer` assertion passed.)

**Restore:** inverse edit, `if False and layer_only and reads != layer:` back to `if layer_only and reads != layer:`.

**Restore receipt:** `leftover_settings.py:107` reads `    if layer_only and reads != layer:`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.80s
```

## G9 - the decisions gate

**Guarded element:** `find`, `has_layer = _present(os.path.join(d_m, _REVIEW_CREW))` passed as `admitted=has_layer`
(`leftover_settings.py:200`) - axis: the decisions family lists nothing while the recorded side has no review-crew
layer, because the decisions side follows the review calibration's location and the other side's decisions may be the
ones read.

**Neutralization:** `has_layer = _present(os.path.join(d_m, _REVIEW_CREW))` became `has_layer = True`.

**Node:** `test_leftover_settings_2587.py::test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_decisions`
(test 2 of the order).

**Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_decisions ____

w = <test_leftover_settings_2587.W object at 0x7f81ecdb9f70>

    def test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_decisions(w):
        # axis: a decisions family lists nothing while the recorded side has no review-crew layer, since the other side's decisions may be the ones read
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        _put(os.path.join(w.entry(w.rr), "review-profile.md"), "## Threat model\nread\n")
        _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
        _put(w.inrepo("review-decisions.json"), '{"in": true}\n')
        _put(os.path.join(w.entry(w.rr), "review-decisions.json"), '{"legacy": true}\n')
>       assert w.paths() == []
E       AssertionError: assert ['/tmp/claude...cisions.json'] == []
E         
E         Left contains one more item: '/tmp/claude-0/pytest-of-root/pytest-20/test_legacy_read_with_a_layer_0/repo/.claude/review-decisions.json'
E         Use -v to get more diff

/home/user/wt-2587/plugins/superheroes/lib/tests/test_leftover_settings_2587.py:343: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_settings_2587.py::test_legacy_read_with_a_layer_on_the_other_side_lists_nothing_decisions
1 failed in 0.64s
```

**Restore:** inverse edit, `has_layer = True` back to `has_layer = _present(os.path.join(d_m, _REVIEW_CREW))`.

**Restore receipt:** `leftover_settings.py:200` reads `        has_layer = _present(os.path.join(d_m, _REVIEW_CREW))`.

**Raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```
