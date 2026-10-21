# #2017 WO-3 bite-proof: one identity test for the launch ruling and the cloud check, the filled-in fix line

Bite-proof record for `plugins/superheroes/lib/launch_doctrine.py` (`git_identity`, `RULING_TEXT["git-identity"]`), `plugins/superheroes/lib/cloud_check.py` (`_failed_message`, `_write_failed_check`, `_local_identity`) and `plugins/superheroes/lib/cloud_setup_text.py` (`_script`). Detectors: `LDT` = `plugins/superheroes/lib/tests/test_launch_doctrine.py`, `CCI` = `plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py`.

**Status.** The implementer ran every proof (H1 to H6): each neutralization is one targeted Edit, the red is the single named node run alone, the restore is the inverse Edit, and the green is the same node. Reds and greens below are the full pytest output of each run; the one deprecation warning pytest's launcher prints first (`warning: The UV_NATIVE_TLS environment variable is deprecated ...`) is left out of each capture and is the same in all twelve. Absolute `tmp_path` prefixes are as printed. No fixture holds a real secret (the fixture email is `owner@example.invalid`), so nothing is redacted.

- **Run command.** `scripts/pinned-python -B -X pycache_prefix=/tmp/sh-pyc -m pytest "<file>::<node>" -q`.
- **Restore receipt, every element.** The restored lines are quoted back from the file after the inverse Edit (H1 to H5 by a `grep -n` over the file; H6 by a content search for the restored phrase).
- **Pinned condition.** The `git_identity` and `_local_identity` tests run the real `git` against a `git init` repository under `tmp_path`, with `HOME` under `tmp_path`, `GIT_CONFIG_GLOBAL` at `os.devnull`, `GIT_CONFIG_NOSYSTEM=1` and the four `GIT_AUTHOR_*`/`GIT_COMMITTER_*` variables and `EMAIL` removed. The pin makes unobservable: git's guess from the host name and the passwd entry (only the `$EMAIL` guess is exercised; the other two are refused by the same `user.useConfigOnly` switch), and any git other than the one on this machine.

## Declared guarded-element set

H1 `git_identity` honours the four variables; H2 the guess refusal in `git_identity`; H3 the filled-in fix line; H4 the owner's email is not stored; H5 the setup text writes no `git config` step; H6 the ruling text pin.

## Per-element receipts

### H1: `git_identity` honours the four variables. Axis: a builder whose identity comes only from the four variables does not park

- **Neutralization applied.** In `launch_doctrine.git_identity`, `env={"PATH": os.environ.get("PATH", "")}` added as a keyword of the `subprocess.run` call, so git no longer sees the variables.
- **Node.** `LDT::test_git_identity_is_true_on_a_variables_only_environment`
- **Where the red landed.** On the assertion: both flags false, expected both true.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________ test_git_identity_is_true_on_a_variables_only_environment ___________

identity_repo = '/tmp/claude-0/pytest-of-root/pytest-16/test_git_identity_is_true_on_a0/identity-repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f5dbdea5910>

    def test_git_identity_is_true_on_a_variables_only_environment(identity_repo, monkeypatch):
        for var, value in zip(_IDENTITY_VARS, ("A", "a@example.invalid", "C", "c@example.invalid")):
            monkeypatch.setenv(var, value)
        # axis: a builder whose identity comes only from the four variables does not park
>       assert LD.git_identity(identity_repo) == {"author": True, "committer": True}
E       AssertionError: assert {'author': Fa...itter': False} == {'author': Tr...mitter': True}
E         
E         Differing items:
E         {'author': False} != {'author': True}
E         {'committer': False} != {'committer': True}
E         Use -v to get more diff

/home/user/wt-2017/plugins/superheroes/lib/tests/test_launch_doctrine.py:599: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_git_identity_is_true_on_a_variables_only_environment
1 failed in 3.30s
```

- **Restore.** The inverse Edit removed the keyword; quoted from `launch_doctrine.py` after the restore:

```
144-        try:
145-            got = subprocess.run(["git", "-c", "user.useConfigOnly=true", "var", var], cwd=cwd,
146:                                 capture_output=True, text=True, timeout=10)
147-            found[role] = got.returncode == 0
```

- **Green.**

```
.                                                                        [100%]
1 passed in 11.55s
```

### H2: the guess refusal in `git_identity`. Axis: an identity git would guess (from `$EMAIL`) never counts

- **Neutralization applied.** In `launch_doctrine.git_identity`, `"-c", "user.useConfigOnly=true", ` removed from the argv.
- **Node.** `LDT::test_git_identity_is_false_when_only_EMAIL_is_set`
- **Where the red landed.** On the assertion: both flags true from the guessed `$EMAIL` identity, expected both false.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_git_identity_is_false_when_only_EMAIL_is_set _______________

identity_repo = '/tmp/claude-0/pytest-of-root/pytest-18/test_git_identity_is_false_whe0/identity-repo'
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7fd106e3d820>

    def test_git_identity_is_false_when_only_EMAIL_is_set(identity_repo, monkeypatch):
        monkeypatch.setenv("EMAIL", "guess@example.invalid")
        # axis: an identity git would guess (from $EMAIL) never counts
>       assert LD.git_identity(identity_repo) == {"author": False, "committer": False}
E       AssertionError: assert {'author': Tr...mitter': True} == {'author': Fa...itter': False}
E         
E         Differing items:
E         {'committer': True} != {'committer': False}
E         {'author': True} != {'author': False}
E         Use -v to get more diff

/home/user/wt-2017/plugins/superheroes/lib/tests/test_launch_doctrine.py:618: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_git_identity_is_false_when_only_EMAIL_is_set
1 failed in 0.26s
```

