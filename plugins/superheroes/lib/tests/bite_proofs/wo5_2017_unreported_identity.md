# #2017 WO-5 bite-proof: an unreported identity is not a missing one

Bite-proof record for `plugins/superheroes/lib/cloud_check.py` (`_failed_message`, `judge`). Detector file: `CCI` = `plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py`.

**Status.** The implementer ran every proof (J1 to J4): each neutralization is one targeted Edit in `cloud_check.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run; the one deprecation warning pytest's launcher prints first (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`) is left out of each capture and is the same in all eight. Absolute `tmp_path` prefixes are as printed. No fixture holds a real secret, so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc -m pytest "<file>::<node>" -q`.
- **Restore receipt, every element.** The restored lines are quoted back from the file by a `grep -n` after the inverse Edit.

## Declared guarded-element set

J1 the reported test (`identity_reported` in `judge`); J2 the sole-part sentence; J3 the count follows the sentences; J4 no local identity read for an unreported identity.

## Per-element receipts

### J1: the reported test. Axis: only a reported identity (a dict) can be told it has none

- **Neutralization applied.** In `judge`, `identity_reported = isinstance(obj.get(IDENTITY_FIELD), dict)` changed to `identity_reported = True`.
- **Node.** `CCI::test_the_fallback_line_never_says_there_is_no_identity`
- **Where the red landed.** On the `"has no git identity" not in result["message"]` assertion: the fallback line's message carried the old sentence and the variables fix.
- **Existing detectors.** The three tests updated in this order (`test_judge_fails_on_identity_when_the_report_has_none`, `test_judge_fails_on_identity_when_it_is_null`, `test_judge_fails_on_identity_when_it_is_not_a_dict`) are the existing detectors that also go red under J1, because under J1 their unreported identity gets the old first paragraph and each asserts the unreported one. This sentence is from the order's reasoning; those three nodes were not run under J1 in this dispatch.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_the_fallback_line_never_says_there_is_no_identity ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-33/test_the_fallback_line_never_s0')

    def test_the_fallback_line_never_says_there_is_no_identity(tmp_path):
        local, _cloud = _pair(tmp_path)
        result = _judge(local, CC._fallback_line(NONCE))
        # axis: a session that reported no identity is never told it has none, nor given the variables fix
        assert "identity" in result["failedParts"]
>       assert "has no git identity" not in result["message"]
E       assert 'has no git identity' not in '**The check...heck again".'
E         
E         'has no git identity' is contained here:
E           d session has no git identity to commit with, so a build there would stop at its first commit.
E         ?           +++++++++++++++++++
E           
E           Cloud builds stay off. To fix it, run /remote-env in Claude Code and pick this project's environment again, then run the pass command and paste the block into that environment, then paste the new setup text into the environment, then paste a fresh pass into the environment, then set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to `Test User`, and GIT_AUTHOR_EMAIL and GIT_COMMITTER_EMAIL to `test@example.invalid`, in the environment's variables and say "check again".

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:226: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_the_fallback_line_never_says_there_is_no_identity
1 failed in 4.67s
```

- **Restore.** The inverse Edit; quoted from `cloud_check.py` after the restore:

```
622:    identity_reported = isinstance(obj.get(IDENTITY_FIELD), dict)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 5.26s
```

### J2: the sole-part sentence. Axis: an unreported identity that is the only failed part is named as unreported

- **Neutralization applied.** In `_failed_message`, the branch `if parts == ["identity"]:` with its `sentences.append(_IDENTITY_UNREPORTED)` deleted, leaving the `continue`.
- **Node.** `CCI::test_an_unreported_identity_alone_says_it_was_not_reported`
- **Where the red landed.** On the exact-message assertion: the first paragraph read `The check failed on 0 parts.` with no sentence.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_an_unreported_identity_alone_says_it_was_not_reported __________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-35/test_an_unreported_identity_al0')

    def test_an_unreported_identity_alone_says_it_was_not_reported(tmp_path):
        local, cloud = _pair(tmp_path)
        result = _judge(local, _unreported(cloud))
        # axis: an unreported identity that is the only failed part is named as unreported, with the
        # setup-text fix
        assert result["failedParts"] == ["identity"]
