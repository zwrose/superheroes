# Bite-proof record — no bare at-sign mention in text the plugin prepares for GitHub (#2453)

Detector file: `plugins/superheroes/lib/tests/test_mention_guard.py`, unedited between every red and its green (the only edits to it in this work order are the order-named G13 test change and the order-named census test, both made before any red run). Every entry is a targeted, reversible Edit-tool edit to one production file, restored by the inverse edit (no `git checkout`, `restore`, `reset` or `stash`). Each `old_string` occurred exactly once (the Edit tool refuses a non-unique match). Runs: `timeout 120 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2453 -m pytest plugins/superheroes/lib/tests/test_mention_guard.py -q -p no:cacheprovider -k <full test function name>`, redirected whole to a file outside the repository and read back. The order named the `-k` form; each `-k` value is a full test function name, and the `N failed/passed, M deselected` line shows the selection. The `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of every capture. Longer red captures are trimmed to the first failing case and the summary; what was elided is said in the entry. No secrets, tokens, private URLs or PII appear in any capture; nothing was redacted. Pytest temp paths under `/tmp/claude-0/pytest-of-root/` are sandbox scratch.

The guarded-element set is the one the order declared: G1, G2, G3, G4, G5, G6, G7, G8, G9, G10, G11, G12, G13, G14, G15a, G15b. None is grouped. One element is not in that set and is proven as an extra, labelled **G16 (undeclared)**: the census test the order added for `vet_slot`.

Restore receipts: for a file the work order left untouched against head `85d7dfe0eac95000672704508d7fdcc6f5b077c6`, `git status --porcelain <path>` and `git diff --stat <path>` both printed nothing after the restore. For `vet_slot.py`, which carries this work order's own uncommitted task-1 edit, a clean diff against head is not possible, so the receipt is the hash of `git diff plugins/superheroes/lib/vet_slot.py` taken before the neutralization and after the restore: both `939366c6bbe151df11de206d2caaf1463457522a3b27d47706dbcdb519c48465`.

## Summary

| Element | Red detector | Red on the declared axis |
|---|---|---|
| G1 | `test_g1_a_bare_mention_is_reported` | yes, 13 of 13 rows |
| G2 | `test_healthy_rows_pass_untouched` (fenced login rows) and `test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes` | yes, after the fixture fix (see G2, Re-proof); the first run on the decorator-only fixture stayed green (vacuous, kept as history) |
| G3 | `test_healthy_rows_pass_untouched` | yes, 2 rows |
| G4 | `test_healthy_rows_pass_untouched` | yes, 2 rows (`a.b@example.com` stayed green) |
| G5 | `test_g5_wrap_never_pairs_with_an_existing_backtick` | yes |
| G6–G13 | each site's wiring test | yes |
| G14, G15a, G15b | each site's `bare_mentions(...) == []` assertion | yes |
| G16 (extra) | `test_vet_slot_emits_no_bare_mention_token_of_its_own` | yes |

## G1. The `MENTION_RE` match as reported by `bare_mentions` (`mention_guard.py:105`)

- **Axis:** a bare at-sign GitHub reads as a login is reported.
- **Detector:** `test_mention_guard.py::test_g1_a_bare_mention_is_reported` (13 flagged rows).
- **Neutralization:** `return [{"line": idx + 1, "token": token} for idx, _start, _end, token in _found(text)]` became `return []`.

**Raw red** (exit 1; first of 13 identical failures shown, the other 12 elided; all 13 fail at `test_mention_guard.py:92`, counted by grep):

```
FFFFFFFFFFFFF                                                            [100%]
=================================== FAILURES ===================================
_______________ test_g1_a_bare_mention_is_reported[ping @zwrose] _______________

text = 'ping @zwrose', tokens = ['@zwrose']

>       assert _tokens(text) == tokens
E       AssertionError: assert [] == ['@zwrose']
E         Right contains one more item: '@zwrose'

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:92: AssertionError
...
13 failed, 59 deselected in 3.73s
```

- **Restore:** inverse edit (`return []` back to the list comprehension).
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `plugins/superheroes/lib/mention_guard.py` printed nothing; `grep -n 'return \[{"line"'` printed `105:    return [{"line": idx + 1, "token": token} for idx, _start, _end, token in _found(text)]`.

**Raw green** (exit 0):

```
.............                                                            [100%]
13 passed, 59 deselected in 3.27s
```

## G2. Fence masking in `_found` (`mention_guard.py:89`)

- **Axis:** lines `md_fence` marks inert are not scanned.
- **Detector (as the order designated):** `test_healthy_rows_pass_untouched`, the fenced-decorator rows (`` ```python\n@pytest.fixture… `` and `~~~\n@pytest.fixture\n~~~`); also the G2-labelled `test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes`.
- **Neutralization:** `if inert[idx]:` became `if False:`.

