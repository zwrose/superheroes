# Bite-proof record: wo2_2587_storage_move_settings

Detector: `plugins/superheroes/lib/tests/test_storage_move_settings_2587.py`.
Guarded file: `plugins/superheroes/lib/mode_migrate.py` (`_settings_entries`, `_is_regular`).
Command, every run: `scripts/pinned-python -B -X pycache_prefix=/tmp/wo2-2587-pyc -m pytest <node> -q`
from `/home/user/wt-2587`. Every neutralization is one targeted edit made with the edit tool and
undone by the inverse edit; the restored line is quoted back. Redaction: none needed (no secrets,
tokens or private URLs in any capture; the tmp paths are pytest's own). Each capture is far under the
32 KiB per-element ceiling. The one `UV_NATIVE_TLS` warning line the interpreter wrapper prints on
every run is kept in the captures.

Guarded-element set (declared by the order): G1 decisions carry, G2 legacy-profile set-aside,
G3 regular-file check, G4 only-copy rule. Four elements, four neutralizations, four reds; no
equivalence classes, no element unproven.

## G1 - the decisions carry (axis: the first present regular M-side copy moves to T's first slot)

- Guarded element: `mode_migrate.py` `_settings_entries`, the branch `elif not carried:` ahead of
  `carried = take(path, t_first, ROLE_CARRY, "decisions")`.
- Neutralization: `elif not carried:` -> `elif False:` (no decisions copy is carried any more).
- Detector: `test_in_repo_to_global_leaves_no_listed_kind_behind`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_in_repo_to_global_leaves_no_listed_kind_behind ______________

w = <test_storage_move_settings_2587.W object at 0x7fa83f2527b0>

    def test_in_repo_to_global_leaves_no_listed_kind_behind(w):
        # axis: a flip out of in-repo carries the decisions and sets every stale copy aside, so find lists nothing
        review_entry, tp_entry = _seed_in_repo(w)
        m = w.plan(mr.GLOBAL)
        assert m.blocked is False
        res = mm.execute(m, root=w.root)
        assert res == {"status": "done"}
        assert mr.resolve(w.cwd, root=w.root)["mode"] == mr.GLOBAL
        result = w.find()
        assert result["mode"] == mr.GLOBAL
        assert result["files"] == []
        # the carried decisions
>       assert _text(w.d_gl(_DEC)) == '{"in": true}\n'
               ^^^^^^^^^^^^^^^^^^^

/home/user/wt-2587/plugins/superheroes/lib/tests/test_storage_move_settings_2587.py:172: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

path = '/tmp/claude-0/pytest-of-root/pytest-24/test_in_repo_to_global_leaves_0/_store_isolation/projects/238a7b644f5fb344/config/review-decisions.json'

    def _text(path):
>       with open(path, encoding="utf-8") as fh:
             ^^^^^^^^^^^^^^^^^^^

E       FileNotFoundError: [Errno 2] No such file or directory: '/tmp/claude-0/pytest-of-root/pytest-24/test_in_repo_to_global_leaves_0/_store_isolation/projects/238a7b644f5fb344/config/review-decisions.json'

/home/user/wt-2587/plugins/superheroes/lib/tests/test_storage_move_settings_2587.py:59: FileNotFoundError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_move_settings_2587.py::test_in_repo_to_global_leaves_no_listed_kind_behind
1 failed in 0.42s
```

(Elision note: pytest's caret marker line under `with open(path, encoding="utf-8") as fh:` is
longer in the live output than the abbreviated one shown here; it carries no information.
Everything else is as printed.)

- Restore: inverse edit `elif False:` -> `elif not carried:`; quoted back, `mode_migrate.py:258`:
  `        elif not carried:`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.83s
```

## G2 - the legacy-profile set-aside (axis: a legacy profile whose hero's unified layer moves is set aside)

- Guarded element: `mode_migrate.py` `_settings_entries`, the branch `elif layer_moves:`.
- Neutralization: `elif layer_moves:` -> `elif False:` (no legacy profile is ever set aside).
- Detector: `test_preview_names_set_asides_left_in_place_and_overwrites`.
- Raw red:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_preview_names_set_asides_left_in_place_and_overwrites __________

w = <test_storage_move_settings_2587.W object at 0x7f96997ca750>

    def test_preview_names_set_asides_left_in_place_and_overwrites(w):
        # axis: the preview shows where each set-aside goes, what stays and why, and what is replaced
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
        _put(w.inrepo("review-profile.md"), "## Threat model\nold\n")        # layer moves: set aside
        _put(w.inrepo("test-pilot", "profile.md"), _PILOT + "old\n")         # no layer: only copy
        _put(w.inrepo(_DEC), '{"in": true}\n')                               # carried
        review_entry = w.entry(w.rr)
        os.makedirs(os.path.join(review_entry, "review-profile.md"))         # not a regular file
        _put(w.d_gl("core.md"), _CORE + "\n<!-- already there -->\n")        # replaced by the flip
        _put(w.d_gl(_DEC), '{"old": true}\n')                                # replaced by the carry
        m = w.enumerate(mr.GLOBAL)
        pv = mm.preview(m)
        folders_before = w.backup_folders()
        assert folders_before == []                                          # nothing is created
>       assert len(pv["setAside"]) == 1
E       assert 0 == 1
E        +  where 0 = len([])

/home/user/wt-2587/plugins/superheroes/lib/tests/test_storage_move_settings_2587.py:251: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_move_settings_2587.py::test_preview_names_set_asides_left_in_place_and_overwrites
1 failed in 0.45s
```

- Restore: inverse edit `elif False:` -> `elif layer_moves:`; quoted back, `mode_migrate.py:286`:
  `            elif layer_moves:`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.31s
```

## G3 - the regular-file check (axis: a directory or a link is never moved and never called an only copy)

- Guarded element: `mode_migrate.py` `_is_regular` (line 194).
- Neutralization: `return os.path.isfile(path) and not os.path.islink(path)` ->
  `return os.path.lexists(path)` (any present path counts as regular).
- Detector: `test_a_non_regular_path_is_never_moved`.
- Raw red (pytest itself elides the long set literal with `...`; the output is as printed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________________ test_a_non_regular_path_is_never_moved ____________________

w = <test_storage_move_settings_2587.W object at 0x7ff460e62270>
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-28/test_a_non_regular_path_is_nev0')

    def test_a_non_regular_path_is_never_moved(w, tmp_path):
        # axis: a directory or a link is named not-a-regular-file, never moved and never called an only copy
        w.register(mr.IN_REPO)
        _put(w.d_in("core.md"), _CORE)
        _put(w.d_in("review-crew.md"), "## Focus hints\n- in-repo\n")
        os.makedirs(w.inrepo(_DEC))                                           # a directory
        target = _put(str(tmp_path / "elsewhere" / "p.md"), "linked\n")
        os.makedirs(w.inrepo("test-pilot"))
        os.symlink(target, w.inrepo("review-profile.md"))                     # a link, layer moves
        os.symlink(target, w.inrepo("test-pilot", "profile.md"))              # a link, no layer
        m = w.enumerate(mr.GLOBAL)
        moved = {p for f in m.files for p in (f["src"], f["dst"])}
        for path in (w.inrepo(_DEC), w.inrepo("review-profile.md"), w.inrepo("test-pilot", "profile.md")):
>           assert path not in moved
E           AssertionError: assert '/tmp/claude-0/pytest-of-root/pytest-28/test_a_non_regular_path_is_nev0/repo/.claude/review-decisions.json' not in {'/tmp/claude-0/pytest-of-root/pytest-28/test_a_non_regular_path_is_nev0/_store_isolation/projects/238a7b644f5fb344/co...ns.json', '/tmp/claude-0/pytest-of-root/pytest-28/test_a_non_regular_path_is_nev0/repo/.claude/review-profile.md', ...}

/home/user/wt-2587/plugins/superheroes/lib/tests/test_storage_move_settings_2587.py:304: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_move_settings_2587.py::test_a_non_regular_path_is_never_moved
1 failed in 0.31s
```

- Restore: inverse edit; quoted back, `mode_migrate.py:194`:
  `    return os.path.isfile(path) and not os.path.islink(path)`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.39s
```

## G4 - the only-copy rule (axis: a legacy profile with no moving unified layer is left in place)

- Guarded element: `mode_migrate.py` `_settings_entries`, the final `else:` branch
  `leave(path, WHY_ONLY_COPY)` (line 289).
- Neutralization: `leave(path, WHY_ONLY_COPY)` -> `take(path, None, ROLE_SET_ASIDE, family)` (the
  only copy is moved aside).
- Detector: `test_a_legacy_profile_without_a_moving_layer_stays_put`.
- Raw red (pytest elides the long set literals with `...`; the output is as printed):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_a_legacy_profile_without_a_moving_layer_stays_put ____________

w = <test_storage_move_settings_2587.W object at 0x7f02614de270>

    def test_a_legacy_profile_without_a_moving_layer_stays_put(w):
        # axis: a legacy profile whose hero has no unified layer to move is left in place as the only copy
        w.register(mr.GLOBAL)
        _put(w.d_gl("core.md"), _CORE)
        review_entry = w.entry(w.rr)
        tp_entry = w.entry(w.tr)
        legacy = [_put(w.inrepo("review-profile.md"), "r\n"),
                  _put(os.path.join(review_entry, "review-profile.md"), "e\n"),
                  _put(w.inrepo("test-pilot", "profile.md"), "t\n"),
                  _put(os.path.join(tp_entry, "profile.md"), "u\n")]
        m = w.enumerate(mr.IN_REPO)
        moved = {f["src"] for f in m.files}
>       assert not (set(legacy) & moved)
E       AssertionError: (pytest's long set-literal line, elided by pytest with "...")

/home/user/wt-2587/plugins/superheroes/lib/tests/test_storage_move_settings_2587.py:326: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_storage_move_settings_2587.py::test_a_legacy_profile_without_a_moving_layer_stays_put
1 failed in 0.38s
```

(Elision, stated plainly: the `E` line of this capture was a very long set literal; I replaced it
above with a one-line description rather than re-typing paths. The decisive lines are the `>` line,
`assert not (set(legacy) & moved)`, and `1 failed`. The other three captures above are as printed.)

- Restore: inverse edit; quoted back, `mode_migrate.py:289`:
  `                leave(path, WHY_ONLY_COPY)`
- Raw green:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 0.30s
```

## Restore receipt (all four)

After the G4 restore, a grep over `mode_migrate.py` for the four guarded lines and for stray
neutralizations (`elif False`) printed exactly: line 194 `return os.path.isfile(path) and not
os.path.islink(path)`, line 258 `elif not carried:`, line 286 `elif layer_moves:`, line 289
`leave(path, WHY_ONLY_COPY)`, and no `elif False` match.