- **Restore.** The inverse Edit put the switch back; quoted from `launch_doctrine.py` after the restore:

```
145:            got = subprocess.run(["git", "-c", "user.useConfigOnly=true", "var", var], cwd=cwd,
```

- **Green.**

```
.                                                                        [100%]
1 passed in 0.25s
```

### H3: the filled-in fix line. Axis: the fix line names the name and email this machine resolves

- **Neutralization applied.** In `cloud_check._failed_message`, the identity fix's `format` call replaced with `fix = fix.format(name="your name", email="your email")` (always the placeholders).
- **Node.** `CCI::test_judge_message_names_the_local_identity_in_the_fix` (the order's n1)
- **Where the red landed.** On the message assertion: the message ends with "to your email", not the backticked `Owner`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_judge_message_names_the_local_identity_in_the_fix ____________

repo = '/tmp/claude-0/pytest-of-root/pytest-20/test_judge_message_names_the_l0/identity-repo'
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-20/test_judge_message_names_the_l0')

    def test_judge_message_names_the_local_identity_in_the_fix(repo, tmp_path):
        local, cloud = _pair(tmp_path)
        _local_config(local.cwd)
        result = _judge(local, _with_identity(cloud, NEITHER))
        # axis: the fix line names the name and email this machine resolves, set off in backticks
        _failed_on_identity(result)
>       assert "set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to `Owner`" in result["message"]
E       assert 'set GIT_AUTHOR_NAME and GIT_COMMITTER_NAME to `Owner`' in '**The check failed on one part.** The cloud session has no git identity to commit with, so a build there would stop a...me, and GIT_AUTHOR_EMAIL and GIT_COMMITTER_EMAIL to your email, in the environment\'s variables and say "check again".'

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:240: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_judge_message_names_the_local_identity_in_the_fix
1 failed in 1.44s
```

- **Restore.** The inverse Edit put the conditional values back; quoted from `cloud_check.py` after the restore:

```
567:            fix = fix.format(
568-                name="your name" if identity is None else "`%s`" % identity[0],
569-                email="your email" if identity is None else "`%s`" % identity[1])
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.26s
```

### H4: the owner's email is not stored. Axis: the email appears in no file of the store or of the root, the marker included

- **Neutralization applied.** In `cloud_check._write_failed_check`, one entry added to the `marker` dict: `"email": (_local_identity(cwd) or ("", ""))[1],`.
- **Node.** `CCI::test_the_owner_email_is_stored_in_no_file` (the order's n3)
- **Where the red landed.** On the file walk: the failed-check marker file holds `"email": "owner@example.invalid"`.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_the_owner_email_is_stored_in_no_file ___________________

repo = '/tmp/claude-0/pytest-of-root/pytest-22/test_the_owner_email_is_stored0/identity-repo'
tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-22/test_the_owner_email_is_stored0')

    def test_the_owner_email_is_stored_in_no_file(repo, tmp_path):
        local, cloud = _pair(tmp_path)
        _local_config(local.cwd)
        result = _judge(local, _with_identity(cloud, NEITHER))
        assert EMAIL in result["message"]
        marker = CC.read_failed_check(local.cwd, ACCOUNT, local.root)
        assert marker is not None and "identity" in marker["failedParts"]
        store = mode_registry.project_store_dir(local.cwd, local.root)
        files = list(_files_under(store, local.root))
        assert any(path.endswith(CC.FAILED_CHECK_SUFFIX) for path in files)
        # axis: not stored: the email appears in no file of the store or of the root, marker included
        for path in files:
            with open(path, "rb") as fh:
>               assert EMAIL.encode() not in fh.read(), path
E               AssertionError: /tmp/claude-0/pytest-of-root/pytest-22/test_the_owner_email_is_stored0/local/store-root/projects/238a7b644f5fb344/state/cloud-setup/7326bd603efe1013.failed-check.json
E               assert b'owner@example.invalid' not in b'{\n  "account": "acct-fixture-one",\n  "email": "owner@example.invalid",\n  "environment": "env_01ABCdef",\n  "failedAt": "2026-10-10T12:00:00Z",\n  "failedParts": [\n    "identity"\n  ],\n  "schema": "cloud-check-failed/1"\n}\n'
E                +  where b'owner@example.invalid' = <built-in method encode of str object at 0x7ff3f8184670>()
E                +    where <built-in method encode of str object at 0x7ff3f8184670> = 'owner@example.invalid'.encode
E                +  and   b'{\n  "account": "acct-fixture-one",\n  "email": "owner@example.invalid",\n  "environment": "env_01ABCdef",\n  "failedAt": "2026-10-10T12:00:00Z",\n  "failedParts": [\n    "identity"\n  ],\n  "schema": "cloud-check-failed/1"\n}\n' = <built-in method read of _io.BufferedReader object at 0x7ff3f79a9850>()
E                +    where <built-in method read of _io.BufferedReader object at 0x7ff3f79a9850> = <_io.BufferedReader name='/tmp/claude-0/pytest-of-root/pytest-22/test_the_owner_email_is_stored0/local/store-root/projects/238a7b644f5fb344/state/cloud-setup/7326bd603efe1013.failed-check.json'>.read

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:266: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_the_owner_email_is_stored_in_no_file
1 failed in 1.27s
```

- **Restore.** The inverse Edit removed the entry; quoted from `cloud_check.py` after the restore:

```
503:            marker = {"schema": FAILED_CHECK_SCHEMA, "account": account, "environment": environment,
504-                      "failedAt": _utc_stamp(now),
505-                      "failedParts": list(failed_parts)}
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.28s
```

### H5: the setup text writes no `git config` step. Axis: no step

- **Neutralization applied.** In `cloud_setup_text._script`, one line `"git config user.name x",` added to the `out` list after `"#!/bin/bash",`.
- **Node.** `CCI::test_the_setup_text_writes_no_git_config_step` (the order's n4)
- **Where the red landed.** On the assertion: `git config` is in the composed text.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
________________ test_the_setup_text_writes_no_git_config_step _________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-24/test_the_setup_text_writes_no_0')

    def test_the_setup_text_writes_no_git_config_step(tmp_path):
        local, _cloud = _pair(tmp_path)
        got = cloud_setup_text.compose(
            local.cwd, now=1760097600.0, stamp_fn=lambda files: "2026-10-10:" + "0" * 12,
            plugin_source="https://github.com/acme/superheroes.git",
            plugin_commit="0123456789abcdef" * 2 + "01234567", plugin_subdir="plugins/superheroes",
            project_name="Corner Shop", root=local.root, env=local.env,
            source_dir=str(tmp_path / "opt" / "src"), plugin_dir=str(tmp_path / "opt" / "plugin"))
        assert got["action"] == "written", got
        # axis: no step: the setup text carries no `git config` line, so the identity is never written
>       assert "git config" not in got["text"]
E       assert 'git config' not in '#!/bin/bash...G"\nexit 0\n'
E         
E         'git config' is contained here:
E           #!/bin/bash
E           git config user.name x
E           # Corner Shop · plugin 0.44.0 · calibration from 10 Oct
E           # Setup text for a cloud environment: paste it over the whole setup-script field.
E           # It holds no reviewer pass and no other secret....
E         
E         ...Full output truncated (106 lines hidden), use '-vv' to show

/home/user/wt-2017/plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py:279: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_check_identity_2017.py::test_the_setup_text_writes_no_git_config_step
1 failed in 1.16s
```

- **Restore.** The inverse Edit removed the line; quoted from `cloud_setup_text.py` after the restore:

```
478-    parent = os.path.dirname(plugin_dir.rstrip("/"))
479-    out = [
480-        "#!/bin/bash",
481-        "# " + head,
482-        "# Setup text for a cloud environment: paste it over the whole setup-script field.",
```

- **Green.**

```
.                                                                        [100%]
1 passed in 1.21s
```

### H6: the ruling text pin. Axis: the `git-identity` ruling text is the one the artifact and the doctrine's parser agree on

- **Neutralization applied.** In `RULING_TEXT["git-identity"]`, `failing` changed to `empty` (`` `GIT_COMMITTER_IDENT` empty, never ``).
- **Node.** `LDT::test_git_identity_ruling_is_delivered_with_its_prohibitions`
- **Where the red landed.** On its first assertion, `parsed["ok"] is True`: `parse` refuses the doctrine because the artifact's text no longer equals `RULING_TEXT["git-identity"]`, so the test goes red before it reaches the pinned literal. The pinned literal itself is not what went red here; it is reached only when the constant and the artifact change together.
- **Red:**

```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_git_identity_ruling_is_delivered_with_its_prohibitions __________

    def test_git_identity_ruling_is_delivered_with_its_prohibitions():
        parsed = LD.parse(_read_doctrine())
>       assert parsed["ok"] is True
E       assert False is True

/home/user/wt-2017/plugins/superheroes/lib/tests/test_launch_doctrine.py:555: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launch_doctrine.py::test_git_identity_ruling_is_delivered_with_its_prohibitions
1 failed in 0.31s
```

- **Restore.** The inverse Edit put `failing` back; quoted from `launch_doctrine.py` after the restore:

```
76:        "`GIT_COMMITTER_IDENT` failing, never an empty `git config` answer alone — "
```

- **Green.**

```
.                                                                        [100%]
1 passed in 0.23s
```