**VACUOUS-PROOF FINDING (edge E1).** With fence masking neutralized, the order's designated detectors stayed **green**. Raw captures (exit 0 each):

```
..............                                                           [100%]
14 passed, 58 deselected in 2.18s          <- test_healthy_rows_pass_untouched
.                                                                        [100%]
1 passed, 71 deselected in 1.84s           <- test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes
```

Cause, measured with the neutralization still in the tree (`mg.bare_mentions`):

```
decorator, fence masking neutralized: []
plain login in same position: [{'line': 1, 'token': '@octo'}]
```

`@pytest.fixture` is never matched by `MENTION_RE`: the login `pytest` is followed by `.f`, and the lookahead accepts a dot only when it is followed by whitespace or a non-word character, or ends the line. So a fenced `@pytest.fixture` row never reaches the fence check, and the fixture does not create the condition the assertion discriminates on (the rubric's second face of vacuity). Those rows stay green whether or not fences are masked; the G2-labelled test has the same fixture and the same defect. Per the order the test was not edited.

What does bite the fence check, and is **not** the designated proof: three other tests that fence a plain login went red under the same neutralization (exit 1, run together; `test_wrap_keeps_everything_but_the_wrapped_tokens` in the same selection stayed green):

```
F.FF                                                                     [100%]
______________ test_line_numbers_are_one_based_and_in_text_order _______________
>       assert mg.bare_mentions(text) == [{"line": 2, "token": "@one"}, {"line": 6, "token": "@two"}]
E       At index 1 diff: {'line': 4, 'token': '@no'} != {'line': 6, 'token': '@two'}
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:134: AssertionError
_________ test_e3_an_unterminated_fence_makes_the_lines_after_it_inert _________
>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 3, ...en': '@octo'}] == []
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:193: AssertionError
___________ test_e5_crlf_line_endings_keep_fences_and_lines_working __________
>       assert mg.bare_mentions(fenced) == [{"line": 5, "token": "@bare"}]
E       At index 0 diff: {'line': 3, 'token': '@octo'} != {'line': 5, 'token': '@bare'}
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:205: AssertionError
3 failed, 1 passed, 68 deselected in 2.22s
```

(Assertion bodies trimmed to the decisive `E` lines; the `Left contains one more item` lines are elided.) These reds are on the right axis (a fenced login is reported when it should not be), so fence masking is bitten by the suite, but the two rows the order and the test names point at do not bite it. Recommended cure, for the orchestrator: a fenced plain-login row (`@octo`) in `HEALTHY` and in `test_g2_…`, in place of or beside the decorator; that is a test edit outside this order and was not made.

- **Restore:** inverse edit (`if False:` back to `if inert[idx]:`).
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `mention_guard.py` printed nothing; `grep -n "if inert\[idx\]:"` printed `89:        if inert[idx]:`.

**Raw green** (exit 0; the designated test, the G2-labelled test and the three biting tests together):

```
..................                                                       [100%]
18 passed, 54 deselected in 1.94s
```

**Re-proof after the fixture fix.** The two new `HEALTHY` rows (`` ```\n@octo\n``` `` and `~~~\n@octo\n~~~`) and an `@octo` line inside the fence of both texts in `test_g2_…` now create the condition the assertion discriminates on (`@octo` matches `MENTION_RE`, `@pytest.fixture` does not). The test file was not edited between the red and the green below.

- **Guarded element and axis:** fence masking in `_found` (`mention_guard.py:89`); lines `md_fence` marks inert are not scanned. Detectors: `test_healthy_rows_pass_untouched` (the two new fenced-`@octo` rows) and `test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes`.
- **Neutralization:** `if inert[idx]:` became `if False:` (targeted Edit, one occurrence).

**Raw red** (exit 1; command `timeout 120 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2453 -m pytest plugins/superheroes/lib/tests/test_mention_guard.py -q -p no:cacheprovider -k "g2 or healthy"`; the `UV_NATIVE_TLS` warning line, the second `HEALTHY` failure's `E` detail lines beyond the first two, the `Use -v to get more diff` lines and the g2 source-line echo are elided; the three failing nodes are all shown):

```
....FF..........F....                                                    [100%]
_____________ test_healthy_rows_pass_untouched[```\n@octo\n```\n] ______________
>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 2, ...en': '@octo'}] == []
E         Left contains one more item: {'line': 2, 'token': '@octo'}
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:102: AssertionError
_____________ test_healthy_rows_pass_untouched[~~~\n@octo\n~~~\n] ______________
>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 2, ...en': '@octo'}] == []
E         Left contains one more item: {'line': 2, 'token': '@octo'}
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:102: AssertionError
_________ test_g2_a_fenced_decorator_is_inert_in_backticks_and_tildes __________
>           assert mg.bare_mentions(text) == [{"line": 6, "token": "@octo"}]
E           AssertionError: assert [{'line': 4, ...en': '@octo'}] == [{'line': 6, ...en': '@octo'}]
E             At index 0 diff: {'line': 4, 'token': '@octo'} != {'line': 6, 'token': '@octo'}
E             Left contains one more item: {'line': 6, 'token': '@octo'}
/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:112: AssertionError
3 failed, 18 passed, 53 deselected in 2.37s
```

The reds are on the expected assertions: `bare_mentions(text) == []` for the two new rows, and `bare_mentions(...) == [...]` for `test_g2_…`. The two decorator rows stayed green, as before.

- **Restore:** inverse Edit (`if False:` back to `if inert[idx]:`).
- **Restore receipt:** the restored line as it reads after the restore: `89:        if inert[idx]:`. `git status --porcelain plugins/superheroes/lib/mention_guard.py` and `git diff --stat plugins/superheroes/lib/mention_guard.py`, each its own call, both printed nothing.

**Raw green** (exit 0; same command; `UV_NATIVE_TLS` warning line elided):

```
.....................                                                    [100%]
21 passed, 53 deselected in 3.79s
```

## G3. Inline code-span masking in `_found` (`mention_guard.py:93`)

- **Axis:** a mention inside an inline code span is not reported.
- **Detector:** `test_healthy_rows_pass_untouched`, the code-span rows.
- **Neutralization:** `if any(start <= m.start() < end for start, end in spans):` became `if False:`.

**Raw red** (exit 1; the second failing case elided, it has the same shape):

```
FF............                                                           [100%]
__________________ test_healthy_rows_pass_untouched[`@octo`] ___________________

text = '`@octo`'

>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 1, ...en': '@octo'}] == []
E         Left contains one more item: {'line': 1, 'token': '@octo'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:100: AssertionError
...
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_healthy_rows_pass_untouched[`@octo`]
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_healthy_rows_pass_untouched[``a ` @octo``]
2 failed, 12 passed, 58 deselected in 2.28s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `mention_guard.py` printed nothing; the Grep tool printed `93:            if any(start <= m.start() < end for start, end in spans):`.

**Raw green** (exit 0):

```
..............                                                           [100%]
14 passed, 58 deselected in 2.24s
```

## G4. The email boundary: the `(?=…)` lookahead of `MENTION_RE` (`mention_guard.py:39`)

- **Axis:** a login must end at a non-word character, not run into a dotted domain.
- **Detector:** `test_healthy_rows_pass_untouched`, the email rows.
- **Neutralization:** the regex string `r"(?:^|(?<=\W))@((?>[a-z0-9][a-z0-9-]*))(?=\.+[ \t\W]|\.+$|[^0-9a-zA-Z_.]|$)",` became `r"(?:^|(?<=\W))@((?>[a-z0-9][a-z0-9-]*))",`.

**Raw red** (exit 1). Red rows: `ops+@example.com` and `<ops+@example.com>`. `a.b@example.com` stayed green, as the order anticipated (its at-sign follows a word character). Second failing case elided (same shape):

```
.....FF.......                                                           [100%]
______________ test_healthy_rows_pass_untouched[ops+@example.com] ______________

text = 'ops+@example.com'

>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 1, ...: '@example'}] == []
E         Left contains one more item: {'line': 1, 'token': '@example'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:100: AssertionError
...
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_healthy_rows_pass_untouched[ops+@example.com]
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_healthy_rows_pass_untouched[<ops+@example.com>]
2 failed, 12 passed, 58 deselected in 1.77s
```

- **Restore:** inverse edit (lookahead put back).
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `mention_guard.py` printed nothing.

**Raw green** (exit 0):

```
..............                                                           [100%]
14 passed, 58 deselected in 1.81s
```

## G5. Wrap delimiter length (`mention_guard.py:126`)

- **Axis:** `wrap`'s delimiter is one backtick longer than any run in the text, so it cannot pair with an existing run.
- **Detector:** `test_g5_wrap_never_pairs_with_an_existing_backtick` (the broken-backtick row).
- **Neutralization:** ``ticks = "`" * (max((len(m) for m in _BACKTICK_RUN_RE.findall(text)), default=0) + 1)`` became ``ticks = "`"``.

**Raw red** (exit 1):

```
F                                                                        [100%]
______________ test_g5_wrap_never_pairs_with_an_existing_backtick ______________

    def test_g5_wrap_never_pairs_with_an_existing_backtick():
        text = "broken " + TICK + " example @893"
        wrapped = mg.wrap(text)
>       assert mg.bare_mentions(wrapped) == []
E       AssertionError: assert [{'line': 1, 'token': '@893'}] == []
E         Left contains one more item: {'line': 1, 'token': '@893'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:153: AssertionError
1 failed, 71 deselected in 1.97s
```

(The two comment lines under the `def` are elided.)

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `mention_guard.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.10s
```

## G6. `cloud_builder.post_comment` (`cloud_builder.py:487`)

- **Axis:** `post_comment` reads the body file and refuses `bare-mention` before the write.
- **Detector:** `test_g6_post_comment_refuses_a_bare_mention_before_any_gh_call`.
- **Neutralization:** `refusal = _mention_refusal(_read_text(body_path))` (the one after the "before any write" axis comment) became `refusal = None`.

**Raw red** (exit 1; the gh seam did make the write):

```
F                                                                        [100%]
>       _assert_refusal(result)

result = {'ok': True, 'reason': None, 'url': 'https://github.com/o/r/issues/1#c1', 'transit': {'transit': 'not-checked', 'why': 'the text could not be read back'}, ...}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: AssertionError
1 failed, 71 deselected in 1.91s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_builder.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.32s
```

## G7. `cloud_builder.edit_comment` (`cloud_builder.py:512`)

- **Axis:** `edit_comment` reads the body file and refuses `bare-mention` before the rewrite.
- **Detector:** `test_g7_edit_comment_refuses_a_bare_mention_before_any_gh_call`.
- **Neutralization:** `refusal = _mention_refusal(_read_text(body_path))` (the one after the "before any rewrite" axis comment) became `refusal = None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
>       _assert_refusal(result)

result = {'ok': True, 'reason': None, 'url': 'https://github.com/o/r/issues/1#c1', 'transit': {'transit': 'not-checked', 'why': 'the text could not be read back'}, ...}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: AssertionError
1 failed, 71 deselected in 2.25s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_builder.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.16s
```

## G8. `cloud_builder.note_text` (`cloud_builder.py:532`)

- **Axis:** the composed note is checked before it is returned.
- **Detector:** `test_g8_note_text_refuses_a_bare_mention_and_the_cli_exits_1`.
- **Neutralization:** in `note_text`, `refusal = _mention_refusal(comment)` became `refusal = None`.

**Raw red** (exit 1). The first clause of the refusal assertion raises `KeyError: 'ok'` instead of an `AssertionError`, because `note_text`'s healthy shape is `{"comment": ...}` with no `ok` key: the refusal assertion (`_assert_refusal`, line 265) is the one that failed, on the right axis:

```
F                                                                        [100%]
>       _assert_refusal(cb.note_text("ping @zwrose"))

result = {'comment': "Builder note for the advisor (cloud build).\n\nping @zwrose\n\nI'm waiting for your answer."}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
               ^^^^^^^^^^^^
E       KeyError: 'ok'

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: KeyError
1 failed, 71 deselected in 2.05s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_builder.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.24s
```

## G9. `cloud_builder.progress_text` (`cloud_builder.py:566`)

- **Axis:** the composed progress comment is checked before it is returned.
- **Detector:** `test_g9_progress_text_refuses_a_bare_mention_and_the_cli_exits_1`.
- **Neutralization:** in `progress_text`, `refusal = _mention_refusal(comment)` became `refusal = None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
>       _assert_refusal(cb.progress_text("building", "ping @zwrose", started, 30))

result = {'ok': True, 'comment': 'Builder progress (cloud build).\n\nPhase: building\nNow running: ping @zwrose\nStarted: 2026-01-02T03:04:05Z\nExpected: 30 minutes'}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: AssertionError
1 failed, 71 deselected in 2.10s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_builder.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.05s
```

## G10. `cloud_builder.terminal_text` (`cloud_builder.py:661`)

- **Axis:** the composed handback, stop or park is checked before it is returned.
- **Detector:** `test_g10_terminal_text_refuses_a_bare_mention_and_the_cli_exits_1`.
- **Neutralization:** in `terminal_text`, `refusal = _mention_refusal(comment)` became `refusal = None`.

**Raw red** (exit 1):

```
F                                                                        [100%]
>           _assert_refusal(cb.terminal_text(kind, "ping @zwrose"))

result = {'ok': True, 'comment': 'Builder handback (cloud build).\n\nping @zwrose'}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: AssertionError
1 failed, 71 deselected in 2.05s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_builder.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.17s
```

## G11. `cloud_relay.compose` (`cloud_relay.py:450`)

- **Axis:** `compose` checks the body right after `text-empty`, before the state opens.
- **Detector:** `test_g11_cloud_relay_compose_refuses_a_bare_mention_before_any_state_or_file`.
- **Neutralization:** `guard = _sibling("mention_guard").check(body)` became `guard = {"ok": True}`.

**Raw red** (exit 1; the compose went on and wrote a relay message):

```
F                                                                        [100%]
>       _assert_refusal(result)

result = {'ok': True, 'msgId': 'de7200c3c084', 'relay': 'superheroes-relay-claude-two-30b4c4ec', 'commentBodyFile': '/tmp/claud...e_r0/ledger-root/62ee07c15e0035ad2bfd2d49d520c5127420fbeef7fb8fa8f4110a4f8047153b/relay-messages/de7200c3c084.md', ...}

    def _assert_refusal(result, token="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:265: AssertionError
1 failed, 71 deselected in 2.50s
```

(The `world` fixture repr line is elided.)

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `cloud_relay.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.37s
```

## G12. `pr_body_stage._publish` (`pr_body_stage.py:256`)

- **Axis:** publish checks the staged body after the unchanged-return and before the audit and the PATCH.
- **Detector:** `test_g12_publish_refuses_a_staged_body_with_a_bare_mention_and_never_rewrites_it`.
- **Neutralization:** `guard = mention_guard.check(staged)` became `guard = {"ok": True}`.

**Raw red** (exit 1; the publish went through):

```
F                                                                        [100%]
        out = PBS.publish(sd, 7, runner=gh)
        assert PBS.REASON_BARE_MENTION == "bare-mention"
>       assert (out["ok"], out["outcome"], out["reason"]) == (False, "refused", "bare-mention")
E       AssertionError: assert (True, 'published', None) == (False, 'refu...bare-mention')
E         At index 0 diff: True != False

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:376: AssertionError
1 failed, 71 deselected in 2.41s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `pr_body_stage.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.37s
```

## G13. `vet_slot.check_slot_text` (`vet_slot.py:849`)

- **Axis:** slot text carrying a bare mention refuses `write-failed`, the detail opening `bare-mention:`.
- **Detector:** `test_g13_vet_slot_check_slot_text_refuses_a_bare_mention` (its healthy sibling `test_g13_a_healthy_slot_text_is_written` is kept).
- **Neutralization:** `guard = mention_guard.check(slot_text)` became `guard = {"ok": True}`.

**Raw red** (exit 1; the write went through):

```
F                                                                        [100%]
>       assert result["ok"] is False and result["reason"] == "write-failed"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:404: AssertionError
1 failed, 71 deselected in 2.20s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` printed ` M plugins/superheroes/lib/vet_slot.py` (this work order's own task-1 edit); `git diff --stat` printed `4 insertions(+), 4 deletions(-)`, the same as before the neutralization; the diff hash is unchanged (`939366c6…8465` before and after).

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.25s
```

## G14. `pr_comment.upsert` wrap (`pr_comment.py:223`)

- **Axis:** `upsert` wraps a bare mention after the scrub and before the marker and the write.
- **Detector:** `test_g14_upsert_wraps_a_bare_mention_in_a_code_span`.
- **Neutralization:** `body = mention_guard.wrap(body)` became `body = body`.

**Raw red** (exit 1):

```
F                                                                        [100%]
>       assert mg.bare_mentions(sent) == []
E       AssertionError: assert [{'line': 4, ...': '@zwrose'}] == []
E         Left contains one more item: {'line': 4, 'token': '@zwrose'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:447: AssertionError
1 failed, 71 deselected in 2.30s
```

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `pr_comment.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.08s
```

## G15a. `review_record.render_plan` summary wrap, single-body site (`review_record.py:2878`)

- **Axis:** the record comment's prose summary has each bare mention wrapped; the JSON block is untouched.
- **Detector:** `test_g15_the_record_summary_wraps_a_bare_mention_and_the_json_block_is_untouched`.
- **Neutralization:** `mention_guard.wrap(_summary(r, 0))` became `_summary(r, 0)` (in `single`, the one-comment body).

**Raw red** (exit 1):

```
F                                                                        [100%]
        body = rr.render(rec)
>       assert mg.bare_mentions(body) == []
E       AssertionError: assert [{'line': 4, ...': '@zwrose'}] == []
E         Left contains one more item: {'line': 4, 'token': '@zwrose'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:469: AssertionError
1 failed, 71 deselected in 2.20s
```

Cross-check while G15a was neutralized (not a proof, shows the two sites are tested separately): the parts test `test_g15_the_head_comment_summary_of_a_record_in_parts_is_wrapped_too` stayed green (`1 passed, 71 deselected in 2.33s`), because an oversized record discards the single-body text and posts the head site's output.

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `review_record.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.25s
```

## G15b. `review_record.render_plan` summary wrap, parts (head comment) site (`review_record.py:2918`)

- **Axis:** the head comment's prose summary, for a record posted in parts, has each bare mention wrapped; the index block is untouched.
- **Detector:** `test_g15_the_head_comment_summary_of_a_record_in_parts_is_wrapped_too` (it builds a record whose size forces parts, asserts `plan.parts`, then checks the head). Edge E3 did not apply: the existing tests reach both sites, so no test was added.
- **Neutralization:** `mention_guard.wrap(_summary(r, level))` became `_summary(r, level)` (in `head`).

**Raw red** (exit 1):

```
F                                                                        [100%]
        plan = rr.render_plan(rec)
        assert plan.parts
        head = plan.head(list(range(1, len(plan.parts) + 1)))
>       assert mg.bare_mentions(head) == []
E       AssertionError: assert [{'line': 4, ...': '@zwrose'}] == []
E         Left contains one more item: {'line': 4, 'token': '@zwrose'}

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:481: AssertionError
1 failed, 71 deselected in 2.26s
```

Cross-check while G15b was neutralized: the single-body test stayed green (`1 passed, 71 deselected in 2.04s`).

- **Restore:** inverse edit.
- **Restore receipt:** `git status --porcelain` and `git diff --stat` on `review_record.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.13s
```

## G16 (undeclared extra). `vet_slot` emits no refusal token of its own for a bare mention

- **Axis:** the `vet_slot` refusal census stays at its existing set: the guard's refusal rides `write-failed`.
- **Detector:** `test_vet_slot_emits_no_bare_mention_token_of_its_own`.
- **Neutralization:** `raise _Refusal("write-failed", "bare-mention: slot text carries at-sign…` became `raise _Refusal("bare-mention", "slot text carries at-sign…`.

**Raw red** (exit 1):

```
F                                                                        [100%]
>       assert "_Refusal(\"bare-mention\"" not in inspect.getsource(vs)
E       assert '_Refusal("bare-mention"' not in '#!/usr/bin/...it(main())\n'
E         '_Refusal("bare-mention"' is contained here:
E               raise _Refusal("bare-mention", "slot text carries at-sign mentions GitHub reads as logins (%s); %s"

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:416: AssertionError
1 failed, 71 deselected in 2.38s
```

(The `?` diff-marker lines and the pytest truncation notice are elided.)

- **Restore:** inverse edit.
- **Restore receipt:** diff hash of `vet_slot.py` against head is `939366c6…8465`, the same as before G13 and after G13.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 71 deselected in 2.12s
```

## WO-4 — a conservative mention mask, and the result key `mention`

Work order WO-4 of #2453 renamed the entry key to `mention`, made a mask rest on the intersection of readings (own line, paragraph, table cell), limited the fence mask to column-0 blocks, and let a link destination hold one level of balanced parentheses. The guarded-element set the order declared is G17, G18, G19, G20, G21; none is grouped. Detector file `plugins/superheroes/lib/tests/test_mention_guard.py` is unedited between each red and its green. Each neutralization is a targeted Edit-tool edit to `plugins/superheroes/lib/mention_guard.py` (each `old_string` occurred exactly once), undone by the inverse Edit; no `git checkout`, `restore`, `reset` or `stash`. Runs: `timeout 120 scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2453 -m pytest plugins/superheroes/lib/tests/test_mention_guard.py -q -p no:cacheprovider -k <full test function name>`. The `UV_NATIVE_TLS` warning line is the only line left out of every capture; the pytest temp path in the G18 capture is sandbox scratch. No secrets, tokens, private URLs or PII appear; nothing was redacted. Because `mention_guard.py` carries this work order's own uncommitted edits, a clean diff against the head is not possible, so each restore receipt quotes the restored line back (with its line number) instead.

| Element | Neutralization | Red detector | Red on the declared axis |
|---|---|---|---|
| G17 | reading (a) replaced by `True` | `test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports` | yes |
| G18 | reading (b) replaced by `True` | `test_g6_post_comment_refuses_a_mention_a_single_reading_would_have_masked[multi-line-span]` | yes (the `[leading-pipe-table]` row stayed green: reading (c) alone catches it) |
| G19 | reading (c) replaced by `True` | `test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell` | yes |
| G20 | the fence indent rule replaced by `True` | `test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence` | yes |
| G21 | destination pattern reverted to `\]\([^)\s]*` | `test_a_link_destination_with_balanced_parentheses_is_left_alone` | yes |

### G17. Per-line reading (a) in the intersection (`mention_guard.py:186`)

- **Axis:** a mention is masked by code only when its own line pairs it as code too.
- **Detector:** `test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports`. The case only reading (a) catches is a span that exists only across the line break: backtick, `a`, newline, the mention, ` b`, backtick. The paragraph reading masks it, the line reading does not.
- **Neutralization:** `if (_inside(line_spans, m.start()) and _inside(paragraph_spans, offset + m.start())` became `if (True and _inside(paragraph_spans, offset + m.start())`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports ________

    def test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports():
        # axis: G17 — code masks a mention only when its own line pairs it too, so a backtick pair that exists only
        # across the line break leaves the mention reported (a doubt reports)
        text = TICK + "a\n@octo b" + TICK + "\n"
>       assert mg.bare_mentions(text) == [{"line": 2, "mention": "@octo"}]
E       AssertionError: assert [] == [{'line': 2, ...on': '@octo'}]
E         
E         Right contains one more item: {'line': 2, 'mention': '@octo'}
E         Use -v to get more diff

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:238: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_a_span_the_line_alone_does_not_pair_is_a_doubt_and_reports
1 failed, 89 deselected in 2.12s
```

- **Restore:** inverse edit.
- **Restore receipt:** line 186 quoted back: `                if (_inside(line_spans, m.start()) and _inside(paragraph_spans, offset + m.start())`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 89 deselected in 2.31s
```

### G18. Paragraph reading (b) in the intersection (`mention_guard.py:186`)

- **Axis:** a mention is masked by code only when its paragraph, joined across its lines, pairs it as code too.
- **Detector:** the multi-line writer regression `test_g6_post_comment_refuses_a_mention_a_single_reading_would_have_masked[multi-line-span]`.
- **Neutralization:** `and _inside(paragraph_spans, offset + m.start())` became `and True` (at the head of the continuation line, before `and (cell_spans`).

**Raw red** (exit 1; the failing row's traceback, with the parametrize decorator echo kept):

```
F.                                                                       [100%]
=================================== FAILURES ===================================
_ test_g6_post_comment_refuses_a_mention_a_single_reading_would_have_masked[multi-line-span] _

body = 'begin `code\nend` then @octo `literal\n'
...
        result = cb.post_comment("o/r", 1, _body_file(tmp_path, body), run=run, env={})
>       _assert_refusal(result, mention="@octo")
...
    def _assert_refusal(result, mention="@zwrose"):
>       assert result["ok"] is False and result["reason"] == "bare-mention"
E       assert (True is False)

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:384: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_g6_post_comment_refuses_a_mention_a_single_reading_would_have_masked[multi-line-span]
1 failed, 1 passed, 88 deselected in 3.56s
```

(Elided: the decorator source, the `tmp_path` line and the `result` dict line of the traceback. The writer posted: `ok` was `True`, so the mention reached `gh`.)

- **Restore:** inverse edit.
- **Restore receipt:** line 186 quoted back: `                if (_inside(line_spans, m.start()) and _inside(paragraph_spans, offset + m.start())`.

**Raw green** (exit 0):

```
..                                                                       [100%]
2 passed, 88 deselected in 1.96s
```

### G19. Cell reading (c) in the intersection (`mention_guard.py:187`)

- **Axis:** on a line with an unescaped pipe, a mention is masked by code only when its cell pairs it as code too.
- **Detector:** `test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell`.
- **Neutralization:** `and (cell_spans is None or _inside(cell_spans, m.start()))):` became `and True):`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell _____

    def test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell():
        # axis: G19 — a row with no leading pipe is still a row: a backtick in one cell cannot pair with one in another
        text = "a | b\n--- | ---\n" + TICK + " | @octo " + TICK + "\n"
>       assert [m["line"] for m in mg.bare_mentions(text)] == [3]
E       assert [] == [3]
E         
E         Right contains one more item: 3
E         Use -v to get more diff

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:258: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_a_table_row_without_a_leading_pipe_pairs_code_spans_cell_by_cell
1 failed, 89 deselected in 2.09s
```

- **Restore:** inverse edit.
- **Restore receipt:** line 187 quoted back: `                        and (cell_spans is None or _inside(cell_spans, m.start()))):`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 89 deselected in 1.84s
```

### G20. Fence indent rule in `_inert_lines` (`mention_guard.py:144`)

- **Axis:** a fenced block masks its lines only when its opener, and its closer when it has one, is at column 0.
- **Detector:** `test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence` (the extended list-fence case: the mention on line 5 must be reported).
- **Neutralization:** `if not _indented(bare[i]) and not (closed and _indented(bare[last])):` became `if True:` (mask every `md_fence` block regardless of indent).

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence _

    def test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence():
        # axis: G20 — md_fence pairs the indented closer (line 3) with the column-0 fence at line 7; that block's opener
        # is indented, so it masks nothing and the mention on line 5 is reported
        text = ("- " + FENCE + "\n  example\n  " + FENCE + "\n\nping @octo\n\n" + FENCE + "\nmore\n" + FENCE + "\n")
>       assert mg.bare_mentions(text) == [{"line": 5, "mention": "@octo"}]
E       AssertionError: assert [] == [{'line': 5, ...on': '@octo'}]
E         
E         Right contains one more item: {'line': 5, 'mention': '@octo'}
E         Use -v to get more diff

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:213: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_a_fence_in_a_list_extended_cannot_pair_its_indented_closer_with_a_later_fence
1 failed, 89 deselected in 2.06s
```

- **Restore:** inverse edit.
- **Restore receipt:** line 144 quoted back: `        if not _indented(bare[i]) and not (closed and _indented(bare[last])):`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 89 deselected in 1.95s
```

### G21. Balanced-parenthesis link destination in `_URL_RE` (`mention_guard.py:52`)

- **Axis:** a link destination may hold one level of balanced parentheses, so an at-sign after `(b)` is still part of the address.
- **Detector:** `test_a_link_destination_with_balanced_parentheses_is_left_alone`.
- **Neutralization:** the first alternative `\]\((?:[^()\s]|\([^()\s]*\))*\)?` was reverted to `\]\([^)\s]*`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_link_destination_with_balanced_parentheses_is_left_alone ________

    def test_a_link_destination_with_balanced_parentheses_is_left_alone():
        # axis: G21 — the destination pattern takes one level of balanced parentheses, so the at-sign after `(b)` is
        # still inside the destination
        text = "[package](https://example.com/a(b)/@scope/pkg)\n"
>       assert mg.bare_mentions(text) == []
E       AssertionError: assert [{'line': 1, ...n': '@scope'}] == []
E         
E         Left contains one more item: {'line': 1, 'mention': '@scope'}
E         Use -v to get more diff

/home/user/wt-2453/plugins/superheroes/lib/tests/test_mention_guard.py:274: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_mention_guard.py::test_a_link_destination_with_balanced_parentheses_is_left_alone
1 failed, 89 deselected in 2.32s
```

- **Restore:** inverse edit.
- **Restore receipt:** line 52 quoted back: `_URL_RE = re.compile(r"\]\((?:[^()\s]|\([^()\s]*\))*\)?|<[A-Za-z][A-Za-z0-9+.-]*:[^\s<>]*>|\b(?:https?|ftp)://[^\s<>()]+", re.IGNORECASE)`.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 89 deselected in 2.31s
```
