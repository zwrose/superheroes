# WO-1b (#2652) bite-proof — stack-layer blockers in issue_contract.py, stack_check.py and launcher.py

Per-element bite proof for the lower-layer-of-a-stack judgement of an open native blocker
(`judge_open_blockers` and its helpers), the `stackEntry` missing-key guard, and the launcher's card pin.

**Register:** 9 guarded elements, E1-E9, one neutralization and one red each. No equivalence classes.

**Head:** `4f52f3c80b2d30f6a079c8f012c3c4f798015412` (WO-1 as committed; the worktree held only the
two authorized test edits and this file when the proofs ran).

**Method:** each neutralization is the smallest edit to the guarded code (never to a test), applied
through the host's edit action and undone by the inverse edit. Each proving test is selected by its
exact node id, run alone. Code line numbers are those at `HEAD`.

**Command** (`<node>` replaced per element), from the worktree root:

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc-wo1b -m pytest <node> -q -p no:cacheprovider
```

**Redaction and elision:** nothing secret appears in these captures. Omitted from every capture: the
one-line `uv` `UV_NATIVE_TLS` deprecation warning that opens each run's stdout. From E9's red only,
the `<sandbox_violations>` block the harness appended is omitted (denied outbound connections,
nearly all to `api.anthropic.com:443` and one to a telemetry host; they come from the child process
the launcher spawned once the neutralized gate let the launch through, which is the failure the test
catches, and are not a test result).

## Summary table

| ID | Guarded element (file:line) | Axis | Proving test | Verdict |
|---|---|---|---|---|
| E1 | issue_contract.py:830 `_blockers_verdict` | a READY lower layer is accepted: only a held blocker refuses, an open-but-accepted one does not | `test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row` | proven |
| E2 | stack_check.py:1145 `_parse_vet_verdict_line` | a vet verdict counts only when pinned to the PR's current head | `test_case2_a_ready_vet_pinned_to_an_earlier_head_holds` | proven |
| E3 | issue_contract.py:754 `_judge` | a blocker listed at or after the blocked issue is not a lower layer | `test_case6_a_blocker_listed_after_the_issue_holds` | proven |
| E4 | issue_contract.py:642 `_judge_with_premise` | a layer counts only in the launch's own stack | `test_case6_premise_stack_s_with_the_pr_in_stack_x_holds` | proven |
| E5 | issue_contract.py:613 `_layer_of` | a card mark counts only for this stack's own parent | `test_case8_a_stack_card_mark_for_another_parent_holds_naming_it` | proven |
| E6 | issue_contract.py:599 `_layer_of` | a draft pull request is never a handed-back layer | `test_case3_a_draft_pr_holds` | proven |
| E7 | issue_contract.py:537 `_closes_issue` | only the first non-empty body line carries a closing reference | `test_first_line_only_a_closing_ref_on_the_second_line_does_not_count` | retired (WO-3 deleted the first-line reader) |
| E8 | stack_check.py:493 `_parse_membership_page` | an absent `stackEntry` key is unreadable, not not-linked | `test_e28_stack_entry_key_missing_is_unreadable_not_not_linked` | proven |
| E9 | launcher.py:2630 `_apply_dependency_gate` | a card-marked dependency is gated on base equality like a READY one | `test_dependency_gate_stack_card_base_mismatch_refuses` | proven at 4f52f3c8; superseded by E9r |

---

## E1 — only a held blocker refuses

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_blockers_verdict`):

```python
    if blockers["held"]:
```
→
```python
    if blockers["open"]:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row ______

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-5/test_ready_lower_layer_as_only0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f796db3a210>

    def test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row(tmp_path, capsys):
        fake = _world(blocked=(12,), subs=(12, 7), prs=[_pr_row(101, closes=12)])
        members = _Members({101: _in_stack(900, 1)})
        out = _build_ready(tmp_path, capsys, fake, members=members)
>       assert out["ok"] is True
E       assert False is True

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:960: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_ready_lower_layer_as_only_blocker_passes_with_its_accepted_row
1 failed in 0.43s
```

**restore:** the inverse edit, `blockers["open"]` → `blockers["held"]`.

**restored lines:**
```python
    if blockers["held"]:
```

**raw green** after the inverse edit (re-run on the final restored tree; the first green, taken
during the dispatch, also read `1 passed`):
```
.                                                                        [100%]
1 passed in 0.41s
```

