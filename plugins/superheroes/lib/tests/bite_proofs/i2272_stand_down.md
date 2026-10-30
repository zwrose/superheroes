# #2272 WO4 bite-proofs — a superseded cloud builder stands down

Detector file: `plugins/superheroes/lib/tests/test_i2272_stand_down.py`. Production surface: `plugins/superheroes/lib/cloud_builder.py`
(`superseded`, `_opens_with`, `TERMINAL_HEADERS`, `STAND_DOWN_HEADER`, `SUPERSEDED_HEADER`) and three doc files.
Every command below ran from the worktree root as
`scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest <node> -q -p no:randomly`.
Each capture drops pytest's first output line, `warning: The UV_NATIVE_TLS environment variable is deprecated …`, which is the
launcher's own noise. Each neutralization was undone by the inverse edit (never `git checkout`, `git restore`, `git reset` or
`git stash`). No secrets or private URLs appear in any capture.

## BP1 — the "later than the builder's start" comparison (`test_a_notice_created_in_the_start_second_does_not_supersede`)

**Guarded element:** `cloud_builder.py` `superseded`, the `newer` filter's `created > started_at` — axis: a newer launch is shown only by a
supersession notice created strictly later than the builder's own start time (`--started`, UTC ISO), never by an intake comment's order.

**Neutralization:** `created > started_at` became `created >= started_at` (`>=`).

**Command:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_created_in_the_start_second_does_not_supersede" -q -p no:randomly
```

**Red run:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
_________ test_a_notice_created_in_the_start_second_does_not_supersede _________

    def test_a_notice_created_in_the_start_second_does_not_supersede():
>       assert _superseded([_notice(101, 2)], started=_at(2))["superseded"] is False
E       assert True is False

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_created_in_the_start_second_does_not_supersede
1 failed in 0.37s
```

**Restore:** the inverse edit put `created > started_at` back.

**Restore receipt:** `grep -n "created > started_at"` printed `647:             if created > started_at and _opens_with(comment.get("body"), SUPERSEDED_HEADER)]`.

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
>       assert _superseded([quoting])["superseded"] is False
E       assert True is False

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:130: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_header_quoted_mid_body_is_not_a_newer_launch
1 failed in 0.29s
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
The red run below is from that neutralization against the start-time reader.

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
>       assert _superseded([_notice(101, 1)], fail=True) == {"ok": False, "reason": "comments-unreadable"}
E       AssertionError: assert {'ok': True, ...omment': None} == {'ok': False,...s-unreadable'}
E         
E         Differing items:
E         {'ok': True} != {'ok': False}
E         Left contains 3 more items:
E         {'comment': None, 'newerLaunch': None, 'superseded': False}
E         Right contains 1 more item:
E         {'reason': 'comments-unreadable'}
E         Use -v to get more diff

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:140: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_comments_not_read_whole_is_a_refusal
1 failed in 0.22s
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

## BP5 — only the supersession notice shows a newer launch (`test_a_notice_later_than_the_start_supersedes_and_stand_down_names_it`, `test_a_delayed_own_intake_posted_after_the_notice_does_not_reverse_the_supersession`)

**Guarded element:** `cloud_builder.py` `superseded`, the `newer` filter's `_opens_with(comment.get("body"), SUPERSEDED_HEADER)` —
axis: the advisor's notice, posted before a successor on any machine, stops an earlier builder that wakes; an intake comment, which a
delayed post can land in any order, never shows a newer launch.

**Neutralization A:** `SUPERSEDED_HEADER` became `INTAKE_HEADER` (the notice dropped from the filter, intakes counted instead).
**Neutralization B:** `SUPERSEDED_HEADER` became `INTAKE_HEADER, SUPERSEDED_HEADER` (intakes counted beside the notice).

