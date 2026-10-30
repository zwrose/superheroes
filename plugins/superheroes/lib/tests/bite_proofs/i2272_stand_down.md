# #2272 WO4 bite-proofs — a superseded cloud builder stands down

Detector file: `plugins/superheroes/lib/tests/test_i2272_stand_down.py`. Production surface: `plugins/superheroes/lib/cloud_builder.py`
(`superseded`, `_opens_with`, `TERMINAL_HEADERS`, `STAND_DOWN_HEADER`, `SUPERSEDED_HEADER`) and three doc files.
Every command below ran from the worktree root as
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:randomly`.
Each capture drops pytest's first output line, `warning: The UV_NATIVE_TLS environment variable is deprecated …`, which is the
launcher's own noise. Each neutralization was undone by the inverse edit (never `git checkout`, `git restore`, `git reset` or
`git stash`). No secrets or private URLs appear in any capture.

## BP1 — the "later than own" comparison (`test_same_created_at_with_a_smaller_id_is_not_superseded`)

**Guarded element:** `cloud_builder.py` `superseded`, the `newer` filter's `(created, cid) > own[0]` — axis: a launch is newer only when it
is later than the own intake, or the same second with a larger id.

**Neutralization:** `(created, cid) > own[0]` became `created >= own[0][0]` (`>=` with no id tie-break).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_same_created_at_with_a_smaller_id_is_not_superseded" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_same_created_at_with_a_smaller_id_is_not_superseded ___________

    def test_same_created_at_with_a_smaller_id_is_not_superseded():
>       assert _superseded([_intake(OWN, 0), _intake(OWN - 1, 0)])["superseded"] is False
E       assert True is False

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:126: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_same_created_at_with_a_smaller_id_is_not_superseded
1 failed in 0.42s
```

**Restore:** the inverse edit put `(created, cid) > own[0]` back.

**Restore receipt:** `grep -n "(created, cid) > own"` printed `649:             if (created, cid) > own[0] and cid != own_intake_id`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.37s
```

---

## BP2 — the intake header must open the comment (`test_a_header_quoted_mid_body_is_not_a_newer_launch`)

**Guarded element:** `cloud_builder.py` `_opens_with`, `text.lstrip().startswith(headers)` — axis: a comment is a launch only when its
(footer-stripped, leading-whitespace-stripped) body starts with the header, never when it merely quotes it.

**Neutralization:** `text.lstrip().startswith(headers)` became `any(h in text for h in headers)` (`in`).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_header_quoted_mid_body_is_not_a_newer_launch" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_a_header_quoted_mid_body_is_not_a_newer_launch ______________

    def test_a_header_quoted_mid_body_is_not_a_newer_launch():
        quoting = _comment(101, "I saw the earlier comment:\n" + CB.INTAKE_HEADER + " Plugin 0.47.0. and a notice\n"
                           + CB.SUPERSEDED_HEADER, _at(1))
>       assert _superseded([_intake(OWN, 0), quoting])["superseded"] is False
E       assert True is False

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:112: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_header_quoted_mid_body_is_not_a_newer_launch
1 failed in 2.08s
```

**Restore:** the inverse edit put `text.lstrip().startswith(headers)` back.

**Restore receipt:** `grep -n "text.lstrip().startswith(headers)"` printed `618:    return text is not None and text.lstrip().startswith(headers)`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.24s
```

---

## BP3 — the comments are read whole (`test_comments_not_read_whole_is_a_refusal`)

**Guarded element:** `cloud_builder.py` `superseded`, the `if comments is None:` refusal `comments-unreadable` — axis: a failed read is a
refusal, never an issue with no comments.

**Neutralization:** `return {"ok": False, "reason": "comments-unreadable"}` became `comments = []` (a failed read treated as no comments).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_comments_not_read_whole_is_a_refusal" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
__________________ test_comments_not_read_whole_is_a_refusal ___________________

    def test_comments_not_read_whole_is_a_refusal():
>       assert _superseded([_intake(OWN, 0), _intake(101, 1)], fail=True) == {"ok": False, "reason": "comments-unreadable"}
E       AssertionError: assert {'ok': False,...ke-not-found'} == {'ok': False,...s-unreadable'}
E         
E         Omitting 1 identical items, use -vv to show
E         Differing items:
E         {'reason': 'own-intake-not-found'} != {'reason': 'comments-unreadable'}
E         Use -v to get more diff

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:131: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_comments_not_read_whole_is_a_refusal
1 failed in 0.25s
```

**Restore:** the inverse edit put `return {"ok": False, "reason": "comments-unreadable"}` back.