## E2 — a vet verdict counts only at the PR's current head

**neutralization** (`plugins/superheroes/lib/stack_check.py`, `_parse_vet_verdict_line`):

```python
    if not same_commit(sha_part, head_sha):
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_case2_a_ready_vet_pinned_to_an_earlier_head_holds`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_case2_a_ready_vet_pinned_to_an_earlier_head_holds ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-7/test_case2_a_ready_vet_pinned_0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f87c36d02f0>

    def test_case2_a_ready_vet_pinned_to_an_earlier_head_holds(tmp_path, capsys):
        pr = _pr_row(101, closes=12, vet=_vet("READY", _head(999)))
        members = _Members({101: _in_stack(900, 1)})
        out = _build_ready(tmp_path, capsys, _world(prs=[pr]), members=members)
>       assert out["ok"] is False
E       assert True is False

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1077: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_case2_a_ready_vet_pinned_to_an_earlier_head_holds
1 failed in 0.47s
```

**restore:** the inverse edit, `if False:` → `if not same_commit(sha_part, head_sha):`.

**restored lines** (read back after the restore):
```python
    if not same_commit(sha_part, head_sha):
        return VET_NOT_READY

    return matched_verdict
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.30s
```

## E3 — a blocker listed at or after the blocked issue is not a lower layer

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_judge`):

```python
            elif siblings.index(ref) >= own_at:
```
→
```python
            elif False:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_case6_a_blocker_listed_after_the_issue_holds`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
______________ test_case6_a_blocker_listed_after_the_issue_holds _______________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-9/test_case6_a_blocker_listed_af0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f3fe80d18b0>

    def test_case6_a_blocker_listed_after_the_issue_holds(tmp_path, capsys):
        members = _Members({101: _in_stack(900, 1)})
        fake = _world(blocked=(12,), subs=(7, 12), prs=[_pr_row(101, closes=12)])
        out = _build_ready(tmp_path, capsys, fake, members=members)
>       assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
E       AssertionError: assert None == 'blocker-open'
E        +  where 'blocker-open' = ic.REFUSAL_BLOCKER_OPEN

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1144: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_case6_a_blocker_listed_after_the_issue_holds
1 failed in 0.41s
```

**restore:** the inverse edit, `elif False:` → `elif siblings.index(ref) >= own_at:`.

**restored lines:**
```python
            elif siblings.index(ref) >= own_at:
```

**raw green** (re-run on the final restored tree; the first green also read `1 passed`):
```
.                                                                        [100%]
1 passed in 0.35s
```

## E4 — a layer counts only in the launch's own stack

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_judge_with_premise`):

```python
            elif layer["stack"] != want:
```
→
```python
            elif False:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_case6_premise_stack_s_with_the_pr_in_stack_x_holds`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_case6_premise_stack_s_with_the_pr_in_stack_x_holds ____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-11/test_case6_premise_stack_s_wit0')
capsys = <_pytest.capture.CaptureFixture object at 0x7faaf24768a0>

    def test_case6_premise_stack_s_with_the_pr_in_stack_x_holds(tmp_path, capsys):
        fake = _world(prs=[_pr_row(101, closes=12)])
        out = _judge_cli(capsys, fake, _Members({101: _in_stack(901, 1)}), tmp_path, {"stack": 900, "layerPosition": 3})
>       assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
E       AssertionError: assert None == 'blocker-open'
E        +  where 'blocker-open' = ic.REFUSAL_BLOCKER_OPEN

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1182: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_case6_premise_stack_s_with_the_pr_in_stack_x_holds
1 failed in 0.46s
```

**restore:** the inverse edit, `elif False:` → `elif layer["stack"] != want:`.

**restored lines:**
```python
            elif layer["stack"] != want:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.32s
```

## E5 — a card mark counts only for this stack's own parent

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_layer_of`):

```python
        if card is not None and card != parent:
```
→
```python
        if False:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_case8_a_stack_card_mark_for_another_parent_holds_naming_it`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_case8_a_stack_card_mark_for_another_parent_holds_naming_it ________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-13/test_case8_a_stack_card_mark_f0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f10c13490a0>

    def test_case8_a_stack_card_mark_for_another_parent_holds_naming_it(tmp_path, capsys):
        fake = _world(prs=[_pr_row(101, closes=12, vet=_card(_head(101), parent=77))])
        out = _build_ready(tmp_path, capsys, fake, members=_Members({101: _in_stack(900, 1)}))
