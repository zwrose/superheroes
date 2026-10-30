# #2272 launcher bite-proofs — the limit reading, the removed exemption, the pre-spawn re-check, the adoption checkout

Declared guarded elements (WO3): (a) the `limited is True` requirement; (b) the `startedTs < recordedAt`
requirement; (c) a limited lane still refused when a listing shows it live; (d) the deleted-branch exemption's
removal; (e) the adoption-checkout target; (e2) the pre-spawn re-check on the cloud path; (e3) the pre-spawn
re-check on the local path; (f) the non-adoption base rule. One red and one green per element, each the
detector alone as a single test node, run with
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:randomly`
(`<file>` below is `plugins/superheroes/lib/tests/test_i2272_launcher.py`). Every neutralization is in
`plugins/superheroes/lib/launcher.py` and was undone by the inverse edit; after every restore
`git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing (the file equals the committed
head). Redaction: the (e) red output printed the process environment inside an assertion message; the proxy URL
there carried credentials and is replaced by `<redacted proxy URL>`, and the rest of that line is elided with
`...`. All other captures are raw, with only the leading `warning: The UV_NATIVE_TLS ...` line of every run dropped
(it is the interpreter wrapper's deprecation notice, identical in all sixteen runs).

## (g) an adoption passes from a checkout at its adopted head or at its base — axis: the either-commit rule

**Guarded element:** `launcher.py` `_cloud_start_refusal`, the line
`if head != base and _cloud_checkout_refusal(repo_root, base, env) is None:` (the `# axis:` comment above it).

**Neutralization:** deleted that line and its `return None`, so an adoption is checked against its adopted head alone.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adoption_checkout_at_its_base_passes_the_checkout_check -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
    def test_an_adoption_checkout_at_its_base_passes_the_checkout_check(tmp_path):
        repo, base, head, branch = _adoption_checkout(tmp_path)
        _git(repo, "checkout", "-q", "-B", branch, base)
        _git(repo, "push", "-q", "-f", "origin", "HEAD:refs/heads/%s" % branch)
        stamped = _stamped(base, adoptsBranch=branch, adoptsHead=head)
>       assert L._cloud_start_refusal(repo, stamped, dict(os.environ)) is None
E       AssertionError: assert ('launch-cloud-checkout-off-base', {...}) is None
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adoption_checkout_at_its_base_passes_the_checkout_check
1 failed in 3.72s
```

**Restore:** re-inserted the deleted two lines.

**Green:** the node passes again (the scoped run of the launcher, adoption and checkout tests passed).

## (h) the checkout is the last read before the cloud command — axis: the original-session re-check runs first

**Guarded element:** `launcher.py` `launch_build`, the cloud path runs `_original_session_refusal` before `_cloud_start_refusal`.

**Detector:** `plugins/superheroes/lib/tests/test_i2272_checkout_during_session_read_break_it.py::test_checkout_movement_during_final_session_read_prevents_cloud_spawn`, which failed with the two checks in the old order (`assert result["ok"] is False`, actual `ok: True`) and passes with the re-check first.

## (a) `limited is True` — axis: a limit that has passed gives no relief

**Guarded element:** `launcher.py` `_original_session_pass`, the line `and reading.get("limited") is True` in the
limited-lane test (the `# axis:` comment above it).

**Neutralization:** deleted the line `and reading.get("limited") is True`, so any `ok: True` reading with a
recorded time that postdates the lane relieves it.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_has_passed_leaves_both_lanes_needing_a_listing -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_limit_that_has_passed_leaves_both_lanes_needing_a_listing _______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-75/test_a_limit_that_has_passed_l0')
account = <test_i2272_launcher._Account object at 0x7fd9e98a88c0>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd9e9272120>

    def test_a_limit_that_has_passed_leaves_both_lanes_needing_a_listing(tmp_path, account, monkeypatch):
        # axis: a limit whose reset time has passed (the reading says not limited) gives no relief, so both lanes need a listing — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _two_bound_lanes(repo)
        account.limited_until()
        monkeypatch.setattr(L, "_now_fn", lambda: RESETS_AT)
        result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
>       _refused_unread(repo, result, calls, "listing-not-given")

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:130: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-75/test_a_limit_that_has_passed_l0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-f602244d30fb99bf', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_has_passed_leaves_both_lanes_needing_a_listing
1 failed in 11.26s
```

**Restore:** re-inserted the deleted line between `reading.get("ok") is True` and the `_is_number(started_ts)` line.

**Restore receipt:** `launcher.py` 3264-3271 reads
```
        if (
            isinstance(reading, dict) and reading.get("ok") is True
            and reading.get("limited") is True
            and cloud_recover._is_number(started_ts)
            and cloud_recover._is_number(reading.get("recordedAt"))
            and started_ts < reading["recordedAt"]
        ):
            limited.add(launch_id)
```

**Green:**
```
.                                                                        [100%]
1 passed in 6.46s
```

## (b) `startedTs < recordedAt` — axis: a limit recorded before a lane started says nothing about it

**Guarded element:** `launcher.py` `_original_session_pass`, the line `and started_ts < reading["recordedAt"]`.

**Neutralization:** deleted the line `and started_ts < reading["recordedAt"]` (the `_is_number` checks stay).

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_recorded_before_a_lane_started_leaves_that_lane_needing_a_listing -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_limit_recorded_before_a_lane_started_leaves_that_lane_needing_a_listing _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-77/test_a_limit_recorded_before_a0')
account = <test_i2272_launcher._Account object at 0x7f8847503140>

    def test_a_limit_recorded_before_a_lane_started_leaves_that_lane_needing_a_listing(tmp_path, account):
        # axis: a limit recorded before a lane started says nothing about that lane, so it needs a listing while the older lane is relieved — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _two_bound_lanes(repo, started_ts=RECORDED_AT + 60)
        account.limited_until()
        result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
>       _refused_unread(repo, result, calls, "listing-not-given")

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:140: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-77/test_a_limit_recorded_before_a0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-eeaafca107e7d239', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_recorded_before_a_lane_started_leaves_that_lane_needing_a_listing
1 failed in 5.43s
```

**Restore:** re-inserted `and started_ts < reading["recordedAt"]` before the closing `):`.

**Restore receipt:** `launcher.py` 3264-3271 as quoted under (a).

**Green:**
```
.                                                                        [100%]
1 passed in 2.60s
```

## (c) a limited lane is still refused when a listing shows it live — axis: the limit relieves the listing requirement, never affirmative live evidence

**Guarded element:** `launcher.py` `_original_session_pass`, the evaluation loop over `candidates` (limited lanes
are in `candidates`, only out of `lane_ids`), which matches each lane to the supplied rows and appends it to
`live`.

**Neutralization:** made limited lanes skip the live check: inserted `if launch_id in limited:` / `continue` as the
first statements of `for launch_id, info in candidates.items():` at the start of the evaluation loop.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limited_lane_whose_session_the_listing_shows_live_refuses_live -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_limited_lane_whose_session_the_listing_shows_live_refuses_live _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-79/test_a_limited_lane_whose_sess0')
account = <test_i2272_launcher._Account object at 0x7f82941b2180>

    def test_a_limited_lane_whose_session_the_listing_shows_live_refuses_live(tmp_path, account):
        # axis: a limit relieves a lane of needing a listing but a supplied listing that shows its session live still refuses — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
        account.limited_until()
        result, calls = _adopt(repo, tmp_path, _fixture("get_session_running.json"), branch=ADOPTED)
>       _assert_refused_cloud_lane(repo, result, TOKEN_LIVE, "original-session")

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:230: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-79/test_a_limited_lane_whose_sess0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-9007e8782e52b5ff', 'place': 'cloud', ...}
reason = 'adopt-original-session-live', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limited_lane_whose_session_the_listing_shows_live_refuses_live
1 failed in 2.69s
```

**Restore:** removed the two inserted lines. The first restore left a one-space residue on the next line
(`matched =[row ...`, valid Python, behaviour identical); it was corrected, `git diff --stat HEAD` then printed
nothing, and the green below was re-run on the exactly restored file. (The first green, taken before the
whitespace fix, also passed: `1 passed in 2.85s`.)

**Restore receipt:** `launcher.py` 3298-3302 reads
```
    for launch_id, info in candidates.items():
        if info.get("cloudSessionId") is not None:
            matched = [row for row in rows if row["id"] == info["cloudSessionId"]]
        else:
            matched = [row for row in rows if row.get("title") == info["cloudSessionName"]]
```

**Green:**
```
.                                                                        [100%]
1 passed in 2.90s
```

## (d) the deleted-branch exemption's removal — axis: a bound lane needs a session read (or the limit) whether or not its branch is on origin

**Guarded element:** `launcher.py` `_original_session_pass`, the bound-lane branch (`kept[launch_id] = info` /
`continue`, the `# axis:` comment above it).

**Neutralization:** restored the exemption: in the bound-lane branch, before `kept[launch_id] = info`, asked
`origin` afresh (`_git_scrubbed(repo_root, "ls-remote", "--heads", "origin", "refs/heads/<branch>", env=env,
timeout=_WORKTREE_GIT_TIMEOUT)`, the body of the removed `_adopted_branch_absent`) and, when git succeeded and
printed nothing, `limited.add(launch_id)` (the gone-branch lane is left out of `lane_ids`, the role the old `gone`
set played). This is test 5's first half going from green to red.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_bound_lane_whose_branch_is_gone_with_no_listing_refuses_unread_naming_the_helper_read -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_bound_lane_whose_branch_is_gone_with_no_listing_refuses_unread_naming_the_helper_read _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-82/test_a_bound_lane_whose_branch0')
first_pr = <function first_pr.<locals>.set_value at 0x7f57836de480>

    def test_a_bound_lane_whose_branch_is_gone_with_no_listing_refuses_unread_naming_the_helper_read(
        tmp_path, first_pr,
    ):
        # axis: a lane bound to the adopted branch needs a session read whether or not its branch is still on origin — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _seed_lane(repo, LANE_ID, premise_extra={"adoptsBranch": ADOPTED})
        _delete_remote_branch(repo)
        first_pr(None)
        result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
>       _refused_unread(repo, result, calls, "listing-not-given")

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:298: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-82/test_a_bound_lane_whose_branch0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-2f110f40bb7ddbbd', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_bound_lane_whose_branch_is_gone_with_no_listing_refuses_unread_naming_the_helper_read
1 failed in 3.06s
```

**Restore:** removed the five inserted lines; the bound-lane branch is `kept[launch_id] = info` / `continue` again.

**Restore receipt:** `git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing.

**Green:**
```
.                                                                        [100%]
1 passed in 2.71s
```

## (e) the adoption-checkout target — axis: an adoption's checkout is compared against `adoptsHead`

**Guarded element:** `launcher.py` `_cloud_start_refusal`, `target = head if adopting else stamped["baseCommit"]`.

**Neutralization:** `target = stamped["baseCommit"]` (compare against `baseCommit` always).

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adoption_checkout_at_its_adopted_head_passes_the_checkout_check -q -p no:randomly`

**Red** (the long `E` lines print the process environment; the proxy URL in them is replaced by
`<redacted proxy URL>` and the remainder of each such line is elided with `...`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_an_adoption_checkout_at_its_adopted_head_passes_the_checkout_check ____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-84/test_an_adoption_checkout_at_i0')

    def test_an_adoption_checkout_at_its_adopted_head_passes_the_checkout_check(tmp_path):
        # axis: an adoption is checked against its adopted head, not its base, so a checkout at that head whose remote tip is the head passes — see bite-proof record i2272_launcher
        repo, base, head, branch = _adoption_checkout(tmp_path)
        stamped = _stamped(base, adoptsBranch=branch, adoptsHead=head)
>       assert L._cloud_start_refusal(repo, stamped, dict(os.environ)) is None
E       AssertionError: assert ('launch-cloud-checkout-off-base', {'checkout': '/tmp/claude-0/pytest-of-root/pytest-84/test_an_adoption_checkout_at_i...ckoutHead': '08c08715d78b241debfb6d9654edf9474e1b9fca', 'baseCommit': '0227ed9a7cac4c848c6896d1c5e84a16d0f27fdc', ...}) is None
E        +  where ('launch-cloud-checkout-off-base', {...}) = <function _cloud_start_refusal at 0x7f11f06e2f20>('/tmp/claude-0/pytest-of-root/pytest-84/test_an_adoption_checkout_at_i0/repo', {'baseCommit': '0227ed9a7cac4c848c6896d1c5e84a16d0f27fdc', 'adoptsBranch': 'master', 'adoptsHead': '08c08715d78b241debfb6d9654edf9474e1b9fca'}, {... '<redacted proxy URL>' ...})
E        +    where <function _cloud_start_refusal at 0x7f11f06e2f20> = L._cloud_start_refusal
E        +    and   {... '<redacted proxy URL>' ...} = dict(environ({... '<redacted proxy URL>' ...}))

plugins/superheroes/lib/tests/test_i2272_launcher.py:453: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adoption_checkout_at_its_adopted_head_passes_the_checkout_check
1 failed in 2.24s
```

**Restore:** `target = head if adopting else stamped["baseCommit"]`.

**Restore receipt:** `git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing.

**Green:**
```
.                                                                        [100%]
1 passed in 2.13s
```

## (e2) the pre-spawn re-check on the cloud path — axis: the limit is read again right before `_run_cloud_spawn`

**Guarded element:** `launcher.py` `launch_build` cloud path, `recheck = _original_session_refusal(...)` and its
refusal block between the second `_cloud_start_refusal` re-check and `_run_cloud_spawn`.

**Neutralization:** replaced `recheck = _original_session_refusal(repo_root, issue, stamped, cloud_sessions_file, env)`
with `recheck = None` (the refusal block below it stays, never taken).

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_before_the_cloud_spawn_refuses_and_spawns_nothing -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_limit_that_expires_before_the_cloud_spawn_refuses_and_spawns_nothing __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-86/test_a_limit_that_expires_befo0')
account = <test_i2272_launcher._Account object at 0x7f3c3f7b2180>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f3c3e783350>

    def test_a_limit_that_expires_before_the_cloud_spawn_refuses_and_spawns_nothing(
        tmp_path, account, monkeypatch,
    ):
        # axis: the limit read by the first original-session check is read again right before the cloud command, so a limit that expired in between refuses unread and terminalizes the lane — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _two_bound_lanes(repo)
        account.limited_until()
        clock = _Expiring()
        monkeypatch.setattr(L, "_now_fn", clock)
        result, calls = _adopt(repo, tmp_path, branch=ADOPTED)
>       _refused_unread(repo, result, calls, "listing-not-given")

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:355: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_adopt_original_session.py:149: in _refused_unread
    _assert_refused_cloud_lane(repo, result, TOKEN_UNREAD, "original-session")
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-86/test_a_limit_that_expires_befo0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-730e77515c214832', 'place': 'cloud', ...}
reason = 'adopt-original-session-unread', stage = 'original-session'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_before_the_cloud_spawn_refuses_and_spawns_nothing
1 failed in 2.60s
```

**Restore:** `recheck = _original_session_refusal(repo_root, issue, stamped, cloud_sessions_file, env)`.

**Restore receipt:** `git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing.

**Green:**
```
.                                                                        [100%]
1 passed in 2.96s
```

## (e3) the pre-spawn re-check on the local path — axis: the limit is read again right before every `_spawn_attempt`

**Guarded element:** `launcher.py` `launch_build` local retry loop, `recheck = _original_session_refusal(...)` and
its refusal block immediately before `spawn_result = _spawn_attempt(`.

**Neutralization:** replaced that `recheck = _original_session_refusal(...)` line with `recheck = None`.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_before_the_local_spawn_refuses_and_spawns_nothing -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_limit_that_expires_before_the_local_spawn_refuses_and_spawns_nothing __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-88/test_a_limit_that_expires_befo0')
account = <test_i2272_launcher._Account object at 0x7fdeed16ec60>
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fdeed16e4e0>

    def test_a_limit_that_expires_before_the_local_spawn_refuses_and_spawns_nothing(
        tmp_path, account, monkeypatch,
    ):
        # axis: the limit read by the first original-session check is read again right before the local spawn, so a limit that expired in between refuses unread and terminalizes the lane — see bite-proof record i2272_launcher
        repo = _adopted_repo(tmp_path)
        _two_bound_lanes(repo)
        account.limited_until()
        clock = _Expiring()
        monkeypatch.setattr(L, "_now_fn", clock)
        spawned = []
        delegate = _make_spawn_fn("sleep")
    
        def recording_spawn(*args, **kwargs):
            spawned.append(args)
            return delegate(*args, **kwargs)
    
        result = _local_adoption(repo, tmp_path, recording_spawn)
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-2272-wo3/plugins/superheroes/lib/tests/test_i2272_launcher.py:387: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_a_limit_that_expires_before_the_local_spawn_refuses_and_spawns_nothing
1 failed in 3.34s
```

**Restore:** `recheck = _original_session_refusal(repo_root, issue, stamped, cloud_sessions_file, env)`.

**Restore receipt:** `git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing.

**Green:**
```
.                                                                        [100%]
1 passed in 2.91s
```

## (f) the non-adoption base rule — axis: only a premise that carries `adoptsBranch` is checked against `adoptsHead`

**Guarded element:** `launcher.py` `_cloud_start_refusal`, the `"adoptsBranch" in stamped` term of the `adopting`
test.

**Neutralization:** removed the term `"adoptsBranch" in stamped and` from the `adopting` line, leaving
`adopting = isinstance(head, str) and bool(_HEX40.match(head))` (compare against `adoptsHead` whenever a full
sha is present, even without `adoptsBranch`).

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adopted_head_without_an_adopted_branch_is_still_checked_against_the_base -q -p no:randomly`

**Red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_an_adopted_head_without_an_adopted_branch_is_still_checked_against_the_base _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-90/test_an_adopted_head_without_a0')

    def test_an_adopted_head_without_an_adopted_branch_is_still_checked_against_the_base(tmp_path):
        # axis: only a premise that carries adoptsBranch is checked against adoptsHead; a stray adoptsHead alone keeps the base rule — see bite-proof record i2272_launcher
        repo, base, head, branch = _adoption_checkout(tmp_path)
>       reason, detail = L._cloud_start_refusal(
        ^^^^^^^^^^^^^^
            repo, _stamped(base, adoptsHead=head), dict(os.environ),
        )
E       TypeError: cannot unpack non-iterable NoneType object

plugins/superheroes/lib/tests/test_i2272_launcher.py:469: TypeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_launcher.py::test_an_adopted_head_without_an_adopted_branch_is_still_checked_against_the_base
1 failed in 2.28s
```

**Restore:** re-inserted `"adoptsBranch" in stamped and` into the `adopting` line.

**Restore receipt:** `launcher.py` line 2858 reads
`    adopting = "adoptsBranch" in stamped and isinstance(head, str) and bool(_HEX40.match(head))`;
`git diff --stat HEAD -- plugins/superheroes/lib/launcher.py` printed nothing.

**Green:**
```
.                                                                        [100%]
1 passed in 2.32s
```