**Restore receipt:** `sed -n 635,638p` printed the axis comment, `    if comments is None:`, `        return {"ok": False, "reason": "comments-unreadable"}`, `    stamped = []`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.41s
```

---

## BP4 — the stand-down header is not a terminal header (`test_the_stand_down_is_not_read_as_any_other_builder_comment`)

**Guarded element:** `cloud_builder.py` line 90, `TERMINAL_HEADERS`, and the `STAND_DOWN_HEADER` constant beside it — axis: the stand-down is not the
newer lane's ending, so no terminal reader may read it as one.

**Neutralization:** `TERMINAL_HEADERS` gained `"stand-down": "Builder stand-down (cloud build)."` (the stand-down header added to it).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_the_stand_down_is_not_read_as_any_other_builder_comment" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_the_stand_down_is_not_read_as_any_other_builder_comment _________

    def test_the_stand_down_is_not_read_as_any_other_builder_comment():
        text = CB.stand_down_text("https://github.com/%s/issues/%d#issuecomment-101" % (REPO, ISSUE))
        for body in (text, text + "\n" + CB.CLOUD_FOOTER):
>           assert CB.terminal_kind(body) is None
E           AssertionError: assert 'stand-down' is None
E            +  where 'stand-down' = <function terminal_kind at 0x7fbfd8a19a80>('Builder stand-down (cloud build).\n\nA newer launch took this issue over (its intake: https://github.com/owner/repo/issues/17#issuecomment-101). This session stopped when it woke: it pushed nothing after waking and will push nothing more.')
E            +    where <function terminal_kind at 0x7fbfd8a19a80> = CB.terminal_kind

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:162: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_the_stand_down_is_not_read_as_any_other_builder_comment
1 failed in 0.28s
```

**Restore:** the inverse edit removed the added entry.

**Restore receipt:** `sed -n 90p` printed `TERMINAL_HEADERS = {"handback": HANDBACK_HEADER, "stop": STOP_HEADER, "park": PARK_HEADER}`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.20s
```

---

## BP5 — the supersession notice counts as a newer launch (`test_a_notice_later_than_the_own_intake_supersedes_and_is_named`)

**Guarded element:** `cloud_builder.py` `superseded`, the `newer` filter's `_opens_with(comment.get("body"), INTAKE_HEADER, SUPERSEDED_HEADER)` —
axis: the advisor's notice, posted before a successor on any machine, stops an earlier builder that wakes.

**Neutralization:** `INTAKE_HEADER, SUPERSEDED_HEADER` became `INTAKE_HEADER` (the notice dropped from the filter).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_later_than_the_own_intake_supersedes_and_is_named" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_a_notice_later_than_the_own_intake_supersedes_and_is_named ________

    def test_a_notice_later_than_the_own_intake_supersedes_and_is_named():
        result = _superseded([_intake(OWN, 0), _notice(101, 2)])
>       assert result["superseded"] is True
E       assert False is True

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:195: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_later_than_the_own_intake_supersedes_and_is_named
1 failed in 0.31s
```

**Restore:** the inverse edit put `INTAKE_HEADER, SUPERSEDED_HEADER` back.

**Restore receipt:** `sed -n 647,651p` printed `and _opens_with(comment.get("body"), INTAKE_HEADER, SUPERSEDED_HEADER)]` as the filter's last line.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.34s
```

---

## BP6 — `cloud.md` tells a waking builder to push nothing (`test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing`)

**Guarded element:** `skills/workhorse/reference/cloud.md` § Workspace, "On `superseded: true`, push nothing, post its `comment` …" — axis: a doc pin.

**Neutralization:** the words `push nothing, ` removed from that sentence.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing" -q -p no:randomly
```

