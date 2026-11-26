# Bite-proof record: #2651 the cloud builder's terminal comment stays on the issue

Detector under proof: `plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py`.
Guarded code: `plugins/superheroes/lib/cloud_builder.py` (`terminal_text`), unchanged by the order that re-ran this record.
Base: `2f804e8ba99f5f3f050c91e9398d85b5e7519517`. Declared guarded-element set: the two below (one neutralization and
one red each, no grouping): (1) the `also_on` check, (2) the `target` key. The doc pins in the same test file are
literal-presence pins and declare no bite-proof. Both were re-run against the current `cloud_builder.py`; the
entries below replace the earlier ones. Every neutralization was one targeted edit made with the Edit tool, undone by
the inverse Edit, each Edit and each run in its own tool call. No `git checkout`, `restore`, `reset` or `stash` was
used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py -q -p no:cacheprovider -k "<selector>"`.
The selector differs per run and is named in each entry. Captures are raw pytest output (the `UV_NATIVE_TLS`
warning line kept) unless an entry says otherwise. Nothing is redacted (no secrets, only a fixture URL for a
made-up repository). The red runs exit 1 by design. The production sites cite this record with `# axis:` comments.
The restore receipt for each entry is the restored line quoted; after both restores `git diff --stat --
plugins/superheroes/lib/cloud_builder.py` printed nothing.

Disclosures:
- Element 2's first restore attempt failed: the Edit tool refused the inverse edit because the line
  `    return {"ok": True, "comment": comment}` occurs five times in the file, so the neutralization stayed in the tree
  and the run that followed (issued in the same step as the failed edit) was red. Its raw output was
  `F`, `KeyError: 'target'` at `test_cloud_builder_also_on_2651.py:28`, `1 failed, 18 deselected in 0.24s`: the same
  output as the red below, so the failed restore was caught at once. The restore was redone with the preceding
  comment line as an anchor and the green below is the run after it. That is one run more than the budget's 24
  bite-proof runs.
- Element 1's red capture is incomplete: the tool that ran it cut 5194 characters out of the middle of the output
  (its own marker is kept below). The six blocks shown by name in the summary and the closing `9 failed` line are intact.

## 1. The `also_on` check in `terminal_text` (`cloud_builder.py:681`)

- **Axis:** `also_on` is exactly one pull request comment permalink, with nothing before, after or around it. Anything else is refused `also-on-invalid`.
- **Neutralization:** `    if also_on is not None and (comment_permalink(also_on) or (None, None))[1] != "pull":` became `    if False:`.
- **Raw red, incomplete** (`-k "row3_an_also_on"`; all nine parametrizations red). Only the first failure block is kept here in full. The other eight repeat it word for word with their own `bad = ...` value and are shortened to the summary lines, about 5 KiB elided by me, on top of the 5194 characters the tool cut from its own copy:

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFFFFF                                                                [100%]
=================================== FAILURES ===================================
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/issues/5#issuecomment-1] _

bad = 'https://github.com/acme/widgets/issues/5#issuecomment-1'

    @pytest.mark.parametrize("bad", [
        "https://github.com/acme/widgets/issues/5#issuecomment-1",
        "https://github.com/acme/widgets/pull/42",
        PR_COMMENT + " " + PR_COMMENT,
        PR_COMMENT + "\nand more text",
        "https://example.com/acme/widgets/pull/42#issuecomment-1234567",
        "",
        "https://github.com/acme/../pull/42#issuecomment-1",
        "https://github.com/./widgets/pull/42#issuecomment-1",
        "https://github.com/acme/widgets/pull/42#issuecomment-0",
    ])
    def test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused(bad):
>       assert cb.terminal_text("park", "Waiting.", also_on=bad) == {"ok": False, "reason": "also-on-invalid"}
E       AssertionError: assert {'ok': True, ...get': 'issue'} == {'ok': False,...o-on-invalid'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 2 more items:
E         {'comment': 'Builder park (cloud build).\n'
E                     '\n'
E                     'Waiting.\n'...
E         
E         ...Full output truncated, use '-vv' to show

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py:53: AssertionError
(blocks 2 to 9: the same failure, for the eight other `bad` values)

... [5194 characters truncated] ...

=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/issues/5#issuecomment-1]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[bad2]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42#issuecomment-1234567\nand more text]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://example.com/acme/widgets/pull/42#issuecomment-1234567]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/../pull/42#issuecomment-1]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/./widgets/pull/42#issuecomment-1]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42#issuecomment-0]
9 failed, 10 deselected in 0.29s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if also_on is not None and (comment_permalink(also_on) or (None, None))[1] != "pull":` (a `grep -n "if False\|if also_on is not None and"` printed line 681 only).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.........                                                                [100%]
9 passed, 10 deselected in 0.30s
```

## 2. The `target` key (`terminal_text`, `cloud_builder.py:691`)

- **Axis:** every composed terminal comment names its one target, the build's issue, in the result.
- **Neutralization:** `    return {"ok": True, "comment": comment, "target": "issue"}` became `    return {"ok": True, "comment": comment}`.
- **Raw red** (`-k "row1_the_comment"`):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
F                                                                        [100%]
=================================== FAILURES ===================================
___ test_row1_the_comment_without_also_on_is_unchanged_and_targets_the_issue ___

    def test_row1_the_comment_without_also_on_is_unchanged_and_targets_the_issue():
        result = cb.terminal_text("handback", "Done.")
        assert result["ok"] is True
>       assert result["target"] == "issue"
               ^^^^^^^^^^^^^^^^
E       KeyError: 'target'

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py:28: KeyError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row1_the_comment_without_also_on_is_unchanged_and_targets_the_issue
1 failed, 18 deselected in 0.24s
```

- **Restore:** inverse Edit, second attempt (see the disclosure above), anchored on the preceding comment line. **Restore receipt:** the restored line, `    return {"ok": True, "comment": comment, "target": "issue"}` (a `grep -n "\"target\": \"issue\""` printed line 691 only).
- **Raw green** (same selector, after the completed restore):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 18 deselected in 0.21s
```
