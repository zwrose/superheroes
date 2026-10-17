"""Conformance: every GitHub REST list read under lib asks for pages by number (#1901). The cloud session's
proxy refuses gh's paginate flag past page 1, so each moved read is run against one fake of that proxy, and the
shared reader's own edges are pinned once, at `gh_pages.read`. Nothing here runs gh, touches the network or reads
the real home directory."""
import ast
import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

_LIB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import cloud_cleanup as CC  # noqa: E402
import cloud_parked as CP  # noqa: E402
import cloud_recover as CR  # noqa: E402
import gh_pages  # noqa: E402
import pr_comment as pc  # noqa: E402
import vet_slot as vs  # noqa: E402

_PAGE_RE = re.compile(r"^repos/[^?]+\?(?:[^?]*&)?per_page=100&page=(\d+)$")


class CloudProxy:
    """A fake `run`/`subprocess.run` that answers `gh api <endpoint>` as the cloud session's GitHub proxy does.
    An argv with --paginate prints page 1 of the list and exits 1 with `HTTP 403` (real gh, when the proxy refuses
    the next-page repositories/ link); an endpoint naming repositories/ exits 1; an endpoint
    `repos/...?...per_page=100&page=N` (one per_page only) serves rows (N-1)*100 .. N*100 of `rows`; anything
    else exits 2. `fail_pages` are page numbers answered with exit 1. Every argv is recorded."""

    def __init__(self, rows, fail_pages=()):
        self.rows, self.fail_pages, self.calls = rows, set(fail_pages), []

    def __call__(self, argv, **_kw):
        argv = list(argv)
        self.calls.append(argv)
        endpoint = next((a for a in argv[2:] if not a.startswith("-")), "")
        if "--paginate" in argv:
            return subprocess.CompletedProcess(argv, 1, json.dumps(self.rows[:100]), "HTTP 403")
        if "repositories/" in endpoint:
            return subprocess.CompletedProcess(argv, 1, "", "HTTP 403")
        found = _PAGE_RE.match(endpoint)
        if argv[:2] == ["gh", "api"] and found and endpoint.count("per_page=") == 1:
            number = int(found.group(1))
            if number in self.fail_pages:
                return subprocess.CompletedProcess(argv, 1, "", "HTTP 500")
            return subprocess.CompletedProcess(argv, 0, json.dumps(self.rows[(number - 1) * 100:number * 100]), "")
        return subprocess.CompletedProcess(argv, 2, "", "unrouted")

    def pages(self):
        """The page numbers asked for, in order."""
        asked = (_PAGE_RE.match(next((a for a in c[2:] if not a.startswith("-")), "")) for c in self.calls)
        return [int(m.group(1)) for m in asked if m]

    def paginated(self):
        return [c for c in self.calls if "--paginate" in c]


def _asked_by_number(proxy, count=3):
    assert proxy.pages() == list(range(1, count + 1)), proxy.calls
    assert proxy.paginated() == [], proxy.calls


# --- one cloud-shape test per moved read (three pages: 250 rows) ---

def test_cloud_cleanup_reads_branches_and_open_prs_page_by_number():
    # axis: cleanup's branch and open-PR lists past 100 rows; --paginate refused by the proxy would make every branch unreadable
    rows = [{"name": "b%03d" % i, "base": {"ref": "main"} if i < 249 else {"ref": "feature"}} for i in range(250)]
    proxy = CloudProxy(rows)
    assert CC._pages(proxy, "repos/o/r/branches", {}) == rows
    _asked_by_number(proxy)
    proxy = CloudProxy(rows)
    assert CC._listing("o/r", {}, proxy) == [r["name"] for r in rows]
    _asked_by_number(proxy)
    proxy = CloudProxy(rows)
    assert CC._in_use("o/r", "feature", {}, proxy) is True  # the last row, on page 3, names the branch as its base
    _asked_by_number(proxy)


def test_cloud_cleanup_pages_are_absent_when_a_middle_page_fails():
    # axis: cleanup's complete-or-absent list (risk area: destroying work); a failed page 2 read as the end of the list
    rows = [{"name": "b%03d" % i} for i in range(250)]
    proxy = CloudProxy(rows, fail_pages={2})
    assert CC._pages(proxy, "repos/o/r/branches", {}) is None
    assert CC._listing("o/r", {}, CloudProxy(rows, fail_pages={2})) is None
    assert CC._in_use("o/r", "feature", {}, CloudProxy(rows, fail_pages={2})) is None
    assert proxy.pages() == [1, 2]