>       assert result["message"] == (
            "**The check failed on one part.** The cloud session did not report its git identity.\n\n"
            "Cloud builds stay off. To fix it, paste the new setup text into the environment and say "
            "\"check again\".")
E       assert '**The check ...check again".' == '**The check ...check again".'
E         
E         - **The check failed on one part.** The cloud session did not report its git identity.
E         + **The check failed on 0 parts.** 
E           
E           Cloud builds stay off. To fix it, paste the new setup text into the environment and say "check again".

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:247: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_an_unreported_identity_alone_says_it_was_not_reported
1 failed in 5.21s
```

- **Restore.** The inverse Edit; quoted from `cloud_check.py` after the restore:

```
563-            # an unreported identity is named only when it is the one part that failed
564-            if parts == ["identity"]:
565:                sentences.append(_IDENTITY_UNREPORTED)
566-            continue
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.40s
```

### J3: the count follows the sentences. Axis: the count always matches what the message lists

- **Neutralization applied.** In `_failed_message`, `count = "one part" if len(sentences) == 1 else "%d parts" % len(sentences)` changed back to use `len(parts)`.
- **Node.** `CCI::test_an_older_report_without_identity_never_says_there_is_no_identity`
- **Where the red landed.** On the first-paragraph assertion: `2 parts` where `one part` is expected.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_an_older_report_without_identity_never_says_there_is_no_identity _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-37/test_an_older_report_without_i0')

    def test_an_older_report_without_identity_never_says_there_is_no_identity(tmp_path):
        local, cloud = _pair(tmp_path)
        result = _judge(local, _unreported(cloud, pluginVersion="0.0.1"))
        # axis: the count follows the sentences listed, so an unreported identity beside another part
        # adds neither a sentence, a fix nor a part to the count
        assert result["failedParts"] == ["version", "identity"]
>       assert result["message"].split("\n\n")[0] == (
            "**The check failed on one part.** The cloud's plugin is 0.0.1 and mine is %s." % VERSION)
E       AssertionError: assert '**The check ...ne is 0.44.0.' == '**The check ...ne is 0.44.0.'
E         
E         - **The check failed on one part.** The cloud's plugin is 0.0.1 and mine is 0.44.0.
E         ?                       ^^^
E         + **The check failed on 2 parts.** The cloud's plugin is 0.0.1 and mine is 0.44.0.
E         ?                       ^     +

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:236: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_an_older_report_without_identity_never_says_there_is_no_identity
1 failed in 1.47s
```

- **Restore.** The inverse Edit; quoted from `cloud_check.py` after the restore:

```
570:    count = "one part" if len(sentences) == 1 else "%d parts" % len(sentences)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.20s
```

### J4: no spawn. Axis: an identity the session never reported spawns no git process on the owner's machine

- **Neutralization applied.** In `judge`, the `_local_identity` guard `if "identity" in failed and identity_reported` changed to `if "identity" in failed`.
- **Node.** `CCI::test_an_unreported_identity_spawns_no_local_identity_read`
- **Where the red landed.** On `assert calls == []`: `_local_identity` was called once with the local repository.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_an_unreported_identity_spawns_no_local_identity_read ___________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_an_unreported_identity_sp0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f8af3198530>

    def test_an_unreported_identity_spawns_no_local_identity_read(tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(CC, "_local_identity", lambda cwd: calls.append(cwd))
        local, cloud = _pair(tmp_path)
        result = _judge(local, _unreported(cloud))
        # axis: an identity the session never reported spawns no git process on the owner's machine
        assert result["failedParts"] == ["identity"]
>       assert calls == []
E       AssertionError: assert ['/tmp/claude...0/local/repo'] == []
E         
E         Left contains one more item: '/tmp/claude-0/pytest-of-root/pytest-39/test_an_unreported_identity_sp0/local/repo'
E         Use -v to get more diff

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:260: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_an_unreported_identity_spawns_no_local_identity_read
1 failed in 1.28s
```

- **Restore.** The inverse Edit; quoted from `cloud_check.py` after the restore:

```
664:                       if "identity" in failed and identity_reported else {}))}
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.34s
```