**Red run** (the `E` line's file dump is elided by pytest itself; nothing was cut by me):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing _____

    def test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing():
        text = _doc("skills/workhorse/reference/cloud.md")
        assert "cloud_builder.py superseded" in text
>       assert "On `superseded: true`, push nothing" in text
E       assert 'On `superseded: true`, push nothing' in "# Contents\n\n- [Building in a cloud session](#building-in-a-cloud-session)\n  - [When this file applies](#when-this-...r's path |\n\nThis page adds `gh api` reads only: the pull request, the issue and its comments, and the\nrepository.\n"

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:251: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_cloud_reference_tells_a_waking_builder_to_check_and_push_nothing
1 failed in 0.31s
```

**Restore:** the inverse edit put `push nothing, ` back.

**Restore receipt:** `grep -n "On .superseded: true"` printed `89:On `superseded: true`, push nothing, post its `comment` on the issue as it is, and end the turn; do`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP7 — `orchestration.md` drops the deleted-branch exemption (`test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone`)

**Guarded element:** `skills/showrunner/reference/orchestration.md` § Adoption mechanics, the "Send a NOT-READY back…" bullet — axis: a doc pin
(the removed sentence pair stays removed).

**Neutralization:** the removed sentence pair was put back ("A bound lane whose branch is gone from the remote needs no session listing, but a
listing you supply that shows its session live still refuses `adopt-original-session-live`: a deleted branch does not stop its builder.").

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone" -q -p no:randomly
```

**Red run** (I piped this one through `cut -c1-400`, which cut the long `E` lines at 400 columns; the cut is mine, not pytest's):
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone ____

    def test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone():
        text = " ".join(_doc("skills/showrunner/reference/orchestration.md").split())
>       assert "A bound lane whose branch is gone from the remote needs no session listing" not in text
E       assert 'A bound lan...sion listing' not in "# Contents ...'s go-ahead."
E         
E         'A bound lane whose... no session listing' is contained here:
E         ?                                                                                                                                                                                                                                                                                                                                                                                                     
E         
E         ...Full output truncated, use '-vv' to show

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:256: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_orchestration_no_longer_exempts_a_bound_lane_whose_branch_is_gone
1 failed in 0.24s
```

**Restore:** the inverse edit removed the put-back sentence pair again.

**Restore receipt:** `grep -c "A bound lane whose" …/orchestration.md` printed `0`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.31s
```

---

## BP8 — `orchestration.md` names `helper-read` and its four fields (`test_orchestration_names_the_helper_read_and_its_four_fields`)

**Guarded element:** `skills/showrunner/reference/orchestration.md` § Acting on the builders' account, the cloud-helper read: "The prompt comes
from `cloud_recover.py helper-read …`, and the helper posts only the four fields `cloud_recover.HELPER_READ_FIELDS` names (the fields the takeover check reads) per session" — axis: a doc pin.
The section is guarded by `test_c8c_relay_doctrine.py`, which forbids the substring `session_`, so the doc names the fields through `cloud_recover.HELPER_READ_FIELDS` rather than listing them (WO4b).

**Neutralization:** the phrase "only the four fields `cloud_recover.HELPER_READ_FIELDS` names (the fields the takeover check reads)" put back to the earlier literal list "only `id`, `session_status`, `status_bucket` and `archived`". The `helper-read` command stays in the sentence, so the red lands on the second assertion.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_orchestration_names_the_helper_read_and_its_four_fields" -q -p no:randomly
```

**Red run** (piped through `cut -c1-300`; the cut `E` line is mine). The first assertion (`helper-read`) passes; the red is the second (`cloud_recover.HELPER_READ_FIELDS`):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_orchestration_names_the_helper_read_and_its_four_fields _________

    def test_orchestration_names_the_helper_read_and_its_four_fields():
        text = " ".join(_doc("skills/showrunner/reference/orchestration.md").split())
        assert "cloud_recover.py helper-read" in text
>       assert "`cloud_recover.HELPER_READ_FIELDS`" in text
E       assert '`cloud_recover.HELPER_READ_FIELDS`' in "# Contents - [Orchestration — launcher, ledger, and wave mechanics](#orchestration--launcher-ledger-and-wave-mechanic..., so the session's permission classifier refuses its merges and pushes on the others, even after the owner's go-ahead."

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:262: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_orchestration_names_the_helper_read_and_its_four_fields
1 failed in 0.28s
```

**Restore:** the inverse edit put the new phrase back.

**Restore receipt:** the sentence reads again "…since a cloud session cannot message back. The prompt comes from `cloud_recover.py helper-read --repo O/N --issue N --session-id S …`, and the helper posts only the four fields `cloud_recover.HELPER_READ_FIELDS` names (the fields the takeover check reads) per session (never usage or cost data: the issue is public)." `grep -n "session_"` over the file prints nothing.

**Green run:**
```
.                                                                        [100%]
1 passed in 2.16s
```

---

## BP9 — `launch-doctrine.md` § Recovery names the usage-limit recovery (`test_launch_doctrine_recovery_names_the_usage_limit_recovery`)

**Guarded element:** `rubric/launch-doctrine.md` § Recovery, the final paragraph of "Read liveness from the right signals" — axis: a doc pin.

**Neutralization:** the whole paragraph ("A cloud lane stopped by its account's usage limit … at the reset time it read.") removed.

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_launch_doctrine_recovery_names_the_usage_limit_recovery" -q -p no:randomly
```

**Red run** (piped through `cut -c1-300`; the cut `E` line is mine):
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_launch_doctrine_recovery_names_the_usage_limit_recovery _________

    def test_launch_doctrine_recovery_names_the_usage_limit_recovery():
        text = _doc("rubric/launch-doctrine.md")
        section = text.split("## Recovery — taking over a build that stopped", 1)[1].split("\n## ", 1)[0]
        section = " ".join(section.split())
>       assert "usage limit" in section
E       assert 'usage limit' in "A launched builder can stop for reasons unrelated to its work — the account it burns hits a limit, the host kills the...owrunner's [wave-watch reference](../skills/showrunner/reference/wave-watch.md#before-treating-lane-stale-as-a-wedge)."

/home/user/wt-2272-wo4/plugins/superheroes/lib/tests/test_i2272_stand_down.py:269: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_launch_doctrine_recovery_names_the_usage_limit_recovery
1 failed in 0.33s
```

**Restore:** the inverse edit put the paragraph back; the file's trailing newline, lost by that edit, was restored by a second edit.

**Restore receipt:** `git diff plugins/superheroes/rubric/launch-doctrine.md` shows 8 inserted lines and no "No newline at end of file" marker; `git diff | grep -c "No newline"` printed `0`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.26s
```
