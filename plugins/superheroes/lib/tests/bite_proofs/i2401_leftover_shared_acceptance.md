# Bite-proof record: i2401_leftover_shared_acceptance (#2401) the leftover refusal says when a finding shares one acceptance with another

Detector under proof: `plugins/superheroes/lib/tests/test_leftover_shared_acceptance_2401.py`, test `test_t1_sub_bullets_refuse_with_the_shared_acceptance_named` (unedited between the red and the green).
Guarded code: `plugins/superheroes/lib/leftover_accepting.py` (`describe`, the shared branch). Base head `c72c4282`.
The neutralization was one targeted edit made with the Edit tool and undone by the inverse Edit. No `git checkout`, `restore`, `reset`, `stash` or `sed` was used.
Command (worktree root):
`timeout 300 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_leftover_shared_acceptance_2401.py -q -p no:cacheprovider -k t1`

Guarded-element set (declared by the order): G1 the shared branch in `describe` (the `sharedWith` rendering plus the appended sentence). No others.

Disclosures: captures are the runner's output; the red's long assertion line is shown as the runner printed it (the runner itself elided the middle of the detail string with `...`). Nothing was redacted. Captures are far under the 32 KiB ceiling.

## G1: a gap with a non-empty `sharedWith` reads `shares one acceptance with <holder>` and the one-acceptance sentence follows once

- **Guarded element / axis:** `leftover_accepting.py`, `describe`, the `if holders:` branch (axis comment above it). Axis: a missing finding named inside an acceptance another finding already took says so, and asks for one top-level bullet per finding.
- **Neutralization:** `holders = g.get("sharedWith") or []` became `holders = []` (`describe` ignores `sharedWith`).
- **Raw red** (`-k t1`):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_t1_sub_bullets_refuse_with_the_shared_acceptance_named __________

    def test_t1_sub_bullets_refuse_with_the_shared_acceptance_named():
        b = body(SUB_ALL)
        assert la.missing(rec(), b) == [gap(F2), gap(F3)]
        result = handback(b)
        assert result["ok"] is False and result["reason"] == "leftover-not-accepted"
        for f in (F2, F3):
>           assert "%s (%s) shares one acceptance with f-1 (%s)" % (f["id"], f["title"], F1["title"]) in result["detail"]
E           assert ('%s (%s) shares one acceptance with f-1 (%s)' % ('f-2', 'a stale cache entry survives restart', 'the retry loop never backs off')) in "What we're accepting does not name these findings left for the owner, each by its record id and its title in one line...hed as lib/leftover_accepting.py states: f-2 (a stale cache entry survives restart); f-3 (the export drops empty rows)"

/home/user/wt-2401/plugins/superheroes/lib/tests/test_leftover_shared_acceptance_2401.py:52: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_leftover_shared_acceptance_2401.py::test_t1_sub_bullets_refuse_with_the_shared_acceptance_named
1 failed, 10 deselected in 0.22s
```

- **Restore:** inverse Edit, `holders = []` back to `holders = g.get("sharedWith") or []`.
- **Restore receipt:** the Grep tool for `holders = ` printed `490:        holders = g.get("sharedWith") or []`.
- **Raw green** (same command):

```
.                                                                        [100%]
1 passed, 10 deselected in 0.22s
```
