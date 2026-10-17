# #1901 bite-proof — every cloud GitHub list read pages by number (WO-1: `gh_pages.read` and the five reads moved onto it)

Per-element bite-proof for the detectors added in `plugins/superheroes/lib/tests/test_gh_pages.py` over `plugins/superheroes/lib/gh_pages.py` and its five callers, following `plugins/superheroes/rubric/bite-proof.md`. Each element was neutralized with one targeted edit, its single test node ran alone and went red, the edit was undone by the inverse edit (the restored lines are quoted back below), and the same node ran green. No test file was edited between a red and its green. The implementer (WO-1, build worktree) ran these once; the orchestrator re-runs them.

Command for every run (never `-k`, never filtered):

```
scripts/pinned-python -B -X pycache_prefix=/tmp/superheroes-pyc -m pytest 'plugins/superheroes/lib/tests/test_gh_pages.py::<node>' -q -p no:cacheprovider
```

`T` = `plugins/superheroes/lib/tests/test_gh_pages.py`.

Declared guarded-element set: G1–G8, as dispatched. Redaction: the one `warning: The UV_NATIVE_TLS environment variable is deprecated ...` line every run printed first is omitted; the `Exit code 1` wrapper line is omitted. Local object addresses are left as printed.

## Summary

| ID | Guarded element | Axis | Neutralization | Node | Red |
|---|---|---|---|---|---|
| G1 | `cloud_cleanup._pages` reads by page number | cleanup's branch and open-PR lists past 100 rows under the cloud proxy | the site back to `_gh(run, ["api", "--paginate", path], env)` + the concatenated-page decoder | `T::test_cloud_cleanup_reads_branches_and_open_prs_page_by_number` | `assert None == [{'name': 'b000', ...}]` |
| G2 | `cloud_parked._comments` reads by page number | the parked-PR comment list past 100 rows | the site back to `_gh(run, ["api", "--paginate", ...])` + an inline concatenated-page parse | `T::test_cloud_parked_reads_every_comment_page_by_number` | `assert None == [{'id': 0, ...}]` |
| G3 | `cloud_recover._newest_comment` reads by page number | the recovery comment list past 100 rows, `?since` on the path | the site back to `cb._gh(run, ["api", "--paginate", endpoint], ...)` + an inline concatenated-page parse | `T::test_cloud_recover_finds_the_newest_comment_on_page_three_by_number` | `assert False is True` (`read`) |
| G4 | `vet_slot._read_comments` reads by page number | the vet's comment list past 100 rows | the site back to `... "--paginate", "--slurp"` + `_gh_json` + the pages-are-lists check | `T::test_vet_slot_reads_every_comment_page_by_number` | `vet_slot._Refusal: read-failed` |
| G5 | `pr_comment.list_comments` reads by page number | the test-pilot comment upsert's list past 100 rows | the site back to `_gh("api", ..., "--paginate")` + `_parse_paginated_arrays` inlined | `T::test_pr_comment_list_comments_reads_every_page_by_number` | `RuntimeError: ... --paginate... failed: HTTP 403` |
| G6 | `gh_pages.read` empty page after a full one | the end of a list: exactly 100 rows read in full, not failed | inserted `if not page:` / `return None` before `rows.extend(page)` | `T::test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read[100-pages2]` | `assert None == [{'n': 0}, ...]` |
| G7 | `gh_pages.read` failed page read | the complete-or-absent list: a failed page never reads as the end of the list | `page = None if out is None else json.loads(out)` → `page = [] if out is None else json.loads(out)` | `T::test_a_page_that_fails_makes_the_whole_read_unavailable` | `assert [] is None` |
| G8 | the census | no lib module reads a GitHub list through gh's paginate flag | a string constant `"--paginate"` added to `cloud_cleanup._pages`'s fetch argv | `T::test_the_only_paginate_flag_left_under_lib_is_gits_pager_flag_and_the_cloud_recipe_pages_by_number` | `Extra items in the left set: 'cloud_cleanup.py'` |

G1–G5 are the issue's cloud-shape proof: with a site reverted to the paginate flag, the shared cloud-proxy fake answers page 1 and `HTTP 403`, so its D1 test fails; restored, it passes.

G7 note: the node loops over a failed page 1, 2 and 3. The neutralized run went red on the first iteration (page 1). A failed middle page goes through the same line, so it is the same failure mode.

G2, G3 and G5 inline the removed `pr_comment._parse_paginated_arrays` body in the neutralization only; the production file has no such function.

## G1 — `cloud_cleanup._pages` reads by page number

