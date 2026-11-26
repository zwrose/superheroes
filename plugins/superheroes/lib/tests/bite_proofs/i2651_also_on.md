# Bite-proof record: #2651 the cloud builder's terminal comment stays on the issue

Detector under proof: `plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py`.
Guarded code: `plugins/superheroes/lib/cloud_builder.py` (`terminal_text`).
Declared guarded-element set: the two below (one neutralization and one red each, no grouping): (1) the
`also_on` full-match validation, (2) the `target` key. The doc pins in the same test file are literal-presence
pins and declare no bite-proof. Every neutralization was one targeted edit made with the Edit tool, undone by
the inverse Edit before the next element, each Edit and each run in its own tool call. No `git checkout`,
`restore`, `reset` or `stash` was used. Command prefix for every run below (worktree root):
`timeout 900 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py -q -p no:cacheprovider -k "<selector>"`.
The selector differs per run and is named in each entry. Captures are raw pytest output (the `UV_NATIVE_TLS`
warning line kept); in element 1's red the pytest "Full output truncated, use '-vv' to show" lines are pytest's
own. Nothing is redacted (no secrets, only a fixture URL for a made-up repository). Each capture is under 32 KiB.
The red runs exit 1 by design. The production sites cite this record with `# axis:` comments.
The restore receipt for each entry is the restored line quoted; the worktree carries uncommitted work, so a
whole-file `git diff` is not empty and is not the receipt.

## 1. The `also_on` full-match validation (`terminal_text`, `cloud_builder.py:665`)

- **Axis:** `also_on` is exactly one pull request comment permalink, with nothing before, after or around it. Anything else is refused `also-on-invalid`.
- **Neutralization:** `if also_on is not None and not (isinstance(also_on, str) and _PR_COMMENT_URL_RE.fullmatch(also_on)):` became `if False and also_on is not None and not (isinstance(also_on, str) and _PR_COMMENT_URL_RE.fullmatch(also_on)):`.
- **Raw red** (`-k "row3_an_also_on"`; all six parametrizations red):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
FFFFFF                                                                   [100%]
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

/home/user/superheroes/.claude/worktrees/b2651/plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py:50: AssertionError
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42] _
(the same failure, for the input 'https://github.com/acme/widgets/pull/42')
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[bad2] _
(the same failure, for the two URLs separated by a space)
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42#issuecomment-1234567\nand more text] _
(the same failure, for a URL followed by a newline and text)
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://example.com/acme/widgets/pull/42#issuecomment-1234567] _
(the same failure, for a non-github host)
_ test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[] _
(the same failure, for the empty string)
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/issues/5#issuecomment-1]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[bad2]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://github.com/acme/widgets/pull/42#issuecomment-1234567\nand more text]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[https://example.com/acme/widgets/pull/42#issuecomment-1234567]
FAILED plugins/superheroes/lib/tests/test_cloud_builder_also_on_2651.py::test_row3_an_also_on_that_is_not_one_pull_request_comment_permalink_is_refused[]
6 failed, 9 deselected in 0.29s
```

The five other failure blocks in the capture repeat the first block's traceback word for word with their own
`bad = ...` value. They are shortened to one line each here: about 5 KiB elided, all six inputs shown above by
name and by the summary lines.

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    if also_on is not None and not (isinstance(also_on, str) and _PR_COMMENT_URL_RE.fullmatch(also_on)):`; a search of `cloud_builder.py` for `if False` finds nothing.
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
......                                                                   [100%]
6 passed, 9 deselected in 5.85s
```

## 2. The `target` key (`terminal_text`, `cloud_builder.py:675`)

- **Axis:** every composed terminal comment names its one target, the build's issue, in the result.
- **Neutralization:** `return {"ok": True, "comment": comment, "target": "issue"}` became `return {"ok": True, "comment": comment}`.
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
1 failed, 14 deselected in 0.24s
```

- **Restore:** inverse Edit. **Restore receipt:** the restored line, `    return {"ok": True, "comment": comment, "target": "issue"}`, which a search of `cloud_builder.py` for `"target": "issue"` finds once (line 675).
- **Raw green** (same selector):

```
warning: The `UV_NATIVE_TLS` environment variable is deprecated and will be removed in a future release. Use `UV_SYSTEM_CERTS` instead.
.                                                                        [100%]
1 passed, 14 deselected in 0.23s
```
