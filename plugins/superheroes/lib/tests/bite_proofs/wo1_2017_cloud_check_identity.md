# #2017 WO-1 bite-proof: the cloud check judges a git commit identity (`cloud_check.py`)

Bite-proof record for `plugins/superheroes/lib/cloud_check.py` (`_git_identity`, `report`, `_judge_parts`, `judge`), detectors in `plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py` (`T`).

**Status.** The implementer ran every proof (G1 to G5): each neutralization is a targeted Edit in `cloud_check.py`, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run; the one deprecation warning pytest's launcher prints first (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`) is left out of each capture and is the same in all ten. Absolute `tmp_path` prefixes are as printed. No fixture holds a real secret (the fixture email is `owner@example.invalid`), so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc -m pytest "<T>::<node>" -q`.
- **Restore receipt, every element.** The restored line is quoted back from the file after the inverse Edit.
- **Pinned condition.** The judgment tests use the fixture projects of `test_cloud_check` and write the identity into the report object, so the real `git` is not run there. The `_git_identity` tests run the real `git` against a `git init` repository under `tmp_path`, with `HOME` under `tmp_path`, `GIT_CONFIG_GLOBAL` at `os.devnull`, `GIT_CONFIG_NOSYSTEM=1` and the four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` variables and `EMAIL` removed. The pin makes unobservable: git's guess from the host name and the passwd entry (only the `$EMAIL` guess is exercised; the other two are refused by the same `user.useConfigOnly` switch), and any git older or newer than the one on this machine.

## Declared guarded-element set

G1 the judge's identity part; G2 the author requirement; G3 the committer requirement; G4 the refusal of a guessed identity; G5 the failed-part wiring.

## Per-element receipts

### G1: the judge's identity part: `identity_ok` in `_judge_parts`. Axis: the cloud session must resolve a configured author and committer identity

- **Neutralization applied.** `identity_ok = (isinstance(identity, dict) and identity.get("author") is True and identity.get("committer") is True)` (two lines) replaced with `identity_ok = True`.
- **Node.** `T::test_judge_fails_on_identity_when_the_report_has_none`
- **Where the red landed.** On `action`: `passed`, not `failed`, for a report with no identity key.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_judge_fails_on_identity_when_the_report_has_none _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-2/test_judge_fails_on_identity_w0')

    def test_judge_fails_on_identity_when_the_report_has_none(tmp_path):
        local, cloud = _pair(tmp_path)
        obj = _cloud_report(cloud)
        del obj[CC.IDENTITY_FIELD]
        # axis: a report without an identity key does not show a configured identity
>       _failed_on_identity(_judge(local, obj))

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:150: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}

    def _failed_on_identity(result):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_judge_fails_on_identity_when_the_report_has_none
1 failed in 1.51s
```

- **Restore.** The inverse Edit put the lines back; quoted from `cloud_check.py` after the restore:

```
447:    identity_ok = (isinstance(identity, dict) and identity.get("author") is True
448-                   and identity.get("committer") is True)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 4.97s
```

### G2: the author requirement: `identity.get("author") is True` in `_judge_parts`. Axis: the author identity must be exactly true

- **Neutralization applied.** `identity.get("author") is True` replaced with `True`.
- **Node.** `T::test_judge_fails_on_identity_without_an_author`
- **Where the red landed.** On the first case of the loop (`author` false, `committer` true): `action` was `passed`, not `failed`. The other four cases (`"true"`, `1`, `None`, key missing) are guarded by the same expression and are reached only after that first assertion, so their own reds were not observed separately.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_judge_fails_on_identity_without_an_author ________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-4/test_judge_fails_on_identity_w0')

    def test_judge_fails_on_identity_without_an_author(tmp_path):
        local, cloud = _pair(tmp_path)
        for author in (False, "true", 1, None, "missing"):
            identity = {"committer": True}
            if author != "missing":
                identity["author"] = author
            # axis: the author identity must be exactly true
>           _failed_on_identity(_judge(local, _with_identity(cloud, identity)))

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:181: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}

    def _failed_on_identity(result):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_judge_fails_on_identity_without_an_author