Neutralization: `plugins/superheroes/lib/cloud_cleanup.py` `_pages`, the `fetch` adapter and the `gh_pages.read` call (lines 185–189) →

```
    code, out, _ = _gh(run, ["api", "--paginate", path], env)
    if code != 0 or not out.strip():
        return None
    decoder, at, found = json.JSONDecoder(), 0, []
    try:
        while True:
            while at < len(out) and out[at] in " \r\n\t":
                at += 1
            if at >= len(out):
                break
            page, at = decoder.raw_decode(out, at)
            if not isinstance(page, list):
                return None
            found.extend(page)
    except ValueError:
        return None
    return found if all(isinstance(i, dict) for i in found) else None
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
________ test_cloud_cleanup_reads_branches_and_open_prs_page_by_number _________

    def test_cloud_cleanup_reads_branches_and_open_prs_page_by_number():
        # axis: cleanup's branch and open-PR lists past 100 rows; --paginate refused by the proxy would make every branch unreadable
        rows = [{"name": "b%03d" % i, "base": {"ref": "main"} if i < 249 else {"ref": "feature"}} for i in range(250)]
        proxy = CloudProxy(rows)
>       assert CC._pages(proxy, "repos/o/r/branches", {}) == rows
E       AssertionError: assert None == [{'name': 'b000', 'base': {'ref': 'main'}}, {'name': 'b001', 'base': {'ref': 'main'}}, {'name': 'b002', 'base': {'ref'...', 'base': {'ref': 'main'}}, {'name': 'b004', 'base': {'ref': 'main'}}, {'name': 'b005', 'base': {'ref': 'main'}}, ...]
E        +  where None = <function _pages at 0x7f117c6ad580>(<test_gh_pages.CloudProxy object at 0x7f117d083ec0>, 'repos/o/r/branches', {})
E        +    where <function _pages at 0x7f117c6ad580> = CC._pages

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:75: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_cloud_cleanup_reads_branches_and_open_prs_page_by_number
1 failed in 0.20s
```

Restore: the inverse edit. Restored lines (`cloud_cleanup.py` 182–189):

```
def _pages(run, path, env):
    """Every item of a paginated REST list, read page by number, or None when any page failed or the rows
    were not all JSON objects (a page that is a bare object, such as `{}`, is unreadable)."""
    def fetch(endpoint):
        code, out, _ = _gh(run, ["api", endpoint], env)
        return out if code == 0 else None
    found = _sib("gh_pages").read(fetch, path)
    return found if found is not None and all(isinstance(i, dict) for i in found) else None
```

Green: `1 passed in 0.19s`

## G2 — `cloud_parked._comments` reads by page number

Neutralization: `plugins/superheroes/lib/cloud_parked.py` `_comments`, the `fetch` adapter and the `gh_pages.read` call →

```
    code, out = _sib("cloud_builder")._gh(run, ["api", "--paginate", "repos/%s/issues/%d/comments" % (repo, pr)], env)
    try:
        dec, idx, found = json.JSONDecoder(), 0, []
        while code == 0 and idx < len(out):
            while idx < len(out) and out[idx] in " \r\n\t":
                idx += 1
            if idx >= len(out):
                break
            obj, idx = dec.raw_decode(out, idx)
            found.extend(obj if isinstance(obj, list) else [obj])
        found = found if code == 0 else None
    except ValueError:
        return None
    return found
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____________ test_cloud_parked_reads_every_comment_page_by_number _____________

    def test_cloud_parked_reads_every_comment_page_by_number():
        # axis: the parked-PR comment list past 100 rows; --paginate refused by the proxy, or a first-page read
        rows = [{"id": i, "body": "chat %d" % i} for i in range(250)]
        proxy = CloudProxy(rows)
>       assert CP._comments("o/r", 7, {}, proxy) == rows
E       AssertionError: assert None == [{'id': 0, 'body': 'chat 0'}, {'id': 1, 'body': 'chat 1'}, {'id': 2, 'body': 'chat 2'}, {'id': 3, 'body': 'chat 3'}, {'id': 4, 'body': 'chat 4'}, {'id': 5, 'body': 'chat 5'}, ...]
E        +  where None = <function _comments at 0x7f9c517ae480>('o/r', 7, {}, <test_gh_pages.CloudProxy object at 0x7f9c529b21e0>)
E        +    where <function _comments at 0x7f9c517ae480> = CP._comments

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:99: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_cloud_parked_reads_every_comment_page_by_number
1 failed in 5.46s
```

Restore: the inverse edit. Restored lines (`cloud_parked.py` 183–188):

