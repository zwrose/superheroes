# Bite-proof record: WO 2118-C2 (REST activity read, branch committer date)

Detector added: `test_rest_branch_committer_date_is_the_newest_activity` in
`plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py` (sibling GraphQL-side test:
`test_graphql_branch_committed_date_is_the_newest_activity`, which guards no production line
mutated here and is not a detector for either element below).

Guarded-element set (declared by the order): (1) the branch committer date reaching the activity
age; (2) the committer, not the author, date. Each proof ran the detector unedited, selected by
exact node id, under `-B -X pycache_prefix=/tmp/superheroes-pyc-2118`. Receipts are unredacted
(nothing secret in them); the `UV_NATIVE_TLS` deprecation warning line is elided from each capture.

## 1. Branch committer date read

- **Element and axis:** `_cloud_activity_repository_rest`, the branch node's `committedDate`
  (`plugins/superheroes/lib/wave_watch.py:1291`); axis: the branch's commit date reaches the
  activity age.
- **Neutralization** (one targeted Edit; the target occurred exactly once):
  - before: `target = {"committedDate": commit_dates[sha]}`
  - after: `target = {"committedDate": issue.get("updated_at")}`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_rest_branch_committer_date_is_the_newest_activity ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-27/test_rest_branch_committer_dat0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f9c7b9b20f0>

    def test_rest_branch_committer_date_is_the_newest_activity(tmp_path, clock):
        # axis: the branch head commit's committer date, not its author date or the issue's time
        gh = _activity_gh(_GRAPHQL_REFUSED)
        commit = _json("git_commits_34dc2c5c.json")
        commit["author"]["date"] = _OTHER_TIME
        commit["committer"]["date"] = _FRESH_AT
        endpoint = "%s/git/commits/%s" % (_BASE, _BRANCH_SHA)
        gh.routes[endpoint] = (0, json.dumps(commit), "")
>       assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}
E       assert {2110: 1792811789.0} == {2110: 1792886400.0}
E         
E         Differing items:
E         {2110: 1792811789.0} != {2110: 1792886400.0}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:347: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_rest_branch_committer_date_is_the_newest_activity
1 failed in 0.32s
```

  The red is on the claimed axis: the read returned the issue's `updated_at` epoch
  (1792811789.0 = 2026-10-24T03:16:29Z) instead of the branch commit's committer date.
- **Restore:** the inverse Edit (the `after` line back to the `before` line).
- **Restore receipt** (restored line quoted back, `wave_watch.py:1291`):
  `                    target = {"committedDate": commit_dates[sha]}`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 3.43s
```

## 2. Committer, not author

- **Element and axis:** `_cloud_activity_repository_rest`, the git commit's date source
  (`plugins/superheroes/lib/wave_watch.py:1287`); axis: which commit date (committer vs author).
- **Neutralization** (one targeted Edit; the target occurred exactly once):
  - before: `committer = get("%s/git/commits/%s" % (base, sha)).get("committer")`
  - after: `committer = get("%s/git/commits/%s" % (base, sha)).get("author")`
- **Raw red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_rest_branch_committer_date_is_the_newest_activity ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-29/test_rest_branch_committer_dat0')
clock = <test_wave_watch_cloud_rest._Clock object at 0x7f01547b20c0>

    def test_rest_branch_committer_date_is_the_newest_activity(tmp_path, clock):
        # axis: the branch head commit's committer date, not its author date or the issue's time
        gh = _activity_gh(_GRAPHQL_REFUSED)
        commit = _json("git_commits_34dc2c5c.json")
        commit["author"]["date"] = _OTHER_TIME
        commit["committer"]["date"] = _FRESH_AT
        endpoint = "%s/git/commits/%s" % (_BASE, _BRANCH_SHA)
        gh.routes[endpoint] = (0, json.dumps(commit), "")
>       assert _fetch(gh, tmp_path, clock=clock) == {2110: _epoch(_FRESH_AT)}
E       assert {2110: 1792811789.0} == {2110: 1792886400.0}
E         
E         Differing items:
E         {2110: 1792811789.0} != {2110: 1792886400.0}
E         Use -v to get more diff

/home/user/wt-2118/plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py:347: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_wave_watch_cloud_rest.py::test_rest_branch_committer_date_is_the_newest_activity
1 failed in 0.28s
```

  Reading the author date (`_OTHER_TIME`, 2026-10-20) leaves the issue's `updated_at` epoch
  (1792811789.0) as the newest signal, so the committer-date assertion goes red on the claimed axis.
- **Restore:** the inverse Edit (the `after` line back to the `before` line).
- **Restore receipt** (restored line quoted back, `wave_watch.py:1287`):
  `                        committer = get("%s/git/commits/%s" % (base, sha)).get("committer")`
- **Raw green:**

```
.                                                                        [100%]
1 passed in 0.27s
```
