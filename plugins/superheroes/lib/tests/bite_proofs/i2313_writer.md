# Bite-proof record — the record writer's raiser source, driven end to end (#2313, WO-I)

Detector file: `plugins/superheroes/lib/tests/test_raised_by_2313.py`, unedited between each red and its green (one comment line was added above the `len(calls) == 2` assertion after both elements' greens; no code changed). Every entry is a targeted, reversible edit to one line of `plugins/superheroes/lib/review_record_session.py`, made and undone with the edit tool (no `git checkout`, `restore`, `reset` or `stash`). Runs: `scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest plugins/superheroes/lib/tests/test_raised_by_2313.py -q -k "<fragment>"`; each capture is the last 40 (element 2 red: 90) lines of the run (`| tail`), which cut nothing; the `UV_NATIVE_TLS` deprecation warning that `uv` prints first is the only line left out of the captures below. No secret, token, URL or personal data appears in any capture, so nothing is redacted. The two guarded elements are the two the order declared; none is grouped.

## 1. The writer's raiser source (`lib/review_record_session.py:1550`, `write_from_session`)

- **Axis:** the writer takes a finding's raiser from another session's record only; a rewrite of this session's own record posts the row's current raiser, not the one its earlier record carried.
- **Detector:** `test_r2_the_writer_posts_the_rows_current_raiser_when_the_session_rewrites_its_own_record` (`-k posts_the_rows_current_raiser`).
- **Neutralization:** `_fill(account, earlier, raisers)` became `_fill(account, earlier, None)`.

**Raw red** (exit 1):

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_r2_the_writer_posts_the_rows_current_raiser_when_the_session_rewrites_its_own_record _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-39/test_r2_the_writer_posts_the_r0')

    def test_r2_the_writer_posts_the_rows_current_raiser_when_the_session_rewrites_its_own_record(tmp_path):
        # axis: the writer takes raisers from another session's record only; a rewrite of this session's own record posts the row's current raiser, not the one its earlier record carried
        session, runs, body = fix_session(tmp_path)
        fake = Fake(runs=runs)
        state_path = os.path.join(session, "loop-state.json")
    
        def set_raiser(raiser):
            with open(state_path, encoding="utf-8") as fh:
                state = json.load(fh)
            assert state["dispositionLedger"]
            for row in state["dispositionLedger"]:
                row[RAISED] = raiser
            with open(state_path, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
        set_raiser("scoped finder")
        out = send(tmp_path, session, fake, ci="green", **body)
        assert out["ok"], out
        assert rr.read(7, readers=fake.readers())["findings"][0][RAISED] == "scoped finder"
        set_raiser("code-reviewer")  # the raiser synthesis moved, in the same session
        out = send(tmp_path, session, fake, ci="green", **body)
        assert out["ok"], out
>       assert rr.read(7, readers=fake.readers())["findings"][0][RAISED] == "code-reviewer"
E       AssertionError: assert 'scoped finder' == 'code-reviewer'
E         
E         - code-reviewer
E         + scoped finder

/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:671: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_r2_the_writer_posts_the_rows_current_raiser_when_the_session_rewrites_its_own_record
1 failed, 85 deselected in 3.49s
```

**Restore:** the inverse edit put `_fill(account, earlier, raisers)` back.
**Restore receipt** (`grep -n "_fill(account"` over the file, after the restore): `1550:        _fill(account, earlier, raisers)` (the other hit, line 1478, is the `def`); `git diff --stat -- plugins/superheroes/lib/review_record_session.py` printed nothing.

**Raw green** (exit 0):

```
.                                                                        [100%]
1 passed, 85 deselected in 7.36s
```

## 2. The writer refuses on a failed history read (`lib/review_record_session.py:1435`, `_other_session_findings`)

- **Axis:** a comments read that fails is not an absent predecessor: the writer refuses `review-record-gh-failed` at the history walk and posts nothing.
- **Detector:** `test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing` (`-k failed_history_read`; parametrized `none`, `non-list`, `raises`). The first `list_comments` call is the latest-record read in `_earlier` (via `review_record.read`); the second is the history walk in `_other_session_findings`; the test passes the first and fails the second, and asserts exactly two calls were made.
- **Neutralization:** in the `except Exception` branch, `raise Refusal("review-record-gh-failed", "the PR comments could not be listed")` became `return []`.

**Raw red** (exit 1; `non-list` and `raises` go red, `none` stays green — see the note below):

```
.FF                                                                      [100%]
=================================== FAILURES ===================================
_ test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing[non-list] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_r2_a_failed_history_read_1')
failure = 'non-list'

    @pytest.mark.parametrize("failure", ["none", "non-list", "raises"])
    def test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing(tmp_path, failure):
        # axis: a comments read that fails is not an absent predecessor: the writer refuses review-record-gh-failed and posts nothing
        session, runs, body = fix_session(tmp_path)
        fake = Fake(runs=runs)
        calls = []
        inner = fake.readers()["list_comments"]
    
        def list_comments(pr, repo):
            calls.append((pr, repo))
            if len(calls) == 1:  # the latest-record read in `_earlier`
                return inner(pr, repo)
            if failure == "raises":  # the history walk in `_other_session_findings`
                raise OSError("gh down")
            return None if failure == "none" else {"not": "a list"}
        out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green", **body)), str(tmp_path),
                                    {**fake.readers(), "list_comments": list_comments})
>       assert len(calls) == 2, calls
E       AssertionError: [(7, 'o/r'), (7, 'o/r'), (7, 'o/r')]
E       assert 3 == 2
E        +  where 3 = len([(7, 'o/r'), (7, 'o/r'), (7, 'o/r')])

/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:645: AssertionError
_ test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing[raises] _

tmp_path = PosixPath('/tmp/claude-0/pytest-of-root/pytest-41/test_r2_a_failed_history_read_2')
failure = 'raises'

    @pytest.mark.parametrize("failure", ["none", "non-list", "raises"])
    def test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing(tmp_path, failure):
        # axis: a comments read that fails is not an absent predecessor: the writer refuses review-record-gh-failed and posts nothing
        session, runs, body = fix_session(tmp_path)
        fake = Fake(runs=runs)
        calls = []
        inner = fake.readers()["list_comments"]
    
        def list_comments(pr, repo):
            calls.append((pr, repo))
            if len(calls) == 1:  # the latest-record read in `_earlier`
                return inner(pr, repo)
            if failure == "raises":  # the history walk in `_other_session_findings`
                raise OSError("gh down")
            return None if failure == "none" else {"not": "a list"}
        out = rs.write_from_session(session, put_extras(tmp_path, extras(ci="green", **body)), str(tmp_path),
                                    {**fake.readers(), "list_comments": list_comments})
>       assert len(calls) == 2, calls
E       AssertionError: [(7, 'o/r'), (7, 'o/r'), (7, 'o/r')]
E       assert 3 == 2
E        +  where 3 = len([(7, 'o/r'), (7, 'o/r'), (7, 'o/r')])

/home/user/wt-2313/plugins/superheroes/lib/tests/test_raised_by_2313.py:645: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing[non-list]
FAILED plugins/superheroes/lib/tests/test_raised_by_2313.py::test_r2_a_failed_history_read_refuses_with_gh_failed_and_posts_nothing[raises]
2 failed, 1 passed, 83 deselected in 3.31s
```

**What bites, and what does not.** The red is the call-count assertion (`len(calls) == 2`): with the branch returning `[]` the writer carries on to `review_record.write`, which reads the comments a third time, fails the same way, and refuses `review-record-gh-failed` itself with nothing posted. So the `ok`/`reason` and `fake.writes == []` assertions alone stay green under this neutralization; the call count is what tells a refusal at the history walk from one further on. The `none` variant stays green under this neutralization: `review_record._comments` raises `Refusal` for `None` before the neutralized branch is reached (`except Refusal: raise`), so that variant is guarded by the `except Refusal` / `_comments` path, not by this branch.

**Restore:** the inverse edit put `raise Refusal("review-record-gh-failed", "the PR comments could not be listed")` back.
**Restore receipt** (`sed -n 1432,1436p`, after the restore; `git diff -- plugins/superheroes/lib/review_record_session.py` printed nothing):

```
    except Refusal:
        raise
    except Exception:  # noqa: BLE001 — a failed history read must refuse, never read as an absent predecessor
        raise Refusal("review-record-gh-failed", "the PR comments could not be listed")
    for comment in reversed(marked):
```

**Raw green** (exit 0):

```
...                                                                      [100%]
3 passed, 83 deselected in 3.46s
```