>       assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
E       AssertionError: assert None == 'blocker-open'
E        +  where 'blocker-open' = ic.REFUSAL_BLOCKER_OPEN

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1288: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_case8_a_stack_card_mark_for_another_parent_holds_naming_it
1 failed in 0.38s
```

**restore:** the inverse edit, `if False:` → `if card is not None and card != parent:`.

**restored lines:**
```python
        if card is not None and card != parent:
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.30s
```

## E6 — a draft pull request is never a handed-back layer

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_layer_of`):

```python
    if pr["draft"]:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_case3_a_draft_pr_holds`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________________________ test_case3_a_draft_pr_holds __________________________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-15/test_case3_a_draft_pr_holds0')
capsys = <_pytest.capture.CaptureFixture object at 0x7f4061b74230>

    def test_case3_a_draft_pr_holds(tmp_path, capsys):
        members = _Members({101: _in_stack(900, 1)})
        out = _build_ready(tmp_path, capsys, _world(prs=[_pr_row(101, closes=12, draft=True)]), members=members)
>       assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
E       AssertionError: assert None == 'blocker-open'
E        +  where 'blocker-open' = ic.REFUSAL_BLOCKER_OPEN

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1090: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_case3_a_draft_pr_holds
1 failed in 0.42s
```

**restore:** the inverse edit, `if False:` → `if pr["draft"]:`.

**restored lines:**
```python
    if pr["draft"]:
        decided[index] = ("held", "its pull request #%d is a draft" % pr["number"])
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.35s
```

## E7 — only the first non-empty body line carries a closing reference

**neutralization** (`plugins/superheroes/lib/issue_contract.py`, `_closes_issue`):

```python
    line = _first_nonempty_line(pr["body"])
```
→
```python
    line = pr["body"]
```

(The scan below it then reads every line of the body.)

**node id:** `plugins/superheroes/lib/tests/test_issue_contract.py::test_first_line_only_a_closing_ref_on_the_second_line_does_not_count`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_first_line_only_a_closing_ref_on_the_second_line_does_not_count _____

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-17/test_first_line_only_a_closing0')
capsys = <_pytest.capture.CaptureFixture object at 0x7fb76cd5a210>

    def test_first_line_only_a_closing_ref_on_the_second_line_does_not_count(tmp_path, capsys):
        body = "A layer of the feature.\nCloses #12\n\n" + _vet("READY", _head(101))
        out = _build_ready(tmp_path, capsys, _world(prs=[_pr_row(101, body=body)]), members=_Members({101: _in_stack(900, 1)}))
>       assert out["reason"] == ic.REFUSAL_BLOCKER_OPEN
E       AssertionError: assert None == 'blocker-open'
E        +  where 'blocker-open' = ic.REFUSAL_BLOCKER_OPEN

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_issue_contract.py:1055: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_issue_contract.py::test_first_line_only_a_closing_ref_on_the_second_line_does_not_count
1 failed in 0.29s
```

**restore:** the inverse edit, `line = pr["body"]` → `line = _first_nonempty_line(pr["body"])`.

**restored lines:**
```python
    line = _first_nonempty_line(pr["body"])
    if line is None:
        return False
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.29s
```

## E8 — an absent `stackEntry` key is unreadable

**neutralization** (`plugins/superheroes/lib/stack_check.py`, `_parse_membership_page`):

```python
    if "stackEntry" not in pull_request:
```
→
```python
    if False:
```

**node id:** `plugins/superheroes/lib/tests/test_stack_check.py::test_e28_stack_entry_key_missing_is_unreadable_not_not_linked`

**raw red:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_e28_stack_entry_key_missing_is_unreadable_not_not_linked _________

    def test_e28_stack_entry_key_missing_is_unreadable_not_not_linked():
        page = {
            "number": PR,
            "baseRefName": STACK_BASE,
            "headRefName": "branch-3",
            "headRefOid": "oid3",
        }
        run, _calls = _make_run({_argv_page(PR, sc.DEFAULT_PAGE_SIZE): _graphql_ok(page)})
        result = sc.read_membership(pr=PR, repo=REPO, run=run)
>       _assert_refusal(result, sc.REASON_STACK_UNREADABLE)

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_stack_check.py:603: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

