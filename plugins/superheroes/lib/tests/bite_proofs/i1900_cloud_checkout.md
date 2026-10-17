# I1900 cloud-checkout bite-proof record

Invariant: a cloud launch runs the cloud command only when the launching checkout is on a named
branch whose local HEAD and whose tip on `origin` are both exactly the premise's `baseCommit`;
otherwise it refuses with a named reason before the command runs, at both check points; the
checkout is never written.

Guarded-element set (declared by the order): G1–G7 below, all in
`plugins/superheroes/lib/launcher.py`. Each node was run alone as
`scripts/pinned-python -B -X pycache_prefix=/tmp/claude-0/pyc -m pytest "<node>" -q -p no:cacheprovider`
with the detector unedited. Every capture below is the full output of that command; each begins
with the same harness warning line (`UV_NATIVE_TLS`), which is not part of the test. Nothing is
redacted. Every restore was the inverse edit (no `git checkout`/`restore`/`reset`/`stash`), and the
restored lines were read back from the file after the last restore.

Reading the reds: a refusal under the wrong token still counts as red (the order's rule), and the
axis of each red is stated per entry. In G1 and G2 the neutralized guard lets the launch fall
through to the next guard, so the red token is the next guard's, not the expected one.

---

## G1 — HEAD != base → off-base (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2598` `if head != base:` → `launch-cloud-checkout-off-base`.
**Axis:** a checkout whose HEAD is not the base refuses, and the remote is not asked.

**Neutralization:** `if head != base:` → `if False and head != base:` (the comparison is never true).

**Red run** (`test_row1_a_checkout_on_another_branch_at_another_commit_refuses_and_is_left_untouched`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row1_a_checkout_on_another_branch_at_another_commit_refuses_and_is_left_untouched _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-0/test_row1_a_checkout_on_anothe0')

    def test_row1_a_checkout_on_another_branch_at_another_commit_refuses_and_is_left_untouched(
        tmp_path,
    ):
        # axis: HEAD that is not the base refuses, and the launcher never writes the checkout
        repo = _cloud_repo(tmp_path)
        base = _head_sha(repo)
        _git(repo, "checkout", "-q", "-b", "elsewhere")
        elsewhere = _commit(repo, "tracked.txt")
        assert elsewhere != base
        with open(os.path.join(repo, "file.txt"), "w") as fh:
            fh.write("staged\n")
        _git(repo, "add", "file.txt")
        with open(os.path.join(repo, "tracked.txt"), "w") as fh:
            fh.write("unstaged\n")
        with open(os.path.join(repo, "untracked.txt"), "w") as fh:
            fh.write("untracked\n")
    
        def snapshot():
            return {
                "symbolic": _git(repo, "symbolic-ref", "HEAD"),
                "head": _head_sha(repo),
                "status": _git(repo, "status", "--porcelain"),
                "cached": _git(repo, "diff", "--cached"),
                "diff": _git(repo, "diff"),
                "files": {
                    name: open(os.path.join(repo, name), "rb").read()
                    for name in ("file.txt", "tracked.txt", "untracked.txt")
                },
            }
    
        before = snapshot()
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                         premise=_valid_premise(repo, baseCommit=base))
>       _assert_refused_cloud_lane(repo, result, OFF_BASE, "cloud-base")

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:104: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-0/test_row1_a_checkout_on_anothe0/repo'
result = {'ok': False, 'reason': 'launch-cloud-checkout-branch-not-on-remote', 'launchId': 'launch-5295894fdce5e7e8', 'warnings': [], ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
        assert result["ok"] is False
>       assert result["reason"] == reason
E       AssertionError: assert 'launch-cloud...not-on-remote' == 'launch-cloud...kout-off-base'
E         
E         - launch-cloud-checkout-off-base
E         + launch-cloud-checkout-branch-not-on-remote

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud.py:613: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row1_a_checkout_on_another_branch_at_another_commit_refuses_and_is_left_untouched
1 failed in 1.90s
```
Axis check: the red is on the refusal token for the HEAD comparison (`off-base` expected; the launch
fell through to the remote question, which answered `branch-not-on-remote`).

**Restore:** inverse edit, `if False and head != base:` → `if head != base:`.
**Restore receipt:** read back from the file (`launcher.py:2598-2599`):
```
    if head != base:
        return "launch-cloud-checkout-off-base", detail
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.58s
```

---

## G2 — branch/HEAD unread → unreadable (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2595` `if branch is None or head is None:` → `launch-cloud-checkout-unreadable`.
**Axis:** a branch or HEAD that could not be read refuses, a detached HEAD included.

**Neutralization:** `if branch is None or head is None:` → `if head is None:` (skips the guard for the
symbolic-ref leg only; the `branch is None` leg of a detached HEAD no longer refuses).

**Red run** (`test_row3_a_detached_head_at_the_base_refuses_as_unreadable`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_row3_a_detached_head_at_the_base_refuses_as_unreadable __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_row3_a_detached_head_at_t0')

    def test_row3_a_detached_head_at_the_base_refuses_as_unreadable(tmp_path):
        # axis: a branch or HEAD that could not be read refuses
        repo = _cloud_repo(tmp_path)
        base = _head_sha(repo)
        _git(repo, "checkout", "-q", "--detach")
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
>       _assert_refused_cloud_lane(repo, result, UNREADABLE, "cloud-base")

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:134: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-2/test_row3_a_detached_head_at_t0/repo'
result = {'ok': False, 'reason': 'launch-cloud-checkout-branch-not-on-remote', 'launchId': 'launch-9bf74bbce29e75ce', 'warnings': [], ...}
reason = 'launch-cloud-checkout-unreadable', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
        assert result["ok"] is False
>       assert result["reason"] == reason
E       AssertionError: assert 'launch-cloud...not-on-remote' == 'launch-cloud...ut-unreadable'
E         
E         - launch-cloud-checkout-unreadable
E         + launch-cloud-checkout-branch-not-on-remote

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud.py:613: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row3_a_detached_head_at_the_base_refuses_as_unreadable
1 failed in 1.72s
```
Axis check: the red is on the unreadable token for a detached HEAD (`unreadable` expected; the launch
fell through to the remote question).

**Restore:** inverse edit, `if head is None:` → `if branch is None or head is None:`.
**Restore receipt:** read back from the file (`launcher.py:2595-2596`):
```
    if branch is None or head is None:
        return "launch-cloud-checkout-unreadable", detail
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.69s
```
Disclosure about this green: the G2 green command and the first edit of G3 were issued in the same
tool batch, so the order they hit the file is not recorded. The G3 edit sits after the G2 guard and
the detached-HEAD test returns at the G2 guard, so the G3 neutralization cannot change this
node's outcome. The G2 restore is confirmed by the read-back above.

---

## G3 — remote tip != base → off-base (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2609` `if tip != base:` → `launch-cloud-checkout-off-base`.
**Axis:** a remote branch tip that is not the base refuses.

**Neutralization:** `if tip != base:` → `if False and tip != base:` (the comparison is skipped).

**Red run** (`test_row5_a_remote_branch_tip_that_moved_past_the_base_refuses_as_off_base`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
__ test_row5_a_remote_branch_tip_that_moved_past_the_base_refuses_as_off_base __

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_row5_a_remote_branch_tip_0')

    def test_row5_a_remote_branch_tip_that_moved_past_the_base_refuses_as_off_base(tmp_path):
        # axis: a remote branch tip that is not the base refuses
        repo = _cloud_repo(tmp_path)
        base = _head_sha(repo)
        branch = _branch(repo)
        later = _commit(repo, "later.txt")
        _git(repo, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)
        _git(repo, "reset", "-q", "--hard", base)
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls),
                         premise=_valid_premise(repo, baseCommit=base))
>       _assert_refused_cloud_lane(repo, result, OFF_BASE, "cloud-base")

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:190: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-4/test_row5_a_remote_branch_tip_0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-a3a7953ceed7ae89', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-off-base', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row5_a_remote_branch_tip_that_moved_past_the_base_refuses_as_off_base
1 failed in 1.78s
```
Axis check: the red is the launch running (`ok` True) with the remote tip past the base.

**Restore:** inverse edit, `if False and tip != base:` → `if tip != base:`.
**Restore receipt:** read back from the file (`launcher.py:2609-2611`):
```
    if tip != base:
        return "launch-cloud-checkout-off-base", detail
    return None
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.64s
```

---

## G4 — "absent" → branch-not-on-remote (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2606` `if why == "absent":` → `launch-cloud-checkout-branch-not-on-remote`.
**Axis:** a branch the remote lacks refuses.

**Neutralization:** `return "launch-cloud-checkout-branch-not-on-remote", detail` → `return None`
(absent treated as ok).

**Red run** (`test_row6_a_branch_never_pushed_refuses_as_not_on_the_remote`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_row6_a_branch_never_pushed_refuses_as_not_on_the_remote _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_row6_a_branch_never_pushe0')

    def test_row6_a_branch_never_pushed_refuses_as_not_on_the_remote(tmp_path):
        # axis: a branch the remote lacks refuses
        repo = _cloud_repo(tmp_path)
        _git(repo, "checkout", "-q", "-b", "never-pushed")
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
>       _assert_refused_cloud_lane(repo, result, NOT_ON_REMOTE, "cloud-base")

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:202: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-6/test_row6_a_branch_never_pushe0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-93f2e749a9360b3a', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-branch-not-on-remote', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row6_a_branch_never_pushed_refuses_as_not_on_the_remote
1 failed in 1.88s
```
Axis check: the red is the launch running (`ok` True) for a branch the remote lacks.

**Restore:** inverse edit, `return None` → `return "launch-cloud-checkout-branch-not-on-remote", detail`.
**Restore receipt:** read back from the file (`launcher.py:2606-2607`):
```
    if why == "absent":
        return "launch-cloud-checkout-branch-not-on-remote", detail
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.62s
```

---

## G5 — "unchecked" → remote-unchecked (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2603` `if why == "unchecked":` → `launch-cloud-checkout-remote-unchecked`.
**Axis:** a remote branch tip that could not be read refuses.

**Neutralization:** `return "launch-cloud-checkout-remote-unchecked", detail` → `return None`
(unchecked treated as ok).

**Red run** (`test_row7_a_remote_that_could_not_be_asked_for_the_branch_tip_refuses`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_row7_a_remote_that_could_not_be_asked_for_the_branch_tip_refuses _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-8/test_row7_a_remote_that_could_0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f1c9d22b320>

    def test_row7_a_remote_that_could_not_be_asked_for_the_branch_tip_refuses(tmp_path, monkeypatch):
        # axis: a remote branch tip that could not be read refuses
        repo = _cloud_repo(tmp_path)
        monkeypatch.setattr(L, "_remote_branch_head_fn", lambda *a, **k: (None, "unchecked"))
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
>       _assert_refused_cloud_lane(repo, result, REMOTE_UNCHECKED, "cloud-base")

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:214: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

repo = '/tmp/claude-0/pytest-of-root/pytest-8/test_row7_a_remote_that_could_0/repo'
result = {'ok': True, 'reason': None, 'launchId': 'launch-7cb4191d40deb32f', 'place': 'cloud', ...}
reason = 'launch-cloud-checkout-remote-unchecked', stage = 'cloud-base'

    def _assert_refused_cloud_lane(repo, result, reason, stage):
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud.py:612: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row7_a_remote_that_could_not_be_asked_for_the_branch_tip_refuses
1 failed in 1.64s
```
Axis check: the red is the launch running (`ok` True) when the remote could not be asked.

**Restore:** inverse edit, `return None` → `return "launch-cloud-checkout-remote-unchecked", detail`.
**Restore receipt:** read back from the file (`launcher.py:2603-2604`):
```
    if why == "unchecked":
        return "launch-cloud-checkout-remote-unchecked", detail
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.41s
```

---

## G6 — the re-check call site (`launcher.py:3206`)

**Guarded element:** `drift = _cloud_start_refusal(repo_root, stamped, env)` right before the cloud
command, after reservation. **Axis:** the checkout is re-checked right before the command;
reservation can wait on the lock.

**Neutralization:** the line was replaced by two lines:
```
        drift = _cloud_base_refusal(repo_root, stamped, env)
        drift = (drift, {}) if drift is not None else None
```
(the re-check keeps the base-on-remote question and drops the checkout question).

**Red run** (`test_row9_a_checkout_that_moves_while_reserving_terminalizes_the_unstarted_lane`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_row9_a_checkout_that_moves_while_reserving_terminalizes_the_unstarted_lane _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_row9_a_checkout_that_move0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fba051c8860>

    def test_row9_a_checkout_that_moves_while_reserving_terminalizes_the_unstarted_lane(
        tmp_path, monkeypatch,
    ):
        # axis: the checkout is re-checked right before the command; reservation can wait on the lock
        repo = _cloud_repo(tmp_path)
        real_reserve = ll.reserve
    
        def reserve_then_move_the_checkout(*args, **kwargs):
            result = real_reserve(*args, **kwargs)
            _git(repo, "checkout", "-q", "-b", "moved")
            _commit(repo, "moved.txt")
            return result
    
        monkeypatch.setattr(ll, "reserve", reserve_then_move_the_checkout)
        calls = []
        result = _launch(repo, tmp_path, _fake_spawn(calls=calls))
>       assert result["ok"] is False
E       assert True is False

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py:287: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout.py::test_row9_a_checkout_that_moves_while_reserving_terminalizes_the_unstarted_lane
1 failed in 1.77s
```
Axis check: the red is the launch running (`ok` True) after the checkout moved during reservation.

**Restore:** inverse edit, the two neutralizing lines → the one original line.
**Restore receipt:** read back from the file (`launcher.py:3204-3208`):
```
        # axis: reservation may have waited on the ledger lock, so the base is re-checked
        # right before the command; a base the remote lost terminalizes the unstarted lane.
        drift = _cloud_start_refusal(repo_root, stamped, env)
        if drift is not None:
            drift_reason, drift_extra = drift
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.64s
```

---

## G7 — the re-read after the remote answered (`_cloud_checkout_refusal`)

**Guarded element:** `launcher.py:2625` `if again_branch != branch or again_head != base:` →
`launch-cloud-checkout-off-base`, the comparison on the checkout read again after the remote
answered `tip == base`.
**Axis:** a checkout that moved to another branch or commit while the remote lookup was pending
refuses, and the launch does not run.

**Neutralization:** `if again_branch != branch or again_head != base:` →
`if False and (again_branch != branch or again_head != base):` (the comparison is never true).

**Red run** (`test_final_remote_lookup_cannot_accept_a_stale_local_checkout`, in
`test_launcher_cloud_checkout_race_break_it.py`):
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_final_remote_lookup_cannot_accept_a_stale_local_checkout _________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_final_remote_lookup_canno0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f28c0db8410>

    def test_final_remote_lookup_cannot_accept_a_stale_local_checkout(tmp_path, monkeypatch):
        # axis: movement during the final remote lookup refuses without altering owner work.
        monkeypatch.setenv(ll.LEDGER_ROOT_ENV, str(tmp_path / "ledger-root"))
        monkeypatch.delenv("CLAUDE_PID", raising=False)
        monkeypatch.setattr(L, "_pause_between_appends", lambda: None)
        monkeypatch.setattr(L, "_base_on_remote_fn", _local_remote_has)
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    
        repo = _cloud_repo(tmp_path)
        base = _head_sha(repo)
        original_branch = _git(repo, "symbolic-ref", "--short", "HEAD").strip()
        _git(repo, "checkout", "-q", "-b", "owner-work")
        other_head = _commit(repo, "owner.txt")
        assert other_head != base
        _git(repo, "checkout", "-q", original_branch)
    
        tracked = tmp_path / "repo" / "file.txt"
        untracked = tmp_path / "repo" / "untracked.txt"
        tracked.write_text("staged owner work\n")
        _git(repo, "add", "file.txt")
        tracked.write_text("unstaged owner work\n")
        untracked.write_text("untracked owner work\n")
    
        def owner_work():
            return (
                tracked.read_bytes(),
                untracked.read_bytes(),
                _git(repo, "diff", "--cached"),
                _git(repo, "diff"),
                _git(repo, "status", "--porcelain"),
            )
    
        before = owner_work()
        real_remote_head = L._remote_branch_head_fn
        lookups = []
        moved = []
    
        def remote_head_then_owner_switches(repo_root, branch, env):
            answer = real_remote_head(repo_root, branch, env)
            lookups.append(branch)
            if len(lookups) == 2:
                assert answer == (base, None)
                # Deterministic interleaving: the owner switches while the final lookup is pending.
                _git(repo, "checkout", "-q", "owner-work")
                moved.append(True)
            return answer
    
        monkeypatch.setattr(L, "_remote_branch_head_fn", remote_head_then_owner_switches)
        calls = []
        result = _launch(
            repo, tmp_path, _fake_spawn(calls=calls),
            premise=_valid_premise(repo, baseCommit=base),
        )
    
        assert moved, "the final remote-lookup interleaving was not exercised"
        assert _head_sha(repo) == other_head
        assert owner_work() == before
>       assert result["ok"] is False, result
E       AssertionError: {'ok': True, 'reason': None, 'launchId': 'launch-d24dafa37c624f4c', 'place': 'cloud', ...}
E       assert True is False

/home/user/wt-1900/plugins/superheroes/lib/tests/test_launcher_cloud_checkout_race_break_it.py:76: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher_cloud_checkout_race_break_it.py::test_final_remote_lookup_cannot_accept_a_stale_local_checkout
1 failed in 1.70s
```
Axis check: the red is the launch running (`ok` True) after the owner switched branches while the
final remote lookup was pending.

**Restore:** inverse edit, `if False and (again_branch != branch or again_head != base):` →
`if again_branch != branch or again_head != base:`.
**Restore receipt:** read back from the file (`launcher.py:2625-2626`):
```
    if again_branch != branch or again_head != base:
        return "launch-cloud-checkout-off-base", detail
```

**Green run:**
```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed in 1.63s
```