```
def _comments(repo, pr, env, run):
    def fetch(endpoint):
        code, out = _sib("cloud_builder")._gh(run, ["api", endpoint], env)
        return out if code == 0 else None
    found = _sib("gh_pages").read(fetch, "repos/%s/issues/%d/comments" % (repo, pr))
    return found if found is not None and all(isinstance(c, dict) for c in found) else None
```

Green: `1 passed in 0.22s`

## G3 — `cloud_recover._newest_comment` reads by page number

Neutralization: `plugins/superheroes/lib/cloud_recover.py` `_newest_comment`, from `git_env = cb._git_env(env)` through `comments = _sib("gh_pages").read(fetch, endpoint)` →

```
    code, out = cb._gh(run, ["api", "--paginate", endpoint], cb._git_env(env))
    try:
        comments, dec, idx = [], json.JSONDecoder(), 0
        while code == 0 and idx < len(out):
            while idx < len(out) and out[idx] in " \r\n\t":
                idx += 1
            if idx >= len(out):
                break
            obj, idx = dec.raw_decode(out, idx)
            comments.extend(obj if isinstance(obj, list) else [obj])
        comments = comments if code == 0 else None
    except (ValueError, TypeError):
        comments = None
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_____ test_cloud_recover_finds_the_newest_comment_on_page_three_by_number ______

    def test_cloud_recover_finds_the_newest_comment_on_page_three_by_number():
        # axis: the recovery comment list past 100 rows (a ?since query on the path); the newest accepted row sits on page 3
        def row(i, hour, body):
            return {"id": i, "html_url": "https://x/c/%d" % i, "body": body,
                    "created_at": "2026-10-12T%02d:00:00Z" % hour, "updated_at": "2026-10-12T%02d:00:00Z" % hour}
        rows = [row(i, 1, "chatter") for i in range(250)]
        rows[5] = row(5, 2, "take early")
        rows[230] = row(230, 9, "take late")
        proxy = CloudProxy(rows)
        since = CR._epoch("2026-10-12T00:00:00Z")
        found, read = CR._newest_comment("o/r", 17, since, {}, proxy, lambda body: body.startswith("take"))
>       assert read is True
E       assert False is True

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:114: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_cloud_recover_finds_the_newest_comment_on_page_three_by_number
1 failed in 0.19s
```

Restore: the inverse edit. Restored lines (`cloud_recover.py` 231–240):

```
    cb = _sib("cloud_builder")
    endpoint = "repos/%s/issues/%d/comments?since=%s" % (repo, issue, _iso(since - 1))
    git_env = cb._git_env(env)

    def fetch(page_endpoint):
        code, out = cb._gh(run, ["api", page_endpoint], git_env)
        return out if code == 0 else None
    comments = _sib("gh_pages").read(fetch, endpoint)
    if comments is None or not all(isinstance(c, dict) for c in comments):
        return None, False
```

Green: `1 passed in 0.21s`

## G4 — `vet_slot._read_comments` reads by page number

Neutralization: `plugins/superheroes/lib/vet_slot.py` `_read_comments`, the `fetch` adapter through the `comments is None` raise →

```
    argv = ["gh", "api", "repos/%s/issues/%d/comments" % (repo, pr), "--paginate", "--slurp"]
    pages = _gh_json(run, argv, "comments")
    if not isinstance(pages, list) or not all(isinstance(p, list) for p in pages):
        raise _Refusal("read-failed", "comments: pages are not lists")
    comments = [c for page in pages for c in page]
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_______________ test_vet_slot_reads_every_comment_page_by_number _______________

    def test_vet_slot_reads_every_comment_page_by_number():
        # axis: the vet's comment list past 100 rows; the receipt on a later page unseen behind --paginate --slurp
        rows = [{"id": i, "body": "chat %d" % i, "created_at": "2026-09-25T10:00:00Z", "user": {"login": "advisor"}}
                for i in range(250)]
        proxy = CloudProxy(rows)
>       assert vs._read_comments(proxy, 42, "o/r") == rows
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:125: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/sh-1901/plugins/superheroes/lib/vet_slot.py:280: in _read_comments
    pages = _gh_json(run, argv, "comments")
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/home/user/sh-1901/plugins/superheroes/lib/vet_slot.py:266: in _gh_json
    return json.loads(_gh(run, argv, what))
                      ^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

run = <test_gh_pages.CloudProxy object at 0x7fc5ebfb21e0>
argv = ['gh', 'api', 'repos/o/r/issues/42/comments', '--paginate', '--slurp']
what = 'comments', reason = 'read-failed'

    def _gh(run, argv, what, reason="read-failed"):
        """Run one gh call; a failure is ``reason`` with ``what`` leading the detail."""
        try:
            proc = run(argv, capture_output=True, text=True, timeout=GH_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise _Refusal(reason, "%s: gh call timed out" % what)
        except OSError as exc:
            raise _Refusal(reason, "%s: %s" % (what, exc))
        if proc.returncode != 0:
            out = ((proc.stdout or "") + (proc.stderr or "")).strip()
>           raise _Refusal(reason, "%s: exit %d %s" % (what, proc.returncode, out))
E           vet_slot._Refusal: read-failed

/home/user/sh-1901/plugins/superheroes/lib/vet_slot.py:260: _Refusal
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_vet_slot_reads_every_comment_page_by_number
1 failed in 0.20s
```