result = {'ok': False, 'reason': 'not-linked', 'detail': 'pull request is not in a stack', 'repo': 'owner/example', ...}
reason = 'stack-unreadable'

    def _assert_refusal(result, reason):
        assert set(result.keys()) == TOTAL_KEYS
        assert result["ok"] is False
>       assert result["reason"] == reason
E       AssertionError: assert 'not-linked' == 'stack-unreadable'
E         
E         - stack-unreadable
E         + not-linked

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_stack_check.py:135: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_stack_check.py::test_e28_stack_entry_key_missing_is_unreadable_not_not_linked
1 failed in 0.37s
```

**restore:** the inverse edit, `if False:` → `if "stackEntry" not in pull_request:`.

**restored lines:**
```python
    if "stackEntry" not in pull_request:
        return None, _refusal(REASON_STACK_UNREADABLE,
            "stackEntry is missing", repo=repo, pr=pr, pages=pages)
```

**raw green:**
```
.                                                                        [100%]
1 passed in 0.34s
```

## E9 — a card-marked dependency is gated on base equality

**neutralization** (`plugins/superheroes/lib/launcher.py`, `_apply_dependency_gate`):

```python
        if issue_contract.stack_card_parent(pr_state["body"], pr_state["headRefOid"]) is None:
```
→
```python
        if True:
```

(Every non-READY dependency, card-marked or not, now takes the not-ready path and the gate is not applied.)

**node id:** `plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_stack_card_base_mismatch_refuses`

**raw red** (the `<sandbox_violations>` block that followed is omitted, as stated at the top):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____________ test_dependency_gate_stack_card_base_mismatch_refuses _____________

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-21/test_dependency_gate_stack_car0')
monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f17bd9a4470>

    def test_dependency_gate_stack_card_base_mismatch_refuses(tmp_path, monkeypatch):
      # axis: a card-marked dependency with a different base refuses dependency-open-ready-pr — see bite-proof record wo_2652_stack_layer_blockers
        repo = _init_repo(tmp_path / "repo")
        _ledger_env(tmp_path, monkeypatch)
        log_dir = str(tmp_path / "logs")
        dep_head = "a" * 40
    
        def reader(pr, repo_name, **kwargs):
            return _pr_vet_state_ok(dep_head, _card_vet_body(dep_head)), None
    
        monkeypatch.setattr(
            L.stack_check, "resolve_repo_slug",
            lambda *a, **k: ("owner/repo", None),
        )
    
        result = L.launch_build(
            repo,
            656,
            _dependency_premise(repo, 701),
            _all_checks(),
            log_dir,
            pr_vet_reader=reader,
        )
>       assert result["ok"] is False
E       assert True is False

/home/user/superheroes/.claude/worktrees/issue-2652/plugins/superheroes/lib/tests/test_launcher.py:7724: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_launcher.py::test_dependency_gate_stack_card_base_mismatch_refuses
1 failed in 21.52s
```

**restore:** the inverse edit, `if True:` → the original `if issue_contract.stack_card_parent(...) is None:` line.

**restored lines:**
```python
        if issue_contract.stack_card_parent(pr_state["body"], pr_state["headRefOid"]) is None:
            # axis: unreadable verdict is never treated as absent — only explicit not-ready passes
```

**raw green:**
```
.                                                                        [100%]
1 passed in 1.00s
```

## Restore receipt

After the last restore, `git diff HEAD -- plugins/superheroes/lib/issue_contract.py
plugins/superheroes/lib/stack_check.py plugins/superheroes/lib/launcher.py` printed nothing: all three
files read exactly as at `HEAD`. No residue remains.

## Replay on the reviewed head (review session 2)

**Head:** `4cf72dd7de24acf7b5cd0a5e661fdabe6d37d025`, checked out detached in a separate probe worktree.
E7 and E9 above quote code that review fixes have since replaced (`_closes_issue` now reads
`_first_prose_line`, and E9's outer card check is gone). **E7r and E9r supersede them.** E10-E22 prove the
guards added after the first record: the stale-card refusal and review session 2's fixes. The method and
command are as above, plus `--tb=line -rf`. Each neutralization is one exact, single-match edit to the
guarded code, never to a test. Each is undone by writing back the file's original text, and the same nodes
are re-run. Line numbers are at this head. The raw red lines are pytest's own `E` / assertion lines,
trimmed to the first failures, with the probe path prefix shortened to `tests/`. The `UV_NATIVE_TLS`
warning line is omitted. E13's first attempt was a two-line edit that left a syntax error (exit 4,
`SyntaxError`), which proves nothing. It was re-taken as the whole-condition edit shown, and only that
run is counted.

