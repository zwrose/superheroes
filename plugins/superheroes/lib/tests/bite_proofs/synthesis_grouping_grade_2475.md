# Bite-proof — `test_synthesis_grouping_grade_2475.py` (#2475: a non-empty synthesis grouping is not graded vacuous in a PR-body run)

Detector: `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py`, run unedited for every red and
green below. Production under test: `plugins/superheroes/lib/engine_dispatch.py`, `_finish_review_grade_from_parse`
(the PR-body branch, `if (has_payload and pr_body_staged and not accepted and kind != engine_adapter.review_payload_key("grouping")):`).

Command shape for the element runs (exact node ids, no `-k`, no file argument — the summary line names the expected count):

`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-2475 -m pytest -q -p no:cacheprovider "<node id>" ...`

Guarded-element set (declared by the order), exact pytest node ids (every parametrization listed):

- **G1** `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok`
- **G2** `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g2_nonempty_findings_pr_body_staged_no_investigated_is_vacuous`
- **G3** `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g3_nonempty_verdicts_pr_body_staged_no_investigated_is_vacuous`
- **G4** `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g4_ruling_pr_body_staged_no_investigated_is_vacuous`
- **G5** (four parametrizations):
  - `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[none-pr-body-staged]`
  - `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[none-pr-body-not-staged]`
  - `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[empty-list-pr-body-staged]`
  - `plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[empty-list-pr-body-not-staged]`

Run opening: every case opens its run with `_grade_state_with_view_meta` (which calls `_manual_open_review_run`,
expected result kind unpinned, the same open the existing grader tests use). "PR body staged" sets `viewMeta`
to `{"prBodyPath": <PR_BODY_FILE_NAME>, "headSha": "abc"}` and `prBodySourcePath` on the `run-opened` record;
"not staged" sets `viewMeta` to `None` and no `prBodySourcePath`. No expected kind `grouping` was needed.

Each neutralization is a targeted edit made with the edit tool and undone by the inverse edit; no
`git stash`/`checkout`/`restore`. Receipts are test-runner output with no secrets, tokens, private URLs or
PII; nothing is redacted. Pytest's `UV_NATIVE_TLS` deprecation warning line is omitted from the captures
(one line each, tooling noise). The `tmp_path` lines and the decorator echo of the G5 parametrization are
elided where marked; the failing assertion, its message and the summary lines are verbatim.

## Pre-change baseline (G1 neutralization applied = the pre-change code; G2–G5 green and G1 red together)

Production state: the PR-body condition read `if (has_payload and pr_body_staged and not accepted):`
(the grouping exclusion removed). Full new file, one run:

```
F.......                                                                 [100%]
=================================== FAILURES ===================================
________ test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok ________
...
>       assert staged.get("ok") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7f3c52938dc0>('ok')
E        +    where <built-in method get of dict object at 0x7f3c52938dc0> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 62, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get

/home/user/wt-2475/plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py:69: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok
1 failed, 7 passed in 3.25s
```

The seven passes are G2, G3, G4 and the four G5 parametrizations: on the pre-change code they pass, as they
do after the change. (Disclosure: a second run in the same state selected the whole file by mistake — the
file path was passed before the node id — and printed the same `1 failed, 7 passed`; it is not used below.)

## G1 — a non-empty grouping with a staged PR body and no `investigated` is graded ok

- **Axis:** result kind at the PR-body vacuous forfeit (`resultKind`, `ok`, absence of `forfeit`); the same
  input with no staged PR body is also asserted ok.
- **Neutralization:** `engine_dispatch.py`, the exclusion removed (this is the pre-change condition):
  `if (has_payload and pr_body_staged and not accepted\n            and kind != engine_adapter.review_payload_key("grouping")):`
  became `if (has_payload and pr_body_staged and not accepted):`
- **Raw red** (node id alone):
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok ________
...
>       assert staged.get("ok") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7f470afe0340>('ok')
E        +    where <built-in method get of dict object at 0x7f470afe0340> = {'forfeit': True, 'reason': 'vacuous', 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 62, 'wallSeconds': 1.0, ...}, 'investigatedRejected': ['not-a-list'], ...}.get