Restore: the inverse edit. Restored lines (`vet_slot.py` 278–287):

```
def _read_comments(run, pr, repo):
    def fetch(endpoint):
        try:
            return _gh(run, ["gh", "api", endpoint], "comments")
        except _Refusal:
            return None
    comments = gh_pages.read(fetch, "repos/%s/issues/%d/comments" % (repo, pr))
    if comments is None:
        raise _Refusal("read-failed", "comments: a page could not be read")
    for c in comments:
```

Green: `1 passed in 0.18s`

## G5 — `pr_comment.list_comments` reads by page number

Neutralization: `plugins/superheroes/lib/pr_comment.py` `list_comments`, from `def fetch(endpoint):` through the `raise RuntimeError(...)` →

```
    text = _gh("api", f"repos/{{owner}}/{{repo}}/issues/{pr}/comments", "--paginate")
    dec, idx, raw = json.JSONDecoder(), 0, []
    while idx < len(text):
        while idx < len(text) and text[idx] in " \r\n\t":
            idx += 1
        if idx >= len(text):
            break
        obj, idx = dec.raw_decode(text, idx)
        raw.extend(obj if isinstance(obj, list) else [obj])
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_pr_comment_list_comments_reads_every_page_by_number ___________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x7f5533bb2b40>

    def test_pr_comment_list_comments_reads_every_page_by_number(monkeypatch):
        # axis: the test-pilot comment upsert's list past 100 rows; the existing marker comment on a later page unseen
        rows = [{"id": i, "user": {"login": "u%d" % i}, "body": "chat %d" % i} for i in range(250)]
        proxy = CloudProxy(rows)
        # the fake replaces the module's own `subprocess` name, so the real subprocess module is not patched for other tests
        monkeypatch.setattr(pc, "subprocess", SimpleNamespace(run=proxy))
>       assert pc.list_comments(7) == [{"id": r["id"], "author": r["user"]["login"], "body": r["body"]} for r in rows]
               ^^^^^^^^^^^^^^^^^^^

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:135: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
/home/user/sh-1901/plugins/superheroes/lib/pr_comment.py:201: in list_comments
    text = _gh("api", f"repos/{{owner}}/{{repo}}/issues/{pr}/comments", "--paginate")
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 

inp = None
args = ('api', 'repos/{owner}/{repo}/issues/7/comments', '--paginate')

    def _gh(*args, inp=None):
        r = subprocess.run(["gh", *args], capture_output=True, text=True,
                           timeout=60, input=inp)
        if r.returncode != 0:
>           raise RuntimeError(f"gh {' '.join(args[:3])}... failed: "
                               f"{r.stderr.strip()[:300]}")
E           RuntimeError: gh api repos/{owner}/{repo}/issues/7/comments --paginate... failed: HTTP 403

/home/user/sh-1901/plugins/superheroes/lib/pr_comment.py:191: RuntimeError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_pr_comment_list_comments_reads_every_page_by_number
1 failed in 0.19s
```

Restore: the inverse edit. Restored lines (`pr_comment.py` 200–211):

```
def list_comments(pr):
    def fetch(endpoint):
        try:
            return _gh("api", endpoint)
        except RuntimeError:
            return None
    endpoint = f"repos/{{owner}}/{{repo}}/issues/{pr}/comments"
    raw = gh_pages.read(fetch, endpoint)
    if raw is None or not all(isinstance(c, dict) for c in raw):
        raise RuntimeError(f"gh api {endpoint} failed: a page could not be read")
    return [{"id": c["id"], "author": c["user"]["login"], "body": c["body"]}
            for c in raw]
```

Green: `1 passed in 0.17s`

## G6 — an empty page after a full one ends the read