**Command A:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_later_than_the_start_supersedes_and_stand_down_names_it" -q -p no:randomly
```

**Red run A:**
```
F                                                                        [100%]
=================================== FAILURES ===================================
____ test_a_notice_later_than_the_start_supersedes_and_stand_down_names_it _____

    def test_a_notice_later_than_the_start_supersedes_and_stand_down_names_it():
        result = _superseded([_intake(100, 0), _notice(101, 1)])
>       assert result["ok"] is True and result["superseded"] is True
E       assert (True is True and False is True)

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:70: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_notice_later_than_the_start_supersedes_and_stand_down_names_it
1 failed in 0.23s
```

**Command B:**
```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_delayed_own_intake_posted_after_the_notice_does_not_reverse_the_supersession" -q -p no:randomly
```

**Red run B:**
```
    def test_a_delayed_own_intake_posted_after_the_notice_does_not_reverse_the_supersession():
        comments = [_notice(100, 1), _intake(101, 2), _intake(102, 3)]
        result = _superseded(comments)
>       assert result["superseded"] is True and result["newerLaunch"]["commentId"] == 100
E       assert (True is True and 102 == 100)

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:94: AssertionError
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_delayed_own_intake_posted_after_the_notice_does_not_reverse_the_supersession
1 failed in 20.54s
```

**Restore:** the inverse edit put `_opens_with(comment.get("body"), SUPERSEDED_HEADER)` back after each.

**Restore receipt:** `sed -n 645,647p` printed the axis comment, `    newer = [...` and `             if created > started_at and _opens_with(comment.get("body"), SUPERSEDED_HEADER)]`.

**Green run:**
```
.                                                                        [100%]
1 passed in 0.35s
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

---

## BP6 — a notice supersedes by launch identity, not by time (`test_a_notice_naming_another_launch_never_supersedes`, `test_a_launch_id_is_matched_as_a_whole_token`, `test_a_notice_older_than_the_builders_own_intake_still_supersedes_it`)

**Guarded element:** `cloud_builder.py` `superseded`, the `newer` filter's `_names_launch(comment["body"], launch_id)` — axis: a newer launch is shown by a `SUPERSEDED_HEADER` comment that names exactly the builder's own launch id as a whole token, whatever its time (`--launch-id`; the start-time rule is gone).

**Neutralization:** `and _names_launch(comment["body"], launch_id)]` became `and True]`.

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_i2272_stand_down.py -q -p no:randomly`

**Red run:** `6 failed, 51 passed`: `test_a_notice_naming_another_launch_never_supersedes` and the five `test_a_launch_id_is_matched_as_a_whole_token[...]` cases (`launch-12`, `launch-10`, `xlaunch-1`, `launch-1-x`, `launch-1_a`).

**Restore:** the inverse edit put `_names_launch(comment["body"], launch_id)` back.

**Green run:** `57 passed` for the file.

## BP10 — a whole notice quoted mid-body is not a newer launch (`test_a_header_quoted_mid_body_is_not_a_newer_launch`)

**Guarded element:** `cloud_builder.py` `_opens_with`, `text.lstrip().startswith(headers)` — axis: the comment quotes a complete supersession notice naming the builder's own launch id (`LAUNCH`) after other text, so only the header-at-start rule rejects it.

**Neutralization:** `text.lstrip().startswith(headers)` became `any(h in text for h in headers)` (substring containment).

**Command:** `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest "plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_header_quoted_mid_body_is_not_a_newer_launch" -q -p no:randomly`

**Red (final lines):**
```
E       assert True is False

/home/user/wt-2272/plugins/superheroes/lib/tests/test_i2272_stand_down.py:139: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_i2272_stand_down.py::test_a_header_quoted_mid_body_is_not_a_newer_launch
1 failed in 0.37s
```

**Restore:** the inverse edit put `text.lstrip().startswith(headers)` back; `git diff --stat -- plugins/superheroes/lib/cloud_builder.py` printed nothing.

**Green (final lines):**
```
.                                                                        [100%]
1 passed in 0.31s
```