/home/user/wt-2475/plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py:69: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g1_nonempty_grouping_pr_body_staged_no_investigated_is_ok
1 failed in 3.10s
```
- **Restore:** the inverse edit put the `and kind != engine_adapter.review_payload_key("grouping")` line back.
- **Restore receipt:** `git diff --stat -- plugins/superheroes/lib/engine_dispatch.py` printed
  `plugins/superheroes/lib/engine_dispatch.py | 5 ++++-` / `1 file changed, 4 insertions(+), 1 deletion(-)`
  (only the intended change); the restored condition reads
  `if (has_payload and pr_body_staged and not accepted` / `        and kind != engine_adapter.review_payload_key("grouping")):`.
- **Raw green:**
```
.                                                                        [100%]
1 passed in 2.90s
```

## G2 — a non-empty `findings` payload with a staged PR body and no `investigated` is a vacuous forfeit

- **Axis:** result kind at the PR-body vacuous forfeit — findings are not exempt.
- **Neutralization:** `engine_dispatch.py`, `and kind != engine_adapter.review_payload_key("grouping")):` became
  `and kind not in (engine_adapter.review_payload_key("grouping"), "findings")):`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_g2_nonempty_findings_pr_body_staged_no_investigated_is_vacuous ______
...
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7f30549c4880>('forfeit')
E        +    where <built-in method get of dict object at 0x7f30549c4880> = {'ok': True, 'resultKind': 'findings', 'findings': [{'id': 'f1', 'severity': 'Critical', 'dimension': 'Architecture', ...: 'example', ...}], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 54, 'wallSeconds': 1.0, ...}, ...}.get

/home/user/wt-2475/plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py:84: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g2_nonempty_findings_pr_body_staged_no_investigated_is_vacuous
1 failed in 2.77s
```
- **Restore:** the inverse edit set the condition line back to `and kind != engine_adapter.review_payload_key("grouping")):`.
- **Restore receipt:** `git diff --stat -- plugins/superheroes/lib/engine_dispatch.py` printed
  `plugins/superheroes/lib/engine_dispatch.py | 5 ++++-` / `1 file changed, 4 insertions(+), 1 deletion(-)`.
- **Raw green:**
```
.                                                                        [100%]
1 passed in 3.55s
```

## G3 — a non-empty `verdicts` payload with a staged PR body and no `investigated` is a vacuous forfeit

- **Axis:** result kind at the PR-body vacuous forfeit — verdicts are not exempt.
- **Neutralization:** `engine_dispatch.py`, the condition's last line became
  `and kind not in (engine_adapter.review_payload_key("grouping"), "verdicts")):`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_g3_nonempty_verdicts_pr_body_staged_no_investigated_is_vacuous ______
...
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7f8df41a0e80>('forfeit')
E        +    where <built-in method get of dict object at 0x7f8df41a0e80> = {'ok': True, 'resultKind': 'verdicts', 'verdicts': [{'id': 'v1', 'verdict': 'CONFIRMED', 'reason': 'reproduced in test'}], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 84, 'wallSeconds': 1.0, ...}, ...}.get