Neutralization: `plugins/superheroes/lib/gh_pages.py`, inserted after the `return None` of `if not isinstance(page, list):`, before `rows.extend(page)`:

```
        if not page:
            return None
```

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read[100-pages2] _

count = 100, pages = [1, 2]

    @pytest.mark.parametrize("count, pages", [(0, [1]), (99, [1]), (100, [1, 2]), (200, [1, 2, 3]), (250, [1, 2, 3])])
    def test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read(count, pages):
        # axis: the end of a list; exactly 100 or 200 rows treated as unfinished (failing) or read past the empty page
        rows = [{"n": i} for i in range(count)]
        fetch = recording_fetch(rows)
>       assert gh_pages.read(fetch, "repos/o/r/x") == rows
E       AssertionError: assert None == [{'n': 0}, {'n': 1}, {'n': 2}, {'n': 3}, {'n': 4}, {'n': 5}, ...]
E        +  where None = <function read at 0x7f63969c3100>(<function recording_fetch.<locals>.fetch at 0x7f6396187ce0>, 'repos/o/r/x')
E        +    where <function read at 0x7f63969c3100> = gh_pages.read

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:192: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read[100-pages2]
1 failed in 0.25s
```

Restore: the two inserted lines removed. Restored lines (`gh_pages.py` 36–41):

```
        if not isinstance(page, list):
            return None
        rows.extend(page)
        # axis: the first page with fewer than a full page's rows (an empty one included) ends the read — see bite-proof record wo1_1901_gh_pages
        if len(page) < PAGE_ROWS:
            return rows
```

Green: `1 passed in 0.18s`

## G7 — a failed page read fails the whole read

Neutralization: `gh_pages.py` line 30, `page = None if out is None else json.loads(out)` → `page = [] if out is None else json.loads(out)`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
___________ test_a_page_that_fails_makes_the_whole_read_unavailable ____________

    def test_a_page_that_fails_makes_the_whole_read_unavailable():
        # axis: the complete-or-absent list; a failed page returning the rows read so far as if they were the whole list
        rows = [{"n": i} for i in range(250)]
        for failed in (1, 2, 3):
            fetch = recording_fetch(rows, override={failed: None})
>           assert gh_pages.read(fetch, "repos/o/r/x") is None
E           AssertionError: assert [] is None
E            +  where [] = <function read at 0x7f1a59747100>(<function recording_fetch.<locals>.fetch at 0x7f1a59243ce0>, 'repos/o/r/x')
E            +    where <function read at 0x7f1a59747100> = gh_pages.read

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:201: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_a_page_that_fails_makes_the_whole_read_unavailable
1 failed in 0.20s
```

Restore: the inverse edit. Restored lines (`gh_pages.py` 29–32):

```
        try:
            page = None if out is None else json.loads(out)
        except ValueError:
            page = None
```

Green: `1 passed in 0.18s`

## G8 — the census

Neutralization: `plugins/superheroes/lib/cloud_cleanup.py` line 186, in `_pages`'s fetch: `_gh(run, ["api", endpoint], env)` → `_gh(run, ["api", "--paginate", endpoint], env)`.

Red:

```
F                                                                        [100%]
=================================== FAILURES ===================================
_ test_the_only_paginate_flag_left_under_lib_is_gits_pager_flag_and_the_cloud_recipe_pages_by_number _

    def test_the_only_paginate_flag_left_under_lib_is_gits_pager_flag_and_the_cloud_recipe_pages_by_number():
        # axis: the census; any lib module reading a GitHub list through gh's paginate flag, or a cloud recipe that names it
>       assert _files_holding_the_flag() == {"worktree_guard.py"}
E       AssertionError: assert {'cloud_clean...ree_guard.py'} == {'worktree_guard.py'}
E         
E         Extra items in the left set:
E         'cloud_cleanup.py'
E         Use -v to get more diff

/home/user/sh-1901/plugins/superheroes/lib/tests/test_gh_pages.py:273: AssertionError
=========================== short test summary info ============================
FAILED plugins/superheroes/lib/tests/test_gh_pages.py::test_the_only_paginate_flag_left_under_lib_is_gits_pager_flag_and_the_cloud_recipe_pages_by_number
1 failed in 1.78s
```

Restore: the inverse edit. Restored lines (`cloud_cleanup.py` 185–189):

```
    def fetch(endpoint):
        code, out, _ = _gh(run, ["api", endpoint], env)
        return out if code == 0 else None
    found = _sib("gh_pages").read(fetch, path)
    return found if found is not None and all(isinstance(i, dict) for i in found) else None
```

Green: `1 passed in 1.70s`