| ID | Guarded element (file:line) | Neutralization | Proving nodes | Red | Green after restore |
|---|---|---|---|---|---|
| E7r | issue_contract.py:587 `_first_prose_line` | `line = next((line for line in lines if line.strip()), None)` → `line = " ".join(lines)` (read the whole body) | `test_issue_contract.py::test_first_line_only_a_closing_ref_on_the_second_line_does_not_count` | 1 failed | 1 passed |
| E9r | launcher.py:2685 `_apply_dependency_gate` | `if stack_check.same_commit(resolved_base_commit, head_sha):` → `if True:` | `test_launcher.py::test_dependency_gate_stack_card_base_mismatch_refuses` | 1 failed | 1 passed |
| E10 | launcher.py:2643 `_apply_dependency_gate` | `if mark is not None and not stack_check.same_commit(mark[0], head_sha):` → `if False:` | `test_break_it_stack_card_dependency_advance_2652.py`, `test_break_it_draft_card_dependency_2652.py` | 2 failed | 2 passed |
| E11 | issue_contract.py:652 `_read_layer_membership` | `if not stack_check.same_commit(read_head, head):` → `if False:` | `test_break_it_2652_unlinked_membership_head.py`, `test_break_it_unlinked_membership_snapshot_2652.py` | 2 failed, 1 passed | 3 passed |
| E12 | issue_contract.py:450 `stack_card_mark` | the `_parse_vet_verdict_line(...) != VERDICT_PARKED` test → `if False:` | `test_issue_contract.py::test_stack_card_mark_reads_only_a_line_the_vet_parser_reads_as_parked` | 1 failed | 1 passed |
| E13 | issue_contract.py:595 `_first_prose_line` | the whole plain-line condition (indents, markup characters, `$` pairs, `~~~`) → `if False:` | `test_issue_contract.py::test_first_line_close_in_code_quote_comment_or_html_closes_nothing` | 9 failed, 6 passed | 15 passed |
| E14 | issue_contract.py:590 `_first_prose_line` | `_HTML_COMMENT_RE.sub("\x00", line)` → `.sub("", line)` (a dropped comment no longer breaks a reference) | same node as E13 | 1 failed, 14 passed | 15 passed |
| E20 | issue_contract.py:591 `_first_prose_line` | `_CODE_SPAN_RE.sub("\x00", text)` → `.sub("", text)` (a dropped code span no longer breaks a reference) | same node as E13 | 1 failed, 14 passed | 15 passed |
| E21 | issue_contract.py:592 `_first_prose_line` | `item = _LIST_MARKER_RE.sub("", text, count=1)` → `item = text` (no list-nested indent check) | same node as E13 | 1 failed, 14 passed | 15 passed |
| E15 | launcher.py:2647 `_apply_dependency_gate` | `lapsed = None if accepted is None else {` → `lapsed = None if True else {` | `test_break_it_2652_card_withdrawn.py`, `test_dependency_acceptance_lapse_2652.py` | 3 failed, 6 passed | 9 passed |
| E16 | launcher.py:4508 `_check_premises` | `accepted=accepted` → `accepted=None` in the gate call | `test_break_it_2652_card_withdrawn.py` | 1 failed | 1 passed |
| E17 | launcher.py:2559 `_preflight_accepted` | unreadable evidence `return False` → `return None` | `test_dependency_acceptance_lapse_2652.py::test_the_accepted_row_is_read_only_from_base_state_rows_naming_the_dependency` | 1 failed | 1 passed |
| E18 | launcher.py:2672 `_apply_dependency_gate` | the accepted card's feature test → `if False:` | `test_dependency_acceptance_lapse_2652.py::test_an_accepted_card_dependency_must_name_the_feature_it_was_accepted_for` | 1 failed, 1 passed | 2 passed |
| E19 | launcher.py:989 `walk_preflight` | the base-state `json.dumps(...) if check_id == "base-state" and ...` → `if False` | `test_dependency_acceptance_lapse_2652.py::test_walk_preflight_keeps_base_state_json_evidence_as_its_json_text` | 2 failed | 2 passed |
| E22 | launcher.py:2652 `_apply_dependency_gate` | the draft branch's `if accepted is not None:` → `if lapsed is not None:` | `test_dependency_acceptance_lapse_2652.py::test_an_unaccepted_draft_keeps_the_ungated_pass_even_with_a_stale_card` | 1 failed | 1 passed |