1 failed in 7.17s
```

- **Restore.** The inverse Edit put the expression back; quoted from `cloud_check.py` after the restore:

```
447:    identity_ok = (isinstance(identity, dict) and identity.get("author") is True
448-                   and identity.get("committer") is True)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.80s
```

### G3: the committer requirement: `identity.get("committer") is True` in `_judge_parts`. Axis: the committer identity must be exactly true

- **Neutralization applied.** `identity.get("committer") is True` replaced with `True`.
- **Node.** `T::test_judge_fails_on_identity_without_a_committer`
- **Where the red landed.** On the first case of the loop (`committer` false, `author` true): `action` was `passed`, not `failed`. The other four cases (`"true"`, `1`, `None`, key missing) are guarded by the same expression and are reached only after that first assertion, so their own reds were not observed separately.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_judge_fails_on_identity_without_a_committer _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-6/test_judge_fails_on_identity_w0')

    def test_judge_fails_on_identity_without_a_committer(tmp_path):
        local, cloud = _pair(tmp_path)
        for committer in (False, "true", 1, None, "missing"):
            identity = {"author": True}
            if committer != "missing":
                identity["committer"] = committer
            # axis: the committer identity must be exactly true
>           _failed_on_identity(_judge(local, _with_identity(cloud, identity)))

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:171: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}

    def _failed_on_identity(result):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_judge_fails_on_identity_without_a_committer
1 failed in 1.54s
```

- **Restore.** The inverse Edit put the expression back; quoted from `cloud_check.py` after the restore:

```
447:    identity_ok = (isinstance(identity, dict) and identity.get("author") is True
448-                   and identity.get("committer") is True)
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.99s
```

### G4: the refusal of a guessed identity: `-c user.useConfigOnly=true` in `_git_identity`'s argv. Axis: refusal: an identity git guesses (from `$EMAIL`, the host name or the passwd entry) never counts

- **Neutralization applied.** `"git", "-c", "user.useConfigOnly=true", "var", var` replaced with `"git", "var", var` in the `subprocess.run` argv.
- **Node.** `T::test_git_identity_refuses_a_guess_from_EMAIL`
- **Where the red landed.** On the result: both `author` and `committer` were `True` from the guessed `$EMAIL`, not `False`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________ test_git_identity_refuses_a_guess_from_EMAIL _________________

repo = '/tmp/claude-0/pytest-of-root/pytest-8/test_git_identity_refuses_a_gu0/identity-repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f4ff6ad51f0>

    def test_git_identity_refuses_a_guess_from_EMAIL(repo, monkeypatch):
        monkeypatch.setenv("EMAIL", "guess@example.invalid")
        # axis: an identity git guesses (from $EMAIL, the host name or the passwd entry) never counts
>       assert CC._git_identity(repo) == NEITHER
E       AssertionError: assert {'author': Tr...mitter': True} == {'author': Fa...itter': False}
E         
E         Differing items:
E         {'author': True} != {'author': False}
E         {'committer': True} != {'committer': False}
E         Use -v to get more diff

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:78: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_git_identity_refuses_a_guess_from_EMAIL
1 failed in 0.73s
```

- **Restore.** The inverse Edit put the argv back; quoted from `cloud_check.py` after the restore:

```
326:            got = subprocess.run(["git", "-c", "user.useConfigOnly=true", "var", var], cwd=cwd,
```

- **Green.**

```
.                                                                        [100%]
1 passed in 0.72s
```

### G5: the failed-part wiring: the `("identity", "identityPresent")` pair in `judge`'s list. Axis: a false identity part is reported as a failed part

- **Neutralization applied.** The pair `("identity", "identityPresent")` deleted from the failed-part list, leaving `("reviewer", "reviewerAnswered")) if not results[key]]` as the last pair.
- **Node.** `T::test_judge_fails_on_identity_when_the_report_has_none`
- **Where the red landed.** On `action`: `passed`, not `failed`, although `identityPresent` was false (the part was computed and then ignored).
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_judge_fails_on_identity_when_the_report_has_none _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-10/test_judge_fails_on_identity_w0')

    def test_judge_fails_on_identity_when_the_report_has_none(tmp_path):
        local, cloud = _pair(tmp_path)
        obj = _cloud_report(cloud)
        del obj[CC.IDENTITY_FIELD]
        # axis: a report without an identity key does not show a configured identity
>       _failed_on_identity(_judge(local, obj))

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:150: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}

    def _failed_on_identity(result):
>       assert result["action"] == "failed", result
E       AssertionError: {'action': 'passed', 'results': {'versionMatches': True, 'calibrationMatches': True, 'reviewerAnswered': True, 'environmentMatches': True, ...}, 'failedParts': [], 'recordWritten': True, ...}
E       assert 'passed' == 'failed'
E         
E         - failed
E         + passed

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:62: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_judge_fails_on_identity_when_the_report_has_none
1 failed in 1.25s
```

- **Restore.** The inverse Edit put the pair back; quoted from `cloud_check.py` after the restore:

```
607:                                     ("reviewer", "reviewerAnswered"),
608-                                     ("identity", "identityPresent")) if not results[key]]
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.23s
```