/home/user/wt-2475/plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py:91: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g3_nonempty_verdicts_pr_body_staged_no_investigated_is_vacuous
1 failed in 3.15s
```
- **Restore:** the inverse edit set the line back to `and kind != engine_adapter.review_payload_key("grouping")):`.
- **Restore receipt:** the restored line is quoted above; the final `git diff` of `engine_dispatch.py` (below) shows only the intended change.
- **Raw green:**
```
.                                                                        [100%]
1 passed in 2.72s
```

## G4 — a `ruling` payload with a staged PR body and no `investigated` is a vacuous forfeit

- **Axis:** result kind at the PR-body vacuous forfeit — a ruling is not exempt.
- **Neutralization:** `engine_dispatch.py`, the condition's last line became
  `and kind not in (engine_adapter.review_payload_key("grouping"), "ruling")):`
- **Raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_g4_ruling_pr_body_staged_no_investigated_is_vacuous ___________
...
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7fc42fb0b840>('forfeit')
E        +    where <built-in method get of dict object at 0x7fc42fb0b840> = {'ok': True, 'resultKind': 'ruling', 'ruling': {'id': 'f1', 'ruling': 'discharged', 'reason': 'resolved in diff', 'che...hy': 'checked'}}}, 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 231, 'wallSeconds': 1.0, ...}, ...}.get

/home/user/wt-2475/plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py:98: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g4_ruling_pr_body_staged_no_investigated_is_vacuous
1 failed in 2.61s
```
- **Restore:** the inverse edit set the line back to `and kind != engine_adapter.review_payload_key("grouping")):`.
- **Restore receipt:** the restored line is quoted above; the final `git diff` of `engine_dispatch.py` (below) shows only the intended change.
- **Raw green:**
```
.                                                                        [100%]
1 passed in 2.77s
```

## G5 — an empty grouping (`None` and `[]`), staged or not, with no `investigated` is a vacuous forfeit

- **Axis:** payload emptiness at the empty-payload forfeit (the first branch) — an empty grouping stays vacuous.
- **Neutralization:** `engine_dispatch.py`, the empty-payload branch condition
  `if not _parse_review_has_payload(res) and not accepted:` became
  `if not _parse_review_has_payload(res) and not accepted and kind != engine_adapter.review_payload_key("grouping"):`
- **Raw red** (all four parametrizations selected by exact node id; the four failure bodies are identical in
  shape, so one is quoted whole and the other three are cut to their `where` line, the rest elided — about 75 lines):
```
FFFF                                                                     [100%]
=================================== FAILURES ===================================
____ test_g5_empty_grouping_no_investigated_is_vacuous[none-pr-body-staged] ____
...
>       assert grade.get("forfeit") is True
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x7ff47af8c3c0>('forfeit')
E        +    where <built-in method get of dict object at 0x7ff47af8c3c0> = {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 18, 'wallSeconds': 1.0, ...}, ...}.get
...
E        +    where <built-in method get of dict object at 0x7ff47af8cc00> = {'ok': True, 'resultKind': 'grouping', 'grouping': None, 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 18, 'wallSeconds': 1.0, ...}, ...}.get
...
E        +    where <built-in method get of dict object at 0x7ff47a3ae800> = {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 16, 'wallSeconds': 1.0, ...}, ...}.get
...
E        +    where <built-in method get of dict object at 0x7ff47a89c840> = {'ok': True, 'resultKind': 'grouping', 'grouping': [], 'engagement': {'tokens': None, 'toolCalls': None, 'stdoutBytes': 16, 'wallSeconds': 1.0, ...}, ...}.get
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[none-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[none-pr-body-not-staged]
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[empty-list-pr-body-staged]
FAILED plugins/superheroes/lib/tests/test_synthesis_grouping_grade_2475.py::test_g5_empty_grouping_no_investigated_is_vacuous[empty-list-pr-body-not-staged]
4 failed in 3.36s
```
- **Restore:** the inverse edit removed ` and kind != engine_adapter.review_payload_key("grouping")` from the empty-payload branch.
- **Restore receipt:** `git diff -- plugins/superheroes/lib/engine_dispatch.py` after the restore shows one hunk only, at
  `@@ -5282,7 +5282,10 @@`: a two-line comment (the second is the `# axis:` line), the condition
  `if (has_payload and pr_body_staged and not accepted` / `        and kind != engine_adapter.review_payload_key("grouping")):`
  replacing `if has_payload and pr_body_staged and not accepted:`. The empty-payload branch line
  `if not _parse_review_has_payload(res) and not accepted:` is untouched (no hunk touches it). Non-test lines changed: 5 (4 added, 1 removed).
- **Raw green:**
```
....                                                                     [100%]
4 passed in 3.05s
```

## Final runs after the last restore

Full new file: `8 passed in 2.90s`. Existing grader tests, scoped
(`test_engine_dispatch.py -n auto -k "grade_review or pr_body or vacuous or grouping"`): `53 passed in 5.20s`.