def test_cloud_parked_reads_every_comment_page_by_number():
    # axis: the parked-PR comment list past 100 rows; --paginate refused by the proxy, or a first-page read
    rows = [{"id": i, "body": "chat %d" % i} for i in range(250)]
    proxy = CloudProxy(rows)
    assert CP._comments("o/r", 7, {}, proxy) == rows
    _asked_by_number(proxy)


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
    assert read is True
    assert found == {"commentId": 230, "url": "https://x/c/230", "parsed": True, "createdAt": "2026-10-12T09:00:00Z"}
    _asked_by_number(proxy)
    assert all("/issues/17/comments?since=2026-10-11T23:59:59Z&per_page=100&page=" in c[2] for c in proxy.calls)


def test_vet_slot_reads_every_comment_page_by_number():
    # axis: the vet's comment list past 100 rows; the receipt on a later page unseen behind --paginate --slurp
    rows = [{"id": i, "body": "chat %d" % i, "created_at": "2026-09-25T10:00:00Z", "user": {"login": "advisor"}}
            for i in range(250)]
    proxy = CloudProxy(rows)
    assert vs._read_comments(proxy, 42, "o/r") == rows
    _asked_by_number(proxy)


def test_pr_comment_list_comments_reads_every_page_by_number(monkeypatch):
    # axis: the test-pilot comment upsert's list past 100 rows; the existing marker comment on a later page unseen
    rows = [{"id": i, "user": {"login": "u%d" % i}, "body": "chat %d" % i} for i in range(250)]
    proxy = CloudProxy(rows)
    # the fake replaces the module's own `subprocess` name, so the real subprocess module is not patched for other tests
    monkeypatch.setattr(pc, "subprocess", SimpleNamespace(run=proxy))
    assert pc.list_comments(7) == [{"id": r["id"], "author": r["user"]["login"], "body": r["body"]} for r in rows]
    _asked_by_number(proxy)
    assert all(c[2].startswith("repos/{owner}/{repo}/issues/7/comments?") for c in proxy.calls)


def test_each_moved_read_keeps_its_failure_face_when_a_page_fails(monkeypatch):
    # axis: per caller failure faces (E7/E8); a failed page 2 returning the rows read so far, or a different face
    rows = [{"id": i, "body": "chat", "created_at": "2026-09-25T10:00:00Z", "user": {"login": "a"}} for i in range(250)]
    assert CC._pages(CloudProxy(rows, fail_pages={2}), "repos/o/r/branches", {}) is None
    assert CP._comments("o/r", 7, {}, CloudProxy(rows, fail_pages={2})) is None
    assert CR._newest_comment("o/r", 17, 0, {}, CloudProxy(rows, fail_pages={2}), lambda body: True) == (None, False)
    with pytest.raises(vs._Refusal) as refusal:
        vs._read_comments(CloudProxy(rows, fail_pages={2}), 42, "o/r")
    assert (refusal.value.reason, refusal.value.detail) == ("read-failed", "comments: a page could not be read")
    monkeypatch.setattr(pc, "subprocess", SimpleNamespace(run=CloudProxy(rows, fail_pages={2})))
    with pytest.raises(RuntimeError, match="a page could not be read"):
        pc.list_comments(7)
    # a row that is not an object: cleanup, parked and recover read it as unreadable, vet_slot refuses it, pr_comment raises
    odd = rows[:3] + ["not a dict"]
    assert CC._pages(CloudProxy(odd), "repos/o/r/branches", {}) is None
    assert CP._comments("o/r", 7, {}, CloudProxy(odd)) is None
    assert CR._newest_comment("o/r", 17, 0, {}, CloudProxy(odd), lambda body: True) == (None, False)
    with pytest.raises(vs._Refusal) as refusal:
        vs._read_comments(CloudProxy(odd), 42, "o/r")
    assert refusal.value.reason == "read-failed" and "a comment lacks" in refusal.value.detail
    monkeypatch.setattr(pc, "subprocess", SimpleNamespace(run=CloudProxy(odd)))
    with pytest.raises(RuntimeError, match="a page could not be read"):
        pc.list_comments(7)


# --- the shared reader's edges, once ---

def recording_fetch(rows, key=None, override=None):
    """A fetch over `rows` served 100 a page by page number; `override` maps a page number to the text it
    returns (None is a failed call). `seen` holds the endpoints asked for, in order."""
    seen = []

    def fetch(endpoint):
        seen.append(endpoint)
        number = int(endpoint.rsplit("page=", 1)[1])
        if override and number in override:
            return override[number]
        piece = rows[(number - 1) * 100:number * 100]
        return json.dumps(piece if key is None else {"total_count": len(rows), key: piece})
    fetch.seen = seen
    return fetch


def numbers(fetch):
    return [int(e.rsplit("page=", 1)[1]) for e in fetch.seen]