Raw red, per element:

```
E7r  tests/test_issue_contract.py:1074: AssertionError: assert None == 'blocker-open'
E9r  tests/test_launcher.py:7668: AssertionError: a refused launch spawned a builder
E10  tests/test_break_it_stack_card_dependency_advance_2652.py:49: Failed: launch reached worktree creation after its card-marked dependency advanced
     tests/test_break_it_draft_card_dependency_2652.py:49: AssertionError: assert 'dependency-acceptance-lapsed' == 'dependency-card-stale'
E11  E   assert True is False   (test_break_it_2652_unlinked_membership_head.py::test_unlinked_membership_at_a_new_head_cannot_use_the_old_vet)
     tests/test_break_it_unlinked_membership_snapshot_2652.py:29: AssertionError: assert None == 'blockers-unreadable'   ([...03e7-blockers-unreadable]; the same-head case stays green)
E12  tests/test_issue_contract.py:1381: AssertionError: assert ('0000000000000000000000000000000000000007', 50) is None
E13  tests/test_issue_contract.py:1116: AssertionError: > Closes #12
     tests/test_issue_contract.py:1116: AssertionError:     Closes #12
     tests/test_issue_contract.py:1116: AssertionError: <details>Closes #12</details>   (9 of the 15 cases red; first three shown)
E14  tests/test_issue_contract.py:1116: AssertionError: Closes <!-- x --> #12
E20  tests/test_issue_contract.py:1116: AssertionError: Closes `x` #12
E21  tests/test_issue_contract.py:1116: AssertionError: -     Closes #12
E15  tests/test_break_it_2652_card_withdrawn.py:49: Failed: launch reached worktree creation after the dependency lost its card mark
     tests/test_dependency_acceptance_lapse_2652.py:37: AssertionError: assert {'ok': True, ...y-not-ready'}} == {'ok': False,...}
     E   TypeError: 'NoneType' object is not subscriptable   (the [77-False] feature case: the gate returned the neutralized None)
E16  tests/test_break_it_2652_card_withdrawn.py:49: Failed: launch reached worktree creation after the dependency lost its card mark
E17  tests/test_dependency_acceptance_lapse_2652.py:70: AssertionError: Accepted PR #701 at abc
E18  E   assert True is False   (test_an_accepted_card_dependency_must_name_the_feature_it_was_accepted_for[77-False])
E19  E   json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)   (both cases: the dropped evidence read back as "")
E22  tests/test_dependency_acceptance_lapse_2652.py:84: AssertionError: assert {'ok': False,...} == {'ok': True, ...y-not-ready'}}
```

Each red fails on the element's own axis: the second-line close accepted (E7r); a mismatched base let
through to a spawn (E9r); a stale card launched or misnamed (E10); the moved unlinked head accepted (E11);
the two-token card line read as a mark (E12); markup-carried closes accepted (E13); a reference joined across
a dropped comment (E14) or code span (E20); a list-nested indented code line read as prose (E21); a lapsed
acceptance passed ungated (E15, E16); prose evidence read as "nothing accepted" (E17); a card for another
feature passed (E18); JSON evidence dropped (E19); an unaccepted draft refused instead of passing ungated
(E22). After the last restore, the probe worktree's `git status --short` printed nothing.

## Retired entries and the GitHub-link replay (WO-3)

**Retired.** WO-3 (`c1063075742e1aef9d4659e86d418cc69af8ef66`) deleted the first-line reader (`_closes_issue`,
`_first_prose_line` and its comment, code-span and list-marker handling) on the advisor's order, so the entries that
guarded it guard nothing now: **E7, E7r, E13, E14, E20 and E21 are retired**, kept above as history only. The
first-line-only axis they proved is gone with the reader: a blocker's pull request is now found from GitHub's
recorded links (L1-L3 below), never from body text. The other entries above stand; their line numbers are those at
the head each section names.