@pytest.mark.parametrize("count, pages", [(0, [1]), (99, [1]), (100, [1, 2]), (200, [1, 2, 3]), (250, [1, 2, 3])])
def test_a_full_last_page_is_followed_by_an_empty_page_that_ends_the_read(count, pages):
    # axis: the end of a list; exactly 100 or 200 rows treated as unfinished (failing) or read past the empty page
    rows = [{"n": i} for i in range(count)]
    fetch = recording_fetch(rows)
    assert gh_pages.read(fetch, "repos/o/r/x") == rows
    assert numbers(fetch) == pages


def test_a_page_that_fails_makes_the_whole_read_unavailable():
    # axis: the complete-or-absent list; a failed page returning the rows read so far as if they were the whole list
    rows = [{"n": i} for i in range(250)]
    for failed in (1, 2, 3):
        fetch = recording_fetch(rows, override={failed: None})
        assert gh_pages.read(fetch, "repos/o/r/x") is None
        assert numbers(fetch) == list(range(1, failed + 1))


def test_a_page_that_is_not_json_or_not_a_list_makes_the_read_unavailable():
    # axis: page shape; a page that is not JSON, or an object where a list belongs, skipped as an empty page that ends the read
    rows = [{"n": i} for i in range(250)]
    for page in (1, 2):
        for text in ("not json", "{broken", '{"message": "Not Found"}', "null", '"x"', ""):
            assert gh_pages.read(recording_fetch(rows, override={page: text}), "repos/o/r/x") is None, (page, text)


def test_a_key_names_the_list_inside_an_object_page():
    # axis: the keyed form (check runs); an object page without a list under the key read as an empty page
    rows = [{"n": i} for i in range(250)]
    fetch = recording_fetch(rows, key="check_runs")
    assert gh_pages.read(fetch, "repos/o/r/x", key="check_runs") == rows
    assert numbers(fetch) == [1, 2, 3]
    for text in ('{"total_count": 0}', '{"check_runs": "x"}', '{"check_runs": {"a": 1}}', "[]", "null"):
        assert gh_pages.read(recording_fetch(rows, override={1: text}), "repos/o/r/x", key="check_runs") is None, text
        assert gh_pages.read(recording_fetch(rows, key="check_runs", override={2: text}), "repos/o/r/x",
                             key="check_runs") is None, text


def test_a_list_that_never_ends_fails_the_read_after_the_page_cap(monkeypatch):
    # axis: the page cap; a list that never ends returning the rows read so far, or being asked for without end
    assert gh_pages.MAX_PAGES == 1000 and gh_pages.PAGE_ROWS == 100
    monkeypatch.setattr(gh_pages, "MAX_PAGES", 4)
    seen = []

    def endless(endpoint):
        seen.append(endpoint)
        return json.dumps([{"n": 1}] * 100)
    assert gh_pages.read(endless, "repos/o/r/x") is None
    assert len(seen) == 4


def test_the_page_query_joins_a_path_that_already_has_one_with_an_ampersand():
    # axis: the page request's query; a second ? appended to a path that already carries a query
    seen = []

    def fetch(endpoint):
        seen.append(endpoint)
        return "[]"
    assert gh_pages.read(fetch, "repos/o/r/x?state=open") == []
    assert gh_pages.read(fetch, "repos/o/r/y") == []
    assert seen == ["repos/o/r/x?state=open&per_page=100&page=1", "repos/o/r/y?per_page=100&page=1"]


# --- the census: no GitHub list read left on the paginate flag ---

_PLUGIN = os.path.abspath(os.path.join(_LIB, ".."))


def _files_holding_the_flag():
    held = set()
    for root, dirs, files in os.walk(_LIB):
        dirs[:] = [d for d in dirs if d != "tests" and d != "__pycache__"]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            if any(isinstance(n, ast.Constant) and isinstance(n.value, str) and "--paginate" in n.value
                   for n in ast.walk(tree)):
                held.add(os.path.relpath(path, _LIB).replace(os.sep, "/"))
    return held


def test_the_only_paginate_flag_left_under_lib_is_gits_pager_flag_and_the_cloud_recipe_pages_by_number():
    # axis: the census; any lib module reading a GitHub list through gh's paginate flag, or a cloud recipe that names it
    assert _files_holding_the_flag() == {"worktree_guard.py"}
    with open(os.path.join(_LIB, "worktree_guard.py"), encoding="utf-8") as fh:
        assert "--paginate" in fh.read()  # the exclusion is real: git's pager flag, so it cannot go stale silently
    with open(os.path.join(_PLUGIN, "skills", "workhorse", "reference", "cloud.md"), encoding="utf-8") as fh:
        recipes = fh.read()
    assert "--paginate" not in recipes
    assert "per_page=100&page=" in recipes