**Head:** `c1063075742e1aef9d4659e86d418cc69af8ef66`, detached in the same probe worktree, same method and command,
plus `--tb=line -rf`. Line numbers are at this head.

| ID | Guarded element (file:line) | Neutralization | Proving node (`test_github_links_2652.py::`) | Red | Green after restore |
|---|---|---|---|---|---|
| L1 | issue_contract.py:737 `_layer_of` | the timeline gate `if pr["number"] not in cross_referenced: continue` → `if False: continue` | `test_a_body_whose_first_line_closes_the_blocker_is_no_link_without_a_github_record` (the no-body-text axis) | 1 failed | 1 passed |
| L2 | issue_contract.py:740 `_layer_of` | `if pr["base"] != default_branch or number in _closing_refs(...):` → `if True:` | `test_default_base_pr_whose_closing_references_omit_the_blocker_is_not_linked` (case 1, default base) | 1 failed | 1 passed |
| L3 | issue_contract.py:740 `_layer_of` | the same test → `if number in _closing_refs(...):` (a stack layer must have a closing reference too) | `test_stack_layer_is_linked_by_its_timeline_cross_reference_and_reads_no_closing_references` (case 1, stack layer) | 1 failed | 1 passed |
| L4 | issue_contract.py:671 `_closing_refs` | the `hasNextPage is not False` clause removed | `test_closing_references_that_cannot_be_read_in_full_are_unreadable` | 2 failed, 15 passed | 17 passed |
| L5 | issue_contract.py:787 `_layer_of` | `except _Moved`: hold → `raise _Unreadable(str(exc))` | `test_a_stack_membership_read_at_another_head_holds_instead_of_unreadable` | 1 failed | 1 passed |

Raw red:

```
L1  tests/test_github_links_2652.py:114: AssertionError: layer-base   (the case's base id: a body-only "Closes #12" PR was accepted)
L2  tests/test_github_links_2652.py:60: AssertionError: assert None == 'blocker-open'
L3  E   assert False is True   (the stack layer, linked only by its timeline cross-reference, was not accepted)
L4  E   assert True is False   (the [hasNextPage is true] and [hasNextPage is missing] cases read as checked)
L5  tests/test_github_links_2652.py:327: AssertionError: assert 'blockers-unreadable' == 'blocker-open'
```

Each red fails on its own axis: body text alone linked a pull request (L1); a default-base pull request linked with no
closing reference (L2); a stack layer refused its timeline link (L3); a paged closing-reference answer read as whole
(L4); a moved head refused the whole judgement instead of holding (L5). After the last restore, the probe worktree's
`git status --short` printed nothing.

## Review session 3 fixes

Review session 3's fix commits changed code that L1-L4 quote: the timeline gate L1 neutralized became a per-base
choice, and the per-pull-request closing-reference read L2-L4 name became one read of the blocker issue's own
closing pull requests (`closedByPullRequestsReferences`). **L1-L4 are kept as history at `c1063075`**; their tests
still exist and pass, but their neutralizations quote lines that no longer exist. L5 stands.

Each session-3 fix was proved the same way, not by a one-edit neutralization: with the fix commit's code files
stashed (tests kept), the fix's new tests were run on the code before the fix, and each failed; after the stash was
restored, each passed. `git status --short` after each restore showed only the fix's own files.

| Fix commit | Code stashed | Tests that failed on the code before the fix |
|---|---|---|
| `a998e2e0` | `issue_contract.py`, `launcher.py` | the boolean-feature and duplicate-key break-it tests; every default-base pull request's closing references read; a default-base pull request linked by hand with no timeline mention; a parent in another repository read there (5 failed) |
| `6453cd29` | `launcher.py`, `stack_check.py` | the unlink-during-verification break-it test (GraphQL and REST); the dependency-joins-a-stack break-it test; the membership reread (three cases); the stack premise recheck with a withdrawn card (7 failed) |
| `558b6205` | `issue_contract.py`, `launcher.py` | the blocker's closing pull requests read once, by the blocker's number (two tests); a card under a parent in another repository; a not-linked membership read at another head; an accepted layer moved to the launch's own position (5 failed) |
| `342ef18c` | `issue_contract.py` | a parent in another repository records no feature (1 failed) |

Two of the new tests are regression guards that also pass on the code before the fix, by design: a stack layer
closing the blocker with no timeline mention is not linked, and a stack premise with an intact card passes on to the
layer gate.
